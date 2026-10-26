#!/usr/bin/env python3
"""Managed raw runtime artifact binding regressions (H6 close).

Covers the strict known-component validator in scripts/runtime_dependency.py
and its three integration points:

  * source/package production — build_packages.build_one refuses a staged
    package whose embedded references/engine-dependency.json drifts from the
    frozen tree descriptor or whose referenced artifact is unsafe;
  * release builder — build_catalog.py --mode release validates the
    descriptor + artifact ONLY from the frozen --source-snapshot (audited X)
    and stages both the validated descriptor bytes (at the frozen
    descriptor path) and the validated raw artifact bytes into the
    publication output (Y), making the output standalone for runtime
    binding in a fresh root;
  * standalone publication checker — check_catalog.py re-binds the published
    package's authenticated descriptor to the published frozen descriptor and
    the actual artifact bytes at Y for BOTH channels, never to a mutable
    candidate HEAD.

Positive coverage uses (a) the real frozen descriptor value and the real
read-only RISC-V binary metadata (never executed) and (b) clearly test-only
synthetic ELF fixtures built inline. No real private keys, no fixture trust
in production, no production feed or qualified-source flags are touched.

Run: python3 -m unittest discover -s tests/catalog -t tests/catalog
"""
import base64
import hashlib
import json
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import hubcore
import fixture_status
import runtime_dependency
import build_packages
from test_publication_integrity import (
    SIGN_ENV, SOURCE_X, ephemeral_key, trust_file, run_script, release_cli,
)

REPO = HERE.parents[2]
REAL_DESCRIPTOR_BYTES = (REPO / "engines" / "impeccable" / "runtime-dependency" /
                         "descriptor.v1.json").read_bytes()
REAL_ARTIFACT_REL = "engines/impeccable/dist/impeccable-0.1.17+floe.1.0.0/" \
                    "riscv64gc-unknown-linux-musl/floe-impeccable"
REAL_ARTIFACT_BYTES = (REPO / REAL_ARTIFACT_REL).read_bytes()

# Clearly test-only synthetic component identity; never a real release.
SYNTHETIC_VERSION = "0.0.0+floe.9.9.9"
SYNTHETIC_TRIPLE = "riscv64gc-unknown-linux-musl"


# --------------------------------------------------------------------------
# pure test-only synthetic fixtures
# --------------------------------------------------------------------------

def synthetic_elf(payload_size=0x800, *, e_type=2, e_machine=243, ei_class=2,
                  ei_data=1, ei_version=1, e_version=1, ehsize=64, phentsize=56,
                  phnum=1, phoff=64, shentsize=64, shnum=0, shoff=0,
                  with_interp=False, ph_offset=0, ph_filesz=None, ph_memsz=None):
    """A minimal ELF64 LE RISC-V EXEC static image (public fixture header).

    Built inline by the test; never downloaded, never executed.
    """
    phdrs = b""
    for index in range(phnum):
        p_type = runtime_dependency.PT_INTERP if (with_interp and index == 0) else 1
        filesz = (ph_filesz if ph_filesz is not None
                  else phoff + phnum * phentsize + payload_size - ph_offset)
        memsz = ph_memsz if ph_memsz is not None else filesz
        phdrs += struct.pack("<IIQQQQQQ", p_type, 5, ph_offset, 0x10000, 0x10000,
                             filesz, memsz, 0x1000)
    ehdr = bytearray(64)
    ehdr[0:4] = b"\x7fELF"
    ehdr[4], ehdr[5], ehdr[6] = ei_class, ei_data, ei_version
    struct.pack_into("<HHI", ehdr, 16, e_type, e_machine, e_version)
    struct.pack_into("<QQQIHHHHHH", ehdr, 24, 0x10000, phoff, shoff, 0,
                     ehsize, phentsize, phnum, shentsize, shnum, 0)
    return bytes(ehdr) + phdrs + b"\0" * payload_size


def synthetic_descriptor(data, version=SYNTHETIC_VERSION,
                         triple=SYNTHETIC_TRIPLE):
    """A descriptor VALUE matching the given synthetic artifact bytes."""
    return {
        "schemaVersion": 1,
        "componentID": "impeccable-engine",
        "componentVersion": version,
        "minimumAppVersion": "1.7.59",
        "target": {"os": "linux", "arch": "riscv64", "triple": triple,
                   "format": "elf64-little-riscv-exec-static"},
        "artifact": {
            "path": runtime_dependency.expected_artifact_path(version, triple),
            "size": len(data),
            "sha256": hubcore.sha256_hex(data),
        },
        "captureContract": {
            "version": 1,
            "sha256": "baf2453164be6162703af9d671be16da152fa874db53ce95ad5b3516d40de4a3",
        },
    }


def base_descriptor():
    return synthetic_descriptor(synthetic_elf())


# --------------------------------------------------------------------------
# descriptor value gate
# --------------------------------------------------------------------------

