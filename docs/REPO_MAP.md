# Repository map

Design rule: the AI perceives and talks; deterministic code decides every rupee. The package names keep the `autosettle_` prefix from the project's earlier working name.

| Path | What it is | Needs GPU or weights? |
|---|---|---|
| `autosettle_engine/` | The money logic. `engine.py` (information gate, pricing, thresholds), `dispute.py` (claim state machine, garage-quote check, hash-chained audit log), `rationale.py` (the customer text and the checker that blocks any model wording that adds a number, drops a line or names the upper bound), `config.py` (every tunable number, tagged REAL, RULE or ASSUMPTION), `rate_card_v3.csv`, `exploit_suite.py` (20 attack scripts plus 1 control), `tests/` (48 tests including a 5,000-claim fuzz). No AI in this package. | no |
| `autosettle_vision/` | Perception. `pipeline.py` (three YOLO models: parts, damage detector, merged damage model; quality, edit-tag and duplicate checks; severity from area fraction), `qwen.py` (Qwen3-VL 4-bit: rewords the engine's text, reads a quote or plate photo), `video.py`, `video_integrity.py`, `video_claim.py`, `tracker.py` (the video path), `synthetic_clip.py` (the SYNTHETIC walk-around generator), `video_attacks.py`, `crops.py` and `surface_check.py` (two evaluated, not adopted, off by default), `app.py` (the older Gradio app), `tests/`. | yes, except the tests that use fakes |
| `autosettle_api/` | FastAPI backend. `app.py` (routes), `backends.py` (live pipeline or recorded replay), `scenarios.py` (five recorded scenarios), `attack_runner.py` (read-only attack console), `plate_blur.py` (display-only plate blur for the demo photos), `replay_data/` (recorded vision output, SYNTHETIC walk-arounds under `video/`), `static/` (the built web app), `static_v1/` (the earlier build, kept as a safety net: `--ui v1`), `tests/` (26 tests). | no in replay mode |
| `web/` | Source of the web app: Vite, React, TypeScript, plain CSS, bundled Inter. `npm install --ignore-scripts && npm run build` writes `autosettle_api/static/`. The built output is committed so the demo needs no npm. | no |
| `tools/` | `eval_dev.py` (the one command every dev-photo number comes from), `smoke.py` (demo-machine check), `demo_check.py`, `counteroffer_script.py`, `record_replay*.py` (record replay data from the live pipeline), `make_limits.py` (generates `docs/LIMITS.json` from `docs/DECK_NUMBERS_FINAL.md`), `make_quote.py` (a synthetic garage-quote image for any claim), `scan_tree.py` (credentials, personal data, local paths, big files), thermal guard and evaluation helpers. | some |
| `docs/` | `SOLUTION_DESIGN.md`, `TECH_STACK.md`, `GUARDRAILS.md`, `ASSUMPTIONS.md`, `QA.md`, `FEATURE_COVERAGE.md`, `DEMO_SCRIPT.md`, `TEST_GUIDE.md`, `ARCHITECTURE.md`, `DECK_NUMBERS_FINAL.md` (every number with source, sample and caveat), `LIMITS.json`, experiment write-ups. | no |
| `run1/` | Logs, reports, caches and numbers from the frozen Run 1 state, and the synthetic quote images `run1/quotes/`. | no |
| `results_heldout.md` | The 8-photo held-out result, kept unmodified. | no |
| `test_photos/commons/` | Ground-truth labels and photo sources for the 41 dev photos. The photos themselves are not in the repository. | no |
| `scripts/`, `weights/` | Data-preparation scripts; a note on where the model weights go. No weights are distributed. | no |
| `requirements-replay.txt`, `requirements-live.txt` | Pinned installs for replay mode and for the live GPU stack. | |
| `run.ps1`, `run.sh` | `test`, `attacks`, `eval`, `api`, `smoke`. | |
| `README.md`, `LICENSE`, `LICENSE_NOTES.md`, `THIRD_PARTY_NOTICES.md`, `DEMO_RUNBOOK.md` | Start here; licence facts; notices; demo start commands. | |

## Where a claim goes
`POST /claims` -> photos or a video, a typed plate -> `autosettle_vision` (live) or `replay_data` (recorded) -> vision dictionary -> `autosettle_engine.engine.assess` -> decision OFFER, ASK_MORE, ESCALATE or SURVEYOR -> `rationale.build_rationale` (optionally reworded by Qwen and checked) -> `/claims/{id}` for the customer, `/adjuster/{id}` for the adjuster. Every event is a hash-chained entry in the claim's audit log (`/claims/{id}/audit`).
