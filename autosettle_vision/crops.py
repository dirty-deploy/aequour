"""
Per-panel crop variant of the damage detector (Stage C experiment; OFF by default; nothing imports this unless asked).
For every segmented panel the damage detector also runs on the full-resolution crop of that panel (15 % margin); boxes are
mapped back to the full frame and merged with the whole-frame boxes by class-wise box NMS. Evaluated on the 41 dev photos with
`python tools/eval_dev.py --live --variant crops` and written up in final/CROPS_EXPERIMENT.md.
"""
import numpy as np

from . import pipeline as P

MARGIN = 0.15
NMS_IOU = 0.5


def _iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def nms(dets, iou=NMS_IOU):
    """dets = [(box, conf, cls)]; class-wise NMS keeping the highest confidence."""
    keep = []
    for d in sorted(dets, key=lambda d: -d[1]):
        if all(not (k[2] == d[2] and _iou(k[0], d[0]) >= iou) for k in keep):
            keep.append(d)
    return keep


def panel_boxes(polys, shape):
    """Crop windows (x1, y1, x2, y2) around each polygon with a 15 % margin."""
    h, w = shape[:2]
    out = []
    for poly in polys:
        p = np.asarray(poly)
        if len(p) < 3:
            continue
        x1, y1, x2, y2 = p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()
        mx, my = (x2 - x1) * MARGIN, (y2 - y1) * MARGIN
        out.append((max(0, int(x1 - mx)), max(0, int(y1 - my)), min(w, int(x2 + mx)), min(h, int(y2 + my))))
    return out


def crop_dets(img, windows, det_model, conf, imgsz=None):
    """Run the detector on each crop window; returns [(box_full_frame, conf, cls_index)]."""
    out = []
    for x1, y1, x2, y2 in windows:
        if x2 - x1 < 32 or y2 - y1 < 32:
            continue
        r = det_model.predict(img[y1:y2, x1:x2], conf=conf, imgsz=imgsz or P.IMGSZ, verbose=False)[0]
        for b, c, k in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            out.append(([b[0] + x1, b[1] + y1, b[2] + x1, b[3] + y1], float(c), float(k)))
    return out


def hook(img, parts, dets, det_model):
    """pipeline.DET_HOOK: add crop detections to the whole-frame ones and merge. Only panels the detector has classes for."""
    polys = [p["poly"] for p in parts if p["part_class"] in P.DET_PARTS]
    extra = crop_dets(img, panel_boxes(polys, img.shape), det_model, P.CONF_DET)
    merged = nms([(list(b), float(c), float(k)) for b, c, k in dets] + extra)
    return [(b, c, k) for b, c, k in merged]


def enable():
    P.DET_HOOK = hook


def disable():
    P.DET_HOOK = None
