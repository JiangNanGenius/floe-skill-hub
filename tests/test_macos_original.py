#!/usr/bin/env python3
"""Focused contract tests for scripts/macos_original.py.

These tests pin the macOS original author contract, not incidental
implementation details:

  * the canonical digest is the frozen path-sorted four-field recipe (bytes
    excluded, compact UTF-8, unescaped Unicode, no trailing newline);
  * exact feed/entry/file field sets, limits, safe NFC paths, strict versions,
    bilingual client caps and 100644/100755 modes fail closed;
  * staged bytes, executable bits, symlinks and undeclared files are checked
    against the declaration, and the package stays inside its id directory;
  * a same (id, version) history entry may never change its upstream commit,
    repository/subdirectory or file identity, while a new version is allowed
    (including an honest commit-only advance whose digest is unchanged);
  * the producer fetches a pinned Git commit read-only, refuses symlinks and
    never executes upstream content, and writes a proposal without a
    minimumAppVersion instead of a signable feed;
  * finalize refuses a missing/0.0.0 floor and writes nothing until every feed
    and every history check passes;
  * a positive feed and a targeted negative agree with the exact committed App
    validator ``FloeMacBridge/scripts/validate_original_catalog.py`` at App
    commit 55457ad5 (sha256 72a1c570...), when that immutable file is present.

The Main-validator comparison is skipped with an explicit reason when the
pinned App checkout is unavailable; it is not silently replaced by a copy.
No signing, publication, installation, execution or runtime claims are made.

Run:
    python3 tests/test_macos_original.py
"""
import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
APP_ROOT = HERE.parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import macos_original as mo  # noqa: E402

PINNED_MAIN_VALIDATOR = "72a1c570f4a5438a78aadc53dafd9e7559449b228470ff2249f951bf90f5b60b"
HEX40 = "a" * 40
HEX64 = "b" * 64
GIT_ENV = None


