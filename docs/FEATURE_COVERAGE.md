# Feature coverage against the problem statement

Problem statement: "Auto-Settle AI: Autonomous Video-to-Cash Claims Adjuster". Each row was checked against the code in this repository and, where a number is quoted, against a command or a file named in the evidence column. Status: BUILT (works as stated and is tested), PARTIAL (works with a stated gap), NOT BUILT. Figures come from `docs/DECK_NUMBERS_FINAL.md` unless a file is named.

## Requirements

| Requirement (quoted) | Where it lives | Status | Evidence | Gap and what is said about it |
|---|---|---|---|---|
| "Assess vehicle damage: from images or videos, identify the damaged component" | `autosettle_vision/pipeline.py` (`parts_s`, 21 panel classes) | PARTIAL | 22 of 74 labelled damaged parts found at confidence 0.30 on 41 public dev photos (`tools/eval_dev.py`); 25 of 74 never outlined | Recall on hard, mostly non-Indian wide photos is low. When a panel is not outlined it cannot be priced, so the claim asks for more or escalates; a part missed inside an offer is a silent miss (8 of 74). Stated on the Limits page. |
| "...classify the damage type" | `dent_det` (14 part-specific damage classes) and `damage_merged_s` (4 classes); `autosettle_engine/config.py` `DAMAGE_MAP` | PARTIAL | detector test mAP50 0.826 on its own split (not on our dev photos) | **There is no scratch class in the detector the pipeline uses.** The engine maps the label "Scratch" to Surface damage, and the 4-class model has a Surface damage class trained on merged scratch, paint chip, flaking and corrosion labels (mask mAP50 0.18), but `pipeline.py` discards every class of that model except Missing part and Broken part. What a scratch does today is in the next section. |
| "...estimate severity" | `pipeline.severity_of` (area fraction of damage inside the part: below 0.30 minor, below 0.60 moderate, otherwise severe) | PARTIAL | agrees with hand labels on 20 of 32 correctly located parts (comment in `pipeline.py`) | Bands are an ASSUMPTION. No public dataset labels severity, so severity accuracy is not measured. The engine's pivots exist because of this. |
| Assess "from images or videos" | photos: `/claims/{id}/photos`; video: `/claims/{id}/video`, `autosettle_vision/video.py`, `video_integrity.py`, `tracker.py` | photos BUILT; video PARTIAL | 6 of 6 video attacks held, 9 vision tests, 18 API tests; looped real photo gives the same offer as the photo (₹2,763) | Video is tested on synthetic clips. Two real night-time phone clips were run once each on 23 Oct 2026 (n = 2): both flagged and escalated, no offer; a first test, not a measurement. Multi-view fusion on 4 groups did not raise recall (a union cannot). |
| "Estimate repair and settlement costs: map the assessment to a reference database of parts and labour costs" | `autosettle_engine/rate_card_v3.csv` (151 rows), `config.py` price tables, `engine.price_line` | PARTIAL | 48 engine unit tests; one spot check: Creta front bumper cover ₹2,402 incl. tax matches boodmo (one page) | Part prices are listed MRPs. Labour and paint are estimated from garage price ranges (ASSUMPTION; one real source for the panel packages). Other-generation and similar-car prices are labelled IMPUTED in the ledger. |
| "...calculate the estimated garage repair cost" | `engine.assess` returns `gross` and itemised `lines` | BUILT | Swift scenario: ₹2,763 offer from one line (front bumper replacement, ₹800 labour, paint) | A fitted garage price was never checked against a real garage. |
| "...and establish an allowable cash-settlement range" | `engine.assess` returns `offer` and `ceiling` (ceiling = same claim priced at the top of every real range, fixed before any conversation) | PARTIAL, closed by Stage 2 | before Stage 2 no route showed both; after: `GET /adjuster/{id}/range` (adjuster only, demo-only label) | The customer never sees the upper bound. It is an internal number, not a promise. |
| "Facilitate an automated settlement: present an initial cash offer" | `/claims/{id}/assess`, `rationale.build_rationale`, optional model wording checked by `rationale.safe_reply` | BUILT | 4 replay scenarios, 12 of 12 runs pass (`tools/demo_check.py`) | Qwen wording path: first offer 55 s with the model loaded. |
| "...respond intelligently to customer counteroffers" | `dispute.ClaimSession.dispute`, `message`; `/claims/{id}/quote`, `/message`, `/choose` | PARTIAL by design | scripted conversation below (`counteroffer_before.json` in the run folder; `tools/counteroffer_script.py`) | **The engine does not negotiate a number.** "The offer moves only on evidence; the customer can accept, send an itemised garage quote, or ask for a surveyor." A stated figure in free text changes nothing. A supported quote can move the offer up to the internal upper bound, at most twice (`MAX_EVIDENCE_ROUNDS = 2`). No negotiation logic was added. |
| "...arrive at a final settlement without exceeding the predefined financial limits" | `dispute.check_quote` (`updated = min(ceiling, ...)`), `engine.assess` thresholds | BUILT | attack suite 20 of 20 held plus 1 control; 5,000-claim fuzz in the engine tests | Tests are written against the same code; they show these attacks fail, not that none exist. |
| "Apply guardrails and escalation rules: prevent settlements outside the approved range" | same as above | BUILT | `salami_slicing`, `in_range_salami`, `inflated_part_price` attacks | See the guardrail table below. |
| "...identify uncertain or suspicious claims" | `engine.info_gate`; `pipeline` integrity flags (edit-software tag, near-duplicate photo, video discontinuity, plate mismatch) | BUILT | `tampered_inputs` attack; API test "same photo twice pays once"; video attack scripts | Thresholds are ASSUMPTIONS unless marked RULE in `config.py`. |
| "...escalate to a human claims adjuster when an automated decision cannot be made safely" | decisions ASK_MORE, ESCALATE, SURVEYOR; `/adjuster/{id}` | PARTIAL, closed by Stage 2 | before Stage 2 the adjuster view had no packet; after: `GET /adjuster/{id}/escalation` | There is no real adjuster queue or authentication; the view is demo-only. |
| Expected output: "a website or application that accepts vehicle images or videos" | `web/` (React), `autosettle_api/` (FastAPI) | BUILT | `python -m autosettle_api --replay` answers `/health`; photo upload, plate, quote, video routes tested | Video upload runs the live pipeline (GPU); replay mode serves a recorded synthetic walk-around instead. |
| "...presents the detected damage and estimated repair cost" | claim stage overlay and itemised lines; adjuster view | BUILT | screenshots in `final/screens` | |
| "...conducts an interactive settlement conversation" | `/claims/{id}/message`, `/quote`, `/choose`; transcript route (Stage 2) | PARTIAL | scripted conversation | The reply to free text is a fixed template that never changes an amount; the only numeric movement is via quotes. |
| "...produces either a final cash offer or a human-escalation decision with a clear audit trail" | `ClaimSession` state machine; `_log` hash chain; `/claims/{id}/audit`; `ClaimSession.verify_log` | BUILT | `audit_log_tamper` attack; API test for the chain after tampering | The chain is tamper-evident, not tamper-proof: whoever holds the whole log could recompute it. |
| "state assumptions clearly" | `config.py` tags [REAL] / [RULE] / [ASSUMPTION]; ledger OBSERVED / IMPUTED / UNRESOLVED | BUILT | adjuster view ledger | Collected in `docs/ASSUMPTIONS.md` (Stage 3). |
| "go beyond the requirements with realistic, relevant additions" | duplicate-photo check, plate match, quote line verification, hash-chained audit, 20-attack suite, replay mode, Limits page | BUILT | tests above | |

