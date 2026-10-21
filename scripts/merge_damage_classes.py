#!/usr/bin/env python3
"""
Merge the 8 fine-grained damage classes in yolo/damage into 4 coarser ones.

    Missing part                      -> Missing part
    Broken part, Cracked              -> Broken part
    Scratch, Paint chip, Flaking,
      Corrosion                       -> Surface damage
    Dent                              -> Dent

Why: the repair ACTION (repaint / repair / replace) and the damaged AREA drive the price,
not the exact surface-damage label, and the confusion matrix shows the four surface classes
are mostly confused with each other. Cracked has too few examples (76) to learn alone.
This is a hypothesis to test: compare per-class mAP against the 8-class run.

Run from the folder containing download_data.py, with the env active:

    python merge_damage_classes.py

Reads  ./yolo/damage          Writes ./yolo/damage_merged   (the original is left untouched)
"""
import pathlib, shutil, sys
import yaml

HERE = pathlib.Path(__file__).parent
SRC = HERE / "yolo" / "damage"
OUT = HERE / "yolo" / "damage_merged"

MERGE = {
    "Missing part": "Missing part",
    "Broken part": "Broken part",
    "Cracked": "Broken part",
    "Scratch": "Surface damage",
    "Paint chip": "Surface damage",
    "Flaking": "Surface damage",
    "Corrosion": "Surface damage",
    "Dent": "Dent",
}
NEW = ["Missing part", "Broken part", "Surface damage", "Dent"]


def main():
    ymlp = SRC / "data.yaml"
    if not ymlp.exists():
        sys.exit(f"Not found: {ymlp}. Run convert_hf_to_yolo.py first.")
    names = yaml.safe_load(open(ymlp))["names"]
    names = dict(names) if isinstance(names, dict) else dict(enumerate(names))
    unknown = [n for n in names.values() if n not in MERGE]
    if unknown:
        sys.exit(f"Classes not in the merge table: {unknown}. Edit MERGE in this file.")
    old2new = {int(i): NEW.index(MERGE[n]) for i, n in names.items()}

    if OUT.exists():
        shutil.rmtree(OUT)
    counts = {n: 0 for n in NEW}
    n_img = 0
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True)
        (OUT / "labels" / split).mkdir(parents=True)
        for img in sorted((SRC / "images" / split).iterdir()):
            lbl = SRC / "labels" / split / (img.stem + ".txt")
            if not lbl.exists():
                continue
            lines = []
            for line in lbl.read_text().splitlines():
                p = line.split()
                if len(p) < 7:
                    continue
                new = old2new[int(float(p[0]))]
                counts[NEW[new]] += 1
                lines.append(" ".join([str(new)] + p[1:]))
            shutil.copy2(img, OUT / "images" / split / img.name)
            (OUT / "labels" / split / lbl.name).write_text("\n".join(lines) + ("\n" if lines else ""))
            n_img += 1

    yaml.safe_dump(
        {"path": OUT.resolve().as_posix(), "train": "images/train", "val": "images/val",
         "names": {i: n for i, n in enumerate(NEW)}},
        open(OUT / "data.yaml", "w"), sort_keys=False)

    print(f"Wrote {OUT}  ({n_img} images)")
    print("Instances per merged class:")
    for n in NEW:
        print(f"  {n:<16} {counts[n]}")
    print("\nTrain with:")
    print("  yolo segment train data=yolo/damage_merged/data.yaml model=yolo11s-seg.pt "
          "epochs=100 imgsz=640 batch=8 workers=2 device=0 patience=30 name=damage_merged_s")


if __name__ == "__main__":
    main()
