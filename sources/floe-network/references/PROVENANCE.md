# Provenance — floe-network

- Upstream (first-party) repository: https://github.com/JiangNanGenius/floe-agent
- Immutable pin: commit `257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd` (skill-hub/sources/floe-network)
- Extracted files: `SKILL.md`, `floe.json`, `release.json` (byte-identical, `git show 257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd:...`).
- Package version in floe.json: `1.1.3`
- Legacy released feed state: version `1.1.3`
  - archive sha256: `80a2b1b11d50ec5bc29f58930f86ff25c4b40787382a8a77ad4b34adf6354990`
  - contentDigest: `a6e2fe78c5681886da65d43b61a26288e9c6cefd2e172d9a4c2f972112a2466d`
  - size: 1661 bytes
  - legacy archive path: `skill-hub/packages/floe-network/1.1.3/floe-network.zip` (in the parent repo; Main owns the old feed — untouched here)
- License status: floe-owned (see references/licenses/FLOE-OWNED-NOTICE.md)
- Retrieval date: 2026-10-26 (H2 lane, this checkout).

## Payload delta vs released bytes (coordinator ruling 2026-10-26)
- Legacy released archive: version `1.1.3`, sha256 `80a2b1b11d50ec5bc29f58930f86ff25c4b40787382a8a77ad4b34adf6354990`, contentDigest `a6e2fe78c5681886da65d43b61a26288e9c6cefd2e172d9a4c2f972112a2466d`, size 1661 bytes, payload files = [SKILL.md, floe.json] only (verified from the parent's signed catalog.json).
- This Hub package: version `1.1.4`; payload = [SKILL.md, floe.json, references/licenses/FLOE-OWNED-NOTICE.md, references/PROVENANCE.md].
- Byte-comparison vs the published old payload: `SKILL.md` identical to the pin; `floe.json` identical except the `version` field (packaging a new release requires its own version); the added `references/` files change the contentDigest BY CONSTRUCTION.
- Consequence honored: the Hub NEVER re-releases the same id+version with different bytes. Proposed registry delta for H1 (not applied by this lane): `versionTarget` 1.1.3 -> 1.1.4 and `firstParty.stagedSourceVersion` accordingly; floe-office keeps 1.5.0 because the legacy feed released 1.3.0 and the staged pin bytes already differ.
- release.json moved out of the package gate to the private maintainer handoff as legacy-feed metadata, not ZIP content; the old feed and native App are untouched.

- Coordinator packaging review (2026-10-26): included the full applicable source license text alongside the existing ownership notice; upstream license files remain unchanged.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `be4d0ab337905b4a831aea4bcfc2d34016c1d6a944f1a68b783dd498220bae0e`
- `floe.json` sha256 `f2c7c9adcd2262681d8d29c3b69d07335f2f207dbacceeba25c1b379c40e1cb4`
- `references/licenses/FLOE-LICENSE.txt` sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`
- `references/licenses/FLOE-OWNED-NOTICE.md` sha256 `ad6701089ba327143fd72ac706f7688600ab50722fab68c23388b9a1db07e526`
