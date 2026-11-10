# Floe Skill Hub

Curated, source-pinned agent skills adapted for Floe Agent. This repository owns content, review records, package production and separately verified Linux execution dependencies. App UI, native services and release ownership stay in the Floe Agent repository.

Mac original Skills for the same-Mac bridge use a **separate channel that is not yet published**. The [frozen author contract](docs/MACOS-ORIGINAL-CONTRACT.md), [candidate producer](docs/MACOS-ORIGINAL-PACKAGING.md) and [data-only candidate signing transport](docs/MACOS-ORIGINAL-SIGNING.md) prepare source-pinned originals for client verification. Candidate artifacts are not live install offers; the default branch has no production `macos/catalog.json` feed or signature. Linux dependency declarations retain their separate contract.

The registry contains 86 selections. The signed standard complete catalogs offer **81 optional skills on iOS and 71 on Android**; four builtin features stay App-provided. The [iOS large-source catalog](catalog-large-source-v1.json) adds **Taste Skill 2.5.1**, bringing that complete view to 82 offers. Its full 1,638-file ARM64 Linux kit requires a compatible iOS client; the signed entry records the minimum version. Android's large-source view retains its existing 71 offers until its own consumer is ready. [Package profiles](docs/PACKAGE-PROFILES.md), the [qualification scope](docs/qualification/taste-skill-arm64-20261110.md) and the [original publication receipt](docs/qualification/taste-skill-publication-20261110.json) distinguish signed Hub availability, Linux component execution and App distribution. Existing standard offers and historical packages are unchanged. The standard views remain the [iOS catalog](catalog-full.json) and [Android catalog](android/catalog-full.json).

The [Linux-compatible guide batch](https://github.com/JiangNanGenius/floe-skill-hub/commit/9487d7b12bb377132e3fb06ff1c64a87dbb836ba) publishes 28 instruction-only skills at 1.0.1; 24 basic Android guides have no SDK content-version floor. Instruction-only portability is separate from ARM/x86 script execution qualification.

Literature Review 1.0.0 is now offered with unchanged package bytes; its [qualification review receipt](docs/provenance/review-signing-run-40413407672/README.md) records the exact component scope and remaining native-PDF limitation.

The App reads the signed catalog and downloads skill/runtime artifacts directly from GitHub. The official website is a browser client of the same Hub data with a pre-rendered cache. Shared editorial, references and media live under [showcase/](showcase/CONTRACT.md); the website does not serve App store requests or proxy downloads.

The opt-in [automatic publication workflows](docs/AUTOMATIC-PUBLICATION.md) check external skills every six hours in GitHub Actions. Eligible updates retain local adaptations, receive a new immutable version and pass independent verification before signing and publication. Conflicts, license or permission changes, and runtime changes needing qualification preserve the existing published version with an actionable hold. Impeccable uses its separate daily engine-candidate workflow. No local daemon, model call or online Mac is required.

[Upstream tracking](docs/UPSTREAM-TRACKING.md) and [per-entry pins](docs/UPSTREAM-PIN-CONTRACT.md) let eligible skills advance independently. [Android portable guides](docs/ANDROID-PORTABLE-GUIDES.md) separate instruction-only content from architecture-specific execution; App installation and ARM/x86 runtime qualification remain distinct checks.

See [the implementation plan](docs/IMPLEMENTATION_PLAN.zh-CN.md) and [integration contract](docs/INTEGRATION-CONTRACT.md). Per-package upstream licenses and notices remain authoritative. Floe-authored repository tooling follows MPL-2.0 unless a file states otherwise; this does not relicense third-party skills, fonts or assets.

[Curation decisions](docs/CURATION.md) explain the first-release selection and its current evidence limits. Repository attention is recorded separately from per-skill quality, permissions and runtime qualification.
