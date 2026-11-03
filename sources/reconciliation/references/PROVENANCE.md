# Provenance — reconciliation

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `finance/skills/reconciliation`
- License: see `references/licenses/LICENSE-NOTE.md`; the full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone or vendoring.
- Variant: adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; the slash-command argument hint was removed; input is now a workspace file or pasted tables plus the organization policy. The reconciliation types, item categories, aging model and escalation discipline are retained. Floe adds an arithmetic proof, an input contract, a review summary and an explicit human sign-off boundary.

## File mapping and hashes

- `SKILL.md` ← upstream `finance/skills/reconciliation/SKILL.md` (upstream sha256 `aa17e90539f4d4d84130c910c7f527236bfaa71977c4c03493c8e8e515ddeea6`)
- No other upstream files were present in the pinned skill directory; the upstream skill has one file.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package, not upstream files.
- `floe.json` is the Floe package manifest, authored for this package.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `finance/LICENSE` (exact bytes; hash in the license note and package list below).

## Package file hashes

- `SKILL.md` sha256 `cebbdbab0953c4c07084e9e88ae9ee331639b2647a67ff5a37986ed8c21c0542`
- `assets/examples/expected-output.md` sha256 `64069b4d2c899372e797cb6bd76721bde85ce92f3e0a79f4f77fa879e0d84fbf`
- `assets/examples/figures.json` sha256 `ee15da7369c3a151b5937f167af03d06e315d8f6040ab260ebfd7a92335fe4a9`
- `assets/examples/input.md` sha256 `89d7f88c4c22348c49d5cff003c82c1cfba7c617e80726f7938565e8a0d3cccc`
- `floe.json` sha256 `5a6b3a09451e94251ae496c3fd662dfe1f2294a93a7aa6f0935557b609314801`
- `references/licenses/LICENSE-NOTE.md` sha256 `61fc1b7aa685b0646b40dfd0a7ebfda925eef7ad0dcf812a2a09c8216dd0305e`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- Upstream license/NOTICE: the exact applicable upstream license bytes are preserved; no upstream NOTICE file was present at the pin. See the license note for the evidence path and any root-file caveat.
- The synthetic fixtures are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
