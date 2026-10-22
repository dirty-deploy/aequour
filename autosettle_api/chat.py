"""
Chat replies to a customer's message. The split is: the language model may PHRASE, code DECIDES.

  1. intents.classify()           code decides what the message is about (never the model)
  2. build_facts()                code selects the facts for this claim: no ceiling, no hidden range, no hashes
  3. template()                   a fixed reply written from the same facts (always available)
  4. the model writes a draft     chat_prompt.build_messages(): fixed rules + FACTS + the message as untrusted text
  5. chat_check.check_chat()      code accepts or rejects the draft; any doubt falls back to the template
  6. guidance.attach()            the code-built Next step line is added last, so the model cannot change it

The result says which path was taken and why, and carries what the page shows under "Behind this reply".
"""
import concurrent.futures
import os
import re
import threading

from autosettle_engine import chat_check as K, config as C, guidance as G, rationale as R
from autosettle_vision import chat_prompt as P

# Seconds to wait for the model before using the template. Measured on the development laptop: 48 replies took 2.3 to 6.8 s (median about 3.3 s); 20 s is about three times the slowest. Override with AEQUOUR_CHAT_TIMEOUT.
CHAT_TIMEOUT_S = float(os.environ.get("AEQUOUR_CHAT_TIMEOUT", "20"))

STATE_WORDS = {"INTAKE": "waiting for more photos or information", "OFFERED": "an offer has been made", "UPDATED_OFFER": "the offer was updated after a garage quote",
               "SETTLED": "the offer was accepted", "PARTNER_GARAGE": "a partner-garage repair was requested", "SURVEYOR": "a surveyor needs to inspect the car",
               "ESCALATED": "a person is reviewing the claim", "STALL": "the claim is closed"}
ACTION_WORDS = {"replace": "replace the part", "repair_dent": "repair the dent and repaint", "repaint": "repaint", "polish": "polish and touch up"}
REASONS = {
    "not_for_model": "this kind of message always gets fixed wording",
    "model_off": "the language model is off",
    "model_loading": "the language model is still loading",
    "model_error": "the language model could not start",
    "model_busy": "the model was busy with another reply",
    "timeout": "the model took too long",
    "exception": "the model returned an error",
    "check_failed": "the checker rejected the model's reply",
}
CHECK_WORDS = {"english_only": "it was not plain English", "length": "it was too long", "format": "it used a list, heading, link or code",
               "no_next_step_line": "it wrote its own Next step", "amounts": "it used a rupee figure that is not in this claim",
               "numbers": "it used a number that is not in this claim", "ceiling": "it touched on internal limits",
               "banned_words": "it used a word that is not allowed", "no_promise": "it made a promise", "no_accusation": "it used accusing wording",
               "parts": "it named a part that is not in this claim", "no_injection_echo": "it repeated an instruction"}

_lock = threading.Lock()
_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="chat")


# ------------------------------------------------------------------ facts
def _line_facts(ln):
    m = R.money          # amounts go to the model as text, exactly as the customer sees them: ₹2,763
    d = {"part": R.pname(ln["part_class"]), "what_is_done": ACTION_WORDS.get(ln["action"], ln["action"]), "line_total": m(ln["line_total"])}
    if ln["action"] == "replace":
        d["part_price"] = m(ln["part_mrp"])
        d["depreciation_percent"] = int(round(ln["dep_rate"] * 100))
        d["depreciation_amount"] = m(ln["dep_amount"])
        d["part_price_after_depreciation"] = m(ln["part_net"])
    if ln["labour"]:
        d["labour"] = m(ln["labour"])
    if ln["paint_gross"]:
        d["painting"] = m(ln["paint_gross"])
        d["paint_material_deduction"] = m(ln["paint_dep"])
        d["painting_after_deduction"] = m(ln["paint_net"])
    b = ln.get("dep_basis")
    if b:
        d["material"] = b["material"]
        if b["material"] == "metal":
            d["car_age_years"] = b.get("age_years")
            d["age_band"] = b.get("band")
    return d


