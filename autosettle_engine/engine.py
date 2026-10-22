"""
Auto-Settle AI policy engine. The code in this file OWNS THE MONEY.

    vision JSON + policy record  ->  assess()  ->  decision, line items, offer, ceiling, ledger

Nothing here reads free text from the customer or from the language model.
The language model only rewords what this file returns (see rationale.py).

Money formula per damaged part (all amounts whole rupees):
    line = part_net + labour + paint_net
    part_net  = MRP - depreciation            (replace only)
    paint_net = paint_gross * (1 - 0.25*0.5)  (paint material share, depreciated)
    offer     = max(0, sum(lines) - deductible)
    ceiling   = same claim priced at the top of every real range (see price_line mode="ceiling")
"""
import csv
import re
import statistics
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config as C


# ------------------------------------------------------------------ inputs
@dataclass(frozen=True)
class Policy:
    policy_id: str
    plate: str
    make: str
    model: str
    reg_date: str      # ISO date of first registration
    engine_cc: int
    idv: int           # insured declared value, rupees
    variant_group: str = "base"


def norm_plate(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def age_years(policy, today=None):
    today = today or C.TODAY
    return (today - date.fromisoformat(policy.reg_date)).days / 365.25


def r(x):
    """Round half up to whole rupees (avoids banker's rounding surprises)."""
    return int(x + 0.5)


# ------------------------------------------------------------------ rate card
def _d(s):
    s = (s or "").strip()
    return date.fromisoformat(s) if s else None


class RateCard:
    """Genuine part prices by (model, part). Rows tagged tier D are ignored.

    A row may carry a validity window (valid_from / valid_to, ISO dates; blank = unknown/open) saying which
    registration dates the listing is known to fit. A claim outside every window of its (model, part) still gets the
    same-model price, but it is marked "other_generation" (tier F, IMPUTED in the ledger), never "rate_card".
    """

    def __init__(self, path=None):
        path = Path(path) if path else Path(__file__).with_name("rate_card_v3.csv")
        self.rows = {}
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tier = row["confidence"][:1]
                if tier == "D":
                    continue
                try:
                    price = float(row["price_inr"])
                except ValueError:
                    continue
                self.rows.setdefault((row["model"], row["part_class"]), []).append(
                    (price, tier, _d(row.get("valid_from")), _d(row.get("valid_to"))))

    @staticmethod
    def _covers(row, on):
        _, _, vf, vt = row
        return on is None or ((vf is None or on >= vf) and (vt is None or on <= vt))

    def lookup(self, model, part, on=None):
        """on = registration date of the insured car (date) or None to ignore windows."""
        rows = self.rows.get((model, part))
        if rows:
            ok = [x for x in rows if self._covers(x, on)]
            use, status = (ok, "rate_card") if ok else (rows, "other_generation")
            prices = [x[0] for x in use]
            tier = min(x[1] for x in use) if ok else "F"
            return {"median": r(statistics.median(prices)), "max": r(max(prices)),
                    "tier": tier, "status": status, "n": len(use)}
        seg = C.SEGMENT.get(model)
        for status, ok in (("fallback_segment", lambda m: C.SEGMENT.get(m) == seg),
                           ("fallback_all", lambda m: True)):
            groups = [v for (m, p), v in self.rows.items() if p == part and m != model and ok(m)]
            if groups:
                meds = [statistics.median([x[0] for x in g]) for g in groups]
                allp = [x[0] for g in groups for x in g]
                return {"median": r(statistics.median(meds)), "max": r(max(allp)),
                        "tier": "F", "status": status, "n": len(allp)}
        return None


# ------------------------------------------------------------------ repair logic
def normalise_damage(label):
    return C.DAMAGE_MAP.get(label)


def dedupe(dets):
    """One detection per part: keep the worst. Stops split/duplicated detections double-paying."""
    best = {}
    for d in dets:
        dc = normalise_damage(d.get("damage_class"))
        part = d.get("part_class")
        sev = d.get("severity")
        if dc is None or part in (None, "unassigned") or sev not in C.SEVERITIES:
            continue
        score = (C.DAMAGE_RANK[dc], C.SEVERITIES.index(sev))
        if part not in best or score > best[part][0]:
            best[part] = (score, {**d, "damage_class": dc})
    return [best[p][1] for p in sorted(best)]


def decide_action(dc, sev, part):
    """repair-vs-replace rule [ASSUMPTION]. Returns None when we have no price basis."""
    if part in C.UNPRICEABLE:
        return None
    if part in C.REPLACE_ONLY:
        return "replace"
    if part in C.REPAIR_ONLY:
        if dc in ("Dent", "Broken part", "Missing part"):
            return "repair_dent"
        return "polish" if sev == "minor" else "repaint"
    if dc in ("Missing part", "Broken part"):
        return "replace"
    if dc == "Dent":
        return "replace" if sev == "severe" else "repair_dent"
    return "polish" if sev == "minor" else "repaint"      # Surface damage


def package(part, seg):
    """(lo, hi), is_proxy  for 'dent repair + panel paint' on this panel, or None."""
    real = C.PANEL_PACKAGE_REAL
    if part in real:
        row = real[part]
        if seg in row:
            return row[seg], False
        if part == "Fender" and seg == "suv":
            lo, hi = row["hatch"]
            return (r(lo * C.SUV_FENDER_FACTOR), r(hi * C.SUV_FENDER_FACTOR)), True
        return None
    if part in C.PANEL_PROXY:
        base, f = C.PANEL_PROXY[part]
        row = real[base]
        lo, hi = row.get(seg) or row["hatch"]
        return (r(lo * f), r(hi * f)), True
    return None


def price_line(det, policy, rc, mode="offer", today=None, part_mrp_override=None):
    """Price one damaged part. mode='offer' = best estimate, mode='ceiling' = top of every real range.

    Lesser-of rule: for a dent on a part that can be either repaired or replaced we pay the cheaper
    action. This also guarantees that calling damage 'less severe' can never raise the price."""
    part, dc, sev = det["part_class"], det["damage_class"], det["severity"]
    action = decide_action(dc, sev, part)
    if mode == "ceiling" and action == "polish":
        action = "repaint"
    line = _cost_line(det, action, policy, rc, mode, today, part_mrp_override)
    if dc == "Dent" and action == "repair_dent" and part in C.PRICED_PARTS and part not in C.REPLACE_ONLY:
        alt = _cost_line(det, "replace", policy, rc, mode, today, part_mrp_override)
        if not alt["unresolved"] and not line["unresolved"] and alt["line_total"] < line["line_total"]:
            line = alt
    return line


def _cost_line(det, action, policy, rc, mode, today, part_mrp_override):
    part, dc, sev = det["part_class"], det["damage_class"], det["severity"]
    seg = C.SEGMENT.get(policy.model, "hatch")
    pos = C.SEV_POS[sev] if mode == "offer" else 1.0
    line = {"part_class": part, "damage_class": dc, "severity": sev, "action": action,
            "part_mrp": 0, "dep_rate": 0.0, "dep_amount": 0, "part_net": 0, "labour": 0,
            "paint_gross": 0, "paint_dep": 0, "paint_net": 0, "line_total": 0,
            "price_tier": None, "price_status": None, "package_proxy": False, "unresolved": [],
            "dep_basis": None, "paint_basis": None}
    if action is None:
        line["unresolved"].append("no_price_basis_for_part")
        return line

    mrp = 0
    labour = 0
    paint_gross = 0.0
    pk = package(part, seg) if (part in C.PAINTED) else None
    if part in C.PAINTED and pk is None:
        line["unresolved"].append("no_labour_paint_basis")
    if pk:
        (lo, hi), line["package_proxy"] = pk

    if action == "replace":
        info = rc.lookup(policy.model, part, date.fromisoformat(policy.reg_date))
        if info is None:
            line["unresolved"].append("no_part_price")
        else:
            mrp = info["median"] if mode == "offer" else info["max"]
            line["price_tier"], line["price_status"] = info["tier"], info["status"]
            if part_mrp_override is not None:
                mrp = part_mrp_override
            basis = {"material": "metal", "reg_date": policy.reg_date, "loss_date": (today or C.TODAY).isoformat()}
            if part in C.PLASTIC_PARTS:
                line["dep_rate"] = C.PLASTIC_DEP
                basis["material"] = "plastic"
            elif part in C.GLASS_PARTS:
                line["dep_rate"] = 0.0
                basis["material"] = "glass"
            else:
                age = age_years(policy, today)
                line["dep_rate"] = C.metal_depreciation(age)
                basis.update(age_years=round(age, 1), band=C.metal_band(age)["label"])
            # the facts behind dep_rate, for the "?" help in the page; display only, no amount is computed from them
            basis["rate"] = line["dep_rate"]
            basis["list_price"] = int(mrp)
            line["dep_basis"] = basis
            labour = C.FITTING_LABOUR.get(part, C.FITTING_LABOUR_DEFAULT)
        if pk:
            paint_gross = (lo if mode == "offer" else (lo + hi) / 2) * C.PAINT_SHARE
    elif action == "repair_dent" and pk:
        pkg = lo + pos * (hi - lo)
        labour = r(pkg * (1 - C.PAINT_SHARE))
        paint_gross = pkg * C.PAINT_SHARE
    elif action == "repaint" and pk:
        paint_gross = (lo if mode == "offer" else (lo + hi) / 2) * C.PAINT_SHARE
    elif action == "polish":
        labour = C.POLISH
    elif pk is None:
        line["unresolved"].append("no_labour_paint_basis")

    if mode == "ceiling" and action in ("replace", "polish"):
        labour = r(labour * C.FITTING_LABOUR_CEILING_FACTOR)
    line["part_mrp"] = int(mrp)
    line["part_net"] = r(mrp * (1 - line["dep_rate"]))
    line["dep_amount"] = line["part_mrp"] - line["part_net"]
    line["labour"] = int(labour)
    line["paint_gross"] = r(paint_gross)
    line["paint_net"] = r(paint_gross * C.PAINT_NET_FACTOR)
    line["paint_dep"] = line["paint_gross"] - line["paint_net"]
    if line["paint_gross"]:
        line["paint_basis"] = {"painting": line["paint_gross"], "share": C.PAINT_MATERIAL_SHARE, "rate": C.PAINT_MATERIAL_DEP}
    line["line_total"] = line["part_net"] + line["labour"] + line["paint_net"]
    return line


# ------------------------------------------------------------------ information gate (GAIA-style TCI)
def info_gate(policy, vision, ask_count=0):
    """Returns (tci, fields, decision, reasons). decision in proceed|ask_more|escalate."""
    dets = vision.get("detections", [])
    plate_read = vision.get("plate_read")
    fields = {
        "policy_record": policy is not None,
        "plate_verified": plate_read is not None and norm_plate(plate_read) == norm_plate(policy.plate),
        "integrity_ok": not vision.get("integrity_flags"),
        "parts_identified": bool(dets) and all(
            d.get("part_class") not in (None, "unassigned") and d.get("part_conf", 0) >= C.MIN_PART_CONF
            for d in dets),
        "damage_identified": bool(dets) and all(
            d.get("damage_conf", 0) >= C.MIN_DAMAGE_CONF and d.get("damage_class") in C.DAMAGE_MAP
            and d.get("severity") in C.SEVERITIES for d in dets),
        "coverage_ok": "unassigned_damage" not in vision.get("flags", []),
    }
    tci = sum(fields.values()) / len(fields)
    if not fields["integrity_ok"]:
        return tci, fields, "escalate", ["integrity:" + ",".join(vision["integrity_flags"])]
    if "structural_suspected" in vision.get("flags", []):
        # a heavy crash needs an inspection, not more photos (hidden damage: supports, airbags, pillars)
        return tci, fields, "surveyor", ["structural_or_safety_damage"]
    if plate_read is not None and not fields["plate_verified"]:
        return tci, fields, "escalate", ["plate_mismatch"]
    if tci >= C.TAU_GATE:
        return tci, fields, "proceed", []
    missing = [k for k, v in fields.items() if not v]
    if ask_count >= C.K_STALL:
        return tci, fields, "escalate", ["info_incomplete_after_%d_requests" % C.K_STALL] + missing
    return tci, fields, "ask_more", missing


# ------------------------------------------------------------------ main entry
def assess(policy, vision, rc, today=None, ask_count=0):
    tci, fields, gate, reasons = info_gate(policy, vision, ask_count)
    out = {"decision": None, "reasons": list(reasons), "tci": round(tci, 3), "missing": [k for k, v in fields.items() if not v],
           "lines": [], "ceiling_lines": [], "gross": None, "deductible": C.deductible(policy.engine_cc),
           "offer": None, "ceiling": None, "ledger": [], "age_years": round(age_years(policy, today), 2),
           "policy_id": policy.policy_id}
    if gate == "escalate":
        out["decision"] = "ESCALATE"
        return out
    if gate == "surveyor":
        out["decision"] = "SURVEYOR"
        return out
    if gate == "ask_more":
        out["decision"] = "ASK_MORE"
        return out
    if any(d.get("severity") == "severe" and d.get("damage_conf", 0) < C.LOW_CONF_SEVERE for d in vision["detections"]):
        # a severe call the detector is unsure of drives the biggest line items: a human checks it before any offer
        out["decision"] = "ESCALATE"
        out["reasons"].append("low_conf_severe")
        return out

    dets = dedupe(vision["detections"])
    lines = [price_line(d, policy, rc, "offer", today) for d in dets]
    ceil = [price_line(d, policy, rc, "ceiling", today) for d in dets]
    unresolved = sorted({u for ln in lines for u in ln["unresolved"]})
    out["lines"], out["ceiling_lines"] = lines, ceil
    out["ledger"] = build_ledger(policy, lines, today)
    if unresolved:
        out["decision"] = "ESCALATE"
        out["reasons"] += ["unpriceable:" + ",".join(unresolved)]
        return out

    gross = sum(ln["line_total"] for ln in lines)
    ded = out["deductible"]
    out["gross"] = gross
    structural = ("structural_suspected" in vision.get("flags", []) or
                  any(d["part_class"] in C.STRUCTURAL_WATCH and d["severity"] == "severe" for d in dets))
    if structural:
        out["reasons"].append("structural_or_safety_damage")
    if gross >= C.SURVEYOR_REQUIRED:
        out["reasons"].append("gross_loss_at_or_above_surveyor_limit")
    if gross >= C.TOTAL_LOSS_SHARE_OF_IDV * policy.idv:
        out["reasons"].append("possible_constructive_total_loss")
    if structural or gross >= C.SURVEYOR_REQUIRED or "possible_constructive_total_loss" in out["reasons"]:
        out["decision"] = "SURVEYOR"
        return out
    if gross >= C.GROSS_REVIEW:
        out["decision"] = "ESCALATE"
        out["reasons"].append("gross_loss_at_or_above_review_threshold")
        return out

    out["offer"] = max(0, gross - ded)
    out["ceiling"] = max(out["offer"], max(0, sum(ln["line_total"] for ln in ceil) - ded))
    out["decision"] = "OFFER"
    return out


# ------------------------------------------------------------------ assumptions ledger
def build_ledger(policy, lines, today=None):
    """Every input to the price, labelled OBSERVED (evidence/regulation), IMPUTED (assumed) or UNRESOLVED."""
    led = [
        {"item": "vehicle", "value": f"{policy.make} {policy.model}", "status": "OBSERVED", "source": "policy record via number plate"},
        {"item": "vehicle_age_years", "value": round(age_years(policy, today), 1), "status": "OBSERVED", "source": "policy record"},
        {"item": "deductible", "value": C.deductible(policy.engine_cc), "status": "OBSERVED", "source": "compulsory deductible rule"},
        {"item": "gst_treatment", "value": "prices treated as tax-inclusive", "status": "IMPUTED", "source": "assumption; open question"},
    ]
    for ln in lines:
        p = ln["part_class"]
        led.append({"item": f"{p}.damage", "value": f"{ln['damage_class']} / {ln['severity']}", "status": "OBSERVED", "source": "photo analysis"})
        led.append({"item": f"{p}.action", "value": ln["action"], "status": "IMPUTED", "source": "repair-vs-replace rule"})
        if ln["action"] == "replace":
            if ln["price_status"] == "rate_card":
                st = "OBSERVED" if ln["price_tier"] in ("A", "B", "C") else "IMPUTED"
                led.append({"item": f"{p}.part_price", "value": ln["part_mrp"], "status": st,
                            "source": f"genuine-part listing, confidence tier {ln['price_tier']}"})
            elif ln["price_status"] == "other_generation":
                led.append({"item": f"{p}.part_price", "value": ln["part_mrp"], "status": "IMPUTED",
                            "source": "genuine-part listing is for a different generation of this model"})
            elif ln["price_status"]:
                led.append({"item": f"{p}.part_price", "value": ln["part_mrp"], "status": "IMPUTED",
                            "source": f"no listing for this model; {ln['price_status']}"})
            else:
                led.append({"item": f"{p}.part_price", "value": None, "status": "UNRESOLVED", "source": "no price"})
            led.append({"item": f"{p}.depreciation", "value": ln["dep_rate"], "status": "OBSERVED", "source": "insurance depreciation rule"})
        if ln["labour"] or ln["paint_gross"]:
            src = "estimated from garage price ranges" + ("; panel size proxied" if ln["package_proxy"] else "")
            led.append({"item": f"{p}.labour_and_paint", "value": ln["labour"] + ln["paint_gross"], "status": "IMPUTED", "source": src})
        for u in ln["unresolved"]:
            led.append({"item": f"{p}.{u}", "value": None, "status": "UNRESOLVED", "source": "missing basis"})
    return led


# ------------------------------------------------------------------ pivotal conditions
_SEV_NEIGH = {"minor": ["moderate"], "moderate": ["minor", "severe"], "severe": ["moderate"]}
_CLASS_ALT = {"Dent": "Broken part", "Broken part": "Dent", "Surface damage": "Dent"}


def pivots(policy, vision, rc, today=None):
    """Single-input flips that change the outcome. INTERNAL (contains amounts, so it can reveal the ceiling)."""
    base = assess(policy, vision, rc, today)
    if base["decision"] != "OFFER":
        return []
    dets = dedupe(vision["detections"])
    out = []
    for i, d in enumerate(dets):
        variants = [("severity", d["severity"], s, {**d, "severity": s}) for s in _SEV_NEIGH[d["severity"]]]
        if d["damage_class"] in _CLASS_ALT:
            alt = _CLASS_ALT[d["damage_class"]]
            variants.append(("damage_class", d["damage_class"], alt, {**d, "damage_class": alt}))
        for kind, frm, to, nd in variants:
            v2 = {**vision, "detections": dets[:i] + [nd] + dets[i + 1:]}
            res = assess(policy, v2, rc, today)
            if res["decision"] == base["decision"] and res["offer"] == base["offer"]:
                continue
            if res["offer"] is not None and res["offer"] > base["offer"]:
                direction = "up"
            elif res["offer"] is not None and res["offer"] < base["offer"]:
                direction = "down"
            else:
                direction = "review"
            out.append({"part_class": d["part_class"], "kind": kind, "from": frm, "to": to,
                        "direction": direction, "offer_before": base["offer"], "offer_after": res["offer"],
                        "decision_after": res["decision"], "flipped_vision": v2})
    return out


def customer_pivots(pivs):
    """Customer-safe pivots: condition + evidence needed + direction. NO amounts (amounts would leak the ceiling)."""
    safe = []
    for p in pivs:
        word = {"severity": "is {to} rather than {from}", "damage_class": "is {to} rather than {from}"}[p["kind"]]
        safe.append({"part_class": p["part_class"], "direction": p["direction"],
                     "condition": "if an inspection or closer photos show the damage on the %s %s" %
                                  (p["part_class"].lower().replace("-", " "), word.format(**{"to": str(p["to"]).lower(), "from": str(p["from"]).lower()}))})
    return safe


# ------------------------------------------------------------------ message flags (text can never change a number)
_ABUSE = re.compile(r"\b(idiot|stupid|scam|fraud|useless|cheat|bastard|damn|bloody|shut up|fuck\w*|chor|bekaar|"
                    r"bewa?koo?f|kamina|harami)\b|\bf\*{2,}|बेवकूफ|चोर|कमीन|हरामी", re.I)
# keyword flags only; the real protection is that no free text reaches assess(). Hinglish/Hindi terms added in RUN1.
_INJECT = re.compile(r"(ignore (all |the )?(previous|prior|above)|system prompt|you are now|developer mode|"
                     r"reveal .{0,20}(ceiling|limit|maximum)|override|pay me \d|approve .{0,15}(rs|inr|₹)\s*\d|"
                     r"upper limit|highest (you|we) (can|could)|max(imum)? kitna|limit batao|ignore karo|"
                     r"instructions? ignore|निर्देश.{0,20}(अनदेखा|नज़रअंदाज़|नजरअंदाज))", re.I)


# legal / regulator threats (RUN2): a human answers these, like abuse. English, Hinglish and Hindi spellings.
_LEGAL = re.compile(r"\bombudsm[ae]n|\bombud\b|\blokpal\b|\blegal (notice|action|case|proceedings?)|\bsue\b|\bcourt case|"
                    r"\b(go|going|take|taking|jaunga|jaungi|jayenge)\b.{0,25}\bcourt\b|\bcourt (mein|me)\b|"
                    r"\bconsumer (court|forum|commission)|\blawyers?\b|\battorneys?\b|\bsolicitor\b|\b[vw]a?k[ei]+l\b|"
                    r"\bk[a]+n[o]+ni\b|\bpolice (complaint|report|case|station|mein|me|ko)\b|\bpulis\b|"
                    r"(?-i:\bFIR\b)|"
                    r"लोकपाल|ओम्?बड्?समै?न|ओंबड्समैन|कानूनी|उपभोक्ता\s*(अदालत|फोरम|आयोग|कोर्ट)|वकील|पुलिस|कोर्ट|अदालत|मुकदमा", re.I)


def classify_message(text):
    """Heuristic flags only. The real protection is structural: no free text reaches any input of assess()."""
    flags = []
    if _ABUSE.search(text or ""):
        flags.append("abusive")
    if _INJECT.search(text or ""):
        flags.append("injection_suspected")
    if _LEGAL.search(text or ""):
        flags.append("legal_threat")
    return flags
