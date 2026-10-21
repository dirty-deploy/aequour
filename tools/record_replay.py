"""Record REPLAY data for the demo scenarios from real pipeline runs (GPU).  python tools/record_replay.py
Each scenario names a dev photo (Wikimedia Commons, licence in test_photos/commons/SOURCES.csv). The photo itself is never
committed; only the pipeline's output (parts, boxes, polygons, flags) and the photo's SHA-256 are stored."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from autosettle_vision import pipeline as P  # noqa: E402

DEV = Path(os.environ.get("AEQUOUR_DEV_PHOTOS", ROOT / "test_photos" / "commons"))
PHOTOS = {
    "swift_front": "c05_Abandoned_Suzuki_Osidge_London_2.jpg",
    "alto_crash": "c53_Alto_800_accident.jpg",
    "chennai_street": "c44_Chennai_damage_1.jpg",
}
OUT = ROOT / "autosettle_api" / "replay_data"


def main():
    for key, name in PHOTOS.items():
        path = DEV / name
        seen = P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json")
        v = P.run_claim([path], claim_id="replay-" + key, seen=seen)
        h, w = cv2.imread(str(path)).shape[:2]
        rec = {"key": key, "source_file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "width": w, "height": h,
               "vision": v}
        (OUT / (key + ".json")).write_text(json.dumps(rec, indent=1, default=str))
        print(key, name, [(d["part_class"], d["damage_class"], d["severity"]) for d in v["detections"]], v["flags"], v["integrity_flags"])


if __name__ == "__main__":
    main()
