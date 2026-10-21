"""Numbered contact sheet of a folder of images (for writing ground-truth notes).   python tools/contact_sheet.py DIR OUT.jpg [start] [count]"""
import sys
from pathlib import Path

import cv2
import numpy as np

src, out = Path(sys.argv[1]), sys.argv[2]
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
count = int(sys.argv[4]) if len(sys.argv) > 4 else 12
files = sorted(p for p in src.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[start:start + count]
tiles = []
for p in files:
    im = cv2.imread(str(p))
    h, w = im.shape[:2]
    s = 480 / max(h, w)
    im = cv2.resize(im, (int(w * s), int(h * s)))
    tile = np.full((480, 480, 3), 30, np.uint8)
    tile[:im.shape[0], :im.shape[1]] = im
    cv2.rectangle(tile, (0, 0), (480, 30), (0, 0, 0), -1)
    cv2.putText(tile, p.name[:40], (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    tiles.append(tile)
while len(tiles) % 3:
    tiles.append(np.full((480, 480, 3), 30, np.uint8))
rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
print(len(files), "images ->", out)