def digest_of(files):
    """Independent literal implementation of the frozen digest recipe."""
    manifest = [
        {"path": f["path"], "sourcePath": f["sourcePath"], "sha256": f["sha256"], "mode": f["mode"]}
        for f in files
    ]
    payload = json.dumps(
        sorted(manifest, key=lambda row: row["path"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_stage(tmp, skill_id, files):
    """files: {package path: (bytes, mode)} -> source_root/<id>/<path>."""
    root = pathlib.Path(tmp) / "stage"
    for path, (data, mode) in files.items():
        target = root / skill_id / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        os.chmod(target, mode)
    return root


def build_entry(
    tmp,
    *,
    skill_id="demo-skill",
    version="1.0.0",
    subdirectory="skills/demo",
    license_path="LICENSE",
    license_source="LICENSE",
    floor="1.7.99",
    files=None,
    commit=HEX40,
):
    files = files or {
        "SKILL.md": (b"---\nname: demo\n---\n\nDo the thing.\n", 0o644),
        "scripts/run.sh": (b"#!/bin/sh\necho hello\n", 0o755),
        license_path: (b"MIT License\n\nPermission is hereby granted.\n", 0o644),
    }
    root = write_stage(tmp, skill_id, files)
    rows = []
    for path in sorted(files):
        data, mode = files[path]
        source_path = license_source if path == license_path else (
            (subdirectory + "/" + path) if subdirectory else path
        )
        rows.append(
            {
                "path": path,
                "sourcePath": source_path,
                "sha256": sha(data),
                "bytes": len(data),
                "mode": "100755" if mode & 0o111 else "100644",
            }
        )
    entry = {
        "id": skill_id,
        "name": {"en": "Demo Skill", "zh-Hans": "演示技能"},
        "description": {"en": "A demo.", "zh-Hans": "一个演示。"},
        "category": "productivity-organization",
        "version": version,
        "minimumAppVersion": floor,
        "repository": "acme/demo",
        "subdirectory": subdirectory,
        "commit": commit,
        "license": "MIT",
        "licensePath": license_path,
        "digest": digest_of(rows),
        "files": rows,
    }
    return entry, root


def feed_of(*entries):
    return {"schemaVersion": 1, "channel": "macos-original", "entries": list(entries)}


def dump_feed(document):
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def git(repo, *arguments):
    global GIT_ENV
    command = [
        "git",
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
    ] + list(arguments)
    result = subprocess.run(command, cwd=str(repo), env=GIT_ENV, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError("git %s failed: %s" % (" ".join(arguments), result.stderr))
    return result.stdout.strip()


def git_fixture(tmp):
    global GIT_ENV
    home = pathlib.Path(tmp) / "git-home"
    home.mkdir(exist_ok=True)
    GIT_ENV = dict(os.environ)
    GIT_ENV.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    repo = pathlib.Path(tmp) / "upstream"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    return repo


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def find_main_validator():
    candidates = []
    override = os.environ.get("FLOE_MAIN_VALIDATOR")
    if override:
        candidates.append(pathlib.Path(override))
    candidates.append(APP_ROOT / "FloeAgent/FloeMacBridge/scripts/validate_original_catalog.py")
    worktrees = APP_ROOT / "Local/Worktrees"
    if worktrees.is_dir():
        candidates.extend(sorted(worktrees.glob("*/FloeMacBridge/scripts/validate_original_catalog.py")))
    for candidate in candidates:
        if candidate.is_file():
            observed = sha(candidate.read_bytes())
            if observed == PINNED_MAIN_VALIDATOR:
                return candidate
    return None


class DigestTests(unittest.TestCase):
    def test_literal_recipe_and_bytes_excluded(self):
        files = [
            {"path": "SKILL.md", "sourcePath": "skills/x/SKILL.md", "sha256": "c" * 64, "bytes": 10, "mode": "100644"},
        ]
        expected = hashlib.sha256(
            b'[{"mode":"100644","path":"SKILL.md","sha256":"' + b"c" * 64 + b'","sourcePath":"skills/x/SKILL.md"}]'
        ).hexdigest()
        self.assertEqual(mo.canonical_manifest_digest(files), expected)
        changed_bytes = [dict(files[0], bytes=999)]
        self.assertEqual(mo.canonical_manifest_digest(changed_bytes), expected)
        self.assertEqual(mo.canonical_manifest_digest(files), expected)

    def test_sorted_and_unicode_unescaped_and_no_newline(self):
        files = [
            {"path": "z/SKILL.md", "sourcePath": "s/z/SKILL.md", "sha256": "1" * 64, "mode": "100644"},
            {"path": "a/SKILL.md", "sourcePath": "s/a/SKILL.md", "sha256": "2" * 64, "mode": "100755"},
        ]
        expected_payload = (
            '[{"mode":"100755","path":"a/SKILL.md","sha256":"' + "2" * 64 + '","sourcePath":"s/a/SKILL.md"},'
            '{"mode":"100644","path":"z/SKILL.md","sha256":"' + "1" * 64 + '","sourcePath":"s/z/SKILL.md"}]'
        ).encode("utf-8")
        self.assertEqual(mo.canonical_manifest_digest(files), hashlib.sha256(expected_payload).hexdigest())
        unicode_row = [
            {"path": "réf/SKILL.md", "sourcePath": "s/réf/SKILL.md", "sha256": "3" * 64, "mode": "100644"}
        ]
        encoded = json.dumps(
            [{"mode": "100644", "path": "réf/SKILL.md", "sha256": "3" * 64, "sourcePath": "s/réf/SKILL.md"}],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(mo.canonical_manifest_digest(unicode_row), hashlib.sha256(encoded).hexdigest())
        self.assertNotIn(b"\\u", encoded)

    def test_rejects_bad_rows_and_does_not_mutate(self):
        good = {"path": "SKILL.md", "sourcePath": "SKILL.md", "sha256": "d" * 64, "mode": "100644"}
        original = copy.deepcopy(good)
        mo.canonical_manifest_digest([good])
        self.assertEqual(good, original)
        for bad in (
            [dict(good, path="/SKILL.md")],
            [dict(good, path="a/../b")],
            [dict(good, path="a//b")],
            [dict(good, path="bad\nname")],
            [dict(good, mode="120000")],
            [dict(good, sha256="D" * 64)],
            [good, good],
        ):
            with self.assertRaises(mo.MacOriginalError):
                mo.canonical_manifest_digest(bad)
        with self.assertRaises(mo.MacOriginalError):
            mo.canonical_manifest_digest([])
        with self.assertRaises(mo.MacOriginalError):
            mo.canonical_manifest_digest({"path": "x"})


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.entry, self.root = build_entry(self.tmp.name)

    def test_positive(self):
        self.assertEqual(mo.validate_catalog(feed_of(self.entry)), 1)
        self.assertEqual(mo.validate_catalog(feed_of(self.entry), self.root), 1)

    def test_feed_fields_and_types(self):
        cases = [
            {"schemaVersion": 1, "channel": "macos-original"},
            dict(feed_of(self.entry), extra=1),
            dict(feed_of(self.entry), schemaVersion=True),
            dict(feed_of(self.entry), schemaVersion="1"),
            dict(feed_of(self.entry), schemaVersion=1.0),
            dict(feed_of(self.entry), channel="ios"),
            dict(feed_of(self.entry), entries=[]),
            dict(feed_of(self.entry), entries=self.entry),
        ]
        for document in cases:
            with self.assertRaises(mo.MacOriginalError):
                mo.validate_catalog(document)

    def test_entry_identity_gates(self):
        mutations = {
            "id trailing dash": {"id": "demo-"},
            "id double dash": {"id": "de--mo"},
            "id uppercase": {"id": "Demo"},
            "name empty": {"name": {"en": " ", "zh-Hans": "演示"}},
            "name long": {"name": {"en": "x" * 129, "zh-Hans": "演示"}},
            "name extra": {"name": {"en": "x", "zh-Hans": "y", "fr": "z"}},
            "category": {"category": "other"},
            "version short": {"version": "1.0"},
            "version leading zero": {"version": "01.0.0"},
            "version suffix": {"version": "1.0.0-rc1"},
            "floor zero": {"minimumAppVersion": "0.0.0"},
            "floor missing": {"minimumAppVersion": "1.0"},
            "repository one": {"repository": "acme"},
            "repository three": {"repository": "a/b/c"},
            "repository empty component": {"repository": "acme/"},
            "subdirectory absolute": {"subdirectory": "/skills"},
            "subdirectory backslash": {"subdirectory": "skills\\demo"},
            "subdirectory dotdot": {"subdirectory": "skills/../demo"},
            "subdirectory long": {"subdirectory": "a/" * 600},
            "commit short": {"commit": "a" * 39},
            "commit uppercase": {"commit": "A" * 40},
            "license empty": {"license": "  "},
            "license long": {"license": "L" * 257},
            "license control": {"license": "MIT\n"},
            "licensePath unsafe": {"licensePath": "../LICENSE"},
            "digest short": {"digest": "c" * 63},
            "digest uppercase": {"digest": "C" * 64},
        }
        for label, change in mutations.items():
            with self.subTest(label=label):
                entry = copy.deepcopy(self.entry)
                entry.update(change)
                with self.assertRaises(mo.MacOriginalError):
                    mo.validate_catalog(feed_of(entry))

    def test_duplicate_id_and_bad_entry_shape(self):
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry, copy.deepcopy(self.entry)))
        extra = copy.deepcopy(self.entry)
        extra["extra"] = 1
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(extra))
        missing = copy.deepcopy(self.entry)
        del missing["license"]
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(missing))
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry, "not an entry"))

    def test_file_gates(self):
        def mutate(function):
            entry = copy.deepcopy(self.entry)
            function(entry)
            entry["digest"] = digest_of(entry["files"])
            with self.assertRaises(mo.MacOriginalError):
                mo.validate_catalog(feed_of(entry))

        mutate(lambda e: e.update(files=[]))
        mutate(lambda e: e["files"][0].update(extra=1))
        missing_mode = copy.deepcopy(self.entry)
        missing_mode["files"][0].pop("mode")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(missing_mode))
        mutate(lambda e: e["files"][0].update(path="/etc/passwd"))
        mutate(lambda e: e["files"][0].update(path="a/../b"))
        mutate(lambda e: e["files"][0].update(path="bad\\name"))
        mutate(lambda e: e["files"][0].update(path="bad\x00name"))
        mutate(lambda e: next(row for row in e["files"] if row["path"] == "SKILL.md").update(sourcePath="other/SKILL.md"))
        mutate(lambda e: e["files"][0].update(sha256="D" * 64))
        mutate(lambda e: e["files"][0].update(bytes=True))
        mutate(lambda e: e["files"][0].update(bytes=-1))
        mutate(lambda e: e["files"][0].update(bytes=16 * 1024 * 1024 + 1))
        mutate(lambda e: e["files"][0].update(mode="120000"))
        mutate(lambda e: e["files"].append(dict(e["files"][0])))
        mutate(lambda e: e.update(licensePath="NOT-THERE"))

    def test_license_root_copy_exception_and_non_license_mismatch(self):
        entry = copy.deepcopy(self.entry)
        self.assertEqual(entry["files"][0]["path"], "LICENSE")
        self.assertEqual(entry["files"][0]["sourcePath"], "LICENSE")
        self.assertEqual(mo.validate_catalog(feed_of(entry), self.root), 1)
        entry = copy.deepcopy(self.entry)
        skill = next(row for row in entry["files"] if row["path"] == "SKILL.md")
        skill["sourcePath"] = "elsewhere/SKILL.md"
        entry["digest"] = digest_of(entry["files"])
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(entry))

    def test_package_total_and_required_files(self):
        entry = copy.deepcopy(self.entry)
        for row in entry["files"]:
            row["bytes"] = 16 * 1024 * 1024
        entry["digest"] = digest_of(entry["files"])
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(entry))
        entry = copy.deepcopy(self.entry)
        entry["files"] = [row for row in entry["files"] if row["path"] != "SKILL.md"]
        entry["digest"] = digest_of(entry["files"])
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(entry))

    def test_digest_mismatch(self):
        entry = copy.deepcopy(self.entry)
        entry["digest"] = "0" * 64
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(entry))

    def test_inputs_are_not_mutated(self):
        document = feed_of(self.entry)
        previous = feed_of(copy.deepcopy(self.entry))
        before_document = copy.deepcopy(document)
        before_previous = copy.deepcopy(previous)
        mo.validate_catalog(document, self.root, [previous])
        self.assertEqual(document, before_document)
        self.assertEqual(previous, before_previous)


class StagedSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.entry, self.root = build_entry(self.tmp.name)

    def test_bytes_and_mode_mismatch(self):
        (self.root / "demo-skill/scripts/run.sh").write_bytes(b"changed\n")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), self.root)
        self.entry, self.root = build_entry(self.tmp.name + "-2")
        os.chmod(self.root / "demo-skill/scripts/run.sh", 0o644)
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), self.root)

    def test_missing_extra_and_symlink(self):
        os.unlink(self.root / "demo-skill/scripts/run.sh")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), self.root)

        self.entry, self.root = build_entry(self.tmp.name + "-3")
        (self.root / "demo-skill/EXTRA.md").write_bytes(b"extra")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), self.root)

        self.entry, self.root = build_entry(self.tmp.name + "-4")
        os.symlink("SKILL.md", self.root / "demo-skill/link")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), self.root)

        self.entry, self.root = build_entry(self.tmp.name + "-5")
        os.symlink("..", self.root / "demo-skill/dir-link")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), self.root)

    def test_id_directory_missing_or_symlink(self):
        empty = pathlib.Path(self.tmp.name + "-empty")
        empty.mkdir()
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), empty)
        linked = pathlib.Path(self.tmp.name + "-linked")
        linked.mkdir()
        outside = pathlib.Path(self.tmp.name + "-outside")
        outside.mkdir()
        os.symlink(outside, linked / "demo-skill")
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.entry), linked)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.first, self.root = build_entry(self.tmp.name)
        self.second = copy.deepcopy(self.first)
        self.second["version"] = "1.0.1"
        self.second["commit"] = "e" * 40
        self.second["files"][0]["sha256"] = "f" * 64
        self.second["digest"] = digest_of(self.second["files"])

    def test_same_identity_passes_and_new_version_passes(self):
        self.assertEqual(mo.validate_catalog(feed_of(self.first), previous_catalogs=[feed_of(self.first)]), 1)
        self.assertEqual(mo.validate_catalog(feed_of(self.second), previous_catalogs=[feed_of(self.first)]), 1)

    def test_same_version_changes_fail(self):
        changes = [
            ("commit", {"commit": "1" * 40}),
            ("repository", {"repository": "other/repo"}),
            ("subdirectory", {"subdirectory": "skills/other"}),
            ("sourcePath", {"files": None}),
            ("bytes", {"files": None}),
            ("mode", {"files": None}),
            ("path", {"files": None}),
        ]
        for label, change in changes:
            with self.subTest(label=label):
                current = copy.deepcopy(self.first)
                if "files" not in change:
                    current.update(change)
                else:
                    if label == "sourcePath":
                        current["files"][0]["sourcePath"] = "other/LICENSE"
                    elif label == "bytes":
                        current["files"][0]["bytes"] += 1
                    elif label == "mode":
                        current["files"][0]["mode"] = "100755"
                    elif label == "path":
                        current["files"][0]["path"] = "LICENSE.txt"
                        current["licensePath"] = "LICENSE.txt"
                    current["digest"] = digest_of(current["files"])
                with self.assertRaises(mo.MacOriginalError):
                    mo.validate_catalog(feed_of(current), previous_catalogs=[feed_of(self.first)])

    def test_metadata_may_change_but_identity_may_not(self):
        current = copy.deepcopy(self.first)
        current["name"] = {"en": "Renamed", "zh-Hans": "改名"}
        current["minimumAppVersion"] = "1.8.0"
        self.assertEqual(mo.validate_catalog(feed_of(current), previous_catalogs=[feed_of(self.first)]), 1)
        current["license"] = "Apache-2.0"
        self.assertEqual(mo.validate_catalog(feed_of(current), previous_catalogs=[feed_of(self.first)]), 1)

    def test_invalid_or_conflicting_history_fails(self):
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.first), previous_catalogs=[{"bad": "feed"}])
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(feed_of(self.first), previous_catalogs={"bad": "not a sequence"})
        conflict = copy.deepcopy(self.first)
        conflict["commit"] = "2" * 40
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(
                feed_of(self.first), previous_catalogs=[feed_of(self.first), feed_of(conflict)]
            )

    def test_empty_previous_and_duplicate_previous(self):
        self.assertEqual(mo.validate_catalog(feed_of(self.first), previous_catalogs=[]), 1)
        self.assertEqual(
            mo.validate_catalog(feed_of(self.first), previous_catalogs=[feed_of(self.first), feed_of(self.first)]),
            1,
        )


