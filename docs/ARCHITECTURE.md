# Architecture

Design rule: the AI perceives and talks; deterministic code decides every rupee.

```
 browser (web/, built into autosettle_api/static)
   landing + claim flow (customer)         adjuster view (dense, demo only)
        |                                        |
        v                                        v
 FastAPI  autosettle_api  (python -m autosettle_api [--replay] [--no-qwen] [--video on|off])
   /claims  /photos /plate /video /assess /quote /message /choose /audit     /adjuster/{id}   /limits  /health
        |  one ClaimSession per claim (state machine, hash-chained audit log, JSON copy in final/runtime)
        v
 vision backend ---- LIVE: autosettle_vision.pipeline.run_claim  (GPU)        ---- REPLAY: recorded JSON, labelled "REPLAY"
   photos:  quality + edit-tag + duplicate checks -> parts_s (21 panels) -> dent_det (14 damage classes) -> damage_merged_s
   video:   sampler (<=60 s, <=12 keyframes) -> each keyframe as a photo -> fusion (>=2 keyframes) ; continuity check -> escalate
        |   (vision dictionary: detections, flags, integrity flags)
        v
 autosettle_engine  (unchanged; no AI)   information gate -> decision OFFER / ASK_MORE / ESCALATE / SURVEYOR
   rate card -> itemised lines -> depreciation -> deductible -> offer, ceiling fixed before any conversation
   dispute: a garage quote line moves the offer only if photos support it and the price is inside the genuine range
        |
        v
 language layer (Qwen3-VL 4-bit, optional): rewords the engine's rationale (checked against the engine's numbers before the
 customer sees it), reads a quote or plate photo. It never sees the ceiling or the pivots.
```

## What the layers may and may not do
- The frontend and the API compute no price. They display what the engine returned. Customer routes never return the ceiling, the pivots or internal assumptions; the adjuster route returns detections, evidence per line and the assumption ledger (labelled demo-only, no authentication is claimed) and also omits the ceiling.
- A check may escalate or ask for more evidence; it may never silently drop a detection or lower an offer. A video clip with a cut or a different car is flagged and escalated. Damage seen in one keyframe only becomes a request for a clearer view.
- REPLAY mode serves recorded vision output so the demo works without the GPU. The engine runs live in both modes. Every response and the page say REPLAY.

## Measured and assumed
Measured: see `docs/DECK_NUMBERS_FINAL.md` (22 of 74 damaged parts found on 41 dev photos, 8 silent misses, 20 of 20 attacks held, 48 + 18 + 9 tests). Assumed (all labelled in `autosettle_engine/config.py` and in the adjuster ledger): labour and paint price ranges, severity bands from area fraction, the 0.50 low-confidence-severe rule, the 40,000 review threshold. Not validated: real walk-around video, severity accuracy, real Indian claim photos at scale.

## Where things are
`autosettle_engine/` money logic and attack suite; `autosettle_vision/` pipeline, Qwen wrapper, video modules, experiments (`crops.py`, `surface_check.py`, off by default); `autosettle_api/` API, replay data, tests, built UI; `web/` UI source; `tools/` evaluation and demo checks (`eval_dev.py` is the one command every number comes from).
