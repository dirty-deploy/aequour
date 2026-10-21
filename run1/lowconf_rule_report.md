# Task 3: low-confidence-severe rule

**Rule (engine.py, after the information gate, before any pricing):** if any detection has severity `severe` and
`damage_conf < LOW_CONF_SEVERE` (0.50, config.py, tagged ASSUMPTION), the decision is ESCALATE with reason
`low_conf_severe`. The customer sees the existing human-review message (`claim.decision_text`: "A claims specialist
will review this claim..."). Integrity, plate mismatch and the heavy-crash (structural → SURVEYOR) rule still take
precedence; an incomplete claim still gets ASK_MORE first.

Why: on the held-out run, an undamaged grey Swift got a severe hood dent at 0.339 and a moderate fender dent at 0.395.
Its plate did not match, so it went to a human; with a matching plate it would have been priced.

Tests added (test_engine.py, `LowConfidenceSevere`): the grey-Swift detections escalate with `low_conf_severe` and no
offer; a severe call at exactly 0.50 and a moderate call at 0.35 still get offers; the structural rule still wins.
Suite: 33 tests pass (incl. the 5,000-claim fuzz); exploit suite 20/20 held.

## Evaluation on the dev photos

**The 41 Wikimedia Commons dev photos are now used for a design choice.** They can no longer count as an independent
test of this rule. The held-out set (`test_photos/heldout`, `results_heldout.md`) was not touched or re-run.

Method: `tools/lowconf_eval.py`, run under the thermal guard. The app's vision pipeline (960 px, detector conf 0.25,
same as the "22 of 74 parts, 56% precision" numbers) ran once per photo; detections are cached in
`run1/cache/dev_vision.json`. The engine then assessed each cached claim twice, plate assumed verified, Swift 2023
policy: rule off (threshold 0) and rule on (0.50). Labels are the existing hand labels in
`test_photos/commons/ground_truth.csv`.

| Measure | Rule off | Rule on |
|---|---|---|
| Photos that got an offer | 9 | 7 |
| … of 16 photos labelled "should be offered" | 6 | 4 |
| … of 17 photos labelled "needs a human" | 2 | 2 |
| … of 8 photos labelled "unusable, ask for more" | 1 | 1 |

| Severe detections (all 41 photos) | Count |
|---|---|
| All severe detections | 27 |
| Severe with damage confidence < 0.50 | 12 |
| … on a part that is really damaged (label) | 6 of 12 |
| … right part and labelled severe | 3 of 12 |

Offers removed by the rule: `c16` (Honda Civic, doors; labelled "offer"; ₹14,031) and `c23` (Subaru Levorg, front
corner; labelled "offer"; ₹5,915). Both are photos where an offer was the right outcome.

## What this means
- On the dev set the rule removed 2 correct offers and stopped 0 wrong ones. The 2 heavy-crash photos that still get an
  offer (`c06` Dodge, `c18` Fabia) had their damage read as **moderate**, so this rule cannot catch them.
- It does catch the specific failure it was written for: a confident-looking price driven by an unsure "severe" call.
  Half of those calls (6 of 12) were on a part that was not damaged at all.
- With 41 photos these are counts, not rates. The rule trades some customer friction (2 extra human reviews) for not
  paying the biggest line items on an unsure call. Keep it as a stated assumption; tune it only on new photos.
