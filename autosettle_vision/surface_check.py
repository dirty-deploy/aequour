"""
Edge-gradient surface heuristic for dent candidates.  It is NOT VGGT and NOT 3D reconstruction.

adapted from Ishan6907/AutoSettleAI (MIT licence as found in that repository), copyright held by its author
(`VGGT3DChecker.estimate_depth_map`, `compute_local_concavity`, `verify_dent`). What it really does: it blurs the grey image,
rescales it to 0..1 and calls that a "depth map", then takes the brightness Laplacian inside the damage box. A dark dent
shadow and a dark sticker look the same to it. It was evaluated here (tools/surface_eval.py, final/SURFACE_CHECK.md).

Rules for this module (final-run rules 7): its output may only add an "ask for a clearer photo" flag. It never removes a
detection and never changes a rupee. Whether it is wired into the pipeline depends on the evaluation; see final/SURFACE_CHECK.md.
"""
import cv2
import numpy as np

CONCAVITY_MIN = 0.015       # as in the original
LOW_CONF = 0.45             # as in the original: only low-confidence candidates are examined


def pseudo_depth(img_bgr):
    g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    smooth = cv2.bilateralFilter(g, d=9, sigmaColor=0.1, sigmaSpace=9.0)
    z = cv2.GaussianBlur(smooth, (15, 15), 3.0)
    return (z - z.min()) / max(float(z.max() - z.min()), 1e-6)


def concavity(depth, box):
    """Mean brightness Laplacian inside the box (the original's 'concavity'); 0.0 for a degenerate box."""
    h, w = depth.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, max(x1 + 1, x2)), min(h, max(y1 + 1, y2))
    crop = depth[y1:y2, x1:x2]
    if crop.size < 4:
        return 0.0
    return float(np.mean(cv2.Laplacian(crop, cv2.CV_32F, ksize=5)))


def check(img_bgr, box, damage_conf):
    """Returns {"ask_for_clearer_photo": bool, "concavity": float, "reason": str|None}. Advisory only."""
    c = concavity(pseudo_depth(img_bgr), box)
    weak = damage_conf < LOW_CONF and c < CONCAVITY_MIN
    return {"ask_for_clearer_photo": weak, "concavity": round(c, 4),
            "reason": f"low confidence ({damage_conf:.2f}) and little surface curvature ({c:.3f}): ask for a clearer photo" if weak else None}
