"""What this machine can run, which build is being served, and whether a port is free. No git calls: a downloaded ZIP has no .git."""
import json
import socket
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS = ("parts_s_best.pt", "dent_det_best.pt", "damage_merged_s_best.pt")       # the three files autosettle_vision/pipeline.py loads
UI_DIRS = {"public": "static", "demo": "static_demo", "v1": "static_v1"}


def missing_weights(root=ROOT):
    return [w for w in WEIGHTS if not (Path(root) / "backup" / w).is_file()]


def gpu_available():
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def read_build(ui="public"):
    """build.json sits next to index.html in the folder being served."""
    name = UI_DIRS.get(ui, "static")
    info = {"build": "unknown", "built_at": None, "ui": name}
    try:
        info.update(json.loads((Path(__file__).with_name(name) / "build.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return info


def probe_port(host, port):
    """None if the port is free; otherwise a description of what holds it."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1) as r:
            j = json.loads(r.read().decode("utf-8"))
        if isinstance(j, dict) and "mode" in j:
            return f"another Aequour server ({str(j['mode']).lower()}, build {j.get('build', 'unknown, an older build')})"
    except Exception:
        pass
    s = socket.socket()
    s.settimeout(1)
    try:
        return "another program" if s.connect_ex((host, port)) == 0 else None
    finally:
        s.close()


QWEN_MIN_FREE_GB = 6.6      # measured: the 4-bit language model took about 6.55 GB of GPU memory when it loaded (nvidia-smi before and after)


def gpu_memory_problem(min_free_gb=None):
    """None if the language model can be loaded; otherwise a plain reason. Checked before loading, so a full GPU gives
    a clear message and a template-only server instead of a crash."""
    try:
        import torch
    except Exception:
        return "torch is not installed (live mode needs requirements-live.txt)"
    if not torch.cuda.is_available():
        return "no CUDA GPU was found"
    free = torch.cuda.mem_get_info()[0] / 1e9
    need = QWEN_MIN_FREE_GB if min_free_gb is None else min_free_gb
    if free < need:
        return f"not enough free GPU memory ({free:.1f} GB free, about {need:.0f} GB needed): close other GPU programs"
    return None
