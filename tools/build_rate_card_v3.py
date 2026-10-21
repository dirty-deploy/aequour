"""
Rate card v3 = v2 + the fixes from rate_card_v2_flags.csv (TASKS RUN1, Task 2). v2 is left untouched.

Every price, URL and window changed here was read on a page opened in this run (21 Oct 2026, browser):
boodmo part pages (MRP, "Incl. of all taxes", "<part> for <MAKE> <MODEL> <GEN>", compatibility table) and
Maruti Suzuki genuine-parts product pages (MRP, "Incl. of all taxes", "This item fits").
Rows are addressed by their CSV line number in rate_card_v2.csv (line 1 = header), as in the flags file.

    python tools/build_rate_card_v3.py   -> autosettle_engine/rate_card_v3.csv  (+ run1/ratecard_v3_changes.json)
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "autosettle_engine" / "rate_card_v2.csv"
V3 = ROOT / "autosettle_engine" / "rate_card_v3.csv"
OPENED = "2026-10-21 page opened in RUN1 (browser)"
B = "https://boodmo.com/catalog/"
MS = "https://www.marutisuzuki.com/genuine-parts/"

# line -> dict of field updates; "why" goes to the change list
EDITS = {
    # ---- rejects named by the task
    6: {"confidence": "D_REJECTED_UNVERIFIED", "why": "Creta tail lamp C row from an aftermarket template-price source, never opened; reject per task"},
    15: {"confidence": "D_REJECTED_NOT_FOUND", "why": "Nexon grille 2,820: its own flag says no genuine item at this price exists; reject per task"},
    # ---- range-endpoint A rows -> B, part-page URL and window from the opened page
    8: {"confidence": "B_RANGE_ENDPOINT", "source_url": B + "part-543888516304-57903301/", "valid_from": "2020-01-01",
        "valid_to": "2023-02-28", "window_basis": "boodmo part page compatibility rows 01.2020-02.2023",
        "flag": "range endpoint", "why": "variant-range endpoint (FRONT BUMPER SKIN 6,035; listing range 4,365-6,035); part page opened: fits NEXON 01.2020-02.2023"},
    10: {"confidence": "B_RANGE_ENDPOINT", "source_url": B + "part-assy_hood_shell-37962940/", "valid_from": "2017-08-01",
         "valid_to": "2020-01-31", "window_basis": "boodmo part page: NEXON 1ST GEN 08.2017-01.2020",
         "flag": "range endpoint", "why": "variant-range endpoint (ASSY HOOD SHELL 7,947; hoods 7,947-12,201); part page opened: NEXON 1ST GEN 08.2017-01.2020"},
    36: {"confidence": "B_RANGE_ENDPOINT", "source_url": B + "part-lamp_assy_head_lh-50518017/", "valid_from": "2019-05-01",
         "valid_to": "2022-05-31", "window_basis": "boodmo part page: VENUE 1ST GEN 05.2019-06.2022",
         "flag": "range endpoint; base variant, higher trims cost more", "why": "variant-range endpoint (LH lamps 5,436-25,285); part page opened: VENUE 1ST GEN"},
    37: {"confidence": "B_RANGE_ENDPOINT", "source_url": B + "part-lamp_assy_head_rh-58446918/", "valid_from": "2022-06-01",
         "valid_to": "2025-10-31", "window_basis": "boodmo part page: VENUE 1ST GEN F/L 06.2022-10.2025",
         "flag": "range endpoint; base variant, higher trims cost more", "why": "variant-range endpoint (RH lamps 5,436-24,196); part page opened: VENUE 1ST GEN F/L"},
    # ---- windowless C/B rows: window (and MRP) from the opened page, or C + "no window"
    9: {"confidence": "C_LISTED_UNVERIFIED", "window_basis": "no window",
        "why": "Nexon rear bumper 6,162 (aftermarket listing): no genuine item at this price in the boodmo NEXON rear-bumper listing (5,472-6,292); stays C, no window"},
    13: {"price_inr": "9783", "confidence": "A_CONFIRMED", "source_url": B + "part-543854400161-53163265/",
         "valid_from": "2020-01-01", "valid_to": "2023-07-31", "window_basis": "boodmo part page: NEXON 1ST GEN F/L (+EV F/L)",
         "flag": "", "why": "8,724 was a discounted selling price; part page opened: HEADLAMP ASSY WITH CLEAR LENS LH, MRP 9,783 incl. taxes, NEXON 1ST GEN F/L"},
    14: {"price_inr": "9783", "confidence": "A_CONFIRMED", "source_url": B + "part-543854400162-53163266/",
         "valid_from": "2020-01-01", "valid_to": "2023-07-31", "window_basis": "boodmo part page: NEXON 1ST GEN F/L (+EV F/L)",
         "flag": "", "why": "8,724 was a discounted selling price; part page opened: HEADLAMP ASSY WITH CLEAR LENS RH, MRP 9,783 incl. taxes, NEXON 1ST GEN F/L"},
    29: {"confidence": "A_CONFIRMED", "source_url": B + "part-headlamp_assy_l-58237908/", "valid_from": "2022-07-01",
         "valid_to": "", "window_basis": "boodmo part page: BREZZA 2ND GEN 07.2022-now",
         "why": "Maruti store page shows MRP 7,799 but no fitment; same part on boodmo (HEADLAMP ASSY L, MRP 7,799 incl. taxes) fits BREZZA 2ND GEN"},
    # ---- listing-URL A rows: part-page URL recorded from the page opened in this run
    7: {"source_url": B + "part-glass_assy_windshield-53900676/", "why": "listing URL -> part page (fits CRETA 2ND GEN + F/L, Alcazar)"},
    11: {"source_url": B + "part-ced_fender_assy_rh-58330605/", "why": "listing URL -> part page (CED FENDER ASSY RH, NEXON 2ND GEN)"},
    12: {"source_url": B + "part-assy_rear_door_shell_rh_ced_coated-58370223/", "side": "R",
         "why": "listing URL -> part page (REAR DOOR SHELL RH, NEXON 2ND GEN); side corrected L -> R (the page is the RH door)"},
    19: {"source_url": B + "part-panel_assyfr_doorl-57597798/", "why": "listing URL -> part page (PANEL ASSY FR DOOR L, SWIFT 2ND GEN)"},
    34: {"source_url": B + "part-panel_assy_front_door_lh-50408057/", "why": "listing URL -> part page (VENUE 1ST GEN + F/L)"},
    35: {"source_url": B + "part-panel_assy_rear_door_lh-50408061/", "why": "listing URL -> part page (VENUE 1ST GEN)"},
    38: {"source_url": B + "part-72800k3000-53621853/", "why": "listing URL -> part page (PANEL ASSY-TAIL GATE, VENUE 1ST GEN)"},
    43: {"source_url": B + "part-544554430123-58539278/", "why": "listing URL -> part page (TAIL LAMP LED ASSY LH, PUNCH 1ST GEN)"},
    44: {"source_url": B + "part-544554430124-58180024/", "why": "listing URL -> part page (TAIL LAMP LED ASSY RH, PUNCH 1ST GEN)"},
    45: {"source_url": B + "part-544567100101-58179896/", "why": "listing URL -> part page (WINDSCREEN GLASS ASSY, PUNCH 1ST GEN + F/L)"},
    22: {"source_url": MS + "head-lamp-assembly-left/35300m55t23", "why": "Maruti listing URL -> product page (MRP 12,955 incl. taxes; fits BALENO 2022-2026)"},
    23: {"source_url": MS + "head-lamp-assembly-right/35100m55t23", "why": "Maruti listing URL -> product page (MRP 12,955 incl. taxes; fits BALENO 2022-2026)"},
    # ---- two-piece bumpers: one rule
    147: {"confidence": "D_SUPERSEDED_BY_SUM", "why": "Brezza 2nd-gen upper skin only; both skins now priced, so the replace price is the new sum row (keeps partial and full prices apart)"},
    148: {"confidence": "C_PARTIAL_UPPER_ONLY", "flag": "upper skin only, replace understated",
          "why": "Brezza 1st-gen upper skin; no lower skin priced for this generation"},
    149: {"confidence": "C_PARTIAL_UPPER_ONLY", "flag": "upper skin only, replace understated",
          "why": "Punch upper skin; the only priced lower skin (2,515) fits PUNCH EV, not this car"},
}

NEW = [
    {"make": "Maruti", "model": "Brezza", "generation": "BREZZA 2ND GEN", "generation_status": "page",
     "part_class": "Front-bumper", "side": "single", "part_number": "boodmo#58238284+58238286", "price_inr": "4120",
     "gst_included": "yes", "source_name": "boodmo", "source_url": B + "part-bumper_front_upper-58238284/",
     "confidence": "B_SUM_OF_TWO_PIECES", "flag": "sum of two pieces",
     "claude_note": "BUMPER FRONT UPPER 2,050 (" + B + "part-bumper_front_upper-58238284/) + BUMPER FRONT LOWER 2,070 ("
                    + B + "part-bumper_front_lower-58238286/); both MRP incl. taxes, both fit BREZZA 2ND GEN",
     "valid_from": "2022-07-01", "valid_to": "", "window_basis": "boodmo part pages: BREZZA 2ND GEN 07.2022-now",
     "verified": OPENED, "why": "two-piece bumper with both skins priced: replace = sum (tier B)"},
]

KEEP_NOTE = {139: "kept A: part page title is COVER-FR BUMPER (not UPR/LWR) and fits CRETA 2ND GEN; the UPR/LWR covers in "
                  "the listing belong to other generations"}


def main():
    with open(V2, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        cols, rows = rd.fieldnames, list(rd)
    changes = []
    for line, upd in EDITS.items():
        row = rows[line - 2]
        before = {k: row[k] for k in ("model", "part_class", "price_inr", "confidence")}
        assert not row["confidence"].startswith("D"), f"line {line} is already D; not touched"
        for k, v in upd.items():
            if k != "why":
                row[k] = v
        row["verified"] = OPENED
        changes.append({"line": line, **before, "new_confidence": row["confidence"], "new_price": row["price_inr"], "why": upd["why"]})
    for r in NEW:
        why = r.pop("why")
        rows.append(r)
        changes.append({"line": "new", "model": r["model"], "part_class": r["part_class"], "price_inr": r["price_inr"],
                        "confidence": "", "new_confidence": r["confidence"], "new_price": r["price_inr"], "why": why})
    for line, note in KEEP_NOTE.items():
        changes.append({"line": line, "model": rows[line - 2]["model"], "part_class": rows[line - 2]["part_class"],
                        "price_inr": rows[line - 2]["price_inr"], "confidence": rows[line - 2]["confidence"],
                        "new_confidence": rows[line - 2]["confidence"], "new_price": rows[line - 2]["price_inr"], "why": note})
    with open(V3, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (ROOT / "run1" / "ratecard_v3_changes.json").write_text(json.dumps(changes, indent=1))
    print(f"v3: {len(rows)} rows, {len(EDITS)} edited, {len(NEW)} added -> {V3}")


if __name__ == "__main__":
    main()
