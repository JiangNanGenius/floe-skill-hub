#!/usr/bin/env python3
"""DATA-ONLY candidate signing for the macOS original Skill channel.

This tool produces the CANDIDATE ``macos/catalog.json`` signature and an
authenticated receipt for the reserved macOS original feed. It publishes
nothing, installs nothing and proves no macOS execution or App acceptance.
The feed pair is the exact candidate feed bytes carried by one clean official
Hub commit S plus a fresh Ed25519 envelope under the existing production
identity.

Trust model (fixed):

* T — one pinned, reviewed tooling checkout of the official Hub. ALL code is
  imported from T: ``sign_publication`` (snapshot verification and key
  loading), ``hubcore`` (envelope helpers), ``build_catalog`` (public trust)
  and the macOS original producer ``scripts/macos_original.py``. Nothing is
  imported, executed or installed from the data checkout S.
* S — a separate clean, exact Git snapshot of ``JiangNanGenius/floe-skill-hub``
  at the claimed 40-hex candidate commit carrying ``macos/catalog.json``.
  Snapshot verification is the reviewed ``sign_publication.verify_exact_snapshot``
  (disk bytes hashed against HEAD blobs, extra/ignored files refused, no
  replacement refs, index never written).
* B — a separate clean, exact snapshot of the CURRENT official default branch
  (``refs/heads/main``), with FULL history. Published macOS original feed
  history is read ONLY from B's committed ``macos/catalog.json`` +
  ``macos/catalog.json.sig`` pairs. Candidate branches are never history.

Modes (fixed argv; no arbitrary command input):

  plan    Validate the candidate declaration with the trusted producer and
          write the list of exact upstream files to fetch. No key.
  fetch   Fetch ONLY the plan's declared upstream repositories/commits with
          argv-only Git, verify each blob's actual SHA-256/byte count/Git mode,
          and stage the exact package bytes. No key.
  verify  Revalidate T/S/B, schema, manifest digest, floor and full signed
          macOS publication history, then verify the staged upstream bytes and
          write a public-safe verification receipt. No key.
  sign    Require the separate read-only job's tiny verification receipt,
          hash-bound to the job output and rederived against the actual T/S/B,
          floor, feed bytes and per-entry upstream identities; only after that
          proof passes does it read ``FLOE_SKILL_HUB_SIGNING_KEY``, sign the
          EXACT candidate feed bytes carried at S, and write
          ``macos/catalog.json`` + ``macos/catalog.json.sig`` plus an
          authenticated receipt.

The receipt binds T, S, B, the exact minimum App floor, the feed SHA-256/size
and every output hash. It is candidate-only: published/installable/qualified
claims stay false.

The minimum App floor is supplied by the release owner and is refused unless
it is a strict semantic version other than ``0.0.0`` and every entry declares
exactly that value. No capability is inferred from the candidate version,
the schema, the source commit or a test run.

History: every committed feed pair on B's official default-branch FIRST-PARENT
publication spine is signature-verified at its own commit. A signed feed
version that was later removed from the current feed still participates in the
``(id, version)`` identity comparison (repository, subdirectory, commit,
licensePath, digest and every file path/sourcePath/sha256/bytes/mode). A
changed commit needs a new version even when the four-field manifest digest is
unchanged. A shallow, missing, unsigned or unreadable history — or a published
feed removed from HEAD — is refused rather than downgraded to "first
publication". Candidate-branch intermediate commits are not publication
history; actual publication must atomically copy the signed pair onto
official main in a first-parent commit, never merge an unsigned intermediate
candidate history.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True  # keep T, S and B untouched by this run

OFFICIAL_HUB_OWNER_REPO = "JiangNanGenius/floe-skill-hub"
HUB_ORIGIN = "https://github.com/JiangNanGenius/floe-skill-hub.git"
SIGNING_ENV_NAME = "FLOE_SKILL_HUB_SIGNING_KEY"
CHANNEL = "macos-original"
FEED_REL = "macos/catalog.json"
SIG_REL = "macos/catalog.json.sig"
RECEIPT_REL = "macos/signing-receipt.json"
RECEIPT_SIG_REL = RECEIPT_REL + ".sig"
VERIFICATION_REL = "verification.json"
PLAN_REL = "plan.json"
MAX_FEED_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_PLAN_BYTES = 16 * 1024 * 1024
MAX_VERIFICATION_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 256
MAX_FILES = 2048
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")
VERSION_RE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
REPOSITORY_COMPONENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\Z")
NO_HOOKS_PATH = "/nonexistent-floe-macos-original-signer-hooks"
ENTRY_FIELDS = {"id", "name", "description", "category", "version",
                "minimumAppVersion", "repository", "subdirectory", "commit",
                "license", "licensePath", "digest", "files"}
FILE_FIELDS = {"path", "sourcePath", "sha256", "bytes", "mode"}
VERIFICATION_FIELDS = {
    "schemaVersion", "mode", "channel", "hubRepository", "sourceCommit",
    "sourceTree", "toolingCommit", "toolingTree", "baselineCommit",
    "baselineTree", "baselineFeedPresent", "minimumAppVersion", "feed",
    "history", "upstream", "observedManifestSha256", "upstreamVerification",
    "limitations",
}
VERIFICATION_UPSTREAM_FIELDS = {
    "id", "version", "repository", "commit", "fileCount", "totalBytes",
    "manifestSha256",
}


class SigningError(RuntimeError):
    """Fail-closed signer violation; never contains key material."""


def _die(message):
    print("macos-original-signer: refusing: " + message, file=sys.stderr)
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# path / Git helpers
# ---------------------------------------------------------------------------

def _is_under(child, parent):
    child_s = os.fspath(child)
    parent_s = os.fspath(parent)
    try:
        return os.path.commonpath([child_s, parent_s]) == parent_s
    except ValueError:
        return False


def _git_env():
    """No inherited Git redirects, config, hooks or replacement refs."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_ASKPASS": "/bin/false",
    })
    return env


def _run_git(where, arguments, purpose):
    """One argv-only read-only Git call; returns raw stdout bytes."""
    command = ["git", "-C", str(where),
               "-c", "core.hooksPath=" + NO_HOOKS_PATH,
               "-c", "core.fsmonitor=false"] + list(arguments)
    proc = subprocess.run(command, capture_output=True, env=_git_env())
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise SigningError(f"git {purpose} failed (exit {proc.returncode})"
                           + (": " + detail if detail else ""))
    return proc.stdout


def _git_text(where, arguments, purpose):
    return _run_git(where, arguments, purpose).decode("utf-8").strip()