class TestDescriptorValidation(unittest.TestCase):
    def test_real_frozen_descriptor_value_validates(self):
        descriptor = json.loads(REAL_DESCRIPTOR_BYTES)
        self.assertIs(runtime_dependency.validate_descriptor(descriptor), descriptor)

    def test_synthetic_fixture_descriptor_validates(self):
        runtime_dependency.validate_descriptor(base_descriptor())

    def test_exact_key_set_enforced(self):
        for extra in ("url", "repository", "command", "approval", "environment",
                      "permissions", "notes"):
            with self.subTest(extra=extra):
                descriptor = base_descriptor()
                descriptor[extra] = "x"
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_descriptor(descriptor)
        descriptor = base_descriptor()
        descriptor.pop("captureContract")
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.validate_descriptor(descriptor)

    def test_unknown_component_id_rejected(self):
        descriptor = base_descriptor()
        descriptor["componentID"] = "other-engine"
        with self.assertRaisesRegex(hubcore.HubError, "unknown componentID"):
            runtime_dependency.validate_descriptor(descriptor)

    def test_unknown_target_rejected(self):
        for key, value in (("os", "macos"), ("arch", "x86_64"),
                           ("triple", "x86_64-unknown-linux-gnu"),
                           ("format", "elf64-little-x86_64-exec-static")):
            with self.subTest(key=key):
                descriptor = base_descriptor()
                descriptor["target"][key] = value
                with self.assertRaisesRegex(hubcore.HubError, "allowlist"):
                    runtime_dependency.validate_descriptor(descriptor)

    def test_component_version_strictness(self):
        for bad in ("0.1.17", "0.1.17+floe.1.0", "01.1.17+floe.1.0.0",
                    "0.1.17+floe.01.0.0", "0.1.17+floe.1.0.0-rc1",
                    "v0.1.17+floe.1.0.0", 1):
            with self.subTest(bad=bad):
                descriptor = base_descriptor()
                descriptor["componentVersion"] = bad
                with self.assertRaisesRegex(hubcore.HubError, "componentVersion"):
                    runtime_dependency.validate_descriptor(descriptor)

    def test_minimum_app_version_strictness(self):
        for bad in ("1.7", "01.7.59", "1.7.59-beta", None, 1759):
            with self.subTest(bad=bad):
                descriptor = base_descriptor()
                descriptor["minimumAppVersion"] = bad
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_descriptor(descriptor)

    def test_size_bound_only_for_known_component(self):
        descriptor = base_descriptor()
        descriptor["artifact"]["size"] = 16 * 1024 * 1024
        runtime_dependency.validate_descriptor(descriptor)
        for bad in (0, 16 * 1024 * 1024 + 1, -5, True, "5579704", 5.5):
            with self.subTest(bad=bad):
                descriptor = base_descriptor()
                descriptor["artifact"]["size"] = bad
                with self.assertRaisesRegex(hubcore.HubError, "size"):
                    runtime_dependency.validate_descriptor(descriptor)

    def test_sha256_strict_lowercase(self):
        for bad in ("AF" + "0" * 62, "a" * 63, "g" * 64, "A" * 64, None, 7):
            with self.subTest(bad=str(bad)[:12]):
                descriptor = base_descriptor()
                descriptor["artifact"]["sha256"] = bad
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_descriptor(descriptor)

    def test_capture_contract_supported_version_and_hash(self):
        for version in (0, 2, True, "1"):
            with self.subTest(version=version):
                descriptor = base_descriptor()
                descriptor["captureContract"]["version"] = version
                with self.assertRaisesRegex(hubcore.HubError, "captureContract"):
                    runtime_dependency.validate_descriptor(descriptor)
        descriptor = base_descriptor()
        descriptor["captureContract"]["sha256"] = "B" * 64
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.validate_descriptor(descriptor)

    def test_artifact_path_rejections(self):
        bad_paths = (
            "../evil/floe-impeccable",
            "/engines/impeccable/dist/x/floe-impeccable",
            "engines\\impeccable\\dist\\x\\floe-impeccable",
            "engines/impeccable\0dist/x/floe-impeccable",
            "engines//dist/impeccable-0.0.0+floe.9.9.9/riscv64gc-unknown-linux-musl/floe-impeccable",
            "engines/./impeccable/dist/x/floe-impeccable",
            "engines/impeccable/dist/impeccable-0.0.0+floe.9.9.9/riscv64gc-unknown-linux-musl/not-floe-impeccable",
            "elsewhere/impeccable/dist/impeccable-0.0.0+floe.9.9.9/riscv64gc-unknown-linux-musl/floe-impeccable",
            "",
        )
        for bad in bad_paths:
            with self.subTest(bad=bad[:40]):
                descriptor = base_descriptor()
                descriptor["artifact"]["path"] = bad
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_descriptor(descriptor)

    def test_artifact_path_cross_field_version_drift(self):
        descriptor = base_descriptor()
        drifted = runtime_dependency.expected_artifact_path("0.0.1+floe.9.9.9",
                                                            SYNTHETIC_TRIPLE)
        descriptor["artifact"]["path"] = drifted
        with self.assertRaisesRegex(hubcore.HubError, "disagrees"):
            runtime_dependency.validate_descriptor(descriptor)

    def test_artifact_path_cross_field_triple_drift(self):
        descriptor = base_descriptor()
        descriptor["artifact"]["path"] = runtime_dependency.expected_artifact_path(
            SYNTHETIC_VERSION, "riscv64gc-unknown-linux-gnu")
        with self.assertRaisesRegex(hubcore.HubError, "disagrees"):
            runtime_dependency.validate_descriptor(descriptor)

    def test_nested_extra_keys_rejected(self):
        descriptor = base_descriptor()
        descriptor["target"]["url"] = "https://example.invalid"
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.validate_descriptor(descriptor)
        descriptor = base_descriptor()
        descriptor["artifact"]["repository"] = "https://example.invalid"
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.validate_descriptor(descriptor)
        descriptor = base_descriptor()
        descriptor["captureContract"]["approval"] = True
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.validate_descriptor(descriptor)

    def test_non_object_descriptor_rejected(self):
        for bad in ([], "x", None, 3):
            with self.subTest(bad=bad):
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_descriptor(bad)

    def test_parse_descriptor_rejects_non_json(self):
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.parse_descriptor(b"not json {", "test")

    def test_schema_version_must_be_exact_int_one(self):
        # Python True == 1 and 1.0 == 1: only the actual int 1 may pass.
        for bad in (True, False, 1.0, 0, 2, "1", None):
            with self.subTest(bad=repr(bad)):
                descriptor = base_descriptor()
                descriptor["schemaVersion"] = bad
                with self.assertRaisesRegex(hubcore.HubError, "schemaVersion"):
                    runtime_dependency.validate_descriptor(descriptor)
        self.assertEqual(
            runtime_dependency.validate_descriptor(base_descriptor())["schemaVersion"], 1)

    def test_parse_descriptor_accepts_only_canonical_utf8_bytes(self):
        # Unchanged positives: the exact frozen 563-byte descriptor and the
        # canonical synthetic encoding both parse.
        self.assertEqual(
            runtime_dependency.parse_descriptor(REAL_DESCRIPTOR_BYTES, "test"),
            json.loads(REAL_DESCRIPTOR_BYTES))
        runtime_dependency.parse_descriptor(hubcore.encoded(base_descriptor()), "test")
        canonical = REAL_DESCRIPTOR_BYTES
        value = json.loads(canonical)
        shuffled = dict(reversed(list(value.items())))
        cases = {
            "utf-16": canonical.decode().encode("utf-16"),
            "utf-8 BOM": b"\xef\xbb\xbf" + canonical,
            "invalid UTF-8": b'{"componentID":"\xff\xfe"}',
            "trailing newline": canonical + b"\n",
            "pretty-printed": json.dumps(value, indent=2, sort_keys=True).encode(),
            "unsorted keys": json.dumps(shuffled, separators=(",", ":")).encode(),
            "duplicate schemaVersion key": b'{"schemaVersion":1,' + canonical[1:],
            "bool schemaVersion bytes": canonical.replace(b'"schemaVersion":1',
                                                          b'"schemaVersion":true'),
            "float schemaVersion bytes": canonical.replace(b'"schemaVersion":1',
                                                           b'"schemaVersion":1.0'),
        }
        for label, data in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.parse_descriptor(data, "test")


