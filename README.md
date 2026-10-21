# Aequour

**Aequour** (from Latin *aequus*, "fair, level") settles small motor-insurance claims from photos of the damage. Vision models identify the part and the damage. A deterministic engine prices it from a sourced genuine-parts rate card, inside hard limits the AI cannot cross. A garage quote is checked line by line against the evidence, and every event goes into a hash-chained audit log.

> **Status:** hackathon prototype (Confluentia 2026 x Tredence). On 8 unseen real-world photos it made 0 offers, because plate and parts checks stopped them; recall on damaged parts was about 30% on the dev photos; labour and paint prices are estimates. See `docs\` and `run1\DECK_NUMBERS.md` for measured numbers and limits.

Package names keep the `autosettle_` prefix from the project's earlier working name.

## Design rule
The AI perceives and talks; deterministic code decides every rupee. The language model never receives the ceiling, the ceiling lines or the internal pivots, and the chat path never changes a number.

## Layout
- `autosettle_engine/`: the money logic (`engine.py`, `rationale.py`, `dispute.py`, `config.py`), rate cards, tests and the attack suite (`exploit_suite.py`). Unchanged by the API, UI and video work.
- `autosettle_vision/`: YOLO pipeline, Qwen layer, the video path (`video.py`, `video_integrity.py`, `video_claim.py`, `tracker.py`), two evaluated-and-not-adopted experiments (`crops.py`, `surface_check.py`), the Gradio app (kept as a fallback) and evals.
- `autosettle_api/`: FastAPI backend (`python -m autosettle_api`), recorded REPLAY data for the demo scenarios, API tests and the built web app (`static/`, committed so the demo needs no npm).
- `web/`: source of the web app (Vite, React, TypeScript, plain CSS). `npm install --ignore-scripts && npm run build` writes `autosettle_api/static/`.
- `tools/`: `eval_dev.py` (the one command every dev-photo number comes from), `demo_check.py`, `make_limits.py`, rate-card builders, the thermal guard.
- `docs/`: `ARCHITECTURE.md`, `DECK_NUMBERS_FINAL.md` (every number with source, sample, caveat), `LIMITS.json`, experiment write-ups. `DEMO_RUNBOOK.md`: start commands, timings, what to do if a model fails.
- `run1/`: logs, reports, caches and numbers from the frozen Run 1 state. `results_heldout.md`: the 8-photo held-out result, kept unmodified.
- `THIRD_PARTY_NOTICES.md`: code adapted from a teammate's repository, licences of dependencies.

## Run
Python 3.10+ with the packages the vision README lists; model weights are not in this repository (see `weights/README.md`); put them in `backup/` (`parts_s_best.pt`, `dent_det_best.pt`, `damage_merged_s_best.pt`).

```
python -m autosettle_api --replay                 # demo without a GPU: recorded vision output, labelled REPLAY, http://127.0.0.1:8000
python -m autosettle_api --no-qwen --fresh-seen   # live photo pipeline, template wording
python -m autosettle_api --fresh-seen             # live, with the language model (first offer takes about a minute)
python -m autosettle_vision.app                   # the older Gradio app, http://127.0.0.1:7860
```

## Tests (each count was measured with the command shown)
```
python -m unittest discover -s autosettle_engine/tests -t .     # 48 tests
python -m unittest discover -s autosettle_api/tests -t .        # 18 tests (no GPU)
python -m unittest discover -s autosettle_vision/tests -t .     # 9 tests (1 skipped unless AEQUOUR_ISHAN_VIDEOS is set)
python -m autosettle_engine.exploit_suite                       # 20 attack scripts + 1 control
python -m autosettle_vision.video_attacks                       # 6 video attack scripts + 1 control (synthetic clips)
python tools/eval_dev.py                                        # replays the 41-dev-photo table from the cache (22 of 74 found)
```
`tools/eval_dev.py --live` needs the weights and the dev photos (`AEQUOUR_DEV_PHOTOS`); `--variant crops|fusion` counts against a 3-evaluation limit.

## Video
`POST /claims/{id}/video` (on by default; `--video off` disables it). Keyframes (at most 12, at most 60 s) go through the photo pipeline; a cut or a different car escalates; damage seen in one keyframe only becomes a request for a clearer view. Implemented and tested on synthetic cases; not validated on real walk-around video.

## Honest limits
- Measured: engine invariants (fuzz, 5,000 claims), attack scripts, detector scores on its own test split, pipeline recall and precision on 41 dev photos, 0 offers on the 8-photo held-out set, quote reading on synthetic images.
- Assumed, not measured: labour and paint prices, severity bands, review and total-loss thresholds, GST treatment, base-variant prices for higher trims, simulated policy records and plates.
- Not measured: handwritten quotes, real Indian claim photos at scale, severity accuracy, real walk-around video.
- Tried and not adopted (written up in `docs/`): retraining the parts model (Run 3), per-panel crop detection (found 22 to 34 of 74 but more false alarms), the teammate's surface heuristic.
- Dev-photo labels in `test_photos/commons/ground_truth.csv` were made by Claude by eye, not by a person.

## Credits
Built for the Confluentia 2026 x Tredence hackathon. Photos and datasets keep their own licences (see `test_photos/commons/SOURCES.csv` and `scripts/download_data.py`).
