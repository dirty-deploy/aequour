# Auto-Settle AI: policy engine, rationale checker, dispute flow

Design rule: **the AI perceives and talks; this code decides every rupee.**
Pure Python 3 standard library. No installs. Run from the folder that contains `autosettle_engine/`:

```
python -m unittest discover -s autosettle_engine/tests -t .     # 23 tests
python -m autosettle_engine.exploit_suite                        # 20 attack scripts + 1 control
python -m autosettle_engine.demo                                 # one full claim, printed
```

## Files
| File | What it does |
|---|---|
| `config.py` | Every tunable number, each tagged REAL / RULE / ASSUMPTION |
| `engine.py` | Rate-card lookup, repair-vs-replace rule, payout formula, ceiling, escalation triggers, information gate, assumptions ledger, pivotal conditions |
| `rationale.py` | Deterministic customer rationale + `check_rationale()` (is a model's wording faithful?) + `safe_reply()` |
| `dispute.py` | Garage-quote line checker + claim state machine + hash-chained audit log |
| `exploit_suite.py` | Scripted attacks (injection, inflated/padded quotes, salami slicing, model lies...) |
| `rate_card_v1.csv` | genuine-part prices with confidence tier and fitment window (see below) |

## Input from the vision pipeline (ML teammate)
The Task 5 JSON, plus two fields:
```json
{"image_id": "car01.jpg",
 "plate_read": "DL 3C AB 1234",          // OCR of the plate, or null if not visible
 "integrity_flags": [],                   // e.g. ["duplicate_image", "edited_metadata", "cut_video"]
 "flags": [],                             // e.g. ["unassigned_damage", "structural_suspected"]
 "detections": [{"part_class": "Front-bumper", "part_conf": 0.91, "damage_class": "Dent",
                 "damage_conf": 0.62, "severity": "moderate"}]}
```
Policy record (from the number-plate lookup): `Policy(policy_id, plate, make, model, reg_date, engine_cc, idv)`.
`damage_class` may be any label in `config.DAMAGE_MAP` (merged-model classes, Roboflow "Damage", old 8 classes).

## How a claim runs
```python
s = ClaimSession(policy, RateCard());  res = s.submit(vision_json)
# res["decision"]: OFFER | ASK_MORE | ESCALATE | SURVEYOR
text = rationale.build_rationale(res, engine.customer_pivots(engine.pivots(policy, vision_json, rc)))
reply, used_llm, violations = rationale.safe_reply(qwen_text, res, safe_pivots)   # model wording only if it passes every check
chk = s.dispute(quote_json)      # quote_json = {"lines":[{"description","type":"part|labour|paint","qty","unit_price","total"}]}
s.choose("accept_updated" | "partner_garage" | "surveyor");  s.accept()
```
**The language model must never receive `res["ceiling"]`, `res["ceiling_lines"]` or the internal `pivots()` output.**

## What the engine guarantees (tested)
- offer <= ceiling, offer >= 0; ceiling >= offer for every model x part x damage x severity.
- Calling damage "less severe" never raises a price; more severe never lowers it.
- Duplicate or split detections of one part never pay twice; detection order does not matter.
- Free text (chat) can change no number: it is only classified (abusive -> human; injection -> logged).
- A garage quote moves the offer only on lines that (1) match damage seen in the photos and (2) are priced inside the genuine range; above-range lines get no uplift; at most 2 distinct quotes can move it; identical re-submissions are ignored.
- Every model reply is checked: unknown rupee figures, missing line items or depreciation, wrong percentages, ceiling leaks, promises, and parts not in the claim all force the fixed template.

## Honest limits (read before the demo)
1. **Labour and paint are estimates**, built from Ride N Repair's public "dent repair + panel paint" ranges with an assumed 60% paint share, flat fitting labour and proxied rows for rear door, quarter panel and rocker panel. Replace them with real garage quotes as soon as they arrive (edit `config.py`).
2. **Price coverage (rate card v1, 2026-10-20):** of 104 model x part cells, 44 have a direct listing (22 tier A, 3 tier B, 19 tier C), 44 use a similar-car fallback (marked IMPUTED), 16 have none and escalate to a human (all Back-windshield and Mirror). Tiers: A = price and fitment seen on the source page; B = price seen, fitment not shown; C = listed but not opened; D = rejected (kept in the CSV for the audit trail, ignored by the engine). Rows may carry a fitment window (`valid_from`/`valid_to`); a claim registered outside every window gets the same-model price marked `other_generation` (IMPUTED), e.g. a 2024-05+ Swift is priced from 3rd-gen rows. Part prices are the MRP printed on the page (tax-inclusive). Do not add rows from an LLM without opening the page: in round 2, 6 of Gemini's Maruti rows pointed at pages that return 404 and one fitted a different car.
3. The attack scripts are ones I wrote against my own code. They show the invariants hold for those attacks, not that no attack exists. They cannot cover staged or edited photos (that is the integrity-check work) or the vision models being wrong.
4. The language-model layer is tested with hand-written bad replies, not with real Qwen output yet.
5. The depreciation schedule, the 40k review threshold, the 75%-of-IDV total-loss rule and the structural-damage rule are tagged RULE or ASSUMPTION in `config.py`; verify the RULE ones before presenting them as regulation.
6. GST treatment of labour and paint is an open question; the ledger lists it as IMPUTED.
