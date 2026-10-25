# engines/impeccable — the Floe Impeccable engine

This directory owns the build recipe, the tracked patches, the Floe adapter crate,
the frozen scan contract, the license/provenance record, the separately packaged
riscv64 engine and the updater workflow template. It also owns
`sources/impeccable/` (the derived skill source).

Upstream: `pbakaus/impeccable`, Apache-2.0, commit
`4fc2f83e1c8710dba772bfd4523d0efab57737b6` (tree
`1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`), `ENGINE_VERSION` `0.1.17`, skill
package `4.7.1`. Pin authority: hub `docs/UPSTREAM-PINS.json`.

## Layout

| Path | Content |
| --- | --- |
| `ENGINE-LOCK.json` | the one deliberate pin, the toolchain, the included and excluded upstream crates |
| `BUILD-RECIPE.md` | the exact reproducible build and verification steps |
| `build/build_engine.py` | pin verify → export → patch → stage adapter → build → verify → dist + receipt |
| `build/verify_engine_run.py` | runtime verification matrix (contract, fixpoint, refusals, upstream parity) |
| `build/verify_launcher.py` | launcher resolution, digest gate and no-download verification |
| `adapter/` | the Floe adapter crate (`floe-impeccable`): router, snapshot scan, identity/facts gates, coverage receipt, tests |
| `patches/` | tracked upstream patches, applied at build time and post-condition checked |
| `contract/` | the frozen v1 snapshot/facts contract: spec, schemas, fixtures, producer guidance, tools |
| `workflows/` | the updater/build workflow **template** (H1 owns the repository's root workflows) |
| `dist/<engineId>/<triple>/` | the versioned engine artifact with digest, provenance, receipt and licenses |
| `evidence/` | exported verification evidence (small JSON), including what is still pending |

## What the engine is

`floe-impeccable` links the pinned upstream rule core (`impeccable-core` over
`impeccable-foundation`), the static source/markup engines
(`impeccable-detect`, `impeccable-html`), the offline context verbs
(`impeccable-context`) and `impeccable-common`, behind a Floe router that adds the
file-based `snapshot-scan` verb. It is **not** the upstream CLI and does not claim
to be: the Chromium/CDP URL engine, the live rewrite server, the editor hooks,
the comp-fidelity capture verbs and the upstream skill installer/updater are not
linked at all, and each refused verb says which Floe owner holds it.

After `patches/0001`, the dependency graph contains no TLS or crypto stack — the
build fails if `ring`, `rustls`, `aws-lc-rs`, `rustls-native-certs` or
`webpki-roots` is reachable from the adapter crate — so the contract's
`transport.network: none` is a structural property, not a convention.

## States (kept apart on purpose)

| State | Meaning | Current |
| --- | --- | --- |
| source-ready | adapter, patches, contract and recipe are tracked | done |
| host-tested | built for the host and the adapter suite passes | done: 38 tests |
| artifact-built | a real riscv64 static ELF exists with digest and provenance | done |
| riscv64-executed | the artifact ran on riscv64 and passed the behaviour matrix | done **under Docker/qemu user-mode emulation**, kernel 6.8.0-117-generic |
| guest-qualified | the artifact ran in the actual Floe Linux guest (Debian 13 riscv64 on TinyEMU/4.15) | **pending** — needs the dedicated qualification path, owned by Main |
| app-accepted | the native capture/file bridge plus a real page-scan round trip in the App | **pending** — A2 owns the producer, Main owns App acceptance |
| published | in a signed catalog release | not authorized here |

Emulated execution proves the binary is a working static riscv64 ELF and that the
contract behaves as specified on riscv64. It does **not** prove the TinyEMU guest
path: the guest kernel is 4.15, the interpreter has no JIT, and default guest RAM
is 256 MB, so latency and memory headroom are unmeasured.

## Reproduce

```bash
python3 engines/impeccable/build/build_engine.py \
  --source <clone-at-the-pinned-commit> \
  --target riscv64gc-unknown-linux-musl --profile release \
  --cargo-target-dir <internal-ssd-cache> --build-dir <scratch>/build-riscv64 \
  --log-dir <scratch>/logs --zig-python <scratch>/tools/venv/bin/python \
  --jobs 6 --dist engines/impeccable/dist \
  [--wrapper <shared serialized build wrapper>]
```

Details, expected digests and the verification commands are in
[`BUILD-RECIPE.md`](BUILD-RECIPE.md).
