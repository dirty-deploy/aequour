"""Video path tests. No GPU. Videos are SYNTHETIC. Plumbing on the teammate's two synthetic walk-around clips runs only when
AEQUOUR_ISHAN_VIDEOS points at a folder holding them (they are not in this repository)."""
import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from autosettle_vision import video as V, video_attacks as A, video_integrity as VI
from autosettle_vision.tracker import VideoByteTracker


class TestVideoAttacks(unittest.TestCase):
    def test_every_attack_holds(self):
        for f in A.ATTACKS:
            ok, detail = f()
            self.assertTrue(ok, f"{f.__name__}: {detail}")

    def test_control_looped_video_matches_single_photo_offer(self):
        ok, detail = A.control_looped_video_matches_photo()
        self.assertTrue(ok, detail)


class TestSamplerAndContinuity(unittest.TestCase):
    def test_smooth_drift_is_one_scene(self):
        p = A.drift_video(Path(tempfile.mkdtemp()) / "d.mp4", seed=1, n=60)
        self.assertEqual(VI.check_video(p)["breaks"], [])

    def test_keyframes_capped_and_ordered(self):
        p = A.drift_video(Path(tempfile.mkdtemp()) / "d.mp4", seed=1, n=60)
        frames, info = V.sample_keyframes(p)
        self.assertTrue(2 <= len(frames) <= V.MAX_KEYFRAMES)
        self.assertEqual([n.split("#f")[1] for n, _ in frames], [str(k) for k in range(len(frames))])
        self.assertLessEqual(max(max(f.shape[:2]) for _, f in frames), V.MAX_SIDE)

    def test_blurred_frames_are_dropped(self):
        d = Path(tempfile.mkdtemp())
        base = A.scene(9)
        blurred = cv2.GaussianBlur(base, (0, 0), 12)
        frames = [A.view(base, k, 20) for k in range(10)] + [blurred] * 10
        _, info = V.sample_keyframes(A.write_video(d / "b.mp4", frames))
        self.assertGreater(info["dropped_blur_or_dark"], 0)

    def test_teammate_synthetic_videos_plumbing(self):
        folder = os.environ.get("AEQUOUR_ISHAN_VIDEOS")
        if not folder:
            self.skipTest("AEQUOUR_ISHAN_VIDEOS not set (the clips are not in this repository)")
        vids = sorted(Path(folder).glob("*.mp4"))
        self.assertTrue(vids)
        for p in vids:
            frames, info = V.sample_keyframes(p)
            self.assertTrue(2 <= len(frames) <= V.MAX_KEYFRAMES)
            res = VI.check_video(p)
            self.assertIn("breaks", res)


class TestTracker(unittest.TestCase):
    def _frames(self, appear, n=6, severity=None):
        out = []
        for i in range(n):
            img = np.zeros((240, 320, 3), np.uint8)
            fnd = []
            if i in appear:
                fnd = [{"part_class": "Front-door", "damage_class": "Dent", "damage_conf": 0.85, "damage_box": [100 + 2 * i, 80, 160 + 2 * i, 140],
                        "severity": severity, "damage_area_fraction": None if severity is None else 0.08}]
            out.append((f"f{i}", img, {"findings": fnd}))
        return out

    def test_same_dent_in_dense_frames_is_one_entity_and_defaults_are_not_invented(self):
        ents, dropped = VideoByteTracker().track_video_detections(self._frames(range(6)))
        self.assertEqual(len(ents), 1)
        self.assertEqual(dropped, [])
        self.assertIsNone(ents[0].severity)            # the original defaulted to "moderate"
        self.assertIsNone(ents[0].damage_area_fraction)  # ... and 0.05
        self.assertFalse(hasattr(ents[0], "is_verified_physical"))

    def test_severity_comes_only_from_the_finding(self):
        ents, _ = VideoByteTracker().track_video_detections(self._frames(range(6), severity="minor"))
        self.assertEqual(ents[0].severity, "minor")
        self.assertEqual(ents[0].damage_area_fraction, 0.08)

    def test_single_frame_sighting_is_reported_not_silently_dropped(self):
        ents, dropped = VideoByteTracker().track_video_detections(self._frames({2}))
        self.assertEqual(ents, [])
        self.assertEqual(len(dropped), 1)
        self.assertIn("single sighting", dropped[0].reason)


if __name__ == "__main__":
    unittest.main()
