"""
Deterministic intent for a customer chat message. Plain code, no model: the intent decides which facts and which template
the reply may use, so it has to be predictable and testable. Customer text is untrusted data: this module only reads it.

Intents: amount_named, depreciation, how_calculated, payout_timing, what_next, why_not_more, greeting_or_meta, other.
(abusive and legal-threat messages are flagged by the engine's own classifier and handled before this is called.)
"""
import difflib
import re

AMOUNT = re.compile(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*)|\b([0-9][0-9,]{2,})\b", re.I)

# words the patterns below depend on; a misspelt token is mapped to the closest of these ("calcualted" -> "calculated")
VOCAB = ("calculate", "calculated", "calculation", "explain", "explained", "depreciation", "deducted", "deduction", "breakdown",
         "payment", "paid", "money", "received", "receive", "increase", "raise", "higher", "bigger", "negotiate", "offer",
         "please", "what", "should", "next", "options", "accept", "unfair", "greeting", "message", "understand", "human",
         "robot", "assistant", "hello", "when", "how", "why", "more", "low", "step", "proceed", "continue", "worked", "work")
_ALIASES = {"u": "you", "ur": "your", "pls": "please", "plz": "please", "wat": "what", "wht": "what", "whts": "what", "r": "are",
            "abt": "about", "hw": "how", "y": "why", "msg": "message", "mesage": "message", "thx": "thanks", "ok": "ok",
            "shud": "should", "shld": "should", "wud": "would", "nxt": "next", "dont": "don't", "cant": "can't", "wen": "when", "rupees": "rs"}

_MONEY_VERB = re.compile(r"\b(increase|raise|add|top ?up|match|pay|give|want|need|demand|make it|change it to|set it to|offer me|"
                         r"settle (for|at)|approve)\b")
_DEPRECIATION = re.compile(r"\bdeprec\w*|\bdeduct\w*|\bwhy .{0,40}\b(taken off|cut|reduced|knocked|subtracted|less)\b|\bwear and tear\b")
_HOW = re.compile(r"\bhow\b.{0,40}\b(calculat\w*|work\w*( \w+)? out|worked|come|arrive\w*|get|got|derive\w*|decid\w*|made up|compute\w*)\b|"
                  r"\b(explain|breakdown|break down|itemi[sz]\w*|working|calculation|justify)\b|"
                  r"\bwhy\b.{0,12}(rs|inr|₹)?\s?[0-9][0-9,]{2,}|\bwhy (is|was|are) (it|my offer|the offer|this)\b|"
                  r"\bwhat (is|are) (included|in|my offer made)|\bhow much (is|was|are)\b")
_PAYOUT = re.compile(r"\bwhen\b.{0,40}\b(paid|pay me|payment|money|receive|credited|transfer\w*|get it|refund)\b|\bhow long\b|"
                     r"\b(how soon|timeline|payout|pay ?out|how many days)\b|\bpaid\b.{0,20}\bwhen\b")
_NEXT = re.compile(r"\bwhat (should|do|shall|now|next|are my|happens)\b.{0,25}\b(do|next|now|options|i)\b|\bwhat now\b|\bnext step\b|"
                   r"\bwhat'?s next\b|\bwhat (should|do) i do\b|\bhow (do|can|should) i (accept|proceed|continue|claim|move)\b|"
                   r"\b(my )?options\b|\bnow what\b|\bwhat can i do\b")
_MORE = re.compile(r"\bwhy not more\b|\bmore money\b|\b(give|pay|offer|get) (me )?more\b|\btoo (low|little|less|small)\b|\bnot enough\b|\bunfair\b|"
                   r"\blow ?ball\b|\b(increase|raise|higher|bigger|improve)\b.{0,25}\b(offer|amount|it|payment)\b|\b(offer|amount)\b.{0,20}\b(higher|more|increase)\b|"
                   r"\bnegotiat\w*|\bmatch (my|the) garage\b|\bgarage'?s? (number|quote|price|estimate)\b|\bis that (all|it)\b|\bonly (rs|inr|₹)?\s?[0-9]|\b(maximum|highest|upper limit|max you|most you|most u|how much more|what is the max)\b")
_GREET = re.compile(r"^\s*(hi+|hello+|hey+|hallo|namaste|namaskar|good (morning|afternoon|evening)|yo)\b|"
                    r"\bcan (you|u) (read|understand|hear|see)\b|\b(are|r) (you|u) (a |an )?(bot|ai|human|real|robot|person|machine|assistant)\b|"
                    r"\bwho (are|r) (you|u)\b|\bwhat can (you|u) do\b|\b(is|are) (this|that|anyone|someone) (a |an )?(there|bot|ai|human)\b|"
                    r"\b(anyone|somebody|someone) there\b|\bhelp me\b|^\s*help\??\s*$|\btest(ing)?\b|\bread my message\b")


def stated_amount(text):
    m = AMOUNT.search(text or "")
    if not m:
        return None
    try:
        return int((m.group(1) or m.group(2)).replace(",", ""))
    except ValueError:
        return None


def _normalise(text):
    """Lower-case, map short forms, and repair near-miss spellings of the words the patterns use."""
    t = (text or "").lower().replace("’", "'").replace("₹", " ₹ ")
    out = []
    for w in re.findall(r"[a-z]+(?:'[a-z]+)?|\d[\d,]*|₹|[?.!]", t):
        w = _ALIASES.get(w, w)
        if w.isalpha() and len(w) > 4 and w not in VOCAB:
            close = difflib.get_close_matches(w, VOCAB, n=1, cutoff=0.84)
            if close:
                w = close[0]
        out.append(w)
    return " ".join(out).replace(" ?", "?").replace(" .", ".").replace(" !", "!")


def classify(text):
    """One intent for the message. Returns (intent, amount) where amount is a figure the customer named, or None."""
    t = _normalise(text)
    amount = stated_amount(text)
    asks_change = bool(_MONEY_VERB.search(t))
    asks_how = bool(_HOW.search(t) or _DEPRECIATION.search(t))
    # a figure with a verb that asks for a different amount is never a question about the calculation
    if amount is not None and asks_change and not asks_how:
        return "amount_named", amount
    if amount is not None and asks_change and re.search(r"\b(give|pay|want|need|demand|increase|raise|make it|match|set it)\b", t) \
            and not re.search(r"\bwhy\b|\bhow\b|\bexplain\b", t):
        return "amount_named", amount
    if _DEPRECIATION.search(t):
        return "depreciation", amount
    if _HOW.search(t):
        return "how_calculated", amount
    if _PAYOUT.search(t):
        return "payout_timing", amount
    if _NEXT.search(t):
        return "what_next", amount
    if amount is not None:
        return "amount_named", amount
    if _MORE.search(t):
        return "why_not_more", amount
    if _GREET.search(t):
        return "greeting_or_meta", amount
    return "other", amount
