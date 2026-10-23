# Test guide: a click path for someone with no documents

Everything here runs in replay mode: no GPU, no weights, no photos or quotes of your own. Samples are labelled RECORDED or SYNTHETIC in the app. Times are from the development laptop.

## 0. Start
1. `python -m pip install -r requirements-replay.txt`, then `python -m autosettle_api --replay`.
2. Open <http://127.0.0.1:8000>. The page shows a REPLAY badge in the top bar, and the footer shows the build id.
3. Optional check first: `python tools/smoke.py` should end with `14 of 14 steps passed`.

## 1. The first minute (no clicking needed)
1. The hero reads "The AI looks. Code pays." Move the cursor over the hero: a ghost "Aequour" appears behind the buttons.
2. Scroll. The pinned scene turns one photo into planes (photo, panel outline, damage box) and then an itemised receipt: **Front bumper: replace ₹3,763, deductible -₹1,000, Offer ₹2,763** (the total counts up).
3. Keep scrolling: "Two jobs, kept apart", "What is in a claim" (six miniatures of real components), "Try to break the money logic" (attack console), "Try a claim", "The whole system on one page".

## 2. Try a claim (left column, one click each)
| Click | What it must show |
|---|---|
| A protocol-compliant claim reaches an offer | OFFER **₹2,763**, photo with the front-bumper detection (plate blurred), itemised lines, "Read the explanation" |
| A heavy crash goes to a surveyor | **Surveyor visit**, no price, four severe detections drawn |
| A prompt-injection attempt changes nothing | OFFER stays **₹2,763**; the chat shows the hostile message and the system's reply; "blocked" flashes |
| A wide street photo ends in a request for more | **More needed**, no offer, a list of what to send |
| A counteroffer moves the offer only on evidence | **Offer before your quote ₹2,763, Updated offer ₹3,063**; the chat shows 11 turns, each system turn with its wording ("template") and audit entry |

## 3. The quote dispute (on the first scenario)
1. **Garage quote** tab (under the chat), "Use the recorded quote": the table shows Bumper Front Assy ok, Labour ok, Painting above range; **₹2,763 becomes ₹3,063**. The big number is the updated offer and the old one stays beside it.
2. "Try an inflated quote (x5)" on a fresh claim: every line above range, the offer does **not** move.
3. A quote of your own: `python tools/make_quote.py --claim <id> --post` (the claim id is in the Adjuster view link), or write `synthetic_quote.jpg` and its JSON, then send the JSON. The image is stamped SYNTHETIC. Reading a quote *photo* needs the live pipeline and the language model.

## 4. Counteroffers and pressure
In the chat of a claim with an open offer, type "I want ₹6,000 for the bumper": the reply names the current offer and the routes that can move it, and the offer does not change. Repeat it: "The answer stays the same." Abusive or legal-threat words go to a person.

## 5. Video
**Video** tab (under the chat): "Recorded walk-around" (SYNTHETIC) shows 12 keyframes with sharpness and light scores, a continuity result (continuous), the damage tracked across keyframes (Front bumper dent in all 12) and the decision (OFFER ₹2,763). "Recorded walk-around, closer" ends in **More needed**: the roof shows damage in a single keyframe, so the system asks for a clearer view instead of guessing. Both are a zoom and pan over one photo, not real footage. Uploading a clip needs the live pipeline.

## 6. The attack console
Guardrails scene, **Run all**: 21 scripts run on fresh in-memory claims; every one is marked Held, and the honest-quote control is marked Held because the offer moved a little, as it should. "Show what happened" on any row gives what was attempted, what the system did, and whether the offer and the audit chain were unchanged.

## 7. The adjuster view (demo only)
From any claim, "Adjuster view": the allowable range (initial and current offer, the internal upper bound, the guardrails that stop a higher number), the escalation packet for the surveyor claim (reasons, evidence, audit events), the assumption ledger (OBSERVED, IMPUTED, UNRESOLVED), the detections table and the audit chain with its verification result. The customer view never shows the upper bound.

## 7b. The estimate on the adjuster page
Open the adjuster view of any recorded claim: the **Estimate from what the system can see** section sits above the allowable range. On the offer claim it shows ₹2,763 to ₹4,213 (gross ₹3,763 to ₹5,213, deductible ₹1,000) labelled "an estimate, not an offer"; on the surveyor claim it shows a figure although the engine priced nothing. The customer page never shows it.

## 7c. Your own clip (live mode only)
Start `run.ps1 demo-live`, choose **Video** in the left panel, pick a clip and press **Check my claim**. In replay mode the control is visible but disabled and the page names this command.

## 8. If something fails
- `python -m autosettle_api --replay` is the safest start.
- `--ui v1` serves the earlier web build.
- With a GPU: `--no-qwen --fresh-seen`, then `--fresh-seen`.
- The recording in `final2/deck_assets/` shows the whole path.
