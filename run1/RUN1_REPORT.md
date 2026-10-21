# RUN1 report (unattended, 21 Oct 2026, 00:56 → about 01:26)

Tasks 0–7 took about 30 minutes, well inside the 105/120-minute limits. Tests at the end: 39 pass; exploit suite 20/20
held. No weights, training, dataset downloads, deletions or package-version changes. `test_photos/heldout` and
`results_heldout.md` were not touched.

| Task | Result | One line |
|---|---|---|
| 0 Preconditions + thermal guard | done | No GPU job to stop (desktop apps only; LibreHardwareMonitor left alone); AC on; LHM at :8085; `tools/thermal.py` + `tools/run_guarded.py`; self-test passed (suspended about 9 s, resumed, 39 s wall) |
| 1 Backup, baseline, fuzz | done | Backup at `C:\autosettle_backup_run1` (datasets excluded: 6.6 GB > 3 GB; weights included). 29/29 tests already passed, so the "28 of 29" premise was out of date. 5,000-claim fuzz passes (0.2 s) |
| 2 Rate card v3 | done | 25 rows fixed + 1 sum row, all from pages opened this run; engine loads v3; 2023 coverage 70 matched / 22 other-gen / 12 fallback / 0 none (direct 93 → 92); 2 tests added |
| 3 Low-confidence-severe rule | done | ESCALATE `low_conf_severe` if a severe call has confidence < 0.50; dev photos: offers 9 → 7, removing 2 correct offers and 0 wrong ones |
| 4 Audit-repair loop | **failed (skipped after 2 THERMAL_KILLs)** | Code + 3 tests done (`safe_reply_repair`); measured on only 6 of 30 claims (0 violations either way). No result claimed |
| 5 Conversation + quotes | done | 25 messages: no number ever changed; classifier 6/10 injections, 2/5 abuse before keyword fixes. 15 quotes: 42/53 lines exact, 0 offers above ceiling |
| 6 Documents | done | `DECK_NUMBERS.md`, `HANDOFF_current.md` |
| 7 Freeze | done | `C:\autosettle_FROZEN_20261021` (155 MB), `FROZEN_HASHES.txt` (19 files, all equal to the working copy) |
| 8 VGGT spike | skipped | Precondition not met (Task 4 not done). Also, every Qwen job tripped the CPU hard limit, and VGGT is heavier and needs its own torch install and weights |

## Top three things to look at
1. **Thermal protocol vs this laptop.** The required CPU reading (highest AMD sensor = per-CCD Tdie) jumps 12–20 °C in
   a single 2-second poll as soon as Qwen generates. It reached **92.5 °C and 90.3 °C** for one poll each (above your
   90 °C target) before the guard killed the job. GPU never exceeded 67 °C. Decide the sensor (Tctl reads about 9 °C
   lower) or a two-poll kill rule before any more Qwen work. Task 4's measurement is blocked on this.
2. **The low-confidence-severe rule has a cost.** On the dev photos it removed 2 correct offers and caught none of the 2
   wrong ones (their damage was read as moderate). It does fix the held-out undamaged-Swift case it was written for.
   Keep it as a stated assumption, or drop it; it is one constant (`LOW_CONF_SEVERE`).
3. **Rate-card changes that move money.**
   - Brezza 2nd-gen front bumper ₹2,050 → ₹4,120 (upper + lower skin).
   - Nexon headlamp ₹8,724 → ₹9,783 (the old figure was a selling price, not the MRP).
   - The grille fallback rose ₹4,060 → ₹5,299 after the bad Nexon grille row was rejected.
   - The Punch and Brezza 1st-gen bumpers are priced on the upper skin only (tier C, understated).

## Peak temperatures (`run1/thermal_log.csv`, 365 polls, guarded jobs only)
| Job | GPU max | CPU max | Suspends | Kill |
|---|---|---|---|---|
| Guard self-test | 48 °C | 73.9 °C | 5 | – |
| Task 3 (YOLO on 41 photos) | 52 °C | 83.0 °C | 6 | – |
| Task 4 attempt 1 (Qwen) | 65 °C | 90.3 °C | 12 | yes |
| Task 4 attempt 2 (Qwen, 4 threads) | 64 °C | 92.5 °C | 34 | yes |
| Task 5 quotes attempt 1 (Qwen) | 67 °C | 86.4 °C | 55 | yes |
| Task 5 quotes retry (Qwen) | 61 °C | 81.9 °C | 18 | – |
| **Overall** | **67 °C** | **92.5 °C** | 130 | 3 |
