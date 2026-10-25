# Floe Skill Hub contributor instructions

- Preserve upstream commit pins, licenses, notices and published bytes. Do not relabel third-party content with this repository's tooling license.
- App UI, native browser/MCP changes, App builds and distribution belong to the iOS main owner. Do not edit the parent App checkout.
- Only the coordinator commits/pushes or changes shared integration contracts while parallel lanes are active. Lanes own their explicitly assigned paths. Do not create worktrees or replace another lane's files.
- Skill ZIPs contain instructions, audited source scripts and resources, never native binaries. Linux engine dependencies are separate and digest-bound. No host interpreter fallback or model-authored arbitrary WebKit evaluation.
- Candidate/reviewed/packaged/qualified/published are different states. Do not mark execution verified from source inspection, host execution or synthetic fixtures.
- Private keys, credentials, operational addresses, private checkout paths and raw private evidence never enter this repository. Tests use clearly isolated ephemeral signing keys only.
- Keep downloaded upstream source and regenerable build output outside tracked source. Do not vendor the full Impeccable source tree. Export necessary artifacts/evidence, then clean task-owned disposable output.
- Follow docs/INTEGRATION-CONTRACT.md. Contact the coordinator on an interface conflict; do not silently change a shared wire shape.
