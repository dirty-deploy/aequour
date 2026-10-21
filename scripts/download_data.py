#!/usr/bin/env python3
"""
Auto-Settle AI: download and sanity-check training data.

Run on your own machine or in Colab/Kaggle (not in the Claude sandbox, which cannot reach these hosts).

    pip install roboflow huggingface_hub ultralytics opencv-python pillow numpy
    export ROBOFLOW_API_KEY=...        # free key from roboflow.com -> Settings -> API
    python download_data.py            # all sources
    python download_data.py roboflow   # or: hf | carparts | inspect

Output goes to ./data/<source>/ . Afterwards open ./data/_preview/*.jpg and LOOK at the
overlays before training. Wrong labels cost more than missing data.
"""
import os, sys, glob, random, json, pathlib

ROOT = pathlib.Path(__file__).parent / "data"
ROOT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- sources
ROBOFLOW_WORKSPACE = "automobile-damage-detection"      # from the Universe URL
ROBOFLOW_PROJECT = "automobile-damage-detection"
HF_REPO = "AshimaVinod/car-parts-and-damage-dataset"    # 1,812 images, MIT as listed (see DATA.md note)


def get_roboflow():
    from roboflow import Roboflow
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        sys.exit("Set ROBOFLOW_API_KEY first (free key: roboflow.com -> Settings -> API).")
    proj = Roboflow(api_key=key).workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
    versions = proj.versions()
    if not versions:
        sys.exit("No versions found for the Roboflow project.")
    latest = max(versions, key=lambda v: int(str(v.version)))
    out = ROOT / "roboflow_damage"
    print(f"Roboflow: downloading version {latest.version} as yolov8 -> {out}")
    # 'yolov8' exports boxes for detection projects and polygons for segmentation projects.
    latest.download("yolov8", location=str(out))
    return out


def get_hf():
    from huggingface_hub import snapshot_download
    out = ROOT / "hf_parts_damage"
    print(f"Hugging Face: downloading {HF_REPO} (about 3.3 GB) -> {out}")
    snapshot_download(repo_id=HF_REPO, repo_type="dataset", local_dir=str(out))
    return out


def get_carparts():
    # Ultralytics fetches Carparts-seg (3,833 images, 23 classes) on first use of its yaml.
    from ultralytics.data.utils import check_det_dataset
    print("Ultralytics: fetching carparts-seg ...")
    info = check_det_dataset("carparts-seg.yaml")
    print("Carparts-seg path:", info.get("path"))
    return pathlib.Path(str(info.get("path")))


# ---------------------------------------------------------------- inspection
def read_yolo_label(path):
    """Return list of (class_id, [(x,y),...] normalised). 5 numbers = box, more = polygon."""
    objs = []
    for line in open(path).read().strip().splitlines():
        p = line.split()
        if len(p) < 5:
            continue
        cls, vals = int(float(p[0])), list(map(float, p[1:]))
        if len(vals) == 4:                      # cx, cy, w, h
            cx, cy, w, h = vals
            pts = [(cx - w/2, cy - h/2), (cx + w/2, cy - h/2), (cx + w/2, cy + h/2), (cx - w/2, cy + h/2)]
            objs.append((cls, pts, "box"))
        else:
            pts = list(zip(vals[0::2], vals[1::2]))
            objs.append((cls, pts, "poly"))
    return objs


def overlay(img_path, lbl_path, names, out_path):
    import cv2, numpy as np
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    layer = img.copy()
    kinds = set()
    for cls, pts, kind in read_yolo_label(lbl_path):
        kinds.add(kind)
        poly = np.array([[int(x * w), int(y * h)] for x, y in pts], np.int32)
        colour = (int(37 * (cls + 3)) % 255, int(91 * (cls + 1)) % 255, int(53 * (cls + 5)) % 255)
        if kind == "poly":
            cv2.fillPoly(layer, [poly], colour)
        cv2.polylines(img, [poly], True, colour, 3)
        label = names[cls] if cls < len(names) else str(cls)
        cv2.putText(img, label, tuple(poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    img = cv2.addWeighted(layer, 0.35, img, 0.65, 0)
    cv2.imwrite(str(out_path), img)
    return kinds


def inspect(folder, n=12):
    folder = pathlib.Path(folder)
    yamls = list(folder.rglob("data.yaml")) + list(folder.rglob("*.yaml"))
    names = []
    for y in yamls:
        try:
            import yaml
            d = yaml.safe_load(open(y))
            nm = d.get("names")
            names = list(nm.values()) if isinstance(nm, dict) else (nm or [])
            if names:
                break
        except Exception:
            pass
    labels = [p for p in folder.rglob("*.txt") if "labels" in p.relative_to(folder).parts]
    images = {p.stem: p for p in folder.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png") and "labels" not in str(p)}
    pairs = [(images[l.stem], l) for l in labels if l.stem in images]
    prev = ROOT / "_preview"
    prev.mkdir(exist_ok=True)
    print(f"\n{folder.name}: {len(images)} images, {len(labels)} label files, classes ({len(names)}): {names}")
    if not pairs:
        print("  No YOLO-format image/label pairs found. Check the folder layout by hand.")
        return
    random.seed(0)
    kinds_seen = set()
    for i, (ip, lp) in enumerate(random.sample(pairs, min(n, len(pairs)))):
        k = overlay(ip, lp, names, prev / f"{folder.name}_{i:02d}.jpg")
        kinds_seen |= (k or set())
    verdict = "polygons (usable for segmentation)" if "poly" in kinds_seen else "boxes only (detection only; use SAM to get masks)"
    print(f"  Label type: {verdict}")
    print(f"  Overlays written to {prev}")


def write_data_md():
    md = ROOT / "DATA.md"
    if md.exists():
        return
    md.write_text("""# Data sources (fill in counts after download)

| Source | Use | Licence as listed | Notes |
|---|---|---|---|
| Roboflow Automobile Damage Detection | damage + location | CC BY 4.0 | check box vs polygon |
| HF AshimaVinod/car-parts-and-damage-dataset | parts + damage polygons | MIT (listed) | looks like a copy of a CC BY 4.0 Roboflow set; give attribution |
| Ultralytics Carparts-seg | part masks | see Ultralytics docs | no fender/quarter-panel class |
| CarDD (official site) | evaluation only | non-commercial research | do not train on the test split |
""")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    folders = []
    if which in ("all", "roboflow"):
        folders.append(get_roboflow())
    if which in ("all", "carparts"):
        folders.append(get_carparts())
    if which in ("all", "hf"):
        folders.append(get_hf())
    if which == "inspect":
        folders.append(pathlib.Path(__file__).parent / "datasets" / "carparts-seg")
    for f in folders:
        inspect(f)
    write_data_md()
    print("\nDone. Now open the preview images and check the labels by eye.")
