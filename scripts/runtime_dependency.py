#!/usr/bin/env python3
"""Strict known-component validator for managed raw runtime artifacts.

The Impeccable branch retains its capture contract. The Ortie branch uses
oauthContract and binds the complete pinned MCP schema fixture plus every
notice/source distribution file. Both branches read only their own fixed
descriptor paths from the same frozen source/publication root. No native
binary is permitted inside an ordinary Skill ZIP.

Frozen input (coordinator, 2026-10-26): engines/impeccable/runtime-dependency/
{descriptor.v1.json, schema.v1.json, README.md}. The canonical Impeccable Skill
package embeds byte-identical `references/engine-dependency.json` data. That
descriptor is authenticated indirectly: it sits inside the signed Skill ZIP,
so the signed catalog -> archive sha256/contentDigest -> review chain binds its
exact bytes. It grants no permissions by itself.

This module provides the pure checks shared by:
  * source/package production (build_packages.py): a staged package embedding
    references/engine-dependency.json must match the frozen tree descriptor
    and the actual artifact bytes in the same tree;
  * the release builder (build_catalog.py --mode release): the descriptor and
    the raw artifact are read ONLY from the frozen --source-snapshot of the
    audited X, and BOTH validated byte sets are staged into the publication
    output (Y) under their exact descriptor-relative paths, so a fresh output
    root binds the runtime package standalone without any manual copy;
  * the standalone publication checker (check_catalog.py): the published
    package's embedded descriptor is re-validated against the published
    frozen descriptor and the actual artifact bytes at Y, for both channels,
    never against a mutable candidate HEAD.

Safety invariants enforced here (fail closed):
  * descriptor: exactly 7 keys with exact subkey shapes; schemaVersion is
    exactly the integer 1 (bool/float/str rejected); raw bytes must be the
    canonical UTF-8 encoding (no BOM/UTF-16/duplicate-key last-wins); known
    allowlisted component/target only; strict semver+floe component version; strict
    minimumAppVersion; artifact size 1..16 MiB (native hard cap for this known
    component ONLY — ordinary Skill limits of 2 MiB/file and 8 MiB/package
    stay unchanged); strict lowercase SHA-256; captureContract version 1 with
    a strict hash; exact cross-field agreement between componentVersion,
    target.triple and artifact.path; no URL/repository/command/approval/
    environment fields (unknown keys are rejected); no traversal, absolute,
    backslash, NUL, empty or dot paths;
  * artifact: bounded read, exact size+SHA-256 match, ELF64 little-endian
    AArch64 EXEC static only (no PT_INTERP; e_machine 183), bounded
    program-header table with in-file offsets. A legacy RISC-V (e_machine 243)
    artifact can never pass. The binary is NEVER executed on the host and no
    producer code is invoked;
  * filesystem: no symlinks at the artifact path or any ancestor, and the
    frozen descriptor is likewise read without symlink indirection.

Nothing in this module widens the ordinary Skill ZIP gates: a native binary
inside a Skill ZIP is still rejected by the unchanged package gates.
"""
import json
import pathlib
import re
import struct
import unicodedata

import hubcore

# --- frozen contract constants (mirror runtime-dependency/schema.v1.json) ---
RUNTIME_DESCRIPTOR_SCHEMA_VERSION = 1
CAPTURE_CONTRACT_SUPPORTED_VERSION = 1
MAX_RUNTIME_ARTIFACT_BYTES = 16 * 1024 * 1024  # 16 MiB native hard cap, known component only

KNOWN_COMPONENT_ID = "impeccable-engine"
ORTIE_COMPONENT_ID = "ortie-oauth-engine"
ORTIE_DESCRIPTOR_REL = "engines/ortie/runtime-dependency/descriptor.v1.json"
ORTIE_CONTRACT_REL = "engines/ortie/runtime-dependency/oauth-contract.v1.json"
ORTIE_HANDSHAKE_REL = "engines/ortie/runtime-dependency/mcp-handshake.v1.json"
ORTIE_DISTRIBUTION_REL = "engines/ortie/runtime-dependency/distribution.v1.json"
ORTIE_HANDSHAKE_SHA256 = "1cbf74ffdba9bf2179435cf1dfa9089b87185031c11813d2dbb7a7080ad69d1e"
# Frozen managed runtime-component target (ARM64 transition, 2026-11-05):
# the resident Floe Linux guest executes AArch64; this is the verified guest
# fact, never the build host CPU. The legacy RISC-V tuple is deliberately not
# allowlisted: the retired RISC-V native engine can never pass this gate.
KNOWN_TARGET = {
    "os": "linux",
    "arch": "arm64",
    "triple": "aarch64-unknown-linux-musl",
    "format": "elf64-little-aarch64-exec-static",
}
DESCRIPTOR_KEYS = {"schemaVersion", "componentID", "componentVersion",
                   "minimumAppVersion", "target", "artifact", "captureContract"}
