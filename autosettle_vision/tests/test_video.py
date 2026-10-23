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


def _dimmed(alpha, sigma=0.0, seed=9):
    """The synthetic scene darkened (and optionally blurred), generated here with OpenCV."""
    base = A.scene(seed)
    if sigma:
        base = cv2.GaussianBlur(base, (0, 0), sigma)
    return (base.astype(np.float32) * alpha).astype(np.uint8)


class TestVideoQualityFloors(unittest.TestCase):
    """Video frames use their own floors. Photos keep theirs. (Synthetic clips; real footage is n = 2 and not tested here.)"""
    def test_floors_are_separate_and_photo_floors_unchanged(self):
        from autosettle_vision import pipeline as P
        self.assertEqual((P.BLUR_MIN, P.DARK_MIN, V.BLUR_MIN, V.DARK_MIN), (60.0, 40.0, 60.0, 40.0))
        self.assertLess(V.BLUR_MIN_VIDEO, V.BLUR_MIN)
        self.assertLess(V.DARK_MIN_VIDEO, V.DARK_MIN)

    def test_dim_soft_clip_passes_video_floors_but_would_fail_photo_floors(self):
        from autosettle_vision import pipeline as P
        dim = _dimmed(0.32)
        q = P.quality(dim)
        self.assertIn("blurry", q["flags"])
        self.assertIn("too_dark", q["flags"])
        self.assertEqual(P.quality(dim, V.BLUR_MIN_VIDEO, V.DARK_MIN_VIDEO)["flags"], [])
        frames = [np.roll(dim, 3 * k, axis=1) for k in range(24)]
        kf, info = V.sample_keyframes(A.write_video(Path(tempfile.mkdtemp()) / "dim.mp4", frames))
        self.assertGreaterEqual(len(kf), 2)
        self.assertLessEqual(len(kf), V.MAX_KEYFRAMES)
        self.assertEqual((info["blur_min"], info["dark_min"]), (V.BLUR_MIN_VIDEO, V.DARK_MIN_VIDEO))

    def test_a_clip_that_is_too_dark_is_rejected_with_the_numbers(self):
        frames = [A.view(_dimmed(0.1), k, 20) for k in range(20)]
        with self.assertRaises(V.VideoRejected) as cm:
            V.sample_keyframes(A.write_video(Path(tempfile.mkdtemp()) / "black.mp4", frames))
        m = str(cm.exception)
        self.assertIn("No frame was clear enough to read", m)
        self.assertIn(f"at least {V.BLUR_MIN_VIDEO:g}", m)
        self.assertIn(f"at least {V.DARK_MIN_VIDEO:g}", m)
        self.assertRegex(m, r"sharpness \d+")
        self.assertIn("Film in daylight", m)

    def test_a_clip_that_is_too_blurred_is_rejected_with_the_numbers(self):
        frames = [A.view(_dimmed(1.0, sigma=3.0), k, 20) for k in range(20)]
        with self.assertRaises(V.VideoRejected) as cm:
            V.sample_keyframes(A.write_video(Path(tempfile.mkdtemp()) / "soft.mp4", frames))
        self.assertIn("No frame was clear enough to read", str(cm.exception))

    def test_a_photo_between_the_floors_is_still_flagged_blurry(self):
        from autosettle_vision import pipeline as P
        soft = _dimmed(1.0, sigma=0.8)                                    # sharpness about 43, bright
        g = cv2.cvtColor(soft, cv2.COLOR_BGR2GRAY)
        v = float(cv2.Laplacian(g, cv2.CV_64F).var())
        self.assertTrue(8 < v < P.BLUR_MIN, v)
        self.assertEqual(P.quality(soft)["flags"], ["blurry"])
        self.assertEqual(P.quality(soft, V.BLUR_MIN_VIDEO, V.DARK_MIN_VIDEO)["flags"], ["blurry"] if v < V.BLUR_MIN_VIDEO else [])

    def test_the_sharpest_usable_frame_of_each_time_window_is_kept_in_time_order(self):
        good = [(0, "a", 5.0), (1, "b", 9.0), (2, "c", 7.0), (60, "d", 3.0), (61, "e", 4.0)]
        picked = V._pick_by_window(good, 100, 2)
        self.assertEqual([x[1] for x in picked], ["b", "e"])

    def test_a_file_that_is_not_video_says_how_to_fix_it(self):
        p = Path(tempfile.mkdtemp()) / "notes.mov"
        p.write_bytes(b"this is not a video" * 50)
        with self.assertRaises(V.VideoRejected) as cm:
            V.sample_keyframes(p)
        self.assertEqual(str(cm.exception), "This video format could not be read. Save it as H.264 MP4 and try again.")


