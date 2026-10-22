"""python -m autosettle_api [--live | --replay] [--port 8000] [--no-qwen] [--with-qwen] [--ui public|demo|v1] [--fresh-seen]

With no mode flag the server runs live if the model files and a CUDA GPU are present, and replay otherwise."""
import argparse
import sys

import uvicorn

from . import runtime
from .app import Settings, create_app


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--live", action="store_true", help="force live mode (analyses new photos; needs the model files in backup/ and a CUDA GPU)")
    ap.add_argument("--no-qwen", action="store_true", help="never load the language model (template wording, no quote or plate reading from images)")
    ap.add_argument("--replay", action="store_true", help="serve vision outputs from recorded JSON (clearly marked REPLAY); no GPU and no language model (template wording) unless --with-qwen")
    ap.add_argument("--with-qwen", action="store_true", help="with --replay: still load the language model for wording (needs the GPU and about 8 GB)")
    ap.add_argument("--ui", choices=("public", "demo", "v1"), default="public", help="'v1' serves the earlier build kept as a safety net; 'demo' serves the git-ignored build that may include third-party UI code")
    ap.add_argument("--video", choices=("on", "off"), default="on", help="video evidence endpoint (default on: its tests pass)")
    ap.add_argument("--fresh-seen", action="store_true", help="start with an empty duplicate-photo store (the same photo in a second claim is otherwise escalated, correctly)")
    return ap.parse_args(argv)


def pick_mode(a, missing=None, gpu=None):
    """Returns (replay, reason). Raises SystemExit with the exact missing thing if --live cannot run."""
    if a.live and a.replay:
        raise SystemExit("Choose one of --live and --replay, not both.")
    if a.replay:
        return True, "replay, because --replay was given"
    missing = runtime.missing_weights() if missing is None else missing
    gpu = runtime.gpu_available() if gpu is None else gpu
    if a.live:
        if missing:
            raise SystemExit("Live mode needs these model files in backup/: " + ", ".join(missing) + ". See weights/README.md, or run without --live for replay.")
        if not gpu:
            raise SystemExit("Live mode needs a CUDA GPU and none was found (is the CUDA build of torch installed?). Run without --live for replay.")
        return False, "live, because --live was given"
    if missing:
        return True, "replay, because backup/ has no " + ", ".join(missing)
    if not gpu:
        return True, "replay, because no CUDA GPU was found"
    return False, "live, because the model files are in backup/ and a CUDA GPU was found"


def settings_from(a, replay=None):
    """Replay mode means no GPU: the language model is loaded only if --with-qwen says so."""
    replay = a.replay if replay is None else replay
    qwen = (not a.no_qwen) and (not replay or a.with_qwen)
    return Settings(replay=replay, qwen=qwen, preload=qwen, ui=a.ui, video=a.video == "on", fresh_seen=a.fresh_seen)


def qwen_line(settings):
    """What the banner says about the language model: loading in the background, off, or the exact reason it cannot load."""
    if not settings.qwen:
        return "off (templates write every reply)"
    problem = runtime.gpu_memory_problem()
    if problem:
        return f"cannot load: {problem}. Replies use templates."
    return "loading in the background; replies use templates until it is ready"


def banner(a, replay, reason, missing, gpu, build, qwen=None):
    other = "--live" if replay else "--replay"
    lines = [f"MODE      {'REPLAY: recorded demo claims only' if replay else 'LIVE: analyses your photos'}",
             f"WHY       {reason}",
             f"URL       http://{a.host}:{a.port}",
             f"UI        {build['ui']}   build {build['build']}   built {build.get('built_at') or 'unknown'}",
             f"WEIGHTS   {'yes' if not missing else 'no (' + ', '.join(missing) + ')'}",
             f"GPU       {'yes' if gpu else 'no'}"]
    if qwen:
        lines.append(f"LANGUAGE  {qwen}")
    lines += [f"SWITCH   python -m autosettle_api {other} --port {a.port + 1}"]
    w = max(len(x) for x in lines) + 2
    return "\n".join(["+" + "-" * w + "+"] + ["| " + x.ljust(w - 1) + "|" for x in lines] + ["+" + "-" * w + "+"])


def main():
    a = parse()
    busy = runtime.probe_port(a.host, a.port)
    if busy:
        raise SystemExit(f"Port {a.port} is busy with {busy}. Use --port {a.port + 1} or stop that process.")
    missing = runtime.missing_weights()
    gpu = runtime.gpu_available()
    replay, reason = pick_mode(a, missing, gpu)
    if a.ui == "v1":
        print("WARNING: --ui v1 serves the old build (the 'Four recorded claims' page). Leave it out for the current build.", file=sys.stderr)
    settings = settings_from(a, replay)
    print(banner(a, replay, reason, missing, gpu, runtime.read_build(a.ui), qwen_line(settings)), flush=True)
    uvicorn.run(create_app(settings), host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
