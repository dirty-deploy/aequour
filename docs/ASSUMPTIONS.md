# Assumptions

The problem statement asks for assumptions to be stated clearly. Tags follow the adjuster view's assumption ledger (`engine.build_ledger`):

- **OBSERVED**: taken from evidence (the photos, the policy record) or from a rule or source we opened, named in the last column.
- **IMPUTED**: a team choice or a proxy where no source was found. Shown as "assumed" in the ledger.
- **UNRESOLVED**: something the system cannot know or decide; it escalates or says so.

Values live in `autosettle_engine/config.py` (each tagged REAL, RULE or ASSUMPTION in the code) and `autosettle_vision/pipeline.py`. Change a value there and the engine, the rationale and the tests follow. A RULE is an insurance rule or regulation as used in our research; it was not checked with an insurer or a lawyer and should be verified before anyone relies on it.

## Prices and money

| # | Assumption | Value | Tag | Source or justification |
|---|---|---|---|---|
| 1 | Panel "dent repair + paint" package ranges | e.g. front bumper ₹3,500 to ₹7,500 (hatch) | OBSERVED (one source) | Ride N Repair, 5 Apr 2026, independent garage, Delhi NCR. One garage's price list, not a market survey |
| 2 | Panels the source does not give are proxied | back door = front door; quarter panel = front door x 1.3; rocker panel = front door x 0.8; SUV fender = hatch fender x 1.25 | IMPUTED | no source; shown as "panel size proxied" in the ledger |
| 3 | Position inside the price range by severity | minor 0.0, moderate 0.5, severe 1.0 | IMPUTED | team choice |
| 4 | Share of a package that is paint | 60% | IMPUTED | team choice |
| 5 | Fitting labour for a replaced part | ₹800 flat; hood and trunk ₹1,000; doors ₹1,200; glass ₹1,500; the top of the labour range is 1.5 times | IMPUTED | to be calibrated with real garage quotes |
| 6 | Polish and touch-up for minor surface damage | ₹1,150 | IMPUTED | midpoint of ₹500 to ₹1,800 (a garage listing and an aggregator price) |
| 7 | Genuine part prices | rate card v3, 151 rows; median price of the matching rows | OBSERVED for tiers A, B and C; IMPUTED for other-generation and similar-car prices (tier F) | listed MRPs with a part-page URL; rows from aftermarket or partial-part listings are rejected (tier D) and never price a claim. One spot check: Creta front bumper cover ₹2,402 incl. tax matches boodmo (one page) |
| 8 | GST | prices treated as tax-inclusive | IMPUTED | open question; labelled in every ledger |
| 9 | Paint material | 25% of the paint bill, depreciated 50% | OBSERVED (RULE) | insurance rule as used in our research; verify |
| 10 | Part depreciation | plastic and rubber parts 50%; glass 0%; metal by age (0% under 6 months up to 50% over 10 years) | OBSERVED (RULE) | IMT-style depreciation as used in our research; verify |
| 11 | Compulsory deductible | ₹1,000 up to 1,500 cc, ₹2,000 above | OBSERVED (RULE) | as used in our research; verify |
| 12 | Repair versus replace | glass, lamps, mirror and grille are replaced; panels are repaired unless severe; broken or missing parts are replaced; the cheaper action wins for a dent | IMPUTED | team rule; the lesser-of rule also means calling damage less severe can never raise the price |
| 13 | Car size class | hatch or SUV by model name | IMPUTED | `config.SEGMENT` |
| 14 | Loss date | 20 Oct 2026 (a default for the demo) | IMPUTED | only the car's age depends on it |
| 15 | Policy records, plates and insured values | simulated (`autosettle_vision/policies.json`) | IMPUTED | no insurer lookup exists; the plate on the policy is simulated |

## Escalation thresholds

| # | Assumption | Value | Tag | Source or justification |
|---|---|---|---|---|
| 16 | Surveyor required | gross loss at or above ₹50,000 | OBSERVED (RULE) | IRDAI surveyor regulations as used in our research; verify |
| 17 | Human review | gross loss at or above ₹40,000 | IMPUTED | team's own choice |
| 18 | Possible total loss | gross loss at or above 75% of the insured value | IMPUTED | an insurer-blog rule, no regulation cited |
| 19 | Information gate | part confidence 0.50, damage confidence 0.30, at most 2 requests for more | IMPUTED | team choice |
| 20 | Low-confidence severe | below 0.50 goes to a human | IMPUTED | derived from one false alarm on an undamaged car (held-out run) |
| 21 | Quote tolerance and rounds | a part price up to 115% of ours is "ok"; at most 2 quotes move the offer | IMPUTED | team choice |

## Perception

| # | Assumption | Value | Tag | Source or justification |
|---|---|---|---|---|
| 22 | Severity from area | damage share of the part: below 0.30 minor, below 0.60 moderate, else severe | IMPUTED | agrees with hand labels on 20 of 32 correctly located parts; the labels are Claude's; no public dataset labels severity |
| 23 | Detector settings | confidence 0.25 (parts and damage), 0.50 for the merged model, image size 960, overlap rules 0.30 and 0.10 | IMPUTED | chosen during development; the 41 dev photos were also used for design choices |
| 24 | Photo quality floors | sharpness below 60 (variance of the Laplacian) or brightness below 40 | IMPUTED | team choice |
| 25 | Heavy crash | 3 severe parts, or a severe hood plus one more | IMPUTED | team choice |
| 26 | Video limits | at most 60 s, 12 keyframes, 1,280 px; continuity needs 15 geometric inliers between neighbouring frames | IMPUTED | validated on synthetic clips only |
| 27 | A typed plate counts as read | labelled "typed" in the adjuster view | IMPUTED | weaker than a plate photo |
| 28 | Dev-photo labels | made by Claude by eye, not by a person | IMPUTED | all recall figures depend on them |
| 29 | Demo scenarios | recorded pipeline output on public Wikimedia Commons photos, replayed through the live engine | OBSERVED | shown as REPLAY |

## Things the system cannot know (UNRESOLVED)

| # | What | What the system does |
|---|---|---|
| 30 | Whether the photographed car is the insured car | checks only the plate, which is typed in the demo |
| 31 | Whether the damage is new or old | prices what the photo shows |
| 32 | Hidden or structural damage | structural or heavy damage goes to a surveyor; otherwise it is not priced |
| 33 | Cashless versus reimbursement, salvage, tax treatment of labour | not modelled |
| 34 | Regulation and data-protection compliance | not assessed |
| 35 | The price a garage would actually charge | the garage quote is the evidence; a fitted price was never checked against a real garage |
