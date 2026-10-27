#!/usr/bin/env python3
"""DATA-ONLY publication signing bridge (fixed trusted tooling T).

This tool is executed from ONE pinned, reviewed trusted tooling checkout T
(``--tooling``, by default the checkout that contains this very script) and
operates on a SEPARATE clean immutable data checkout S/X (``--data``) that
must be an exact Git snapshot of the official Hub repository
``JiangNanGenius/floe-skill-hub`` at the claimed 40-hex commit. It never
executes, imports, installs or hooks anything from the data checkout: all
code comes from T (``hubcore``/``build_catalog``/``runtime_dependency``/
``dependency_declaration``/``publication_immutability``),
and every Git invocation uses argument lists only (no shell), with system
and global Git config removed, an empty hooks path, optional locks off,
inherited Git environment redirects stripped and replacement refs disabled
(GIT_NO_REPLACE_OBJECTS=1), so a local refs/replace tree can never make the
claimed commit resolve to replacement content. Snapshot verification does
NOT trust ``git status``: every tracked regular file is hashed from disk
against its HEAD blob object id, any on-disk entry outside HEAD (including
ignored or assume-unchanged/skip-worktree shadows) is rejected, and the
index is never written or refreshed.

Modes (fixed; there is no arbitrary script/command input):
  reviews  S = clean snapshot carrying UNSIGNED canonical approved review
           records at ``reviews/<id>/<version>.review.json``. For every
           actual record the bridge hashes the real frozen package archives
           at S, recomputes their ZIP SHA-256, manifest and contentDigest
           through the unchanged package gates, and validates/joins the
           record with the existing hubcore contracts. Bad identity, hash
           drift, permission drift, non-canonical bytes, unsupported key
           material, unknown review stage or a status/promotion mismatch is
           rejected
           fail-closed. A static-content-reviewed record stays static: this
           mode never promotes anything and never rewrites registry status
           (the data checkout is read-only to this tool). Output: the exact
           canonical review bytes plus a matching Ed25519 signature envelope
           per record and one public-safe canonical receipt binding the
           source commit S, tooling commit T, the ROOT key ID, and the
           SHA-256 of every review record, package and signature, with the
           exact input archive paths. The receipt itself is authenticated:
           ``signing-receipt.json.sig`` carries the same official envelope
           over the canonical receipt bytes (the receipt lists every output
           hash excluding itself and its own sidecar, so nothing is circular).

  catalog  X = clean snapshot carrying ALREADY-SIGNED reviews
           (``.review.json`` + ``.sig`` pairs) and a qualified registry.
            The bridge invokes the existing trusted-T
            ``build_catalog.build`` release API as a data operation (both
            channels, package/review joins and the H6 runtime artifact
            staging included) and then enforces the agreed launch gate BEFORE
            signing. The Root-approved staged opening (2026-10-27) changed
            ONLY the old batch-completeness rule (>=40 unique qualified iOS
            offers plus all nine mandatory deep IDs present). The
            2026-10-28 platform-admission amendment replaced the remaining
            universal both-feeds forcing for actually-offered mandatory IDs
            with the qualified registry row's explicit
            plannedRuntime.installPlatforms as the authoritative channel set:
            a both-channel plan still requires both feeds, an explicitly
            single-platform plan is admitted on its declared channel alone,
            and no channel may be invented for a mandatory slot. Every real
            remote-script, frozen-plan, bound-review, manifest and (for
            impeccable) full H6 check still runs on EACH offered channel;
            Android native capability is never fabricated to satisfy an old
            both-feeds rule. Per-item trust is unchanged and still fully
            enforced:
              * a nonempty genuinely qualified set in BOTH feeds: each feed
                must be EXACTLY the qualified, download-eligible registry rows
                advertising that channel (no invented rows, no partial drop,
                no duplicates; the four App-provided builtin ids are never
                Hub download offers and are excluded by exact ID, and the
                builtins are iOS-only by contract); an empty feed is
                always refused;
              * every offered scripted manifest requires
                status.executionVerified true, adaptation frozen, its actual
                bound review guest-execution-qualified with execution
                linux/riscv64/guest-verified; guide-only packages keep
                static-content-reviewed and no invented guest claim;
              * the nine pinned mandatory deep-adaptation IDs (constants in
                this trusted tooling; registry deepAdaptation relabeling can
                never satisfy the gate) keep their full per-offered contract:
                whenever such an ID is offered it is present and qualified on
                EXACTLY its qualified plannedRuntime.installPlatforms (Root
                platform-admission policy 2026-10-28): a both-channel plan
                must still appear in BOTH feeds, an explicitly iOS-only (or
                Android-only) qualified plan is admitted on its declared
                channel only and no channel may be invented for it; in every
                offered channel it ships with actual manifest scriptRuntime
                remote, frozen adaptation, status.executionVerified true and
                a guest-execution-qualified review bound to
                linux/riscv64/guest-verified execution — a guide-only
                replacement of a mandatory slot is refused;
                impeccable must additionally retain its real embedded
                ``references/engine-dependency.json`` with the builder-
                validated frozen descriptor and raw engine bytes staged in
                the output (omitting the descriptor cannot bypass H6);
               * a held-back (not yet admitted) mandatory ID no longer blocks
                 unrelated qualified offers. The retired batch rule survives
                 ONLY as informational complete-selection coverage metadata
                 in the gate summary; it can never claim completeness for a
                 partial feed. There is no option that disables any gate.
            BEFORE any signing, the bridge additionally enforces
            publication-history immutability through the trusted-T
            ``publication_immutability`` module: the cumulative publication
            ledger at T (exactly ``catalog/publication-ledger.json``) plus
            the current publication independently resolved by the workflow
            and supplied through mandatory ``--published-y`` form the
            verified baseline, with every
            ledger row re-verified against the signed feed bytes at its
            pinned publication commit. The baseline is read ONLY from T,
            never from the data checkout X (whose registry, ledger and reviews
            are caller-replaceable), and a candidate feed reusing an already
            published ``(channel, id, version)`` with a different
            ``contentDigest`` is refused even though this bridge could sign
            the new bytes. Production history without a ledger, a ledger row
            that fails verification, or a stale ledger that does not cover
            the currently published offers fail closed; there is no
            first-publication downgrade once history exists.
           The two canonical channel feeds are then signed with the
           production identity and written together with EXACTLY the
           feed-referenced package archives and signed review records
           (re-verified against the feeds' own digests), the staged runtime
           artifacts (if any), and the authenticated canonical SHA receipt
           binding T/X, so the output is standalone.

Signing key: read ONLY from the fixed environment variable
``FLOE_SKILL_HUB_SIGNING_KEY`` (strict base64 of the raw 32-byte Ed25519
seed, identical to the legacy official skill-hub build.py representation).
The derived public identity must equal the configured official trust root
in ``public-key.json`` inside T (keyID ``official-2026-09``). No key value
ever appears in an error, a log line or a receipt — only the key ID.

The bridge writes ONLY new files under a fresh ``--out`` directory outside
both T and the data checkout (O_EXCL, no foreign overwrite, symlink and
traversal safe). It never mutates or promotes the data checkout, never
touches the legacy Hub and never pushes anything anywhere.
"""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True  # keep T and S verifiably untouched by this run