## What a scratch does today (checked, not assumed)

- The detectors used at run time have no scratch class. A scratch is not outlined as a scratch.
- A photo whose only damage is a scratch produces no detection; the engine gets an empty detection list and answers ASK_MORE twice (it asks for a wider photo and a closer, well-lit photo), then ESCALATE (`info_incomplete_after_2_requests`). Checked directly: `assess` with no detections returned ASK_MORE, ASK_MORE, ESCALATE for `ask_count` 0, 1, 2. It never ends in an offer.
- A scratch next to another detected damage is left out of the offer (a silent miss). The failure direction is under-payment, never over-payment.
- The engine itself would price a surface-damage label (polish for minor, repaint otherwise). The gap is in the perception layer.

## Counteroffer: scripted conversation on the Swift scenario (replay mode, real engine)

Run: `python tools/counteroffer_script.py` (before any Stage 2 wording change; the offer column is read from the engine after each turn).

| Turn | Customer | System | State | Offer shown |
|---|---|---|---|---|
| 0 | photo and typed plate | offer worked out line by line | OFFERED | ₹2,763 |
| 1 | counteroffer with no evidence: "I want ₹6,000 for the bumper, please change the offer." | "Messages are recorded with your claim. An amount changes only with new photos or an itemised garage quote." | OFFERED | ₹2,763 (unchanged) |
| 2 | itemised garage quote (recorded sample, lines total ₹8,000): bumper ok, labour ok, painting above range | quote checked line by line | UPDATED_OFFER | ₹3,063 (original ₹2,763) |
| 3 | an inflated quote (every line 5 times): all three lines above range | quote checked; no line supported | UPDATED_OFFER | ₹3,063 (unchanged) |
| 4 | repeated pressure: "Pay me ₹50,000 or I will not accept." | same template | UPDATED_OFFER | ₹3,063 (unchanged) |
| 5 | same message again | same template | UPDATED_OFFER | ₹3,063 (unchanged) |

