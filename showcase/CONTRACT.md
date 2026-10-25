# Website client content contract v1

Frozen coordinator input, 2026-10-26. This is presentation data, not a change to catalog schema3, Skill manifests, permissions or executable packages. The website is a browser client of the same GitHub publication as the App. Its UI code remains in the website project; editorial content and media are maintained only in this Hub.

## Source files and identity

- `catalog/skills.json` remains the only candidate source for names, short descriptions, categories, tags, sources and runtime/status facts. Production clients use the authenticated channel feeds for those facts.
- `showcase/skills.json` supplies editorial overview, use cases, example requests/expected output, selected entries and media references. It never overrides signed basic facts.
- `showcase/links.json` records evidence-backed cross-skill references. It is not an installer dependency manifest.
- `showcase/media/` holds original or licensed media. The initial 43 SVG covers are explicitly illustrations, not App screenshots or proof of skill execution.

Resolve the production release/ref once to immutable publication Y. Catalogs, signatures, review records, showcase JSON and every media file of one update come from that same Y. The signed sourceCommit X remains separate. The browser requests the fixed GitHub API/raw-content hosts directly and never calls the website as a catalog API, package proxy, image proxy or fallback source. Do not execute code fetched from GitHub.

The Node importer can pre-render a snapshot for the first screen and SEO. The browser may refresh from GitHub without rebuilding the website. Cache exact signed bytes and Y; verify them under the compiled official key before restoring them. Commit a new cached publication atomically after its required validations pass. Failed, interrupted, unsupported-crypto, rate-limited or offline updates retain the last verified snapshot. With no production publication, the existing honest candidate preview remains usable; unsigned candidates never acquire an install offer.

Presentation JSON is untrusted text from the pinned official GitHub tree. Validate its shape, paths, bounds and media before rendering. It cannot set signatures, grants, status, availability, minimum App version, runtime or package/review bindings. Do not load a public-key file from Y into trust.

## skills.json

Top-level keys are exactly `schemaVersion: 1`, `editorPicks: [skillID]` and `entries: {skillID: editorial}`. IDs use the existing catalog grammar; picks are unique and at most 12.

An editorial has exactly `overview`, `useCases`, `examples`, `cover`, `gallery`. Text is plain bilingual `{en, zh-Hans}`. Use cases and examples are bounded arrays (at most 12 each); an example has exactly `prompt` and `output`, describing a request and expected output rather than claiming a successful run. Cover is a media reference or null; gallery has at most 12 media references. Missing editorial falls back to the signed basic description without invented examples.

A media reference has required `path`, `kind`, `credit`, optional `alt` and `caption`. Kind is `illustration`, `example-output` or `app-screenshot`. Credit, alt and caption are bilingual text; non-illustration media require a truthful caption. Omitted alt derives from the current canonical skill name. Keep license/source attribution with any third-party asset. Paths are strict relative files under `showcase/media/`; no URL, traversal, empty component, backslash, control character, symlink or executable content is allowed.

Only PNG, JPEG, WebP and SVG images are supported in v1. Bound JSON to 2 MiB, media to 4 MiB per file, 32 MiB total and 256 files. SVGs must not contain scripts, event handlers, foreignObject, DTD/entities or external resource references. The client validates bytes/MIME and computes media hashes before creating local Blob URLs; never execute or inline an untrusted SVG. Content hashes key caches; revoke unused Blob URLs. These bounds are separate from unchanged Skill package limits.

## links.json

Top-level keys are exactly `schemaVersion: 1`, `entries: {skillID: audit}`. An audit has `auditStatus` (`audited` or `pending`) and `links` (at most 32). An empty audited list means no cross-skill reference was found in the inspected source; pending means unknown.

A link has `relation` (`references`, `optional` or `requires`), `target`, `evidence` and optional bilingual `notes`. Internal target is exactly `{kind: "hub", id: skillID}`. External target is exactly `{kind: "external-skill", label, url}`; label is bilingual and url is an HTTPS GitHub source URL with an explicit pinned commit where available. External targets are visibly unlisted/unreviewed references; no automatic fetch/install follows them.

Evidence is an array of 1..8 `{file, sha256, lineStart, lineEnd}` records, naming strict relative source files in this repository and exact inspected bytes, with 1-based ordered line bounds. Preserve source meaning: a mention is not a required dependency. Report genuinely required unlisted skills and required cycles to the coordinator instead of relabeling them optional. Browsing follows one link at a time; graph inspection is bounded and detects cycles. No permission propagation, recursive installation, source execution or replacement of signed availability occurs through this file.

## Ownership

Hub content validation and cross-reference auditing write this directory only. The website client owns transport, compiled trust, cache, rendering and pre-render imports. Native App integration and release remain with the iOS main owner. The initial approved editorial/artwork was migrated from the website's frozen df0477d6 source; the generated website snapshot is a cache, never a second authoring source. Production activation and real install qualification remain separately recorded.