# --------------------------------------------------------------------------
# raw artifact byte gate (synthetic fixtures + real binary metadata, no exec)
# --------------------------------------------------------------------------

class TestArtifactBytesGate(unittest.TestCase):
    def test_real_binary_validates_read_only(self):
        descriptor = json.loads(REAL_DESCRIPTOR_BYTES)
        runtime_dependency.validate_artifact_bytes(REAL_ARTIFACT_BYTES, descriptor,
                                                   "real-readonly")
        self.assertEqual(len(REAL_ARTIFACT_BYTES), 5579704)

    def test_synthetic_fixture_binary_validates(self):
        data = synthetic_elf()
        runtime_dependency.validate_artifact_bytes(data, synthetic_descriptor(data))

    def test_size_mismatch_rejected(self):
        data = synthetic_elf()
        descriptor = synthetic_descriptor(data)
        descriptor["artifact"]["size"] = len(data) + 1
        with self.assertRaisesRegex(hubcore.HubError, "size mismatch"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_sha_mismatch_rejected(self):
        data = synthetic_elf()
        descriptor = synthetic_descriptor(data)
        descriptor["artifact"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(hubcore.HubError, "sha256 mismatch"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_non_elf_rejected(self):
        data = (b"#!/bin/sh\necho no\n" + b"#" * 64)[:96]
        descriptor = synthetic_descriptor(data)
        with self.assertRaisesRegex(hubcore.HubError, "not an ELF"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_truncated_header_rejected(self):
        data = synthetic_elf()[:32]
        descriptor = synthetic_descriptor(data)
        with self.assertRaises(hubcore.HubError):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_elf_class_data_version_rejected(self):
        for kw in ({"ei_class": 1}, {"ei_data": 2}, {"ei_version": 2}):
            with self.subTest(kw=kw):
                data = synthetic_elf(**kw)
                descriptor = synthetic_descriptor(data)
                with self.assertRaisesRegex(hubcore.HubError, "ELF64 little-endian"):
                    runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_shared_or_pie_rejected(self):
        for e_type in (1, 3):  # REL, DYN
            with self.subTest(e_type=e_type):
                data = synthetic_elf(e_type=e_type)
                descriptor = synthetic_descriptor(data)
                with self.assertRaisesRegex(hubcore.HubError, "EXEC"):
                    runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_wrong_machine_rejected(self):
        data = synthetic_elf(e_machine=62)  # x86-64
        descriptor = synthetic_descriptor(data)
        with self.assertRaisesRegex(hubcore.HubError, "RISC-V"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_pt_interp_rejected(self):
        data = synthetic_elf(with_interp=True, ph_filesz=0)
        descriptor = synthetic_descriptor(data)
        with self.assertRaisesRegex(hubcore.HubError, "PT_INTERP"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_program_header_table_bounded(self):
        cases = (
            {"phnum": 0},
            {"phnum": 0xFFFF},
            {"phnum": 5000},
            {"phoff": 10 ** 7},
        )
        for kw in cases:
            with self.subTest(kw=kw):
                data = synthetic_elf(**kw)
                descriptor = synthetic_descriptor(data)
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_header_shape_strictness(self):
        for kw in ({"ehsize": 52}, {"phentsize": 32}, {"shentsize": 60, "shnum": 2}):
            with self.subTest(kw=kw):
                data = synthetic_elf(**kw)
                descriptor = synthetic_descriptor(data)
                with self.assertRaises(hubcore.HubError):
                    runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_program_header_out_of_file_rejected(self):
        data = synthetic_elf(ph_filesz=10 ** 9)
        descriptor = synthetic_descriptor(data)
        with self.assertRaisesRegex(hubcore.HubError, "outside the file"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_program_header_memsz_smaller_than_filesz_rejected(self):
        data = synthetic_elf(ph_memsz=1)
        descriptor = synthetic_descriptor(data)
        with self.assertRaisesRegex(hubcore.HubError, "memsz"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)

    def test_section_table_out_of_file_rejected(self):
        data = synthetic_elf(shnum=4, shoff=64 + 56 + 0x800 + 10 ** 6)
        descriptor = synthetic_descriptor(data)
        with self.assertRaisesRegex(hubcore.HubError, "section-header table"):
            runtime_dependency.validate_artifact_bytes(data, descriptor)


# --------------------------------------------------------------------------
# unchanged ordinary ZIP gates
# --------------------------------------------------------------------------

class TestOrdinaryZipGatesUnchanged(unittest.TestCase):
    def test_runtime_binary_inside_zip_still_rejected(self):
        files = {
            "SKILL.md": (b"---\nname: impeccable\ndescription: synthetic test\n---\n\nbody\n"),
            "floe.json": hubcore.encoded({
                "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
                "capabilities": [], "tools": [], "platforms": ["ios"],
                "scriptRuntime": "none", "pythonPackages": []}),
            "references/NOTICE.md": b"test\n",
            "references/floe-impeccable": REAL_ARTIFACT_BYTES,
        }
        with self.assertRaisesRegex(hubcore.HubError, "native payload magic"):
            hubcore.validate_package_files(files)

    def test_ordinary_size_limits_unchanged(self):
        self.assertEqual(hubcore.MAX_FILE_BYTES, 2_097_152)
        self.assertEqual(hubcore.MAX_TOTAL_BYTES, 8_388_608)
        self.assertEqual(runtime_dependency.MAX_RUNTIME_ARTIFACT_BYTES,
                         16 * 1024 * 1024)

    def test_descriptor_inside_zip_is_plain_data_not_permission(self):
        # the descriptor may ride inside references/ as data; the manifest of
        # such a package carries no extra capability/tool from it
        files = {
            "SKILL.md": (b"---\nname: impeccable\ndescription: synthetic test\n---\n\nbody\n"),
            "floe.json": hubcore.encoded({
                "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
                "capabilities": [], "tools": [], "platforms": ["ios"],
                "scriptRuntime": "none", "pythonPackages": []}),
            "references/NOTICE.md": b"test\n",
            "references/engine-dependency.json": hubcore.encoded(base_descriptor()),
        }
        manifest, _ = hubcore.validate_package_files(files)
        self.assertEqual(manifest["capabilities"], [])
        self.assertEqual(manifest["tools"], [])


# --------------------------------------------------------------------------
# tree binding: package <-> frozen descriptor <-> artifact at one root
# --------------------------------------------------------------------------

def make_bound_tree(tmp, descriptor_bytes=None, artifact_bytes=None,
                    artifact_rel=None):
    """Temp tree carrying the frozen descriptor + artifact at one root."""
    root = pathlib.Path(tmp)
    descriptor_bytes = (REAL_DESCRIPTOR_BYTES if descriptor_bytes is None
                        else descriptor_bytes)
    artifact_bytes = REAL_ARTIFACT_BYTES if artifact_bytes is None else artifact_bytes
    if artifact_rel is None:
        artifact_rel = json.loads(descriptor_bytes)["artifact"]["path"]
    frozen = root / runtime_dependency.FROZEN_DESCRIPTOR_REL
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(descriptor_bytes)
    artifact = root / artifact_rel
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(artifact_bytes)
    return root, artifact_rel


class TestTreeBinding(unittest.TestCase):
    def test_real_tree_binds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = make_bound_tree(tmp)
            runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)

    def test_missing_frozen_descriptor_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            with self.assertRaisesRegex(hubcore.HubError, "frozen runtime descriptor missing"):
                runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)

    def test_missing_artifact_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact_rel = make_bound_tree(tmp)
            (root / artifact_rel).unlink()
            with self.assertRaisesRegex(hubcore.HubError, "runtime artifact missing"):
                runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)

    def test_tampered_artifact_hash_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact_rel = make_bound_tree(tmp)
            blob = bytearray((root / artifact_rel).read_bytes())
            blob[-1] ^= 0xFF
            (root / artifact_rel).write_bytes(bytes(blob))
            with self.assertRaisesRegex(hubcore.HubError, "sha256 mismatch"):
                runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)

    def test_tampered_artifact_size_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact_rel = make_bound_tree(tmp)
            (root / artifact_rel).write_bytes(REAL_ARTIFACT_BYTES + b"x")
            with self.assertRaisesRegex(hubcore.HubError, "size mismatch"):
                runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)

    def test_embedded_descriptor_drift_from_frozen_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = make_bound_tree(tmp)
            tampered = json.loads(REAL_DESCRIPTOR_BYTES)
            tampered["minimumAppVersion"] = "1.7.60"
            with self.assertRaisesRegex(hubcore.HubError, "differs from the frozen"):
                runtime_dependency.bind_package_descriptor(
                    hubcore.encoded(tampered), root)

    def test_artifact_symlink_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unsupported")
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact_rel = make_bound_tree(tmp)
            target = root / artifact_rel
            real = target.read_bytes()
            target.unlink()
            target.symlink_to(pathlib.Path(tmp) / "elsewhere")
            (pathlib.Path(tmp) / "elsewhere").write_bytes(real)
            with self.assertRaisesRegex(hubcore.HubError, "symbolic link"):
                runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)

    def test_artifact_ancestor_symlink_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unsupported")
        with tempfile.TemporaryDirectory() as tmp:
            root, artifact_rel = make_bound_tree(tmp)
            engines = root / "engines"
            saved = engines.rename(pathlib.Path(tmp) / "engines-real")
            engines.symlink_to(saved, target_is_directory=True)
            with self.assertRaisesRegex(hubcore.HubError, "symbolic link"):
                runtime_dependency.bind_package_descriptor(REAL_DESCRIPTOR_BYTES, root)


# --------------------------------------------------------------------------
# source/package production gate (build_packages)
# --------------------------------------------------------------------------

def stage_impeccable_source(root, descriptor_bytes):
    folder = root / "sources" / "impeccable"
    folder.mkdir(parents=True, exist_ok=True)
    files = {
        "SKILL.md": (b"---\nname: impeccable\ndescription: Synthetic H6 gate test "
                     b"package; not real content.\n---\n\nSynthetic body.\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
            "capabilities": [], "tools": [], "platforms": ["ios"],
            "scriptRuntime": "none", "pythonPackages": []}),
        "references/NOTICE.md": b"Synthetic test notice.\n",
        "references/engine-dependency.json": descriptor_bytes,
    }
    for rel, data in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return files


