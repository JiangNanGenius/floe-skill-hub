# Skill Hub integration contract

Status: integration input; live publication is established by signed feed readback, not this document. The macOS original channel described below is author input only and is not yet published. Changes require coordinator review.

## Repository and channels

- Remote: `JiangNanGenius/floe-skill-hub`; default branch `main`.
- iOS legacy feed: `catalog.json` and `catalog.sig`; immutable archives `packages/{id}/{version}/{id}.zip`.
- Android legacy view: `android/catalog.json` and `android/catalog.sig`; archives `android/packages/{id}/{version}/{id}.zip`. No channel becomes active until real signed publication and client compatibility are verified.
- Complete curated views: `catalog-full.json` / `catalog-full.sig` and `android/catalog-full.json` / `android/catalog-full.sig`; see [the expansion contract](CATALOG-EXPANSION.md). Original43 planning identities stay in the legacy projection; new rows append only in the complete view. All current signing/publication runs bind the four pairs at one Y. Historical legacy-only publications remain valid; partial complete pairs never do.
- Reserved macOS original channel: `macos/catalog.json` and `macos/catalog.json.sig`, `schemaVersion: 1`, `channel: "macos-original"`; see [the source-pinned author contract](MACOS-ORIGINAL-CONTRACT.md). It has a separate file manifest and installation lifecycle, reuses the existing signing trust, and does not change the curated feeds or require Linux review/archive/qualification records. Do not create or publish this feed until the release owner establishes the capable client identity and authorizes publication.
- App's historical `JiangNanGenius/floe-agent/skill-hub` four-item feed remains available unchanged. Legacy compatibility views are produced separately; new candidates never silently enter the legacy four-item decoder.
- Candidate metadata lives in `catalog/skills.json`; deterministic packaging, validation and signing live in `scripts/`; package sources live in `sources/{id}/`.
- `engines/impeccable/` owns build recipe, patches, license/provenance and separately packaged riscv64 engine. It owns `sources/impeccable/` too. No other lane writes these paths.

The curated iOS/Android signed feed carries `sourceCommit`: the audited source revision X used to build its content. The client separately resolves `publicationCommit` Y, the immutable repository revision containing the feed, signatures, reviews and archives, and retrieves every artifact at Y for the whole operation. X is signed provenance and is not required to equal Y. Never require a feed to contain the hash of the Git commit that contains itself, and never re-resolve a mutable branch separately for each artifact. Search/install receipts keep these two identities distinct.

## GitHub-only App delivery

The App obtains catalog metadata, signatures, review records, skill archives and managed runtime artifacts directly from the trusted GitHub repository at the operation's immutable publication Y. The website is an independent browser client of the same GitHub data, with a pre-rendered cache for its first screen and SEO. Editorial, references and media are authored only in this Hub under `showcase/`; the browser can refresh them from the same pinned Y without rebuilding the website. See [the presentation contract](../showcase/CONTRACT.md). The website is never an App API, package proxy, download CDN, telemetry collector or fallback source. If GitHub is unavailable, retain the existing verified local cache and show the applicable offline state; never silently route App requests through the website.

## Trust, review and runtime

Retain the existing signed-feed envelope and Ed25519 trust model. Package hashes are authenticated through the signed catalog. Do not generate a production trust root or read signing secrets in a worker. An ephemeral test signature must be explicitly labeled fixture-only and must never be installed as a production trust root.

Reviewed curated iOS/Android catalog entries bind ID/version/content digest to reviewed tools, permissions and execution dependencies. The native installer checks the signed review and the user's existing effective grants. Previously granted rights do not require a repeated per-item install confirmation; absent, revoked or expanded rights require only the missing delta. Imported metadata and model parameters cannot self-approve. Existing explicit disabled/uninstalled choices and task ceilings remain authoritative.

Installation/store OS and execution OS/architecture are separate. The curated channels reuse the App owner's additive `runtime` and platform-channel semantics; unknown execution evidence is unproven. Their execution uses the resolved task Linux `exec.shell`, jobs and service lifecycle, never language aliases or an implicit host fallback.

The separate same-Mac original route uses the existing Mac bridge and the task's actual macOS environment with its normal permissions. Keep upstream files byte-for-byte at the declared commit, preserve modes and license provenance, and pin running/checkpointed tasks to their original installed version. Original and adapted variants retain separate files, enable state, installation receipts and dependency ownership. Do not turn Linux `references/dependencies.json` into a Mac install plan or apply Debian/riscv64 commands to the host. Source authenticity and safe installation checks do not assert Mac execution or RISC-V qualification.

## Native integration ownership

The iOS main thread owns A1 store and model `skill.search/read/install`, A2 controlled WebKit design capture/file bridge, A3 MCP creation/test wizard. Hub lanes produce fixed package/catalog samples, typed examples, build artifacts and qualification evidence. They do not patch native App files.

Impeccable H3 must promptly publish a versioned snapshot/facts JSON fixture, CLI invocation and coverage receipt before waiting for the full binary build. Snapshot capture uses fixed trusted native measurement, document/session/viewport binding and missing-facts iteration, not arbitrary evaluate or full CDP. Keep missing measurements distinct from a successful clean scan.

## Publication and status

Candidate packages can be built and checked locally without claiming publication. A curated iOS/Android release catalog includes only qualified entries and approved signed review records; the public preview index can describe pending candidates but never offer an unqualified install action. Website and App reference the same immutable publication commit and catalog digest, with the audited source commit recorded separately. The read-only publication gate requires both channel feed/signature pairs and verifies their exact bytes with the configured public trust; an absent signature never passes as unpublished once production files exist.

Only the coordinator commits/pushes public Hub content after reviewing file scope and privacy. No worker publishes an App release, alters signing keys, deploys production website, switches DNS, or dispatches unrelated CI. Source/code readiness, host tests, riscv64 guest execution, App acceptance and live publication remain separate evidence.

For the future Mac original feed, use the frozen manifest/digest and upstream-byte checks in the Mac author contract, plus historical `(id, version)` immutability and the existing feed signature trust. A changed commit, file or mode requires a new version. `minimumAppVersion` comes from the release owner's verified capable App identity; candidate 1.7.62 (303) is not proof of availability. No Mac feed, signature or install offer is introduced by this documentation alignment. The existing automatic publication pipeline continues to serve the curated channels; this alignment does not enable a Mac producer or signing workflow.
