"""
One command for the dev-photo evaluation.  Every number in the final run's reports comes from this file.

    python tools/eval_dev.py                 replay the Run 2 table from the cache (CPU only, seconds)
    python tools/eval_dev.py --live          run the real pipeline on the 41 dev photos (GPU; use tools/guard wrapper)
    python tools/eval_dev.py --live --variant crops     a pipeline variant (counts against the 3-evaluation limit)

The 41 dev photos are evaluation only: nothing here trains or calibrates on them.
Inputs (not in the repository): the Run 2 cache `run2/cache/dev_raw.json` and `run1/cache/dev_vision.json`
(the second is in the repository), the photos (env AEQUOUR_DEV_PHOTOS, default test_photos/commons), and the
dev-evaluation counter file (env AEQUOUR_EVAL_COUNT, default runs/DEV_EVAL_COUNT.txt).
The held-out folder is never read.
"""
import argparse
import csv
import json
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from autosettle_engine import engine as E                       # noqa: E402
from autosettle_engine.tests.helpers import RC, policy          # noqa: E402
from autosettle_vision import pipeline as P                     # noqa: E402
from autosettle_vision.claim import engine_vision               # noqa: E402

DEV = Path(os.environ.get("AEQUOUR_DEV_PHOTOS", ROOT / "test_photos" / "commons"))
COUNTER = Path(os.environ.get("AEQUOUR_EVAL_COUNT", ROOT / "runs" / "DEV_EVAL_COUNT.txt"))
RAW = json.loads((ROOT / "run2" / "cache" / "dev_raw.json").read_text())
CACHE = json.loads((ROOT / "run1" / "cache" / "dev_vision.json").read_text())
GT = {}
for r in csv.DictReader(open(ROOT / "test_photos" / "commons" / "ground_truth.csv", encoding="utf-8")):
    items = []
    for it in filter(None, (x.strip() for x in r["damage"].split(";"))):
        part, dclass, sev = (it.split(":") + ["", ""])[:3]
        items.append({"part": part, "damage": dclass, "severity": sev})
    GT[r["file"]] = {"items": items, "car": r["car"]}
LOWQ = {f for f, v in CACHE.items() if any(x.startswith("low_quality:") for x in v["flags"])}
FILES = list(RAW)
MODELS = {m for (m, _) in RC.rows}


def pol_for(car):
    for m in sorted(MODELS, key=len, reverse=True):
        if m.lower() in car.lower():
            return policy(m, reg="2023-06-01")
    return policy("Swift", reg="2023-06-01")


# ------------------------------------------------------------ cache replay (Run 2 harness)
def _mask(poly, w, h):
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.asarray(poly, np.int32)], 1)
    return m


_pc = {}


def parts_of(f):
    if f not in _pc:
        R = RAW[f]
        _pc[f] = [{"part_class": p["part_class"], "conf": p["conf"], "mask": m, "poly": p["poly"]}
                  for p in R["parts"] if (m := _mask(p["poly"], R["w"], R["h"])).sum() > 0]
    return _pc[f]


def findings(f, thr):
    """Replay of pipeline.analyse_image at detector confidence thr on cached raw output."""
    if f in LOWQ:
        return []
    R, parts = RAW[f], parts_of(f)
    h, w = R["h"], R["w"]

    def assign(dm, allowed):
        need = P.MIN_OVERLAP_NAMED if allowed else P.MIN_OVERLAP
        best = None
        for p in parts:
            if allowed and p["part_class"] not in allowed:
                continue
            ov = float((dm & p["mask"]).sum()) / max(dm.sum(), 1)
            if ov >= need and (best is None or ov > best[0]):
                best = (ov, p)
        return best

    out = []
    for d in R["det"]:
        if d["conf"] < thr - 1e-9:
            continue
        allowed, dclass = P.DET_MAP[d["cls"]]
        x1, y1, x2, y2 = [int(round(v)) for v in d["box"]]
        dm = np.zeros((h, w), np.uint8)
        dm[max(0, y1):max(0, y2), max(0, x1):max(0, x2)] = 1
        hit = assign(dm, set(allowed))
        if hit:
            out.append({"kind": "masked", "part_class": hit[1]["part_class"], "damage_class": dclass, "damage_conf": d["conf"]})
        else:
            out.append({"kind": "named", "part_class": allowed[0] if len(allowed) == 1 else "unassigned", "damage_class": dclass,
                        "damage_conf": d["conf"]})
    for m_ in RAW[f]["merged"]:
        if m_["conf"] < max(P.CONF_MERGED, thr) or m_["cls"] not in P.MERGED_CLASSES:
            continue
        hit = assign(_mask(m_["poly"], w, h), None)
        if hit and hit[1]["part_class"] not in P.DET_PARTS:
            out.append({"kind": "masked", "part_class": hit[1]["part_class"], "damage_class": m_["cls"], "damage_conf": m_["conf"]})
    return out


