"""
Adjuster-only estimate from what the system can see. Read-only: it prices detections with the engine's own two modes and
changes nothing (not the decision, the offer, the ceiling, the session or the audit log). Pure Python, no GPU.

    low  = price_line(det, policy, rc, "offer")     the engine's best estimate for the line
    high = price_line(det, policy, rc, "ceiling")   the engine's top-of-range figure for the line

It invents no price: every rupee is a figure price_line produced. A detection the engine cannot price is listed under
not_priced with the reason, so an incomplete estimate is a floor on what is visible, not the likely total.
This dict is for the adjuster route only. Customer routes and the language-model prompt never receive it.
"""
from . import config as C, engine as E

RATE_CARD_FILE = "rate_card_v3.csv"

_UNRESOLVED = {
    "no_part_price": "no price in the rate card for {part}",
    "no_labour_paint_basis": "no labour and paint price for {part}",
    "no_price_basis_for_part": "no price basis for {part}: it needs an inspection",
}


def _note(part, codes):
    return "; ".join(_UNRESOLVED.get(c, c).format(part=part) for c in codes)


def _line(lo, hi):
    return {"part_class": lo["part_class"], "damage_class": lo["damage_class"], "severity": lo["severity"], "action": lo["action"],
            "low": lo["line_total"], "high": hi["line_total"],
            "part_mrp": lo["part_mrp"], "dep_rate": lo["dep_rate"], "dep_amount": lo["dep_amount"], "part_net": lo["part_net"],
            "labour": lo["labour"], "paint_gross": lo["paint_gross"], "paint_net": lo["paint_net"],
            "price_tier": lo["price_tier"], "price_status": lo["price_status"], "dep_basis": lo["dep_basis"], "paint_basis": lo["paint_basis"]}


def estimate_from_evidence(policy, vision, rc, today=None, decision=None):
    """vision is the engine contract dict (or None). decision is the engine's real decision, copied unchanged."""
    dets = list((vision or {}).get("detections") or [])
    if not dets:
        return {"applies": False, "decision": decision, "note": "No damage has been detected yet, so there is nothing to estimate."}
    not_priced, usable = [], []
    for d in dets:
        part = d.get("part_class")
        if part in (None, "unassigned"):
            not_priced.append({"part": part or "unknown", "reason": "part not identified"})
            continue
        if E.normalise_damage(d.get("damage_class")) is None or d.get("severity") not in C.SEVERITIES:
            not_priced.append({"part": part, "reason": "severity not determined: needs a clearer view"})
            continue
        usable.append(d)
    lines = []
    for d in E.dedupe(usable):                     # one line per part, the worst detection, as the engine does
        try:
            lo = E.price_line(d, policy, rc, "offer", today)
            hi = E.price_line(d, policy, rc, "ceiling", today)
        except Exception as e:                     # never crash the page
            not_priced.append({"part": d["part_class"], "reason": f"the price calculation could not run ({type(e).__name__})"})
            continue
        codes = sorted(set(lo["unresolved"]) | set(hi["unresolved"]))
        if codes:
            not_priced.append({"part": d["part_class"], "reason": _note(d["part_class"], codes)})
            continue
        lines.append(_line(lo, hi))
    gross_low = sum(ln["low"] for ln in lines)
    gross_high = sum(ln["high"] for ln in lines)
    ded = C.deductible(policy.engine_cc)
    payable_low = max(0, gross_low - ded)
    payable_high = max(payable_low, max(0, gross_high - ded))      # the engine's ceiling is never below its offer
    complete = not not_priced
    n = len(not_priced)
    reading = ("Estimate from the damage the system can see. "
               + ("Every detection was priced. " if complete else
                  f"It is incomplete: {n} detection{'s' if n != 1 else ''} could not be priced, so the figure is a floor on what is visible, not the likely total. ")
               + "It is not an offer.")
    age = E.age_years(policy, today)
    return {"applies": True, "decision": decision, "lines": lines, "not_priced": not_priced,
            "gross_low": gross_low, "gross_high": gross_high, "deductible": ded, "payable_low": payable_low, "payable_high": payable_high,
            "complete": complete, "reading": reading,
            "basis": (f"Rate card {RATE_CARD_FILE}; vehicle age {age:.1f} years at the loss date; labour and paint prices are ASSUMPTIONS "
                      "listed in docs/ASSUMPTIONS.md. Low is the engine's own best-estimate pricing, high is the top of its price range.")}
