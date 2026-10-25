# Provenance — writing-guidelines (first-party replacement of a license-blocked candidate)

## Original candidate identity (preserved for H1)
- Candidate id: `writing-guidelines` (same id, category, tags, planNumber and versionTarget 1.0.0 in the registry)
- Original upstream: `https://github.com/vercel-labs/agent-skills` @ `063bee94c3f4df8453406c830b0a7df0f2860278` path `skills/writing-guidelines`
- License status at source: blocked-no-upstream-license — repository has no license file at the pinned commit or on its current default branch; content may not be copied
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
- `SKILL.md` sha256 `2dbf5c3cdadf0540937564032c9faf30cb95c5e5a6f63fa8d73155ed5b62e880`
- `floe.json` sha256 `f900380a8973f93086916a30cc9c272ffe0121194d74ba006916adc6c0f431c4`
- `references/licenses/FLOE-LICENSE.txt` sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`
- `references/licenses/FLOE-OWNED-NOTICE.md` sha256 `b61e9b46f63f4b47f34c5fc14adb9bb4a9e72779891ee08f6be136898e5eadd2`
- `references/readability-procedure.md` sha256 `05009d61c69a82401ab7275114e5aea1f1ce7b6018a6098873757764e226cc32`
