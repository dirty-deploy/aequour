"""
Evaluate the vision pipeline + engine on test photos from OUTSIDE the training data (Wikimedia Commons set).

    python -m autosettle_vision.photo_eval [DIR]     -> runs/photo_eval.json + printed table

Ground truth: DIR/ground_truth.csv  (file, car, damage) where damage = "Part:Class:severity; ..." written by
looking at each photo (Claude, 20 Oct 2026). Severity labels are a human judgement, not a measurement.
Part-level scoring: a ground-truth damaged part counts as found if the pipeline returns a detection on the same part
(Front-door/Back-door and Headlight/Fender are NOT merged). Each photo is run as its own claim.
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

from autosettle_engine import engine as E
from autosettle_engine.tests.helpers import RC, policy

from . import pipeline as P
from .claim import engine_vision


def parse_gt(s):
    out = []
    for item in filter(None, (x.strip() for x in s.split(";"))):
        part, dclass, sev = (item.split(":") + ["", ""])[:3]
        out.append({"part": part, "damage": dclass, "severity": sev})
    return out


def main(d="test_photos/commons"):
    d = Path(d)
    gt = {r["file"]: r for r in csv.DictReader(open(d / "ground_truth.csv", encoding="utf-8"))}
    pol = policy("Swift", reg="2023-06-01")
    seen = P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json")
    rows = []
    tp = fn = fp = cls_ok = sev_ok = 0
    decisions = {}
    for f, g in sorted(gt.items()):
        truth = parse_gt(g["damage"])
        v = P.run_claim([d / f], claim_id=f, seen=seen)
        ev = engine_vision(v)
        ev["plate_read"] = pol.plate          # plates in these photos are foreign: plate check is out of scope here
        res = E.assess(pol, ev, RC)
        got = {"OFFER": "OFFER", "ASK_MORE": "ASK_MORE"}.get(res["decision"], "HUMAN")
        key = f"expect {g['expect']} -> {got}"
        decisions[key] = decisions.get(key, 0) + 1
        found = {x["part_class"]: x for x in v["detections"] if x.get("damage_class")}
        tparts = {t["part"]: t for t in truth}
        for p, t in tparts.items():
            if p in found:
                tp += 1
                cls_ok += found[p]["damage_class"] == t["damage"]
                sev_ok += found[p]["severity"] == t["severity"]
            else:
                fn += 1
        fp += sum(1 for p in found if p not in tparts)
        rows.append({"file": f, "car": g["car"], "truth": truth,
                     "pred": [{k: x.get(k) for k in ("part_class", "damage_class", "severity", "damage_conf", "damage_source")}
                              for x in v["detections"]],
                     "flags": v["flags"], "decision": res["decision"], "reasons": res["reasons"], "offer": res["offer"]})
        print(f"{f[:38]:<38} {res['decision']:<9} truth={[t['part'] for t in truth]} "
              f"pred={[(x['part_class'], x['damage_class'], x['severity']) for x in v['detections']]}")
    summary = {"photos": len(rows), "gt_damaged_parts": tp + fn, "found": tp, "missed": fn, "extra": fp,
               "part_recall": round(tp / max(tp + fn, 1), 3), "part_precision": round(tp / max(tp + fp, 1), 3),
               "damage_class_agree_on_found": round(cls_ok / max(tp, 1), 3),
               "severity_agree_on_found": round(sev_ok / max(tp, 1), 3),
               "decisions": dict(sorted(decisions.items())),
               "auto_offer_on_human_cases": decisions.get("expect HUMAN -> OFFER", 0),
               "human_cases": sum(v for k, v in decisions.items() if k.startswith("expect HUMAN"))}
    print(json.dumps(summary, indent=1))
    Path("runs/photo_eval.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:])
