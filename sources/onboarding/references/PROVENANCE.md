# Provenance — onboarding

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `human-resources/skills/onboarding`
- Upstream file: `human-resources/skills/onboarding/SKILL.md` (sha256 `c9210cdd00f8c2998a01c6d1310a8742aafa82a5861fb7c1c18686b72a56da97`, 3,195 bytes)
- Last upstream content commit for this exact path: `2d6f7e22dd` on 2026-03-13 (`Migrate commands to skills across all plugins`). One commit was observed for this path; the plugin directory had later README/manifest commits that did not touch this skill file. The content is stable, not recent.
- License: Apache-2.0; there is no directory-level `human-resources/LICENSE` at the pin (verified 404 by the prior lane), so the exact bytes of the repository root `LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. The root file contains the Apache-2.0 text plus an unrelated trailing fragment; only the Apache-2.0 text is relied on. No `NOTICE` file exists at this path, at `human-resources/NOTICE`, or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-03 plus GitHub metadata/path-history APIs. No full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream pre-start checklist, Day 1 and Week 1 schedules, key-contacts table, tools-access table, 30/60/90-day goal sections and the role-customization tips are retained. The slash-command invocation, the `$ARGUMENTS` placeholder, the `~~HRIS` / `~~knowledge base` / `~~calendar` connector paths and the CONNECTORS.md pointer are removed. Floe adds an input contract, least-privilege access rules with named human approvers and blocked rows when the approver is unknown, fact-versus-proposal discipline, privacy minimization, a human open-items list and a claim boundary. Input is pasted new-hire details; the output is a workspace onboarding plan.

## File mapping

- `SKILL.md` ← upstream `human-resources/skills/onboarding/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream root `LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `d360f20f300b568f77c0d73a5db5bfcede71dce1b57948f4d49626a47885b789`
- `assets/examples/expected-output.md` sha256 `9f3dbac9dd0edd5437b47cba1e0914607d21991d87a9eda178b6fb210fd3b13b`
- `assets/examples/figures.json` sha256 `8980c30cdcf655b0e7243a98e162437678fa6fe1cb6f7db92717ac2caaa375ae`
- `assets/examples/input.md` sha256 `0e7f4aca4c02b805a4851618c44b56a85a950b2cc8044ef3a879e247a92ba914`
- `floe.json` sha256 `a97ae0c25616cc41bb1066cd4c5ba3853589d4a87e2c7993dcf60a78e4ab234d`
- `references/licenses/LICENSE-NOTE.md` sha256 `3a1b7c819b26c30af23af2d4da21921fc2072e1f10da902cd5fb094d080edec0`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`

## Notes

- The synthetic fixtures use invented people and teams. No real personal data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
