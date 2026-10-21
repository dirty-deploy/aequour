"""A SYNTHETIC walk-around: a slow zoom and pan over ONE photo. It is not a real walk-around; there is no parallax, no
second angle and no new information. It exists so the video path can be exercised, recorded for replay mode and tested
end to end. `frames()` is deterministic, so the same keyframes can be rebuilt later for display."""
import cv2
import numpy as np

FPS = 10
SECONDS = 12
# variant -> (final zoom factor, how far the window's top-left moves, in pixels of a 1280x960 source)
VARIANTS = {"wide": (1.15, (60, 100)), "close": (1.3, (120, 200))}


def _ease(t):
    return t * t * (3 - 2 * t)


def frames(img, variant="wide", n=FPS * SECONDS):
    """List of BGR frames, all the size of `img`, each a crop of it scaled back up. The crops keep the lower-centre of the
    photo (where the demo damage is) in view."""
    h, w = img.shape[:2]
    zoom_end, pan = VARIANTS[variant]
    out = []
    for k in range(n):
        t = _ease(k / max(1, n - 1))
        z = 1.0 + (zoom_end - 1.0) * t
        cw, ch = int(round(w / z)), int(round(h / z))
        x0 = int(round(pan[0] * w / 1280 * t))
        y0 = int(round(pan[1] * h / 960 * t))
        x0, y0 = min(x0, w - cw), min(y0, h - ch)
        crop = img[y0:y0 + ch, x0:x0 + cw]
        out.append(cv2.resize(crop, (w, h), interpolation=cv2.INTER_CUBIC) if z > 1.0 else crop.copy())
    return out


def write_mp4(img, path, variant="wide"):
    h, w = img.shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))
    for fr in frames(img, variant):
        vw.write(fr)
    vw.release()
    return path
