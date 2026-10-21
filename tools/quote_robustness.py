"""Task 5 part 2: 15 SYNTHETIC garage quotes (PIL), read by Qwen3-VL, then checked by the dispute flow.

    python tools/quote_robustness.py render                       (CPU: images + ground truth -> run1/quotes/)
    python tools/run_guarded.py --tag task5q -- env/Scripts/python.exe tools/quote_robustness.py read   (GPU, cached)

Claim for every quote: the demo claim (Swift 2023, front bumper broken/moderate + fender surface damage/moderate).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "run1" / "quotes"
CACHE = ROOT / "run1" / "cache" / "quote_reads.json"

P, L, Pt, O = "part", "labour", "paint", "other"
# (variant, description of the trap, lines: (text, type, qty, unit))
QUOTES = [
    ("clean", "honest quote, garage naming", [("Bumper Front Assy", P, 1, 2250), ("Labour", L, 1, 1100), ("Painting", Pt, 1, 4650)]),
    ("blur", "honest quote", [("Front Bumper (Genuine)", P, 1, 2250), ("Fitting charges", L, 1, 900), ("Paint & polish", Pt, 1, 3800)]),
    ("rotate", "padded lines", [("Bumper Front Assy", P, 1, 2250), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 4000),
                                 ("Consumables", O, 1, 450), ("Misc charges", O, 1, 300), ("Car wash", O, 1, 250)]),
    ("lowcon", "inflated part price", [("Front Bumper", P, 1, 3900), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 4000)]),
    ("clean", "line for an undamaged part (bonnet)", [("Bumper Front Assy", P, 1, 2250), ("Bonnet Panel", P, 1, 5450),
                                                       ("Labour", L, 1, 1500), ("Painting", Pt, 1, 6000)]),
    ("blur", "quantity 2 on the bumper", [("Front Bumper", P, 2, 2250), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 4000)]),
    ("rotate", "undamaged headlamp added", [("Bumper Front Assy", P, 1, 2250), ("Head Lamp Assy RH", P, 1, 7500),
                                             ("Labour", L, 1, 1200), ("Painting", Pt, 1, 4000)]),
    ("lowcon", "fender priced as a replacement (photos show a repaint)", [("Bumper Front Assy", P, 1, 2250),
                                                                         ("Fr Fender LH", P, 1, 1500), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 4000)]),
    ("clean", "inflated labour", [("Front Bumper", P, 1, 2250), ("Labour", L, 1, 6000), ("Painting", Pt, 1, 4000)]),
    ("blur", "inflated painting", [("Front Bumper", P, 1, 2250), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 9000)]),
    ("rotate", "part 7% above reference (inside tolerance)", [("Bumper Front Assy", P, 1, 2400), ("Labour", L, 1, 900), ("Painting", Pt, 1, 3000)]),
    ("lowcon", "abbreviated naming", [("BUMPER FR", P, 1, 2250), ("Denting & painting", Pt, 1, 4000), ("R&R labour", L, 1, 800)]),
    ("clean", "honest, cheaper than our estimate", [("Front Bumper", P, 1, 2100), ("Labour", L, 1, 700), ("Painting", Pt, 1, 2500)]),
    ("blur", "undamaged tail lamp added", [("Bumper Front Assy", P, 1, 2250), ("Tail Lamp LH", P, 1, 2600), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 4000)]),
    ("rotate+lowcon", "inflated part + padded line", [("Front Bumper", P, 1, 2700), ("Labour", L, 1, 1000), ("Painting", Pt, 1, 4000), ("Service charge", O, 1, 500)]),
]


def render():
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    OUT.mkdir(parents=True, exist_ok=True)
    f_big = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40)
    f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 26)
    for i, (variant, trap, lines) in enumerate(QUOTES):
        W, H = 1100, 1300
        img = Image.new("RGB", (W, H), (252, 252, 248))
        d = ImageDraw.Draw(img)
        d.text((60, 50), "Sharma Car Care, Gurugram", font=f_big, fill=(20, 20, 90))
        d.text((60, 110), f"ESTIMATE No. {300 + i}   Vehicle: Maruti Swift   Date: 21/10/2026", font=f, fill=(0, 0, 0))
        y = 190
        for x, h in zip((60, 620, 730, 900), ("Description", "Qty", "Rate", "Amount")):
            d.text((x, y), h, font=f, fill=(0, 0, 0))
        y += 40
        d.line((50, y, W - 50, y), fill=(0, 0, 0), width=2)
        y += 15
        gt = []
        for text, typ, qty, unit in lines:
            for x, s in zip((60, 620, 730, 900), (text, str(qty), f"{unit:,}", f"{unit * qty:,}")):
                d.text((x, y), s, font=f, fill=(0, 0, 0))
            gt.append({"description": text, "type": typ, "qty": qty, "unit_price": unit, "total": unit * qty})
            y += 44
        d.line((50, y, W - 50, y), fill=(0, 0, 0), width=2)
        y += 20
        sub = sum(g["total"] for g in gt)
        gst = round(sub * 0.18)
        for lab, val in (("Sub total", sub), ("GST @ 18%", gst), ("GRAND TOTAL (Rs.)", sub + gst)):
            d.text((560, y), lab, font=f, fill=(0, 0, 0))
            d.text((900, y), f"{val:,}", font=f, fill=(0, 0, 0))
            y += 42
        a = np.array(img)
        if "blur" in variant:
            a = cv2.GaussianBlur(a, (0, 0), 2.2)
        if "rotate" in variant:
            M = cv2.getRotationMatrix2D((W / 2, H / 2), 5, 1.0)
            a = cv2.warpAffine(a, M, (W, H), borderValue=(110, 100, 90))
        if "lowcon" in variant:
            a = (128 + (a.astype(np.float32) - 128) * 0.35).clip(0, 255).astype(np.uint8)
        Image.fromarray(a).save(OUT / f"rq{i:02d}.jpg", quality=88)
        (OUT / f"rq{i:02d}.json").write_text(json.dumps({"variant": variant, "trap": trap, "lines": gt, "gst_percent": 18,
                                                         "grand_total": sub + gst}, indent=1))
    print(f"{len(QUOTES)} quotes -> {OUT}")


def read():
    import thermal as T
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    q, n = None, 0
    for gtp in sorted(OUT.glob("rq*.json")):
        if gtp.stem in cache:
            continue
        if q is None:
            import torch
            torch.set_num_threads(4)
            from autosettle_vision.qwen import QwenVL
            T.cooldown_until(65, 72)
            q = QwenVL()
        T.cooldown_until(65, 72, timeout=180)
        n += 1
        if n % 10 == 0:
            time.sleep(10)
        parsed, raw = q.read_quote(str(gtp.with_suffix(".jpg")))
        cache[gtp.stem] = {"parsed": parsed, "raw": raw}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        print(gtp.stem, "read", flush=True)
    score(cache)


def score(cache):
    from autosettle_engine.dispute import ClaimSession
    from autosettle_engine.tests.helpers import RC, det, policy, vision
    rows = []
    for gtp in sorted(OUT.glob("rq*.json")):
        gt = json.loads(gtp.read_text())
        if gtp.stem not in cache:
            rows.append({"quote": gtp.stem, "variant": gt["variant"], "trap": gt["trap"], "read": False})
            continue
        rd = cache[gtp.stem]["parsed"]
        match = sum(1 for g in gt["lines"] if any(r["total"] == g["total"] and r["type"] == g["type"] for r in rd["lines"]))
        pol = policy("Swift", reg="2023-06-01")
        s = ClaimSession(pol, RC)
        res = s.submit(vision(det("Front-bumper", "Broken part", "moderate", 0.91, 0.62),
                              det("Fender", "Surface damage", "moderate", 0.88, 0.55), plate=pol.plate))
        chk = s.dispute(rd)
        rows.append({"quote": gtp.stem, "variant": gt["variant"], "trap": gt["trap"], "read": True,
                     "lines_exact": f"{match}/{len(gt['lines'])}", "grand_total_ok": rd.get("grand_total") == gt["grand_total"],
                     "offer": res["offer"], "updated": chk["updated_offer"], "ceiling": res["ceiling"],
                     "verdicts": [f"{v['description']}: {v['verdict']}" for v in chk["verdicts"]]})
    (ROOT / "run1" / "quote_robustness.json").write_text(json.dumps(rows, indent=1))
    for r in rows:
        print(r)


if __name__ == "__main__":
    {"render": render, "read": read, "score": lambda: score(json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {})}[sys.argv[1]]()
