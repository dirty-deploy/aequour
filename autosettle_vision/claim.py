"""
One claim end to end: photos -> vision JSON -> engine -> customer rationale (Qwen wording only if it passes the checker).

    python -m autosettle_vision.claim --policy POL-DEMO-001 IMG [IMG ...] [--video V] [--qwen]

The policy record is looked up from policies.json (simulated insurer plate lookup).
"""
import argparse
import json
from pathlib import Path

from autosettle_engine import engine as E, rationale as R
from autosettle_engine.dispute import ClaimSession

from . import pipeline as P

POLICIES = {p["policy_id"]: p for p in json.loads(Path(__file__).with_name("policies.json").read_text())}
RC = E.RateCard()


def get_policy(policy_id):
    return E.Policy(**POLICIES[policy_id])


def engine_vision(v):
    """Only the contract fields go to the engine (debug fields such as per-image quality stay out)."""
    keep = ("part_class", "part_conf", "damage_class", "damage_conf", "severity", "damage_area_fraction")
    return {"image_id": v["image_id"], "plate_read": v["plate_read"], "integrity_flags": v["integrity_flags"],
            "flags": [f for f in v["flags"] if f == "unassigned_damage" or f == "structural_suspected"],
            "detections": [{k: d.get(k) for k in keep} for d in v["detections"]]}


def customer_text(res, policy, vision, qwen=None):
    """Returns (text, used_model_wording, violations). The model only ever sees build_rationale() output."""
    if res["decision"] != "OFFER":
        return decision_text(res), False, []
    safe_piv = E.customer_pivots(E.pivots(policy, vision, RC))
    template = R.build_rationale(res, safe_piv)
    if qwen is None:
        return template, False, []
    draft = qwen.reword(template, res)
    text, used, viol = R.safe_reply(draft, res, safe_piv)
    return text, used, viol


def decision_text(res):
    d = res["decision"]
    if d == "ASK_MORE":
        need = {"plate_verified": "a clear photo of the number plate",
                "parts_identified": "a wider photo that shows each damaged panel in full",
                "damage_identified": "a closer, well-lit photo of each damaged area",
                "coverage_ok": "a photo that shows where the damage is on the car",
                "integrity_ok": "original photos straight from your camera"}
        asks = [need[m] for m in res["missing"] if m in need] or ["clearer photos of the damage"]
        return "We need a little more before we can make an offer: " + "; ".join(asks) + "."
    if d == "SURVEYOR":
        return "This claim needs a licensed surveyor to inspect the car. We have booked the request and a surveyor will contact you."
    return "A claims specialist will review this claim and contact you. You do not need to do anything else for now."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*")
    ap.add_argument("--policy", default="POL-DEMO-001")
    ap.add_argument("--video")
    ap.add_argument("--qwen", action="store_true")
    ap.add_argument("--test-assume-plate", action="store_true",
                    help="TESTING ONLY: dataset photos have no plate; treat the plate as read and matching")
    a = ap.parse_args()
    pol = get_policy(a.policy)
    q = None
    if a.qwen:
        from .qwen import QwenVL
        q = QwenVL()
    v = P.run_claim(a.images, a.video, plate_reader=q.read_plate if q else None)
    ev = engine_vision(v)
    if a.test_assume_plate and ev["plate_read"] is None:
        ev["plate_read"] = pol.plate
    s = ClaimSession(pol, RC)
    res = s.submit(ev)
    print("decision:", res["decision"], res["reasons"], "missing:", res["missing"])
    text, used, viol = customer_text(res, pol, ev, q)
    print(("[model wording passed checks]" if used else f"[template; model violations: {viol}]") + "\n" + text)


if __name__ == "__main__":
    main()
