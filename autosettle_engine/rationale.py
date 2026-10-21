"""
Rationale = the engine's own derivation, written out. The language model may reword it,
but every reply is checked against the engine's numbers before the customer sees it.

Failure types we test for (adapted from FaithCoT-Bench / SAVER taxonomies):
  invented number     : a rupee figure the engine never produced        -> unknown_amount
  selective omission  : a line item or the depreciation left out        -> missing_amount / missing_depreciation
  unsupported claim   : a part or accusation not in the engine's output -> part_not_in_claim / banned_phrase
  ceiling leak        : the settlement ceiling (or any number near it)  -> ceiling_leak
"""
import re

from . import config as C

RUPEE = re.compile(r"(?:₹|Rs\.?\s?|INR\s?)\s?([0-9][0-9,]*)")
PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s?%")
BANNED = re.compile(r"\b(ceiling|guarantee\w*|we can go (?:up )?to|maximum we|negotiat\w*|haggl\w*|fraud\w*|tamper\w*|"
                    r"lie|lying|cheat\w*|best and final|nobody else|upper limit|at most|no more than|most we (?:could|can|would|will)|highest we)\b|up to ₹", re.I)
ALL_PARTS = sorted(C.PRICED_PARTS | C.REPAIR_ONLY | C.UNPRICEABLE)
_ALIASES = {**{p.replace("-", " ").lower(): p for p in ALL_PARTS}, **C.PART_KEYWORDS}
_ALIAS_ORDER = sorted(_ALIASES, key=lambda k: -len(k))


def money(n):
    return "₹{:,}".format(int(n))


def pname(part):
    return part.replace("-", " ").lower()


def _line_text(ln):
    p = pname(ln["part_class"]).capitalize()
    act = ln["action"]
    if act == "replace":
        s = f"{p}: replacement. Genuine part {money(ln['part_mrp'])}"
        if ln["dep_amount"]:
            s += f", less {int(round(ln['dep_rate'] * 100))}% depreciation ({money(ln['dep_amount'])}) = {money(ln['part_net'])}"
        s += f". Fitting labour {money(ln['labour'])}."
        if ln["paint_gross"]:
            s += f" Painting {money(ln['paint_gross'])}, less {money(ln['paint_dep'])} for paint material depreciation = {money(ln['paint_net'])}."
    elif act == "repair_dent":
        s = (f"{p}: dent repair and repaint. Labour {money(ln['labour'])}. "
             f"Painting {money(ln['paint_gross'])}, less {money(ln['paint_dep'])} for paint material depreciation = {money(ln['paint_net'])}.")
    elif act == "repaint":
        s = (f"{p}: repaint. Painting {money(ln['paint_gross'])}, less {money(ln['paint_dep'])} "
             f"for paint material depreciation = {money(ln['paint_net'])}.")
    else:  # polish
        s = f"{p}: polish and touch-up. Labour {money(ln['labour'])}."
    return s + f" Line total {money(ln['line_total'])}."


def build_rationale(result, safe_pivots=None, extra_lines=None):
    """Deterministic customer-facing rationale from an OFFER result. Never mentions the ceiling."""
    assert result["decision"] == "OFFER", "rationale is only built for an offer"
    out = [f"Here is how your offer of {money(result['offer'])} was worked out."]
    out += [_line_text(ln) for ln in result["lines"]]
    for t in (extra_lines or []):
        out.append(t)
    out.append(f"Total repair cost {money(result['gross'])}. Less the compulsory deductible of "
               f"{money(result['deductible'])}. Offer: {money(result['offer'])}.")
    assumed = [e for e in result["ledger"] if e["status"] == "IMPUTED" and not e["item"].endswith(".action")]
    notes = []
    if any(e["item"].endswith(".labour_and_paint") for e in assumed):
        notes.append("labour and painting are estimated from typical garage price ranges, not from a quote")
    if any(e["item"].endswith(".part_price") for e in assumed):
        notes.append("some part prices are estimated from similar cars because we have no listing for your model")
    if any(e["item"] == "gst_treatment" for e in assumed):
        notes.append("prices are treated as tax-inclusive")
    if notes:
        out.append("What we assumed: " + "; ".join(notes) + ".")
    for sp in (safe_pivots or []):
        word = {"up": "the offer would go up", "down": "the offer would go down", "review": "the claim would need a human review"}[sp["direction"]]
        out.append(f"What could change this: {sp['condition']}, {word}.")
    out.append("If you disagree, you can share your garage's itemised quote, repair at one of our partner garages, "
               "or ask for a surveyor.")
    return "\n".join(out)


def allowed_amounts(result, extra=()):
    s = set(extra)
    for ln in result["lines"]:
        for k in ("part_mrp", "dep_amount", "part_net", "labour", "paint_gross", "paint_dep", "paint_net", "line_total"):
            s.add(ln[k])
    s |= {result["gross"], result["deductible"], result["offer"]}
    return s