TARGET_KEYS = {"os", "arch", "triple", "format"}
ARTIFACT_KEYS = {"path", "size", "sha256"}
CAPTURE_CONTRACT_KEYS = {"version", "sha256"}
MAX_ARTIFACT_PATH_BYTES = 256

FLOE_COMPONENT_VERSION_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\+floe\."
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")

# ELF64 little-endian AArch64 EXEC static invariants
EM_AARCH64 = 183
ET_EXEC = 2
ELFCLASS64 = 2
ELFDATA2LSB = 1
EV_CURRENT = 1
PT_INTERP = 3
ELF64_EHDR_SIZE = 64
ELF64_PHDR_SIZE = 56
ELF64_SHDR_SIZE = 64
MAX_PROGRAM_HEADERS = 4096   # bounded table; real image carries 10
MAX_SECTION_HEADERS = 4096   # bounded table; real image carries 16
PN_XNUM = 0xFFFF             # extended numbering is not supported (fail closed)

FROZEN_DESCRIPTOR_REL = "engines/impeccable/runtime-dependency/descriptor.v1.json"
EMBEDDED_DESCRIPTOR_REL = "references/engine-dependency.json"


def expected_artifact_path(component_version, triple, component_id=KNOWN_COMPONENT_ID):
    """The exact cross-field artifact path for a validated known component."""
    if component_id == ORTIE_COMPONENT_ID:
        return (f"engines/ortie/dist/ortie-{component_version}/"
                f"{triple}/floe-ortie")
    return (f"engines/impeccable/dist/impeccable-{component_version}/"
            f"{triple}/floe-impeccable")


def _validate_artifact_path(value, component_version, triple, field, component_id=KNOWN_COMPONENT_ID):
    if (not isinstance(value, str) or not value
            or value.startswith("/") or "\\" in value or "\0" in value):
        raise hubcore.HubError(f"{field}: artifact path must be a safe relative path")
    if len(value.encode("utf-8")) > MAX_ARTIFACT_PATH_BYTES:
        raise hubcore.HubError(
            f"{field}: artifact path exceeds {MAX_ARTIFACT_PATH_BYTES} bytes")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise hubcore.HubError(
            f"{field}: artifact path must not contain empty, dot or dot-dot segments")
    expected = expected_artifact_path(component_version, triple, component_id)
    if value != expected:
        raise hubcore.HubError(
            f"{field}: artifact path disagrees with componentVersion/target "
            f"(expected {expected!r})")
    return value


