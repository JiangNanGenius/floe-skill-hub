# Build recipe: Floe Impeccable engine 1.1.1

Public-relative reproduction record for the frozen candidate artifact in
`dist/impeccable-0.1.17+floe.1.1.1/`. The binary there was built **once** by the
contract-fix lane on 2026-10-27; this recipe documents exactly how it was
produced and how to verify it. It does not claim two-build byte equality — the
byte-stability proof below is the toolchain/flag argument plus the recorded
1.0.0 lineage evidence, not a second observed build of these bytes.

## 1. Inputs (pinned, unchanged from the 1.0.0 lineage)

| Input | Value |
| --- | --- |
| Upstream | `pbakaus/impeccable` @ `4fc2f83e1c8710dba772bfd4523d0efab57737b6` (tree `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`) |
| `ENGINE_VERSION` | `0.1.17` (skill package `4.7.1`) |
| Pin authority | hub `docs/UPSTREAM-PINS.json`, `reviewBaselineDate 2026-10-26` |
| Rust | `1.98.1` (rustc commit `48a229ceaefd4985c50990b14116b6d856af0985`), `RUSTUP_TOOLCHAIN=1.98.1` |
| Target | `riscv64gc-unknown-linux-musl` (guest), `aarch64-apple-darwin` (host comparison) |
| Cross toolchain | zig `0.17.0` from a scratch venv (`pip install ziglang`), C compiler and linker driver for `riscv64-linux-musl` |
| Patches | `patches/0001-floe-context-network-and-updater-trim.patch` (`77b9d37c…`), `patches/0002-floe-rule-pass-limiter.patch` (`15fd69f3…`) — byte-identical to the 1.1.0 lineage |
| Adapter | `adapter/` → staged as `crates/floe-impeccable` (crate version `1.1.1`) |
| Contract | `contract/` → staged into the crate `data/` and embedded with `include_str!` |
| Lock | upstream pinned `Cargo.lock` (`f898885f…` at `4fc2f83e`); post-stage lock `0e51e4f7…` adds only `floe-impeccable 1.1.1` |
| `SOURCE_DATE_EPOCH` | `1761436800` |
| Build host | macOS 27.0.1, Apple M5 Pro, Python 3.9.6, 2 cargo jobs, `CARGO_NET_OFFLINE=1` |

The full upstream tree is never committed. `build/build_engine.py` exports it
with `git archive <commit>` into task scratch and starts from the pin.

## 2. What changed from 1.0.0 → 1.1.1 (source level)

1. **1.0.0 → 1.1.0 (rule-pass limiter)**: adapter scan-path improvements with
   typed cooperative trips and element/occlusion memos; new
   `tests/rule_pass_limiter.rs`, regression fixtures and
   `tools/make_regression_fixtures.py`; upstream patch `0002`. Component
   `0.1.17+floe.1.1.0`.
2. **1.1.0 → 1.1.1 (contract identity repair)**: the adapter crate `Cargo.toml`
   version is now the single component-version constant. The contract's three
   identity strings (`engine.floeAdapterVersion`, `engine.engineId`,
   `verbs[engine-probe].stdout`) are derived from it by
   `adapter/tools/sync_contract_identity.py`, and `build_engine.py` refuses to
   compile while any drift exists (`verify_contract_identity`), then refuses to
   export while a runnable probe disagrees. New consistency test
   `the_contract_engine_probe_example_is_the_live_probe`. Protocol v1, schema,
   caps, budgets, rules and `--no-timeout` semantics: byte-identical logic.

## 3. Build (placeholder paths)

```sh
# one-off toolchain setup (host)
rustup target add riscv64gc-unknown-linux-musl riscv64gc-unknown-linux-gnu
python3 -m venv <scratch>/tools/venv && <scratch>/tools/venv/bin/pip install ziglang

# guest artifact
python3 engines/impeccable/build/build_engine.py \
  --source <scratch>/upstream \
  --target riscv64gc-unknown-linux-musl --profile release \
  --cargo-target-dir <build-cache>/riscv64 \
  --build-dir <scratch>/build-riscv64 \
  --log-dir <scratch>/logs \
  --zig-python <scratch>/tools/venv/bin/python \
  --jobs 2 \
  --dist engines/impeccable/dist
```

The builder fails closed on: pin/tree mismatch, unclean checkout, patch
post-condition failure, adapter/contract digest mismatch, TLS/crypto crates in
the graph, and (1.1.1) any contract identity drift before compiling. Run
`adapter/tools/sync_contract_identity.py` first to check or derive the three
identity fields.

## 4. Observed results (this artifact, one build)

| Item | Value |
| --- | --- |
| Guest artifact | `dist/impeccable-0.1.17+floe.1.1.1/riscv64gc-unknown-linux-musl/floe-impeccable` |
| Digest | `774333d30d6e54604342182e49853851c7e0ebfa9e92fc4216f4a68872d00a1a` |
| Size | 5,594,368 bytes |
| ELF | ELF64 LSB, machine RISC-V (243), type EXEC, statically linked, no `PT_INTERP`, stripped, e_flags=5 |
| Crates in graph | 130 (no TLS/crypto) |
| Cargo time | 79.03 s cold (130 crates, 2 jobs, exit 0, 2 warnings) |
| Host adapter suite | 49/49 passed (48 prior + 1 new consistency test) |
| qemu-user recheck | 32/32 PASS (`--version`, live probe == contract example, contract digest, typed timeout controls, `--no-timeout` media round) |

## 5. Verification

```sh
# digest + static identity
shasum -a 256 engines/impeccable/dist/impeccable-0.1.17+floe.1.1.1/riscv64gc-unknown-linux-musl/floe-impeccable

# descriptor + artifact strict gate (pure checks, no execution)
python3 - <<'PY'
import sys, pathlib, json
sys.path.insert(0, "scripts")
import runtime_dependency as rt
root = pathlib.Path(".")
d = rt.parse_descriptor((root/"engines/impeccable/runtime-dependency/descriptor.v1.json").read_bytes())
rt.load_artifact(root, d)
print("descriptor+artifact OK")
PY

# behaviour matrix (riscv64 runner required; qemu-user or the Floe guest)
python3 engines/impeccable/build/verify_engine_run.py \
  --binary engines/impeccable/dist/impeccable-0.1.17+floe.1.1.1/riscv64gc-unknown-linux-musl/floe-impeccable \
  --build-tree <scratch>/build-riscv64 --contract engines/impeccable/contract \
  --adapter-data engines/impeccable/adapter/tests/data \
  --stage <scratch>/verify-stage-riscv64 \
  --out engines/impeccable/evidence/verify-riscv64-docker.json \
  --docker-platform linux/riscv64 --parity-limit 12
```

## 6. Reproducibility limits (honest)

* Byte-stable rebuild assumes the same toolchain `1.98.1`, zig `0.17.0`,
  offline registry cache and path remapping (`/build /target /registry /rustup
  /home`); panic metadata embeds remapped paths only. The recorded 1.0.0
  lineage observed byte-identical cold rebuilds under the same flags; the 1.1.1
  bytes are a single observed build and are treated as frozen.
* `cargo`'s `include_str!` fingerprint is mtime-based: a file swapped into a
  staged `data/` contract must change mtime (or be touched) or it is silently
  not rebuilt.
* qemu-user verification is not the Floe TinyEMU guest proof; guest execution
  remains a separate qualification stage.
