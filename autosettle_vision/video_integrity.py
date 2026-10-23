"""
Continuity check for a video: consecutive frames must be geometrically related (SIFT + RANSAC homography inliers).
A cut or a splice (a different car or scene joined in) leaves too few inliers. The result only ever adds an integrity
flag, which the engine turns into ESCALATE; it can never lower an offer.

Adapted from the multi-view consistency idea in Ishan6907/AutoSettleAI (MIT, copyright held by its author) and from
pipeline.video_frames. Run on densely sampled frames, not on the sparse keyframes: a walk-around moves a lot between
keyframes taken seconds apart, which would give false cuts.

[ASSUMPTION] fewer than MIN_INLIERS geometric inliers between neighbouring dense frames = not the same scene. Validated on
synthetic clips (see tests). Two real night-time phone clips were run once each on 23 Oct 2026 (n = 2): a large share of their
neighbouring pairs fell below the threshold, so real handheld footage is often flagged. That costs a human look (ESCALATE),
not money, and the rule is NOT relaxed.

The flag is the same for every break. What differs is the NAME of the reason, from a second signal that is never used to excuse
a break: the change in overall appearance (Bhattacharyya distance between HSV colour histograms of neighbouring frames).
A geometric break with a large appearance change is a hard cut; one with a small change is unverified (shaky or dark footage).
"""
import cv2
import numpy as np

from . import video as V

DENSE_FRAMES = 120         # a denser sample is better evidence, not a looser rule (60 before; CPU time is reported in the run notes)
MIN_INLIERS = 15
WIDTH = 640
# [ASSUMPTION] A geometric break whose appearance distance is above this is named a hard cut. Evidence: two real night-time phone
# clips (n = 2) had consecutive-frame maxima of 0.289 and 0.268 over 240 frames; two deliberate splices of those clips scored 0.567
# and 0.543 at the join (ranked first of 239). Two clips and two splices are not a validation. It only names a break; it never excuses one.
APPEARANCE_CUT = 0.40
HIST_SIZE = (160, 90)
HIST_BINS = [12, 8, 8]


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


def _hist(fr):
    hsv = cv2.cvtColor(cv2.resize(fr, HIST_SIZE, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, HIST_BINS, [0, 180, 0, 256, 0, 256])
    return cv2.normalize(h, h, 1.0, 0.0, cv2.NORM_L1)


def appearance_changes(frames):
    """Bhattacharyya distance between the HSV colour histograms of each neighbouring pair (0 = the same look, 1 = nothing shared)."""
    hs = [_hist(f) for f in frames]
    return [float(cv2.compareHist(hs[k - 1], hs[k], cv2.HISTCMP_BHATTACHARYYA)) for k in range(1, len(hs))]


def check_frames(frames, min_inliers=MIN_INLIERS):
    """frames = [bgr]. Returns the geometric result and its naming:
    transitions (inliers per neighbouring pair), breaks (index of the frame that starts a new scene), hard_cuts and unverified
    (the breaks split by appearance change; every break is in exactly one of them), appearance, max_appearance, median_appearance."""
    sift = cv2.SIFT_create(800)
    feats = [_features(f, sift) for f in frames]
    inl = [inliers(feats[k - 1], feats[k]) for k in range(1, len(feats))]
    app = appearance_changes(frames)
    breaks = [k + 1 for k, v in enumerate(inl) if v < min_inliers]
    hard = [k for k in breaks if app[k - 1] > APPEARANCE_CUT]
    srt = sorted(app)
    return {"transitions": inl, "breaks": breaks, "hard_cuts": hard, "unverified": [k for k in breaks if k not in hard],
            "appearance": [round(a, 3) for a in app], "max_appearance": round(srt[-1], 3) if srt else None,
            "median_appearance": round(srt[len(srt) // 2], 3) if srt else None}


def check_video(path):
    """Dense-sample the clip and check continuity. Returns the dict from check_frames plus 'frames_checked'."""
    fps, n, _ = V.probe(path)
    idx = np.unique(np.linspace(0, n - 1, min(DENSE_FRAMES, n)).round().astype(int))
    read = V.read_frames(path, idx)
    out = check_frames([f for _, f in read])
    out["frames_checked"] = len(read)
    out["seconds"] = [round(i / fps, 1) for i, _ in read]          # where each dense frame sits in the clip
    return out


def outcome(result):
    """(name, plain words) for the person reading the result. 'continuous' only when there is no break at all."""
    if not result["breaks"]:
        return "continuous", "One continuous take: no breaks"
    if result["hard_cuts"]:
        sec = result.get("seconds") or []
        k = result["hard_cuts"][0]
        at = f" at about {sec[k]:.0f} s" if k < len(sec) else ""
        return "hard_cut", f"A hard cut was found{at}: a person will check"
    return "unverified", "Could not confirm one continuous take (the footage is shaky or dark): a person will check"


def flags(result):
    return [f"video_not_continuous:frames_{result['breaks'][:5]}"] if result["breaks"] else []
