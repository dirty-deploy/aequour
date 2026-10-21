"""
Dispute flow. The AI never haggles: the offer moves only when a garage quote line is supported
by the photos AND priced inside the genuine range for this model; a line above the range is flagged and
gets no uplift. The offer never exceeds the ceiling fixed before the conversation.

State machine (GAIA-style named end states):
  INTAKE -> OFFERED -> {SETTLED | UPDATED_OFFER | PARTNER_GARAGE | SURVEYOR}
  INTAKE -> {ESCALATED | SURVEYOR}      (integrity, plate, size, structural ...)
  any open state -> STALL (no reply)
"""
import hashlib
import json

from . import config as C
from . import engine as E

import re

_KW = sorted(C.PART_KEYWORDS, key=lambda k: -len(k))


_ABBREV = {"fr": "front", "frt": "front", "rr": "rear", "bk": "back", "lamp": "lamp", "headlamp": "headlamp",
           "assy": "", "lh": "", "rh": "", "l": "", "r": ""}


def map_part(description):
    """Match a quote line to a part class; longest keyword wins, whole words only, any word order
    ('Bumper Front Assy' and 'Front Bumper' both match), garage abbreviations expanded (Fr, Rr)."""
    words = [_ABBREV.get(w, w) for w in re.findall(r"[a-z]+", (description or "").lower())]
    have = set(w for w in words if w)
    for k in _KW:
        if set(k.split()) <= have:
            return C.PART_KEYWORDS[k]
    return None


def check_quote(policy, vision, result, quote, rc, today=None):
    """Line-by-line check of a garage quote against photos and the rate card."""
    assert result["decision"] == "OFFER"
    dets = {d["part_class"]: d for d in E.dedupe(vision["detections"])}
    ours = {ln["part_class"]: ln for ln in result["lines"]}
    ceil = {ln["part_class"]: ln for ln in result["ceiling_lines"]}
    verdicts, override = [], {}
    q_labour = q_paint = 0
    seen_in_quote = set()
    for ql in quote.get("lines", []):
        t, desc = ql.get("type"), ql.get("description", "")
        unit, qty = ql.get("unit_price", 0), ql.get("qty", 1)
        total = ql.get("total", unit * qty)
        v = {"description": desc, "type": t, "quoted": total}
        if t == "part":
            part = map_part(desc)
            if part is None:
                v.update(verdict="unknown_item", reason="could not match this item to a part")
            elif part not in ours:
                v.update(part=part, verdict="not_seen", reason="no damage found on this part in your photos")
            elif ours[part]["action"] != "replace":
                v.update(part=part, verdict="action_mismatch",
                         reason="photos suggest a repair, not a replacement; a partner garage can confirm")
                seen_in_quote.add(part)
            else:
                ref, cap = ours[part]["part_mrp"], ceil[part]["part_mrp"]
                v.update(part=part, reference=ref)
                if qty and qty > 1:
                    v["note"] = "quantity above 1 ignored"
                if unit <= ref * C.QUOTE_OK_TOLERANCE:
                    v.update(verdict="ok", reason="within the normal range for this part")
                elif unit <= cap:
                    v.update(verdict="high", reason="above our reference price but inside the genuine-price range for this model")
                else:
                    v.update(verdict="above_range", reason="above the genuine price range for this model")
                if unit <= cap:             # inside the genuine range: pay the quoted price (never below our reference)
                    override[part] = max(ref, unit)
                seen_in_quote.add(part)     # above the range: flagged, no uplift
        elif t == "labour":
            q_labour += total
            v["verdict"] = "pending"
        elif t == "paint":
            q_paint += total
            v["verdict"] = "pending"
        else:
            v.update(verdict="unverified", reason="item type not covered by the claim rules")
        verdicts.append(v)

    new_lines = [E.price_line(dets[p], policy, rc, "offer", today, part_mrp_override=override.get(p)) for p in sorted(dets)]
    lines_sum = sum(ln["line_total"] for ln in new_lines)
    our_lab, our_pnt = sum(l["labour"] for l in new_lines), sum(l["paint_gross"] for l in new_lines)
    ceil_lab, ceil_pnt = sum(l["labour"] for l in ceil.values()), sum(l["paint_gross"] for l in ceil.values())
    lab_up = pnt_up = 0
    if seen_in_quote:  # workmanship can only be supported if the quote is tied to damage we saw
        # a workmanship total inside the normal range is paid as quoted; one above the range gets no uplift
        lab_up = max(0, q_labour - our_lab) if 0 < q_labour <= ceil_lab else 0
        pnt_gross_up = max(0, q_paint - our_pnt) if 0 < q_paint <= ceil_pnt else 0
        pnt_up = E.r(pnt_gross_up * C.PAINT_NET_FACTOR)
    for v in verdicts:
        if v["verdict"] == "pending":
            cap = ceil_lab if v["type"] == "labour" else ceil_pnt
            tied = bool(seen_in_quote)
            v["verdict"] = "ok" if (tied and v["quoted"] <= cap) else ("above_range" if tied else "not_seen")
            v["reason"] = ("within the normal range for this job" if v["verdict"] == "ok" else
                           "above the normal range for this job" if tied else
                           "not tied to any damage found in your photos")
    gross2 = lines_sum + lab_up + pnt_up
    updated = min(result["ceiling"], max(result["offer"], gross2 - result["deductible"]))
    quote_total = quote.get("grand_total") or sum(v["quoted"] for v in verdicts)
    return {"verdicts": verdicts, "updated_offer": updated, "current_offer": result["offer"],
            "moved": updated > result["offer"], "quote_total": quote_total,
            "options": [{"id": "accept_updated", "label": "Accept the updated cash offer", "amount": updated},
                        {"id": "partner_garage", "label": "Repair at a partner garage at agreed rates"},
                        {"id": "surveyor", "label": "Ask for a surveyor to inspect"}]}


