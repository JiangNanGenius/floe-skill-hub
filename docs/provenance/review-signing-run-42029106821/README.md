# EDA and statistics ARM64 execution reviews

[GitHub Actions run](https://github.com/JiangNanGenius/floe-agent/actions/runs/42029106821) signed exactly two package-bound guest-execution reviews. Tooling `e7290d44f82cd327cbe0bc5afaefccb9855788e6`; unsigned data `f8a04c2fccf803f814081aedbec272c18e7e5d13`; source `93b50eba7a5a1eedbcea3b5ebcce88d91710362f`.

All output bytes, record signatures, package joins and receipt bindings were independently verified. EDA passed all 12 full golden checks and statistical analysis passed all 9 in a real Linux ARM64 guest hosted by App 1.7.74 (315) on iPad Simulator. The parent cross-skill suite was intentionally stopped after these complete results for a shared-resource handoff; the suite is incomplete.

These candidates are qualified only for the iOS channel, minimum App 1.7.74. No official installation/automatic preparation, Android/x86 or physical-device acceptance is claimed. A separate signed catalog is required before offers are published. Detailed method and timing: `docs/qualification/data-arm64-two-20261105.json`.
