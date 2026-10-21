"""
Auto-Settle AI policy engine: ALL tunable numbers live here.

Every value is tagged with where it comes from:
  [REAL]       a number taken from a public source we opened (source named)
  [RULE]       an insurance rule/regulation as used in our research (verify before the demo)
  [ASSUMPTION] a team choice or a proxy; shown to the customer as "assumed"
Change a value here and the engine, the rationale and the tests all follow.
"""
from datetime import date

TODAY = date(2026, 10, 20)  # loss date used by default (tests pass their own)

# ---------------------------------------------------------------- cars
# [ASSUMPTION] size class used to pick a labour/paint package row (hatch vs SUV).
SEGMENT = {
    "Swift": "hatch", "Baleno": "hatch", "i20": "hatch",
    "Punch": "suv", "Brezza": "suv", "Venue": "suv", "Nexon": "suv", "Creta": "suv",
}

# ---------------------------------------------------------------- vision vocabulary
SEVERITIES = ("minor", "moderate", "severe")
# [ASSUMPTION] position inside the real price range that each severity maps to.
SEV_POS = {"minor": 0.0, "moderate": 0.5, "severe": 1.0}

# Damage labels from the models -> the 4 classes the engine reasons about.
DAMAGE_MAP = {
    "Missing part": "Missing part",
    "Broken part": "Broken part", "Cracked": "Broken part", "Damage": "Broken part",
    "Dent": "Dent",
    "Surface damage": "Surface damage", "Scratch": "Surface damage",
    "Paint chip": "Surface damage", "Flaking": "Surface damage", "Corrosion": "Surface damage",
}
DAMAGE_RANK = {"Missing part": 3, "Broken part": 2, "Dent": 1, "Surface damage": 0}

# ---------------------------------------------------------------- parts
PRICED_PARTS = {  # have genuine-part price rows in the rate card
    "Front-bumper", "Back-bumper", "Hood", "Fender", "Front-door", "Back-door",
    "Headlight", "Tail-light", "Windshield", "Back-windshield", "Mirror", "Grille", "Trunk",
}
REPAIR_ONLY = {"Quarter-panel", "Rocker-panel", "Roof"}          # not sold as a bolt-on part
UNPRICEABLE = {"Front-wheel", "Back-wheel", "Front-window", "Back-window", "License-plate"}
REPLACE_ONLY = {"Windshield", "Back-windshield", "Headlight", "Tail-light", "Mirror", "Grille"}
PAINTED = {"Front-bumper", "Back-bumper", "Hood", "Fender", "Front-door", "Back-door",
           "Trunk", "Roof", "Quarter-panel", "Rocker-panel"}
STRUCTURAL_WATCH = {"Roof", "Quarter-panel", "Rocker-panel"}      # [ASSUMPTION] severe here => surveyor

# ---------------------------------------------------------------- money
# [REAL] Ride N Repair, 2026-04-05, "Dent repair + panel paint", independent garage, Delhi NCR (INR min, max).
PANEL_PACKAGE_REAL = {
    "Front-bumper": {"hatch": (3500, 7500), "suv": (4500, 10000)},
    "Back-bumper":  {"hatch": (3000, 7000), "suv": (4000, 9500)},
    "Fender":       {"hatch": (2500, 5500)},
    "Front-door":   {"hatch": (2800, 6000), "suv": (3800, 8000)},
    "Hood":         {"hatch": (4500, 9000), "suv": (6500, 14000)},
    "Roof":         {"hatch": (6000, 12000), "suv": (8500, 18000)},
    "Trunk":        {"hatch": (3500, 7500), "suv": (5000, 10500)},
}
# [ASSUMPTION] rows the source does not give are proxied: (use this row, multiply by factor).
PANEL_PROXY = {
    "Back-door": ("Front-door", 1.0),
    "Quarter-panel": ("Front-door", 1.3),
    "Rocker-panel": ("Front-door", 0.8),
}
SUV_FENDER_FACTOR = 1.25  # [ASSUMPTION] SUV fender not in source: hatch row x 1.25

# [ASSUMPTION] share of a "dent repair + paint" package that is paint (rest is labour).
PAINT_SHARE = 0.6
FITTING_LABOUR_DEFAULT = 800                      # [ASSUMPTION] flat fitting labour for a replaced part
FITTING_LABOUR = {"Hood": 1000, "Front-door": 1200, "Back-door": 1200, "Trunk": 1000,
                  "Windshield": 1500, "Back-windshield": 1500}
