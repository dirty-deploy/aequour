"""
Keyframe sampler for the video path. Perception only; the engine never sees a video.

Limits (assumptions, chosen for an 8 GB laptop and a demo): at most 60 s, at most 12 keyframes, long side scaled to 1280 px.
Blurred and dark frames are dropped, using floors calibrated for video frames (BLUR_MIN_VIDEO, DARK_MIN_VIDEO), not the
photo floors. The clip is cut into equal time windows and the sharpest usable frame of each window is kept, in time order.
A file that is not decodable video, has no frames, or has only unusable frames raises VideoRejected (with the numbers and
what to do), so the claim can never reach an offer from a bad file.
Real footage: two night-time phone clips were run once each on 23 Oct 2026 (n = 2). That is a first test, not a measurement.

Sampling idea adapted from Ishan6907/AutoSettleAI (MIT), copyright held by its author (see THIRD_PARTY_NOTICES.md).
"""
from pathlib import Path

import cv2
import os

import numpy as np

MAX_SECONDS = 60.0
MAX_KEYFRAMES = 12
MAX_SIDE = 1280
CANDIDATES = 96            # frames inspected before choosing keyframes (96 decoded in 0.57 to 0.63 s on a 35 to 37 s clip here; 48 took 0.30 to 0.37 s)
BLUR_MIN = 60.0            # photo floors, same as pipeline.quality(); they still describe photos
DARK_MIN = 40.0


def _floor(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# [ASSUMPTION] Sharpness floor for a video frame (variance of the Laplacian). The photo floor of 60 was set for 12-megapixel
# photos. On the project's dev photos wider than 1280 px (n = 4), resizing the long side to 1280 px lowered the variance to a
# median 0.56 of its original (orig/resized median 1.78), so the same real sharpness is 60 * 0.56 = 33.7 at video size. Two
# night-time phone clips (n = 2) scored far lower than that (median 10.9 and 14.2 at 1280x720 on Ash's first measurement), so
# real night footage is expected to be rejected with its numbers until it is re-measured on daylight footage.
# Override for a test run with AEQUOUR_BLUR_MIN_VIDEO; the default is the measured equivalent.
BLUR_MIN_VIDEO = _floor("AEQUOUR_BLUR_MIN_VIDEO", 33.7)
# [ASSUMPTION] Light floor for a video frame (mean grey level). Chosen below the photo floor of 40 because phone video at night is
# darker; calibrated on the same two night-time phone clips (n = 2: frame brightness means 33.3 and 63.8); not measured on
# daylight footage. Override with AEQUOUR_DARK_MIN_VIDEO.
DARK_MIN_VIDEO = _floor("AEQUOUR_DARK_MIN_VIDEO", 25.0)
_FORMAT_HELP = "This video format could not be read. Save it as H.264 MP4 and try again."
_ADVICE = "Film in daylight, hold the phone steady, and walk slowly round the car."


class VideoRejected(Exception):
    """The file cannot be used as evidence (not video, too long, empty, or no usable frame)."""


def _scale(fr):
    h, w = fr.shape[:2]
    m = max(h, w)
    if m <= MAX_SIDE:
        return fr
    f = MAX_SIDE / m
    return cv2.resize(fr, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)


def _scores(fr):
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var()), float(g.mean())


def _usable(fr):
    s, b = _scores(fr)
    return s >= BLUR_MIN_VIDEO and b >= DARK_MIN_VIDEO


def keyframe_scores(fr, index, fps):
    """What the UI shows under each keyframe: where it is in the clip and the two numbers the usability filter used."""
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    return {"frame": int(index), "seconds": round(index / fps, 2), "sharpness": round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 1),
            "brightness": round(float(g.mean()), 1)}


def thumbnails(frames, max_side=192, quality=70):
    """Small JPEG data URIs for the keyframe strip (display only; the pipeline reads the full frames)."""
    import base64
    out = []
    for _, fr in frames:
        h, w = fr.shape[:2]
        f = max_side / max(h, w)
        small = cv2.resize(fr, (max(1, int(w * f)), max(1, int(h * f))), interpolation=cv2.INTER_AREA) if f < 1 else fr
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
        out.append("data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii") if ok else None)
    return out


