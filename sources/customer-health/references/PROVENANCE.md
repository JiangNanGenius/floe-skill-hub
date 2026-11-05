# Provenance — customer-health

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `sales/skills/customer-health`
- Upstream file: `sales/skills/customer-health/SKILL.md` (sha256 `dcfcae0bce25de315e575a783c66fc7509d479cab4045d5f9ce53831ed2363d1`, 10,152 bytes)
- Last upstream content commit for this exact path: `2d97716bce` on 2026-10-21 (`feat(sales): show the source of every line with a link to check it (2.1.0) (#1351)`). Two commits were observed; the 2026-10-21 change is genuine (small) content maintenance — the shared "Links to check the work" rule — not a bulk migration or a description-only edit.
- License: Apache-2.0; exact applicable bytes from `sales/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. No `NOTICE` file exists at this path, at `sales/NOTICE`, or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-03 plus GitHub metadata/path-history APIs. No full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream two-job model — the ongoing health check and the QBR prep — and the five-dimension scoring model are retained. The live CRM, email, calendar, docs and transcript pulls and the health/status field updates and meeting booking are removed. Floe adds an input contract, a visibility table that marks dimensions not visible instead of guessing them, trend arithmetic shown on supplied tallies, evidence classes, a suggested-update checklist a human applies, privacy minimization and a claim boundary. Input is a workspace file or pasted account material; the output is a workspace assessment and agenda.

## File mapping

- `SKILL.md` ← upstream `sales/skills/customer-health/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `sales/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README, connector documentation and marketplace metadata are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `7a9045c217aeab2816f90429bd1ae3b4355fe770657cec6cc5dfafb481168514`
- `assets/examples/expected-output.md` sha256 `e4c586bf86fbfa879a0904405fd0ce2445ade65c263c65151f2b9294a9d8068e`
- `assets/examples/figures.json` sha256 `ff6b9c9a0a4f2b3a6f604702b3e57a72cb9a922ae27022aa6bbf89de826ee330`
- `assets/examples/input.md` sha256 `47f3fc586769fedf410117af12cd2d1fec5626a5fc642e07cd8b20e71c5d3795`
- `floe.json` sha256 `ffa2945a0dcd2840d3a7d46470cb6761f8a6b6868d979c72188731da9254f2b4`
- `references/licenses/LICENSE-NOTE.md` sha256 `3edfea375c44e92aaa0980ff13d8a88167f4d893fbc6b592a3a6109fa0a51c91`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented accounts, contacts and figures. No real account or personal data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
