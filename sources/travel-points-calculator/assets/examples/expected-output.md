# Expected output shape and acceptance notes

The response should:

1. Normalize the itinerary: 110,000 Aeroplan miles + USD 184 taxes versus USD 3,150 cash.
2. Compute CPP: (3150 - 184) / 110000 * 100 = 2.70 cpp.
3. Compare with the user's floor (1.5) and ceiling (2.2): above ceiling, so "Excellent" at the stated valuation.
4. Compare the portal option separately: 2,950 / 210,000 * 100 = 1.40 cpp, below floor, so cash or the Aeroplan award is better than the portal.
5. Recommend the award only if the user confirms availability and the award can be held or is otherwise low-risk before transferring. Do not tell the user to transfer speculatively.
6. Show a Markdown table with option, program, miles/points, taxes, opportunity cost at the stated floor, CPP and rating.
7. State that no live fare or award search was performed and that availability/taxes must be verified.

Acceptance checks:

- The arithmetic is correct and reproducible.
- The table states the assumed point floor; its opportunity-cost column reconciles with that floor.
- The one-way award and round-trip cash are normalized to the same itinerary.
- No invented transfer bonus, fare or availability is used.
- The recommendation separates value from booking risk.
