# Skill Hub integration contract

Status: implementation input, not a published catalog. Changes require coordinator review.

## Repository and channels

- Remote: `JiangNanGenius/floe-skill-hub`; default branch `main`.
- iOS curated feed: `catalog.json` and `catalog.sig`; immutable archives `packages/{id}/{version}/{id}.zip`.
- Android channel: `android/catalog.json` and `android/catalog.sig`; archives `android/packages/{id}/{version}/{id}.zip`. No channel becomes active until real signed publication and client compatibility are verified.
- App's historical `JiangNanGenius/floe-agent/skill-hub` four-item feed remains available unchanged. Legacy compatibility views are produced separately; new candidates never silently enter the legacy four-item decoder.
- Candidate metadata lives in `catalog/skills.json`; deterministic packaging, validation and signing live in `scripts/`; package sources live in `sources/{id}/`.
- `engines/impeccable/` owns build recipe, patches, license/provenance and separately packaged riscv64 engine. It owns `sources/impeccable/` too. No other lane writes these paths.

The signed feed carries `sourceCommit`: the audited source revision X used to build its content. The client separately resolves `publicationCommit` Y, the immutable repository revision containing the feed, signatures, reviews and archives, and retrieves every artifact at Y for the whole operation. X is signed provenance and is not required to equal Y. Never require a feed to contain the hash of the Git commit that contains itself, and never re-resolve a mutable branch separately for each artifact. Search/install receipts keep these two identities distinct.

## GitHub-only App delivery

The App obtains catalog metadata, signatures, review records, skill archives and managed runtime artifacts directly from the trusted GitHub repository at the operation's immutable publication Y. The website is an independent static showcase, populated from GitHub at website build time. It is never an App API, package proxy, download CDN, telemetry collector or fallback source. If GitHub is unavailable, retain the existing verified local cache and show the applicable offline state; never silently route App requests through the website.

## Trust, review and runtime

Retain the existing signed-feed envelope and Ed25519 trust model. Package hashes are authenticated through the signed catalog. Do not generate a production trust root or read signing secrets in a worker. An ephemeral test signature must be explicitly labeled fixture-only and must never be installed as a production trust root.

Reviewed catalog entries bind ID/version/content digest to reviewed tools, permissions and execution dependencies. The native installer checks the signed review and the user's existing effective grants. Previously granted rights do not require a repeated per-item install confirmation; absent, revoked or expanded rights require only the missing delta. Imported metadata and model parameters cannot self-approve. Existing explicit disabled/uninstalled choices and task ceilings remain authoritative.

Installation/store OS and execution OS/architecture are separate. Reuse the App owner's additive `runtime` and platform-channel semantics; unknown execution evidence is unproven. Use existing task Linux `exec.shell`, jobs and service lifecycle, never language aliases or a host interpreter.

## Native integration ownership

The iOS main thread owns A1 store and model `skill.search/read/install`, A2 controlled WebKit design capture/file bridge, A3 MCP creation/test wizard. Hub lanes produce fixed package/catalog samples, typed examples, build artifacts and qualification evidence. They do not patch native App files.

Impeccable H3 must promptly publish a versioned snapshot/facts JSON fixture, CLI invocation and coverage receipt before waiting for the full binary build. Snapshot capture uses fixed trusted native measurement, document/session/viewport binding and missing-facts iteration, not arbitrary evaluate or full CDP. Keep missing measurements distinct from a successful clean scan.

## Publication and status

Candidate packages can be built and checked locally without claiming publication. A release catalog includes only qualified entries and approved signed review records; the public preview index can describe pending candidates but never offer an unqualified install action. Website and App reference the same immutable publication commit and catalog digest, with the audited source commit recorded separately. The read-only publication gate requires both channel feed/signature pairs and verifies their exact bytes with the configured public trust; an absent signature never passes as unpublished once production files exist.

Only the coordinator commits/pushes public Hub content after reviewing file scope and privacy. No worker publishes an App release, alters signing keys, deploys production website, switches DNS, or dispatches unrelated CI. Source/code readiness, host tests, riscv64 guest execution, App acceptance and live publication remain separate evidence.
