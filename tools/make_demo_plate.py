"""Render a SYNTHETIC number-plate photo for the demo claim (plate of simulated policy POL-DEMO-001)."""
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

text = sys.argv[1] if len(sys.argv) > 1 else "DL 3C AB 1234"
out = sys.argv[2] if len(sys.argv) > 2 else "test_photos/demo/00_plate_DL3CAB1234.jpg"
W, H = 1280, 900
img = Image.new("RGB", (W, H), (40, 70, 140))                      # blue car body
d = ImageDraw.Draw(img)
d.rectangle((0, 560, W, H), fill=(25, 25, 28))                    # bumper
d.rounded_rectangle((330, 360, 950, 500), 12, fill=(250, 250, 250), outline=(0, 0, 0), width=6)
f = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 96)
d.text((640, 430), text, font=f, fill=(0, 0, 0), anchor="mm")
d.text((40, 40), "SYNTHETIC DEMO IMAGE", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28), fill=(220, 220, 220))
a = np.array(img)
M = cv2.getPerspectiveTransform(np.float32([[0, 0], [W, 0], [W, H], [0, H]]),
                                np.float32([[30, 20], [W - 10, 0], [W - 40, H - 10], [0, H - 30]]))
a = cv2.warpPerspective(a, M, (W, H), borderValue=(40, 70, 140))
a = np.clip(a + np.random.default_rng(1).normal(0, 5, a.shape), 0, 255).astype(np.uint8)
from pathlib import Path
Path(out).parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(a).save(out, quality=88)
print(out)