def predicted(f, thr):
    return {x["part_class"] for x in findings(f, thr) if x["kind"] == "masked"}


def replay_table():
    gt_pairs = [(f, it["part"]) for f in FILES for it in GT[f]["items"]]
    seg = {f: {p["part_class"] for p in parts_of(f)} for f in FILES}
    t = {"gt_parts": len(gt_pairs),
         "found_0.30": sum(1 for f, p in gt_pairs if p in predicted(f, 0.30)),
         "found_0.15": sum(1 for f, p in gt_pairs if p in predicted(f, 0.15)),
         "found_0.05": sum(1 for f, p in gt_pairs if p in predicted(f, 0.05)),
         "never_segmented": sum(1 for f, p in gt_pairs if p not in seg[f])}
    t["segmented"] = t["gt_parts"] - t["never_segmented"]
    return t


def decisions_from_vision(vis_by_file):
    """Engine decision per photo with the plate treated as read; silent misses = labelled damaged parts missed inside an OFFER."""
    dec, silent, escal, offers, off_clean, offer_files = Counter(), 0, 0, 0, 0, []
    per = {}
    for f in FILES:
        pol = pol_for(GT[f]["car"])
        ev = {**vis_by_file[f], "plate_read": pol.plate}
        res = E.assess(pol, ev, RC)
        dec[res["decision"]] += 1
        found = {d["part_class"] for d in ev["detections"] if d.get("damage_class")}
        per[f] = {"decision": res["decision"], "offer": res["offer"], "found": sorted(found)}
        if res["decision"] == "OFFER":
            offers += 1
            offer_files.append(f)
            if not GT[f]["items"]:
                off_clean += 1
        for it in GT[f]["items"]:
            if it["part"] not in found:
                silent += res["decision"] == "OFFER"
                escal += res["decision"] != "OFFER"
    return {"decisions": dict(dec), "offer_claims": offers, "silent_misses": silent, "missed_but_escalated": escal,
            "offers_on_clean_photos": off_clean, "n_clean_photos": sum(1 for f in FILES if not GT[f]["items"])}, per


def cache_vision():
    return {f: CACHE[f]["engine_vision"] for f in FILES}


# ------------------------------------------------------------ live pipeline
def live(variant):
    if variant != "baseline":
        n = int(COUNTER.read_text().strip() or 0) if COUNTER.exists() else 0
        if n >= 3:
            sys.exit("dev evaluation limit (3) reached")
        COUNTER.parent.mkdir(parents=True, exist_ok=True)
        COUNTER.write_text(str(n + 1))
    if variant == "crops":
        from autosettle_vision import crops
        crops.enable()
    seen = P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json")
    vis, t0 = {}, time.time()
    for f in FILES:
        v = P.run_claim([DEV / f], claim_id=f, seen=seen)
        vis[f] = engine_vision(v)
        vis[f]["_dets_full"] = v["detections"]
    sec = (time.time() - t0) / len(FILES)
    gt_pairs = [(f, it["part"]) for f in FILES for it in GT[f]["items"]]
    found_pairs = {(f, p) for f, p in gt_pairs if p in {d["part_class"] for d in vis[f]["detections"] if d.get("damage_class")}}
    out, per = decisions_from_vision({f: {k: v for k, v in vis[f].items() if k != "_dets_full"} for f in FILES})
    return {"variant": variant, "e2e_found_of_74": len(found_pairs), "sec_per_img": round(sec, 2), **out}, per, vis


# groups of dev photos of the same car or scene (from the file notes in ground_truth.csv)
GROUPS = [["c04_Abandoned_Suzuki_Osidge_London.jpg", "c05_Abandoned_Suzuki_Osidge_London_2.jpg"],
          ["c13_Crash_test_car_from_the_West_Germany_USA.jpg", "c24_Crash_test_car_from_the_West_Germany_USA.jpg"],
          ["c20_Damaged_car_on_road_Dubai_01.jpg", "c21_Damaged_car_on_road_Dubai_02.jpg"]]


