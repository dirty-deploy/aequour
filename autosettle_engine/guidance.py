"""
Plain-words replies and the closing "Next step:" line. Everything here is deterministic code.

The language model may reword the body of an offer explanation. It never writes, changes or drops the Next step: this
module builds that line and attaches it afterwards (attach). No function here invents an amount: the only amounts that
appear are ones the caller passes in from the engine.
"""
import re

NEXT = "Next step:"
_NEXT_LINE = re.compile(r"\n*\s*next step:.*\Z", re.I | re.S)

# ----------------------------------------------------------------- the engine's missing fields: what is wrong, what to send
ASKS = {
    "plate": "type the plate number, or add a clear photo of the plate",
    "closeup": "send a close-up of the damaged area in daylight, with the whole panel in the frame",
    "where": "send a photo that shows the damaged area and the panel around it",
    "retake": "retake the blurry photo in daylight, holding the phone steady",
    "dark": "retake the dark photo in daylight, without flash",
    "original": "send original photos straight from your camera",
    "policy": "check the policy number",
}
MISSING = {
    "plate_verified": ("I couldn't confirm the number plate.", "plate"),
    "parts_identified": ("I can't see each damaged panel clearly enough.", "closeup"),
    "damage_identified": ("The damage isn't clear enough for me to judge how bad it is.", "closeup"),
    "coverage_ok": ("I can see damage, but not where on the car it is.", "where"),
    "integrity_ok": ("One of the photos failed a check.", "original"),
    "policy_record": ("I couldn't find your policy.", "policy"),
}
# vision flags that sharpen the ask when present (the pipeline's own flag names, matched by prefix)
FLAGS = (
    ("low_quality", "blurry", "A photo is too blurry to read.", "retake"),
    ("low_quality", "too_dark", "A photo is too dark to read.", "dark"),
    ("need_wider_photo", None, "The car is too far away for me to see the damage clearly.", "closeup"),
    ("no_damage_found", None, "I couldn't find any damage in the photos.", "closeup"),
)

# ----------------------------------------------------------------- reason codes the engine writes in result["reasons"]
REASONS = {
    "plate_mismatch": "The number plate in the photo doesn't match the plate on your policy, so a person needs to look at it.",
    "integrity": "One of the photos failed a check, so a person needs to look at it.",
    "info_incomplete_after": "I still couldn't get what I need after asking more than once.",
    "low_conf_severe": "I'm not sure how bad the damage is, and that changes the price a lot.",
    "unpriceable": "Some damaged parts don't have a price I can rely on.",
    "structural_or_safety_damage": "Several panels look badly damaged, and hidden damage can't be priced from photos.",
    "gross_loss_at_or_above_surveyor_limit": "The repair cost is high enough that a surveyor needs to inspect the car.",
    "possible_constructive_total_loss": "The repair cost is close to the value of the car, so a surveyor needs to inspect it.",
    "gross_loss_at_or_above_review_threshold": "The repair cost is high enough that a person should check it.",
}
INTEGRITY = (("photo_seen_in_claim_", "This photo was already used in another claim."),
             ("edited_with_", "One photo shows signs of having been edited."),
             ("video_not_continuous", "The video jumps between scenes, so I can't rely on it."),
             ("unreadable", "One photo could not be read."))


def reason_known(code):
    """True if the engine's reason code (or a missing-field name) has words here."""
    c = code.split(":", 1)[0]
    return c in REASONS or c in MISSING or c.startswith("info_incomplete_after")


def explain_reason(code):
    c = code.split(":", 1)[0]
    if c == "integrity":
        for prefix, words in INTEGRITY:
            if prefix in code:
                return words
    if c.startswith("info_incomplete_after"):
        return REASONS["info_incomplete_after"]
    return REASONS.get(c) or (MISSING[c][0] if c in MISSING else "")


def attach(body, step):
    """Body, then the code-built Next step line. A Next step the model wrote is removed first."""
    body = _NEXT_LINE.sub("", (body or "").rstrip()).rstrip()
    return f"{body}\n\n{NEXT} {step}"


def _sentence(s):
    s = s.strip()
    return s[0].upper() + s[1:] if s else s


def _join_asks(keys):
    keys = list(dict.fromkeys(keys))[:2]
    if not keys:
        return "send clearer photos of the damage"
    first = ASKS[keys[0]]
    if len(keys) == 1:
        return first
    second = ASKS[keys[1]]
    return first + ", and " + (second[5:] if first.startswith("send ") and second.startswith("send ") else second)


# ----------------------------------------------------------------- next steps
def offer_step():
    return "accept this offer, or send your garage's itemised quote and each line is checked against your photos. You can also repair at a partner garage or ask for a surveyor."


