# Frozen managed runtime artifact descriptor v1 — ARM64 candidate delta

Coordinator/Main interface, frozen 2026-10-26; ARM64 target consts added for the
`0.1.17+floe.1.2.0` candidate on 2026-11-05. No catalog schema3 change. The canonical
Skill package carries exactly `references/engine-dependency.json`, byte-identical to
descriptor.v1.json for its release. It is data, not a source of permissions. JSON keys
and casing in schema.v1.json are normative; unknown fields fail closed.

## Authority and retrieval

Decode only from the already verified official Impeccable package snapshot: signed
production catalog + approve review + exact archive/contentDigest + effective existing
grants. Retain the verified catalog digest, sourceCommit X, and external immutable
publicationCommit Y in the native operation/receipt. An imported same-ID skill, edited
copy, README, model parameter or descriptor cannot create this authority. Respect
explicit disabled/uninstalled/user-modified choices.

The artifact is a raw binary in the independent Hub repository at `artifact.path`,
retrieved at that SAME Y. Y is externally resolved once, never serialized into this
descriptor; X is signed provenance and need not equal Y. Native constructs the URL from
its trusted Hub repository and Y. There is no descriptor URL, repository override,
install command, approval flag or environment selector. Require the exact cross-field
path `engines/impeccable/dist/impeccable-{componentVersion}/{target.triple}/floe-impeccable`.

Keep ordinary Skill limits unchanged (2MiB per file, 8MiB per package). The separately
handled runtime artifact has a native hard cap 16MiB ONLY for the explicitly
allowlisted `impeccable-engine` target; require descriptor integer size, actual
streamed bytes and SHA256 all to match. Validate ELF64 little-endian/AArch64
(e_machine 183)/EXEC/static (no PT_INTERP, no dynamic DT_NEEDED), not a general
executable bypass. Reject incompatible App version, target or capture-contract
version/digest before execution. No native-host execution/fallback.

## Lifecycle and readiness

Global Skill data installation need not choose an environment. At actual task use,
resolve explicit task/workspace/environmentID and existing write layer; prepare the
component via existing managed download + environment staging + jobs/native-service
lifecycle. No first-project or arbitrary temporary fallback, new model
installer/execution tool, or parallel approvals database. Stream to staged storage,
verify before atomic commit, preserve recoverable originals, and bind
cancellation/shared references to services rather than a view. Pass runtime Skill data
into the same resolved Linux environment through the existing verified snapshot stager.

In the guest, make the verified binary executable and probe using FIXED native-owned
commands, never commands from JSON: `engine-probe` must exit 0 and stdout must equal
`impeccable-engine {componentVersion}\n`; `contract` bytes must hash to
captureContract.sha256 and its version must be supported by the native producer. File
download/extraction alone is not runtime readiness. Set FLOE_IMPECCABLE_ENGINE to that
verified guest path and IMPECCABLE_SKILL_DIR to the canonical package read-only
engine-data root; the no-download launcher remains a consumer. If no task/environment
exists, defer readiness rather than claiming usable or selecting a random environment.

Native chooses concrete safe destination/storage APIs and transaction/lease mechanics;
those are not descriptor fields. Readiness receipts keep known
component/version/hash/target, actual environment and probe results separate from
source installation, reference emulation, App acceptance and publication.

## ARM64 candidate integration requirement (2026-11-05)

This schema's target consts now name the ARM64 guest (`arch arm64`, triple
`aarch64-unknown-linux-musl`, format `elf64-little-aarch64-exec-static`). The published
1.1.1 riscv64 descriptor, artifact bytes and schema line remain frozen and untouched.
The real `0.1.17+floe.1.2.0` descriptor is assembled atomically at integration time by
the package helper from the genuine engine build FACTS (actual size/SHA-256, capture
contract digest) plus the Main-confirmed `minimumAppVersion` floor; no descriptor
bytes are asserted here and no old floor (`1.7.60`/`1.7.65`) or digest may be reused.
This source delta is not independently deployable: it becomes valid only together with
the real artifact, the assembled descriptor and the package republication. Actual
ARM64 Debian 13 guest execution, latency/memory measurement and App tests remain
Main-owned and pending.
