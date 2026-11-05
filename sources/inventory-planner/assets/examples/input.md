# Synthetic inventory intake

Currency AUD; cutoff day 0; reliable complete 28-day history, no returns or
stockout distortion. Target cover 60 days; safety buffer 7 baseline days.

| SKU | 7-day sales | 28-day sales | Available | Lead days | Inbound | Pack | MOQ | Unit cost |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| FILTER-A | 42 | 112 | 40 | 7 | 20 confirmed on day 3 | 12 | 24 | 8 |
| SLOW-B | 0 | 0 | 30 | 7 | 0 | 6 | 12 | 12 |
| PART-C | 14 | 56 | 14 | UNKNOWN | 0 | 1 | 1 | 4 |

Produce the buy list and source-visible arithmetic. Drafts only.
