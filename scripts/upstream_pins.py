#!/usr/bin/env python3
"""Per-skill upstream pin contract for docs/UPSTREAM-PINS.json (H lane 2026-10-28).

Why this module exists. ``check_catalog.py check_pins`` historically compared
every registry ``upstream.commit`` against the single repository default in
``docs/UPSTREAM-PINS.json`` ``repositories``. That made per-REPOSITORY atomic
acceptance block unrelated skills sharing a corpus repository (one held script
row froze every guide in the same repository). This module adds an OPTIONAL,
explicit, reviewed ``skillOverrides`` map so an eligible entry can advance to
its own reviewed commit while held peers keep the repository default — a
per-entry override IS that entry's effective pin and is still compared for
EXACT equality. Nothing here loosens provenance: a row never "passes" because
some commit merely looks well-formed; it passes only against its reviewed
effective pin.

Document shape (top-level keys are exactly these):

  {
    "reviewBaselineDate": "YYYY-MM-DD" (a real calendar date),
    "repositories": { "owner/repo": "<40 lowercase hex>", ... },
    "skillOverrides": {                       # optional; legacy docs omit it
      "<exact external registry id>": { "repository": "owner/repo",
                                        "commit": "<40 lowercase hex>" }, ...
    }
  }

Effective pin for an upstream row = its valid explicit override commit, else
its repository default. Every override must bind an EXISTING registry row that
carries a non-null ``upstream`` block (unknown ids and local/builtin/
Floe-original ``upstream == null`` rows are refused), must name the SAME
``owner/repo`` as that row's registry ``upstream.repository`` (no repository
identity change), and must reference a repository listed in ``repositories``
(no new/unlisted repository, no arbitrary URL/branch/loose-commit matching).

Deny-by-construction: non-canonical document bytes are refused before trust —
duplicate JSON keys at any nesting depth, non-UTF-8 or > MAX_PINS_BYTES input,
NaN/Infinity literals, unknown top-level or override fields, malformed
repository ids or commits, and a fake baseline date.

Authority boundary (deliberate, see docs/UPSTREAM-PIN-CONTRACT.md):
  * ``advance_pin_document`` consumes ``accepted_ids`` ONLY as the trusted
    recomputed update plan's output — it is NOT an external approval flag and
    grants nothing by itself. The helper never fetches, clones or verifies
    commit CONTENT; upstream reachability, license review, merge policy and
    the execution gates stay with the tracker lane and the App-side recompute
    (and Root owns review/commit plus the one-time App anchor re-pin).
  * A valid registry's full structural shape (43-row candidate contract) is
    ``hubcore.validate_registry``'s job (check_catalog runs it before calling
    into this module). This module enforces ONLY the pin semantics below and
    the minimal registry structure the pin semantics need, so trusted lanes
    can reuse one contract without re-implementing equality rules.
  * Full registry re-serialization is left to the caller; a legacy document
    without overrides keeps working byte-identically (no production bytes
    change until a real accepted advance happens).

Pure module: every entry point validates and returns fresh objects, never
mutates the inputs, and never touches the filesystem (``load_pins_file`` reads
one path it is given, read-only).
"""
import copy
import datetime
import json
import pathlib
import re

import hubcore

PINS_DOC_RELATIVE_PATH = "docs/UPSTREAM-PINS.json"
GITHUB_URL_PREFIX = "https://github.com/"
MAX_PINS_BYTES = 64 * 1024  # generous for 43 rows + overrides; refuses giant input
DOC_FIELDS = ("reviewBaselineDate", "repositories")
DOC_OPTIONAL_FIELDS = ("skillOverrides",)
OVERRIDE_FIELDS = ("repository", "commit")
REPO_SHORT_PATTERN = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
DATE_PATTERN = hubcore.DATE_PATTERN
COMMIT_PATTERN = hubcore.COMMIT_PATTERN
ID_PATTERN = hubcore.ID_PATTERN


class UpstreamPinError(Exception):
    """Fail-closed pin-contract violation with a descriptive reason."""


def _require_date(value, field):
    if (not isinstance(value, str) or not DATE_PATTERN.fullmatch(value)
            or not _is_real_date(value)):
        raise UpstreamPinError(f"invalid {field}: expected a real YYYY-MM-DD date "
                               f"(got {value!r})")
    return value


def _is_real_date(value):
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _require_commit(value, field):
    if not isinstance(value, str) or not COMMIT_PATTERN.fullmatch(value):
        raise UpstreamPinError(f"invalid {field}: expected 40 lowercase hex "
                               f"(got {value!r})")
    return value


def _require_repo_short(value, field):
    if not isinstance(value, str) or not REPO_SHORT_PATTERN.fullmatch(value):
        raise UpstreamPinError(f"invalid {field}: expected an 'owner/repo' "
                               f"identifier (got {value!r})")
    return value


