# Synthetic fixtures

These files are Floe-authored synthetic inputs for deterministic tests and the offline
self-check. They are not customer data, market research, survey results or evidence of
willingness to pay.

- `brief_valid.json` — a complete pricing brief for the model picker.
- `survey_valid.json` — 40 synthetic Van Westendorp responses with valid ordering. The
  intersections are regression values, not a recommendation.
- `features_valid.json` — nine synthetic features with an explicit `best: 0` anchor to
  exercise the "no published price" anti-pattern.

All files are UTF-8 JSON. None contains a real company, person, price, credential or URL.
