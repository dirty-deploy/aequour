# Licence notes

This is a statement of facts for people reading the repository, not legal advice. Nothing here was checked with a lawyer.

## What the repository's own licence covers
`LICENSE` is the MIT licence, "The Aequour authors". It covers the files written for this project. It does not change the licence of anything listed below.

## The vision modules use Ultralytics, which is AGPL-3.0
- These modules import the `ultralytics` package: `autosettle_vision/pipeline.py`, `autosettle_vision/tracker.py` (it uses Ultralytics' BYTETracker), `autosettle_vision/crops.py`, `autosettle_vision/surface_check.py` and the tools that call the pipeline. Ultralytics is published under AGPL-3.0 (and offers a separate commercial licence).
- The engine (`autosettle_engine/`), the API (`autosettle_api/`) in replay mode, and the web app do not import `ultralytics`. Replay mode installs without it (`requirements-replay.txt`).
- **No model weights are distributed** in this repository. They are produced from public datasets and Ultralytics training code on the development laptop and are kept outside git.
- Stance taken: keep MIT for our own files and state plainly that the Ultralytics-based modules, when combined with Ultralytics, are subject to AGPL-3.0. Someone who needs to distribute the combined live system should read the AGPL-3.0 terms or Ultralytics' commercial terms and decide.
- The options, stated factually: (1) keep MIT for our files and add this notice (current choice); (2) relicense the whole repository under AGPL-3.0; (3) obtain a commercial licence from Ultralytics. Which one is right was not decided or verified here.

## Other components (terms as understood; not re-verified for redistribution)
- PyTorch, OpenCV, FastAPI, uvicorn, Pillow, NumPy, React, Vite, TypeScript: permissive licences (BSD, MIT, Apache-2.0 families). See `THIRD_PARTY_NOTICES.md`.
- Inter Variable via `@fontsource-variable/inter`: SIL Open Font Licence 1.1; the font files are bundled in the built app.
- Qwen3-VL-8B: the model licence terms should be checked before anyone redistributes the model; weights are not in this repository.
- Training datasets keep their own licences. The 14-class damage detector was trained on a Roboflow dataset whose terms were not re-verified here; CarDD is excluded from training by the team's own rule.
- Demo photos are Wikimedia Commons files kept outside the repository; each photo's licence is in `test_photos/commons/SOURCES.csv`.
- Code adapted from a teammate's MIT-licensed repository is listed in `THIRD_PARTY_NOTICES.md`.
