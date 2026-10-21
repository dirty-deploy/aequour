"""
Keyframe sampler for the video path. Perception only; the engine never sees a video.

Limits (assumptions, chosen for an 8 GB laptop and a demo): at most 60 s, at most 12 keyframes, long side scaled to 1280 px.
Blurred and dark frames are dropped. Keyframes are spread over time. A file that is not decodable video, has no frames, or
has only unusable frames raises VideoRejected, so the claim can never reach an offer from a bad file.

Sampling idea adapted from Ishan6907/AutoSettleAI (MIT), copyright held by its author (see THIRD_PARTY_NOTICES.md).
"""
from pathlib import Path

import cv2
import numpy as np

MAX_SECONDS = 60.0
MAX_KEYFRAMES = 12
MAX_SIDE = 1280
CANDIDATES = 48            # frames inspected before choosing keyframes
BLUR_MIN = 60.0            # same floors as pipeline.quality()
DARK_MIN = 40.0


class VideoRejected(Exception):
    """The file cannot be used as evidence (not video, too long, empty, or no usable frame)."""


def _scale(fr):
    h, w = fr.shape[:2]
    m = max(h, w)
    if m <= MAX_SIDE:
        return fr
    f = MAX_SIDE / m
    return cv2.resize(fr, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)


def _usable(fr):
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var()) >= BLUR_MIN and float(g.mean()) >= DARK_MIN


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
            raise VideoRejected("the file is not a decodable video")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or n <= 0:
            raise VideoRejected("the video has no readable frames")
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


def sample_keyframes(path, max_keyframes=MAX_KEYFRAMES):
    """Returns (frames, info). frames = [(name, bgr)] in time order; info is a plain dict for the audit log."""
    path = Path(path)
    fps, n, dur = probe(path)
    if dur > MAX_SECONDS:
        raise VideoRejected(f"the video is longer than {int(MAX_SECONDS)} seconds")
    idx = np.unique(np.linspace(0, n - 1, min(CANDIDATES, n)).round().astype(int))
    cand = read_frames(path, idx)
    if not cand:
        raise VideoRejected("no frame could be decoded")
    good = [(i, f) for i, f in cand if _usable(f)]
    info = {"fps": round(fps, 2), "frames": n, "seconds": round(dur, 2), "candidates": len(cand), "usable": len(good),
            "dropped_blur_or_dark": len(cand) - len(good)}
    if not good:
        raise VideoRejected("every sampled frame is too blurred or too dark to use")
    if len(good) > max_keyframes:
        pick = np.unique(np.linspace(0, len(good) - 1, max_keyframes).round().astype(int))
        good = [good[k] for k in pick]
    if len(good) < 2:
        raise VideoRejected("a video needs at least two usable frames; send photos instead")
    info["keyframes"] = len(good)
    info["keyframe_scores"] = [keyframe_scores(f, i, fps) for i, f in good]
    return [(f"{path.name}#f{k}", fr) for k, (_, fr) in enumerate(good)], info
