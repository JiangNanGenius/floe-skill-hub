# Provenance — cash-flow-snapshot

- Repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d` (existing Hub pin authority).
- Source path: `small-business/skills/cash-flow-snapshot`.
- SKILL.md: Git blob `0377d29a2b47490b0c6f0c06b4f93775237f0ebe`, sha256 `1e5584378c5817981899bfa81296d8a9c2a7e4381a2f1deed616194e51944fff`, 12709 bytes.
- Exact SKILL.md bytes also matched the observed default-branch head `d900840716eb262e1feb17c6f4406c9ce0e06bcf` on 2026-11-05.
- Last path commit at the pin: `84d8efdb6e80e2b26898e5c3109d13eddde97761` on 2026-09-15T15:58:57Z (Claude for Small Business launch (#1144)). Repository activity is not a claim of a newer per-skill content change.
- Current repository metadata observed 2026-11-05: 34,788 stars, not archived, pushed 2026-11-04. These are curation context, never permission or execution evidence.
- License evidence: root LICENSE, exact bytes retained under references/licenses/; no applicable NOTICE.

## Adaptation

Retains opening-balance evidence and a 30/60/90-day transaction model. Removes financial connectors, automatic schedules and mandatory external XLSX/artifact skills. Replaces the percentage-on-net confidence-band heuristic with explicit dated scenarios; distinguishes disjoint net changes, cumulative cash and within-period shortfalls. Adds zero-lag and missing-opening-balance boundaries.

The adapted SKILL.md derives its workflow from upstream SKILL.md. Upstream reference/shared-plugin files are not bundled or linked at runtime. Floe authors the package manifest and synthetic input/expected-output/figures examples. There are no scripts, binaries, dependencies, connectors, automatic sends or execution claims. Routine workspace actions retain the App's existing task authorization.

## Package file hashes

- `SKILL.md` sha256 `02a9cf78735a10f3eb8cbc78807c30b61cce0f2d06669438675e690f4af017ff`
- `assets/examples/expected-output.md` sha256 `aaf2a60b6ec6fb742e856db6adc524ff4ba2951d14e741eda40a9e6bd98b3d87`
- `assets/examples/figures.json` sha256 `4bb853d17d65326ee494a184e9506dd678e0ad74a4556c2239a106c721c69da6`
- `assets/examples/input.md` sha256 `29450fc1c2fdca56fdc5d9368b138417f890dfbe26daa93eee23cfe6f3bc40ae`
- `floe.json` sha256 `0c99eb733d8a487dc9fe7ba2f5e92e2b2d501b73254169cca2422925e1be0eeb`
- `references/licenses/LICENSE-NOTE.md` sha256 `9c76457d0e382e842d1f930a8dc34d3b4cee8161b515da29863d528b33f5ae21`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`

PROVENANCE.md intentionally omits its own hash.
