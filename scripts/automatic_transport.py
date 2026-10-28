#!/usr/bin/env python3
"""Unattended GitHub-Actions transport primitives for automatic publication.

This module is FIXED TRUSTED TOOLING T that runs ONLY inside a scheduled
GitHub Actions job. It implements the three independently testable primitives
of the decided architecture — nothing else:

  1. a strict canonical bounded candidate-request parser (schemaVersion 1,
     mode reviews|catalog, sourceCommit, basePublication, policySha256 and a
     requestId derived from the canonical other fields; unknown fields,
     path/identity overrides, non-canonical bytes and oversized input are
     refused). The official repositories are fixed constants
     (JiangNanGenius/floe-skill-hub and JiangNanGenius/floe-agent); branch
     names are trusted workflow config and are NEVER request input.

   2. a safe trusted-tooling history refresh: given the immutable reviewed
      bootstrap anchor commit A and the live official-main commit Y resolved
      from the fixed origin by the CLI itself, it proves (a) the anchor disk is
      the exact clean anchor snapshot via the EXISTING sign_publication
      verification helper, (b) every tracked path outside the minimal
      publication-DATA allowlist has an identical Git (mode, blob object id)
      pair at Y as at A — so scripts/**, public-key.json, schema/**,
      policy/config files (catalog/curation.json), workflows (.github/**),
      engine contracts/locks (engines/**), tests/** and every unknown path
      stay byte-identical INCLUDING the executable bit, and any code/trust
      drift fails closed with HOLD instead of silently trusting newer code;
      tracked deletions are tolerated ONLY for ordinary mutable sources/**
      data (licence/notice material, the ledger, feeds, packages, reviews,
      frozen, engines and every trust/tooling path are never deletable); and
      (c) EVERY effective main-first-parent ledger transition between A and Y
      (git rev-list --first-parent with the ledger path filter over the
      locally fetched complete history) keeps the previous mainline ledger
      byte/structurally identical as an ordered prefix — so no row drop,
      rewrite, reordering or duplicate introduced anywhere in between can be
      hidden by a later append — each distinct ledger state is strictly
      canonical-parsed and independently re-verified against the official
      signed feed bytes at its immutable pin through the trusted-A
      publication_immutability functions, every observed publication pin stays
      reachable as an ancestor of live main, and the live current offers are
      covered. History that cannot be fully verified (anchor off the live
      first-parent mainline, unreadable intermediate objects, shallow clones)
      fails closed; there is never a caller-selected baseline.
      Candidate code is never executed,
     imported or checked out: Y is read exclusively from committed Git
     objects fetched over the fixed origin URL with argument lists only (no
     shell), inherited Git redirects stripped, replacement refs disabled and
     hooks suppressed. The existing canonical-ledger-inside-T signer is not
     weakened in any way; the refresh merely proves the existing signer code
     can safely run from live Y because all executable/trust bytes equal A
     and the live ledger verifies.

  3. signed relay metadata validation/extraction: the relay carries ONLY the
     canonical channel feeds with their signature envelopes,
     reviews/<id>/<semver>.review.json records with their envelopes, and the
     authenticated signing receipt with its own envelope — never packages,
     never binaries, never executable files or arbitrary paths. The receipt
     and every envelope are verified with public-key.json loaded at the
     trusted anchor, the receipt mode/sourceCommit must equal the parsed
     request exactly, and every relayed member's SHA-256/size must be bound
     by the signed receipt outputs list; archived package references stay at
     the immutable candidate source for the separate Hub publisher check.
     The validated metadata bytes/map is returned for a downstream PURE data
     write — this package performs no remote mutation itself.

It additionally exposes the X-vs-B engine-authority freeze required by the
architecture evidence (AFLT-PREMISE-PROOFS.json): the signer core reads the
impeccable frozen descriptor and raw engine bytes from the candidate data
checkout X, so freezing trusted tooling T alone does not freeze engine
authority. verify_candidate_engine_freeze() independently requires every
engines/** path at candidate X to equal the request base publication B in
(mode, bytes) (no engine add/remove/modify without a genuinely reviewed new
engine qualification, which can only arrive through an anchor update), every
published package archive at B to remain present at X byte- and
mode-identically (archive DELETION is refused in every mode; package history
is always frozen), and every archive embedding
``references/engine-dependency.json`` to equal the B frozen descriptor bytes.
The immutable review history is mode-aware and the mode is only authoritative
when it is the canonical requestId-bound mode of a validated request:
catalog mode (also the strict default) retains every base review record and
sidecar exactly, while the reviews mode permits the expected minimal
candidate pruning of historical review pairs but never any mutation of a
retained base record. verify_request_candidate_engine_freeze() binds the
candidate commit to the request sourceCommit, the freeze base to the request
basePublication and the history mode to the request mode; no caller-selected
flag weakens any of them. For the same reason verify_request_history_base()
binds a request basePublication to the live main commit that
run_history_refresh resolved itself from the fixed origin: the correct CAS
base is the current live main (the ledger commit of the last publication or
any reviewed code/data commit after it), never a historical feed-publication
pin, so a stale base is refused even when it was historically signed.

No secrets are ever read, copied or relocated here: the signing private key
stays only in the App repository's final signing step; this module verifies
signatures against PUBLIC material only. It never writes inside a verified
snapshot, never pushes, never dispatches anything, and honours the existing
fail-closed contracts by reusing the hubcore cryptographic helpers,
publication_immutability baseline verification and sign_publication snapshot
verification unchanged.
"""
import argparse
import io
import json
import pathlib
import re
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True  # keep the trusted checkout byte-clean

import hubcore
import publication_immutability as pi
import runtime_dependency
import sign_publication as sp

# ---------------------------------------------------------------------------
# fixed official identity (trusted constants; branch names are workflow config)
# ---------------------------------------------------------------------------

OFFICIAL_HUB_REPO = "JiangNanGenius/floe-skill-hub"
OFFICIAL_APP_REPO = "JiangNanGenius/floe-agent"
OFFICIAL_HUB_URLS = (
    "https://github.com/JiangNanGenius/floe-skill-hub.git",
    "https://github.com/JiangNanGenius/floe-skill-hub",
    "git@github.com:JiangNanGenius/floe-skill-hub.git",
)
OFFICIAL_APP_URLS = (
    "https://github.com/JiangNanGenius/floe-agent.git",
    "https://github.com/JiangNanGenius/floe-agent",
    "git@github.com:JiangNanGenius/floe-agent.git",
)
FETCH_ORIGIN_URL = OFFICIAL_HUB_URLS[0]  # literal fetch target, never a caller value
LIVE_MAIN_LOCAL_REF = "refs/floe/auto/live-main"
CANDIDATE_LOCAL_REF = "refs/floe/auto/candidate"
BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")

# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------


class TransportError(hubcore.HubError):
    """Fail-closed transport refusal; never contains secret material."""


def _hold(message):
    raise TransportError("HOLD: " + message)


# ---------------------------------------------------------------------------
# 1. strict canonical bounded candidate-request parser
# ---------------------------------------------------------------------------

REQUEST_SCHEMA_VERSION = 1
REQUEST_MODES = ("reviews", "catalog")
REQUEST_CORE_FIELDS = ("schemaVersion", "mode", "sourceCommit",
                       "basePublication", "policySha256")
REQUEST_FIELDS = frozenset(REQUEST_CORE_FIELDS + ("requestId",))
MAX_REQUEST_FILE_BYTES = 16_384


def request_core(doc):
    """The canonical identity core of a request (everything but requestId)."""
    return {field: doc[field] for field in REQUEST_CORE_FIELDS}


def derive_request_id(doc):
    """requestId := SHA-256 over the canonical bytes of the other fields."""
    return hubcore.sha256_hex(hubcore.encoded(request_core(doc)))


def build_request(mode, source_commit, base_publication, policy_sha256):
    """Canonical request bytes plus the validated document (single builder)."""
    doc = {"schemaVersion": REQUEST_SCHEMA_VERSION, "mode": mode,
           "sourceCommit": source_commit, "basePublication": base_publication,
           "policySha256": policy_sha256}
    doc["requestId"] = derive_request_id(doc)
    return hubcore.encoded(doc), doc


