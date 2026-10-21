"""
Synthetic garage quotes (handoff item 12): rendered estimate images with known ground truth, used to measure
Qwen's quote reading and to exercise the dispute flow. SYNTHETIC: no real garage issued these.

    python -m autosettle_vision.quote_gen       -> runs/quotes/q*.png + q*.json (ground truth)
"""
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path("runs/quotes")
FONTS = [f for f in ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/times.ttf",
                     "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/segoeui.ttf"] if Path(f).exists()]
GARAGES = ["Shree Balaji Motors", "New Delhi Auto Works", "Sharma Car Care", "Royal Denting & Painting",
           "A-1 Auto Garage", "Gurgaon Car Clinic"]

# (description, type, typical unit price range)  scenario lines are drawn from these
PART_LINES = {
    "Front-bumper": [("Front Bumper (Genuine)", (2100, 2900)), ("Bumper Front Assy", (2000, 3200))],
    "Back-bumper": [("Rear Bumper", (2400, 4500))],
    "Hood": [("Bonnet Panel", (5200, 9000))],
    "Fender": [("Fender LH", (1500, 3600)), ("Front Fender RH", (1500, 3600))],
    "Headlight": [("Head Lamp Assy RH", (3000, 8000))],
    "Tail-light": [("Tail Lamp LH", (2400, 4200))],
    "Mirror": [("ORVM RH Electric", (1400, 4800))],
}
LABOUR = [("Labour - removing & refitting", (600, 1500)), ("Denting labour", (800, 2500)), ("Fitting charges", (500, 1200))]
PAINT = [("Painting (per panel)", (2000, 4500)), ("Paint & polish", (1800, 4000))]


def scenario(rng, parts):
    lines = []
    for p in parts:
        d, (lo, hi) = rng.choice(PART_LINES[p])
        u = rng.randrange(lo, hi, 10)
        lines.append({"description": d, "type": "part", "qty": 1, "unit_price": u, "total": u})
    for d, (lo, hi) in rng.sample(LABOUR, 1):
        u = rng.randrange(lo, hi, 50)
        lines.append({"description": d, "type": "labour", "qty": 1, "unit_price": u, "total": u})
    d, (lo, hi) = rng.choice(PAINT)
    q = len(parts)
    u = rng.randrange(lo, hi, 50)
    lines.append({"description": d, "type": "paint", "qty": q, "unit_price": u, "total": u * q})
    sub = sum(l["total"] for l in lines)
    return {"lines": lines, "gst_percent": 18, "grand_total": round(sub * 1.18)}


def render(q, rng, path):
    W, H = 1100, 1400
    img = Image.new("RGB", (W, H), (250, 250, 245))
    dr = ImageDraw.Draw(img)
    fpath = rng.choice(FONTS)
    big, mid, small = (ImageFont.truetype(fpath, s) for s in (44, 28, 24))
    y = 50
    dr.text((60, y), rng.choice(GARAGES), font=big, fill=(20, 20, 90)); y += 70
    dr.text((60, y), "ESTIMATE / QUOTATION   No. %d" % rng.randint(100, 999), font=mid, fill=(0, 0, 0)); y += 45
    dr.text((60, y), "Vehicle: %s   Date: %02d/10/2026" % (rng.choice(["Swift", "Nexon", "Creta", "i20"]), rng.randint(1, 20)),
            font=small, fill=(0, 0, 0)); y += 60
    cols = [60, 600, 720, 900]
    for x, h in zip(cols, ["Description", "Qty", "Rate", "Amount"]):
        dr.text((x, y), h, font=mid, fill=(0, 0, 0))
    y += 40
    dr.line((50, y, W - 50, y), fill=(0, 0, 0), width=2); y += 15
    for l in q["lines"]:
        dr.text((cols[0], y), l["description"], font=small, fill=(0, 0, 0))
        dr.text((cols[1], y), str(l["qty"]), font=small, fill=(0, 0, 0))
        dr.text((cols[2], y), f"{l['unit_price']:,}", font=small, fill=(0, 0, 0))
        dr.text((cols[3], y), f"{l['total']:,}", font=small, fill=(0, 0, 0))
        y += 42
    dr.line((50, y, W - 50, y), fill=(0, 0, 0), width=2); y += 20
    sub = sum(l["total"] for l in q["lines"])
    for lab, val in (("Sub total", sub), ("GST @ 18%", q["grand_total"] - sub), ("GRAND TOTAL (Rs.)", q["grand_total"])):
        dr.text((560, y), lab, font=mid, fill=(0, 0, 0))
        dr.text((cols[3], y), f"{val:,}", font=mid, fill=(0, 0, 0)); y += 42
    dr.text((60, H - 120), "Authorised signatory", font=small, fill=(60, 60, 60))
    # phone-photo look: slight rotation, perspective, blur, noise, uneven light
    a = np.array(img)
    ang = rng.uniform(-4, 4)
    M = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
    a = cv2.warpAffine(a, M, (W, H), borderValue=(90, 80, 70))
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    j = lambda: rng.uniform(-30, 30)
    dst = np.float32([[j(), j()], [W + j(), j()], [W + j(), H + j()], [j(), H + j()]])
    a = cv2.warpPerspective(a, cv2.getPerspectiveTransform(src, dst), (W, H), borderValue=(90, 80, 70))
    grad = np.tile(np.linspace(rng.uniform(0.75, 0.9), 1.05, W)[None, :, None], (H, 1, 3))
    a = np.clip(a * grad + np.random.default_rng(rng.randint(0, 9999)).normal(0, 6, a.shape), 0, 255).astype(np.uint8)
    a = cv2.GaussianBlur(a, (3, 3), 0)
    Image.fromarray(a).save(path, quality=85)


SCENARIOS = [["Front-bumper"], ["Front-bumper", "Fender"], ["Hood"], ["Headlight", "Front-bumper"],
             ["Back-bumper", "Tail-light"], ["Mirror"], ["Fender"], ["Front-bumper", "Hood"], ["Back-bumper"], ["Headlight"]]


def main(seed=7):
    rng = random.Random(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    for i, parts in enumerate(SCENARIOS):
        q = scenario(rng, parts)
        render(q, rng, OUT / f"q{i:02d}.jpg")
        (OUT / f"q{i:02d}.json").write_text(json.dumps({"parts": parts, **q}, indent=1))
    print(f"{len(SCENARIOS)} quotes in {OUT}")


if __name__ == "__main__":
    main()
