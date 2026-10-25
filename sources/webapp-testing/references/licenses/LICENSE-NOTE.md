# Upstream license note — webapp-testing

- Repository: https://github.com/anthropics/skills
- Pinned commit: `dbd4588f9e1033efb41dad4bef2f7947c8993d44`
- Skill path: `skills/webapp-testing`; per-skill license file at the pin: `LICENSE.txt`
- License: Apache License 2.0, `Copyright 2026 Anthropic, PBC.` (appendix notice inside the
  license file). `UPSTREAM-LICENSE.txt` carries the full text byte-identical from that commit
  (SHA-256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362`).
- Per-asset audit (closes the registry's licenseNote caveat): the pinned subtree contains ONLY
  `.md`, `.py` and the license `.txt` — no fonts, images, binary templates or third-party
  embedded assets — so there is nothing beyond text/code to itemize. The retained text/code
  carries the single Apache-2.0 grant above.
- Upstream SKILL.md frontmatter declared `license: Complete terms in LICENSE.txt`; this package
  keeps that pointer by shipping the complete terms verbatim and referencing them from SKILL.md.
- Floe-authored additions in this package (`floe.json`, the rewritten SKILL.md,
  `references/{floe-browser-tools,service-lifecycle,qualification-runbook,PROVENANCE}.md`,
  `assets/fixtures/site/*`, `scripts/*`) are new first-party work distributed as part of this
  package under the same Apache-2.0 terms with attribution to Anthropic for the derived
  methodology; upstream code was NOT re-labelled or re-licensed away from Apache-2.0.
- No upstream file is vendored byte-for-byte except `LICENSE.txt` (required notice). Methodology
  and example patterns are preserved in transformed form (see references/upstream-methodology.md).