@unittest.skipUnless(shutil.which("git"), "git is required for producer tests")
class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = git_fixture(self.tmp.name)
        (self.repo / "LICENSE").write_bytes(b"MIT License\n\nPermission is hereby granted.\n")
        (self.repo / "skills/demo").mkdir(parents=True)
        (self.repo / "skills/demo/SKILL.md").write_bytes(b"---\nname: demo\n---\n\nDo the thing.\n")
        (self.repo / "skills/demo/scripts").mkdir()
        (self.repo / "skills/demo/scripts/run.sh").write_bytes(b"#!/bin/sh\necho hello\n")
        os.chmod(self.repo / "skills/demo/scripts/run.sh", 0o755)
        self.first = commit_all(self.repo, "first")

    def spec(self, commit, version="1.0.0", **changes):
        spec = {
            "id": "demo-skill",
            "name": {"en": "Demo Skill", "zh-Hans": "演示技能"},
            "description": {"en": "A demo.", "zh-Hans": "一个演示。"},
            "category": "productivity-organization",
            "version": version,
            "repository": "acme/demo",
            "subdirectory": "skills/demo",
            "commit": commit,
            "license": "MIT",
            "licensePath": "LICENSE",
            "licenseSourcePath": "LICENSE",
        }
        spec.update(changes)
        return spec

    def test_prepare_writes_proposal_not_feed(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        path, proposal = mo.prepare_proposal(
            self.spec(self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        self.assertTrue(path.is_file())
        self.assertEqual(proposal["kind"], "macos-original-proposal")
        self.assertNotIn("minimumAppVersion", proposal["entry"])
        self.assertFalse(list(output.rglob("*.catalog.json")))
        provenance = json.loads((path.parent / "provenance.json").read_text())
        self.assertEqual(provenance["commit"], self.first)
        self.assertEqual(provenance["licenseSourcePath"], "LICENSE")
        self.assertIn("refs/remotes/origin/", " ".join(provenance["branchRefs"]))
        staged = path.parent / "source/demo-skill"
        self.assertTrue((staged / "SKILL.md").is_file())
        self.assertTrue(os.stat(staged / "scripts/run.sh").st_mode & 0o111)
        self.assertFalse(os.stat(staged / "SKILL.md").st_mode & 0o111)
        skill_row = next(row for row in provenance["files"] if row["path"] == "SKILL.md")
        self.assertEqual(skill_row["gitBlob"], git(self.repo, "rev-parse", "HEAD:skills/demo/SKILL.md"))

    def test_prepare_never_executes_upstream_content(self):
        marker = pathlib.Path(self.tmp.name) / "EXECUTED"
        (self.repo / "skills/demo/scripts/trap.sh").write_bytes(
            ("#!/bin/sh\ntouch %s\n" % marker).encode()
        )
        os.chmod(self.repo / "skills/demo/scripts/trap.sh", 0o755)
        commit = commit_all(self.repo, "trap")
        output = pathlib.Path(self.tmp.name) / "candidate"
        mo.prepare_proposal(
            self.spec(commit, version="1.0.1", expectAncestor=self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        self.assertFalse(marker.exists())

    def test_prepare_refuses_ancestry_and_missing_license(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        not_ancestor = "3" * 40
        with self.assertRaises(mo.MacOriginalError):
            mo.prepare_proposal(
                self.spec(self.first, expectAncestor=not_ancestor),
                output,
                source_url="file://" + str(self.repo),
            )
        no_license = self.spec(self.first, licenseSourcePath="LICENSE")
        (self.repo / "LICENSE").unlink()
        commit = commit_all(self.repo, "drop license")
        no_license["commit"] = commit
        with self.assertRaises(mo.MacOriginalError):
            mo.prepare_proposal(no_license, output, source_url="file://" + str(self.repo))
        self.assertFalse(output.exists() and any(output.iterdir()))

    def test_prepare_refuses_floor_in_spec_and_existing_output(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        with self.assertRaises(mo.MacOriginalError):
            mo.prepare_proposal(
                self.spec(self.first, minimumAppVersion="1.7.99"),
                output,
                source_url="file://" + str(self.repo),
            )
        mo.prepare_proposal(
            self.spec(self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        with self.assertRaises(mo.MacOriginalError):
            mo.prepare_proposal(
                self.spec(self.first),
                output,
                source_url="file://" + str(self.repo),
            )

    def test_prepare_refuses_symlink_and_prefix_collision(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        (self.repo / "skills/xy").mkdir()
        (self.repo / "skills/xy/evil.md").write_bytes(b"evil")
        os.symlink("SKILL.md", self.repo / "skills/demo/link")
        commit = commit_all(self.repo, "symlink")
        with self.assertRaises(mo.MacOriginalError):
            mo.prepare_proposal(
                self.spec(commit, version="1.0.1", expectAncestor=self.first),
                output,
                source_url="file://" + str(self.repo),
            )
        (self.repo / "skills/demo/link").unlink()
        commit = commit_all(self.repo, "no symlink")
        path, proposal = mo.prepare_proposal(
            self.spec(commit, version="1.0.1", expectAncestor=self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        self.assertNotIn("evil.md", [row["path"] for row in proposal["entry"]["files"]])

    def test_finalize_and_history(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        # Commit-only advance: the skill tree is byte-identical.
        (self.repo / "README.md").write_bytes(b"unrelated change\n")
        second = commit_all(self.repo, "unrelated")
        p1, _ = mo.prepare_proposal(
            self.spec(self.first, version="1.0.0"),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        p2, proposal2 = mo.prepare_proposal(
            self.spec(second, version="1.0.1", expectAncestor=self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        self.assertEqual(
            proposal2["entry"]["digest"],
            json.loads(p1.read_text())["entry"]["digest"],
        )
        feeds = pathlib.Path(self.tmp.name) / "feeds"
        written = mo.finalize([p2, p1], "1.7.99", output_dir=feeds)
        self.assertEqual([item[3] for item in written], ["1.0.0", "1.0.1"])
        feed1 = json.loads((feeds / "demo-skill-1.0.0.catalog.json").read_text())
        feed2 = json.loads((feeds / "demo-skill-1.0.1.catalog.json").read_text())
        self.assertEqual(feed1["entries"][0]["digest"], feed2["entries"][0]["digest"])
        self.assertNotEqual(feed1["entries"][0]["commit"], feed2["entries"][0]["commit"])
        self.assertEqual(mo.validate_catalog(feed2, previous_catalogs=[feed1]), 1)
        with self.assertRaises(mo.MacOriginalError):
            mo.finalize([p1, p2], "0.0.0", output_dir=feeds)
        with self.assertRaises(mo.MacOriginalError):
            mo.finalize([p1, p2], "1.7.99", output=feeds / "single.json")

    def test_finalize_refuses_tampered_provenance_and_writes_nothing(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        p1, _ = mo.prepare_proposal(
            self.spec(self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        provenance_path = p1.parent / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["digest"] = "0" * 64
        provenance_path.write_text(json.dumps(provenance))
        feeds = pathlib.Path(self.tmp.name) / "feeds"
        with self.assertRaises(mo.MacOriginalError):
            mo.finalize([p1], "1.7.99", output_dir=feeds)
        self.assertFalse(feeds.exists() and any(feeds.iterdir()))

    def test_finalize_mixed_ids_and_duplicate_versions(self):
        output = pathlib.Path(self.tmp.name) / "candidate"
        p1, _ = mo.prepare_proposal(
            self.spec(self.first),
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        with self.assertRaises(mo.MacOriginalError):
            mo.finalize([p1, p1], "1.7.99", output_dir=pathlib.Path(self.tmp.name) / "feeds")
        other_spec = self.spec(self.first, version="2.0.0")
        other_spec["id"] = "other-skill"
        p2, _ = mo.prepare_proposal(
            other_spec,
            output,
            source_url="file://" + str(self.repo),
            fetched_at="2026-10-29T00:00:00Z",
        )
        with self.assertRaises(mo.MacOriginalError):
            mo.finalize([p1, p2], "1.7.99", output_dir=pathlib.Path(self.tmp.name) / "feeds")


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = find_main_validator()
        if cls.validator is None:
            raise unittest.SkipTest(
                "exact App validator (sha256 %s) is not present; set FLOE_MAIN_VALIDATOR"
                % PINNED_MAIN_VALIDATOR
            )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.entry, self.root = build_entry(self.tmp.name)
        self.feed_path = pathlib.Path(self.tmp.name) / "catalog.json"
        self.feed_path.write_bytes(dump_feed(feed_of(self.entry)))

    def run_main(self, *arguments):
        return subprocess.run(
            [sys.executable, str(self.validator)] + [str(argument) for argument in arguments],
            capture_output=True,
            text=True,
        )

    def test_positive_with_and_without_staged_source(self):
        result = self.run_main(self.feed_path, "--source-root", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 macOS-original declarations", result.stdout)
        result = self.run_main(self.feed_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mo.validate_catalog(json.loads(self.feed_path.read_text()), self.root), 1)

    def test_targeted_negative_digest(self):
        document = json.loads(self.feed_path.read_text())
        document["entries"][0]["digest"] = "0" * 64
        self.feed_path.write_bytes(dump_feed(document))
        result = self.run_main(self.feed_path)
        self.assertNotEqual(result.returncode, 0)
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(document, self.root)

    def test_targeted_negative_staged_bytes(self):
        target = self.root / "demo-skill/SKILL.md"
        target.write_bytes(b"tampered")
        result = self.run_main(self.feed_path, "--source-root", self.root)
        self.assertNotEqual(result.returncode, 0)
        with self.assertRaises(mo.MacOriginalError):
            mo.validate_catalog(json.loads(self.feed_path.read_text()), self.root)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.entry, self.root = build_entry(self.tmp.name)
        self.feed = pathlib.Path(self.tmp.name) / "catalog.json"
        self.feed.write_bytes(dump_feed(feed_of(self.entry)))

    def test_validate_success_and_failure(self):
        self.assertEqual(mo.main(["validate", str(self.feed), "--source-root", str(self.root)]), 0)
        document = json.loads(self.feed.read_text())
        document["entries"][0]["commit"] = "A" * 40
        self.feed.write_bytes(dump_feed(document))
        self.assertEqual(mo.main(["validate", str(self.feed)]), 1)

    def test_validate_previous_and_duplicate_keys(self):
        self.assertEqual(
            mo.main(["validate", str(self.feed), "--previous", str(self.feed)]), 0
        )
        self.feed.write_bytes(b'{"schemaVersion":1,"schemaVersion":1,"channel":"macos-original","entries":[]}')
        self.assertEqual(mo.main(["validate", str(self.feed)]), 1)

    def test_prepare_rejects_floor_before_any_fetch(self):
        spec = pathlib.Path(self.tmp.name) / "spec.json"
        spec.write_text(
            json.dumps(
                {
                    "id": "demo-skill",
                    "name": {"en": "Demo", "zh-Hans": "演示"},
                    "description": {"en": "A demo.", "zh-Hans": "一个演示。"},
                    "category": "productivity-organization",
                    "version": "1.0.0",
                    "repository": "acme/demo",
                    "subdirectory": "",
                    "commit": HEX40,
                    "license": "MIT",
                    "licensePath": "LICENSE",
                    "licenseSourcePath": "LICENSE",
                    "minimumAppVersion": "1.7.99",
                }
            )
        )
        output = pathlib.Path(self.tmp.name) / "out"
        self.assertEqual(
            mo.main(["prepare", "--spec", str(spec), "--output-root", str(output)]), 1
        )
        self.assertFalse(output.exists())

    def test_finalize_cli_refuses_zero_floor(self):
        proposal = pathlib.Path(self.tmp.name) / "proposal.json"
        proposal.write_text("{}")
        self.assertEqual(
            mo.main(
                [
                    "finalize",
                    "--proposal",
                    str(proposal),
                    "--minimum-app-version",
                    "0.0.0",
                    "--output-dir",
                    str(pathlib.Path(self.tmp.name) / "feeds"),
                ]
            ),
            1,
        )


class ValidatorPinTests(unittest.TestCase):
    def test_contract_digest_is_reported(self):
        """The frozen digest is documented; this test never rewrites it."""
        self.assertEqual(mo.SCHEMA_VERSION, 1)
        self.assertEqual(mo.CHANNEL, "macos-original")
        self.assertEqual(mo.MAX_FEED_BYTES, 4 * 1024 * 1024)
        self.assertEqual(mo.MAX_FILE_BYTES, 16 * 1024 * 1024)
        self.assertEqual(mo.MAX_FILES, 2048)
        self.assertEqual(mo.MAX_ENTRIES, 256)


if __name__ == "__main__":
    unittest.main(verbosity=2)