def _validate_request_doc(doc):
    if not isinstance(doc, dict):
        raise TransportError("request must be a JSON object")
    unknown = set(doc) - REQUEST_FIELDS
    if unknown:
        # also refuses caller-selected identity/path overrides such as
        # repository, branch, ref, out or tooling pins — none is request input
        raise TransportError(f"request has unknown fields: {sorted(unknown)}")
    missing = REQUEST_FIELDS - set(doc)
    if missing:
        raise TransportError(f"request is missing fields: {sorted(missing)}")
    if isinstance(doc["schemaVersion"], bool) or doc["schemaVersion"] != REQUEST_SCHEMA_VERSION:
        raise TransportError(f"request schemaVersion must be {REQUEST_SCHEMA_VERSION}")
    if doc["mode"] not in REQUEST_MODES:
        raise TransportError(f"request mode must be one of {list(REQUEST_MODES)}")
    hubcore.require_commit(doc["sourceCommit"], "request sourceCommit")
    hubcore.require_commit(doc["basePublication"], "request basePublication")
    hubcore.require_hex64(doc["policySha256"], "request policySha256")
    hubcore.require_hex64(doc["requestId"], "request requestId")
    derived = derive_request_id(doc)
    if doc["requestId"] != derived:
        raise TransportError("request requestId does not equal the canonical "
                             "derivation over its other fields")
    return doc


def _as_transport(action):
    """Run a pure check, normalizing any bare HubError to TransportError."""
    try:
        return action()
    except TransportError:
        raise
    except hubcore.HubError as error:
        raise TransportError(str(error)) from None


def validate_request(doc):
    return _as_transport(lambda: _validate_request_doc(doc))


def parse_request_bytes(raw):
    """Strict canonical bounded parser: canonical bytes or refuse."""
    if not isinstance(raw, bytes):
        raise TransportError("request input must be bytes")
    if len(raw) > MAX_REQUEST_FILE_BYTES:
        raise TransportError(f"request exceeds {MAX_REQUEST_FILE_BYTES} bytes")
    try:
        doc = json.loads(raw)
    except ValueError:
        raise TransportError("request is not valid JSON") from None
    validate_request(doc)
    if hubcore.encoded(doc) != raw:
        raise TransportError("request bytes are not the canonical encoding "
                             "(no pretty-printing, no trailing whitespace)")
    return doc


def parse_request_file(path):
    path = pathlib.Path(path)
    if path.is_symlink() or not path.is_file():
        raise TransportError("request must be a real regular file")
    if path.stat().st_size > MAX_REQUEST_FILE_BYTES:
        raise TransportError(f"request file exceeds {MAX_REQUEST_FILE_BYTES} bytes")
    return parse_request_bytes(path.read_bytes())


def request_policy_matches(request, policy_bytes):
    """True only when the bytes digest exactly equals the request binding."""
    return hubcore.sha256_hex(policy_bytes) == request["policySha256"]


def is_official_url(url, repo):
    expected = OFFICIAL_HUB_URLS if repo == OFFICIAL_HUB_REPO else OFFICIAL_APP_URLS
    if repo not in (OFFICIAL_HUB_REPO, OFFICIAL_APP_REPO):
        raise TransportError(f"not a fixed official repository: {repo!r}")
    return url in expected


def _require_branch_config(name, field):
    if (not isinstance(name, str) or not BRANCH_NAME_RE.fullmatch(name)
            or ".." in name.split("/") or name.startswith("-")):
        raise TransportError(f"{field} must be a plain trusted-config branch name")
    return name


# ---------------------------------------------------------------------------
# controlled fixed-origin Git reads (bytes-preserving, argv only)
# ---------------------------------------------------------------------------

COMMIT_40 = re.compile(r"[0-9a-f]{40}")


def _require_commit(value, field):
    if not isinstance(value, str) or not COMMIT_40.fullmatch(value):
        raise TransportError(f"{field} must be a 40-hex lowercase commit")
    return value


def _git_bytes(root, args, purpose):
    """One controlled argv-only read through the trusted A git reader."""
    try:
        return pi._git_output(pathlib.Path(root), args, purpose)
    except hubcore.HubError as error:
        raise TransportError(str(error)) from None


def _git_text(root, args, purpose):
    try:
        return sp._git(pathlib.Path(root), args, purpose)
    except sp.SigningError as error:
        raise TransportError(str(error)) from None


def fetch_official_refspec(branch):
    """Exact forced fetch argv against the literal fixed origin URL."""
    _require_branch_config(branch, "branch")
    return ["fetch", "--no-tags", FETCH_ORIGIN_URL,
            f"+refs/heads/{branch}:refs/floe/auto/live-main"]


def fetch_official_main(root):
    """Fetch live official main from the fixed origin into a private ref."""
    _git_bytes(root, fetch_official_refspec("main"), "fixed-origin live main fetch")
    return resolve_live_main(root)


def resolve_live_main(root):
    head = _git_text(root, ["rev-parse", "--verify", LIVE_MAIN_LOCAL_REF + "^{commit}"],
                     "live main resolution")
    return _require_commit(head, "live main commit")


def fetch_official_branch(root, branch):
    _git_bytes(root, ["fetch", "--no-tags", FETCH_ORIGIN_URL,
                      f"+refs/heads/{branch}:{CANDIDATE_LOCAL_REF}"],
               "fixed-origin candidate branch fetch")
    head = _git_text(root, ["rev-parse", "--verify", CANDIDATE_LOCAL_REF + "^{commit}"],
                     "candidate branch resolution")
    return _require_commit(head, "candidate branch commit")


def tree_of(root, commit, label):
    """{rel: (mode, blobOid)} over the committed tree (never the disk)."""
    _require_commit(commit, f"{label} commit")
    listing = _git_bytes(root, ["ls-tree", "-r", "-z", commit], f"{label} tracked tree")
    tree = {}
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, _, rel = record.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3:
            _hold(f"{label}: unparsable tree entry")
        mode, objtype, oid = (f.decode("ascii") for f in fields)
        try:
            path = rel.decode("utf-8", "strict")
        except UnicodeDecodeError:
            _hold(f"{label}: tree path is not UTF-8: {rel!r}")
        if objtype != "blob":
            _hold(f"{label}: non-blob tree entry ({objtype}): {path}")
        if mode not in ("100644", "100755"):
            _hold(f"{label}: unsupported tree mode {mode}: {path}")
        if not COMMIT_40.fullmatch(oid):
            _hold(f"{label}: bad blob id for {path}")
        tree[path] = (mode, oid)
    return tree


def read_blob(root, commit, rel, label):
    """Read one committed blob; a missing committed file returns None."""
    try:
        return pi._git_output(pathlib.Path(root), ["show", f"{commit}:{rel}"],
                              f"{label} blob {rel}")
    except hubcore.HubError:
        return None


def is_descendant(root, ancestor, descendant):
    try:
        _git_bytes(root, ["merge-base", "--is-ancestor", ancestor, descendant],
                   "anchor ancestry")
        return True
    except TransportError:
        return False


# ---------------------------------------------------------------------------
# 2. minimal publication-DATA allowlist (established from the actual tree)
# ---------------------------------------------------------------------------

DATA_EXACT_PATHS = frozenset({
    "catalog/publication-ledger.json",   # ledger continuity rules below
    "catalog/skills.json",               # registry content rules below
    "catalog.json", "catalog.sig",       # official iOS feed pair
    "android/catalog.json", "android/catalog.sig",
    "docs/UPSTREAM-PINS.json",           # upstream pin data (JSON-parsed)
})
DATA_DIR_PREFIXES = (
    "sources/", "frozen/", "reviews/", "packages/",
    "android/packages/", "android/reviews/",
)
SHOWCASE_PREFIX = "showcase/"
SHOWCASE_SCRIPTS_PREFIX = "showcase/scripts/"
SHOWCASE_DATA_EXTENSIONS = frozenset({
    ".json", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".ico", ".bmp",
})
MAX_CHANGED_LIST = 64
MAX_DATA_FILE_BYTES = hubcore.MAX_TOTAL_BYTES