def impeccable_registry_entry(root):
    registry = json.loads((root / "catalog" / "skills.json").read_bytes())
    return next(e for e in registry["skills"] if e["id"] == "impeccable")


class TestSourcePackageGate(unittest.TestCase):
    def _staged_tree(self, tmp, embedded_descriptor=None):
        # the tree always carries the REAL frozen descriptor + artifact; the
        # staged source may embed a drifted copy to prove the gate fails closed
        root, _ = make_bound_tree(tmp)
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        (root / "catalog").mkdir(exist_ok=True)
        (root / "catalog" / "skills.json").write_bytes(hubcore.encoded(registry))
        stage_impeccable_source(root, embedded_descriptor or REAL_DESCRIPTOR_BYTES)
        return root

    def test_staged_source_with_real_descriptor_and_artifact_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._staged_tree(tmp)
            entry = impeccable_registry_entry(root)
            written = build_packages.build_one("impeccable", entry, True, root=root)
            self.assertTrue(any("impeccable" in path for path in written))

    def test_staged_source_descriptor_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tampered = json.loads(REAL_DESCRIPTOR_BYTES)
            tampered["minimumAppVersion"] = "1.7.60"
            root = self._staged_tree(tmp, embedded_descriptor=hubcore.encoded(tampered))
            entry = impeccable_registry_entry(root)
            with self.assertRaisesRegex(hubcore.HubError, "differs from the frozen"):
                build_packages.build_one("impeccable", entry, True, root=root)

    def test_staged_source_missing_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._staged_tree(tmp)
            (root / REAL_ARTIFACT_REL).unlink()
            entry = impeccable_registry_entry(root)
            with self.assertRaisesRegex(hubcore.HubError, "runtime artifact missing"):
                build_packages.build_one("impeccable", entry, True, root=root)

    def test_staged_source_unsafe_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._staged_tree(tmp)
            (root / REAL_ARTIFACT_REL).write_bytes(
                REAL_ARTIFACT_BYTES[:64] + b"\x03\x00\x00\x00" +
                REAL_ARTIFACT_BYTES[68:])
            entry = impeccable_registry_entry(root)
            with self.assertRaises(hubcore.HubError):
                build_packages.build_one("impeccable", entry, True, root=root)


