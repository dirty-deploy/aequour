"""
Auto-Settle AI vision pipeline: photos / video in, vision JSON out (the contract autosettle_engine.assess() reads).

    python -m autosettle_vision.pipeline IMG [IMG ...] [--video V] [--plate-ocr] [--out claim.json]

Three models, each used for what it is good at (numbers from our own val/test runs, 20 Oct 2026):
  parts_s          YOLO11s-seg, 21 parts, mask mAP50 0.888   -> WHERE: part masks
  dent_det         YOLO11s detect, 14 part-specific damage classes (Roboflow), test mAP50 0.826
                                                             -> WHAT: main damage signal (box + implied part)
  damage_merged_s  YOLO11s-seg, 4 classes, mask mAP50 0.18   -> weak; only Missing/Broken part at high confidence,
                                                                and only for parts the detector has no class for
Severity = damage area inside the part / part area  [ASSUMPTION thresholds below].
Money is never computed here. This module only perceives.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
W_PARTS = ROOT / "backup" / "parts_s_best.pt"
W_DET = ROOT / "backup" / "dent_det_best.pt"
W_MERGED = ROOT / "backup" / "damage_merged_s_best.pt"

# detector class -> (compatible part classes, engine damage class). First part is the default if no mask matches.
DET_MAP = {
    "Front-windscreen-damage": (("Windshield",), "Broken part"),
    "Headlight-damage": (("Headlight",), "Broken part"),
    "Rear-windscreen-Damage": (("Back-windshield",), "Broken part"),
    "Runningboard-Damage": (("Rocker-panel",), "Dent"),
    "Sidemirror-Damage": (("Mirror",), "Broken part"),
    "Taillight-Damage": (("Tail-light",), "Broken part"),
    "bonnet-dent": (("Hood",), "Dent"),
    "boot-dent": (("Trunk",), "Dent"),
    "doorouter-dent": (("Front-door", "Back-door"), "Dent"),
    "fender-dent": (("Fender",), "Dent"),
    "front-bumper-dent": (("Front-bumper",), "Dent"),
    "quaterpanel-dent": (("Quarter-panel",), "Dent"),
    "rear-bumper-dent": (("Back-bumper",), "Dent"),
    "roof-dent": (("Roof",), "Dent"),
}
# parts the detector already covers; the weak merged model is not trusted there
DET_PARTS = {p for parts, _ in DET_MAP.values() for p in parts}

# Tuned on the 41 Commons test photos (tools/sweep_vision.py), part recall / precision:
#   640/0.25 0.432/0.500 · 640/0.15 0.554/0.482 · 960/0.25 0.405/0.577 · 960/0.15 0.554/0.506 · 1280 worse.
# 0.15 finds more, but the engine gate needs damage confidence >= 0.30, so those extra low-confidence finds only
# block claims (ASK_MORE). 960 px / 0.25 = best precision.
IMGSZ = 960
CONF_PARTS = 0.25
CONF_DET = 0.25
CONF_MERGED = 0.50          # [ASSUMPTION] weak model: only confident Missing/Broken part findings are used
MERGED_CLASSES = {"Missing part", "Broken part"}
# [ASSUMPTION, weakly calibrated] area fraction < 0.30 minor, < 0.60 moderate, else severe. No public dataset labels
# severity. On the 32 correctly located parts in the Commons photos, hand-labelled moderate damage had a median
# fraction of 0.51 and severe 0.64, with heavy overlap: these bands agree with the labels on 20 of 32. Severity is
# the weakest signal in the pipeline; the engine's pivots and the dispute flow exist for exactly this.
SEV_THRESHOLDS = (0.30, 0.60)
HEAVY_SEVERE_PARTS = 3      # [ASSUMPTION] this many severe parts, or a severe hood plus one more, = heavy crash
BOX_FILL = 0.785            # detector gives boxes; a dent/crack region is roughly elliptical: area ~ pi/4 of its box
MIN_OVERLAP = 0.30          # share of a damage region that must fall on a part mask to assign it (any part)
MIN_OVERLAP_NAMED = 0.10    # lower bar when the detector class already names the panel (only compatible masks count)
BLUR_MIN = 60.0             # [ASSUMPTION] variance of Laplacian below this = too blurry
DARK_MIN = 40.0             # [ASSUMPTION] mean grey level below this = too dark
EDIT_SOFTWARE = ("photoshop", "gimp", "snapseed", "picsart", "lightroom", "canva", "facetune", "pixlr")

_models = {}
DET_HOOK = None       # set by autosettle_vision.crops.enable(); never set in the default pipeline


def models():
    if not _models:
        from ultralytics import YOLO
        _models.update(parts=YOLO(str(W_PARTS)), det=YOLO(str(W_DET)), merged=YOLO(str(W_MERGED)))
    return _models


def severity_of(frac):
    lo, hi = SEV_THRESHOLDS
    return "minor" if frac < lo else ("moderate" if frac < hi else "severe")


# ------------------------------------------------------------------ quality and integrity
def quality(img, blur_min=None, dark_min=None):
    """Photos use BLUR_MIN and DARK_MIN. A video keyframe passes the video floors instead (autosettle_vision.video)."""
    blur_min = BLUR_MIN if blur_min is None else blur_min
    dark_min = DARK_MIN if dark_min is None else dark_min
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    bright = float(grey.mean())
    flags = []
    if blur < blur_min:
        flags.append("blurry")
    if bright < dark_min:
        flags.append("too_dark")
    return {"blur": round(blur, 1), "brightness": round(bright, 1), "flags": flags}


def dhash(img, size=8):
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (size + 1, size))
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a, b):
    return bin(a ^ b).count("1")


def exif_flags(path):
    """Editing-software tag = integrity flag (escalate). Missing camera data = soft flag only (screenshots, forwards)."""
    try:
        from PIL import Image
        ex = Image.open(path).getexif()
    except Exception:
        return [], ["unreadable_metadata"]
    software = str(ex.get(305, "")).lower()   # 305 = Software
    hard = ["edited_with_" + s for s in EDIT_SOFTWARE if s in software]
    soft = [] if (ex.get(271) or ex.get(272)) else ["no_camera_metadata"]   # 271 Make, 272 Model
    return hard, soft


class SeenStore:
    """Perceptual hashes of photos from earlier claims; a near-duplicate is an integrity flag."""

    def __init__(self, path=ROOT / "runs" / "seen_hashes.json"):
        self.path = Path(path)
        self.items = json.loads(self.path.read_text()) if self.path.exists() else []

    def match(self, h, claim_id, max_dist=4):
        return [it for it in self.items if it["claim"] != claim_id and hamming(it["h"], h) <= max_dist]

    def add(self, h, claim_id, name):
        self.items.append({"h": h, "claim": claim_id, "name": name})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.items))


def video_frames(path, every_s=1.0, max_frames=40):
    """Sample frames and check the take is continuous: each sampled frame must match the previous one
    (SIFT + RANSAC homography). A cut, or a different car, breaks the chain."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(round(fps * every_s)))
    frames, i = [], 0
    while len(frames) < max_frames:
        ok, fr = cap.read()
        if not ok:
            break
        if i % step == 0:
            frames.append(fr)
        i += 1
    cap.release()
    sift = cv2.SIFT_create(800)
    breaks = []
    prev = None
    for k, fr in enumerate(frames):
        g = cv2.cvtColor(cv2.resize(fr, (640, int(640 * fr.shape[0] / fr.shape[1]))), cv2.COLOR_BGR2GRAY)
        kp, des = sift.detectAndCompute(g, None)
        if prev is not None and des is not None and prev[1] is not None and len(kp) > 10:
            m = cv2.BFMatcher().knnMatch(prev[1], des, k=2)
            good = [a for a, *b in m if b and a.distance < 0.75 * b[0].distance]
            inl = 0
            if len(good) >= 8:
                src = np.float32([prev[0][a.queryIdx].pt for a in good])
                dst = np.float32([kp[a.trainIdx].pt for a in good])
                _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
                inl = int(mask.sum()) if mask is not None else 0
            if inl < 15:   # [ASSUMPTION] fewer than 15 geometric inliers = not the same scene
                breaks.append(k)
        prev = (kp, des)
    return frames, breaks


