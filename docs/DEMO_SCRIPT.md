# Demo script

Start before you walk on: `python -m autosettle_api --replay`, open <http://127.0.0.1:8000> full screen, run `python tools/smoke.py` (14 of 14 steps) once. Numbers below are from `docs/DECK_NUMBERS_FINAL.md` or measured by `tools/smoke.py`.

## The two moments where honesty matters most
1. **The offer scenario under-pays, and we know it.** The Swift photo shows heavier damage on the passenger side; the system prices the front bumper only. Our own labels say it missed two of the three damaged parts. Say it, then show the remedy: the garage-quote dispute moves the offer only on evidence.
2. **Recall on hard photos is low.** 22 of 74 labelled damaged parts found on 41 public photos (labels made by Claude by eye); 25 of 74 never outlined; 8 silent misses; 0 offers on 8 unseen photos. The system declines rather than guesses. We did not tune to improve these numbers.

## Five minutes, timed to the five milestone items

**1. Solution design (about 60 s).** Hero: "The AI looks. Code pays." Scroll the pinned scene.
- Say: "A customer sends photos. A model outlines panels and finds damage. Deterministic code prices every line and decides; the language model only rewords and can never see a limit."
- Show: the planes opening, then the receipt: front bumper replace ₹3,763, deductible ₹1,000, **offer ₹2,763**.
- Scroll to "The whole system on one page" later for the diagram if asked.

**2. Feature coverage (about 100 s).** Go to *Try a claim*.
- Click *A protocol-compliant claim*: photo with the detection, decision, itemised lines, offer ₹2,763 (plate blurred on screen).
- Quote tab, *Use the recorded quote*: ₹2,763 becomes **₹3,063**; the painting line is flagged above range. Say moment 1 here.
- Conversation tab on *A counteroffer moves the offer only on evidence*: a figure with no evidence changes nothing; the supported quote moves it once; an inflated quote and pressure do nothing. "The engine does not negotiate a number; it moves only on evidence."
- Video tab, *Recorded walk-around* (SYNTHETIC): 12 keyframes, continuity, damage tracked across frames, OFFER ₹2,763. Then *closer*: "More needed", because one panel appears in a single keyframe. Say plainly that video is validated on synthetic clips only.
- Click *A heavy crash*: SURVEYOR, no price. Then *Adjuster view*: the escalation packet.

**3. Technology stack (about 40 s).** Say: FastAPI and React; three YOLO11 models for panels and damage; Qwen3-VL-8B in 4-bit for wording and quote reading; a rate card of 151 listed part prices; the engine has no AI. Replay mode runs with no GPU. Versions and licences: `docs/TECH_STACK.md` (Ultralytics is AGPL-3.0; no weights are distributed).

**4. Guardrails and limits (about 80 s).** Scroll to *Try to break the money logic*.
- Click *Run all*: 21 of 21 held (20 attacks and an honest-quote control that moves the offer a little, as it should). Open one row to show what was attempted and that the offer and audit chain were unchanged. Say "these show these attacks fail, not that none exist".
- Table: surveyor at ₹50,000 (a rule as used in our research), human review at ₹40,000, 75% of insured value, plate match, duplicate photo, evidence rounds, the rationale checker.
- Scroll to *Where it falls short* and say moment 2. Add: no scratch class; plates typed; severity not measured; labour and paint estimated.

**5. The complete codebase (about 20 s).** Say: `autosettle_engine` (money, 48 tests, 20 attacks), `autosettle_vision`, `autosettle_api` (31 tests), `web/`, `tools/smoke.py`, `docs/REPO_MAP.md`; replay mode installs from `requirements-replay.txt` and passes the engine, API and attack tests on Python 3.12 and 3.14.

## Ninety-second version
Hero line (10 s) -> pinned scene to the receipt: "offer ₹2,763, every line itemised" (20 s) -> *Try a claim*: offer, recorded quote to ₹3,063 (25 s) -> *Run all* attacks: "21 of 21 held" (15 s) -> Adjuster view, Known limits (no longer a landing-page section): "22 of 74 found, 0 offers on unseen photos; it declines rather than guesses" (15 s) -> one sentence on the two honesty moments (5 s).

## If the live demo fails
1. Restart with `python -m autosettle_api --replay` (no GPU, no model).
2. Then `python -m autosettle_api --replay --ui v1` (the earlier web build).
3. Then play the recording: `final2/deck_assets/demo_path_1280x720.mp4` (82 s) and the screenshots in `final2/deck_assets/` with `captions.md`.
4. Say what happened. Do not pretend a recording is live.

## Answers to keep ready
`docs/QA.md` has 14 questions. The three most likely: how the offer is computed (listed part price less depreciation, plus labour, plus paint, less deductible); why code and not the model decides (a model can be argued with; the money must not be); what if the model misses damage (it does; the failure direction is under-payment, never over-payment; the quote dispute and the surveyor are the remedies).
