# Legacy compatibility of the Skill Hub feeds

Status: contract for the migration window. The App's historical four-item
feed at `JiangNanGenius/floe-agent/skill-hub` remains byte-immutable for old
clients; this Hub produces the new channels and can render a compatibility
**view** of it, nothing else.

## What old clients hard-require (verified against current App code)

* `OfficialSkillHub` fetches only `JiangNanGenius/floe-agent` →
  `skill-hub/catalog.json` + `skill-hub/catalog.sig` (pinned source; a feed is
  data, never a new trust root).
* Accepted `schemaVersion` window is `[1, 2]` and `publisher` must be
  `JiangNanGenius`; `catalog.packages` must contain **exactly** the four
  reserved ids `floe-pdf`, `floe-office`, `floe-network`, `floe-video`.
* Every package entry keeps `path == "skill-hub/packages/{id}/{version}/{id}.zip"`,
  `1 ≤ size ≤ 8 MiB`, lowercase 64-hex `sha256` and `contentDigest`, strict
  `X.Y.Z` `version`/`minimumAppVersion`, and non-empty `releaseNotes` for both
  `zh-Hans` and `en`.
* The Ed25519 envelope is `{"keyID": "official-2026-09", "signature": base64}`
  over the exact canonical catalog bytes; the trust root is compiled into the
  app (`OfficialSkillHubKeys.generated.swift`).
* `skill-hub/models.json` (the floe-video CoreML asset catalogue) continues to
  live with the App repo; it is not part of any Hub channel.

## Rules during migration

1. The old four-item feed is never rewritten in place: a same-version content
   change is refused by both the legacy builder's immutability gate and the
   client. Any refresh means a new version published by the App main publish
   owner, from byte-identical qualified archives.
2. This Hub's new channel feeds use `schemaVersion 3` deliberately **outside**
   the old `[1, 2]` window, so any old client pointed at the new repo fails
   closed rather than mis-decoding. New candidates never silently enter the
   four-item decoder.
3. `scripts/build_legacy_view.py` renders the old shape strictly from a
   production Hub catalog whose four builtins are qualified with signed review
   bindings. While the builtins are staged-but-unqualified (the current honest
   state), the script reports the view as **pending**; the existing released
   four-item bytes stay authoritative. The view is never emitted to a
   production path automatically and carries no signature from this lane.
4. Who publishes what:
   * Coordinator/main publish owner: signs and places any refreshed legacy
     view into `JiangNanGenius/floe-agent/skill-hub` using the production key
     and the existing release route.
   * H1 (this lane): registry, schemas, deterministic builder/check gates,
     fixture-only signed samples and the view generator.
   * Content lanes: `sources/{id}` only; deltas back to the coordinator.
5. Built-in identity continuity: the four official ids, their content digests,
   user disabled/uninstalled choices, local modifications and in-flight task
   snapshots survive migration; a newer installed version is never downgraded
   and same-name packages never auto-overwrite.

## Legacy view shape (for byte comparison)

The rendered view equals the old decoder's expected canonical bytes:

```json
{"models": [], "packages": [ /* exactly the four reserved guides, old path prefix */ ],
 "publisher": "JiangNanGenius", "schemaVersion": 2}
```

`scripts/tests/catalog/test_build_and_boundaries.py::TestLegacyView` keeps
these invariants under test (four rows only, no candidate widening, clear
pending reason, old path prefix and bilingual release notes present).
