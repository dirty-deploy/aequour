"""Thermal readings and cooldowns for unattended runs (TASKS RUN1, Task 0).

GPU: nvidia-smi. CPU: LibreHardwareMonitor web server (data.json), highest /amdcpu/ or /intelcpu/ temperature.
Limits (deg C):  GPU soft 80 / resume 72 / hard 86;  CPU soft 80 / resume 72 / hard 86.
"""
import json
import subprocess
import time
import urllib.request

LIMITS = {"gpu": {"soft": 80, "resume": 72, "hard": 86},
          "cpu": {"soft": 80, "resume": 72, "hard": 86}}
LHM_URLS = ("http://127.0.0.1:8085/data.json", "http://localhost:8085/data.json")


def read_gpu():
    """{'temp','power','util','vram','sm_clock'} or None."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,clocks.sm",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout
        t, p, u, m, c = [x.strip() for x in out.strip().splitlines()[0].split(",")]
        num = lambda s: float(s) if s not in ("", "[N/A]", "N/A") else None
        return {"temp": num(t), "power": num(p), "util": num(u), "vram": num(m), "sm_clock": num(c)}
    except Exception:
        return None


def _walk(node):
    yield node
    for ch in node.get("Children", []) or []:
        yield from _walk(ch)


def read_cpu():
    """Highest CPU temperature (deg C) from LibreHardwareMonitor, or None if unreachable / no CPU sensor."""
    for url in LHM_URLS:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            continue
        vals = []
        for n in _walk(data):
            sid = n.get("SensorId") or ""
            if n.get("Type") == "Temperature" and (sid.startswith("/amdcpu/") or sid.startswith("/intelcpu/")):
                try:
                    vals.append(float(str(n.get("Value", "")).replace("°C", "").replace(",", ".").strip()))
                except ValueError:
                    pass
        return max(vals) if vals else None
    return None


def state(gpu_t, cpu_t, current="run"):
    """'kill' at a hard limit, 'suspend' at a soft limit, 'run' once everything is at/below resume (hysteresis)."""
    temps = {"gpu": gpu_t, "cpu": cpu_t}
    if any(t is not None and t >= LIMITS[k]["hard"] for k, t in temps.items()):
        return "kill"
    if any(t is not None and t >= LIMITS[k]["soft"] for k, t in temps.items()):
        return "suspend"
    if current == "suspend" and any(t is not None and t > LIMITS[k]["resume"] for k, t in temps.items()):
        return "suspend"
    return "run"


def cooldown_until(gpu_max=65, cpu_max=72, timeout=600, poll=5, log=print):
    """Block until GPU <= gpu_max and CPU <= cpu_max (CPU ignored if unreadable). Returns True if reached."""
    t0 = time.time()
    while True:
        g = read_gpu()
        gt = g["temp"] if g else None
        ct = read_cpu()
        if (gt is None or gt <= gpu_max) and (ct is None or ct <= cpu_max):
            return True
        if time.time() - t0 > timeout:
            log(f"cooldown timeout after {timeout}s (gpu {gt}, cpu {ct})")
            return False
        time.sleep(poll)


def wait_if_hot(log=print):
    """Call inside long loops: if anything is at a soft limit, wait for the resume temperatures."""
    g = read_gpu()
    gt = g["temp"] if g else None
    ct = read_cpu()
    if state(gt, ct) != "run":
        log(f"hot (gpu {gt}, cpu {ct}): cooling to resume limits")
        cooldown_until(LIMITS["gpu"]["resume"], LIMITS["cpu"]["resume"])


if __name__ == "__main__":
    print("gpu", read_gpu(), "cpu", read_cpu())
