# UPSTREAM-PIN-CONTRACT — per-skill reviewed pins (2026-10-28)

Implementation:
`scripts/upstream_pins.py`; enforced by `scripts/check_catalog.py check_pins`
and `tests/catalog/test_registry.py`; focused tests:
`tests/test_upstream_pins.py`. This document is the review authority for the
`docs/UPSTREAM-PINS.json` shape; changing the shape requires maintainer review.

## Why

`check_pins` historically compared every registry `upstream.commit` against
one default per repository in `docs/UPSTREAM-PINS.json`. Tracker acceptance
is therefore per-repository atomic: one held script row in a shared corpus
repository freezes every guide from the same repository even when the guide
update itself was reviewed and eligible. The contract permits an OPTIONAL,
EXPLICIT, per-entry reviewed override — not a weakening of the pin rule.

## Document shape

```json
{
  "reviewBaselineDate": "YYYY-MM-DD",
  "repositories": { "owner/repo": "<40 lowercase hex>", "...": "..." },
  "skillOverrides": {
    "<exact registry id>": { "repository": "owner/repo", "commit": "<40 lowercase hex>" }
  }
}
```

* `repositories` — unchanged: the reviewed default effective pin for every
  entry of that repository, plus watch-only baselines with no rows (they are
  never removed by an advance).
* `skillOverrides` — OPTIONAL. Legacy documents without it keep validating
  and passing exactly as before; no production bytes change until a real
  accepted advance lands.
* No other top-level or override fields exist or are tolerated.

## Effective pin rule (never loosened)

For each registry row with a non-null `upstream` block:

```
effective pin = explicit override commit (when the row has a valid bound override)
              else repositories[repository]
requirement: registry upstream.commit == effective pin  (EXACT, byte-for-byte)
```

A row never passes because a commit is merely well-formed; equality is
always against its reviewed baseline. Without overrides the check reproduces
the original `check_catalog` failure messages verbatim. A mis-bound or
stale override still governs its row: matching the repository default is
not an escape hatch (`"… diverges from its reviewed per-entry baseline …"`).

## Deny-by-construction (all fail closed, `UpstreamPinError`)

Strict byte parsing (`parse_pins_bytes` / `load_pins_file`):

* input must be bytes, ≤ `MAX_PINS_BYTES` (64 KiB), valid UTF-8;
* duplicate JSON keys at any nesting depth refused; NaN/Infinity refused;
* exactly `reviewBaselineDate` + `repositories` (+ optional `skillOverrides`);
* `reviewBaselineDate` must be a REAL calendar date (shape + `datetime.date`);
* repository keys must be `owner/repo`; every default and override commit
  must be 40 lowercase hex;
* override keys must be SkillIdentifiers; override values must carry exactly
  `{repository, commit}`; `repository` must be listed in `repositories`.

Registry binding (`check_registry_pins` reasons):

* an override may only bind an EXISTING registry row whose `upstream` is
  non-null — unknown ids and local/builtin/Floe-original (`upstream == null`)
  rows are refused, so unlicensed Floe-original replacements can never be
  "imported" through this document;
* the override's `repository` must equal the row's own upstream repository —
  overrides cannot change repository identity;
* no arbitrary source URLs, branches, tags or loose/abbreviated commit
  matching exist anywhere in this contract.

## Advancement — `advance_pin_document(prior_doc, old_registry, new_registry,
accepted_ids, today)`

Deterministic, pure (inputs never mutated; result post-verified against
`new_registry` before it is returned). Guards, all fail closed:

1. `prior_doc` must be exactly valid against `old_registry` (the current
   reviewed baseline);
2. `old_registry` and `new_registry` must carry the EXACT same entry id set,
   the same per-entry repository identity and the same upstream null-ness —
   rows cannot be added, removed, re-homed, or flipped between upstream and
   Floe-original here;
3. only `accepted_ids` may change `upstream.commit`; every held entry keeps
   its old commit byte-for-byte;
4. accepted ids must be real external entries; accepted new commits must be
   40 lowercase hex (format only);
5. `today` must be a real `YYYY-MM-DD` date and becomes the new baseline date.

Per-repository compaction after the guards pass:

* all current external rows of a repository share ONE commit → that commit
  becomes the compact repository default and every redundant override for
  the repository is dropped;
* commits are MIXED → the previous repository default is retained and
  overrides are written ONLY for entries differing from it (prior unrelated
  overrides are recomputed honestly, never silently erased or expanded);
* repositories without rows (watch-only baselines) are preserved untouched;
* non-upstream rows never gain pins; `skillOverrides` is omitted entirely
  when empty.

`deterministic_bytes(doc)` gives the stable serialization (sorted keys,
indent 2, trailing newline) for a NEW version of the document; the current
live baseline keeps its historical key order until an advance replaces it.

## Authority boundary

* `accepted_ids` are the trusted recomputed update plan's output — NOT an
  external approval flag. Passing ids here grants nothing by itself.
* This module NEVER fetches, clones, or verifies commit content, upstream
  reachability, license status, merge eligibility or package bytes. Those
  gates stay with the tracker lane (`upstream_updates.py` and its policy/
  schema owner), the signed review chain, and the App-side recompute.
* The trusted tracker derives eligible per-entry pin advances. The publication
  pipeline independently recomputes and verifies them before signing. Policy
  and tooling changes require maintainer review and an explicit App anchor
  update; ordinary data-only skill updates need no anchor change.
* This document is the CURRENT review-pin baseline. The cumulative
  publication ledger and every published package/review fact are unchanged
  by any advance here.
* Full 43-row candidate registry shape validation remains
  `hubcore.validate_registry`'s job (run by `check_catalog` before this
  gate); `upstream_pins` enforces pin semantics plus the minimal structure
  it reads, so trusted lanes and deterministic tests share one contract.

## Tracker integration seam

`scripts/upstream_updates.py` resolves each tracked entry through
`upstream_pins.effective_pin_for_entry` and validates the strict pin document
before planning. An accepted guide can advance independently while a held
peer keeps its reviewed pin. Every entry still requires exact equality with
its effective pin; overrides never grant approval or bypass source, license,
package or signature checks.
