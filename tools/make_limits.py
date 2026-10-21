"""Generate docs/LIMITS.json (the source of GET /limits and the app's Known-limits panel) from docs/DECK_NUMBERS_FINAL.md.
The page can then say no more than the numbers file says.   python tools/make_limits.py"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOW = ["recall", "never_outlined", "silent_misses", "offers", "heldout", "scratch", "severity", "plates", "crops", "video_tests", "engine", "prices", "quotes"]
NOT_MEASURED = ["Accuracy on real Indian claim photos at scale", "Severity accuracy (no public dataset labels severity)",
                "Handwritten garage quotes and real garage invoices", "Anything about real walk-around videos"]


def rows(text):
    out = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and re.fullmatch(r"[a-z_]+", cells[0]) and cells[0] != "id":
            out[cells[0]] = dict(zip(("id", "label", "value", "source", "detail", "date", "caveat"), cells))
    return out


def main():
    src = (ROOT / "docs" / "DECK_NUMBERS_FINAL.md").read_text(encoding="utf-8")
    r = rows(src)
    items = [{k: r[i][k] for k in ("id", "label", "value", "detail", "caveat", "source")} for i in SHOW]
    (ROOT / "docs" / "LIMITS.json").write_text(json.dumps({
        "generated_by": "tools/make_limits.py from docs/DECK_NUMBERS_FINAL.md",
        "headline": "What this system measured, and what it has not.", "items": items, "not_measured": NOT_MEASURED}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote docs/LIMITS.json with", len(items), "items")


if __name__ == "__main__":
    main()
