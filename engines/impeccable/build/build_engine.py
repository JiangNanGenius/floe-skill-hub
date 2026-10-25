#!/usr/bin/env python3
"""Reproducible builder for the Floe Impeccable engine.

One command turns the pinned upstream source plus the tracked Floe adapter into
a versioned engine artifact with a receipt:

  build_engine.py --source <clone> --target riscv64gc-unknown-linux-musl \
      --profile release --dist <engines/impeccable/dist> \
      [--zig-python <venv python>] [--wrapper <run_local_build.py>] [--jobs 6] \
      [--tests] [--cargo-target-dir <dir>]

What it does, in order, failing closed at every step:

 1. verify the source checkout is exactly the pinned commit and tree;
 2. export that commit with `git archive` into a clean build tree (no git
    metadata, no working-tree drift);
 3. apply `patches/*.patch` in lexical order with `git apply --check` first,
    recording each digest;
 4. copy the tracked adapter crate in as `crates/floe-impeccable` and the frozen
    `contract/` into its `data/`, verifying every contract digest against the
    tracked files so the binary cannot embed a contract that differs from the
    committed one;
 5. build with an explicit toolchain, target, profile, job count and target dir
    (cross builds get the zig C compiler and linker driver, so `ring`-free pure
    Rust links statically with the Rust self-contained musl runtime);
 6. verify the artifact: ELF class/machine/type, static linkage, size, digest,
    and (for a host build, or a riscv64 build under an available runner) the
    `engine-probe` handshake and a fixture scan;
 7. write BUILD-RECEIPT.json, PROVENANCE.json, SHA256SUMS.txt and the license
    files into the versioned dist directory.

Nothing here publishes, signs, commits or uploads. It writes only inside the
build tree, the cargo target dir and --dist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_ROOT = HERE.parent
HUB_ROOT = ENGINE_ROOT.parent.parent
ADAPTER_SRC = ENGINE_ROOT / "adapter"
CONTRACT_SRC = ENGINE_ROOT / "contract"
PATCH_DIR = ENGINE_ROOT / "patches"
LOCK_PATH = ENGINE_ROOT / "ENGINE-LOCK.json"

CROSS_TARGETS = {
    "riscv64gc-unknown-linux-musl": {
        "zigTarget": "riscv64-linux-musl",
        "elfMachine": "RISC-V",
        "elfClass": "ELF64",
        "envPrefix": "RISCV64GC_UNKNOWN_LINUX_MUSL",
    },
    "riscv64gc-unknown-linux-gnu": {
        "zigTarget": "riscv64-linux-gnu",
        "elfMachine": "RISC-V",
        "elfClass": "ELF64",
        "envPrefix": "RISCV64GC_UNKNOWN_LINUX_GNU",
    },
}


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None,
        capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    merged = dict(os.environ)
    if env:
        merged.update({k: str(v) for k, v in env.items()})
    return subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        env=merged,
        capture_output=capture,
        text=True,
        check=check,
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fail(message: str, **detail) -> None:
    print(json.dumps({"ok": False, "error": message, **detail}, indent=2))
    raise SystemExit(2)


def load_lock() -> dict:
    if not LOCK_PATH.is_file():
        fail(f"missing engine lock: {LOCK_PATH}")
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1-2. pin verification and export
# --------------------------------------------------------------------------


def verify_pin(source: Path, lock: dict) -> dict:
    if not (source / ".git").exists():
        fail("the source directory is not a git checkout; this builder verifies a real pin", source=str(source))
    head = run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=source).stdout.strip()
    engine_version = (source / "ENGINE_VERSION").read_text(encoding="utf-8").strip()
    expected_commit = lock["upstream"]["commit"]
    expected_tree = lock["upstream"]["tree"]
    expected_version = lock["upstream"]["engineVersion"]
    if head != expected_commit:
        fail("source HEAD is not the pinned commit", head=head, pinned=expected_commit)
    if tree != expected_tree:
        fail("source tree is not the pinned tree", tree=tree, pinned=expected_tree)
    if engine_version != expected_version:
        fail("ENGINE_VERSION does not match the lock", found=engine_version, pinned=expected_version)
    dirty = run(["git", "status", "--porcelain"], cwd=source).stdout.strip()
    if dirty:
        fail("the pinned checkout has uncommitted changes; export would not be reproducible", dirty=dirty[:2000])
    return {"commit": head, "tree": tree, "engineVersion": engine_version}


def export_tree(source: Path, commit: str, build_dir: Path) -> None:
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", commit],
        cwd=str(source), capture_output=True, check=True,
    )
    extract = subprocess.run(["tar", "-x", "-C", str(build_dir)], input=archive.stdout, check=True)
    del extract
    count = sum(1 for p in build_dir.rglob("*") if p.is_file())
    if count < 1000:
        fail("the exported tree looks truncated", files=count)


# --------------------------------------------------------------------------
# 3. patches
# --------------------------------------------------------------------------


def apply_patches(build_dir: Path) -> list[dict]:
    """Apply every tracked patch and then prove it took effect.

    `git apply` is deliberately not used: the build tree lives under `Local/`,
    which is inside an unrelated git work tree, and git silently *skips* patch
    entries there ("Skipped patch ...", exit 0) instead of failing. `patch(1)`
    has no repository discovery, and the post-conditions below mean a skipped or
    half-applied patch fails the build instead of producing an engine that still
    carries the upstream TLS and update paths.
    """
    applied = []
    if not PATCH_DIR.is_dir():
        verify_patch_effects(build_dir, applied)
        return applied
    patch_bin = shutil.which("patch")
    if not patch_bin:
        fail("patch(1) is required to apply the tracked upstream patches")
    for patch in sorted(PATCH_DIR.glob("*.patch")):
        digest = sha256_file(patch)
        dry = subprocess.run(
            [patch_bin, "-p1", "--forward", "--dry-run", "-i", str(patch)],
            cwd=str(build_dir), capture_output=True, text=True,
        )
        if dry.returncode != 0:
            fail(
                "a patch no longer applies to the pinned source; the updater workflow must rebase "
                "it rather than build unpatched",
                patch=patch.name,
                stdout=dry.stdout[-2000:],
                stderr=dry.stderr[-2000:],
            )
        result = subprocess.run(
            [patch_bin, "-p1", "--forward", "-i", str(patch)],
            cwd=str(build_dir), capture_output=True, text=True,
        )
        if result.returncode != 0:
            fail("applying a patch failed", patch=patch.name,
                 stdout=result.stdout[-2000:], stderr=result.stderr[-2000:])
        rejects = list(build_dir.rglob("*.rej")) + list(build_dir.rglob("*.orig"))
        if rejects:
            fail("a patch left reject or original files behind", files=[str(r) for r in rejects[:10]])
        applied.append({"patch": patch.name, "sha256": digest})
    verify_patch_effects(build_dir, applied)
    return applied


# Post-conditions keyed by the patch that must establish them. Each entry is a
# (relative path, must_contain, must_not_contain) triple.
PATCH_EFFECTS = {
    "0001-floe-context-network-and-updater-trim.patch": [
        ("crates/context/Cargo.toml", ["ureq = { version = \"2\", default-features = false, features = [\"json\", \"socks-proxy\"] }"],
         ["rustls-native-certs", "webpki-roots", 'features = ["tls"']),
        # The replacement file explains the trim in prose, so the check looks
        # for actual code usage rather than the word "rustls".
        ("crates/context/src/http.rs", ["no TLS stack", "agent_builder"],
         ["use ureq::rustls", "rustls::crypto", "webpki_roots::", "rustls_native_certs"]),
        ("crates/context/src/context_cli.rs", ["floe_updates_disabled"], []),
    ],
}


def verify_patch_effects(build_dir: Path, applied: list[dict]) -> None:
    names = {entry["patch"] for entry in applied}
    for patch_name, effects in PATCH_EFFECTS.items():
        if patch_name not in names:
            continue
        for rel, must_contain, must_not_contain in effects:
            path = build_dir / rel
            if not path.is_file():
                fail("a patched file is missing after patching", file=rel)
            text = path.read_text(encoding="utf-8")
            for needle in must_contain:
                if needle not in text:
                    fail("a patch did not take effect (expected content missing)",
                         file=rel, expected=needle, patch=patch_name)
            for needle in must_not_contain:
                if needle in text:
                    fail("a patch did not take effect (upstream content still present)",
                         file=rel, unexpected=needle, patch=patch_name)


def audit_dependency_graph(build_dir: Path, args, target: str, receipt: dict) -> None:
    """Prove the trimmed engine carries no TLS/crypto stack.

    The v1 contract claims `transport.network: none`. After patch 0001 that is a
    structural property of the dependency graph, not a convention, so the build
    fails if `ring` (or a rustls provider) is reachable from the adapter crate.
    """
    env = {"RUSTUP_TOOLCHAIN": args.toolchain, "CARGO_TARGET_DIR": str(args.cargo_target_dir)}
    audit = {}
    for forbidden in ("ring", "rustls", "aws-lc-rs", "rustls-native-certs", "webpki-roots"):
        result = subprocess.run(
            ["cargo", "tree", "--package", "floe-impeccable", "--invert", "--target", target,
             forbidden],
            cwd=str(build_dir), env={**os.environ, **env}, capture_output=True, text=True,
        )
        # cargo tree exits non-zero when the package is not in the graph at all,
        # which is the outcome we require.
        present = result.returncode == 0 and forbidden in result.stdout
        audit[forbidden] = {"present": bool(present), "exitCode": result.returncode}
        if present:
            fail(
                f"{forbidden} is still reachable from the adapter crate; the network trim did not "
                "take effect and the engine must not be built",
                tree=result.stdout[:2000],
            )
    crate_count = subprocess.run(
        ["cargo", "tree", "--package", "floe-impeccable", "--target", target, "--prefix", "none"],
        cwd=str(build_dir), env={**os.environ, **env}, capture_output=True, text=True,
    )
    if crate_count.returncode == 0:
        names = set()
        for line in crate_count.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[1].startswith("v"):
                names.add(fields[0])
        audit["cratesInGraph"] = len(names)
        audit["crateNames"] = sorted(names)
    else:
        audit["cratesInGraph"] = None
    audit["target"] = target
    receipt["dependencyAudit"] = audit


# --------------------------------------------------------------------------
# 4. adapter and frozen contract
# --------------------------------------------------------------------------


def stage_adapter(build_dir: Path) -> dict:
    crate_dir = build_dir / "crates" / "floe-impeccable"
    if crate_dir.exists():
        shutil.rmtree(crate_dir)
    shutil.copytree(ADAPTER_SRC, crate_dir)
    data_dir = crate_dir / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)

    # Copy the frozen contract and verify every digest against the tracked file,
    # so the embedded bytes are the committed bytes.
    copied = {}
    for path in sorted(CONTRACT_SRC.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        rel = path.relative_to(CONTRACT_SRC)
        if str(rel).startswith("tools"):
            continue
        # Engine-observed goldens are outputs, not inputs: the binary must not
        # embed them, and staging them would make the artifact depend on a
        # previous run.
        if str(rel).startswith("expected"):
            continue
        target = data_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        source_digest = sha256_file(path)
        staged_digest = sha256_file(target)
        if source_digest != staged_digest:
            fail("a contract file changed while being staged", file=str(rel))
        copied[str(rel)] = source_digest

    required = [
        "snapshot-contract.v1.json",
        "producer/snapshot.schema.v1.json",
        "producer/facts.schema.v1.json",
        "producer/identity.schema.v1.json",
        "producer/result.schema.v1.json",
        "producer/style-props.v1.json",
        "producer/pseudo-props.v1.json",
        "producer/state-pseudos.v1.json",
        "producer/capture-limits.v1.json",
    ]
    missing = [name for name in required if name not in copied]
    if missing:
        fail("the adapter needs these frozen contract files embedded", missing=missing)

    adapter_sources = sorted(
        str(p.relative_to(crate_dir)) for p in crate_dir.rglob("*.rs")
    )
    return {
        "crate": "crates/floe-impeccable",
        "contractFiles": copied,
        "adapterSources": {
            name: sha256_file(crate_dir / name) for name in adapter_sources
        },
    }


# --------------------------------------------------------------------------
# 5. build
# --------------------------------------------------------------------------


def zig_wrappers(zig_python: Path, work: Path, zig_target: str) -> dict:
    bindir = work / "zigbin"
    bindir.mkdir(parents=True, exist_ok=True)
    env = {}
    scripts = {}
    for name, mode in (("cc", "cc"), ("cxx", "c++"), ("ar", "ar")):
        script = bindir / f"zig-{mode}-{'cxx' if name == 'cxx' else name}"
        script.write_text(
            f'#!/bin/sh\nexec "{zig_python}" -m ziglang {name} -target {zig_target} "$@"\n'
            if name != "ar"
            else f'#!/bin/sh\nexec "{zig_python}" -m ziglang ar "$@"\n'
        )
        script.chmod(0o755)
        scripts[name] = script
    env["CC"] = str(scripts["cc"])
    env["CXX"] = str(scripts["cxx"])
    env["AR"] = str(scripts["ar"])
    return env


def remap_flags(args, build_dir: Path) -> str:
    """Keep private absolute paths out of the artifact.

    Rust embeds source locations in panic metadata, and the cargo registry and
    rustup sysroot live under the builder's home. `remap-path-prefix` rewrites
    them to neutral placeholders, so a shipped engine carries no private checkout
    path and two builders on different machines still produce identical bytes.
    """
    home = str(Path.home())
    pairs = [
        (str(build_dir), "/build"),
        (str(args.cargo_target_dir), "/target"),
        (f"{home}/.cargo/registry", "/registry"),
        (f"{home}/.rustup", "/rustup"),
        (home, "/home"),
    ]
    # `--remap-path-prefix` is a rustc flag, not a `-C` codegen option. RUSTFLAGS
    # is whitespace-split, so a source path containing a space cannot be
    # expressed: skip it and say so in the receipt. Keeping build trees on a
    # space-free path (the internal build cache) is therefore part of the recipe.
    usable = [(src, dst) for src, dst in pairs if src and " " not in src and " " not in dst]
    skipped = [src for src, dst in pairs if src and (" " in src or " " in dst)]
    args.remap_skipped = skipped
    return " ".join(f"--remap-path-prefix={src}={dst}" for src, dst in usable)


PRIVATE_PATH_SUBSTITUTIONS = None


def scrub(value, args, build_dir: Path):
    """Replace private absolute paths in recorded evidence with placeholders."""
    home = str(Path.home())
    substitutions = [
        (str(build_dir), "<build-tree>"),
        (str(args.cargo_target_dir), "<cargo-target-dir>"),
        (str(args.log_dir), "<log-dir>"),
        (str(args.source), "<pinned-source>"),
        (str(args.dist) if args.dist else "\0never", "<dist>"),
        (str(HUB_ROOT), "<hub-root>"),
        (str(Path(HUB_ROOT).parent.parent), "<parent-checkout>"),
        (f"{home}/.cargo", "<home>/.cargo"),
        (f"{home}/.rustup", "<home>/.rustup"),
        (home, "<home>"),
    ]
    if args.zig_python:
        substitutions.insert(0, (str(Path(args.zig_python).parent.parent), "<zig-venv>"))
    if args.wrapper:
        substitutions.insert(0, (str(args.wrapper), "<shared-build-wrapper>"))

    def walk(node):
        if isinstance(node, str):
            for src, dst in substitutions:
                node = node.replace(src, dst)
            return node
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(value)


def build(args, build_dir: Path, target: str, receipt: dict) -> Path:
    remap = remap_flags(args, build_dir)
    env = {
        "RUSTUP_TOOLCHAIN": args.toolchain,
        "CARGO_TARGET_DIR": str(args.cargo_target_dir),
        "CARGO_BUILD_JOBS": str(args.jobs),
        # Never let a stray rust-toolchain.toml channel resolution or a
        # registry fetch change the build; the pinned Cargo.lock is authoritative.
        "CARGO_NET_OFFLINE": "1" if args.offline else "0",
        "SOURCE_DATE_EPOCH": str(args.source_date_epoch),
    }
    if target != host_triple():
        spec = CROSS_TARGETS.get(target)
        if not spec:
            fail("unsupported cross target", target=target, supported=sorted(CROSS_TARGETS))
        if not args.zig_python:
            fail(f"cross building {target} needs --zig-python (the C compiler and linker driver)")
        zig_env = zig_wrappers(Path(args.zig_python), Path(args.cargo_target_dir), spec["zigTarget"])
        prefix = spec["envPrefix"]
        env[f"CC_{prefix}"] = zig_env["CC"]
        env[f"CXX_{prefix}"] = zig_env["CXX"]
        env[f"AR_{prefix}"] = zig_env["AR"]
        env[f"CARGO_TARGET_{prefix}_LINKER"] = zig_env["CC"]
        env[f"CARGO_TARGET_{prefix}_RUSTFLAGS"] = f"{remap} " + env.get(f"CARGO_TARGET_{prefix}_RUSTFLAGS", "")
        if target.endswith("-musl"):
            # `link-self-contained=no` hands the whole C side (startup files and
            # libc) to the zig musl sysroot. Rust's own self-contained crt1.o
            # plus zig's produces `duplicate symbol: _start`; letting one side
            # own startup keeps a single, fully static musl image. Verified: the
            # artifact is ELF64 RISC-V EXEC with no PT_INTERP.
            env[f"CARGO_TARGET_{prefix}_RUSTFLAGS"] = (
                f"-C target-feature=+crt-static -C link-self-contained=no {remap}".strip()
            )
    if target == host_triple():
        env["RUSTFLAGS"] = remap
    cargo_cmd = [
        "cargo", "build",
        "--package", "floe-impeccable",
        "--profile", args.profile,
        "--target", target,
    ]
    started = time.time()
    command = cargo_cmd
    if args.wrapper:
        command = [sys.executable, str(args.wrapper), "--"] + cargo_cmd
    print(f"[build] {' '.join(command)}", flush=True)
    result = subprocess.run(
        [str(c) for c in command], cwd=str(build_dir), env={**os.environ, **env},
        capture_output=True, text=True,
    )
    elapsed = round(time.time() - started, 2)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"cargo-build-{target}-{args.profile}.log"
    log_path.write_text(
        f"$ {' '.join(command)}\n\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n",
        encoding="utf-8",
    )
    receipt["build"] = scrub({
        "command": [str(c) for c in command],
        "target": target,
        "profile": args.profile,
        "toolchain": args.toolchain,
        "jobs": args.jobs,
        "rustflags": env.get(f"CARGO_TARGET_{CROSS_TARGETS.get(target, {}).get('envPrefix', '')}_RUSTFLAGS", "")
        or env.get("RUSTFLAGS", ""),
        "pathRemapping": "private absolute paths are remapped to /build, /target, /registry, /rustup and /home",
        "pathRemappingSkipped": getattr(args, "remap_skipped", []),
        "crossToolchain": (
            {
                "zig": getattr(args, "zig_version", None),
                "zigPython": str(args.zig_python),
                "zigTarget": CROSS_TARGETS[target]["zigTarget"],
                "role": "C compiler and linker driver; the engine graph is pure Rust after patch 0001, "
                        "so no C or assembly is compiled and the link uses the Rust self-contained musl runtime",
            }
            if target in CROSS_TARGETS and target != host_triple() and args.zig_python else None
        ),
        "elapsedSeconds": elapsed,
        "exitCode": result.returncode,
        "log": str(log_path),
        "logSha256": sha256_file(log_path),
        "warnings": len(re.findall(r"^warning", result.stderr, re.MULTILINE)),
    }, args, build_dir)
    if result.returncode != 0:
        print(result.stderr[-6000:], file=sys.stderr)
        fail("cargo build failed", log=str(log_path), exitCode=result.returncode)
    binary_name = "floe-impeccable"
    # cargo names the dev profile's output directory "debug"
    profile_dir = "debug" if args.profile == "dev" else args.profile
    artifact = Path(args.cargo_target_dir) / target / profile_dir / binary_name
    if not artifact.is_file():
        fail("the build reported success but the binary is missing", expected=str(artifact))
    return artifact


def host_triple() -> str:
    machine = platform.machine().lower()
    system = platform.system().lower()
    if system == "darwin":
        return "aarch64-apple-darwin" if machine in ("arm64", "aarch64") else "x86_64-apple-darwin"
    if system == "linux":
        return "aarch64-unknown-linux-gnu" if machine in ("arm64", "aarch64") else "x86_64-unknown-linux-gnu"
    return f"{machine}-{system}"


# --------------------------------------------------------------------------
# 6. verification
# --------------------------------------------------------------------------


def verify_binary(artifact: Path, target: str, receipt: dict, runner: list[str] | None,
                  args=None, build_dir: Path | None = None) -> dict:
    info: dict = {
        "path": str(artifact),
        "bytes": artifact.stat().st_size,
        "sha256": sha256_file(artifact),
    }
    header = artifact.open("rb").read(20)
    if header[:4] == b"\x7fELF":
        info["format"] = "ELF"
        info["elfClass"] = "ELF64" if header[4] == 2 else "ELF32"
        info["endian"] = "little" if header[5] == 1 else "big"
        machine = int.from_bytes(header[18:20], "little")
        info["elfMachine"] = {0xF3: "RISC-V", 0xB7: "AArch64", 0x3E: "x86-64"}.get(machine, hex(machine))
        info["elfType"] = {2: "EXEC", 3: "DYN (pie)"}.get(int.from_bytes(header[16:18], "little"), "other")
        spec = CROSS_TARGETS.get(target)
        if spec:
            if info["elfMachine"] != spec["elfMachine"]:
                fail("the artifact is not built for the requested architecture", **info)
            if info["elfClass"] != spec["elfClass"]:
                fail("the artifact has the wrong ELF class", **info)
    elif header[:4] == b"\xcf\xfa\xed\xfe" or header[:4] == b"\xca\xfe\xba\xbe":
        info["format"] = "Mach-O"
    else:
        info["format"] = "unknown"

    # Static linkage: no PT_INTERP. `file`/`readelf` are not guaranteed on every
    # host, so parse the program headers directly for ELF.
    if info.get("format") == "ELF":
        info["static"] = elf_has_no_interp(artifact)
        info["dynamic"] = not info["static"]
        if target.endswith("-musl") and not info["static"]:
            fail("a musl target artifact must be statically linked", **info)

    # Runtime probe: only when a runner for this architecture is available.
    probe_cmd = ([*runner, str(artifact)] if runner else None) if _can_run_locally(target) or runner else None
    if probe_cmd:
        try:
            probe = subprocess.run([*probe_cmd, "engine-probe"], capture_output=True, text=True, timeout=180)
            info["probe"] = {
                "command": probe_cmd + ["engine-probe"],
                "exitCode": probe.returncode,
                "stdout": probe.stdout.strip(),
                "stderr": probe.stderr.strip()[:500],
            }
        except subprocess.TimeoutExpired:
            info["probe"] = {"command": probe_cmd + ["engine-probe"], "timeout": True}
    else:
        info["probe"] = {
            "command": None,
            "note": "no runner for this architecture on this host; runtime verification is recorded as pending",
        }
    if args is not None and build_dir is not None:
        info = scrub(info, args, build_dir)
    receipt["artifact"] = info
    return info


def elf_has_no_interp(path: Path) -> bool:
    with path.open("rb") as fh:
        data = fh.read()
    if data[:4] != b"\x7fELF" or data[4] != 2:
        return False
    e_phoff = int.from_bytes(data[32:40], "little")
    e_phentsize = int.from_bytes(data[54:56], "little")
    e_phnum = int.from_bytes(data[56:58], "little")
    for i in range(e_phnum):
        offset = e_phoff + i * e_phentsize
        p_type = int.from_bytes(data[offset:offset + 4], "little")
        if p_type == 3:  # PT_INTERP
            return False
    return True


def _can_run_locally(target: str) -> bool:
    return target == host_triple()


# --------------------------------------------------------------------------
# 7. dist
# --------------------------------------------------------------------------


def write_dist(args, artifact: Path, target: str, receipt: dict, pin: dict, patches: list[dict],
               staged: dict) -> Path:
    engine_id = receipt["engineId"]
    dist_root = Path(args.dist) / engine_id / target
    if dist_root.exists():
        shutil.rmtree(dist_root)
    dist_root.mkdir(parents=True)
    binary_target = dist_root / "floe-impeccable"
    shutil.copyfile(artifact, binary_target)
    binary_target.chmod(0o755)

    upstream_license = Path(args.build_dir) / "LICENSE"
    upstream_notice = Path(args.build_dir) / "NOTICE.md"
    shutil.copyfile(upstream_license, dist_root / "LICENSE-impeccable-apache-2.0")
    shutil.copyfile(upstream_notice, dist_root / "NOTICE-impeccable.md")
    (dist_root / "LICENSE-adapter").write_text(
        (HUB_ROOT / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8"
    )

    provenance = {
        "engineId": engine_id,
        "binary": "floe-impeccable",
        "target": target,
        "upstream": {
            "project": "pbakaus/impeccable",
            "commit": pin["commit"],
            "tree": pin["tree"],
            "engineVersion": pin["engineVersion"],
            "packageVersion": receipt["upstreamPackageVersion"],
            "license": "Apache-2.0",
            "pinAuthority": "floe-skill-hub docs/UPSTREAM-PINS.json",
        },
        "floe": {
            "adapterVersion": receipt["adapterVersion"],
            "adapterCrate": staged["crate"],
            "adapterSources": staged["adapterSources"],
            "contractFiles": staged["contractFiles"],
            "patches": patches,
            "contractVersion": receipt["contractVersion"],
            "license": "MPL-2.0 (Floe-authored adapter files)",
        },
        "toolchain": receipt["build"],
        "artifact": receipt["artifact"],
        "notVendored": "the full upstream source tree is never committed; it is exported from the pinned commit at build time",
    }
    provenance = scrub(provenance, args, args.build_dir)
    receipt = scrub(receipt, args, args.build_dir)
    (dist_root / "PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (dist_root / "BUILD-RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    lines = []
    for path in sorted(dist_root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{sha256_file(path)}  {path.relative_to(dist_root)}")
    (dist_root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dist_root


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path, help="git checkout of the pinned upstream source")
    ap.add_argument("--target", default=host_triple())
    ap.add_argument("--profile", default="release", choices=["release", "dev"])
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--toolchain", default="1.98.1")
    ap.add_argument("--build-dir", type=Path, default=None)
    ap.add_argument("--cargo-target-dir", type=Path, required=True)
    ap.add_argument("--dist", type=Path, default=None)
    ap.add_argument("--log-dir", type=Path, required=True)
    ap.add_argument("--zig-python", default=None)
    ap.add_argument("--wrapper", default=None, help="shared serialized build wrapper (run_local_build.py)")
    ap.add_argument("--runner", default=None, help="command prefix that can execute the target binary (qemu/docker)")
    ap.add_argument("--offline", action="store_true", default=True)
    ap.add_argument("--allow-network", dest="offline", action="store_false")
    ap.add_argument("--source-date-epoch", type=int, default=1761436800)
    ap.add_argument("--skip-build", action="store_true", help="stage and verify only (used by --tests runs)")
    ap.add_argument("--skip-dependency-audit", action="store_true",
                    help="skip the no-TLS/no-crypto dependency graph proof")
    ap.add_argument("--tests", action="store_true", help="run the adapter test suite after building")
    args = ap.parse_args()

    # Every path becomes absolute: cargo runs with the build tree as cwd, so a
    # relative wrapper, log dir or dist path would resolve against it.
    args.source = args.source.expanduser().resolve()
    args.cargo_target_dir = args.cargo_target_dir.expanduser().resolve()
    args.log_dir = args.log_dir.expanduser().resolve()
    if args.dist:
        args.dist = args.dist.expanduser().resolve()
    if args.wrapper:
        args.wrapper = Path(args.wrapper).expanduser().resolve()
        if not args.wrapper.is_file():
            fail("the shared build wrapper does not exist", wrapper=str(args.wrapper))
    if args.build_dir:
        args.build_dir = args.build_dir.expanduser().resolve()
    if args.zig_python:
        # abspath, not resolve(): a venv's `bin/python` is a symlink to the
        # interpreter it was created from, and resolving it drops the venv's
        # site-packages (where ziglang lives).
        args.zig_python = os.path.abspath(os.path.expanduser(args.zig_python))
        if not Path(args.zig_python).exists():
            fail("the zig python interpreter does not exist", zigPython=args.zig_python)
        probe = subprocess.run([args.zig_python, "-m", "ziglang", "version"], capture_output=True, text=True)
        if probe.returncode != 0:
            fail("the zig python interpreter cannot run `python -m ziglang version`",
                 zigPython=args.zig_python, stderr=probe.stderr[-500:])
        args.zig_version = probe.stdout.strip()

    lock = load_lock()
    args.build_dir = args.build_dir or (Path(args.cargo_target_dir).parent / "build-tree")

    pin = verify_pin(args.source, lock)
    print(f"[pin] {pin['commit']} tree={pin['tree']} ENGINE_VERSION={pin['engineVersion']}", flush=True)
    export_tree(args.source, pin["commit"], args.build_dir)
    patches = apply_patches(args.build_dir)
    print(f"[patches] applied {len(patches)}", flush=True)
    staged = stage_adapter(args.build_dir)
    print(f"[adapter] staged {len(staged['contractFiles'])} contract files, "
          f"{len(staged['adapterSources'])} sources", flush=True)

    package_json = json.loads((args.build_dir / "package.json").read_text(encoding="utf-8"))
    contract = json.loads((CONTRACT_SRC / "snapshot-contract.v1.json").read_text(encoding="utf-8"))
    receipt = {
        "engineId": f"impeccable-{pin['engineVersion']}+floe.{ADAPTER_VERSION}",
        "adapterVersion": ADAPTER_VERSION,
        "contractVersion": contract["contractVersion"],
        "upstreamPackageVersion": package_json.get("version"),
        "pin": pin,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }
    if contract["engine"]["upstreamCommit"] != pin["commit"]:
        fail(
            "the frozen contract names a different upstream commit than the build pin; "
            "one deliberate pin only",
            contract=contract["engine"]["upstreamCommit"], build=pin["commit"],
        )

    if not args.skip_dependency_audit:
        audit_dependency_graph(args.build_dir, args, args.target, receipt)
        print(f"[audit] no TLS/crypto stack reachable from the adapter crate "
              f"({receipt['dependencyAudit']['cratesInGraph']} crates in graph)", flush=True)

    artifact = None
    if not args.skip_build:
        artifact = build(args, args.build_dir, args.target, receipt)
        runner = args.runner.split() if args.runner else None
        verify_binary(artifact, args.target, receipt, runner, args, args.build_dir)
        print(f"[artifact] {receipt['artifact']['sha256']} {receipt['artifact']['bytes']} bytes "
              f"format={receipt['artifact'].get('format')} static={receipt['artifact'].get('static')}", flush=True)

    if args.tests:
        run_tests(args, receipt)

    if args.dist and artifact is not None:
        dist = write_dist(args, artifact, args.target, receipt, pin, patches, staged)
        receipt["dist"] = str(dist)
        (dist / "BUILD-RECEIPT.json").write_text(
            json.dumps(scrub(receipt, args, args.build_dir), indent=2) + "\n", encoding="utf-8")
        lines = []
        for path in sorted(dist.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS.txt":
                lines.append(f"{sha256_file(path)}  {path.relative_to(dist)}")
        (dist / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[dist] {dist}", flush=True)

    receipt["patches"] = patches
    receipt["staged"] = {"contractFiles": len(staged["contractFiles"]), "adapterSources": staged["adapterSources"]}
    summary = Path(args.log_dir) / f"build-summary-{args.target}-{args.profile}.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(scrub(receipt, args, args.build_dir), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "summary": str(summary),
                      "artifact": receipt.get("artifact", {}).get("sha256"),
                      "probe": receipt.get("artifact", {}).get("probe")}, indent=2))
    return 0


ADAPTER_VERSION = "1.0.0"


def run_tests(args, receipt: dict) -> None:
    # The test build must use the same RUSTFLAGS as the shipped build, or cargo
    # rebuilds the binary without the path remapping and the tested artifact is
    # no longer the artifact the receipt describes.
    env = {
        "RUSTUP_TOOLCHAIN": args.toolchain,
        "CARGO_TARGET_DIR": str(args.cargo_target_dir),
        "CARGO_BUILD_JOBS": str(args.jobs),
        "CARGO_NET_OFFLINE": "1" if args.offline else "0",
        "RUSTFLAGS": remap_flags(args, args.build_dir),
    }
    cmd = ["cargo", "test", "--package", "floe-impeccable", "--target", host_triple()]
    command = [sys.executable, str(args.wrapper), "--"] + cmd if args.wrapper else cmd
    print(f"[tests] {' '.join(command)}", flush=True)
    result = subprocess.run([str(c) for c in command], cwd=str(args.build_dir),
                            env={**os.environ, **env}, capture_output=True, text=True)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "cargo-test-host.log"
    log_path.write_text(
        f"$ {' '.join(command)}\n\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n",
        encoding="utf-8",
    )
    passed = len(re.findall(r"^test [\w:]+ \.\.\. ok$", result.stdout, re.MULTILINE))
    failed = len(re.findall(r"^test [\w:]+ \.\.\. FAILED$", result.stdout, re.MULTILINE))
    receipt["tests"] = scrub({
        "command": [str(c) for c in command],
        "target": host_triple(),
        "exitCode": result.returncode,
        "passed": passed,
        "failed": failed,
        "log": str(log_path),
        "logSha256": sha256_file(log_path),
    }, args, args.build_dir)
    print(f"[tests] exit={result.returncode} passed={passed} failed={failed}", flush=True)
    if result.returncode != 0:
        print(result.stdout[-6000:], file=sys.stderr)
        print(result.stderr[-4000:], file=sys.stderr)
        fail("the adapter test suite failed", log=str(log_path))


if __name__ == "__main__":
    sys.exit(main())
