# Floe Skill Hub — Signed Package Capacity Profiles

The Hub signs **package capacity profiles** into the channel feeds. A profile
is an explicit, reviewed opt-in: it never changes the default bounds, an
unknown profile fails closed everywhere, and a *present null* is rejected
(the native strict decoder checks key presence and requires a string; only a
missing key means standard).

## Wire shape (App consumer contract, 2026-11-10)

* **Registry (author field, unsigned source metadata)** —
  `catalog/skills.json` skill rows may carry an optional
  `packageProfile` string: `standard` (also the default when absent) or
  `large-source-v1`.
* **Standard feeds** — `catalog.json`, `catalog-full.json`,
  `android/catalog.json`, `android/catalog-full.json` keep the ORIGINAL
  five-key package binding and never carry a `profile` key: pre-capability
  strict readers reject unknown package keys before any version floor.
  Large-source entries never appear in these feeds.
* **Capability feeds** — separate same-Y signed feeds
  `catalog-large-source-v1.json`+`.sig` and
  `android/catalog-large-source-v1.json`+`.sig`. Each is a complete
  replacement/superset of the corresponding standard FULL feed at the same
  immutable publication commit Y: every standard entry id is present, every
  standard row is byte-identical, and only the additional large-source
  entries carry `package.profile = "large-source-v1"`. Absent or invalid
  capability projections leave the independently verified standard
  projection authoritative — a large entry is never enabled from an
  unverified projection.
* No `floe.json` or review-record change: the archive `sha256`,
  `contentDigest`, signature and review already authenticate every approved
  byte; only the verified catalog entry selects capacity.

## Profiles

| profile | files | compressed archive | single file |
| --- | --- | --- | --- |
| `standard` (default, also explicit) | 128 | 8 MiB | 2 MiB |
| `large-source-v1` | 2048 | 64 MiB | 2 MiB (unchanged) |

Rules that hold for every profile:

* Unknown profiles fail closed — no fallback, no silent standard treatment.
* A present `null` (or any non-string) profile value is rejected; only a
  missing key means standard.
* The archive gate enforces the selected profile's compressed-byte cap,
  central-directory entry count and declared running total BEFORE any
  payload is read; native-binary rejection, path/NFC/case-collision,
  symlink, zip-structure and `SKILL.md`/`floe.json` gates stay fully active.
* Download/transport capacity derives **only** from the verified, signed
  bound entry (`package.profile` + authenticated `size`). Budgets are never
  raised globally and never derived from a URL.
* `packageProfile` is frozen across automatic updates: the tracker refuses
  a profile drift between base and candidate registry rows (a capacity
  change is a reviewed act).
* The legacy four-item compatibility view, all historical publications and
  the fixture samples are unchanged; fixtures rebuild byte-identical.

## Tooling surface

* `hubcore` — `PACKAGE_PROFILES` (`standard`, `large-source-v1`),
  `package_profile_bounds()`, profile-aware `validate_package_files` /
  `check_archive_bytes` (early bounds), registry `packageProfile` validation,
  standard-vs-capability `validate_catalog`, `validate_capability_projection`.
* `build_packages` / `build_catalog` — staged sources and release bindings
  use the registry row's profile; standard feeds exclude large rows and
  stay profile-free; both same-Y capability pairs are emitted atomically
  when either channel has large-source entries. A channel without a large
  offer retains its exact standard full rows; App readiness is independent.
* `check_catalog` / `sign_publication` — published and staged referenced
  archive bytes are verified under the profile of the signed binding;
  capability pairs verify standalone and as exact supersets. The signing
  launch gate checks the standard-profile set independently, requires both
  capability feeds atomically when either channel has a large-source offer,
  and applies every execution, review and mandatory-runtime gate to the
  effective complete offers. A large row cannot bypass an admission gate by
  being absent from the standard feeds. Appended deep adaptations retain
  their own truthful label and per-item gates; they never replace any of
  the original nine mandatory IDs or change a legacy label.
* `automatic_publication` — candidate re-derivation verifies archives under
  the frozen row profile, stages scan-side package writes with the
  trusted-entry-derived capacity, and extends Y/H diffs, ledger rows and
  public readback to atomic capability pairs.
* `automatic_transport` — relay receipts declare capability feeds
  atomically; the capability pair is verified after the standard full view
  at the same Y (signature, capability shape, exact superset projection);
  package references carry the verified bound sizes.
* `upstream_updates` — candidate gates and the published-digest baseline
  reader use the trusted entry's profile.
* `gen_schemas` — `registry.schema.json` carries `packageProfile`;
  `catalog.schema.json` stays the strict standard shape;
  `catalog-large-source-v1.schema.json` documents the capability feed.

Tests: `tests/catalog/test_package_profiles.py` and
`tests/catalog/test_sign_large_source.py` (real isolated signing path with
ephemeral test keys, including single-channel admission).

## Client version floors by channel

The optional author-only `minimumAppVersions` map selects the existing signed
`minimumAppVersion` for each offered channel. For example, an entry can retain
its iOS `minimumAppVersion` and declare `{"android": "0.1.1"}` in the map,
because Android's client compatibility domain is independent of its APK display
version and the iOS version. Missing overrides preserve historical feed bytes;
unknown/unoffered channels, empty/null maps and non-`X.Y.Z` values are rejected.
Explicit floors are retained instead of applying the portable-guide sentinel.
The map never appears in a signed feed or changes an App wire field.

Only the native owner can establish the first capable delivered consumer.
These source fields do not prove compilation, App execution or availability,
and the automatic updater cannot change version floors. Taste's Android
consumer and release remain pending; this tooling does not publish an offer.
Focused tests: `tests/catalog/test_channel_versions.py`.