# ------------------------------------------------------------------ perception on one image
def _poly_mask(poly, shape):
    m = np.zeros(shape[:2], np.uint8)
    if poly is not None and len(poly) >= 3:
        cv2.fillPoly(m, [np.asarray(poly, np.int32)], 1)
    return m


def _box_mask(box, shape):
    m = np.zeros(shape[:2], np.uint8)
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    m[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = 1
    return m


def analyse_image(img, image_id="img"):
    M = models()
    shape = img.shape
    pr = M["parts"].predict(img, conf=CONF_PARTS, imgsz=IMGSZ, verbose=False)[0]
    parts = []
    if pr.masks is not None:
        for poly, c, k in zip(pr.masks.xy, pr.boxes.conf.tolist(), pr.boxes.cls.tolist()):
            mk = _poly_mask(poly, shape)
            if mk.sum() > 0:
                parts.append({"part_class": pr.names[int(k)], "conf": float(c), "mask": mk, "poly": poly})

    findings = []

    def assign(dmask, allowed):
        """Best-overlapping part mask among the allowed classes (None = any)."""
        area = dmask.sum()
        need = MIN_OVERLAP_NAMED if allowed else MIN_OVERLAP
        best = None
        for p in parts:
            if allowed and p["part_class"] not in allowed:
                continue
            ov = float((dmask & p["mask"]).sum()) / max(area, 1)
            if ov >= need and (best is None or ov > best[0]):
                best = (ov, p)
        return best

    dr = M["det"].predict(img, conf=CONF_DET, imgsz=IMGSZ, verbose=False)[0]
    dets = list(zip(dr.boxes.xyxy.tolist(), dr.boxes.conf.tolist(), dr.boxes.cls.tolist()))
    if DET_HOOK is not None:           # optional variant (e.g. per-panel crops); None = the published behaviour
        dets = DET_HOOK(img, parts, dets, M["det"])
    for box, c, k in dets:
        name = dr.names[int(k)]
        allowed, dclass = DET_MAP[name]
        dmask = _box_mask(box, shape)
        hit = assign(dmask, set(allowed))
        if hit:
            p = hit[1]
            inter = float((dmask & p["mask"]).sum())
            frac = min(1.0, BOX_FILL * inter / float(p["mask"].sum()))
            findings.append({"part_class": p["part_class"], "part_conf": round(p["conf"], 3), "part_source": "parts_model",
                             "damage_class": dclass, "damage_conf": round(float(c), 3), "damage_source": "dent_det:" + name,
                             "damage_area_fraction": round(frac, 4), "severity": severity_of(frac),
                             "part_polygon": np.asarray(p["poly"]).round(1).tolist(), "damage_box": [round(v, 1) for v in box]})
        else:
            # the detector's class already names the panel; the parts model did not outline it in this view
            findings.append({"part_class": allowed[0] if len(allowed) == 1 else "unassigned", "part_conf": round(float(c), 3),
                             "part_source": "damage_class", "damage_class": dclass, "damage_conf": round(float(c), 3),
                             "damage_source": "dent_det:" + name, "damage_area_fraction": None, "severity": None,
                             "damage_box": [round(v, 1) for v in box], "note": "no part mask; severity unknown"})

    mr = M["merged"].predict(img, conf=CONF_MERGED, imgsz=IMGSZ, verbose=False)[0]
    if mr.masks is not None:
        for poly, c, k in zip(mr.masks.xy, mr.boxes.conf.tolist(), mr.boxes.cls.tolist()):
            name = mr.names[int(k)]
            if name not in MERGED_CLASSES:
                continue
            dmask = _poly_mask(poly, shape)
            hit = assign(dmask, None)
            if not hit or hit[1]["part_class"] in DET_PARTS:
                continue
            p = hit[1]
            frac = float((dmask & p["mask"]).sum()) / float(p["mask"].sum())
            findings.append({"part_class": p["part_class"], "part_conf": round(p["conf"], 3), "part_source": "parts_model",
                             "damage_class": name, "damage_conf": round(float(c), 3), "damage_source": "damage_merged_s",
                             "damage_area_fraction": round(frac, 4), "severity": severity_of(frac),
                             "part_polygon": np.asarray(p["poly"]).round(1).tolist(),
                             "damage_polygon": np.asarray(poly).round(1).tolist()})

    plate = next((p for p in sorted(parts, key=lambda p: -p["conf"]) if p["part_class"] == "License-plate"), None)
    plate_box = None
    if plate is not None:
        ys, xs = np.nonzero(plate["mask"])
        plate_box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return {"image_id": image_id, "findings": findings, "parts_seen": sorted({p["part_class"] for p in parts}),
            "plate_box": plate_box}


# ------------------------------------------------------------------ claim-level fusion
def _fuse(per_image, min_support):
    """Merge findings by (part, damage class). Keep the worst severity seen in at least `min_support` images."""
    groups = {}
    for im in per_image:
        for f in im["findings"]:
            if f["severity"] is None or f["part_class"] == "unassigned":
                continue
            groups.setdefault((f["part_class"], f["damage_class"]), []).append({**f, "image_id": im["image_id"]})
    out = []
    for (part, dclass), fs in sorted(groups.items()):
        if len({f["image_id"] for f in fs}) < min_support:
            continue
        sev_rank = {"minor": 0, "moderate": 1, "severe": 2}
        best = max(fs, key=lambda f: (sev_rank[f["severity"]], f["damage_conf"]))
        best = {**best, "support_images": sorted({f["image_id"] for f in fs})}
        out.append(best)
    return out


def run_claim(image_paths=(), video=None, claim_id=None, plate_reader=None, seen=None, frames=None, extra_integrity=(), analyse=None):
    """Returns the vision JSON for one claim. plate_reader(crop_bgr) -> str | None (e.g. the Qwen reader).
    frames: [(name, bgr)] keyframes already chosen by autosettle_vision.video (the video path); extra_integrity: flags from
    video_integrity; analyse: replaces analyse_image (tests)."""
    claim_id = claim_id or hashlib.sha1("|".join(map(str, image_paths)).encode()).hexdigest()[:10]
    seen = seen if seen is not None else SeenStore()
    integrity, flags, imgs = [], [], []
    for p in image_paths:
        img = cv2.imread(str(p))
        if img is None:
            flags.append(f"unreadable:{Path(p).name}")
            continue
        hard, soft = exif_flags(p)
        integrity += [f"{h}:{Path(p).name}" for h in hard]
        flags += [f"{s}:{Path(p).name}" for s in soft]
        imgs.append((Path(p).name, img))
    min_support = 1
    if video:
        frames, breaks = video_frames(video)
        if breaks:
            integrity.append(f"video_not_continuous:frames_{breaks[:5]}")
        imgs += [(f"{Path(video).name}#f{i}", fr) for i, fr in enumerate(frames)]
        min_support = 2 if len(frames) >= 4 else 1   # a real dent shows up in more than one frame
    elif frames:
        integrity += list(extra_integrity)
        imgs += list(frames)
        min_support = 2 if len(frames) >= 4 else 1

    # duplicates inside this claim and against earlier claims
    hashes = {}
    for name, img in imgs:
        h = dhash(img)
        if not name.count("#f"):
            for other, oh in hashes.items():
                if hamming(h, oh) <= 2:
                    flags.append(f"duplicate_within_claim:{name}={other}")
            for m in seen.match(h, claim_id):
                integrity.append(f"photo_seen_in_claim_{m['claim']}:{name}")
            hashes[name] = h

    per_image, quality_report = [], {}
    for name, img in imgs:
        if name.count("#f"):               # a video keyframe: the video floors (the sampler already applied them)
            from .video import BLUR_MIN_VIDEO, DARK_MIN_VIDEO
            q = quality(img, BLUR_MIN_VIDEO, DARK_MIN_VIDEO)
        else:
            q = quality(img)
        quality_report[name] = q
        if q["flags"]:
            flags.append(f"low_quality:{name}:{','.join(q['flags'])}")
            continue
        per_image.append((analyse or analyse_image)(img, name))

    dets = _fuse(per_image, min_support)
    if min_support > 1:
        # video: damage seen in a single keyframe is never dropped silently. It becomes a request for a clearer view
        # (a detection with no severity fails the engine's information gate -> ASK_MORE), never a smaller offer.
        have = {(d["part_class"], d["damage_class"]) for d in dets}
        for part in sorted({f["part_class"] for im in per_image for f in im["findings"]
                            if f["severity"] is not None and f["part_class"] != "unassigned"
                            and (f["part_class"], f["damage_class"]) not in have}):
            flags.append(f"single_frame_only:{part}")
            if part not in {d["part_class"] for d in dets}:
                dets.append({"part_class": part, "part_conf": 0.0, "damage_class": None, "damage_conf": 0.0, "severity": None,
                             "damage_area_fraction": None, "damage_source": "one keyframe only", "note": "seen in one keyframe only"})
    if any(f["part_class"] == "unassigned" for im in per_image for f in im["findings"]):
        flags.append("unassigned_damage")
    # heavy front/side crash: hidden damage (radiator support, airbags, pillars) is likely -> surveyor, never auto-offer
    severe = {d["part_class"] for d in dets if d["severity"] == "severe"}
    if (len(severe) >= HEAVY_SEVERE_PARTS or ("Hood" in severe and len(severe) >= 2)
            or {"Front-door", "Back-door"} <= severe):    # both doors severe = side impact at the B-pillar
        flags.append("structural_suspected")
    # damage seen only in close-ups where the whole panel is not visible: no severity -> ask for a wider photo
    sized = {d["part_class"] for d in dets}
    for part in sorted({f["part_class"] for im in per_image for f in im["findings"]
                        if f["severity"] is None and f["part_class"] != "unassigned"} - sized):
        flags.append(f"need_wider_photo:{part}")
        dets.append({"part_class": part, "part_conf": 0.0, "damage_class": None, "damage_conf": 0.0, "severity": None,
                     "damage_area_fraction": None, "damage_source": "close-up only", "note": "whole panel not visible"})

    plate_read = None
    if plate_reader:
        for (name, img), im in zip([x for x in imgs if not quality_report[x[0]]["flags"]], per_image):
            if im["plate_box"]:
                x1, y1, x2, y2 = im["plate_box"]
                pad = 6
                crop = img[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
                plate_read = plate_reader(crop)
                if plate_read:
                    break
        if plate_read is None and imgs:
            # capture protocol: the first photo is the number plate; read it whole if no plate was outlined
            plate_read = plate_reader(imgs[0][1])

    for name, h in hashes.items():
        seen.add(h, claim_id, name)
    if not dets and per_image:
        flags.append("no_damage_found")
    return {"image_id": claim_id, "plate_read": plate_read, "integrity_flags": integrity, "flags": flags,
            "detections": dets, "images": [n for n, _ in imgs], "quality": quality_report,
            "findings_by_image": {im["image_id"]: im["findings"] for im in per_image},
            "per_image": [{k: v for k, v in im.items() if k != "findings"} | {"n_findings": len(im["findings"])} for im in per_image]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--video")
    ap.add_argument("--claim-id")
    ap.add_argument("--plate-ocr", action="store_true", help="read the plate with Qwen (loads the VLM)")
    ap.add_argument("--out")
    a = ap.parse_args()
    reader = None
    if a.plate_ocr:
        from .qwen import QwenVL
        reader = QwenVL().read_plate
    v = run_claim(a.images, a.video, a.claim_id, reader)
    txt = json.dumps(v, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(txt)
    print(json.dumps({k: v[k] for k in ("plate_read", "integrity_flags", "flags")}, indent=1))
    for d in v["detections"]:
        print(f"  {d['part_class']:<14} {str(d['damage_class']):<13} {str(d['severity']):<9} area={d['damage_area_fraction']}"
              f"  part_conf={d['part_conf']} dmg_conf={d['damage_conf']}  [{d['damage_source']}]")


if __name__ == "__main__":
    main()