def validate_descriptor(descriptor, field="engine-dependency"):
    """Fail-closed validation of one parsed descriptor VALUE.

    Accepts only the known allowlisted component/target with the exact frozen
    key shape; returns the descriptor on success.
    """
    if not isinstance(descriptor, dict):
        raise hubcore.HubError(f"{field}: runtime descriptor must be an object")
    component_id = descriptor.get("componentID")
    contract_key = "oauthContract" if component_id == ORTIE_COMPONENT_ID else "captureContract"
    descriptor_keys = (DESCRIPTOR_KEYS - {"captureContract"}) | {contract_key}
    if set(descriptor) != descriptor_keys:
        raise hubcore.HubError(
            f"{field}: runtime descriptor keys must be exactly {sorted(descriptor_keys)}")
    schema_version = descriptor["schemaVersion"]
    if (not isinstance(schema_version, int) or isinstance(schema_version, bool)
            or schema_version != RUNTIME_DESCRIPTOR_SCHEMA_VERSION):
        raise hubcore.HubError(
            f"{field}: unsupported runtime descriptor schemaVersion "
            f"{schema_version!r} (supported: exactly the integer "
            f"{RUNTIME_DESCRIPTOR_SCHEMA_VERSION})")
    if component_id not in (KNOWN_COMPONENT_ID, ORTIE_COMPONENT_ID):
        raise hubcore.HubError(
            f"{field}: unknown componentID {descriptor['componentID']!r} "
            f"(allowlist: {KNOWN_COMPONENT_ID!r}, {ORTIE_COMPONENT_ID!r})")
    version = descriptor["componentVersion"]
    if (not isinstance(version, str) or len(version) > 64
            or not FLOE_COMPONENT_VERSION_PATTERN.fullmatch(version)):
        raise hubcore.HubError(
            f"{field}: componentVersion must be strict semver + floe.X.Y.Z "
            f"without leading zeros: {version!r}")
    hubcore.require_version(descriptor["minimumAppVersion"],
                            f"{field}.minimumAppVersion")
    target = descriptor["target"]
    if not isinstance(target, dict) or set(target) != TARGET_KEYS:
        raise hubcore.HubError(
            f"{field}: target keys must be exactly {sorted(TARGET_KEYS)}")
    if target != KNOWN_TARGET:
        raise hubcore.HubError(
            f"{field}: target {target!r} is outside the known allowlist "
            f"{KNOWN_TARGET!r}")
    artifact = descriptor["artifact"]
    if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_KEYS:
        raise hubcore.HubError(
            f"{field}: artifact keys must be exactly {sorted(ARTIFACT_KEYS)}")
    _validate_artifact_path(artifact["path"], version, target["triple"], field, component_id)
    size = artifact["size"]
    if (not isinstance(size, int) or isinstance(size, bool)
            or not 1 <= size <= MAX_RUNTIME_ARTIFACT_BYTES):
        raise hubcore.HubError(
            f"{field}: artifact size must be an integer 1.."
            f"{MAX_RUNTIME_ARTIFACT_BYTES}")
    hubcore.require_hex64(artifact["sha256"], f"{field}.artifact.sha256")
    contract = descriptor[contract_key]
    if not isinstance(contract, dict) or set(contract) != CAPTURE_CONTRACT_KEYS:
        raise hubcore.HubError(
            f"{field}: {contract_key} keys must be exactly "
            f"{sorted(CAPTURE_CONTRACT_KEYS)}")
    if (not isinstance(contract["version"], int) or isinstance(contract["version"], bool)
            or contract["version"] != CAPTURE_CONTRACT_SUPPORTED_VERSION):
        raise hubcore.HubError(
            f"{field}: unsupported {contract_key} version "
            f"{contract['version']!r} (supported: {CAPTURE_CONTRACT_SUPPORTED_VERSION})")
    hubcore.require_hex64(contract["sha256"], f"{field}.{contract_key}.sha256")
    return descriptor


def _canonical_object(data, field):
    try:
        value = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise hubcore.HubError(f"{field}: invalid UTF-8 JSON: {error}") from None
    if not isinstance(value, dict) or hubcore.encoded(value) != data:
        raise hubcore.HubError(f"{field}: expected canonical JSON object")
    return value


def _read_binding(root, binding, expected_path, limit, field):
    if not isinstance(binding, dict) or set(binding) != {"path", "size", "sha256"}:
        raise hubcore.HubError(f"{field}: exact path/size/sha256 binding required")
    if binding["path"] != expected_path:
        raise hubcore.HubError(f"{field}: unexpected bound path")
    if type(binding["size"]) is not int or not 1 <= binding["size"] <= limit:
        raise hubcore.HubError(f"{field}: invalid bounded size")
    hubcore.require_hex64(binding["sha256"], field)
    _reject_symlink_components(root, expected_path, field)
    path = pathlib.Path(root) / expected_path
    if not path.is_file():
        raise hubcore.HubError(f"{field}: missing bound file {expected_path}")
    data = _read_bounded(path, limit, field)
    if len(data) != binding["size"] or hubcore.sha256_hex(data) != binding["sha256"]:
        raise hubcore.HubError(f"{field}: bound bytes disagree with size/sha256")
    return data


