# License note — canvas-design (Floe adaptation)

- Upstream skill: https://github.com/anthropics/skills `skills/canvas-design`
  at pinned commit `dbd4588f9e1033efb41dad4bef2f7947c8993d44`.
- Upstream per-skill license: Apache License 2.0 (`skills/canvas-design/LICENSE.txt`
  at the pinned commit). `UPSTREAM-LICENSE.txt` carries the full text
  byte-identical from that commit (verified with `cmp` against the pinned
  checkout).
- The adapted SKILL.md workflow text derives from that Apache-2.0 material and
  keeps this license and notice; it is NOT re-licensed.
- Floe first-party files in this package — `scripts/make_poster.py`,
  `scripts/png_to_pdf.py`, `assets/fonts/fonts.json`, `assets/examples/*.json`,
  `references/FONTS-LICENSE.md`, `references/poster-spec-format.md`,
  `references/PROVENANCE.md`, `floe.json` — are Floe-authored under the
  Mozilla Public License 2.0 (the license of the hub tooling; text at the
  floe-skill-hub repository root LICENSE).
- Bundled font binaries and their OFL texts are third-party SIL Open Font
  License 1.1 material, redistributed under their own licenses
  (per-family `<Family>-OFL.txt` beside each face in `assets/fonts/`).
- No upstream code, scripts, templates or binaries were vendored beyond the
  audited font subset documented in `references/FONTS-LICENSE.md`; the upstream
  tree contains no scripts/templates besides the font catalog.
- Copyright holders: upstream skill text — the anthropics/skills project
  authors (Apache-2.0); fonts — the respective OFL project authors named in
  each OFL file; first-party additions — the Floe Skill Hub authors. No third
  party's work is presented as Floe's, and no Floe authorship is invented for
  upstream content.
