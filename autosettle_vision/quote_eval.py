"""
Measure Qwen3-VL quote reading on the synthetic quotes, then push each read quote through the dispute flow.

    python -m autosettle_vision.quote_eval      -> runs/quote_eval.json
"""
import json
import time
from pathlib import Path

from autosettle_engine import engine as E
from autosettle_engine.dispute import ClaimSession
from autosettle_engine.tests.helpers import RC, det, policy, vision

from .qwen import QwenVL

DMG = {"Front-bumper": "Broken part", "Back-bumper": "Broken part", "Hood": "Dent", "Fender": "Dent",
       "Headlight": "Broken part", "Tail-light": "Broken part", "Mirror": "Broken part"}


def main():
    q = QwenVL()
    rows = []
    for gt_path in sorted(Path("runs/quotes").glob("q*.json")):
        gt = json.loads(gt_path.read_text())
        t0 = time.time()
        read, raw = q.read_quote(str(gt_path.with_suffix(".jpg")))
        dt = time.time() - t0
        gl = gt["lines"]
        rl = read["lines"]
        # line match: same type and same total
        matched = sum(1 for g in gl if any(r["type"] == g["type"] and r["total"] == g["total"] for r in rl))
        amounts_ok = sorted(g["total"] for g in gl) == sorted(r["total"] for r in rl)
        # dispute flow on what Qwen read (Swift 2023; damage = the quoted parts, severe so they are replaced)
        pol = policy("Swift", reg="2023-06-01")
        v = vision(*[det(p, DMG[p], "severe") for p in gt["parts"]], plate=pol.plate)
        s = ClaimSession(pol, RC)
        res = s.submit(v)
        chk = s.dispute(read) if res["decision"] == "OFFER" else None
        rows.append({"quote": gt_path.stem, "lines_gt": len(gl), "lines_read": len(rl), "lines_matched": matched,
                     "all_amounts_exact": amounts_ok, "grand_total_ok": read.get("grand_total") == gt["grand_total"],
                     "seconds": round(dt, 1), "decision": res["decision"], "offer": res["offer"],
                     "updated_offer": chk and chk["updated_offer"], "ceiling": res["ceiling"],
                     "verdicts": chk and [(x["description"], x["verdict"]) for x in chk["verdicts"]], "raw": raw})
        r = rows[-1]
        print(f"{r['quote']}: {matched}/{len(gl)} lines exact, grand total ok={r['grand_total_ok']}, {dt:.1f}s; "
              f"offer {r['offer']} -> {r['updated_offer']} (ceiling {r['ceiling']})")
    tot = sum(r["lines_gt"] for r in rows)
    ok = sum(r["lines_matched"] for r in rows)
    summary = {"quotes": len(rows), "line_accuracy": round(ok / tot, 3), "lines": f"{ok}/{tot}",
               "quotes_all_exact": sum(r["all_amounts_exact"] for r in rows),
               "grand_total_exact": sum(r["grand_total_ok"] for r in rows),
               "never_above_ceiling": all((r["updated_offer"] or 0) <= (r["ceiling"] or 0) for r in rows)}
    print(summary)
    Path("runs/quote_eval.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str))


if __name__ == "__main__":
    main()
