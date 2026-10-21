#!/usr/bin/env python3
"""
Convert the Hugging Face "car parts / car damages" download (Supervisely export)
into two YOLO-seg datasets:

    yolo/parts/    (from "Car parts dataset")
    yolo/damage/   (from "Car damages dataset")

Run from the folder that holds download_data.py, with the env active:

    python convert_hf_to_yolo.py

Reads   ./data/hf_parts_damage/<set>/<FileN>/{ann,img}
Writes  ./yolo/<name>/{images,labels}/{train,val} + data.yaml

Handles polygon and bitmap objects. Exact duplicate images are dropped before the
train/val split. There is no vehicle/claim ID in this data, so the split is random
by image: validation scores will be optimistic. Keep a separate test set of your own photos.
"""
import base64, collections, hashlib, json, pathlib, random, shutil, sys, zlib

import cv2
import numpy as np
import yaml

HERE = pathlib.Path(__file__).parent
SRC = HERE / "data" / "hf_parts_damage"
OUT = HERE / "yolo"
SETS = {"damage": "Car parts dataset", "parts": "Car damages dataset"}
VAL_FRAC = 0.15
SEED = 0
MIN_AREA_PX = 16          # ignore specks smaller than this
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


# ------------------------------------------------------------------ geometry
def bitmap_to_mask(obj, h, w):
    """Supervisely bitmap: base64(zlib(PNG)) placed at origin [x, y]."""
    data = obj["bitmap"]["data"]
    ox, oy = obj["bitmap"]["origin"]
    png = np.frombuffer(zlib.decompress(base64.b64decode(data)), np.uint8)
    im = cv2.imdecode(png, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 3 and im.shape[2] == 4:
        small = im[:, :, 3] > 0
    elif im.ndim == 3:
        small = im.sum(axis=2) > 0
    else:
        small = im > 0
    mask = np.zeros((h, w), np.uint8)
    sh, sw = small.shape
    y1, x1 = min(h, oy + sh), min(w, ox + sw)
    if y1 <= oy or x1 <= ox or oy < 0 or ox < 0:
        return None
    mask[oy:y1, ox:x1] = small[: y1 - oy, : x1 - ox]
    return mask


def mask_to_polys(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for c in cnts:
        if cv2.contourArea(c) < MIN_AREA_PX:
            continue
        eps = 0.002 * cv2.arcLength(c, True)
        c = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(c) >= 3:
            polys.append(c.astype(float).tolist())
    return polys


def object_polys(obj, h, w, geom_counter):
    gt = obj.get("geometryType")
    geom_counter[gt] += 1
    if gt == "polygon":
        pts = obj["points"]["exterior"]
        return [pts] if len(pts) >= 3 else []
    if gt == "bitmap":
        m = bitmap_to_mask(obj, h, w)
        return mask_to_polys(m) if m is not None else []
    if gt == "rectangle":
        (x1, y1), (x2, y2) = obj["points"]["exterior"]
        return [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]
    return []


def find_image(img_dir, ann_path):
    cand = img_dir / ann_path.stem            # "x.jpg.json" -> "x.jpg"
    if cand.exists():
        return cand
    base = ann_path.stem.rsplit(".", 1)[0]
    for ext in IMG_EXT:
        p = img_dir / (base + ext)
        if p.exists():
            return p
    return None


# ------------------------------------------------------------------ one set
def convert_set(name, folder_name):
    set_dir = SRC / folder_name
    if not set_dir.exists():
        print(f"[{name}] folder not found: {set_dir}")
        return
    meta_path = set_dir / "meta.json"
    meta_order = []
    if meta_path.exists():
        meta_order = [c["title"] for c in json.load(open(meta_path, encoding="utf-8")).get("classes", [])]

    ann_dirs = [p for p in set_dir.rglob("ann") if p.is_dir()]
    records = []                                  # (img_path, [(title, poly), ...])
    geom = collections.Counter()
    stats = collections.Counter()
    seen_hash = set()
    for ad in ann_dirs:
        img_dir = ad.parent / "img"
        for ap in sorted(ad.glob("*.json")):
            stats["ann_files"] += 1
            try:
                ann = json.load(open(ap, encoding="utf-8"))
            except Exception:
                stats["bad_json"] += 1
                continue
            ip = find_image(img_dir, ap)
            if ip is None:
                stats["missing_image"] += 1
                continue
            digest = hashlib.md5(ip.read_bytes()).hexdigest()
            if digest in seen_hash:
                stats["duplicate_image"] += 1
                continue
            seen_hash.add(digest)
            size = ann.get("size") or {}
            h, w = size.get("height"), size.get("width")
            if not h or not w:
                im = cv2.imread(str(ip))
                if im is None:
                    stats["unreadable_image"] += 1
                    continue
                h, w = im.shape[:2]
            items = []
            for obj in ann.get("objects", []):
                for poly in object_polys(obj, h, w, geom):
                    items.append((obj["classTitle"], poly, w, h))
            if not items:
                stats["no_usable_objects"] += 1
                continue
            records.append((ip, items))

    if not records:
        print(f"[{name}] nothing converted. stats={dict(stats)} geometry={dict(geom)}")
        return

    used = collections.Counter(t for _, items in records for t, *_ in items)
    classes = [t for t in meta_order if t in used] + sorted(t for t in used if t not in meta_order)
    cid = {t: i for i, t in enumerate(classes)}

    rng = random.Random(SEED)
    idx = list(range(len(records)))
    rng.shuffle(idx)
    n_val = max(1, int(len(idx) * VAL_FRAC))
    val_set = set(idx[:n_val])

    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    for sp in ("train", "val"):
        (out / "images" / sp).mkdir(parents=True)
        (out / "labels" / sp).mkdir(parents=True)

    for i, (ip, items) in enumerate(records):
        sp = "val" if i in val_set else "train"
        stem = f"{name}_{i:05d}"
        shutil.copy2(ip, out / "images" / sp / (stem + ip.suffix.lower()))
        lines = []
        for title, poly, w, h in items:
            coords = []
            for x, y in poly:
                coords += [f"{min(max(x / w, 0), 1):.6f}", f"{min(max(y / h, 0), 1):.6f}"]
            lines.append(f"{cid[title]} " + " ".join(coords))
        (out / "labels" / sp / (stem + ".txt")).write_text("\n".join(lines) + "\n")

    yaml.safe_dump(
        {"path": out.resolve().as_posix(), "train": "images/train", "val": "images/val",
         "names": {i: c for i, c in enumerate(classes)}},
        open(out / "data.yaml", "w"), sort_keys=False)

    print(f"\n[{name}] from '{folder_name}'")
    print(f"  ann files: {stats['ann_files']}  kept images: {len(records)}  "
          f"train/val: {len(records) - n_val}/{n_val}")
    skipped = {k: v for k, v in stats.items() if k != "ann_files"}
    print(f"  skipped: {skipped or 'none'}   geometry types seen: {dict(geom)}")
    print(f"  classes ({len(classes)}), instances per class:")
    for c in classes:
        print(f"    {cid[c]:>2} {c:<22} {used[c]}")
    print(f"  wrote {out}\\data.yaml")


if __name__ == "__main__":
    if not SRC.exists():
        sys.exit(f"Not found: {SRC}\nRun this from the folder containing download_data.py.")
    for n, f in SETS.items():
        convert_set(n, f)
    print("\nDone. Next: look at overlays (see instructions), then train.")