def is_refresh_data_path(rel):
    """Only ordinary publication DATA may differ between A and Y."""
    if rel in DATA_EXACT_PATHS:
        return True
    if rel.startswith(DATA_DIR_PREFIXES):
        return True
    if rel.startswith(SHOWCASE_PREFIX) and not rel.startswith(SHOWCASE_SCRIPTS_PREFIX):
        leaf = rel.rsplit("/", 1)[-1]
        ext = ("." + leaf.rsplit(".", 1)[-1]).lower() if "." in leaf else ""
        return ext in SHOWCASE_DATA_EXTENSIONS
    return False


def _checked_json(raw, rel, limit=MAX_DATA_FILE_BYTES):
    if len(raw) > limit:
        _hold(f"data path {rel!r} exceeds {limit} bytes")
    try:
        return json.loads(raw)
    except ValueError:
        _hold(f"data path {rel!r} changed but is not valid JSON")


JSON_CONTENT_DATA_PATHS = ("catalog/skills.json", "docs/UPSTREAM-PINS.json")

# The ONLY zone whose ordinary files a data-only refresh may lose: a
# legitimately deleted upstream source file. Licence/notice material is never
# deletable here (the separate policy-updater lane owns licence changes), and
# nothing outside sources/** is ever deletable (ledger, feeds, registry,
# packages, reviews, frozen, android data, showcase evidence, docs pins,
# engines, schema, scripts, workflows, keys, policy and tests included).
DELETABLE_SOURCE_PREFIX = "sources/"
LICENSE_COMPONENT_RE = re.compile(r"licen[cs]|notice|copying|eula", re.IGNORECASE)

# Review history zone frozen by the mode-aware candidate check.
REVIEW_HISTORY_PREFIXES = ("reviews/", "android/reviews/")

# The engine-freeze default is the STRICTEST mode: nothing about the
# immutable-history policy can be relaxed except through the canonical,
# requestId-bound mode of a validated request.
ENGINE_FREEZE_MODES = REQUEST_MODES
STRICT_ENGINE_FREEZE_MODE = "catalog"


def is_deletable_source_data_path(rel):
    """True only for ordinary mutable sources/** data (never licence paths)."""
    if not rel.startswith(DELETABLE_SOURCE_PREFIX):
        return False
    return not any(LICENSE_COMPONENT_RE.search(part) for part in rel.split("/"))


def _verify_changed_data_content(root, live_commit, modified, added):
    """Content guards for the permitted DATA changes that carry contracts."""
    for rel in sorted(set(modified) | set(added)):
        needs_json = rel in JSON_CONTENT_DATA_PATHS or (
            rel.startswith(SHOWCASE_PREFIX) and rel.endswith(".json"))
        if not needs_json:
            continue
        raw = read_blob(root, live_commit, rel, "live")
        if raw is None:
            _hold(f"live blob for data path {rel!r} vanished")
        if rel == "catalog/skills.json":
            try:
                hubcore.validate_registry(json.loads(raw))
            except (ValueError, hubcore.HubError) as error:
                _hold(f"catalog/skills.json refresh is not a valid registry: {error}")
        else:
            _checked_json(raw, rel)
    # feed pair content integrity is verified at the live pin itself below
    # (load_trustworthy_baseline), and ledger content by the continuity rules.


# ---------------------------------------------------------------------------
# ledger continuity (anchor rows: byte-identical ordered prefix, superset)
# ---------------------------------------------------------------------------

def _ledger_document(raw, label):
    try:
        doc = json.loads(raw)
    except ValueError:
        _hold(f"{label}: ledger is not valid JSON")
    if hubcore.encoded(doc) != raw:
        _hold(f"{label}: ledger bytes are not canonical")
    if not isinstance(doc, dict) or set(doc) != {
            "schemaVersion", "publisher", "description", "publications"}:
        _hold(f"{label}: ledger root keys mismatch")
    if doc["schemaVersion"] != pi.LEDGER_SCHEMA_VERSION:
        _hold(f"{label}: ledger schemaVersion must be {pi.LEDGER_SCHEMA_VERSION}")
    if doc["publisher"] != "JiangNanGenius":
        _hold(f"{label}: ledger publisher mismatch")
    if not isinstance(doc["publications"], list):
        _hold(f"{label}: ledger publications must be a list")
    return doc


def verify_ledger_continuity(anchor_raw, live_raw):
    """Return (anchor_rows, live_rows) enforcing prefix + no duplicates."""
    anchor_doc = _ledger_document(anchor_raw, "anchor") if anchor_raw is not None else None
    live_doc = _ledger_document(live_raw, "live")
    anchor_rows = anchor_doc["publications"] if anchor_doc else []
    live_rows = live_doc["publications"]
    if len(live_rows) < len(anchor_rows):
        _hold("live ledger is shorter than the anchor ledger: anchor rows were "
              "deleted — the publication ledger is append-only")
    for index, (a_row, l_row) in enumerate(zip(anchor_rows, live_rows)):
        if hubcore.encoded(a_row) != hubcore.encoded(l_row):
            _hold(f"live ledger row {index} is not byte/structurally identical to "
                  "the anchor row: historical rows can never be rewritten or reordered")
    seen = set()
    for index, row in enumerate(live_rows):
        canonical = hubcore.encoded(row)
        if canonical in seen:
            _hold(f"live ledger row {index} duplicates an earlier publication row")
        seen.add(canonical)
    return anchor_rows, live_rows


def _require_anchor_on_live_mainline(root, anchor_commit, live_commit):
    """The anchor must sit on live main's first-parent mainline itself."""
    mainline = _git_text(root, ["rev-list", "--first-parent", live_commit],
                         "live main first-parent history").split()
    if anchor_commit not in mainline:
        _hold(f"anchor {anchor_commit[:10]} is not on the first-parent mainline "
              f"history of live main {live_commit[:10]}: cumulative ledger "
              "continuity can only be proven over a fully verifiable mainline "
              "(the complete fetched history is required; history that cannot "
              "be verified is never trusted)")


def _ledger_state_blob(root, commit):
    """Committed ledger bytes at a mainline commit; None only if truly absent.

    A pathspec ls-tree distinguishes "the ledger is not in this committed
    tree" from "the object cannot be read" — an unreadable object fails closed
    instead of silently masquerading as an absent ledger.
    """
    listing = _git_bytes(root, ["ls-tree", commit, "--", pi.LEDGER_REL],
                         "mainline ledger presence")
    if not listing.strip():
        return None
    return _as_transport(lambda: pi._git_output(
        pathlib.Path(root), ["show", f"{commit}:{pi.LEDGER_REL}"],
        "mainline ledger blob"))


