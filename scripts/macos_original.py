#!/usr/bin/env python3
"""macOS original Skill candidate producer and author validator.

This module implements the *author input* side of
``docs/MACOS-ORIGINAL-CONTRACT.md``: a bounded producer that fetches one
immutable upstream commit, stages byte-exact original files with their Git
modes, and emits a proposal that still lacks the release owner's verified
``minimumAppVersion``; plus the author validator used by that producer and by
the release owner's preflight.

Public interface (shared with the signing/publication lane):

  * ``canonical_manifest_digest(files) -> str``
  * ``validate_catalog(document, source_root=None, previous_catalogs=()) -> int``

``source_root`` is ``Path | None``; when set it must contain the staged package
at ``<source_root>/<id>/<path>``. ``previous_catalogs`` is a sequence of parsed
complete macOS-original feed documents; a same ``(id, version)`` pair must keep
its exact upstream commit and file identity.

What this module deliberately does NOT do: sign, publish, install, execute or
qualify anything. It never reads a private key and never writes under the Hub
checkout unless the caller points it there. Upstream fetching uses read-only
Git plumbing (``init``/``fetch``/``ls-tree``/``cat-file``) with hooks and local
configuration disabled; source content is never executed and no working tree is
checked out.

CLI:

  python3 scripts/macos_original.py prepare --spec spec.json --output-root DIR
  python3 scripts/macos_original.py finalize --proposal DIR/1.0.1/proposal.json \
      [--proposal DIR/1.0.0/proposal.json] --minimum-app-version X.Y.Z \
      --output-dir DIR/feeds
  python3 scripts/macos_original.py validate macos/catalog.json \
      [--source-root DIR] [--previous DIR/1.0.0.catalog.json]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath

CHANNEL = "macos-original"
SCHEMA_VERSION = 1
FEED_FIELDS = frozenset(("schemaVersion", "channel", "entries"))
ENTRY_FIELDS = frozenset(
    (
        "id",
        "name",
        "description",
        "category",
        "version",
        "minimumAppVersion",
        "repository",
        "subdirectory",
        "commit",
        "license",
        "licensePath",
        "digest",
        "files",
    )
)
FILE_FIELDS = frozenset(("path", "sourcePath", "sha256", "bytes", "mode"))
BILINGUAL_FIELDS = frozenset(("en", "zh-Hans"))
SOURCE_SPEC_FIELDS = frozenset(
    (
        "id",
        "name",
        "description",
        "category",
        "version",
        "repository",
        "subdirectory",
        "commit",
        "license",
        "licensePath",
        "licenseSourcePath",
    )
)
SOURCE_SPEC_OPTIONAL_FIELDS = frozenset(("expectAncestor",))
PROPOSAL_FIELDS = frozenset(("schemaVersion", "kind", "status", "entry", "sourceRoot", "provenance"))
PROVENANCE_FILE_FIELDS = frozenset(("path", "sourcePath", "gitBlob", "gitMode", "sha256", "bytes"))
PROVENANCE_FIELDS = frozenset(
    (
        "schemaVersion",
        "kind",
        "repository",
        "repositoryUrl",
        "commit",
        "commitTree",
        "subdirectory",
        "tree",
        "licenseSourcePath",
        "licensePath",
        "fetchedAt",
        "gitVersion",
        "branchRefs",
        "expectAncestor",
        "files",
        "digest",
    )
)
CATEGORIES = frozenset(
    (
        "office-documents",
        "writing-communication",
        "web-development",
        "research-data",
        "design-creation",
        "product-requirements",
        "productivity-organization",
    )
)
MODES = frozenset(("100644", "100755"))
MAX_FEED_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 256
MAX_FILES = 2048
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_PACKAGE_BYTES = 16 * 1024 * 1024
MAX_PATH_BYTES = 1024
MAX_NAME_CHARS = 128
MAX_LICENSE_CHARS = 256
ZERO_FLOOR = "0.0.0"

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\Z")

GIT_SAFETY = (
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "gc.auto=0",
    "-c",
    "maintenance.auto=false",
    "-c",
    "core.symlinks=false",
    "-c",
    "advice.detachedHead=false",
)


class MacOriginalError(ValueError):
    """A fail-closed author/producer check failed."""


def _fail(reason):
    raise MacOriginalError(reason)


# ---------------------------------------------------------------------------
# shared primitives
# ---------------------------------------------------------------------------


def _require_text(value, reason, *, allow_empty=False, max_chars=None, control=False):
    if not isinstance(value, str):
        _fail("%s must be a string" % reason)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("%s contains an unpaired surrogate" % reason)
    if not allow_empty and not value.strip():
        _fail("%s must not be empty" % reason)
    if max_chars is not None and len(value) > max_chars:
        _fail("%s exceeds %d characters" % (reason, max_chars))
    if control and any(ord(ch) < 0x20 for ch in value):
        _fail("%s contains a control character" % reason)
    if "\0" in value:
        _fail("%s must not contain NUL" % reason)
    return value


def _relative_path(value, reason):
    """A safe, canonical, NFC, UTF-8 POSIX relative path."""
    if not isinstance(value, str):
        _fail("%s must be a string" % reason)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("%s contains an unpaired surrogate" % reason)
    if not 0 < len(encoded) <= MAX_PATH_BYTES:
        _fail("%s must be 1..%d UTF-8 bytes" % (reason, MAX_PATH_BYTES))
    if value.startswith("/") or "\\" in value or "\0" in value:
        _fail("%s must be a safe relative POSIX path" % reason)
    if any(part in ("", ".", "..") for part in value.split("/")):
        _fail("%s must not contain empty, '.' or '..' segments" % reason)
    if any(ord(ch) < 0x20 for ch in value):
        _fail("%s must not contain control characters" % reason)
    if unicodedata.normalize("NFC", value) != value:
        _fail("%s must be NFC-normalized" % reason)
    return value


def _version(value, reason, *, refuse_zero=False):
    if not isinstance(value, str) or VERSION.fullmatch(value) is None:
        _fail("%s must be strict major.minor.patch" % reason)
    if refuse_zero and value == ZERO_FLOOR:
        _fail("%s must be the release owner's verified capable App version, not 0.0.0" % reason)
    return value


def _identifier(value):
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        _fail("id must match [a-z][a-z0-9-]{0,63}")
    if value.endswith("-") or "--" in value:
        _fail("id must not end with '-' or contain '--'")
    return value


def _bilingual(value, reason, max_chars=None):
    if not isinstance(value, dict) or set(value) != BILINGUAL_FIELDS:
        _fail("%s must be an object with exactly en and zh-Hans" % reason)
    out = {}
    for language in ("en", "zh-Hans"):
        text = _require_text(
            value[language],
            "%s.%s" % (reason, language),
            control=(reason == "name"),
            max_chars=max_chars,
        )
        out[language] = text
    return out


def _repository(value):
    if not isinstance(value, str):
        _fail("repository must be an owner/repo string")
    parts = value.split("/")
    if len(parts) != 2 or not all(COMPONENT.fullmatch(part) for part in parts):
        _fail("repository must be exactly owner/repo with GitHub-safe components")
    return value


def _license(value):
    text = _require_text(value, "license", max_chars=MAX_LICENSE_CHARS)
    if any(ord(ch) < 0x20 for ch in text):
        _fail("license must not contain control characters")
    return text


def _check_identity(entry):
    _identifier(entry["id"])
    _bilingual(entry["name"], "name", max_chars=MAX_NAME_CHARS)
    _bilingual(entry["description"], "description")
    if entry["category"] not in CATEGORIES:
        _fail("category must be one of the seven existing categories")
    _version(entry["version"], "version")
    _repository(entry["repository"])
    if not isinstance(entry["subdirectory"], str):
        _fail("subdirectory must be a string")
    if entry["subdirectory"]:
        _relative_path(entry["subdirectory"], "subdirectory")
    if not isinstance(entry["commit"], str) or HEX40.fullmatch(entry["commit"]) is None:
        _fail("commit must be 40 lowercase hexadecimal characters")
    _license(entry["license"])
    _relative_path(entry["licensePath"], "licensePath")


# ---------------------------------------------------------------------------
# digest and structural validation
# ---------------------------------------------------------------------------


def canonical_manifest_digest(files):
    """SHA-256 of the frozen four-field, path-sorted, compact UTF-8 manifest.

    ``bytes`` and every other key are deliberately excluded from the digest
    payload; the declared byte count is still validated separately. Inputs are
    never mutated.
    """
    if isinstance(files, (str, bytes, dict)) or files is None:
        _fail("files must be a sequence of file objects")
    rows = []
    seen = set()
    for file in files:
        if not isinstance(file, dict):
            _fail("each file must be an object")
        missing = frozenset(("path", "sourcePath", "sha256", "mode")).difference(file)
        if missing:
            _fail("file is missing %s" % ", ".join(sorted(missing)))
        path = _relative_path(file["path"], "file path")
        source_path = _relative_path(file["sourcePath"], "sourcePath")
        sha256 = file["sha256"]
        if not isinstance(sha256, str) or HEX64.fullmatch(sha256) is None:
            _fail("file sha256 must be 64 lowercase hexadecimal characters")
        if file["mode"] not in MODES:
            _fail("file mode must be 100644 or 100755")
        if path in seen:
            _fail("duplicate file path %r" % path)
        seen.add(path)
        rows.append({"path": path, "sourcePath": source_path, "sha256": sha256, "mode": file["mode"]})
    if not rows:
        _fail("a manifest digest requires at least one file")
    payload = json.dumps(
        sorted(rows, key=lambda row: row["path"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _check_files(entry):
    files = entry["files"]
    if not isinstance(files, list) or not 0 < len(files) <= MAX_FILES:
        _fail("files must be a list of 1..%d file objects" % MAX_FILES)
    expected_prefix = entry["subdirectory"] + "/" if entry["subdirectory"] else ""
    paths = set()
    total = 0
    for file in files:
        if not isinstance(file, dict) or set(file) != FILE_FIELDS:
            _fail("each file must have exactly path, sourcePath, sha256, bytes and mode")
        path = _relative_path(file["path"], "file path")
        if path in paths:
            _fail("duplicate file path %r" % path)
        paths.add(path)
        source_path = _relative_path(file["sourcePath"], "sourcePath")
        if path != entry["licensePath"] and source_path != expected_prefix + path:
            _fail("sourcePath %r does not match subdirectory/path" % source_path)
        if not isinstance(file["sha256"], str) or HEX64.fullmatch(file["sha256"]) is None:
            _fail("file sha256 must be 64 lowercase hexadecimal characters")
        if type(file["bytes"]) is not int or not 0 <= file["bytes"] <= MAX_FILE_BYTES:
            _fail("file bytes must be an integer in 0..%d" % MAX_FILE_BYTES)
        if file["mode"] not in MODES:
            _fail("file mode must be 100644 or 100755")
        total += file["bytes"]
    if total > MAX_PACKAGE_BYTES:
        _fail("package declares more than %d bytes" % MAX_PACKAGE_BYTES)
    if "SKILL.md" not in paths:
        _fail("package must contain SKILL.md")
    if entry["licensePath"] not in paths:
        _fail("licensePath must appear in files")
    if canonical_manifest_digest(files) != entry["digest"]:
        _fail("manifest digest differs from the frozen recipe")


def _check_entry(entry, source_root=None):
    if not isinstance(entry, dict) or set(entry) != ENTRY_FIELDS:
        _fail("an entry must have exactly the thirteen declared fields")
    _check_identity(entry)
    _version(entry["minimumAppVersion"], "minimumAppVersion", refuse_zero=True)
    if not isinstance(entry["digest"], str) or HEX64.fullmatch(entry["digest"]) is None:
        _fail("digest must be 64 lowercase hexadecimal characters")
    _check_files(entry)
    if source_root is not None:
        _check_staged(entry, Path(source_root))


def _check_staged(entry, source_root):
    if source_root.is_symlink():
        _fail("source root must not be a symlink")
    root = source_root / entry["id"]
    if root.is_symlink() or not root.is_dir():
        _fail("staged package directory %s is missing" % entry["id"])
    resolved_root = root.resolve()
    actual = set()
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        for name in list(dirnames):
            candidate = Path(dirpath) / name
            if candidate.is_symlink():
                _fail("staged package contains a directory symlink: %s" % candidate.relative_to(root))
        for name in filenames:
            candidate = Path(dirpath) / name
            if candidate.is_symlink():
                _fail("staged package contains a symlink: %s" % candidate.relative_to(root))
            relative = candidate.relative_to(root).as_posix()
            _relative_path(relative, "staged file path")
            actual.add(relative)
    declared = {file["path"]: file for file in entry["files"]}
    extra = actual.difference(declared)
    if extra:
        _fail("staged package contains undeclared file(s): %s" % ", ".join(sorted(extra)))
    for path, file in sorted(declared.items()):
        target = root.joinpath(*PurePosixPath(path).parts)
        if target.is_symlink() or not target.is_file():
            _fail("staged file is missing: %s" % path)
        resolved = target.resolve()
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            _fail("staged file escapes the package: %s" % path)
        data = resolved.read_bytes()
        if len(data) != file["bytes"]:
            _fail("staged byte count differs for %s" % path)
        if hashlib.sha256(data).hexdigest() != file["sha256"]:
            _fail("staged sha256 differs for %s" % path)
        if bool(resolved.stat().st_mode & 0o111) != (file["mode"] == "100755"):
            _fail("staged executable mode differs for %s" % path)


def _check_feed(document, source_root=None):
    if not isinstance(document, dict) or set(document) != FEED_FIELDS:
        _fail("feed must have exactly schemaVersion, channel and entries")
    if type(document["schemaVersion"]) is not int or document["schemaVersion"] != SCHEMA_VERSION:
        _fail("schemaVersion must be the JSON integer 1")
    if document["channel"] != CHANNEL:
        _fail("channel must be %r" % CHANNEL)
    entries = document["entries"]
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_ENTRIES:
        _fail("entries must be a non-empty list of at most %d entries" % MAX_ENTRIES)
    seen = set()
    for entry in entries:
        _check_entry(entry, source_root)
        if entry["id"] in seen:
            _fail("duplicate id %r in feed" % entry["id"])
        seen.add(entry["id"])
    try:
        compact = json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        _fail("feed is not canonical JSON: %s" % error)
    if len(compact) > MAX_FEED_BYTES:
        _fail("feed exceeds the %d-byte cap" % MAX_FEED_BYTES)
    return entries


def _entry_identity(entry):
    """Identity that a published (id, version) may never change."""
    files = [
        {
            "path": file["path"],
            "sourcePath": file["sourcePath"],
            "sha256": file["sha256"],
            "bytes": file["bytes"],
            "mode": file["mode"],
        }
        for file in sorted(entry["files"], key=lambda row: row["path"])
    ]
    return {
        "repository": entry["repository"],
        "subdirectory": entry["subdirectory"],
        "commit": entry["commit"],
        "licensePath": entry["licensePath"],
        "digest": entry["digest"],
        "files": files,
    }


def validate_catalog(document, source_root=None, previous_catalogs=()):
    """Validate one complete macOS-original feed; return its entry count.

    ``source_root`` optionally checks staged bytes/modes at
    ``<source_root>/<id>/<path>``. ``previous_catalogs`` is a sequence of parsed
    earlier complete feeds; a same ``(id, version)`` entry must preserve its
    upstream commit, repository/subdirectory and every file's path,
    sourcePath, sha256, bytes and mode. A new version is permitted. Inputs are
    never mutated.
    """
    if isinstance(previous_catalogs, (dict, str, bytes)) or previous_catalogs is None:
        _fail("previous_catalogs must be a sequence of parsed feed documents")
    entries = _check_feed(document, source_root)
    history = {}
    for previous in previous_catalogs:
        previous_entries = _check_feed(previous, None)
        for entry in previous_entries:
            key = (entry["id"], entry["version"])
            identity = _entry_identity(entry)
            if key in history and history[key] != identity:
                _fail("previous catalogs disagree about %s %s" % key)
            history[key] = identity
    for entry in entries:
        key = (entry["id"], entry["version"])
        if key in history and history[key] != _entry_identity(entry):
            _fail(
                "%s %s was already published with a different commit or file identity; "
                "choose a new version" % key
            )
    return len(entries)


# ---------------------------------------------------------------------------
# strict JSON I/O
# ---------------------------------------------------------------------------


def _reject_constant(value):
    _fail("feed contains the non-JSON constant %s" % value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON key %r" % key)
        result[key] = value
    return result


def load_json(path, max_bytes=MAX_FEED_BYTES):
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        _fail("cannot read %s: %s" % (path, error))
    if len(data) > max_bytes:
        _fail("%s exceeds the %d-byte cap" % (path, max_bytes))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        _fail("%s is not UTF-8: %s" % (path, error))
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as error:
        _fail("%s is not valid JSON: %s" % (path, error))


def _canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            pass
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _pretty_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# read-only upstream Git access
# ---------------------------------------------------------------------------


def _git_environment(home):
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/usr/bin/false",
            "SSH_ASKPASS": "/usr/bin/false",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        }
    )
    return environment


def _run(command, environment, reason, *, input_bytes=None):
    try:
        process = subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
        )
    except OSError as error:
        _fail("%s: cannot run %s: %s" % (reason, command[0], error))
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", "replace").strip()
        _fail("%s: %s" % (reason, detail or ("%s exited %d" % (command[0], process.returncode))))
    return process.stdout


def _git(repo, arguments, environment, reason, *, text=False):
    output = _run(["git"] + list(GIT_SAFETY) + ["-C", str(repo)] + list(arguments), environment, reason)
    return output.decode("utf-8") if text else output


def _fetch_upstream(repository, commit, ancestor=None, source_url=None):
    """Fetch the commit graph (no blobs eagerly); return a temp repo."""
    if not HEX40.fullmatch(commit):
        _fail("commit must be 40 lowercase hexadecimal characters")
    if ancestor is not None and not HEX40.fullmatch(ancestor):
        _fail("expectAncestor must be 40 lowercase hexadecimal characters")
    if source_url is None:
        url = "https://github.com/%s.git" % _repository(repository)
    elif source_url.startswith("https://") or source_url.startswith("file://"):
        url = source_url
    else:
        _fail("source_url must be https:// or file://")
    temporary = Path(tempfile.mkdtemp(prefix="macos-original-git-"))
    home = temporary / "home"
    home.mkdir()
    repo = temporary / "repo.git"
    environment = _git_environment(home)
    try:
        _run(["git"] + list(GIT_SAFETY) + ["init", "--quiet", "--bare", str(repo)], environment, "git init failed")
        heads = "+refs/heads/*:refs/remotes/origin/*"
        output = _run(
            ["git"] + list(GIT_SAFETY) + ["-C", str(repo), "fetch", "--quiet", "--filter=blob:none", "--no-tags", url, heads],
            environment,
            "upstream fetch failed",
        )
        del output
        for wanted in (commit, ancestor):
            if wanted is None:
                continue
            present = subprocess.run(
                ["git"] + list(GIT_SAFETY) + ["-C", str(repo), "cat-file", "-e", wanted + "^{commit}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
                check=False,
            )
            if present.returncode != 0:
                _run(
                    ["git"] + list(GIT_SAFETY) + ["-C", str(repo), "fetch", "--quiet", "--filter=blob:none", "--no-tags", url, wanted],
                    environment,
                    "upstream commit fetch failed",
                )
        containing = _git(repo, ["for-each-ref", "--contains", commit, "--format=%(refname)", "refs/remotes/origin"], environment, "cannot inspect refs", text=True).split()
        if not containing:
            _fail("commit %s is not reachable from any fetched upstream branch" % commit)
        if ancestor is not None:
            ancestry = subprocess.run(
                ["git"] + list(GIT_SAFETY) + ["-C", str(repo), "merge-base", "--is-ancestor", ancestor, commit],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=environment,
                check=False,
            )
            if ancestry.returncode != 0:
                _fail("expectAncestor %s is not a true ancestor of %s" % (ancestor, commit))
        git_version = _git(repo, ["--version"], environment, "git version failed", text=True).strip()
        return temporary, repo, environment, sorted(containing), git_version
    except BaseException:
        shutil.rmtree(str(temporary), ignore_errors=True)
        raise


def _tree_rows(repo, environment, commit, subdirectory):
    arguments = ["ls-tree", "-r", "-z", commit]
    if subdirectory:
        arguments.extend(["--", subdirectory])
    raw = _git(repo, arguments, environment, "cannot list the upstream tree")
    rows = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        header, separator, raw_path = record.partition(b"\t")
        if not separator:
            _fail("unexpected git ls-tree record")
        parts = header.split(b" ")
        if len(parts) != 3:
            _fail("unexpected git ls-tree header")
        mode, kind, blob = (part.decode("ascii") for part in parts)
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            _fail("upstream tree contains a non-UTF-8 path")
        if kind != "blob":
            _fail("upstream tree contains a non-file entry at %r" % path)
        if mode not in MODES:
            _fail("upstream tree entry %r has unsupported Git mode %s (symlinks/submodules are refused)" % (path, mode))
        if subdirectory:
            prefix = subdirectory + "/"
            if not path.startswith(prefix):
                _fail("upstream tree path %r escapes subdirectory" % path)
            relative = path[len(prefix):]
        else:
            relative = path
        _relative_path(relative, "upstream file path")
        rows.append({"path": relative, "mode": mode, "blob": blob})
    if not rows:
        _fail("upstream subdirectory is empty or missing")
    return rows


def _blob_sized(repo, environment, blob):
    raw = _git(repo, ["cat-file", "-s", blob], environment, "cannot read upstream blob size")
    try:
        size = int(raw.strip())
    except ValueError:
        _fail("upstream blob size is not an integer")
    if size > MAX_FILE_BYTES:
        _fail("upstream file exceeds the %d-byte limit" % MAX_FILE_BYTES)
    return size


def _blob(repo, environment, blob):
    # ``git cat-file`` verifies the object id and checksum itself; never run
    # any upstream content and never apply a working-tree filter.
    return _git(repo, ["cat-file", "blob", blob], environment, "cannot read upstream blob")


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


def _validate_spec(spec):
    if not isinstance(spec, dict):
        _fail("spec must be a JSON object")
    if "minimumAppVersion" in spec:
        _fail("the source spec must not carry minimumAppVersion; it is supplied only at finalize")
    keys = set(spec)
    allowed = SOURCE_SPEC_FIELDS | SOURCE_SPEC_OPTIONAL_FIELDS
    if not SOURCE_SPEC_FIELDS.issubset(keys) or not keys.issubset(allowed):
        missing = SOURCE_SPEC_FIELDS.difference(keys)
        unknown = keys.difference(allowed)
        if missing:
            _fail("spec is missing %s" % ", ".join(sorted(missing)))
        _fail("spec has unknown field(s) %s" % ", ".join(sorted(unknown)))
    probe = {
        "id": spec["id"],
        "name": _bilingual(spec["name"], "name"),
        "description": _bilingual(spec["description"], "description"),
        "category": spec["category"],
        "version": spec["version"],
        "repository": spec["repository"],
        "subdirectory": spec["subdirectory"],
        "commit": spec["commit"],
        "license": spec["license"],
        "licensePath": spec["licensePath"],
    }
    _check_identity(probe)
    _relative_path(spec["licenseSourcePath"], "licenseSourcePath")
    if "expectAncestor" in spec and (
        not isinstance(spec["expectAncestor"], str) or HEX40.fullmatch(spec["expectAncestor"]) is None
    ):
        _fail("expectAncestor must be 40 lowercase hexadecimal characters")
    return probe


def prepare_proposal(spec, output_root, source_url=None, fetched_at=None, keep_cache=False):
    """Fetch, stage and write one proposal without a capability floor.

    Returns ``(proposal_path, proposal)``. No feed is written: without the
    release owner's verified minimum App version no signable/publishable
    document exists.
    """
    entry_core = _validate_spec(spec)
    if source_url is None:
        source_url = "https://github.com/%s.git" % _repository(entry_core["repository"])
    elif not (source_url.startswith("https://") or source_url.startswith("file://")):
        _fail("source_url must be https:// or file://")
    output_root = Path(output_root)
    target = output_root / entry_core["id"] / entry_core["version"]
    if target.exists() or target.is_symlink():
        _fail("proposal output already exists: %s" % target)
    fetched_at = fetched_at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ancestor = spec.get("expectAncestor")
    temporary, repo, environment, branch_refs, git_version = _fetch_upstream(
        entry_core["repository"], entry_core["commit"], ancestor, source_url
    )
    staging_parent = output_root
    staging_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(dir=str(staging_parent), prefix=".staging-"))
    try:
        rows = _tree_rows(repo, environment, entry_core["commit"], entry_core["subdirectory"])
        rows.sort(key=lambda row: row["path"])
        blob_by_path = {row["path"]: row["blob"] for row in rows}
        package_root = stage / entry_core["id"]
        files = []
        total = 0
        for row in rows:
            size = _blob_sized(repo, environment, row["blob"])
            data = _blob(repo, environment, row["blob"])
            if len(data) != size:
                _fail("upstream blob size changed while reading %r" % row["path"])
            destination = package_root.joinpath(*PurePosixPath(row["path"]).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            os.chmod(destination, 0o755 if row["mode"] == "100755" else 0o644)
            source_path = (
                entry_core["subdirectory"] + "/" + row["path"]
                if entry_core["subdirectory"]
                else row["path"]
            )
            files.append(
                {
                    "path": row["path"],
                    "sourcePath": source_path,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "mode": row["mode"],
                }
            )
            total += len(data)
        if len(files) > MAX_FILES or total > MAX_PACKAGE_BYTES:
            _fail("upstream package exceeds the file count or size limit")

        license_source = spec["licenseSourcePath"]
        subdirectory = entry_core["subdirectory"]
        inside = (not subdirectory) or license_source.startswith(subdirectory + "/")
        if inside:
            relative = license_source if not subdirectory else license_source[len(subdirectory) + 1:]
            if entry_core["licensePath"] != relative:
                _fail("licensePath must equal the in-package path of licenseSourcePath")
            if relative not in blob_by_path:
                _fail("declared license is missing from the upstream package")
        else:
            if entry_core["licensePath"] in blob_by_path:
                _fail("licensePath collides with a non-license package file; declare the in-package license")
            license_raw = _git(
                repo,
                ["ls-tree", "-z", entry_core["commit"], "--", license_source],
                environment,
                "cannot read license tree",
            )
            records = [record for record in license_raw.split(b"\0") if record]
            if len(records) != 1:
                _fail("license file %r was not found exactly once at commit %s" % (license_source, entry_core["commit"]))
            header, separator, raw_path = records[0].partition(b"\t")
            if not separator or raw_path.decode("utf-8", "replace") != license_source:
                _fail("license tree lookup is ambiguous")
            parts = header.split(b" ")
            if len(parts) != 3:
                _fail("unexpected license tree record")
            mode, kind, blob = (part.decode("ascii") for part in parts)
            if kind != "blob" or mode not in MODES:
                _fail("license must be a regular Git file with mode 100644 or 100755")
            size = _blob_sized(repo, environment, blob)
            data = _blob(repo, environment, blob)
            if len(data) != size:
                _fail("upstream license size changed while reading")
            destination = package_root.joinpath(*PurePosixPath(entry_core["licensePath"]).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            os.chmod(destination, 0o755 if mode == "100755" else 0o644)
            files.append(
                {
                    "path": entry_core["licensePath"],
                    "sourcePath": license_source,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "mode": mode,
                }
            )
            blob_by_path[entry_core["licensePath"]] = blob
            total += len(data)

        files.sort(key=lambda row: row["path"])
        if len(files) > MAX_FILES or total > MAX_PACKAGE_BYTES:
            _fail("upstream package exceeds the file count or size limit")
        entry = dict(entry_core)
        entry["digest"] = canonical_manifest_digest(files)
        entry["files"] = files
        probe = dict(entry)
        probe["minimumAppVersion"] = "0.0.1"  # in-memory structural probe only; never written
        _check_entry(probe, stage)
        del probe

        manifest = {
            "schemaVersion": 1,
            "kind": "macos-original-proposal",
            "status": "awaiting-minimum-app-version",
            "entry": entry,
            "sourceRoot": "source",
            "provenance": "provenance.json",
        }
        provenance_files = [
            {
                "path": file["path"],
                "sourcePath": file["sourcePath"],
                "gitBlob": blob_by_path[file["path"]],
                "gitMode": file["mode"],
                "sha256": file["sha256"],
                "bytes": file["bytes"],
            }
            for file in files
        ]
        commit_tree = _git(
            repo,
            ["rev-parse", entry_core["commit"] + "^{tree}"],
            environment,
            "cannot resolve commit tree",
            text=True,
        ).strip()
        provenance = {
            "schemaVersion": 1,
            "kind": "macos-original-source-provenance",
            "repository": entry_core["repository"],
            "repositoryUrl": "https://github.com/%s" % entry_core["repository"],
            "commit": entry_core["commit"],
            "commitTree": commit_tree,
            "subdirectory": subdirectory,
            "tree": _git(
                repo,
                ["rev-parse", entry_core["commit"] + ":" + subdirectory],
                environment,
                "cannot resolve upstream subtree",
                text=True,
            ).strip()
            if subdirectory
            else commit_tree,
            "licenseSourcePath": license_source,
            "licensePath": entry_core["licensePath"],
            "fetchedAt": fetched_at,
            "gitVersion": git_version,
            "branchRefs": branch_refs,
            "expectAncestor": {"commit": ancestor, "isAncestor": True} if ancestor else None,
            "files": provenance_files,
            "digest": entry["digest"],
        }
        staged_source = stage / "source"
        staged_source.mkdir()
        os.replace(str(package_root), str(staged_source / entry_core["id"]))
        _write_atomic(stage / "proposal.json", _pretty_json(manifest))
        _write_atomic(stage / "provenance.json", _pretty_json(provenance))
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(stage), str(target))
    except BaseException:
        shutil.rmtree(str(stage), ignore_errors=True)
        raise
    finally:
        if keep_cache:
            print("upstream Git cache retained at %s" % temporary, file=sys.stderr)
        else:
            shutil.rmtree(str(temporary), ignore_errors=True)
    return target / "proposal.json", manifest


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------


def _load_proposal(path):
    path = Path(path)
    proposal = load_json(path)
    if not isinstance(proposal, dict) or set(proposal) != PROPOSAL_FIELDS:
        _fail("proposal must have exactly %s" % ", ".join(sorted(PROPOSAL_FIELDS)))
    if proposal["schemaVersion"] != 1 or proposal["kind"] != "macos-original-proposal":
        _fail("proposal has the wrong schemaVersion or kind")
    if proposal["status"] != "awaiting-minimum-app-version":
        _fail("proposal is not awaiting a minimum App version")
    entry = proposal["entry"]
    expected = ENTRY_FIELDS.difference(("minimumAppVersion",))
    if not isinstance(entry, dict) or set(entry) != expected:
        _fail("proposal entry must contain every declared field except minimumAppVersion")
    _check_identity(entry)
    if not isinstance(entry["digest"], str) or HEX64.fullmatch(entry["digest"]) is None:
        _fail("proposal entry digest is invalid")
    _check_files(entry)
    relative_root = _relative_path(proposal["sourceRoot"], "sourceRoot")
    source_root = path.parent.joinpath(*PurePosixPath(relative_root).parts)
    _check_staged(entry, source_root)

    provenance = _load_json_relative(path.parent / proposal["provenance"])
    if not isinstance(provenance, dict) or set(provenance) != PROVENANCE_FIELDS:
        _fail("provenance must have exactly %s" % ", ".join(sorted(PROVENANCE_FIELDS)))
    if provenance["kind"] != "macos-original-source-provenance" or provenance["schemaVersion"] != 1:
        _fail("provenance has the wrong kind or schemaVersion")
    if provenance["commit"] != entry["commit"] or provenance["subdirectory"] != entry["subdirectory"]:
        _fail("provenance source identity differs from the proposal")
    if provenance["digest"] != entry["digest"]:
        _fail("provenance digest differs from the proposal")
    if provenance["licensePath"] != entry["licensePath"]:
        _fail("provenance licensePath differs from the proposal")
    _relative_path(provenance["licenseSourcePath"], "provenance licenseSourcePath")
    if not isinstance(provenance["files"], list):
        _fail("provenance files must be a list")
    actual_files = {}
    for file in provenance["files"]:
        if not isinstance(file, dict) or set(file) != PROVENANCE_FILE_FIELDS:
            _fail("each provenance file must have exactly %s" % ", ".join(sorted(PROVENANCE_FILE_FIELDS)))
        actual_files[file["path"]] = (file["sourcePath"], file["sha256"], file["bytes"], file["gitMode"])
    expected_files = {
        file["path"]: (file["sourcePath"], file["sha256"], file["bytes"], file["mode"])
        for file in entry["files"]
    }
    if actual_files != expected_files:
        _fail("provenance files differ from the proposal")
    return entry, source_root


def _load_json_relative(path):
    return load_json(path, max_bytes=MAX_FEED_BYTES)


def finalize(proposals, minimum_app_version, output=None, output_dir=None, previous=()):
    """Build one feed per version of a single id from staged proposals."""
    _version(minimum_app_version, "minimum-app-version", refuse_zero=True)
    if not proposals:
        _fail("at least one --proposal is required")
    loaded = [_load_proposal(path) for path in proposals]
    ids = {entry["id"] for entry, _ in loaded}
    if len(ids) != 1:
        _fail("all proposals in one finalize run must share one skill id")
    seen_versions = set()
    for entry, _ in loaded:
        if entry["version"] in seen_versions:
            _fail("duplicate proposal for %s %s" % (entry["id"], entry["version"]))
        seen_versions.add(entry["version"])
    previous_documents = [load_json(path) for path in previous]
    for document in previous_documents:
        _check_feed(document, None)

    ordered = sorted(loaded, key=lambda item: _version_key(item[0]["version"]))
    built = []
    for entry, source_root in ordered:
        entry = dict(entry)
        entry["minimumAppVersion"] = minimum_app_version
        entry = {
            "id": entry["id"],
            "name": entry["name"],
            "description": entry["description"],
            "category": entry["category"],
            "version": entry["version"],
            "minimumAppVersion": entry["minimumAppVersion"],
            "repository": entry["repository"],
            "subdirectory": entry["subdirectory"],
            "commit": entry["commit"],
            "license": entry["license"],
            "licensePath": entry["licensePath"],
            "digest": entry["digest"],
            "files": entry["files"],
        }
        feed = {"schemaVersion": SCHEMA_VERSION, "channel": CHANNEL, "entries": [entry]}
        validate_catalog(
            feed,
            source_root=source_root,
            previous_catalogs=list(previous_documents) + [item[1] for item in built],
        )
        built.append((entry, feed))

    if output is not None and len(built) != 1:
        _fail("--output is only valid with exactly one proposal")
    if output is None and output_dir is None:
        _fail("--output or --output-dir is required")
    written = []
    for entry, feed in built:
        data = _canonical_json(feed)
        if len(data) > MAX_FEED_BYTES:
            _fail("feed exceeds the %d-byte cap" % MAX_FEED_BYTES)
        destination = (
            Path(output)
            if output is not None
            else Path(output_dir) / ("%s-%s.catalog.json" % (entry["id"], entry["version"]))
        )
        _write_atomic(destination, data)
        written.append((destination, hashlib.sha256(data).hexdigest(), len(data), entry["version"]))
    return written


def _version_key(value):
    return tuple(int(part) for part in value.split("."))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_validation(count, prior):
    print(
        "Validated %d macOS-original declarations against %d prior feed(s); "
        "no execution qualification performed." % (count, prior)
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="macOS original Skill candidate producer/validator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="fetch, stage and write a floor-less proposal")
    prepare_parser.add_argument("--spec", required=True, type=Path)
    prepare_parser.add_argument("--output-root", required=True, type=Path)
    prepare_parser.add_argument("--keep-cache", action="store_true", help="retain the temporary Git cache")

    finalize_parser = subparsers.add_parser("finalize", help="build feed(s) once the floor is verified")
    finalize_parser.add_argument("--proposal", required=True, action="append", type=Path)
    finalize_parser.add_argument("--minimum-app-version", required=True)
    finalize_parser.add_argument("--output", type=Path)
    finalize_parser.add_argument("--output-dir", type=Path)
    finalize_parser.add_argument("--previous", action="append", default=[], type=Path)

    validate_parser = subparsers.add_parser("validate", help="read-only feed/history validation")
    validate_parser.add_argument("catalog", type=Path)
    validate_parser.add_argument("--source-root", type=Path)
    validate_parser.add_argument("--previous", action="append", default=[], type=Path)

    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "prepare":
            spec = load_json(arguments.spec, max_bytes=64 * 1024)
            path, proposal = prepare_proposal(spec, arguments.output_root, keep_cache=arguments.keep_cache)
            entry = proposal["entry"]
            print("Staged %s %s at %s" % (entry["id"], entry["version"], path.parent))
            print(
                "commit=%s files=%d bytes=%d digest=%s minimumAppVersion=<pending>"
                % (
                    entry["commit"],
                    len(entry["files"]),
                    sum(file["bytes"] for file in entry["files"]),
                    entry["digest"],
                )
            )
        elif arguments.command == "finalize":
            written = finalize(
                arguments.proposal,
                arguments.minimum_app_version,
                output=arguments.output,
                output_dir=arguments.output_dir,
                previous=arguments.previous,
            )
            for path, digest, size, version in written:
                print("Wrote %s version=%s bytes=%d sha256=%s" % (path, version, size, digest))
        else:
            document = load_json(arguments.catalog)
            previous = [load_json(path) for path in arguments.previous]
            count = validate_catalog(document, arguments.source_root, previous)
            _print_validation(count, len(previous))
    except MacOriginalError as error:
        print("error: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
