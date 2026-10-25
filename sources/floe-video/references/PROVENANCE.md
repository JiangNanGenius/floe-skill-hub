# Provenance — floe-video

- Upstream (first-party) repository: https://github.com/JiangNanGenius/floe-agent
- Immutable pin: commit `257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd` (skill-hub/sources/floe-video)
- Extracted files: `SKILL.md`, `floe.json`, `release.json` (byte-identical, `git show 257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd:...`).
- Package version in floe.json: `1.0.1`
- Legacy released feed state: version `1.0.1`
  - archive sha256: `89d92b809a9b11768b149b96857a11062b5d94d09e2a335e7068c29ebf536154`
  - contentDigest: `84eea2619c84f59a868906e0f5b7222aa7bba60541059569b441d2f8bfd2a261`
  - size: 2838 bytes
  - legacy archive path: `skill-hub/packages/floe-video/1.0.1/floe-video.zip` (in the parent repo; Main owns the old feed — untouched here)
- License status: floe-owned (see references/licenses/FLOE-OWNED-NOTICE.md)
- Retrieval date: 2026-10-26 (H2 lane, this checkout).

## Payload delta vs released bytes (coordinator ruling 2026-10-26)
- Legacy released archive: version `1.0.1`, sha256 `89d92b809a9b11768b149b96857a11062b5d94d09e2a335e7068c29ebf536154`, contentDigest `84eea2619c84f59a868906e0f5b7222aa7bba60541059569b441d2f8bfd2a261`, size 2838 bytes, payload files = [SKILL.md, floe.json] only (verified from the parent's signed catalog.json).
- This Hub package: version `1.0.2`; payload = [SKILL.md, floe.json, references/licenses/FLOE-OWNED-NOTICE.md, references/PROVENANCE.md].
- Byte-comparison vs the published old payload: `SKILL.md` identical to the pin; `floe.json` identical except the `version` field (packaging a new release requires its own version); the added `references/` files change the contentDigest BY CONSTRUCTION.
- Consequence honored: the Hub NEVER re-releases the same id+version with different bytes. Proposed registry delta for H1 (not applied by this lane): `versionTarget` 1.0.1 -> 1.0.2 and `firstParty.stagedSourceVersion` accordingly; floe-office keeps 1.5.0 because the legacy feed released 1.3.0 and the staged pin bytes already differ.
- release.json moved out of the package gate to the private handoff (Local/Private/skill-hub-20261026/ordinary/builtin-release-metadata/) — legacy-feed metadata, not ZIP content; the old feed and native App are untouched.

- Coordinator packaging review (2026-10-26): included the full applicable source license text alongside the existing ownership notice; upstream license files remain unchanged.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `9bea68b275cfdfa5a1ac230d5c3ac06fa3899ff9f56c9f959a3319f548787abc`
- `floe.json` sha256 `3e2e0371a54f5779cb89122b3ebbe906204a91113b7c8de2fceaf4af70ba5e92`
- `references/licenses/FLOE-LICENSE.txt` sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`
- `references/licenses/FLOE-OWNED-NOTICE.md` sha256 `ad6701089ba327143fd72ac706f7688600ab50722fab68c23388b9a1db07e526`
