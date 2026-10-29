#!/usr/bin/env python3
"""Deterministic tests for the DATA-ONLY macOS original candidate signer.

These tests use an isolated ephemeral Ed25519 fixture identity and throw-away
Git repositories. They prove the signer's own trust, floor, history, stage,
output and secret boundaries. The trusted macOS original producer is a fixture
with the contracted interface until the real ``scripts/macos_original.py``
lands in trusted tooling; that integration remains pending.
"""
import base64
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HUB = pathlib.Path(__file__).resolve().parents[1]
SIGNER_PATH = HUB / "scripts" / "sign_macos_original.py"
OFFICIAL_ORIGIN = "https://github.com/JiangNanGenius/floe-skill-hub.git"
FIXTURE_SEED_LABEL = (
    b"floe skill hub macos original signer deterministic test key "
    b"-- ephemeral fixture only -- never a trust root")
OTHER_SEED_LABEL = b"floe skill hub macos original signer wrong-key fixture"
FIXTURE_SEED = hashlib.sha256(FIXTURE_SEED_LABEL).digest()
OTHER_SEED = hashlib.sha256(OTHER_SEED_LABEL).digest()


def _load_signer():
    spec = importlib.util.spec_from_file_location(
        "sign_macos_original_under_test", SIGNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SIGNER = _load_signer()


def _key(seed=FIXTURE_SEED):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(seed)


def _public_b64(seed=FIXTURE_SEED):
    from cryptography.hazmat.primitives import serialization
    raw = _key(seed).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def _seed_b64(seed=FIXTURE_SEED):
    return base64.b64encode(seed).decode()


def _sign_feed(feed_bytes, seed=FIXTURE_SEED):
    signature = _key(seed).sign(feed_bytes)
    return json.dumps({"keyID": "official-2026-09",
                       "signature": base64.b64encode(signature).decode()},
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def _manifest_digest(files):
    manifest = [{"path": f["path"], "sourcePath": f["sourcePath"],
                 "sha256": f["sha256"], "mode": f["mode"]} for f in files]
    payload = json.dumps(sorted(manifest, key=lambda row: row["path"]),
                         ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _producer_code(enforce_history=True):
    code = r'''"""Fixture macOS original producer with the contracted interface.

Test-only stand-in; the real producer remains pending in trusted tooling.
"""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\Z")
ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
CATEGORIES = {"office-documents", "writing-communication", "web-development",
              "research-data", "design-creation", "product-requirements",
              "productivity-organization"}
LIMIT = 16 * 1024 * 1024
ENFORCE_HISTORY = __ENFORCE_HISTORY__


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _relative(value):
    return (isinstance(value, str) and 0 < len(value.encode()) <= 1024
            and not value.startswith("/") and "\\" not in value
            and "\0" not in value
            and all(part not in ("", ".", "..") for part in value.split("/")))


def _identity(entry):
    return json.dumps({
        "repository": entry.get("repository"),
        "subdirectory": entry.get("subdirectory"),
        "commit": entry.get("commit"),
        "licensePath": entry.get("licensePath"),
        "digest": entry.get("digest"),
        "files": [{key: file.get(key) for key in
                   ("path", "sourcePath", "sha256", "bytes", "mode")}
                  for file in sorted(entry.get("files") or [],
                                     key=lambda row: str(row.get("path")))],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_manifest_digest(files):
    manifest = [{"path": f["path"], "sourcePath": f["sourcePath"],
                 "sha256": f["sha256"], "mode": f["mode"]} for f in files]
    return hashlib.sha256(json.dumps(
        sorted(manifest, key=lambda row: row["path"]),
        ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_catalog(document, source_root=None, previous_catalogs=()):
    _require(isinstance(document, dict), "feed object")
    _require(set(document) == {"schemaVersion", "channel", "entries"},
             "unknown/missing feed fields")
    _require(document["schemaVersion"] == 1
             and document["channel"] == "macos-original",
             "wrong schema/channel")
    entries = document["entries"]
    _require(isinstance(entries, list) and len(entries) <= 256, "entry count")
    seen = set()
    fields = {"id", "name", "description", "category", "version",
              "minimumAppVersion", "repository", "subdirectory", "commit",
              "license", "licensePath", "digest", "files"}
    for entry in entries:
        _require(isinstance(entry, dict) and set(entry) == fields,
                 "unknown/missing entry fields")
        _require(ID.fullmatch(entry["id"]) and entry["id"] not in seen,
                 "invalid/duplicate id")
        seen.add(entry["id"])
        for key in ("name", "description"):
            _require(set(entry[key]) == {"en", "zh-Hans"}
                     and all(isinstance(v, str) and v.strip()
                             for v in entry[key].values()), "bilingual text")
        _require(entry["category"] in CATEGORIES, "category")
        _require(VERSION.fullmatch(entry["version"])
                 and VERSION.fullmatch(entry["minimumAppVersion"]),
                 "semantic versions")
        repo = entry["repository"].split("/")
        _require(len(repo) == 2
                 and all(COMPONENT.fullmatch(v) for v in repo), "repository")
        _require(HEX40.fullmatch(entry["commit"])
                 and HEX64.fullmatch(entry["digest"]), "commit/digest")
        _require(entry["subdirectory"] == ""
                 or _relative(entry["subdirectory"]), "subdirectory")
        _require(entry["license"].strip()
                 and _relative(entry["licensePath"]), "license")
        _require(isinstance(entry["files"], list)
                 and 0 < len(entry["files"]) <= 2048, "files")
        paths, total, manifest = set(), 0, []
        for file in entry["files"]:
            _require(isinstance(file, dict)
                     and set(file) == {"path", "sourcePath", "sha256",
                                       "bytes", "mode"},
                     "unknown/missing file fields")
            path = file["path"]
            _require(_relative(path) and path not in paths,
                     "unsafe/duplicate file path")
            paths.add(path)
            _require(_relative(file["sourcePath"]), "unsafe upstream source path")
            expected = (entry["subdirectory"] + "/" + path
                        if entry["subdirectory"] else path)
            _require(path == entry["licensePath"]
                     or file["sourcePath"] == expected,
                     "original package layout differs")
            _require(HEX64.fullmatch(file["sha256"])
                     and type(file["bytes"]) is int
                     and 0 <= file["bytes"] <= LIMIT, "file identity")
            _require(file["mode"] in ("100644", "100755"), "file mode")
            total += file["bytes"]
            manifest.append({k: file[k] for k in
                             ("path", "sourcePath", "sha256", "mode")})
            if source_root is not None:
                root = (Path(source_root) / entry["id"]).resolve()
                target = root.joinpath(*PurePosixPath(path).parts)
                _require(not target.is_symlink()
                         and target.resolve().is_relative_to(root)
                         and target.is_file(),
                         "source file escapes package")
                data = target.read_bytes()
                _require(len(data) == file["bytes"]
                         and hashlib.sha256(data).hexdigest() == file["sha256"],
                         "source file differs")
                _require(bool(target.stat().st_mode & 0o111)
                         == (file["mode"] == "100755"),
                         "source executable mode differs")
        _require(total <= LIMIT and "SKILL.md" in paths
                 and entry["licensePath"] in paths,
                 "package size/SKILL/license")
        encoded = json.dumps(sorted(manifest, key=lambda row: row["path"]),
                             ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()
        _require(hashlib.sha256(encoded).hexdigest() == entry["digest"],
                 "manifest digest differs")
    if ENFORCE_HISTORY:
        historical = {}
        for previous in previous_catalogs:
            for entry in previous["entries"]:
                key = (entry["id"], entry["version"])
                identity = _identity(entry)
                if key in historical and historical[key] != identity:
                    raise ValueError("official history is inconsistent")
                historical[key] = identity
        for entry in entries:
            key = (entry["id"], entry["version"])
            identity = _identity(entry)
            if key in historical and historical[key] != identity:
                raise ValueError("published (id, version) identity drift")
    return len(entries)
'''
    return code.replace("__ENFORCE_HISTORY__", "True" if enforce_history else "False")


class MacOSOriginalSignerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="macos-signer-test-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.cwd = self.tmp / "cwd"
        self.cwd.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if key != "FLOE_SKILL_HUB_SIGNING_KEY"}
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.counter = 0

    # -- git helpers -----------------------------------------------------

    def _git(self, root, args):
        proc = subprocess.run(["git", "-C", str(root)] + list(args),
                              capture_output=True, text=True,
                              env={k: v for k, v in os.environ.items()
                                   if not k.startswith("GIT_")})
        self.assertEqual(proc.returncode, 0,
                         f"git {' '.join(args)} failed: {proc.stderr}")
        return proc.stdout.strip()

    def _init_repo(self, root, origin=OFFICIAL_ORIGIN):
        root = pathlib.Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self._git(root, ["init", "-q"])
        self._git(root, ["symbolic-ref", "HEAD", "refs/heads/main"])
        self._git(root, ["remote", "add", "origin", origin])
        return root

    def _commit(self, root, message="commit"):
        self._git(root, ["add", "-A"])
        self._git(root, ["-c", "user.name=test", "-c", "user.email=test@example.com",
                         "commit", "-q", "-m", message])
        return self._git(root, ["rev-parse", "HEAD"])

    def _write(self, root, rel, data, mode=0o644):
        target = pathlib.Path(root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        os.chmod(str(target), mode)
        return target

    def _put_feed_pair(self, root, feed_bytes, sig_bytes):
        self._write(root, "macos/catalog.json", feed_bytes)
        self._write(root, "macos/catalog.json.sig", sig_bytes)

    # -- fixture tools ---------------------------------------------------

    def _path(self, prefix):
        self.counter += 1
        return self.tmp / f"{prefix}-{self.counter}"

    def _make_tooling(self, enforce_history=True, include_producer=True,
                      name=None, producer_source="fixture"):
        root = self._init_repo(self.tmp / (name or self._path("tooling").name))
        shutil.copytree(HUB / "scripts", root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if not include_producer:
            (root / "scripts" / "macos_original.py").unlink(missing_ok=True)
        elif producer_source == "real":
            if not (root / "scripts" / "macos_original.py").is_file():
                raise AssertionError("real producer is not present in scripts/")
        else:
            (root / "scripts" / "macos_original.py").write_text(
                _producer_code(enforce_history), encoding="utf-8")
        (root / "public-key.json").write_text(json.dumps(
            {"keyID": "official-2026-09", "publicKey": _public_b64()}),
            encoding="utf-8")
        (root / "README.md").write_text("fixture tooling\n", encoding="utf-8")
        commit = self._commit(root, "fixture tooling")
        return root, commit

    def _make_upstream(self, child_text=b"original skill\n",
                       script_text=b"#!/bin/sh\necho fixture\n",
                       license_text=b"MIT fixture\n"):
        root = self._init_repo(self._path("upstream"))
        files = []
        for path, data, mode, package in (
                ("skills/demo/SKILL.md", child_text, 0o644, "SKILL.md"),
                ("License", license_text, 0o644, "LICENSE"),
                ("skills/demo/run.sh", script_text, 0o755, "run.sh")):
            self._write(root, path, data, mode)
            files.append({
                "path": package,
                "sourcePath": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "mode": "100755" if mode & 0o111 else "100644",
            })
        commit = self._commit(root, "upstream fixture")
        return root, commit, files

    def _entry(self, commit, files, version="1.0.0", floor="1.7.63",
               skill_id="demo-skill", repository="example-org/demo-skill",
               subdirectory="skills/demo", license_path="LICENSE",
               digest=None):
        return {
            "id": skill_id,
            "name": {"en": "Demo Skill", "zh-Hans": "演示技能"},
            "description": {"en": "Fixture description", "zh-Hans": "夹具说明"},
            "category": "research-data",
            "version": version,
            "minimumAppVersion": floor,
            "repository": repository,
            "subdirectory": subdirectory,
            "commit": commit,
            "license": "MIT",
            "licensePath": license_path,
            "digest": digest or _manifest_digest(files),
            "files": files,
        }

    def _feed_bytes(self, entries, indent=None):
        return (json.dumps({"schemaVersion": 1, "channel": "macos-original",
                            "entries": entries}, ensure_ascii=False,
                           sort_keys=True, indent=indent,
                           separators=None if indent else (",", ":"))
                + ("\n" if indent else "")).encode("utf-8")

    def _make_data(self, feed_bytes, extras=None, name=None):
        root = self._init_repo(self.tmp / (name or self._path("data").name))
        self._write(root, "macos/catalog.json", feed_bytes)
        for rel, data in (extras or {}).items():
            self._write(root, rel, data)
        commit = self._commit(root, "candidate data")
        return root, commit

    def _make_data_with_history(self, history, feed_bytes, name=None):
        root = self._init_repo(self.tmp / (name or self._path("data-history").name))
        for prior_feed, prior_sig in history:
            self._put_feed_pair(root, prior_feed, prior_sig)
            self._commit(root, "prior branch feed")
        self._write(root, "macos/catalog.json", feed_bytes)
        commit = self._commit(root, "candidate branch head")
        return root, commit

    def _make_baseline(self, history=(), head_feed=None, head_sig=None,
                       remove_after_history=False, shallow=False):
        root = self._init_repo(self._path("baseline"))
        self._write(root, "README.md", b"official baseline\n")
        self._commit(root, "baseline readme")
        for prior_feed, prior_sig in history:
            self._put_feed_pair(root, prior_feed, prior_sig)
            self._commit(root, "baseline feed")
        if remove_after_history:
            (root / "macos" / "catalog.json").unlink()
            (root / "macos" / "catalog.json.sig").unlink()
            self._commit(root, "remove feed")
        if head_feed is not None:
            self._put_feed_pair(root, head_feed, head_sig)
            self._commit(root, "baseline head feed")
        commit = self._git(root, ["rev-parse", "HEAD"])
        if shallow:
            shallow_root = self._path("baseline-shallow")
            subprocess.run(["git", "clone", "--quiet", "--depth", "1",
                            "file://" + str(root), str(shallow_root)],
                           check=True, capture_output=True, text=True)
            self._git(shallow_root, ["remote", "set-url", "origin",
                                     OFFICIAL_ORIGIN])
            root = shallow_root
            commit = self._git(root, ["rev-parse", "HEAD"])
        return root, commit

    # -- CLI helper ------------------------------------------------------

    def _tree(self, root):
        return self._git(root, ["rev-parse", "HEAD^{tree}"])

    def _make_verification(self, tooling, data, data_commit, baseline,
                           baseline_commit, floor):
        """A shape-correct receipt for signer-boundary tests.

        The signer rederives T/S/B identities, the feed hash, the floor and
        every per-entry manifest from the actual snapshots; this fixture only
        fills the separate-job metadata fields. End-to-end use of the real
        verify output is covered by test_plan_fetch_verify_and_sign_end_to_end.
        """
        feed = (pathlib.Path(data) / "macos" / "catalog.json").read_bytes()
        document = json.loads(feed)
        entries = []
        for entry in document["entries"]:
            manifest = [{key: file[key] for key in
                         ("path", "sourcePath", "sha256", "mode")}
                        for file in entry["files"]]
            entries.append({
                "id": entry["id"],
                "version": entry["version"],
                "repository": entry["repository"],
                "commit": entry["commit"],
                "fileCount": len(entry["files"]),
                "totalBytes": sum(file["bytes"] for file in entry["files"]),
                "manifestSha256": hashlib.sha256(json.dumps(
                    sorted(manifest, key=lambda row: row["path"]),
                    ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode()).hexdigest(),
            })
        baseline = pathlib.Path(baseline)
        head_present = (baseline / "macos" / "catalog.json").is_file()
        latest = (hashlib.sha256(
            (baseline / "macos" / "catalog.json").read_bytes()).hexdigest()
            if head_present else None)
        commits = self._git(
            baseline, ["log", "--first-parent", "--format=%H", "--",
                       "macos/catalog.json", "macos/catalog.json.sig"])
        observed = hashlib.sha256(b"fixture-observed-manifest").hexdigest()
        receipt = {
            "schemaVersion": 1,
            "mode": "macos-original-verify",
            "channel": "macos-original",
            "hubRepository": "JiangNanGenius/floe-skill-hub",
            "sourceCommit": data_commit,
            "sourceTree": self._tree(data),
            "toolingCommit": self._git(tooling, ["rev-parse", "HEAD"]),
            "toolingTree": self._tree(tooling),
            "baselineCommit": baseline_commit,
            "baselineTree": self._tree(baseline),
            "baselineFeedPresent": head_present,
            "minimumAppVersion": floor,
            "feed": {"path": "macos/catalog.json",
                     "sha256": hashlib.sha256(feed).hexdigest(),
                     "size": len(feed),
                     "entryCount": len(entries)},
            "history": {
                "signedFeedCount": len([line for line in commits.splitlines()
                                        if line]),
                "latestFeedSha256": latest,
            },
            "upstream": entries,
            "observedManifestSha256": observed,
            "upstreamVerification": {
                "verified": True,
                "targetCount": len(entries),
                "observedManifestSha256": observed,
            },
            "limitations": ["candidate-only", "not published"],
        }
        path = self._path("verification")
        path.write_bytes(json.dumps(receipt, ensure_ascii=False,
                                    sort_keys=True, indent=2).encode() + b"\n")
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def _run(self, mode, tooling, data=None, data_commit=None, baseline=None,
             baseline_commit=None, floor=None, out=None, extra=(),
             env_extra=None, proof=True, verification_receipt=None,
             verification_sha256=None):
        self.counter += 1
        out = pathlib.Path(out or (self.tmp / f"out-{self.counter}"))
        command = [sys.executable,
                   str(pathlib.Path(tooling) / "scripts" / "sign_macos_original.py"),
                   mode]
        if data is not None:
            command += ["--data", str(data), "--source-commit", data_commit,
                        "--tooling", str(tooling), "--out", str(out)]
        if baseline is not None:
            command += ["--baseline", str(baseline),
                        "--baseline-commit", baseline_commit,
                        "--minimum-app-version", floor]
        if mode == "sign":
            if verification_receipt is None and proof:
                verification_receipt, verification_sha256 = \
                    self._make_verification(tooling, data, data_commit,
                                            baseline, baseline_commit, floor)
            if verification_receipt is not None:
                if verification_sha256 is None:
                    verification_sha256 = hashlib.sha256(
                        pathlib.Path(verification_receipt).read_bytes()).hexdigest()
                command += ["--verification-receipt",
                            str(verification_receipt),
                            "--verification-sha256",
                            verification_sha256]
        command += list(extra)
        env = self.env.copy()
        if env_extra:
            for key, value in env_extra.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
        proc = subprocess.run(command, cwd=str(self.cwd), env=env,
                              capture_output=True, text=True)
        return proc, out

    def _expect_refusal(self, proc, needle=None):
        self.assertEqual(proc.returncode, 2,
                         f"expected refusal, got {proc.returncode}\n"
                         f"stdout={proc.stdout}\nstderr={proc.stderr}")
        self.assertIn("refusing:", proc.stderr)
        if needle:
            self.assertIn(needle, proc.stderr)

    def _valid_candidate(self, indent=None):
        upstream, commit, files = self._make_upstream()
        entry = self._entry(commit, files)
        feed = self._feed_bytes([entry], indent=indent)
        data, data_commit = self._make_data(feed)
        tooling, tooling_commit = self._make_tooling()
        baseline, baseline_commit = self._make_baseline()
        return {"upstream": upstream, "commit": commit, "files": files,
                "entry": entry, "feed": feed, "data": data,
                "data_commit": data_commit, "tooling": tooling,
                "tooling_commit": tooling_commit, "baseline": baseline,
                "baseline_commit": baseline_commit}

    # -- tests -----------------------------------------------------------

    def test_valid_candidate_signs_exact_bytes_and_receipt(self):
        fixture = self._valid_candidate(indent=2)
        proc, out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63", out=self.tmp / "signed",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        feed = (out / "macos" / "catalog.json").read_bytes()
        sig = (out / "macos" / "catalog.json.sig").read_bytes()
        self.assertEqual(feed, fixture["feed"], "the exact candidate bytes must be signed")
        envelope = json.loads(sig)
        self.assertEqual(envelope["keyID"], "official-2026-09")
        _key().public_key().verify(base64.b64decode(envelope["signature"]), feed)
        receipt = json.loads((out / "macos" / "signing-receipt.json").read_bytes())
        self.assertEqual(receipt["sourceCommit"], fixture["data_commit"])
        self.assertEqual(receipt["toolingCommit"], fixture["tooling_commit"])
        self.assertEqual(receipt["baselineCommit"], fixture["baseline_commit"])
        self.assertEqual(receipt["minimumAppVersion"], "1.7.63")
        self.assertEqual(receipt["feed"]["sha256"], hashlib.sha256(feed).hexdigest())
        self.assertEqual(receipt["claims"]["candidateOnly"], True)
        self.assertEqual(receipt["claims"]["published"], False)
        receipt_sig = (out / "macos" / "signing-receipt.json.sig").read_bytes()
        _key().public_key().verify(
            base64.b64decode(json.loads(receipt_sig)["signature"]),
            (out / "macos" / "signing-receipt.json").read_bytes())
        listed = {item["path"]: item for item in receipt["outputs"]}
        self.assertEqual(set(listed), {"macos/catalog.json",
                                       "macos/catalog.json.sig"})
        for path, item in listed.items():
            payload = (out / path).read_bytes()
            self.assertEqual(item["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(item["size"], len(payload))
        self.assertEqual(sorted(p.name for p in (out / "macos").iterdir()),
                         ["catalog.json", "catalog.json.sig",
                          "signing-receipt.json", "signing-receipt.json.sig"])
        seed_text = _seed_b64()
        self.assertNotIn(seed_text, proc.stdout + proc.stderr)
        for path in out.rglob("*"):
            if path.is_file():
                self.assertNotIn(seed_text.encode(), path.read_bytes())
                self.assertNotIn(b"PRIVATE", path.read_bytes())

    def test_wrong_key_is_refused_without_output(self):
        fixture = self._valid_candidate()
        proc, out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "wrong-key",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64(OTHER_SEED)})
        self._expect_refusal(proc, "does not match")
        self.assertFalse((out / "macos" / "catalog.json").exists())

    def test_floor_is_exact_and_never_an_all_zero_placeholder(self):
        fixture = self._valid_candidate()
        cases = [
            ("1.7.62", "differs from the release-owner floor"),
            ("1.7.063", "strict semantic version"),
            ("0.0.0", "all-zero placeholder"),
            ("1.7.63.1", "strict semantic version"),
        ]
        for floor, needle in cases:
            with self.subTest(floor=floor):
                proc, _out = self._run(
                    "sign", fixture["tooling"], fixture["data"],
                    fixture["data_commit"], fixture["baseline"],
                    fixture["baseline_commit"], floor,
                    out=self.tmp / ("floor-" + floor.replace(".", "-")),
                    env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
                self._expect_refusal(proc, needle)

    def test_entry_floor_must_equal_the_confirmed_floor(self):
        upstream, commit, files = self._make_upstream()
        entry = self._entry(commit, files, floor="1.7.62")
        feed = self._feed_bytes([entry])
        data, data_commit = self._make_data(feed)
        tooling, _ = self._make_tooling()
        baseline, baseline_commit = self._make_baseline()
        proc, _out = self._run(
            "sign", tooling, data, data_commit, baseline, baseline_commit,
            "1.7.63", out=self.tmp / "entry-floor",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "differs from the release-owner floor")

    def test_snapshot_tamper_untracked_assume_unchanged_and_symlink_refused(self):
        fixture = self._valid_candidate()
        key = {"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()}

        self._write(fixture["data"], "macos/hidden.json", b"hidden")
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "untracked", env_extra=key)
        self._expect_refusal(proc, "untracked or ignored")
        (fixture["data"] / "macos" / "hidden.json").unlink()

        self._write(fixture["data"], "macos/catalog.json",
                    fixture["feed"] + b" ")
        self._git(fixture["data"], ["update-index", "--assume-unchanged",
                                    "macos/catalog.json"])
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "assume-unchanged", env_extra=key)
        self._expect_refusal(proc, "differs from the HEAD blob")

        link = self.tmp / "data-link"
        link.symlink_to(fixture["data"], target_is_directory=True)
        proc, _out = self._run(
            "sign", fixture["tooling"], link, fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "symlink", env_extra=key)
        self._expect_refusal(proc, "must be a real directory")

        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"], "0" * 40,
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "wrong-commit", env_extra=key)
        self._expect_refusal(proc, "does not equal the claimed commit")

    def test_candidate_code_is_never_imported_or_executed(self):
        marker = self.tmp / "candidate-code-ran"
        malicious = (
            "import pathlib\n"
            f"pathlib.Path({str(marker)!r}).write_text('ran')\n"
            "raise RuntimeError('candidate code imported')\n").encode()
        fixture = self._valid_candidate()
        # The candidate snapshot carries shadow modules with the exact names
        # the signer imports from trusted tooling.
        data = fixture["data"]
        self._write(data, "scripts/hubcore.py", malicious)
        self._write(data, "scripts/macos_original.py", malicious)
        self._write(data, "scripts/sitecustomize.py", malicious)
        data_commit = self._commit(data, "add candidate shadow modules")
        proc, out = self._run(
            "sign", fixture["tooling"], data, data_commit,
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "shadow-modules",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(marker.exists())
        self.assertTrue((out / "macos" / "catalog.json.sig").is_file())

    def test_tooling_dirty_and_shadow_files_are_refused(self):
        fixture = self._valid_candidate()
        self._write(fixture["tooling"], "README.md", b"dirty tooling\n")
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "dirty-tooling",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "differs from the HEAD blob")

    def test_real_producer_contract_interface_when_present(self):
        if not (HUB / "scripts" / "macos_original.py").is_file():
            self.skipTest("the real macOS original producer is still pending")
        fixture = self._valid_candidate()
        tooling, _commit = self._make_tooling(producer_source="real")
        proc, plan_out = self._run(
            "plan", tooling, fixture["data"], fixture["data_commit"],
            out=self.tmp / "real-plan")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plan = json.loads((plan_out / "plan.json").read_bytes())
        stage = self.tmp / "real-stage"
        observed = self.tmp / "real-observed.json"
        SIGNER._fetch_plan(plan, stage, observed, self.tmp / "real-fetch-work",
                           origin_override="file://" + str(fixture["upstream"]))
        proc, verify_out = self._run(
            "verify", tooling, fixture["data"], fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "real-verify",
            extra=["--stage", str(stage), "--observed", str(observed)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = verify_out / "verification.json"
        sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
        proc, out = self._run(
            "sign", tooling, fixture["data"], fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "real-producer",
            verification_receipt=receipt, verification_sha256=sha,
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((out / "macos" / "catalog.json.sig").is_file())
        signed = json.loads(
            (out / "macos" / "signing-receipt.json").read_bytes())
        self.assertEqual(signed["upstreamVerification"]["receiptSha256"], sha)

    def test_history_same_id_version_drift_is_refused(self):
        commit_a, commit_b = "a" * 40, "b" * 40
        files = [{"path": "SKILL.md", "sourcePath": "SKILL.md",
                  "sha256": "1" * 64, "bytes": 10, "mode": "100644"},
                 {"path": "LICENSE", "sourcePath": "LICENSE",
                  "sha256": "2" * 64, "bytes": 5, "mode": "100644"}]
        entry_a = self._entry(commit_a, files, version="1.0.0",
                              subdirectory="", license_path="LICENSE")
        feed_a = self._feed_bytes([entry_a])
        sig_a = _sign_feed(feed_a)
        baseline, baseline_commit = self._make_baseline(
            history=[(feed_a, sig_a)])
        tooling, _ = self._make_tooling(enforce_history=False)

        for label, candidate_entry in (
                ("changed commit", self._entry(
                    commit_b, files, version="1.0.0", subdirectory="",
                    license_path="LICENSE")),
                ("changed bytes", self._entry(
                    commit_a, [dict(files[0], sha256="3" * 64,
                                    bytes=11), files[1]],
                    version="1.0.0", subdirectory="",
                    license_path="LICENSE"))):
            with self.subTest(label=label):
                feed = self._feed_bytes([candidate_entry])
                data, data_commit = self._make_data(feed)
                proc, _out = self._run(
                    "sign", tooling, data, data_commit, baseline,
                    baseline_commit, "1.7.63",
                    out=self.tmp / ("drift-" + label.replace(" ", "-")),
                    env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
                self._expect_refusal(proc, "is immutable")

    def test_history_covers_versions_removed_from_current_feed(self):
        commit_a, commit_b = "a" * 40, "b" * 40
        files = [{"path": "SKILL.md", "sourcePath": "SKILL.md",
                  "sha256": "1" * 64, "bytes": 10, "mode": "100644"},
                 {"path": "LICENSE", "sourcePath": "LICENSE",
                  "sha256": "2" * 64, "bytes": 5, "mode": "100644"}]
        entry_v1 = self._entry(commit_a, files, version="1.0.0",
                               subdirectory="")
        feed_v1 = self._feed_bytes([entry_v1])
        entry_v2 = self._entry(commit_b, files, version="2.0.0",
                               subdirectory="")
        feed_v2 = self._feed_bytes([entry_v2])
        baseline, baseline_commit = self._make_baseline(
            history=[(feed_v1, _sign_feed(feed_v1)),
                     (feed_v2, _sign_feed(feed_v2))])
        tooling, _ = self._make_tooling(enforce_history=False)
        reintroduced = self._entry(commit_b, files, version="1.0.0",
                                   subdirectory="")
        data, data_commit = self._make_data(self._feed_bytes([reintroduced]))
        proc, _out = self._run(
            "sign", tooling, data, data_commit, baseline, baseline_commit,
            "1.7.63", out=self.tmp / "reintroduced",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "is immutable")

    def test_commit_only_change_with_new_version_is_allowed(self):
        commit_a, commit_b = "a" * 40, "b" * 40
        files = [{"path": "SKILL.md", "sourcePath": "SKILL.md",
                  "sha256": "1" * 64, "bytes": 10, "mode": "100644"},
                 {"path": "LICENSE", "sourcePath": "LICENSE",
                  "sha256": "2" * 64, "bytes": 5, "mode": "100644"}]
        entry_v1 = self._entry(commit_a, files, version="1.0.0",
                               subdirectory="")
        feed_v1 = self._feed_bytes([entry_v1])
        baseline, baseline_commit = self._make_baseline(
            history=[(feed_v1, _sign_feed(feed_v1))])
        tooling, _ = self._make_tooling()
        entry_v101 = self._entry(commit_b, files, version="1.0.1",
                                 subdirectory="")
        self.assertEqual(entry_v101["digest"], entry_v1["digest"])
        data, data_commit = self._make_data(self._feed_bytes([entry_v101]))
        proc, _out = self._run(
            "sign", tooling, data, data_commit, baseline, baseline_commit,
            "1.7.63", out=self.tmp / "commit-only-new-version",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_candidate_branch_history_is_not_official_history(self):
        commit_a, commit_b = "a" * 40, "b" * 40
        files = [{"path": "SKILL.md", "sourcePath": "SKILL.md",
                  "sha256": "1" * 64, "bytes": 10, "mode": "100644"},
                 {"path": "LICENSE", "sourcePath": "LICENSE",
                  "sha256": "2" * 64, "bytes": 5, "mode": "100644"}]
        prior = self._entry(commit_a, files, version="1.0.0", subdirectory="")
        prior_feed = self._feed_bytes([prior])
        candidate = self._entry(commit_b, files, version="1.0.0",
                                subdirectory="")
        candidate_feed = self._feed_bytes([candidate])
        data, data_commit = self._make_data_with_history(
            [(prior_feed, _sign_feed(prior_feed))], candidate_feed)
        baseline, baseline_commit = self._make_baseline()
        tooling, _ = self._make_tooling()
        proc, _out = self._run(
            "sign", tooling, data, data_commit, baseline, baseline_commit,
            "1.7.63", out=self.tmp / "branch-history",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_baseline_signed_history_is_required_and_fully_verified(self):
        commit_a = "a" * 40
        files = [{"path": "SKILL.md", "sourcePath": "SKILL.md",
                  "sha256": "1" * 64, "bytes": 10, "mode": "100644"},
                 {"path": "LICENSE", "sourcePath": "LICENSE",
                  "sha256": "2" * 64, "bytes": 5, "mode": "100644"}]
        entry = self._entry(commit_a, files, version="1.0.0", subdirectory="")
        feed = self._feed_bytes([entry])
        tooling, _ = self._make_tooling()
        candidate_data, candidate_commit = self._make_data(
            self._feed_bytes([self._entry(commit_a, files, version="1.0.1",
                                          subdirectory="")]))

        # Wrong signing identity in official history: refusal.
        baseline, baseline_commit = self._make_baseline(
            history=[(feed, _sign_feed(feed, OTHER_SEED))])
        proc, _out = self._run(
            "sign", tooling, candidate_data, candidate_commit, baseline,
            baseline_commit, "1.7.63", out=self.tmp / "wrong-history-key",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "signature is not trustworthy")

        # Missing signature object in history: refusal.
        baseline2, baseline2_commit = self._make_baseline()
        self._put_feed_pair(baseline2, feed, _sign_feed(feed))
        (baseline2 / "macos" / "catalog.json.sig").unlink()
        self._commit(baseline2, "unsigned feed")
        baseline2_commit = self._git(baseline2, ["rev-parse", "HEAD"])
        proc, _out = self._run(
            "sign", tooling, candidate_data, candidate_commit, baseline2,
            baseline2_commit, "1.7.63", out=self.tmp / "unsigned-history",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "history cannot be established")

        # Published feed removed from HEAD: refusal.
        baseline3, baseline3_commit = self._make_baseline(
            history=[(feed, _sign_feed(feed))], remove_after_history=True)
        proc, _out = self._run(
            "sign", tooling, candidate_data, candidate_commit, baseline3,
            baseline3_commit, "1.7.63", out=self.tmp / "removed-history",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc)

        # Shallow baseline cannot prove history: refusal.
        baseline4, baseline4_commit = self._make_baseline(shallow=True)
        proc, _out = self._run(
            "sign", tooling, candidate_data, candidate_commit, baseline4,
            baseline4_commit, "1.7.63", out=self.tmp / "shallow-baseline",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "shallow")

    def test_first_parent_publication_spine_ignores_merged_candidate_history(self):
        fixture = self._valid_candidate()
        candidate_doc = json.loads(fixture["feed"])
        drift_doc = json.loads(json.dumps(candidate_doc))
        drift_doc["entries"][0]["commit"] = "f" * 40
        drift_feed = json.dumps(drift_doc, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")).encode()

        def baseline_with_branch(feed_bytes, sig_bytes, ours):
            root = self._init_repo(self._path("baseline-merge"))
            self._write(root, "README.md", b"official baseline\n")
            self._commit(root, "baseline readme")
            self._git(root, ["checkout", "-q", "-b", "candidate"])
            self._put_feed_pair(root, feed_bytes, sig_bytes)
            self._commit(root, "candidate intermediate feed")
            self._git(root, ["checkout", "-q", "main"])
            args = ["-c", "user.name=test", "-c", "user.email=test@example.com",
                    "merge", "--no-ff", "-m", "merge candidate"]
            if ours:
                args += ["-s", "ours"]
            args.append("candidate")
            self._git(root, args)
            return root, self._git(root, ["rev-parse", "HEAD"])

        # A second-parent candidate feed that is NOT copied by the merge is
        # not publication history. The candidate itself is intentionally a
        # drift, so only first-parent traversal can let this pass.
        baseline, baseline_commit = baseline_with_branch(
            drift_feed, _sign_feed(drift_feed), ours=True)
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], baseline, baseline_commit, "1.7.63",
            out=self.tmp / "first-parent-ignore",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)

        # A first-parent merge that actually brings an unsigned/wrong-key
        # feed is a publication boundary and must be refused, never merged
        # into official history unverified.
        baseline2, baseline2_commit = baseline_with_branch(
            drift_feed, _sign_feed(drift_feed, OTHER_SEED), ours=False)
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], baseline2, baseline2_commit, "1.7.63",
            out=self.tmp / "first-parent-unsigned-merge",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "signature is not trustworthy")

    def test_baseline_feed_present_but_tooling_stale_is_not_relevant(self):
        # T is tooling only; official history comes from B. A baseline with a
        # valid current feed must still be accepted when T has no feed.
        commit_a = "a" * 40
        files = [{"path": "SKILL.md", "sourcePath": "SKILL.md",
                  "sha256": "1" * 64, "bytes": 10, "mode": "100644"},
                 {"path": "LICENSE", "sourcePath": "LICENSE",
                  "sha256": "2" * 64, "bytes": 5, "mode": "100644"}]
        old = self._entry(commit_a, files, version="1.0.0", subdirectory="")
        old_feed = self._feed_bytes([old])
        baseline, baseline_commit = self._make_baseline(
            history=[(old_feed, _sign_feed(old_feed))])
        tooling, _ = self._make_tooling()
        new = self._entry("b" * 40, files, version="1.0.1", subdirectory="")
        data, data_commit = self._make_data(self._feed_bytes([new]))
        proc, _out = self._run(
            "sign", tooling, data, data_commit, baseline, baseline_commit,
            "1.7.63", out=self.tmp / "baseline-current",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_plan_fetch_and_verify_upstream_bytes(self):
        fixture = self._valid_candidate()
        proc, plan_out = self._run(
            "plan", fixture["tooling"], fixture["data"], fixture["data_commit"],
            out=self.tmp / "plan")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        plan = json.loads((plan_out / "plan.json").read_bytes())
        stage = self.tmp / "upstream-stage"
        observed = self.tmp / "observed.json"
        work = self.tmp / "fetch-work"
        SIGNER._fetch_plan(plan, stage, observed, work,
                           origin_override="file://" + str(fixture["upstream"]))
        proc, verify_out = self._run(
            "verify", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verify",
            extra=["--stage", str(stage), "--observed", str(observed)])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        verification = json.loads(
            (verify_out / "verification.json").read_bytes())
        self.assertEqual(verification["feed"]["sha256"],
                         hashlib.sha256(fixture["feed"]).hexdigest())
        self.assertEqual(verification["minimumAppVersion"], "1.7.63")
        self.assertEqual(len(verification["upstream"]), 1)
        self.assertEqual(verification["upstream"][0]["fileCount"],
                         len(fixture["files"]))
        self.assertEqual(verification["upstreamVerification"]["verified"], True)
        self.assertEqual(verification["upstreamVerification"]["targetCount"], 1)
        self.assertEqual(verification["upstreamVerification"]
                         ["observedManifestSha256"],
                         verification["observedManifestSha256"])

        # The real verify receipt is the mandatory sign proof.
        verification_path = verify_out / "verification.json"
        verification_sha = hashlib.sha256(
            verification_path.read_bytes()).hexdigest()
        proc, sign_out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verify-then-sign",
            verification_receipt=verification_path,
            verification_sha256=verification_sha,
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        signed = json.loads(
            (sign_out / "macos" / "signing-receipt.json").read_bytes())
        self.assertEqual(signed["upstreamVerification"]["receiptSha256"],
                         verification_sha)
        self.assertEqual(signed["upstreamVerification"]["verifiedEntryCount"], 1)

        # Staged byte tamper is refused.
        staged_skill = stage / "demo-skill" / "SKILL.md"
        original = staged_skill.read_bytes()
        staged_skill.write_bytes(original + b"tamper")
        proc, _out = self._run(
            "verify", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verify-tamper",
            extra=["--stage", str(stage), "--observed", str(observed)])
        self._expect_refusal(proc, "staged")

        # Observed manifest tamper is refused.
        staged_skill.write_bytes(original)
        observed_doc = json.loads(observed.read_bytes())
        observed_doc["targets"][0]["files"][0]["sha256"] = "f" * 64
        observed.write_text(json.dumps(observed_doc), encoding="utf-8")
        proc, _out = self._run(
            "verify", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verify-observed-tamper",
            extra=["--stage", str(stage), "--observed", str(observed)])
        self._expect_refusal(proc, "observed")

        # Extra staged file is refused.
        observed.write_bytes(json.dumps(
            {"schemaVersion": 1,
             "planSha256": hashlib.sha256(json.dumps(
                 plan, ensure_ascii=False, sort_keys=True,
                 separators=(",", ":")).encode()).hexdigest(),
             "targets": [{"id": "demo-skill",
                          "repository": "example-org/demo-skill",
                          "commit": fixture["commit"],
                          "files": fixture["files"]}]},
            ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode())
        (stage / "demo-skill" / "EXTRA").write_bytes(b"extra")
        proc, _out = self._run(
            "verify", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verify-extra",
            extra=["--stage", str(stage), "--observed", str(observed)])
        self._expect_refusal(proc, "staged file set")

    def test_fetch_refuses_mode_byte_count_and_path_traversal(self):
        fixture = self._valid_candidate()
        plan = SIGNER._plan_from_candidate(json.loads(fixture["feed"]))

        bad_mode = json.loads(json.dumps(plan))
        bad_mode["targets"][0]["files"][2]["mode"] = "100644"
        with self.assertRaises(SIGNER.SigningError):
            SIGNER._fetch_plan(
                bad_mode, self.tmp / "stage-mode", self.tmp / "obs-mode.json",
                self.tmp / "work-mode",
                origin_override="file://" + str(fixture["upstream"]))

        bad_sha = json.loads(json.dumps(plan))
        bad_sha["targets"][0]["files"][0]["sha256"] = "f" * 64
        with self.assertRaises(SIGNER.SigningError):
            SIGNER._fetch_plan(
                bad_sha, self.tmp / "stage-sha", self.tmp / "obs-sha.json",
                self.tmp / "work-sha",
                origin_override="file://" + str(fixture["upstream"]))

        traversal = json.loads(json.dumps(plan))
        traversal["targets"][0]["files"][0]["path"] = "../escape"
        with self.assertRaises(SIGNER.SigningError):
            SIGNER._validate_plan(json.dumps(traversal).encode())

    def test_output_integrity_and_foreign_overwrite_refused(self):
        fixture = self._valid_candidate()
        key = {"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()}

        occupied = self.tmp / "occupied"
        occupied.mkdir()
        (occupied / "foreign").write_text("keep")
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63", out=occupied,
            env_extra=key)
        self._expect_refusal(proc, "fresh or empty")
        self.assertEqual((occupied / "foreign").read_text(), "keep")

        link = self.tmp / "out-link"
        link.symlink_to(self.tmp / "target-dir", target_is_directory=True)
        proc, _out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63", out=link,
            env_extra=key)
        self._expect_refusal(proc, "symlink")

        for label, out_path in (
                ("tooling", fixture["tooling"] / "out"),
                ("data", fixture["data"] / "out"),
                ("baseline", fixture["baseline"] / "out")):
            with self.subTest(label=label):
                proc, _out = self._run(
                    "sign", fixture["tooling"], fixture["data"],
                    fixture["data_commit"], fixture["baseline"],
                    fixture["baseline_commit"], "1.7.63", out=out_path,
                    env_extra=key)
                self._expect_refusal(proc, "must live outside")

    def test_feed_smuggling_and_oversize_are_refused(self):
        fixture = self._valid_candidate()
        document = json.loads(fixture["feed"])

        cases = []
        top_extra = json.loads(json.dumps(document))
        top_extra["command"] = "curl evil"
        cases.append(("top field", top_extra))
        file_extra = json.loads(json.dumps(document))
        file_extra["entries"][0]["files"][0]["url"] = "https://evil"
        cases.append(("file field", file_extra))
        entry_extra = json.loads(json.dumps(document))
        entry_extra["entries"][0]["install"] = "sh -c evil"
        cases.append(("entry field", entry_extra))
        wrong_channel = json.loads(json.dumps(document))
        wrong_channel["channel"] = "macrohard"
        cases.append(("channel", wrong_channel))
        bad_digest = json.loads(json.dumps(document))
        bad_digest["entries"][0]["digest"] = "f" * 64
        cases.append(("digest", bad_digest))

        for label, candidate in cases:
            with self.subTest(label=label):
                data, data_commit = self._make_data(
                    json.dumps(candidate, ensure_ascii=False,
                               sort_keys=True, separators=(",", ":")).encode())
                proc, _out = self._run(
                    "sign", fixture["tooling"], data, data_commit,
                    fixture["baseline"], fixture["baseline_commit"], "1.7.63",
                    out=self.tmp / ("smuggle-" + label.replace(" ", "-")),
                    env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
                self._expect_refusal(proc)

        duplicate = fixture["feed"].replace(
            b'"channel":"macos-original"',
            b'"channel":"macos-original","channel":"macos-original"', 1)
        self.assertNotEqual(duplicate, fixture["feed"])
        data, data_commit = self._make_data(duplicate)
        proc, _out = self._run(
            "sign", fixture["tooling"], data, data_commit, fixture["baseline"],
            fixture["baseline_commit"], "1.7.63", out=self.tmp / "duplicate-key",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "duplicate JSON key")

        oversize = json.loads(json.dumps(document))
        oversize["entries"][0]["description"]["en"] = "x" * (4 * 1024 * 1024)
        data, data_commit = self._make_data(
            json.dumps(oversize, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode())
        proc, _out = self._run(
            "sign", fixture["tooling"], data, data_commit, fixture["baseline"],
            fixture["baseline_commit"], "1.7.63", out=self.tmp / "oversize",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "exceeds")

    def test_tracked_symlink_feed_is_refused(self):
        fixture = self._valid_candidate()
        data = self._init_repo(self.tmp / "data-symlink")
        self._write(data, "real.json", fixture["feed"])
        (data / "macos").mkdir()
        os.symlink("../real.json", data / "macos" / "catalog.json")
        commit = self._commit(data, "symlink feed")
        proc, _out = self._run(
            "sign", fixture["tooling"], data, commit, fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "tracked-symlink",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "tracked symlink")

    def test_readonly_modes_refuse_the_signing_key(self):
        fixture = self._valid_candidate()
        key = {"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()}
        proc, _out = self._run(
            "plan", fixture["tooling"], fixture["data"], fixture["data_commit"],
            out=self.tmp / "plan-key", env_extra=key)
        self._expect_refusal(proc, "must not run")
        proc, _out = self._run(
            "verify", fixture["tooling"], fixture["data"], fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verify-key",
            extra=["--stage", str(self.tmp / "missing-stage"),
                   "--observed", str(self.tmp / "missing-observed")],
            env_extra=key)
        self._expect_refusal(proc, "must not run")

        plan_path = self.tmp / "fetch-plan.json"
        plan_path.write_text(json.dumps(
            SIGNER._plan_from_candidate(json.loads(fixture["feed"]))))
        proc, _out = self._run(
            "fetch", fixture["tooling"], out=self.tmp / "fetch-key",
            extra=["--plan", str(plan_path),
                   "--stage", str(self.tmp / "fetch-stage"),
                   "--observed", str(self.tmp / "fetch-observed.json")],
            env_extra=key)
        self._expect_refusal(proc, "must not run")

    def test_missing_producer_is_reported_as_pending(self):
        fixture = self._valid_candidate()
        tooling, _ = self._make_tooling(include_producer=False,
                                        name="tooling-no-producer")
        proc, out = self._run(
            "sign", tooling, fixture["data"], fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "no-producer",
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self._expect_refusal(proc, "integration is still pending")
        self.assertFalse((out / "macos" / "catalog.json").exists())

    def test_receipt_binds_exact_verification_sha(self):
        fixture = self._valid_candidate()
        receipt_path, digest = self._make_verification(
            fixture["tooling"], fixture["data"], fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63")
        proc, out = self._run(
            "sign", fixture["tooling"], fixture["data"],
            fixture["data_commit"], fixture["baseline"],
            fixture["baseline_commit"], "1.7.63",
            out=self.tmp / "verification-sha",
            verification_receipt=receipt_path,
            verification_sha256=digest,
            env_extra={"FLOE_SKILL_HUB_SIGNING_KEY": _seed_b64()})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads((out / "macos" / "signing-receipt.json").read_bytes())
        self.assertEqual(receipt["upstreamVerification"]["receiptSha256"], digest)
        self.assertEqual(receipt["upstreamVerification"]["mode"],
                         "separate-readonly-job")
        self.assertEqual(receipt["upstreamVerification"]["verifiedEntryCount"], 1)
        self.assertEqual(
            receipt["upstreamVerification"]["observedManifestSha256"],
            json.loads(receipt_path.read_bytes())["observedManifestSha256"])

    def test_sign_requires_verified_proof_before_reading_the_key(self):
        fixture = self._valid_candidate()
        bad_key = {"FLOE_SKILL_HUB_SIGNING_KEY": "not-valid-base64"}
        receipt_path, digest = self._make_verification(
            fixture["tooling"], fixture["data"], fixture["data_commit"],
            fixture["baseline"], fixture["baseline_commit"], "1.7.63")
        base = json.loads(receipt_path.read_bytes())

        def rewritten(mutate):
            document = json.loads(json.dumps(base))
            mutate(document)
            path = self._path("verification-negative")
            path.write_bytes(json.dumps(document, ensure_ascii=False,
                                        sort_keys=True, indent=2).encode() + b"\n")
            return path, hashlib.sha256(path.read_bytes()).hexdigest()

        cases = [
            ("missing receipt", None, digest,
             "sign requires --verification-receipt"),
            ("wrong receipt hash", receipt_path, "e" * 64,
             "does not equal the separate verify job"),
        ]
        cases.append(("wrong floor",) + rewritten(
            lambda doc: doc.__setitem__("minimumAppVersion", "1.7.64"))
            + ("minimum App floor differs",))
        cases.append(("wrong source commit",) + rewritten(
            lambda doc: doc.__setitem__("sourceCommit", "f" * 40))
            + ("sourceCommit does not bind",))
        cases.append(("wrong tooling commit",) + rewritten(
            lambda doc: doc.__setitem__("toolingCommit", "f" * 40))
            + ("toolingCommit does not bind",))
        cases.append(("wrong entry manifest",) + rewritten(
            lambda doc: doc["upstream"][0].__setitem__("manifestSha256",
                                                       "f" * 64))
            + ("upstream identity",))
        cases.append(("upstream not verified",) + rewritten(
            lambda doc: doc["upstreamVerification"].__setitem__("verified",
                                                                False))
            + ("does not prove a successful upstream",))

        for label, path, sha, needle in cases:
            with self.subTest(label=label):
                proc, _out = self._run(
                    "sign", fixture["tooling"], fixture["data"],
                    fixture["data_commit"], fixture["baseline"],
                    fixture["baseline_commit"], "1.7.63",
                    out=self.tmp / ("proof-" + label.replace(" ", "-")),
                    proof=False, verification_receipt=path,
                    verification_sha256=sha, env_extra=bad_key)
                self._expect_refusal(proc, needle)
                self.assertNotIn("strict base64", proc.stderr)




if __name__ == "__main__":
    unittest.main()
