"""Measure the video path with the REAL models (GPU; run under the thermal guard).  python tools/video_eval.py [CLIP ...]
Reports seconds and peak VRAM per video and the decision. With no arguments it builds a looped video from one dev photo
(AEQUOUR_DEV_PHOTOS, file c05) and compares its offer with the single-photo offer. All clips named on the command line, and
the teammate's two clips, are SYNTHETIC; nothing here says anything about real walk-around footage."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import cv2
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from autosettle_engine import engine as E                       # noqa: E402
from autosettle_engine.dispute import ClaimSession              # noqa: E402
from autosettle_engine.tests.helpers import RC, policy          # noqa: E402
from autosettle_vision import pipeline as P                     # noqa: E402
from autosettle_vision.claim import engine_vision               # noqa: E402
from autosettle_vision.video import VideoRejected               # noqa: E402
from autosettle_vision.video_claim import run_video_claim       # noqa: E402


def decide(v):
    pol = policy("Swift", reg="2023-06-01")
    ev = {**engine_vision(v), "plate_read": pol.plate}
    r = ClaimSession(pol, RC).submit(ev)
    return r["decision"], r["offer"]


def timed(path):
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    seen = P.SeenStore(Path(tempfile.mkdtemp()) / "s.json")
    try:
        v = run_video_claim(path, "ve", seen)
    except VideoRejected as e:
        return {"clip": Path(path).name, "rejected": str(e)}
    sec = time.time() - t0
    d, o = decide(v)
    return {"clip": Path(path).name, "seconds": round(sec, 1), "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
            "decision": d, "offer": o, "keyframes": v["video"]["keyframes"], "continuity_breaks": v["video"]["continuity_breaks"],
            "flags": [f for f in v["flags"] if not f.startswith("no_camera")][:4], "integrity_flags": v["integrity_flags"],
            "detections": [(x["part_class"], x["damage_class"], x["severity"]) for x in v["detections"]]}


def main():
    out = []
    clips = [Path(a) for a in sys.argv[1:]]
    if not clips:
        dev = Path(os.environ["AEQUOUR_DEV_PHOTOS"]) / "c05_Abandoned_Suzuki_Osidge_London_2.jpg"
        img = cv2.imread(str(dev))
        d = Path(tempfile.mkdtemp())
        vw = cv2.VideoWriter(str(d / "loop.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (img.shape[1], img.shape[0]))
        for _ in range(30):
            vw.write(img)
        vw.release()
        photo = P.run_claim([dev], claim_id="photo", seen=P.SeenStore(Path(tempfile.mkdtemp()) / "s.json"))
        out.append({"single_photo": decide(photo)})
        clips = [d / "loop.mp4"]
    for c in clips:
        out.append(timed(c))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
