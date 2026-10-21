# SURFACE_CHECK (Stage C.1): the teammate's "VGGT" dent check, renamed `autosettle_vision/surface_check.py`

What it is: an edge-gradient / brightness heuristic (blurred grey image rescaled to 0..1, Laplacian inside the damage box). It is not VGGT and not 3D reconstruction.

Evaluation (`tools/surface_eval.py`, CPU, cached detector output on the 41 dev photos, 52 detector candidates at confidence 0.30 or more; labels by Claude by eye). The check can only fire on candidates below 0.45 confidence with low "concavity".

| group | candidates | flagged "ask for a clearer photo" | share |
|---|---|---|---|
| true damage (named panel is a labelled damaged panel) | 32 | 6 | 18.8% |
| false alarms on the 6 photos with no labelled damage | 6 | 1 | 16.7% |
| right photo, wrong panel | 14 | 3 | 21.4% |

**Decision: not wired in.** It flags a larger share of true damage (18.8%) than of false alarms (16.7%), so it would push claims toward ASK_MORE on correct detections at least as often as on wrong ones. 6 of 6 false alarms is a tiny sample (1 flagged); the result is "no evidence of use", not proof of harm. The module stays in the tree as an advisory helper with this result documented; nothing in the pipeline or API calls it. Its output could only ever add a request for a clearer photo (never remove a detection or change a rupee).
