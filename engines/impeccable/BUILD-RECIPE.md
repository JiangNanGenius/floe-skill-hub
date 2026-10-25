# Build recipe: Floe Impeccable engine

Reproducible from the pinned upstream commit. Everything below was actually run
for the artifact in `dist/`; the recorded digests and timings are from those runs,
not estimates.

## 1. Inputs

| Input | Value |
| --- | --- |
| Upstream | `pbakaus/impeccable` @ `4fc2f83e1c8710dba772bfd4523d0efab57737b6` (tree `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`) |
| `ENGINE_VERSION` | `0.1.17` (skill package `4.7.1`) |
| Pin authority | hub `docs/UPSTREAM-PINS.json`, `reviewBaselineDate 2026-10-26` |
| Rust | `1.98.1` (rustc commit `48a229ceaefd4985c50990b14116b6d856af0985`), pinned with `RUSTUP_TOOLCHAIN=1.98.1` so `rust-toolchain.toml` cannot pull another channel |
| Targets | `riscv64gc-unknown-linux-musl` (guest), `aarch64-apple-darwin` (host comparison) |
| Cross toolchain | zig `0.17.0` from a scratch venv (`pip install ziglang`), used as the C compiler and linker driver for `riscv64-linux-musl` |
| Patches | `patches/0001-floe-context-network-and-updater-trim.patch` |
| Adapter | `adapter/` → staged as `crates/floe-impeccable` |
| Contract | `contract/` → staged into the crate's `data/` and embedded with `include_str!` |
| Build host | macOS 27.0.1, Apple M5 Pro (15 cores, 24 GB), Python 3.9.6 |

The full upstream tree is never committed. `build_engine.py` exports it with
`git archive <commit>` into task scratch, so the build starts from the pin and
nothing else.

## 2. Commands

```bash
# one-off toolchain setup (host)
rustup target add riscv64gc-unknown-linux-musl riscv64gc-unknown-linux-gnu
python3 -m venv <scratch>/tools/venv && <scratch>/tools/venv/bin/pip install ziglang

# the guest artifact (heavy compile: run it through the shared serialized build
# wrapper, 6 jobs, cargo target dir on the internal SSD)
python3 engines/impeccable/build/build_engine.py \
  --source <scratch>/upstream \
  --target riscv64gc-unknown-linux-musl --profile release \
  --cargo-target-dir <build-cache>/riscv64 \
  --build-dir <scratch>/build-riscv64 \
  --log-dir <scratch>/logs \
  --zig-python <scratch>/tools/venv/bin/python \
  --jobs 6 \
  --wrapper <shared-build-wrapper> \
  --dist engines/impeccable/dist

# the host comparison build plus the adapter suite
python3 engines/impeccable/build/build_engine.py \
  --source <scratch>/upstream --target aarch64-apple-darwin --profile dev \
  --cargo-target-dir <build-cache>/host \
  --build-dir <scratch>/build-host --log-dir <scratch>/logs --tests \
  --wrapper <shared-build-wrapper> --jobs 6
```

What the builder enforces, failing closed:

1. `git rev-parse HEAD` and `HEAD^{tree}` equal the lock, `ENGINE_VERSION`
   matches, and the checkout is clean;
2. `git archive` export (no git metadata, no working-tree drift);
3. patches applied with `patch -p1 --forward` after a `--dry-run`, then
   **post-conditions checked on the patched bytes** (`git apply` is not used: it
   silently skips entries inside an unrelated work tree and exits 0);
4. the adapter and the frozen contract staged, with a digest comparison per file
   so the binary cannot embed a contract that differs from the committed one;
5. a dependency audit: `cargo tree --invert` must not reach `ring`, `rustls`,
   `aws-lc-rs`, `rustls-native-certs` or `webpki-roots`;
6. the build itself, with `CARGO_NET_OFFLINE=1`, a fixed `SOURCE_DATE_EPOCH`
   (`1761436800`) and the release profile inherited from the upstream workspace
   (`opt-level 3`, `lto fat`, `codegen-units 1`, `strip`, `panic abort`);
7. ELF verification: class, machine, type, static linkage (no `PT_INTERP`),
   size and digest.

Linker and privacy flags for the musl target:

```
CARGO_TARGET_RISCV64GC_UNKNOWN_LINUX_MUSL_LINKER=<zig cc wrapper>
CARGO_TARGET_RISCV64GC_UNKNOWN_LINUX_MUSL_RUSTFLAGS="-C target-feature=+crt-static \
  -C link-self-contained=no \
  --remap-path-prefix=<build-tree>=/build --remap-path-prefix=<cargo-target-dir>=/target \
  --remap-path-prefix=<home>/.cargo/registry=/registry --remap-path-prefix=<home>/.rustup=/rustup \
  --remap-path-prefix=<home>=/home"
CC_/CXX_/AR_RISCV64GC_UNKNOWN_LINUX_MUSL=<zig cc / c++ / ar wrappers>
```

Two consequences worth knowing:

