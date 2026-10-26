# Floe Skill Hub

Curated, source-pinned agent skills adapted for Floe Agent. This repository owns content, review records, package production and separately verified Linux execution dependencies. App UI, native services and release ownership stay in the Floe Agent repository.

The curated selection contains 43 entries. The current signed catalog offers 31 optional skills on both iOS and Android: 28 reviewed text guides and three script skills with authenticated Linux RISC-V qualification evidence (SymPy, Citation Management and Webapp Testing). Four builtin features stay App-provided; eight other scripted entries remain unavailable pending qualification. An entry or a successful build is not proof of execution. See the [current signed receipt](docs/provenance/catalog-signing-run-40378895919/README.md) and the [first 30-entry publication](docs/provenance/catalog-signing-run-40372899273/README.md).

Literature Review 1.0.0 has newly authenticated component qualification; its [review receipt](docs/provenance/review-signing-run-40413407672/README.md) is separate from the next catalog publication.

The App reads the signed catalog and downloads skill/runtime artifacts directly from GitHub. The official website is a browser client of the same Hub data with a pre-rendered cache. Shared editorial, references and media live under [showcase/](showcase/CONTRACT.md); the website does not serve App store requests or proxy downloads.

See [the implementation plan](docs/IMPLEMENTATION_PLAN.zh-CN.md) and [integration contract](docs/INTEGRATION-CONTRACT.md). Per-package upstream licenses and notices remain authoritative. Floe-authored repository tooling follows MPL-2.0 unless a file states otherwise; this does not relicense third-party skills, fonts or assets.

[Curation decisions](docs/CURATION.md) explain the first-release selection and its current evidence limits. Repository attention is recorded separately from per-skill quality, permissions and runtime qualification.
