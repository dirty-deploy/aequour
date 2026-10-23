"""Read-only check that this machine is ready for the demo.   python tools/preflight.py [--port 8000] [--expect live|replay] [--json FILE]
(run.ps1 preflight | ./run.sh preflight)

It loads no model, starts no server and writes nothing (only `--json FILE`, if you pass it). One line per check: PASS, WARN or FAIL,
then READY or NOT READY. Exit code 0 unless a check FAILed."""
import argparse
import hashlib
import importlib
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEMO_BRANCHES = ("finals-video-price", "main")
MIN_FREE_MIB = 6000
HOT_C = 75
WEIGHTS = ("parts_s_best.pt", "dent_det_best.pt", "damage_merged_s_best.pt")        # the files autosettle_vision/pipeline.py loads, in backup/


# ---------------------------------------------------------------- pure functions (tested without a GPU or a server)
def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def needed_photos(replay_dir):
    """Every distinct (source_file, sha256) named by the recorded scenarios and the recorded synthetic walk-arounds."""
    out = set()
    for f in list(Path(replay_dir).glob("*.json")) + list((Path(replay_dir) / "video").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if rec.get("source_file") and rec.get("sha256"):
            out.add((rec["source_file"], rec["sha256"]))
    return sorted(out)


def photo_status(folder, pairs):
    """[(source_file, 'ok' | 'missing' | 'wrong hash')]: a file only counts if its SHA-256 equals the recorded one."""
    res = []
    for name, sha in pairs:
        p = Path(folder) / name
        if not p.is_file():
            res.append((name, "missing"))
        elif sha256_of(p) != sha:
            res.append((name, "wrong hash"))
        else:
            res.append((name, "ok"))
    return res


def parse_gpu(text):
    """First line of `nvidia-smi --query-gpu=temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits`."""
    try:
        t, used, total = [int(x.strip()) for x in text.strip().splitlines()[0].split(",")[:3]]
    except (ValueError, IndexError):
        return None
    return {"temp_c": t, "used_mib": used, "total_mib": total, "free_mib": total - used}


def gpu_verdict(g):
    if g is None:
        return "WARN", "nvidia-smi gave no readable answer"
    msg = f"{g['temp_c']} C, {g['used_mib']} of {g['total_mib']} MiB used ({g['free_mib']} MiB free)"
    if g["free_mib"] < MIN_FREE_MIB:
        return "WARN", msg + f"; under {MIN_FREE_MIB} MiB free, close other GPU programs before live mode"
    if g["temp_c"] >= HOT_C:
        return "WARN", msg + f"; {HOT_C} C or more, let it cool before live mode"
    return "PASS", msg


def branch_verdict(branch, dirty):
    if not branch:
        return "WARN", "not on a branch (detached HEAD or no git)"
    msg = f"on {branch}"
    state = "WARN" if branch not in DEMO_BRANCHES else "PASS"
    if state == "WARN":
        msg += f" (the demo branch is {DEMO_BRANCHES[0]})"
    if dirty:
        state, msg = "WARN", msg + "; uncommitted changes to tracked files"
    return state, msg


def summarise(results):
    """results: [(status, name, detail)] -> ('READY' | 'NOT READY', exit code). Only a FAIL makes it not ready."""
    bad = any(s == "FAIL" for s, _, _ in results)
    return ("NOT READY", 1) if bad else ("READY", 0)


def port_verdict(port, health, expect):
    """health is None when the port is free, else the /health dict (or {} if the occupant did not answer as Aequour)."""
    if health is None:
        return "PASS", f"port {port} is free"
    if not health:
        return "WARN", f"port {port} is in use by something that is not an Aequour server"
    msg = f"port {port} is in use: mode {health.get('mode')}, video {health.get('video')}, qwen {health.get('qwen')}, build {health.get('build')}"
    if expect and str(health.get("mode", "")).upper() != expect.upper():
        return "WARN", msg + f"; expected {expect.upper()}"
    return "PASS", msg


# ---------------------------------------------------------------- the checks
def run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def check_git():
    rc, out = run(["git", "branch", "--show-current"])
    branch = out.strip() if rc == 0 else ""
    rc2, st = run(["git", "status", "--porcelain", "--untracked-files=no"])
    return branch_verdict(branch, bool(st.strip()) if rc2 == 0 else False)


def check_python():
    out, bad = [], []
    for m in ("fastapi", "uvicorn", "cv2", "numpy"):
        try:
            importlib.import_module(m)
        except Exception as e:
            bad.append(f"{m} ({type(e).__name__})")
    v = ".".join(map(str, sys.version_info[:3]))
    if bad:
        return "FAIL", f"Python {v}; cannot import: {', '.join(bad)}"
    live = [m for m in ("torch", "ultralytics") if importlib.util.find_spec(m) is None]
    if live:
        return "WARN", f"Python {v}; replay packages import; {', '.join(live)} not installed (needed for live mode)"
    return "PASS", f"Python {v}; fastapi, uvicorn, cv2, numpy import; torch and ultralytics are installed"


def check_photos():
    pairs = needed_photos(ROOT / "autosettle_api" / "replay_data")
    st = photo_status(ROOT / "test_photos" / "commons", pairs)
    return [("PASS" if s == "ok" else "FAIL", f"demo photo {n}", s if s != "ok" else "present, hash matches") for n, s in st]


def check_weights():
    res = []
    for w in WEIGHTS:
        p = ROOT / "backup" / w
        res.append(("PASS", f"weights {w}", f"found ({p.stat().st_size // (1024 * 1024)} MB)") if p.is_file()
                   else ("WARN", f"weights {w}", "missing in backup/; live mode will not work"))
    return res


def check_gpu():
    if shutil.which("nvidia-smi") is None:
        return "WARN", "no NVIDIA GPU visible (live mode needs one)"
    rc, out = run(["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], timeout=8)
    return gpu_verdict(parse_gpu(out) if rc == 0 else None)


def check_build():
    p = ROOT / "autosettle_api" / "static"
    if not (p / "index.html").is_file():
        return "FAIL", "autosettle_api/static/index.html is missing (the web build)"
    try:
        b = json.loads((p / "build.json").read_text(encoding="utf-8"))
        return "PASS", f"web build present, build id {b.get('build')} ({b.get('built_at')})"
    except (OSError, ValueError):
        return "WARN", "web build present, build.json unreadable"


def check_port(port, expect):
    s = socket.socket()
    s.settimeout(1)
    try:
        in_use = s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()
    if not in_use:
        return port_verdict(port, None, expect)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            j = json.loads(r.read().decode("utf-8"))
        health = j if isinstance(j, dict) and "mode" in j else {}
    except Exception:
        health = {}
    return port_verdict(port, health, expect)


def check_data():
    try:
        from autosettle_engine.engine import RateCard
        rc = RateCard()
        n = len(getattr(rc, "rows", []) or [])
        rate = f"rate card loads ({n} rows)" if n else "rate card loads"
        files = list((ROOT / "autosettle_api" / "replay_data").glob("*.json")) + list((ROOT / "autosettle_api" / "replay_data" / "video").glob("*.json"))
        for f in files:
            json.loads(f.read_text(encoding="utf-8"))
        return "PASS", f"{rate}; {len(files)} replay files parse"
    except Exception as e:
        return "FAIL", f"rate card or replay data did not load ({type(e).__name__}: {e})"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--expect", choices=["live", "replay"], default=None)
    ap.add_argument("--json", default=None, help="also write the results to this file (nothing is written otherwise)")
    a = ap.parse_args(argv)

    results = []

    def add(name, v):
        if isinstance(v, list):
            results.extend(v)
        else:
            results.append((v[0], name, v[1]))

    add("git", check_git())
    add("python", check_python())
    add("photos", check_photos())
    add("weights", check_weights())
    add("gpu", check_gpu())
    add("web build", check_build())
    add(f"port {a.port}", check_port(a.port, a.expect))
    add("data", check_data())
    for s, n, d in results:
        print(f"{s:4}  {n}: {d}")
    verdict, code = summarise(results)
    print(verdict)
    if a.json:
        Path(a.json).write_text(json.dumps({"verdict": verdict, "checks": [{"status": s, "check": n, "detail": d} for s, n, d in results]}, indent=1), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
