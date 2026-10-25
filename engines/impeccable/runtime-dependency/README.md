# Frozen managed runtime artifact descriptor v1

Coordinator/Main interface, frozen 2026-10-26. No catalog schema3 change. The canonical Skill package carries exactly `references/engine-dependency.json`, byte-identical to descriptor.v1.json for this release. It is data, not a source of permissions. JSON keys and casing in schema.v1.json are normative; unknown fields fail closed.

## Authority and retrieval

Decode only from the already verified official Impeccable package snapshot: signed production catalog + approve review + exact archive/contentDigest + effective existing grants. Retain the verified catalog digest, sourceCommit X, and external immutable publicationCommit Y in the native operation/receipt. An imported same-ID skill, edited copy, README, model parameter or descriptor cannot create this authority. Respect explicit disabled/uninstalled/user-modified choices.

The artifact is a raw binary in the independent Hub repository at `artifact.path`, retrieved at that SAME Y. Y is externally resolved once, never serialized into this descriptor; X is signed provenance and need not equal Y. Native constructs the URL from its trusted Hub repository and Y. There is no descriptor URL, repository override, install command, approval flag or environment selector. Require the exact cross-field path `engines/impeccable/dist/impeccable-{componentVersion}/{target.triple}/floe-impeccable`.

Keep ordinary Skill limits unchanged (2MiB per file,8MiB per package). The separately handled runtime artifact has a native hard cap16MiB ONLY for the explicitly allowlisted `impeccable-engine` target; require descriptor integer size, actual streamed bytes and SHA256 all to match. Validate ELF64 little-endian/RISC-V/EXEC/static(no PT_INTERP), not a general executable bypass. Reject incompatible App version, target or capture-contract version/digest before execution. No native-host execution/fallback.

## Lifecycle and readiness

Global Skill data installation need not choose an environment. At actual task use, resolve explicit task/workspace/environmentID and existing write layer; prepare the component via existing managed download + environment staging + jobs/native-service lifecycle. No first-project or arbitrary temporary fallback, new model installer/execution tool, or parallel approvals database. Stream to staged storage, verify before atomic commit, preserve recoverable originals, and bind cancellation/shared references to services rather than a view. Pass runtime Skill data into the same resolved Linux environment through the existing verified snapshot stager.

In the guest, make the verified binary executable and probe using FIXED native-owned commands, never commands from JSON: `engine-probe` must exit0 and stdout must equal `impeccable-engine {componentVersion}\n`; `contract` bytes must hash to captureContract.sha256 and its version must be supported by the native producer. File download/extraction alone is not runtime readiness. Set FLOE_IMPECCABLE_ENGINE to that verified guest path and IMPECCABLE_SKILL_DIR to the canonical package read-only engine-data root; the no-download launcher remains a consumer. If no task/environment exists, defer readiness rather than claiming usable or selecting a random environment.

Native chooses concrete safe destination/storage APIs and transaction/lease mechanics; those are not descriptor fields. Readiness receipts keep known component/version/hash/target, actual environment and probe results separate from source installation, reference emulation, App acceptance and publication. The current binary is verified under reference riscv64 emulation; actual TinyEMU4.15/256MiB and App tests remain Main-owned.
