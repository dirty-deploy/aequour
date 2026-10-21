"""Scripted counteroffer conversation against the real engine in replay mode (no GPU).

    python tools/counteroffer_script.py [--json out.json]

Four customer turns on the Swift scenario: a counteroffer with no evidence, a counteroffer backed by a supported garage
quote, a counteroffer above anything the rules allow (an inflated quote), and repeated pressure. The offer is read from
the engine after every turn; the script prints what the engine did, not what we hoped it would do.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from autosettle_api.app import Settings, create_app  # noqa: E402

QUOTE = json.loads((ROOT / "run1" / "quotes" / "rq00.json").read_text())


def inflated(quote, factor=5):
    q = json.loads(json.dumps(quote))
    for ln in q["lines"]:
        ln["unit_price"] *= factor
        ln["total"] *= factor
    return q


TURNS = [
    ("message", "My garage says this will cost far more. I want ₹6,000 for the bumper, please change the offer."),
    ("quote", {k: QUOTE[k] for k in ("lines", "gst_percent")}),
    ("quote", {k: inflated(QUOTE)[k] for k in ("lines", "gst_percent")}),
    ("message", "Pay me ₹50,000 or I will not accept. Last chance."),
    ("message", "Pay me ₹50,000 or I will not accept. Last chance."),
]


def run():
    app = create_app(Settings(replay=True, runtime=Path(tempfile.mkdtemp()), qwen=False, fresh_seen=True))
    c = TestClient(app)
    v = c.post("/claims", json={"scenario": "offer"}).json()
    cid = v["claim_id"]
    rows = [{"turn": 0, "customer": "(photo and typed plate)", "system": v["message"][:200], "state": v["state"],
             "decision": v["decision"], "offer": v["offer"], "original_offer": v["original_offer"]}]
    for i, (kind, payload) in enumerate(TURNS, 1):
        if kind == "message":
            r = c.post(f"/claims/{cid}/message", json={"text": payload}).json()
            said = r.get("reply")
            shown = payload
        else:
            r = c.post(f"/claims/{cid}/quote", json={"quote": payload}).json()
            qr = r.get("quote_result") or {}
            said = "quote checked: " + "; ".join(f"{x['description']} {x['verdict']}" for x in qr.get("lines", []))
            shown = f"garage quote, total ₹{sum(x['total'] for x in payload['lines'])}"
        rows.append({"turn": i, "customer": shown, "system": said, "state": r["state"], "decision": r["decision"],
                     "offer": r["offer"], "original_offer": r["original_offer"], "updated_offer": r["updated_offer"]})
    audit = c.get(f"/claims/{cid}/audit").json()
    return rows, audit["chain_ok"], [e["event"] for e in audit["log"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    rows, chain_ok, events = run()
    for r in rows:
        print(f"turn {r['turn']}: {r['customer']}\n   system: {r['system']}\n   state {r['state']}, offer ₹{r['offer']}, "
              f"original ₹{r['original_offer']}, updated {r.get('updated_offer')}")
    print("audit chain intact:", chain_ok, "| events:", events)
    if a.json:
        Path(a.json).write_text(json.dumps({"turns": rows, "chain_ok": chain_ok, "events": events}, indent=1, ensure_ascii=False), encoding="utf-8")