TERMINAL = {"SETTLED", "PARTNER_GARAGE", "SURVEYOR", "ESCALATED", "STALL"}
_ALLOWED = {
    "INTAKE": {"INTAKE", "OFFERED", "ESCALATED", "SURVEYOR", "STALL"},
    "OFFERED": {"SETTLED", "UPDATED_OFFER", "OFFERED", "PARTNER_GARAGE", "SURVEYOR", "ESCALATED", "STALL"},
    "UPDATED_OFFER": {"SETTLED", "UPDATED_OFFER", "PARTNER_GARAGE", "SURVEYOR", "ESCALATED", "STALL"},
}


class ClaimSession:
    def __init__(self, policy, rc, today=None):
        self.policy, self.rc, self.today = policy, rc, today
        self.state, self.ask_count, self.result, self.vision = "INTAKE", 0, None, None
        self.offer = self.updated_offer = None
        self.evidence_rounds, self.seen_quotes = 0, set()
        self.last_check, self.log, self.last_hash = None, [], "0" * 64
        self.flags = []

    # -- audit log: each record carries the hash of the previous one
    def _log(self, event, data=None):
        rec = {"seq": len(self.log), "event": event, "state": self.state, "data": data or {}, "prev": self.last_hash}
        rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()
        self.log.append(rec)
        self.last_hash = rec["hash"]

    @staticmethod
    def verify_log(log):
        prev = "0" * 64
        for rec in log:
            body = {k: v for k, v in rec.items() if k != "hash"}
            if rec["prev"] != prev or hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest() != rec["hash"]:
                return False
            prev = rec["hash"]
        return True

    def _go(self, new):
        assert self.state not in TERMINAL, f"session already ended in {self.state}"
        assert new in _ALLOWED[self.state], f"illegal transition {self.state} -> {new}"
        self.state = new

    @property
    def current_offer(self):
        return self.updated_offer if self.updated_offer is not None else self.offer

    # -- events
    def submit(self, vision):
        self.vision = vision
        res = E.assess(self.policy, vision, self.rc, self.today, self.ask_count)
        self.result = res
        if res["decision"] == "ASK_MORE":
            self.ask_count += 1
            self._go("INTAKE")
        elif res["decision"] == "ESCALATE":
            self._go("ESCALATED")
        elif res["decision"] == "SURVEYOR":
            self._go("SURVEYOR")
        else:
            self.offer = res["offer"]
            self._go("OFFERED")
        self._log("submit", {"decision": res["decision"], "reasons": res["reasons"], "tci": res["tci"], "offer": res["offer"]})
        return res

    def accept(self):
        self._go("SETTLED")
        self._log("accept", {"amount": self.current_offer})

    def dispute(self, quote):
        assert self.state in ("OFFERED", "UPDATED_OFFER"), "no open offer to dispute"
        key = hashlib.sha256(json.dumps(quote, sort_keys=True, default=str).encode()).hexdigest()
        if key in self.seen_quotes:
            self._log("dispute_duplicate_quote")
            return self.last_check
        if self.evidence_rounds >= C.MAX_EVIDENCE_ROUNDS:
            self._log("dispute_rounds_exhausted")
            return {**(self.last_check or {}), "moved": False, "note": "no further changes; choose a partner garage or a surveyor"}
        chk = check_quote(self.policy, self.vision, self.result, quote, self.rc, self.today)
        self.evidence_rounds += 1
        self.seen_quotes.add(key)
        self.last_check = chk
        if chk["updated_offer"] > self.current_offer:
            self.updated_offer = chk["updated_offer"]
            self._go("UPDATED_OFFER")
        self._log("dispute", {"moved": chk["moved"], "updated_offer": chk["updated_offer"],
                              "verdicts": [(v["description"], v["verdict"]) for v in chk["verdicts"]]})
        return chk

    def choose(self, option_id):
        target = {"accept_updated": "SETTLED", "partner_garage": "PARTNER_GARAGE", "surveyor": "SURVEYOR"}[option_id]
        self._go(target)
        self._log("choose", {"option": option_id, "amount": self.current_offer})

    def message(self, text):
        """Free text is classified for flags and logged. It can never change an amount or an input."""
        flags = E.classify_message(text)
        self.flags += flags
        if "abusive" in flags and self.state not in TERMINAL:
            self._go("ESCALATED")
        self._log("message", {"flags": flags, "chars": len(text or "")})
        return flags

    def timeout(self):
        if self.state not in TERMINAL:
            self._go("STALL")
            self._log("timeout")
