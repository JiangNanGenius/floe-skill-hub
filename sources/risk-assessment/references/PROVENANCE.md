# Provenance — risk-assessment

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `operations/skills/risk-assessment`
- Upstream file: `operations/skills/risk-assessment/SKILL.md` (sha256 `82e29810a762c396a56f92bbd5c5afd252f7a07c6be69a246c28f7b82c4086d9`, 1,630 bytes)
- Last upstream content commit for this exact path: `4fa3cb92e2` on 2026-02-24 (`Big round of pushes`). One commit was observed for this path. The content is stable, not recent.
- License: Apache-2.0; there is no directory-level `operations/LICENSE` at the pin (verified by the prior support-operations lane), so the exact bytes of the repository root `LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. The root file contains the Apache-2.0 text plus an unrelated trailing fragment; only the Apache-2.0 text is relied on. No `NOTICE` file exists at this path, at `operations/NOTICE`, or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-03 plus GitHub metadata/path-history APIs. No full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream 3x3 assessment matrix, the six risk categories, the register fields and the prioritized output are retained. Floe expands the short upstream guide with an input contract, evidence classes, unknown-handling rules (unknowns stay unknown and join a fact-finding queue), a control-evidence view that classifies controls as tested-effective / tested-exception / untested, a residual-risk view bounded by tested controls, acceptance-threshold handling, mitigation ownership and a claim boundary. Input is pasted facts and control evidence; the output is a workspace register and mitigation plan.

## File mapping

- `SKILL.md` ← upstream `operations/skills/risk-assessment/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream root `LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `6582ef316b09e84f08a95ff8485624a6ad350a4acf855df1c1618c1c6cf857bf`
- `assets/examples/expected-output.md` sha256 `e4d1012d70c059d1b954172e015de98f7c711082442fef54ee2b3c4dd3fc03cf`
- `assets/examples/figures.json` sha256 `ba454fb805edf2bcba794687ccc6e51481f56bf4efd7d4d4eb27897fd0f2e7cc`
- `assets/examples/input.md` sha256 `c0fefd576103a4b8326378dd99de85fac92adbec3b383118ff79227bcb1a50cf`
- `floe.json` sha256 `0df6ef611fd855b0fceea15b6173a89479db4235e3841f4836c0eb122983eac2`
- `references/licenses/LICENSE-NOTE.md` sha256 `101bff8fb6e521e9de95533565b804e673cf84c38a9bdd9a6605d7d40179a3aa`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`

## Notes

- The synthetic fixtures use invented processes, risks and controls. No real organization data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
