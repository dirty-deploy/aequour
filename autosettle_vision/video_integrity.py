"""
Continuity check for a video: consecutive frames must be geometrically related (SIFT + RANSAC homography inliers).
A cut or a splice (a different car or scene joined in) leaves too few inliers. The result only ever adds an integrity
flag, which the engine turns into ESCALATE; it can never lower an offer.

Adapted from the multi-view consistency idea in Ishan6907/AutoSettleAI (MIT, copyright held by its author) and from
pipeline.video_frames. Run on densely sampled frames, not on the sparse keyframes: a walk-around moves a lot between
keyframes taken seconds apart, which would give false cuts.

[ASSUMPTION] fewer than MIN_INLIERS geometric inliers between neighbouring dense frames = not the same scene. Validated only
on synthetic clips (see tests); no real walk-around video exists on this laptop. A real walk-around that turns a corner
quickly may be flagged, which costs a human look (ESCALATE), not money.
"""
import cv2
import numpy as np

from . import video as V

DENSE_FRAMES = 60
MIN_INLIERS = 15
WIDTH = 640


def _features(fr, sift):
    h, w = fr.shape[:2]
    g = cv2.cvtColor(cv2.resize(fr, (WIDTH, max(1, int(WIDTH * h / w)))), cv2.COLOR_BGR2GRAY)
    return sift.detectAndCompute(g, None)


def inliers(a, b):
    """Homography inliers between two feature sets (kp, des)."""
    (kp1, d1), (kp2, d2) = a, b
    if d1 is None or d2 is None or len(kp1) < 10 or len(kp2) < 10:
        return 0
    m = cv2.BFMatcher().knnMatch(d1, d2, k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
    if len(good) < 8:
        return 0
    src = np.float32([kp1[g.queryIdx].pt for g in good])
    dst = np.float32([kp2[g.trainIdx].pt for g in good])
    _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    return int(mask.sum()) if mask is not None else 0


def check_frames(frames, min_inliers=MIN_INLIERS):
    """frames = [bgr]. Returns {"transitions": [inliers...], "breaks": [index of the frame that starts a new scene]}."""
    sift = cv2.SIFT_create(800)
    feats = [_features(f, sift) for f in frames]
    inl = [inliers(feats[k - 1], feats[k]) for k in range(1, len(feats))]
    return {"transitions": inl, "breaks": [k + 1 for k, v in enumerate(inl) if v < min_inliers]}


def check_video(path):
    """Dense-sample the clip and check continuity. Returns the dict from check_frames plus 'frames_checked'."""
    _, n, _ = V.probe(path)
    idx = np.unique(np.linspace(0, n - 1, min(DENSE_FRAMES, n)).round().astype(int))
    frames = [f for _, f in V.read_frames(path, idx)]
    out = check_frames(frames)
    out["frames_checked"] = len(frames)
    return out


def flags(result):
    return [f"video_not_continuous:frames_{result['breaks'][:5]}"] if result["breaks"] else []