# --------------------------------------------------------------------------
# release builder + standalone publication checker end-to-end (synthetic)
# --------------------------------------------------------------------------

def synthetic_registry():
    """Registry copy with ONLY impeccable flipped qualified (isolated test)."""
    reg = fixture_status.stage_unadmitted_fixture(
        json.loads((REPO / "catalog" / "skills.json").read_bytes()))
    for entry in reg["skills"]:
        if entry["id"] == "impeccable":
            entry["status"] = dict(entry["status"], licenseChecked=True,
                                   adaptation="frozen", packaged=True,
                                   reviewed=True, qualified=True)
    return reg


def stage_impeccable_tree(tmp, pub_b64, descriptor_bytes, artifact_bytes,
                          artifact_rel):
    """Isolated hub tree with a fully staged, synthetic qualified impeccable."""
    root = pathlib.Path(tmp)
    for name in ("scripts", "schema"):
        shutil.copytree(REPO / name, root / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (root / "docs").mkdir(exist_ok=True)
    shutil.copy(REPO / "docs" / "UPSTREAM-PINS.json", root / "docs")
    fixtures_dst = root / "tests" / "catalog" / "fixtures"
    fixtures_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO / "tests" / "catalog" / "fixtures", fixtures_dst)
    (root / "catalog").mkdir(exist_ok=True)
    (root / "catalog" / "skills.json").write_bytes(hubcore.encoded(synthetic_registry()))
    if pub_b64 is not None:
        (root / "public-key.json").write_bytes(trust_file(pub_b64))
    frozen = root / runtime_dependency.FROZEN_DESCRIPTOR_REL
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(descriptor_bytes)
    artifact = root / artifact_rel
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(artifact_bytes)
    return root