def verify_ledger_mainline_history(root, anchor_commit, live_commit):
    """Prove EVERY effective main-first-parent ledger transition A→Y.

    Walks the first-parent commits between the anchor and live main that
    changed the ledger blob (git rev-list --first-parent with the ledger path
    filter over the locally fetched complete history) and enforces, for every
    consecutive effective mainline ledger state, that the earlier rows remain
    a byte/structurally identical ORDERED prefix — so a row added after A and
    dropped mid-chain can never be hidden by a later append that restores the
    anchor prefix and covers the current offers. Each distinct ledger state is
    strictly canonical-parsed, every state's rows are cryptographically
    re-verified at their immutable pins through the trusted-A
    publication_immutability verify_ledger reader (intermediate states; the
    final live state is re-verified with coverage by the baseline builder),
    and every observed publication pin must stay reachable as an ancestor of
    live main so the published historical bytes stay verifiable evidence.
    Returns (transition_count, distinct_states_verified).
    """
    transitions = _git_text(
        root, ["rev-list", "--first-parent", "--reverse",
               f"{anchor_commit}..{live_commit}", "--", pi.LEDGER_REL],
        "mainline ledger transition commits").split()
    states = [anchor_commit] + [c for c in transitions if c != anchor_commit]
    if states[-1] != live_commit:
        states.append(live_commit)
    prev_raw = None
    reachable = set()
    verified_digests = set()
    verified_states = 0
    temp_dir = None
    try:
        for position, commit in enumerate(states):
            is_final = commit == live_commit
            label = ("anchor" if position == 0 else
                     "live main" if is_final else f"mainline commit {commit[:10]}")
            raw = _ledger_state_blob(root, commit)
            if raw is None:
                if prev_raw is not None:
                    _hold(f"the cumulative publication ledger was deleted at {label} "
                          "on live main's first-parent history: ledger history "
                          "that disappears mid-chain is never trusted")
                continue
            if prev_raw is not None and raw != prev_raw:
                _, rows = verify_ledger_continuity(prev_raw, raw)
            else:
                rows = _ledger_document(raw, f"{label} ledger")["publications"]
            digest = hubcore.sha256_hex(raw)
            if digest not in verified_digests:
                verified_digests.add(digest)
                for row in rows:
                    pin = row.get("publication") if isinstance(row, dict) else None
                    if (isinstance(pin, str) and COMMIT_40.fullmatch(pin)
                            and pin not in reachable):
                        reachable.add(pin)
                        if not is_descendant(root, pin, live_commit):
                            _hold(f"{label} ledger row pins publication "
                                  f"{pin[:10]}, which is not reachable as an "
                                  "ancestor of live main: published historical "
                                  "bytes must stay reachable evidence")
                if not is_final:
                    if temp_dir is None:
                        temp_dir = tempfile.TemporaryDirectory(
                            prefix="floe-hub-ledger-")
                    state_file = pathlib.Path(temp_dir.name) / "ledger.json"
                    state_file.write_bytes(raw)
                    _as_transport(lambda: pi.verify_ledger(
                        state_file, pathlib.Path(root)))
                verified_states += 1
            prev_raw = raw
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
    return len(transitions), verified_states


# ---------------------------------------------------------------------------
# history refresh core + CLI resolution
# ---------------------------------------------------------------------------

def verify_history_refresh(root, anchor_commit, live_commit):
    """Pure core over the trusted A checkout's object store (fetched live).

    Returns a JSON-safe verdict; raises TransportError (HOLD) unless Y is on
    and descends from the reviewed anchor along the first-parent mainline,
    every path outside the DATA allowlist is (mode, blob)-identical to A, no
    tracked path outside the ordinary sources/** data zone was removed, every
    mainline ledger transition between A and Y extends the previous ledger as
    a byte-identical ordered prefix with each state verified cryptographically
    at its immutable reachable pins, and the live ledger covers the live
    current offers.
    """
    _require_commit(anchor_commit, "anchor commit")
    _require_commit(live_commit, "live commit")
    root_path = pathlib.Path(root)
    if not is_descendant(root_path, anchor_commit, live_commit):
        _hold(f"live official main {live_commit[:10]} does not descend from the "
              f"reviewed anchor {anchor_commit[:10]} (force-pushed or rewritten "
              "history is never silently trusted)")
    _require_anchor_on_live_mainline(root_path, anchor_commit, live_commit)
    tree_a = tree_of(root_path, anchor_commit, "anchor")
    tree_y = tree_of(root_path, live_commit, "live")

    removed = sorted(set(tree_a) - set(tree_y))
    forbidden_removals = [rel for rel in removed
                          if not is_deletable_source_data_path(rel)]
    if forbidden_removals:
        _hold("tracked file(s) removed on live main outside the only permitted "
              "deletion zone (ordinary mutable sources/** data; licence/notice "
              "material, the ledger, feeds, packages, reviews, frozen, engines "
              "and every trust/tooling path are never deletable): "
              f"{forbidden_removals[:MAX_CHANGED_LIST]}")
    removed_data = [rel for rel in removed if is_deletable_source_data_path(rel)]
    added = sorted(set(tree_y) - set(tree_a))
    # full (mode, oid) comparison: executable-bit drift on a trust path is
    # code drift even when the blob object id is unchanged
    modified = sorted(rel for rel in set(tree_a) & set(tree_y)
                      if tree_a[rel] != tree_y[rel])
    trusted_drift = [rel for rel in added + modified if not is_refresh_data_path(rel)]
    if trusted_drift:
        _hold("code/trust drift is denied by default: non-DATA path(s) added or "
              "changed (bytes or mode) between anchor and live main: "
              f"{trusted_drift[:MAX_CHANGED_LIST]}")

    _verify_changed_data_content(root_path, live_commit, modified, added)

    anchor_ledger_raw = read_blob(root_path, anchor_commit, pi.LEDGER_REL, "anchor")
    live_ledger_raw = read_blob(root_path, live_commit, pi.LEDGER_REL, "live")
    if anchor_ledger_raw is not None and live_ledger_raw is None:
        _hold("the cumulative publication ledger disappeared on live main")
    anchor_rows, live_rows = verify_ledger_continuity(anchor_ledger_raw, live_ledger_raw)

    # Cumulative HISTORY, not just the endpoints: every effective mainline
    # ledger transition between A and Y must extend the previous mainline
    # ledger as an ordered prefix, each distinct state must parse strictly
    # and verify cryptographically at its immutable pins, and every observed
    # publication pin must stay reachable on live main.
    transitions, ledger_states_verified = verify_ledger_mainline_history(
        root_path, anchor_commit, live_commit)

    # Independent cryptographic re-verification, run ONLY through trusted-A
    # publication_immutability against committed objects (no candidate import):
    #   * current feed pairs at the live pin (signature + canonical + schema),
    #   * every live ledger row anchored to its immutable publication pin,
    #   * coverage of the live current offers and merge-conflict refusal.
    provenance = {}
    merged = {}
    temp_dir = None
    try:
        ledger_path = None
        if live_ledger_raw is not None:
            temp_dir = tempfile.TemporaryDirectory(prefix="floe-hub-refresh-")
            ledger_file = pathlib.Path(temp_dir.name) / "publication-ledger.json"
            ledger_file.write_bytes(live_ledger_raw)
            ledger_path = ledger_file
        merged = pi.build_validated_baseline(root_path, ledger_path, live_commit,
                                             provenance)
    except hubcore.HubError as error:
        _hold(f"live publication ledger/baseline refused: {error}")
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    return {
        "status": "refresh-ok",
        "anchorCommit": anchor_commit,
        "liveCommit": live_commit,
        "addedDataPaths": added[:MAX_CHANGED_LIST],
        "modifiedDataPaths": modified[:MAX_CHANGED_LIST],
        "removedDataPaths": removed_data[:MAX_CHANGED_LIST],
        "addedTruncated": len(added) > MAX_CHANGED_LIST,
        "modifiedTruncated": len(modified) > MAX_CHANGED_LIST,
        "removedTruncated": len(removed_data) > MAX_CHANGED_LIST,
        "anchorLedgerRows": len(anchor_rows),
        "liveLedgerRows": len(live_rows),
        "appendedLedgerRows": len(live_rows) - len(anchor_rows),
        "ledgerTransitions": transitions,
        "ledgerStatesVerified": ledger_states_verified,
        "baselineHistoricalFacts": len(merged),
        "baselineProvenance": provenance,
    }


def run_history_refresh(tooling_root, anchor_commit):
    """CLI path: verify the anchor snapshot, resolve official main, refresh.

    The live pin is never caller-selected: it is fetched and resolved here
    from the literal fixed origin URL only. The anchor snapshot is proven
    exact and clean by the EXISTING sign_publication.verify_exact_snapshot
    helper before any live object is read. The integration fetch must carry
    the COMPLETE history (a default full-depth fetch already does; a shallow
    clone is refused fail-closed by the mainline continuity check, never
    silently trusted).
    """
    tooling_root = pathlib.Path(tooling_root)
    _require_commit(anchor_commit, "anchor commit")
    try:
        anchor_info = sp.verify_exact_snapshot("trusted-anchor", tooling_root,
                                              anchor_commit)
    except sp.SigningError as error:
        _hold(str(error))
    live_commit = fetch_official_main(tooling_root)
    verdict = verify_history_refresh(tooling_root, anchor_commit, live_commit)
    verdict["anchorTree"] = anchor_info["tree"]
    return verdict


