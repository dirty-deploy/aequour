# Technology stack

Versions were read from the development environment on 22 Oct 2026 (`python -c`, `pip freeze`, `npm`, `nvidia-smi`), not from memory. Licences are as understood and were not re-verified for redistribution (see `LICENSE_NOTES.md`). "Used where" names the module.

## Hardware and runtime
| Item | Measured value |
|---|---|
| GPU | NVIDIA GeForce RTX 5050 Laptop GPU, 8,151 MiB, driver 596.13 |
| OS | Windows 11 Home |
| Python | 3.12.10 (the replay path was also run on 3.14.7) |
| Node, npm (web build only) | v24.14.0, 11.9.0 |

## Backend and perception
| Component | Version | Licence | Used where | Why chosen |
|---|---|---|---|---|
| FastAPI | 0.155.0 | MIT | `autosettle_api/app.py` | typed routes, a test client, small |
| uvicorn | 0.54.0 | BSD-3 | `python -m autosettle_api` | the usual ASGI server for FastAPI |
| Starlette, pydantic, httpx, python-multipart | 1.9.0, 2.14.1, 0.28.1, 0.0.32 | BSD, MIT | API, tests, uploads | FastAPI's dependencies |
| NumPy, Pillow | 2.5.2, 12.3.0 | BSD-3, HPND | image handling | standard |
| OpenCV (opencv-python 5.0.0.93; the replay install uses the headless build) | 5.0.0 | Apache-2.0 (wheel packaging MIT) | decoding, video sampling, SIFT continuity check, plate blur | no extra dependency for video |
| PyTorch | 2.11.0+cu128 | BSD-style | models | required by the models |
| Ultralytics | 8.4.182 | **AGPL-3.0** | `pipeline.py`, `tracker.py` (BYTETracker), `crops.py`, `surface_check.py` | YOLO11 segmentation and detection in one package; its licence consequence is in `LICENSE_NOTES.md` |
| Transformers | 5.20.2 | Apache-2.0 | `qwen.py` | loads Qwen3-VL |
| bitsandbytes | 0.50.2 | MIT | `qwen.py` | 4-bit (NF4) loading so an 8B model fits an 8 GB GPU |
| Gradio (optional) | 6.30.0 | Apache-2.0 | `autosettle_vision/app.py` | the earlier app, kept as a fallback |

## Models
| Model | Task | File and SHA-256 prefix | Our own measurement | Notes |
|---|---|---|---|---|
| Parts model, YOLO11s-seg | outlines 21 car panels | `parts_s_best.pt`, 55be0a95ace6e145 (20.5 MB) | mask mAP50 0.888 on its own test split (`run1/DECK_NUMBERS.md`) | the 22 of 74 recall figure is end to end on hard photos, a different measurement |
| Damage detector, YOLO11s box detector, 14 part-specific damage classes | finds damage and names the panel | `dent_det_best.pt`, 7658ddc39d03fb64 (19.2 MB) | test mAP50 0.826 on its own split, same source as training | no scratch class |
| Merged damage model, YOLO11-seg, 4 classes (Missing part, Broken part, Surface damage, Dent) | weak backup; only confident Missing or Broken part findings on panels the detector has no class for are used | `damage_merged_s_best.pt`, 6a30119796f0a21a (101.5 MB) | mask mAP50 0.18 | its Surface damage class (trained on merged scratch, paint chip, flaking, corrosion labels) is discarded at run time |
| Qwen3-VL-8B-Instruct, 4-bit NF4, bf16 compute | rewords the offer text, reads quote and plate photos; never prices | four safetensors shards, SHA-256 prefixes d5d0aef0eb170fc7, 8be88fb5501e4d57, 83de00eafe6e0d57, 0a88b98e9f962709 | 45 of 53 quote lines exact and 15 of 15 grand totals on 15 synthetic printed quotes | Apache-2.0 model licence as understood; check before redistribution. First offer with the model: 55 s, 7,788 MiB of GPU memory (`final/FINAL_REPORT.md`) |

Weights are not in the repository. Training used public datasets only; CarDD is excluded by the team's own rule.

## Frontend
| Component | Version | Licence | Notes |
|---|---|---|---|
| React, React DOM | 19.3.1 | MIT | |
| Vite | 7.3.7 (esbuild 0.28.2) | MIT | automatic JSX through esbuild; no React plugin |
| TypeScript | 5.9.3 | Apache-2.0 | `tsc --noEmit` runs before every build |
| Inter Variable (`@fontsource-variable/inter`) | 5.3.0 | SIL OFL-1.1 | bundled in `autosettle_api/static/assets`; no external font or script is loaded, so the page works offline |
| three.js | not used | | the reference look is built with CSS, canvas 2D and inline SVG |

All npm packages are pinned to exact versions and installed with `--ignore-scripts`. The built output is committed.

## What was considered and not used
- **CarDD** as training data: excluded by the team's rule (its licence needs the authors' form).
- **ThreeUI** buttons and shaders: the bundle's files matched their hashes, but one study imports a file that is not in the bundle and renders through an iframe, so an original CSS chrome button is used; no ThreeUI code is in any commit.
- **The teammate's "VGGT" module**: it is an edge-gradient heuristic, not VGGT; kept as an advisory experiment only (`surface_check.py`, not wired in).
- **Retraining the parts model** (Run 3): found parts rose only from 22 to at most 25 of 74, so the model was not swapped.
- **Per-panel crop detection**: found 22 to 34 of 74 but raised false alarms beyond the pre-set limit; off by default (`docs/CROPS_EXPERIMENT.md`).
- **Multi-view fusion**: a union of detections cannot raise recall; kept for video keyframes where it only merges.
