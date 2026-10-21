# Held-out photo results

Run 21 Oct 2026 on the team laptop. No project code was changed. Each run uses the same steps as the web app (`autosettle_vision.app.assess`): `pipeline.run_claim` with Qwen3-VL-8B (4-bit) as the plate reader → `claim.engine_vision` → `ClaimSession.submit` → `claim.customer_text`.

Run conditions:
- One run per photo. The Creta photo was run twice: on its own, then with the synthetic demo plate image (`test_photos/demo/00_plate_DL3CAB1234.jpg`) uploaded first, as the capture protocol asks.
- Policy per run: the simulated policy for the same model where one exists (Creta → POL-DEMO-003, Nexon → POL-DEMO-002, Swift → POL-DEMO-001). The Dzire and the unidentified black SUV have no matching policy, so they used the app's default, POL-DEMO-001 (Swift). Detections do not depend on the policy; price and the plate check do.
- One deviation from the app: each run used a fresh, empty duplicate-photo store, so the two Creta runs did not flag each other. The app's persistent store would mark the second Creta run as a reused photo and send it to a human.
- Decision words: offer = OFFER, ask for more = ASK_MORE, surveyor = SURVEYOR, human = ESCALATE.

## Summary

| # | Photo | Policy used | Decision | Offer | Plate read | Reasons |
|---|---|---|---|---|---|---|
| 1 | Hyundai Creta, heavy front crash - no plate image | POL-DEMO-003 | ask for more | - | not read | plate_verified, parts_identified |
| 2 | Hyundai Creta, heavy front crash - with synthetic demo plate image first | POL-DEMO-003 | human | - | DL3CAB1234 | plate_mismatch |
| 3 | Tata Nexon (teal), two-photo collage, front crash | POL-DEMO-002 | ask for more | - | not read | plate_verified |
| 4 | Tata Nexon (black), heavy front crash | POL-DEMO-002 | surveyor | - | not read | structural_or_safety_damage |
| 5 | Black SUV (model not identified), heavy front-left crash | POL-DEMO-001 | human | - | DL11AV1234 | plate_mismatch |
| 6 | Maruti Dzire (white), heavy front crash | POL-DEMO-001 | ask for more | - | not read | plate_verified, parts_identified, damage_identified |
| 7 | Maruti Swift (white), side crushed, Shutterstock watermark | POL-DEMO-001 | ask for more | - | not read | plate_verified, parts_identified, damage_identified |
| 8 | Maruti Swift (grey), no visible damage | POL-DEMO-001 | human | - | UP78HD2313 | plate_mismatch |
| 9 | Tata Nexon.ev studio image, no damage | POL-DEMO-002 | ask for more | - | not read | plate_verified, parts_identified, damage_identified |

## 1. Hyundai Creta, heavy front crash - no plate image

- Files: `WhatsApp Image 2026-10-21 at 12.15.25 AM.jpeg`
- Policy: POL-DEMO-003 (Hyundai Creta, plate UP16BT4521)
- **Decision: ask for more**
- Reasons: plate_verified, parts_identified
- Missing information fields: plate_verified, parts_identified
- Plate read by Qwen: not read
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.15.25 AM.jpeg

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Front-bumper | Dent | moderate | 0.3788 | 0.358 | dent_det:front-bumper-dent |
| Front-door | Dent | moderate | 0.4908 | 0.359 | dent_det:doorouter-dent |
| Hood | Dent | severe | 0.7569 | 0.852 | dent_det:bonnet-dent |

Message shown to the customer (fixed template):

> We need a little more before we can make an offer: a clear photo of the number plate; a wider photo that shows each damaged panel in full.

## 2. Hyundai Creta, heavy front crash - with synthetic demo plate image first

- Files: `00_plate_DL3CAB1234.jpg`, `WhatsApp Image 2026-10-21 at 12.15.25 AM.jpeg`
- Policy: POL-DEMO-003 (Hyundai Creta, plate UP16BT4521)
- **Decision: human**
- Reasons: plate_mismatch
- Missing information fields: plate_verified, parts_identified
- Plate read by Qwen: DL3CAB1234
- Integrity flags: none
- Pipeline flags: no_camera_metadata:00_plate_DL3CAB1234.jpg, no_camera_metadata:WhatsApp Image 2026-10-21 at 12.15.25 AM.jpeg

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Front-bumper | Dent | moderate | 0.3788 | 0.358 | dent_det:front-bumper-dent |
| Front-door | Dent | moderate | 0.4908 | 0.359 | dent_det:doorouter-dent |
| Hood | Dent | severe | 0.7569 | 0.852 | dent_det:bonnet-dent |

Message shown to the customer (fixed template):

> A claims specialist will review this claim and contact you. You do not need to do anything else for now.

## 3. Tata Nexon (teal), two-photo collage, front crash

- Files: `WhatsApp Image 2026-10-21 at 12.18.55 AM (1).jpeg`
- Policy: POL-DEMO-002 (Tata Nexon, plate HR26DK8337)
- **Decision: ask for more**
- Reasons: plate_verified
- Missing information fields: plate_verified
- Plate read by Qwen: not read
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.18.55 AM (1).jpeg

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| License-plate | Missing part | severe | 0.6574 | 0.661 | damage_merged_s |
| Rocker-panel | Dent | severe | 0.6069 | 0.699 | dent_det:Runningboard-Damage |

Message shown to the customer (fixed template):

> We need a little more before we can make an offer: a clear photo of the number plate.

## 4. Tata Nexon (black), heavy front crash

