# Demo runbook (22 Oct presentation)

## Start (from the repository folder)
```
python -m venv .venv && .venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements-replay.txt           # replay mode needs only this
python -m autosettle_api --replay                          # safest: no GPU, no model, deterministic (the page says REPLAY)
```
Open <http://127.0.0.1:8000>. Optional: `AEQUOUR_DEV_PHOTOS` (a folder with the public Commons demo photos) lets the recorded scenarios show their photo; without it the detections are drawn on a blank card. `python tools/smoke.py` (or `run.ps1 smoke`, `./run.sh smoke`) checks the whole replay path first and prints PASS or FAIL per step.

To analyse **your own photos or a video clip**, start live mode with `run.ps1 demo-live` (`./run.sh demo-live` elsewhere). It is the live pipeline with fixed-template wording, video on and an empty duplicate-photo store. `run.ps1 demo-qwen` is **replay** mode with the language model: it cannot take uploads, and the page says so. Clip advice: daylight, phone steady and upright, one clip up to 60 seconds and 60 MB, H.264 MP4 or MOV.

With the GPU stack (`requirements-live.txt`, weights in `backup/`):
```
python -m autosettle_api --no-qwen --fresh-seen            # live photo pipeline, fixed-template wording
python -m autosettle_api --fresh-seen                      # live photo pipeline with the language model
python -m autosettle_api --replay --with-qwen              # recorded vision, language-model wording
python -m autosettle_api --ui v1                           # the earlier web build, if the new one misbehaves
```
`--replay` does **not** load the language model (it used to; fixed in this run). Ctrl+C stops the server.

## Measured start-up (RTX 5050 laptop, 21 to 22 Oct)
| mode | time |
|---|---|
| `--replay`, server answering `/health` | 0.8 s |
| a recorded scenario, replay | 39 ms (counteroffer scenario with all its turns) |
| live, `--no-qwen`: first assessment loads the three detectors | 3.7 s; warm 0.35 s |
| live with the language model: the first OFFER loads Qwen3-VL (4-bit) and rewords | about 44 to 55 s; GPU memory about 7.5 to 7.8 GB of 8 GB, so close other GPU programs and do not run a benchmark at the same time |
| a quote photo read by the language model | about 8 s (two synthetic quotes, `final2/REAL_MEDIA.md`) |

## If something fails (in this order)
1. GPU or a model error ("the vision pipeline failed"): restart with `--replay`.
2. The new page misbehaves: `--ui v1` serves the earlier build.
3. The language model is slow or out of memory: restart with `--no-qwen` (offers then show the fixed-template explanation; quote photos and plate photos need the recorded quote or typed input).
4. Uploading the same photo in a second claim escalates it ("photo seen in an earlier claim"): that is the duplicate check working; restart with `--fresh-seen`.
5. The browser shows an old page: hard refresh (Ctrl+F5).
6. Everything fails: the screen recording (`final2/deck_assets/`).

## The five recorded scenarios (Try a claim, left column)
| scenario | what the judge sees | expected result |
|---|---|---|
| A protocol-compliant claim reaches an offer | Swift front-end photo (number plate blurred on screen), plate typed and matching | OFFER ₹2,763 (front bumper, replace, genuine part ₹2,250, 50% depreciation, labour ₹800, paint ₹2,100 less ₹262, deductible ₹1,000); "Use the recorded quote" moves it to ₹3,063 |
| A heavy crash goes to a surveyor | Alto crash photo, several severe panels | SURVEYOR, no price; the adjuster view shows the escalation packet |
| A prompt-injection attempt changes nothing | the offer scenario plus a hostile message | offer unchanged at ₹2,763, message flagged ("blocked") |
| A wide street photo ends in a request for more | Chennai street photo, nothing the models can price | "More needed", no offer, lists what to send |
| A counteroffer moves the offer only on evidence | recorded customer turns: a figure with no evidence, a supported quote, an inflated quote, repeated pressure | ₹2,763, then ₹3,063 after the supported quote, then no change |

Also: Video tab, "Recorded walk-around" (SYNTHETIC, OFFER ₹2,763 from 12 keyframes) and "Recorded walk-around, closer" ("More needed": one panel in a single keyframe only); the attack console (Guardrails scene, "Run all"); the "Test it" tab with one-click samples. `docs/TEST_GUIDE.md` is the click path for someone with no documents; `docs/DEMO_SCRIPT.md` is the spoken script.

Honesty notes for the presenter: in the Swift photo the heavier damage is on the passenger side while the system prices the front bumper only (our own labels say it missed two of the three damaged parts; the quote dispute is the remedy). Recall on hard photos is 22 of 74. Video is validated on synthetic clips only. Say so if asked; it is the system's real behaviour.

## Likely questions
See `docs/QA.md` (14 questions with honest answers and where the evidence is). Numbers: `docs/DECK_NUMBERS_FINAL.md`. Limits shown in the app: `docs/LIMITS.json`.
