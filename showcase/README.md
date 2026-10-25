# Floe Skill Hub showcase (website client content)

This directory is the single authoring source for the Skill Hub website's
*presentation* layer. It is not a second catalog. The frozen v1 rules live in
[`CONTRACT.md`](CONTRACT.md); this README is the maintainer's edit guide.

## What is authored where

| Facts | Source of truth | Who edits |
| --- | --- | --- |
| Name, short description, category, tags, sources, runtime/status | `catalog/skills.json` (signed channel feeds in production) | Hub catalog lane only |
| Editorial overview, use cases, examples, editor picks, covers/gallery | `showcase/skills.json` + `showcase/media/` (this directory) | Website-content maintainer |
| Cross-skill references with evidence | `showcase/links.json` (this directory) | Website-content maintainer |
| Transport, trust, caching, rendering, pre-render | website project (W lane) | Website owner |

Basic facts are edited **only** in the catalog. Showcase records never repeat
or override them: an omitted media `alt` is derived from the current canonical
skill name at render time, and a missing editorial record falls back to the
signed basic description — never to invented examples.

## Editing showcase content

1. Edit `showcase/skills.json`:
   - top-level keys stay exactly `schemaVersion: 1`, `editorPicks`, `entries`;
   - `editorPicks` is unique and at most 12;
   - every entry key is an existing registry id from `catalog/skills.json`;
   - each editorial has exactly `overview`, `useCases`, `examples`, `cover`,
     `gallery`; all text is plain bilingual `{en, zh-Hans}`;
   - use cases and examples hold at most 12 items each; an example is exactly
     `prompt` + `output` describing a request and its expected output — it
     must not claim a successful run.
2. Add media under `showcase/media/` and reference it with a strict relative
   path (`showcase/media/...`): no URLs, no traversal, no backslashes, no
   symlinks. v1 supports PNG, JPEG, WebP and SVG only. SVGs must not contain
   scripts, event handlers, `foreignObject`, DTD/entities or external
   references. Keep third-party credits and license notices with the asset;
   keep the original generated covers faithful (no cosmetic redraws).
3. Run the gate after editing:

   ```sh
   python3 showcase/scripts/validate_showcase.py
   ```

   It is read-only, stdlib-only and fail-closed: shape, bilingual bounds,
   registry join, picks, media paths, magic-MIME, SVG safety, size/file
   bounds, links evidence (hashes + line ranges) and required-cycle checks.

## Auditing cross-skill references

`showcase/links.json` records, per registry id, what the installed skill
sources actually say about other skills:

- `relation` is `references` (routing/pairing guidance), `optional` (used
  only when present/provisioned) or `requires` (hard prerequisite). Do not
  soften a real required unlisted skill into `optional`; report it to the
  coordinator instead.
- internal targets are `{kind: "hub", id}` with a registry id;
- external targets are `{kind: "external-skill", label, url}` — visibly
  unlisted/unreviewed references pinned to an explicit commit URL where
  available. Never auto-fetch, auto-install or inherit permissions from them.
- every link carries 1–8 evidence records: strict repository-relative `file`,
  `sha256` of the exact inspected bytes, and 1-based `lineStart`/`lineEnd`.
  Recompute hashes after any source edit (`shasum -a 256 <file>`).
- `auditStatus: "audited"` with an empty `links` list means no cross-skill
  reference was found in the inspected corpus — not a skipped audit.
  `pending` means unknown (e.g. source bytes still inflight under another
  lane).

## Publishing flow

The coordinator resolves one immutable publication `Y`. Catalog, showcase
JSON and every media file of one update come from that same `Y`; the website
client fetches them directly from GitHub (never through the website as an
API/proxy/CDN) and may refresh without a website rebuild. There is no
manually maintained generated manifest or hash index here — `Y` binds the
source files and the website computes media hashes for its cache.
