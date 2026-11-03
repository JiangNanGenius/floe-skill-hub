# Change-order control checklist

Use this before a change order is routed or recorded as approved. Tick each item and record the evidence or `UNKNOWN`.

## Identity and basis

- [ ] CO number is unique and stable.
- [ ] Title and description state what changed and why, without blame.
- [ ] Change type is one of the six allowed values.
- [ ] RFI, specification, drawing and location references are recorded where applicable.
- [ ] Original contract value, currency and tax basis are stated.
- [ ] Overhead and profit rates and their bases are stated and approved.

## Cost

- [ ] Every cost item has a description, quantity > 0, unit and unit cost >= 0.
- [ ] Every item has a category and a source note.
- [ ] Item totals recompute from quantity × unit cost × (1 + item markup).
- [ ] Direct cost equals the sum of item totals.
- [ ] Overhead is applied to direct; profit is applied to (direct + overhead).
- [ ] No markup is applied twice (item markup plus overhead/profit on the same amount).
- [ ] Credits keep a negative sign and are labelled.
- [ ] Tax, if any, is a separate line after the total.
- [ ] Presented rounding is stated; the total recomputes from the displayed amounts.

## Schedule

- [ ] Schedule impact is an integer (0 is valid; `UNKNOWN` is not zero).
- [ ] Affected activities are listed when the impact is non-zero.
- [ ] The schedule impact is linked to the approved baseline/update, not asserted in isolation.

## Routing and audit

- [ ] The status transition is legal (`draft → pending_review → pending_approval → approved/rejected`).
- [ ] Reviewer name, role, action, date and comments are recorded.
- [ ] Approver name, role, action, date and comments are recorded.
- [ ] Rejection has a reason; a rejected record is not edited back to draft.
- [ ] Prior approval records are preserved; no history is overwritten.
- [ ] The guide did not approve, sign or submit on the user's behalf.

## Summary

- [ ] Current contract = original + approved changes.
- [ ] Potential contract = current contract + pending changes.
- [ ] Change percent uses the original contract as denominator and states rounding.
- [ ] Total schedule impact uses approved changes only.
- [ ] The register and cost detail reconcile to the summary.
- [ ] A qualified commercial/contracts professional reviews the change before issue.
