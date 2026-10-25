# Provenance — floe-office

- Upstream (first-party) repository: https://github.com/JiangNanGenius/floe-agent
- Immutable pin: commit `257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd` (skill-hub/sources/floe-office)
- Extracted files: `SKILL.md`, `floe.json`, `release.json` (byte-identical, `git show 257acf30dcb1d40bd11860ec0b7f49ecc1ef32cd:...`).
- Package version in floe.json: `1.5.0`
- Legacy released feed state: version `1.3.0`
  - archive sha256: `007023c275c873f6abde244de117cd3f39cbf082370a3c69edc1077529d22f4a`
  - contentDigest: `d0606b0f9251bec331c34729e5da12fbe457c3164f055cc4e4d7ebd1ce72bfb9`
  - size: 4278 bytes
  - legacy archive path: `skill-hub/packages/floe-office/1.3.0/floe-office.zip` (in the parent repo; Main owns the old feed — untouched here)
- STAGED SOURCE ONLY: this tree is version 1.5.0; the released legacy feed still carries 1.3.0. The two states must never be mixed; this hub source has NOT been released to the legacy feed.
- License status: floe-owned (see references/licenses/FLOE-OWNED-NOTICE.md)
- Retrieval date: 2026-10-26 (H2 lane, this checkout).

## Payload delta vs released bytes (coordinator ruling 2026-10-26)
- Legacy released archive: version `1.3.0`, sha256 `007023c275c873f6abde244de117cd3f39cbf082370a3c69edc1077529d22f4a`, contentDigest `d0606b0f9251bec331c34729e5da12fbe457c3164f055cc4e4d7ebd1ce72bfb9`, size 4278 bytes, payload files = [SKILL.md, floe.json] only (verified from the parent's signed catalog.json).
- This Hub package: version `1.5.0`; payload = [SKILL.md, floe.json, references/licenses/FLOE-OWNED-NOTICE.md, references/PROVENANCE.md].
- Byte-comparison vs the published old payload: `SKILL.md` identical to the pin; `floe.json` identical except the `version` field (packaging a new release requires its own version); the added `references/` files change the contentDigest BY CONSTRUCTION.
- Consequence honored: the Hub NEVER re-releases the same id+version with different bytes. Proposed registry delta for H1 (not applied by this lane): `versionTarget` 1.5.0 -> 1.5.0 and `firstParty.stagedSourceVersion` accordingly; floe-office keeps 1.5.0 because the legacy feed released 1.3.0 and the staged pin bytes already differ.
- release.json moved out of the package gate to the private maintainer handoff as legacy-feed metadata, not ZIP content; the old feed and native App are untouched.

- Coordinator packaging review (2026-10-26): included the full applicable source license text alongside the existing ownership notice; upstream license files remain unchanged.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `01ce6781a87e647f6ee3dd77a2f7e5168c08c1611908cf7609efb4454f7e6f68`
- `floe.json` sha256 `4c21e47f6b227c1dfd4e54eb9a2c58f174748bcc924274ae3ced8446eff38147`
- `references/licenses/FLOE-LICENSE.txt` sha256 `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04`
- `references/licenses/FLOE-OWNED-NOTICE.md` sha256 `ad6701089ba327143fd72ac706f7688600ab50722fab68c23388b9a1db07e526`
