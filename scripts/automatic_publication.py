#!/usr/bin/env python3
"""Cloud-only end-to-end orchestration for automatic Skill Hub publication.

Concrete GitHub-Actions pipeline glue between the settled stage0 tracker CLI
(scripts/upstream_updates.py, consumed strictly through its committed
staging-manifest/apply contract), the fixed trusted transport primitives
(scripts/automatic_transport.py) and the UNCHANGED signing/publishing core
(sign_publication.py, build_catalog.py, hubcore.py, publication_immutability.py).
It implements the settled AFLT-RELAY-CAS flow defined by this repository's
frozen publication contract (public docs under docs/, e.g. the integration
contract and upstream tracking guides):

  Hub grouped scan (6h) -> upstream_updates check/plan/stage -> automatic
  publication verifies every staged candidate INDEPENDENTLY from bytes
  (deterministic archive rebuild, registry/pin/lineage deltas, tier
  recomputation, full prior-proof re-verification for scripted docs-only
  reuse), stages the minimal UNSIGNED tree S (only the verified new review
  records; every other reviews/** path pruned inside S, never rewritten),
  runs the unchanged gates, commits S on an auto/candidate-* ref, and writes
  the six-field canonical request + candidate manifest + bounded rolling
  state (held records included) to the Hub control branch -> the App
  scheduled orchestrator bootstraps ONLY from the literal reviewed trusted
  anchor, verifies the trusted-tooling history refresh, resolves the CURRENT
  live main B independently (basePublication must equal live main, never a
  ledger-pin membership), re-verifies the committed candidate from the public
  Hub objects and the engine freeze, then the existing signer signs reviews
  at S (later the catalog at X) in the App repository where the private key
  exists and nowhere else -> the metadata-only relay on the dedicated App
  data branch (top-level prefix signing-relay/requests/<requestId>/) carries
  ONLY signature envelopes plus the authenticated receipt -> the Hub
  publisher reconstructs the full bounded metadata (JSON bodies from the
  immutable candidate commits, feeds from its own deterministic rebuild),
  re-verifies every official signature and every receipt-bound digest
  (including package and staged engine bytes that never leave the Hub),
  rebuilds X from the ORIGINAL B preserving ALL historical review pairs
  byte-identically, appends the cumulative ledger after Y, and advances main
  exactly once B -> H through the GitHub GraphQL updateRefs exact CAS
  (beforeOid re-resolved live, afterOid H, force=false, GraphQL errors
  checked even at HTTP 200, on the live-proved updateRefs(input) exact-CAS
  shape), then verifies the actual public bytes directly.

Hard rules enforced here (fail closed; HOLD is loud committed data, never
silence):

  * Nothing candidate-supplied is trusted. Tiers, review records, digests,
    fingerprints, registry deltas, pins and lineage are RECOMPUTED from
    committed bytes with the unchanged frozen helpers; the tracker's proposed
    review bytes are accepted only after independent verification.
  * No new permission/dependency/runtime/engine/unknown-file change ever
    auto-promotes. Guide-only records must be static-content-reviewed with no
    execution claim; scripted docs-only records may reuse the prior signed
    guest proof ONLY under byte-identical recomputed execution AND
    instruction-code fingerprints, a ledger-bound envelope-valid prior
    qualified review, unchanged grants and unchanged minimumAppVersion — and
    the record's bilingual notes must cite the complete prior binding. No
    execution is ever invented; emulation never counts as guest-verified.
  * This module never reads a signing key, never signs, and never pushes.
    Remote ref writes belong to the narrowly scoped workflow jobs. The only
    network egress is the FIXED GitHub GraphQL endpoint for the exact CAS
    (token strictly from an environment variable, never argv/logs/files) and
    tokenless fixed-host raw reads of the two public official repositories.
    Everything runs on GitHub-hosted runners and is resumable and idempotent
    from the committed control/relay state; no Mac, App, Codex or local
    daemon is ever required.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.dont_write_bytecode = True  # keep trusted checkouts byte-clean

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import automatic_transport as at  # noqa: E402
import build_catalog  # noqa: E402
import hubcore  # noqa: E402
import catalog_views as cv  # noqa: E402
import publication_immutability as pi  # noqa: E402
import upstream_pins  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]

PUBLICATION_NAME = "floe-skill-hub-auto-publication"
SCHEMA_VERSION = 1

POLICY_REL = "catalog/upstream-update-policy.json"
REGISTRY_REL = "catalog/skills.json"
PINS_REL = "docs/UPSTREAM-PINS.json"
LINKS_REL = "showcase/links.json"
LEDGER_REL = pi.LEDGER_REL
IOS_FEED_REL = "catalog.json"
ANDROID_FEED_REL = "android/catalog.json"
FEED_PATHS = at.FEED_PATHS
PACKAGE_PREFIXES = ("packages/", "android/packages/")

CONTROL_REQUEST_FILE = "request.json"
CONTROL_MANIFEST_FILE = "candidate-manifest.json"
CONTROL_STATE_FILE = "state.json"
CONTROL_CHANGES_FILE = "control-changes.json"
CONTROL_ARCHIVE_PREFIX = "requests/"
RELAY_PREFIX = "signing-relay/"                 # TOP-LEVEL App data prefix
RELAY_REQUEST_DIR = RELAY_PREFIX + "requests/"
RELAY_STATE_FILE = RELAY_PREFIX + "state.json"
RELAY_MANIFEST_FILE = "relay-manifest.json"
CANDIDATE_REF_PREFIX = "auto/candidate-"
CONTROL_BRANCH = "auto-state"
RELAY_BRANCH = "skill-hub-signing-relay"

GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
RAW_HOST = "https://raw.githubusercontent.com"
CAS_OWNER, CAS_REPO_NAME, CAS_REF = "JiangNanGenius", "floe-skill-hub", "refs/heads/main"
CAS_MUTATION_ID = "floe-skill-hub-auto-cas"

ENV_TOKEN_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
MACHINE_ID_RE = re.compile(
    r"^floe-skill-hub-auto-curation(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,31})?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_MANIFEST_BYTES = 4_194_304
MAX_STATE_BYTES = 262_144
MAX_PAYLOAD_FILE_BYTES = hubcore.MAX_TOTAL_BYTES
PROCESSED_IDS_CAP = 32
HOLD_RECORDS_CAP = 24
GAP_RECORDS_CAP = 24
REQUEST_HISTORY_KEEP = 20

# Trust-critical paths no automatic commit may ever touch (DECISION denylist
# plus the B9 pinned automatic-update policy blob).
DENIED_PREFIXES = ("scripts/", "schema/", ".github/", "engines/", "tests/",
                   "system/",)
DENIED_EXACT = frozenset({"public-key.json", "AGENTS.md", "LICENSE",
                          POLICY_REL, "catalog/curation.json"})

# A candidate (S or X) may only change ordinary publication DATA.
CANDIDATE_ALLOW_DIRS = ("sources/", "packages/", "android/packages/", "reviews/")
CANDIDATE_ALLOW_EXACT = frozenset({REGISTRY_REL, PINS_REL, LINKS_REL})
# The final B..H main diff must stay inside the publication allowlist.
PUBLISH_ALLOW_DIRS = ("packages/", "android/packages/", "reviews/", "sources/",
                      "showcase/", "docs/provenance/", "docs/qualification/")
PUBLISH_ALLOW_EXACT = frozenset({
    REGISTRY_REL, LEDGER_REL, IOS_FEED_REL, "catalog.sig", ANDROID_FEED_REL,
    "android/catalog.sig", "catalog-full.json", "catalog-full.sig",
    "android/catalog-full.json", "android/catalog-full.sig", PINS_REL, "catalog/curation.json",
    "README.md", "README.zh-CN.md",
})

_PROSE_ROOT_MD = re.compile(r"^SKILL\.md$")
_PROSE_REF_MD = re.compile(r"^references/[^/]+\.md$")
_PROSE_LICENSES = re.compile(r"^references/licenses/.+$")
_INSTRUCTION_EXCLUDES = frozenset({
    "references/PROVENANCE.md", "references/ADAPTATION-NOTES.md",
    "references/MODIFICATIONS.md",
})

REVIEW_HISTORY_PREFIXES_TUPLE = ("reviews/", "android/reviews/")
LIVE_REGISTRY_EXPECT_COUNTS = None  # append-only production cohort; fixtures pass exact counts
RECEIPT_REL = at.RELAY_RECEIPT_REL
RECEIPT_SIG_REL = at.RELAY_RECEIPT_SIG_REL


class PublicationError(hubcore.HubError):
    """Fail-closed orchestration refusal. Messages never contain secrets."""


def _hold(message):
    raise PublicationError("HOLD: " + message)


def _as_publication(action):
    try:
        return action()
    except PublicationError:
        raise
    except (hubcore.HubError, at.TransportError) as error:
        raise PublicationError(str(error)) from None


def _git_out(root, args, field):
    return pi._git_output(pathlib.Path(root), args, field)


# ---------------------------------------------------------------------------
# bounded pure helpers
# ---------------------------------------------------------------------------


def policy_sha256(policy_bytes):
    """request.policySha256 := sha256 of the exact committed policy blob.

    The policy sits on a denied publication path, so its bytes can only change
    through a reviewed base/anchor advance; the request bound to the live base
    B (whose trust-critical OIDs run_history_refresh proves equal to the
    anchor) plus automatic_transport.request_policy_matches over the read-back
    blob is the exact enforced-policy binding the contract requires.
    """
    return hubcore.sha256_hex(policy_bytes)


def build_request(mode, source_commit, base_publication, policy_bytes):
    """Six-field canonical request through the settled transport builder."""
    return at.build_request(mode, source_commit, base_publication,
                            policy_sha256(policy_bytes))


def _canonical_json(raw, field, limit=MAX_PAYLOAD_FILE_BYTES):
    if len(raw) > limit:
        _hold(f"{field} exceeds {limit} bytes")
    try:
        return json.loads(raw)
    except ValueError:
        _hold(f"{field} is not valid JSON")


def write_payload_file(out_dir, rel, data, mode=None):
    """Write one payload member under out_dir at the repo-relative path."""
    if (not rel or rel.startswith("/") or "\\" in rel or "\0" in rel
            or any(part in ("", ".", "..") for part in rel.split("/"))):
        _hold(f"unsafe payload path: {rel!r}")
    if len(data) > MAX_PAYLOAD_FILE_BYTES:
        _hold(f"payload file exceeds {MAX_PAYLOAD_FILE_BYTES} bytes: {rel}")
    target = pathlib.Path(out_dir) / rel
    walk = pathlib.Path(out_dir)
    parts = [part for part in rel.split("/")[:-1]]
    for part in parts:
        walk = walk / part
        if walk.is_symlink():
            _hold(f"refusing symlinked output path: {walk}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_file():
        _hold(f"refusing non-file output path: {target}")
    target.write_bytes(data)
    if mode is not None:
        os.chmod(target, mode)
    return target


def commit_tree_oid(root, commit, path):
    """Subtree/blob OID for <commit>:<path> (None when absent)."""
    try:
        out = _git_out(root, ["rev-parse", "--verify", "--quiet",
                              f"{commit}:{path}"], f"tree oid {path}")
    except hubcore.HubError:
        return None
    return out.decode("ascii", "strict").strip() or None


def _require_commit40(value, field):
    if not isinstance(value, str) or not at.COMMIT_40.fullmatch(value):
        _hold(f"{field} must be a 40-hex lowercase commit")
    return value


def tree_at(root, commit, label):
    return _as_publication(lambda: at.tree_of(root, commit, label))


def blob_at(root, commit, rel, label):
    return at.read_blob(root, commit, rel, label)


def tree_diff(tree_a, tree_b):
    added = sorted(set(tree_b) - set(tree_a))
    removed = sorted(set(tree_a) - set(tree_b))
    modified = sorted(rel for rel in set(tree_a) & set(tree_b)
                      if tree_a[rel] != tree_b[rel])
    return added, removed, modified


# ---------------------------------------------------------------------------
# execution / instruction-code fingerprints (independently recomputed, B3)
# ---------------------------------------------------------------------------


def _is_prose_allowlisted(rel):
    return bool(_PROSE_ROOT_MD.fullmatch(rel) or _PROSE_REF_MD.fullmatch(rel)
                or _PROSE_LICENSES.match(rel))


def _manifest_without_version(manifest):
    return {key: value for key, value in manifest.items() if key != "version"}


def _archive_files(archive_bytes, field):
    if len(archive_bytes) > MAX_PAYLOAD_FILE_BYTES:
        _hold(f"{field}: archive exceeds {MAX_PAYLOAD_FILE_BYTES} bytes")
    return _as_publication(lambda: hubcore.check_archive_bytes(archive_bytes))


def execution_fingerprint(files):
    """Canonical fingerprint over every execution-relevant member byte.

    Sorted 'path blobSha256' lines for every member outside the narrow prose
    allowlist (and outside floe.json), plus one final line binding floe.json
    with only its version removed: stable across the mechanical version bump,
    changed by ANY script, asset, engine-data, dependency, grant or manifest
    byte.
    """
    lines = []
    for rel in sorted(files):
        if rel == "floe.json":
            continue
        if _is_prose_allowlisted(rel):
            continue
        lines.append(f"{rel} {hubcore.sha256_hex(files[rel])}")
    if "floe.json" not in files:
        _hold("package has no floe.json")
    manifest = hubcore.parse_manifest(files["floe.json"])
    lines.append("floe.json " + hubcore.sha256_hex(
        hubcore.encoded(_manifest_without_version(manifest))))
    return hubcore.sha256_hex("\n".join(lines).encode("utf-8"))


_FENCE_RE = re.compile(r"^```(.*?)\s*$")


def _length_prefixed(kind, data):
    return kind + str(len(data)).encode("ascii") + b":" + data


def _inline_units(line):
    """Length-prefixed inline code spans (backtick runs) extracted in order."""
    parts = []
    rest = line
    while True:
        start = rest.find("`")
        if start < 0:
            break
        run_len = 0
        while rest[start + run_len:start + run_len + 1] == "`":
            run_len += 1
        close = rest.find("`" * run_len, start + run_len)
        if close < 0:
            break
        parts.append(_length_prefixed(b"I", rest[start + run_len:close].encode("utf-8")))
        rest = rest[close + run_len:]
    return parts


def _code_units(markdown_bytes):
    """Fenced blocks (info string + body) + inline spans, in document order."""
    text = markdown_bytes.decode("utf-8")
    units = []
    in_fence = False
    fence_info = ""
    fence_body = []
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if match and not in_fence:
            in_fence = True
            fence_info = match.group(1)
            fence_body = []
            continue
        if in_fence and match and not match.group(1).strip():
            body = "\n".join(fence_body).encode("utf-8")
            info = fence_info.encode("utf-8")
            units.append(_length_prefixed(b"F", info + b"\x00" + body))
            in_fence = False
            fence_info = ""
            continue
        if in_fence:
            fence_body.append(line)
            continue
        units.extend(_inline_units(line))
    if in_fence:
        _hold("unterminated fenced code block in instruction markdown")
    return units


def _is_instruction_markdown(rel):
    if rel in _INSTRUCTION_EXCLUDES or rel.startswith("references/licenses/"):
        return False
    if rel.startswith("references/engine-data/"):
        return False
    return rel == "SKILL.md" or (rel.startswith("references/")
                                 and rel.endswith(".md"))


def instruction_code_fingerprint(files):
    """sha256 over per-file extracted code units of instruction markdown."""
    lines = []
    for rel in sorted(files):
        if not _is_instruction_markdown(rel):
            continue
        try:
            units = _code_units(files[rel])
        except UnicodeDecodeError:
            _hold(f"instruction markdown {rel} is not UTF-8")
        lines.append(f"{rel} {hubcore.sha256_hex(b''.join(units))}")
    return hubcore.sha256_hex("\n".join(lines).encode("utf-8"))


# ---------------------------------------------------------------------------
# effective upstream pins (current global contract; the per-entry
# skillOverrides shape the pin lane is adding is honored when present)
# ---------------------------------------------------------------------------


def effective_pins(pins_raw, registry_doc):
    """Parse + validate the pins document and resolve every entry's exact pin.

    Uses the frozen upstream_pins contract (per-entry skillOverrides honored;
    no raw-global-pin fallback for mixed overrides) and returns the resolved
    {entry_id: commit} map plus the parsed document.
    """
    doc = _as_publication(lambda: upstream_pins.parse_pins_bytes(pins_raw))
    resolved = {}
    for row in registry_doc["skills"]:
        upstream = row.get("upstream")
        if not upstream:
            continue
        repo_short = upstream["repository"].removeprefix("https://github.com/")
        commit, _is_override = _as_publication(
            lambda: upstream_pins.effective_pin_for_entry(doc, row["id"], repo_short))
        resolved[row["id"]] = commit
    return doc, resolved


# ---------------------------------------------------------------------------
# tracker stage-root loader (settled staging-manifest contract, digest-checked)
# ---------------------------------------------------------------------------


def _find_stage_manifest(stage_root):
    for name in ("staging-manifest.json", "staged-manifest.json",
                 "stage-manifest.json"):
        path = pathlib.Path(stage_root) / name
        if path.is_file():
            return path.read_bytes(), name
    _hold("tracker stage root carries no staging-manifest.json")


def _apply_entries(apply_doc):
    """Normalize the ordered exact write list from apply/manifest.json.

    Presence, not truthiness, marks the ordered list: the producer always
    emits the canonical ``writes`` key, and a legitimate held-only stage
    (every intended write byte-identical to base, zero eligible candidates)
    carries an EMPTY list there. Only a manifest with no ordered list at
    all, or a non-list under the first present canonical/alias key, is
    malformed; an empty list must not be re-badged as a missing one.
    """
    if isinstance(apply_doc, dict):
        raw = None
        for key in ("writes", "files", "entries"):
            if key in apply_doc:
                raw = apply_doc[key]
                break
    else:
        raw = apply_doc
    if not isinstance(raw, list):
        _hold("apply/manifest.json carries no ordered write list")
    writes = []
    for item in raw:
        digest = None
        if isinstance(item, str):
            rel = item
        elif isinstance(item, dict):
            rel = item.get("path") or item.get("rel")
            digest = item.get("sha256") or item.get("digest")
        else:
            _hold("apply manifest entry has an unusable shape")
        if not isinstance(rel, str) or rel.startswith("/") \
                or any(p in ("", ".", "..") for p in rel.split("/")):
            _hold(f"apply manifest unsafe path: {rel!r}")
        writes.append((rel, digest))
    return writes


def load_stage(stage_root):
    stage_root = pathlib.Path(stage_root)
    raw, name = _find_stage_manifest(stage_root)
    manifest = _canonical_json(raw, name, MAX_MANIFEST_BYTES)
    facts = manifest.get("candidateFacts")
    if not isinstance(facts, dict):
        _hold("staging manifest has no candidateFacts block")
    apply_path = stage_root / "apply" / "manifest.json"
    if not apply_path.is_file():
        _hold("staging manifest has no apply/manifest.json")
    apply_doc = _canonical_json(apply_path.read_bytes(), "apply/manifest.json",
                               MAX_MANIFEST_BYTES)
    apply_entries = _apply_entries(apply_doc)
    apply_deletions = []
    for rel in (apply_doc.get("deletions") or [] if isinstance(apply_doc, dict)
                else []):
        if not isinstance(rel, str) or rel.startswith("/") \
                or any(p in ("", ".", "..") for p in rel.split("/")):
            _hold(f"apply manifest deletion unsafe path: {rel!r}")
        if not rel.startswith("sources/"):
            _hold(f"apply manifest deletes a non-DATA path: {rel}")
        apply_deletions.append(rel)
    files = {}
    for rel, digest in apply_entries:
        source = stage_root / "apply" / "files" / rel
        if source.is_symlink() or not source.is_file():
            _hold(f"apply manifest references a missing regular file: {rel}")
        data = source.read_bytes()
        if digest is not None and hubcore.sha256_hex(data) != digest:
            _hold(f"apply file {rel} drifted from its manifest digest")
        files[rel] = data
    candidates = {}
    candidates_root = stage_root / "candidates"
    if candidates_root.is_dir():
        for id_dir in sorted(candidates_root.iterdir()):
            if not id_dir.is_dir():
                continue
            for version_dir in sorted(id_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                candidate_json = version_dir / "candidate.json"
                if not candidate_json.is_file():
                    _hold(f"candidate {id_dir.name}@{version_dir.name} lacks candidate.json")
                doc = _canonical_json(candidate_json.read_bytes(),
                                      "candidate.json", MAX_MANIFEST_BYTES)
                tree_dir = version_dir / "tree"
                if not tree_dir.is_dir():
                    _hold(f"candidate {id_dir.name}@{version_dir.name} lacks tree")
                tree = {}
                for path in sorted(tree_dir.rglob("*")):
                    if path.is_symlink():
                        _hold("symlink inside a staged candidate tree is forbidden")
                    if not path.is_file():
                        continue
                    tree[path.relative_to(tree_dir).as_posix()] = path.read_bytes()
                package_path = version_dir / "package.zip"
                package = package_path.read_bytes() if package_path.is_file() else None
                candidates[(id_dir.name, version_dir.name)] = {
                    "candidate": doc, "tree": tree, "package": package}
    held = {}
    held_root = stage_root / "held"
    if held_root.is_dir():
        for path in sorted(held_root.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            held[path.stem] = _canonical_json(path.read_bytes(), "held record",
                                              MAX_MANIFEST_BYTES)
    deferred = []
    deferred_root = stage_root / "deferred"
    if deferred_root.is_dir():
        deferred = sorted(p.name for p in deferred_root.iterdir() if p.is_dir())
    return {"manifest": manifest, "facts": facts, "applyFiles": files,
            "applyOrder": [rel for rel, _ in apply_entries],
            "applyDeletions": apply_deletions,
            "candidates": candidates, "held": held, "deferred": deferred}


def _stage_candidate_facts(stage):
    """(changedIds, bumpedVersions, pinAdvances) from the staged manifest."""
    facts = stage["facts"]
    changed = facts.get("changedSkillIds")
    bumped = facts.get("bumpedVersions")
    pins = facts.get("pinAdvances")
    if not isinstance(changed, list):
        _hold("candidateFacts.changedSkillIds must be a list")
    if not isinstance(bumped, dict) or not isinstance(pins, dict):
        _hold("candidateFacts needs bumpedVersions and per-entry pinAdvances blocks")
    if changed and set(changed) != set(bumped):
        _hold("candidateFacts changedSkillIds/bumpedVersions disagree")
    return changed, bumped, pins


# ---------------------------------------------------------------------------
# candidate path classification + immutable-history freeze
# ---------------------------------------------------------------------------


def classify_candidate_diff(added, removed, modified, mode):
    for rel in added + removed + modified:
        if rel in DENIED_EXACT or rel.startswith(DENIED_PREFIXES):
            _hold(f"{mode}-mode candidate touches trust-critical path {rel!r}")
    for rel in added + modified:
        ok = (rel in CANDIDATE_ALLOW_EXACT
              or any(rel.startswith(prefix) for prefix in CANDIDATE_ALLOW_DIRS))
        if not ok:
            _hold(f"{mode}-mode candidate changes unknown path {rel!r}")
    for rel in removed:
        if rel.startswith(REVIEW_HISTORY_PREFIXES_TUPLE):
            if mode == "reviews":
                continue  # B1: minimal S prunes old reviews; X restores from B
            _hold(f"catalog-mode candidate may never drop historical review "
                  f"paths: {rel!r}")
        if rel.startswith("sources/"):
            continue  # ordinary mutable publication data per the settled contract
        _hold(f"candidate may never delete {rel!r}")


def assert_frozen_history(base_tree, candidate_tree, mode, label):
    """Old archives/reviews are immutable; reviews pruning is reviews-mode only."""
    for rel, entry in sorted(base_tree.items()):
        if rel.startswith(PACKAGE_PREFIXES):
            if candidate_tree.get(rel) != entry:
                _hold(f"{label}: published archive changed or deleted at candidate: {rel}")
        elif rel.startswith(REVIEW_HISTORY_PREFIXES_TUPLE):
            kept = candidate_tree.get(rel)
            if mode == "catalog" and kept != entry:
                _hold(f"{label}: catalog-mode candidate must preserve every "
                      f"historical review pair exactly: {rel}")
            if kept is not None and kept != entry:
                _hold(f"{label}: candidate mutated a retained historical review "
                      f"path: {rel}")
        elif rel in cv.ARTIFACT_FILES or rel == LEDGER_REL:
            if candidate_tree.get(rel) != entry:
                _hold(f"{label}: candidate cannot pre-write feeds/ledger path {rel!r}")


# ---------------------------------------------------------------------------
# registry delta + prior published proof (pure over provided bytes/blobs)
# ---------------------------------------------------------------------------


def validate_registry_delta(base_registry_raw, candidate_registry_raw,
                            candidate_pins_raw, base_commit_label,
                            candidate_ids, bumped, pins_expected, *,
                            expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    if base_registry_raw == candidate_registry_raw:
        _hold(f"{candidate_ids and 'candidate'}: candidate registry is unchanged; "
              "an update must carry bumped rows")
    base_reg = _canonical_json(base_registry_raw, "base registry")
    cand_reg = _canonical_json(candidate_registry_raw, "candidate registry")
    _as_publication(lambda: hubcore.validate_registry(base_reg,
                                                      expect_counts=expect_counts))
    _as_publication(lambda: hubcore.validate_registry(cand_reg,
                                                      expect_counts=expect_counts))
    base_rows = {e["id"]: e for e in base_reg["skills"]}
    cand_rows = {e["id"]: e for e in cand_reg["skills"]}
    if set(base_rows) != set(cand_rows):
        _hold("candidate registry cannot add or remove skill ids (curation is a "
              "reviewed act, never an automatic update)")
    pins_doc, resolved_pins = effective_pins(
        candidate_pins_raw or b"{}", _canonical_json(candidate_registry_raw,
                                                      "candidate registry"))
    reasons = upstream_pins.check_registry_pins(pins_doc, _canonical_json(
        candidate_registry_raw, "candidate registry"))
    if reasons:
        _hold("candidate pins/registry provenance is inconsistent for the "
              "effective per-entry pins: " + " | ".join(str(r) for r in reasons[:6]))
    frozen_fields = ("id", "planNumber", "kind", "source", "name", "description",
                     "category", "tags", "deepAdaptation", "firstParty",
                     "minimumAppVersion", "plannedRuntime")
    for id_, after in sorted(cand_rows.items()):
        before = base_rows[id_]
        if set(after) != set(before):
            _hold(f"{id_}: registry row key set drifted")
        changed = {key for key in after if after[key] != before[key]}
        if id_ not in candidate_ids:
            if changed and changed != {"upstream"}:
                _hold(f"non-candidate registry row changed: {id_}")
            if changed:
                up_before, up_after = before["upstream"], after["upstream"]
                if (up_before is None or up_after is None
                        or set(up_after) != set(up_before)
                        or {k for k in up_after if up_after[k] != up_before[k]}
                        - {"commit", "retrievedAt"}):
                    _hold(f"non-candidate row {id_} may only track its pin advance")
                if resolved_pins.get(id_) != up_after["commit"]:
                    _hold(f"non-candidate row {id_} pin disagrees with the "
                          "effective upstream pin")
            continue
        if changed - {"versionTarget", "upstream", "status", "notes"}:
            _hold(f"{id_}: candidate changed frozen registry fields "
                  f"{sorted(changed - {'versionTarget', 'upstream', 'status', 'notes'})} "
                  "(permissions/platforms/licenses/minimumAppVersion are never automatic)")
        target = bumped.get(id_)
        if not isinstance(target, dict) or after["versionTarget"] != target.get("to") \
                or before["versionTarget"] != target.get("from"):
            _hold(f"{id_}: registry version does not equal the staged bump")
        if before["upstream"] is None or after["upstream"] is None:
            _hold(f"{id_}: first-party rows are outside automatic tracking")
        up_before, up_after = before["upstream"], after["upstream"]
        up_changed = {k for k in up_after if up_after[k] != up_before.get(k)}
        if set(up_after) != set(up_before) or up_changed - {"commit", "retrievedAt"}:
            _hold(f"{id_}: upstream identity fields changed: "
                  f"{sorted(up_changed | (set(up_after) ^ set(up_before)))}")
        if pins_expected.get(id_) not in (None, up_after["commit"]):
            _hold(f"{id_}: registry pin is not the staged resolved commit")
        if resolved_pins.get(id_) != up_after["commit"]:
            _hold(f"{id_}: registry pin does not equal the effective upstream pin")
        for key in frozen_fields:
            if before[key] != after[key]:
                _hold(f"{id_}: frozen registry field {key} drifted")
        if after["status"]["published"] or before["status"]["published"]:
            _hold(f"{id_}: registry data can never claim published")
        if not (after["status"]["reviewed"] and after["status"]["packaged"]):
            _hold(f"{id_}: candidate registry row is not reviewed+packaged; "
                  "signing could not bind it honestly")
        if before["status"]["qualified"] and not after["status"]["qualified"]:
            _hold(f"{id_}: candidate silently unqualifies a published entry")
    return base_rows, cand_rows


def ledger_rows_at(root, commit):
    raw = blob_at(root, commit, LEDGER_REL, "ledger")
    if raw is None:
        _hold("the base publication has no cumulative ledger (history cannot be proven)")
    return _canonical_json(raw, "base ledger")["publications"]


def baseline_via_blob(root, base_commit):
    raw = blob_at(root, base_commit, LEDGER_REL, "base ledger")
    if raw is None:
        _hold("the base publication has no ledger blob")
    tmp = tempfile.TemporaryDirectory(prefix="floe-auto-pub-")
    try:
        path = pathlib.Path(tmp.name) / "publication-ledger.json"
        path.write_bytes(raw)
        return _as_publication(
            lambda: pi.build_validated_baseline(pathlib.Path(root), path,
                                                base_commit, {}))
    finally:
        tmp.cleanup()


def prior_published_proof(root, base_commit, trust, baseline, id_, prior_version):
    """Ledger-verified prior proof: signed feed binding + qualified record."""
    found = False
    for channel in cv.VIEWS:
        feed_rel, sig_rel = FEED_PATHS[channel]
        feed_bytes = blob_at(root, base_commit, feed_rel, "base feed")
        sig_bytes = blob_at(root, base_commit, sig_rel, "base feed sig")
        if feed_bytes is None and sig_bytes is None:
            continue  # historical publication without this view
        if feed_bytes is None or sig_bytes is None:
            _hold(f"base {channel} publication pair is incomplete")
        key_id = _as_publication(
            lambda: hubcore.verify_envelope(feed_bytes, sig_bytes, trust))
        if key_id != hubcore.PRODUCTION_KEY_ID:
            _hold(f"base {channel} feed is not official-identity signed")
        feed = _canonical_json(feed_bytes, f"base {channel} feed")
        _as_publication(
            lambda: cv.validate_view(feed, channel))
        entry = next((e for e in feed["entries"] if e["id"] == id_
                      and e["version"] == prior_version), None)
        if entry is None:
            continue
        found = True
        if baseline.get((cv.channel_for(channel), id_, prior_version)) is None:
            _hold(f"{id_}: prior offer is absent from the verified ledger baseline")
        if entry["package"] is None or entry["review"] is None:
            _hold(f"{id_}@{prior_version} is not a published offer on {channel}")
    if not found:
        _hold(f"{id_}@{prior_version} has no verified prior published offer")

    record_rel = f"reviews/{id_}/{prior_version}.review.json"
    record_bytes = blob_at(root, base_commit, record_rel, "prior review")
    envelope = blob_at(root, base_commit, record_rel + ".sig", "prior review sig")
    if record_bytes is None or envelope is None:
        _hold(f"{id_}: prior review pair {record_rel} is missing at the base")
    key_id = _as_publication(
        lambda: hubcore.verify_envelope(record_bytes, envelope, trust))
    if key_id != hubcore.PRODUCTION_KEY_ID:
        _hold(f"{id_}: prior review envelope is not official-identity signed")
    record = _canonical_json(record_bytes, "prior review record")
    _as_publication(lambda: hubcore.validate_review(record))
    if record["reviewStage"] != "guest-execution-qualified":
        _hold(f"{id_}: prior review is not a guest-execution qualification")
    if record["decision"] != "approve" or record["id"] != id_ \
            or record["version"] != prior_version:
        _hold(f"{id_}: prior review identity/decision drift")
    if record["execution"] != {"os": "linux", "arch": "riscv64",
                               "evidence": "guest-verified"}:
        _hold(f"{id_}: prior review execution is not the real guest plane")
    pins = sorted({row["publication"] for row in ledger_rows_at(root, base_commit)
                   for offer in row["offers"]
                   if offer["id"] == id_ and offer["version"] == prior_version
                   and offer["contentDigest"] == record["contentDigest"]})
    if not pins:
        _hold(f"{id_}: no ledger row pins the prior offer with its signed digest")
    return {"recordRel": record_rel,
            "recordSha256": hubcore.sha256_hex(record_bytes),
            "contentDigest": record["contentDigest"],
            "packageSha256": record["packageSha256"],
            "publicationPins": pins}


# ---------------------------------------------------------------------------
# independent verification of the tracker's honest review records
# ---------------------------------------------------------------------------


def _citation_present(note_text, value, prefix=10):
    return str(value)[:prefix] in note_text


def verify_review_record_bytes(record_bytes, *, id_, version, archive_bytes,
                               expected_stage, expected_execution, today,
                               notes_must_cite=None):
    """Field-level independent verification of one proposed approval record."""
    if hubcore.sha256_hex(b"") is None:  # unreachable; keeps helper pure
        pass
    if len(record_bytes) > hubcore.MAX_FILE_BYTES:
        _hold(f"{id_}: review record oversized")
    record = _canonical_json(record_bytes, f"review {id_}")
    if hubcore.encoded(record) != record_bytes:
        _hold(f"{id_}: review record is not canonical")
    _as_publication(lambda: hubcore.validate_review(record))
    if record["id"] != id_ or record["version"] != version:
        _hold(f"{id_}: review identity drift")
    if record["decision"] != "approve":
        _hold(f"{id_}: only approved records may stage; a rejection is a HOLD")
    if not MACHINE_ID_RE.fullmatch(record["reviewer"]):
        _hold(f"{id_}: reviewer is not the bounded machine identity — automatic "
              "publication carries no human or model review attestation")
    if today is not None and record["reviewedAt"] != today:
        _hold(f"{id_}: reviewedAt is not the deterministic staging date")
    if record["reviewStage"] != expected_stage or record["execution"] != expected_execution:
        _hold(f"{id_}: review stage/execution contradict the recomputed tier")
    files_of_archive = _archive_files(archive_bytes, id_)
    manifest, _ = _as_publication(
        lambda: hubcore.validate_package_files(files_of_archive,
                                               require_notice=True))
    if manifest["id"] != id_ or manifest["version"] != version:
        _hold(f"{id_}: review/package identity drift")
    if record["contentDigest"] != hubcore.content_digest(files_of_archive) or \
            record["packageSha256"] != hubcore.sha256_hex(archive_bytes):
        _hold(f"{id_}: review digests do not equal the recomputed archive bytes")
    if set(record["reviewedCapabilities"]) != set(manifest["capabilities"]) or \
            set(record["reviewedTools"]) != set(manifest["tools"]):
        _hold(f"{id_}: review does not cover exactly the manifest grants")
    if {p["spec"] for p in record["reviewedPythonPackages"]} != \
            {p["spec"] for p in manifest["pythonPackages"]}:
        _hold(f"{id_}: review does not cover exactly the manifest dependencies")
    binding = {"path": "packages/verify-only", "size": len(archive_bytes),
               "sha256": hubcore.sha256_hex(archive_bytes),
               "contentDigest": hubcore.content_digest(files_of_archive),
               "containsScripts": any(n.startswith("scripts/")
                                      for n in files_of_archive)}
    _as_publication(lambda: hubcore.join_review(record, manifest, binding, id_))
    if notes_must_cite:
        note_text = record["notes"]["en"] + " " + record["notes"]["zh-Hans"]
        for value, prefix in notes_must_cite:
            if not _citation_present(note_text, value, prefix):
                _hold(f"{id_}: review notes omit the required prior-proof citation "
                      f"for {str(value)[:16]}…")
    return record, manifest


# ---------------------------------------------------------------------------
# immutable-candidate upstream re-derivation (frozen contract
# immutableUpstreamRecompute): the candidate's OWN selected NEW commits are
# proven reachable in fixed official history, then the frozen tracker
# re-derives ONLY those ids so unrelated fresh drift cannot change the
# expected apply set.
# ---------------------------------------------------------------------------


def _argv_git(cwd, args, purpose, timeout=600):
    """One controlled argv-only git invocation with a scrubbed environment."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
                "GIT_NO_REPLACE_OBJECTS": "1"})
    proc = subprocess.run(["git", "-C", str(cwd),
                           "-c", "core.hooksPath=/nonexistent",
                           "-c", "core.fsmonitor=false", *args],
                          capture_output=True, env=env, timeout=timeout)
    if proc.returncode != 0:
        _hold(f"{purpose}: git {' '.join(args[:3])} failed: "
              f"{proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return proc.stdout


def plan_rederivation(root, base_commit, candidate_commit, *,
                      expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """Parse the candidate's OWN upstream selections from the committed
    B..candidate registry diff (input choice, never approval authority)."""
    base_raw = blob_at(root, base_commit, REGISTRY_REL, "base registry")
    cand_raw = blob_at(root, candidate_commit, REGISTRY_REL, "candidate registry")
    if base_raw is None or cand_raw is None:
        _hold("registry blob missing on base or candidate")
    base_reg = _canonical_json(base_raw, "base registry")
    cand_reg = _canonical_json(cand_raw, "candidate registry")
    _as_publication(lambda: hubcore.validate_registry(base_reg,
                                                      expect_counts=expect_counts))
    _as_publication(lambda: hubcore.validate_registry(cand_reg,
                                                      expect_counts=expect_counts))
    policy_bytes = blob_at(root, base_commit, POLICY_REL, "policy")
    if policy_bytes is None:
        _hold("pinned policy blob missing at the base")
    policy_doc = _canonical_json(policy_bytes, "policy")
    declared = policy_doc.get("repositories") or {}
    base_rows = {e["id"]: e for e in base_reg["skills"]}
    cand_rows = {e["id"]: e for e in cand_reg["skills"]}
    entries = {}
    repositories = {}
    for id_, after in sorted(cand_rows.items()):
        before = base_rows.get(id_)
        if before is None:
            _hold(f"{id_}: candidate added a registry row (curation is never automatic)")
        if before == after:
            continue
        up_b, up_c = before.get("upstream"), after.get("upstream")
        if up_b is None or up_c is None:
            _hold(f"{id_}: first-party rows are outside automatic tracking")
        if up_c["repository"] != up_b["repository"]:
            _hold(f"{id_}: upstream repository identity changed")
        old, new = up_b["commit"], up_c["commit"]
        hubcore.require_commit(old, f"{id_} old pin")
        hubcore.require_commit(new, f"{id_} new pin")
        if old == new:
            _hold(f"{id_}: registry row changed without any upstream pin advance")
        if up_c["repository"] not in declared:
            _hold(f"{id_}: repository {up_c['repository']} is not declared in "
                  "the pinned policy")
        bumped = after["versionTarget"] != before["versionTarget"]
        entries[id_] = {"repository": up_c["repository"], "old": old, "new": new,
                        "bumped": bumped}
        slot = repositories.setdefault(up_c["repository"], {"olds": set(), "news": set()})
        slot["olds"].add(old)
        slot["news"].add(new)
    if not entries:
        _hold("candidate registry diff carries no upstream pin advance")
    repo_view = {}
    for url, slot in sorted(repositories.items()):
        if len(slot["news"]) != 1:
            _hold(f"repository {url} carries conflicting NEW selections: "
                  f"{sorted(slot['news'])}")
        repo_view[url] = {"olds": sorted(slot["olds"]), "new": sorted(slot["news"])[0]}
    return {"targetIds": sorted(entries), "entries": entries,
            "repositories": repo_view}


def prove_upstream_ancestry(cache_dir, url, old_commit, new_commit, *,
                            tracked_ref="HEAD"):
    """Prove NEW is an official immutable ancestor of the CURRENT head and a
    descendant of the OLD pin, using only the fixed policy URL (public,
    tokenless).

    Shallow-cache safety (live-proved detail): the trusted tracker's
    GitUpstreamSource fetches each sha with --depth 1 blobless, so a shared or
    reused cache can hold disconnected shallow boundaries where a plain
    merge-base --is-ancestor would FALSE-NEGATIVE a legitimate update. This
    prover therefore never trusts a shallow object store: it detects
    --is-shallow-repository and --unshallow-fetches (blobless, full commit
    graph) before proving, and it fetches the tracked ref's FULL blobless
    history plus the exact OLD/NEW objects. An unknown object after a full
    fetch is reported as unreachable (never as a proven rewrite), and every
    git invocation keeps the scrubbed environment, disabled hooks/fsmonitor
    and replacement refs of the frozen readers. Unreachable commits,
    rewritten history and OLD rollbacks fail closed: the candidate NEW is an
    INPUT choice, never authority.
    """
    hubcore.require_commit(old_commit, "upstream old pin")
    hubcore.require_commit(new_commit, "upstream selected new commit")
    if (not isinstance(url, str) or "@" in url or not url
            or url.startswith("-")):
        _hold(f"upstream URL is not a plain fixed policy origin: {url!r}")
    cache = pathlib.Path(cache_dir) / ("repo-" + hubcore.sha256_hex(url.encode())[:16])
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        cache.mkdir(parents=True)
        _argv_git(cache, ["init", "-q"], "upstream ancestry init")
        _argv_git(cache, ["remote", "add", "origin", url], "upstream ancestry remote")
    head_out = _argv_git(cache, ["ls-remote", "origin", tracked_ref],
                         "upstream ls-remote")
    head = None
    for line in head_out.decode("utf-8", "replace").splitlines():
        sha, _, refname = line.partition("\t")
        sha = sha.strip()
        if tracked_ref == "HEAD" or refname.strip() == tracked_ref \
                or refname.strip().endswith("/" + tracked_ref):
            head = sha
            break
    if head is None or not hubcore.COMMIT_PATTERN.fullmatch(head):
        _hold(f"upstream head could not be resolved for {url}")
    shallow = _argv_git(cache, ["rev-parse", "--is-shallow-repository"],
                        "shallow probe").decode().strip() == "true"
    if shallow:
        _argv_git(cache, ["fetch", "-q", "--unshallow", "--no-tags",
                          "--filter=blob:none", "origin"],
                  "unshallow blobless fetch of the full official history")
    try:
        _argv_git(cache, ["fetch", "-q", "--no-tags", "--filter=blob:none",
                          "origin", f"+{tracked_ref}:refs/floe/track",
                          old_commit, new_commit, head],
                  f"upstream blobless fetch {url}")
    except PublicationError as error:
        _hold(f"selected commit is unreachable at the fixed official origin "
              f"{url} (the server refused the object; never treated as a "
              f"proven rewrite, always fail closed): {error}")

    def ancestry(a, b, what):
        proc = subprocess.run(
            ["git", "-C", str(cache), "-c", "core.hooksPath=/nonexistent",
             "-c", "core.fsmonitor=false", "merge-base", "--is-ancestor", a, b],
            capture_output=True)
        if proc.returncode == 0:
            return True
        if proc.returncode == 1:
            return False
        _hold(f"{what}: ancestry undecidable after a full blobless fetch "
              "(missing objects; treated as unreachable, never as proof of "
              f"rewrite): {proc.stderr.decode('utf-8', 'replace').strip()[:200]}")

    if not ancestry(old_commit, new_commit,
                    f"OLD {old_commit[:10]} -> NEW {new_commit[:10]}"):
        _hold(f"selected NEW {new_commit[:10]} is not a descendant of the OLD "
              f"pin {old_commit[:10]} at {url} (rollback/rewrite never accepted)")
    if not ancestry(new_commit, head,
                    f"NEW {new_commit[:10]} -> head {head[:10]}"):
        _hold(f"selected NEW {new_commit[:10]} is unreachable from the current "
              f"official head {head[:10]} at {url} (rewritten or dropped "
              "history is never trusted)")
    return {"url": url, "old": old_commit, "new": new_commit,
            "currentHead": head, "oldAncestorNew": True,
            "newAncestorCurrentHead": True, "unshallowed": shallow}


class PinnedUpstreamSource:
    """Trusted upstream source whose resolve_ref answers with the candidate's
    proven selected NEW commit for exactly the pinned repositories; every
    other repository (engine tags, watch-only signals) passes through to the
    inner source untouched. Informational signals may legitimately reflect
    the live head and never grant or revoke candidate approval."""

    def __init__(self, inner, pins_by_url):
        self._inner = inner
        self._pins = dict(pins_by_url)

    def resolve_ref(self, url, ref="HEAD"):
        if url in self._pins:
            return (self._pins[url], "refs/floe/selected")
        return self._inner.resolve_ref(url, ref)

    def list_tags(self, url, prefix=""):
        return self._inner.list_tags(url, prefix)

    def commit_tree_oid(self, url, commit, subpath):
        return self._inner.commit_tree_oid(url, commit, subpath)

    def commit_root_tree_oid(self, url, commit):
        return self._inner.commit_root_tree_oid(url, commit)

    def list_tree(self, url, commit, subpath):
        return self._inner.list_tree(url, commit, subpath)

    def read_subtree(self, url, commit, subpath):
        return self._inner.read_subtree(url, commit, subpath)

    def read_file(self, url, commit, path):
        return self._inner.read_file(url, commit, path)


def rederive_candidate(root, base_commit, candidate_commit, *, today,
                       stage_root, source=None, prove=None, cache=None,
                       expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """Re-run the frozen tracker for EXACTLY the candidate's changed and
    pin-advanced ids against its OWN proven immutable NEW commits, writing a
    deterministic stage root consumable by derive_expected_apply_set /
    verify_candidate. Production injects nothing: the tracker CLI path
    (rederive-candidate) uses the real GitUpstreamSource with policy-fixed
    origins; pure tests may inject a trusted local source/prover seam.
    """
    import upstream_updates as uu
    selection = plan_rederivation(root, base_commit, candidate_commit,
                                  expect_counts=expect_counts)
    policy_bytes = blob_at(root, base_commit, POLICY_REL, "policy")
    policy_doc = _canonical_json(policy_bytes, "policy")
    cache = cache or str(pathlib.Path(os.environ.get("RUNNER_TEMP")
                                      or tempfile.gettempdir())
                         / "floe-rederive-cache")
    proofs = {}
    for id_, sel in sorted(selection["entries"].items()):
        # policy repositories are keyed by the canonical FULL https URL (the
        # loader validates that shape); a short owner/name lookup would miss
        # and silently degrade every declared trackedRef to HEAD.
        tracked_ref = (policy_doc.get("repositories", {})
                       .get(sel["repository"]) or {}).get("trackedRef", "HEAD")
        if prove is not None:
            if not prove(sel["repository"], sel["old"], sel["new"]):
                _hold(f"{id_}: injected ancestry proof failed")
            proofs[id_] = {"url": sel["repository"], "old": sel["old"],
                           "new": sel["new"], "proved": "injected-trusted"}
        else:
            proofs[id_] = prove_upstream_ancestry(cache, sel["repository"],
                                                  sel["old"], sel["new"],
                                                  tracked_ref=tracked_ref)
    pins_by_url = {}
    for sel in selection["entries"].values():
        pins_by_url.setdefault(sel["repository"], sel["new"])
    inner = source if source is not None else uu.GitUpstreamSource(cache)
    pinned = PinnedUpstreamSource(inner, pins_by_url)
    inputs = uu.load_inputs(root, expect_counts=expect_counts)
    only = selection["targetIds"]
    check = uu.run_check(root, inputs, pinned, today, only=only)
    plan = uu.run_plan(root, inputs, pinned, today, only=only,
                       check_report=check)
    stage = uu.run_stage(root, inputs, pinned, plan, stage_root)
    return {"status": "rederived", "targetIds": only,
            "repositories": selection["repositories"],
            "proofs": proofs,
            "stagedChangedIds": stage["candidateFacts"]["changedSkillIds"],
            "stagedHeldIds": stage["candidateFacts"].get("heldSkillIds") or []}


# ---------------------------------------------------------------------------
# independent re-derivation: the ONLY candidate authority
# ---------------------------------------------------------------------------


def _manifest_freeze_check(id_, manifest, prior_manifest):
    """Every floe.json field except version is frozen for ALL tiers.

    platforms, scriptRuntime, tools, capabilities, pythonPackages and any
    future non-version field must equal the published baseline byte-for-byte;
    a guide-only body rewrite can therefore never smuggle a runtime/grant
    change, and a scripted docs-only change cannot either.
    """
    if _manifest_without_version(manifest) != _manifest_without_version(prior_manifest):
        _hold(f"{id_}: floe.json fields outside version differ from the published "
              "baseline (grants/runtime/platforms/dependencies are never automatic)")


def derive_expected_apply_set(repo_root, base_commit, stage_root, *, today,
                              trust=None,
                              expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """Recompute the EXACT expected candidate writes from a fresh tracker stage.

    Production passes a stage root freshly produced by the frozen
    upstream_updates check/plan/stage re-run against official base B with its
    own live-resolved upstream commits and --today fixed to the candidate's
    staging date; pure tests may inject a trusted local re-derivation of the
    same shape. Caller manifests, gateResults, pins_expected and
    candidateFacts are cross-checked against this output and are NEVER
    authority: the expected bytes of every source file, archive, registry,
    pin, showcase file and proposed review record are determined here from
    upstream-merged staged trees, the unchanged package gates, the effective
    pin contract and the ledger-bound prior proof.
    """
    if not DATE_RE.fullmatch(today or ""):
        _hold("today must be YYYY-MM-DD")
    stage = load_stage(stage_root)
    changed_ids, bumped, pins = _stage_candidate_facts(stage)
    staging_today = stage["manifest"].get("today")
    if staging_today != today:
        _hold(f"fresh stage today {staging_today!r} is not the candidate staging "
              f"date {today!r} (the re-run must pin --today to the request)")
    base_tree = tree_at(repo_root, base_commit, "base")
    base_registry = blob_at(repo_root, base_commit, REGISTRY_REL, "base registry")
    if base_registry is None:
        _hold("base registry blob missing")
    base_rows = {e["id"]: e for e in _canonical_json(base_registry,
                                                     "base registry")["skills"]}
    trust = trust or build_catalog.load_trust(repo_root)
    if not trust or hubcore.FIXTURE_KEY_ID in trust:
        _hold("official public trust is unavailable")
    baseline_cache = {}

    def ensure_baseline():
        if "value" not in baseline_cache:
            baseline_cache["value"] = baseline_via_blob(repo_root, base_commit)
        return baseline_cache["value"]

    writes, deletions, gate_results = {}, set(), {}
    stage_counts = {"static-content-reviewed": 0, "prior-proof-reuse": 0}
    executable_digests, pins_before, pins_after = {}, {}, {}

    proposed_records = {}
    for rel in stage["applyOrder"]:
        data = stage["applyFiles"][rel]
        if rel in DENIED_EXACT or rel.startswith(DENIED_PREFIXES):
            _hold(f"fresh apply set touches a trust-critical path: {rel}")
        if rel.startswith("reviews/") and rel.endswith(".review.json"):
            proposed_records[rel] = data
            continue
        if rel in CANDIDATE_ALLOW_EXACT or rel.startswith(("sources/",)):
            writes[rel] = data
            continue
        _hold(f"fresh apply set contains an unclassified path: {rel}")
    if REGISTRY_REL not in writes:
        _hold("fresh apply set must carry the bumped registry")
    if not changed_ids:
        _hold("fresh stage carries no candidates (held-state path only)")
    for rel in stage["applyDeletions"]:
        if rel not in base_tree:
            _hold(f"fresh apply deletion targets a path absent from the base: {rel}")
        if rel in writes:
            _hold(f"fresh apply set writes and deletes the same path: {rel}")
        deletions.add(rel)

    for id_ in sorted(set(changed_ids)):
        matches = [key for key in stage["candidates"] if key[0] == id_]
        if len(matches) != 1:
            _hold(f"{id_}: expected exactly one staged candidate version")
        key = matches[0]
        entry = stage["candidates"][key]
        version = key[1]
        row = base_rows.get(id_)
        bump = bumped.get(id_)
        pin = pins.get(id_)
        if row is None or not isinstance(bump, dict) or not isinstance(pin, dict):
            _hold(f"{id_}: no registry row or incomplete bump/pin facts")
        if bump.get("to") != version or row["versionTarget"] != bump.get("from"):
            _hold(f"{id_}: staged version contradicts the registry bump")
        expected_commit = pin.get("to")
        if not isinstance(expected_commit, str) or \
                not hubcore.COMMIT_PATTERN.fullmatch(expected_commit):
            _hold(f"{id_}: pin advance is not a 40-hex commit")
        if row["upstream"] is None or row["upstream"]["commit"] != pin.get("from"):
            _hold(f"{id_}: pin advance from-value does not match the base registry")

        zip_files = {rel: blob for rel, blob in entry["tree"].items()
                     if rel != "release.json"}
        if not zip_files:
            _hold(f"{id_}: staged candidate tree is empty")
        built = hubcore.make_zip(zip_files)
        if entry["package"] is not None and entry["package"] != built:
            _hold(f"{id_}: staged package.zip is not the deterministic rebuild of "
                  "its staged tree")
        files_of_archive = _archive_files(built, id_)
        manifest, _ = _as_publication(
            lambda: hubcore.validate_package_files(files_of_archive,
                                                   require_notice=True))
        planned = row["plannedRuntime"]
        if manifest["id"] != id_ or manifest["version"] != version:
            _hold(f"{id_}: candidate manifest identity drift")
        if set(manifest["capabilities"]) != set(planned["capabilities"]) or \
                set(manifest["tools"]) != set(planned["tools"]):
            _hold(f"{id_}: capability/tool grants differ from the published plan")
        if [p["spec"] for p in manifest["pythonPackages"]] != \
                list(planned["pythonPackagesPlan"] or []):
            _hold(f"{id_}: dependency plan differs from the published row")

        # THE published baseline freeze applies to every tier: the prior
        # package's floe.json (version excepted) must equal the candidate's.
        channels = planned["installPlatforms"]
        prior_rel = hubcore.package_path_for(id_, bump["from"], channels[0])
        prior_blob = blob_at(repo_root, base_commit, prior_rel, "prior archive")
        if prior_blob is None:
            _hold(f"{id_}: prior published archive {prior_rel} is absent")
        prior_files = _archive_files(prior_blob, id_)
        prior_manifest, _ = _as_publication(
            lambda: hubcore.validate_package_files(prior_files,
                                                   require_notice=True))
        _manifest_freeze_check(id_, manifest, prior_manifest)

        for channel in channels:
            rel = hubcore.package_path_for(id_, version, channel)
            if rel in base_tree:
                _hold(f"{id_}: candidate version collides with an immutable base archive")
            writes[rel] = built

        # actual sources <-> frozen ZIP byte equality over the FULL expected
        # source tree: base blobs at sources/<id>/ overlaid by the (changed-file
        # only) apply writes, minus apply deletions. The producer contract
        # writes ONLY changed source files into apply/, so unchanged members
        # must come from the committed base and still equal the ZIP exactly.
        staged_source_prefix = f"sources/{id_}/"
        expected_sources = {}
        for rel in sorted(base_tree):
            if rel.startswith(staged_source_prefix):
                member = rel[len(staged_source_prefix):]
                blob = blob_at(repo_root, base_commit, rel, "base source")
                if blob is None:
                    _hold(f"{id_}: base source blob unreadable: {rel}")
                expected_sources[member] = blob
        for rel, data in writes.items():
            if rel.startswith(staged_source_prefix):
                expected_sources[rel[len(staged_source_prefix):]] = data
        for rel in deletions:
            if rel.startswith(staged_source_prefix):
                expected_sources.pop(rel[len(staged_source_prefix):], None)
        if expected_sources.get("floe.json") != files_of_archive.get("floe.json"):
            _hold(f"{id_}: expected source floe.json is not the packaged floe.json")
        for member, data in sorted(files_of_archive.items()):
            if member == "release.json":
                continue
            if expected_sources.get(member) != data:
                _hold(f"{id_}: packaged member {member} differs from the "
                      "expected source bytes (base + apply overlay)")
        for member in sorted(expected_sources):
            if member == "release.json":
                continue
            if member not in files_of_archive:
                _hold(f"{id_}: expected source {member} is absent from the "
                      "frozen ZIP")

        guide = manifest["scriptRuntime"] == "none"
        expected_stage = "static-content-reviewed" if guide \
            else "guest-execution-qualified"
        expected_execution = ({"os": None, "arch": "n/a", "evidence": "unproven"}
                              if guide else
                              {"os": "linux", "arch": "riscv64",
                               "evidence": "guest-verified"})
        staged_tier = entry["candidate"].get("tier")
        if (staged_tier == 1) != guide or (staged_tier == 2) == guide:
            _hold(f"{id_}: staged tier flag contradicts the recomputed runtime")
        executable_digests[id_] = {"archiveSha256": hubcore.sha256_hex(built)}
        notes_cite = None
        if not guide:
            candidate_fp = execution_fingerprint(files_of_archive)
            candidate_icf = instruction_code_fingerprint(files_of_archive)
            if execution_fingerprint(prior_files) != candidate_fp or \
                    instruction_code_fingerprint(prior_files) != candidate_icf:
                _hold(f"{id_}: execution or instruction-code fingerprint changed; "
                      "runtime-relevant updates are HELD for genuine "
                      "qualification and never auto-published")
            proof = prior_published_proof(repo_root, base_commit, trust,
                                          ensure_baseline(), id_, bump["from"])
            executable_digests[id_].update({
                "fingerprint": candidate_fp,
                "instructionCodeFingerprint": candidate_icf,
                "priorProof": {"priorVersion": bump["from"],
                               "priorContentDigest": proof["contentDigest"],
                               "priorReviewSha256": proof["recordSha256"],
                               "publicationPins": proof["publicationPins"]}})
            notes_cite = [(bump["from"], 4),
                          (proof["contentDigest"], 10),
                          (proof["recordSha256"], 10),
                          (proof["publicationPins"][0], 10),
                          (candidate_fp, 10)]
        else:
            executable_digests[id_]["fingerprint"] = \
                execution_fingerprint(files_of_archive)
        record_rel = f"reviews/{id_}/{version}.review.json"
        if record_rel not in proposed_records:
            _hold(f"{id_}: fresh apply set carries no proposed review record")
        verify_review_record_bytes(proposed_records[record_rel], id_=id_,
                                   version=version, archive_bytes=built,
                                   expected_stage=expected_stage,
                                   expected_execution=expected_execution,
                                   today=today, notes_must_cite=notes_cite)
        writes[record_rel] = proposed_records[record_rel]
        stage_counts["static-content-reviewed" if guide else "prior-proof-reuse"] += 1
        pins_before[id_], pins_after[id_] = row["upstream"]["commit"], expected_commit
        gate_results[id_] = {"tier": 1 if guide else 2, "checks": [
            "deterministic-archive-rebuild", "package-gates", "grants-equality",
            "manifest-freeze-vs-published", "effective-pin-agreement",
            "ledger-bound-prior-proof" if not guide
            else "guide-only-no-execution-claim"]}

    unused_records = sorted(set(proposed_records) - set(writes))
    if unused_records:
        _hold(f"fresh apply set carries review records for unapplied candidates: "
              f"{unused_records[:8]}")

    validate_registry_delta(base_registry, writes[REGISTRY_REL],
                            writes.get(PINS_REL), "fresh",
                            set(changed_ids), bumped, pins_after,
                            expect_counts=expect_counts)

    facts = stage["facts"]
    if {k: v for k, v in (facts.get("reviewStageCounts") or {}).items() if v} \
            != {k: v for k, v in stage_counts.items() if v}:
        _hold(f"staged reviewStageCounts {facts.get('reviewStageCounts')!r} "
              f"disagree with the recomputed {stage_counts}")
    subset = facts.get("executableSubsetUnchanged") or {}
    for id_, claimed in subset.items():
        if id_ in gate_results and gate_results[id_]["tier"] == 2 \
                and claimed is not True:
            _hold(f"{id_}: staged executable-subset claim contradicts eligibility")

    deletions |= {rel for rel in base_tree
                  if rel.startswith(REVIEW_HISTORY_PREFIXES_TUPLE)
                  and rel not in writes}

    integration_gaps = []
    if stage["deferred"]:
        integration_gaps.append({
            "code": "per-entry-pin-contract",
            "ids": sorted(stage["deferred"]),
            "detail": "staged per-entry candidates in mixed repositories await "
                      "the reviewed per-entry pin override; they are fully "
                      "staged and honestly reported, never dropped",
        })
    hold_reasons = list(facts.get("holdReasons") or [])

    return {
        "writes": writes, "deletions": sorted(deletions),
        "changedSkillIds": sorted(set(changed_ids)),
        "appliedSkillIds": sorted(gate_results),
        "bumpedVersions": {id_: bumped[id_] for id_ in sorted(gate_results)},
        "reviewStageCounts": stage_counts,
        "holdReasons": hold_reasons,
        "gateResults": gate_results,
        "engineTreeOidAtB": commit_tree_oid(repo_root, base_commit, "engines"),
        "executableSubsetDigests": executable_digests,
        "upstreamPinsBefore": {id_: pins_before[id_] for id_ in gate_results},
        "upstreamPinsAfter": {id_: pins_after[id_] for id_ in gate_results},
        "integrationGaps": integration_gaps,
        "stageToday": today,
    }


def build_candidate_payload(repo_root, base_commit, stage_root, out_dir, *, today,
                            expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """Scan-side: derive the expected set and write the minimal S payload."""
    payload = derive_expected_apply_set(repo_root, base_commit, stage_root,
                                        today=today, expect_counts=expect_counts)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, data in sorted(payload["writes"].items()):
        write_payload_file(out_dir / "snapshot", rel, data)
    changes = {k: v for k, v in payload.items() if k != "writes"}
    (out_dir / "changes.json").write_bytes(
        hubcore.pretty({"schemaVersion": SCHEMA_VERSION, **changes}))
    return payload


# ---------------------------------------------------------------------------
# candidate verification shared by the App orchestrator and the Hub publisher
# ---------------------------------------------------------------------------


def _candidate_map_matches(root, base_commit, candidate_commit, expected,
                           mode, require_new_sigs=False):
    base_tree = tree_at(root, base_commit, "base")
    cand_tree = tree_at(root, candidate_commit, "candidate")
    deletions = set(expected["deletions"])
    writes = expected["writes"]
    new_records = {rel for rel in writes if rel.startswith(REVIEW_HISTORY_PREFIXES_TUPLE)
                   and rel.endswith(".review.json")}
    expected_paths = (set(base_tree) - deletions) | set(writes)
    if mode == "catalog":
        # X restores every historical review pair pruned from S and adds the
        # signed envelopes for exactly the new records.
        expected_paths |= {rel for rel in base_tree
                           if rel.startswith(REVIEW_HISTORY_PREFIXES_TUPLE)}
        expected_paths |= {rel + ".sig" for rel in new_records}
    extra = sorted(set(cand_tree) - expected_paths)
    missing = sorted(expected_paths - set(cand_tree))
    if extra:
        _hold(f"candidate carries unexpected paths beyond the independently "
              f"re-derived apply set: {extra[:12]}")
    if missing:
        _hold(f"candidate omits paths required by the independently re-derived "
              f"apply set: {missing[:12]}")
    for rel, (cand_mode, cand_oid) in sorted(cand_tree.items()):
        if rel in writes:
            blob = blob_at(root, candidate_commit, rel, "candidate write")
            if blob != writes[rel]:
                _hold(f"candidate byte-for-byte deviates from the expected "
                      f"upstream-merged output: {rel}")
            continue
        if mode == "catalog" and rel.endswith(".sig") and rel[: -len(".sig")] \
                in new_records:
            continue  # envelope content is bound by the signed relay check
        if base_tree.get(rel) != (cand_mode, cand_oid):
            _hold(f"candidate path {rel} is not the exact retained base entry")
    if require_new_sigs:
        for rel in sorted(new_records):
            if rel + ".sig" not in cand_tree:
                _hold(f"catalog candidate X lacks the signed envelope for {rel}")


def verify_candidate(root, request_doc, manifest_doc, policy_bytes, *,
                     fresh_stage_root, trust=None, history_verdict=None,
                     expected_base=None,
                     expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """Recompute the candidate from a FRESH upstream re-derivation and compare.

    fresh_stage_root is mandatory and is the authoritative expectation: in
    production it is the output of the frozen upstream_updates check/plan/stage
    re-run performed at verification time against the official base B and the
    currently resolved immutable upstream commits (with --today fixed to the
    candidate staging date); trusted tests inject their own local re-derivation
    of the same shape. The caller manifest, gateResults, pins_expected and
    candidateFacts are cross-checked for agreement and never trusted.
    """
    at.validate_request(dict(request_doc))
    if history_verdict is not None:
        _as_publication(lambda: at.verify_request_history_base(
            request_doc, history_verdict))
    mode = request_doc["mode"]
    base_commit = request_doc["basePublication"]
    candidate_commit = request_doc["sourceCommit"]
    if expected_base is not None:
        # independently resolved live main (publisher checkout); must equal the
        # request base — a stale request is refused, never silently rebased
        _require_commit40(expected_base, "expected live base")
        if expected_base != base_commit:
            _hold(f"request basePublication {base_commit[:10]} does not equal the "
                  f"independently resolved live main {expected_base[:10]} — the "
                  "candidate must rebase on the next scan")
    if not at.request_policy_matches(request_doc, policy_bytes):
        _hold("request policySha256 does not bind the presented policy bytes")
    policy_at_base = blob_at(root, base_commit, POLICY_REL, "policy")
    if policy_at_base is None or policy_at_base != policy_bytes:
        _hold("policy bytes do not equal the committed blob at the base publication")
    if blob_at(root, candidate_commit, POLICY_REL, "candidate policy") != policy_bytes:
        _hold("candidate moved the pinned automatic-update policy")
    trust = trust or build_catalog.load_trust(root)
    if not trust or hubcore.FIXTURE_KEY_ID in trust:
        _hold("verification requires official public trust material")
    base_tree = tree_at(root, base_commit, "base")
    cand_tree = tree_at(root, candidate_commit, "candidate")
    added, removed, modified = tree_diff(base_tree, cand_tree)
    classify_candidate_diff(added, removed, modified, mode)
    assert_frozen_history(base_tree, cand_tree, mode, "candidate")
    _as_publication(lambda: at.verify_request_candidate_engine_freeze(
        root, request_doc, candidate_commit))

    manifest = manifest_doc
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != SCHEMA_VERSION:
        _hold("candidate manifest schema invalid")
    for field, expected in (("basePublication", base_commit),
                            ("sourceCommit", candidate_commit),
                            ("requestId", request_doc["requestId"]),
                            ("policySha256", request_doc["policySha256"]),
                            ("mode", mode)):
        if manifest.get(field) != expected:
            _hold(f"manifest {field} disagrees with the request/base")
    if mode == "catalog" and manifest.get("X") != candidate_commit:
        _hold("catalog request is not bound to the manifest X commit")

    today = manifest.get("stageToday")
    expected = derive_expected_apply_set(root, base_commit, fresh_stage_root,
                                         today=today, trust=trust,
                                         expect_counts=expect_counts)

    # The manifest must AGREE with the independent re-derivation; disagreement
    # is a forgery signal, agreement grants the manifest no authority.
    for field in ("changedSkillIds", "bumpedVersions", "reviewStageCounts",
                  "upstreamPinsBefore", "upstreamPinsAfter", "integrationGaps"):
        if manifest.get(field) != expected[field]:
            _hold(f"manifest {field} disagrees with the fresh independent "
                  "re-derivation (candidateFacts are never authority)")
    manifest_gates = manifest.get("gateResults") or {}
    if {k: v.get("tier") for k, v in manifest_gates.items()} != \
            {k: v.get("tier") for k, v in expected["gateResults"].items()}:
        _hold("manifest gateResults disagree with the recomputed tiers")
    # holdReasons and integrationGaps are informational peer snapshots: the
    # fresh re-derivation may legitimately differ once unrelated upstream
    # moved, and wording drift can never invalidate (nor approve) the
    # candidate. The candidate's own identity facts stay strictly equal.
    informational = {
        "holdReasonsEqual": manifest.get("holdReasons") == expected["holdReasons"],
        "integrationGapsEqual": manifest.get("integrationGaps")
        == expected["integrationGaps"],
    }

    _candidate_map_matches(root, base_commit, candidate_commit, expected, mode,
                           require_new_sigs=(mode == "catalog"))
    if manifest.get("engineTreeOidAtB") != expected["engineTreeOidAtB"]:
        _hold("manifest engineTreeOidAtB disagrees with the fresh re-derivation")
    subset = manifest.get("executableSubsetDigests") or {}
    if sorted(subset) != sorted(expected["executableSubsetDigests"]):
        _hold("manifest executableSubsetDigests identity set drifted")
    for id_, info in expected["executableSubsetDigests"].items():
        presented = subset.get(id_) or {}
        if presented.get("archiveSha256") != info["archiveSha256"] or \
                presented.get("fingerprint") != info.get("fingerprint"):
            _hold(f"{id_}: manifest executable-subset digest disagrees with the "
                  "fresh recomputation")
    return {"status": "candidate-ok", "mode": mode,
            "basePublication": base_commit, "sourceCommit": candidate_commit,
            "requestId": request_doc["requestId"],
            "changedSkillIds": expected["changedSkillIds"],
            "reviewStageCounts": expected["reviewStageCounts"],
            "engineFreeze": "verified", "policySha256": request_doc["policySha256"],
            "expectedWrites": len(expected["writes"]),
            "informational": informational,
            "independentRecompute": "fresh upstream_updates plan/stage re-run"}


# ---------------------------------------------------------------------------
# control branch payloads (request + manifest + rolling state)
# ---------------------------------------------------------------------------


def _state_update(old_state, patch):
    state = dict(old_state) if isinstance(old_state, dict) else \
        {"schemaVersion": SCHEMA_VERSION}
    state.update(patch)
    for key, cap in (("processedRequestIds", PROCESSED_IDS_CAP),
                     ("holdReasons", HOLD_RECORDS_CAP),
                     ("integrationGaps", GAP_RECORDS_CAP)):
        value = state.get(key)
        if isinstance(value, list) and len(value) > cap:
            state[key] = value[-cap:]
    return state


def _state_bytes(state):
    data = hubcore.encoded(state)
    if len(data) > MAX_STATE_BYTES:
        _hold("control state exceeded its bounded size")
    return data


def control_payload(out_dir, *, base_commit, candidate_commit, mode,
                    staging_ref, manifest_extra, today, policy_bytes,
                    control_state=None):
    """Canonical control-branch payload: request + manifest + state + archive."""
    request_bytes, request_doc = build_request(mode, candidate_commit,
                                               base_commit, policy_bytes)
    manifest = {"schemaVersion": SCHEMA_VERSION, "pipeline": PUBLICATION_NAME,
                "mode": mode, "basePublication": base_commit,
                "sourceCommit": candidate_commit, "stagingRef": staging_ref,
                "requestId": request_doc["requestId"],
                "request": request_doc,
                "policySha256": request_doc["policySha256"],
                "createdAtUTC": today, **manifest_extra}
    manifest_bytes = hubcore.pretty(manifest)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        _hold("candidate manifest exceeded its bounded size")
    prior = control_state if isinstance(control_state, dict) else {}
    state = _state_update(prior, {
        "lastCheckUTC": today, "openRequestId": request_doc["requestId"],
        "pipelineStage": f"{mode}-requested",
        "lastRequestId": request_doc["requestId"],
        # hold/integration facts emitted by this scan must stay visible on the
        # control branch state (never drop them into the void)
        "holdReasons": manifest_extra.get("holdReasons")
        or prior.get("holdReasons") or [],
        "integrationGaps": manifest_extra.get("integrationGaps")
        or prior.get("integrationGaps") or []})
    out_dir = pathlib.Path(out_dir)
    write_payload_file(out_dir, CONTROL_REQUEST_FILE, request_bytes)
    write_payload_file(out_dir, CONTROL_MANIFEST_FILE, manifest_bytes)
    write_payload_file(out_dir, CONTROL_STATE_FILE, _state_bytes(state))
    archive = CONTROL_ARCHIVE_PREFIX + request_doc["requestId"] + "/"
    write_payload_file(out_dir, archive + CONTROL_REQUEST_FILE, request_bytes)
    write_payload_file(out_dir, archive + CONTROL_MANIFEST_FILE, manifest_bytes)
    write_payload_file(out_dir, CONTROL_CHANGES_FILE, hubcore.pretty({
        "schemaVersion": SCHEMA_VERSION,
        "mirror": [CONTROL_REQUEST_FILE, CONTROL_MANIFEST_FILE, CONTROL_STATE_FILE],
        "appendArchive": [archive],
    }))
    return {"request": request_doc, "requestBytes": request_bytes,
            "manifest": manifest, "manifestBytes": manifest_bytes,
            "state": state, "stateBytes": _state_bytes(state)}


def held_state_payload(out_dir, *, stage_root, today, control_state):
    """Held-only scan: actionable state on the control branch, no request."""
    stage = load_stage(stage_root)
    changed_ids, bumped, _pins = _stage_candidate_facts(stage)
    if changed_ids or stage["candidates"]:
        # a staged candidate tree is eligible-update authority even when
        # the manifest facts claim zero change (facts are never authority)
        _hold("stage carries candidates; use the candidate request path")
    facts = stage["facts"]
    hold_reasons = list(facts.get("holdReasons") or [])
    if not hold_reasons and not stage["held"] and not stage["deferred"]:
        _hold("nothing staged to hold; this is a no-op scan, not a held state")
    gaps = [{"code": "per-entry-pin-contract", "ids": sorted(stage["deferred"]),
             "detail": "awaiting the reviewed per-entry pin override"}] \
        if stage["deferred"] else []
    state = _state_update(control_state, {
        "lastCheckUTC": today, "pipelineStage": "held",
        "holdReasons": hold_reasons, "integrationGaps": gaps,
        "openRequestId": control_state.get("openRequestId")
        if isinstance(control_state, dict) else None})
    out_dir = pathlib.Path(out_dir)
    write_payload_file(out_dir, CONTROL_STATE_FILE, _state_bytes(state))
    write_payload_file(out_dir, CONTROL_CHANGES_FILE, hubcore.pretty({
        "schemaVersion": SCHEMA_VERSION,
        "mirror": [CONTROL_STATE_FILE],
        "closeOpenRequest": bool(state.get("openRequestId") is None),
    }))
    return {"state": state, "holdCount": len(hold_reasons)}


def read_control_payload(root, control_commit):
    """Parse the request/manifest/state committed on the control branch tip."""
    request_bytes = blob_at(root, control_commit, CONTROL_REQUEST_FILE,
                            "open request")
    if request_bytes is None:
        state_raw = blob_at(root, control_commit, CONTROL_STATE_FILE, "state")
        state = _canonical_json(state_raw, "state", MAX_STATE_BYTES) if state_raw else {}
        return {"status": "idle", "openRequest": None, "state": state}
    request_doc = _as_publication(lambda: at.parse_request_bytes(request_bytes))
    manifest_raw = blob_at(root, control_commit, CONTROL_MANIFEST_FILE, "manifest")
    if manifest_raw is None:
        _hold("control branch carries a request without its candidate manifest")
    manifest = _canonical_json(manifest_raw, "candidate manifest", MAX_MANIFEST_BYTES)
    if manifest.get("requestId") != request_doc["requestId"]:
        _hold("control manifest is not bound to the open request")
    state_raw = blob_at(root, control_commit, CONTROL_STATE_FILE, "state")
    state = _canonical_json(state_raw, "state", MAX_STATE_BYTES) if state_raw else {}
    return {"status": "open", "openRequest": request_doc,
            "manifest": manifest, "state": state}


def already_processed(state_doc, request_id):
    return request_id in (state_doc.get("processedRequestIds") or [])


def mark_processed(state_doc, request_id, *, extra=None):
    processed = list(state_doc.get("processedRequestIds") or [])
    if request_id not in processed:
        processed.append(request_id)
    return _state_update(state_doc, {
        "processedRequestIds": processed[-PROCESSED_IDS_CAP:],
        "lastRequestId": request_id, "openRequestId": None,
        **(extra or {})})


# ---------------------------------------------------------------------------
# relay payload build + reconstruction + validation
# ---------------------------------------------------------------------------


def build_relay_payload(signer_out_dir, request_doc, out_dir, *, info=None):
    """Metadata-only relay: .sig envelopes + authenticated receipt + indexes."""
    at.validate_request(dict(request_doc))
    signer_out = pathlib.Path(signer_out_dir)
    if signer_out.is_symlink() or not signer_out.is_dir():
        _hold("--signer-out must be a real directory")
    members = {}
    for path in sorted(signer_out.rglob("*")):
        if path.is_symlink():
            _hold(f"symlink in signer output: {path}")
        if not path.is_file():
            continue
        rel = path.relative_to(signer_out).as_posix()
        cls = at.relay_member_class(rel)
        if cls is None or cls in ("review", "feed"):
            continue  # JSON bodies stay at the immutable Hub candidate
        members[rel] = path.read_bytes()
    for required in (RECEIPT_REL, RECEIPT_SIG_REL):
        if required not in members:
            _hold(f"signer output lacks {required}")
    receipt = _canonical_json(members[RECEIPT_REL], RECEIPT_REL)
    if receipt.get("mode") != request_doc["mode"] or \
            receipt.get("sourceCommit") != request_doc["sourceCommit"]:
        _hold("signer receipt does not equal the request mode/sourceCommit")
    info = dict(info or {})
    relay_manifest = {"schemaVersion": SCHEMA_VERSION,
                      "requestId": request_doc["requestId"],
                      "mode": request_doc["mode"],
                      "anchorCommit": info.get("anchorCommit"),
                      "liveToolingCommit": info.get("liveToolingCommit"),
                      "liveToolingTree": info.get("liveToolingTree"),
                      "anchorEqualities": info.get("anchorEqualities"),
                      "runId": info.get("runId"), "runUrl": info.get("runUrl"),
                      "files": [{"path": rel, "sha256": hubcore.sha256_hex(data),
                                 "size": len(data)}
                                for rel, data in sorted(members.items())]}
    if at.derive_request_id(request_doc) != request_doc["requestId"]:
        _hold("request document is not internally consistent")
    request_bytes = hubcore.encoded(request_doc)
    out_dir = pathlib.Path(out_dir)
    root_rel = RELAY_REQUEST_DIR + request_doc["requestId"] + "/"
    for rel, data in sorted(members.items()):
        write_payload_file(out_dir, root_rel + rel, data)
    write_payload_file(out_dir, root_rel + RELAY_MANIFEST_FILE,
                       hubcore.pretty(relay_manifest))
    write_payload_file(out_dir, root_rel + CONTROL_REQUEST_FILE, request_bytes)
    state = _state_update(info.get("appState"), {
        "lastCheckUTC": info.get("today"),
        "lastSignedRequestId": request_doc["requestId"],
        "lastSignedMode": request_doc["mode"],
        "pipelineStage": f"{request_doc['mode']}-relayed"})
    write_payload_file(out_dir, RELAY_STATE_FILE, _state_bytes(state))
    return {"requestId": request_doc["requestId"], "mode": request_doc["mode"],
            "members": sorted(members), "relayManifest": relay_manifest,
            "rootRel": root_rel}


def rebuild_feeds(x_root, source_commit, trust=None):
    """Deterministic feed bytes exactly as the signer produced them at X."""
    registry = json.loads((pathlib.Path(x_root) / REGISTRY_REL).read_bytes())
    _as_publication(lambda: hubcore.validate_registry(registry))
    trust = trust or build_catalog.load_trust(x_root)
    if not trust:
        _hold("no public trust configured for the feed rebuild")
    outputs = _as_publication(
        lambda: build_catalog.build(registry, "release", source_commit,
                                    pathlib.Path(x_root),
                                    pathlib.Path(x_root), trust))
    return {rel: outputs[rel] for rel in sorted(cv.FEED_FILES)}


def assemble_relay_members(relay_dir, request_root_rel, repo_root,
                           source_commit, request_doc, *, feeds=None):
    """Reconstruct the full bounded metadata map for the settled validator."""
    relay_dir = pathlib.Path(relay_dir)
    base = relay_dir / request_root_rel
    if base.is_symlink() or not base.is_dir():
        _hold("relay request directory is missing or unsafe")
    members = {}
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            _hold(f"symlink in relay tree: {path}")
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        if rel in (RELAY_MANIFEST_FILE, CONTROL_REQUEST_FILE):
            continue
        if at.relay_member_class(rel) is None:
            _hold(f"unexpected relay member path: {rel}")
        members[rel] = path.read_bytes()
    for required in (RECEIPT_REL, RECEIPT_SIG_REL):
        if required not in members:
            _hold(f"relay lacks {required}")
    receipt = _canonical_json(members[RECEIPT_REL], RECEIPT_REL)
    if receipt.get("mode") != request_doc["mode"] or \
            receipt.get("sourceCommit") != request_doc["sourceCommit"]:
        _hold("relay receipt does not equal the request")
    by_path = {entry["path"]: entry for entry in receipt["outputs"]}
    for rel, entry in sorted(by_path.items()):
        cls = at.relay_member_class(rel)
        if cls in ("receipt", "receipt-sig"):
            continue
        if cls in ("feed", "review"):
            if rel in members:
                _hold("metadata relay must not carry JSON bodies")
            if rel in cv.FEED_FILES:
                if not feeds or rel not in feeds:
                    _hold(f"rebuilt feed bytes unavailable for {rel}")
                members[rel] = feeds[rel]
            else:
                blob = blob_at(repo_root, source_commit, rel, "review body")
                if blob is None:
                    _hold(f"candidate lacks review body {rel}")
                members[rel] = blob
            continue
        if cls in ("feed-sig", "review-sig"):
            if rel not in members:
                _hold(f"relay is missing the envelope bound by the receipt: {rel}")
            continue
        if rel.startswith(PACKAGE_PREFIXES + ("engines/",)):
            blob = blob_at(repo_root, source_commit, rel, "bound content")
            if blob is None:
                _hold(f"receipt-bound content {rel} is absent from the candidate")
            if hubcore.sha256_hex(blob) != entry["sha256"] or \
                    len(blob) != entry["size"]:
                _hold(f"receipt-bound content {rel} drifted from the candidate bytes")
            continue
        _hold(f"unclassifiable receipt output path: {rel}")
    bound_content = sorted(rel for rel in by_path
                           if rel.startswith(PACKAGE_PREFIXES + ("engines/",)))
    return members, bound_content


def relay_validate(relay_dir, request_doc, repo_root, source_commit, *,
                   feeds=None, trust=None):
    at.validate_request(dict(request_doc))
    if request_doc["sourceCommit"] != source_commit:
        _hold("relay verification sourceCommit is not the request source")
    trust = trust or build_catalog.load_trust(repo_root)
    root_rel = RELAY_REQUEST_DIR + request_doc["requestId"] + "/"
    members, bound = assemble_relay_members(relay_dir, root_rel, repo_root,
                                            source_commit, request_doc,
                                            feeds=feeds)
    verdict = _as_publication(lambda: at.validate_signed_relay(
        members, request_doc, trust))
    result = {k: v for k, v in verdict.items() if k != "files"}
    result["boundContentVerified"] = len(bound)
    result["memberPaths"] = sorted(verdict["files"])
    return result, verdict["files"]


# ---------------------------------------------------------------------------
# X reconstruction (minimal S -> full publication candidate)
# ---------------------------------------------------------------------------


def build_x_payload(repo_root, base_commit, s_commit, request_doc, relay_dir,
                    out_dir, *, trust=None):
    """X = S + every historical review pair from B + the new signed sidecars."""
    verdict, files = relay_validate(relay_dir, request_doc, repo_root, s_commit,
                                    trust=trust)
    base_tree = tree_at(repo_root, base_commit, "base")
    s_tree = tree_at(repo_root, s_commit, "stage S")
    receipt = _canonical_json(files[RECEIPT_REL], RECEIPT_REL)
    by_path = {entry["path"]: entry for entry in receipt["outputs"]}
    writes = {}
    for rel, entry in sorted(base_tree.items()):
        if not rel.startswith("reviews/"):
            continue
        if rel in s_tree:
            if s_tree[rel] != entry:
                _hold(f"S mutated a historical review path before restore: {rel}")
            continue
        blob = blob_at(repo_root, base_commit, rel, "base review")
        if blob is None:
            _hold(f"historical review blob unreadable: {rel}")
        writes[rel] = blob
    for rel, data in sorted(files.items()):
        if rel.endswith(".sig") and rel.startswith("reviews/"):
            record_rel = rel[: -len(".sig")]
            if record_rel not in s_tree and record_rel not in writes:
                _hold(f"relayed envelope has no candidate record: {record_rel}")
            if hubcore.sha256_hex(data) != by_path[rel]["sha256"]:
                _hold(f"relayed envelope drifted: {rel}")
            writes[rel] = data
    payload = {"writes": writes, "deletions": [],
               "S": s_commit, "basePublication": base_commit,
               "requestId": request_doc["requestId"],
               "reviewsRelayVerdict": {k: verdict[k] for k in
                                       ("status", "requestId", "mode",
                                        "reviewRecordCount")}}
    out_dir = pathlib.Path(out_dir)
    for rel, data in sorted(writes.items()):
        write_payload_file(out_dir / "snapshot", rel, data)
    (out_dir / "changes.json").write_bytes(hubcore.pretty(
        {k: v for k, v in payload.items() if k != "writes"}))
    return payload


# ---------------------------------------------------------------------------
# Y + H publication payloads + final chain proof
# ---------------------------------------------------------------------------


def build_y_payload(request_doc, relay_dir, repo_root, feeds, out_dir, *,
                    trust=None):
    verdict, files = relay_validate(relay_dir, request_doc, repo_root,
                                    request_doc["sourceCommit"], feeds=feeds,
                                    trust=trust)
    _as_publication(lambda: cv.assert_projection(feeds))
    writes = {}
    for channel in cv.VIEWS:
        feed_rel, sig_rel = FEED_PATHS[channel]
        if feed_rel not in feeds or sig_rel not in files:
            _hold(f"{channel} feed pair incomplete")
        writes[feed_rel] = feeds[feed_rel]
        writes[sig_rel] = files[sig_rel]
    payload = {"writes": writes, "deletions": [],
               "requestId": request_doc["requestId"],
               "sourceCommit": request_doc["sourceCommit"]}
    out_dir = pathlib.Path(out_dir)
    for rel, data in sorted(writes.items()):
        write_payload_file(out_dir / "snapshot", rel, data)
    (out_dir / "changes.json").write_bytes(hubcore.pretty(
        {k: v for k, v in payload.items() if k != "writes"}))
    return verdict, payload


def expected_ledger_bytes(repo_root, base_commit, y_commit):
    """(base_rows, new_rows, canonical expected ledger bytes) for ORIGINAL Y.

    Central proof helper: H's ledger must equal EXACTLY these bytes, so every
    recovery path re-derives the expectation from the ORIGINAL committed Y —
    never by rebuilding a fresh timestamped Y'/H' that could never match.
    """
    hubcore.require_commit(y_commit, "publication commit Y")
    base_ledger = blob_at(repo_root, base_commit, LEDGER_REL, "base ledger")
    if base_ledger is None:
        _hold("base ledger blob missing")
    doc = _canonical_json(base_ledger, "base ledger")
    rows = doc["publications"]
    new_rows = []
    for channel in cv.VIEWS:
        if blob_at(repo_root, y_commit, FEED_PATHS[channel][0], "y feed") is None:
            continue
        row = _as_publication(lambda: pi.build_ledger_row(pathlib.Path(repo_root),
                                                          y_commit, channel))
        new_rows.append(row)
    if not new_rows:
        _hold("Y carries no published feed to ledger")
    ledger_bytes = pi.render_ledger(rows + new_rows,
                                    description=doc.get("description",
                                                        pi.LEDGER_DESCRIPTION))
    return rows, new_rows, ledger_bytes


def build_h_payload(repo_root, base_commit, y_commit, out_dir):
    """H = Y + the cumulative ledger with newly verified rows appended."""
    rows, new_rows, ledger_bytes = expected_ledger_bytes(repo_root, base_commit,
                                                         y_commit)
    out_dir = pathlib.Path(out_dir)
    write_payload_file(out_dir / "snapshot", LEDGER_REL, ledger_bytes)
    base_ledger_raw = blob_at(repo_root, base_commit, LEDGER_REL, "base ledger")
    payload = {"writes": [LEDGER_REL],
               "historicalRowsRetained": len(rows),
               "appendedRows": len(new_rows),
               "newRowPublications": sorted({row["publication"] for row in new_rows}),
               "baseLedgerSha256": hubcore.sha256_hex(base_ledger_raw)}
    (out_dir / "changes.json").write_bytes(hubcore.pretty(payload))
    return payload, ledger_bytes


def verify_publication_diffs(root, base_commit, x_commit, y_commit, h_commit):
    """Prove the whole chain stays lawful around the CAS."""
    base_tree = tree_at(root, base_commit, "base")
    x_tree = tree_at(root, x_commit, "X")
    y_tree = tree_at(root, y_commit, "Y")
    h_tree = tree_at(root, h_commit, "H")
    added, removed, modified = tree_diff(x_tree, y_tree)
    if removed:
        _hold("Y deleted paths from X")
    if sorted(set(added) | set(modified)) != sorted(
            cv.ARTIFACT_FILES):
        _hold("Y deviates from X beyond the signed feed pair")
    added, removed, modified = tree_diff(y_tree, h_tree)
    if removed or sorted(set(added) | set(modified)) != [LEDGER_REL]:
        _hold("H changes anything except the cumulative ledger")
    added, removed, modified = tree_diff(base_tree, h_tree)
    for rel in added + removed + modified:
        if rel in DENIED_EXACT or rel.startswith(DENIED_PREFIXES):
            _hold(f"publication touches a denied path end-to-end: {rel}")
        if not (rel in PUBLISH_ALLOW_EXACT
                or any(rel.startswith(p) for p in PUBLISH_ALLOW_DIRS)):
            _hold(f"publication path is outside the allowlist: {rel}")
    if not _as_publication(lambda: at.is_descendant(root, base_commit, h_commit)):
        _hold("H is not a descendant of the live base B")
    _as_publication(lambda: at.verify_candidate_engine_freeze(root, base_commit,
                                                              x_commit))
    # X carries the full frozen-history proof; Y/H differ from X ONLY by the
    # exact feed pair / ledger checks above, so the review+archive preservation
    # transitively covers H without mislabeling the publication itself.
    assert_frozen_history(base_tree, x_tree, "catalog", "X")
    ledger_raw = blob_at(root, h_commit, LEDGER_REL, "h ledger")
    base_ledger_raw = blob_at(root, base_commit, LEDGER_REL, "base ledger")
    # Append-only ordered-prefix retention of the OLD base rows is enforced
    # EXPLICITLY here (the tempfile verify_ledger below cannot run the
    # canonical-path append guard): byte-identical prefix, no deletion,
    # rewrite, reorder or duplicate — and H's ledger must equal EXACTLY
    # base rows + the rows derived from the ORIGINAL committed Y.
    _as_publication(lambda: at.verify_ledger_continuity(base_ledger_raw,
                                                        ledger_raw))
    _base_rows, new_rows, expected_ledger = expected_ledger_bytes(
        root, base_commit, y_commit)
    if ledger_raw != expected_ledger:
        _hold("H ledger bytes are not exactly base-rows + the rows derived "
              "from the original committed Y (no rebuilt-commit comparison, "
              "no reordering, no extra rows)")
    published_channels = {channel for channel in cv.VIEWS
                          if blob_at(root, y_commit, FEED_PATHS[channel][0],
                                     "y feed") is not None}
    if {row["channel"] for row in new_rows} != published_channels:
        _hold("appended ledger rows do not cover every channel published at Y")
    tmp = tempfile.TemporaryDirectory(prefix="floe-auto-pub-h-")
    try:
        path = pathlib.Path(tmp.name) / "publication-ledger.json"
        path.write_bytes(ledger_raw)
        _as_publication(lambda: pi.verify_ledger(path, pathlib.Path(root)))
    finally:
        tmp.cleanup()
    return {"status": "publication-diffs-ok", "mainAdvance": "B->H exactly once",
            "changedPathsBtoH": sorted(set(added) | set(modified)),
            "ledgerRowsAppended": len(new_rows)}


# ---------------------------------------------------------------------------
# crash-resumable publisher planning (bounded, cryptographically re-verified)
# ---------------------------------------------------------------------------


def verify_published_chain(root, base_commit, x_commit, y_commit, h_commit,
                           request_doc, relay_dir, *, x_root,
                           fresh_stage_root, manifest_doc,
                           trust=None,
                           expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """ONE centralized proof for both H-recovery paths (CAS retry and
    already-published close) and for direct workflow checks: the ORIGINAL
    committed Y/H are verified against expectations derived from immutable
    inputs — never against freshly rebuilt timestamped commits.

      * structural chain: X -> Y feeds-only -> H ledger-only, B..H allow/
        deny, engine + historical-review freezes, append-only ledger
        continuity and exact expected ledger bytes over the ORIGINAL Y
        (verify_publication_diffs);
      * relay binding: the catalog relay receipt's feed signatures verify
        over the locally REBUILT deterministic feed bytes at X, and those
        rebuilt bytes must equal the committed Y feed blobs byte-for-byte;
      * candidate binding: the full verify_candidate (catalog mode) over the
        committed X is REQUIRED on every path — no published-chain proof
        (recover, CLI or direct API) ever completes without the fresh
        re-derivation stage and the request-bound manifest.
    """
    if fresh_stage_root is None or manifest_doc is None:
        _hold("the full candidate proof is required for any published-chain "
              "verification: pass the fresh re-derivation --stage-root and "
              "the request-bound --manifest-file (no proof-light close)")
    chain = verify_publication_diffs(root, base_commit, x_commit, y_commit,
                                     h_commit)
    trust = trust or build_catalog.load_trust(root)
    feeds = rebuild_feeds(x_root, x_commit, trust=trust)
    for channel in cv.VIEWS:
        rel = FEED_PATHS[channel][0]
        committed = blob_at(root, y_commit, rel, "Y feed")
        if committed != feeds[rel]:
            _hold(f"committed Y {channel} feed is not the deterministic local "
                  "rebuild over X")
    relay_verdict, _files = relay_validate(relay_dir, request_doc, root,
                                           x_commit, feeds=feeds, trust=trust)
    proof = {"chain": chain,
             "relay": {k: relay_verdict[k] for k in
                       ("status", "requestId", "mode", "reviewRecordCount",
                        "boundContentVerified")},
             "candidate": verify_candidate(
                 root, request_doc, manifest_doc,
                 blob_at(root, base_commit, POLICY_REL, "policy"),
                 fresh_stage_root=fresh_stage_root, trust=trust,
                 expected_base=base_commit, expect_counts=expect_counts)}
    return proof


def recover_publish_plan(root, request_doc, manifest_doc, policy_bytes, *,
                         live_main, candidate_tip, fresh_stage_root,
                         relay_dir=None, trust=None, x_root=None,
                         expect_counts=LIVE_REGISTRY_EXPECT_COUNTS):
    """Decide the safe publisher action when the candidate ref tip has already
    advanced past the open request (a previous run pushed X or H before its
    control write / CAS / close, or CAS succeeded but closing failed).

    Every reuse decision is cryptographically re-verified from public objects
    here or by the following authoritative steps, and NOTHING resumes while
    live main has moved off the request base — except the intentional
    published close, which is precisely the case where live main EQUALS the
    recovered H and demands the SAME full proof as the CAS recovery. Nothing
    is ever forced:
      * reviews request, live main == request base, tip == sourceCommit(S)
                                                                   -> "advance-from-request"
      * reviews request, live main == request base, tip is an exact S->X
        restore of the ORIGINAL B with the relay-bound sidecars (built from
        the fresh re-derivation) and S is its ancestor       -> "reuse-x"
      * catalog request, live main == tip(H)                        -> "close-published"
      * catalog request, live main == request base, tip == X        -> "advance-from-request"
      * catalog request, tip = X -> Y -> H linear, chain proofs pass,
        live main still equals the request base                       -> "cas-existing-h"
      * anything else (incl. any stale live main on an advance/reuse path)
                                                                   -> PublicationError HOLD
    reuse-x must be followed by the standard verify-candidate (catalog mode)
    and the canonical signing flow over the SAME committed tip; cas-existing-h
    re-issues the exact CAS (same H, same base) without re-signing or
    rebuilding any historical object; close-published only records idempotent
    completion after direct public verification.
    """
    at.validate_request(dict(request_doc))
    mode = request_doc["mode"]
    base_commit = request_doc["basePublication"]
    source_commit = request_doc["sourceCommit"]
    hubcore.require_commit(live_main, "live main")
    hubcore.require_commit(candidate_tip, "candidate tip")
    if not isinstance(manifest_doc, dict) \
            or manifest_doc.get("requestId") != request_doc["requestId"]:
        _hold("recover requires the manifest bound to this request")
    if mode == "reviews" and live_main != base_commit:
        _hold(f"live main {live_main[:10]} is not the reviews request base "
              f"{base_commit[:10]}: a reviews advance/reuse only resumes while "
              "main still equals the base the candidate was built on; an "
              "unrelated advance must supersede this pipeline, never resume "
              "onto it")
    if candidate_tip == source_commit and mode == "reviews":
        return {"action": "advance-from-request", "mode": mode,
                "requestId": request_doc["requestId"],
                "candidateTip": candidate_tip}
    if mode == "reviews":
        if relay_dir is None:
            _hold("tip advanced beyond S for a reviews request but no relay "
                  "directory is available to re-verify the committed X")
        if not _as_publication(lambda: at.is_descendant(root, source_commit,
                                                        candidate_tip)):
            _hold("candidate tip does not descend from the request sourceCommit")
        tmp = tempfile.TemporaryDirectory(prefix="floe-recover-x-")
        try:
            expected = build_x_payload(root, base_commit, source_commit,
                                       request_doc, relay_dir, tmp.name,
                                       trust=trust)
        finally:
            tmp.cleanup()
        s_tree = tree_at(root, source_commit, "S")
        tip_tree = tree_at(root, candidate_tip, "tip X")
        expected_paths = set(s_tree) | set(expected["writes"])
        extra = sorted(set(tip_tree) - expected_paths)
        missing = sorted(expected_paths - set(tip_tree))
        if extra or missing:
            _hold(f"tip does not equal the exact S->X restore "
                  f"(extra={extra[:8]}, missing={missing[:8]})")
        for rel, data in sorted(expected["writes"].items()):
            if blob_at(root, candidate_tip, rel, "tip blob") != data:
                _hold(f"tip blob deviates from the expected X member: {rel}")
        for rel, entry in sorted(s_tree.items()):
            if tip_tree.get(rel) != entry:
                _hold(f"tip mutated an S-side path: {rel}")
        return {"action": "reuse-x", "mode": mode, "x": candidate_tip,
                "requestId": request_doc["requestId"],
                "next": "verify-candidate(catalog) then emit-catalog-request "
                        "for this exact tip; never rebuild a different X"}
    if candidate_tip == source_commit:
        if live_main != base_commit:
            _hold(f"live main {live_main[:10]} is not the catalog request base "
                  f"{base_commit[:10]}: advancing a catalog request from the "
                  "tip only resumes while main still equals the request base")
        return {"action": "advance-from-request", "mode": mode,
                "requestId": request_doc["requestId"],
                "candidateTip": candidate_tip}
    if live_main != base_commit and live_main != candidate_tip:
        _hold(f"live main {live_main[:10]} is neither the request base "
              f"{base_commit[:10]} nor the candidate tip; an unrelated "
              "advance must supersede this pipeline, never force over it")
    if relay_dir is None or x_root is None:
        _hold("H-chain recovery requires the catalog relay directory and a "
              "materialized X checkout to re-prove the ORIGINAL chain (no "
              "proof-free close, no rebuilt-commit comparison)")
    # ORIGINAL-Y semantics (frozen contract): resolve Y = tip^, require
    # the single-parent X -> Y -> H chain over the request sourceCommit;
    # never rebuild a timestamped Y'/H' for comparison.
    y_commit = _git_out(root, ["rev-parse", "--verify", f"{candidate_tip}^"],
                        "H parent Y").decode("ascii", "strict").strip()
    x_commit = _git_out(root, ["rev-parse", "--verify", f"{candidate_tip}^^"],
                        "Y parent X").decode("ascii", "strict").strip()
    h_parents = _git_out(root, ["rev-list", "--parents", "-n", "1",
                                candidate_tip], "H parents").decode().split()
    y_parents = _git_out(root, ["rev-list", "--parents", "-n", "1",
                                y_commit], "Y parents").decode().split()
    if len(h_parents) != 2 or len(y_parents) != 2:
        _hold("recovered chain is not strictly single-parent X -> Y -> H")
    if x_commit != source_commit:
        _hold("recovered H is not a linear X -> Y -> H chain over the request "
              "sourceCommit")
    proof = verify_published_chain(root, base_commit, x_commit, y_commit,
                                   candidate_tip, request_doc, relay_dir,
                                   x_root=x_root,
                                   fresh_stage_root=fresh_stage_root,
                                   manifest_doc=manifest_doc, trust=trust,
                                   expect_counts=expect_counts)
    if live_main == candidate_tip:
        return {"action": "close-published", "mode": mode, "h": candidate_tip,
                "y": y_commit, "x": x_commit,
                "requestId": request_doc["requestId"], "proof": proof,
                "next": "the CAS already succeeded in a previous run: verify "
                        "public bytes/history directly, then mark-processed "
                        "idempotently (same full proof as the CAS recovery)"}
    return {"action": "cas-existing-h", "mode": mode, "base": base_commit,
            "y": y_commit, "h": candidate_tip, "x": x_commit,
            "requestId": request_doc["requestId"], "proof": proof,
            "next": "re-issue the exact CAS for the SAME original H (no "
                    "re-signing, no rebuild, no new commits), then verify "
                    "public and close processed"}


# ---------------------------------------------------------------------------
# exact CAS through the GitHub GraphQL updateRefs (live-proved mechanism)
# ---------------------------------------------------------------------------


def _graphql_queries():
    # ACTUAL GitHub GraphQL schema (live-proved exact-CAS shape): repository
    # node id + ref(qualifiedName:) for the base read, and
    # updateRefs(input: UpdateRefsInput!) with named RefUpdate entries for
    # the compare-and-set. Invented refPrefix/refId/oid arguments are not
    # valid schema and would be refused by the real endpoint.
    fetch = ("query casBase($owner: String!, $name: String!, "
             "$qualifiedName: String!) {"
             " repository(owner: $owner, name: $name) {"
             " id"
             " ref(qualifiedName: $qualifiedName) { target { oid } } } }")
    mutate = ("mutation casPublish($input: UpdateRefsInput!) {"
              " updateRefs(input: $input) { clientMutationId } }")
    return fetch, mutate


def default_graphql_transport(token):
    """POST one GraphQL payload to the FIXED endpoint; token strictly env-fed."""
    if not token:
        _hold("no API token present in the environment; the CAS never accepts "
              "caller-supplied secrets")

    def send(query, variables):
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = urllib.request.Request(
            GRAPHQL_ENDPOINT, data=body, method="POST",
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json",
                     "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)
                raw = response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except OSError as error:
            raise PublicationError(
                f"fixed GraphQL endpoint unreachable: {error}") from None
        try:
            return status, json.loads(raw)
        except ValueError:
            raise PublicationError(
                f"GraphQL response is not JSON (status {status})") from None
    return send


def _require_graphql_ok(status, payload, field):
    # GitHub returns HTTP 200 with an errors array for refused mutations
    if isinstance(payload, dict) and payload.get("errors"):
        messages = "; ".join(str(item.get("message", item))
                             for item in payload["errors"][:4])
        raise PublicationError(f"{field}: GraphQL refused (status {status}): "
                               f"{messages}")
    if status != 200:
        raise PublicationError(f"{field}: unexpected HTTP status {status}")


def cas_publish(base_commit, head_commit, *, token_env="GITHUB_TOKEN",
                transport=None, dry_run=False):
    """Exact CAS of refs/heads/main: beforeOid=B, afterOid=H, force=false."""
    hubcore.require_commit(base_commit, "CAS base B")
    hubcore.require_commit(head_commit, "CAS head H")
    if not ENV_TOKEN_PATTERN.fullmatch(token_env or ""):
        _hold("token_env must name an environment variable, never carry a value")
    plan = {"endpoint": GRAPHQL_ENDPOINT,
            "repository": f"{CAS_OWNER}/{CAS_REPO_NAME}", "ref": CAS_REF,
            "beforeOid": base_commit, "afterOid": head_commit, "force": False,
            "mutation": "updateRefs(input:UpdateRefsInput!) RefUpdate.beforeOid "
                        "exact CAS (live-proved shape: repository.id + "
                        "ref(qualifiedName))",
            "liveEvidence": "the live-proved GitHub GraphQL updateRefs CAS: a "
                            "stale beforeOid is refused with refs unchanged; "
                            "GraphQL errors are checked even at HTTP 200"}
    if dry_run:
        return {"status": "cas-planned", **plan}
    fetch, mutate = _graphql_queries()
    variables = {"owner": CAS_OWNER, "name": CAS_REPO_NAME,
                 "qualifiedName": CAS_REF}
    transport = transport or default_graphql_transport(os.environ.get(token_env))
    status, payload = transport(fetch, variables)
    _require_graphql_ok(status, payload, "CAS base query")
    try:
        repository = payload["data"]["repository"]
        ref = repository["ref"]
        repository_id, live_oid = repository["id"], ref["target"]["oid"]
    except (KeyError, TypeError) as error:
        raise PublicationError(
            f"CAS base query returned an unusable shape: {error}") from None
    if not isinstance(repository_id, str) or not repository_id:
        _hold("CAS base query carried no repository node id; the exact CAS "
              "cannot address updateRefs without it")
    if live_oid == head_commit:
        return {"status": "cas-already-published", "liveOid": live_oid,
                "head": head_commit}
    if live_oid != base_commit:
        _hold(f"live main moved ({live_oid[:10]} != B {base_commit[:10]}); the "
              "exact CAS aborts and the candidate rebases on the next scan")
    status, payload = transport(mutate, {"input": {
        "clientMutationId": CAS_MUTATION_ID, "repositoryId": repository_id,
        "refUpdates": [{"name": CAS_REF, "beforeOid": base_commit,
                        "afterOid": head_commit, "force": False}]}})
    _require_graphql_ok(status, payload, "CAS updateRefs")
    try:
        echoed = payload["data"]["updateRefs"]["clientMutationId"]
    except (KeyError, TypeError) as error:
        raise PublicationError(f"CAS response shape unusable: {error}") from None
    if echoed != CAS_MUTATION_ID:
        _hold("CAS mutation echo drifted")
    status, payload = transport(fetch, variables)
    _require_graphql_ok(status, payload, "CAS re-read")
    after_oid = payload["data"]["repository"]["ref"]["target"]["oid"]
    if after_oid != head_commit:
        _hold("post-CAS live main does not equal H")
    return {"status": "cas-published", "base": base_commit, "head": head_commit,
            "liveOid": after_oid}


def fetch_public_raw(commit_or_ref, rel, *, repo=at.OFFICIAL_HUB_REPO,
                     max_bytes=32_000_000, transport=None):
    """Tokenless raw read of one official repository path at a ref/commit."""
    if repo not in (at.OFFICIAL_HUB_REPO, at.OFFICIAL_APP_REPO):
        _hold("raw reads are restricted to the fixed official repositories")
    if not (at.COMMIT_40.fullmatch(commit_or_ref)
            or at.BRANCH_NAME_RE.fullmatch(commit_or_ref or "")):
        _hold("raw ref must be a 40-hex commit or a plain branch name")
    if rel.startswith("/") or ".." in rel.split("/") or "\0" in rel:
        _hold("unsafe raw path")
    url = f"{RAW_HOST}/{repo}/{commit_or_ref}/{rel}"
    if transport is not None:
        data = transport(url)
    else:
        request = urllib.request.Request(
            url, headers={"User-Agent": "floe-skill-hub-automation"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(max_bytes + 1)
        except OSError as error:
            raise PublicationError(f"fixed raw host unreachable: {error}") from None
    if len(data) > max_bytes:
        _hold(f"raw response exceeds {max_bytes} bytes: {url}")
    return url, data


def relay_exists(request_id, *, ref=RELAY_BRANCH, transport=None):
    """True when the App relay already carries a request directory."""
    if not hubcore.HEX64_PATTERN.fullmatch(request_id):
        _hold("requestId must be hex64")
    try:
        _url, data = fetch_public_raw(
            ref, RELAY_REQUEST_DIR + request_id + "/" + RELAY_MANIFEST_FILE,
            repo=at.OFFICIAL_APP_REPO, transport=transport)
    except PublicationError:
        return False, None
    if not data:
        return False, None
    return True, data


def verify_public_main(head_commit, x_commit, *, trust_root, base_commit=None,
                       transport=None):
    """After the CAS, verify the ACTUAL public bytes directly (no CI re-run).

    This readback attests nothing it cannot prove: every downloaded object
    must be byte-exact against the locally authenticated committed object at
    H, cryptographically valid under the official production trust, and the
    FULL ledger must independently pass signature verification over the
    committed feed pins.  Fail-closed coverage:

      * per channel the public feed and signature bytes must equal the blobs
        committed at H; the envelope must verify under production trust with
        the production key id; the feed must be canonical, schema-valid and
        bind the verified source X as its sourceCommit;
      * the public ledger bytes must equal the ledger committed at H and pass
        publication_immutability.verify_ledger (every historical row's
        signature, feed digest, channel and offers re-verified against the
        committed publication pin; fixture identity refused);
      * when the request base is supplied, the base ledger must be retained
        as the exact append-only prefix (old rows can never be rewritten,
        reordered, duplicated or deleted);
      * the two newest ledger rows must cover BOTH published channels exactly
        once, and each channel's newest row must quote the digest of the feed
        actually published at H.

    A missing object, a wrong body, a wrong key, a malformed ledger, an
    old-row rewrite or a stale/mischannelled newest row all fail closed.
    """
    root = pathlib.Path(trust_root)
    hubcore.require_commit(head_commit, "public head H")
    hubcore.require_commit(x_commit, "verified X")
    if base_commit is not None:
        hubcore.require_commit(base_commit, "request base B")
    trust = build_catalog.load_trust(root)
    results = {}
    for channel in cv.VIEWS:
        feed_rel, sig_rel = FEED_PATHS[channel]
        _url, feed = fetch_public_raw(head_commit, feed_rel, transport=transport)
        _url, sig = fetch_public_raw(head_commit, sig_rel, transport=transport)
        for rel, data in ((feed_rel, feed), (sig_rel, sig)):
            committed = blob_at(root, head_commit, rel, f"H {rel}")
            if committed is None:
                _hold(f"no locally authenticated committed object at H for "
                      f"{rel}; the public readback never attests against an "
                      "absent reference")
            if data != committed:
                _hold(f"public {channel} {rel} bytes are not byte-exact with "
                      f"the object committed at H ({hubcore.sha256_hex(data)[:10]} "
                      f"!= {hubcore.sha256_hex(committed)[:10]})")
        key_id = _as_publication(lambda: hubcore.verify_envelope(feed, sig, trust))
        if key_id != hubcore.PRODUCTION_KEY_ID:
            _hold(f"public {channel} feed identity drifted")
        doc = _canonical_json(feed, f"public {channel} feed")
        _as_publication(lambda: cv.validate_view(doc, channel))
        if doc["sourceCommit"] != x_commit:
            _hold(f"public {channel} feed sourceCommit is not the verified X")
        results[channel] = {"sha256": hubcore.sha256_hex(feed),
                            "entries": len(doc["entries"]),
                            "signatureKeyId": key_id,
                            "byteExactWithH": True}
    _url, ledger_raw = fetch_public_raw(head_commit, LEDGER_REL,
                                       transport=transport)
    committed_ledger = blob_at(root, head_commit, LEDGER_REL, "H ledger")
    if committed_ledger is None:
        _hold("no locally authenticated ledger object at H to attest the "
              "public ledger against")
    if ledger_raw != committed_ledger:
        _hold("public ledger bytes are not byte-exact with the ledger "
              "committed at H")
    doc = _canonical_json(ledger_raw, "public ledger")
    rows = doc["publications"]
    tmp = tempfile.TemporaryDirectory(prefix="floe-auto-pub-readback-")
    try:
        path = pathlib.Path(tmp.name) / "publication-ledger.json"
        path.write_bytes(ledger_raw)
        _as_publication(lambda: pi.verify_ledger(path, root))
    finally:
        tmp.cleanup()
    prefix_status = "skipped (request base not supplied to the readback)"
    if base_commit is not None:
        base_ledger = blob_at(root, base_commit, LEDGER_REL, "base ledger")
        if base_ledger is None:
            _hold("base ledger blob missing at the request base; append-only "
                  "continuity cannot be attested")
        _as_publication(lambda: at.verify_ledger_continuity(base_ledger,
                                                            ledger_raw))
        prefix_status = "base rows retained as the exact append-only prefix"
    if len(rows) < len(results):
        _hold("public ledger does not carry a newest row to quote the digest for each published "
              "channel")
    by_channel = {}
    for row in rows[-len(results):]:
        channel = row["channel"]
        if channel not in results or channel in by_channel:
            _hold("the newest ledger rows do not cover the published channels "
                  "exactly once (missing, duplicated or wrong-channel row)")
        by_channel[channel] = row
    if len({row["publication"] for row in by_channel.values()}) != 1:
        _hold("newest catalog views must share the same immutable publication Y")
    for channel, info in results.items():
        if by_channel[channel]["feedSha256"] != info["sha256"]:
            _hold(f"the newest {channel} ledger row does not quote the digest "
                  "of the feed actually published at H")
    return {"status": "public-verified", "head": head_commit,
            "sourceX": x_commit, "feeds": results,
            "ledgerRows": len(rows), "ledgerCryptoVerified": True,
            "ledgerPrefix": prefix_status,
            "newestRowCoverage": {channel: by_channel[channel]["publication"]
                                  for channel in sorted(by_channel)}}


# ---------------------------------------------------------------------------
# payload application helper (used by workflows; pure local file writes)
# ---------------------------------------------------------------------------


def apply_payload(payload_dir, repo_root):
    """Apply a changes.json + snapshot/ payload into a checkout working tree."""
    payload_dir = pathlib.Path(payload_dir)
    repo_root = pathlib.Path(repo_root)
    changes = _canonical_json((payload_dir / "changes.json").read_bytes(),
                              "payload changes", MAX_MANIFEST_BYTES)
    snap = payload_dir / "snapshot"
    applied_w = 0
    for rel in changes.get("deletions") or []:
        target = repo_root / rel
        if target.is_symlink() or (target.exists() and not target.is_file()):
            _hold(f"deletion target is not a regular file: {rel}")
        if target.exists():
            target.unlink()
    for path in sorted(snap.rglob("*")) if snap.is_dir() else []:
        if not path.is_file():
            continue
        rel = path.relative_to(snap).as_posix()
        target = repo_root / rel
        if target.is_symlink():
            _hold(f"payload target is a symlink: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        applied_w += 1
    return {"writes": applied_w,
            "deletions": len(changes.get("deletions") or [])}


def plan_control_update(payload_dir, current_state, current_request_doc,
                        live_main, today):
    """Deterministic control-branch merge decision for the scan job.

    payload_dir: a control payload (candidate request or held-state), or None
    for a no-op checkpoint. current_request_doc: the currently open request
    (None when idle). Rules (no silent overwrite, bounded state):
      * open request whose basePublication still equals live main -> the
        pipeline is busy: the scan pushes at most a bounded state checkpoint
        and never replaces the open request;
      * open request with a stale basePublication -> supersede honestly: the
        old request is closed in state (never re-processable), archived under
        requests/, and the new request takes the root slot;
      * idle -> apply the payload as-is.
    Returns {"action": "idle|busy-checkpoint|supersede-apply|apply",
             "state": new state doc, "mirror": files the workflow must place
             at root, "removeRoot": [files], "appendArchive": [dirs]}.
    """
    _require_commit40(live_main, "live main")
    payload_dir = pathlib.Path(payload_dir) if payload_dir else None
    base_state = dict(current_state or {"schemaVersion": SCHEMA_VERSION})
    payload_files, payload_archive, changes, payload_state = [], [], None, None
    if payload_dir and (payload_dir / CONTROL_CHANGES_FILE).is_file():
        changes = _canonical_json((payload_dir / CONTROL_CHANGES_FILE).read_bytes(),
                                  "control changes", MAX_MANIFEST_BYTES)
        payload_files = list(changes.get("mirror") or [])
        payload_archive = list(changes.get("appendArchive") or [])
    ps_path = payload_dir / CONTROL_STATE_FILE if payload_dir else None
    if ps_path is not None and ps_path.is_file():
        payload_state = _canonical_json(ps_path.read_bytes(), "payload state",
                                       MAX_STATE_BYTES)
    open_request = current_request_doc
    if open_request is not None:
        at.validate_request(dict(open_request))
    has_new_request = bool(changes and CONTROL_REQUEST_FILE in payload_files)
    if open_request is not None and has_new_request:
        if open_request["basePublication"] == live_main:
            # busy: NEVER replace the in-flight state (its openRequestId,
            # pipelineStage and holds must survive untouched)
            state = _state_update(base_state, {
                "note": "scan deferred: a request bound to the live base is "
                        "still in flight"})
            return {"action": "busy-checkpoint", "state": state,
                    "mirror": [CONTROL_STATE_FILE], "removeRoot": [],
                    "appendArchive": [], "today": today,
                    "payloadDir": str(payload_dir) if payload_dir else None}
        base_state = _state_update(base_state, {
            "closedStaleRequestIds": sorted(set(
                base_state.get("closedStaleRequestIds") or [])
                | {open_request["requestId"]})[:PROCESSED_IDS_CAP],
            "note": "stale request superseded by a fresh scan against the "
                     "current live base"})
        action = "supersede-apply"
    else:
        action = "apply" if payload_dir else "idle"
    if payload_state is not None:
        # the freshly emitted payload state carries the authoritative NEW
        # facts (openRequestId/pipelineStage/holdReasons/integrationGaps);
        # history-bearing lists from the current state are unioned, never
        # dropped, and bounded by _state_update
        merged = dict(base_state)
        for key, value in payload_state.items():
            if key == "processedRequestIds":
                merged[key] = list(dict.fromkeys(
                    list(base_state.get("processedRequestIds") or [])
                    + list(value or [])))
            else:
                merged[key] = value
        new_state = _state_update(merged, {})
    else:
        new_state = _state_update(base_state, {"lastCheckUTC": today})
    close_open = bool(changes and changes.get("closeOpenRequest") is True)
    remove_root = ([CONTROL_REQUEST_FILE, CONTROL_MANIFEST_FILE]
                   if close_open else [])
    return {"action": action, "state": new_state,
            "mirror": payload_files or [CONTROL_STATE_FILE],
            "removeRoot": remove_root, "appendArchive": payload_archive,
            "today": today, "payloadDir": str(payload_dir) if payload_dir else None}


def write_control_plan_output(out_dir, plan):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"schemaVersion": SCHEMA_VERSION, "action": plan["action"],
                "mirror": plan["mirror"], "removeRoot": plan["removeRoot"],
                "appendArchive": plan["appendArchive"]}
    write_payload_file(out, "control-plan.json", hubcore.pretty(manifest))
    write_payload_file(out, CONTROL_STATE_FILE, _state_bytes(plan["state"]))
    payload_dir = plan.get("payloadDir")
    if payload_dir:
        src_dir = pathlib.Path(payload_dir)
        for rel in plan["mirror"]:
            source = src_dir / rel
            if source.is_file() and rel != CONTROL_STATE_FILE:
                (out / rel).parent.mkdir(parents=True, exist_ok=True)
                (out / rel).write_bytes(source.read_bytes())
        for archive in plan["appendArchive"]:
            source = src_dir / archive
            target = out / archive
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                for path in sorted(source.rglob("*")):
                    if path.is_file():
                        dest = target / path.relative_to(source)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(path.read_bytes())
    return manifest


def prune_request_history(requests_dir, state, keep=REQUEST_HISTORY_KEEP):
    """Bounded requests/ archive: open + processed + closed-stale newest first."""
    requests_dir = pathlib.Path(requests_dir)
    if not requests_dir.is_dir():
        return []
    keep_ids = set(state.get("processedRequestIds") or [])
    keep_ids |= set(state.get("closedStaleRequestIds") or [])
    if state.get("openRequestId"):
        keep_ids.add(state["openRequestId"])
    present = [p.name for p in requests_dir.iterdir() if p.is_dir()]
    removed = []
    import shutil
    for name in sorted(present):
        if name in keep_ids:
            continue
        if len([p for p in requests_dir.iterdir() if p.is_dir()]) <= keep:
            break
        shutil.rmtree(requests_dir / name)
        removed.append(name)
    return removed


# ---------------------------------------------------------------------------
# CLI (workflow glue): read/verify or pure file output. Git writes and pushes
# belong to the narrowly scoped workflow steps; only `cas` touches the network
# (fixed endpoint; token strictly from the environment).
# ---------------------------------------------------------------------------


class _SandboxParser(argparse.ArgumentParser):
    """Parser surface without any redirect/bypass option."""

    def add_argument(self, *args, **kwargs):
        for name in args:
            lowered = str(name).lower()
            if any(banned in lowered for banned in
                   ("replace", "redirect", "no-verify", "insecure", "allow-",
                    "skip-", "override", "baseline")):
                raise ValueError("mutable redirect/bypass options are never offered")
        return super().add_argument(*args, **kwargs)


def build_parser():
    parser = _SandboxParser(prog="automatic_publication",
                            description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("stage-build", help="tracker stage -> verified minimal S payload")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--stage-root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--today", required=True)

    p = sub.add_parser("emit-request", help="verify committed S -> control payload")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--candidate-commit", required=True)
    p.add_argument("--stage-root", required=True)
    p.add_argument("--candidate-ref", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--today", required=True)

    p = sub.add_parser("rederive-candidate",
                       help="immutable-NEW pinned fresh tracker re-derivation")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--candidate-commit", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--stage-root", required=True)
    p.add_argument("--cache", default=None)

    p = sub.add_parser("verify-candidate",
                       help="request+manifest+FRESH stage -> recomputed verdict")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--request-file", required=True)
    p.add_argument("--manifest-file", required=True)
    p.add_argument("--stage-root", required=True,
                   help="fresh upstream_updates re-derivation stage root "
                        "(authority; pinned --today to the candidate staging date)")
    p.add_argument("--history-verdict-file", default=None)
    p.add_argument("--expected-base", default=None,
                   help="independently resolved live main commit (publisher path)")

    p = sub.add_parser("emit-catalog-request", help="committed X -> catalog control payload")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--expected-base", required=True)
    p.add_argument("--x-commit", required=True)
    p.add_argument("--stage-root", required=True)
    p.add_argument("--manifest-file", required=True)
    p.add_argument("--candidate-ref", required=True)
    p.add_argument("--control-state-file", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--today", required=True)

    p = sub.add_parser("poll-request", help="read request/manifest/state from a control tip")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--control-commit", required=True)

    p = sub.add_parser("held-state", help="held-only scan -> control state payload")
    p.add_argument("--stage-root", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--state-file", default=None)

    p = sub.add_parser("mark-processed", help="idempotent processed-state writer")
    p.add_argument("--state-file", required=True)
    p.add_argument("--request-file", required=True)
    p.add_argument("--extra-file", default=None)
    p.add_argument("--out", required=True)

    p = sub.add_parser("processed-check", help="exit 3 when a requestId is processed")
    p.add_argument("--state-file", required=True)
    p.add_argument("--request-file", required=True)

    p = sub.add_parser("apply-payload", help="apply changes.json+snapshot into a checkout")
    p.add_argument("--payload-dir", required=True)
    p.add_argument("--repo-root", default=str(REPO))

    p = sub.add_parser("build-relay", help="signer out dir -> metadata-only relay payload")
    p.add_argument("--request-file", required=True)
    p.add_argument("--signer-out", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--info-file", default=None)
    p.add_argument("--today", default=None)

    p = sub.add_parser("relay-peek", help="tokenless check whether a relay already exists")
    p.add_argument("--request-id", required=True)
    p.add_argument("--relay-ref", default=RELAY_BRANCH)

    p = sub.add_parser("relay-verify", help="relay + candidate (+rebuild feeds) -> verdict")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--request-file", required=True)
    p.add_argument("--relay-dir", required=True)
    p.add_argument("--candidate-commit", required=True)
    p.add_argument("--feeds-dir", default=None)

    p = sub.add_parser("build-x", help="S + relay -> X payload")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--s-commit", required=True)
    p.add_argument("--request-file", required=True)
    p.add_argument("--relay-dir", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("rebuild-feeds", help="deterministic feed bytes at an X checkout")
    p.add_argument("--x-root", required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("build-y", help="X + verified relay feeds -> Y payload")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--request-file", required=True)
    p.add_argument("--relay-dir", required=True)
    p.add_argument("--feeds-dir", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("build-h", help="Y + appended ledger -> H payload")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--y-commit", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("check-chain", help="prove B/X/Y/H stay inside the contract")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--x-commit", required=True)
    p.add_argument("--y-commit", required=True)
    p.add_argument("--h-commit", required=True)

    p = sub.add_parser("recover", help="crash-resume publisher plan for an advanced tip")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--request-file", required=True)
    p.add_argument("--manifest-file", required=True)
    p.add_argument("--live-main", required=True)
    p.add_argument("--candidate-tip", required=True)
    p.add_argument("--stage-root", required=True)
    p.add_argument("--relay-dir", default=None)
    p.add_argument("--x-root", default=None)

    p = sub.add_parser("verify-published-chain",
                       help="centralized ORIGINAL-Y/H chain + relay + full "
                            "candidate proof (all mandatory)")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--base-commit", required=True)
    p.add_argument("--x-commit", required=True)
    p.add_argument("--y-commit", required=True)
    p.add_argument("--h-commit", required=True)
    p.add_argument("--request-file", required=True)
    p.add_argument("--relay-dir", required=True)
    p.add_argument("--x-root", required=True)
    p.add_argument("--stage-root", required=True,
                   help="fresh upstream_updates re-derivation stage root "
                        "(full candidate proof is mandatory)")
    p.add_argument("--manifest-file", required=True,
                   help="manifest bound to this request (full candidate "
                        "proof is mandatory)")

    p = sub.add_parser("cas", help="exact GraphQL updateRefs main advance B->H")
    p.add_argument("--base-commit", required=True)
    p.add_argument("--head-commit", required=True)
    p.add_argument("--token-env", default="GITHUB_TOKEN")
    p.add_argument("--plan-only", action="store_true")

    p = sub.add_parser("verify-public",
                       help="post-publish public byte-exact + full ledger proof")
    p.add_argument("--repo-root", default=str(REPO))
    p.add_argument("--head-commit", required=True)
    p.add_argument("--x-commit", required=True)
    p.add_argument("--base-commit", default=None,
                   help="request base B; when supplied the append-only ledger "
                        "prefix over the committed base ledger is also proven")

    p = sub.add_parser("plan-control-update",
                       help="deterministic control-branch merge decision")
    p.add_argument("--payload-dir", default=None)
    p.add_argument("--state-file", required=True)
    p.add_argument("--request-file", default=None)
    p.add_argument("--live-main", required=True)
    p.add_argument("--today", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("prune-requests", help="bounded requests/ archive housekeeping")
    p.add_argument("--requests-dir", required=True)
    p.add_argument("--state-file", required=True)

    p = sub.add_parser("state-patch", help="bounded rolling state update")
    p.add_argument("--state-file", required=True)
    p.add_argument("--patch-file", required=True)
    p.add_argument("--out", required=True)
    return parser


def _load_request(path):
    return at.parse_request_file(path)


def _manifest_from_payload(payload, run_id):
    return {
        "changedSkillIds": payload["changedSkillIds"],
        "bumpedVersions": payload["bumpedVersions"],
        "upstreamPinsBefore": payload["upstreamPinsBefore"],
        "upstreamPinsAfter": payload["upstreamPinsAfter"],
        "holdReasons": payload["holdReasons"],
        "reviewStageCounts": payload["reviewStageCounts"],
        "gateResults": payload["gateResults"],
        "executableSubsetDigests": payload["executableSubsetDigests"],
        "integrationGaps": payload["integrationGaps"],
        "engineTreeOidAtB": payload["engineTreeOidAtB"],
        "stageToday": payload["stageToday"],
        "runId": run_id,
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = pathlib.Path(getattr(args, "repo_root", REPO))

    if args.command == "stage-build":
        hubcore.require_commit(args.base_commit, "base commit")
        payload = build_candidate_payload(root, args.base_commit, args.stage_root,
                                         args.out, today=args.today)
        summary = {k: payload[k] for k in
                   ("appliedSkillIds", "changedSkillIds", "bumpedVersions",
                    "reviewStageCounts", "holdReasons", "integrationGaps",
                    "engineTreeOidAtB")}
        summary["writes"] = sorted(payload["writes"])
        summary["deletions"] = payload["deletions"]
        print(hubcore.pretty({"status": "stage-built", **summary}).decode())
        return 0

    if args.command == "emit-request":
        hubcore.require_commit(args.base_commit, "base commit")
        hubcore.require_commit(args.candidate_commit, "candidate commit")
        policy_bytes = blob_at(root, args.base_commit, POLICY_REL, "base policy")
        if policy_bytes is None or blob_at(root, args.candidate_commit, POLICY_REL,
                                           "candidate policy") != policy_bytes:
            _hold("policy blob missing or drifted on the candidate")
        payload = derive_expected_apply_set(root, args.base_commit,
                                            args.stage_root, today=args.today)
        request_bytes, request_doc = build_request("reviews", args.candidate_commit,
                                                   args.base_commit, policy_bytes)
        manifest_extra = _manifest_from_payload(
            payload, os.environ.get("GITHUB_RUN_ID", "local-run"))
        manifest_doc = {"schemaVersion": SCHEMA_VERSION, "pipeline": PUBLICATION_NAME,
                        "mode": "reviews", "basePublication": args.base_commit,
                        "sourceCommit": args.candidate_commit,
                        "stagingRef": args.candidate_ref,
                        "requestId": request_doc["requestId"],
                        "request": request_doc,
                        "policySha256": request_doc["policySha256"],
                        "createdAtUTC": args.today, **manifest_extra}
        # full recomputed verification against the COMMITTED candidate (the
        # same fresh stage is authoritative) before anything reaches control
        verify_candidate(root, request_doc, manifest_doc, policy_bytes,
                         fresh_stage_root=args.stage_root)
        result = control_payload(args.out, base_commit=args.base_commit,
                                 candidate_commit=args.candidate_commit,
                                 mode="reviews", staging_ref=args.candidate_ref,
                                 manifest_extra=manifest_extra,
                                 today=args.today, policy_bytes=policy_bytes)
        print(hubcore.pretty({"status": "request-built", "verified": True,
                              "requestId": result["request"]["requestId"],
                              "sourceCommit": args.candidate_commit,
                              "candidateRef": args.candidate_ref}).decode())
        return 0

    if args.command == "rederive-candidate":
        hubcore.require_commit(args.base_commit, "base commit")
        hubcore.require_commit(args.candidate_commit, "candidate commit")
        facts = rederive_candidate(root, args.base_commit, args.candidate_commit,
                                   today=args.today, stage_root=args.stage_root,
                                   cache=args.cache)
        print(hubcore.pretty(facts).decode())
        return 0

    if args.command == "verify-candidate":
        request_doc = _load_request(args.request_file)
        manifest = _canonical_json(pathlib.Path(args.manifest_file).read_bytes(),
                                   "manifest", MAX_MANIFEST_BYTES)
        policy_bytes = blob_at(root, request_doc["basePublication"], POLICY_REL,
                               "policy")
        if policy_bytes is None:
            _hold("policy blob is unreadable at the base publication")
        history_verdict = None
        if args.history_verdict_file and \
                pathlib.Path(args.history_verdict_file).is_file():
            history_verdict = _canonical_json(
                pathlib.Path(args.history_verdict_file).read_bytes(),
                "history verdict", MAX_MANIFEST_BYTES)
        verdict = verify_candidate(root, request_doc, manifest, policy_bytes,
                                   fresh_stage_root=args.stage_root,
                                   history_verdict=history_verdict,
                                   expected_base=args.expected_base)
        print(hubcore.pretty(verdict).decode())
        return 0

    if args.command == "emit-catalog-request":
        hubcore.require_commit(args.x_commit, "X commit")
        manifest = _canonical_json(pathlib.Path(args.manifest_file).read_bytes(),
                                   "manifest", MAX_MANIFEST_BYTES)
        base_commit = manifest["basePublication"]
        policy_bytes = blob_at(root, base_commit, POLICY_REL, "base policy")
        if policy_bytes is None:
            _hold("policy blob missing at the base")
        request_bytes, request_doc = build_request("catalog", args.x_commit,
                                                   base_commit, policy_bytes)
        catalog_manifest = dict(manifest)
        catalog_manifest.update({"mode": "catalog",
                                 "sourceCommit": args.x_commit, "X": args.x_commit,
                                 "stagingRef": args.candidate_ref,
                                 "requestId": request_doc["requestId"],
                                 "request": request_doc,
                                 "policySha256": request_doc["policySha256"],
                                 "createdAtUTC": args.today})
        verify_candidate(root, request_doc, catalog_manifest, policy_bytes,
                         fresh_stage_root=args.stage_root,
                         expected_base=args.expected_base)
        state = None
        if args.control_state_file and pathlib.Path(args.control_state_file).is_file():
            state = _canonical_json(pathlib.Path(args.control_state_file).read_bytes(),
                                    "control state", MAX_STATE_BYTES)
        payload_dir = pathlib.Path(args.out)
        write_payload_file(payload_dir, CONTROL_REQUEST_FILE, request_bytes)
        write_payload_file(payload_dir, CONTROL_MANIFEST_FILE,
                           hubcore.pretty(catalog_manifest))
        archive = CONTROL_ARCHIVE_PREFIX + request_doc["requestId"] + "/"
        write_payload_file(payload_dir, archive + CONTROL_REQUEST_FILE, request_bytes)
        write_payload_file(payload_dir, archive + CONTROL_MANIFEST_FILE,
                           hubcore.pretty(catalog_manifest))
        new_state = _state_update(state, {"openRequestId": request_doc["requestId"],
                                          "pipelineStage": "catalog-requested",
                                          "lastRequestId": request_doc["requestId"],
                                          "lastCheckUTC": args.today})
        write_payload_file(payload_dir, CONTROL_STATE_FILE, _state_bytes(new_state))
        write_payload_file(payload_dir, CONTROL_CHANGES_FILE, hubcore.pretty({
            "schemaVersion": SCHEMA_VERSION,
            "mirror": [CONTROL_REQUEST_FILE, CONTROL_MANIFEST_FILE,
                       CONTROL_STATE_FILE],
            "appendArchive": [archive]}))
        print(hubcore.pretty({"status": "catalog-request-built",
                              "requestId": request_doc["requestId"],
                              "X": args.x_commit}).decode())
        return 0

    if args.command == "poll-request":
        print(hubcore.pretty(read_control_payload(root, args.control_commit)).decode())
        return 0

    if args.command == "held-state":
        state = None
        if args.state_file and pathlib.Path(args.state_file).is_file():
            state = _canonical_json(pathlib.Path(args.state_file).read_bytes(),
                                    "control state", MAX_STATE_BYTES)
        result = held_state_payload(args.out, stage_root=args.stage_root,
                                    today=args.today, control_state=state)
        print(hubcore.pretty({"status": "held-state-built",
                              "holdCount": result["holdCount"]}).decode())
        return 0

    if args.command == "mark-processed":
        state = _canonical_json(pathlib.Path(args.state_file).read_bytes(),
                                "state", MAX_STATE_BYTES)
        request_doc = _load_request(args.request_file)
        extra = None
        if args.extra_file:
            extra = _canonical_json(pathlib.Path(args.extra_file).read_bytes(),
                                    "extra", MAX_STATE_BYTES)
        new_state = mark_processed(state, request_doc["requestId"], extra=extra)
        pathlib.Path(args.out).write_bytes(_state_bytes(new_state))
        print(hubcore.pretty({"status": "state-marked",
                              "requestId": request_doc["requestId"]}).decode())
        return 0

    if args.command == "processed-check":
        state = _canonical_json(pathlib.Path(args.state_file).read_bytes(),
                                "state", MAX_STATE_BYTES)
        request_doc = _load_request(args.request_file)
        processed = already_processed(state, request_doc["requestId"])
        print(hubcore.pretty({"requestId": request_doc["requestId"],
                              "processed": processed}).decode())
        return 3 if processed else 0

    if args.command == "apply-payload":
        report = apply_payload(args.payload_dir, args.repo_root)
        print(hubcore.pretty({"status": "payload-applied", **report}).decode())
        return 0

    if args.command == "build-relay":
        request_doc = _load_request(args.request_file)
        info = None
        if args.info_file:
            info = _canonical_json(pathlib.Path(args.info_file).read_bytes(),
                                   "relay info", MAX_MANIFEST_BYTES)
        if info is not None and args.today:
            info = dict(info, today=args.today)
        result = build_relay_payload(args.signer_out, request_doc, args.out,
                                     info=info)
        print(hubcore.pretty({"status": "relay-built",
                              "requestId": result["requestId"],
                              "mode": result["mode"],
                              "members": result["members"]}).decode())
        return 0

    if args.command == "relay-peek":
        exists, data = (False, None) if transport_is_offline() \
            else relay_exists(args.request_id)
        print(hubcore.pretty({"requestId": args.request_id,
                              "exists": exists,
                              "manifestSha256": (hubcore.sha256_hex(data)
                                                 if exists else None)}).decode())
        return 0 if exists else 10

    if args.command == "relay-verify":
        request_doc = _load_request(args.request_file)
        feeds = None
        if args.feeds_dir:
            feeds_dir = pathlib.Path(args.feeds_dir)
            feeds = {rel: (feeds_dir / rel).read_bytes()
                     for rel in sorted(cv.FEED_FILES)
                     if (feeds_dir / rel).is_file()}
        verdict, _files = relay_validate(args.relay_dir, request_doc, root,
                                         args.candidate_commit, feeds=feeds)
        print(hubcore.pretty(verdict).decode())
        return 0

    if args.command == "build-x":
        request_doc = _load_request(args.request_file)
        payload = build_x_payload(root, args.base_commit, args.s_commit,
                                  request_doc, args.relay_dir, args.out)
        print(hubcore.pretty({"status": "x-payload-built",
                              "writes": sorted(payload["writes"]),
                              "reviewsRelayVerdict": payload["reviewsRelayVerdict"]}
                             ).decode())
        return 0

    if args.command == "rebuild-feeds":
        feeds = rebuild_feeds(args.x_root, args.source_commit)
        out = pathlib.Path(args.out)
        for rel, data in sorted(feeds.items()):
            write_payload_file(out, rel, data)
        print(hubcore.pretty({"status": "feeds-rebuilt",
                              "sha256": {rel: hubcore.sha256_hex(data)
                                         for rel, data in sorted(feeds.items())}}
                             ).decode())
        return 0

    if args.command == "build-y":
        request_doc = _load_request(args.request_file)
        feeds_dir = pathlib.Path(args.feeds_dir)
        feeds = {rel: (feeds_dir / rel).read_bytes()
                 for rel in sorted(cv.FEED_FILES)}
        verdict, payload = build_y_payload(request_doc, args.relay_dir, root,
                                           feeds, args.out)
        print(hubcore.pretty({"status": "y-payload-built",
                              "writes": sorted(payload["writes"]),
                              "relayRequestId": verdict["requestId"],
                              "boundContentVerified": verdict["boundContentVerified"]}
                             ).decode())
        return 0

    if args.command == "build-h":
        payload, ledger_bytes = build_h_payload(root, args.base_commit,
                                                args.y_commit, args.out)
        print(hubcore.pretty({"status": "h-payload-built", **payload}).decode())
        return 0

    if args.command == "check-chain":
        print(hubcore.pretty(verify_publication_diffs(
            root, args.base_commit, args.x_commit, args.y_commit,
            args.h_commit)).decode())
        return 0

    if args.command == "recover":
        request_doc = _load_request(args.request_file)
        manifest = _canonical_json(pathlib.Path(args.manifest_file).read_bytes(),
                                   "manifest", MAX_MANIFEST_BYTES)
        policy_bytes = blob_at(root, request_doc["basePublication"], POLICY_REL,
                               "policy")
        if policy_bytes is None:
            _hold("policy blob is unreadable at the request base")
        plan = recover_publish_plan(
            root, request_doc, manifest, policy_bytes,
            live_main=args.live_main, candidate_tip=args.candidate_tip,
            fresh_stage_root=args.stage_root, relay_dir=args.relay_dir,
            x_root=args.x_root)
        printable = {k: v for k, v in plan.items() if k != "proof"}
        if "proof" in plan:
            printable["proofStatus"] = {
                "chain": plan["proof"]["chain"]["status"],
                "relay": plan["proof"]["relay"]["status"],
                "candidate": (plan["proof"].get("candidate") or {}).get("status")}
        print(hubcore.pretty(printable).decode())
        return 0

    if args.command == "verify-published-chain":
        request_doc = _load_request(args.request_file)
        manifest = _canonical_json(pathlib.Path(args.manifest_file).read_bytes(),
                                   "manifest", MAX_MANIFEST_BYTES)
        proof = verify_published_chain(
            root, args.base_commit, args.x_commit, args.y_commit,
            args.h_commit, request_doc, args.relay_dir, x_root=args.x_root,
            fresh_stage_root=args.stage_root, manifest_doc=manifest)
        print(hubcore.pretty({"status": "published-chain-verified",
                              "chain": proof["chain"]["status"],
                              "relay": proof["relay"]["status"],
                              "candidate": proof["candidate"]["status"]}).decode())
        return 0

    if args.command == "cas":
        print(hubcore.pretty(cas_publish(args.base_commit, args.head_commit,
                                         token_env=args.token_env,
                                         dry_run=args.plan_only)).decode())
        return 0

    if args.command == "verify-public":
        print(hubcore.pretty(verify_public_main(
            args.head_commit, args.x_commit, trust_root=root,
            base_commit=args.base_commit)).decode())
        return 0

    if args.command == "plan-control-update":
        state = None
        if pathlib.Path(args.state_file).is_file():
            state = _canonical_json(pathlib.Path(args.state_file).read_bytes(),
                                    "current state", MAX_STATE_BYTES)
        open_request = None
        if args.request_file and pathlib.Path(args.request_file).is_file():
            open_request = _load_request(args.request_file)
        plan = plan_control_update(args.payload_dir, state, open_request,
                                   args.live_main, args.today)
        manifest = write_control_plan_output(args.out, plan)
        print(hubcore.pretty({"status": "control-planned", **manifest}).decode())
        return 0

    if args.command == "prune-requests":
        state = _canonical_json(pathlib.Path(args.state_file).read_bytes(),
                                "state", MAX_STATE_BYTES)
        removed = prune_request_history(pathlib.Path(args.requests_dir), state)
        print(hubcore.pretty({"status": "requests-pruned", "removed": removed}).decode())
        return 0

    if args.command == "state-patch":
        old = None
        state_path = pathlib.Path(args.state_file)
        if state_path.is_file():
            old = _canonical_json(state_path.read_bytes(), "state", MAX_STATE_BYTES)
        patch = _canonical_json(pathlib.Path(args.patch_file).read_bytes(),
                                "state patch", MAX_STATE_BYTES)
        pathlib.Path(args.out).write_bytes(_state_bytes(_state_update(old, patch)))
        print(hubcore.pretty({"status": "state-patched"}).decode())
        return 0

    _hold(f"unknown command {args.command!r}")


def transport_is_offline():
    return os.environ.get("FLOE_AUTO_PUB_OFFLINE") == "1"


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PublicationError as error:
        print("automatic-publication: refusing: " + str(error), file=sys.stderr)
        sys.exit(2)
