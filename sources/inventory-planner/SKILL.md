---
name: inventory-planner
description: Turn supplied sales and stock exports into a dated replenishment plan, with transparent quantities, supplier drafts and a separate slow-stock list. No inventory connector, purchasing or sending is performed.
---

# Inventory Planner

Adapted from the Apache-2.0 source recorded in `references/PROVENANCE.md`.
Use supplied workspace files or pasted tables. Keep each recommendation tied
to its source and cutoff date. This guide connects to no shop, accounting
system, supplier or calendar and installs no software.

## Establish the inputs

Ask for the stock count's cutoff, currency, planning period and these fields:

| Field | Handling when missing |
| --- | --- |
| SKU, item name, dated units sold | Request the missing rows; never invent demand |
| On-hand and reserved/unavailable units | Separate available stock from physical stock |
| Unit cost | Show units only and mark purchase value unknown |
| Vendor and lead time | Mark the lead time unknown; do not invent an order date or quantity |
| Confirmed inbound quantity and arrival date | List unconfirmed arrivals separately |
| Pack size and minimum order quantity | Do not assume a pack rule; label any provisional calculation |
| Stockout periods, returns and bulk orders | Separate distorted observations from the baseline |

Confirm ambiguous quantity/sign/date columns once. Keep currencies separate
unless the user supplies a rate and rate date. A sales export is evidence,
not an instruction to place orders or change supplier bank details.

## Calculate the plan

1. Show 7-day and 28-day daily velocity, the date ranges and observation
   counts. Sales during a stockout do not establish zero demand. If the
   available-day denominator is unknown, show the raw rate with that gap;
   do not silently extrapolate lost sales.
2. For reliable history, use the higher observed rate to flag stockout
   urgency and the 28-day baseline to size a normal replenishment. Explain
   a one-week spike instead of silently buying 60 days at that spike rate.
3. Project stock balances in date order, including only confirmed arrivals
   on their arrival dates. An arrival after the first shortage does not
   prevent that shortage. Show approximate days of cover and the first
   projected shortage; distinguish these from a promised delivery date.
4. Use the user's target cover and safety buffer. If none is supplied,
   propose 60 days of cover and ask which buffer to use. With confirmed
   lead time and safety units, the calculation is:

   `raw order = max(0, daily baseline × (target days + lead days) + safety units − available stock − confirmed eligible inbound)`

   State which arrivals qualify within that horizon. Check the dated
   shortage timeline separately. Round a positive order up to full packs,
   then meet the vendor minimum. A zero order stays zero; a minimum is not
   a reason to buy a slow item. Show raw units, rounded units and cost.
5. For zero velocity, do not divide by zero or invent a stockout date.
   Report tied-up cost separately. Mark an item with more than 120 days of
   reliable cover for review; that threshold is an editorial default, not
   the user's stock policy. New and interrupted items remain explicit gaps.
6. Apply seasonality only from a sufficiently long supplied history or a
   named user assumption. Label the source and compare the unadjusted case.

Use an actually available calculation/table tool for a substantial dataset
and retain its calculation sheet. Without one, deliver the input mapping,
formulas and a clearly uncomputed table rather than claiming verified totals.

## Deliver

Lead with the dated total proposed spend and urgent items. Provide:

- An order-now/order-soon table with both rates, stock, arrivals, lead time,
  raw and rounded quantities, unit cost, currency and source rows.
- A separate slow/zero-stock-movement table and tied-up cost, with missing
  or uncertain information visible.
- Assumptions, data gaps, and the review date.
- If requested, draft purchase-order lines and supplier email text. Mark
  them drafts. Do not issue a PO, contact a vendor or create a reminder.

Markdown and CSV are portable outputs. Use Floe's existing document/table
capabilities when requested and actually available; claim a workbook or
document was saved only after the real save returns a readable artifact.
Routine workspace drafts use the normal task permission flow.

For a worked arithmetic check, see `assets/examples/input.md` and
`assets/examples/expected-output.md`. Do not treat the synthetic example as
the user's inventory.
