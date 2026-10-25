# License note — algorithmic-art (Floe adaptation)

- Upstream skill: https://github.com/anthropics/skills `skills/algorithmic-art`
  at pinned commit `dbd4588f9e1033efb41dad4bef2f7947c8993d44`.
- Upstream per-skill license: Apache License 2.0
  (`skills/algorithmic-art/LICENSE.txt` at the pinned commit); the full text is
  preserved byte-identical in `UPSTREAM-LICENSE.txt` (verified with `cmp`).
- The adapted SKILL.md workflow text (philosophy → conceptual seed →
  implementation → fixed-vs-variable viewer contract, seed navigation and
  action buttons) derives from that Apache-2.0 material and keeps its license
  and notice. `assets/shell-template.html` reproduces the *structure and
  section layout* of upstream `templates/viewer.html` (Seed / Parameters /
  Colors / Actions, sidebar+canvas chrome) as an Apache-2.0 derivative; its
  Anthropic branding, Poppins/Lora Google-Fonts bindings and the p5.js
  CDN `<script src>` were replaced (see below). Upstream template files are
  not vendored.
- p5.js is NOT bundled or referenced at runtime. Redistribution of p5.js
  (LGPL-2.1) was considered and rejected: the Floe core is first-party,
  offline, seed-deterministic and LGPL-free. No CDN, no npm, no download
  instruction remains.
- Floe first-party files — `assets/floegart.js`, `assets/viewer-ui.js`,
  `scripts/generate_art.py`, `scripts/prng_parity.js`,
  `references/numeric-contract.md`, `references/PROVENANCE.md`, `floe.json` —
  are Floe-authored under the Mozilla Public License 2.0 (the hub tooling
  license; full text at the floe-skill-hub repository root LICENSE).
- The generated artifacts (`*.html`, `*.svg`, `*.primitives.json`,
  `*.params.json`) are user works; nothing in this skill claims rights in them.
- Copyright: upstream skill text and template structure — the
  anthropics/skills project authors (Apache-2.0); first-party additions — the
  Floe Skill Hub authors. No relabeling in either direction.
