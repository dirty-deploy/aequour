"""Number-plate blur for the DISPLAYED demo photos. The pipeline always reads the original file; only what the browser,
the deck assets and the video thumbnails show is blurred. Boxes are fixed rectangles for the three known demo photos,
keyed by the photo's SHA-256 (image pixel coordinates, [x0, y0, x1, y1]). A photo that is not listed is shown unchanged:
uploads from the user are the user's own."""
import cv2
import numpy as np

DEMO_PLATE_BOXES = {
    # c05_Abandoned_Suzuki_Osidge_London_2.jpg, 1280x960 (UK plate)
    "885a5e583d1c7cd9c911f4a700c9b166c69b6aa2e9e130d4fa633f657f181de2": [[196, 614, 394, 718]],
    # c53_Alto_800_accident.jpg, 1280x720
    "26399f811a353c8dbadc1ad6ed5bbd19eb3a62ffc57ddb2d2d18eef628ff5e54": [[158, 638, 400, 706]],
    # c44_Chennai_damage_1.jpg, 800x600
    "fce7b1abe4461cd4d49e50233c3394777c640f97b5171e87b23e45cd47d898e7": [[314, 138, 370, 170]],
}


def blur_boxes(bgr, boxes, scale=1.0):
    """Return a copy with each box pixelated and blurred (the characters cannot be recovered). `scale` maps the
    boxes onto a resized image (thumbnails)."""
    out = bgr.copy()
    h, w = out.shape[:2]
    for x0, y0, x1, y1 in boxes:
        x0, y0, x1, y1 = [int(round(v * scale)) for v in (x0, y0, x1, y1)]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        roi = out[y0:y1, x0:x1]
        small = cv2.resize(roi, (max(2, (x1 - x0) // 14), max(2, (y1 - y0) // 14)), interpolation=cv2.INTER_AREA)
        pix = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        out[y0:y1, x0:x1] = cv2.GaussianBlur(pix, (0, 0), max(3, (y1 - y0) / 6))
    return out


def displayed_bytes(data, sha, media="image/jpeg"):
    """Bytes the browser should get for a stored photo: blurred if the photo is a known demo photo."""
    boxes = DEMO_PLATE_BOXES.get(sha)
    if not boxes:
        return data
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return data
    ok, buf = cv2.imencode(".jpg" if media == "image/jpeg" else ".png", blur_boxes(img, boxes))
    return buf.tobytes() if ok else data
