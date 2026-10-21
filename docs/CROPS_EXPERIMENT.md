# CROPS_EXPERIMENT (Stage C.2): per-panel crop detection

Variant (`autosettle_vision/crops.py`, off by default, switched on only by `tools/eval_dev.py --variant crops` or `crops.enable()`): for each segmented panel the damage detector also runs on the full-resolution crop (15% margin); boxes are mapped back and merged with the whole-frame boxes by class-wise NMS (IoU 0.5).

One paired comparison on the 41 dev photos, 74 labelled parts, labels by Claude by eye (counts as dev evaluation 2 of 3; the multi-view fusion experiment was 1). Source: `tools/eval_dev.py --live --variant crops` (`final/crops_eval.json`).

| measure | baseline | with crops |
|---|---|---|
| parts found at confidence 0.30 | 22 of 74 | 34 of 74 (+12, none of the 22 lost) |
| parts found at confidence 0.15 | 31 | 39 |
| end to end through the pipeline and engine | 22 | 35 |
| silent misses (labelled part missed inside an OFFER) | 8 | 0 |
| OFFER claims | 7 | 2 (decisions: ASK_MORE 25 to 29, SURVEYOR 7 to 9, ESCALATE 2 to 1) |
| predicted damaged parts at 0.30 / precision | 37 / 0.60 | 95 / 0.36 |
| false-alarm parts on the 6 photos with no labelled damage | 1 | 5 |
| photos with no labelled damage that get any false-alarm part | 1 of 6 (17%) | 3 of 6 (50%) |
| OFFERs on photos with no labelled damage | 1 | 0 |
| seconds per image (detector part, warm) | 0.24 end to end | 0.24 end to end (crops 0.16 added in the replay run) |

**Adoption rule (set before the run): found rises by at least 6 with at most 1 previously found part lost, silent misses do not rise, and false alarms on clean photos do not rise by more than about 10 percentage points.** Found +12 (pass), lost 0 (pass), silent misses 8 to 0 (pass, but only because OFFERs fall from 7 to 2: the extra low-confidence boxes block most claims), false alarms on clean photos +33 percentage points at photo level, 1 to 5 parts (fail).

**Not adopted.** It stays a documented, off-by-default option. The recall gain is the largest measured in any run so far (22 to 34), which is why the false-alarm cost deserves a second look on unseen photos: the next step is a comparison on photos the variant has never been run on, not a threshold tweak on these. One comparison on 74 labelled parts with 6 clean photos is small: gains and losses below the rule are noise, and the false-alarm change rests on 6 photos.
