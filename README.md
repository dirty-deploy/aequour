# Aequour

## For the mentor: run it in 5 minutes

**What this is.** Aequour settles small motor-insurance claims from photos: vision models find the damage, a deterministic engine prices every rupee, and a language model only rewords text the engine already wrote (and every reply is checked in code before the customer sees it). This page gets you to a running demo with nothing installed but Python.

**1. Download.** On GitHub choose **Code, then Download ZIP** and unzip it, or run `git clone https://github.com/dirty-deploy/aequour`.

**2. What you need.** Python 3.12 or later (tested on 3.12 and 3.14; 3.11 was not available to test). No GPU, no Node, no model files.

**3. Commands.** Open a terminal in the unzipped folder.

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-replay.txt
python -m autosettle_api
```
macOS and Linux:
```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-replay.txt
python -m autosettle_api
```
Then open the URL printed in the box. Shortcuts that do the same: `run.ps1 demo` and `./run.sh demo`. If PowerShell refuses to run scripts: `powershell -ExecutionPolicy Bypass -File run.ps1 demo`.

**4. What you should see.** The server prints a box that says `MODE REPLAY` and the URL. The page has a gold **REPLAY** badge in the top bar and a **Try a claim** section with a large chat. Replay is chosen automatically because there is no GPU or model file; the box says why.

**5. A six-step click path** (a longer one, with what each screen shows, is in `docs/MENTOR_WALKTHROUGH.md`):
1. Open **Try a claim**.
2. Pick the first recorded claim, "A protocol-compliant claim reaches an offer". Read the offer (₹2,763) and the reply, which ends with a **Next step** line.
3. Open **How this was worked out** on the offer card and click the **?** beside Depreciation to see how it was calculated.
4. Under the chat, open the **Garage quote** tab and press **Use the recorded quote**. The offer moves from ₹2,763 to ₹3,063.
5. Open the **Adjuster view** (link on the offer card): the allowable range, the evidence per line and the audit chain.
6. Open the **Guardrails** section and press **Run all** in the attack console, or run one attack.

**6. What is real and what is recorded in replay.** Real, running on your machine: the pricing engine, the dispute logic (a quote moves the offer only on evidence), the audit chain, the attack suites and the web app. Recorded: the vision output, meaning what the detection models saw in the demo photos. That is why replay cannot analyse a new photo, and the page says so.

**7. Live mode (optional, to analyse a new photo).** It needs an NVIDIA GPU with 8 GB and the three model files (`parts_s_best.pt`, `dent_det_best.pt`, `damage_merged_s_best.pt`). The model files are **not in this repository**: they are large and the vision stack is AGPL-licensed. The team shares them privately on request. Put them in `backup/` as described in `weights/README.md`, install `requirements-live.txt`, then run `python -m autosettle_api --live --fresh-seen`. You can evaluate the whole design in replay mode without them.

**8. Troubleshooting**

| You see | Cause | Fix |
|---|---|---|
| An old page, or "Four recorded claims" | Stale server or browser cache | Use the **Reload** button in the banner; or hard refresh; or `--port 8001` |
| "Port 8000 is busy" | Another server holds the port | Use `--port 8001` or stop the other process |
| "Your own photos" is greyed out | Replay mode, by design | Start live mode (needs GPU and model files) |
| "This photo was already used" | The duplicate-photo fraud check | Start with `--fresh-seen` (the demo scripts do) |
| `python` not found or too old | Python missing or older than 3.12 | Install Python 3.12 or later |

**9. Open questions for you.**
- Depreciation today follows the part's material and the car's age; age stands in for current value. Should it be linked to a market-value source, and which one?
- The rest of what we assumed is listed in [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

**Aequour** (Latin *aequus*, "fair, level") settles small motor-insurance claims from photos or a short video of the damage. Vision models find the damaged panel and the damage. A deterministic engine prices it from a sourced genuine-parts rate card, inside hard limits the AI cannot cross. A garage quote is checked line by line against the photos, and every event goes into a hash-chained audit log. The result is either an itemised cash offer or a human-escalation decision.

**Design rule: the AI perceives and talks; deterministic code decides every rupee.** The language model never sees the upper bound or the internal what-if analysis, and free text from the customer can never change an amount.

> **Status: hackathon prototype** (Confluentia 2026 x Tredence). On 41 public dev photos the vision models find 22 of 74 labelled damaged parts (hard, mostly non-Indian, wide photos; labels made by Claude by eye); on 8 unseen photos the system made 0 offers, because plate and parts checks stopped them. There is no scratch class in the damage detector. Severity bands, labour and paint prices and several thresholds are assumptions. Video is validated on synthetic clips only. Every figure is in `docs/DECK_NUMBERS_FINAL.md` with its source and caveat, and the Adjuster view's Known-limits panel is generated from it.

## More about replay mode (no GPU, no weights, no torch)
Replay mode serves vision output that was recorded earlier from the real pipeline and labels every response and the page `REPLAY`. The engine, the dispute logic, the audit chain, the attack console and the web app all run live.

```
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements-replay.txt
python -m autosettle_api --replay
```
Open <http://127.0.0.1:8000>. A longer click path is in `docs/MENTOR_WALKTHROUGH.md`, and a shorter one in `docs/TEST_GUIDE.md`. `python tools/smoke.py` (or `run.ps1 smoke`, `./run.sh smoke`) checks the whole replay path in one go and prints PASS or FAIL per step.

The demo photos are public Wikimedia Commons files and are not in this repository; without them the recorded claims show the recorded detections on a blank canvas (to fetch them into the folder the app already looks in: `python -m pip install requests`, then `python tools/fetch_commons.py test_photos/commons`; it needs internet and may be throttled). If the web app needs rebuilding: `cd web && npm install --ignore-scripts && npm run build` (the built output is committed, so npm is not needed to run it). `--ui v1` serves the earlier build.

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
Our own files are MIT (`LICENSE`). The vision modules use Ultralytics, which is AGPL-3.0; model weights are not distributed in this repository. See `LICENSE_NOTES.md`.

## Credits
Built for the Confluentia 2026 x Tredence hackathon. Photos and datasets keep their own licences (`test_photos/commons/SOURCES.csv`, `scripts/download_data.py`). The video sampler and tracker adapt ideas and code from a teammate's MIT-licensed repository (`THIRD_PARTY_NOTICES.md`).
