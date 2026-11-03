# Provenance — travel-points-calculator

- Upstream title: Borski Travel Hacking Toolkit trip-calculator
- Upstream repository: https://github.com/borski/travel-hacking-toolkit
- Pinned commit: `b46172deee14b106fc815c1d57f2587a581f8a27`
- Upstream skill path: `plugins/travel-hacking-toolkit/skills/trip-calculator`
- Retrieved: 2026-10-31
- Upstream license: MIT (root LICENSE; the skill file itself carries no separate license declaration)

## Adaptation

The CPP formula, opportunity-cost rule, transfer-ratio treatment, hotel comparison, portal comparison, decision framework, common pitfalls and Markdown output are preserved. Floe adaptation removes the live Duffel/Seats.aero/API workflow and replaces it with user-provided or already-visible quotes, an explicit data worksheet, and a rule that no fare, availability, transfer bonus or valuation may be invented.

## File mapping

| Local file | Relationship to upstream |
|---|---|
| `SKILL.md` | Adapted |
| `LICENSE` | Verbatim |

The exact upstream and local SHA-256 values and sizes are recorded in `references/SNAPSHOT-MANIFEST.json`. The upstream license bytes are retained under `references/licenses/`; the upstream repository has no separate NOTICE file.

## Not shipped

The upstream `data/points-valuations.json` and `data/transfer-partners.json` files are deliberately not shipped because they are time-sensitive reference data. The guide asks the user for current valuations and transfer ratios instead. No booking, account or API integration is included.

## Synthetic examples

`assets/examples/example-input.md` and `assets/examples/expected-output.md` are Floe-authored synthetic fixtures. They contain no real student, customer, employee, patient or financial data, and they are not upstream content.

## Auditor review (2026-10-31)

- `SKILL.md`: labelled the worked table as one-way, stated the example's 1.7 cpp floor explicitly, renamed the "Cash equiv" column to "Opportunity cost @1.7 cpp", and added the missing `× 100` to the round-trip CPP formula.
- `assets/examples/expected-output.md`: aligned the table field with the opportunity-cost wording and added a floor-reconciliation acceptance check.
- `references/PROVENANCE.md`: corrected the upstream license claim; the MIT root LICENSE is the source, and the skill file does not carry a separate license declaration.
- `references/licenses/LICENSE-NOTE.md`: named the actual MIT copyright holder, Michael Borohovski.
- No fare, award availability, transfer bonus or market valuation was invented.

## Boundary

This package is a guide. It does not claim execution verification, App qualification, review, packaging or publication. It does not include private paths, credentials, operational addresses or raw private evidence.
