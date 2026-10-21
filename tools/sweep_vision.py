"""Sweep inference size and detector confidence on the Commons test photos; log area fraction vs labelled severity."""
import csv
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autosettle_vision import pipeline as P  # noqa: E402
from autosettle_vision.photo_eval import parse_gt  # noqa: E402

D = Path("test_photos/commons")
gt = {r["file"]: parse_gt(r["damage"]) for r in csv.DictReader(open(D / "ground_truth.csv", encoding="utf-8"))}
imgs = {f: cv2.imread(str(D / f)) for f in gt}
out = {}
for imgsz in (640, 960, 1280):
    for conf in (0.25, 0.15):
        P.IMGSZ, P.CONF_DET = imgsz, conf
        tp = fn = fp = 0
        fr = []
        for f, truth in gt.items():
            found = {}
            for x in P.analyse_image(imgs[f], f)["findings"]:
                if x["part_class"] != "unassigned":
                    found.setdefault(x["part_class"], x)
            tparts = {t["part"]: t for t in truth}
            for p, t in tparts.items():
                if p in found:
                    tp += 1
                    if found[p]["damage_area_fraction"] is not None:
                        fr.append((t["severity"], found[p]["damage_area_fraction"], found[p]["damage_source"]))
                else:
                    fn += 1
            fp += sum(1 for p in found if p not in tparts)
        out[f"{imgsz}/{conf}"] = {"recall": round(tp / (tp + fn), 3), "precision": round(tp / max(tp + fp, 1), 3),
                                  "tp": tp, "fp": fp, "fractions": fr}
        print(imgsz, conf, out[f"{imgsz}/{conf}"]["recall"], out[f"{imgsz}/{conf}"]["precision"], tp, fp, flush=True)
Path("runs/sweep_vision.json").write_text(json.dumps(out, indent=1))
