"""python -m autosettle_api [--port 8000] [--no-qwen] [--replay [--with-qwen]] [--ui public|demo|v1]"""
import argparse

import uvicorn

from .app import Settings, create_app


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-qwen", action="store_true", help="never load the language model (template wording, no quote or plate reading from images)")
    ap.add_argument("--replay", action="store_true", help="serve vision outputs from recorded JSON (clearly marked REPLAY); no GPU and no language model (template wording) unless --with-qwen")
    ap.add_argument("--with-qwen", action="store_true", help="with --replay: still load the language model for wording (needs the GPU and about 8 GB)")
    ap.add_argument("--ui", choices=("public", "demo", "v1"), default="public", help="'v1' serves the earlier build kept as a safety net; 'demo' serves the git-ignored build that may include third-party UI code")
    ap.add_argument("--video", choices=("on", "off"), default="on", help="video evidence endpoint (default on: its tests pass)")
    ap.add_argument("--fresh-seen", action="store_true", help="start with an empty duplicate-photo store (the same photo in a second claim is otherwise escalated, correctly)")
    return ap.parse_args(argv)


def settings_from(a):
    """Replay mode means no GPU: the language model is loaded only if --with-qwen says so."""
    return Settings(replay=a.replay, qwen=(not a.no_qwen) and (not a.replay or a.with_qwen), ui=a.ui, video=a.video == "on", fresh_seen=a.fresh_seen)


def main():
    a = parse()
    uvicorn.run(create_app(settings_from(a)), host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