* `--remap-path-prefix` keeps private absolute paths out of the shipped binary
  (Rust embeds source locations in panic metadata, and the cargo registry lives
  under the builder's home). The artifact now contains only `/build`, `/target`,
  `/registry`, `/rustup` and `/home` prefixes; `strings` finds no checkout path.
* `RUSTFLAGS` is whitespace-split, so a remap source containing a space cannot be
  expressed. **Keep build trees on a space-free path** (the internal build cache);
  a path that cannot be remapped is skipped and recorded in the receipt as
  `pathRemappingSkipped`, which is a reason to move the build tree, not to ship.

`link-self-contained=no` is required: Rust's own `crt1.o` plus zig's produces
`duplicate symbol: _start`. Letting one side own startup yields a single fully
static musl image.

## 3. Observed results

| Item | Value |
| --- | --- |
| Guest artifact | `dist/impeccable-0.1.17+floe.1.0.0/riscv64gc-unknown-linux-musl/floe-impeccable` |
| Digest | `af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b` |
| Size | 5,579,704 bytes |
| ELF | ELF64 LSB, machine RISC-V, type EXEC, statically linked, no `PT_INTERP`, stripped |
| Crates in graph | 130 (no TLS/crypto) |
| Build time | 48.3 s cold (all 130 crates, 6 jobs, exit 0, 2 warnings); 46.2 s for the primary build with a partly warm cache |
| Host comparison build | `aarch64-apple-darwin` dev, 32,791,120 bytes, `079c102abecdf5157a9ab947cb0fbdff1d37b4d3db4aff422834d375d73fd86a` |
| Host adapter suite | 38 tests, 0 failed |
| Host verification | 74/74 checks, 25/25 upstream oracle goldens byte-identical |
| riscv64 verification | 74/74 checks, 12/12 upstream oracle goldens byte-identical, `uname` = Linux riscv64 |
| riscv64 scan timing | ~110–130 ms per 18 KB snapshot scan, stable over 3 repeats (Docker qemu user-mode) |
| Launcher verification | 25/25 checks, including real riscv64 execution through the launcher |

The riscv64 runs are **Docker/qemu user-mode emulation on kernel 6.8.0-117-generic**,
not the Floe guest (Debian 13 riscv64 on TinyEMU with a 4.15 kernel, 256 MB
default RAM, no JIT). Emulated timing is not a guest latency prediction.

## 4. Verification commands

```bash
# behaviour matrix on riscv64 (Docker with a riscv64 binfmt handler installed)
python3 engines/impeccable/build/verify_engine_run.py \
  --binary dist/impeccable-0.1.17+floe.1.0.0/riscv64gc-unknown-linux-musl/floe-impeccable \
  --build-tree <scratch>/build-riscv64 \
  --contract engines/impeccable/contract \
  --adapter-data engines/impeccable/adapter/tests/data \
  --stage <scratch>/verify-stage-riscv64 \
  --out engines/impeccable/evidence/verify-riscv64-docker.json \
  --docker-platform linux/riscv64 --parity-limit 12

# the same matrix on the host build
python3 engines/impeccable/build/verify_engine_run.py ... --out engines/impeccable/evidence/verify-host.json

# launcher resolution, digest gate, no-download guarantee
python3 engines/impeccable/build/verify_launcher.py \
  --launcher ../../sources/impeccable/scripts/floe-impeccable \
  --host-binary <host binary> --riscv64-binary <guest artifact> \
  --contract engines/impeccable/contract \
  --stage <scratch>/verify-launcher \
  --out engines/impeccable/evidence/verify-launcher.json

# contract coherence (61 checks) and the Needs -> facts -> re-run fixpoint
python3 engines/impeccable/contract/tools/validate_fixtures.py \
  --contract engines/impeccable/contract --upstream <pinned-source-dir>
python3 engines/impeccable/contract/tools/observe_and_complete.py \
  --engine <binary> --contract engines/impeccable/contract --out <expected-dir> \
  --case positive=fixtures/snapshot-positive.v1.json,fixtures/identity-positive.v1.json \
  --case overlay=fixtures/snapshot-needs-hit-tests.v1.json,fixtures/identity-needs.v1.json
```

Docker note: this host's Docker Desktop has no shared-path mapping for the
checkout, so `verify_engine_run.py --docker-platform` uses
`docker create` + `docker cp` + `docker start -a` instead of a bind mount (a
`-v` bind silently presents an empty directory there). A riscv64 binfmt handler
must be registered once (`docker run --privileged --rm tonistiigi/binfmt
--install riscv64`); that changes the Docker VM only, never a Floe guest.

## 5. Reproducibility

Rebuild from the same pin with the same toolchain and compare the digest:

```bash
python3 engines/impeccable/build/build_engine.py ... \
  --cargo-target-dir <a-fresh-cache-dir> --build-dir <the-same-build-dir-path>
shasum -a 256 <fresh>/riscv64gc-unknown-linux-musl/release/floe-impeccable
```

With the remap flags above the build-tree path no longer reaches the artifact, so
a rebuild from the same pin, toolchain and flags on another machine should match.
What was actually observed: a cold rebuild in a fresh cargo target directory
produced a **byte-identical** artifact (`af8795bf…`, 5,579,704 bytes). The
recorded runs are in `evidence/reproducibility.json`.

## 6. Cleanup

Regenerable output lives outside the repository: the pinned clone, the exported
build tree, the cargo target directories and the verification stages. Delete them
after the artifact, receipt, provenance, digests and evidence are exported; the
recipe above recreates all of them from the pin. What must be kept: `dist/`
(artifact + receipt + provenance + licenses), `evidence/`, the patches, the
adapter source and the contract.
