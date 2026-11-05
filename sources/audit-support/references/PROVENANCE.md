# Provenance — audit-support

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `finance/skills/audit-support`
- Upstream file: `finance/skills/audit-support/SKILL.md` (sha256 `6e53c9529c42bb92c11d00a58af5119f7383903d9cb3b911625089fec2ff4784`, 16,801 bytes)
- Last upstream content commit for this exact path: `2d6f7e22dd` on 2026-03-13 (`Migrate commands to skills across all plugins`). Two commits were observed for this path, the earlier being the repository's initial import. The plugin directory had later README/manifest commits that did not touch this skill file. The content is stable, not recent.
- License: Apache-2.0; exact applicable bytes from `finance/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt` (verified by the prior finance-legal-hr lane; evidence preserved). No `NOTICE` file exists at this path, at `finance/NOTICE`, or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-03 plus GitHub metadata/path-history APIs. No full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream SOX 404 testing methodology, the sample-selection approaches and size-guidance table, the workpaper documentation standards, the deficiency classification and the common control types are retained. Floe adds an input contract, a sample-validity gate (a systematic sample needs a defined complete population and a supplied random start), an evidence-sufficiency gate that classifies supplied items without upgrading them, indicator-based deficiency classification with an explicit indeterminate/escalation path, aggregation analysis, remediation tracking, privacy minimization and a claim boundary that denies any compliance claim. Input is pasted control and population facts; the output is workspace workpaper drafts for human testers.

## File mapping

- `SKILL.md` ← upstream `finance/skills/audit-support/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `finance/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `9d17b714a4209473697bfdb02a99f0c678a548e1dfca6989fd6328e0ca5cc5a8`
- `assets/examples/expected-output.md` sha256 `a2b7f5b2e81ddaa8c1933b4ccd866d52b7fa0ee9262254f8acdebbff138ad07e`
- `assets/examples/figures.json` sha256 `2b021139caf2dcf77ebd84027586fe2df050cdf0b521bba62410041c66b95ca9`
- `assets/examples/input.md` sha256 `40f2275e4b0a32fcf1006d4863e5cf8b1034897e27a243f38657eac033a2b90f`
- `floe.json` sha256 `b89ed383a21eeb8913e22e13b6dc4eec0ee9d617dcb4b2f88ac0b9063bad1744`
- `references/licenses/LICENSE-NOTE.md` sha256 `9df646b42e0093f229cec100cec679da6b86524a0899328bc8ad72f34f515b1e`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented controls, populations and evidence. No real audit data is included and no real compliance is claimed.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
