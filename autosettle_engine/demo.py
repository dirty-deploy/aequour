"""
End-to-end demo of one claim, printed for the deck / video.   python -m autosettle_engine.demo
The 'vision' dict is what the ML pipeline outputs (contract in ML_Teammate_Tasks.md, Task 5).
"""
from . import engine as E, rationale as R
from .dispute import ClaimSession
from .tests.helpers import RC, policy, det, vision, quote


def main():
    pol = policy("Swift", reg="2023-06-01", cc=1197, idv=600000, plate="DL3CAB1234")
    s = ClaimSession(pol, RC)
    v = vision(det("Front-bumper", "Broken part", "moderate", 0.91, 0.62), det("Fender", "Surface damage", "moderate", 0.88, 0.55))
    res = s.submit(v)
    print(f"[{s.state}] decision={res['decision']}  information completeness={res['tci']}")
    sp = E.customer_pivots(E.pivots(pol, v, RC))
    print("\n--- Customer sees (rationale checked against the engine) ---")
    print(R.build_rationale(res, sp))
    print("\n--- Internal only (never shown to the customer or the language model) ---")
    print(f"ceiling = {R.money(res['ceiling'])}")
    print("\n--- Customer uploads their garage's quote ---")
    ref = next(l["part_mrp"] for l in res["lines"] if l["part_class"] == "Front-bumper")
    our_paint = sum(l["paint_gross"] for l in res["lines"]); ceil_paint = sum(l["paint_gross"] for l in res["ceiling_lines"])
    q = quote([("Front bumper", ref), ("Bonnet", 9000)], labour=1100, paint=(our_paint + ceil_paint) // 2)
    chk = s.dispute(q)
    for vd in chk["verdicts"]:
        print(f"  {vd['description']:<12} quoted {R.money(vd['quoted']):>8}  -> {vd['verdict']:<14} {vd.get('reason', '')}")
    print(f"\n[{s.state}] updated offer {R.money(chk['updated_offer'])} (was {R.money(chk['current_offer'])})")
    print("Options:", " | ".join(o["label"] for o in chk["options"]))
    s.choose("accept_updated")
    print(f"\n[{s.state}] settled at {R.money(s.current_offer)}; audit log intact: {ClaimSession.verify_log(s.log)} ({len(s.log)} records)")


if __name__ == "__main__":
    main()
