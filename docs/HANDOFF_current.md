# Auto-Settle AI: current handoff (after RUN1, 21 Oct 2026)

Design rule: the AI perceives and talks; deterministic code decides every rupee. Qwen never receives the ceiling,
the ceiling lines or the internal pivots.

## Layout (C:\autosettle)
| Path | What |
|---|---|
| `autosettle_engine/` | Money: `engine.py` (assess, info gate, rules), `rationale.py` (customer text + checker + audit-repair), `dispute.py` (quote check, state machine, hash-chained audit), `config.py` (every tunable, tagged), `exploit_suite.py`, `tests/` |
| `autosettle_engine/rate_card_v3.csv` | Rate card the engine loads (v1 and v2 kept for audit) |
| `autosettle_vision/` | YOLO pipeline, Qwen layer, web app, evals (see its README) |
| `backup/*.pt` | Model weights (parts, dent detector, damage segmenters) |
| `tools/` | Builders (`build_rate_card_v2/v3.py`), coverage, sweeps, thermal guard (`thermal.py`, `run_guarded.py`), RUN1 evals |
| `test_photos/commons` | 41 dev photos + `ground_truth.csv` + `SOURCES.csv` (licences) |
| `test_photos/heldout`, `results_heldout.md` | Held-out set: spent, read-only |
| `run1/` | This run's log, reports, caches, thermal log |

## Run
- App: `.\env\Scripts\python.exe -m autosettle_vision.app` → http://127.0.0.1:7860 (loads Qwen; close it before any other GPU job).
- Tests: `.\env\Scripts\python.exe -m unittest discover -s autosettle_engine/tests -t .` (39 tests, about 0.5 s).
- Attacks: `.\env\Scripts\python.exe -m autosettle_engine.exploit_suite` (20 scripts + 1 control).
- Any GPU job: `.\env\Scripts\python.exe tools\run_guarded.py --tag NAME -- <command>`. On this laptop Qwen generation
  trips the CPU hard limit (see the thermal note below).

## Key config (`autosettle_engine/config.py`)
| Value | Setting | Tag |
|---|---|---|
| Surveyor required at gross loss | ₹50,000 | RULE (IRDAI) |
| Human review at gross loss | ₹40,000 | ASSUMPTION |
| Constructive total loss | 75% of IDV | ASSUMPTION |
| Deductible | ₹1,000 up to 1,500 cc, else ₹2,000 | RULE |
| Min part / damage confidence (info gate) | 0.50 / 0.30 | ASSUMPTION |
| **Severe call below this confidence → human (new)** | 0.50 | ASSUMPTION |
| Quote part tolerance | 115% of reference | ASSUMPTION |
| Distinct quotes that can move an offer | 2 | ASSUMPTION |
| Paint share of a panel package | 60% | ASSUMPTION |
| Vision: inference size / detector confidence | 960 px / 0.25 | tuned on dev photos (`autosettle_vision/pipeline.py`) |
| Severity bands (area fraction) | < 0.30 minor, < 0.60 moderate | ASSUMPTION, weakly calibrated |
| Heavy crash → surveyor | 3+ severe parts, severe hood + 1, or both doors severe | ASSUMPTION |

## Verified vs assumed
**Verified (measured or opened):**
- Part prices on A rows (part page, MRP incl. GST, fitment window).
- Engine invariants (fuzz, 5,000 claims).
- Attack scripts.
- Detector scores on its own test split.
- Pipeline recall and precision on the 41 dev photos.
- Held-out outcomes (0 offers).
- Qwen VRAM and speed.
- Quote reading on synthetic images.
- Chat path never changes a number.

**Assumed:**
- Labour and paint (public garage ranges; no real quotes).
- Severity bands.
- Review and total-loss thresholds.
- The heavy-crash and low-confidence-severe rules.
- GST treatment.
- Base-variant prices for higher trims.
- Simulated policy records and plates.

**Not measured:**
- The audit-repair loop's effect.
- Handwritten quotes.
- Real Indian claim photos at scale.
- Severity accuracy.

## Open items for the team
1. Thermal: decide which CPU sensor and hard limit to use (see `run1/qwen_repair_report.md`). Then re-run
   `tools/qwen_repair_eval.py`; it resumes from its cache.
2. In `autosettle_vision` (outside RUN1's edit list):
   - make `qwen.parse_quote_json` tolerant of a missing bracket;
   - optionally switch `claim.customer_text` to `rationale.safe_reply_repair`.
3. Routing: legal or ombudsman threats are logged but not routed to a human.
4. Two-piece bumpers: the Punch and Brezza 1st-gen bumpers are priced from the upper skin only (tier C, replace
   price understated).
