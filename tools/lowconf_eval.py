"""Task 3: effect of the low-confidence-severe rule on the 41 Wikimedia Commons DEV photos (never the held-out set).

    python tools/run_guarded.py -- env/Scripts/python.exe tools/lowconf_eval.py

Step 1 (GPU, once): run the app's vision pipeline on each dev photo, one claim per photo, and cache the output to
run1/cache/dev_vision.json. Re-runs read the cache. Step 2 (CPU): assess every cached claim with the plate assumed
verified, rule off (LOW_CONF_SEVERE = 0) and rule on (0.5), and score severe detections against the labels.
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import os  # noqa: E402
os.chdir(ROOT)

from autosettle_engine import config as C, engine as E  # noqa: E402
from autosettle_engine.tests.helpers import RC, policy  # noqa: E402

DEV = ROOT / "test_photos" / "commons"
CACHE = ROOT / "run1" / "cache" / "dev_vision.json"


def parse_gt(s):
    out = []
    for item in filter(None, (x.strip() for x in s.split(";"))):
        part, dclass, sev = (item.split(":") + ["", ""])[:3]
        out.append({"part": part, "damage": dclass, "severity": sev})
    return out


def detect_all(gt):
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    sys.path.insert(0, str(ROOT / "tools"))
    import thermal as T
    from autosettle_vision import pipeline as P
    from autosettle_vision.claim import engine_vision
    T.cooldown_until(65, 72)
    seen = P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json")
    out = {}
    for i, f in enumerate(sorted(gt)):
        if i and i % 10 == 0:
            T.wait_if_hot()
        v = P.run_claim([DEV / f], claim_id=f, seen=seen)
        out[f] = {"engine_vision": engine_vision(v),
                  "detections": [{k: d.get(k) for k in ("part_class", "damage_class", "severity", "damage_conf",
                                                        "damage_area_fraction", "damage_source")} for d in v["detections"]],
                  "flags": v["flags"]}
        print(f"{i + 1}/{len(gt)} {f}", flush=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, indent=1, default=str))
    return out


def main():
    gt = {r["file"]: r for r in csv.DictReader(open(DEV / "ground_truth.csv", encoding="utf-8"))}
    cache = detect_all(gt)
    pol = policy("Swift", reg="2023-06-01")
    rows, low = [], []
    for f, g in sorted(gt.items()):
        ev = dict(cache[f]["engine_vision"])
        ev["plate_read"] = pol.plate                    # plate assumed verified (photos carry foreign plates)
        C.LOW_CONF_SEVERE = 0.0
        before = E.assess(pol, ev, RC)
        C.LOW_CONF_SEVERE = 0.5
        after = E.assess(pol, ev, RC)
        truth = {t["part"]: t for t in parse_gt(g["damage"])}
        for d in cache[f]["detections"]:
            if d["severity"] == "severe" and (d["damage_conf"] or 0) < 0.5:
                t = truth.get(d["part_class"])
                low.append({"file": f, "part": d["part_class"], "damage": d["damage_class"], "conf": d["damage_conf"],
                            "part_correct": t is not None, "severity_correct": bool(t and t["severity"] == "severe"),
                            "expect": g["expect"]})
        rows.append({"file": f, "expect": g["expect"], "before": before["decision"], "offer_before": before["offer"],
                     "after": after["decision"], "offer_after": after["offer"], "reasons_after": after["reasons"]})
    C.LOW_CONF_SEVERE = 0.5
    sev_all = [d for f in cache for d in cache[f]["detections"] if d["severity"] == "severe"]
    summary = {
        "photos": len(rows),
        "offers_before": sum(r["before"] == "OFFER" for r in rows),
        "offers_after": sum(r["after"] == "OFFER" for r in rows),
        "offers_removed": [(r["file"], r["expect"], r["offer_before"]) for r in rows if r["before"] == "OFFER" and r["after"] != "OFFER"],
        "offers_before_by_expect": {e: sum(r["before"] == "OFFER" and r["expect"] == e for r in rows) for e in ("OFFER", "HUMAN", "ASK_MORE")},
        "offers_after_by_expect": {e: sum(r["after"] == "OFFER" and r["expect"] == e for r in rows) for e in ("OFFER", "HUMAN", "ASK_MORE")},
        "severe_detections": len(sev_all),
        "severe_below_0_5": len(low),
        "severe_below_0_5_part_correct": sum(d["part_correct"] for d in low),
        "severe_below_0_5_part_and_severity_correct": sum(d["severity_correct"] for d in low),
    }
    print(json.dumps(summary, indent=1))
    (ROOT / "run1" / "lowconf_eval.json").write_text(json.dumps({"summary": summary, "low": low, "rows": rows}, indent=1, default=str))


if __name__ == "__main__":
    main()
