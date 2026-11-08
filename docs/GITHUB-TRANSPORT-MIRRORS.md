# GitHub transport mirror list v1

The one discovery pair is `transport/mirrors.v1.json` and `transport/mirrors.v1.json.sig` in this repository. A website may cache these exact small signed bytes for display and separately maintain its authorized bounded website-image cache. It does not become an App discovery root or an App SkillHub package/image acceleration proxy.

The list orders or disables the two App-approved IDs `ghfast.top` and `gh-proxy.com`. URLs, templates, repositories, keys, content hashes, permissions and new hosts cannot be supplied by the list. GitHub primary is always first. Role defaults are `rawFiles=[ghfast.top,gh-proxy.com]`, `atom=[gh-proxy.com]`, `releaseAssets=[]`. GHFast did not support the probed Atom path; release downloads/VM images are not claimed to consume this list.

## Wire and trust

The six exact fields are `schemaVersion`, `purpose`, `generation`, `issuedAt`, `expiresAt`, `roles`. Purpose is `floe-github-transport-mirrors`; version is integer 1. Generation is an integer from 1 to 9007199254740991. Timestamps are real UTC RFC3339 seconds ending in `Z`; issue time may be at most 300 seconds ahead, and validity is positive and at most 30 days. The roles object has exactly `rawFiles`, `atom`, `releaseAssets`, each an ordered array of at most two distinct approved IDs.

Canonical payload is ASCII UTF-8, sorted keys, compact separators and exactly one final LF. The existing official detached Ed25519 envelope signs the exact ASCII prefix `FLOE-GITHUB-TRANSPORT-MIRRORS-V1` followed by LF and then the canonical payload bytes. A normal catalog signature cannot verify this context, nor can this signature verify a catalog. Limits are 16 KiB payload and 8 KiB envelope. The App's compiled trusted keys remain the root; the mirror and downloaded list cannot supply a key.

Native consumers verify signature before interpreting fields, persist the highest accepted generation together with the last verified list atomically, and refresh at most once per six hours of normal use. An unchanged byte-identical refresh is a no-op, not a new accepted generation. Changed bytes at the same generation or lower generations are refused. Expired cache uses bundled defaults while retaining its generation floor. Invalid refreshes never replace the valid record. Bootstrap discovery uses compiled routes and one immutable Hub publication commit for both payload and signature.

Only transport availability errors may switch an existing content request to the next approved route. The original repository, publication commit Y, path, view and expected content identity stay unchanged. Access, certificate, redirects, cancellation, size, parser, signature and digest failures never justify trying a different source or base view. Anonymous requests carry no credentials or cookies.

## Controlled publication and renewal

1. Prepare canonical data with `scripts/transport_manifest.py generate`, an explicit new generation and UTC interval. The generator never reads a signing key. Every role/order/enablement or validity change requires a higher generation.
2. Put the exact payload into a reviewed immutable data snapshot S. Keep code and data distinct. The pinned data-only signing bridge in `JiangNanGenius/floe-agent` uses `mode=transport`, fetches S as data and the reviewed tooling T separately, independently resolves current publication Y, verifies its signed generation baseline, and signs only the fixed pair with the existing official secret. No candidate code, maintenance probes or arbitrary script runs in the secret-bearing step.
3. Verify the artifact's detached context signature and signed receipt, including T/S/tree/byte hashes. Publish only the exact pair and public-safe receipt from that run with a compare-and-swap against current main. Do not modify a payload while retaining its signature. Preserve published catalog/package/review bytes.
4. Read the public pair back at its immutable publication commit and verify it again. The website and Apps consume that same pair; no App rebuild is needed to update the already-approved role order after reader integration.

`transport-mirror-maintenance.yml` runs daily in GitHub Actions, entirely independently of a developer Mac. It verifies the published list, probes only listed approved hosts/roles using fixed sample URLs and bounded requests, and retains a short report. Health is observed from the Actions runner, not from the user's device, and never changes signed role order or replaces the user's actual download result. Redirects are refused. It holds no signing secret or repository write/approval/merge permissions.

When expiry is within seven days (including an expired verified historical list), maintenance emits only an **unsigned** same-role renewal candidate at generation+1 with 14-day validity. It does not sign, merge, publish, add a host or automatically disable one based on health. That candidate follows the same controlled data-only signing and public read-back path above. A failed check leaves the published pair untouched, retaining the original diagnostic in the run/report. A missing initial signed pair is reported as not initialized; no substitute trusted list is fabricated. The initial transport mode must be added to the existing App-repository signing workflow by its owner; no additional private key is requested or copied into this repository.

## Qualification boundary

Python tests exercise strict canonical/time/role/generation gates, domain separation, missing keys, exact real Git snapshot checks, data-only bridge behavior, missing pair/history refusal, and advisory-only maintenance using isolated ephemeral test keys. Native model/verifier/cache/transport candidates are qualified separately and remain subject to App integration. Neither signing a list nor an offline component test proves an installed App or Android flow. APT/PyPI software sources are a separate mechanism.
