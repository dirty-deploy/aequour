"""
Video claim path: keyframes -> the existing photo pipeline (one photo per keyframe) -> the existing multi-photo fusion.
The result is the same vision dictionary the photo path returns, plus a "video" block for the audit log. The engine is unchanged.
"""
from . import pipeline as P
from . import video as V
from . import video_integrity as VI


def run_video_claim(path, claim_id=None, seen=None, analyse=None):
    """Raises video.VideoRejected for files that cannot be evidence. `analyse` replaces pipeline.analyse_image (tests)."""
    frames, info = V.sample_keyframes(path)
    cont = VI.check_video(path)
    v = P.run_claim([], claim_id=claim_id or "video", seen=seen, frames=frames, extra_integrity=VI.flags(cont), analyse=analyse)
    tr = sorted(cont["transitions"])
    v["video"] = {**info, "continuity_frames_checked": cont["frames_checked"], "continuity_breaks": cont["breaks"],
                  "continuity_hard_cuts": cont["hard_cuts"], "continuity_unverified": cont["unverified"],
                  "continuity_max_appearance": cont["max_appearance"], "continuity_median_appearance": cont["median_appearance"],
                  "continuity_outcome": VI.outcome(cont), "continuity_seconds": cont.get("seconds"),
                  "min_inliers": VI.MIN_INLIERS, "continuity_lowest": tr[0] if tr else None,
                  "continuity_median": tr[len(tr) // 2] if tr else None, "thumbnails": V.thumbnails(frames),
                  "keyframe_names": [n for n, _ in frames]}
    return v
