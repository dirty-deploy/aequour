# Real-clip check, 23 Oct 2026

Two real night-time phone clips were each run **once** through the live pipeline (`python -m autosettle_api --no-qwen --fresh-seen --port 8100`, three YOLO detectors, no language model). **n = 2. This is a first test, not a measurement.** Nothing here is an accuracy, recall or validation figure. The clips and any frame from them are not in this repository (they show a readable number plate).

## What the files were

Both were WhatsApp-re-encoded MP4 files, already upright (portrait, no rotation flag; a decoded frame shows the car the right way up), so no upright copy was made. Sizes as decoded: 464 x 832 (37.4 s, 31.58 fps) and 480 x 848 (35.1 s, 24 fps). These are **not** the 1280 x 720 `.mov` originals that were measured earlier, so the earlier sharpness and brightness numbers do not carry over.

## Settings used

| Setting | Value | Where it comes from |
|---|---|---|
| Sharpness floor for a video frame | 33.7 | the dev photos wider than 1280 px (n = 4) lose about 44 percent of their Laplacian variance when resized to 1280 px (median resized/original 0.56, so 60 x 0.56); see `autosettle_vision/video.py` |
| Light floor for a video frame | 25 | [ASSUMPTION], two night-time clips (n = 2) |
| Candidate frames inspected | 96 | decoding 96 frames took 0.57 to 0.63 s on a 35 to 37 s clip here (48 took 0.30 to 0.37 s) |
| Continuity frames | 120 | `check_video` took 6.97 s and 6.43 s on CPU for the two clips (60 frames: 3.43 s and 3.16 s); the 8 s budget holds |
| Hard-cut appearance threshold | 0.40 | [ASSUMPTION], two clips and two splices measured earlier |

## Result of each clip

| Field | Clip A (Tata Nexon policy) | Clip B (Maruti Swift policy) |
|---|---|---|
| HTTP status | 200 | 200 |
| Wall-clock seconds | 10.5 | 10.1 |
| Rejection message | none | none |
| Sampled frames usable | 22 of 96 (74 dropped as too blurred or too dark) | 6 of 96 (90 dropped) |
| Keyframes kept | 8 | 3 |
| Continuity | 33 breaks in 119 pairs; lowest 0 inliers, median 22, 15 needed; 0 hard cuts, 33 unverified; largest change in overall look 0.369, median 0.186. Outcome: "Could not confirm one continuous take (the footage is shaky or dark): a person will check" | 53 breaks in 119 pairs; lowest 0, median 19, 15 needed; 0 hard cuts, 53 unverified; largest change 0.369, median 0.178. Same outcome wording |
| Detections found | Back-bumper, damage seen in 1 of 8 keyframes, no severity, confidence 0.262 | Roof, damage seen in 1 of 3 keyframes, no severity, confidence 0.277 |
| Engine decision | ESCALATE (reason: video not continuous; gate also missing parts and damage identified) | ESCALATE (same reasons) |
| Offer | none | none |
| What the customer was told | "Sorry, I can't go further with this one." then a reason line and the Next step line (a claims specialist will review this). The reason line on this run said "The video jumps between scenes, so I can't rely on it."; that wording was wrong for shaky footage and has since been replaced by "I couldn't confirm that the video is one continuous take, so a person needs to look at it." (the server had been started before the change) | same |
| Adjuster estimate | nothing priced: payable 0 to 0, incomplete; Back-bumper not priced (severity not determined: needs a clearer view) | nothing priced: 0 to 0, incomplete; Roof not priced (same reason) |
| GPU after the run | 55 C, 1,269 MiB | 55 C, 1,318 MiB |

Nothing was edited to make either clip pass. Neither clip reached an offer.

## What this does and does not show

- Real handheld night footage was flagged by the geometric continuity check on a large share of neighbouring pairs, as expected. The flag stayed and the engine escalated. That is the safe result, and it is uninformative about whether the footage was edited.
- The appearance signal did not name a hard cut in either clip at 120 frames (largest 0.369, threshold 0.40). At 60 frames the same clips scored 0.440 and 0.416 and would have been named as having one hard cut and two respectively, so the 0.40 threshold depends on how densely the clip is sampled. It was calibrated at 240 frames; 0.369 is close to it.
- The detectors saw one weak, low-confidence dent each, in one keyframe only. That says nothing about the actual damage on these cars.
- With the 33.7 sharpness floor, 22 and 6 of 96 sampled frames were usable. A floor of 8 (the first guess) would have kept more. The floor is an ASSUMPTION to be re-measured on daylight footage.

## Photo path

`python tools/eval_dev.py`, run once at 48 C: 22 of 74 parts found, as before. The photo quality floors (60 and 40) are untouched.