def verify_request_history_base(request, history_verdict):
    """Bind the request CAS base to the independently fetched live main.

    The correct compare-and-swap base B is the CURRENT live official main Y —
    the ledger commit of the last publication or any reviewed code/data
    commit made after it (today that is e.g. 3e145cd, which is not any ledger
    publication pin). The historical feed-publication pins carried by the
    ledger's baselineProvenance are NOT CAS bases: a request bound to one of
    them is stale even when that pin was genuinely published and signed, so
    this refuses it instead of letting a publication overwrite anything landed
    after the request was made. There is no caller-selected baseline: the
    live pin must come from a successful run_history_refresh/
    verify_history_refresh verdict resolved from the fixed origin. Returns
    the bound live commit.
    """
    validate_request(dict(request))
    if not isinstance(history_verdict, dict) \
            or history_verdict.get("status") != "refresh-ok":
        _hold("request base binding requires a successful history-refresh verdict")
    live_commit = history_verdict.get("liveCommit")
    _require_commit(live_commit, "live main commit")
    if request["basePublication"] != live_commit:
        _hold(f"request basePublication {request['basePublication'][:10]} does "
              f"not equal the independently fetched live main {live_commit[:10]}: "
              "only the current live CAS base is a valid basePublication (a "
              "historical publication pin is stale even when it was genuinely "
              "published and signed)")
    return live_commit


# ---------------------------------------------------------------------------
# X-vs-B engine-authority freeze (candidate data against the request base)
# ---------------------------------------------------------------------------

PACKAGE_ARCHIVE_RE = re.compile(r"^(?:android/)?packages/.+\.zip$")
ENGINES_PREFIX = "engines/"