OFFICIAL_HUB_OWNER_REPO = "JiangNanGenius/floe-skill-hub"
SIGNING_ENV_NAME = "FLOE_SKILL_HUB_SIGNING_KEY"
RECEIPT_REL = "signing-receipt.json"
RECEIPT_SIG_REL = RECEIPT_REL + ".sig"
# Root-approved staged opening (2026-10-27): the old product launch BATCH rule
# (at least 40 unique qualified iOS offers plus all nine mandatory deep IDs
# present in both feeds) is superseded by the incremental policy enforced in
# enforce_launch_gate. The number 40 and the nine-ID complete set stay here
# ONLY as informational complete-selection coverage metadata; they can never
# gate a publication on and can never claim completeness for a partial feed.
# Per-item trust (exact advertised qualified set, signatures, guest-execution
# evidence, H6, presence of an offered mandatory ID on exactly its qualified
# plannedRuntime.installPlatforms channels with every hard check running on
# EACH offered channel) is unchanged. The 2026-10-28 amendment removed only
# the redundant UNIVERSAL both-feeds forcing that blocked an explicitly
# iOS-only (or Android-only) qualified admission; a both-channel plan still
# requires both feeds and no channel may ever be invented.
COMPLETE_SELECTION_QUALIFIED_TARGET = 40
IMPECCABLE_ID = "impeccable"
# The nine mandatory deep adaptations are pinned HERE, in trusted tooling.
# A candidate registry flipping deepAdaptation labels can never satisfy the
# launch gate; the IDs themselves are the contract. They are ALL real
# remote-script adaptations in the frozen contract, so the catalog gate also
# refuses any attempt to satisfy a mandatory ID with a guide-only relabel.
MANDATORY_DEEP_IDS = frozenset({
    "algorithmic-art", "canvas-design", "exploratory-data-analysis",
    "impeccable", "literature-review", "markitdown",
    "scientific-visualization", "statistical-analysis", "webapp-testing",
})
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
REVIEW_REL_RE = re.compile(
    r"^([a-z][a-z0-9]*(?:-[a-z0-9]+)*)/((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))\.review\.json$")
NO_HOOKS_PATH = "/nonexistent-floe-signing-bridge-hooks"


class SigningError(RuntimeError):
    """Fail-closed bridge violation; never contains key material."""


def _die(message):
    print("signing-bridge: refusing: " + message, file=sys.stderr)
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# fixed official-origin Git reader (no shell, no hooks, no external config)
# ---------------------------------------------------------------------------

