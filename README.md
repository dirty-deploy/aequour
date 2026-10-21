# Aequour

**Aequour** (from Latin *aequus*, "fair, level") settles small motor-insurance claims from photos of the damage. Vision models identify the part and the damage. A deterministic engine prices it from a sourced genuine-parts rate card, inside hard limits the AI cannot cross. A garage quote is checked line by line against the evidence, and every event goes into a hash-chained audit log.

> **Status:** hackathon prototype (Confluentia 2026 x Tredence). On 8 unseen real-world photos it made 0 offers, because plate and parts checks stopped them; recall on damaged parts was about 30% on the dev photos; labour and paint prices are estimates. See `docs\` and `run1\DECK_NUMBERS.md` for measured numbers and limits.

Package names keep the `autosettle_` prefix from the project's earlier working name.

## Design rule
The AI perceives and talks; deterministic code decides every rupee. The language model never receives the ceiling, the ceiling lines or the internal pivots, and the chat path never changes a number.

## Layout
- `autosettle_engine/`: the money logic (`engine.py`, `rationale.py`, `dispute.py`, `config.py`), rate cards, tests and the attack suite (`exploit_suite.py`).
- `autosettle_vision/`: YOLO pipeline, Qwen layer, web app and evals (see its README).
- `tools/`: rate-card builders, coverage and sweep scripts, the thermal guard.
- `scripts/`: data download and conversion scripts (set `ROBOFLOW_API_KEY` in your environment first).
- `run1/`: logs, reports, caches and numbers from the frozen Run 1 state.
- `docs/`: handoff and process notes.

## Run
Python 3.10+ with the packages the vision README lists; model weights are not in this repository (see `weights/README.md`).

```
# tests (engine only, about 0.5 s)
python -m unittest discover -s autosettle_engine/tests -t .

# attack suite (20 scripts + 1 control)
python -m autosettle_engine.exploit_suite

# web app (needs the weights and a GPU; loads Qwen)
python -m autosettle_vision.app     # http://127.0.0.1:7860
```

## Honest limits
- Measured: engine invariants (fuzz, 5,000 claims), attack scripts, detector scores on its own test split, pipeline recall and precision on 41 dev photos, 0 offers on the 8-photo held-out set, quote reading on synthetic images.
- Assumed, not measured: labour and paint prices, severity bands, review and total-loss thresholds, GST treatment, base-variant prices for higher trims, simulated policy records and plates.
- Not measured: handwritten quotes, real Indian claim photos at scale, severity accuracy.
- Dev-photo labels in `test_photos/commons/ground_truth.csv` were made by Claude by eye, not by a person.

## Credits
Built for the Confluentia 2026 x Tredence hackathon. Photos and datasets keep their own licences (see `test_photos/commons/SOURCES.csv` and `scripts/download_data.py`).
