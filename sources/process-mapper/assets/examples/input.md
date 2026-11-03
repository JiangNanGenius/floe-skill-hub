# Synthetic process input — procurement intake

> Synthetic fixture based on the upstream sample shape. Values are invented for acceptance testing.

- Process name: Procurement Intake (Synthetic)
- Owner role: Operations Manager
- Frequency: Daily
- Trigger: A department submits a purchase request
- End state: Purchase order issued
- WIP: 12 requests in process at a typical time
- Profile: saas

| # | Stage | Owner | Type | P50 minutes | P90 minutes |
|---:|---|---|---|---:|---:|
| 1 | Submit request | Requestor | value-add | 15 | 30 |
| 2 | Wait for manager approval queue | Manager | wait | 480 | 1,440 |
| 3 | Manager approves | Manager | value-add | 10 | 25 |
| 4 | Wait for finance review | Finance | wait | 720 | 2,880 |
| 5 | Finance validates budget code | Finance | value-add | 20 | 60 |
| 6 | Rework — missing vendor W-9 | Requestor | rework | 120 | 360 |
