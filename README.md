# Floe Skill Hub

Curated, source-pinned agent skills adapted for Floe Agent. This repository owns content, review records, package production and separately verified Linux execution dependencies. App UI, native services and release ownership stay in the Floe Agent repository.

Mac original Skills for the same-Mac bridge are **author input only and not a released channel**: [the macOS original contract](docs/MACOS-ORIGINAL-CONTRACT.md) defines the reserved `macos/catalog.json` feed and its preflight, but this repository has no `macos/` feed, signature, package or install offer. Linux dependency declarations remain a separate channel with their existing contract.

The curated selection contains 43 entries. The signed catalogs offer 39 optional skills on iOS and 36 on Android: 28 reviewed text guides, eight shared Linux RISC-V-qualified scripts, and three iOS-qualified scripts (Impeccable, Canvas Design and Algorithmic Art). Four builtin features stay App-provided. The two art skills require Floe 1.7.62 or later; existing 301/302 clients cannot install them. App build, acceptance and distribution remain separate from content publication. The [full-selection admission receipt](docs/provenance/catalog-signing-run-40581578679/README.md) records that milestone; current versions are in the [iOS catalog](catalog.json) and [Android catalog](android/catalog.json).

The [Linux-compatible guide batch](https://github.com/JiangNanGenius/floe-skill-hub/commit/9487d7b12bb377132e3fb06ff1c64a87dbb836ba) publishes 28 instruction-only skills at 1.0.1; 24 basic Android guides have no SDK content-version floor. This does not claim that older App builds include the Hub interface or that script execution has been qualified on ARM/x86.

Literature Review 1.0.0 is now offered with unchanged package bytes; its [qualification review receipt](docs/provenance/review-signing-run-40413407672/README.md) records the exact component scope and remaining native-PDF limitation.

The App reads the signed catalog and downloads skill/runtime artifacts directly from GitHub. The official website is a browser client of the same Hub data with a pre-rendered cache. Shared editorial, references and media live under [showcase/](showcase/CONTRACT.md); the website does not serve App store requests or proxy downloads.

The opt-in [automatic publication workflows](docs/AUTOMATIC-PUBLICATION.md) check external skills every six hours in GitHub Actions. Eligible updates retain local adaptations, receive a new immutable version and pass independent verification before signing and publication. Conflicts, license or permission changes, and runtime changes needing qualification preserve the existing published version with an actionable hold. Impeccable uses its separate daily engine-candidate workflow. No local daemon, model call or online Mac is required.

[Upstream tracking](docs/UPSTREAM-TRACKING.md) and [per-entry pins](docs/UPSTREAM-PIN-CONTRACT.md) let eligible skills advance independently. [Android portable guides](docs/ANDROID-PORTABLE-GUIDES.md) separate instruction-only content from architecture-specific execution; App installation and ARM/x86 runtime qualification remain distinct checks.

See [the implementation plan](docs/IMPLEMENTATION_PLAN.zh-CN.md) and [integration contract](docs/INTEGRATION-CONTRACT.md). Per-package upstream licenses and notices remain authoritative. Floe-authored repository tooling follows MPL-2.0 unless a file states otherwise; this does not relicense third-party skills, fonts or assets.

[Curation decisions](docs/CURATION.md) explain the first-release selection and its current evidence limits. Repository attention is recorded separately from per-skill quality, permissions and runtime qualification.
