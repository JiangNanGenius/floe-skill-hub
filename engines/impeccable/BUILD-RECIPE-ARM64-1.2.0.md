# Build recipe: Floe Impeccable engine 1.2.0 (aarch64 candidate, private)

This is the **private modified copy** for the ARM64 transition candidate
`0.1.17+floe.1.2.0`. The Hub baseline recipe it derives from is reproduced
below unchanged for reference; the deltas for this candidate are:

* target `aarch64-unknown-linux-musl` (zig `aarch64-linux-musl`), replacing
  the guest riscv64 triple — the published 1.1.1 riscv64 bytes stay frozen;
* adapter crate version `1.2.0` (the single component-version constant), with
  the contract identity re-derived by `adapter/tools/sync_contract_identity.py`
  and `engine.targetTriple` set to `aarch64-unknown-linux-musl`;
* `adapter/src/error.rs` `runtime_execution_state()` gains the `aarch64-linux`
  branch so the shipped guest artifact self-describes correctly;
* `build/build_engine.py` `CROSS_TARGETS` gains the aarch64 musl entry; the
  riscv64 entries stay for the frozen lineage;
* the generated zig cc/cxx drivers filter rustc's `-Wl,--fix-cortex-a53-843419`
  (an old Cortex-A53 erratum workaround that zig cc does not support and that
  the Floe ARM64 guest, not an A53 core, does not need) before invoking zig;
* patches `0001`/`0002` are byte-identical to the reviewed 1.1.1 lineage.

## 1. Inputs (pinned, unchanged from the 1.1.1 lineage)

| Input | Value |
| --- | --- |
| Upstream | `pbakaus/impeccable` @ `4fc2f83e1c8710dba772bfd4523d0efab57737b6` (tree `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`) |
| `ENGINE_VERSION` | `0.1.17` (skill package `4.7.1`) |
| Adapter | `1.2.0` → staged as `crates/floe-impeccable` |
| Rust | `1.98.1` (rustc commit `48a229ceaefd4985c50990b14116b6d856af0985`), `RUSTUP_TOOLCHAIN=1.98.1`, target `aarch64-unknown-linux-musl` added via `rustup target add` |
| Cross toolchain | zig `0.17.0` from the retained scratch venv (`pip install ziglang`), C compiler and linker driver for `aarch64-linux-musl` |
| Patches | `patches/0001-floe-context-network-and-updater-trim.patch`, `patches/0002-floe-rule-pass-limiter.patch` — byte-identical to the 1.1.1 lineage |
| Lock | upstream pinned `Cargo.lock` at `4fc2f83e` (unchanged; the dependency graph has no target-conditional crates) |
| `SOURCE_DATE_EPOCH` | `1761436800` |
| Build host | macOS, Apple M5 Pro, `CARGO_NET_OFFLINE=1`, jobs 6, build tree + cargo target dir on an internal-SSD build cache (`<internal-ssd-cache>`) |

## 2. Build (placeholder paths)

```sh
python3 engines/impeccable/build/build_engine.py \
  --source <pinned-upstream-source> \
  --target aarch64-unknown-linux-musl --profile release \
  --cargo-target-dir <cargo-target-dir> \
  --build-dir <build-dir> \
  --log-dir <log-dir> \
  --zig-python <zig-venv-python> \
  --jobs 6 \
  --dist engines/impeccable/dist \
  --tests
```

Every actual native compile/test subprocess is serialized through the approved
shared wrapper: `python3 <approved-native-wrapper> --label hub-arm64-engine-<step> -- <command>`.
The exact private command lines, paths and results for the 2026-11-05 candidate
build are recorded in this lane's private FACTS.json and the build receipt.

## 3. Verification (static, honest)

* ELF64 little-endian, `e_type == ET_EXEC (2)`, `e_machine == 183 (EM_AARCH64)`;
* no `PT_INTERP` program header **and** no dynamic `DT_NEEDED` entries
  (a pure-static musl image has no `PT_DYNAMIC` with needed libraries);
* real file length and SHA-256 recorded in `dist/.../BUILD-RECEIPT.json`,
  `PROVENANCE.json`, `SHA256SUMS.txt` and this scope's `FACTS.json`;
* host adapter suite (`cargo test --target aarch64-apple-darwin`) is a host
  behavioral comparison only — it is **not** guest execution;
* no aarch64 user-mode runner is installed on this host, so the live
  `engine-probe` handshake is recorded as pending real-guest qualification
  (owned by Main). No emulated run is claimed as guest execution.

## 4. What this candidate is not

* not guest-qualified (no ARM64 Linux guest run in this lane);
* not App-accepted, not published, not signed;
* `minimumAppVersion` stays unknown/pending — the old `1.7.60`/`1.7.65`
  floors and any digest must not be reused for this component version.

---