def fusion_groups():
    """Multi-view fusion experiment (counts as ONE dev evaluation): for groups of photos of the same car, parts found with each
    photo alone (union) against the parts found when the photos are submitted as one claim. Fusion keeps every detection, so
    the expected result is no change in parts found; what can change is the claim-level decision."""
    n = int(COUNTER.read_text().strip() or 0) if COUNTER.exists() else 0
    if n >= 3:
        sys.exit("dev evaluation limit (3) reached")
    COUNTER.parent.mkdir(parents=True, exist_ok=True)
    COUNTER.write_text(str(n + 1))
    groups = [[f for f in g if f in GT] for g in GROUPS]
    groups += [[f for f in GT if f[:3] in ("c48", "c50", "c51")]]
    out = []
    for g in groups:
        seen = P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json")
        labelled = {i["part"] for f in g for i in GT[f]["items"]}
        singles = {}
        for f in g:
            v = P.run_claim([DEV / f], claim_id="s_" + f[:3], seen=P.SeenStore(Path(tempfile.mkdtemp()) / "seen.json"))
            singles[f] = {d["part_class"] for d in v["detections"] if d.get("damage_class")}
        v = P.run_claim([DEV / f for f in g], claim_id="grp_" + g[0][:3], seen=seen)
        fused = {d["part_class"] for d in v["detections"] if d.get("damage_class")}
        pol = pol_for(GT[g[0]]["car"])
        ev = {**engine_vision(v), "plate_read": pol.plate}
        res = E.assess(pol, ev, RC)
        before = set().union(*singles.values())
        out.append({"photos": [f[:3] for f in g], "labelled_parts": sorted(labelled), "found_alone_union": sorted(before & labelled),
                    "found_fused": sorted(fused & labelled), "labelled_n": len(labelled), "before_n": len(before & labelled),
                    "after_n": len(fused & labelled), "fused_decision": res["decision"], "integrity_flags": v["integrity_flags"]})
    return {"variant": "fusion", "groups": len(out), "results": out,
            "note": "fewer than 3 groups cannot support a conclusion" if len(out) < 3 else "4 small groups: anecdote, not evidence"}


def crops_replay():
    """found-of-74 at 0.30 and 0.15 with per-panel crops: cached whole-frame detector output plus live crop detections on the
    cached part polygons (detector at 0.15), merged by class-wise NMS, then the same replay as the baseline table."""
    from autosettle_vision import crops as C
    M = P.models()
    names = M["det"].names
    inv = {v: k for k, v in names.items()}
    orig = {f: RAW[f]["det"] for f in FILES}
    t0 = time.time()
    for f in FILES:
        if f in LOWQ:
            continue
        img = cv2.imread(str(DEV / f))
        polys = [p["poly"] for p in RAW[f]["parts"] if p["part_class"] in P.DET_PARTS]
        extra = C.crop_dets(img, C.panel_boxes(polys, img.shape), M["det"], 0.15)
        base = [(d["box"], d["conf"], float(inv[d["cls"]])) for d in orig[f]]
        RAW[f]["det"] = [{"cls": names[int(k)], "conf": c, "box": b} for b, c, k in C.nms(base + extra)]
    sec = (time.time() - t0) / len(FILES)
    gt_pairs = [(f, it["part"]) for f in FILES for it in GT[f]["items"]]
    res = {"found_0.30": sum(1 for f, p in gt_pairs if p in predicted(f, 0.30)), "found_0.15": sum(1 for f, p in gt_pairs if p in predicted(f, 0.15)),
           "found_0.30_pairs": [(f, p) for f, p in gt_pairs if p in predicted(f, 0.30)], "sec_per_img_crops": round(sec, 2)}
    clean = [f for f in FILES if not GT[f]["items"]]
    res["false_alarm_parts_0.30_clean"] = sum(len(predicted(f, 0.30)) for f in clean)
    for f in FILES:
        RAW[f]["det"] = orig[f]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.variant == "fusion":
        txt = json.dumps(fusion_groups(), indent=1, default=str)
        if a.out:
            Path(a.out).write_text(txt)
        print(txt)
        return
    res = {"replay_table": replay_table()}
    if a.variant == "crops":
        n = int(COUNTER.read_text().strip() or 0) if COUNTER.exists() else 0
        if n + 1 > 3:
            sys.exit("dev evaluation limit (3) reached")
        res["crops_replay"] = crops_replay()
        res["baseline_false_alarm_parts_0.30_clean"] = sum(len(predicted(f, 0.30)) for f in FILES if not GT[f]["items"])
        base_found = {(f, it["part"]) for f in FILES for it in GT[f]["items"] if it["part"] in predicted(f, 0.30)}
        res["previously_found_now_lost_0.30"] = sorted(base_found - {tuple(x) for x in res["crops_replay"]["found_0.30_pairs"]})
    base, per = decisions_from_vision(cache_vision())
    res["cache_decisions"] = base
    if a.live:
        lv, lper, vis = live(a.variant)
        res["live"] = lv
        res["live_vs_cache_pairs_changed"] = sorted({(f, d["part_class"], d["damage_class"]) for f in FILES for d in vis[f]["detections"] if d.get("damage_class")}
                                                    ^ {(f, d["part_class"], d["damage_class"]) for f in FILES for d in cache_vision()[f]["detections"] if d.get("damage_class")})
    txt = json.dumps(res, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
