# Provenance — vendor-review

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `operations/skills/vendor-review`
- Upstream file: `operations/skills/vendor-review/SKILL.md` (sha256 `c2a959a7ed068e34a83984cf223754062e6819deb0ba1ca33eb747b4cc808d5e`, 3,170 bytes)
- Last upstream content commit for this exact path: `2d6f7e22dd25593f0f748010430ef86f19659735` on 2026-03-13. One commit was observed for this path. The plugin directory had later README and manifest commits, but this skill file did not change after that date.
- License: Apache-2.0; the `operations` plugin directory has no `LICENSE` file at this pin, so the exact bytes of the repository root `LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. The root file contains the Apache-2.0 text followed by an unrelated trailing fragment; only the Apache-2.0 text is relied on. No `NOTICE` file exists at this path or at the repository root. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream guide's cost analysis, risk assessment, performance metrics and comparison-matrix framework are retained. The slash-command invocation, `$ARGUMENTS`, `CONNECTORS.md` reference and optional knowledge-base/procurement lookups were removed. Because the upstream file is brief (3,170 bytes), this package is a substantial Floe-authored expansion rather than a light edit. Floe adds must-have gates, a deterministic three-year TCO method with cost coverage, a weighted scorecard with evidence anchors and score coverage, an evidence hierarchy, a conflict-of-interest procedure, a risk register, a renewal and exit-management section, a negotiation plan and a complete no-authority output contract.

The package is a decision-support guide. It does not approve, purchase, pay, sign, terminate, contact a vendor or change a procurement record.

## File mapping

- `SKILL.md` ← upstream `operations/skills/vendor-review/SKILL.md`, adapted and substantially expanded as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream repository root `LICENSE`, exact bytes, because no directory-level license exists.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `e55a9ea6b8ca0b748429869d34b788a22f475cd153719af49f4c15b5ea793bab`
- `assets/examples/expected-output.md` sha256 `c03543490b29b9cfbf913f3bc9640f85e5256ea2bf04f95f6c3bf0b33042717f`
- `assets/examples/figures.json` sha256 `7edf434745a99b997e07f325d4208decccf4d3011dd50bd2c520ef5e2e150d6e`
- `assets/examples/input.md` sha256 `df12505923025d081aa683934253cb566c10a0a29c0dbfd1f0690a1d2d05099a`
- `floe.json` sha256 `b0cb7a1f50a4cc182b7e85dd1d70417908a6256b8755baa418953c98d56eb59b`
- `references/licenses/LICENSE-NOTE.md` sha256 `ff2d5f65b38ae3b30a8ea8c73351a2dd23a857b03e9d1c0d2dccc977664a882c`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`

## Notes

- The synthetic fixtures use invented vendors, prices, terms and references. No real proposal, contract or vendor performance data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
