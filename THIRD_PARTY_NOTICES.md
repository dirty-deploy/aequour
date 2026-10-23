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

## Demo photos committed in `test_photos/commons/`
Three Wikimedia Commons photographs are included, only as demo inputs for the recorded scenarios (and the synthetic walk-around clips made from the first one). They carry their own licences, which are not the licence of this repository. The details below are copied from `test_photos/commons/SOURCES.csv`; where it says "see page", the author is named on the source page.

| File | Title | Author | Licence | Source |
|---|---|---|---|---|
| `c05_Abandoned_Suzuki_Osidge_London_2.jpg` | Abandoned Suzuki, Osidge, London (2).jpg | Philafrenzy | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Abandoned_Suzuki,_Osidge,_London_(2).jpg |
| `c53_Alto_800_accident.jpg` | Alto 800 accident.jpg | see page | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Alto_800_accident.jpg |
| `c44_Chennai_damage_1.jpg` | Chennai damage 1.jpg | see page | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Chennai_damage_1.jpg |

The app blurs the number plates in these photos for display. No other photo is included.

## Not included
Third-party UI code (ThreeUI) is in no commit. Other photos listed in `test_photos/commons/SOURCES.csv` are Wikimedia Commons files kept outside the repository (licences in that file).
