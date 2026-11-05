# Synthetic cash-flow intake

Currency AUD. Opening available cash is 5,000 at the start of day 0;
subsequent rows are future calendar-day offsets from that cutoff. No foreign
currency, fees or unlisted movements. Dates/amounts are supplied assumptions.

| ID | Day | Inflow | Outflow | Description |
| --- | ---: | ---: | ---: | --- |
| PAY-1 | 5 | 0 | 6,000 | Payroll |
| AR-A | 10 | 8,000 | 0 | Open customer invoice, remaining balance 8,000 |
| RENT | 15 | 0 | 2,000 | Rent |
| AP-B | 35 | 0 | 7,000 | Supplier payment |
| AR-C | 45 | 5,000 | 0 | Open customer invoice |
| COST | 65 | 0 | 6,000 | Known fixed payment |
| AR-D | 75 | 9,000 | 0 | Open customer invoice |

An already paid invoice with remaining balance 0 is not another future
inflow. Downside assumption: AR-A arrives on day 40 instead of day 10;
everything else stays the same. Show periods 1–30, 31–60 and 61–90, and
cash gaps within the periods. Do not claim a statistical confidence band.
