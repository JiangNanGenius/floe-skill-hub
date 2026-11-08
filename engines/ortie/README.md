# Ortie OAuth runtime candidate

This is a separately managed Linux component, not a native binary embedded in a Skill ZIP or the App. No install offer or frozen descriptor is issued until the App integration supplies its actual supported minimum version. The Google and Microsoft authorization Skills use separate native account configurations; Himalaya is a separate mail engine.

- Component: `ortie-oauth-engine`, candidate version `2.3.0+floe.1.0.0`.
- Source: [pimalaya/ortie](https://github.com/pimalaya/ortie/tree/5e500f1023432b6f2587b2b6cb2c6077a8ac4659), plus the retained `external-loopback-listener-ownership` patch.
- Build: locked release, default features disabled, `rustls-ring`; static `aarch64-unknown-linux-musl` ELF executable.
- Artifact: 3,691,576 bytes, SHA-256 `836adf744e9981a6c1920818e36a313cf8f0aa4b5c24e49e874f2c99def0b291`.
- Upstream license: MIT OR Apache-2.0. Third-party dependency licenses are retained individually. In particular, the unmodified MPL-2.0 `option-ext` 0.2.0 source archive is distributed under `notices/2.3.0+floe.1.0.0/sources/`, matching its Cargo.lock checksum. The dependency inventory covers 150 packages, including build dependencies; 141 are in the normal graph including Ortie itself.

`runtime-dependency/oauth-contract.v1.json` binds the complete canonical MCP handshake fixture and the sorted distribution manifest by exact size and SHA-256. The distribution manifest binds all 403 original notice, license, source and provenance files without including itself. A signed Skill's embedded descriptor will bind the contract; the catalog builder and standalone checker validate the entire same-snapshot chain. No arbitrary URLs, commands, environment overrides or additional executable components are accepted by this contract.

The MCP fixture comes from an actual offline ARM64 Linux startup. It contains complete input/output schemas for the five default tools, with protocol `2025-06-18` and server `ortie` 2.3.0. It is data for a private native adapter, not model instructions or public model tools. Native code owns system authorization and callback capture; the runtime owns PKCE and token exchange. The transport contract requires private stdio, external native loopback ownership, and revocation tools disabled. Token storage, cancellation and environment lifecycle remain owned by the App's existing services.

Offline startup is not full App, iPad, live-provider or environment-transition acceptance. The reviewed exact runtime bytes are reused without recompilation. Ordinary Skill ZIP executable rejection and Impeccable's separate capture contract are unchanged.