def probe(path):
    """(fps, frame_count, duration_s) or raises VideoRejected."""
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise VideoRejected(_FORMAT_HELP)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or n <= 0:
            raise VideoRejected(_FORMAT_HELP)
        return fps, n, n / fps
    finally:
        cap.release()


def read_frames(path, indices, scale=True):
    """Frames at the given indices (sorted), skipping any that fail to decode."""
    cap = cv2.VideoCapture(str(path))
    out = []
    try:
        for i in sorted(set(int(x) for x in indices)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, fr = cap.read()
            if ok and fr is not None:
                out.append((i, _scale(fr) if scale else fr))
    finally:
        cap.release()
    return out


def _rejection(cand_scores, usable_count):
    """The words for a clip that cannot be used: the best numbers it reached, the floors, and what to do."""
    best_s = max(sc for sc, _ in cand_scores)
    best_b = max(b for _, b in cand_scores)
    floors = f"(sharpness needs at least {BLUR_MIN_VIDEO:g}, light at least {DARK_MIN_VIDEO:g})"
    if usable_count == 0:
        return (f"No frame was clear enough to read. The sharpest frame scored sharpness {best_s:.0f} and the brightest light {best_b:.0f} "
                f"{floors}. {_ADVICE}")
    return (f"Only {usable_count} frame{'s were' if usable_count != 1 else ' was'} clear enough to read and at least 2 are needed. "
            f"The sharpest frame scored sharpness {best_s:.0f} and the brightest light {best_b:.0f} {floors}. {_ADVICE}")


def _pick_by_window(good, n, max_keyframes):
    """good = [(frame_index, frame, sharpness)]. Cut the clip [0, n) into max_keyframes equal time windows and keep the sharpest
    usable frame of each window. The result is in time order."""
    picked = {}
    for item in good:
        w = min(max_keyframes - 1, int(item[0] * max_keyframes / max(1, n)))
        if w not in picked or item[2] > picked[w][2]:
            picked[w] = item
    return [picked[w] for w in sorted(picked)]


def sample_keyframes(path, max_keyframes=MAX_KEYFRAMES):
    """Returns (frames, info). frames = [(name, bgr)] in time order; info is a plain dict for the audit log."""
    path = Path(path)
    fps, n, dur = probe(path)
    if dur > MAX_SECONDS:
        raise VideoRejected(f"the video is longer than {int(MAX_SECONDS)} seconds")
    idx = np.unique(np.linspace(0, n - 1, min(CANDIDATES, n)).round().astype(int))
    cand = read_frames(path, idx)
    if not cand:
        raise VideoRejected(_FORMAT_HELP)
    scored = [(i, f, *_scores(f)) for i, f in cand]
    good = [(i, f, s) for i, f, s, b in scored if s >= BLUR_MIN_VIDEO and b >= DARK_MIN_VIDEO]
    info = {"fps": round(fps, 2), "frames": n, "seconds": round(dur, 2), "candidates": len(cand), "usable": len(good),
            "dropped_blur_or_dark": len(cand) - len(good), "blur_min": BLUR_MIN_VIDEO, "dark_min": DARK_MIN_VIDEO}
    if len(good) < 2:
        raise VideoRejected(_rejection([(s, b) for _, _, s, b in scored], len(good)))
    chosen = _pick_by_window(good, n, max_keyframes)
    if len(chosen) < 2:
        raise VideoRejected(f"The clear frames are all from one short part of the clip, and at least 2 parts are needed. {_ADVICE}")
    info["keyframes"] = len(chosen)
    info["keyframe_scores"] = [keyframe_scores(f, i, fps) for i, f, _ in chosen]
    return [(f"{path.name}#f{k}", fr) for k, (_, fr, _) in enumerate(chosen)], info
