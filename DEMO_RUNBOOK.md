# Demo runbook (22 Oct presentation)

## Start (PowerShell, from the repository folder)
```powershell
cd <repo folder>
$env:AEQUOUR_DEV_PHOTOS = "<folder with the 41 dev photos>"     # lets the four scenarios show their photo
$py = "<python environment>\Scripts\python.exe"

& $py -m autosettle_api --replay                    # safest: no GPU, no model, deterministic scenarios (page says REPLAY)
& $py -m autosettle_api --no-qwen --fresh-seen      # live photo pipeline, fixed-template wording
& $py -m autosettle_api --fresh-seen                # live photo pipeline with the language model
```
Then open http://127.0.0.1:8000 . Port 8000. Weights are found through the git-ignored junction `backup\` (to your weights folder); the duplicate-photo store is emptied by `--fresh-seen`. Ctrl+C stops the server.

## Measured start-up (RTX 5050 laptop, 21 Oct)
| mode | time |
|---|---|
| `--replay`, server answering `/health` | 0.8 s |
| live, `--no-qwen`, server answering | 0.8 s; the first assessment loads the three detectors: 3.7 s; warm assessments 0.35 s |
| live with the language model | server 0.8 s; the first OFFER loads Qwen3-VL (4-bit) and rewords: 55 s; GPU memory 7.8 GB of 8 GB, so close other GPU programs and do not run a benchmark at the same time |
| scenario button (replay), each of 12 runs | 0.01 to 0.05 s |

## If something fails
- GPU or a model error (the page shows "the vision pipeline failed"): restart with `--replay`.
- Qwen slow or out of memory: restart with `--no-qwen`; offers still show the engine's fixed-template explanation, quote photos and plate photos then need typed input or the recorded quote.
- Uploading the same photo in a second claim escalates it ("photo seen in an earlier claim"). That is the duplicate check working; restart with `--fresh-seen` or use a different photo.
- Chrome shows an old page: hard refresh (Ctrl+F5).

## The four scenarios (Run this claim)
| scenario | what the judge sees | expected result |
|---|---|---|
| A protocol-compliant claim reaches an offer | Swift front-end photo, plate matches policy | OFFER ₹2,763 (front bumper, replace, genuine part ₹2,250, 50% depreciation, labour ₹800, paint ₹2,100 less ₹262, deductible ₹1,000); "Use the recorded demo quote" moves it within rules |
| A heavy crash goes to a surveyor | Alto crash photo, several severe panels | SURVEYOR, no price |
| A prompt-injection attempt changes nothing | the offer scenario plus a hostile message | offer unchanged at ₹2,763, message flagged |
| A wide street photo ends in a request for more | Chennai street photo, nothing the models can price | ASK_MORE, no offer, lists what to send |

Each was run three times end to end (`python tools/demo_check.py --runs 3`): 12 of 12 passed, decision and offer identical every time, audit chain intact. Result in `final/demo_check_replay.txt`.

The Swift photo shows a readable number plate. In the photo the heavier damage is on the passenger side, while the system prices the front bumper only: say so if asked, it is the system's real behaviour.

## Three questions judges are likely to ask
1. **How good is recall on hard photos?** 22 of 74 labelled damaged parts found on 41 public photos (mostly non-Indian cars, wide shots), labels made by Claude by eye. 25 of 74 are never outlined by the parts model. Retraining on 4,937 more images moved that to at most 25 of 74, so we did not swap the model. Running the damage detector on each panel crop finds 34 of 74 but raises false alarms (3 of 6 clean photos instead of 1), so it is off.
2. **Why zero offers on unseen photos?** On 8 photos run once and never tuned to, plate and parts checks stopped every claim: 5 asked for more, 3 went to a human (plate mismatches against simulated policies), 1 to a surveyor. The system declines rather than guesses. The flip side: we have no evidence yet of correct offers on unseen photos, and on the dev photos none of the 6 offers on damaged cars found every labelled damaged part.
3. **What is estimated?** Part prices are listed prices (rate card, 151 rows); labour and paint are estimates from garage price ranges, not real quotes; severity comes from the share of the panel covered (assumed bands); GST treatment and other-generation part prices are imputed. All are labelled OBSERVED, IMPUTED or UNRESOLVED in the adjuster view.

## Files
Screenshots: `final/screens/`. Numbers: `docs/DECK_NUMBERS_FINAL.md`. Limits shown in the app: `docs/LIMITS.json`.
