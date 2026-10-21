"""Coverage of a rate card for one registration date: per (model, part) cell over the 8 models x 13 priced parts:
direct and generation-matched / direct but other generation / fallback (similar car) / none. Plus tier counts.
    python tools/ratecard_coverage.py [csv ...]"""
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autosettle_engine import config as C, engine as E  # noqa: E402

REG = date(2023, 6, 15)


def coverage(path):
    rc = E.RateCard(path)
    cells = Counter()
    for m in sorted(C.SEGMENT):
        for p in sorted(C.PRICED_PARTS):
            info = rc.lookup(m, p, REG)
            cells["none" if info is None else {"rate_card": "matched", "other_generation": "other_gen"}.get(info["status"], "fallback")] += 1
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    tiers = Counter(r["confidence"][0] for r in rows)
    direct = cells["matched"] + cells["other_gen"]
    return {"rows": len(rows), "tiers": dict(sorted(tiers.items())), "cells": dict(cells), "direct": direct}


if __name__ == "__main__":
    for p in sys.argv[1:] or ["autosettle_engine/rate_card_v2.csv", "autosettle_engine/rate_card_v3.csv"]:
        print(p, coverage(p))
