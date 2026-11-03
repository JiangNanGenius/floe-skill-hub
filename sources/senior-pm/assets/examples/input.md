# Synthetic project portfolio input

> Synthetic fixture. Projects, people and amounts are invented for acceptance testing.

## Review period

2026-10-31. Portfolio of two active projects. Currency: USD.

## Project A — Customer portal migration

- Priority: high
- Status: active
- Planned start: 2026-01-01; planned end: 2026-12-31; forecast end: 2027-01-31
- Planned budget: 1,000,000; forecast total cost: 1,120,000
- Planned features: 20; added: 2; descoped: 1; completed: 16
- Defects: 10 total, 8 resolved, 2 critical; test coverage: 80%
- Risk score: 20

## Project B — Billing reconciliation automation

- Priority: medium
- Status: active
- Planned start: 2026-04-01; planned end: 2026-12-15; forecast end: 2026-12-15
- Planned budget: 400,000; forecast total cost: 392,000
- Planned features: 12; added: 0; descoped: 0; completed: 11.4 (95%)
- Defects: 6 total, 6 resolved, 0 critical; test coverage: 97%
- Risk score: 8

## Risk register (excerpt)

| Risk | Category | Probability (1–5) | Impact (1–5) | Financial impact | Owner | Mitigation |
|---|---|---:|---:|---:|---|---|
| Portal integration slips again | Schedule | 4 | 4 | 120,000 | PM A | Freeze scope; add integration test environment |
| Vendor API changes without notice | External | 3 | 4 | 80,000 | PM A | Contract notice clause; adapter layer |
| Billing data reconciliation misses edge cases | Technical | 2 | 3 | 25,000 | PM B | Parallel run for one cycle |

## Capacity

- Team: 8 people, 40 hours/week gross each.
- Capacity factors: meetings 15%, learning 5%, admin 10%, context switching 5%, vacation/sick 12%.
- Demand from committed projects next quarter: 150 hours/week.
