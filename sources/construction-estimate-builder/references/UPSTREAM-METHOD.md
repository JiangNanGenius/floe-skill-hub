# Upstream method — estimate-builder

- Repository: https://github.com/datadrivenconstruction/DDC_Skills_for_AI_Agents_in_Construction
- Pinned commit: `410ed1e71e4a5c6fd231afd0c8d1e586a9f546e8`
- Upstream path: `2_DDC_Book/3.1-Cost-Estimation/estimate-builder/SKILL.md`
- Licence: MIT for the skill instructions (root `LICENSE`); the repository `NOTICE.md` separately excludes the book and the CC BY-NC CWICR compilation. No book or database content is included here.

## Business case preserved from upstream

Estimates have complex cost structures, multiple cost categories, markup calculations and format requirements. The upstream solution is a structured estimate builder with cost categorisation, markups and export.

## Data model

**Estimate line item:** `line_number`, `wbs_code`, `description`, `quantity`, `unit`, `unit_cost`, `category`, `notes`. The line total is `quantity × unit_cost`, rounded to two decimals.

**Cost categories:** `labor`, `material`, `equipment`, `subcontractor`, `other`.

**Markup:** `name`, `rate` (decimal), `base` (`direct` or `subtotal`).

**Standard markups (upstream defaults):** General Conditions/Overhead 15% on direct; Profit 10% on subtotal; Contingency 5% on subtotal. These are examples, not mandated rates.

## Formulas

```text
line_total = round(quantity × unit_cost, 2)
direct_cost = Σ line_total
overhead = direct_cost × overhead_rate
subtotal_1 = direct_cost + overhead
profit = subtotal_1 × profit_rate
subtotal_2 = subtotal_1 + profit
contingency = subtotal_2 × contingency_rate
grand_total = subtotal_2 + contingency
```

A markup with base `direct` uses the original direct cost. A markup with base `subtotal` uses the running subtotal after previous markups.

## Validation preserved from upstream

- Estimate has no line items.
- Quantity is less than or equal to zero.
- Unit cost is negative.
- Description is missing.
- No markups are defined.

The Floe guide adds checks for missing unit/WBS, invalid markup bases, category values, reconciliation, currency/tax drift and missing source notes.

## Outputs preserved from upstream

- Cost summary by category (labor, material, equipment, subcontractor, other, direct cost).
- Markup detail (name, rate, amount, running subtotal).
- Total markups and grand total.
- Line-item table with WBS codes (grouping is optional).
- Excel/CSV export fields: Line, WBS, Description, Qty, Unit, Unit Cost, Total, Category, Notes.

## What was not copied

The upstream Python implementation (`EstimateBuilder`, `EstimateLineItem`, `CostSummary`, `Markup`) is not shipped as executable code. Its data model, formulas, defaults, validation and output fields are preserved in the guide and this reference. No dependency (`pandas`, `openpyxl`) is required by the guide.

## File mapping

| Upstream file | Floe package file | Treatment |
| --- | --- | --- |
| `SKILL.md` | `SKILL.md` | Rewritten as a guide; business case, model, formulas and validation preserved |
| `instructions.md` | `references/UPSTREAM-METHOD.md` | Input/output constraints and defaults folded into the method extraction |
| `LICENSE` | `references/licenses/UPSTREAM-LICENSE.txt` | Byte-identical |
| `NOTICE.md` | `references/licenses/UPSTREAM-NOTICE.md` | Byte-identical |