def build_facts(c, intent):
    """The facts for this intent, from this claim's engine output only. Never the ceiling, the hidden range, internal thresholds,
    audit hashes or another claim."""
    s, res = c.session, c.session.result
    facts = {"claim_state": STATE_WORDS.get(s.state, "in progress")}
    open_offer = bool(res and res["decision"] == "OFFER" and s.state in ("OFFERED", "UPDATED_OFFER"))
    if res and res["decision"] == "OFFER":
        facts["current_offer"] = R.money(s.current_offer)
        if s.updated_offer is not None and s.offer is not None:
            facts["offer_before_garage_quote"] = R.money(s.offer)
    if open_offer:
        facts["offer_is_open"] = True      # the choices (accept, quote, partner garage, surveyor) are listed by the code-built Next step
    if intent in ("how_calculated", "depreciation") and res and res["decision"] == "OFFER":
        facts["repair_cost"] = R.money(res["gross"])
        facts["deductible"] = R.money(res["deductible"])
        facts["lines"] = [_line_facts(ln) for ln in res["lines"]]
    if intent == "depreciation":
        facts["depreciation_rules"] = {"plastic_and_rubber_parts_percent": int(round(C.PLASTIC_DEP * 100)), "glass_percent": 0,
                                       "metal_parts": "lose value with the age of the car, by band",
                                       "metal_age_bands": [{"band": b["label"], "percent": int(round(b["rate"] * 100))} for b in C.metal_bands()],
                                       "paint_material_share_of_painting_percent": int(round(C.PAINT_MATERIAL_SHARE * 100)),
                                       "paint_material_depreciation_percent": int(round(C.PAINT_MATERIAL_DEP * 100)),
                                       "labour_is_never_depreciated": True,
                                       "note": "the car's age stands in for its current value"}
    if intent == "why_not_more":
        facts["what_can_change_the_offer"] = "new photos, or an itemised garage quote that the photos support"
        facts["customer_can_not_change_the_amount_by_asking"] = True
    if intent == "payout_timing":
        facts["payment"] = "a person confirms payment with the customer; no date is available"
    if intent in ("greeting_or_meta", "other"):
        facts["what_the_assistant_can_do"] = "explain how the offer was worked out, explain depreciation, and say what the customer can do next"
        facts["assistant_is"] = "an automated claims assistant; a language model writes replies and code checks them; code sets every amount"
    return facts


# ------------------------------------------------------------------ templates (always available, written from the same facts)
def _m(n):
    return n if isinstance(n, str) else R.money(n)


def _line_sentence(l):
    bits = []
    if "part_price" in l:
        b = f"the part is {_m(l['part_price'])}"
        if l.get("depreciation_amount"):
            b += f", less {l['depreciation_percent']}% depreciation ({_m(l['depreciation_amount'])})"
        bits.append(b)
    if l.get("labour"):
        bits.append(f"labour is {_m(l['labour'])}")
    if l.get("painting"):
        bits.append(f"painting is {_m(l['painting'])}, less {_m(l['paint_material_deduction'])} for paint material")
    return f"The {l['part']} comes to {_m(l['line_total'])}: " + "; ".join(bits) + "."


def _dep_sentence(l):
    if "part_price" not in l:
        return None
    mat = l.get("material")
    if mat == "plastic":
        why = f"plastic parts lose {l['depreciation_percent']}% of their price, whatever the age of the car"
    elif mat == "glass":
        why = "glass is paid in full"
    else:
        why = (f"metal parts lose value with the age of the car, and yours is {l.get('car_age_years')} years old, "
               f"which is the {l.get('age_band')} band ({l['depreciation_percent']}%)")
    return f"On the {l['part']}, {why}. {_m(l['part_price'])} less {l['depreciation_percent']}% leaves {_m(l['part_price_after_depreciation'])}, so {_m(l['depreciation_amount'])} is deducted."