def _motion_blur(img, k):
    ker = np.zeros((k, k), np.float32)
    ker[k // 2, :] = 1.0 / k
    return cv2.filter2D(img, -1, ker)


class TestContinuityNaming(unittest.TestCase):
    """A break is named hard cut or unverified from the change in overall look. Either way the flag stays and the engine escalates."""
    def _run(self, frames, name):
        from autosettle_vision.video_claim import run_video_claim
        p = A.write_video(Path(tempfile.mkdtemp()) / name, frames)
        cont = VI.check_video(p)
        v = run_video_claim(p, name, A._seen(), A.fake_analyser())
        res, _ = A._decide(v)
        return cont, v, res

    def test_a_continuous_clip_has_no_break_and_no_flag(self):
        a = A.scene(1)
        cont, v, res = self._run([A.view(a, k, 60) for k in range(60)], "c.mp4")
        self.assertEqual((cont["breaks"], cont["hard_cuts"], cont["unverified"]), ([], [], []))
        self.assertEqual(VI.outcome(cont)[0], "continuous")
        self.assertEqual(VI.flags(cont), [])
        self.assertEqual(v["integrity_flags"], [])
        self.assertEqual(res["decision"], "OFFER")

    def test_a_splice_is_a_hard_cut_and_still_escalates(self):
        a, b = A.scene(1), A.scene(2)
        cont, v, res = self._run([A.view(a, k, 30) for k in range(30)] + [A.view(b, k, 30) for k in range(30)], "s.mp4")
        self.assertTrue(cont["hard_cuts"], cont)
        self.assertEqual(cont["unverified"], [])
        self.assertEqual(VI.outcome(cont)[0], "hard_cut")
        self.assertIn("A hard cut was found", VI.outcome(cont)[1])
        self.assertTrue(any(f.startswith("video_not_continuous") for f in v["integrity_flags"]))
        self.assertEqual((res["decision"], res["offer"]), ("ESCALATE", None))

    def test_shaky_footage_is_unverified_keeps_the_flag_and_still_escalates(self):
        a = A.scene(1)
        frames = [_motion_blur(A.view(a, k, 60), 31 if k % 2 else 3) for k in range(60)]
        cont, v, res = self._run(frames, "shaky.mp4")
        self.assertTrue(cont["breaks"], cont)
        self.assertEqual(cont["hard_cuts"], [])
        self.assertEqual(cont["unverified"], cont["breaks"])
        self.assertEqual(VI.outcome(cont)[0], "unverified")
        self.assertIn("Could not confirm one continuous take", VI.outcome(cont)[1])
        self.assertLess(cont["max_appearance"], VI.APPEARANCE_CUT)
        self.assertTrue(any(f.startswith("video_not_continuous") for f in v["integrity_flags"]))
        self.assertEqual((res["decision"], res["offer"]), ("ESCALATE", None))

    def test_every_break_is_in_exactly_one_group_and_the_flag_follows_the_breaks(self):
        a, b = A.scene(1), A.scene(2)
        r = VI.check_frames([A.view(a, k, 20) for k in range(20)] + [A.view(b, k, 20) for k in range(20)])
        self.assertEqual(sorted(r["hard_cuts"] + r["unverified"]), r["breaks"])
        self.assertEqual(bool(VI.flags(r)), bool(r["breaks"]))


if __name__ == "__main__":
    unittest.main()
