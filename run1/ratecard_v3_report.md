# Task 2: rate card v3

`autosettle_engine/rate_card_v3.csv` (151 rows) is built by `tools/build_rate_card_v3.py` from v2 plus the fixes for
`rate_card_v2_flags.csv`. v2 is unchanged. The engine now loads v3. Every changed price, URL and window was read on a
page opened in this run (21 Oct 2026, browser): boodmo part pages and Maruti Suzuki product pages; prices are the MRP
printed on the page, all marked "Incl. of all taxes". Machine-readable change list: `run1/ratecard_v3_changes.json`.
Coverage numbers: `tools/ratecard_coverage.py` (engine's own `RateCard.lookup`, 8 models × 13 priced parts).

## Tiers

| Tier | v2 rows | v3 rows |
|---|---|---|
| A (price + fitment on a part page) | 118 | 117 |
| B (range endpoint / sum of two pieces / price without page fitment) | 8 | 9 |
| C (unverified, or upper skin only) | 5 | 3 |
| D (rejected; never prices a claim) | 19 | 22 |
| Total | 150 | 151 |

## Coverage for a 2023 registration (15 Jun 2023), 104 model × part cells

| Category | v2 (before) | v3 (after) |
|---|---|---|
| Direct, generation-matched | 74 | 70 |
| Direct, other generation (IMPUTED) | 19 | 22 |
| **Direct total** | **93** | **92** |
| Fallback to a similar car (IMPUTED) | 11 | 12 |
| None | 0 | 0 |

v2 reproduces the stated baseline (74 matched, 93 direct). "Matched" falls by 4 because rows with no window used to match
every registration date. Now they carry the window read on the page:
- Nexon front bumper and Nexon bonnet: other generation for 2023.
- Creta tail lamp: the C row was rejected; the 1st-gen row is other generation.
- Nexon grille: the row was rejected, so it falls back to a similar car.

The direct total falls from 93 to 92 because of the Nexon grille.

Cells whose 2023 price changed:

| Cell | v2 | v3 |
|---|---|---|
| Brezza front bumper | 2,050 (upper skin only) | 4,120 (upper + lower, sum of two pieces) |
| Nexon headlight | 8,724 (selling price) | 9,783 (MRP) |
| Venue headlight | 5,648 (median of 5,859 + 5,436, both windowless) | 5,436 (F/L lamp, window covers 2023) |
| Creta tail lamp | 2,521 (unverified C) | 2,081 (1st-gen genuine, other generation) |
| Nexon front bumper / hood | 6,035 / 7,947 matched | same prices, now other generation |
| Grille fallback (Creta, i20, Swift, Baleno, Brezza, Punch, Nexon) | 4,060 | 5,299 (the rejected Nexon 2,820 row no longer pulls the median down) |
| Venue front bumper fallback | 2,563 | 3,081 |

## Rows changed (v2 CSV line numbers)

| Line | Row | Before | After | Why |
|---|---|---|---|---|
| 6 | Creta Tail-light L 2,521 | C | D | aftermarket template-price row, never opened (task rule) |
| 15 | Nexon Grille 2,820 | C | D | its own flag: no genuine item at that price (task rule) |
| 8 | Nexon Front-bumper 6,035 | A, listing URL, no window | B "range endpoint", part page, 2020-01-01 → 2023-02-28 | variant range 4,365–6,035; FRONT BUMPER SKIN page compatibility rows |
| 10 | Nexon Hood 7,947 | A, listing URL, no window | B "range endpoint", part page, 2017-08-01 → 2020-01-31 | hoods 7,947–12,201; ASSY HOOD SHELL fits NEXON 1ST GEN |
| 36 | Venue Headlight L 5,859 | A, listing URL, no window | B "range endpoint", part page, 2019-05-01 → 2022-05-31 | LH lamps 5,436–25,285; fits VENUE 1ST GEN |
| 37 | Venue Headlight R 5,436 | A, listing URL, no window | B "range endpoint", part page, 2022-06-01 → 2025-10-31 | RH lamps 5,436–24,196; fits VENUE 1ST GEN F/L |
| 9 | Nexon Back-bumper 6,162 | C, no window | C, window_basis "no window" | no genuine item at 6,162 in the NEXON rear-bumper listing (5,472–6,292) |
| 13, 14 | Nexon Headlight L / R 8,724 | C, no window | A 9,783, part pages, 2020-01-01 → 2023-07-31 | 8,724 was a discounted selling price; MRP 9,783; HEADLAMP ASSY WITH CLEAR LENS, NEXON 1ST GEN F/L |
| 29 | Brezza Headlight L 7,799 | B, no window | A, boodmo part page, 2022-07-01 → open | Maruti page shows MRP 7,799 but no fitment; same part on boodmo fits BREZZA 2ND GEN |
| 7 | Creta Windshield 5,546 | A, listing URL | A, part page | CRETA 2ND GEN + F/L (and Alcazar) |
| 11 | Nexon Fender 3,410 | A, listing URL | A, part page | CED FENDER ASSY RH, NEXON 2ND GEN |
| 12 | Nexon Back-door 12,680 | A, listing URL, side L | A, part page, side R | the page is the RH door |
| 19 | Swift Front-door 4,665 | A, listing URL | A, part page | SWIFT 2ND GEN |
| 34, 35, 38 | Venue Front-door 13,166 / Back-door 12,072 / Trunk 8,226 | A, listing URL | A, part pages | VENUE 1ST GEN (front door also F/L) |
| 43, 44 | Punch Tail-light L 2,420 / R 2,469 | A, listing URL | A, part pages | PUNCH 1ST GEN |
| 45 | Punch Windshield 7,574 | A, listing URL | A, part page | PUNCH 1ST GEN + F/L |
| 22, 23 | Baleno Headlight L / R 12,955 | A, Maruti listing URL | A, Maruti product pages | MRP 12,955 incl. taxes; "This item fits BALENO 2022–2026" (not in the flags file, but the new A-row URL test needs it) |
| new | Brezza Front-bumper 4,120 | – | B "sum of two pieces", 2022-07-01 → open | BUMPER FRONT UPPER 2,050 + BUMPER FRONT LOWER 2,070, both pages opened, both BREZZA 2ND GEN |
| 147 | Brezza Front-bumper 2,050 (upper) | B | D (superseded by the sum row) | keeps a partial and a full price out of the same median |
| 148 | Brezza Front-bumper 3,000 (1st-gen upper) | B | C "upper skin only, replace understated" | no lower skin priced for that generation |
| 149 | Punch Front-bumper 2,601 (upper) | B | C "upper skin only, replace understated" | the only priced lower skin (2,515) fits PUNCH EV, not this car |
| 139 | Creta Front-bumper 2,402 | A | A (kept) | the page title is COVER-FR BUMPER, not UPR/LWR, and it fits CRETA 2ND GEN; the UPR/LWR covers in the listing belong to other generations |

**Two-piece bumper rule:**
- If both skins were opened in this run: one replace row equal to the sum, tier B.
- If only the upper skin is known: tier C, "upper skin only, replace understated".
- Never a partial and a full price in the same lookup.

Rows marked D in v2 were not touched. No row was added that was not opened in this run.

Flag notes on base-variant prices (Venue and Nexon mirrors, Punch headlights) need no data change. They belong on the
assumptions slide: these are base-variant prices, so offers for higher trims will be low.

## Tests
- Added `test_no_tier_d_row_prices_a_claim`: a replacement claim on every model and part that has a D row never uses
  a D-only price.
- Added `test_every_a_row_has_a_part_page_url`.
- `RateCardWindowsAndRejects` now reads v3.
- Full suite: 35 tests pass. Exploit suite: 20 of 20 held.
