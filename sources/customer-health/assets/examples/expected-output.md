# Expected output — customer-health (synthetic)

Health check draft — no field updated, nothing sent to the customer. Built only from the supplied export, tallies and notes.

## 1. Assessment header

Account: Cascade Retail Group (synthetic) | Mode: health check | Period: Q3 2026 vs Q2 2026 | As-of 2026-10-30. Sources: book row + opportunity export, user-counted activity tallies, CSM notes. No CRM, email, calendar or docs source was read live.

## 2. Visibility table

| Dimension | Visible? | Basis |
| --- | --- | --- |
| Relationship | yes | CSM notes |
| Engagement trend | yes | user-counted tallies |
| Commercial | yes | export (renewal date, lost opp) |
| Support | **not visible** | no case data supplied |
| Value delivery | **not visible** | no success plan or QBR summary supplied |

## 3. Dimension table

| Dimension | Status | Evidence |
| --- | --- | --- |
| Relationship | yellow | champion in seat and engaged; no executive sponsor supplied |
| Engagement trend | **red** | meetings 8 → 5, emails 40 → 22 |
| Commercial | yellow | renewal 2026-12-28 within about 60 days; loyalty integration lost 2026-09-05 |
| Support | not visible | no data supplied — not guessed |
| Value delivery | not visible | no data supplied — not guessed |

## 4. Engagement trend (arithmetic shown)

- Meetings: Q3 5 vs Q2 8 → change (5 - 8) / 8 = **-37.5%**.
- Emails: Q3 22 vs Q2 40 → change (22 - 40) / 40 = **-45.0%**.
- Both periods' counts are the user's tallies; the guide did not verify them against a system of record.

## 5. Overall verdict

**Yellow trending red.** Driven by engagement trend (red) and commercial (renewal inside ~60 days after a competitive loss). Relationship yellow keeps the account out of red for now; support and value delivery are not visible and could move the verdict either way once supplied.

## 6. Watch items

1. Meeting volume down 37.5% quarter over quarter — engagement is falling ahead of a December renewal. Suggested action: propose an executive touchpoint before renewal paperwork.
2. Loyalty integration lost 2026-09-05 — second consecutive competitive loss. Suggested action: schedule a win-loss debrief.

## 7. Suggested update checklist (a human applies — nothing was written)

- [ ] Health/status field → "at risk - engagement declining into renewal" (proposed before/after; a person with write access applies it).

## 8. Claim boundary

This assessment used only supplied material; support and value delivery are named not visible rather than guessed; no health/status field was updated and no meeting was booked. The trend arithmetic reflects the user's tallies. Renewal and churn decisions belong to the named owner. Synthetic example — no real account or person.