def _amounts(text):
    return [int(m.replace(",", "")) for m in RUPEE.findall(text)]


def check_rationale(text, result, extra_allowed=()):
    """Return a list of violations (empty list = faithful). Pure code: no model involved."""
    v = []
    allowed = allowed_amounts(result, extra_allowed)
    found = _amounts(text)
    for a in found:
        if a not in allowed:
            v.append(("unknown_amount", a))
    # completeness: every non-zero component the engine used must be stated
    need = {result["gross"], result["deductible"], result["offer"]}
    for ln in result["lines"]:
        need |= {ln[k] for k in ("part_mrp", "dep_amount", "labour", "paint_gross", "paint_dep", "line_total") if ln[k]}
    for a in sorted(need - set(found)):
        v.append(("missing_amount", a))
    if any(ln["dep_amount"] or ln["paint_dep"] for ln in result["lines"]) and "depreciation" not in text.lower():
        v.append(("missing_depreciation", None))
    # percentages must be the depreciation rates the engine used
    ok_pct = {int(round(ln["dep_rate"] * 100)) for ln in result["lines"]}
    for p in PERCENT.findall(text):
        if int(float(p)) not in ok_pct:
            v.append(("unknown_percent", p))
    # ceiling leak: the ceiling value itself, unless that number is legitimately shown for another reason
    if result.get("ceiling") and result["ceiling"] != result["offer"]:
        digits = re.sub(r"[,\s]", "", text)
        for val in [result["ceiling"]] + [cl["line_total"] for cl in result.get("ceiling_lines", [])]:
            if val not in allowed and str(val) in digits:
                v.append(("ceiling_leak", val))
    if BANNED.search(text):
        v.append(("banned_phrase", BANNED.search(text).group(0)))
    # parts mentioned that are not in this claim (any common name; longest first so 'windshield' != 'back windshield')
    work = text.lower()
    claim_parts = {ln["part_class"] for ln in result["lines"]}
    for k in _ALIAS_ORDER:
        pat = r"\b" + re.escape(k) + r"\b"
        if re.search(pat, work):
            if _ALIASES[k] not in claim_parts:
                v.append(("part_not_in_claim", _ALIASES[k]))
            work = re.sub(pat, " ", work)
    return v


_VIOLATION_WORDS = {
    # the stray amount itself is never repeated back: it may be the ceiling
    "unknown_amount": "it states a rupee amount that is not in the original; use only the amounts in the original",
    "missing_amount": "it leaves out the amount {v} from the original; every amount in the original must appear",
    "missing_depreciation": "it does not mention depreciation; keep the depreciation lines",
    "unknown_percent": "it states a percentage ({v}%) that is not in the original",
    "ceiling_leak": "it contains a figure that must not be shown to the customer; use only the amounts in the original",
    "banned_phrase": "it uses wording about limits, guarantees, negotiation or blame (\"{v}\"); remove it",
    "part_not_in_claim": "it mentions a part ({v}) that is not in this claim",
    "empty_reply": "the reply was empty",
}


def describe_violations(viol):
    """Plain-language repair notes for the model. Never includes the ceiling (ceiling_leak values are dropped)."""
    out = []
    for kind, val in viol:
        text = _VIOLATION_WORDS.get(kind, kind)
        out.append(text.format(v="" if kind == "ceiling_leak" else (val.lower().replace("-", " ") if isinstance(val, str) else val)))
    return list(dict.fromkeys(out))


def safe_reply_repair(llm_text, result, repair, safe_pivots=None, extra_allowed=(), max_repairs=2):
    """Audit, then repair (SAVER-style): if the model's wording fails a check, ask it to rewrite once or twice,
    telling it only which rules it broke (never the ceiling or internal pivots), and re-check each time.
    repair(notes) -> new text. Returns (text, used_model_wording, violations_of_last_attempt, repair_rounds)."""
    text = llm_text
    viol = check_rationale(text, result, extra_allowed) if text else [("empty_reply", None)]
    rounds = 0
    while viol and rounds < max_repairs:
        rounds += 1
        text = repair(describe_violations(viol))
        viol = check_rationale(text, result, extra_allowed) if text else [("empty_reply", None)]
    if not viol:
        return text, True, [], rounds
    return build_rationale(result, safe_pivots), False, viol, rounds


def safe_reply(llm_text, result, safe_pivots=None, extra_allowed=()):
    """Use the model's wording only if it passes every check; otherwise fall back to the fixed template."""
    if llm_text:
        viol = check_rationale(llm_text, result, extra_allowed)
        if not viol:
            return llm_text, True, []
    else:
        viol = [("empty_reply", None)]
    return build_rationale(result, safe_pivots), False, viol
