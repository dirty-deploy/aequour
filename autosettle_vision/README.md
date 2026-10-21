# autosettle_vision

Perception and language layer for Auto-Settle AI. Photos or video go in; the vision JSON the engine reads comes out.
Qwen only rewords and reads. Money is decided in `autosettle_engine`.

Run everything from `C:\autosettle` with the project env: `.\env\Scripts\python.exe -m ...`

| Command | What it does |
|---|---|
| `-m autosettle_vision.app` | Local web app (Gradio, http://127.0.0.1:7860): policy → photos → offer → quote dispute → settle, with the audit log. `--no-qwen` skips the VLM. |
| `-m autosettle_vision.claim --policy POL-DEMO-001 IMG...` | One claim from the command line (`--qwen` loads the VLM; `--test-assume-plate` for dataset photos with no plate). |
| `-m autosettle_vision.pipeline IMG... [--video V]` | Vision JSON only. |
| `-m autosettle_vision.photo_eval` | Scores the pipeline + engine on `test_photos/commons` (41 photos, hand-labelled). → `runs/photo_eval.json` |
| `-m autosettle_vision.qwen_eval` | Real Qwen rewordings through `rationale.safe_reply()`. → `runs/qwen_eval.json` |
| `-m autosettle_vision.quote_gen` then `-m autosettle_vision.quote_eval` | Synthetic garage quotes, Qwen quote reading, dispute flow. → `runs/quote_eval.json` |
| `tools/sweep_vision.py` | Inference size / confidence sweep on the Commons photos. |
| `tools/build_rate_card_v2.py` | Rebuilds `autosettle_engine/rate_card_v2.csv` from v1 + the verified boodmo rows. |

## Models
- `backup/parts_s_best.pt`: YOLO11s-seg, 21 parts (where).
- `backup/dent_det_best.pt`: YOLO11s detect, 14 part-specific damage classes from Roboflow (what). Main damage signal.
- `backup/damage_merged_s_best.pt`: YOLO11s-seg, 4 classes. Weak; used only for Missing/Broken part at confidence ≥ 0.5 on parts the detector has no class for.
- `Qwen/Qwen3-VL-8B-Instruct`, 4-bit NF4 (bitsandbytes), about 6.4 GB VRAM on the RTX 5050. Jobs: `reword()`, `read_quote()`, `read_plate()`. It never receives the ceiling, `ceiling_lines` or `pivots()` (`reword()` refuses text containing the ceiling).

## Pipeline rules (all in `pipeline.py`, tagged in comments)
- Inference at 960 px, detector confidence 0.25 (picked by `tools/sweep_vision.py`).
- Damage box → best-overlapping compatible part mask. Severity = damage area inside the part ÷ part area (box × π/4): < 0.30 minor, < 0.60 moderate, else severe. Weakly calibrated (see the comment).
- Close-up with no panel outline → `need_wider_photo:<part>` → engine asks for more.
- Heavy crash (3+ severe parts, a severe hood plus another severe part, or both doors severe) → `structural_suspected` → the engine sends it to a surveyor.
- Integrity: near-duplicate of a photo from another claim (`runs/seen_hashes.json`), editing-software EXIF tag, a video that is not one continuous take (SIFT + RANSAC) → `integrity_flags` → escalate. Blurry or dark frames are dropped and flagged.
- Plate: Qwen reads the License-plate crop; if none was outlined, it reads the first photo whole (capture protocol: start on the plate). Only Indian-format plates are accepted.

`policies.json` is a simulated insurer plate lookup. `test_photos/demo/00_plate_DL3CAB1234.jpg` is a synthetic plate image for the demo policy.
