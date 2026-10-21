"""Task 4: Qwen wording with and without the audit-repair loop, on 30 scripted claims (no photos).

    python tools/run_guarded.py --tag task4 -- env/Scripts/python.exe tools/qwen_repair_eval.py

One first draft per claim (cached), so both modes start from the same text:
  repair OFF = rationale.safe_reply(draft)             -> model wording or template
  repair ON  = rationale.safe_reply_repair(draft, ...)  -> up to 2 repair prompts, each listing the broken rules only
The repair prompt holds the engine's original explanation and the rule notes; never the ceiling, the pivots, or the
failed draft (a failed draft may itself contain the ceiling). All model outputs are cached in run1/cache/qwen_repair.json.
"""
import json
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import thermal as T  # noqa: E402
from autosettle_engine import engine as E, rationale as R  # noqa: E402
from autosettle_engine.tests.helpers import RC, det, policy, vision  # noqa: E402

CACHE = ROOT / "run1" / "cache" / "qwen_repair.json"
TODAY = date(2026, 10, 21)

# (label, model, reg, cc, detections)
CLAIMS = [
    ("Swift bumper broken", "Swift", "2023-06-01", 1197, [("Front-bumper", "Broken part", "moderate")]),
    ("Swift bumper + fender", "Swift", "2023-06-01", 1197, [("Front-bumper", "Broken part", "moderate"), ("Fender", "Surface damage", "moderate")]),
    ("Swift 4th gen bumper (other generation)", "Swift", "2025-01-15", 1197, [("Front-bumper", "Broken part", "severe")]),
    ("Swift grille (fallback price)", "Swift", "2022-03-01", 1197, [("Grille", "Broken part", "moderate")]),
    ("Swift mirror", "Swift", "2019-05-01", 1197, [("Mirror", "Broken part", "moderate")]),
    ("Swift door scratch", "Swift", "2021-11-01", 1197, [("Front-door", "Surface damage", "minor")]),
    ("Baleno hood dent", "Baleno", "2023-02-01", 1197, [("Hood", "Dent", "moderate")]),
    ("Baleno headlight + bumper", "Baleno", "2024-04-01", 1197, [("Headlight", "Broken part", "severe"), ("Front-bumper", "Dent", "minor")]),
    ("Baleno rear door dent", "Baleno", "2018-08-01", 1197, [("Back-door", "Dent", "moderate")]),
    ("i20 fender dent", "i20", "2021-09-10", 1197, [("Fender", "Dent", "moderate")]),
    ("i20 tail lamp", "i20", "2022-01-01", 1197, [("Tail-light", "Broken part", "moderate")]),
    ("i20 windshield", "i20", "2023-03-01", 1197, [("Windshield", "Broken part", "severe")]),
    ("Venue rear bumper + tail lamp", "Venue", "2023-01-01", 998, [("Back-bumper", "Broken part", "moderate"), ("Tail-light", "Broken part", "moderate")]),
    ("Venue hood scratch", "Venue", "2020-08-01", 998, [("Hood", "Surface damage", "minor")]),
    ("Venue trunk dent", "Venue", "2020-02-01", 998, [("Trunk", "Dent", "moderate")]),
    ("Creta headlight + bumper", "Creta", "2024-01-20", 1497, [("Headlight", "Broken part", "severe"), ("Front-bumper", "Dent", "minor")]),
    ("Creta 2.0 diesel fender (Rs 2,000 deductible)", "Creta", "2022-05-01", 1956, [("Fender", "Dent", "moderate")]),
    ("Creta rear door + quarter panel", "Creta", "2021-07-01", 1497, [("Back-door", "Dent", "moderate"), ("Quarter-panel", "Dent", "minor")]),
    ("Creta mirror (2,000 deductible)", "Creta", "2024-06-01", 1956, [("Mirror", "Broken part", "moderate")]),
    ("Nexon hood dent", "Nexon", "2022-03-15", 1199, [("Hood", "Dent", "moderate")]),
    ("Nexon fender + headlight", "Nexon", "2024-02-01", 1199, [("Fender", "Dent", "moderate"), ("Headlight", "Broken part", "moderate")]),
    ("Nexon rear windshield", "Nexon", "2024-05-01", 1199, [("Back-windshield", "Broken part", "severe")]),
    ("Nexon diesel bumper (2,000 deductible)", "Nexon", "2021-06-01", 1497 + 100, [("Front-bumper", "Broken part", "moderate")]),
    ("Punch rear bumper + tail lamp", "Punch", "2023-11-05", 1199, [("Back-bumper", "Broken part", "severe"), ("Tail-light", "Broken part", "moderate")]),
    ("Punch roof dent", "Punch", "2022-10-01", 1199, [("Roof", "Dent", "moderate")]),
    ("Punch door scratch", "Punch", "2024-03-01", 1199, [("Front-door", "Surface damage", "moderate")]),
    ("Brezza front bumper (sum of two pieces)", "Brezza", "2023-04-01", 1462, [("Front-bumper", "Broken part", "moderate")]),
    ("Brezza windshield + hood", "Brezza", "2022-09-01", 1462, [("Windshield", "Broken part", "severe"), ("Hood", "Dent", "minor")]),
    ("Brezza three parts", "Brezza", "2019-01-01", 1462, [("Front-door", "Dent", "moderate"), ("Back-door", "Surface damage", "minor"), ("Mirror", "Broken part", "moderate")]),
    ("Venue rocker panel scratch", "Venue", "2021-01-01", 998, [("Rocker-panel", "Surface damage", "moderate")]),
]


