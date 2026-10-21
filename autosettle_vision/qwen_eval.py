"""
Run REAL Qwen output through the rationale checker (handoff item 11) and record the model facts for the deck.

    python -m autosettle_vision.qwen_eval            -> runs/qwen_eval.json

Cases: the demo claim and a spread of single- and multi-part claims across models, ages and actions.
For each: Qwen rewords build_rationale(); safe_reply() decides whether the wording may be shown.
"""
import json
import time
from pathlib import Path

import torch

from autosettle_engine import engine as E, rationale as R
from autosettle_engine.tests.helpers import RC, det, policy, vision

from .qwen import QwenVL

CASES = [
    ("demo Swift bumper+fender", policy("Swift", reg="2023-06-01", cc=1197, idv=600000, plate="DL3CAB1234"),
     [det("Front-bumper", "Broken part", "moderate", 0.91, 0.62), det("Fender", "Surface damage", "moderate", 0.88, 0.55)]),
    ("Nexon hood dent", policy("Nexon", reg="2022-03-15", cc=1199, idv=820000, plate="HR26DK8337"),
     [det("Hood", "Dent", "moderate", 0.9, 0.7)]),
    ("Creta headlight + bumper", policy("Creta", reg="2024-01-20", cc=1497, idv=1250000, plate="UP16BT4521"),
     [det("Headlight", "Broken part", "severe", 0.93, 0.8), det("Front-bumper", "Dent", "minor", 0.9, 0.6)]),
    ("i20 door scratch", policy("i20", reg="2021-09-10", cc=1197, idv=520000, plate="DL8CAF5031"),
     [det("Front-door", "Surface damage", "minor", 0.88, 0.5)]),
    ("Punch rear bumper + tail lamp", policy("Punch", reg="2023-11-05", cc=1199, idv=610000, plate="HR51BX7712"),
     [det("Back-bumper", "Broken part", "severe", 0.9, 0.7), det("Tail-light", "Broken part", "moderate", 0.9, 0.7)]),
    ("Venue fender + door dents", policy("Venue", reg="2020-08-01", cc=998, idv=700000, plate="DL1CX0001"),
     [det("Fender", "Dent", "moderate", 0.9, 0.6), det("Front-door", "Dent", "minor", 0.9, 0.6)]),
]


def main():
    q = QwenVL()
    info = {"model": q.model_id, "params": "8B", "quantisation": "4-bit NF4 (bitsandbytes), double quant, bf16 compute",
            "load_seconds": q.load_s, "vram_after_load_gb": q.vram_gb, "gpu": torch.cuda.get_device_name(0)}
    print(info)
    rows = []
    for name, pol, dets in CASES:
        v = vision(*dets, plate=pol.plate)
        res = E.assess(pol, v, RC)
        assert res["decision"] == "OFFER", (name, res["decision"], res["reasons"])
        sp = E.customer_pivots(E.pivots(pol, v, RC))
        template = R.build_rationale(res, sp)
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        draft = q.reword(template, res)
        dt = time.time() - t0
        text, used, viol = R.safe_reply(draft, res, sp)
        rows.append({"case": name, "offer": res["offer"], "passed": used, "violations": viol, "seconds": round(dt, 1),
                     "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2), "template": template, "qwen": draft})
        print(f"\n=== {name}: offer {res['offer']}  passed={used}  {dt:.1f}s  violations={viol}\n{draft}")
    out = {"model_info": info, "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows}
    Path("runs").mkdir(exist_ok=True)
    Path("runs/qwen_eval.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n{out['passed']}/{out['total']} Qwen rewordings passed the checker")


if __name__ == "__main__":
    main()
