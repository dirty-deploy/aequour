"""Smoke test for a demo machine: replay mode, no GPU, no weights.   python tools/smoke.py   (run.ps1 smoke | ./run.sh smoke)

Starts the API in-process, walks the five recorded scenarios, the quote dispute, the injection message, the recorded
synthetic walk-around and two attack scripts, then starts the real server on a free port and asks /health. Prints PASS or
FAIL per step with the expected result, and exits non-zero if any step fails."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from autosettle_api.app import Settings, create_app  # noqa: E402

RESULTS = []


def step(name, expected, fn):
    try:
        got = fn()
        ok = got is True or (isinstance(got, tuple) and got[0])
        note = got[1] if isinstance(got, tuple) else ""
    except Exception as e:                                   # a crash is a failed step
        ok, note = False, f"{type(e).__name__}: {e}"
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n        expected: {expected}" + (f"\n        got: {note}" if note else ""))


def main():
    app = create_app(Settings(replay=True, runtime=Path(tempfile.mkdtemp()), qwen=False, fresh_seen=True))
    c = TestClient(app)
    quote = json.loads((ROOT / "run1" / "quotes" / "rq00.json").read_text())
    q = {"lines": quote["lines"], "gst_percent": quote.get("gst_percent")}

    def scenario(sid):
        return c.post("/claims", json={"scenario": sid}).json()

    step("health says REPLAY", "mode REPLAY", lambda: (c.get("/health").json()["mode"] == "REPLAY", c.get("/health").text))
    step("scenario offer", "OFFER, ₹2,763", lambda: ((v := scenario("offer"))["decision"] == "OFFER" and v["offer"] == 2763, f"{v['decision']} {v['offer']}"))
    step("scenario surveyor", "SURVEYOR, no offer", lambda: ((v := scenario("surveyor"))["decision"] == "SURVEYOR" and v["offer"] is None, v["decision"]))
    step("scenario street", "ASK_MORE, no offer", lambda: ((v := scenario("street"))["decision"] == "ASK_MORE" and v["offer"] is None, v["decision"]))

    def injection():
        v = scenario("injection")
        r = c.post(f"/claims/{v['claim_id']}/message", json={"text": next(x for x in c.get("/scenarios").json() if x["id"] == "injection")["message"]}).json()
        return r["offer"] == v["offer"] == 2763, f"offer {v['offer']} -> {r['offer']}"
    step("scenario injection", "offer stays ₹2,763", injection)

    def counter():
        v = scenario("counter")
        t = c.get(f"/claims/{v['claim_id']}/transcript").json()
        return (v["original_offer"], v["offer"]) == (2763, 3063) and t["chain_ok"], f"{v['original_offer']} -> {v['offer']}, {len(t['turns'])} turns"
    step("scenario counteroffer", "₹2,763 -> ₹3,063 on a supported quote, then no change; transcript chain intact", counter)

    def dispute():
        cid = scenario("offer")["claim_id"]
        r = c.post(f"/claims/{cid}/quote", json={"quote": q}).json()
        return r["offer"] == 3063 and r["original_offer"] == 2763, f"{r['original_offer']} -> {r['offer']}"
    step("quote dispute (recorded quote)", "₹2,763 -> ₹3,063", dispute)

    def inflated():
        cid = scenario("offer")["claim_id"]
        big = {"lines": [{**ln, "unit_price": ln["unit_price"] * 5, "total": ln["total"] * 5} for ln in q["lines"]]}
        r = c.post(f"/claims/{cid}/quote", json={"quote": big}).json()
        return r["offer"] == 2763, f"offer {r['offer']}"
    step("inflated quote", "offer stays ₹2,763", inflated)

    def video():
        cid = c.post("/claims", json={"policy_id": "POL-DEMO-001", "plate_text": "DL3CAB1234"}).json()["claim_id"]
        v = c.post(f"/claims/{cid}/video", data={"recorded": "synthetic_walkaround"}).json()
        return v["decision"] == "OFFER" and v["offer"] == 2763 and len(v["video"]["keyframes"]) == 12, f"{v['decision']} {v['offer']}, SYNTHETIC={v['video']['synthetic']}"
    step("recorded synthetic walk-around", "OFFER ₹2,763 from 12 keyframes (SYNTHETIC)", video)

    def bad_video():
        cid = c.post("/claims", json={"policy_id": "POL-DEMO-001"}).json()["claim_id"]
        r = c.post(f"/claims/{cid}/video", files={"file": ("x.mp4", b"not a video", "video/mp4")})
        return r.status_code == 422, f"HTTP {r.status_code}"
    step("a file that is not a video", "refused (HTTP 422)", bad_video)

    def attacks():
        out = [c.post(f"/attacks/{n}/run").json() for n in ("prompt_injection_in_chat", "inflated_part_price")]
        return all(o["held"] and o["offer_unchanged"] for o in out), "; ".join(f"{o['name']}: held={o['held']}" for o in out)
    step("two attacks through the attack runner", "both held, offer unchanged", attacks)

    def synthetic_quote():
        import random
        sys.path.insert(0, str(ROOT / "tools"))
        import make_quote
        from autosettle_vision import quote_gen
        v = scenario("offer")
        qq = make_quote.lines_to_quote(v["lines"], {"part": 2.5})
        out = Path(tempfile.mkdtemp()) / "synthetic_quote.jpg"
        quote_gen.render(qq, random.Random(11), out, stamp="SYNTHETIC")
        r = c.post(f"/claims/{v['claim_id']}/quote", json={"quote": qq}).json()
        flagged = [x["verdict"] for x in r["quote_result"]["lines"] if x["description"].endswith("Assy")]
        return out.stat().st_size > 5000 and flagged == ["above_range"], f"image {out.stat().st_size // 1024} KiB, inflated part: {flagged}, offer {r['original_offer']} -> {r['offer']}"
    step("tools/make_quote.py: a SYNTHETIC quote with one inflated line", "image written; the inflated part is flagged above range", synthetic_quote)

    def range_hidden():
        cid = scenario("offer")["claim_id"]
        return "ceiling" not in c.get(f"/claims/{cid}").text.lower() and c.get(f"/adjuster/{cid}/range").json()["applies"], "customer view clean, adjuster range present"
    step("allowable range is adjuster-only", "no upper bound in the customer view; adjuster route has it", range_hidden)

    def server():
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        p = subprocess.Popen([sys.executable, "-m", "autosettle_api", "--replay", "--port", str(port)], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                time.sleep(0.5)
                try:
                    h = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).read())
                    page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).status
                    return h["mode"] == "REPLAY" and page == 200, f"/health {h}, page HTTP {page}"
                except Exception:
                    continue
            return False, "the server did not answer in 20 s"
        finally:
            p.terminate()
    step("python -m autosettle_api --replay answers", "/health REPLAY and the page loads", server)

    failed = RESULTS.count(False)
    print(f"\n{len(RESULTS) - failed} of {len(RESULTS)} steps passed" + ("" if not failed else f", {failed} FAILED"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