FITTING_LABOUR_CEILING_FACTOR = 1.5   # [ASSUMPTION] top of the labour range = 1.5x the flat estimate; calibrate with real garage quotes
POLISH = 1150                                     # [REAL-ish] midpoint of Rs 500-1,800 scratch polish (Ride N Repair, GaadiMech Rs 499)

# [RULE] paint: material = 25% of the paint bill, depreciated 50%.
PAINT_MATERIAL_SHARE = 0.25
PAINT_MATERIAL_DEP = 0.50
PAINT_NET_FACTOR = 1 - PAINT_MATERIAL_SHARE * PAINT_MATERIAL_DEP   # 0.875

# [RULE] part depreciation (IMT-style): plastic/rubber 50%, glass nil, metal by age.
PLASTIC_PARTS = {"Front-bumper", "Back-bumper", "Grille", "Headlight", "Tail-light", "Mirror"}
GLASS_PARTS = {"Windshield", "Back-windshield"}


def metal_depreciation(age_years: float) -> float:
    """[RULE] metal-part depreciation by vehicle age."""
    for limit, rate in ((0.5, 0.0), (1, 0.05), (2, 0.10), (3, 0.15), (4, 0.25), (5, 0.35), (10, 0.40)):
        if age_years < limit:
            return rate
    return 0.50


def deductible(engine_cc: int) -> int:
    """[RULE] compulsory deductible."""
    return 1000 if engine_cc <= 1500 else 2000


# ---------------------------------------------------------------- escalation thresholds
GROSS_REVIEW = 40_000       # [ASSUMPTION] team's own choice: human review at/above this gross loss
SURVEYOR_REQUIRED = 50_000  # [RULE] IRDAI Surveyors & Loss Assessors Regs 2015, Reg 12(2)
TOTAL_LOSS_SHARE_OF_IDV = 0.75  # [ASSUMPTION] insurer-blog rule, no regulation cited
MIN_PART_CONF = 0.50        # [ASSUMPTION]
MIN_DAMAGE_CONF = 0.30      # [ASSUMPTION]
# [ASSUMPTION] a "severe" call below this damage confidence goes to a human before any offer. Origin: an undamaged
# grey Swift got a severe hood dent at 0.339 and a moderate fender dent at 0.395 (held-out run, 21 Oct 2026).
LOW_CONF_SEVERE = 0.50
TAU_GATE = 1.0              # information gate: all required fields must be known
K_STALL = 2                 # ask for more info / re-submit at most this many times
QUOTE_OK_TOLERANCE = 1.15   # quoted part price up to 115% of our reference counts as "ok"
MAX_EVIDENCE_ROUNDS = 2     # distinct quotes that may move the offer


# ---------------------------------------------------------------- words customers, garages and models use for each part
PART_KEYWORDS = {
    "rear windshield": "Back-windshield", "back windshield": "Back-windshield", "rear windscreen": "Back-windshield",
    "back windscreen": "Back-windshield",
    "front bumper": "Front-bumper", "rear bumper": "Back-bumper", "back bumper": "Back-bumper",
    "front door": "Front-door", "rear door": "Back-door", "back door": "Back-door",
    "tail lamp": "Tail-light", "tail light": "Tail-light", "taillight": "Tail-light",
    "head lamp": "Headlight", "headlamp": "Headlight", "headlight": "Headlight",
    "windshield": "Windshield", "windscreen": "Windshield", "bonnet": "Hood", "hood": "Hood",
    "fender": "Fender", "wing": "Fender", "mirror": "Mirror", "orvm": "Mirror", "grille": "Grille",
    "tailgate": "Trunk", "boot": "Trunk", "trunk": "Trunk", "dicky": "Trunk",
    "quarter panel": "Quarter-panel", "rocker panel": "Rocker-panel", "roof": "Roof",
    "front wheel": "Front-wheel", "rear wheel": "Back-wheel", "back wheel": "Back-wheel",
    "front window": "Front-window", "rear window": "Back-window", "back window": "Back-window",
    "license plate": "License-plate", "number plate": "License-plate",
}
