"""
FastAPI app. Design rule: the AI perceives and talks; deterministic code decides every rupee.

Customer routes (/claims/...) never return the ceiling, the pivots or internal assumptions. The adjuster route
(/adjuster/{id}) returns detections, evidence per line and the assumption ledger; it is labelled demo-only and has no
authentication. Neither route returns the ceiling.
"""
import hashlib
import io
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from autosettle_engine import config as C, engine as E, guidance as G, rationale as R
from autosettle_engine.estimate import estimate_from_evidence
from autosettle_engine.dispute import TERMINAL, ClaimSession
from autosettle_vision.claim import POLICIES, RC, customer_text, decision_text, engine_vision, get_policy

from . import attack_runner, chat as CHAT, plate_blur
from .intents import classify
from . import runtime as rt
from .backends import LiveVision, ReplayMiss, ReplayVision
from .scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PHOTOS = 12
MAX_VIDEO_BYTES = 60 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_CLAIMS = 200
RATE_LIMIT = 90                 # requests per claim per 60 s
MAX_MESSAGE_CHARS = 1000
AMOUNT = re.compile(r"(?:\u20b9|rs\.?|inr)\s*([0-9][0-9,]*)|\b([0-9][0-9,]{2,})\b", re.I)
REASON_TEXT = {
    "integrity": "A photo or video failed an integrity check",
    "plate_mismatch": "The number plate does not match the policy",
    "structural_or_safety_damage": "Heavy or structural damage is suspected; a photo cannot price hidden damage",
    "info_incomplete_after": "The photos were still not enough after the allowed requests for more",
    "low_conf_severe": "A severe call was made at low confidence",
    "unpriceable": "A damaged part has no price basis in the rate card",
    "gross_loss_at_or_above_surveyor_limit": "The gross loss reaches the surveyor threshold",
    "possible_constructive_total_loss": "The gross loss is close to the insured value (possible total loss)",
    "gross_loss_at_or_above_review_threshold": "The gross loss reaches the human-review threshold",
}
MISSING_TEXT = {"plate_verified": "plate not verified against the policy", "parts_identified": "a damaged panel was not outlined with enough confidence",
                "damage_identified": "damage class, confidence or severity missing", "coverage_ok": "damage not located on any panel",
                "integrity_ok": "integrity flag raised", "policy_record": "no policy record"}
VIDEO_SAMPLES = {
    "synthetic_walkaround": "A zoom and pan over one photo. Every keyframe agrees, so the offer matches the single photo.",
    "synthetic_walkaround_close": "The same clip zoomed closer. One panel shows damage in a single keyframe only, so the system asks for a clearer view instead of guessing.",
}
MEDIA = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
CUSTOMER_LINE_KEYS = ("part_class", "damage_class", "severity", "action", "part_mrp", "dep_rate", "dep_amount", "part_net",
                      "labour", "paint_gross", "paint_dep", "paint_net", "line_total", "dep_basis", "paint_basis")
NEED_TEXT = {"plate_verified": "A clear number plate: type it, or add a photo of the plate.",
             "parts_identified": "A wider photo that shows each damaged panel in full.",
             "damage_identified": "A closer, well-lit photo of each damaged area.",
             "coverage_ok": "A photo that shows where on the car the damage is.",
             "integrity_ok": "Original photos straight from your camera."}
CAPTURE_GUIDE = [
    {"id": "plate", "title": "Number plate", "text": "Stand square to the plate so all characters are sharp."},
    {"id": "front", "title": "Front three-quarter", "text": "Step back so the whole front, both corners and the bonnet are in frame."},
    {"id": "side", "title": "Side", "text": "The full side from wheel to wheel, taken straight on."},
    {"id": "rear", "title": "Rear three-quarter", "text": "The whole rear with both lamps and the boot lid."},
    {"id": "close", "title": "Close-up of each damaged area", "text": "Close enough to see the dent or crack, in daylight, no flash."},
]


@dataclass
class Settings:
    replay: bool = False
    qwen: bool = True
    ui: str = "public"
    runtime: Path = ROOT / "final" / "runtime"
    demo_photos: tuple = ()
    fresh_seen: bool = False
    video: bool = True      # on only because every video test passes (Stage B gate); `--video off` turns it off
    preload: bool = False   # start loading the language model in the background at server start (the command line sets this)


class Claim:
    def __init__(self, cid, policy, replay_key=None):
        self.id, self.policy, self.replay_key = cid, policy, replay_key
        self.session = ClaimSession(policy, RC)
        self.photos = []                # dicts: path, name, media, width, height
        self.plate_text, self.plate_source = None, None
        self.vision = None              # full vision dict from the backend (adjuster view)
        self.ev = None                  # engine contract
        self.message_text, self.message_source = None, None
        self.created = time.time()
        self.hits = []
        self.lock = threading.RLock()
        self.assessed = False
        self.chat = []
        self.recorded = False           # the vision output came from replay data, whatever mode the server is in
        self.silent = False             # a data claim made by the landing page: never loads the language model
        self.turns = []
        self.video_view = None


