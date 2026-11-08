# OAuth runtime candidate — 2026-11-08

This checkpoint implements Hub support for the known `ortie-oauth-engine` branch and the two native configuration declarations `floe-google-auth` / `floe-microsoft-auth`. It does not publish install offers. The minimum App version and production descriptor remain absent until actual App integration evidence is supplied. No old-App OAuth compatibility path is added.

The original OAuth owner and Hub agreed on these canonical bytes:

| Input | SHA-256 |
| --- | --- |
| OAuth contract, 470 bytes | `f2d6c2f5d233b695a1e96576e5410fb286fbf0a1e7892055bb8b7acf8056b630` |
| Full MCP handshake fixture, 9,206 bytes | `1cbf74ffdba9bf2179435cf1dfa9089b87185031c11813d2dbb7a7080ad69d1e` |
| Distribution manifest, 403 original files | `d94713417182f1b86e61a64dffcc4cc7cb67195771f5c9dbc1ee6c39a5467e66` |
| Static ARM64 runtime, 3,691,576 bytes | `836adf744e9981a6c1920818e36a313cf8f0aa4b5c24e49e874f2c99def0b291` |

The seven-key descriptor uses `oauthContract`, while Impeccable retains `captureContract`. Source/package validation, catalog construction and standalone publication validation bind the same-root descriptor, artifact, contract, complete MCP schemas and all notice/source files. Fresh publication reconstruction contains 408 bound files. Existing release-builder output was byte-identical to baseline `8aa129cddbe50e8094c8bafc2a2be4772193823f` for the same current registry and source identity.

## Focused verification

- Configuration admission: 7 checks passed, including existing native iOS configuration and all existing manifests.
- Ortie runtime binding: 9 checks passed, including complete fresh-tree reconstruction, component/path confusion, byte tampering, missing/symlink notices, traversal/duplicate entries, mandatory pinned MPL source, strict transport types and the full handshake schema pin. Actual runtime bytes are inspected, never executed by these tests. The descriptor floor in temporary fixtures is test-only.
- Upstream pin handling: 40 checks passed after updating the live-baseline expectations to the exact three reviewed small-business overrides.
- `scripts/check_catalog.py` passed. Missing per-entry review pins were added for `business-pulse`, `invoice-chase` and `payroll-prep`; their actual existing commit is retained. Repository-wide defaults, published packages, reviews, feeds and signatures are unchanged.
- Historical `test_runtime_dependency.py` remains a known failing suite with retired RISC-V fixtures: 60 tests produced 24 failures and 5 errors. In its 33 pure descriptor/artifact checks, both original HEAD code and this candidate produced the same 12 failures and 5 errors. These failures were retained, not skipped or rewritten to pass. The new checks validate the actual current ARM64 contract separately.

Initial candidate checks exposed a distribution ordering error (Path-component ordering rather than full path-string ordering); sorting and contract hashes were corrected before this checkpoint. A temporary additional test incorrectly assumed a no-op pin advancement retains the prior date; the helper's documented supplied-date result is now asserted explicitly. Neither correction changes published history.

## Remaining delivery

The two bilingual Skill source candidates have passed manifest and dependency-declaration checks. They are deliberately kept outside published `sources/` and have no ZIP until their exact descriptor can be supplied. Main/OAuth-owner work still must complete native composition, private worker transport, lifecycle/vault integration and actual App verification. Offline Linux initialization and earlier component/provider checks do not establish that integrated App flow. Signed reviews, catalog publication and public install read-back follow demonstrated native support; no guessed version floor, borrowed mail client registration or token executor is introduced.
