# Upstream method — change-order-processor

- Repository: https://github.com/datadrivenconstruction/DDC_Skills_for_AI_Agents_in_Construction
- Pinned commit: `410ed1e71e4a5c6fd231afd0c8d1e586a9f546e8`
- Upstream path: `1_DDC_Toolkit/Cost-Management/change-order-processor/SKILL.md`
- Licence: MIT for the skill instructions (root `LICENSE`); the repository `NOTICE.md` separately excludes the book and the CC BY-NC CWICR compilation. No book or database content is included here.

## Business case preserved from upstream

Change orders cause disruption: delayed processing affects cash flow, cost impact is unclear, documentation is lost, and schedule impacts are not tracked. The upstream solution is a change-order processor with cost analysis, an approval workflow and impact tracking.

## Enumerations

**Status:** `draft`, `pending_review`, `pending_approval`, `approved`, `rejected`, `void`.

**Change type:** `owner_requested`, `design_change`, `field_condition`, `code_compliance`, `value_engineering`, `error_omission`.

**Impact type (upstream classification):** `cost_increase`, `cost_decrease`, `time_increase`, `time_decrease`, `no_impact`. The Floe guide records cost and schedule impacts as separate fields; the impact-type list is retained here for mapping.

## Data model

**Cost item:** `description`, `quantity`, `unit`, `unit_cost`, `total_cost`, `category` (labor/material/equipment/subcontractor), `markup_percent`.

**Approval record:** `approver_name`, `approver_role`, `action` (approved/rejected/returned), `action_date`, `comments`.

**Change order:** `co_number`, `title`, `description`, `change_type`, `status`, `created_date`, `created_by`; cost items; `direct_cost`, `overhead_cost`, `profit_cost`, `total_cost`; `schedule_impact_days`, `affected_activities`; approvals, `approved_date`, `approved_by`; `rfi_reference`, `spec_section`, `drawing_reference`, `location`.

## Formulas

```text
item_total = quantity × unit_cost × (1 + markup_percent)
direct_cost = Σ item_total
overhead_cost = direct_cost × overhead_rate
profit_cost = (direct_cost + overhead_cost) × profit_rate
total_cost = direct_cost + overhead_cost + profit_cost
```

Upstream defaults: overhead 10%, profit 10%. They are examples, not mandated rates.

## State machine preserved from upstream

- Create in `draft`.
- `submit_for_review`: only `draft → pending_review`.
- `submit_for_approval`: only `pending_review → pending_approval`; appends a reviewer record.
- `approve_change_order`: appends an approval record, sets `approved`, `approved_date`, `approved_by`.
- `reject_change_order`: appends a rejection record with reason, sets `rejected`.

The Floe guide adds explicit guards for illegal transitions and requires a named approver/role/date.

## Summary fields preserved from upstream

The single-order contract summary preserves `project` context, `original_contract`, `approved_changes`, `current_contract`, `pending_changes`, `potential_contract`, `total_schedule_impact_days` and `change_percent`. The upstream multi-order aggregates (`total_change_orders`, `by_status`, `by_type`) are not expanded in the single-order output; they remain derivable from the register's status and type columns.

```text
current_contract = original_contract + approved_changes
potential_contract = current_contract + pending_changes
change_percent = approved_changes ÷ original_contract × 100
```

## Log fields preserved from upstream

Change Orders sheet: CO number, title, change type, status, created date, direct/overhead/profit/total cost, schedule impact, approved date. Cost Details sheet: CO number, description, quantity, unit, unit cost, total, category. Summary sheet: original contract, approved changes, current contract, pending changes, change percent, schedule impact.

## What was not copied

The upstream Python implementation (`ChangeOrderProcessor`, `ChangeOrder`, `CostItem`, `ApprovalRecord`) is not shipped as executable code. Its data model, formulas, defaults, state machine, summary and log fields are preserved in the guide and this reference. No dependency (`pandas`, `openpyxl`) is required by the guide.

## File mapping

| Upstream file | Floe package file | Treatment |
| --- | --- | --- |
| `SKILL.md` | `SKILL.md` | Rewritten as a guide; business case, enums, formulas, state machine and summary preserved |
| `instructions.md` | `references/UPSTREAM-METHOD.md` | Input/output constraints folded into the method extraction |
| `LICENSE` | `references/licenses/UPSTREAM-LICENSE.txt` | Byte-identical |
| `NOTICE.md` | `references/licenses/UPSTREAM-NOTICE.md` | Byte-identical |