def stage_impeccable_package(root, descriptor_bytes):
    """Deterministic synthetic impeccable archive at both channel paths."""
    files = {
        "SKILL.md": (b"---\nname: impeccable\ndescription: Synthetic H6 publication "
                     b"test package; not real content.\n---\n\nSynthetic body.\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
            "capabilities": [], "tools": [], "platforms": ["ios"],
            "scriptRuntime": "none", "pythonPackages": []}),
        "references/NOTICE.md": b"Synthetic test notice.\n",
        "references/engine-dependency.json": descriptor_bytes,
    }
    hubcore.validate_package_files(files)
    data = hubcore.make_zip(files)
    for channel in ("ios", "android"):
        rel = hubcore.package_path_for("impeccable", "1.0.0", channel)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return files, data


def stage_impeccable_review(root, key, files, data):
    manifest, _ = hubcore.validate_package_files(files)
    record = {
        "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
        "contentDigest": hubcore.content_digest(files),
        "packageSha256": hubcore.sha256_hex(data),
        "reviewedCapabilities": list(manifest["capabilities"]),
        "reviewedTools": list(manifest["tools"]),
        "reviewedPythonPackages": list(manifest["pythonPackages"]),
        "execution": {"os": None, "arch": "n/a", "evidence": "unproven"},
        "reviewStage": "static-content-reviewed",
        "reviewedAt": "2026-10-26",
        "reviewer": "isolated-ephemeral-test-reviewer",
        "decision": "approve",
        "notes": {"en": "Synthetic review for the isolated H6 runtime-binding CLI regression.",
                  "zh-Hans": "仅供隔离 H6 运行时绑定 CLI 回归使用的合成审核记录。"},
    }
    record_bytes = hubcore.encoded(record)
    path = root / "reviews" / "impeccable" / "1.0.0.review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(record_bytes)
    path.with_suffix(path.suffix + ".sig").write_bytes(
        hubcore.sign_envelope(record_bytes, key, hubcore.PRODUCTION_KEY_ID))


def synthetic_runtime_fixture():
    """(descriptor_bytes, artifact_bytes, artifact_rel) test-only fixture."""
    data = synthetic_elf()
    descriptor = synthetic_descriptor(data)
    return hubcore.encoded(descriptor), data, descriptor["artifact"]["path"]


def published_impeccable_repo(tmp):
    """Isolated tree with a fully published synthetic impeccable runtime entry."""
    key, pub, raw = ephemeral_key()
    descriptor_bytes, artifact_bytes, artifact_rel = synthetic_runtime_fixture()
    root = stage_impeccable_tree(tmp, pub, descriptor_bytes, artifact_bytes,
                                 artifact_rel)
    files, data = stage_impeccable_package(root, descriptor_bytes)
    stage_impeccable_review(root, key, files, data)
    snapshot = pathlib.Path(tmp) / "snapshot-x"
    shutil.copytree(root, snapshot, ignore=shutil.ignore_patterns("out"))
    code, out = release_cli(root, snapshot, root / "out", sign_raw=raw)
    assert code == 0, out
    for src in sorted((root / "out").rglob("*")):
        if src.is_file():
            rel = src.relative_to(root / "out")
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, target)
    shutil.rmtree(root / "out")
    shutil.rmtree(snapshot)
    return root, key, descriptor_bytes, artifact_bytes, artifact_rel