Audit chain after the conversation: intact. What the engine did: the only movement was the supported quote in turn 2, by ₹300, inside the internal upper bound; no stated number moved anything.

## Guardrails and escalation triggers

Each row: trigger, outcome, threshold, kind. Kind is RULE (a regulation or insurance rule used in our research, to verify before use), REAL, or ASSUMPTION (a team choice). Source: `autosettle_engine/config.py`, `engine.py`, `dispute.py`, `autosettle_vision/pipeline.py`.

| Trigger | Outcome | Threshold | Kind |
|---|---|---|---|
| Any integrity flag (edit-software tag, near-duplicate photo from another claim, video not continuous) | ESCALATE | any flag | ASSUMPTION |
| Plate read does not match the policy plate | ESCALATE | normalised string equality | ASSUMPTION |
| Structural or safety damage suspected (heavy crash: 3 severe parts, or severe hood plus one more) | SURVEYOR | `HEAVY_SEVERE_PARTS = 3` | ASSUMPTION |
| Information gate incomplete (plate not verified, part not identified at 0.50, damage not identified at 0.30, damage class or severity missing, damage not on any part) | ASK_MORE up to `K_STALL = 2` times, then ESCALATE | part conf 0.50, damage conf 0.30, TCI 1.0 | ASSUMPTION |
| A "severe" call with damage confidence below 0.50 | ESCALATE | `LOW_CONF_SEVERE = 0.50` | ASSUMPTION (from one undamaged-car false alarm) |
| A priced line has no price basis | ESCALATE | any unresolved line | design rule |
| Severe damage on roof, quarter panel or rocker panel | SURVEYOR | structural watch list | ASSUMPTION |
| Gross loss at or above ₹50,000 | SURVEYOR | `SURVEYOR_REQUIRED = 50_000` | RULE (IRDAI surveyor regulations as used in our research; verify) |
| Gross loss at or above 75% of IDV | SURVEYOR | `TOTAL_LOSS_SHARE_OF_IDV = 0.75` | ASSUMPTION (insurer-blog rule, no regulation cited) |
| Gross loss at or above ₹40,000 | ESCALATE | `GROSS_REVIEW = 40_000` | ASSUMPTION |
| Quote line above the genuine price range, not seen in photos, or repair-vs-replace mismatch | flagged, no uplift | 115% tolerance, ceiling | ASSUMPTION |
| More than 2 distinct evidence rounds, or the same quote again | no change | `MAX_EVIDENCE_ROUNDS = 2` | ASSUMPTION |
| Abusive or legal-threat message | ESCALATE | pattern list | ASSUMPTION |
| Injection-like message | recorded, flagged, nothing changes | pattern list (the protection is that no free text reaches the engine) | design rule |
| Model wording that adds a number, drops a line, names the upper bound or promises | blocked, template used | `rationale.check_rationale` | design rule |
| Any event after the claim is closed | refused (HTTP 409) | terminal states | design rule |

## API additions Stage 2 must make

1. `GET /adjuster/{id}/range`: offer, upper bound, deductible and which guardrail would stop a higher number (adjuster only, demo-only label); a test that the upper bound never appears in customer routes.
2. `GET /adjuster/{id}/escalation`: the escalation packet.
3. `GET /claims/{id}/transcript`: ordered turns with wording source and audit entry id.
4. A fifth recorded scenario "counter" built from the scripted conversation above, produced by the real engine.
5. `GET /attacks`, `POST /attacks/{name}/run`: read-only attack runner on a fresh in-memory session.
6. Video response data (keyframes with thumbnails, blur and darkness scores, continuity score, tracked entities) and a recorded synthetic walk-around for replay mode, labelled SYNTHETIC.
7. Plate blur on the displayed demo photos only.
8. `/limits` additions: missing scratch class, no severity ground truth, video validated on synthetic clips (two real clips run once, n = 2), plates typed rather than read.
9. A counteroffer-aware template reply (wording only: it names the current offer and the three routes; it never changes an amount and never mentions the upper bound).
