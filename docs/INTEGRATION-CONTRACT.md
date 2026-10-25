# Skill Hub integration contract

Status: implementation input, not a published catalog. Changes require coordinator review.

## Repository and channels

- Remote: `JiangNanGenius/floe-skill-hub`; default branch `main`.
- iOS curated feed: `catalog.json` and `catalog.sig`; immutable archives `packages/{id}/{version}/{id}.zip`.
- Android channel: `android/catalog.json` and `android/catalog.sig`; archives `android/packages/{id}/{version}/{id}.zip`. No channel becomes active until real signed publication and client compatibility are verified.
- App's historical `JiangNanGenius/floe-agent/skill-hub` four-item feed remains available unchanged. Legacy compatibility views are produced separately; new candidates never silently enter the legacy four-item decoder.
- Candidate metadata lives in `catalog/skills.json`; deterministic packaging, validation and signing live in `scripts/`; package sources live in `sources/{id}/`.
- `engines/impeccable/` owns build recipe, patches, license/provenance and separately packaged riscv64 engine. It owns `sources/impeccable/` too. No other lane writes these paths.

## Trust, review and runtime

Retain the existing signed-feed envelope and Ed25519 trust model. Package hashes are authenticated through the signed catalog. Do not generate a production trust root or read signing secrets in a worker. An ephemeral test signature must be explicitly labeled fixture-only and must never be installed as a production trust root.

Reviewed catalog entries bind ID/version/content digest to reviewed tools, permissions and execution dependencies. The native installer checks the signed review and the user's existing effective grants. Previously granted rights do not require a repeated per-item install confirmation; absent, revoked or expanded rights require only the missing delta. Imported metadata and model parameters cannot self-approve. Existing explicit disabled/uninstalled choices and task ceilings remain authoritative.

Installation/store OS and execution OS/architecture are separate. Reuse the App owner's additive `runtime` and platform-channel semantics; unknown execution evidence is unproven. Use existing task Linux `exec.shell`, jobs and service lifecycle, never language aliases or a host interpreter.

## Native integration ownership

The iOS main thread owns A1 store and model `skill.search/read/install`, A2 controlled WebKit design capture/file bridge, A3 MCP creation/test wizard. Hub lanes produce fixed package/catalog samples, typed examples, build artifacts and qualification evidence. They do not patch native App files.

Impeccable H3 must promptly publish a versioned snapshot/facts JSON fixture, CLI invocation and coverage receipt before waiting for the full binary build. Snapshot capture uses fixed trusted native measurement, document/session/viewport binding and missing-facts iteration, not arbitrary evaluate or full CDP. Keep missing measurements distinct from a successful clean scan.

## Publication and status

Candidate packages can be built and checked locally without claiming publication. A release catalog includes only qualified entries and approved signed review records; the public preview index can describe pending candidates but never offer an unqualified install action. Website and App reference one immutable Hub commit/catalog digest.

Only the coordinator commits/pushes public Hub content after reviewing file scope and privacy. No worker publishes an App release, alters signing keys, deploys production website, switches DNS, or dispatches unrelated CI. Source/code readiness, host tests, riscv64 guest execution, App acceptance and live publication remain separate evidence.
