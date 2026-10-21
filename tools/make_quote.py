"""Make a SYNTHETIC garage-quote image (and its JSON) from any claim, with one line inflated, so the quote-dispute flow can be
tested on any claim without a real document.

    python tools/make_quote.py --api http://127.0.0.1:8000 --claim <claim id> [--inflate part=2.5] [--out quote.jpg] [--post]
    python tools/make_quote.py --lines lines.json [--inflate labour=3]

The lines come from GET /claims/<id> (the customer view: each engine line has the genuine part price, labour and painting).
Inflate keys: part, labour, paint (a factor; default part=2.5). The image is stamped SYNTHETIC. With --post the JSON quote
is sent to the claim so the verdicts can be seen straight away. Nothing here ever changes an offer except through the same
quote check a real quote goes through."""
import argparse
import json
import random
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from autosettle_vision import quote_gen  # noqa: E402


def lines_to_quote(engine_lines, inflate):
    """A plausible garage quote for these engine lines: one part line per replaced part at the genuine price, one labour line
    and one painting line (gross), with the chosen kind of line multiplied by its factor."""
    f = {"part": 1.0, "labour": 1.0, "paint": 1.0, **inflate}
    q = []
    for ln in engine_lines:
        name = ln["part_class"].replace("-", " ").title()
        if ln["action"] == "replace" and ln.get("part_mrp"):
            u = round(ln["part_mrp"] * f["part"])
            q.append({"description": f"{name} Assy", "type": "part", "qty": 1, "unit_price": u, "total": u})
    labour = round(sum(ln.get("labour", 0) for ln in engine_lines) * f["labour"])
    paint = round(sum(ln.get("paint_gross", 0) for ln in engine_lines) * f["paint"])
    if labour:
        q.append({"description": "Labour", "type": "labour", "qty": 1, "unit_price": labour, "total": labour})
    if paint:
        q.append({"description": "Painting", "type": "paint", "qty": 1, "unit_price": paint, "total": paint})
    sub = sum(x["total"] for x in q)
    return {"lines": q, "gst_percent": 18, "grand_total": round(sub * 1.18)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--claim")
    ap.add_argument("--lines", help="a JSON file with the engine lines instead of a claim")
    ap.add_argument("--inflate", default="part=2.5", help="kind=factor, e.g. part=2.5 or labour=3 (default part=2.5)")
    ap.add_argument("--out", default="synthetic_quote.jpg")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--post", action="store_true", help="send the JSON quote to the claim and print the verdicts")
    a = ap.parse_args()
    if a.lines:
        engine_lines = json.loads(Path(a.lines).read_text())
    elif a.claim:
        engine_lines = json.loads(urllib.request.urlopen(f"{a.api}/claims/{a.claim}").read())["lines"]
    else:
        sys.exit("give --claim <id> (with --api) or --lines <file>")
    if not engine_lines:
        sys.exit("this claim has no priced lines (no offer), so there is nothing to quote")
    k, _, v = a.inflate.partition("=")
    if k not in ("part", "labour", "paint"):
        sys.exit("--inflate kind must be part, labour or paint")
    q = lines_to_quote(engine_lines, {k: float(v)})
    out = Path(a.out)
    quote_gen.render(q, random.Random(a.seed), out, stamp="SYNTHETIC")
    out.with_suffix(".json").write_text(json.dumps({"synthetic": True, "inflated": a.inflate, **q}, indent=1), encoding="utf-8")
    print(f"wrote {out} and {out.with_suffix('.json')} (SYNTHETIC; inflated {a.inflate}; lines {[(x['description'], x['total']) for x in q['lines']]})")
    if a.post and a.claim:
        body = json.dumps({"quote": q}).encode()
        r = urllib.request.urlopen(urllib.request.Request(f"{a.api}/claims/{a.claim}/quote", data=body, headers={"content-type": "application/json"}))
        res = json.loads(r.read())
        for row in res["quote_result"]["lines"]:
            print(f"  {row['description']:<22} {row['quoted']:>7}  {row['verdict']:<12} {row['reason']}")
        print("  offer", res["original_offer"], "->", res["offer"])


if __name__ == "__main__":
    main()
