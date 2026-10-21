"""
Attacks on the video path, in the style of autosettle_engine.exploit_suite. Each returns (held, detail); "held" means no
rupee moved outside the rules and no bad file produced an offer.  Run:  python -m autosettle_vision.video_attacks
No GPU: the photo analyser is replaced by the recorded Swift front-end findings, the engine runs for real.
All videos here are SYNTHETIC (generated textures, not footage of cars).
"""
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

from autosettle_engine import engine as E
from autosettle_engine.dispute import ClaimSession
from autosettle_engine.tests.helpers import RC, policy

from . import pipeline as P
from . import video as V
from .claim import engine_vision
from .video_claim import run_video_claim

REPLAY = Path(__file__).resolve().parent.parent / "autosettle_api" / "replay_data" / "swift_front.json"
W, H = 480, 360


def scene(seed):
    """A strongly textured synthetic scene (stands in for 'one car')."""
    rng = np.random.default_rng(seed)
    img = rng.integers(40, 200, (H, W, 3), dtype=np.uint8)
    img = cv2.GaussianBlur(img, (0, 0), 2)
    for _ in range(140):
        c = tuple(int(x) for x in rng.integers(0, 255, 3))
        p = (int(rng.integers(0, W)), int(rng.integers(0, H)))
        if rng.random() < 0.5:
            cv2.circle(img, p, int(rng.integers(4, 30)), c, -1)
        else:
            cv2.rectangle(img, p, (p[0] + int(rng.integers(6, 50)), p[1] + int(rng.integers(6, 40))), c, -1)
    return img


def view(base, k, n):
    """Frame k of n: a smooth camera drift over the same scene."""
    t = k / max(1, n - 1)
    M = np.float32([[1 + 0.05 * t, 0, 25 * t], [0, 1 + 0.05 * t, 12 * t]])
    return cv2.warpAffine(base, M, (W, H), borderMode=cv2.BORDER_REFLECT)


def write_video(path, frames, fps=10):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (frames[0].shape[1], frames[0].shape[0]))
    for f in frames:
        vw.write(f)
    vw.release()
    return path


def drift_video(path, seed=1, n=60, fps=10):
    base = scene(seed)
    return write_video(path, [view(base, k, n) for k in range(n)], fps)


def fake_analyser(only_frames=None):
    """Replays the recorded Swift findings for every frame (or only for the listed frame positions)."""
    rec = json.loads(REPLAY.read_text(encoding="utf-8"))["vision"]
    findings = next(iter(rec["findings_by_image"].values()))
    counter = {"i": -1}

    def analyse(img, name):
        counter["i"] += 1
        use = only_frames is None or counter["i"] in only_frames
        return {"image_id": name, "findings": [dict(f) for f in findings] if use else [], "parts_seen": [], "plate_box": None}
    return analyse


def _decide(v, plate=True):
    pol = policy("Swift", reg="2023-06-01")
    ev = engine_vision(v)
    if plate:
        ev["plate_read"] = pol.plate
    s = ClaimSession(pol, RC)
    return s.submit(ev), ev


def _seen():
    return P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json")


def single_photo_offer():
    rec = json.loads(REPLAY.read_text(encoding="utf-8"))["vision"]
    res, _ = _decide(rec)
    return res


def control_looped_video_matches_photo():
    d = Path(tempfile.mkdtemp())
    base = scene(3)
    p = write_video(d / "loop.mp4", [base.copy() for _ in range(30)])
    v = run_video_claim(p, "loop", _seen(), fake_analyser())
    res, ev = _decide(v)
    ref = single_photo_offer()
    ok = res["decision"] == "OFFER" and res["offer"] == ref["offer"] and len({x["part_class"] for x in ev["detections"]}) == len(ev["detections"])
    return ok, f"video offer {res['offer']} vs photo offer {ref['offer']}, detections {len(ev['detections'])}"


def spliced_video_escalates():
    d = Path(tempfile.mkdtemp())
    a, b = scene(1), scene(2)
    frames = [view(a, k, 30) for k in range(30)] + [view(b, k, 30) for k in range(30)]
    v = run_video_claim(write_video(d / "splice.mp4", frames), "splice", _seen(), fake_analyser())
    res, _ = _decide(v)
    return res["decision"] == "ESCALATE" and res["offer"] is None, f"decision {res['decision']}, integrity {v['integrity_flags']}"


def black_video_rejected():
    d = Path(tempfile.mkdtemp())
    p = write_video(d / "black.mp4", [np.zeros((H, W, 3), np.uint8) for _ in range(30)])
    try:
        run_video_claim(p, "black", _seen(), fake_analyser())
    except V.VideoRejected as e:
        return True, f"rejected: {e}"
    return False, "a black video was accepted"


def one_frame_video_rejected():
    d = Path(tempfile.mkdtemp())
    p = write_video(d / "one.mp4", [scene(5)])
    try:
        v = run_video_claim(p, "one", _seen(), fake_analyser())
    except V.VideoRejected as e:
        return True, f"rejected: {e}"
    res, _ = _decide(v)
    return res["decision"] != "OFFER", f"decision {res['decision']}"


def overlong_video_rejected():
    d = Path(tempfile.mkdtemp())
    base = scene(6)
    small = cv2.resize(base, (96, 72))
    p = write_video(d / "long.mp4", [small for _ in range(130)], fps=2)       # 65 s
    try:
        run_video_claim(p, "long", _seen(), fake_analyser())
    except V.VideoRejected as e:
        return True, f"rejected: {e}"
    return False, "an over-long video was accepted"


def non_video_file_rejected():
    d = Path(tempfile.mkdtemp())
    p = d / "x.mp4"
    p.write_bytes(np.random.default_rng(0).bytes(5000))
    try:
        run_video_claim(p, "junk", _seen(), fake_analyser())
    except V.VideoRejected as e:
        return True, f"rejected: {e}"
    return False, "a non-video file was accepted"


def one_frame_ghost_never_offers_or_lowers():
    """Damage seen in a single keyframe of a clip is never dropped silently: it asks for a clearer view, it never pays."""
    d = Path(tempfile.mkdtemp())
    p = drift_video(d / "ghost.mp4", seed=4, n=40)
    v = run_video_claim(p, "ghost", _seen(), fake_analyser(only_frames={3}))
    res, ev = _decide(v)
    flagged = any(f.startswith("single_frame_only:") for f in v["flags"])
    return res["decision"] == "ASK_MORE" and res["offer"] is None and flagged, f"decision {res['decision']}, flags {v['flags'][:3]}"


ATTACKS = [spliced_video_escalates, black_video_rejected, one_frame_video_rejected, overlong_video_rejected,
           non_video_file_rejected, one_frame_ghost_never_offers_or_lowers]
CONTROLS = [control_looped_video_matches_photo]


def main():
    held = 0
    for f in ATTACKS:
        ok, detail = f()
        held += ok
        print(("HELD  " if ok else "BROKE ") + f"{f.__name__:<42} {detail}")
    for f in CONTROLS:
        ok, detail = f()
        print(("CONTROL ok  " if ok else "CONTROL FAILED ") + f"{f.__name__:<34} {detail}")
    print(f"\n{held}/{len(ATTACKS)} video attack scripts held (+{len(CONTROLS)} control)")
    return held == len(ATTACKS)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
