"""The pure parts of tools/preflight.py: hash matching, GPU reading, verdicts and the final summary. No GPU, no server."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("preflight", ROOT / "tools" / "preflight.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class TestPhotos(unittest.TestCase):
    def test_hash_match_and_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.jpg").write_bytes(b"real photo")
            (Path(d) / "b.jpg").write_bytes(b"resaved photo")
            pairs = [("a.jpg", hashlib.sha256(b"real photo").hexdigest()),
                     ("b.jpg", hashlib.sha256(b"real photo").hexdigest()),
                     ("c.jpg", hashlib.sha256(b"x").hexdigest())]
            self.assertEqual(P.photo_status(d, pairs), [("a.jpg", "ok"), ("b.jpg", "wrong hash"), ("c.jpg", "missing")])

    def test_needed_photos_reads_scenarios_and_videos_once_each(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "video").mkdir()
            (Path(d) / "s1.json").write_text(json.dumps({"key": "s1", "source_file": "p.jpg", "sha256": "aa"}))
            (Path(d) / "video" / "v1.json").write_text(json.dumps({"key": "v1", "source_file": "p.jpg", "sha256": "aa"}))
            (Path(d) / "video" / "v2.json").write_text(json.dumps({"key": "v2", "source_file": "q.jpg", "sha256": "bb"}))
            self.assertEqual(P.needed_photos(d), [("p.jpg", "aa"), ("q.jpg", "bb")])

    def test_the_repository_photos_are_all_present(self):
        pairs = P.needed_photos(ROOT / "autosettle_api" / "replay_data")
        self.assertGreaterEqual(len(pairs), 3)
        self.assertTrue(all(s == "ok" for _, s in P.photo_status(ROOT / "test_photos" / "commons", pairs)))


class TestGpu(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(P.parse_gpu("51, 1518, 8188\n"), {"temp_c": 51, "used_mib": 1518, "total_mib": 8188, "free_mib": 6670})
        self.assertIsNone(P.parse_gpu(""))
        self.assertIsNone(P.parse_gpu("N/A, N/A, N/A"))

    def test_verdicts(self):
        self.assertEqual(P.gpu_verdict(P.parse_gpu("51, 1518, 8188"))[0], "PASS")
        self.assertEqual(P.gpu_verdict(P.parse_gpu("51, 5000, 8188"))[0], "WARN")      # 3,188 MiB free
        self.assertEqual(P.gpu_verdict(P.parse_gpu("75, 1000, 8188"))[0], "WARN")      # hot
        self.assertEqual(P.gpu_verdict(P.parse_gpu("74, 1000, 8188"))[0], "PASS")
        self.assertEqual(P.gpu_verdict(None)[0], "WARN")


class TestVerdicts(unittest.TestCase):
    def test_branch(self):
        self.assertEqual(P.branch_verdict("finals-video-price", False)[0], "PASS")
        self.assertEqual(P.branch_verdict("main", False)[0], "PASS")
        self.assertEqual(P.branch_verdict("demo-photos", False)[0], "WARN")
        self.assertEqual(P.branch_verdict("main", True)[0], "WARN")
        self.assertEqual(P.branch_verdict("", False)[0], "WARN")

    def test_port(self):
        self.assertEqual(P.port_verdict(8000, None, None)[0], "PASS")
        live = {"mode": "LIVE", "video": True, "qwen": "off", "build": "abc"}
        self.assertEqual(P.port_verdict(8000, live, "live")[0], "PASS")
        self.assertEqual(P.port_verdict(8000, {**live, "mode": "REPLAY"}, "live")[0], "WARN")
        self.assertEqual(P.port_verdict(8000, {**live, "mode": "REPLAY"}, None)[0], "PASS")
        self.assertEqual(P.port_verdict(8000, {}, None)[0], "WARN")

    def test_summary_only_a_fail_blocks(self):
        self.assertEqual(P.summarise([("PASS", "a", ""), ("WARN", "b", "")]), ("READY", 0))
        self.assertEqual(P.summarise([("PASS", "a", ""), ("FAIL", "b", "")]), ("NOT READY", 1))
        self.assertEqual(P.summarise([]), ("READY", 0))


if __name__ == "__main__":
    unittest.main()
