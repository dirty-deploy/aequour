"""python -m autosettle_api [--port 8000] [--no-qwen] [--replay] [--ui public|demo]"""
import argparse

import uvicorn

from .app import Settings, create_app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-qwen", action="store_true", help="never load the language model (template wording, no quote or plate reading from images)")
    ap.add_argument("--replay", action="store_true", help="serve vision outputs from recorded JSON (clearly marked REPLAY); no GPU needed")
    ap.add_argument("--ui", choices=("public", "demo"), default="public", help="'demo' serves the git-ignored build that may include third-party UI code")
    ap.add_argument("--video", choices=("on", "off"), default="on", help="video evidence endpoint (default on: its tests pass)")
    ap.add_argument("--fresh-seen", action="store_true", help="start with an empty duplicate-photo store (the same photo in a second claim is otherwise escalated, correctly)")
    a = ap.parse_args()
    app = create_app(Settings(replay=a.replay, qwen=not a.no_qwen, ui=a.ui, video=a.video == "on", fresh_seen=a.fresh_seen))
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
