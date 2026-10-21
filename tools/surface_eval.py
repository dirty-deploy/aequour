"""Stage C.1: evaluate autosettle_vision.surface_check on the cached detections of the 41 dev photos (CPU; no model runs, no dev
evaluation of a new pipeline variant). A candidate is a cached dent-detector box at confidence >= 0.30 (the engine's floor).
'True damage' = the detector's named panel is a labelled damaged panel of that photo. 'False alarm' = any candidate on a photo
with no labelled damage.  python tools/surface_eval.py   (env AEQUOUR_DEV_PHOTOS, run from the repository root)"""
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import eval_dev as D                                   # noqa: E402
from autosettle_vision import pipeline as P, surface_check as S   # noqa: E402

rows = []
for f in D.FILES:
    if f in D.LOWQ:
        continue
    img = cv2.imread(str(D.DEV / f))
    gt_parts = {i["part"] for i in D.GT[f]["items"]}
    for d in D.RAW[f]["det"]:
        if d["conf"] < 0.30:
            continue
        allowed, _ = P.DET_MAP[d["cls"]]
        r = S.check(img, d["box"], d["conf"])
        kind = "false_alarm" if not gt_parts else ("true" if set(allowed) & gt_parts else "wrong_panel")
        rows.append({"file": f[:3], "cls": d["cls"], "conf": round(d["conf"], 3), "kind": kind, "flag": r["ask_for_clearer_photo"], "concavity": r["concavity"]})
tot = {k: sum(1 for r in rows if r["kind"] == k) for k in ("true", "false_alarm", "wrong_panel")}
fl = {k: sum(1 for r in rows if r["kind"] == k and r["flag"]) for k in tot}
out = {"candidates": len(rows), "counts": tot, "flagged": fl,
       "share_flagged": {k: (round(fl[k] / tot[k], 3) if tot[k] else None) for k in tot}, "rows": rows}
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
