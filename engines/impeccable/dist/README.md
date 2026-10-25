# dist — versioned engine artifacts

One directory per engine identity and target triple:

```
dist/<engineId>/<triple>/
  floe-impeccable                 the engine binary
  SHA256SUMS.txt                  digests of every file in this directory
  PROVENANCE.json                 upstream pin, patches, adapter and contract digests, toolchain
  BUILD-RECEIPT.json              the build and verification record for this artifact
  LICENSE-impeccable-apache-2.0   upstream license, verbatim
  NOTICE-impeccable.md            upstream notices, verbatim
  LICENSE-adapter                 MPL-2.0 for the Floe-authored adapter
```

Current: `impeccable-0.1.17+floe.1.0.0/riscv64gc-unknown-linux-musl`, SHA-256
`af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b`, 5,579,704
bytes, static ELF64 RISC-V EXEC.

## State of this artifact

**Built and executed on riscv64 under emulation; not guest-qualified and not
published.** The engine ran the full behaviour matrix on `docker
--platform linux/riscv64` (qemu user-mode, kernel 6.8.0-117-generic): 74/74
checks with 12/12 upstream oracle goldens byte-identical, plus 25/25 launcher
checks including a real scan through the launcher. It has **not** run in the Floe
Linux guest (Debian 13 riscv64 on TinyEMU, kernel 4.15, 256 MB default RAM, no
JIT), which is the qualification that matters and is owned by Main. Emulated or
host execution is not product-guest proof, and a static ABI check is not runtime
proof.

## Handling rules

* This is a separate, digest-bound Linux execution dependency. It never goes into
  a skill ZIP, and a skill ZIP never contains a native binary.
* Installation, update and rollback are Hub-owned and go through the signed
  catalog and the reviewed update PR flow. The engine and its launcher have no
  download path.
* Verify the digest before staging it into a task environment, and keep the
  receipt next to the binary: `SHA256SUMS.txt` is what the launcher's optional
  `FLOE_IMPECCABLE_VERIFY_DIGEST=1` gate reads.
* Keep old versions until a replacement is qualified in the real guest; a
  candidate never replaces an installed engine automatically.
* Rebuild rather than hand-edit: `engines/impeccable/build/build_engine.py`
  reproduces this directory from the pin (see `../BUILD-RECIPE.md`).
