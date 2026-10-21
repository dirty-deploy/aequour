"""Self-test of the thermal guard without heating anything (Task 0.5).
Sets the GPU soft limit to current GPU temperature - 1 via run1/thermal_override.json, runs a 30 s sleep under the
guard, restores the real limits after ~10 s, and checks the job was suspended, resumed and took longer than 30 s."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thermal as T  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OV = ROOT / "run1" / "thermal_override.json"
g = T.read_gpu()["temp"]
soft = g - 1
OV.write_text(json.dumps({"gpu": {"soft": soft, "resume": soft - 8, "hard": 999}}))
print(f"gpu now {g}; test soft limit {soft}")


def restore():
    time.sleep(10)
    OV.write_text("{}")
    print("real limits restored", flush=True)


threading.Thread(target=restore, daemon=True).start()
t0 = time.time()
r = subprocess.run([sys.executable, str(ROOT / "tools" / "run_guarded.py"), "--tag", "selftest", "--",
                    sys.executable, str(ROOT / "tools" / "guard_selftest_sleep.py")], capture_output=True, text=True)
wall = time.time() - t0
out = r.stdout
print(out)
ok = "[guard] suspended" in out and "[guard] resumed" in out and r.returncode == 0 and wall > 36
OV.write_text("{}")
print(f"wall {wall:.1f}s, returncode {r.returncode}: SELFTEST {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