class TestReleaseBuilderRuntimeStaging(unittest.TestCase):
    def test_release_stages_frozen_x_artifact_into_y(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _key, descriptor_bytes, artifact_bytes, artifact_rel = \
                published_impeccable_repo(tmp)
            staged = root / artifact_rel
            self.assertTrue(staged.is_file())
            self.assertEqual(staged.read_bytes(), artifact_bytes)
            # the staged bytes are exactly what the descriptor authenticates
            descriptor = json.loads(descriptor_bytes)
            self.assertEqual(len(artifact_bytes), descriptor["artifact"]["size"])
            self.assertEqual(hubcore.sha256_hex(artifact_bytes),
                             descriptor["artifact"]["sha256"])

    def test_release_uses_snapshot_not_mutable_tree(self):
        key, pub, raw = ephemeral_key()
        descriptor_bytes, artifact_bytes, artifact_rel = synthetic_runtime_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_impeccable_tree(tmp, pub, descriptor_bytes,
                                         artifact_bytes, artifact_rel)
            files, data = stage_impeccable_package(root, descriptor_bytes)
            stage_impeccable_review(root, key, files, data)
            snapshot = pathlib.Path(tmp) / "frozen-x"
            shutil.copytree(root, snapshot, ignore=shutil.ignore_patterns("out"))
            first = pathlib.Path(tmp) / "out1"
            code, out = release_cli(root, snapshot, first, sign_raw=raw)
            self.assertEqual(code, 0, out)
            # advance the mutable tree AFTER the freeze: tamper the artifact and
            # write a canonical-but-drifted frozen descriptor at HEAD; the same
            # snapshot X must still produce the exact same validated descriptor
            # + artifact bytes in Y (X binds, never the mutable HEAD Z).
            (root / artifact_rel).write_bytes(synthetic_elf(payload_size=0x900))
            drifted = json.loads(descriptor_bytes)
            drifted["minimumAppVersion"] = "9.9.9"
            (root / runtime_dependency.FROZEN_DESCRIPTOR_REL).write_bytes(
                hubcore.encoded(drifted))
            self.assertNotEqual(
                (root / runtime_dependency.FROZEN_DESCRIPTOR_REL).read_bytes(),
                descriptor_bytes)
            second = pathlib.Path(tmp) / "out2"
            code, out = release_cli(root, snapshot, second, sign_raw=raw)
            self.assertEqual(code, 0, out)
            self.assertNotEqual(str(first.resolve()), str(second.resolve()))
            self.assertEqual((first / artifact_rel).read_bytes(),
                             (second / artifact_rel).read_bytes())
            self.assertEqual((second / artifact_rel).read_bytes(), artifact_bytes)
            self.assertEqual((first / runtime_dependency.FROZEN_DESCRIPTOR_REL).read_bytes(),
                             descriptor_bytes)
            self.assertEqual((second / runtime_dependency.FROZEN_DESCRIPTOR_REL).read_bytes(),
                             descriptor_bytes)

    def test_release_output_is_standalone_for_runtime_binding(self):
        # A fresh output root Y — without any manual descriptor copy and
        # without the candidate tree — must carry BOTH the exact validated
        # frozen descriptor bytes and the raw artifact bytes, and the runtime
        # package must bind against that root alone. Only those two files are
        # staged under engines/: never a full engine-tree copy.
        key, pub, raw = ephemeral_key()
        descriptor_bytes, artifact_bytes, artifact_rel = synthetic_runtime_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_impeccable_tree(tmp, pub, descriptor_bytes,
                                         artifact_bytes, artifact_rel)
            files, data = stage_impeccable_package(root, descriptor_bytes)
            stage_impeccable_review(root, key, files, data)
            snapshot = pathlib.Path(tmp) / "frozen-x"
            shutil.copytree(root, snapshot, ignore=shutil.ignore_patterns("out"))
            out = pathlib.Path(tmp) / "out-root"
            code, output = release_cli(root, snapshot, out, sign_raw=raw)
            self.assertEqual(code, 0, output)
            self.assertEqual((out / runtime_dependency.FROZEN_DESCRIPTOR_REL).read_bytes(),
                             descriptor_bytes)
            self.assertEqual((out / artifact_rel).read_bytes(), artifact_bytes)
            bound = runtime_dependency.bind_package_descriptor(descriptor_bytes, out)
            self.assertEqual(bound, json.loads(descriptor_bytes))
            staged_engine = sorted(str(p.relative_to(out))
                                   for p in (out / "engines").rglob("*") if p.is_file())
            self.assertEqual(staged_engine,
                             sorted([runtime_dependency.FROZEN_DESCRIPTOR_REL,
                                     artifact_rel]))

    def test_release_refuses_snapshot_without_frozen_descriptor(self):
        # The standalone-output guarantee is fail-closed: if the frozen X
        # snapshot carries no descriptor at FROZEN_DESCRIPTOR_REL the build
        # refuses before writing anything.
        key, pub, raw = ephemeral_key()
        descriptor_bytes, artifact_bytes, artifact_rel = synthetic_runtime_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_impeccable_tree(tmp, pub, descriptor_bytes,
                                         artifact_bytes, artifact_rel)
            files, data = stage_impeccable_package(root, descriptor_bytes)
            stage_impeccable_review(root, key, files, data)
            snapshot = pathlib.Path(tmp) / "frozen-x"
            shutil.copytree(root, snapshot, ignore=shutil.ignore_patterns("out"))
            (snapshot / runtime_dependency.FROZEN_DESCRIPTOR_REL).unlink()
            out = pathlib.Path(tmp) / "out"
            code, output = release_cli(root, snapshot, out, sign_raw=raw)
            self.assertNotEqual(code, 0)
            self.assertIn("frozen runtime descriptor missing", output)
            self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_release_refuses_consistent_interp_artifact(self):
        # A PT_INTERP artifact can never reach a signed publication through
        # the release builder: even when descriptor/artifact/package/review
        # are mutually consistent (same size+SHA), the ELF safety gate fails
        # the build before anything is emitted.
        key, pub, raw = ephemeral_key()
        bad = synthetic_elf(with_interp=True, ph_filesz=0)
        descriptor = synthetic_descriptor(bad)
        descriptor_bytes = hubcore.encoded(descriptor)
        artifact_rel = descriptor["artifact"]["path"]
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_impeccable_tree(tmp, pub, descriptor_bytes,
                                         bad, artifact_rel)
            files, data = stage_impeccable_package(root, descriptor_bytes)
            stage_impeccable_review(root, key, files, data)
            snapshot = pathlib.Path(tmp) / "frozen-x"
            shutil.copytree(root, snapshot, ignore=shutil.ignore_patterns("out"))
            out = pathlib.Path(tmp) / "out"
            code, output = release_cli(root, snapshot, out, sign_raw=raw)
            self.assertNotEqual(code, 0)
            self.assertIn("PT_INTERP", output)
            self.assertFalse((out / artifact_rel).exists())
            self.assertFalse((out / "catalog.json").exists())


class TestPublicationRuntimeGate(unittest.TestCase):
    def test_published_runtime_entry_passes_real_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_impeccable_repo(tmp)
            code, out = run_script(root, "check_catalog.py", [])
            self.assertEqual(code, 0, out)

    def test_missing_published_artifact_fails_both_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _k, _d, _a, artifact_rel = published_impeccable_repo(tmp)
            (root / artifact_rel).unlink()
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("ios/impeccable", out)
            self.assertIn("android/impeccable", out)
            self.assertIn("runtime artifact binding failed", out)

    def test_tampered_published_artifact_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _k, _d, artifact_bytes, artifact_rel = published_impeccable_repo(tmp)
            blob = bytearray(artifact_bytes)
            blob[0x100] ^= 0xFF
            (root / artifact_rel).write_bytes(bytes(blob))
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("runtime artifact binding failed", out)

    def test_published_frozen_descriptor_drift_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _k, descriptor_bytes, _a, _r = published_impeccable_repo(tmp)
            tampered = json.loads(descriptor_bytes)
            tampered["minimumAppVersion"] = "1.7.60"
            (root / runtime_dependency.FROZEN_DESCRIPTOR_REL).write_bytes(
                hubcore.encoded(tampered))
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("differs from the frozen", out)

    def test_publication_checker_uses_same_elf_gate(self):
        # bind_package_descriptor (release builder AND publication checker)
        # rejects an interpreter-bearing artifact even when every digest is
        # internally consistent — proven here at the published-tree level.
        with tempfile.TemporaryDirectory() as tmp:
            bad = synthetic_elf(with_interp=True, ph_filesz=0)
            descriptor = synthetic_descriptor(bad)
            root, _ = make_bound_tree(tmp,
                                      descriptor_bytes=hubcore.encoded(descriptor),
                                      artifact_bytes=bad,
                                      artifact_rel=descriptor["artifact"]["path"])
            with self.assertRaisesRegex(hubcore.HubError, "PT_INTERP"):
                runtime_dependency.bind_package_descriptor(
                    hubcore.encoded(descriptor), root)

    def test_tampered_embedded_descriptor_still_breaks_digest_chain(self):
        # an attacker editing the descriptor inside the ZIP changes the archive
        # bytes: the signed feed's sha256/contentDigest and the review chain
        # reject it before the runtime gate is even reached.
        with tempfile.TemporaryDirectory() as tmp:
            root, _k, descriptor_bytes, _a, _r = published_impeccable_repo(tmp)
            tampered = json.loads(descriptor_bytes)
            tampered["minimumAppVersion"] = "1.7.60"
            files = {
                "SKILL.md": (b"---\nname: impeccable\ndescription: Synthetic H6 "
                             b"publication test package; not real content.\n---\n\n"
                             b"Synthetic body.\n"),
                "floe.json": hubcore.encoded({
                    "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
                    "capabilities": [], "tools": [], "platforms": ["ios"],
                    "scriptRuntime": "none", "pythonPackages": []}),
                "references/NOTICE.md": b"Synthetic test notice.\n",
                "references/engine-dependency.json": hubcore.encoded(tampered),
            }
            data = hubcore.make_zip(files)
            for channel in ("ios", "android"):
                rel = hubcore.package_path_for("impeccable", "1.0.0", channel)
                (root / rel).write_bytes(data)
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertTrue("sha256" in out or "contentDigest" in out, out)


class TestXPinnedYRuntimePublication(unittest.TestCase):
    """Git-level X -> Y publication with the runtime artifact pinned at Y."""

    def git(self, root, *args):
        proc = subprocess.run(["git", "-c", "user.name=H6PublicationTest",
                               "-c", "user.email=h6-test@invalid", "-C", str(root)]
                              + list(args), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def fetch_at(self, repo, rev, dest):
        archive = subprocess.run(["git", "-C", str(repo), "archive", rev],
                                 capture_output=True)
        self.assertEqual(archive.returncode, 0, archive.stderr.decode())
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout,
                       check=True)
        return dest

    def test_pinned_fetch_at_y_verifies_runtime_regardless_of_mutable_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "hub"
            repo.mkdir()
            key, pub, raw = ephemeral_key()
            descriptor_bytes, artifact_bytes, artifact_rel = \
                synthetic_runtime_fixture()
            root = stage_impeccable_tree(str(repo), pub, descriptor_bytes,
                                         artifact_bytes, artifact_rel)
            files, data = stage_impeccable_package(root, descriptor_bytes)
            stage_impeccable_review(root, key, files, data)
            self.git(root, "init", "-q", "-b", "main")
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "audited source X")
            x = self.git(root, "rev-parse", "HEAD")
            snapshot = self.fetch_at(repo, x, pathlib.Path(tmp) / "snapshot-x")
            staging = pathlib.Path(tmp) / "staging"
            code, out = release_cli(repo, snapshot, staging, sign_raw=raw,
                                    source_commit=x)
            self.assertEqual(code, 0, out)
            for src in sorted(staging.rglob("*")):
                if src.is_file():
                    rel = src.relative_to(staging)
                    target = repo / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, target)
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "published artifacts Y")
            y = self.git(root, "rev-parse", "HEAD")
            self.assertNotEqual(x, y)
            self.git(root, "merge-base", "--is-ancestor", x, y)
            fetch_y = self.fetch_at(repo, y, pathlib.Path(tmp) / "fetch-y")
            self.assertEqual((fetch_y / artifact_rel).read_bytes(), artifact_bytes)
            code, out = run_script(fetch_y, "check_catalog.py", [])
            self.assertEqual(code, 0, out)
            # advance the mutable head: tamper the artifact + descriptor at Z;
            # the pinned Y fetch keeps verifying, the tampered HEAD tree fails.
            (repo / artifact_rel).write_bytes(
                synthetic_elf(payload_size=len(artifact_bytes) - 64 - 56))
            drifted = json.loads(descriptor_bytes)
            drifted["minimumAppVersion"] = "1.7.60"
            (repo / runtime_dependency.FROZEN_DESCRIPTOR_REL).write_bytes(
                hubcore.encoded(drifted))
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "mutable head tamper Z")
            code, out = run_script(fetch_y, "check_catalog.py", [])
            self.assertEqual(code, 0, out)  # pinned Y verification is standalone
            head_fetch = self.fetch_at(repo, self.git(root, "rev-parse", "HEAD"),
                                       pathlib.Path(tmp) / "fetch-head")
            code, out = run_script(head_fetch, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("runtime artifact binding failed", out)


if __name__ == "__main__":
    unittest.main()
