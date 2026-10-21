import copy
from autosettle_engine import engine as E, config as C

RC = E.RateCard()


def policy(model="Swift", reg="2023-06-01", cc=1197, idv=600000, plate="DL3CAB1234"):
    return E.Policy("P-" + model, plate, "X", model, reg, cc, idv)


def det(part="Front-bumper", dc="Broken part", sev="moderate", pc=0.9, dcf=0.6):
    return {"part_class": part, "part_conf": pc, "damage_class": dc, "damage_conf": dcf, "severity": sev,
            "damage_area_fraction": 0.1, "part_polygon": [[0, 0]], "damage_polygon": [[0, 0]]}


def vision(*dets, plate="DL 3C AB 1234", flags=(), integrity=()):
    return {"image_id": "t.jpg", "plate_read": plate, "integrity_flags": list(integrity),
            "flags": list(flags), "detections": list(dets) or [det()]}


def quote(parts=(), labour=0, paint=0, qty=1, descr_suffix=""):
    lines = []
    for name, price in parts:
        lines.append({"description": name + descr_suffix, "type": "part", "qty": qty, "unit_price": price, "total": price * qty})
    if labour:
        lines.append({"description": "Labour", "type": "labour", "qty": 1, "unit_price": labour, "total": labour})
    if paint:
        lines.append({"description": "Painting", "type": "paint", "qty": 1, "unit_price": paint, "total": paint})
    return {"lines": lines, "gst_percent": 18, "grand_total": sum(l["total"] for l in lines)}
