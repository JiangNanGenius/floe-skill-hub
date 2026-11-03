# Provenance — financial-statements

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `finance/skills/financial-statements`
- License: see `references/licenses/LICENSE-NOTE.md`; the full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone or vendoring.
- Variant: adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; the `/financial-statements` command and the `CONNECTORS.md` reference were removed; ERP and data-warehouse data sources were replaced with supplied workspace data, and the `/flux` offer was removed. The statement layouts, variance method, GAAP presentation notes and adjustment checklist are retained. Floe adds the three-statement proof checks, framework/jurisdiction assumptions and an explicit draft-only boundary.

## File mapping and hashes

- `SKILL.md` ← upstream `finance/skills/financial-statements/SKILL.md` (upstream sha256 `1a9ba1cc85495eef32fa250b8a4c05e4854430af574a290b855f919dbb557dfc`)
- No other upstream files were present in the pinned skill directory; the upstream skill has one file.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package, not upstream files.
- `floe.json` is the Floe package manifest, authored for this package.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `finance/LICENSE` (exact bytes; hash in the license note and package list below).

## Package file hashes

- `SKILL.md` sha256 `1c340fd6d789768be660801bef01ac0ee3593d2e35b7c726832bddd1c67fb0f1`
- `assets/examples/expected-output.md` sha256 `45bf83462b30404deb0bce316d8af339bfc3cb21889a80e8f84b88cc8fa24614`
- `assets/examples/figures.json` sha256 `f7dfe210fdf24694e44bd0312a75bd0923c66559caaa0d5a90fb0228c8242f02`
- `assets/examples/input.md` sha256 `3372b9bf920c3a71a71d822b861e59e9c6e73281b87bc375d20ac298ab43b277`
- `floe.json` sha256 `4ba5cd6f8e5ec2a2ddd7ff405652d78878d3bdc22e259761e0de48f9bfd7cd3c`
- `references/licenses/LICENSE-NOTE.md` sha256 `3ecdf10db81aaa1f8eaaf079a8735550fd86749efce4ce0ba8c36bff934c1095`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- Upstream license/NOTICE: the exact applicable upstream license bytes are preserved; no upstream NOTICE file was present at the pin. See the license note for the evidence path and any root-file caveat.
- The synthetic fixtures are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
