"""
Rate card v2 = v1 + rows verified on boodmo part pages on 20 Oct 2026 + corrections to v1 rows.

Every new row was read from the boodmo product page in the browser: MRP, "Incl. of all taxes", and the
"<part> for <MAKE> <MODEL> <GEN>" fitment line with the compatibility table (registration years).
Validity windows come from those generation labels (dates as shown in boodmo's compatibility tables).
Genuine brands only (MOBIS for Hyundai, MARUTI SUZUKI, TATA). Base variant = cheapest full assembly for that generation.

    python tools/build_rate_card_v2.py   -> autosettle_engine/rate_card_v2.csv
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "autosettle_engine" / "rate_card_v1.csv"
V2 = ROOT / "autosettle_engine" / "rate_card_v2.csv"
VERIFIED = "2026-10-20 boodmo part page opened (browser)"

# generation windows (first registration), from boodmo compatibility tables
GEN = {
    "CRETA 1ST GEN": ("2015-06-01", "2020-01-31"), "CRETA 2ND GEN": ("2020-02-01", "2023-11-30"),
    "CRETA 2ND GEN+F/L": ("2020-02-01", ""), "CRETA 2ND GEN F/L": ("2023-12-01", ""),
    "I20 2ND GEN": ("2014-08-01", "2020-10-31"), "I20 2ND GEN pre-F/L": ("2014-08-01", "2018-01-31"),
    "I20 2ND GEN F/L": ("2018-02-01", "2020-10-31"), "I20 3RD GEN": ("2020-11-01", ""),
    "I20 3RD GEN pre-F/L": ("2020-11-01", "2023-08-31"),
    "VENUE 1ST GEN+F/L": ("2019-05-01", "2025-10-31"), "VENUE 1ST GEN pre-F/L": ("2019-05-01", "2022-05-31"),
    "VENUE 1ST GEN F/L": ("2022-06-01", "2025-10-31"),
    "SWIFT 2ND GEN": ("2011-06-01", "2017-12-31"), "SWIFT 3RD GEN": ("2018-01-01", "2024-04-30"),
    "SWIFT 4TH GEN": ("2024-05-01", ""),
    "BALENO 2ND GEN": ("2015-08-01", "2021-12-31"), "BALENO 3RD GEN": ("2022-01-01", ""),
    "VITARA BREZZA 1ST GEN": ("2016-02-01", "2022-06-30"), "VITARA BREZZA 1ST GEN pre-F/L": ("2016-02-01", "2020-01-31"),
    "BREZZA 2ND GEN": ("2022-07-01", ""),
    "NEXON 1ST GEN": ("2017-08-01", "2023-07-31"), "NEXON 1ST+2ND GEN": ("2017-08-01", ""), "NEXON 2ND GEN": ("2023-08-01", ""),
    "PUNCH 1ST GEN": ("2021-10-01", ""), "PUNCH 1ST GEN pre-F/L": ("2021-10-01", "2025-12-31"), "PUNCH 1ST GEN F/L": ("2026-01-01", ""),
}
MAKE = {"Creta": "Hyundai", "i20": "Hyundai", "Venue": "Hyundai", "Swift": "Maruti", "Baleno": "Maruti",
        "Brezza": "Maruti", "Nexon": "Tata", "Punch": "Tata"}

# (model, part, side, boodmo id, page title, MRP, generation key, tier, note)
NEW = [
    # ---- mirrors (all 8 models were empty in v1)
    ("Creta", "Mirror", "R", 33582316, "MIRROR ASSY-OUTSIDE RR VIEW,RH", 2489, "CRETA 1ST GEN", "A", "LH same price (33582309)"),
    ("Creta", "Mirror", "L", 58227279, "MIRROR ASSY-OUTSIDE RR VIEW,LH", 2997, "CRETA 2ND GEN F/L", "A", "RH same price (58227288)"),
    ("i20", "Mirror", "L", 33602354, "MIRROR ASSY-OUTSIDE RR VIEW,LH", 1527, "I20 2ND GEN", "A", "2nd gen Elite/Active; RH same price"),
    ("Venue", "Mirror", "L", 57674738, "MIRROR ASSY-OUTSIDE RR VIEW,LH", 1378, "VENUE 1ST GEN+F/L", "A", "base mirror; RH same price; higher-trim mirror 3,998 (fitment not read)"),
    ("Swift", "Mirror", "single", 36625480, "MIRROR ASSY, OUT REAR VIEW", 1375, "SWIFT 2ND GEN", "A", ""),
    ("Swift", "Mirror", "R", 58369274, "MIRROR ASSY OUT REAR VIEW R", 1425, "SWIFT 4TH GEN", "A", ""),
    ("Baleno", "Mirror", "L", 6788790, "MIRROR ASSY OUT REAR VIEW LH", 1165, "BALENO 2ND GEN", "A", ""),
    ("Baleno", "Mirror", "R", 58267955, "MIRROR ASSY OUT REAR VIEW RH", 1650, "BALENO 3RD GEN", "A", "LH same price (58267956)"),
    ("Brezza", "Mirror", "L", 38162450, "MIRROR ASSY OUT REAR VIEW L", 1840, "VITARA BREZZA 1ST GEN pre-F/L", "A", "RH same price"),
    ("Nexon", "Mirror", "L", 37963926, "ORVM ASSY;MANUAL OPERATED & SRL;LH", 3112, "NEXON 1ST+2ND GEN", "A", "manual ORVM; page lists 1st gen, F/L and 2nd gen"),
    ("Punch", "Mirror", "R", 58180400, "ORVM ASSY,TIP TAP TYPE,RH", 4267, "PUNCH 1ST GEN", "A", "LH same price; electric ORVM 4,777"),
    # ---- back windshields (all 8 empty in v1)
    ("Creta", "Back-windshield", "single", 53900684, "GLASS ASSY-TAIL GATE", 2177, "CRETA 2ND GEN+F/L", "A", "page: CRETA 2ND GEN, 2ND GEN F/L"),
    ("Creta", "Back-windshield", "single", 33582464, "GLASS ASSY-TAIL GATE", 3465, "CRETA 1ST GEN", "A", ""),
    ("i20", "Back-windshield", "single", 25454758, "GLASS ASSY-REAR WINDOW", 2340, "I20 2ND GEN", "A", ""),
    ("Venue", "Back-windshield", "single", 58312087, "GLASS ASSY-TAIL GATE", 3842, "VENUE 1ST GEN+F/L", "A", ""),
    ("Swift", "Back-windshield", "single", 32999451, "GLASS BACK DOOR WINDOW", 2160, "SWIFT 2ND GEN", "A", ""),
    ("Baleno", "Back-windshield", "single", 6769752, "GLASS BACK DOOR WINDOW", 2770, "BALENO 2ND GEN", "A", ""),
    ("Baleno", "Back-windshield", "single", 58209287, "GLASS BACK DOOR WINDOW", 2450, "BALENO 3RD GEN", "A", ""),
    ("Brezza", "Back-windshield", "single", 36625324, "GLASS COMP BACK DOOR WINDOW", 2215, "VITARA BREZZA 1ST GEN", "A", ""),
    ("Brezza", "Back-windshield", "single", 58238618, "GLASS BACK DOOR WINDOW", 2595, "BREZZA 2ND GEN", "A", ""),
    ("Nexon", "Back-windshield", "single", 58330705, "BACK LIGHT GLASS ASSY", 2628, "NEXON 2ND GEN", "A", ""),
    ("Punch", "Back-windshield", "single", 58180064, "TAILGATE GLASS ASSY WITH DEMISTER", 2276, "PUNCH 1ST GEN", "A", ""),
    # ---- bumpers
    ("i20", "Front-bumper", "single", 57882251, "COVER-FR BUMPER", 2081, "I20 3RD GEN pre-F/L", "A", ""),
    ("i20", "Back-bumper", "single", 58213558, "COVER-RR BUMPER", 2481, "I20 3RD GEN pre-F/L", "A", ""),
    ("Venue", "Back-bumper", "single", 58446953, "COVER-RR BUMPER", 2691, "VENUE 1ST GEN F/L", "A", ""),
    ("Swift", "Back-bumper", "single", 38438059, "BUMPER RR (BLACK)", 2700, "SWIFT 3RD GEN", "A", "unpainted (black) cover"),
    ("Baleno", "Front-bumper", "single", 50719873, "BUMPER FR (BLACK)", 2650, "BALENO 2ND GEN", "A", "unpainted (black) cover"),
    ("Baleno", "Back-bumper", "single", 6791970, "BUMPER RR (BLACK)", 4400, "BALENO 2ND GEN", "A", ""),
    ("Baleno", "Back-bumper", "single", 58209037, "BUMPER REAR", 4100, "BALENO 3RD GEN", "A", ""),
    # ---- body panels, glass, lamps, tailgates
    ("i20", "Tail-light", "L", 58214849, "LAMP ASSY-REAR COMB OUTSIDE,LH", 2529, "I20 3RD GEN", "A", "split lamp: outer (body) unit, the part usually broken; RH same price"),
    ("i20", "Windshield", "single", 25454759, "GLASS ASSY-WINDSHIELD", 3307, "I20 2ND GEN", "A", ""),
    ("i20", "Windshield", "single", 58214071, "GLASS ASSY-WINDSHIELD", 3531, "I20 3RD GEN", "A", ""),
    ("i20", "Trunk", "single", 25455248, "PANEL ASSY-TAIL GATE", 4238, "I20 2ND GEN pre-F/L", "A", ""),
    ("i20", "Trunk", "single", 39704459, "PANEL ASSY-TAIL GATE", 4825, "I20 2ND GEN F/L", "A", ""),
    ("Venue", "Windshield", "single", 50517954, "GLASS ASSY-WINDSHIELD", 5013, "VENUE 1ST GEN+F/L", "A", ""),
    ("Venue", "Grille", "single", 58467193, "GRILLE ASSY-RADIATOR", 4456, "VENUE 1ST GEN pre-F/L", "A", ""),
    ("Venue", "Grille", "single", 58447734, "GRILLE ASSY-RADIATOR", 6142, "VENUE 1ST GEN F/L", "A", ""),
    ("Creta", "Trunk", "single", 58226874, "PANEL ASSY-TAIL GATE", 9462, "CRETA 2ND GEN", "A", ""),
    ("Swift", "Fender", "R", 58369331, "PANEL FRONT FENDER R", 1385, "SWIFT 4TH GEN", "A", "LH same price"),
    ("Swift", "Windshield", "single", 38438219, "GLASS WINDSHIELD", 4100, "SWIFT 3RD GEN", "A", ""),
    ("Swift", "Windshield", "single", 58369132, "GLASS WINDSHIELD", 4230, "SWIFT 4TH GEN", "A", ""),
    ("Swift", "Trunk", "single", 38437691, "PANEL ASSY BACK DOOR", 5070, "SWIFT 3RD GEN", "A", "Maruti calls the tailgate 'back door'"),
    ("Swift", "Trunk", "single", 9782069, "PANEL ASSY BACK DOOR", 4650, "SWIFT 2ND GEN", "A", "this is the v1 'Swift Back-door 4,650' row: it is a tailgate"),
    ("Baleno", "Hood", "single", 31679343, "PANEL FRONT HOOD", 5720, "BALENO 2ND GEN", "A", ""),
    ("Baleno", "Hood", "single", 58264840, "PANEL COMP FRONT HOOD", 5750, "BALENO 3RD GEN", "A", ""),
    ("Baleno", "Fender", "L", 6781283, "PANEL FRONT FENDER L", 1520, "BALENO 2ND GEN", "A", "RH same price"),
    ("Baleno", "Fender", "R", 58208903, "PANEL FRONT FENDER RH", 1785, "BALENO 3RD GEN", "A", "LH same price"),
    ("Baleno", "Front-door", "R", 58225081, "PANEL ASSY FRONT DOOR RH", 6650, "BALENO 2ND GEN", "A", ""),
    ("Baleno", "Front-door", "R", 58209009, "PANEL ASSY FRONT DOOR RH", 6776, "BALENO 3RD GEN", "A", "LH same price"),
    ("Baleno", "Back-door", "R", 57903475, "PANEL ASSY REAR DOOR RH", 7999, "BALENO 2ND GEN", "A", "LH same price"),
    ("Baleno", "Back-door", "R", 58810127, "PANEL ASSY REAR DOOR RH", 8570, "BALENO 3RD GEN", "A", ""),
    ("Baleno", "Tail-light", "L", 34745136, "LAMP UNIT RR COMB LH", 2720, "BALENO 2ND GEN", "A", "RH same price"),
    ("Baleno", "Windshield", "single", 58280149, "GLASS WINDSHIELD", 4950, "BALENO 2ND GEN", "A", ""),
    ("Baleno", "Windshield", "single", 58295140, "GLASS WINDSHIELD", 4600, "BALENO 3RD GEN", "A", "also fits FRONX"),
    ("Baleno", "Trunk", "single", 56726033, "PANEL ASSY BACK DOOR", 7120, "BALENO 2ND GEN", "A", "tailgate"),
    ("Baleno", "Trunk", "single", 58209013, "PANEL ASSY BACK DOOR", 8000, "BALENO 3RD GEN", "A", "tailgate"),
    ("Brezza", "Hood", "single", 36620675, "PANEL FRONT HOOD", 7450, "VITARA BREZZA 1ST GEN", "A", ""),
    ("Brezza", "Hood", "single", 58238144, "FRONT HOOD", 7250, "BREZZA 2ND GEN", "A",
     "7,250 is real on boodmo for BREZZA 2ND GEN; the Maruti-store URL Gemini gave for it was a 404"),
    ("Brezza", "Front-door", "R", 57597811, "PANEL ASSY FRONT DOOR R", 8260, "VITARA BREZZA 1ST GEN", "A", "LH same price"),
    ("Brezza", "Front-door", "L", 58466763, "PANEL ASSY FRONT DOOR LH", 9300, "BREZZA 2ND GEN", "A", "RH same price"),
    ("Brezza", "Back-door", "R", 57597824, "PANEL ASSY REAR DOOR R", 8750, "VITARA BREZZA 1ST GEN", "A", "LH same price"),
    ("Brezza", "Back-door", "L", 58238281, "PANEL ASSY REAR DOOR L", 8999, "BREZZA 2ND GEN", "A", "RH same price"),
    ("Brezza", "Windshield", "single", 58280146, "GLASS SET WINDSHIELD", 6070, "VITARA BREZZA 1ST GEN", "A", ""),
    ("Brezza", "Windshield", "single", 58272240, "GLASS SET WINDSHIELD", 5750, "BREZZA 2ND GEN", "A", ""),
    ("Brezza", "Trunk", "single", 38162066, "PANEL ASSY BACK DOOR", 8296, "VITARA BREZZA 1ST GEN pre-F/L", "A", "tailgate"),
    ("Brezza", "Trunk", "single", 58238282, "PANEL ASSY BACK DOOR", 9970, "BREZZA 2ND GEN", "A", "tailgate"),
    ("Nexon", "Front-door", "L", 39005995, "ASSY FRONT DOOR SHELL LH", 14741, "NEXON 1ST GEN", "A", ""),
    ("Nexon", "Front-door", "R", 58330597, "CED ASSY FRONT DOOR SHELL RH", 13648, "NEXON 2ND GEN", "A", "LH same price"),
    ("Nexon", "Windshield", "single", 37963027, "ASSY WINDSCREEN GLASS", 8085, "NEXON 1ST GEN", "A", "page fitment row 08.2017-01.2020; later 1st-gen years assumed"),
    ("Nexon", "Trunk", "single", 58244137, "KIT TAILGATE SHELL ASSY W/O WIPER", 12110, "NEXON 1ST GEN", "A", ""),
    ("Punch", "Back-door", "L", 58179835, "ASSY COMPL REAR DOOR BIW LH", 10701, "PUNCH 1ST GEN", "A", "RH 10,712"),
    ("Punch", "Trunk", "single", 58180353, "TAILGATE BIW ASSEMBLY HIGH END", 10942, "PUNCH 1ST GEN pre-F/L", "A", ""),
    ("Punch", "Trunk", "single", 58848965, "CED COATED TAILGATE ASSY Punch MCE", 16193, "PUNCH 1ST GEN F/L", "A", ""),
]

NEW += [
    # ---- last verification batch: replacements for partial / aftermarket v1 rows and remaining gaps
    ("Creta", "Front-bumper", "single", 58227160, "COVER-FR BUMPER", 2402, "CRETA 2ND GEN", "A", "full cover (v1 row was the upper part only)"),
    ("Creta", "Back-bumper", "single", 58227184, "COVER-RR BUMPER", 1496, "CRETA 2ND GEN", "A", ""),
    ("Creta", "Back-bumper", "single", 58437438, "COVER-RR BUMPER", 2508, "CRETA 2ND GEN F/L", "A", ""),
    ("Creta", "Hood", "single", 9023438, "PANEL ASSY-HOOD", 8060, "CRETA 1ST GEN", "A", ""),
    ("Creta", "Hood", "single", 58226805, "PANEL ASSY-HOOD", 8581, "CRETA 2ND GEN", "A", "also fits Alcazar"),
    ("Creta", "Front-door", "single", 58226880, "PANEL ASSY-FRONT DOOR", 10926, "CRETA 2ND GEN+F/L", "A", ""),
    ("Creta", "Tail-light", "single", 59229873, "LAMP ASSY-REAR COMB", 2081, "CRETA 1ST GEN", "A", ""),
    ("Baleno", "Front-bumper", "single", 58209015, "BUMPER FRONT", 2850, "BALENO 3RD GEN", "A", ""),
    ("Brezza", "Front-bumper", "single", 58238284, "BUMPER FRONT UPPER", 2050, "BREZZA 2ND GEN", "B",
     "two-piece bumper: upper cover priced (the painted part usually replaced); lower 2,070"),
    ("Brezza", "Front-bumper", "single", 36622704, "BUMPER FRONT UPPER", 3000, "VITARA BREZZA 1ST GEN pre-F/L", "B",
     "two-piece bumper: upper cover priced"),
    ("Punch", "Front-bumper", "single", 58180266, "FRONT BUMPER SKIN UPPER", 2601, "PUNCH 1ST GEN", "B",
     "two-piece bumper: upper skin priced; lower skin is a separate part"),
    ("Punch", "Front-door", "R", 58179834, "ASSY COMPL FRT DR BIW RH", 14481, "PUNCH 1ST GEN", "A", "LH 14,745"),
    ("Punch", "Headlight", "R", 58180011, "HEADLAMP ASSY,RH (544...0110)", 3612, "PUNCH 1ST GEN", "B",
     "RH bare lamp found in the PUNCH headlamp listing (MRP 3,612, same as LH 0109): like-for-like with the L row"),
]

# v1 rows to reject or re-tier: (model, part, price) -> (new confidence, note[, generation key for a window])
FIX = {
    ("Creta", "Windshield", "5546"): ("A_CONFIRMED", "boodmo page opened: fits CRETA 2ND GEN (and Alcazar)", "CRETA 2ND GEN+F/L"),
    ("Nexon", "Fender", "3410"): ("A_CONFIRMED", "boodmo page opened: CED FENDER ASSY, NEXON 2ND GEN", "NEXON 2ND GEN"),
    ("Nexon", "Back-door", "12680"): ("A_CONFIRMED", "boodmo page opened: ASSY REAR DOOR SHELL (CED), NEXON 2ND GEN", "NEXON 2ND GEN"),
    ("Swift", "Front-door", "4665"): ("A_CONFIRMED", "boodmo page opened: PANEL ASSY FR DOOR, SWIFT 2ND GEN", "SWIFT 2ND GEN"),
    ("Venue", "Front-door", "13166"): ("A_CONFIRMED", "boodmo page opened: PANEL ASSY-FRONT DOOR, VENUE 1ST GEN + F/L", "VENUE 1ST GEN+F/L"),
    ("Venue", "Back-door", "12072"): ("A_CONFIRMED", "boodmo page opened: PANEL ASSY-REAR DOOR, VENUE 1ST GEN", "VENUE 1ST GEN pre-F/L"),
    ("Venue", "Trunk", "8226"): ("A_CONFIRMED", "boodmo page opened: PANEL ASSY-TAIL GATE, VENUE 1ST GEN", "VENUE 1ST GEN pre-F/L"),
    ("Punch", "Tail-light", "2420"): ("A_CONFIRMED", "boodmo page opened: TAIL LAMP LED ASSY LH, PUNCH 1ST GEN", "PUNCH 1ST GEN"),
    ("Punch", "Tail-light", "2469"): ("A_CONFIRMED", "boodmo page opened: TAIL LAMP LED ASSY RH, PUNCH 1ST GEN", "PUNCH 1ST GEN"),
    ("Punch", "Windshield", "7574"): ("A_CONFIRMED", "boodmo page opened: WINDSCREEN GLASS ASSY, PUNCH 1ST GEN + F/L", "PUNCH 1ST GEN"),
    ("Creta", "Back-bumper", "1898"): ("D_SUPERSEDED", "aftermarket-shop listing; replaced by genuine MOBIS rows with fitment windows"),
    ("Creta", "Hood", "8369"): ("D_SUPERSEDED", "aftermarket-shop listing; replaced by genuine MOBIS rows with fitment windows"),
    ("Creta", "Front-door", "12979"): ("D_SUPERSEDED", "aftermarket-shop listing; replaced by genuine MOBIS row with fitment window"),
    ("Nexon", "Grille", "2820"): ("C_LISTED_UNVERIFIED", "re-check 20 Oct: no genuine item at 2,820 in the NEXON grille listing; nearest TOP GRILL;FRONT BUMPER 2,913"),
    ("Swift", "Back-door", "4650"): ("D_REJECTED_WRONG_PART",
                                    "boodmo item at 4,650 is PANEL ASSY BACK DOOR = Swift 2nd-gen TAILGATE, not a rear door (now a Trunk row)"),
    ("Venue", "Front-bumper", "3183"): ("D_REJECTED_PARTIAL_PART", "boodmo item at 3,183 is COVER-FR BUMPER UPR (upper cover only)"),
    ("Creta", "Front-bumper", "1794"): ("D_REJECTED_PARTIAL_PART",
                                       "Motrparts aftermarket listing for the FRONT UPPER bumper (URL says front-upper-bumper); "
                                       "replaced by MOBIS COVER-FR BUMPER"),
}

COLS = ["make", "model", "generation", "generation_status", "part_class", "side", "part_number", "price_inr", "gst_included",
        "source_name", "source_url", "confidence", "flag", "claude_note", "valid_from", "valid_to", "window_basis", "verified"]


def main(extra=()):
    with open(V1, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n_fix = 0
    for row in rows:
        key = (row["model"], row["part_class"], row["price_inr"])
        if key in FIX:
            conf, note, *gen = FIX[key]
            row["confidence"], row["flag"], row["verified"] = conf, note, VERIFIED
            if gen:
                row["generation"], row["generation_status"] = gen[0], "page"
                row["valid_from"], row["valid_to"] = GEN[gen[0]]
                row["window_basis"] = "boodmo compatibility table (generation)"
            n_fix += 1
    for (model, part, side, bid, title, mrp, gen, tier, note) in list(NEW) + list(extra):
        vf, vt = GEN[gen]
        rows.append({"make": MAKE[model], "model": model, "generation": gen, "generation_status": "page",
                     "part_class": part, "side": side, "part_number": f"boodmo#{bid}", "price_inr": mrp,
                     "gst_included": "yes", "source_name": "boodmo",
                     "source_url": f"https://boodmo.com/catalog/part-x-{bid}/",
                     "confidence": {"A": "A_CONFIRMED", "B": "B_PRICE_EXISTS_FITMENT_UNCONFIRMED"}[tier],
                     "flag": "", "claude_note": f"{title}; MRP incl. of all taxes" + (f"; {note}" if note else ""),
                     "valid_from": vf, "valid_to": vt, "window_basis": "boodmo compatibility table (generation)",
                     "verified": VERIFIED})
    with open(V2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"v2: {len(rows)} rows ({len(NEW) + len(extra)} new, {n_fix} of {len(FIX)} v1 corrections applied) -> {V2}")


if __name__ == "__main__":
    main()