def sniff(data):
    """Decode check: returns (format, width, height) or raises ValueError."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("image is larger than 10 MB")
    try:
        im = Image.open(io.BytesIO(data))
        fmt, (w, h) = im.format, im.size
        if fmt not in MEDIA:
            raise ValueError("only JPEG, PNG or WebP images are accepted")
        if w * h > MAX_PIXELS:
            raise ValueError("image has too many pixels")
        im.verify()
        arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            raise ValueError("image could not be decoded")
        return fmt, w, h
    except ValueError:
        raise
    except Exception:
        raise ValueError("file is not a readable image")


def create_app(settings=None, vision=None, qwen=None):
    cfg = settings or Settings()
    runtime = Path(cfg.runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    replay = ReplayVision(Path(__file__).with_name("replay_data"))
    backend = vision or (replay if cfg.replay else LiveVision(__import__("tempfile").mkdtemp() if cfg.fresh_seen else runtime))
    qstate = {"model": qwen, "tried": qwen is not None}
    claims = {}
    blur_cache = {}
    glock = threading.Lock()
    app = FastAPI(title="Aequour", docs_url="/api-docs", redoc_url=None)
    mode_label = "REPLAY" if backend.mode == "replay" else "LIVE"
    build_info = rt.read_build(cfg.ui)
    gpu_cache = {}

    @app.middleware("http")
    async def cache_headers(request, call_next):
        """Hashed build files never change; every page, API and JSON response is never cached, so a stale tab cannot happen."""
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable" if request.url.path.startswith("/assets/") else "no-store"
        return resp

    # ------------------------------------------------------------------ helpers
    qlock = threading.Lock()

    def get_qwen():
        """Loads the language model once. Concurrent callers wait for the load instead of seeing "model off"."""
        if not cfg.qwen:
            return None
        with qlock:
            if not qstate["tried"]:
                qstate["tried"] = True
                qstate["loading"] = True
                try:
                    reason = rt.gpu_memory_problem()
                    if reason:
                        raise RuntimeError(reason)
                    from autosettle_vision.qwen import QwenVL
                    qstate["model"] = QwenVL()
                    qstate["load_s"], qstate["vram_gb"] = qstate["model"].load_s, qstate["model"].vram_gb
                except Exception as e:      # no GPU, out of memory, model missing: fall back to templates
                    qstate["error"] = str(e)[:200]
                finally:
                    qstate["loading"] = False
            return qstate["model"]

    def qwen_status():
        """off | loading | ready | error. The page and /health read this; the chat uses the model only when it is ready."""
        if qstate["model"] is not None:
            return "ready"
        if qstate.get("error"):
            return "error"
        if qstate.get("loading") or (cfg.preload and cfg.qwen and not qstate["tried"]):
            return "loading"
        return "off"

    if cfg.preload and cfg.qwen and qwen is None:
        threading.Thread(target=get_qwen, name="qwen-load", daemon=True).start()

    def need(cid):
        c = claims.get(cid)
        if c is None:
            raise HTTPException(404, "unknown claim")
        now = time.time()
        c.hits = [t for t in c.hits if now - t < 60] + [now]
        if len(c.hits) > RATE_LIMIT:
            raise HTTPException(429, "too many requests for this claim; slow down")
        return c

    def closed(c):
        if c.session.state in TERMINAL:
            raise HTTPException(409, f"this claim is closed ({c.session.state})")

    def persist(c):
        try:
            (runtime / f"{c.id}.json").write_text(json.dumps({"claim_id": c.id, "mode": claim_mode(c), "log": c.session.log,
                                                              "verified": ClaimSession.verify_log(c.session.log)}, default=str))
        except OSError:
            pass

    def stated_amount(text):
        m = AMOUNT.search(text or "")
        if not m:
            return None
        try:
            return int((m.group(1) or m.group(2)).replace(",", ""))
        except ValueError:
            return None

    def add_turn(c, who, text, wording=None, detail=None):
        """One line of the conversation transcript, tied to the audit entry written just before it."""
        log, res = c.session.log, c.session.result
        c.turns.append({"n": len(c.turns) + 1, "from": who, "text": text, "wording": wording, "state": c.session.state,
                        "decision": res["decision"] if res else None, "offer": c.session.current_offer,
                        "audit_seq": log[-1]["seq"] if log else None, "audit_hash": log[-1]["hash"][:12] if log else None,
                        **({"detail": detail} if detail else {})})

    def fixed(text, kind, intent, why="not_for_model"):
        """A reply that always uses fixed wording (money, abuse, injection): never sent to the model."""
        return text, kind, {"intent": intent, "source": "template", "reason": why, "reason_text": CHAT.REASONS[why], "facts": None,
                            "model_raw": None, "checks": [], "rejected": None}, "template"

    def reply_for(c, flags, amount, text):
        """Returns (reply, kind, detail, wording). Code decides the intent and picks the facts; the model, when it is ready, only phrases
        the reply and code checks it; anything doubtful uses the template. Money, abuse and injection never reach the model.
        No path changes an amount or mentions the upper bound."""
        if "abusive" in flags or "legal_threat" in flags:
            return fixed(G.message_reply("passed_to_human"), "passed_to_human", "escalation")
        s = c.session
        open_offer = s.state in ("OFFERED", "UPDATED_OFFER")
        intent, _ = classify(text)
        if intent == "amount_named" and open_offer:
            again = sum(1 for t in c.turns[:-1] if t["from"] == "customer" and (t.get("detail") or {}).get("stated_amount") is not None)
            return fixed(G.message_reply("amount_named_no_change", R.money(s.current_offer), bool(again)), "amount_named_no_change", "amount_named")
        if "injection_suspected" in flags:
            return fixed(G.message_reply("declined"), "declined", "instruction_in_message")
        if intent == "amount_named":
            intent = "other"
        ceiling = s.result.get("ceiling") if s.result else None
        r = CHAT.reply(c, intent, text, qwen_status, lambda: qstate["model"], ceiling=ceiling)
        detail = {k: r.get(k) for k in ("intent", "source", "reason", "reason_text", "facts", "model_raw", "checks", "rejected")}
        detail["final"] = r["text"]
        return r["text"], "chat_" + intent, detail, ("model, checked" if r["source"] == "model" else "template")

    def next_step_of(c):
        """The Next step text of the latest system reply, so the offer card shows exactly what the chat says."""
        for t in reversed(c.turns):
            if t["from"] == "system":
                m = re.search(r"Next step:\s*(.+)\Z", t["text"], re.S)
                if m:
                    return m.group(1).strip()
        return None

    def do_message(c, text):
        flags = c.session.message(text)
        amount = stated_amount(text)
        c.chat.append({"from": "customer", "text": text[:MAX_MESSAGE_CHARS]})
        add_turn(c, "customer", text[:MAX_MESSAGE_CHARS], detail={"stated_amount": amount, "flags": flags})
        reply, kind, detail, wording = reply_for(c, flags, amount, text)
        c.session._log("reply", {"kind": kind, "stated_amount": amount, "intent": detail.get("intent"), "source": detail.get("source"),
                                 "reason": detail.get("reason")})
        c.chat.append({"from": "system", "text": reply})
        add_turn(c, "system", reply, wording=wording, detail={"kind": kind, **detail})
        return reply, flags

    def clean_quote(q):
        if not isinstance(q, dict) or not isinstance(q.get("lines"), list) or len(q["lines"]) > 40:
            raise HTTPException(422, "quote must be an object with a list of at most 40 lines")
        clean = []
        for ln in q["lines"]:
            try:
                t = ln.get("type")
                if t not in ("part", "labour", "paint"):
                    t = "other"
                clean.append({"description": str(ln.get("description", ""))[:80], "type": t,
                              "qty": max(1, int(ln.get("qty", 1))), "unit_price": max(0, int(ln.get("unit_price", 0))),
                              "total": max(0, int(ln.get("total", ln.get("unit_price", 0))))})
            except (TypeError, ValueError, AttributeError):
                raise HTTPException(422, "each quote line needs numeric qty, unit_price and total")
        return {"lines": clean, "gst_percent": q.get("gst_percent"), "grand_total": sum(x["total"] for x in clean)}

    def do_quote(c, quote_obj, source):
        before = c.session.current_offer
        chk = c.session.dispute(quote_obj)
        qv = quote_view(chk or {})
        total = sum(x["total"] for x in quote_obj["lines"])
        add_turn(c, "customer", f"Sent an itemised garage quote ({len(quote_obj['lines'])} lines, lines total {R.money(total)}).",
                 detail={"quote_source": source, "quote_lines": [{"description": x["description"], "type": x["type"], "total": x["total"]}
                                                                  for x in quote_obj["lines"]]})
        after = c.session.current_offer
        moved = bool(after is not None and before is not None and after > before)
        said = G.quote_reply(moved, R.money(before) if before is not None else "", R.money(after) if after is not None else "",
                             [(r["description"], r["verdict"]) for r in qv["lines"]], C.MAX_EVIDENCE_ROUNDS - c.session.evidence_rounds, qv.get("note"))
        add_turn(c, "system", said, wording="template", detail={"verdicts": qv["lines"], "moved": moved})
        return chk

    def find_demo_photo(rec):
        for d in list(cfg.demo_photos) + [Path(os.environ.get("AEQUOUR_DEV_PHOTOS", ROOT / "test_photos" / "commons")),
                                           ROOT / "test_photos" / "commons"]:
            p = Path(d) / rec["source_file"]
            if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == rec["sha256"]:
                return p
        return None

    def build_video_view(c, v, rec=None):
        """What the Video tab shows: keyframes with their usability scores, the continuity numbers, and the damage seen
        across keyframes (an entity seen in only one keyframe is shown as such, never silently dropped)."""
        from autosettle_vision import synthetic_clip as SC, video as V, video_integrity as VI
        vid = v.get("video", {})
        scores = vid.get("keyframe_scores", [])
        thumbs = vid.get("thumbnails")
        if thumbs is None and rec is not None:
            thumbs = [None] * len(scores)
            p = find_demo_photo(rec)
            if p is not None:
                img = cv2.imread(str(p))
                boxes = plate_blur.DEMO_PLATE_BOXES.get(rec["sha256"])
                if img is not None:
                    if boxes:
                        img = plate_blur.blur_boxes(img, boxes)           # blur first: the crops then carry the blur
                    fr = SC.frames(img, rec.get("variant", "wide"))
                    thumbs = V.thumbnails([(str(k), fr[min(len(fr) - 1, sc["frame"])]) for k, sc in enumerate(scores)])
        thumbs = thumbs or [None] * len(scores)
        names = vid.get("keyframe_names") or []
        by = v.get("findings_by_image", {})
        ents = {}
        for k, name in enumerate(names):
            for f in by.get(name, []):
                if f.get("part_class") in (None, "unassigned") or f.get("severity") is None and f.get("damage_class") is None:
                    continue
                e = ents.setdefault((f["part_class"], f.get("damage_class")), {"part_class": f["part_class"], "damage_class": f.get("damage_class"),
                                                                              "keyframes": [], "best_conf": 0.0, "severity": None})
                e["keyframes"].append(k)
                e["best_conf"] = max(e["best_conf"], f.get("damage_conf") or 0.0)
                rank = {"minor": 0, "moderate": 1, "severe": 2}
                if f.get("severity") and (e["severity"] is None or rank[f["severity"]] > rank[e["severity"]]):
                    e["severity"] = f["severity"]
        entities = []
        for e in ents.values():
            n = len(set(e["keyframes"]))
            entities.append({**e, "keyframes": sorted(set(e["keyframes"])), "seen_in": n, "of": len(names),
                             "best_conf": round(e["best_conf"], 3), "status": "supported" if n >= 2 else "single keyframe only"})
        entities.sort(key=lambda e: (-e["seen_in"], e["part_class"]))
        count = {k: 0 for k in range(len(names))}
        for e in entities:
            for k in e["keyframes"]:
                count[k] += 1
        kfs = [{"index": k, "name": names[k] if k < len(names) else None, **(scores[k] if k < len(scores) else {}),
                "thumbnail": thumbs[k] if k < len(thumbs) else None, "findings": count.get(k, 0)} for k in range(len(scores))]
        breaks = vid.get("continuity_breaks", [])
        hard, unver = vid.get("continuity_hard_cuts", []), vid.get("continuity_unverified", breaks if breaks else [])
        name, words = vid.get("continuity_outcome") or (("continuous", "One continuous take: no breaks") if not breaks else
                                                         ("unverified", "Could not confirm one continuous take: a person will check"))
        return {"synthetic": bool(vid.get("synthetic")), "recorded": rec is not None,
                "label": (rec or {}).get("label") or "uploaded clip", "seconds": vid.get("seconds"), "fps": vid.get("fps"),
                "frames": vid.get("frames"), "candidates": vid.get("candidates"), "usable": vid.get("usable"),
                "dropped_blur_or_dark": vid.get("dropped_blur_or_dark"), "keyframes": kfs,
                "filter": {"sharpness_min": vid.get("blur_min", V.BLUR_MIN_VIDEO), "brightness_min": vid.get("dark_min", V.DARK_MIN_VIDEO)},
                "continuity": {"frames_checked": vid.get("continuity_frames_checked"), "lowest_inliers": vid.get("continuity_lowest"),
                               "median_inliers": vid.get("continuity_median"), "required_inliers": vid.get("min_inliers"),
                               "breaks": breaks, "verdict": "continuous" if not breaks else "not continuous",
                               "outcome": name, "outcome_words": words, "hard_cuts": hard, "unverified": unver,
                               "max_appearance": vid.get("continuity_max_appearance"), "median_appearance": vid.get("continuity_median_appearance"),
                               "appearance_cut": VI.APPEARANCE_CUT},
                "entities": entities,
                "note": "Tested on synthetic clips. Two real night-time phone clips were run once each (n = 2): a first test, not a measurement."}

    def add_photo(c, data, filename):
        try:
            fmt, w, h = sniff(data)
        except ValueError as e:
            raise HTTPException(422, str(e))
        if len(c.photos) >= MAX_PHOTOS:
            raise HTTPException(422, f"at most {MAX_PHOTOS} photos per claim")
        d = runtime / c.id
        d.mkdir(parents=True, exist_ok=True)
        name = f"p{len(c.photos)}{EXT[fmt]}"
        (d / name).write_bytes(data)
        c.photos.append({"path": d / name, "name": name, "media": MEDIA[fmt], "width": w, "height": h,
                         "sha256": hashlib.sha256(data).hexdigest()})
        return c.photos[-1]

    def run_vision(c):
        try:
            if c.replay_key and not c.photos:      # scenario without a local photo: recorded output only
                from .backends import remap
                rec = replay.lookup(c.replay_key)
                c.recorded = True
                return remap(rec["vision"], (rec["vision"].get("images") or ["photo"])[0], c.id)
            return backend.run([p["path"] for p in c.photos], c.id)
        except ReplayMiss as e:
            raise HTTPException(422, str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(503, f"the vision pipeline failed ({type(e).__name__}); try replay mode (--replay)")

    def assess(c, v=None):
        if v is None and not c.photos and not c.replay_key:
            raise HTTPException(422, "add at least one photo first")
        if c.session.state != "INTAKE":
            raise HTTPException(409, f"cannot assess in state {c.session.state}")
        v = v if v is not None else run_vision(c)
        ev = engine_vision(v)
        if c.plate_text:
            ev["plate_read"] = c.plate_text
        c.vision, c.ev = v, ev
        res = c.session.submit(ev)
        text, used, viol = customer_text(res, c.policy, ev, get_qwen() if (res["decision"] == "OFFER" and not c.silent) else None)
        c.session._log("customer_message", {"model_wording_used": used, "violations": [str(x) for x in viol]})
        if res["decision"] == "OFFER":
            text = G.attach(text, G.offer_step())          # the model never writes this line; code adds it afterwards
            c.message_text, c.message_source = text, ("model, checked" if used else "template")
        else:
            c.message_text, c.message_source = decision_text(res, v.get("flags", [])), "template"
        c.assessed = True
        add_turn(c, "system", c.message_text, wording=c.message_source, detail={"event": "assessment"})
        persist(c)
        return res

    def photo_urls(c):
        return [{"index": i, "url": f"/claims/{c.id}/photos/{i}", "width": p["width"], "height": p["height"]}
                for i, p in enumerate(c.photos)]

    def claim_mode(c):
        """REPLAY whenever this claim's vision output was recorded, even on a live server (a scenario without its photo)."""
        return "REPLAY" if (mode_label == "REPLAY" or c.recorded) else "LIVE"

    def dep_rules():
        """The depreciation rules as the engine's config holds them, for the "?" help in the page."""
        return {"plastic_rate": C.PLASTIC_DEP, "glass_rate": 0.0, "metal_bands": C.metal_bands(),
                "paint_share": C.PAINT_MATERIAL_SHARE, "paint_rate": C.PAINT_MATERIAL_DEP}

    def customer_view(c):
        s, res = c.session, c.session.result
        out = {"claim_id": c.id, "mode": claim_mode(c), "state": s.state, "status": "assessed" if c.assessed else "collecting",
               "policy": {"policy_id": c.policy.policy_id, "vehicle": f"{c.policy.make} {c.policy.model}"},
               "plate_given": bool(c.plate_text), "photos": photo_urls(c), "decision": None, "message": None,
               "offer": None, "lines": [], "deductible": None, "gross": None, "needs": [], "options": [],
               "closed": s.state in TERMINAL}
        if claim_mode(c) == "REPLAY":
            out["notice"] = "REPLAY: vision output was recorded earlier from the real pipeline; the engine runs live."
        if res is not None:
            out["decision"] = res["decision"]
            out["message"] = c.message_text
            out["message_source"] = c.message_source
            out["next_step"] = next_step_of(c)
            if res["decision"] == "OFFER":
                out["offer"] = s.current_offer
                out["deductible"], out["gross"] = res["deductible"], res["gross"]
                out["lines"] = [{k: ln[k] for k in CUSTOMER_LINE_KEYS} for ln in res["lines"]]
                out["dep_rules"] = dep_rules()
                if s.state in ("OFFERED", "UPDATED_OFFER"):
                    out["options"] = [{"id": "accept", "label": "Accept the cash offer"},
                                      {"id": "partner_garage", "label": "Repair at a partner garage at agreed rates"},
                                      {"id": "surveyor", "label": "Ask for a surveyor to inspect"}]
            elif res["decision"] == "ASK_MORE":
                out["needs"] = [NEED_TEXT[m] for m in res["missing"] if m in NEED_TEXT]
        out["updated_offer"] = s.updated_offer
        out["original_offer"] = s.offer
        if c.video_view is not None:
            out["video"] = c.video_view
        if s.last_check:
            out["quote_check"] = quote_view(s.last_check)
        return out

    def quote_view(chk):
        rows = [{"description": v["description"], "quoted": v["quoted"], "verdict": v["verdict"], "reason": v.get("reason", "")}
                for v in chk.get("verdicts", [])]
        return {"lines": rows, "moved": chk.get("moved"), "current_offer": chk.get("current_offer"),
                "updated_offer": chk.get("updated_offer"), "quote_total": chk.get("quote_total"), "note": chk.get("note")}

    # ------------------------------------------------------------------ meta
    @app.get("/health")
    def health():
        if "gpu" not in gpu_cache:
            gpu_cache["gpu"] = rt.gpu_available() if mode_label == "LIVE" else False
        return {"ok": True, "mode": mode_label, "qwen": qwen_status(), "qwen_error": qstate.get("error"),
                "qwen_load_s": qstate.get("load_s"),
                "video": cfg.video, "claims": len(claims), "ui": build_info["ui"], "build": build_info["build"],
                "built_at": build_info.get("built_at"), "weights_found": not rt.missing_weights(), "gpu": gpu_cache["gpu"]}

    @app.get("/limits")
    def limits():
        p = ROOT / "docs" / "LIMITS.json"
        if not p.exists():
            raise HTTPException(404, "limits file not generated")
        return JSONResponse(json.loads(p.read_text(encoding="utf-8")))

    @app.get("/policies")
    def policies():
        return [{"policy_id": k, "vehicle": f"{p['make']} {p['model']} ({p['reg_date'][:4]})", "plate": p["plate"]}
                for k, p in POLICIES.items()]

    @app.get("/scenarios")
    def scenarios():
        out = []
        for k, s in SCENARIOS.items():
            item = {kk: s[kk] for kk in ("title", "blurb", "expect")}
            item["id"] = k
            item["recorded"] = True
            if s.get("needs_model"):
                item["needs_model"] = True
                item["available"] = qwen_status() == "ready"
                item["try"] = s.get("try", [])
                item["start_command"] = "run.ps1 demo-qwen   (macOS or Linux: ./run.sh demo-qwen)"
            if s.get("script"):
                item["script"] = [{"customer": st.get("message") or ("a supported garage quote" if not st.get("inflate") else "an inflated garage quote, every line x%d" % st["inflate"])}
                                  for st in s["script"]]
            if s.get("message"):
                item["message"] = s["message"]
            if s.get("quote_example"):
                item["quote_example"] = json.loads((ROOT / "run1" / "quotes" / "rq00.json").read_text())
                item["quote_example"].pop("trap", None)
                item["quote_example"].pop("variant", None)
            out.append(item)
        return out

    @app.get("/sample-quote.jpg")
    def sample_quote():
        """The recorded SYNTHETIC garage-quote photo that ships with the repository, so the quote-reading path can be tried
        without a quote of your own. Reading it needs the language model."""
        p = ROOT / "run1" / "quotes" / "rq00.jpg"
        if not p.exists():
            raise HTTPException(404, "sample quote photo not present")
        return FileResponse(p, media_type="image/jpeg")

    @app.get("/capture-guide")
    def capture_guide():
        return CAPTURE_GUIDE

    # ------------------------------------------------------------------ claims
    @app.post("/claims")
    def create_claim(body: dict = Body(default_factory=dict)):
        sc = body.get("scenario")
        if sc is not None and sc not in SCENARIOS:
            raise HTTPException(422, "unknown scenario")
        pid = SCENARIOS[sc]["policy_id"] if sc else body.get("policy_id", "POL-DEMO-001")
        if pid not in POLICIES:
            raise HTTPException(422, "unknown policy")
        with glock:
            if len(claims) >= MAX_CLAIMS:
                raise HTTPException(429, "claim store is full; restart the demo")
            c = Claim(uuid.uuid4().hex[:12], get_policy(pid), SCENARIOS[sc]["replay"] if sc else None)
            c.silent = bool(body.get("silent"))
            claims[c.id] = c
        if sc:
            s = SCENARIOS[sc]
            c.plate_text, c.plate_source = c.policy.plate, "scenario (typed)"
            rec = replay.lookup(s["replay"])
            p = find_demo_photo(rec)
            if p is not None:
                add_photo(c, p.read_bytes(), p.name)
            c.session._log("scenario_loaded", {"scenario": sc, "mode": mode_label})
            assess(c)
            if s.get("message"):
                c.chat.append({"from": "customer", "text": s["message"]})
            for step in s.get("script", []):                 # recorded customer turns, answered by the live engine
                if "message" in step:
                    do_message(c, step["message"])
                else:
                    sample = json.loads((ROOT / "run1" / "quotes" / "rq00.json").read_text())
                    f = step.get("inflate", 1)
                    for ln in sample["lines"]:
                        ln["unit_price"] *= f
                        ln["total"] *= f
                    do_quote(c, clean_quote({"lines": sample["lines"], "gst_percent": sample.get("gst_percent")}), "recorded sample")
        else:
            if body.get("plate_text"):
                c.plate_text, c.plate_source = str(body["plate_text"])[:20], "typed"
            c.session._log("claim_created", {"policy": pid})
        persist(c)
        return customer_view(c)

    @app.get("/claims/{cid}")
    def get_claim(cid: str):
        return customer_view(need(cid))

    @app.post("/claims/{cid}/photos")
    async def photos(cid: str, request: Request, files: list[UploadFile] = File(...)):
        c = need(cid)
        with c.lock:
            closed(c)
            if c.session.state != "INTAKE":
                raise HTTPException(409, "an offer has already been made; use the quote or the choices")
            if len(files) + len(c.photos) > MAX_PHOTOS:
                raise HTTPException(422, f"at most {MAX_PHOTOS} photos per claim")
            for f in files:
                data = await f.read(MAX_IMAGE_BYTES + 1)
                add_photo(c, data, f.filename)
            c.session._log("photos_added", {"count": len(c.photos)})
            persist(c)
            return customer_view(c)

    @app.post("/claims/{cid}/plate")
    async def plate(cid: str, request: Request):
        c = need(cid)
        with c.lock:
            closed(c)
            ctype = request.headers.get("content-type", "")
            if ctype.startswith("application/json"):
                body = await request.json()
                text = str((body or {}).get("plate_text", "")).strip()[:20]
                if not text:
                    raise HTTPException(422, "plate_text is empty")
                c.plate_text, c.plate_source = text, "typed"
            else:
                form = await request.form()
                f = form.get("file")
                if f is None:
                    raise HTTPException(422, "send plate_text as JSON or a photo as 'file'")
                data = await f.read(MAX_IMAGE_BYTES + 1)
                try:
                    sniff(data)
                except ValueError as e:
                    raise HTTPException(422, str(e))
                q = get_qwen()
                if q is None:
                    raise HTTPException(503, "reading a plate photo needs the language model (it is off); type the plate instead")
                from PIL import Image as _I
                read = q.read_plate(_I.open(io.BytesIO(data)).convert("RGB"))
                if not read:
                    raise HTTPException(422, "the plate could not be read; type it or retake the photo")
                c.plate_text, c.plate_source = read, "photo (model-read)"
            c.session._log("plate_given", {"source": c.plate_source})
            persist(c)
            return customer_view(c)

    @app.post("/claims/{cid}/assess")
    def do_assess(cid: str):
        c = need(cid)
        with c.lock:
            closed(c)
            assess(c)
            return customer_view(c)

    @app.post("/claims/{cid}/video")
    async def video(cid: str, request: Request):
        c = need(cid)
        if not cfg.video:
            raise HTTPException(501, "video is not enabled on this server")
        with c.lock:
            closed(c)
            if c.session.state != "INTAKE":
                raise HTTPException(409, "an offer has already been made; use the quote or the choices")
            form = await request.form()
            rec_key = form.get("recorded")
            if rec_key:                              # the recorded SYNTHETIC walk-around: served from replay data, no upload
                rec = replay.video_record(str(rec_key))
                if rec is None:
                    raise HTTPException(422, "unknown recorded clip")
                from .backends import remap
                v = json.loads(json.dumps(rec["vision"], default=str))
                v["image_id"] = c.id
                c.session._log("video_recorded_sample", {"key": rec["key"], "synthetic": True})
                c.recorded = True
                c.video_view = build_video_view(c, v, rec)
                assess(c, v)
                return customer_view(c)
            f = form.get("file")
            if f is None:
                raise HTTPException(422, "send the video as 'file'")
            data = await f.read(MAX_VIDEO_BYTES + 1)
            if len(data) > MAX_VIDEO_BYTES:
                raise HTTPException(422, "video is larger than 60 MB")
            d = runtime / c.id
            d.mkdir(parents=True, exist_ok=True)
            path = d / "clip.mp4"
            path.write_bytes(data)
            from autosettle_vision.video import VideoRejected
            try:
                v = backend.run_video(path, c.id)
            except (VideoRejected, ReplayMiss) as e:
                c.session._log("video_rejected", {"reason": str(e)})
                persist(c)
                raise HTTPException(422, str(e))
            except Exception as e:
                raise HTTPException(503, f"the video pipeline failed ({type(e).__name__})")
            c.session._log("video_received", {k: v.get("video", {}).get(k) for k in ("seconds", "keyframes", "usable")})
            c.video_view = build_video_view(c, v)
            assess(c, v)
            return customer_view(c)

    @app.post("/claims/{cid}/quote")
    async def quote(cid: str, request: Request):
        c = need(cid)
        with c.lock:
            closed(c)
            if c.session.state not in ("OFFERED", "UPDATED_OFFER"):
                raise HTTPException(409, "there is no open offer to dispute")
            ctype = request.headers.get("content-type", "")
            source = "json"
            if ctype.startswith("application/json"):
                body = await request.json()
                quote_obj = clean_quote((body or {}).get("quote"))
            else:
                form = await request.form()
                f = form.get("file")
                if f is None:
                    raise HTTPException(422, "send a quote photo as 'file' or the quote as JSON")
                data = await f.read(MAX_IMAGE_BYTES + 1)
                try:
                    sniff(data)
                except ValueError as e:
                    raise HTTPException(422, str(e))
                m = get_qwen()
                if m is None:
                    raise HTTPException(503, "reading a quote photo needs the language model (it is off); use a recorded quote")
                from PIL import Image as _I
                quote_obj, _raw = m.read_quote(_I.open(io.BytesIO(data)).convert("RGB"))
                c.session._log("quote_read_by_model", {"lines": len(quote_obj.get("lines", []))})
                source = "photo (model-read)"
            chk = do_quote(c, quote_obj, source)
            persist(c)
            return {**customer_view(c), "quote_result": quote_view(chk)}

    @app.post("/claims/{cid}/message")
    def message(cid: str, body: dict = Body(...)):
        c = need(cid)
        with c.lock:
            closed(c)
            text = str(body.get("text", ""))
            if not text.strip() or len(text) > MAX_MESSAGE_CHARS:
                raise HTTPException(422, f"message must be 1 to {MAX_MESSAGE_CHARS} characters")
            reply, flags = do_message(c, text)
            persist(c)
            return {**customer_view(c), "reply": reply, "flags_seen": bool(flags)}

    @app.post("/claims/{cid}/choose")
    def choose(cid: str, body: dict = Body(...)):
        c = need(cid)
        with c.lock:
            closed(c)
            opt = body.get("option")
            s = c.session
            try:
                if opt == "accept" and s.state == "OFFERED":
                    s.accept()
                elif opt == "accept" and s.state == "UPDATED_OFFER":
                    s.choose("accept_updated")
                elif opt in ("partner_garage", "surveyor") and s.state in ("OFFERED", "UPDATED_OFFER"):
                    s.choose(opt)
                else:
                    raise HTTPException(409, "that choice is not available now")
            except AssertionError as e:
                raise HTTPException(409, str(e))
            label = {"accept": "Accept the cash offer", "partner_garage": "Repair at a partner garage", "surveyor": "Ask for a surveyor"}[opt]
            closing = G.choice_reply(opt, R.money(s.current_offer))
            add_turn(c, "customer", label, detail={"choice": opt})
            add_turn(c, "system", closing, wording="template")
            persist(c)
            return customer_view(c)

    @app.get("/claims/{cid}/audit")
    def audit(cid: str):
        c = need(cid)
        return {"claim_id": c.id, "chain_ok": ClaimSession.verify_log(c.session.log), "state": c.session.state,
                "log": c.session.log, "mode": claim_mode(c)}

    @app.get("/claims/{cid}/photos/{n}")
    def photo(cid: str, n: int):
        c = need(cid)
        if not (0 <= n < len(c.photos)):
            raise HTTPException(404, "no such photo")
        p = c.photos[n]
        if p["sha256"] in plate_blur.DEMO_PLATE_BOXES:                  # displayed copy only; the pipeline read the original
            if p["sha256"] not in blur_cache:
                blur_cache[p["sha256"]] = plate_blur.displayed_bytes(p["path"].read_bytes(), p["sha256"], p["media"])
            return Response(blur_cache[p["sha256"]], media_type=p["media"])
        return FileResponse(p["path"], media_type=p["media"])

    @app.get("/claims/{cid}/chat")
    def chat(cid: str):
        return need(cid).chat

    def recorded_images(c, v):
        if c.photos:
            return [{"name": p["name"], "width": p["width"], "height": p["height"], "has_photo": True} for p in c.photos]
        if c.replay_key:                    # scenario run without the photo on this machine: recorded size, blank canvas
            rec = replay.lookup(c.replay_key)
            return [{"name": (v.get("images") or ["photo"])[0], "width": rec["width"], "height": rec["height"], "has_photo": False}]
        return []

    def estimate_of(c):
        """Adjuster-only estimate from the detections. Read-only: the session, the vision data and the log are not touched."""
        res = c.session.result
        if c.ev is None:
            return {"applies": False, "decision": res["decision"] if res else None, "note": "No photos or video have been analysed yet, so there is nothing to estimate."}
        try:
            return estimate_from_evidence(c.policy, c.ev, RC, decision=res["decision"] if res else None)
        except Exception as e:                      # the page must never fail because of the estimate
            return {"applies": False, "decision": res["decision"] if res else None, "note": f"The estimate could not be made ({type(e).__name__})."}

    # ------------------------------------------------------------------ adjuster (demo only: no authentication is claimed)
    @app.get("/adjuster/{cid}")
    def adjuster(cid: str):
        c = need(cid)
        s, res, v = c.session, c.session.result, c.vision
        out = {"estimate": estimate_of(c), "label": "ADJUSTER VIEW (demo only; no authentication is claimed)", "claim_id": c.id, "mode": claim_mode(c),
               "state": s.state, "plate_source": c.plate_source, "photos": photo_urls(c),
               "audit": {"chain_ok": ClaimSession.verify_log(s.log), "events": len(s.log)}}
        if res is None or v is None:
            return out
        dets = E.dedupe(c.ev["detections"])
        full = {(d["part_class"], d.get("damage_class")): d for d in v["detections"]}
        lines = []
        for ln in res["lines"]:
            d = full.get((ln["part_class"], ln["damage_class"]), {})
            lines.append({**{k: ln[k] for k in CUSTOMER_LINE_KEYS}, "price_tier": ln["price_tier"], "price_status": ln["price_status"],
                          "evidence": {"part_conf": d.get("part_conf"), "damage_conf": d.get("damage_conf"),
                                       "area_fraction": d.get("damage_area_fraction"), "source": d.get("damage_source"),
                                       "support_images": d.get("support_images")}})
        out.update({"decision": res["decision"], "reasons": res["reasons"], "tci": res["tci"], "missing": res["missing"],
                    "lines": lines, "dep_rules": dep_rules(), "ledger": res["ledger"], "offer": s.current_offer, "deductible": res["deductible"],
                    "gross": res["gross"], "integrity_flags": v["integrity_flags"], "flags": v["flags"],
                    "quality": v["quality"], "images": recorded_images(c, v),
                    "recorded_images": v.get("images"),
                    "detections": [{k: d.get(k) for k in ("part_class", "part_conf", "damage_class", "damage_conf", "severity",
                                                          "damage_area_fraction", "damage_source", "part_polygon", "damage_box",
                                                          "damage_polygon", "note")} for d in v["detections"]],
                    "findings_by_image": v["findings_by_image"], "engine_detections_after_dedupe": len(dets)})
        return out

    @app.get("/guardrails")
    def guardrails():
        """The guardrail table the Guardrails scene shows. Every threshold is read from the engine's config, not retyped."""
        m = R.money
        rows = [
            ("Surveyor required", f"gross loss at or above {m(C.SURVEYOR_REQUIRED)}", "RULE", "autosettle_engine/engine.py assess"),
            ("Human review", f"gross loss at or above {m(C.GROSS_REVIEW)}", "ASSUMPTION", "autosettle_engine/engine.py assess"),
            ("Possible total loss", f"gross loss at or above {int(C.TOTAL_LOSS_SHARE_OF_IDV * 100)}% of the insured value", "ASSUMPTION", "autosettle_engine/engine.py assess"),
            ("Plate match", "a plate that does not match the policy", "DESIGN", "autosettle_engine/engine.py info_gate"),
            ("Information gate", f"every field known; part confidence {C.MIN_PART_CONF:.2f}, damage confidence {C.MIN_DAMAGE_CONF:.2f}; asks at most {C.K_STALL} times, then a human", "ASSUMPTION", "autosettle_engine/engine.py info_gate"),
            ("Low-confidence severe", f"a severe call below {C.LOW_CONF_SEVERE:.2f} confidence goes to a human", "ASSUMPTION", "autosettle_engine/engine.py assess"),
            ("Integrity flags", "an editing tag, a near-duplicate photo or a video that is not continuous goes to a human", "ASSUMPTION", "autosettle_vision/pipeline.py, video_integrity.py"),
            ("Quote evidence", f"a quote line moves the offer only if the photos show the part and the price is inside the genuine range; up to {int(C.QUOTE_OK_TOLERANCE * 100)}% of our reference counts as ok", "ASSUMPTION", "autosettle_engine/dispute.py check_quote"),
            ("Evidence rounds", f"at most {C.MAX_EVIDENCE_ROUNDS} distinct quotes may move the offer", "ASSUMPTION", "autosettle_engine/dispute.py dispute"),
            ("Upper bound", "no quote can lift the offer past the bound fixed before the conversation; the customer never sees it", "DESIGN", "autosettle_engine/dispute.py check_quote"),
            ("Text never changes an amount", "free text is recorded and flagged; it reaches no input of the pricing code", "DESIGN", "autosettle_engine/dispute.py message"),
            ("Model wording is checked", "a reply that adds a figure, drops a line, names the bound or promises is replaced by the template", "DESIGN", "autosettle_engine/rationale.py"),
            ("Closed claims stay closed", "any event after the decision is refused", "DESIGN", "autosettle_engine/dispute.py, autosettle_api/app.py"),
            ("Hash-chained audit log", "every event carries the hash of the one before; any edit breaks the chain", "DESIGN", "autosettle_engine/dispute.py _log, verify_log"),
        ]
        return [{"guardrail": a, "threshold": b, "kind": k, "enforced_in": w} for a, b, k, w in rows]

    # ------------------------------------------------------------------ transcript, recorded clips, attack console
    @app.get("/claims/{cid}/transcript")
    def transcript(cid: str):
        c = need(cid)
        return {"claim_id": c.id, "mode": claim_mode(c), "state": c.session.state,
                "chain_ok": ClaimSession.verify_log(c.session.log), "turns": c.turns}

    @app.get("/video-samples")
    def video_samples():
        return [{"key": k, "label": r["label"], "shows": VIDEO_SAMPLES.get(k, ""), "synthetic": True} for k, r in replay.videos.items()]

    attack_hits = []

    @app.get("/attacks")
    def attacks():
        return attack_runner.listing()

    @app.post("/attacks/{name}/run")
    def attack_run(name: str):
        now = time.time()
        attack_hits[:] = [t for t in attack_hits if now - t < 60] + [now]
        if len(attack_hits) > 60:
            raise HTTPException(429, "too many attack runs; slow down")
        out = attack_runner.run(name)
        if out is None:
            raise HTTPException(404, "unknown attack")
        out["label"] = "TEST RUN on a fresh in-memory claim; no real claim or audit log is touched"
        return out

    # ------------------------------------------------------------------ adjuster extras (demo only: no authentication is claimed)
    ADJ_LABEL = "ADJUSTER VIEW, DEMO ONLY (no authentication is claimed)"

    def explain(code):
        for k, t in REASON_TEXT.items():
            if code.startswith(k):
                return t + (f" ({code.split(':', 1)[1]})" if ":" in code else "")
        return code

    @app.get("/adjuster/{cid}/estimate")
    def adjuster_estimate(cid: str):
        c = need(cid)
        return {"label": ADJ_LABEL, "claim_id": c.id, "mode": claim_mode(c), **estimate_of(c)}

    @app.get("/adjuster/{cid}/range")
    def adjuster_range(cid: str):
        c = need(cid)
        s, res = c.session, c.session.result
        out = {"label": ADJ_LABEL, "claim_id": c.id, "mode": claim_mode(c)}
        if res is None or res["decision"] != "OFFER":
            return {**out, "applies": False, "decision": res["decision"] if res else None,
                    "note": "No cash offer was made on this claim, so there is no settlement range."}
        idv = c.policy.idv
        out.update(applies=True, initial_offer=s.offer, current_offer=s.current_offer, ceiling=res["ceiling"],
                   deductible=res["deductible"], gross=res["gross"], idv=idv,
                   ceiling_note="Internal upper bound, fixed before any conversation. The customer is never shown it.",
                   evidence_rounds_used=s.evidence_rounds, evidence_rounds_allowed=C.MAX_EVIDENCE_ROUNDS,
                   which_stops_a_higher_number=[
                       {"guardrail": "Upper bound", "rule": f"No quote can lift the offer above {R.money(res['ceiling'])}.",
                        "enforced_in": "autosettle_engine/dispute.py check_quote"},
                       {"guardrail": "Evidence rounds", "rule": f"At most {C.MAX_EVIDENCE_ROUNDS} distinct quotes may move the offer.",
                        "enforced_in": "autosettle_engine/dispute.py dispute"},
                       {"guardrail": "Genuine-price range", "rule": "A part priced above the genuine range for this model gets no uplift.",
                        "enforced_in": "autosettle_engine/dispute.py check_quote"},
                       {"guardrail": "Photo support", "rule": "A quote line for a part with no damage in the photos is not paid.",
                        "enforced_in": "autosettle_engine/dispute.py check_quote"},
                       {"guardrail": "Review threshold", "rule": f"A gross loss at or above {R.money(C.GROSS_REVIEW)} goes to a human (this claim: {R.money(res['gross'])}).",
                        "enforced_in": "autosettle_engine/engine.py assess"},
                       {"guardrail": "Surveyor threshold", "rule": f"A gross loss at or above {R.money(C.SURVEYOR_REQUIRED)} needs a surveyor.",
                        "enforced_in": "autosettle_engine/engine.py assess"},
                       {"guardrail": "Total loss", "rule": f"A gross loss at or above {int(C.TOTAL_LOSS_SHARE_OF_IDV * 100)}% of the insured value ({R.money(int(C.TOTAL_LOSS_SHARE_OF_IDV * idv))}) needs a surveyor.",
                        "enforced_in": "autosettle_engine/engine.py assess"}])
        return out

    @app.get("/adjuster/{cid}/escalation")
    def adjuster_escalation(cid: str):
        c = need(cid)
        s, res, v = c.session, c.session.result, c.vision
        out = {"label": ADJ_LABEL, "claim_id": c.id, "mode": claim_mode(c), "state": s.state}
        if res is None or s.state not in ("ESCALATED", "SURVEYOR"):
            return {**out, "applies": False,
                    "note": "This claim is not escalated. A packet is built for ESCALATE and SURVEYOR outcomes."}
        reasons = [{"code": r_, "meaning": explain(r_)} for r_ in res["reasons"] if r_ not in res["missing"]]
        for f_ in sorted(set(s.flags)):
            reasons.append({"code": f"message:{f_}", "meaning": {"abusive": "The customer's message was abusive", "legal_threat": "The customer mentioned legal or regulator action",
                                                                  "injection_suspected": "A message looked like an instruction to the system (nothing changed)"}.get(f_, f_)})
        dets = []
        if v:
            dets = [{k: d.get(k) for k in ("part_class", "part_conf", "damage_class", "damage_conf", "severity", "damage_area_fraction",
                                           "damage_source", "note")} for d in v["detections"]]
        out.update(applies=True, decision=res["decision"], reasons=reasons,
                   missing=[{"field": m, "meaning": MISSING_TEXT.get(m, m)} for m in res["missing"]],
                   flags=(v or {}).get("flags", []), integrity_flags=(v or {}).get("integrity_flags", []),
                   evidence=dets, priced_lines=[{k: ln[k] for k in ("part_class", "damage_class", "severity", "action", "line_total")} for ln in res["lines"]],
                   gross=res["gross"], photos=photo_urls(c), findings_by_image=(v or {}).get("findings_by_image", {}),
                   quality=(v or {}).get("quality", {}), video=c.video_view,
                   what_the_human_should_do={"SURVEYOR": "Book a licensed surveyor; do not price hidden structural damage from photos.",
                                             "ESCALATED": "Review the reasons and the evidence below, then contact the customer."}[s.state],
                   audit={"chain_ok": ClaimSession.verify_log(s.log),
                          "events": [{"seq": e["seq"], "event": e["event"], "state": e["state"], "hash": e["hash"][:12]} for e in s.log]})
        return out

    # ------------------------------------------------------------------ static front end
    ui_dir = Path(__file__).with_name(rt.UI_DIRS.get(cfg.ui, "static"))
    if ui_dir.exists() and (ui_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=ui_dir / "assets"), name="assets") if (ui_dir / "assets").exists() else None

        @app.get("/{path:path}")
        def spa(path: str):
            f = (ui_dir / path).resolve()
            if path and ui_dir.resolve() in f.parents and f.is_file():
                return FileResponse(f)
            return FileResponse(ui_dir / "index.html")
    else:
        @app.get("/")
        def placeholder():
            return Response("Aequour API is running. The web build is not present; see /api-docs.", media_type="text/plain")

    app.state.claims = claims
    return app