def load_oauth_payload(root, descriptor, field="engine-dependency"):
    """Read only the authenticated Ortie contract's fixed distribution tree."""
    _reject_symlink_components(root, ORTIE_CONTRACT_REL, field)
    path = pathlib.Path(root) / ORTIE_CONTRACT_REL
    if not path.is_file():
        raise hubcore.HubError(f"{field}: missing OAuth contract")
    data = _read_bounded(path, 65_536, field)
    if hubcore.sha256_hex(data) != descriptor["oauthContract"]["sha256"]:
        raise hubcore.HubError(f"{field}: OAuth contract sha256 mismatch")
    contract = _canonical_object(data, field)
    if (set(contract) != {"schemaVersion", "componentID", "handshake", "distribution", "transport"}
            or type(contract["schemaVersion"]) is not int or contract["schemaVersion"] != 1
            or contract["componentID"] != ORTIE_COMPONENT_ID):
        raise hubcore.HubError(f"{field}: unsupported OAuth contract shape")
    transport = contract["transport"]
    if (not isinstance(transport, dict)
            or set(transport) != {"mode", "externalLoopback", "allowRevoke"}
            or transport["mode"] != "private-stdio"
            or transport["externalLoopback"] is not True
            or transport["allowRevoke"] is not False):
        raise hubcore.HubError(f"{field}: unsupported private OAuth transport")
    fixture = _read_binding(root, contract["handshake"], ORTIE_HANDSHAKE_REL, 65_536, field)
    if hubcore.sha256_hex(fixture) != ORTIE_HANDSHAKE_SHA256:
        raise hubcore.HubError(f"{field}: unsupported full MCP handshake schemas")
    _canonical_object(fixture, field)
    distribution = _read_binding(root, contract["distribution"], ORTIE_DISTRIBUTION_REL,
                                 1024 * 1024, field)
    manifest = _canonical_object(distribution, field)
    if (set(manifest) != {"schemaVersion", "componentID", "files"}
            or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1
            or manifest["componentID"] != ORTIE_COMPONENT_ID
            or not isinstance(manifest["files"], list)
            or not 1 <= len(manifest["files"]) <= 1024):
        raise hubcore.HubError(f"{field}: invalid OAuth distribution manifest")
    result = {ORTIE_CONTRACT_REL: data, ORTIE_HANDSHAKE_REL: fixture,
              ORTIE_DISTRIBUTION_REL: distribution}
    prefix = f"engines/ortie/notices/{descriptor['componentVersion']}/"
    previous = ""
    folded_paths = set()
    total = 0
    for entry in manifest["files"]:
        rel = entry.get("path") if isinstance(entry, dict) else None
        if (not isinstance(rel, str) or len(rel.encode("utf-8")) > 512
                or not rel.startswith(prefix) or "\\" in rel or "\0" in rel
                or any(unicodedata.category(ch).startswith("C") for ch in rel)
                or any(part in ("", ".", "..") for part in rel.split("/"))
                or rel <= previous):
            raise hubcore.HubError(f"{field}: unsafe, duplicate or unsorted notice path")
        folded = unicodedata.normalize("NFC", rel).casefold()
        if folded in folded_paths:
            raise hubcore.HubError(f"{field}: duplicate normalized notice path")
        folded_paths.add(folded)
        local = rel[len(prefix):]
        if not (local in {"THIRD_PARTY_NOTICES.md", "manifest.json"}
                or local.startswith(("licenses/", "toolchain-reference/", "provenance/"))
                or local == "sources/option-ext-0.2.0.crate"):
            raise hubcore.HubError(f"{field}: notice path outside known distribution")
        blob = _read_binding(root, entry, rel, 2 * 1024 * 1024, field)
        if blob.startswith((b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf")):
            raise hubcore.HubError(f"{field}: executable in notice distribution")
        total += len(blob)
        if total > 16 * 1024 * 1024:
            raise hubcore.HubError(f"{field}: notice distribution exceeds 16 MiB")
        result[rel] = blob
        previous = rel
    mpl_rel = prefix + "sources/option-ext-0.2.0.crate"
    if (mpl_rel not in result or hubcore.sha256_hex(result[mpl_rel]) !=
            "04744f49eae99ab78e0d5c0b603ab218f515ea8cfe5a456d7629ad883a3b6e7d"):
        raise hubcore.HubError(f"{field}: complete pinned MPL source missing")
    return result


def publication_files(descriptor_bytes, root, field="engine-dependency"):
    """Produce a standalone publication using only the same frozen root."""
    descriptor = bind_package_descriptor(descriptor_bytes, root, field)
    result = {frozen_descriptor_path(descriptor): descriptor_bytes,
              descriptor["artifact"]["path"]: load_artifact(root, descriptor, field)}
    if descriptor["componentID"] == ORTIE_COMPONENT_ID:
        result.update(load_oauth_payload(root, descriptor, field))
    return result


def parse_descriptor(data, field="engine-dependency"):
    """Parse raw descriptor bytes and validate the value strictly.

    Only the exact canonical UTF-8 JSON bytes accepted: the frozen
    descriptor is canonical (the published component's is 563 bytes), with
    no trailing newline and no duplicate keys. So:

      * the raw material must be valid strict UTF-8 (no UTF-16/UTF-32 or
        other sniffable encodings, and no UTF-8 BOM);
      * re-encoding the parsed value with hubcore.encoded must equal the
        raw bytes exactly — sorted keys, tight separators, canonical
        numbers — so key-order drift, indentation, trailing whitespace,
        and JSON last-one-wins duplicate keys can never be silently
        accepted (native JSON decoders that reject or reinterpret such
        bytes must see the same rejection here).
    """
    if isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise hubcore.HubError(
                f"{field}: runtime descriptor must be valid UTF-8 bytes") from None
    elif isinstance(data, str):
        text = data
        try:
            raw = data.encode("utf-8")
        except UnicodeEncodeError:
            raise hubcore.HubError(
                f"{field}: runtime descriptor must be valid UTF-8 text") from None
    else:
        raise hubcore.HubError(f"{field}: runtime descriptor must be JSON bytes")
    try:
        value = json.loads(text)
    except ValueError as error:
        raise hubcore.HubError(
            f"{field}: runtime descriptor is not valid JSON: {error}") from None
    if hubcore.encoded(value) != raw:
        raise hubcore.HubError(
            f"{field}: runtime descriptor bytes are not the canonical UTF-8 "
            f"encoding (sorted keys, tight separators, no duplicate keys, "
            f"no BOM or trailing whitespace)")
    return validate_descriptor(value, field)


def _validate_elf(data, field):
    """ELF64 little-endian AArch64 EXEC static, bounded headers, no PT_INTERP."""
    if len(data) < ELF64_EHDR_SIZE:
        raise hubcore.HubError(f"{field}: artifact smaller than an ELF64 header")
    if not data.startswith(b"\x7fELF"):
        raise hubcore.HubError(f"{field}: artifact is not an ELF binary")
    if data[4] != ELFCLASS64 or data[5] != ELFDATA2LSB or data[6] != EV_CURRENT:
        raise hubcore.HubError(
            f"{field}: artifact must be ELF64 little-endian version 1 "
            f"(class={data[4]}, data={data[5]}, version={data[6]})")
    e_type, e_machine, e_version = struct.unpack_from("<HHI", data, 16)
    if e_type != ET_EXEC:
        raise hubcore.HubError(
            f"{field}: artifact must be an EXEC binary, not shared/relocatable/PIE "
            f"(e_type={e_type})")
    if e_machine != EM_AARCH64:
        raise hubcore.HubError(
            f"{field}: artifact machine is not AArch64 (e_machine={e_machine}; "
            f"expected {EM_AARCH64})")
    if e_version != EV_CURRENT:
        raise hubcore.HubError(f"{field}: artifact e_version must be {EV_CURRENT}")
    (e_entry, e_phoff, e_shoff, e_flags, e_ehsize, e_phentsize, e_phnum,
     e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from("<QQQIHHHHHH", data, 24)
    del e_entry, e_flags, e_shstrndx  # informational only; not security relevant
    if e_ehsize != ELF64_EHDR_SIZE:
        raise hubcore.HubError(f"{field}: artifact e_ehsize must be {ELF64_EHDR_SIZE}")
    if e_phentsize != ELF64_PHDR_SIZE:
        raise hubcore.HubError(
            f"{field}: artifact e_phentsize must be {ELF64_PHDR_SIZE}")
    if e_phnum in (0, PN_XNUM) or e_phnum > MAX_PROGRAM_HEADERS:
        raise hubcore.HubError(
            f"{field}: artifact program-header count {e_phnum} outside "
            f"1..{MAX_PROGRAM_HEADERS}")
    if e_phoff + e_phnum * e_phentsize > len(data):
        raise hubcore.HubError(f"{field}: artifact program-header table exceeds the file")
    found_interp = False
    for index in range(e_phnum):
        base = e_phoff + index * e_phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
            struct.unpack_from("<IIQQQQQQ", data, base)
        del p_flags, p_vaddr, p_paddr, p_align  # informational only
        if p_type == PT_INTERP:
            found_interp = True
        if p_offset + p_filesz > len(data):
            raise hubcore.HubError(
                f"{field}: program header {index} lies outside the file")
        if p_memsz < p_filesz:
            raise hubcore.HubError(
                f"{field}: program header {index} memsz smaller than filesz")
    if found_interp:
        raise hubcore.HubError(
            f"{field}: artifact carries PT_INTERP; only static executables are allowed")
    if e_shnum not in (0, PN_XNUM):
        if e_shnum > MAX_SECTION_HEADERS:
            raise hubcore.HubError(
                f"{field}: artifact section-header count {e_shnum} outside "
                f"0..{MAX_SECTION_HEADERS}")
        if e_shentsize != ELF64_SHDR_SIZE:
            raise hubcore.HubError(
                f"{field}: artifact e_shentsize must be {ELF64_SHDR_SIZE}")
        if e_shoff + e_shnum * e_shentsize > len(data):
            raise hubcore.HubError(f"{field}: artifact section-header table exceeds the file")


def validate_artifact_bytes(data, descriptor, field="engine-dependency"):
    """Bounded byte validation: exact size+SHA-256, then the ELF safety gate."""
    expected_size = descriptor["artifact"]["size"]
    if len(data) != expected_size:
        raise hubcore.HubError(
            f"{field}: runtime artifact size mismatch "
            f"(descriptor {expected_size}, actual {len(data)})")
    if hubcore.sha256_hex(data) != descriptor["artifact"]["sha256"]:
        raise hubcore.HubError(f"{field}: runtime artifact sha256 mismatch")
    _validate_elf(data, field)
    return data


def _read_bounded(path, limit, field):
    with open(path, "rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise hubcore.HubError(
            f"{field}: file exceeds the {limit}-byte bound: {path}")
    return data


def _reject_symlink_components(root, rel, field):
    current = pathlib.Path(root)
    for part in rel.split("/"):
        current = current / part
        if current.is_symlink():
            raise hubcore.HubError(
                f"{field}: path crosses a symbolic link: {part!r}")


def load_artifact(root, descriptor, field="engine-dependency"):
    """Read + validate the raw artifact at root/<descriptor path>, fail closed
    on missing files, symlinks (at any path component) or unsafe bytes."""
    rel = descriptor["artifact"]["path"]
    _reject_symlink_components(root, rel, field)
    path = pathlib.Path(root) / rel
    if not path.is_file():
        raise hubcore.HubError(f"{field}: runtime artifact missing at {rel}")
    data = _read_bounded(path, MAX_RUNTIME_ARTIFACT_BYTES, field)
    return validate_artifact_bytes(data, descriptor, field)


def frozen_descriptor_path(descriptor):
    return (ORTIE_DESCRIPTOR_REL if descriptor["componentID"] == ORTIE_COMPONENT_ID
            else FROZEN_DESCRIPTOR_REL)


def load_frozen_descriptor_bytes(root, field="engine-dependency", descriptor=None):
    """Read the frozen tree descriptor without symlink indirection."""
    rel = frozen_descriptor_path(descriptor) if descriptor is not None else FROZEN_DESCRIPTOR_REL
    _reject_symlink_components(root, rel, field)
    path = pathlib.Path(root) / rel
    if not path.is_file():
        raise hubcore.HubError(
            f"{field}: frozen runtime descriptor missing at {rel}")
    return _read_bounded(path, 65_536, field)


def bind_package_descriptor(descriptor_bytes, tree_root,
                            field="engine-dependency"):
    """Bind an authenticated package-embedded descriptor to one immutable tree.

    The embedded descriptor must (a) pass the strict value gate, (b) be
    byte-identical to the frozen tree descriptor at the SAME root (X snapshot
    for release builds, Y publication tree for the standalone checker, candidate
    tree for package production), and (c) reference an existing, exact-size,
    exact-hash, safe-static-ELF artifact at that same root. Returns the parsed
    validated descriptor.
    """
    descriptor = parse_descriptor(descriptor_bytes, field)
    frozen_bytes = load_frozen_descriptor_bytes(tree_root, field, descriptor)
    if frozen_bytes != descriptor_bytes:
        raise hubcore.HubError(
            f"{field}: embedded engine-dependency.json differs from the frozen "
            f"tree descriptor at {frozen_descriptor_path(descriptor)}")
    load_artifact(tree_root, descriptor, field)
    if descriptor["componentID"] == ORTIE_COMPONENT_ID:
        load_oauth_payload(tree_root, descriptor, field)
    return descriptor
