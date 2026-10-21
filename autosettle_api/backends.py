"""Vision backends. A backend turns saved image files into the vision dict the engine contract is built from.
LiveVision runs the real pipeline (GPU). ReplayVision serves recorded pipeline output, matched by the photo's SHA-256."""
import hashlib
import json
import threading
from pathlib import Path


class ReplayMiss(Exception):
    pass


class LiveVision:
    mode = "live"

    def __init__(self, runtime_dir):
        from autosettle_vision import pipeline as P
        self.P = P
        self.seen = P.SeenStore(Path(runtime_dir) / "seen_hashes.json")
        self.lock = threading.Lock()          # one GPU job at a time

    def run(self, paths, claim_id):
        with self.lock:
            return self.P.run_claim([str(p) for p in paths], claim_id=claim_id, seen=self.seen)


    def run_video(self, path, claim_id):
        from autosettle_vision.video_claim import run_video_claim
        with self.lock:
            return run_video_claim(path, claim_id, self.seen)


class ReplayVision:
    mode = "replay"

    def __init__(self, replay_dir):
        self.records = {}
        for f in sorted(Path(replay_dir).glob("*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            self.records[rec["sha256"]] = rec
        self.by_key = {r["key"]: r for r in self.records.values()}

    def run_video(self, path, claim_id):
        raise ReplayMiss("REPLAY mode has no recorded video output")

    def lookup(self, key):
        return self.by_key[key]

    def run(self, paths, claim_id):
        if len(paths) != 1:
            raise ReplayMiss("REPLAY mode has recorded output for a single demo photo only")
        sha = hashlib.sha256(Path(paths[0]).read_bytes()).hexdigest()
        rec = self.records.get(sha)
        if rec is None:
            raise ReplayMiss("REPLAY mode: no recorded output for this photo")
        return remap(rec["vision"], Path(paths[0]).name, claim_id)


def remap(vision, stored_name, claim_id):
    """Re-key a recorded vision dict to the stored file name of the photo it is now attached to."""
    v = json.loads(json.dumps(vision, default=str))
    old = (v.get("images") or [None])[0]
    if old and old != stored_name:
        v["images"] = [stored_name]
        v["quality"] = {stored_name: v["quality"][old]} if old in v["quality"] else v["quality"]
        v["findings_by_image"] = {stored_name: v["findings_by_image"].get(old, [])}
        v["per_image"] = [{**p, "image_id": stored_name} for p in v["per_image"]]
        v["flags"] = [f.replace(old, stored_name) for f in v["flags"]]
        v["integrity_flags"] = [f.replace(old, stored_name) for f in v["integrity_flags"]]
    v["image_id"] = claim_id
    return v