def _require_skill_id(value, field):
    if (not isinstance(value, str) or len(value) > 64
            or not ID_PATTERN.fullmatch(value) or "--" in value
            or value.endswith("-")):
        raise UpstreamPinError(f"invalid {field}: {value!r} is not a SkillIdentifier")
    return value


def _reject_constant(constant):
    raise UpstreamPinError(f"JSON literal {constant!r} is not a legal pin value")


def _unique_object(pairs):
    """object_pairs_hook: refuse duplicate keys at any nesting depth."""
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise UpstreamPinError(f"duplicate JSON key {key!r} in the pins document")
        seen.add(key)
    return dict(pairs)


def parse_pins_bytes(data):
    """Strict byte parser: UTF-8, bounded, duplicate-key- and NaN-free JSON,
    then the registry-independent document shape. Returns a fresh dict."""
    if not isinstance(data, bytes):
        raise UpstreamPinError("pins document input must be raw bytes")
    if len(data) > MAX_PINS_BYTES:
        raise UpstreamPinError(f"pins document is oversized: {len(data)} bytes "
                               f"exceeds the {MAX_PINS_BYTES}-byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpstreamPinError(f"pins document is not valid UTF-8: {error}") from error
    try:
        doc = json.loads(text, object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    except UpstreamPinError:
        raise
    except ValueError as error:
        raise UpstreamPinError(f"pins document is not valid JSON: {error}") from error
    validate_pins_document(doc)
    return doc


def load_pins_file(path):
    """Read-only convenience for trusted callers (check_catalog, CI helpers)."""
    path = pathlib.Path(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise UpstreamPinError(f"cannot read {path}: {error}") from error
    return parse_pins_bytes(data)


def validate_pins_document(doc):
    """Registry-independent document shape; raises UpstreamPinError."""
    if not isinstance(doc, dict):
        raise UpstreamPinError("pins document must be a JSON object")
    allowed = set(DOC_FIELDS) | set(DOC_OPTIONAL_FIELDS)
    extra = sorted(set(doc) - allowed)
    missing = sorted(set(DOC_FIELDS) - set(doc))
    if missing:
        raise UpstreamPinError(f"pins document missing field(s): {', '.join(missing)}")
    if extra:
        raise UpstreamPinError("pins document has unknown field(s): "
                               + ", ".join(extra))
    _require_date(doc["reviewBaselineDate"], "reviewBaselineDate")
    repositories = doc["repositories"]
    if not isinstance(repositories, dict) or not repositories:
        raise UpstreamPinError("repositories must be a non-empty object")
    for repo, commit in repositories.items():
        _require_repo_short(repo, f"repositories key {repo!r}")
        _require_commit(commit, f"repositories[{repo!r}]")
    overrides = doc.get("skillOverrides", {})
    if not isinstance(overrides, dict):
        raise UpstreamPinError("skillOverrides must be an object mapping entry id "
                               "to {repository, commit}")
    for sid, override in overrides.items():
        _require_skill_id(sid, f"skillOverrides key {sid!r}")
        if not isinstance(override, dict):
            raise UpstreamPinError(f"skillOverrides[{sid!r}] must be an object")
        override_extra = sorted(set(override) - set(OVERRIDE_FIELDS))
        override_missing = sorted(set(OVERRIDE_FIELDS) - set(override))
        if override_missing or override_extra:
            detail = ", ".join(override_missing + override_extra)
            raise UpstreamPinError(f"skillOverrides[{sid!r}] keys must be exactly "
                                   f"repository+commit (offender: {detail})")
        _require_repo_short(override["repository"],
                            f"skillOverrides[{sid!r}].repository")
        _require_commit(override["commit"], f"skillOverrides[{sid!r}].commit")
        if override["repository"] not in repositories:
            raise UpstreamPinError(f"skillOverrides[{sid!r}].repository "
                                   f"{override['repository']!r} is not listed in "
                                   "the repositories map (a new repository must "
                                   "be added as a reviewed default first)")


def _registry_rows(registry):
    """Minimal structural sanity + id -> (repo_short|None, commit|None) map.

    Full candidate-shape validation stays hubcore.validate_registry's job; this
    only guarantees the fields the pin semantics read. Raises
    UpstreamPinError on malformed input.
    """
    if not isinstance(registry, dict) or not isinstance(registry.get("skills"), list):
        raise UpstreamPinError("registry input must be an object with a skills list")
    rows = {}
    for index, entry in enumerate(registry["skills"]):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise UpstreamPinError(f"registry entry index {index}: missing a string id")
        sid = _require_skill_id(entry["id"], f"registry entry index {index} id")
        if sid in rows:
            raise UpstreamPinError(f"registry entry {sid}: duplicate id")
        upstream = entry.get("upstream")
        if upstream is None:
            rows[sid] = (None, None)
            continue
        if not isinstance(upstream, dict):
            raise UpstreamPinError(f"registry entry {sid}: upstream must be an "
                                   "object or null")
        repository = upstream.get("repository")
        if (not isinstance(repository, str)
                or not repository.startswith(GITHUB_URL_PREFIX)
                or not REPO_SHORT_PATTERN.fullmatch(
                        repository[len(GITHUB_URL_PREFIX):])
                or repository[len(GITHUB_URL_PREFIX):].count("/") != 1):
            raise UpstreamPinError(f"registry entry {sid}: upstream.repository must "
                                   f"be an https://github.com/owner/repo URL "
                                   f"(got {repository!r})")
        rows[sid] = (repository[len(GITHUB_URL_PREFIX):],
                     _require_commit(upstream.get("commit"),
                                     f"registry entry {sid} upstream.commit"))
    return rows


def effective_pin_for_entry(doc, entry_id, repo_short):
    """The EXACT pin this entry must equal: valid explicit override, else the
    repository default. Raises UpstreamPinError when the entry cannot resolve
    (unknown repository default) or when its override is mis-bound (different
    repository than the row itself); check_registry_pins reports those as
    descriptive reasons instead of hiding them."""
    override = doc.get("skillOverrides", {}).get(entry_id)
    if override is not None:
        if override["repository"] != repo_short:
            raise UpstreamPinError(
                f"{entry_id}: override repository {override['repository']!r} does "
                f"not match the entry's upstream repository {repo_short!r}")
        return override["commit"], True
    repositories = doc["repositories"]
    if repo_short not in repositories:
        raise UpstreamPinError(f"{entry_id}: repository {repo_short} is not in "
                               "docs/UPSTREAM-PINS.json")
    return repositories[repo_short], False


def check_registry_pins(doc, registry):
    """Pure semantic check of one document against one registry snapshot.

    Returns a list of descriptive failure reasons (empty = the provenance
    consistency holds). With no overrides this reproduces the original
    check_catalog messages byte-for-byte; a per-entry override uses the same
    exact-equality rule, just against its own reviewed baseline. Never accepts
    any commit merely because its format is valid.
    """
    validate_pins_document(doc)
    rows = _registry_rows(registry)
    reasons = []
    repositories = doc["repositories"]
    overrides = doc.get("skillOverrides", {})
    for sid, override in overrides.items():
        repo_short, _commit = rows.get(sid, (None, None))
        if sid not in rows:
            reasons.append(f"skillOverrides entry {sid}: no registry entry with "
                           "this id (overrides cannot pin unknown skills)")
            continue
        if repo_short is None:
            reasons.append(f"skillOverrides entry {sid}: the registry row has no "
                           "upstream block; overrides cannot pin local/builtin/"
                           "Floe-original entries")
            continue
        if override["repository"] != repo_short:
            reasons.append(f"skillOverrides entry {sid}: repository "
                           f"{override['repository']!r} does not match the entry's "
                           f"upstream repository {repo_short!r} (overrides cannot "
                           "change repository identity)")
        if override["repository"] not in repositories:
            reasons.append(f"skillOverrides entry {sid}: repository "
                           f"{override['repository']!r} is not listed in the "
                           "repositories map")
    for sid, (repo_short, commit) in sorted(rows.items()):
        if repo_short is None:
            continue
        override = overrides.get(sid)
        if override is not None and override["repository"] == repo_short:
            expected = override["commit"]
            if commit != expected:
                reasons.append(f"{sid}: commit {commit[:10]} diverges from its "
                               f"reviewed per-entry baseline {expected[:10]}")
            continue
        if repo_short not in repositories:
            reasons.append(f"{sid}: repository {repo_short} is not in "
                           "docs/UPSTREAM-PINS.json")
        elif commit != repositories[repo_short]:
            reasons.append(f"{sid}: commit {commit[:10]} diverges from the review "
                           f"baseline {repositories[repo_short][:10]}")
    return reasons


def advance_pin_document(prior_doc, old_registry, new_registry, accepted_ids, today):
    """Deterministic, guard-railed advancement of the review-pin document.

    Inputs: ``prior_doc`` must be exactly valid against ``old_registry`` (the
    current reviewed baseline), ``new_registry`` is the recomputed candidate
    registry snapshot, ``accepted_ids`` is the trusted update plan's set/list
    of external entry ids whose ``upstream.commit`` this run publishes, and
    ``today`` is the new review baseline date (real YYYY-MM-DD).

    Guarantees (all fail closed with UpstreamPinError, inputs never mutated):
      * old and new registries must carry the EXACT same entry id set and the
        same per-entry repository identity, with upstream null-ness unchanged
        — no entry may be added/removed, move repositories, or have a
        licensed upstream row replaced by an unlicensed Floe-original row
        (``upstream == null``) or vice versa (automatic imports are this
        document's caller's job only after their own license gates, never
        here);
      * only ``accepted_ids`` may change ``upstream.commit``; every held
        (unaccepted) external row must keep its old commit exactly;
      * accepted ids must be real external entries; accepted new commits must
        be 40 lowercase hex (format only — the helper never verifies commit
        content, reachability or licensing: the tracker plan, license review,
        merge policy and the App-side recompute stay authoritative);
      * for each repository, if all current external rows share ONE commit,
        that commit becomes the compact repository default and its redundant
        overrides are dropped; with MIXED commits the previous repository
        default is retained and overrides are written only for entries that
        differ from it; repositories with no rows (watch-only baselines) are
        preserved untouched; non-upstream rows never gain pins;
      * the result is post-verified: ``check_registry_pins(result,
        new_registry)`` must be empty before it is returned.

    This document is the CURRENT review pins; it is not the cumulative
    publication ledger, and advancing it never erases published package facts.
    """
    doc = copy.deepcopy(prior_doc)
    validate_pins_document(doc)
    prior_reasons = check_registry_pins(doc, old_registry)
    if prior_reasons:
        raise UpstreamPinError("prior pins document does not match the old "
                               "registry: " + "; ".join(prior_reasons))
    _require_date(today, "advance today date")
    if isinstance(accepted_ids, (str, bytes)):
        raise UpstreamPinError("accepted_ids must be a set/list of entry ids, "
                               "not a single string")
    accepted = set()
    for sid in accepted_ids:
        accepted.add(_require_skill_id(sid, "accepted id"))
    old_rows = _registry_rows(old_registry)
    new_rows = _registry_rows(new_registry)

    if set(old_rows) != set(new_rows):
        added = sorted(set(new_rows) - set(old_rows))
        removed = sorted(set(old_rows) - set(new_rows))
        raise UpstreamPinError("registries must carry the exact same entry id set "
                               f"(added: {added or 'none'}; removed: {removed or 'none'})")
    for sid in sorted(old_rows):
        old_repo, old_commit = old_rows[sid]
        new_repo, new_commit = new_rows[sid]
        if old_repo != new_repo:
            raise UpstreamPinError(f"{sid}: repository identity changed "
                                   f"({old_repo!r} -> {new_repo!r}); this advance "
                                   "may not add, drop or re-home upstream rows")
        if sid not in accepted and old_commit != new_commit:
            raise UpstreamPinError(f"{sid}: unaccepted entry changed its upstream "
                                   f"commit ({old_commit[:10]} -> "
                                   f"{new_commit[:10]}); held entries keep the "
                                   "reviewed baseline")
    unknown_accepted = sorted(accepted - set(old_rows))
    if unknown_accepted:
        raise UpstreamPinError("accepted ids must exist in both registries: "
                               + ", ".join(unknown_accepted))
    for sid in sorted(accepted):
        if new_rows[sid][0] is None:
            raise UpstreamPinError(f"{sid}: accepted id has no upstream block; "
                                   "local/builtin/Floe-original entries are never "
                                   "pin-advanced")

    repositories = dict(doc["repositories"])
    external_by_repo = {}
    for sid, (repo_short, commit) in new_rows.items():
        if repo_short is not None:
            external_by_repo.setdefault(repo_short, []).append((sid, commit))
    for repo_short, rows in sorted(external_by_repo.items()):
        commits = {commit for _, commit in rows}
        if len(commits) == 1:
            repositories[repo_short] = commits.pop()
        # mixed: retain the previous default; overrides below re-point only
        # the entries that differ from it. Watch-only repositories never
        # appear in external_by_repo, so their baselines stay untouched.

    new_overrides = {}
    for repo_short, rows in sorted(external_by_repo.items()):
        default = repositories[repo_short]
        for sid, commit in sorted(rows):
            if commit != default:
                new_overrides[sid] = {"repository": repo_short, "commit": commit}

    result = {"reviewBaselineDate": today,
              "repositories": {repo: repositories[repo]
                               for repo in sorted(repositories)},
              "skillOverrides": {sid: {"repository": ov["repository"],
                                       "commit": ov["commit"]}
                                 for sid, ov in sorted(new_overrides.items())}}
    if not result["skillOverrides"]:
        del result["skillOverrides"]
    post_reasons = check_registry_pins(copy.deepcopy(result), new_registry)
    if post_reasons:
        raise UpstreamPinError("advance produced an inconsistent document: "
                               + "; ".join(post_reasons))
    return result


def deterministic_bytes(doc):
    """Stable canonical pretty bytes for a pins document (sorted keys,
    indent 2, trailing newline) so two equivalent advances never differ by
    formatting noise."""
    validate_pins_document(copy.deepcopy(doc))
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")
