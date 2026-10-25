# Engine-observed goldens

Result documents printed by the real engine, one directory per execution
environment. These are **observed outputs**, not authored expectations: they
record what the pinned engine actually returned for each case in the
verification matrix, so a future engine (an upstream update, a toolchain change)
can be compared against them.

| Directory | Environment | Engine digest | Cases |
| --- | --- | --- | --- |
| `riscv64-docker/` | Docker `linux/riscv64`, alpine 3.20, qemu user-mode emulation, `uname` = Linux riscv64 6.8.0-117-generic | `af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b` | 21 |
| `host-arm64/` | local host, `aarch64-apple-darwin` dev build, behavioural comparison only | `079c102abecdf5157a9ab947cb0fbdff1d37b4d3db4aff422834d375d73fd86a` | 21 |

**Neither directory is the Floe Linux guest.** The guest is Debian 13 riscv64 on
TinyEMU with a 4.15 kernel, 256 MB default RAM and no JIT; running these cases
there is still pending and belongs to Main. Emulated execution proves the artifact
is a working static riscv64 ELF and that the contract behaves as specified on
riscv64 — it is not product-guest proof.

Each `MANIFEST.json` records, per case: the exit code, `status`, `verdict`,
`error.code`, the finding total and per-rule counts, the number of hit tests
asked, `coverage.uncoveredRequired`, and the file digest and size. It also
carries the runner identity and the verification summary (74/74 checks in both
environments, with 12/12 and 25/25 upstream oracle goldens byte-identical for
the offline `detect` verb).

## Normalization

Two volatile fields are normalized before export, and only these:

* `budget.elapsedMs` → `0` (wall clock is a measurement, not an expectation);
* `diagnostics.factsFiles[].source` → the basename (an absolute path would record
  the runner's filesystem layout).

Everything else is byte-for-byte what the engine printed.

## Cases

`positive-round1/2`, `overlay-round1/2` (the Needs → facts → re-run fixpoint,
ending in `tiny-text` and `text-occlusion`), `no-findings-round2` (0 findings →
`inconclusive`, never clean), `media-round2`, and the refusal set:
`snapshot-truncated`, `snapshot-bad-version`, `snapshot-column-mismatch`,
`identity-mismatch`, `identity-missing-binding`, `identity-redaction`,
`identity-model-trust`, `identity-fenced`, `facts-bits-mismatch`,
`facts-stale-capture`, `facts-other-tab`, `budget-bytes`, `budget-rounds`,
`timeout`, `no-identity`.

## Regenerate

```bash
python3 engines/impeccable/build/verify_engine_run.py --binary <engine> \
  --build-tree <exported-pinned-tree> --contract engines/impeccable/contract \
  --adapter-data engines/impeccable/adapter/tests/data --stage <stage> \
  --out <verify-report.json> [--docker-platform linux/riscv64] [--parity-limit N]

python3 engines/impeccable/build/export_expected.py --stage <stage> \
  --label <label> --out engines/impeccable/contract/expected/<label> \
  --runner "<runner description>" --evidence <verify-report.json>
```

`contract/tools/observe_and_complete.py` produces the intermediate round-trip
documents (observed Needs, reference facts, round-2 result) used to build the
checked-in facts files in `adapter/tests/data/`.