def _git(where, args, purpose):
    """One controlled argv-only Git invocation against a verified snapshot.

    No shell, no hook path, no fsmonitor, no system/global config, no
    replacement refs (a local refs/replace tree can never make the claimed
    HEAD resolve to replacement content), and no inherited Git environment
    redirect (GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE/GIT_OBJECT_DIRECTORY/
    GIT_ALTERNATE_OBJECT_DIRECTORIES/GIT_CONFIG*/GIT_ATTR_* are removed so a
    hostile or accidental parent environment cannot retarget object
    resolution or index state). Read-only commands only; the index is never
    written or refreshed.
    """
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                "GIT_CONFIG", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                "GIT_CONFIG_COUNT", "GIT_NAMESPACE", "GIT_ATTR_NOSYSTEM",
                "GIT_SSH", "GIT_SSH_COMMAND", "GIT_PROXY_COMMAND",
                "GIT_EDITOR", "GIT_SEQUENCE_EDITOR"):
        env.pop(key, None)
    for key in [k for k in env if k.startswith("GIT_CONFIG_KEY_")
                or k.startswith("GIT_CONFIG_VALUE_")]:
        env.pop(key, None)
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    })
    command = ["git", "-C", str(where),
               "-c", "core.hooksPath=" + NO_HOOKS_PATH,
               "-c", "core.fsmonitor=false"] + list(args)
    proc = subprocess.run(command, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise SigningError(f"trusted git {purpose} failed (exit {proc.returncode}); "
                           "the repository state cannot be verified")
    return proc.stdout.strip()


def _origin_owner_repo(url):
    candidate = url.strip()
    if candidate.endswith("/"):
        candidate = candidate[:-1]
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    match = re.fullmatch(
        r"(?:https?://|ssh://|git://)(?:[^/@]+@)?github\.com/([^/]+/[^/]+)", candidate)
    if not match:
        match = re.fullmatch(r"git@github\.com:([^/]+/[^/]+)", candidate)
    return match.group(1) if match else None


def _blob_sha1(data):
    """Git's own blob hash: proves disk bytes equal the HEAD blob exactly."""
    digest = hashlib.sha1()
    digest.update(b"blob " + str(len(data)).encode("ascii") + b"\x00")
    digest.update(data)
    return digest.hexdigest()


def verify_exact_snapshot(label, root, claimed_commit=None):
    """Return {head, tree} after proving the on-disk tree IS the claimed commit.

    Enforces: a real directory (not a symlink) with a real .git dir; origin
    resolves to exactly the official Hub repository; HEAD equals the claimed
    40-hex commit; and the ACTUAL regular-file tree matches the HEAD blob
    object ids byte for byte. This replaces trusting `git status`: ignored or
    untracked shadows, assume-unchanged and skip-worktree index tricks cannot
    hide here because every tracked file is hashed from disk and every disk
    entry outside HEAD (and outside the top .git) is rejected. Tracked
    symlinks/gitlinks, disk symlinks, special files and extra directories are
    all refused. The repository index is never written or refreshed.
    """
    path = pathlib.Path(root)
    if path.is_symlink() or not path.is_dir():
        raise SigningError(f"{label}: must be a real directory, not a symlink: {path}")
    git_dir = path / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise SigningError(f"{label}: must carry a real .git directory (a bare or "
                           "symlinked gitdir is rejected)")
    origin = _git(path, ["remote", "get-url", "origin"], "remote origin")
    if _origin_owner_repo(origin) != OFFICIAL_HUB_OWNER_REPO:
        raise SigningError(f"{label}: origin is not the pinned official repository "
                           f"{OFFICIAL_HUB_OWNER_REPO!r}")
    head = _git(path, ["rev-parse", "--verify", "HEAD"], "HEAD resolution")
    if not COMMIT_RE.fullmatch(head):
        raise SigningError(f"{label}: HEAD is not a 40-hex commit")
    if claimed_commit is not None and head != claimed_commit:
        raise SigningError(f"{label}: HEAD {head} does not equal the claimed commit "
                           f"{claimed_commit}")
    tree = _git(path, ["rev-parse", "--verify", "HEAD^{tree}"], "tree resolution")
    if not COMMIT_RE.fullmatch(tree):
        raise SigningError(f"{label}: tree id did not resolve")
    listing = _git(path, ["ls-tree", "-r", "-z", "HEAD"], "tracked tree")
    tracked = {}
    for record in listing.split("\0"):
        if not record:
            continue
        meta, _, rel = record.partition("\t")
        fields = meta.split()
        if len(fields) != 3:
            raise SigningError(f"{label}: unparsable HEAD tree entry")
        mode, _type, blob = fields
        if mode == "120000":
            raise SigningError(f"{label}: tracked symlink in HEAD: {rel}")
        if mode == "160000":
            raise SigningError(f"{label}: tracked gitlink (submodule) in HEAD: {rel}")
        if mode not in ("100644", "100755"):
            raise SigningError(f"{label}: unsupported HEAD mode {mode} for {rel}")
        tracked[rel] = blob
    ancestors = set()
    for rel in tracked:
        parts = rel.split("/")
        for depth in range(len(parts)):
            ancestors.add("/".join(parts[:depth]))
    disk_files = set()
    disk_dirs = {""}
    for dirpath, dirnames, filenames in os.walk(str(path)):
        rel_dir = pathlib.Path(dirpath).relative_to(path).as_posix()
        if rel_dir == ".":
            rel_dir = ""
            if ".git" in dirnames:
                dirnames.remove(".git")
        for name in dirnames:
            disk_dirs.add((rel_dir + "/" + name).lstrip("/"))
        for name in filenames:
            rel = (rel_dir + "/" + name).lstrip("/")
            full = pathlib.Path(dirpath) / name
            if full.is_symlink():
                raise SigningError(f"{label}: symlink on disk outside .git: {rel}")
            st = full.lstat()
            if not stat.S_ISREG(st.st_mode):
                raise SigningError(f"{label}: non-regular file on disk: {rel}")
            disk_files.add(rel)
    for extra_dir in sorted(disk_dirs - ancestors - {".git"}):
        raise SigningError(f"{label}: directory outside HEAD: {extra_dir}")
    for extra in sorted(disk_files - set(tracked)):
        raise SigningError(f"{label}: untracked or ignored file outside HEAD: {extra}")
    for missing in sorted(set(tracked) - disk_files):
        raise SigningError(f"{label}: HEAD file missing on disk: {missing}")
    for rel in sorted(tracked):
        data = (path / rel).read_bytes()
        if _blob_sha1(data) != tracked[rel]:
            raise SigningError(f"{label}: {rel} differs from the HEAD blob; "
                               "only the exact commit bytes are accepted")
    return {"head": head, "tree": tree}


# ---------------------------------------------------------------------------
# trust + signing key (never logged)
# ---------------------------------------------------------------------------

def load_official_trust(build_catalog, hubcore, tooling_root):
    try:
        trust = build_catalog.load_trust(tooling_root)
    except hubcore.HubError as error:
        raise SigningError(f"configured public trust is invalid: {error}") from None
    if not trust:
        raise SigningError("public-key.json is missing from trusted tooling: the "
                           "official trust root must be configured to sign")
    if set(trust) != {hubcore.PRODUCTION_KEY_ID}:
        raise SigningError("public-key.json must configure exactly the official "
                           f"root identity {hubcore.PRODUCTION_KEY_ID!r}")
    return trust


def load_signing_key(hubcore, trust):
    value = os.environ.get(SIGNING_ENV_NAME)
    if not value:
        raise SigningError(f"{SIGNING_ENV_NAME} is not present; refusing to "
                           "fabricate a signature")
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:
        raise SigningError(f"{SIGNING_ENV_NAME} must hold strict base64 of the raw "
                           "32-byte Ed25519 key") from None
    if len(raw) != 32:
        raise SigningError(f"{SIGNING_ENV_NAME} must hold a raw 32-byte Ed25519 key")
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    try:
        key = Ed25519PrivateKey.from_private_bytes(raw)
    except Exception:
        raise SigningError(f"{SIGNING_ENV_NAME} is not a usable Ed25519 raw key") from None
    derived = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    if trust[hubcore.PRODUCTION_KEY_ID] != derived:
        raise SigningError("refusing to sign: the signing key's public identity does "
                           "not match the configured official trust root")
    return key


# ---------------------------------------------------------------------------
# path discipline for inputs and outputs
# ---------------------------------------------------------------------------

def _is_under(child_real, parent_real):
    child_s = os.fspath(child_real)
    parent_s = os.fspath(parent_real)
    try:
        return os.path.commonpath([child_s, parent_s]) == parent_s
    except ValueError:
        return False


def validate_out_root(out_arg, data_root, tooling_root):
    """Return the CANONICAL requested output directory itself.

    A nonexistent requested leaf keeps its full leaf path (only fresh parents
    and the leaf are created later); the bridge never silently retargets into
    the parent. An existing leaf must be an empty real directory. The whole
    resolved path must sit outside both verified snapshots.
    """
    out = pathlib.Path(out_arg)
    if out.is_symlink():
        raise SigningError("--out must not be a symlink")
    out_real = pathlib.Path(os.path.realpath(str(out)))
    if out.exists():
        if not out_real.is_dir():
            raise SigningError("--out exists and is not a directory")
        if any(os.scandir(out_real)):
            raise SigningError("--out must be a fresh or empty directory: the bridge "
                               "never overwrites foreign output")
    data_real = pathlib.Path(data_root).resolve()
    tooling_real = pathlib.Path(tooling_root).resolve()
    for label, forbidden in (("data checkout", data_real), ("tooling", tooling_real)):
        if out_real == forbidden or _is_under(out_real, forbidden):
            raise SigningError(f"--out must live outside the {label}; output can never "
                               "land inside a verified snapshot")
    return out_real


def _safe_output_rel(rel):
    if (not rel or rel.startswith("/") or "\\" in rel or "\0" in rel
            or any(part in ("", ".", "..") for part in rel.split("/"))):
        raise SigningError(f"internal error: unsafe output path {rel!r}")


def write_outputs(out_root, files):
    written = []
    for rel in sorted(files):
        _safe_output_rel(rel)
        data = files[rel]
        target = out_root / rel
        if target.is_symlink():
            raise SigningError(f"refusing to write through a symlink: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise SigningError(f"refusing foreign overwrite: {rel} already exists")
        descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            view = memoryview(data)
            offset = 0
            while offset < len(view):
                written_bytes = os.write(descriptor, view[offset:])
                if written_bytes <= 0:
                    raise SigningError(f"short write on {rel}")
                offset += written_bytes
        finally:
            os.close(descriptor)
        if target.read_bytes() != data:
            raise SigningError(f"output verification failed: {rel} does not read back "
                               "byte-identically")
        written.append(rel)
    return written


# ---------------------------------------------------------------------------
# reviews mode
# ---------------------------------------------------------------------------

def collect_unsigned_reviews(data_root):
    reviews_root = pathlib.Path(data_root) / "reviews"
    if not reviews_root.is_dir() or reviews_root.is_symlink():
        raise SigningError("reviews mode needs real unsigned review records under "
                           "reviews/<id>/<version>.review.json in the snapshot")
    found = []
    for path in sorted(reviews_root.rglob("*")):
        if path.is_symlink():
            raise SigningError("symlink inside the reviews input tree is forbidden")
        if not path.is_file():
            continue
        rel = path.relative_to(reviews_root).as_posix()
        if rel.endswith(".sig"):
            raise SigningError(f"reviews mode takes UNSIGNED records only; {rel} is "
                               "already signed (that input belongs to catalog mode)")
        if not REVIEW_REL_RE.fullmatch(rel):
            raise SigningError(f"unexpected file under reviews/: {rel}")
        found.append((rel, path))
    if not found:
        raise SigningError("no review records found under reviews/")
    return found


def run_reviews_mode(args, hubcore, build_catalog, runtime_dependency,
                     tooling_info, data_info, out_root):
    registry_path = pathlib.Path(args.data) / "catalog" / "skills.json"
    if not registry_path.is_file():
        raise SigningError("data snapshot has no catalog/skills.json")
    try:
        registry = hubcore.validate_registry(
            json.loads(registry_path.read_bytes()))
    except hubcore.HubError as error:
        raise SigningError(f"registry gate failed: {error}") from None
    entries = {e["id"]: e for e in registry["skills"]}

    pending = []
    for rel, path in collect_unsigned_reviews(args.data):
        match = REVIEW_REL_RE.fullmatch(rel)
        id_, version = match.group(1), match.group(2)
        entry = entries.get(id_)
        if entry is None:
            raise SigningError(f"review record for unknown registry id {id_!r}")
        if entry["versionTarget"] != version:
            raise SigningError(f"{id_}: review version {version} differs from the "
                               f"registry versionTarget {entry['versionTarget']!r}")
        if not entry["status"]["reviewed"]:
            raise SigningError(f"{id_}: review record exists but the registry status "
                               "is not reviewed (no promotion here)")
        record_bytes = path.read_bytes()
        try:
            record = json.loads(record_bytes)
        except ValueError:
            raise SigningError(f"{id_}: review record is not valid JSON") from None
        if hubcore.encoded(record) != record_bytes:
            raise SigningError(f"{id_}: review record must be canonical bytes")
        try:
            hubcore.validate_review(record)
        except hubcore.HubError as error:
            raise SigningError(f"{id_}: review record failed validation: {error}") from None
        if record["decision"] != "approve":
            raise SigningError(f"{id_}: only approved review records can be signed; "
                               "a reject decision must be resolved before signing")
        if record["id"] != id_ or record["version"] != version:
            raise SigningError(f"{id_}: review record identity drift")
        try:
            bindings, manifest, _files = build_catalog.bind_package(
                entry, pathlib.Path(args.data))
        except hubcore.HubError as error:
            raise SigningError(f"{id_}: package recompute failed: {error}") from None
        if bindings is None:
            raise SigningError(f"{id_}: reviewed entry has no packaged archives")
        try:
            for channel, binding in bindings.items():
                hubcore.join_review(record, manifest, binding, f"{id_}/{channel}")
        except hubcore.HubError as error:
            raise SigningError(f"{id_}: review join failed: {error}") from None
        pending.append((rel, record_bytes, entry, bindings, record))

    trust = load_official_trust(build_catalog, hubcore, args.tooling)
    key = load_signing_key(hubcore, trust)

    files = {}
    reviews = []
    for rel, record_bytes, entry, bindings, record in pending:
        try:
            envelope = hubcore.sign_envelope(record_bytes, key,
                                             hubcore.PRODUCTION_KEY_ID)
        except hubcore.HubError as error:
            raise SigningError(f"{entry['id']}: signing failed: {error}") from None
        try:
            verified_id = hubcore.verify_envelope(record_bytes, envelope, trust)
        except hubcore.HubError as error:
            raise SigningError(f"{entry['id']}: produced signature does not verify") from None
        if verified_id != hubcore.PRODUCTION_KEY_ID:
            raise SigningError(f"{entry['id']}: signature identity drifted")
        files["reviews/" + rel] = record_bytes
        files["reviews/" + rel + ".sig"] = envelope
        reviews.append({
            "id": entry["id"],
            "version": entry["versionTarget"],
            "reviewPath": "reviews/" + rel,
            "recordSha256": hubcore.sha256_hex(record_bytes),
            "signatureSha256": hubcore.sha256_hex(envelope),
            "keyID": hubcore.PRODUCTION_KEY_ID,
            "reviewStage": record["reviewStage"],
            "reviewer": record["reviewer"],
            "reviewedAt": record["reviewedAt"],
            "decision": record["decision"],
            "contentDigest": record["contentDigest"],
            "packageSha256": record["packageSha256"],
            "archivePaths": {channel: bindings[channel]["path"]
                             for channel in sorted(bindings)},
            "archiveSize": bindings[sorted(bindings)[0]]["size"],
        })

    receipt = {
        "schemaVersion": 1,
        "mode": "reviews",
        "hubRepository": OFFICIAL_HUB_OWNER_REPO,
        "sourceCommit": data_info["head"],
        "dataTree": data_info["tree"],
        "toolingCommit": tooling_info["head"],
        "toolingTree": tooling_info["tree"],
        "keyID": hubcore.PRODUCTION_KEY_ID,
        "reviewCount": len(reviews),
        "reviews": reviews,
        "outputs": [{"path": rel, "sha256": hubcore.sha256_hex(files[rel]),
                     "size": len(files[rel])} for rel in sorted(files)],
    }
    finalize_receipt(hubcore, files, receipt, key, trust)
    written = write_outputs(out_root, files)
    print(f"signing-bridge reviews: signed {len(reviews)} approved review record(s); "
          f"wrote {len(written)} file(s) to {out_root}")


# ---------------------------------------------------------------------------
# catalog mode
# ---------------------------------------------------------------------------

def _review_block_from_snapshot(hubcore, args, entry, review_block):
    path = pathlib.Path(args.data) / review_block["path"]
    if path.is_symlink() or not path.is_file():
        raise SigningError(f"{entry['id']}: bound review record is missing")
    record_bytes = path.read_bytes()
    if hubcore.sha256_hex(record_bytes) != review_block["sha256"]:
        raise SigningError(f"{entry['id']}: review record bytes drifted from the "
                           "feed binding")
    record = json.loads(record_bytes)
    return record


def _gate_impeccable_runtime(hubcore, runtime_dependency, args, entry, outputs):
    """Impeccable's mandatory slot must carry the REAL H6 runtime binding.

    The offered archive must embed references/engine-dependency.json, the
    builder-validated frozen descriptor bytes and the raw engine bytes must
    be staged in the publication output, and every cross-check (embedded ==
    frozen, staged artifact size/sha) is recomputed here so an omitted
    descriptor can never bypass H6 by simply not being present.
    """
    archive = pathlib.Path(args.data) / entry["package"]["path"]
    if archive.is_symlink() or not archive.is_file():
        raise SigningError(f"{IMPECCABLE_ID}: referenced archive vanished: "
                           f"{entry['package']['path']}")
    try:
        files = hubcore.check_archive_bytes(archive.read_bytes())
        rel = runtime_dependency.EMBEDDED_DESCRIPTOR_REL
        blob = files.get(rel)
        if blob is None:
            raise hubcore.HubError(f"embedded {rel} is missing")
        descriptor = runtime_dependency.parse_descriptor(blob, IMPECCABLE_ID)
        artifact_rel = descriptor["artifact"]["path"]
        frozen_rel = runtime_dependency.FROZEN_DESCRIPTOR_REL
        if frozen_rel not in outputs or artifact_rel not in outputs:
            raise hubcore.HubError(
                "the builder did not stage the validated frozen descriptor and "
                "raw engine runtime artifact")
        frozen = runtime_dependency.load_frozen_descriptor_bytes(
            pathlib.Path(args.data), IMPECCABLE_ID)
        if frozen != blob or outputs[frozen_rel] != frozen:
            raise hubcore.HubError(
                "staged frozen descriptor disagrees with the embedded descriptor")
        artifact = outputs[artifact_rel]
        if len(artifact) != descriptor["artifact"]["size"] or \
                hubcore.sha256_hex(artifact) != descriptor["artifact"]["sha256"]:
            raise hubcore.HubError(
                "staged raw engine bytes disagree with the validated descriptor")
    except hubcore.HubError as error:
        raise SigningError(f"{IMPECCABLE_ID}: mandatory runtime gate failed: "
                           f"{error}") from None


def enforce_launch_gate(hubcore, runtime_dependency, args, registry, outputs):
    """Root-approved incremental publication gate (staged opening, 2026-10-27).

    This replaced ONLY the old batch-completeness rule (>=40 unique qualified
    iOS offers plus all nine mandatory deep IDs present in both feeds). Every
    per-item trust invariant stays enforced here, with the iOS advertised set
    now checked EXPLICITLY instead of implicitly:

      * both feeds exist, are nonempty, and carry unique ids;
      * each feed is EXACTLY the qualified, download-eligible registry rows
        advertising that channel — no invented rows, no partial drop, no
        duplicates. The four App-provided builtin ids are native App features
        and never Hub download offers, so they are excluded by exact ID
        (a kind/display/source relabel can never hide an arbitrary mandatory
        ID behind the builtin name); the builtins are iOS-only by contract;
      * every offered scripted entry requires status.executionVerified true,
        frozen adaptation and its actually bound review
        guest-execution-qualified with execution linux/riscv64/guest-verified;
        guide-only entries keep static-content-reviewed with an empty
        execution claim (no invented guest claim, no guide/script relabel);
      * the nine mandatory deep IDs stay pinned in this trusted tooling
        (registry relabeling can never satisfy the gate): whenever such an ID
        is actually offered it ships as a real remote-script package matching
        the frozen plannedRuntime contract, present on EXACTLY its qualified
        plannedRuntime.installPlatforms channels (Root 2026-10-28: a
        both-channel plan must appear in BOTH feeds; an explicitly
        iOS-only/Android-only qualified plan is admitted on its declared
        channel only, with no invented channel), with the remote-script and —
        for impeccable — the full H6 runtime binding rechecked on EVERY
        offered channel;
      * held-back (not yet admitted) mandatory IDs no longer block unrelated
        qualified offers;
      * the retired batch rule is reported ONLY as informational
        complete-selection coverage metadata, computed honestly so a partial
        feed can never claim all-nine/40 completeness.

    There is no parameter, flag or environment option that disables any of
    the above.
    """
    entries_by_id = {e["id"]: e for e in registry["skills"]}
    try:
        ios_feed = json.loads(outputs["catalog.json"])
        android_feed = json.loads(outputs["android/catalog.json"])
    except KeyError:
        raise SigningError("builder did not emit both channel feeds") from None
    ios_ids = [e["id"] for e in ios_feed["entries"]]
    android_ids = [e["id"] for e in android_feed["entries"]]
    if len(set(ios_ids)) != len(ios_ids):
        raise SigningError("duplicate ids inside the iOS feed")
    if len(set(android_ids)) != len(android_ids):
        raise SigningError("duplicate ids inside the Android feed")
    if not set(ios_ids) or not set(android_ids):
        raise SigningError("launch gate: an empty feed is never publishable")
    expected_ios = {e["id"] for e in registry["skills"]
                    if e["status"]["qualified"]
                    and "ios" in e["plannedRuntime"]["installPlatforms"]
                    and not hubcore.is_download_offer_excluded(e["id"])}
    if set(ios_ids) != expected_ios:
        raise SigningError("launch gate: the iOS feed must be exactly the qualified "
                           "rows advertising iOS (App-provided builtin offers "
                           "excluded; no partial drop, no invented rows)")
    expected_android = {e["id"] for e in registry["skills"]
                        if e["status"]["qualified"]
                        and "android" in e["plannedRuntime"]["installPlatforms"]
                        and not hubcore.is_download_offer_excluded(e["id"])}
    if set(android_ids) != expected_android:
        raise SigningError("launch gate: the Android feed must be exactly the qualified "
                           "rows advertising android (App-provided builtin offers "
                           "excluded; no partial drop, no invented rows)")
    for feed in (ios_feed, android_feed):
        for entry in feed["entries"]:
            if entry.get("status", {}).get("published") is not True:
                raise SigningError(f"{entry['id']}: release offer requires "
                                   "feed status.published true")
            registry_entry = entries_by_id[entry["id"]]
            scripted = entry["runtime"]["scriptRuntime"] != "none"
            record = _review_block_from_snapshot(hubcore, args, entry, entry["review"])
            if scripted:
                if not registry_entry["status"]["executionVerified"]:
                    raise SigningError(f"{entry['id']}: offered script package requires "
                                       "status.executionVerified true")
                if registry_entry["status"]["adaptation"] != "frozen":
                    raise SigningError(f"{entry['id']}: offered script package requires "
                                       "frozen adaptation")
                if record["reviewStage"] != "guest-execution-qualified" or record["execution"] != {
                        "os": "linux", "arch": "riscv64", "evidence": "guest-verified"}:
                    raise SigningError(f"{entry['id']}: offered script package requires "
                                       "a guest-execution-qualified review bound to "
                                       "linux/riscv64/guest-verified execution")
            else:
                if record["reviewStage"] != "static-content-reviewed":
                    raise SigningError(f"{entry['id']}: guide-only package must keep a "
                                       "static-content-reviewed stage")
                if record["execution"] != {"os": None, "arch": "n/a", "evidence": "unproven"}:
                    raise SigningError(f"{entry['id']}: guide-only package carries an "
                                       "invented guest claim")
    # A pinned mandatory ID that is actually offered keeps its full contract
    # on EVERY channel where it is offered: real remote-script bytes, the
    # frozen plan and — for impeccable — the H6 runtime binding are recomputed
    # per channel from that channel's own feed entry (no assumed iOS
    # representative). A guide relabel can never satisfy a mandatory slot.
    # Channel eligibility itself is authoritative from the qualified registry
    # row: plannedRuntime.installPlatforms is the explicit Root-reviewed
    # platform admission (2026-10-28). The per-channel feed-equality checks
    # above already force each feed to be EXACTLY the qualified rows
    # advertising that channel, so a both-channel plan stays present in both
    # feeds and an explicitly single-platform plan is admitted on its
    # declared channel only — the checks below keep those mandatory-specific
    # invariants explicit and fail-closed: never a dropped declared channel,
    # never an injected unplanned channel, never a fabricated Android offer.
    ios_by_id = {e["id"]: e for e in ios_feed["entries"]}
    android_by_id = {e["id"]: e for e in android_feed["entries"]}
    offered_by_channel = {"ios": ios_by_id, "android": android_by_id}
    offered_mandatory = sorted(MANDATORY_DEEP_IDS & (set(ios_ids) | set(android_ids)))
    for id_ in offered_mandatory:
        declared_channels = [channel for channel in ("ios", "android")
                             if channel in entries_by_id[id_]
                             ["plannedRuntime"]["installPlatforms"]]
        for channel in declared_channels:
            if id_ not in offered_by_channel[channel]:
                raise SigningError(
                    f"launch gate: {id_}: an offered mandatory deep adaptation is "
                    f"missing from its declared {channel} feed; a mandatory slot "
                    "can never ship on only part of its qualified planned channels")
        for channel in ("ios", "android"):
            if id_ in offered_by_channel[channel] and channel not in declared_channels:
                raise SigningError(
                    f"launch gate: {id_}: a mandatory offer on the unplanned "
                    f"{channel} channel is never admissible; no channel may be "
                    "invented or fabricated to satisfy a mandatory slot")
        for channel in declared_channels:
            entry = offered_by_channel[channel][id_]
            if entry["runtime"]["scriptRuntime"] != "remote":
                raise SigningError(f"{id_}: mandatory deep adaptations must ship as "
                                   "remote-script packages; a guide-only replacement "
                                   "can never satisfy the launch gate")
        if entries_by_id[id_]["plannedRuntime"]["scriptRuntime"] != "remote":
            raise SigningError(f"{id_}: plannedRuntime.scriptRuntime drifted away "
                               "from the frozen remote-script contract")
        if id_ == IMPECCABLE_ID:
            for channel in declared_channels:
                _gate_impeccable_runtime(hubcore, runtime_dependency, args,
                                         offered_by_channel[channel][id_], outputs)
    # Informational complete-selection coverage ONLY: honest metadata about
    # how far this feed is from the retired 40 + all-nine launch batch, never
    # a blockade and never a completeness claim for a partial feed. The
    # retired target counts the QUALIFIED REGISTRY SELECTION (including the
    # four App-provided builtins); the actual download offers are the
    # qualified non-builtin rows, so the coverage reports the selection and
    # the builtin-provided count separately from the offer counts.
    selection_qualified = sum(1 for e in registry["skills"]
                              if e["status"]["qualified"])
    builtin_provided = sum(1 for e in registry["skills"]
                           if e["id"] in hubcore.APP_PROVIDED_BUILTIN_IDS
                           and e["status"]["qualified"])
    download_eligible = selection_qualified - builtin_provided
    meets_target = selection_qualified >= COMPLETE_SELECTION_QUALIFIED_TARGET
    all_mandatory_present = bool(offered_mandatory) and set(offered_mandatory) == MANDATORY_DEEP_IDS
    return {
        "policy": "incremental-2026-10-27",
        "iosQualified": len(set(ios_ids)),
        "androidQualified": len(set(android_ids)),
        "selectionQualified": selection_qualified,
        "builtinProvided": builtin_provided,
        "iosMatchesRegistry": True,
        "androidMatchesRegistry": True,
        "mandatoryDeepIds": sorted(MANDATORY_DEEP_IDS),
        "mandatoryDeepOffered": offered_mandatory,
        "completeSelectionCoverage": {
            "informationalOnly": True,
            "qualifiedTarget": COMPLETE_SELECTION_QUALIFIED_TARGET,
            "selectionQualified": selection_qualified,
            "meetsQualifiedTarget": meets_target,
            "builtinProvided": builtin_provided,
            "downloadEligible": download_eligible,
            "mandatoryDeepTotal": len(MANDATORY_DEEP_IDS),
            "mandatoryDeepOfferedCount": len(offered_mandatory),
            "mandatoryDeepAllPresent": all_mandatory_present,
            "complete": meets_target and all_mandatory_present,
        },
    }


def finalize_receipt(hubcore, files, receipt, key, trust):
    """Authenticate the canonical receipt itself with the official envelope.

    The receipt enumerates every output/package/review/feed/signature hash
    EXCLUDING itself and its own sidecar (no circular self-hash), then the
    same production identity signs the receipt bytes so T/S/X plus all output
    summaries are cryptographically bound, not merely asserted.
    """
    receipt_bytes = hubcore.encoded(receipt)
    try:
        envelope = hubcore.sign_envelope(receipt_bytes, key, hubcore.PRODUCTION_KEY_ID)
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


def stage_referenced_inputs(hubcore, args, outputs, trust, files):
    """Stage EXACTLY the feed-referenced package and review bytes from X.

    The publication artifact must be standalone: every archive and every
    signed review record (record + envelope) that either feed binds is
    re-verified against the feed's own digests and copied into the output at
    its feed path. Nothing else from X is copied; no Git metadata and no key
    material ever enter the output.
    """
    for feed_name in ("catalog.json", "android/catalog.json"):
        feed = json.loads(outputs[feed_name])
        for entry in feed["entries"]:
            package = entry["package"]
            archive = pathlib.Path(args.data) / package["path"]
            if archive.is_symlink() or not archive.is_file():
                raise SigningError(f"{entry['id']}: referenced archive vanished: "
                                   f"{package['path']}")
            blob = archive.read_bytes()
            if (hubcore.sha256_hex(blob) != package["sha256"]
                    or len(blob) != package["size"]):
                raise SigningError(f"{entry['id']}: referenced archive bytes drifted "
                                   "from the signed feed binding")
            try:
                unpacked = hubcore.check_archive_bytes(blob)
                if hubcore.content_digest(unpacked) != package["contentDigest"]:
                    raise hubcore.HubError("contentDigest mismatch")
            except hubcore.HubError as error:
                raise SigningError(f"{entry['id']}: referenced archive failed the "
                                   f"package gate: {error}") from None
            files[package["path"]] = blob
            review = entry["review"]
            record_path = pathlib.Path(args.data) / review["path"]
            envelope_path = pathlib.Path(args.data) / (review["path"] + ".sig")
            if (record_path.is_symlink() or not record_path.is_file()
                    or envelope_path.is_symlink() or not envelope_path.is_file()):
                raise SigningError(f"{entry['id']}: referenced review bytes vanished")
            record_bytes = record_path.read_bytes()
            envelope_bytes = envelope_path.read_bytes()
            if hubcore.sha256_hex(record_bytes) != review["sha256"]:
                raise SigningError(f"{entry['id']}: referenced review bytes drifted "
                                   "from the signed feed binding")
            try:
                verified = hubcore.verify_envelope(record_bytes, envelope_bytes, trust)
            except hubcore.HubError as error:
                raise SigningError(f"{entry['id']}: referenced review signature "
                                   f"failed: {error}") from None
            if verified != review["keyID"] or verified != hubcore.PRODUCTION_KEY_ID:
                raise SigningError(f"{entry['id']}: referenced review identity drifted")
            files[review["path"]] = record_bytes
            files[review["path"] + ".sig"] = envelope_bytes


def run_catalog_mode(args, hubcore, build_catalog, runtime_dependency,
                     tooling_info, data_info, out_root, publication_immutability,
                     tooling_root):
    registry_path = pathlib.Path(args.data) / "catalog" / "skills.json"
    if not registry_path.is_file():
        raise SigningError("data snapshot has no catalog/skills.json")
    try:
        registry = hubcore.validate_registry(
            json.loads(registry_path.read_bytes()))
    except hubcore.HubError as error:
        raise SigningError(f"registry gate failed: {error}") from None
    deep_ids = {e["id"] for e in registry["skills"] if e["deepAdaptation"]}
    if deep_ids != set(MANDATORY_DEEP_IDS):
        raise SigningError("the registry deepAdaptation set drifted from the pinned "
                           "mandatory IDs; relabeling can never satisfy the launch gate")

    trust = load_official_trust(build_catalog, hubcore, args.tooling)
    key = load_signing_key(hubcore, trust)

    try:
        outputs = build_catalog.build(registry, "release", args.source_commit,
                                      pathlib.Path(args.data),
                                      pathlib.Path(args.data), trust)
    except hubcore.HubError as error:
        raise SigningError(f"trusted release builder refused: {error}") from None

    # Publication-history immutability, enforced here in the ACTUAL trusted
    # signer path (never only in a CLI wrapper): the baseline comes from the
    # trusted tooling root T — the verified cumulative ledger plus the
    # currently published feed pairs — and never from the caller's data
    # checkout X. A candidate offer reusing an already-published
    # (channel, id, version) with a different contentDigest is refused BEFORE
    # any signature is produced, even though this bridge could sign the new
    # bytes.
    try:
        # The baseline ledger must live INSIDE the trusted tooling root: a
        # ledger supplied from the data checkout X (or anywhere else) is
        # caller-replaceable and could omit historical rows, which the
        # coverage rule alone cannot detect for versions already removed from
        # the latest feed.
        ledger_override = getattr(args, "publication_ledger", None)
        ledger_path = (pathlib.Path(ledger_override).resolve() if ledger_override
                       else (tooling_root / publication_immutability.LEDGER_REL).resolve())
        canonical_ledger = (tooling_root / publication_immutability.LEDGER_REL).resolve()
        if ledger_path != canonical_ledger:
            raise SigningError(
                "the publication ledger must use its canonical path inside the trusted tooling "
                "root; refusing an alternate or caller-supplied baseline input")
        published_y = getattr(args, "published_y", None)
        has_history = ledger_path.is_file() or any(
            (tooling_root / rel).exists()
            for _channel, feed, signature in publication_immutability.FEED_PAIRS
            for rel in (feed, signature))
        if has_history and published_y is None:
            raise SigningError(
                "catalog signing with publication history requires --published-y "
                "resolved independently from the live publication ref; the frozen "
                "tooling tree cannot stand in for the current published baseline")
        baseline_provenance = {}
        baseline = publication_immutability.build_validated_baseline(
            tooling_root, ledger_path, published_y,
            baseline_provenance)
        publication_immutability.assert_immutable_publication(outputs, baseline)
    except hubcore.HubError as error:
        raise SigningError(f"publication immutability gate refused: {error}") from None

    gate = enforce_launch_gate(hubcore, runtime_dependency, args, registry, outputs)

    files = dict(outputs)
    stage_referenced_inputs(hubcore, args, outputs, trust, files)
    signatures = {}
    for name in ("catalog.json", "android/catalog.json"):
        payload = outputs[name]
        try:
            envelope = hubcore.sign_envelope(payload, key, hubcore.PRODUCTION_KEY_ID)
        except hubcore.HubError as error:
            raise SigningError(f"{name}: signing failed: {error}") from None
        try:
            verified_id = hubcore.verify_envelope(payload, envelope, trust)
        except hubcore.HubError as error:
            raise SigningError(f"{name}: produced signature does not verify") from None
        if verified_id != hubcore.PRODUCTION_KEY_ID:
            raise SigningError(f"{name}: signature identity drifted")
        sig_name = name[: -len(".json")] + ".sig"
        files[sig_name] = envelope
        signatures[name] = sig_name

    receipt = {
        "schemaVersion": 1,
        "mode": "catalog",
        "hubRepository": OFFICIAL_HUB_OWNER_REPO,
        "sourceCommit": data_info["head"],
        "dataTree": data_info["tree"],
        "toolingCommit": tooling_info["head"],
        "toolingTree": tooling_info["tree"],
        "keyID": hubcore.PRODUCTION_KEY_ID,
        "launchGate": gate,
        "publicationBaseline": baseline_provenance,
        "signedFeeds": sorted(signatures),
        "outputs": [{"path": name, "sha256": hubcore.sha256_hex(files[name]),
                     "size": len(files[name])} for name in sorted(files)],
    }
    finalize_receipt(hubcore, files, receipt, key, trust)
    written = write_outputs(out_root, files)
    coverage = gate["completeSelectionCoverage"]
    print(f"signing-bridge catalog: signed both channel feeds at source "
          f"{args.source_commit}; iOS qualified {gate['iosQualified']}, Android "
          f"{gate['androidQualified']}; mandatory deep offered "
          f"{len(gate['mandatoryDeepOffered'])}/"
          f"{coverage['mandatoryDeepTotal']}; complete-selection coverage "
          f"(informational only) {coverage['complete']}; wrote {len(written)} "
          f"file(s) to {out_root}")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("reviews", "catalog"), required=True)
    parser.add_argument("--source-commit", dest="source_commit", required=True,
                        help="claimed 40-hex commit S (reviews) or X (catalog) "
                             "the data checkout must exactly equal")
    parser.add_argument("--data", required=True,
                        help="clean immutable data checkout at the claimed commit")
    parser.add_argument("--out", required=True,
                        help="fresh output directory outside the data and tooling roots")
    parser.add_argument("--tooling", default=None,
                        help="trusted tooling root (defaults to this script's checkout)")
    parser.add_argument("--publication-ledger", default=None,
                        help="canonical cumulative publication ledger inside the trusted tooling "
                             "root (default <tooling>/catalog/publication-ledger.json); "
                             "an alternate path is refused")
    parser.add_argument("--published-y", default=None,
                        help="independently resolved 40-hex publication commit Y that "
                             "carries the current published feeds; the immutability "
                             "baseline is then anchored to that pin instead of the "
                             "tooling working tree, so an older tooling checkout can "
                             "never hide already-published history")
    args = parser.parse_args()

    if not COMMIT_RE.fullmatch(args.source_commit):
        _die("--source-commit must be exactly 40 lowercase hex characters")

    tooling_root = pathlib.Path(args.tooling) if args.tooling else \
        pathlib.Path(__file__).resolve().parents[1]
    if not tooling_root.is_dir() or tooling_root.is_symlink():
        _die("--tooling is not a real directory")
    tooling_scripts = pathlib.Path(
        os.path.realpath(str(tooling_root / "scripts")))
    for required_module in ("hubcore.py", "build_catalog.py", "runtime_dependency.py",
                            "dependency_declaration.py", "publication_immutability.py"):
        if not (tooling_scripts / required_module).is_file():
            _die(f"trusted tooling is incomplete: scripts/{required_module} is missing")

    data_real = pathlib.Path(args.data).resolve()
    if data_real == tooling_root.resolve():
        _die("--data and --tooling must be separate checkouts")
    if _is_under(pathlib.Path(os.path.realpath(os.getcwd())), data_real):
        _die("the bridge must not run with the current directory inside the data "
             "checkout")

    # Import code ONLY from the trusted tooling root; scrub any sys.path entry
    # that could let the data checkout satisfy an import.
    sys.path = [str(tooling_scripts)] + [
        p for p in sys.path
        if p and not _is_under(pathlib.Path(os.path.realpath(p)), data_real)]
    for name in ("hubcore", "build_catalog", "runtime_dependency",
                 "dependency_declaration", "publication_immutability"):
        sys.modules.pop(name, None)
    import hubcore  # noqa: E402  (trusted T import, path-scrubbed above)
    import build_catalog  # noqa: E402
    import runtime_dependency  # noqa: E402
    import dependency_declaration  # noqa: E402
    import publication_immutability  # noqa: E402
    for module in (hubcore, build_catalog, runtime_dependency,
                   dependency_declaration, publication_immutability):
        module_file = pathlib.Path(module.__file__).resolve()
        if not _is_under(module_file, pathlib.Path(str(tooling_scripts))):
            _die(f"imported module resolves outside trusted tooling: {module.__name__}")

    out_root = validate_out_root(args.out, args.data, tooling_root)

    tooling_info = verify_exact_snapshot("tooling", tooling_root)
    data_info = verify_exact_snapshot("data", args.data, args.source_commit)

    if args.mode == "reviews":
        run_reviews_mode(args, hubcore, build_catalog, runtime_dependency,
                         tooling_info, data_info, out_root)
    else:
        run_catalog_mode(args, hubcore, build_catalog, runtime_dependency,
                         tooling_info, data_info, out_root,
                         publication_immutability, tooling_root)


if __name__ == "__main__":
    try:
        main()
    except SigningError as error:
        _die(str(error))
