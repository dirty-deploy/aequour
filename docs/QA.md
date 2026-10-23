# Questions judges are likely to ask

Honest answers, with where the evidence is. Figures come from `docs/DECK_NUMBERS_FINAL.md`; "not measured" means we did not measure it.

**1. How is the offer computed?**
Per damaged panel: the listed genuine-part price less depreciation (when the part is replaced), plus fitting labour, plus paint less the paint-material depreciation. Lines are summed, the compulsory deductible is subtracted, and the cheaper of repair and replace is used for a dent. Every number is in `autosettle_engine/config.py` with a tag (REAL, RULE or ASSUMPTION), and every claim shows its lines and an assumption ledger. The Swift demo is one line: front bumper replacement, ₹2,763 after the deductible. Evidence: `engine.price_line`, `rationale.py`, 48 engine tests.

**2. Why does code decide and not the language model?**
A language model can be argued with, and the money must not be. The model only rewords the engine's own derivation and reads quote or plate photos. A checker blocks any reply that adds a figure, drops a line, names the upper bound or promises something, and the template is used instead; no free text from the customer reaches any input of the pricing code. Evidence: attacks `prompt_injection_in_chat`, `llm_*` (5 scripts), 20 of 20 attack scripts held, and the attack console in the app. These tests were written against the same code, so they show these attacks fail, not that none exists.

**3. What if the model misses damage?**
It happens, and it is the main weakness. On 41 public dev photos the models find 22 of 74 labelled damaged parts; 25 of 74 are never outlined; in 8 cases a damaged part was missed inside a claim that still ended in an offer, so that offer under-pays. Two things limit the harm: the failure direction is under-payment, never over-payment, and the customer can send a garage quote, which moves the offer if the photos support it, or ask for a surveyor. No rule drops a detection or lowers an offer. Evidence: `tools/eval_dev.py`, `docs/FEATURE_COVERAGE.md`.

**4. What about scratches?**
The damage detector used at run time has no scratch class, and the problem statement names scratches. A scratch is not outlined as a scratch. A photo whose only damage is a scratch gets ASK_MORE twice and then ESCALATE (checked directly against the engine); it never ends in an offer. A scratch next to other damage is left out of the offer. A 4-class model has a Surface damage class trained on merged scratch, paint chip, flaking and corrosion labels (mask mAP50 0.18), but the pipeline discards it because it is too weak to trust.

**5. Does it work on Indian cars and Indian photos?**
The rate card and policies are for Indian models (Swift, Baleno, i20, Punch, Brezza, Venue, Nexon, Creta), and the prices are listed Indian MRPs. The vision side was built from public datasets and evaluated on public Commons photos that are mostly not Indian cars and are wide shots, not the close protocol photos the system asks for. Accuracy on real Indian claim photos at scale is **not measured**.

**6. Fraud and duplicate claims?**
Built: a near-duplicate check against photos from other claims (perceptual-hash distance at most 4), an editing-software tag check, a plate match, a video continuity check that flags a cut or a different car, repeat-quote and quote-padding limits, and a hash-chained audit log. Not built: staged accidents, old damage presented as new, a photo of a screen, the same photo reworked, cross-insurer checks. The duplicate store only knows photos this server has seen.

**7. Privacy and number plates?**
In the demo the plate is typed, and the number plates on the demo photos are blurred on the displayed copy (the pipeline reads the original). Uploaded photos are stored on the server for the claim, in a runtime folder that is not committed. There is no consent flow, no retention or deletion policy, and no face blurring. Data-protection compliance was not assessed.

**8. How does it handle counteroffers?**
The offer moves only on evidence. The customer can accept, send an itemised garage quote, repair at a partner garage, or ask for a surveyor. A figure named in a message changes nothing; the reply names the current offer and those routes. A quote line moves the offer if the photos show that part and its price is inside the genuine range; at most two quotes count, and the offer never passes the internal upper bound the customer does not see. In the recorded counteroffer scenario the offer went from ₹2,763 to ₹3,063 on one supported quote and stayed there through an inflated quote and two pressure messages. The engine does not negotiate numerically and we did not build negotiation logic. Evidence: `docs/FEATURE_COVERAGE.md`, `tools/counteroffer_script.py`.

**9. Does it work on video?**
It accepts a clip of at most 60 s and at most 12 keyframes, and a continuity check flags a cut or a different car. It is tested on **synthetic clips** (6 of 6 video attack scripts held; a looped video of one photo gives the same offer as the photo). Two real night-time phone clips were run once each on 23 Oct 2026 (n = 2): both were flagged as not confirmed continuous and escalated with no offer. That is a first test, not a measurement, and nothing about real walk-around video is measured. A walk-around that turns a corner quickly, or shaky or dark footage, is flagged and named "could not confirm one continuous take" (or "hard cut" when the look changes sharply), which costs a human look, not money. Damage seen in only one keyframe becomes a request for a clearer view instead of a guess.

**10. How fast is it?**
On the development laptop (RTX 5050 laptop GPU, 8 GB): 3.7 s for the first live assessment (models load), 0.35 s warm, and 55 s for the first offer with the language model loaded. A looped 30-frame video took 3.9 s. One demo claim on one machine.

**11. What does a claim cost to run, and where would it be hosted?**
Not measured. The demo runs locally because the live stack needs a GPU; replay mode needs none. The language-model run used 7,788 MiB of GPU memory, above what we budget for an 8 GB card.

**12. What about regulation?**
Not assessed. The surveyor limit, deductible, depreciation and paint-material rule are rules as used in our research, and should be verified before anyone relies on them. The review threshold and the 75% total-loss share are team assumptions. See `docs/ASSUMPTIONS.md`.

**13. What would you do with more time?**
Collect real claim photos taken to the protocol and re-measure recall; train a detector with a scratch class and measure it on photos it was never tuned on; get severity labels from adjusters; calibrate labour and paint against real garage quotes and invoices; test the video path on real walk-arounds; add authentication and a real adjuster queue; assess privacy and regulation.

**14. Why are the numbers on hard photos low?**
The evaluation photos are public, mostly non-Indian, wide shots of crashed cars, not the five protocol photos the system asks for (plate, front, side, rear, close-ups), and the labels are Claude's by eye. 25 of 74 labelled parts were never outlined by the parts model; retraining on 4,937 more images and changing the image size moved found parts only from 22 to at most 25, and per-panel crops raised it to 34 but with more false alarms than our pre-set limit, so we did not adopt it. The numbers are low because the problem on those photos is hard and because the system declines to guess; we did not tune to improve them on the unseen set.
