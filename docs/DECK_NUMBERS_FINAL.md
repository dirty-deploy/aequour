# Numbers the deck may quote (final run, 21 Oct 2026)

**Test counts last run: 23 Oct 2026.** Engine 61, API 80 (1 skipped), vision 20 (1 skipped); attacks 20 of 20 plus 1 control; video attacks 6 of 6 plus 1 control; smoke 14 of 14; `tools/eval_dev.py` 22 of 74 parts. Nothing else on this page was re-run.

Same conventions as `run1/DECK_NUMBERS.md`: every number was measured on the team laptop (RTX 5050 mobile 8 GB, Ryzen 9 8940HX). "Dev photos" = 41 Wikimedia Commons photos labelled by Claude by eye, already used for design choices; they are evaluation only and nothing was trained on them. "Held-out" = 8 photos run once in Run 1 and never touched since. The first column is an id the app's "Known limits" panel and `GET /limits` are generated from (`tools/make_limits.py`).

| id | Number | Value | Source | Sample | Date | Caveat |
|---|---|---|---|---|---|---|
| recall | Damaged parts found | 22 of 74 | `tools/eval_dev.py` (reproduces the Run 2 table) | labelled damaged parts on 41 public photos, mostly non-Indian cars and wide shots | 21 Oct | labels by Claude by eye; the photos were also used for design choices |
| recall_more | Found at lower confidence | 31 of 74 at 0.15, 33 at 0.05 | `tools/eval_dev.py` | the same 41 photos | 21 Oct | below the engine's 0.30 floor these finds only block claims |
| never_outlined | Parts never outlined | 25 of 74 | `tools/eval_dev.py` | the same 41 photos | 21 Oct | retraining on 4,937 more images (Run 3) and running at other image sizes moved found parts only from 22 to at most 25 |
| silent_misses | Silent misses inside an offer | 8 of 74 | `tools/eval_dev.py` | the same 41 photos | 21 Oct | a labelled damaged part missed in a claim that still ended in an OFFER: the offer under-pays by it |
| offers | Offers on the dev photos | 7 of 41 | `tools/eval_dev.py` | 41 photos | 21 Oct | none of the 6 on damaged cars found every labelled damaged part; 1 was on a car with no labelled damage; 7 claims is an anecdote |
| heldout | Unseen photos | 0 offers | `run1/DECK_NUMBERS.md` | 8 photos, 9 runs (one car was run twice), never re-run or tuned to | 21 Oct | of the 9 runs 5 asked for more, 3 went to a human, 1 to a surveyor; 3 of the 3 human routes were plate mismatches against simulated policies |
| engine | Money logic | 20 of 20 attacks held | `python -m unittest discover -s autosettle_engine/tests -t .`, `python -m autosettle_engine.exploit_suite` | scripted attacks on the claim flow plus 1 control; 61 unit tests including a 5,000-claim fuzz (last run 23 Oct) | 21 Oct | shows these attacks fail, not that none exist; tests written against the same code |
| api | HTTP invariants | 80 API tests (last run 23 Oct) | `python -m unittest discover -s autosettle_api/tests -t .` | injection, ceiling never returned, same photo pays once, oversize and non-image rejected, close refusals, audit chain tamper, replay labelled, video routes, transcript, adjuster range and escalation packet, attack runner sandbox, recorded synthetic walk-around, plate blur, counteroffer wording | 22 Oct | no GPU in these tests; vision is replayed or faked, the engine runs for real |
| video_tests | Video path | 6 of 6 attacks held | `python -m autosettle_vision.video_attacks`, `autosettle_vision/tests` | plus 1 control and 20 vision tests (last run 23 Oct), on synthetic clips (generated textures, 2 clips from the teammate); two real night-time phone clips run once each on 23 Oct (n = 2) | 21 Oct | implemented and tested on synthetic cases; two real night-time phone clips run once each (n = 2): both flagged not continuous and escalated, no offer; a first test, not a measurement, not validated on real walk-around video |
| video_speed | Video processing time | 3.9 s for a 30-frame looped video of one real photo; about 9 s for each of the teammate's two synthetic clips | `tools/video_eval.py` | 3 clips | 21 Oct | warm models, GPU; peak torch allocation 0.25 to 0.29 GB |
| video_same | Looped-video offer | the same offer as the single photo (₹2,763) | `tools/video_eval.py`, `autosettle_vision/video_attacks.py` | 1 photo | 21 Oct | a loop of one photo says nothing about real footage |
| fusion | Multi-view fusion (4 groups of the same car or scene) | parts found unchanged: 2 of 11 labelled parts alone and fused | `tools/eval_dev.py --live --variant fusion` | 4 groups, 9 photos | 21 Oct | fusion keeps every detection (a union), so it cannot raise recall; 4 groups is anecdote |
| crops | Per-panel crop detection | found 22 to 34; not adopted | `tools/eval_dev.py --live --variant crops`, `docs/CROPS_EXPERIMENT.md` | none of the 22 lost and silent misses 8 to 0, but photos with a false-alarm part 1 to 3 of 6 and OFFER claims 7 to 2 (41 photos) | 21 Oct | failed the pre-set false-alarm rule (+33 percentage points); not adopted, off by default |
| surface | Edge-gradient surface check | flags 6 of 32 true candidates (19%) and 1 of 6 false alarms (17%) | `tools/surface_eval.py`, `docs/SURFACE_CHECK.md` | 52 detector candidates | 21 Oct | flags more true damage than false alarms; not wired in |
| latency | Speed on the development laptop | 3.7 s first live assessment (models load), 0.35 s warm; 55 s for the first offer with the language model | `final/FINAL_REPORT.md` (timings run on 21 Oct) | one laptop (RTX 5050 laptop GPU, 8 GB), one demo claim | 21 Oct | the language-model run used 7,788 MiB of GPU memory (above the 7 GB guide) and was not under the thermal guard; cost per claim and hosting were not measured |
| scratch | Scratches | not detected as a class | `autosettle_vision/pipeline.py`, `docs/FEATURE_COVERAGE.md` | the damage detectors used at run time have no scratch class | 22 Oct | a scratch-only photo gets ASK_MORE twice, then ESCALATE; a scratch beside other damage is left out of the offer (under-payment, never over-payment) |
| severity | Severity | not measured | `autosettle_vision/pipeline.py` | bands from the share of the part covered by damage (an assumption); they agree with hand labels on 20 of 32 correctly located parts | 22 Oct | no public dataset labels severity; the labels are Claude's, by eye |
| plates | Number plates | typed, not read | `autosettle_api/app.py` | the claim takes the plate as typed text; reading a plate photo needs the language model | 22 Oct | plate reading was not measured on real plates; a typed plate is weaker evidence than a plate photo |
| prices | Prices | labour and paint estimated | `run1/DECK_NUMBERS.md` | part prices are listed MRPs (151 rate-card rows) | 20-21 Oct | other-generation and similar-car prices are IMPUTED; Creta front bumper cover ₹2,402 incl. tax matches boodmo (Run 3 spot check, one page) |
| quotes | Garage quotes read by the model | 45 of 53 lines exact, 15 of 15 grand totals | Run 1 and Run 3 reports | 15 synthetic printed quotes | 21 Oct | synthetic printed quotes only; handwritten quotes not measured |
| dev_evals | Dev evaluations of new variants used | 2 of 3 | `final/DEV_EVAL_COUNT.txt` | fusion, crops | 21 Oct | baselines do not count |

## Teammate's work
Implemented, tested on synthetic cases, not validated on real video. His tracker, sampler and heuristics were audited (`final/ISHAN_AUDIT.md`) and the fixed versions live on the fork branch `aequour-video-upgrade`.

## Do not quote
- **58 of 74** against **27 of 77** parts found: his own verification report calls 58 of 74 inflated; 27 of 77 was reported to us and is not in any markdown file of his repository. Our measured figure is 22 of 74.
- **"VGGT"**: the module is an edge-gradient heuristic, not VGGT.
- **"254 Indian accident photos"**: an unlabelled web-scraped set evaluated by the same pipeline; not an accuracy figure.
- **79.2% CarDD**: a same-source test split of a different detector (Roboflow 14-class), misattributed to CarDD. CarDD is excluded from our training and its licence needs the authors' form.
- Anything about recall from video, "100% deduplication", or real walk-around footage.

## Not measured
Accuracy on real Indian claim photos at scale; severity accuracy; handwritten garage quotes and real invoices; real walk-around video; the fitted price at a garage.
