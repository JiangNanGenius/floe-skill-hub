# Provenance — doc-coauthoring (first-party replacement of a license-blocked candidate)

## Original candidate identity (preserved for H1)
- Candidate id: `doc-coauthoring` (same id, category, tags, planNumber and versionTarget 1.0.0 in the registry)
- Original upstream: `https://github.com/anthropics/skills` @ `dbd4588f9e1033efb41dad4bef2f7947c8993d44` path `skills/doc-coauthoring`
- License status at source: blocked-no-upstream-license — skill directory carries no LICENSE file at the pinned commit and the repository publishes no root license; GitHub reports no detected license
- Independent verification (2026-10-26): license file absence re-checked at the pinned commit (root listing) and on the repository's current default branch via GitHub API — no license exists at either point, so no later re-pin can license the original text.

## What this package is
- First-party ORIGINAL content authored for Floe on 2026-10-26 (H2 lane) covering the same functional intent as the blocked candidate (see the registry description).
- No upstream bytes were transferred into this package: not the pinned upstream SKILL.md and not its rule files. Authoring inputs were the hub's own reviewed registry description, public standards (WCAG 2.2 / React platform semantics) and Floe's current tool surface.
- License: Floe-owned (references/licenses/FLOE-OWNED-NOTICE.md).

## Proposed catalog delta (H1 decision, NOT applied by this lane)
- `upstream`: -> null;  `source`: -> "F" (optional, both pin blocks null — the registry pattern already used by `floe-email-drafting`);
- `notes`: bilingual replacement record (candidate + reason above, condensed); `status.licenseChecked`: true (first-party owned), `adaptation`: in-progress -> frozen at packaging;
- versionTarget unchanged 1.0.0. If the coordinator instead retires the candidate, the id must not silently be reused for upstream bytes later.

- Coordinator packaging review (2026-10-26): included the full applicable source license text alongside the existing ownership notice; upstream license files remain unchanged.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `f5daee863fafba93f679668027502fb91d17344bea6dde37d9919afe07c33f04`
- `floe.json` sha256 `6bf822d7e78c766491fd84f781092caaa19d1baaf05214942c71e9f208a3d5a6`
- `references/licenses/FLOE-LICENSE.txt` sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`
- `references/licenses/FLOE-OWNED-NOTICE.md` sha256 `b61e9b46f63f4b47f34c5fc14adb9bb4a9e72779891ee08f6be136898e5eadd2`
- `references/templates.md` sha256 `3028c615deb3a430787f27d715b12260c66c20f2b9257f8a9740cb154740fffd`