def _zip_embedded_descriptor(blob, rel):
    """Return the exact embedded engine-dependency.json bytes or None."""
    if len(blob) > MAX_DATA_FILE_BYTES:
        _hold(f"candidate archive {rel!r} exceeds {MAX_DATA_FILE_BYTES} bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for info in archive.infolist():
                if info.filename != runtime_dependency.EMBEDDED_DESCRIPTOR_REL:
                    continue
                if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    _hold(f"candidate archive {rel!r}: embedded descriptor is not a file")
                if info.file_size > MAX_DATA_FILE_BYTES:
                    _hold(f"candidate archive {rel!r}: embedded descriptor oversized")
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    _hold(f"candidate archive {rel!r}: embedded descriptor size mismatch")
                return payload
    except zipfile.BadZipFile:
        _hold(f"candidate archive {rel!r} is not a readable ZIP")
    return None


def verify_candidate_engine_freeze(root, base_commit, candidate_commit,
                                   mode=STRICT_ENGINE_FREEZE_MODE):
    """Freeze engine/package authority: candidate X must not move B history.

    build_catalog reads the frozen descriptor and package bytes from the
    candidate data checkout X, so a separately-run App-side candidate verifier
    MUST call this before trusting any signing over X:
      * every engines/** blob at B must equal the same (mode, blob) at X, and
        X may not add engines/** paths (genuine new engine qualification can
        only arrive through a reviewed anchor/base update, never silently);
      * every published package archive at B must stay PRESENT at X byte- and
        mode-identically — archive deletion is refused in every mode; package
        history is always frozen;
      * every X archive that embeds references/engine-dependency.json must
        embed exactly the B frozen descriptor bytes (new archives/versions are
        allowed; wholesale same-version archive replacement is not);
      * the immutable review history is mode-aware: catalog mode (also the
        strict default) retains every base review record and sidecar exactly,
        while reviews mode permits the expected minimal candidate pruning of
        historical review pairs but never any mutation of a retained base
        record (new pairs and new versions stay allowed in every mode).

    The mode is only authoritative as the canonical requestId-bound mode of a
    validated request — use verify_request_candidate_engine_freeze; there is
    no flag that weakens engine or package freezing, and unknown modes fail
    closed.
    """
    root_path = pathlib.Path(root)
    _require_commit(base_commit, "base publication")
    _require_commit(candidate_commit, "candidate source")
    if mode not in ENGINE_FREEZE_MODES:
        _hold(f"engine-freeze mode must be one of {list(ENGINE_FREEZE_MODES)}; "
              "there is no bypass mode")
    tree_b = tree_of(root_path, base_commit, "base")
    tree_x = tree_of(root_path, candidate_commit, "candidate")

    engines_b = {rel: entry for rel, entry in tree_b.items()
                 if rel.startswith(ENGINES_PREFIX)}
    engines_x = {rel: entry for rel, entry in tree_x.items()
                 if rel.startswith(ENGINES_PREFIX)}
    for rel in sorted(engines_b):
        if rel not in engines_x:
            _hold(f"engine authority drift: {rel} exists at base but not candidate")
        if engines_x[rel] != engines_b[rel]:
            _hold(f"engine authority drift: {rel} differs between base and "
                  "candidate (bytes or mode)")
    for rel in sorted(set(engines_x) - set(engines_b)):
        _hold(f"engine authority drift: candidate adds engines path {rel} without "
              "a reviewed new engine qualification")

    archives_b = {rel: entry for rel, entry in tree_b.items()
                  if PACKAGE_ARCHIVE_RE.fullmatch(rel)}
    archives_x = {rel: entry for rel, entry in tree_x.items()
                  if PACKAGE_ARCHIVE_RE.fullmatch(rel)}
    for rel in sorted(archives_b):
        entry = archives_x.get(rel)
        if entry is None:
            _hold(f"immutable published archive deleted at candidate: {rel} — "
                  "package history is always frozen in every mode")
        if entry != archives_b[rel]:
            _hold(f"immutable published archive changed at candidate (bytes or "
                  f"mode): {rel}")

    frozen_raw = None
    rel_frozen = runtime_dependency.FROZEN_DESCRIPTOR_REL
    if rel_frozen in engines_b:
        frozen_raw = read_blob(root_path, base_commit, rel_frozen, "base")
        if frozen_raw is None:
            _hold("base frozen engine descriptor is unreadable")

    inspected = len(archives_x)
    embedded_count = 0
    for rel in sorted(archives_x):
        if rel in archives_b:
            continue  # byte- and mode-identical to base: descriptor equals B
        blob = read_blob(root_path, candidate_commit, rel, "candidate")
        if blob is None:
            _hold(f"candidate archive unreadable: {rel}")
        embedded = _zip_embedded_descriptor(blob, rel)
        if embedded is not None:
            embedded_count += 1
            if frozen_raw is None:
                _hold(f"candidate archive {rel} embeds an engine descriptor but the "
                      "base carries no frozen descriptor to equal")
            if embedded != frozen_raw:
                _hold(f"candidate archive {rel} embeds a references/engine-dependency"
                      ".json that is not the base frozen descriptor bytes")

    review_b = {rel: entry for rel, entry in tree_b.items()
                if rel.startswith(REVIEW_HISTORY_PREFIXES)}
    review_x = {rel: entry for rel, entry in tree_x.items()
                if rel.startswith(REVIEW_HISTORY_PREFIXES)}
    for rel in sorted(review_b):
        entry = review_x.get(rel)
        if entry is None:
            if mode == "catalog":
                _hold(f"immutable review history: {rel} exists at base but was "
                      "pruned from the catalog candidate — catalog mode retains "
                      "every published review record and sidecar exactly")
            continue  # reviews mode: the expected minimal candidate pruning
        if entry != review_b[rel]:
            _hold(f"immutable review history: {rel} differs between base and "
                  "candidate (bytes or mode); retained records can never mutate")
    return {"status": "engine-freeze-ok", "baseCommit": base_commit,
            "candidateCommit": candidate_commit, "mode": mode,
            "enginePathsCompared": len(engines_b),
            "archivesInspected": inspected,
            "archivesAtBase": len(archives_b),
            "embeddedDescriptorsChecked": embedded_count,
            "reviewPathsAtBase": len(review_b),
            "reviewPathsRetained": len(set(review_b) & set(review_x))}


def verify_request_candidate_engine_freeze(root, request, candidate_commit):
    """Bind the request's canonical identity into the engine-authority freeze.

    The candidate commit must equal the request sourceCommit (a stale or
    moving candidate ref is refused), the freeze base is the request
    basePublication, and the immutable-history mode is exactly the canonical
    requestId-bound mode of the validated request. No caller-selected flag
    weakens any of these bindings.
    """
    validate_request(dict(request))
    _require_commit(candidate_commit, "candidate commit")
    if candidate_commit != request["sourceCommit"]:
        _hold("candidate commit does not equal the request sourceCommit "
              "(stale or moving ref)")
    return verify_candidate_engine_freeze(root, request["basePublication"],
                                          candidate_commit, request["mode"])


# ---------------------------------------------------------------------------
# 3. signed relay metadata validation/extraction
# ---------------------------------------------------------------------------

RELAY_RECEIPT_REL = sp.RECEIPT_REL
RELAY_RECEIPT_SIG_REL = sp.RECEIPT_SIG_REL
FEED_MEMBER_CHANNELS = {
    "catalog.json": "ios", "catalog.sig": "ios",
    "android/catalog.json": "android", "android/catalog.sig": "android",
}
FEED_PATHS = {"ios": ("catalog.json", "catalog.sig"),
              "android": ("android/catalog.json", "android/catalog.sig")}
REVIEW_RECORD_RE = re.compile(
    r"^reviews/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)/"
    r"((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))\.review\.json$")
MAX_RELAY_MEMBERS = 4096
MAX_RELAY_MEMBER_BYTES = hubcore.MAX_FILE_BYTES
MAX_RELAY_TOTAL_BYTES = 16_777_216
MAX_MEMBER_PATH_BYTES = hubcore.MAX_PATH_BYTES

FORBIDDEN_RELAY_HINTS = ("packages/", ".zip", ".dylib", ".so", ".wasm",
                         ".framework", "scripts/", ".github/", "engines/")


def _relay_path_safe(rel):
    if (not isinstance(rel, str) or not rel or rel.startswith("/")
            or "\\" in rel or "\0" in rel
            or any(part in ("", ".", "..") or part.startswith(".")
                   for part in rel.split("/"))):
        raise TransportError(f"unsafe relay path: {rel!r}")
    if len(rel.encode("utf-8")) > MAX_MEMBER_PATH_BYTES:
        raise TransportError(f"relay path exceeds {MAX_MEMBER_PATH_BYTES} bytes: {rel!r}")
    return rel


def relay_member_class(rel):
    """Membership is an exact allow-form, never a prefix guess."""
    if rel == RELAY_RECEIPT_REL:
        return "receipt"
    if rel == RELAY_RECEIPT_SIG_REL:
        return "receipt-sig"
    if rel in FEED_MEMBER_CHANNELS:
        return "feed" if rel.endswith(".json") else "feed-sig"
    if REVIEW_RECORD_RE.fullmatch(rel):
        return "review"
    if rel.endswith(".sig") and REVIEW_RECORD_RE.fullmatch(rel[:-len(".sig")]):
        return "review-sig"
    return None


def parse_relay_archive_bytes(archive_bytes):
    """Bounded safe extraction of the relay container into {rel: bytes}."""
    if not isinstance(archive_bytes, bytes):
        raise TransportError("relay container must be bytes")
    if len(archive_bytes) > MAX_RELAY_TOTAL_BYTES:
        raise TransportError(f"relay container exceeds {MAX_RELAY_TOTAL_BYTES} bytes")
    members = {}
    folded = {}
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as container:
            infos = container.infolist()
            if len(infos) > MAX_RELAY_MEMBERS:
                raise TransportError(f"relay exceeds {MAX_RELAY_MEMBERS} members")
            for info in infos:
                rel = _relay_path_safe(info.filename)
                if info.is_dir():
                    raise TransportError(f"relay container must carry files only: {rel!r}")
                filetype = (info.external_attr >> 16) & 0o170000
                if filetype == 0o120000:
                    raise TransportError(f"relay symlinks are refused: {rel!r}")
                if filetype not in (0o100000, 0):
                    raise TransportError(f"relay entry file type refused: {rel!r}")
                if rel in members:
                    raise TransportError(f"relay duplicate member: {rel!r}")
                folded_key = rel.casefold()
                if folded_key in folded:
                    raise TransportError(f"relay duplicate after folding: {rel!r}")
                folded[folded_key] = True
                if relay_member_class(rel) is None:
                    hint = next((h for h in FORBIDDEN_RELAY_HINTS
                                 if h in rel or rel.endswith(h)), None)
                    reason = f" ({hint.strip('/')}-class content is never relay material)" \
                        if hint else ""
                    raise TransportError(f"relay member is not signed metadata: {rel!r}"
                                         + reason)
                if info.file_size > MAX_RELAY_MEMBER_BYTES:
                    raise TransportError(f"relay member exceeds "
                                         f"{MAX_RELAY_MEMBER_BYTES} bytes: {rel!r}")
                payload = container.read(info)
                if len(payload) != info.file_size:
                    raise TransportError(f"relay member size mismatch: {rel!r}")
                total += len(payload)
                if total > MAX_RELAY_TOTAL_BYTES:
                    raise TransportError("relay exceeds the total size bound")
                members[rel] = payload
    except zipfile.BadZipFile:
        raise TransportError("relay container is not a readable ZIP") from None
    return members


def _load_relay_receipt(members, public_keys):
    receipt_bytes = members.get(RELAY_RECEIPT_REL)
    receipt_sig = members.get(RELAY_RECEIPT_SIG_REL)
    if receipt_bytes is None or receipt_sig is None:
        raise TransportError("relay must carry signing-receipt.json and its "
                             "authenticated .sig envelope")
    try:
        receipt = json.loads(receipt_bytes)
    except ValueError:
        raise TransportError("relay receipt is not valid JSON") from None
    if not isinstance(receipt, dict):
        raise TransportError("relay receipt must be an object")
    if hubcore.encoded(receipt) != receipt_bytes:
        raise TransportError("relay receipt bytes are not the canonical encoding")
    for field in ("schemaVersion", "mode", "sourceCommit", "keyID", "outputs"):
        if field not in receipt:
            raise TransportError(f"relay receipt is missing {field}")
    if isinstance(receipt["schemaVersion"], bool) or receipt["schemaVersion"] != 1:
        raise TransportError("relay receipt schemaVersion must be 1")
    if receipt.get("hubRepository", OFFICIAL_HUB_REPO) != OFFICIAL_HUB_REPO:
        raise TransportError("relay receipt hubRepository is not the official Hub")
    if receipt["keyID"] != hubcore.PRODUCTION_KEY_ID:
        raise TransportError("relay receipt keyID must be the official identity")
    try:
        verified = hubcore.verify_envelope(receipt_bytes, receipt_sig, public_keys)
    except hubcore.HubError as error:
        raise TransportError(f"relay receipt signature failed: {error}") from None
    if verified != hubcore.PRODUCTION_KEY_ID or verified == hubcore.FIXTURE_KEY_ID:
        raise TransportError("relay receipt was not signed by the official identity")
    return receipt


def _receipt_outputs(receipt):
    outputs = receipt["outputs"]
    if not isinstance(outputs, list) or not outputs:
        raise TransportError("relay receipt outputs must be a non-empty list")
    by_path = {}
    for entry in outputs:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
            raise TransportError("relay receipt output entries need exactly "
                                 "path/sha256/size")
        rel = _relay_path_safe(entry["path"])
        hubcore.require_hex64(entry["sha256"], f"relay output sha256 for {rel}")
        # outputs may reference archived package bytes that stay at the
        # candidate source; only the relay-class members are size-further
        # bounded at extraction, here the absolute transport bound applies.
        if isinstance(entry["size"], bool) or not isinstance(entry["size"], int) \
                or not 0 < entry["size"] <= hubcore.MAX_TOTAL_BYTES:
            raise TransportError(f"relay output size invalid for {rel}")
        if rel in by_path:
            raise TransportError(f"relay receipt outputs duplicate path {rel}")
        by_path[rel] = entry
    return by_path


def _verify_feed_pair(members, outputs, channel, request, public_keys,
                      package_references):
    feed_rel, sig_rel = FEED_PATHS[channel]
    feed_bytes = members[feed_rel]
    sig_bytes = members[sig_rel]
    for rel, data in ((feed_rel, feed_bytes), (sig_rel, sig_bytes)):
        bound = outputs.get(rel)
        if bound is None:
            raise TransportError(f"relay feed member {rel!r} is not bound by the "
                                 "signed receipt")
        if hubcore.sha256_hex(data) != bound["sha256"] or len(data) != bound["size"]:
            raise TransportError(f"relay feed member {rel!r} does not match the "
                                 "receipt-bound hash/size")
    try:
        key_id = hubcore.verify_envelope(feed_bytes, sig_bytes, public_keys)
    except hubcore.HubError as error:
        raise TransportError(f"{channel} relay feed signature failed: {error}") from None
    if key_id != hubcore.PRODUCTION_KEY_ID:
        raise TransportError(f"{channel} relay feed signed by unexpected identity "
                             f"{key_id!r}")
    try:
        feed = json.loads(feed_bytes)
    except ValueError:
        raise TransportError(f"{channel} relay feed is not valid JSON") from None
    if hubcore.encoded(feed) != feed_bytes:
        raise TransportError(f"{channel} relay feed bytes are not canonical")
    try:
        hubcore.validate_catalog(feed, channel=channel, allow_fixture=False)
    except hubcore.HubError as error:
        raise TransportError(f"{channel} relay feed failed validation: {error}") from None
    if feed["sourceCommit"] != request["sourceCommit"]:
        raise TransportError(f"{channel} relay feed sourceCommit "
                             f"{feed['sourceCommit']!r} does not equal the request "
                             f"{request['sourceCommit']}")
    for entry in feed["entries"]:
        if entry["package"] is not None:
            package = entry["package"]
            package_references.append({
                "channel": channel, "id": entry["id"], "version": entry["version"],
                "path": package["path"], "sha256": package["sha256"],
                "size": package["size"], "contentDigest": package["contentDigest"],
            })
        review = entry["review"]
        if review is None:
            continue
        record_bytes = members.get(review["path"])
        sig_pair = members.get(review["path"] + ".sig")
        if record_bytes is None or sig_pair is None:
            raise TransportError(f"{entry['id']}: feed-bound review bytes are not "
                                 "relayed (a publication relay is standalone)")
        if hubcore.sha256_hex(record_bytes) != review["sha256"]:
            raise TransportError(f"{entry['id']}: relayed review bytes drifted from "
                                 "the signed feed binding")
        if review["keyID"] != hubcore.PRODUCTION_KEY_ID:
            raise TransportError(f"{entry['id']}: review keyID is not the official "
                                 "identity")
        try:
            verified_review_id = hubcore.verify_envelope(record_bytes, sig_pair,
                                                         public_keys)
        except hubcore.HubError as error:
            raise TransportError(f"{entry['id']}: review signature failed: "
                                 f"{error}") from None
        if verified_review_id != review["keyID"]:
            raise TransportError(f"{entry['id']}: review signature identity drifted")
        try:
            record = json.loads(record_bytes)
            if hubcore.encoded(record) != record_bytes:
                raise hubcore.HubError("review record is not canonical")
            hubcore.validate_review(record, entry)
        except hubcore.HubError as error:
            raise TransportError(f"{entry['id']}: relayed review record invalid: "
                                 f"{error}") from None
        if record["decision"] != "approve":
            raise TransportError(f"{entry['id']}: only approved reviews are relayed")
    return feed


def validate_signed_relay(members, request, public_keys):
    """Verify a fully extracted metadata map against the request and trust.

    Returns the validated metadata (bytes map + parsed feeds/receipt + the
    immutable package references that stay at the candidate source) for a
    downstream pure data write. Nothing is executed, signed or pushed here.
    """
    validate_request(dict(request))
    if not public_keys or hubcore.FIXTURE_KEY_ID in public_keys:
        raise TransportError("relay verification requires real public trust "
                             "material without the fixture identity")
    checked = {}
    for rel in members:
        _relay_path_safe(rel)
        if relay_member_class(rel) is None:
            raise TransportError(f"relay member is not signed metadata: {rel!r}")
        if len(members[rel]) > MAX_RELAY_MEMBER_BYTES:
            raise TransportError(f"relay member exceeds "
                                 f"{MAX_RELAY_MEMBER_BYTES} bytes: {rel!r}")
        checked[rel] = members[rel]
    receipt = _load_relay_receipt(checked, public_keys)
    if receipt["mode"] != request["mode"]:
        raise TransportError(f"relay receipt mode {receipt['mode']!r} does not "
                             f"equal the request mode {request['mode']!r}")
    if receipt["sourceCommit"] != request["sourceCommit"]:
        raise TransportError("relay receipt sourceCommit does not equal the "
                             "request sourceCommit")
    outputs = _as_transport(lambda: _receipt_outputs(receipt))

    # every relayed file except the self-authenticated receipt pair must be
    # bound by the signed receipt outputs list with the exact hash and size
    for rel, data in checked.items():
        if rel in (RELAY_RECEIPT_REL, RELAY_RECEIPT_SIG_REL):
            continue
        bound = outputs.get(rel)
        if bound is None:
            raise TransportError(f"relay field is not bound by the signed receipt: "
                                 f"{rel!r}")
        if hubcore.sha256_hex(data) != bound["sha256"] or len(data) != bound["size"]:
            raise TransportError(f"relay file {rel!r} is not exactly hash/size bound "
                                 "by the signed receipt")

    review_paths = sorted(rel for rel in outputs if relay_member_class(rel) == "review")
    for rel in review_paths:
        if rel + ".sig" not in outputs:
            raise TransportError(f"receipt lists {rel!r} without its signed envelope")
    expected = {RELAY_RECEIPT_REL, RELAY_RECEIPT_SIG_REL}
    if request["mode"] == "catalog":
        for rel in (*FEED_PATHS["ios"], *FEED_PATHS["android"]):
            if rel not in outputs:
                raise TransportError(f"catalog relay receipt does not bind {rel!r}")
            expected.add(rel)
    else:
        for rel in (*FEED_PATHS["ios"], *FEED_PATHS["android"]):
            if rel in outputs or rel in checked:
                raise TransportError("a reviews-mode relay must never carry feeds")
        if not review_paths:
            raise TransportError("reviews-mode relay carries no signed review pairs")
        reviews_meta = receipt.get("reviews")
        if not isinstance(reviews_meta, list) or len(reviews_meta) != len(review_paths):
            raise TransportError("reviews-mode receipt must enumerate exactly the "
                                 "relayed signed review records")
        for item in reviews_meta:
            if not isinstance(item, dict) or set(item) < {"id", "version",
                                                          "reviewPath", "recordSha256",
                                                          "signatureSha256", "keyID"}:
                raise TransportError("reviews-mode receipt entry shape invalid")
            rec = checked.get(item["reviewPath"])
            sig = checked.get(item["reviewPath"] + ".sig")
            if rec is None or sig is None:
                raise TransportError(f"reviews-mode receipt lists {item['reviewPath']!r} "
                                     "but the relay does not carry it")
            if hubcore.sha256_hex(rec) != item["recordSha256"] \
                    or hubcore.sha256_hex(sig) != item["signatureSha256"] \
                    or item["keyID"] != hubcore.PRODUCTION_KEY_ID:
                raise TransportError(f"reviews-mode receipt binding for "
                                     f"{item['reviewPath']!r} does not match bytes")
            try:
                record = json.loads(rec)
                if hubcore.encoded(record) != rec:
                    raise hubcore.HubError("record not canonical")
                hubcore.validate_review(record)
            except hubcore.HubError as error:
                raise TransportError(f"relayed review {item['reviewPath']!r} "
                                     f"invalid: {error}") from None
            if record["decision"] != "approve" or record["id"] != item["id"] \
                    or record["version"] != item["version"]:
                raise TransportError(f"relayed review {item['reviewPath']!r} does not "
                                     "match the approved receipt identity")
            try:
                verified = hubcore.verify_envelope(rec, sig, public_keys)
            except hubcore.HubError as error:
                raise TransportError(f"relayed review {item['reviewPath']!r} "
                                     f"signature failed: {error}") from None
            if verified != hubcore.PRODUCTION_KEY_ID:
                raise TransportError(f"relayed review {item['reviewPath']!r} identity "
                                     "drifted")
    for rel in review_paths:
        expected.add(rel)
        expected.add(rel + ".sig")

    missing = sorted(expected - set(checked))
    extra = sorted(set(checked) - expected)
    if missing or extra:
        raise TransportError(f"relay membership drifted (missing={missing[:8]}, "
                             f"unexpected={extra[:8]})")

    if request["mode"] == "catalog":
        # every relayed signed review pair — not only the feed-bound ones —
        # must stand on its own official signature and approved record
        for rel in review_paths:
            record_bytes = checked[rel]
            try:
                record = json.loads(record_bytes)
                if hubcore.encoded(record) != record_bytes:
                    raise hubcore.HubError("record is not canonical")
                hubcore.validate_review(record)
            except hubcore.HubError as error:
                raise TransportError(f"relayed review {rel!r} invalid: {error}") from None
            if record["decision"] != "approve":
                raise TransportError(f"relayed review {rel!r} is not an approval")
            match = REVIEW_RECORD_RE.fullmatch(rel)
            if record["id"] != match.group(1) or record["version"] != match.group(2):
                raise TransportError(f"relayed review {rel!r} identity does not "
                                     "match its path")
            try:
                verified = hubcore.verify_envelope(record_bytes,
                                                   checked[rel + ".sig"], public_keys)
            except hubcore.HubError as error:
                raise TransportError(f"relayed review {rel!r} signature failed: "
                                     f"{error}") from None
            if verified != hubcore.PRODUCTION_KEY_ID:
                raise TransportError(f"relayed review {rel!r} identity drifted")

    feeds = {}
    package_references = []
    if request["mode"] == "catalog":
        for channel in ("ios", "android"):
            feeds[channel] = _verify_feed_pair(checked, outputs, channel, request,
                                               public_keys, package_references)
    return {
        "status": "relay-ok",
        "requestId": request["requestId"],
        "mode": request["mode"],
        "sourceCommit": request["sourceCommit"],
        "basePublication": request["basePublication"],
        "policySha256": request["policySha256"],
        "files": {rel: checked[rel] for rel in sorted(checked)},
        "feeds": feeds,
        "packageReferences": package_references,
        "reviewRecordCount": len(review_paths),
        "receipt": receipt,
    }


def validate_relay_archive(archive_bytes, request, public_keys):
    return validate_signed_relay(parse_relay_archive_bytes(archive_bytes),
                                 request, public_keys)


# ---------------------------------------------------------------------------
# CLI (read/verify only; never writes into a snapshot, never signs or pushes)
# ---------------------------------------------------------------------------


class _ArgumentSandbox(argparse.ArgumentParser):
    """Parser that keeps the CLI surface free of redirect/bypass options."""

    def add_argument(self, *args, **kwargs):
        for name in args:
            lowered = str(name).lower()
            if any(banned in lowered for banned in
                   ("replace", "redirect", "no-verify", "insecure", "allow-")):
                raise ValueError("mutable redirect/bypass options are never offered")
        return super().add_argument(*args, **kwargs)


def build_parser():
    parser = _ArgumentSandbox(
        prog="automatic_transport",
        description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-request", help="validate one canonical candidate request file")
    p.add_argument("--request", required=True)

    p = sub.add_parser("verify-history", help="anchor A -> live main Y trusted refresh")
    p.add_argument("--tooling", default=None, help="trusted anchor checkout root")
    p.add_argument("--anchor-commit", required=True,
                   help="40-hex reviewed bootstrap anchor (trusted config)")

    p = sub.add_parser("verify-relay", help="validate a signed metadata relay container")
    p.add_argument("--request", required=True)
    p.add_argument("--container", required=True)
    p.add_argument("--tooling", default=None, help="trusted anchor checkout for trust")
    p.add_argument("--anchor-commit", required=True,
                   help="40-hex reviewed anchor the trust root must sit on")

    p = sub.add_parser("verify-engine-freeze",
                       help="candidate X vs request base B engine authority freeze")
    p.add_argument("--tooling", default=None)
    p.add_argument("--anchor-commit", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--candidate-branch", required=True,
                   help="trusted-config candidate request branch name")
    return parser


MODULE_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _tooling_root(value):
    root = pathlib.Path(value) if value else MODULE_ROOT
    if root.is_symlink() or not root.is_dir():
        _hold("--tooling must be a real directory")
    return root


def _load_anchor_trust(root):
    try:
        import build_catalog
    except ImportError as error:  # the trusted scripts directory owns it
        _hold(f"trusted tooling is incomplete: {error}")
    try:
        return sp.load_official_trust(build_catalog, hubcore, root)
    except sp.SigningError as error:
        _hold(str(error))


def _print_json(payload):
    print(hubcore.pretty(payload).decode("utf-8"))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse-request":
        request = parse_request_file(args.request)
        _print_json(request)
        return 0

    if args.command == "verify-history":
        verdict = run_history_refresh(_tooling_root(args.tooling), args.anchor_commit)
        _print_json(verdict)
        return 0

    if args.command == "verify-relay":
        request = parse_request_file(args.request)
        container_path = pathlib.Path(args.container)
        if container_path.is_symlink() or not container_path.is_file():
            _hold("--container must be a real regular file")
        if container_path.stat().st_size > MAX_RELAY_TOTAL_BYTES:
            _hold("relay container file exceeds the transport size bound")
        # trust material may only be read from the proven-clean anchor snapshot
        root = _tooling_root(args.tooling)
        _require_commit(args.anchor_commit, "anchor commit")
        try:
            sp.verify_exact_snapshot("trusted-anchor", root, args.anchor_commit)
        except sp.SigningError as error:
            _hold(str(error))
        trust = _load_anchor_trust(root)
        verdict = validate_relay_archive(container_path.read_bytes(), request, trust)
        summary = {k: v for k, v in verdict.items() if k != "files"}
        summary["relayedFiles"] = {rel: hubcore.sha256_hex(data)
                                   for rel, data in verdict["files"].items()}
        _print_json(summary)
        return 0

    if args.command == "verify-engine-freeze":
        root = _tooling_root(args.tooling)
        request = parse_request_file(args.request)
        # Anchor first, then resolve live official main from the fixed origin:
        # the correct CAS base is the independently fetched LIVE MAIN commit
        # (the last publication's ledger commit or any reviewed code/data
        # commit after it). The historical feed-publication pins carried by
        # the ledger are NOT CAS bases — a stale basePublication is refused
        # even when that pin was genuinely published and signed.
        live = run_history_refresh(root, args.anchor_commit)
        verify_request_history_base(request, live)
        candidate = fetch_official_branch(root, args.candidate_branch)
        # the wrapper rebinds candidate == request sourceCommit, binds the
        # freeze base to request basePublication and binds the immutable
        # review-history policy to the canonical requestId-bound request mode
        verdict = verify_request_candidate_engine_freeze(root, request, candidate)
        verdict["historyRefresh"] = {"anchorCommit": live["anchorCommit"],
                                     "liveCommit": live["liveCommit"]}
        _print_json(verdict)
        return 0

    _hold(f"unknown command {args.command!r}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except TransportError as error:
        print("automatic-transport: refusing: " + str(error), file=sys.stderr)
        sys.exit(2)
