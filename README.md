# Aequour

**Aequour** (Latin *aequus*, "fair, level") settles small motor-insurance claims from photos or a short video of the damage. Vision models find the damaged panel and the damage. A deterministic engine prices it from a sourced genuine-parts rate card, inside hard limits the AI cannot cross. A garage quote is checked line by line against the photos, and every event goes into a hash-chained audit log. The result is either an itemised cash offer or a human-escalation decision.

**Design rule: the AI perceives and talks; deterministic code decides every rupee.** The language model never sees the upper bound or the internal what-if analysis, and free text from the customer can never change an amount.

> **Status: hackathon prototype** (Confluentia 2026 x Tredence). On 41 public dev photos the vision models find 22 of 74 labelled damaged parts (hard, mostly non-Indian, wide photos; labels made by Claude by eye); on 8 unseen photos the system made 0 offers, because plate and parts checks stopped them. There is no scratch class in the damage detector. Severity bands, labour and paint prices and several thresholds are assumptions. Video is validated on synthetic clips only. Every figure is in `docs/DECK_NUMBERS_FINAL.md` with its source and caveat, and the app's Limits page is generated from it.

## Five minutes, replay mode (no GPU, no weights, no torch)
Replay mode serves vision output that was recorded earlier from the real pipeline and labels every response and the page `REPLAY`. The engine, the dispute logic, the audit chain, the attack console and the web app all run live.

```
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements-replay.txt
python -m autosettle_api --replay
```
Open <http://127.0.0.1:8000>. A click path for someone with no documents is in `docs/TEST_GUIDE.md`. `python tools/smoke.py` (or `run.ps1 smoke`, `./run.sh smoke`) checks the whole replay path in one go and prints PASS or FAIL per step.

The demo photos are public Wikimedia Commons files and are not in this repository; without them the scenario pages draw the recorded detections on a blank canvas. If the web app needs rebuilding: `cd web && npm install --ignore-scripts && npm run build` (the built output is committed, so npm is not needed to run it). `--ui v1` serves the earlier build.

## What needs the weights and a GPU
Live photo and video analysis, the language model (Qwen3-VL-8B 4-bit, which rewords the offer text and reads quote or plate photos) and `tools/eval_dev.py --live`. Weights are **not** in this repository; they go in `backup/` (`parts_s_best.pt`, `dent_det_best.pt`, `damage_merged_s_best.pt`, see `weights/README.md`). Install with `requirements-live.txt`, then `python -m autosettle_api --no-qwen --fresh-seen` (live pipeline, template wording) or `python -m autosettle_api --fresh-seen` (with the language model; the first offer takes about a minute). It was developed on an 8 GB laptop GPU.

## Tests (each count was measured with the command shown)
```
python -m unittest discover -s autosettle_engine/tests -t .     # 48 tests (money logic, 5,000-claim fuzz)
python -m unittest discover -s autosettle_api/tests -t .        # 31 tests, no GPU (1 is skipped when the demo photo is not on the machine)
python -m unittest discover -s autosettle_vision/tests -t .     # 9 tests, needs the live stack (1 skipped unless AEQUOUR_ISHAN_VIDEOS is set)
python -m autosettle_engine.exploit_suite                       # 20 attack scripts held, plus 1 control
python -m autosettle_vision.video_attacks                       # 6 video attack scripts held, plus 1 control (synthetic clips)
python tools/smoke.py                                           # replay demo path, 14 steps, PASS or FAIL each
python tools/eval_dev.py                                        # replays the dev-photo table from the cache (22 of 74 found)
```
The engine tests, API tests and attack suite pass in a fresh virtual environment that has only `requirements-replay.txt` installed, on Python 3.12 and 3.14. "Passed" means these tests, written against the same code, pass; it does not mean no attack exists.

## Where to read
| Question | File |
|---|---|
| What is built and what is not, against the problem statement | `docs/FEATURE_COVERAGE.md` |
| Solution design, flow, decision table | `docs/SOLUTION_DESIGN.md` |
| Technology stack and versions | `docs/TECH_STACK.md` |
| Guardrails, thresholds, known limitations | `docs/GUARDRAILS.md` |
| Assumptions (OBSERVED, IMPUTED, UNRESOLVED) | `docs/ASSUMPTIONS.md` |
| Likely questions and honest answers | `docs/QA.md` |
| Every number with source | `docs/DECK_NUMBERS_FINAL.md` |
| Repository map | `docs/REPO_MAP.md` |
| Presenting and fallbacks | `docs/DEMO_SCRIPT.md`, `DEMO_RUNBOOK.md` |
| Licences | `LICENSE` (MIT, our files), `LICENSE_NOTES.md`, `THIRD_PARTY_NOTICES.md` |

## Honest limits, in short
- **Measured:** engine invariants (fuzz of 5,000 claims, attack scripts), detector scores on their own test splits, pipeline recall and precision on 41 dev photos, 0 offers on the 8-photo held-out set, quote reading on synthetic printed quotes, speed on the development laptop.
- **Assumed, not measured:** labour and paint prices, severity bands, the review and total-loss thresholds, GST treatment, simulated policy records and plates.
- **Not measured:** handwritten quotes, real Indian claim photos at scale, severity accuracy, real walk-around video, hosting cost, regulation.
- **Tried and not adopted** (written up in `docs/`): retraining the parts model, per-panel crop detection (found 22 to 34 of 74 but more false alarms), the teammate's surface heuristic.

## Licence
Our own files are MIT (`LICENSE`). The vision modules use Ultralytics, which is AGPL-3.0; no model weights are distributed. See `LICENSE_NOTES.md`.

## Credits
Built for the Confluentia 2026 x Tredence hackathon. Photos and datasets keep their own licences (`test_photos/commons/SOURCES.csv`, `scripts/download_data.py`). The video sampler and tracker adapt ideas and code from a teammate's MIT-licensed repository (`THIRD_PARTY_NOTICES.md`).
