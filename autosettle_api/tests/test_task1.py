"""Build identity, cache headers, auto mode and the port guard."""
import socket
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from autosettle_api import runtime
from autosettle_api.__main__ import banner, parse, pick_mode
from autosettle_api.app import Settings, create_app


def client(**kw):
    return TestClient(create_app(Settings(replay=True, runtime=Path(tempfile.mkdtemp()), qwen=False, **kw)))


class TestHealthAndHeaders(unittest.TestCase):
    def test_health_names_the_build_and_keeps_old_keys(self):
        h = client().get("/health").json()
        for k in ("ok", "mode", "qwen", "video", "claims", "ui", "build", "built_at", "weights_found", "gpu"):
            self.assertIn(k, h)
        self.assertEqual(h["mode"], "REPLAY")
        self.assertFalse(h["gpu"])

    def test_v1_ui_reports_its_own_build(self):
        h = client(ui="v1").get("/health").json()
        self.assertEqual((h["ui"], h["build"]), ("static_v1", "v1-legacy"))

    def test_json_and_pages_are_never_cached_and_hashed_assets_are_immutable(self):
        c = client()
        for path in ("/", "/index.html", "/health", "/scenarios", "/policies", "/guardrails"):
            self.assertEqual(c.get(path).headers["cache-control"], "no-store", path)
        v = c.post("/claims", json={"scenario": "offer"})
        self.assertEqual(v.headers["cache-control"], "no-store")
        assets = sorted((Path(runtime.__file__).with_name("static") / "assets").glob("*.js"))
        self.assertTrue(assets, "the web build is missing")
        r = c.get("/assets/" + assets[0].name)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["cache-control"], "public, max-age=31536000, immutable")


class TestAutoMode(unittest.TestCase):
    def test_auto_picks_live_only_with_weights_and_gpu(self):
        a = parse([])
        self.assertTrue(pick_mode(a, missing=["parts_s_best.pt"], gpu=True)[0])
        self.assertTrue(pick_mode(a, missing=[], gpu=False)[0])
        replay, reason = pick_mode(a, missing=[], gpu=True)
        self.assertFalse(replay)
        self.assertIn("live", reason)

    def test_forced_modes(self):
        self.assertTrue(pick_mode(parse(["--replay"]), missing=[], gpu=True)[0])
        self.assertFalse(pick_mode(parse(["--live"]), missing=[], gpu=True)[0])
        with self.assertRaises(SystemExit) as e:
            pick_mode(parse(["--live"]), missing=["dent_det_best.pt"], gpu=True)
        self.assertIn("dent_det_best.pt", str(e.exception))
        with self.assertRaises(SystemExit) as e:
            pick_mode(parse(["--live"]), missing=[], gpu=False)
        self.assertIn("CUDA", str(e.exception))

    def test_banner_says_mode_url_build_weights_gpu_and_the_switch_command(self):
        a = parse([])
        b = banner(a, True, "replay, because no CUDA GPU was found", [], False, {"ui": "static", "build": "abc123", "built_at": "now"})
        for word in ("REPLAY", "http://127.0.0.1:8000", "abc123", "WEIGHTS", "GPU", "--live"):
            self.assertIn(word, b)


class TestPortGuard(unittest.TestCase):
    def test_a_free_port_reports_nothing(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        self.assertIsNone(runtime.probe_port("127.0.0.1", port))

    def test_a_busy_port_is_named(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(5)
        try:
            self.assertEqual(runtime.probe_port("127.0.0.1", s.getsockname()[1]), "another program")
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