- Files: `WhatsApp Image 2026-10-21 at 12.18.55 AM.jpeg`
- Policy: POL-DEMO-002 (Tata Nexon, plate HR26DK8337)
- **Decision: surveyor**
- Reasons: structural_or_safety_damage
- Missing information fields: plate_verified, parts_identified, damage_identified
- Plate read by Qwen: not read
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.18.55 AM.jpeg, structural_suspected, need_wider_photo:Roof

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Fender | Dent | severe | 0.6004 | 0.424 | dent_det:fender-dent |
| Front-bumper | Dent | moderate | 0.4944 | 0.663 | dent_det:front-bumper-dent |
| Hood | Dent | severe | 0.6968 | 0.568 | dent_det:bonnet-dent |
| Windshield | Broken part | severe | 0.6941 | 0.823 | dent_det:Front-windscreen-damage |
| Roof | - | - | - | 0.0 | close-up only |

Message shown to the customer (fixed template):

> This claim needs a licensed surveyor to inspect the car. We have booked the request and a surveyor will contact you.

## 5. Black SUV (model not identified), heavy front-left crash

- Files: `WhatsApp Image 2026-10-21 at 12.18.56 AM (1).jpeg`
- Policy: POL-DEMO-001 (Maruti Swift, plate DL3CAB1234)
- **Decision: human**
- Reasons: plate_mismatch
- Missing information fields: plate_verified, parts_identified, damage_identified
- Plate read by Qwen: DL11AV1234
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.18.56 AM (1).jpeg, need_wider_photo:Fender, need_wider_photo:Hood, need_wider_photo:Quarter-panel, need_wider_photo:Windshield

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Front-door | Dent | moderate | 0.5596 | 0.585 | dent_det:doorouter-dent |
| Fender | - | - | - | 0.0 | close-up only |
| Hood | - | - | - | 0.0 | close-up only |
| Quarter-panel | - | - | - | 0.0 | close-up only |
| Windshield | - | - | - | 0.0 | close-up only |

Message shown to the customer (fixed template):

> A claims specialist will review this claim and contact you. You do not need to do anything else for now.

## 6. Maruti Dzire (white), heavy front crash

- Files: `WhatsApp Image 2026-10-21 at 12.18.56 AM (2).jpeg`
- Policy: POL-DEMO-001 (Maruti Swift, plate DL3CAB1234)
- **Decision: ask for more**
- Reasons: plate_verified, parts_identified, damage_identified
- Missing information fields: plate_verified, parts_identified, damage_identified
- Plate read by Qwen: not read
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.18.56 AM (2).jpeg, need_wider_photo:Hood

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Hood | - | - | - | 0.0 | close-up only |

Message shown to the customer (fixed template):

> We need a little more before we can make an offer: a clear photo of the number plate; a wider photo that shows each damaged panel in full; a closer, well-lit photo of each damaged area.

## 7. Maruti Swift (white), side crushed, Shutterstock watermark

- Files: `WhatsApp Image 2026-10-21 at 12.18.56 AM.jpeg`
- Policy: POL-DEMO-001 (Maruti Swift, plate DL3CAB1234)
- **Decision: ask for more**
- Reasons: plate_verified, parts_identified, damage_identified
- Missing information fields: plate_verified, parts_identified, damage_identified
- Plate read by Qwen: not read
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.18.56 AM.jpeg, need_wider_photo:Back-windshield, need_wider_photo:Roof

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Fender | Dent | severe | 0.6067 | 0.367 | dent_det:fender-dent |
| Front-door | Dent | moderate | 0.4521 | 0.678 | dent_det:doorouter-dent |
| Back-windshield | - | - | - | 0.0 | close-up only |
| Roof | - | - | - | 0.0 | close-up only |

Message shown to the customer (fixed template):

> We need a little more before we can make an offer: a clear photo of the number plate; a wider photo that shows each damaged panel in full; a closer, well-lit photo of each damaged area.

## 8. Maruti Swift (grey), no visible damage

- Files: `WhatsApp Image 2026-10-21 at 12.21.52 AM (1).jpeg`
- Policy: POL-DEMO-001 (Maruti Swift, plate DL3CAB1234)
- **Decision: human**
- Reasons: plate_mismatch
- Missing information fields: plate_verified
- Plate read by Qwen: UP78HD2313
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.21.52 AM (1).jpeg

| Part | Damage | Severity | Area fraction | Damage conf | Source |
|---|---|---|---|---|---|
| Fender | Dent | moderate | 0.5737 | 0.395 | dent_det:fender-dent |
| Hood | Dent | severe | 0.7095 | 0.339 | dent_det:bonnet-dent |

Message shown to the customer (fixed template):

> A claims specialist will review this claim and contact you. You do not need to do anything else for now.

## 9. Tata Nexon.ev studio image, no damage

- Files: `WhatsApp Image 2026-10-21 at 12.21.52 AM.jpeg`
- Policy: POL-DEMO-002 (Tata Nexon, plate HR26DK8337)
- **Decision: ask for more**
- Reasons: plate_verified, parts_identified, damage_identified
- Missing information fields: plate_verified, parts_identified, damage_identified
- Plate read by Qwen: not read
- Integrity flags: none
- Pipeline flags: no_camera_metadata:WhatsApp Image 2026-10-21 at 12.21.52 AM.jpeg, no_damage_found

No damage detected.

Message shown to the customer (fixed template):

> We need a little more before we can make an offer: a clear photo of the number plate; a wider photo that shows each damaged panel in full; a closer, well-lit photo of each damaged area.
