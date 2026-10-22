# Weights

Weight files used by the pipeline (names and sizes from the working folder):

- `damage_merged_s_best.pt`: 101.5 MB
- `damage_s_best.pt`: 20.5 MB
- `dent_det_best.pt`: 19.2 MB
- `parts_s_best.pt`: 20.5 MB

Not stored in this repository: they are large, and the vision stack (Ultralytics) is AGPL-licensed. The team shares them privately on request.

To use live mode, create a folder named `backup` at the top of the repository (next to `autosettle_api`) and put these three files in it:

- `parts_s_best.pt`
- `dent_det_best.pt`
- `damage_merged_s_best.pt`

(`damage_s_best.pt` is an earlier model and is not loaded.) `backup/` is git-ignored. Then install `requirements-live.txt` and run `python -m autosettle_api --live --fresh-seen`. Replay mode does not need any of these files.