def main():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    q = None
    from autosettle_vision.qwen import REWORD_SYSTEM
    n_gen = 0

    def gen(key, fn):
        nonlocal q, n_gen
        if key in cache:
            return cache[key]
        if q is None:
            import torch
            torch.set_num_threads(4)          # CPU-limited mode after a CPU THERMAL_KILL on the first attempt
            from autosettle_vision.qwen import QwenVL
            T.cooldown_until(65, 72)
            q = QwenVL()
        T.cooldown_until(65, 72, timeout=180)  # let the CPU come down before every generation
        n_gen += 1
        if n_gen % 10 == 0:
            T.wait_if_hot()
            time.sleep(10)
        cache[key] = fn()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        return cache[key]

    rows = []
    for label, model, reg, cc, ds in CLAIMS:
        pol = policy(model, reg=reg, cc=cc)
        v = vision(*[det(p, d, s) for p, d, s in ds], plate=pol.plate)
        res = E.assess(pol, v, RC, TODAY)
        if res["decision"] != "OFFER":
            rows.append({"claim": label, "decision": res["decision"], "reasons": res["reasons"]})
            continue
        sp = E.customer_pivots(E.pivots(pol, v, RC, TODAY))
        template = R.build_rationale(res, sp)
        assert str(res["ceiling"]) not in template.replace(",", "") or res["ceiling"] in R.allowed_amounts(res)
        draft = gen(f"{label}|draft", lambda: q.reword(template, res))
        _, used_off, viol_off = R.safe_reply(draft, res, sp)
        k = [0]

        def repair(notes):
            k[0] += 1
            msg = (template + "\n\nYour previous rewrite of the explanation above broke these rules:\n- "
                   + "\n- ".join(notes) + "\nRewrite the explanation above again, following every rule.")
            return gen(f"{label}|repair{k[0]}|" + "|".join(notes), lambda: q.chat(
                [{"role": "system", "content": [{"type": "text", "text": REWORD_SYSTEM}]},
                 {"role": "user", "content": [{"type": "text", "text": msg}]}], max_new_tokens=700))
        _, used_on, viol_on, rounds = R.safe_reply_repair(draft, res, repair, sp)
        rows.append({"claim": label, "decision": "OFFER", "offer": res["offer"], "deductible": res["deductible"],
                     "statuses": sorted({ln["price_status"] or "-" for ln in res["lines"]}),
                     "off_used": used_off, "off_violations": [v[0] for v in viol_off],
                     "on_used": used_on, "on_violations": [v[0] for v in viol_on], "repair_rounds": rounds})
        print(f"{label}: off={'model' if used_off else 'TEMPLATE'} {[v[0] for v in viol_off]} | "
              f"on={'model' if used_on else 'TEMPLATE'} rounds={rounds} {[v[0] for v in viol_on]}", flush=True)
    offers = [r for r in rows if r["decision"] == "OFFER"]
    summ = {"claims": len(rows), "offers": len(offers),
            "fallback_off": sum(not r["off_used"] for r in offers), "fallback_on": sum(not r["on_used"] for r in offers),
            "violations_off": dict(Counter(v for r in offers for v in r["off_violations"])),
            "violations_on_final": dict(Counter(v for r in offers for v in r["on_violations"])),
            "repair_rounds": dict(Counter(r["repair_rounds"] for r in offers)),
            "not_offer": [(r["claim"], r["decision"], r["reasons"]) for r in rows if r["decision"] != "OFFER"],
            "new_generations_this_run": n_gen}
    print(json.dumps(summ, indent=1))
    (ROOT / "run1" / "qwen_repair_eval.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
