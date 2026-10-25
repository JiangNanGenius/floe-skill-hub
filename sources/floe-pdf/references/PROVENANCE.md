# Provenance — floe-pdf

- Upstream (first-party) repository: https://github.com/JiangNanGenius/floe-agent
- Immutable pin: commit `257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd` (skill-hub/sources/floe-pdf)
- Extracted files: `SKILL.md`, `floe.json`, `release.json` (byte-identical, `git show 257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd:...`).
- Package version in floe.json: `1.3.1`
- Legacy released feed state: version `1.3.1`
  - archive sha256: `627af0008cbe1f3ad6009c77e2c5a802ab539f83a7d3dc0c48698e0a09e12b08`
  - contentDigest: `7f1df5df8b36bf03a681cb8a5be113867b940b424755f3eb415ca3c74fdaae77`
  - size: 5212 bytes
  - legacy archive path: `skill-hub/packages/floe-pdf/1.3.1/floe-pdf.zip` (in the parent repo; Main owns the old feed — untouched here)
- License status: floe-owned (see references/licenses/FLOE-OWNED-NOTICE.md)
- Retrieval date: 2026-10-26 (H2 lane, this checkout).

## Payload delta vs released bytes (coordinator ruling 2026-10-26)
- Legacy released archive: version `1.3.1`, sha256 `627af0008cbe1f3ad6009c77e2c5a802ab539f83a7d3dc0c48698e0a09e12b08`, contentDigest `7f1df5df8b36bf03a681cb8a5be113867b940b424755f3eb415ca3c74fdaae77`, size 5212 bytes, payload files = [SKILL.md, floe.json] only (verified from the parent's signed catalog.json).
- This Hub package: version `1.3.2`; payload = [SKILL.md, floe.json, references/licenses/FLOE-OWNED-NOTICE.md, references/PROVENANCE.md].
- Byte-comparison vs the published old payload: `SKILL.md` identical to the pin; `floe.json` identical except the `version` field (packaging a new release requires its own version); the added `references/` files change the contentDigest BY CONSTRUCTION.
- Consequence honored: the Hub NEVER re-releases the same id+version with different bytes. Proposed registry delta for H1 (not applied by this lane): `versionTarget` 1.3.1 -> 1.3.2 and `firstParty.stagedSourceVersion` accordingly; floe-office keeps 1.5.0 because the legacy feed released 1.3.0 and the staged pin bytes already differ.
- release.json moved out of the package gate to the private handoff (Local/Private/skill-hub-20261026/ordinary/builtin-release-metadata/) — legacy-feed metadata, not ZIP content; the old feed and native App are untouched.

- Coordinator packaging review (2026-10-26): included the full applicable source license text alongside the existing ownership notice; upstream license files remain unchanged.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `9a008bb7705f070cb0125877ac4a9672ab862575db550e0ff0c6b0b9f07f8d9a`
- `floe.json` sha256 `19c16e8da3318697d605ba2bde740ee228c53cbd22bc5ee9124b437cafdc939b`
- `references/licenses/FLOE-LICENSE.txt` sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`
- `references/licenses/FLOE-OWNED-NOTICE.md` sha256 `ad6701089ba327143fd72ac706f7688600ab50722fab68c23388b9a1db07e526`
