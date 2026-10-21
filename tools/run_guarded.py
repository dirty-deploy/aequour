"""Run a command under the thermal guard.

    python tools/run_guarded.py [--gpu-soft N --gpu-resume N --cpu-soft N ...] -- <command ...>

Polls every 2 s. At a soft limit the whole process tree is suspended (psutil); it resumes once everything is at or
below the resume temperatures; at a hard limit the tree is killed and this script exits 99 with THERMAL_KILL.
Every poll is appended to run1/thermal_log.csv (time, gpu temp, gpu power, gpu util, vram, cpu temp or blank, state).
"""
import argparse
import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thermal as T  # noqa: E402

LOG = Path(__file__).resolve().parent.parent / "run1" / "thermal_log.csv"
OVERRIDE = LOG.with_name("thermal_override.json")   # {"gpu": {"soft": 47}} etc.; re-read every poll ({} = defaults)


def apply_override(base):
    import copy
    import json
    lim = copy.deepcopy(base)
    try:
        for k, v in json.loads(OVERRIDE.read_text() or "{}").items():
            lim[k].update(v)
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return lim


def tree(p):
    try:
        return [p] + p.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def act(procs, what):
    for p in procs:
        try:
            getattr(p, what)()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def main():
    if "--" not in sys.argv:
        sys.exit("usage: run_guarded.py [limits] -- <command>")
    i = sys.argv.index("--")
    ap = argparse.ArgumentParser()
    for k in ("gpu", "cpu"):
        for lvl in ("soft", "resume", "hard"):
            ap.add_argument(f"--{k}-{lvl}", type=float, default=T.LIMITS[k][lvl])
    ap.add_argument("--tag", default="")
    a = ap.parse_args(sys.argv[1:i])
    for k in ("gpu", "cpu"):
        for lvl in ("soft", "resume", "hard"):
            T.LIMITS[k][lvl] = getattr(a, f"{k}_{lvl}")
    cmd = sys.argv[i + 1:]
    LOG.parent.mkdir(exist_ok=True)
    new = not LOG.exists()
    f = open(LOG, "a", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["time", "gpu_temp", "gpu_power", "gpu_util", "vram_mib", "cpu_temp", "state", "tag"])
    proc = subprocess.Popen(cmd)
    p = psutil.Process(proc.pid)
    st, suspends = "run", 0
    base = {k: dict(v) for k, v in T.LIMITS.items()}
    while proc.poll() is None:
        T.LIMITS.update(apply_override(base))
        g = T.read_gpu() or {}
        ct = T.read_cpu()
        new_st = T.state(g.get("temp"), ct, st)
        if new_st == "kill":
            act(tree(p), "kill")
            w.writerow([datetime.now().isoformat(timespec="seconds"), g.get("temp"), g.get("power"), g.get("util"),
                        g.get("vram"), "" if ct is None else ct, "kill", a.tag])
            f.close()
            print("THERMAL_KILL", flush=True)
            sys.exit(99)
        if new_st == "suspend" and st == "run":
            act(tree(p), "suspend")
            suspends += 1
            print(f"[guard] suspended (gpu {g.get('temp')}, cpu {ct})", flush=True)
        elif new_st == "run" and st == "suspend":
            act(tree(p), "resume")
            print(f"[guard] resumed (gpu {g.get('temp')}, cpu {ct})", flush=True)
        st = new_st
        w.writerow([datetime.now().isoformat(timespec="seconds"), g.get("temp"), g.get("power"), g.get("util"),
                    g.get("vram"), "" if ct is None else ct, st, a.tag])
        f.flush()
        time.sleep(2)
    f.close()
    print(f"[guard] exit {proc.returncode}, suspends {suspends}", flush=True)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
