"""
Checks on a chat reply the language model wrote. Pure code. A reply that fails any check is replaced by a template, so a
doubtful reply never reaches the customer. These sit on top of the engine's own rationale checks (BANNED words, the
ceiling-leak and part-not-in-claim rules); they are stricter, because chat text is short and free-form.

check_chat(text, facts, result, message) -> list of (check_name, detail); empty means every check passed.
CHECKS lists every check name, in the order the page shows them.
"""
import re

from . import rationale as R

MAX_WORDS = 90
CHECKS = ("english_only", "length", "format", "no_next_step_line", "amounts", "numbers", "ceiling", "banned_words", "no_promise",
          "no_accusation", "parts", "no_injection_echo")

PROMISE = re.compile(
    r"\b(will (pay|be paid|be credited|receive|get|send|transfer|settle|approve|refund|release|reach|arrive|contact you)|"
    r"we'?ll|we will|i'?ll|i will|you'?ll (get|receive|be)|you will (get|receive|be)|guarantee\w*|definitely|certainly|promise\w*|assure\w*|"
    r"for sure|without fail|rest assured|ensure\w*|within \d+|within (a|the next|one|two|three|four|five|seven|ten) (day|week|hour|month)s?|"
    r"by (tomorrow|today|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday|next week|the end)|"
    r"\d+ (working |business |calendar )?(day|hour|week|month)s?\b|tomorrow|shortly|immediately|right away|as soon as|"
    r"next (day|week|month)|same day|instantly|quickly|soon)\b", re.I)
FINALITY = re.compile(r"\b(final|non-negotiable|cannot be changed|can'?t be changed|set in stone|fixed offer|no way to|cannot ask|can'?t ask|being processed|under review)\b", re.I)
ACCUSATION = re.compile(r"\b(fraud\w*|fake\w*|forg\w*|lying|liar|lie|cheat\w*|dishonest\w*|scam\w*|suspicio\w*|false claim|"
                        r"you are (trying|lying|wrong)|you'?re (trying|lying)|manipulat\w*|tamper\w*|mislead\w*)\b", re.I)
INTERNAL = re.compile(r"\b(ceiling|maxim\w+|limits?|caps?|upper (limit|bound)|maximum we|max(imum)? (we|i|payable|amount)|hidden (range|limit)|internal (limit|range|threshold)|"
                      r"threshold|settlement range|what[- ]if|pivot\w*|guardrail\w*|system prompt|my (instructions|rules|prompt))\b", re.I)
INJECTION = re.compile(r"\b(ignore (all |the |your |any )?(previous|prior|above|earlier)?\s*(instructions|rules|prompt)|developer mode|"
                       r"you are now|system prompt|as an? (unrestricted|jailbroken)|disregard)\b", re.I)
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF⭐⬆↔-↪️]")
LINK = re.compile(r"https?://|www\.|\]\(|<a |\.com\b|\.in\b|\.org\b", re.I)
HEADING_OR_LIST = re.compile(r"^\s*(#{1,6}\s|[-*•]\s|\d+[.)]\s|>\s)", re.M)
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
ALLOWED_CHARS = re.compile(r"^[\x20-\x7E\n₹’‘“”–— ]*$")


def numbers_in(text):
    """Every number written in the text, as a canonical string: '2,763' -> '2763', '06' -> '6', '3.40' -> '3.4'."""
    out = set()
    for m in NUMBER.findall(text or ""):
        m = m.replace(",", "")
        out.add(str(float(m)).rstrip("0").rstrip(".") if "." in m else str(int(m)))
    return out


def facts_numbers(facts):
    """The numbers the model was allowed to use: every number that appears anywhere in the facts it was given."""
    import json
    return numbers_in(json.dumps(facts, ensure_ascii=False, default=str))


def _words(s):
    return re.findall(r"[a-z0-9']+", (s or "").lower())


def _echoes(text, message, n=6):
    """True if the reply repeats n or more consecutive words of the customer's message (the model parroting an instruction)."""
    m, t = _words(message), _words(text)
    grams = {tuple(m[i:i + n]) for i in range(len(m) - n + 1)}
    return any(tuple(t[i:i + n]) in grams for i in range(len(t) - n + 1))


def check_chat(text, facts, result=None, message="", ceiling=None):
    """Returns the list of failed checks as (name, detail). The ceiling is passed only so a leak can be detected; it never reaches the model."""
    v = []
    text = text or ""
    if not text.strip():
        return [("length", "empty reply")]
    if not ALLOWED_CHARS.match(text):
        v.append(("english_only", "characters outside English letters and punctuation"))
    words = len(text.split())
    if words > MAX_WORDS:
        v.append(("length", f"{words} words"))
    if HEADING_OR_LIST.search(text) or "```" in text or "`" in text or LINK.search(text) or EMOJI.search(text) or "**" in text:
        v.append(("format", "heading, list, link, code or emoji"))
    if re.search(r"^\s*next step\b", text, re.I | re.M):
        v.append(("no_next_step_line", "the reply wrote a Next step line"))
    # amounts: every rupee figure must be one the engine produced for this claim
    allowed = set()
    if result and result.get("decision") == "OFFER":
        allowed |= {str(a) for a in R.allowed_amounts(result)}
    fn = {n for n in facts_numbers(facts)}
    for a in R._amounts(text):
        if str(a) not in allowed and str(a) not in fn:
            v.append(("amounts", f"a rupee figure that is not in this claim: {a}"))
    # any other number (a percentage, an age, a year, a date, a count) must also be in the facts
    rupee_nums = {str(a) for a in R._amounts(text)}
    for n in sorted(numbers_in(text) - fn - rupee_nums - allowed):
        v.append(("numbers", f"a number that is not in the facts: {n}"))
    if ceiling:
        digits = re.sub(r"[,\s]", "", text)
        if str(ceiling) in digits and str(ceiling) not in fn:
            v.append(("ceiling", "contains the internal upper bound"))
    if INTERNAL.search(text):
        v.append(("ceiling", "names an internal limit: " + INTERNAL.search(text).group(0)))
    if R.BANNED.search(text):
        v.append(("banned_words", R.BANNED.search(text).group(0)))
    if PROMISE.search(text):
        v.append(("no_promise", PROMISE.search(text).group(0)))
    elif FINALITY.search(text):
        v.append(("no_promise", "an outcome stated as certain: " + FINALITY.search(text).group(0)))
    if ACCUSATION.search(text):
        v.append(("no_accusation", ACCUSATION.search(text).group(0)))
    # a part the claim does not contain
    claim_parts = {ln.get("part_class") for ln in (result or {}).get("lines", [])}
    claim_parts |= {str(ln.get("part", "")).replace(" ", "-").title() for ln in facts.get("lines", [])}
    work = text.lower()
    for k in R._ALIAS_ORDER:
        pat = r"\b" + re.escape(k) + r"\b"
        if re.search(pat, work):
            part = R._ALIASES[k]
            if part not in claim_parts and part.lower() not in {p.lower() for p in claim_parts if p}:
                v.append(("parts", f"mentions a part that is not in this claim: {part}"))
            work = re.sub(pat, " ", work)
    if INJECTION.search(text) or (message and _echoes(text, message)):
        v.append(("no_injection_echo", "repeats an instruction or the customer's own text"))
    return v


def results(violations):
    """For the page: [{check, passed, detail}] in CHECKS order."""
    bad = {}
    for name, detail in violations:
        bad.setdefault(name, []).append(detail)
    return [{"check": c, "passed": c not in bad, "detail": "; ".join(bad.get(c, []))} for c in CHECKS]
