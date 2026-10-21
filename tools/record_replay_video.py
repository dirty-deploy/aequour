"""Record the SYNTHETIC walk-around through the real video pipeline (GPU; run under the thermal guard).

    python tools/record_replay_video.py [wide|close]      # needs AEQUOUR_DEV_PHOTOS (the folder with c05_Abandoned_Suzuki_Osidge_London_2.jpg)

Writes autosettle_api/replay_data/video/synthetic_walkaround[_close].json. The clip is a zoom and pan over one photo
(autosettle_vision/synthetic_clip.py), so it proves the video path runs, not that real walk-arounds work. The photo is not
stored in the repository and the record holds no thumbnails (the API rebuilds them from the photo when it is present)."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from autosettle_vision import pipeline as P                      # noqa: E402
from autosettle_vision import synthetic_clip as SC               # noqa: E402
from autosettle_vision.video_claim import run_video_claim        # noqa: E402

SRC = "c05_Abandoned_Suzuki_Osidge_London_2.jpg"
OUT_DIR = ROOT / "autosettle_api" / "replay_data" / "video"


def main(variant):
    key = "synthetic_walkaround" if variant == "wide" else "synthetic_walkaround_close"
    OUT = OUT_DIR / (key + ".json")
    photo = Path(os.environ["AEQUOUR_DEV_PHOTOS"]) / SRC
    data = photo.read_bytes()
    img = cv2.imread(str(photo))
    tmp = Path(tempfile.mkdtemp())
    clip = SC.write_mp4(img, tmp / (key + ".mp4"), variant)
    v = run_video_claim(clip, "recorded", P.SeenStore(tmp / "seen.json"))
    v["video"].pop("thumbnails", None)
    v["video"]["synthetic"] = True
    rec = {"key": key, "variant": variant, "label": "SYNTHETIC: a zoom and pan over one photo, not a real walk-around",
           "source_file": SRC, "sha256": hashlib.sha256(data).hexdigest(), "width": img.shape[1], "height": img.shape[0],
           "generator": {"fps": SC.FPS, "seconds": SC.SECONDS, "zoom_end": SC.VARIANTS[variant][0], "pan": SC.VARIANTS[variant][1]}, "vision": v}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    print("wrote", OUT, "| keyframes", v["video"]["keyframes"], "| breaks", v["video"]["continuity_breaks"],
          "| detections", [(d["part_class"], d["damage_class"], d["severity"]) for d in v["detections"]],
          "| flags", [f for f in v["flags"] if not f.startswith("no_camera")], "| integrity", v["integrity_flags"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wide")
