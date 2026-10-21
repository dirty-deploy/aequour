"""Run every demo scenario N times against a running server and report pass/fail and timings.
    python tools/demo_check.py [--url http://127.0.0.1:8000] [--runs 3]
Pass = the decision equals the scenario's expected decision and, for the injection scenario, the offer is unchanged after the message."""
import argparse
import json
import time
import urllib.request


def call(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers={"content-type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()), round(time.time() - t0, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    print(call(a.url + "/health")[0])
    results = []
    for s in call(a.url + "/scenarios")[0]:
        for n in range(a.runs):
            c, t = call(a.url + "/claims", {"scenario": s["id"]})
            ok = c["decision"] == s["expect"]
            extra = ""
            if s.get("message"):
                r, t2 = call(f"{a.url}/claims/{c['claim_id']}/message", {"text": s["message"]})
                ok = ok and r["offer"] == c["offer"] and r["lines"] == c["lines"]
                extra = f"offer {c['offer']} -> {r['offer']}"
                t += t2
            audit, _ = call(f"{a.url}/claims/{c['claim_id']}/audit")
            ok = ok and audit["chain_ok"]
            results.append((s["id"], n + 1, "PASS" if ok else "FAIL", c["decision"], c["offer"], t, extra))
            print(f"{s['id']:<10} run {n + 1}  {'PASS' if ok else 'FAIL'}  decision {c['decision']:<9} offer {c['offer']}  {t:.2f}s  {extra}")
    print(f"\n{sum(1 for r in results if r[2] == 'PASS')} of {len(results)} runs passed")


if __name__ == "__main__":
    main()
