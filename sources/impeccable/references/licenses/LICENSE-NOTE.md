# License note (Floe-authored, MPL-2.0)

`LICENSE` and `NOTICE.md` in this directory are the upstream `pbakaus/impeccable`
files verbatim (Apache-2.0, pinned commit in `../SOURCE-LOCK.json`). They cover
the upstream skill content preserved under `../engine-data/` (SKILL.md,
reference/*.md, scripts/command-metadata.json) and every derived instruction
text in this package.

Floe-authored files in this package (`scripts/floe-impeccable.sh`,
`../PROVENANCE.md`, `../SOURCE-LOCK.json`, `../MODIFICATIONS.json`,
`../MODIFICATIONS.md`, this note, and the engine-data root placement) are
MPL-2.0 under the Floe Skill Hub repository license. Nothing here relicenses
upstream content, and no full upstream tree is vendored — see
`../SOURCE-LOCK.json` (`notVendored`). The engine binary is a separate
digest-bound runtime artifact (`../engine-dependency.json`) and never enters
this package.