def _safe_rel(value, field):
    if (not isinstance(value, str) or not value
            or len(value.encode("utf-8")) > 1024
            or value.startswith("/") or "\\" in value or "\0" in value
            or any(ord(ch) < 0x20 for ch in value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise SigningError(f"{field} is not a safe repository-relative path")
    return value


def _check_no_prefix_collision(paths, field):
    seen = set(paths)
    for path in paths:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            ancestor = "/".join(parts[:depth])
            if ancestor in seen:
                raise SigningError(f"{field}: file path {ancestor!r} is also a "
                                   "directory of another file")


def _check_regular(path, label):
    if path.is_symlink():
        raise SigningError(f"{label}: symlink is forbidden")
    if not path.is_file():
        raise SigningError(f"{label}: missing regular file")


def _write_file(target, data, mode, label):
    if target.is_symlink():
        raise SigningError(f"{label}: refusing to write through a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise SigningError(f"{label}: short write")
            offset += written
    finally:
        os.close(descriptor)
    os.chmod(str(target), mode)
    if target.read_bytes() != data:
        raise SigningError(f"{label}: read-back is not byte-identical")


def _fresh_dir(path, label, forbidden=()):
    path = pathlib.Path(path)
    if path.is_symlink():
        raise SigningError(f"{label} must not be a symlink")
    real = pathlib.Path(os.path.realpath(str(path)))
    for parent in forbidden:
        if real == parent or _is_under(real, parent):
            raise SigningError(f"{label} must live outside {parent}")
    if path.exists():
        if not real.is_dir():
            raise SigningError(f"{label} exists and is not a directory")
        if any(os.scandir(real)):
            raise SigningError(f"{label} must be fresh or empty")
    real.mkdir(parents=True, exist_ok=True)
    return real


# ---------------------------------------------------------------------------
# trusted-tooling imports (T only; no candidate code)
# ---------------------------------------------------------------------------

def _load_trusted_modules(tooling_root, data_root):
    scripts = pathlib.Path(os.path.realpath(str(pathlib.Path(tooling_root) / "scripts")))
    required = ("hubcore.py", "sign_publication.py", "build_catalog.py",
                "runtime_dependency.py", "dependency_declaration.py",
                "publication_immutability.py")
    for name in required:
        if not (scripts / name).is_file():
            raise SigningError(f"trusted tooling is incomplete: scripts/{name} is missing")
    if not (scripts / "macos_original.py").is_file():
        raise SigningError(
            "trusted tooling has no scripts/macos_original.py producer; the macOS "
            "original producer integration is still pending, so candidate signing "
            "cannot be performed")
    data_real = pathlib.Path(os.path.realpath(str(data_root)))
    sys.path = [str(scripts)] + [
        entry for entry in sys.path
        if entry and not _is_under(pathlib.Path(os.path.realpath(entry)), data_real)]
    for name in ("hubcore", "sign_publication", "build_catalog",
                 "runtime_dependency", "dependency_declaration",
                 "publication_immutability", "macos_original"):
        sys.modules.pop(name, None)
    import hubcore  # noqa: E402
    import sign_publication  # noqa: E402
    import build_catalog  # noqa: E402
    import runtime_dependency  # noqa: E402
    import dependency_declaration  # noqa: E402
    import publication_immutability  # noqa: E402
    import macos_original  # noqa: E402
    for module in (hubcore, sign_publication, build_catalog,
                   runtime_dependency, dependency_declaration,
                   publication_immutability, macos_original):
        module_file = pathlib.Path(module.__file__).resolve()
        if not _is_under(module_file, scripts):
            raise SigningError(f"imported module resolves outside trusted tooling: "
                               f"{module.__name__}")
    for name in ("canonical_manifest_digest", "validate_catalog"):
        if not callable(getattr(macos_original, name, None)):
            raise SigningError(f"trusted producer scripts/macos_original.py does not "
                               f"export {name}()")
    return {"hubcore": hubcore, "sign_publication": sign_publication,
            "build_catalog": build_catalog, "producer": macos_original}


def _load_trust(context, tooling_root):
    trust = context["sign_publication"].load_official_trust(
        context["build_catalog"], context["hubcore"], tooling_root)
    return trust


def _refuse_key_in_readonly_mode(mode):
    if os.environ.get(SIGNING_ENV_NAME):
        raise SigningError(f"{mode} mode must not run with {SIGNING_ENV_NAME} "
                           "present; the secret belongs only to the final signing step")


# ---------------------------------------------------------------------------
# candidate feed / history / floor
# ---------------------------------------------------------------------------

def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _reject_json_constant(value):
    raise ValueError(f"non-finite JSON constant {value!r} is forbidden")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r} is forbidden")
        result[key] = value
    return result


def _decode_json(data, label):
    """Strict UTF-8 JSON; duplicate keys and NaN/Infinity are refused."""
    try:
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        return json.loads(text, object_pairs_hook=_unique_object,
                          parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"{label}: {error}") from None


def _read_feed(root, label):
    path = pathlib.Path(root) / FEED_REL
    _check_regular(path, f"{label} {FEED_REL}")
    data = path.read_bytes()
    if len(data) > MAX_FEED_BYTES:
        raise SigningError(f"{label} {FEED_REL} exceeds {MAX_FEED_BYTES} bytes")
    try:
        document = _decode_json(data, "feed")
    except ValueError as error:
        raise SigningError(f"{label} {FEED_REL} is not valid JSON: {error}") from None
    if not isinstance(document, dict):
        raise SigningError(f"{label} {FEED_REL} must be a JSON object")
    return data, document


def _parse_historical_feed(commit, feed_bytes, sig_bytes, context, trust, field):
    hubcore = context["hubcore"]
    producer = context["producer"]
    if len(feed_bytes) > MAX_FEED_BYTES:
        raise SigningError(f"{field} at {commit}: feed exceeds {MAX_FEED_BYTES} bytes")
    try:
        key_id = hubcore.verify_envelope(feed_bytes, sig_bytes, trust)
    except hubcore.HubError as error:
        raise SigningError(f"{field} at {commit}: signature is not trustworthy: "
                           f"{error}") from None
    if key_id != hubcore.PRODUCTION_KEY_ID:
        raise SigningError(f"{field} at {commit}: signed by unexpected identity "
                           f"{key_id!r}")
    try:
        document = _decode_json(feed_bytes, "historical feed")
    except ValueError as error:
        raise SigningError(f"{field} at {commit}: not valid JSON: {error}") from None
    try:
        producer.validate_catalog(document, None, ())
    except Exception as error:  # trusted producer refusal; never a secret
        raise SigningError(f"{field} at {commit}: trusted producer refused the "
                           f"historical feed: {error}") from None
    return document


def _load_history(baseline_root, context, trust):
    """Every signed feed pair committed on official default-branch history.

    B must be a complete (non-shallow) official main snapshot. History is the
    FIRST-PARENT publication spine; candidate-branch intermediate commits
    merged in later are not published. Every first-parent commit that
    adds/changes either Mac file is read at that commit; both objects must
    exist and the pair must verify. An unsigned intermediate publication
    commit is a refusal, not a skipped row. Unique feed bytes are returned
    oldest first so versions later removed from the current feed remain in the
    identity check.
    """
    root = pathlib.Path(baseline_root)
    shallow = _git_text(root, ["rev-parse", "--is-shallow-repository"],
                        "baseline shallow check")
    if shallow not in ("false", "true"):
        raise SigningError("baseline history depth could not be established")
    if shallow == "true":
        raise SigningError("baseline checkout is shallow; full official "
                           "default-branch history is required to establish "
                           "macOS original publication history")
    commits = [line for line in _git_text(
        root, ["log", "--first-parent", "--reverse", "--format=%H", "--",
               FEED_REL, SIG_REL], "macOS feed history").splitlines() if line]
    history = []
    seen = set()
    for commit in commits:
        if not COMMIT_RE.fullmatch(commit):
            raise SigningError("baseline history yielded a non-commit object")
        try:
            feed_bytes = _run_git(root, ["show", f"{commit}:{FEED_REL}"],
                                  "historical feed blob")
            sig_bytes = _run_git(root, ["show", f"{commit}:{SIG_REL}"],
                                 "historical signature blob")
        except SigningError as error:
            raise SigningError(
                f"baseline history at {commit} does not carry both macOS feed "
                f"files ({error}); history cannot be established") from None
        document = _parse_historical_feed(commit, feed_bytes, sig_bytes,
                                          context, trust, "macOS feed history")
        digest = _sha256(feed_bytes)
        if digest not in seen:
            seen.add(digest)
            history.append({"commit": commit, "sha256": digest,
                            "bytes": feed_bytes, "document": document})
    head_feed = root / FEED_REL
    head_sig = root / SIG_REL
    if head_feed.exists() or head_sig.exists():
        if not head_feed.is_file() or not head_sig.is_file():
            raise SigningError("baseline HEAD has an incomplete macOS feed pair; "
                               "an absent signature never passes as unpublished")
        head_bytes, _document = _read_feed(root, "baseline HEAD")
        if _sha256(head_bytes) not in seen:
            raise SigningError("baseline HEAD macOS feed is not present in the "
                               "committed official history")
    else:
        head_bytes = None
        if history:
            raise SigningError("a previously published macOS original feed was "
                               "removed from official main HEAD; refusing a "
                               "first-publication downgrade")
    return history, head_bytes


def _entry_identity(entry):
    return {
        "repository": entry.get("repository"),
        "subdirectory": entry.get("subdirectory"),
        "commit": entry.get("commit"),
        "licensePath": entry.get("licensePath"),
        "digest": entry.get("digest"),
        "files": [{key: file.get(key) for key in
                   ("path", "sourcePath", "sha256", "bytes", "mode")}
                  for file in sorted(entry.get("files") or [],
                                     key=lambda row: str(row.get("path")))],
    }


def _identity_bytes(identity):
    return json.dumps(identity, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _check_history_identity(history, candidate):
    historical = {}
    for item in history:
        for entry in item["document"].get("entries") or []:
            key = (entry.get("id"), entry.get("version"))
            identity = _identity_bytes(_entry_identity(entry))
            if key in historical and historical[key] != identity:
                raise SigningError(
                    f"official macOS history is internally inconsistent for "
                    f"({key[0]!r}, {key[1]!r}); history cannot be established")
            historical[key] = identity
    for entry in candidate.get("entries") or []:
        key = (entry.get("id"), entry.get("version"))
        identity = _identity_bytes(_entry_identity(entry))
        if key in historical and historical[key] != identity:
            raise SigningError(
                f"published macOS entry ({key[0]!r}, {key[1]!r}) is immutable: "
                "its repository, commit, file identity, bytes or modes differ; "
                "publish a new version instead")


def _check_floor(document, floor):
    if not isinstance(floor, str) or not VERSION_RE.fullmatch(floor):
        raise SigningError("--minimum-app-version must be a strict semantic "
                           "version such as 1.2.3")
    if floor == "0.0.0":
        raise SigningError("--minimum-app-version must be the release owner's "
                           "verified capable App version, not an all-zero placeholder")
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise SigningError("candidate feed entries are missing")
    for entry in entries:
        if entry.get("minimumAppVersion") != floor:
            raise SigningError(
                f"{entry.get('id')!r}: minimumAppVersion "
                f"{entry.get('minimumAppVersion')!r} differs from the "
                f"release-owner floor {floor!r}; the exact confirmed floor is required")


def _validate_candidate(context, tooling_root, data_root, baseline_root, floor):
    hubcore = context["hubcore"]
    producer = context["producer"]
    trust = _load_trust(context, tooling_root)
    feed_bytes, document = _read_feed(data_root, "candidate")
    history, head_bytes = _load_history(baseline_root, context, trust)
    previous = tuple(item["document"] for item in history)
    try:
        count = producer.validate_catalog(document, None, previous)
    except Exception as error:
        raise SigningError(f"trusted macOS original producer refused the "
                           f"candidate: {error}") from None
    entries = document.get("entries")
    if not isinstance(count, int) or count != len(entries):
        raise SigningError("trusted producer entry count disagrees with the feed")
    _check_floor(document, floor)
    _check_history_identity(history, document)
    latest_sha = head_bytes is not None and _sha256(head_bytes) or None
    return {
        "feedBytes": feed_bytes, "document": document, "trust": trust,
        "history": history, "headBytes": head_bytes, "latestSha256": latest_sha,
    }


def _expected_upstream_entries(document):
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
            "manifestSha256": _sha256(json.dumps(
                sorted(manifest, key=lambda row: row["path"]),
                ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8")),
        })
    return entries


def _validate_verification_receipt(args, result, tooling_info, data_info,
                                   baseline_info):
    """The separate read-only job's tiny receipt, bound by its exact SHA-256.

    The receipt is NOT authority for candidate facts: every identity, the
    floor, the feed hash and every per-entry manifest are rederived from the
    actual T/S/B snapshots and the exact candidate feed bytes. The job-output
    digest is the workflow boundary; a missing, tampered, stale or mismatched
    receipt is refused before the signing key is read.
    """
    if not args.verification_receipt or not args.verification_sha256:
        raise SigningError("sign requires the separate verify job's receipt and "
                           "its exact SHA-256")
    path = pathlib.Path(args.verification_receipt)
    _check_regular(path, "verification receipt")
    raw = path.read_bytes()
    if len(raw) > MAX_VERIFICATION_BYTES:
        raise SigningError("verification receipt exceeds the size limit")
    digest = _sha256(raw)
    if digest != args.verification_sha256:
        raise SigningError("verification receipt SHA-256 does not equal the "
                           "separate verify job's output hash")
    try:
        document = _decode_json(raw, "verification receipt")
    except ValueError as error:
        raise SigningError(f"verification receipt is not valid JSON: {error}") from None
    if not isinstance(document, dict) or set(document) != VERIFICATION_FIELDS:
        raise SigningError("verification receipt fields are not exact")
    if type(document["schemaVersion"]) is not int \
            or document["schemaVersion"] != 1 \
            or document["mode"] != "macos-original-verify" \
            or document["channel"] != CHANNEL \
            or document["hubRepository"] != OFFICIAL_HUB_OWNER_REPO:
        raise SigningError("verification receipt schema/channel/repository mismatch")
    for name, expected in (("sourceCommit", data_info["head"]),
                           ("sourceTree", data_info["tree"]),
                           ("toolingCommit", tooling_info["head"]),
                           ("toolingTree", tooling_info["tree"]),
                           ("baselineCommit", baseline_info["head"]),
                           ("baselineTree", baseline_info["tree"])):
        if not isinstance(document[name], str) or document[name] != expected:
            raise SigningError(f"verification receipt {name} does not bind the "
                               "actual snapshot")
    if document["baselineFeedPresent"] is not (result["headBytes"] is not None):
        raise SigningError("verification receipt baseline feed presence differs "
                           "from the actual baseline")
    if document["minimumAppVersion"] != args.minimum_app_version:
        raise SigningError("verification receipt minimum App floor differs from "
                           "the requested exact floor")
    feed = document["feed"]
    if not isinstance(feed, dict) or set(feed) != {
            "path", "sha256", "size", "entryCount"}:
        raise SigningError("verification receipt feed fields are not exact")
    if feed["path"] != FEED_REL \
            or feed["sha256"] != _sha256(result["feedBytes"]) \
            or type(feed["size"]) is not int \
            or feed["size"] != len(result["feedBytes"]) \
            or type(feed["entryCount"]) is not int \
            or feed["entryCount"] != len(result["document"]["entries"]):
        raise SigningError("verification receipt feed does not bind the exact "
                           "candidate bytes")
    history = document["history"]
    if not isinstance(history, dict) or set(history) != {
            "signedFeedCount", "latestFeedSha256"}:
        raise SigningError("verification receipt history fields are not exact")
    if type(history["signedFeedCount"]) is not int or history["signedFeedCount"] < 0:
        raise SigningError("verification receipt signed feed count is invalid")
    if history["latestFeedSha256"] is not None and (
            not isinstance(history["latestFeedSha256"], str)
            or not HEX64_RE.fullmatch(history["latestFeedSha256"])):
        raise SigningError("verification receipt latest feed hash is invalid")
    expected = _expected_upstream_entries(result["document"])
    upstream = document["upstream"]
    if not isinstance(upstream, list) or len(upstream) != len(expected):
        raise SigningError("verification receipt does not cover every entry")
    for actual, wanted in zip(upstream, expected):
        if not isinstance(actual, dict) \
                or set(actual) != VERIFICATION_UPSTREAM_FIELDS \
                or type(actual["fileCount"]) is not int \
                or type(actual["totalBytes"]) is not int:
            raise SigningError("verification receipt upstream fields are not exact")
        if actual != wanted:
            raise SigningError(
                f"verification receipt upstream identity for {wanted['id']!r} "
                "differs from the exact candidate feed")
    observed_sha = document["observedManifestSha256"]
    if not isinstance(observed_sha, str) or not HEX64_RE.fullmatch(observed_sha):
        raise SigningError("verification receipt observed upstream hash is invalid")
    verified = document["upstreamVerification"]
    if not isinstance(verified, dict) or set(verified) != {
            "verified", "targetCount", "observedManifestSha256"}:
        raise SigningError("verification receipt upstream result fields are not exact")
    if verified["verified"] is not True \
            or type(verified["targetCount"]) is not int \
            or verified["targetCount"] != len(expected) \
            or verified["observedManifestSha256"] != observed_sha:
        raise SigningError("verification receipt does not prove a successful "
                           "upstream byte verification")
    limitations = document["limitations"]
    if not isinstance(limitations, list) \
            or not all(isinstance(item, str) for item in limitations):
        raise SigningError("verification receipt limitations are invalid")
    return {"sha256": digest, "document": document}


# ---------------------------------------------------------------------------
# upstream plan / fetch / staged verification
# ---------------------------------------------------------------------------

def _validate_plan(plan_bytes):
    try:
        plan = _decode_json(plan_bytes, "fetch plan")
    except ValueError as error:
        raise SigningError(f"fetch plan is not valid JSON: {error}") from None
    if not isinstance(plan, dict) or set(plan) != {"schemaVersion", "targets"}:
        raise SigningError("fetch plan root fields must be exactly schemaVersion/targets")
    if plan["schemaVersion"] != 1:
        raise SigningError("fetch plan schemaVersion must be 1")
    targets = plan["targets"]
    if not isinstance(targets, list) or not 1 <= len(targets) <= MAX_ENTRIES:
        raise SigningError("fetch plan targets are missing or out of range")
    seen_ids = set()
    for target in targets:
        if not isinstance(target, dict) or set(target) != {
                "id", "repository", "commit", "files"}:
            raise SigningError("fetch plan target fields are not exact")
        skill_id = target["id"]
        if not isinstance(skill_id, str) or not ID_RE.fullmatch(skill_id) \
                or skill_id in seen_ids:
            raise SigningError("fetch plan contains an invalid/duplicate id")
        seen_ids.add(skill_id)
        repository = target["repository"]
        parts = repository.split("/") if isinstance(repository, str) else []
        if len(parts) != 2 or not all(REPOSITORY_COMPONENT_RE.fullmatch(part)
                                     for part in parts):
            raise SigningError(f"{skill_id}: fetch plan repository is invalid")
        if not isinstance(target["commit"], str) \
                or not COMMIT_RE.fullmatch(target["commit"]):
            raise SigningError(f"{skill_id}: fetch plan commit must be 40 lowercase hex")
        files = target["files"]
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
            raise SigningError(f"{skill_id}: fetch plan files are out of range")
        paths, total = set(), 0
        for file in files:
            if not isinstance(file, dict) or set(file) != FILE_FIELDS:
                raise SigningError(f"{skill_id}: fetch plan file fields are not exact")
            path = _safe_rel(file["path"], f"{skill_id}: file path")
            _safe_rel(file["sourcePath"], f"{skill_id}: source path")
            if path in paths:
                raise SigningError(f"{skill_id}: duplicate package path {path!r}")
            paths.add(path)
            if not isinstance(file["sha256"], str) \
                    or not HEX64_RE.fullmatch(file["sha256"]):
                raise SigningError(f"{skill_id}: invalid file sha256")
            if type(file["bytes"]) is not int or not 0 <= file["bytes"] <= MAX_TOTAL_BYTES:
                raise SigningError(f"{skill_id}: invalid file byte count")
            if file["mode"] not in ("100644", "100755"):
                raise SigningError(f"{skill_id}: invalid file mode")
            total += file["bytes"]
        if total > MAX_TOTAL_BYTES:
            raise SigningError(f"{skill_id}: fetch plan total bytes exceed the limit")
        if "SKILL.md" not in paths:
            raise SigningError(f"{skill_id}: fetch plan has no SKILL.md")
        _check_no_prefix_collision(sorted(paths), f"{skill_id}: fetch plan")
    return plan


def _plan_from_candidate(document):
    targets = []
    for entry in document["entries"]:
        targets.append({
            "id": entry["id"],
            "repository": entry["repository"],
            "commit": entry["commit"],
            "files": [{key: file[key] for key in
                       ("path", "sourcePath", "sha256", "bytes", "mode")}
                      for file in entry["files"]],
        })
    return {"schemaVersion": 1, "targets": targets}


def _upstream_origin(repository):
    return f"https://github.com/{repository}.git"


def _git_tree(root, commit):
    listing = _run_git(root, ["ls-tree", "-r", "-z", commit], "upstream tree")
    table = {}
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3:
            raise SigningError("upstream tree contains an unparsable entry")
        mode, kind, oid = (field.decode("ascii") for field in fields)
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            raise SigningError("upstream tree contains a non-UTF-8 path") from None
        if path in table:
            raise SigningError(f"upstream tree repeats path {path!r}")
        table[path] = (mode, kind, oid)
    return table


def _fetch_target(target, stage_root, work_root, origin_override=None):
    skill_id = target["id"]
    repository = target["repository"]
    commit = target["commit"]
    target_dir = stage_root / skill_id
    target_dir.mkdir(parents=True, exist_ok=False)
    work = pathlib.Path(tempfile.mkdtemp(prefix="repo-", dir=str(work_root)))
    try:
        _run_git(work, ["init", "--quiet", "--bare"], "upstream init")
        _run_git(work, ["remote", "add", "origin",
                        origin_override or _upstream_origin(repository)],
                 "upstream remote")
        _run_git(work, ["-c", "gc.auto=0", "fetch", "--depth", "1",
                        "--no-tags", "origin", commit], "upstream fetch")
        resolved = _git_text(work, ["rev-parse", "FETCH_HEAD^{commit}"],
                             "upstream commit resolution")
        if resolved != commit:
            raise SigningError(f"{skill_id}: fetched commit {resolved} does not "
                               f"equal the declared {commit}")
        tree = _git_tree(work, resolved)
        observed = []
        for file in target["files"]:
            source = file["sourcePath"]
            if source not in tree:
                raise SigningError(f"{skill_id}: declared upstream file {source!r} "
                                   "is absent at the pinned commit")
            mode, kind, oid = tree[source]
            if kind != "blob":
                raise SigningError(f"{skill_id}: {source!r} is not a regular blob "
                                   f"({kind})")
            if mode not in ("100644", "100755"):
                raise SigningError(f"{skill_id}: {source!r} has unsupported Git "
                                   f"mode {mode}")
            if mode != file["mode"]:
                raise SigningError(f"{skill_id}: {source!r} Git mode {mode} differs "
                                   f"from the declared {file['mode']}")
            data = _run_git(work, ["cat-file", "blob", oid], "upstream blob")
            if len(data) != file["bytes"] or _sha256(data) != file["sha256"]:
                raise SigningError(f"{skill_id}: {source!r} bytes/sha256 differ "
                                   "from the declaration")
            destination = target_dir.joinpath(*pathlib.PurePosixPath(
                file["path"]).parts)
            _write_file(destination, data,
                        0o755 if mode == "100755" else 0o644,
                        f"{skill_id}: staged {file['path']}")
            observed.append({"path": file["path"],
                             "sourcePath": source,
                             "sha256": file["sha256"],
                             "bytes": file["bytes"],
                             "mode": mode})
        return {"id": skill_id, "repository": repository, "commit": commit,
                "files": observed}
    finally:
        _remove_tree(work)


def _remove_tree(path):
    import shutil
    shutil.rmtree(str(path), ignore_errors=True)


def _fetch_plan(plan, stage_root, observed_path, work_root,
                origin_override=None):
    stage_root = pathlib.Path(stage_root)
    observed_path = pathlib.Path(observed_path)
    if stage_root.exists() and any(os.scandir(stage_root)):
        raise SigningError("upstream staging directory must be fresh or empty")
    stage_root.mkdir(parents=True, exist_ok=True)
    if observed_path.exists() or observed_path.is_symlink():
        raise SigningError("observed manifest must be a fresh path")
    observed_path.parent.mkdir(parents=True, exist_ok=True)
    work_root = pathlib.Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    targets = []
    for target in plan["targets"]:
        targets.append(_fetch_target(target, stage_root, work_root,
                                     origin_override))
    payload = json.dumps({"schemaVersion": 1,
                          "planSha256": _sha256(json.dumps(
                              plan, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")),
                          "targets": targets},
                         ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    _write_file(observed_path, payload, 0o644, "observed upstream manifest")
    return payload


def _validate_observed(observed_bytes, document):
    try:
        observed = _decode_json(observed_bytes, "observed manifest")
    except ValueError as error:
        raise SigningError(f"observed manifest is not valid JSON: {error}") from None
    if not isinstance(observed, dict) or set(observed) != {
            "schemaVersion", "planSha256", "targets"}:
        raise SigningError("observed manifest root fields are not exact")
    if observed["schemaVersion"] != 1:
        raise SigningError("observed manifest schemaVersion must be 1")
    if not isinstance(observed["planSha256"], str) \
            or not HEX64_RE.fullmatch(observed["planSha256"]):
        raise SigningError("observed manifest planSha256 is invalid")
    targets = observed["targets"]
    if not isinstance(targets, list):
        raise SigningError("observed manifest targets are missing")
    observed_by_id = {}
    for target in targets:
        if not isinstance(target, dict) or set(target) != {
                "id", "repository", "commit", "files"}:
            raise SigningError("observed target fields are not exact")
        if not isinstance(target["id"], str) or not ID_RE.fullmatch(target["id"]):
            raise SigningError("observed manifest has an invalid id")
        if not isinstance(target["repository"], str) \
                or not isinstance(target["commit"], str) \
                or not COMMIT_RE.fullmatch(target["commit"]) \
                or not isinstance(target["files"], list):
            raise SigningError("observed manifest has an invalid target identity")
        if target["id"] in observed_by_id:
            raise SigningError("observed manifest repeats an id")
        observed_by_id[target["id"]] = target
    entries = document["entries"]
    if len(observed_by_id) != len(entries) \
            or set(observed_by_id) != {entry["id"] for entry in entries}:
        raise SigningError("observed manifest ids do not equal the candidate ids")
    for entry in entries:
        target = observed_by_id[entry["id"]]
        if target["repository"] != entry["repository"] \
                or target["commit"] != entry["commit"]:
            raise SigningError(f"{entry['id']}: observed repository/commit drift")
        files = target["files"]
        if not isinstance(files, list) or len(files) != len(entry["files"]):
            raise SigningError(f"{entry['id']}: observed file count differs")
        observed_files = {}
        for file in files:
            if not isinstance(file, dict) or set(file) != FILE_FIELDS:
                raise SigningError(f"{entry['id']}: observed file fields are not exact")
            path = _safe_rel(file["path"], f"{entry['id']}: observed path")
            if path in observed_files:
                raise SigningError(f"{entry['id']}: observed manifest repeats a path")
            observed_files[path] = file
        expected_files = {file["path"]: file for file in entry["files"]}
        if set(observed_files) != set(expected_files):
            raise SigningError(f"{entry['id']}: observed paths differ from the feed")
        for path, expected in expected_files.items():
            actual = observed_files[path]
            if any(actual[key] != expected[key] for key in FILE_FIELDS):
                raise SigningError(f"{entry['id']}: observed {path!r} differs "
                                   "from the declared feed identity")
    return observed


def _verify_stage(stage_root, document):
    root = pathlib.Path(stage_root)
    if root.is_symlink() or not root.is_dir():
        raise SigningError("upstream staging root must be a real directory")
    declared_ids = {entry["id"] for entry in document["entries"]}
    disk_ids = {item.name for item in root.iterdir()}
    if disk_ids != declared_ids:
        raise SigningError("upstream staging root ids do not equal the candidate ids")
    for entry in document["entries"]:
        skill_id = entry["id"]
        target_dir = root / skill_id
        if target_dir.is_symlink() or not target_dir.is_dir():
            raise SigningError(f"{skill_id}: staging directory is missing")
        expected = {file["path"]: file for file in entry["files"]}
        _check_no_prefix_collision(sorted(expected), f"{skill_id}: staged")
        disk_files = set()
        disk_dirs = set()
        for dirpath, dirnames, filenames in os.walk(str(target_dir)):
            rel_dir = pathlib.Path(dirpath).relative_to(target_dir).as_posix()
            if rel_dir == ".":
                rel_dir = ""
            for name in dirnames:
                full = pathlib.Path(dirpath) / name
                if full.is_symlink():
                    raise SigningError(f"{skill_id}: symlink directory in staging")
                disk_dirs.add((rel_dir + "/" + name).lstrip("/"))
            for name in filenames:
                full = pathlib.Path(dirpath) / name
                rel = (rel_dir + "/" + name).lstrip("/")
                if full.is_symlink():
                    raise SigningError(f"{skill_id}: symlink file in staging: {rel}")
                disk_files.add(rel)
        expected_dirs = set()
        for path in expected:
            parts = path.split("/")
            for depth in range(1, len(parts)):
                expected_dirs.add("/".join(parts[:depth]))
        if disk_files != set(expected) or disk_dirs != expected_dirs:
            raise SigningError(f"{skill_id}: staged file set differs from the feed")
        for path, file in expected.items():
            target = target_dir.joinpath(*pathlib.PurePosixPath(path).parts)
            _check_regular(target, f"{skill_id}: staged {path}")
            data = target.read_bytes()
            if len(data) != file["bytes"] or _sha256(data) != file["sha256"]:
                raise SigningError(f"{skill_id}: staged {path!r} bytes differ "
                                   "from the feed")
            executable = bool(target.stat().st_mode & 0o111)
            if executable != (file["mode"] == "100755"):
                raise SigningError(f"{skill_id}: staged {path!r} executable mode "
                                   "differs from the feed")


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------

def run_plan(args, context, tooling_info, data_info, out_root):
    _refuse_key_in_readonly_mode("plan")
    feed_bytes, document = _read_feed(args.data, "candidate")
    try:
        context["producer"].validate_catalog(document, None, ())
    except Exception as error:
        raise SigningError(f"trusted macOS original producer refused the "
                           f"candidate: {error}") from None
    plan = _plan_from_candidate(document)
    payload = json.dumps(plan, ensure_ascii=False, sort_keys=True,
                         indent=2).encode("utf-8") + b"\n"
    context["sign_publication"].write_outputs(
        out_root, {PLAN_REL: payload})
    print(f"macos-original-signer plan: {len(plan['targets'])} upstream "
          f"target(s) from candidate {data_info['head']} at tooling "
          f"{tooling_info['head']}; wrote {PLAN_REL}")


def run_fetch(args):
    _refuse_key_in_readonly_mode("fetch")
    plan_path = pathlib.Path(args.plan)
    _check_regular(plan_path, "fetch plan")
    raw = plan_path.read_bytes()
    if len(raw) > MAX_PLAN_BYTES:
        raise SigningError("fetch plan exceeds the size limit")
    plan = _validate_plan(raw)
    stage_root = _fresh_dir(args.stage, "upstream staging")
    observed = pathlib.Path(args.observed)
    work = pathlib.Path(tempfile.mkdtemp(prefix="macos-fetch-work-"))
    try:
        _fetch_plan(plan, stage_root, observed, work)
    finally:
        _remove_tree(work)
    print(f"macos-original-signer fetch: verified and staged "
          f"{len(plan['targets'])} pinned upstream package(s)")


def run_verify(args, context, tooling_info, data_info, baseline_info, out_root):
    _refuse_key_in_readonly_mode("verify")
    result = _validate_candidate(context, args.tooling, args.data,
                                 args.baseline, args.minimum_app_version)
    observed_path = pathlib.Path(args.observed)
    _check_regular(observed_path, "observed upstream manifest")
    observed_bytes = observed_path.read_bytes()
    _validate_observed(observed_bytes, result["document"])
    _verify_stage(args.stage, result["document"])
    entries = _expected_upstream_entries(result["document"])
    verification = {
        "schemaVersion": 1,
        "mode": "macos-original-verify",
        "channel": CHANNEL,
        "hubRepository": OFFICIAL_HUB_OWNER_REPO,
        "sourceCommit": data_info["head"],
        "sourceTree": data_info["tree"],
        "toolingCommit": tooling_info["head"],
        "toolingTree": tooling_info["tree"],
        "baselineCommit": baseline_info["head"],
        "baselineTree": baseline_info["tree"],
        "baselineFeedPresent": result["headBytes"] is not None,
        "minimumAppVersion": args.minimum_app_version,
        "feed": {"path": FEED_REL,
                 "sha256": _sha256(result["feedBytes"]),
                 "size": len(result["feedBytes"]),
                 "entryCount": len(result["document"]["entries"])},
        "history": {"signedFeedCount": len(result["history"]),
                    "latestFeedSha256": result["latestSha256"]},
        "upstream": entries,
        "observedManifestSha256": _sha256(observed_bytes),
        "upstreamVerification": {
            "verified": True,
            "targetCount": len(entries),
            "observedManifestSha256": _sha256(observed_bytes),
        },
        "limitations": ["candidate-only", "not published", "not installable",
                        "no macOS execution", "no Linux qualification",
                        "no package archive"],
    }
    payload = json.dumps(verification, ensure_ascii=False, sort_keys=True,
                         indent=2).encode("utf-8") + b"\n"
    context["sign_publication"].write_outputs(
        out_root, {VERIFICATION_REL: payload})
    print(f"macos-original-signer verify: validated {len(entries)} entry/entries "
          f"and {len(result['history'])} historical signed feed(s); wrote "
          f"{VERIFICATION_REL}")


def _finalize_receipt(hubcore, files, receipt, key, trust):
    receipt_bytes = hubcore.encoded(receipt)
    try:
        envelope = hubcore.sign_envelope(receipt_bytes, key,
                                         hubcore.PRODUCTION_KEY_ID)
    except hubcore.HubError as error:
        raise SigningError(f"receipt signing failed: {error}") from None
    try:
        verified = hubcore.verify_envelope(receipt_bytes, envelope, trust)
    except hubcore.HubError as error:
        raise SigningError("produced receipt signature does not verify") from None
    if verified != hubcore.PRODUCTION_KEY_ID:
        raise SigningError("receipt signature identity drifted")
    files[RECEIPT_REL] = receipt_bytes
    files[RECEIPT_SIG_REL] = envelope


def run_sign(args, context, tooling_info, data_info, baseline_info, out_root):
    hubcore = context["hubcore"]
    sign_publication = context["sign_publication"]
    result = _validate_candidate(context, args.tooling, args.data,
                                 args.baseline, args.minimum_app_version)
    # Proof FIRST: the signing key is not read until the separate read-only
    # job's tiny receipt is present, hash-bound and rederived against T/S/B.
    proof = _validate_verification_receipt(
        args, result, tooling_info, data_info, baseline_info)
    key = sign_publication.load_signing_key(hubcore, result["trust"])
    feed_bytes = result["feedBytes"]
    feed_sha = _sha256(feed_bytes)
    try:
        envelope = hubcore.sign_envelope(feed_bytes, key,
                                         hubcore.PRODUCTION_KEY_ID)
    except hubcore.HubError as error:
        raise SigningError(f"feed signing failed: {error}") from None
    try:
        verified = hubcore.verify_envelope(feed_bytes, envelope, result["trust"])
    except hubcore.HubError as error:
        raise SigningError("produced feed signature does not verify") from None
    if verified != hubcore.PRODUCTION_KEY_ID:
        raise SigningError("feed signature identity drifted")
    files = {FEED_REL: feed_bytes, SIG_REL: envelope}
    receipt = {
        "schemaVersion": 1,
        "mode": "macos-original-candidate",
        "channel": CHANNEL,
        "hubRepository": OFFICIAL_HUB_OWNER_REPO,
        "sourceCommit": data_info["head"],
        "sourceTree": data_info["tree"],
        "toolingCommit": tooling_info["head"],
        "toolingTree": tooling_info["tree"],
        "baselineCommit": baseline_info["head"],
        "baselineTree": baseline_info["tree"],
        "baselineFeedPresent": result["headBytes"] is not None,
        "minimumAppVersion": args.minimum_app_version,
        "keyID": hubcore.PRODUCTION_KEY_ID,
        "feed": {"path": FEED_REL, "sha256": feed_sha,
                 "size": len(feed_bytes),
                 "entryCount": len(result["document"]["entries"])},
        "history": {"signedFeedCount": len(result["history"]),
                    "latestFeedSha256": result["latestSha256"]},
        "upstreamVerification": {
            "mode": "separate-readonly-job",
            "receiptSha256": proof["sha256"],
            "verifiedEntryCount": len(proof["document"]["upstream"]),
            "observedManifestSha256":
                proof["document"]["observedManifestSha256"],
        },
        "outputs": [{"path": path,
                     "sha256": _sha256(files[path]),
                     "size": len(files[path])}
                    for path in sorted(files)],
        "claims": {"candidateOnly": True, "published": False,
                   "installable": False, "macExecutionVerified": False,
                   "linuxQualified": False, "archiveProduced": False},
    }
    _finalize_receipt(hubcore, files, receipt, key, result["trust"])
    # Re-prove the exact snapshots were not mutated by this signing run before
    # any output is committed to disk.
    for label, root, info in (("tooling", args.tooling, tooling_info),
                              ("data", args.data, data_info),
                              ("baseline", args.baseline, baseline_info)):
        after = sign_publication.verify_exact_snapshot(label, root)
        if after != info:
            raise SigningError(f"{label} snapshot changed during signing")
    written = sign_publication.write_outputs(out_root, files)
    print(f"macos-original-signer sign: signed candidate feed {feed_sha} at "
          f"source {data_info['head']} with floor {args.minimum_app_version}; "
          f"{len(result['history'])} historical feed(s); wrote {len(written)} "
          f"file(s) to {out_root}")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("plan", "fetch", "verify", "sign"))
    parser.add_argument("--tooling", default=None,
                        help="trusted tooling checkout T (defaults to this script's repo)")
    parser.add_argument("--data", default=None,
                        help="clean exact official Hub candidate snapshot S")
    parser.add_argument("--source-commit", dest="source_commit", default=None,
                        help="claimed 40-hex candidate commit S")
    parser.add_argument("--baseline", default=None,
                        help="clean exact official default-branch snapshot B with full history")
    parser.add_argument("--baseline-commit", dest="baseline_commit", default=None,
                        help="claimed 40-hex official default-branch commit B")
    parser.add_argument("--minimum-app-version", dest="minimum_app_version",
                        default=None,
                        help="release-owner-confirmed exact App version floor")
    parser.add_argument("--out", default=None,
                        help="fresh output directory outside T, S and B")
    parser.add_argument("--plan", default=None, help="fetch plan path")
    parser.add_argument("--stage", default=None, help="upstream staging directory")
    parser.add_argument("--observed", default=None,
                        help="observed upstream manifest path")
    parser.add_argument("--verification-sha256", dest="verification_sha256",
                        default=None,
                        help="exact SHA-256 of the separate verify job's receipt")
    parser.add_argument("--verification-receipt", dest="verification_receipt",
                        default=None,
                        help="downloaded tiny verification.json from the verify job")
    args = parser.parse_args()

    if args.mode in ("plan", "verify", "sign"):
        if not args.tooling or not args.data or not args.source_commit:
            _die("--tooling, --data and --source-commit are required")
        if not COMMIT_RE.fullmatch(args.source_commit):
            _die("--source-commit must be exactly 40 lowercase hex")
        if not pathlib.Path(args.tooling).is_dir() or pathlib.Path(args.tooling).is_symlink():
            _die("--tooling is not a real directory")
        data_real = pathlib.Path(os.path.realpath(args.data))
        if data_real == pathlib.Path(os.path.realpath(args.tooling)):
            _die("--data and --tooling must be separate checkouts")
        if not args.out:
            _die("--out is required")
    if args.mode in ("verify", "sign"):
        if not args.baseline or not args.baseline_commit:
            _die("--baseline and --baseline-commit are required")
        if not COMMIT_RE.fullmatch(args.baseline_commit):
            _die("--baseline-commit must be exactly 40 lowercase hex")
        if not args.minimum_app_version:
            _die("--minimum-app-version is required")
        if not VERSION_RE.fullmatch(args.minimum_app_version):
            _die("--minimum-app-version must be a strict semantic version")
        if args.minimum_app_version == "0.0.0":
            _die("--minimum-app-version must not be an all-zero placeholder")
    if args.mode == "sign":
        if not args.verification_receipt or not args.verification_sha256:
            _die("sign requires --verification-receipt and "
                 "--verification-sha256 from the separate verify job; an "
                 "unproven signing request is refused")
        if not HEX64_RE.fullmatch(args.verification_sha256):
            _die("--verification-sha256 must be exactly 64 lowercase hex")
    if args.mode == "verify" and (not args.stage or not args.observed):
        _die("verify requires --stage and --observed from the separate fetch step")
    if args.mode == "fetch":
        if not args.plan or not args.stage or not args.observed:
            _die("--plan, --stage and --observed are required")

    context = None
    tooling_info = data_info = baseline_info = None
    if args.mode in ("plan", "verify", "sign"):
        tooling_root = pathlib.Path(args.tooling) if args.tooling else \
            pathlib.Path(__file__).resolve().parents[1]
        if not tooling_root.is_dir() or tooling_root.is_symlink():
            _die("--tooling is not a real directory")
        args.tooling = str(tooling_root)
        context = _load_trusted_modules(args.tooling, args.data)
        sign_publication = context["sign_publication"]
        data_real = pathlib.Path(os.path.realpath(args.data))
        if _is_under(pathlib.Path(os.path.realpath(os.getcwd())), data_real):
            _die("the signer must not run with the current directory inside the "
                 "data checkout")
        out_root = sign_publication.validate_out_root(
            args.out, args.data, args.tooling)
        tooling_info = sign_publication.verify_exact_snapshot(
            "tooling", args.tooling)
        data_info = sign_publication.verify_exact_snapshot(
            "data", args.data, args.source_commit)
        if args.mode in ("verify", "sign"):
            baseline_real = pathlib.Path(os.path.realpath(args.baseline))
            for label, root in (("tooling", pathlib.Path(args.tooling)),
                                ("data", pathlib.Path(args.data))):
                if baseline_real == pathlib.Path(os.path.realpath(root)) \
                        or _is_under(baseline_real, pathlib.Path(os.path.realpath(root))):
                    _die(f"--baseline must be separate from {label}")
            if out_root == baseline_real or _is_under(out_root, baseline_real):
                _die("--out must live outside the baseline snapshot")
            if args.mode == "verify":
                for label, value in (("--stage", args.stage),
                                     ("--observed", args.observed)):
                    real = pathlib.Path(os.path.realpath(value))
                    if real == out_root or _is_under(real, out_root):
                        _die(f"{label} must live outside --out")
                    for root_label, root in (("tooling", pathlib.Path(args.tooling)),
                                             ("data", pathlib.Path(args.data)),
                                             ("baseline", pathlib.Path(args.baseline))):
                        root_real = pathlib.Path(os.path.realpath(root))
                        if real == root_real or _is_under(real, root_real):
                            _die(f"{label} must live outside {root_label}")
            if args.mode == "sign":
                receipt_real = pathlib.Path(os.path.realpath(
                    args.verification_receipt))
                for label, root in (("tooling", pathlib.Path(args.tooling)),
                                    ("data", pathlib.Path(args.data)),
                                    ("baseline", pathlib.Path(args.baseline))):
                    root_real = pathlib.Path(os.path.realpath(root))
                    if receipt_real == root_real \
                            or _is_under(receipt_real, root_real):
                        _die(f"--verification-receipt must live outside {label}")
                if receipt_real == out_root or _is_under(receipt_real, out_root):
                    _die("--verification-receipt must live outside --out")
            baseline_info = sign_publication.verify_exact_snapshot(
                "baseline", args.baseline, args.baseline_commit)
        if args.mode == "plan":
            run_plan(args, context, tooling_info, data_info, out_root)
        elif args.mode == "verify":
            run_verify(args, context, tooling_info, data_info, baseline_info,
                       out_root)
        else:
            run_sign(args, context, tooling_info, data_info, baseline_info,
                     out_root)
    else:
        run_fetch(args)


if __name__ == "__main__":
    try:
        main()
    except SigningError as error:
        _die(str(error))
    except Exception as error:
        # sign_publication.SigningError is the reviewed bridge's own class;
        # convert it to the fixed fail-closed exit path without a traceback.
        module = sys.modules.get("sign_publication")
        bridge_error = getattr(module, "SigningError", None) if module else None
        if bridge_error is not None and isinstance(error, bridge_error):
            _die(str(error))
        raise