def template(intent, facts):
    """(body, next_step) for an intent, from the facts only. No model."""
    offer = facts.get("current_offer")
    open_offer = bool(facts.get("offer_is_open"))
    lines = facts.get("lines", [])
    state = facts.get("claim_state", "")
    if intent == "how_calculated":
        if offer is None or not lines:
            return (f"There is no cash offer to explain yet: {state}.", G.recorded_step())
        body = [f"Your offer is {_m(offer)}.", "",
                f"The repair cost is {_m(facts['repair_cost'])}, less your {_m(facts['deductible'])} deductible.", ""]
        body += [_line_sentence(l) for l in lines]
        return "\n".join(body), G.offer_step() if open_offer else G.recorded_step()
    if intent == "depreciation":
        if not lines:
            return (f"Depreciation is the amount taken off a part's price because it is not new.\n\nThere is no offer on this claim yet, so there is nothing to show: {state}.", G.recorded_step())
        sents = [s for s in (_dep_sentence(l) for l in lines) if s]
        paint = [l for l in lines if l.get("painting")]
        body = ["Depreciation is the amount taken off a part's price because it is not new.", ""] + sents
        if paint:
            r = facts["depreciation_rules"]
            body += ["", f"On painting, {r['paint_material_share_of_painting_percent']}% of the bill is paint material, and that share loses "
                         f"{r['paint_material_depreciation_percent']}%. Labour is never depreciated."]
        return "\n".join(body), "ask about any other line, or accept this offer if you are happy with it." if open_offer else G.recorded_step()
    if intent == "what_next":
        if open_offer:
            return (f"Your offer is {_m(offer)}. Nothing is decided until you choose.\n\nI can also explain any line of it before you do.", G.offer_step())
        return (f"Right now, {state}.", G.recorded_step())
    if intent == "why_not_more":
        body = "I understand it may feel low.\n\nThe offer comes from the photos, listed part prices and fixed depreciation rules, so I can't raise it on request."
        return body, G.more_step()
    if intent == "payout_timing":
        return ("I can't give a payment date.\n\nA person confirms payment with you once the offer is accepted.",
                "accept the offer if you are happy with it, and keep your policy number ready." if open_offer else G.recorded_step())
    if intent == "greeting_or_meta":
        return ("Hello. I'm an automated claims assistant. A language model can help me word replies, and code checks every one. Code sets every amount, not me.\n\n"
                "I can explain how your offer was worked out, what depreciation is, and what you can do next.",
                G.offer_step() if open_offer else G.recorded_step())
    return ("Thanks. I've recorded your message with the claim.\n\nI can explain how your offer was worked out, what depreciation is, and what you can do next.",
            G.offer_step() if open_offer else G.recorded_step())


# ------------------------------------------------------------------ the model draft
def clean(text):
    t = (text or "").strip().strip('"').strip()
    t = re.sub(r"^(reply|assistant|answer)\s*:\s*", "", t, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def reply(c, intent, message, model_status, get_model, ceiling=None, timeout=None):
    """Returns a dict: text (what the customer sees), source ('model' | 'template'), reason (code or None), reason_text, intent, facts,
    model_raw, checks [{check, passed, detail}], rejected (the model's text if the checker refused it), prompt."""
    facts = build_facts(c, intent)
    body, step = template(intent, facts)
    out = {"intent": intent, "facts": facts, "source": "template", "reason": None, "reason_text": "", "model_raw": None,
           "checks": [], "rejected": None, "text": G.attach(body, step), "next_step": step}

    def fall_back(reason, detail=""):
        out["reason"] = reason
        out["reason_text"] = REASONS[reason] + (f" ({detail})" if detail else "")
        return out

    st = model_status()
    if st != "ready":
        return fall_back({"off": "model_off", "loading": "model_loading"}.get(st, "model_error"))
    model = get_model()
    if model is None or not hasattr(model, "chat_text"):
        return fall_back("model_error")
    if _lock.locked():
        return fall_back("model_busy")
    messages = P.build_messages(intent, facts, message)
    out["prompt"] = P.prompt_text(messages)

    def job():
        with _lock:
            return model.chat_text(messages, max_new_tokens=P.MAX_NEW_TOKENS, temperature=P.TEMPERATURE)
    fut = _pool.submit(job)
    try:
        raw = fut.result(timeout=timeout or CHAT_TIMEOUT_S)
    except concurrent.futures.TimeoutError:
        return fall_back("timeout", f"more than {int(timeout or CHAT_TIMEOUT_S)} seconds")
    except Exception as e:                                          # the model threw: say so, answer from the template
        return fall_back("exception", type(e).__name__)
    text = clean(raw)
    out["model_raw"] = raw
    result = c.session.result
    viol = K.check_chat(text, facts, result, message, ceiling=ceiling)
    out["checks"] = K.results(viol)
    if viol:
        out["rejected"] = text
        names = list(dict.fromkeys(n for n, _ in viol))
        return fall_back("check_failed", "; ".join(CHECK_WORDS.get(n, n) for n in names))
    out.update(source="model", text=G.attach(text, step))
    return out
