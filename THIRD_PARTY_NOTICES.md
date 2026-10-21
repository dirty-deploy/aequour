# Third-party notices

## Adapted from Ishan6907/AutoSettleAI (MIT licence as found in that repository), copyright held by its author
The repository is a teammate's work on the same project (https://github.com/Ishan6907/AutoSettleAI). Each adapted file carries
a header saying so.

| File here | Adapted from | What changed |
|---|---|---|
| `autosettle_vision/tracker.py` | `autosettle_vision/tracker.py` | no default severity, area or "verified" flag; tracks seen once are reported, not discarded; the VGGT call and unused homography code removed |
| `autosettle_vision/video.py` | keyframe and continuity ideas in `pipeline.py` and `vggt.py` | new sampler with duration, frame, blur and darkness limits |
| `autosettle_vision/video_integrity.py` | `VGGT3DChecker.check_multiview_consistency` | renamed; used only to add an integrity flag (escalate) |
| `autosettle_vision/surface_check.py` | `VGGT3DChecker.verify_dent` | renamed: an edge-gradient surface heuristic, not VGGT; advisory only (see its docstring for the evaluation) |

Nothing from his panel-snapping, severity estimation, CarDD mapping or point-cloud code is used.

## Python and JavaScript dependencies
Ultralytics (AGPL-3.0), PyTorch, OpenCV, Pillow, NumPy, FastAPI, uvicorn, httpx, python-multipart, Gradio, Transformers and Qwen3-VL (Apache-2.0 model licence, check before redistribution),
React, Vite, TypeScript (MIT, Apache-2.0), Inter Variable via `@fontsource-variable/inter` (SIL Open Font Licence 1.1, bundled in
`autosettle_api/static/assets`). The licence questions for Ultralytics AGPL-3.0 and for the training datasets are listed in
`LICENSE_NOTES.md` and are not decided here. The vision modules that import Ultralytics (`pipeline.py`, `tracker.py`, `crops.py`, `surface_check.py`) are subject to AGPL-3.0 when combined with it; no weights are distributed.

## Not included
Third-party UI code (ThreeUI) is in no commit. Demo photos are Wikimedia Commons files kept outside the repository (licences in `test_photos/commons/SOURCES.csv`).
