"""
Damage tracking across the frames of a video (Ultralytics BYTETracker).

adapted from Ishan6907/AutoSettleAI (MIT licence as found in that repository), copyright held by its author.
Changes made here, each from the audit in final/ISHAN_AUDIT.md:
  * no default severity, area or "verified" flag: an entity's severity and area come from the frame findings or stay None
    (the original defaulted to "moderate", 0.05 and True, which could reach the engine as evidence);
  * a track with fewer than `min_support_frames` frames is RETURNED as dropped with a reason, never discarded silently;
  * the VGGT call is removed (that module is an edge-gradient heuristic; see surface_check.py);
  * the unused homography code path is removed rather than left looking active.

Limit, stated plainly: ByteTrack links boxes by overlap between consecutive frames. It works on a dense sequence (a few frames
per second). On sparse keyframes taken seconds apart the camera has moved and boxes of the same dent do not overlap, so each
sighting would become a new track. The app therefore does not use this for keyframes; it uses part-and-class support across
keyframes (pipeline._fuse). This component is tested on synthetic dense sequences only; nothing here is validated on real video.
"""
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker


@dataclass
class TrackedDamageEntity:
    track_id: int
    damage_class: str
    part_class: str
    canonical_frame_idx: int
    canonical_frame_name: str
    canonical_box: List[float]
    max_confidence: float
    mean_confidence: float
    support_frames_count: int
    frame_indices: List[int]
    severity: Optional[str] = None             # from the canonical frame's finding; None stays None
    damage_area_fraction: Optional[float] = None


@dataclass
class DroppedTrack:
    track_id: int
    damage_class: str
    part_class: str
    support_frames_count: int
    reason: str


class VideoByteTracker:
    def __init__(self, track_high_thresh=0.30, track_low_thresh=0.15, new_track_thresh=0.30, track_buffer=30,
                 match_thresh=0.80, min_support_frames=2):
        self.args = SimpleNamespace(track_high_thresh=track_high_thresh, track_low_thresh=track_low_thresh,
                                    new_track_thresh=new_track_thresh, track_buffer=track_buffer, match_thresh=match_thresh,
                                    fuse_score=True, gmc_method="none")
        self.damage_tracker = BYTETracker(self.args)
        self.min_support_frames = min_support_frames

    @staticmethod
    def keyframe_score(img_bgr, box, conf):
        """sharpness x area x confidence x centrality of the damage box in one frame."""
        h, w = img_bgr.shape[:2]
        x1, y1, x2, y2 = [int(round(v)) for v in box]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, max(x1 + 1, x2)), min(h, max(y1 + 1, y2))
        crop = img_bgr[y1:y2, x1:x2]
        if crop.size < 4:
            return 0.0
        sharp = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        area = float((x2 - x1) * (y2 - y1)) / float(w * h)
        cx, cy = (x1 + x2) / 2.0 / w, (y1 + y2) / 2.0 / h
        centrality = 1.0 - float(np.hypot(cx - 0.5, cy - 0.5))
        return float((np.log1p(max(0.0, sharp)) * 0.3 + 1.0) * area * conf * max(0.2, centrality))

    def track_video_detections(self, frames: List[Tuple[str, np.ndarray, Dict[str, Any]]]) -> Tuple[List[TrackedDamageEntity], List[DroppedTrack]]:
        """frames = [(name, bgr, {"findings": [finding...]})] in time order, dense enough for box overlap between neighbours.
        Returns (supported entities, dropped tracks with the reason). Nothing is discarded without being reported."""
        tracks: Dict[int, Dict[str, Any]] = {}
        linked, seen = set(), []          # linked = (frame, finding) pairs that BYTETracker returned in some track
        for idx, (fname, img, analysis) in enumerate(frames):
            h, w = img.shape[:2]
            fnd = [f for f in analysis.get("findings", []) if f.get("damage_box")]
            if not fnd:
                self.damage_tracker.update(Boxes(torch.zeros((0, 6), dtype=torch.float32), orig_shape=(h, w)))
                continue
            seen += [(idx, k, f) for k, f in enumerate(fnd)]
            t = torch.tensor([[*f["damage_box"], float(f.get("damage_conf", 0.0)), 0.0] for f in fnd], dtype=torch.float32)
            rows = self.damage_tracker.update(Boxes(t, orig_shape=(h, w)))
            for row in rows:
                x1, y1, x2, y2, tid, conf, _cls, oidx = row
                tid, oidx = int(tid), int(oidx)
                linked.add((idx, oidx))
                f = fnd[oidx] if oidx < len(fnd) else {}
                rec = tracks.setdefault(tid, {"damage_class": f.get("damage_class") or "unknown", "part_class": f.get("part_class") or "unassigned",
                                              "frames": []})
                if rec["part_class"] in ("unassigned", "unknown") and f.get("part_class") not in (None, "unassigned", "unknown"):
                    rec["part_class"] = f["part_class"]
                rec["frames"].append((idx, fname, [float(x1), float(y1), float(x2), float(y2)], float(conf), self.keyframe_score(img, [x1, y1, x2, y2], float(conf)), f))
        entities, dropped = [], []
        for tid, rec in sorted(tracks.items()):
            n = len(rec["frames"])
            if n < self.min_support_frames:
                dropped.append(DroppedTrack(tid, rec["damage_class"], rec["part_class"], n, f"seen in {n} frame(s); needs {self.min_support_frames}"))
                continue
            best = max(rec["frames"], key=lambda it: it[4])
            confs = [it[3] for it in rec["frames"]]
            finding = best[5]
            entities.append(TrackedDamageEntity(
                track_id=tid, damage_class=rec["damage_class"], part_class=rec["part_class"], canonical_frame_idx=best[0],
                canonical_frame_name=best[1], canonical_box=best[2], max_confidence=round(max(confs), 3),
                mean_confidence=round(float(np.mean(confs)), 3), support_frames_count=n, frame_indices=[it[0] for it in rec["frames"]],
                severity=finding.get("severity"), damage_area_fraction=finding.get("damage_area_fraction")))
        # BYTETracker only returns a track once it has been matched in a second frame, so a lone sighting never appears in its
        # output at all. Report those explicitly: nothing may disappear without a record (the original dropped them silently).
        for idx, k, f in seen:
            if (idx, k) not in linked:
                dropped.append(DroppedTrack(-1, f.get("damage_class") or "unknown", f.get("part_class") or "unassigned", 1,
                                            f"frame {idx}: single sighting, not matched in a second frame"))
        return entities, dropped
