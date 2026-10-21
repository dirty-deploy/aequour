# Numbers the deck may quote

Every number here was measured on the team laptop (RTX 5050 mobile 8 GB, Ryzen 9 8940HX). "Dev photos" = 41 Wikimedia
Commons photos, labelled by Claude by eye; they have now been used for design choices. "Held-out" = the 8 photos in
`test_photos/heldout`, run once on 21 Oct and never re-run or tuned to.

| Number | Value | Source file | Sample | Date | Caveat |
|---|---|---|---|---|---|
| Rate card rows | 151 (A 117, B 9, C 3, D 22) | `autosettle_engine/rate_card_v3.csv`, `run1/ratecard_v3_report.md` | 151 rows | 21 Oct | D rows are kept for audit and never price a claim |
| Rate-card coverage, 2023 registration | 92 of 104 model × part cells direct (70 generation-matched, 22 other generation); 12 similar-car fallback; 0 none | `run1/ratecard_v3_report.md` (`tools/ratecard_coverage.py`) | 8 models × 13 parts | 21 Oct | "Other generation" and "fallback" prices are IMPUTED; base-variant prices understate higher trims |
| Part prices | MRP incl. GST, read on boodmo / Maruti Suzuki part pages | rate_card_v3.csv `source_url` | every A row | 20–21 Oct | labour and paint are still estimates, not real garage quotes |
| Unit tests | 39 pass | `autosettle_engine/tests` | 39 tests incl. a 5,000-claim seeded fuzz | 21 Oct | written by Claude against its own code |
| Fuzz | 5,000 random claims: offer always between 0 and the ceiling; more severe never cheaper; duplicates never pay twice; ceiling never in customer text | `tests/test_fuzz.py` | 5,000 claims (735 offers) | 21 Oct | random inputs, not real claims |
| Attack scripts | 20 of 20 held (+1 control) | `python -m autosettle_engine.exploit_suite` | 20 scripts | 21 Oct | shows these attacks fail, not that none exist |
| Damage detector, own test split | mAP50 0.826, mAP50-95 0.592, P 0.851, R 0.752 | `runs/detect/dent_test` | 698 images, 1,057 boxes | 20 Oct | same source as training (Roboflow close-ups) |
| Full pipeline, dev photos | 22 of 74 damaged parts found (recall 0.30), precision 0.56 | `runs/photo_eval.json` | 41 photos, 74 labelled parts | 20 Oct | labels by eye; mostly foreign cars and wide shots |
| Held-out photos | 8 photos, 9 runs, **0 offers**: 5 ask for more, 3 human, 1 surveyor; one undamaged car got 2 false dents (severe hood 0.339, moderate fender 0.395) | `results_heldout.md` | 8 photos (Creta twice) | 21 Oct | 3 of the 3 "human" runs were plate mismatches with simulated policies; only 1 of 5 heavy crashes went to a surveyor |
| Low-confidence-severe rule (Task 3) | dev photos: offers 9 → 7; removed 2 correct offers, stopped 0 wrong ones; 12 of 27 severe calls were < 0.5, of which 6 on a damaged part and 3 right part + severity | `run1/lowconf_rule_report.md` | 41 dev photos | 21 Oct | dev set now used for this choice; the rule targets the held-out false positive |
| Qwen3-VL-8B 4-bit | 6.4 GB VRAM, 24 s load, 11–24 s per reply | `runs/qwen_eval.json` | 6 claims | 20 Oct | one laptop |
| Qwen wording vs checker | 6 of 6 passed (20 Oct); 6 of 6 again in RUN1 | `runs/qwen_eval.json`, `run1/qwen_repair_report.md` | 12 drafts | 20–21 Oct | too few to show anything about the repair loop |
| Audit-repair loop (Task 4) | **not measured** | `run1/qwen_repair_report.md` | 6 of 30 claims ran | 21 Oct | two CPU thermal kills; repair never triggered on the 6 |
| Customer messages (Task 5) | 25 of 25: no number changed, ceiling never shown, all logged | `run1/conversation_report.md` | 25 messages incl. 5 Hinglish/Hindi | 21 Oct | keyword classifier caught 6/10 injections and 2/5 abuse **before** fixes fitted to this set |
| Garage quotes read by Qwen | 42 of 53 lines exact (79%); 14 of 15 grand totals; 0 of 15 offers above ceiling | `run1/conversation_report.md` | 15 synthetic images | 21 Oct | rotated 5°: 9 of 17 lines; synthetic printed quotes only |
| Garage quotes, clean (earlier) | 34 of 34 lines, 10 of 10 totals | `runs/quote_eval.json` | 10 synthetic images | 20 Oct | clean printed images |
| Thermal peaks (guarded jobs) | GPU 67 °C; CPU 92.5 °C (one-poll spike; job killed) | `run1/thermal_log.csv` | 365 polls | 21 Oct | CPU = highest AMD CCD sensor, which spikes 12–20 °C between polls |
| Handwritten quotes, severity accuracy on Indian claim photos, real garage invoices | **not measured** | – | – | – | – |