def ask_more_step(missing=(), flags=()):
    keys = [k for pre, sub, _w, k in FLAGS for f in flags if f.startswith(pre) and (sub is None or sub in f)]
    keys += [MISSING[m][1] for m in missing if m in MISSING]
    return _join_asks(keys).rstrip(".") + "."


def escalate_step():
    return "a claims specialist will review this. Keep your policy number and a clear photo of the number plate ready."


def surveyor_step():
    return "a surveyor will contact you to inspect the car. Keep your policy number ready."


def quote_moved_step(offer_text, rounds_left):
    more = ", or send one more itemised quote if you think a line is missing" if rounds_left > 0 else ""
    return f"accept {offer_text}{more}." if more else f"accept {offer_text}, repair at a partner garage, or ask for a surveyor."


def quote_unmoved_step():
    return "send a quote that lists only the damage in your photos, or ask for a surveyor."


def amount_named_step():
    return "send your garage's itemised quote, or ask for a surveyor."


def passed_to_human_step():
    return "a claims specialist will contact you. You don't need to do anything else for now."


def recorded_step():
    return "send new photos or an itemised garage quote that your photos support. The offer moves only with those."


# ----------------------------------------------------------------- whole replies (body plus Next step)
def decision_reply(res, flags=()):
    """The reply for ASK_MORE, ESCALATE and SURVEYOR. res is the engine result; flags are the vision flags (optional)."""
    d = res["decision"]
    reasons, missing = res.get("reasons", []), res.get("missing", [])
    if d == "ASK_MORE":
        why = [w for pre, sub, w, _a in FLAGS for f in flags if f.startswith(pre) and (sub is None or sub in f)]
        why += [MISSING[m][0] for m in missing if m in MISSING]
        why = list(dict.fromkeys(why))[:3] or ["The photos aren't clear enough for me to price this safely."]
        return attach("Thanks for sending this. I can't price it safely yet.\n\n" + "\n".join(why), ask_more_step(missing, flags))
    if d == "SURVEYOR":
        why = [explain_reason(r) for r in reasons if explain_reason(r)] or ["This kind of damage needs an in-person look."]
        return attach("Thanks for these. This damage needs an in-person look.\n\n" + "\n".join(dict.fromkeys(why)), surveyor_step())
    why = [explain_reason(r) for r in reasons if r not in MISSING and explain_reason(r)] or ["A person needs to look at this one."]
    return attach("Sorry, I can't go further with this one.\n\n" + "\n".join(dict.fromkeys(why)), escalate_step())


def quote_reply(moved, before_text, after_text, verdict_rows, rounds_left, note=None):
    """verdict_rows: [(description, verdict)] from the engine's quote check. Amounts are the engine's, passed in as text."""
    if moved:
        body = ("Thanks, your garage's quote helped.\n\nI checked each line against your photos and the normal price range. "
                f"The supported lines raise your offer from {before_text} to {after_text}.")
        return attach(body, quote_moved_step(after_text, rounds_left))
    if note:
        return attach("Thanks for the quote. " + _sentence(note).rstrip(".") + ".", quote_unmoved_step())
    bad = []
    for desc, v in verdict_rows:
        name = desc.strip().lower()
        if v == "not_seen":
            bad.append(f"The {name} line isn't visible in your photos.")
        elif v in ("above_range", "high"):
            bad.append(f"The {name} line is above the normal range.")
        elif v == "action_mismatch":
            bad.append(f"The {name} line doesn't match the repair I found.")
        elif v in ("unknown_item", "unverified"):
            bad.append(f"I couldn't match the {name} line to a part.")
    why = "\n".join(bad[:4]) if bad else "No line was both visible in your photos and priced in the normal range."
    return attach(f"Thanks for the quote. I checked each line, and the offer stays at {after_text}.\n\n{why}", quote_unmoved_step())


def message_reply(kind, offer_text=None, again=False):
    """kind: passed_to_human | amount_named_no_change | recorded"""
    if kind == "passed_to_human":
        return attach("Your message has been passed to a claims specialist.", passed_to_human_step())
    if kind == "amount_named_no_change":
        lead = "The answer stays the same." if again else "I can't change the amount because a figure is named."
        return attach(f"{lead}\n\nYour offer is {offer_text}. It moves only with new photos, or an itemised quote that your photos support.", amount_named_step())
    return attach("Thanks. I've recorded your message with the claim.\n\nThe offer moves only with new photos or a supported quote.", recorded_step())


def choice_reply(option, offer_text=None):
    """The closing reply after the customer picks accept, partner_garage or surveyor."""
    if option == "accept":
        return attach(f"Accepted. The claim is settled at {offer_text}.", "you don't need to do anything else. This claim is closed.")
    if option == "partner_garage":
        return attach("A repair at a partner garage at agreed rates has been requested.", "a person will contact you to arrange the repair. Keep your policy number ready.")
    return attach("A surveyor inspection has been requested.", surveyor_step())
