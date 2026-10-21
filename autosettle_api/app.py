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

from autosettle_engine import engine as E, rationale as R
from autosettle_engine.dispute import TERMINAL, ClaimSession
from autosettle_vision.claim import POLICIES, RC, customer_text, decision_text, engine_vision, get_policy

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
MEDIA = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
CUSTOMER_LINE_KEYS = ("part_class", "damage_class", "severity", "action", "part_mrp", "dep_rate", "dep_amount", "part_net",
                      "labour", "paint_gross", "paint_dep", "paint_net", "line_total")
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
    glock = threading.Lock()
    app = FastAPI(title="Aequour", docs_url="/api-docs", redoc_url=None)
    mode_label = "REPLAY" if backend.mode == "replay" else "LIVE"

    # ------------------------------------------------------------------ helpers
    def get_qwen():
        if not cfg.qwen:
            return None
        if not qstate["tried"]:
            qstate["tried"] = True
            try:
                from autosettle_vision.qwen import QwenVL
                qstate["model"] = QwenVL()
            except Exception as e:      # no GPU, out of memory, model missing: fall back to templates
                qstate["error"] = str(e)[:200]
        return qstate["model"]

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
            (runtime / f"{c.id}.json").write_text(json.dumps({"claim_id": c.id, "mode": mode_label, "log": c.session.log,
                                                              "verified": ClaimSession.verify_log(c.session.log)}, default=str))
        except OSError:
            pass

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
        text, used, viol = customer_text(res, c.policy, ev, get_qwen() if res["decision"] == "OFFER" else None)
        c.session._log("customer_message", {"model_wording_used": used, "violations": [str(x) for x in viol]})
        c.message_text, c.message_source = text, ("model, checked" if used else "template")
        c.assessed = True
        persist(c)
        return res

    def photo_urls(c):
        return [{"index": i, "url": f"/claims/{c.id}/photos/{i}", "width": p["width"], "height": p["height"]}
                for i, p in enumerate(c.photos)]

    def customer_view(c):
        s, res = c.session, c.session.result
        out = {"claim_id": c.id, "mode": mode_label, "state": s.state, "status": "assessed" if c.assessed else "collecting",
               "policy": {"policy_id": c.policy.policy_id, "vehicle": f"{c.policy.make} {c.policy.model}"},
               "plate_given": bool(c.plate_text), "photos": photo_urls(c), "decision": None, "message": None,
               "offer": None, "lines": [], "deductible": None, "gross": None, "needs": [], "options": [],
               "closed": s.state in TERMINAL}
        if mode_label == "REPLAY":
            out["notice"] = "REPLAY: vision output was recorded earlier from the real pipeline; the engine runs live."
        if res is not None:
            out["decision"] = res["decision"]
            out["message"] = c.message_text if res["decision"] == "OFFER" else decision_text(res)
            out["message_source"] = c.message_source if res["decision"] == "OFFER" else "template"
            if res["decision"] == "OFFER":
                out["offer"] = s.current_offer
                out["deductible"], out["gross"] = res["deductible"], res["gross"]
                out["lines"] = [{k: ln[k] for k in CUSTOMER_LINE_KEYS} for ln in res["lines"]]
                if s.state in ("OFFERED", "UPDATED_OFFER"):
                    out["options"] = [{"id": "accept", "label": "Accept the cash offer"},
                                      {"id": "partner_garage", "label": "Repair at a partner garage at agreed rates"},
                                      {"id": "surveyor", "label": "Ask for a surveyor to inspect"}]
            elif res["decision"] == "ASK_MORE":
                out["needs"] = [NEED_TEXT[m] for m in res["missing"] if m in NEED_TEXT]
        out["updated_offer"] = s.updated_offer
        out["original_offer"] = s.offer
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
        return {"ok": True, "mode": mode_label, "qwen": "off" if not cfg.qwen else ("loaded" if qstate["model"] else "lazy"),
                "video": cfg.video, "claims": len(claims)}

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
            if s.get("message"):
                item["message"] = s["message"]
            if s.get("quote_example"):
                item["quote_example"] = json.loads((ROOT / "run1" / "quotes" / "rq00.json").read_text())
                item["quote_example"].pop("trap", None)
                item["quote_example"].pop("variant", None)
            out.append(item)
        return out

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
            claims[c.id] = c
        if sc:
            s = SCENARIOS[sc]
            c.plate_text, c.plate_source = c.policy.plate, "scenario (typed)"
            rec = replay.lookup(s["replay"])
            for d in list(cfg.demo_photos) + [Path(os.environ.get("AEQUOUR_DEV_PHOTOS", ROOT / "test_photos" / "commons")),
                                               ROOT / "test_photos" / "commons"]:
                p = Path(d) / rec["source_file"]
                if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == rec["sha256"]:
                    add_photo(c, p.read_bytes(), p.name)
                    break
            c.session._log("scenario_loaded", {"scenario": sc, "mode": mode_label})
            assess(c)
            if s.get("message"):
                c.chat.append({"from": "customer", "text": s["message"]})
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
            if ctype.startswith("application/json"):
                body = await request.json()
                q = (body or {}).get("quote")
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
                quote_obj = {"lines": clean, "gst_percent": q.get("gst_percent"),
                             "grand_total": sum(x["total"] for x in clean)}
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
            chk = c.session.dispute(quote_obj)
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
            flags = c.session.message(text)
            if "abusive" in flags or "legal_threat" in flags:
                reply = "Your message has been passed to a claims specialist, who will contact you."
            else:
                reply = "Thank you. Messages are recorded with your claim. An amount changes only with new photos or an itemised garage quote."
            c.chat += [{"from": "customer", "text": text[:MAX_MESSAGE_CHARS]}, {"from": "system", "text": reply}]
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
            persist(c)
            return customer_view(c)

    @app.get("/claims/{cid}/audit")
    def audit(cid: str):
        c = need(cid)
        return {"claim_id": c.id, "chain_ok": ClaimSession.verify_log(c.session.log), "state": c.session.state,
                "log": c.session.log, "mode": mode_label}

    @app.get("/claims/{cid}/photos/{n}")
    def photo(cid: str, n: int):
        c = need(cid)
        if not (0 <= n < len(c.photos)):
            raise HTTPException(404, "no such photo")
        p = c.photos[n]
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

    # ------------------------------------------------------------------ adjuster (demo only: no authentication is claimed)
    @app.get("/adjuster/{cid}")
    def adjuster(cid: str):
        c = need(cid)
        s, res, v = c.session, c.session.result, c.vision
        out = {"label": "ADJUSTER VIEW (demo only; no authentication is claimed)", "claim_id": c.id, "mode": mode_label,
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
                    "lines": lines, "ledger": res["ledger"], "offer": s.current_offer, "deductible": res["deductible"],
                    "gross": res["gross"], "integrity_flags": v["integrity_flags"], "flags": v["flags"],
                    "quality": v["quality"], "images": recorded_images(c, v),
                    "recorded_images": v.get("images"),
                    "detections": [{k: d.get(k) for k in ("part_class", "part_conf", "damage_class", "damage_conf", "severity",
                                                          "damage_area_fraction", "damage_source", "part_polygon", "damage_box",
                                                          "damage_polygon", "note")} for d in v["detections"]],
                    "findings_by_image": v["findings_by_image"], "engine_detections_after_dedupe": len(dets)})
        return out

    # ------------------------------------------------------------------ static front end
    ui_dir = Path(__file__).with_name({"demo": "static_demo", "v1": "static_v1"}.get(cfg.ui, "static"))
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
