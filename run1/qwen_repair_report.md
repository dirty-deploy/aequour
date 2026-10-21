# Task 4: audit-repair loop for Qwen wording

**Status: code done and tested; measurement skipped after two THERMAL_KILLs (rule 5).** Only 6 of 30 claims ran.

## What changed (autosettle_engine/rationale.py)
`safe_reply` (unchanged) only checks the model's wording and falls back to the fixed template. Added beside it:
- `describe_violations(viol)`: plain-language notes for the model. It never includes the ceiling: `ceiling_leak`
  values are dropped, and stray rupee amounts (`unknown_amount`) are not repeated, because a test showed the stray
  amount can be the ceiling itself (the first draft of this function leaked it; the test caught it).
- `safe_reply_repair(draft, result, repair, ...)`: SAVER-style audit, then repair. If `check_rationale` finds violations,
  call `repair(notes)` up to 2 times and re-check each time. Use the fixed template only if the last attempt still
  fails. Returns `(text, used_model_wording, violations, repair_rounds)`.
- The repair prompt in `tools/qwen_repair_eval.py` holds the engine's original explanation and the rule notes. It
  never holds the ceiling, the internal pivots, or the failed draft (a failed draft may contain the ceiling).
- Tests (`AuditRepairLoop`, 3): a bad draft is repaired in one round and no repair note contains the ceiling; a
  repair that keeps failing stops after 2 rounds and falls back; a clean draft needs no repair. Suite: 38 pass;
  exploit suite 20/20.
- **Not wired into the app.** `autosettle_vision/claim.py` still calls `safe_reply`. That file is outside this run's
  allowed-to-edit list. One line in `customer_text` would switch it.

## Measurement (incomplete)
Plan: 30 scripted claims (`tools/qwen_repair_eval.py`: all 8 models, deductible ₹1,000 and ₹2,000, an
other-generation price, a similar-car fallback, 1–3 parts). There is one Qwen draft per claim, so repair off and
repair on start from the same text.

| | Attempt 1 | Attempt 2 (CPU-limited: 4 threads, cooldown to CPU ≤ 72 °C before each generation) |
|---|---|---|
| Claims finished | 2 | 6 (2 from cache) |
| Stopped by | THERMAL_KILL 01:09:16, CPU 78.3 → 90.3 °C in one 2 s poll | THERMAL_KILL 01:12:32, CPU 70.6 → 92.5 °C in one poll, 2 s after resuming |
| GPU max | 65 °C | 64 °C |

Raw results for the 6 claims that finished (all Swift: bumper; bumper + fender; 4th-gen bumper priced from another
generation; grille priced from a similar car; mirror; door scratch):

| Mode | Model wording used | Template fallback | Violations |
|---|---|---|---|
| Repair off | 6 | 0 | none |
| Repair on | 6 | 0 | none (0 repair rounds needed) |

6 claims with 0 violations say nothing about whether repair helps: repair never triggered. Earlier, Qwen passed 6 of 6
on different claims (`runs/qwen_eval.json`, 20 Oct). **No improvement is claimed.** Cached drafts are in
`run1/cache/qwen_repair.json`; re-running the script resumes from them.

## Why it stopped
The CPU reading the protocol asks for is the highest `/amdcpu/` sensor. On this Ryzen 9 8940HX that is a per-CCD Tdie
value, and it spikes by 12–20 °C between two 2-second polls the moment Qwen starts generating. The spike happens even
right after a cooldown to 70 °C. The GPU stayed at or below 65 °C. With the 86 °C hard limit on that sensor, Qwen
generation cannot run on this laptop. Options for the user (not decided here):
- use the "Core (Tctl/Tdie)" sensor instead, which read about 9 °C lower at idle;
- raise the CPU hard limit for short spikes, for example kill only on two polls in a row above 86;
- run the evaluation on another machine.
