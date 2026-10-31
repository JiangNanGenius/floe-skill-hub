#!/usr/bin/env python3
"""Generic upstream tracking and candidate construction core (MPL-2.0, Floe tooling).

Implements the stage0 "hubTracker" core of the automatic upstream update
pipeline (see docs/UPSTREAM-TRACKING.md and the publication-design decision):

  check  read-only grouped upstream scan. Resolves each pinned repository's
         current immutable head commit, compares the RELEVANT SOURCE SUBPATH
         TREES (never bare repository commits, so unrelated upstream commits
         never bump anything), tracks the Impeccable engine via its stable
         engine-v* release tags separately from main, watches the
         license-blocked replacement originals for license-appearance signals
         only, and watches repository-root license drift.
  plan   for every drifted tracked skill: fetches the OLD (pinned) and NEW
         (resolved) upstream subtrees, derives the local<->upstream
         correspondence from catalog/upstream-update-policy.json, performs a
         deterministic three-way merge (OLD upstream, NEW upstream, LOCAL Floe
         adaptations), enforces the license/path/symlink/binary/size gates,
         the permission/dependency drift holds, the execution-fingerprint and
         instruction-code-fingerprint proof-reuse rules, the showcase evidence
         maintenance rule, and classifies each candidate into the three-tier
         automatic publication policy or an actionable hold.
  stage  materializes eligible candidate trees, deterministic package zips,
         held-state records and an exact byte-level apply set under
         --stage-root. NEVER writes sources/, packages/, reviews/, catalog
         feeds, the publication ledger, showcase/ or the pins in the live
         checkout; integration and publication stay with the Root-owned
         pipeline (workflows, signing, CAS publish).
  validate-policy
         offline structural + cross-coverage validation of the policy against
         schema/upstream-update-policy.schema.json, catalog/skills.json and
         docs/UPSTREAM-PINS.json.

Unattended execution contract (hard user requirement): every command runs
non-interactively in GitHub Actions, independent of any Mac/App/Codex online
state; no local daemon or heartbeat exists or is needed. Only public tokenless
git reads of upstream repositories happen; check/plan/stage need no secret.
Eligible updates flow to the existing Root-owned build/verify/sign/publish
pipeline; runtime/native-relevant changes are HELD with the previously
published version intact and an actionable adaptation state. Qualification is
never fabricated and emulation never counts as guest-verified.

Determinism: identical inputs (committed repo state + resolved upstream
commits + --today) produce byte-identical JSON reports. Reports are emitted
with sorted keys; nothing iterates unordered collections into output.

This module never executes package code, never signs, never publishes, and
never reads production secrets.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hubcore
import catalog_views as cv

REPO = pathlib.Path(__file__).resolve().parents[1]

REPORT_KIND_CHECK = "floe-skill-hub-upstream-check"
REPORT_KIND_PLAN = "floe-skill-hub-upstream-plan"
REPORT_KIND_STAGE = "floe-skill-hub-upstream-stage"
REPORT_VERSION = 1

POLICY_REL = "catalog/upstream-update-policy.json"
POLICY_SCHEMA_REL = "schema/upstream-update-policy.schema.json"
REGISTRY_REL = "catalog/skills.json"
PINS_REL = "docs/UPSTREAM-PINS.json"
LEDGER_REL = "catalog/publication-ledger.json"
LINKS_REL = "showcase/links.json"
IOS_FEED_REL = "catalog.json"
ANDROID_FEED_REL = "android/catalog.json"

ENGINE_TAG_PATTERN = re.compile(r"^engine-v(\d+)\.(\d+)\.(\d+)$")
LICENSE_NAME_PATTERN = re.compile(r"(license|licence|copying|notice)", re.IGNORECASE)

MACHINE_REVIEWER = "floe-skill-hub-auto-curation"

# Hold/status taxonomy (INTERFACE.json holdTaxonomy).
ST_NO_CHANGE = "no-change"
ST_UP_TO_DATE = "up-to-date"
ST_DRIFTED = "drifted"
ST_ELIGIBLE_T1 = "eligible-tier1"
ST_ELIGIBLE_T2 = "eligible-tier2"
ST_HELD_PREFIX = "held-"
HELD_CONFLICT = "held-conflict"
HELD_RUNTIME = "held-runtime-changed"
HELD_INSTRUCTION_CODE = "held-instruction-code-changed"
HELD_LICENSE = "held-license-drift"
HELD_PERMISSION = "held-permission-drift"
HELD_DEPENDENCY = "held-dependency-drift"
HELD_UNSAFE = "held-unsafe"
HELD_ADAPTATION = "held-adaptation-required"
HELD_EDITORIAL = "held-editorial-review"
HELD_PROVENANCE = "held-provenance-format"
HELD_ENGINE = "held-engine-managed"
HELD_POLICY = "held-policy-inconsistent"
HELD_BASELINE = "held-baseline-missing"
HELD_PRIOR_PROOF = "held-prior-proof-unavailable"
ST_ERROR = "error"

# Mechanical change set allowed for tier-1 guide-only candidates beyond
# upstream-derived files: the floe.json version bump and the mechanical
# provenance re-pin. Anything else that is not upstream-derived holds.
MECHANICAL_LOCAL_PATHS = ("floe.json", "references/PROVENANCE.md")

# Floe bookkeeping prose excluded from the instruction-code fingerprint
# (never model instructions; PROVENANCE.md is mechanically re-pinned).
INSTRUCTION_FINGERPRINT_EXCLUDES = (
    "references/PROVENANCE.md",
    "references/ADAPTATION-NOTES.md",
    "references/MODIFICATIONS.md",
)


class UpstreamError(hubcore.HubError):
    """Fail-closed upstream/policy/plan/stage violation."""


def _today_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def dump_report(obj):
    """Deterministic report bytes (sorted keys, stable indent, trailing NL)."""
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# exclusion / allowlist pattern matching (single-segment '*' globs only)
# --------------------------------------------------------------------------

def _glob_to_regex(pattern):
    """Restricted glob: '*' matches within one path segment, never across '/'."""
    out = []
    for ch in pattern:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return re.compile("^" + "".join(out) + "$")


class PathMatcher:
    """Compiled policy pattern list: exact paths, dir prefixes, segment globs."""

    def __init__(self, patterns):
        self.patterns = list(patterns)
        self._exact = set()
        self._prefixes = []
        self._globs = []
        for pattern in self.patterns:
            if pattern.endswith("/"):
                self._prefixes.append(pattern)
            elif "*" in pattern or "?" in pattern:
                self._globs.append((pattern, _glob_to_regex(pattern)))
            else:
                self._exact.add(pattern)

    def match(self, path):
        for prefix in self._prefixes:
            if path.startswith(prefix):
                return prefix
        if path in self._exact:
            return path
        for pattern, regex in self._globs:
            if regex.match(path):
                return pattern
        return None


def is_prose_allowlisted(path):
    """The narrow prose allowlist (publication-design DECISION B3).

    SKILL.md; references/*.md at that directory level ONLY ('*' never crosses
    '/'); references/licenses/**. Must never match references/engine-data/**
    or assets/** -- both stay inside the execution fingerprint.
    """
    if path == "SKILL.md":
        return True
    if path.startswith("references/licenses/"):
        return True
    if path.startswith("references/") and path.endswith(".md") and path.count("/") == 1:
        return True
    return False


def is_instruction_fingerprint_file(path):
    """Markdown the model reads as instructions (instruction-code surface).

    SKILL.md plus every references/**/*.md except licenses, engine-data
    (already execution fingerprint) and the Floe bookkeeping documents.
    """
    if not path.endswith(".md"):
        return False
    if path in INSTRUCTION_FINGERPRINT_EXCLUDES:
        return False
    if path.startswith("references/licenses/"):
        return False
    if path.startswith("references/engine-data/"):
        return False
    return path == "SKILL.md" or path.startswith("references/")


# --------------------------------------------------------------------------
# policy / registry / pins loading and validation
# --------------------------------------------------------------------------

def load_json_bytes(path, label):
    path = pathlib.Path(path)
    if not path.is_file():
        raise UpstreamError(f"{label} not found: {path}")
    try:
        return json.loads(path.read_bytes())
    except ValueError as error:
        raise UpstreamError(f"{label} is not valid JSON: {error}") from None


def load_inputs(root=REPO, policy_path=None, expect_counts=None):
    """Load + cross-validate policy, registry and pins. Fail closed.

    expect_counts mirrors hubcore.validate_registry's (total, builtins,
    optionals, deep) fixture contract. Production defaults retain the original
    cohort and allow appended optional entries; tests may use explicit counts.
    """
    root = pathlib.Path(root)
    policy_rel = policy_path or (root / POLICY_REL)
    policy = load_json_bytes(policy_rel, "upstream update policy")
    registry = load_json_bytes(root / REGISTRY_REL, "registry")
    pins_bytes = (root / PINS_REL).read_bytes() if (root / PINS_REL).is_file() else None
    if pins_bytes is None:
        raise UpstreamError(f"upstream pins not found: {root / PINS_REL}")
    pins_module = None
    try:
        import upstream_pins as pins_module  # entry-pins lane authority when present
        pins_doc = pins_module.parse_pins_bytes(pins_bytes)
    except ImportError:
        pins_module = None
        try:
            pins_doc = json.loads(pins_bytes)
        except ValueError as error:
            raise UpstreamError(f"docs/UPSTREAM-PINS.json is not valid JSON: {error}") from None
    except Exception as error:  # UpstreamPinError: fail closed with its message
        raise UpstreamError(f"docs/UPSTREAM-PINS.json invalid: {error}") from None
    if not isinstance(pins_doc, dict) or "repositories" not in pins_doc:
        raise UpstreamError("docs/UPSTREAM-PINS.json must carry a repositories map")
    hubcore.validate_registry(registry, expect_counts=expect_counts)
    validate_policy(policy, registry, pins_doc, pins_module)
    entries = {e["id"]: e for e in registry["skills"]}
    return {"policy": policy, "registry": registry,
            "pins": pins_doc.get("repositories") or {},
            "pinsDoc": pins_doc, "pinsModule": pins_module, "entries": entries,
            "expectCounts": expect_counts, "root": root}


def effective_pin(inputs, entry_id, repo_short):
    """The EXACT expected pin of one entry: bound override, else repo default.

    Consumes scripts/upstream_pins.py effective_pin_for_entry when the
    entry-pins lane module is present; the internal mirror keeps the same
    settled semantics (override repository identity must match; unknown
    repositories fail closed).
    """
    pins_module = inputs.get("pinsModule")
    pins_doc = inputs.get("pinsDoc") or {}
    if pins_module is not None:
        try:
            commit, _is_override = pins_module.effective_pin_for_entry(
                pins_doc, entry_id, repo_short)
            return commit
        except Exception as error:
            raise UpstreamError(f"{entry_id}: effective pin resolution failed: {error}") from None
    override = (pins_doc.get("skillOverrides") or {}).get(entry_id)
    if override is not None:
        if not isinstance(override, dict) or override.get("repository") != repo_short:
            raise UpstreamError(f"{entry_id}: skillOverride repository mismatch")
        commit = override.get("commit")
        if not isinstance(commit, str) or not hubcore.COMMIT_PATTERN.fullmatch(commit):
            raise UpstreamError(f"{entry_id}: skillOverride commit must be 40 lowercase hex")
        return commit
    default = (pins_doc.get("repositories") or {}).get(repo_short)
    if default is None:
        raise UpstreamError(f"{entry_id}: repository {repo_short} is not pinned")
    return default


def license_evidence_paths(config):
    """Exact out-of-subtree licence/notice paths, including the legacy root."""
    extra = config.get("licenseEvidencePaths", [])
    if (not isinstance(extra, list) or len(extra) > 16
            or any(not isinstance(path, str) for path in extra)
            or len(set(extra)) != len(extra)):
        raise UpstreamError("licenseEvidencePaths must be a unique array of at most 16 paths")
    root = config.get("rootLicense")
    paths = list(extra) + ([root] if root is not None else [])
    for path in paths:
        if (not isinstance(path, str) or not path or path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..") for part in path.split("/"))
                or any(ord(c) < 32 or ord(c) == 127 for c in path)):
            raise UpstreamError("license evidence must be a clean repository-relative path")
    return tuple(sorted(set(paths)))


def validate_policy(policy, registry, pins_doc, pins_module=None):
    """Structural + cross-coverage validation (mirrors the JSON schema).

    Invariants (fail closed, aggregated reasons):
      * exact root key set, schemaVersion 1, unattended github-actions-only;
      * selection partitions ALL registry ids exactly once:
        tracked + engineManaged + watchOnly + builtins + firstParty == 43;
      * tracked/engineManaged ids carry an upstream block whose repository is
        pinned in docs/UPSTREAM-PINS.json and declared in policy repositories,
        with the registry commit equal to the entry's EFFECTIVE pin (bound
        skillOverride or repository default, entry-pins contract);
      * watchOnly/builtins/firstParty ids have upstream == null (never copied);
      * builtins equal hubcore.RESERVED_BUILTIN_IDS exactly (never by label);
      * every tracked id has a skills layout block and vice versa;
      * fileMappings/relocations reference clean relative paths;
      * engine tracking declares genericMergeProhibited and its owned paths.
    """
    reasons = []
    pins = (pins_doc or {}).get("repositories") or {}
    overrides = (pins_doc or {}).get("skillOverrides") or {}

    def bad(message):
        reasons.append(message)

    if not isinstance(policy, dict):
        raise UpstreamError("policy must be a JSON object")
    required = {"schemaVersion", "policyId", "updatedAt", "description", "executionModel",
                "pinsAuthority", "registryAuthority", "repositories", "engineTracking",
                "selection", "layoutDefaults", "skills", "versioning", "gates"}
    if set(policy) != required:
        bad(f"policy root keys must be exactly {sorted(required)}")
    if policy.get("schemaVersion") != 1:
        bad("policy schemaVersion must be 1")
    if policy.get("policyId") != "floe-skill-hub-upstream-update-policy":
        bad("policy id mismatch")
    execution = policy.get("executionModel") or {}
    if execution.get("unattended") != "github-actions-only" \
            or execution.get("localDaemonsProhibited") is not True \
            or execution.get("noMacAppCodexOnlineDependency") is not True:
        bad("executionModel must pin unattended github-actions-only execution")
    if policy.get("pinsAuthority") != PINS_REL or policy.get("registryAuthority") != REGISTRY_REL:
        bad("policy authorities must be docs/UPSTREAM-PINS.json and catalog/skills.json")

    entries = {e["id"]: e for e in registry.get("skills", [])}
    selection = policy.get("selection") or {}
    tracked = list(selection.get("tracked") or [])
    engine_managed = list(selection.get("engineManaged") or [])
    watch_only = [w.get("id") for w in (selection.get("watchOnly") or [])]
    not_tracked = selection.get("notTracked") or {}
    builtins = list(not_tracked.get("builtins") or [])
    first_party = list(not_tracked.get("firstParty") or [])
    groups = {"tracked": tracked, "engineManaged": engine_managed, "watchOnly": watch_only,
              "builtins": builtins, "firstParty": first_party}
    seen = {}
    for group, ids in groups.items():
        for skill_id in ids:
            if skill_id in seen:
                bad(f"{skill_id}: appears in both {seen[skill_id]} and {group}")
            seen[skill_id] = group
            if skill_id not in entries:
                bad(f"{skill_id}: selection group {group} has no registry entry")
    missing = sorted(set(entries) - set(seen))
    if missing:
        bad(f"registry entries missing from every selection group: {missing}")
    registry_builtins = {e["id"] for e in registry.get("skills", [])
                         if e.get("kind") == "builtin"}
    if set(builtins) != registry_builtins:
        bad("policy builtins must equal the registry's builtin-kind ids exactly")
    if any(b not in hubcore.RESERVED_BUILTIN_IDS for b in builtins):
        bad("builtin ids must be the reserved App-provided ids (never by label)")
    for skill_id in builtins + first_party + watch_only:
        entry = entries.get(skill_id)
        if entry is not None and entry.get("upstream") is not None:
            bad(f"{skill_id}: excluded/watch-only entries must have upstream == null "
                "(license-blocked replacements are never re-copied automatically)")
    for skill_id in tracked + engine_managed:
        entry = entries.get(skill_id)
        if entry is None:
            continue
        upstream = entry.get("upstream")
        if not upstream:
            bad(f"{skill_id}: tracked entries require a registry upstream block")
            continue
        repo = upstream.get("repository")
        short = (repo or "").removeprefix("https://github.com/")
        if short not in pins:
            bad(f"{skill_id}: repository {short} is not pinned in {PINS_REL}")
        else:
            override = overrides.get(skill_id)
            if override is not None:
                if not isinstance(override, dict) \
                        or override.get("repository") != short:
                    bad(f"{skill_id}: skillOverride must bind the entry's own repository")
                elif override.get("commit") != upstream.get("commit"):
                    bad(f"{skill_id}: registry commit diverges from its per-entry override")
            elif pins[short] != upstream.get("commit"):
                bad(f"{skill_id}: commit {str(upstream.get('commit'))[:10]} diverges from "
                    f"the review baseline {str(pins[short])[:10]}")
        if repo not in (policy.get("repositories") or {}):
            bad(f"{skill_id}: repository {repo} is not declared in policy repositories")
        if skill_id in hubcore.APP_PROVIDED_BUILTIN_IDS:
            bad(f"{skill_id}: App-provided builtin ids can never be tracked")

    repositories = policy.get("repositories") or {}
    for url, cfg in sorted(repositories.items()):
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", url or ""):
            bad(f"repository key must be an https GitHub URL: {url!r}")
        if not isinstance(cfg, dict) or cfg.get("role") not in ("corpus", "engine", "watch-only"):
            bad(f"{url}: role must be corpus|engine|watch-only")
        if not isinstance(cfg.get("trackedRef"), str) or not cfg["trackedRef"]:
            bad(f"{url}: trackedRef required")
        if "rootLicense" not in cfg:
            bad(f"{url}: rootLicense key required (null when the repo publishes none)")
        try:
            license_evidence_paths(cfg)
        except UpstreamError as error:
            bad(f"{url}: {error}")

    skills_cfg = policy.get("skills") or {}
    for skill_id in tracked:
        if skill_id not in skills_cfg:
            bad(f"{skill_id}: tracked skill has no policy skills block")
    for skill_id in skills_cfg:
        if skill_id not in tracked:
            bad(f"{skill_id}: policy skills block without a tracked selection")
    for skill_id, cfg in sorted(skills_cfg.items()):
        if not isinstance(cfg, dict) or set(cfg) - {"relocations", "fileMappings",
                                                    "excludedUpstream", "notes"}:
            bad(f"{skill_id}: skills block keys must be relocations/fileMappings/"
                "excludedUpstream[/notes]")
            continue
        for rel in cfg.get("relocations") or []:
            if set(rel) != {"upstreamPrefix", "localPrefix"} \
                    or not rel["upstreamPrefix"].endswith("/") \
                    or not rel["localPrefix"].endswith("/") \
                    or rel["upstreamPrefix"].startswith("/") \
                    or rel["localPrefix"].startswith("/"):
                bad(f"{skill_id}: relocation must map clean trailing-slash prefixes: {rel}")
        seen_upstream = set()
        for mapping in cfg.get("fileMappings") or []:
            if set(mapping) != {"upstream", "local", "kind"} \
                    or mapping["kind"] not in ("license", "asset", "doc"):
                bad(f"{skill_id}: fileMapping needs upstream/local/kind(license|asset|doc): {mapping}")
                continue
            for key in ("upstream", "local"):
                value = mapping[key]
                if value.startswith("/") or ".." in value.split("/") or not value:
                    bad(f"{skill_id}: fileMapping {key} must be a clean relative path: {value!r}")
            if mapping["upstream"] in seen_upstream:
                bad(f"{skill_id}: duplicate fileMapping for {mapping['upstream']}")
            seen_upstream.add(mapping["upstream"])
        for pattern in cfg.get("excludedUpstream") or []:
            if not isinstance(pattern, str) or not pattern or pattern.startswith("/"):
                bad(f"{skill_id}: excludedUpstream patterns must be clean relative strings")

    engine_tracking = policy.get("engineTracking") or {}
    for name, cfg in sorted(engine_tracking.items()):
        if cfg.get("skillId") not in engine_managed:
            bad(f"engineTracking {name}: skillId must appear in selection.engineManaged")
        if cfg.get("genericMergeProhibited") is not True:
            bad(f"engineTracking {name}: genericMergeProhibited must be true")
        for required_key in ("repository", "corpusPath", "engineLock", "route", "ownedPaths",
                             "stableReleaseTagPattern"):
            if not cfg.get(required_key):
                bad(f"engineTracking {name}: {required_key} required")
        if cfg.get("repository") not in repositories:
            bad(f"engineTracking {name}: repository must be declared in policy repositories")

    for watch in selection.get("watchOnly") or []:
        if set(watch) != {"id", "originalRepository", "originalPath", "reason"}:
            bad(f"watchOnly entry keys must be id/originalRepository/originalPath/reason: {watch}")
            continue
        if not watch["originalRepository"].startswith("https://github.com/"):
            bad(f"watchOnly {watch['id']}: originalRepository must be an https GitHub URL")

    versioning = policy.get("versioning") or {}
    if versioning.get("bump") != "patch" or not versioning.get("rule"):
        bad("versioning must declare bump=patch and a rule")

    if reasons:
        raise UpstreamError("upstream update policy invalid:\n  - " + "\n  - ".join(reasons))
    return policy


# --------------------------------------------------------------------------
# upstream sources (grouped git fetches; injectable fixture for tests)
# --------------------------------------------------------------------------

def _scrubbed_git_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    })
    return env


class GitUpstreamSource:
    """Real upstream reads: tokenless public git, grouped blobless fetches.

    One scratch repository per upstream repo under `cache` (outside the
    tracked tree). Commits are fetched by immutable SHA with --depth 1 and
    --filter=blob:none (single retry without the filter when the server
    refuses it); subtrees are materialized through a cone sparse checkout so
    missing blobs arrive in one batched promisor fetch per commit.
    """

    def __init__(self, cache, timeout=600):
        self.cache = pathlib.Path(cache)
        self.timeout = timeout
        self._env = _scrubbed_git_env()

    @staticmethod
    def _slug(url):
        return url.split("github.com/")[-1].replace("/", "__")

    def _run(self, args, cwd=None, field="git", binary=False):
        proc = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                              capture_output=True, env=self._env, timeout=self.timeout)
        if proc.returncode != 0:
            raise UpstreamError(
                f"{field}: git {' '.join(args[:2])} failed: "
                f"{proc.stderr.decode('utf-8', 'replace').strip()[:400]}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")

    def _repo_dir(self, url):
        directory = self.cache / self._slug(url)
        if not directory.exists():
            directory.mkdir(parents=True)
            self._run(["init", "-q", str(directory)], field="init")
            self._run(["-C", str(directory), "remote", "add", "origin", url], field="remote")
            self._run(["-C", str(directory), "config", "core.sparseCheckout", "true"],
                      field="config")
        return directory

    def resolve_ref(self, url, ref="HEAD"):
        """(commit sha, resolved ref name) via one grouped ls-remote."""
        out = self._run(["ls-remote", "--symref", url, ref], field=f"ls-remote {url}")
        refname = ref
        sha = None
        for line in out.splitlines():
            if line.startswith("ref: "):
                refname = line[5:].split("\t")[0]
            else:
                parts = line.split("\t")
                if parts and parts[-1] in (ref, "HEAD"):
                    sha = parts[0]
        if sha is None or not hubcore.COMMIT_PATTERN.fullmatch(sha):
            raise UpstreamError(f"{url}: could not resolve ref {ref!r}")
        return sha, refname

    def list_tags(self, url, prefix=""):
        """[(tag, peeled commit sha)] for refs/tags/<prefix>* (peeled wins)."""
        out = self._run(["ls-remote", "--tags", url], field=f"ls-remote tags {url}")
        peeled = {}
        plain = {}
        for line in out.splitlines():
            sha, _, ref = line.partition("\t")
            if not ref.startswith("refs/tags/"):
                continue
            tag = ref[len("refs/tags/"):]
            if prefix and not tag.startswith(prefix):
                continue
            if tag.endswith("^{}"):
                peeled[tag[:-3]] = sha
            else:
                plain[tag] = sha
        return sorted((tag, peeled.get(tag, sha)) for tag, sha in plain.items())

    def ensure_commit(self, url, commit):
        directory = self._repo_dir(url)
        probe = subprocess.run(["git", "-C", str(directory), "cat-file", "-e", commit + "^{commit}"],
                               capture_output=True, env=self._env, timeout=self.timeout)
        if probe.returncode == 0:
            return directory
        try:
            self._run(["-C", str(directory), "fetch", "-q", "--depth", "1",
                       "--filter=blob:none", "origin", commit],
                      field=f"fetch {self._slug(url)} {commit[:10]}")
        except UpstreamError:
            # Server refused the partial-clone filter: bounded plain shallow fetch.
            self._run(["-C", str(directory), "fetch", "-q", "--depth", "1", "origin", commit],
                      field=f"fetch(full) {self._slug(url)} {commit[:10]}")
        return directory

    def commit_tree_oid(self, url, commit, subpath):
        """Git tree OID of one subpath at one commit (None when absent)."""
        directory = self.ensure_commit(url, commit)
        proc = subprocess.run(["git", "-C", str(directory), "rev-parse", f"{commit}:{subpath}"],
                              capture_output=True, env=self._env, timeout=self.timeout)
        if proc.returncode != 0:
            return None
        return proc.stdout.decode().strip()

    def commit_root_tree_oid(self, url, commit):
        directory = self.ensure_commit(url, commit)
        return self._run(["-C", str(directory), "rev-parse", f"{commit}^{{tree}}"],
                         field="root tree").strip()

    def list_tree(self, url, commit, subpath):
        """[(mode, type, blob sha, size, relpath)] for one subtree (trees only)."""
        directory = self.ensure_commit(url, commit)
        out = self._run(["-C", str(directory), "ls-tree", "-r", "-l", commit, "--",
                         subpath or "."], field="ls-tree")
        rows = []
        prefix = (subpath.rstrip("/") + "/") if subpath not in ("", ".") else ""
        for line in out.splitlines():
            meta, _, path = line.partition("\t")
            mode, obj_type, blob_sha, size = meta.split(None, 3)
            rel = path[len(prefix):] if path.startswith(prefix) else path
            rows.append((mode, obj_type, blob_sha, int(size) if size != "-" else -1, rel))
        return rows

    def read_subtree(self, url, commit, subpath):
        """Materialize one subtree's blobs (batched sparse checkout) -> {rel: bytes}."""
        directory = self.ensure_commit(url, commit)
        self._run(["-C", str(directory), "sparse-checkout", "set", "--cone", subpath],
                  field="sparse-checkout")
        self._run(["-C", str(directory), "checkout", "-q", "-f", "--detach", commit],
                  field="checkout")
        worktree = directory / subpath
        files = {}
        if worktree.is_dir():
            for path in sorted(worktree.rglob("*")):
                rel = path.relative_to(worktree).as_posix()
                if path.is_symlink():
                    files[rel] = None  # caller classifies via list_tree modes
                    continue
                if path.is_file():
                    files[rel] = path.read_bytes()
        self._run(["-C", str(directory), "checkout", "-q", "-f", "--detach", "HEAD"],
                  field="checkout-reset")
        return files

    def read_file(self, url, commit, path):
        """One exact blob at one commit (lazy single-object fetch); None if absent."""
        directory = self.ensure_commit(url, commit)
        proc = subprocess.run(["git", "-C", str(directory), "show", f"{commit}:{path}"],
                              capture_output=True, env=self._env, timeout=self.timeout)
        if proc.returncode != 0:
            return None
        return proc.stdout


class FixtureUpstreamSource:
    """In-memory offline upstream for deterministic tests.

    repos[url] = {
      "head": (sha, refname), "tags": {tag: sha},
      "commits": {sha: {"files": {fullpath: bytes}, "modes": {fullpath: mode}}}
    }
    """

    def __init__(self, repos):
        self.repos = repos

    def resolve_ref(self, url, ref="HEAD"):
        repo = self.repos[url]
        if ref == "HEAD":
            return repo["head"]
        for tag, sha in repo.get("tags", {}).items():
            if ref in (tag, "refs/tags/" + tag):
                return sha, "refs/tags/" + tag
        raise UpstreamError(f"fixture: cannot resolve {ref} for {url}")

    def list_tags(self, url, prefix=""):
        repo = self.repos[url]
        return sorted((tag, sha) for tag, sha in repo.get("tags", {}).items()
                      if not prefix or tag.startswith(prefix))

    def _files(self, url, commit):
        try:
            return self.repos[url]["commits"][commit]
        except KeyError:
            raise UpstreamError(f"fixture: unknown commit {commit[:10]} for {url}") from None

    def commit_tree_oid(self, url, commit, subpath):
        commit_data = self._files(url, commit)
        prefix = (subpath.rstrip("/") + "/") if subpath not in ("", ".") else ""
        members = sorted((path, sha256_bytes(data)) for path, data in commit_data["files"].items()
                         if path.startswith(prefix))
        if not members:
            return None
        return sha256_bytes(json.dumps(members, sort_keys=True).encode())[:40]

    def commit_root_tree_oid(self, url, commit):
        commit_data = self._files(url, commit)
        members = sorted((path, sha256_bytes(data)) for path, data in commit_data["files"].items())
        return sha256_bytes(json.dumps(members, sort_keys=True).encode())[:40]

    def list_tree(self, url, commit, subpath):
        commit_data = self._files(url, commit)
        modes = commit_data.get("modes", {})
        prefix = (subpath.rstrip("/") + "/") if subpath not in ("", ".") else ""
        rows = []
        for path, data in sorted(commit_data["files"].items()):
            if not path.startswith(prefix):
                continue
            rel = path[len(prefix):]
            mode = modes.get(path, "100644")
            obj_type = "blob" if mode != "160000" else "commit"
            rows.append((mode, obj_type, sha256_bytes(data)[:40], len(data), rel))
        return rows

    def read_subtree(self, url, commit, subpath):
        commit_data = self._files(url, commit)
        prefix = (subpath.rstrip("/") + "/") if subpath not in ("", ".") else ""
        return {path[len(prefix):]: data
                for path, data in sorted(commit_data["files"].items())
                if path.startswith(prefix)}

    def read_file(self, url, commit, path):
        commit_data = self._files(url, commit)
        return commit_data["files"].get(path)


# --------------------------------------------------------------------------
# upstream snapshot with the safety classification
# --------------------------------------------------------------------------

def snapshot_upstream_tree(source, url, commit, subpath):
    """{rel: entry} with safety classification; blob data may be None.

    entry = {"mode","type","sha","size","data","problem"}; problem marks
    content that can never be carried (symlink/submodule modes, oversize,
    native payloads, unreadable blobs). Problems are DATA: the planner turns
    a problem on a file it would carry into held-unsafe, while problems on
    excluded paths stay informational.
    """
    rows = source.list_tree(url, commit, subpath)
    data_map = None
    snapshot = {}
    for mode, obj_type, blob_sha, size, rel in rows:
        entry = {"mode": mode, "type": obj_type, "sha": blob_sha, "size": size,
                 "data": None, "problem": None}
        if obj_type != "blob":
            entry["problem"] = f"non-blob upstream tree entry (type={obj_type})"
        elif mode == "120000":
            entry["problem"] = "upstream symlink entries are never carried"
        elif mode not in ("100644", "100755"):
            entry["problem"] = f"unsupported upstream file mode {mode}"
        elif size > hubcore.MAX_FILE_BYTES:
            entry["problem"] = (f"upstream file exceeds the {hubcore.MAX_FILE_BYTES}-byte "
                                "package cap")
        snapshot[rel] = entry
    fetchable = [rel for rel, entry in snapshot.items()
                 if entry["problem"] is None]
    if fetchable:
        data_map = source.read_subtree(url, commit, subpath)
    for rel in fetchable:
        entry = snapshot[rel]
        data = (data_map or {}).get(rel)
        if data is None:
            entry["problem"] = "upstream blob unreadable at the resolved commit"
            continue
        if len(data) != entry["size"] >= 0:
            entry["problem"] = "upstream blob size mismatch"
            continue
        entry["data"] = data
        try:
            hubcore.reject_native_payload(rel, data)
        except hubcore.HubError as error:
            entry["problem"] = f"native payload gate: {error}"
            entry["data"] = None
    problems_present = any(entry["problem"] for entry in snapshot.values())
    return snapshot, problems_present


def snapshot_local_tree(root, skill_id):
    """{rel: bytes} of sources/<id> exactly as build_packages.py would pack it."""
    folder = pathlib.Path(root) / "sources" / skill_id
    if not folder.is_dir():
        raise UpstreamError(f"sources/{skill_id} is missing; cannot plan an update")
    files = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_symlink():
            raise UpstreamError(f"symlink in staged source: sources/{skill_id}/{rel}")
        if path.is_dir():
            continue
        if path.name == "release.json":
            continue  # release metadata lives in the registry, not the archive
        files[rel] = path.read_bytes()
    return files


def published_package_files(root, skill_id, version):
    """Unpacked published archive bytes for the fingerprint baseline (or None)."""
    rel = hubcore.package_path_for(skill_id, version, "ios")
    archive = pathlib.Path(root) / rel
    if not archive.is_file():
        return None
    return hubcore.check_archive_bytes(archive.read_bytes())


# --------------------------------------------------------------------------
# correspondence derivation (policy-declared; content hashes only verify)
# --------------------------------------------------------------------------

def derive_correspondence(old_snapshot, local_tree, skill_cfg):
    """Map every OLD upstream file to its local counterpart per the policy.

    Resolution order (INTERFACE.json mergeContract): explicit fileMappings >
    excludedUpstream globs > relocation prefixes (longest first) > path
    identity. Content hashes never invent mappings; they classify a mapped
    pair as verbatim/adapted and DETECT undeclared carries fail-closed:
      * an old upstream file that is neither mapped nor excluded is a policy
        gap (held-policy-inconsistent upstream side);
      * a local file with no correspondence whose bytes equal an unmapped old
        upstream file is a suspected undeclared carry (same hold), because an
        upstream change to it would silently miss the package.
    Returns a dict with mappings/excluded/problems/floeOwned.
    """
    file_mappings = {}
    mapping_kind = {}
    for mapping in skill_cfg.get("fileMappings") or []:
        file_mappings[mapping["upstream"]] = mapping["local"]
        mapping_kind[mapping["upstream"]] = mapping.get("kind")
    exclusions = PathMatcher(skill_cfg.get("excludedUpstream") or [])
    relocations = sorted(skill_cfg.get("relocations") or [],
                         key=lambda r: -len(r["upstreamPrefix"]))

    mappings = {}
    excluded = {}
    problems = []
    mapped_local = set()
    for rel in sorted(old_snapshot):
        if rel in file_mappings:
            mappings[rel] = {"local": file_mappings[rel], "rule": "fileMapping",
                             "kind": mapping_kind.get(rel)}
            mapped_local.add(file_mappings[rel])
            continue
        pattern = exclusions.match(rel)
        if pattern is not None:
            excluded[rel] = pattern
            continue
        if rel in local_tree:
            mappings[rel] = {"local": rel, "rule": "identity", "kind": None}
            mapped_local.add(rel)
            continue
        target = None
        for relocation in relocations:
            if rel.startswith(relocation["upstreamPrefix"]):
                target = relocation["localPrefix"] + rel[len(relocation["upstreamPrefix"]):]
                break
        if target is not None and target in local_tree:
            mappings[rel] = {"local": target, "rule": "relocation", "kind": None}
            mapped_local.add(target)
            continue
        problems.append({
            "upstream": rel,
            "problem": "undeclared-not-carried",
            "detail": ("the pinned upstream file is neither mapped into the local layout nor "
                       "declared excluded; extend catalog/upstream-update-policy.json "
                       "(fileMappings/relocations/excludedUpstream) after curation review"),
            "proposedTarget": target,
        })

    # Suspected undeclared carries: local bytes identical to an unmapped old file.
    unmapped_old = {rel: entry for rel, entry in old_snapshot.items()
                    if rel not in mappings and rel not in excluded
                    and entry.get("data") is not None}
    if unmapped_old:
        by_hash = {}
        for rel, entry in unmapped_old.items():
            by_hash.setdefault(sha256_bytes(entry["data"]), []).append(rel)
        for local_rel in sorted(set(local_tree) - mapped_local):
            digest = sha256_bytes(local_tree[local_rel])
            if digest in by_hash:
                problems.append({
                    "upstream": by_hash[digest][0],
                    "local": local_rel,
                    "problem": "suspected-undeclared-carry",
                    "detail": ("the local file is byte-identical to an unmapped pinned upstream "
                               "file; declare the mapping so upstream changes cannot miss it"),
                })

    floe_owned = sorted(set(local_tree) - mapped_local)
    return {"mappings": mappings, "excluded": excluded, "problems": problems,
            "floeOwned": floe_owned}


# --------------------------------------------------------------------------
# deterministic three-way merge (hunk-level diff3 over lines)
# --------------------------------------------------------------------------

def _hunks(base_lines, side_lines):
    """[(start, end, replacement_lines)] of side vs base over shared indices."""
    import difflib
    matcher = difflib.SequenceMatcher(None, base_lines, side_lines, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            out.append((i1, i2, side_lines[j1:j2]))
    return out


def merge_three_way(old_bytes, new_bytes, local_bytes):
    """Deterministic three-way merge of NEW upstream + LOCAL Floe edits over OLD.

    Text (UTF-8) files merge hunk-wise: changes anchored to disjoint OLD line
    ranges with at least one unchanged line between them both apply; identical
    changes deduplicate; overlapping, adjacent or divergent regions are
    conflicts. Non-UTF-8 files never merge line-wise: if both sides changed
    them, that is a conflict. Returns (merged_bytes | None, conflicts).
    """
    if old_bytes == new_bytes:
        return local_bytes, []
    if local_bytes == old_bytes:
        return new_bytes, []
    if local_bytes == new_bytes:
        return local_bytes, []
    try:
        old_text = old_bytes.decode("utf-8")
        new_text = new_bytes.decode("utf-8")
        local_text = local_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None, [{"kind": "binary-divergent",
                       "detail": "binary file changed on both the upstream and the local side"}]
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    local_lines = local_text.splitlines(keepends=True)
    local_hunks = _hunks(old_lines, local_lines)
    upstream_hunks = _hunks(old_lines, new_lines)

    # Pair hunks into conflict classes: exact-equal changes deduplicate,
    # overlapping or directly adjacent (no stable anchor line between) hunks
    # conflict, everything else applies independently.
    events = []
    matched_upstream = set()
    for l_index, (l_start, l_end, l_repl) in enumerate(local_hunks):
        overlapping = []
        for u_index, (u_start, u_end, u_repl) in enumerate(upstream_hunks):
            if u_index in matched_upstream:
                continue
            if l_start < u_end and u_start < l_end:
                overlapping.append((u_index, u_start, u_end, u_repl))
            elif l_end == u_start or u_end == l_start:
                overlapping.append((u_index, u_start, u_end, u_repl))
        if not overlapping:
            events.append((l_start, l_end, l_repl, "local"))
            continue
        if len(overlapping) == 1:
            u_index, u_start, u_end, u_repl = overlapping[0]
            if (u_start, u_end, u_repl) == (l_start, l_end, l_repl):
                matched_upstream.add(u_index)
                events.append((l_start, l_end, l_repl, "both"))
                continue
        conflicts = []
        for u_index, u_start, u_end, u_repl in overlapping:
            matched_upstream.add(u_index)
            conflicts.append({
                "kind": "divergent-region",
                "oldRange": [min(l_start, u_start), max(l_end, u_end)],
                "localPreview": _preview(l_repl),
                "upstreamPreview": _preview(u_repl),
                "localLineCount": len(l_repl),
                "upstreamLineCount": len(u_repl),
            })
        return None, conflicts
    for u_index, (u_start, u_end, u_repl) in enumerate(upstream_hunks):
        if u_index in matched_upstream:
            continue
        # Unmatched upstream hunks cannot overlap or touch a local hunk (that
        # case returned a conflict or deduplicated above), so they apply.
        events.append((u_start, u_end, u_repl, "upstream"))
    events.sort(key=lambda e: (e[0], e[1]))

    out = []
    cursor = 0
    for start, end, repl, _origin in events:
        if start < cursor:
            return None, [{"kind": "merge-order", "detail": "internal: overlapping apply order"}]
        out.extend(old_lines[cursor:start])
        out.extend(repl)
        cursor = end
    out.extend(old_lines[cursor:])
    return "".join(out).encode("utf-8"), []


def _preview(lines, limit=2, width=120):
    return [line[:width] for line in lines[:limit]]


# --------------------------------------------------------------------------
# fingerprints
# --------------------------------------------------------------------------

def execution_fingerprint(files, extra_bindings=None):
    """Publication-design DECISION B3 executionFingerprint, exactly.

    sha256 over UTF-8 newline-joined lines '<relativePath> <blobSha256>'
    sorted by path for every package member NOT matching the narrow prose
    allowlist and NOT floe.json, PLUS the final line
    'floe.json <sha256 of hubcore.encoded(manifest minus version)>'.
    Stable across the mechanical version bump; deny-by-default: anything not
    provably prose (scripts/**, assets/**, references/engine-data/**, locks,
    descriptors, .ts/.json/.csv/.jsonl/.bib/.mplstyle ...) is inside.
    extra_bindings: optional [(label, sha256hex)] appended as '<label> <sha>'
    lines (engine descriptor/artifact bindings for engine-managed packages;
    the tracker never constructs those candidates itself).
    """
    lines = []
    for path in sorted(files):
        if path == "floe.json" or is_prose_allowlisted(path):
            continue
        lines.append(f"{path} {sha256_bytes(files[path])}")
    manifest_blob = files.get("floe.json")
    if manifest_blob is not None:
        manifest = json.loads(manifest_blob)
        manifest.pop("version", None)
        lines.append(f"floe.json {sha256_bytes(hubcore.encoded(manifest))}")
    for label, digest in sorted(extra_bindings or []):
        lines.append(f"{label} {digest}")
    return {"digest": sha256_bytes("\n".join(lines).encode("utf-8")),
            "includedPaths": sorted(p.split(" ", 1)[0] for p in lines)}


_CODE_FENCE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})(.*)$")
_INLINE_CODE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)


def instruction_code_units(markdown_bytes):
    """Extract the command/code surface of one instruction markdown file.

    Units in document order: fenced code blocks (fence char/run, info string
    and body) and inline code spans. Prose between them is NOT part of the
    unit digest, so pure prose edits keep the fingerprint stable while any
    changed command or code inside instructions is a runtime-relevant change
    ("do not treat text extension as safe by itself").
    """
    try:
        text = markdown_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return ["<binary:" + sha256_bytes(markdown_bytes) + ">"]
    units = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        match = _CODE_FENCE.match(lines[index])
        if match:
            indent, fence, info = match.groups()
            body = []
            index += 1
            while index < len(lines):
                close = _CODE_FENCE.match(lines[index])
                if close and close.group(2)[0] == fence[0] and len(close.group(2)) >= len(fence) \
                        and not close.group(3).strip():
                    index += 1
                    break
                body.append(lines[index])
                index += 1
            units.append("FENCE\x00" + fence[0] + "\x00" + info.strip() + "\x00" + "\n".join(body))
            continue
        index += 1
    # Inline code spans from the non-fenced prose. Rebuild prose without the
    # fenced regions by re-scanning (cheap and exact for the unit digest).
    prose_text = _strip_fences(text)
    for match in _INLINE_CODE.finditer(prose_text):
        units.append("INLINE\x00" + match.group(2))
    digest_source = "\n".join(f"[{len(u)}]{u}" for u in units)
    return [digest_source]


def _strip_fences(text):
    out = []
    in_fence = False
    fence_char = None
    fence_len = 0
    for line in text.split("\n"):
        match = _CODE_FENCE.match(line)
        if match and not in_fence:
            in_fence = True
            fence_char = match.group(2)[0]
            fence_len = len(match.group(2))
            continue
        if in_fence and match and match.group(2)[0] == fence_char \
                and len(match.group(2)) >= fence_len and not match.group(3).strip():
            in_fence = False
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def instruction_code_fingerprint(files):
    """{path: sha256} of extracted code units for every instruction markdown."""
    details = {}
    for path in sorted(files):
        if not is_instruction_fingerprint_file(path):
            continue
        units = instruction_code_units(files[path])
        details[path] = sha256_bytes(units[0].encode("utf-8")) if units else None
    combined = "\n".join(f"{path} {digest or '-'}" for path, digest in sorted(details.items()))
    return {"digest": sha256_bytes(combined.encode("utf-8")), "details": details}


def manifest_grants(files):
    """The declared permission surface of one tree (capabilities/tools/...)."""
    blob = files.get("floe.json")
    if blob is None:
        return None
    manifest = json.loads(blob)
    return {
        "capabilities": sorted(manifest.get("capabilities", [])),
        "tools": sorted(manifest.get("tools", [])),
        "scriptRuntime": manifest.get("scriptRuntime", "none"),
        "pythonPackages": sorted(p["spec"].lower() for p in manifest.get("pythonPackages", [])),
        "platforms": sorted(manifest.get("platforms", [])),
    }


DEPENDENCY_SURFACES = ("references/dependencies.json", "references/requirements.lock.txt")


def dependency_surface(files):
    return {path: sha256_bytes(files[path]) for path in DEPENDENCY_SURFACES if path in files}


# --------------------------------------------------------------------------
# mechanical, fail-closed updaters (provenance re-pin, manifest version)
# --------------------------------------------------------------------------

PIN_LINE_PATTERN = re.compile(r"^- Pinned commit: ")
INVENTORY_LINE = re.compile(r"^- `([^`]+)` sha256 `([0-9a-f]{64})`$")
INVENTORY_HEADING = "## File inventory"


def update_provenance(data, old_pin, new_pin, today, candidate_files,
                      old_repo_tree=None, new_repo_tree=None,
                      old_subtree_tree=None, new_subtree_tree=None):
    """Strict mechanical re-pin of references/PROVENANCE.md.

    Only mechanical operations happen, each pattern-verified:
      1. every occurrence of the exact old pin sha is replaced by the new
         pin; the old repository-root / subtree tree shas are replaced too,
         but ONLY when they actually appear in the document (provenance
         formats vary: some embed tree shas, some do not);
      2. one dated re-pin note line is inserted directly after the single
         '- Pinned commit:' line;
      3. when a '## File inventory' section exists, its '- `path` sha256
         `hex`' body is regenerated from the final candidate tree (self-hash
         intentionally omitted), preserving the heading bytes.
    Any unexpected shape returns (None, problem) so the candidate holds
    (held-provenance-format) instead of corrupting an authored document.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "PROVENANCE.md is not UTF-8"
    lines = text.split("\n")
    pin_indices = [i for i, line in enumerate(lines) if PIN_LINE_PATTERN.match(line)]
    if len(pin_indices) != 1:
        return None, f"expected exactly one '- Pinned commit:' line, found {len(pin_indices)}"
    if old_pin not in text:
        return None, "the pinned commit sha does not appear in PROVENANCE.md"

    updated = text.replace(old_pin, new_pin)
    if old_repo_tree and new_repo_tree and old_repo_tree in updated:
        updated = updated.replace(old_repo_tree, new_repo_tree)
    if old_subtree_tree and new_subtree_tree and old_subtree_tree in updated:
        updated = updated.replace(old_subtree_tree, new_subtree_tree)
    lines = updated.split("\n")
    pin_indices = [i for i, line in enumerate(lines) if PIN_LINE_PATTERN.match(line)]
    if len(pin_indices) != 1:
        return None, "re-pin produced an unexpected pin-line count"
    note = (f"- Upstream update: re-pinned from `{old_pin}` to `{new_pin}` on {today} by the "
            "automatic upstream tracker (docs/UPSTREAM-TRACKING.md).")
    lines.insert(pin_indices[0] + 1, note)

    heading_indices = [i for i, line in enumerate(lines) if line.startswith(INVENTORY_HEADING)]
    if heading_indices:
        if len(heading_indices) != 1:
            return None, "multiple '## File inventory' headings"
        start = heading_indices[0]
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("#"):
                end = j
                break
        tail = lines[end:]
        regenerated = []
        for path in sorted(candidate_files):
            if path == "references/PROVENANCE.md":
                continue
            regenerated.append(f"- `{path}` sha256 `{sha256_bytes(candidate_files[path])}`")
        if not regenerated:
            return None, "the inventory regeneration produced no entries"
        separator = [""] if end < len(lines) else []
        lines = lines[:start + 1] + regenerated + separator + tail
    result = "\n".join(lines)
    if text.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result.encode("utf-8"), None


def bump_manifest_version(data, new_version):
    """Rewrite floe.json 'version' preserving the file's exact JSON formatting.

    The formatter is detected by round-tripping the original bytes; when no
    supported canonical form reproduces them exactly the update holds
    (held-manifest-format) rather than reflowing a published shape.
    """
    try:
        doc = json.loads(data)
    except ValueError as error:
        return None, f"floe.json is not valid JSON: {error}"
    if not isinstance(doc, dict) or "version" not in doc:
        return None, "floe.json carries no version field"
    formatters = [
        ("compact-sorted", lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True,
                                                separators=(",", ":")).encode("utf-8")),
        ("compact-sorted-nl", lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode("utf-8") + b"\n"),
        ("pretty-sorted", lambda d: hubcore.pretty(d)),
        ("pretty-insertion", lambda d: (json.dumps(d, ensure_ascii=False, indent=2)
                                        + "\n").encode("utf-8")),
    ]
    for name, formatter in formatters:
        if formatter(doc) == data:
            updated = dict(doc)
            updated["version"] = new_version
            return formatter(updated), None
    return None, "floe.json formatting does not round-trip through a supported canonical form"


def rewrite_json_preserving_format(original_bytes, mutate):
    """Load JSON, apply `mutate(doc)`, re-emit in the file's exact format."""
    doc = json.loads(original_bytes)
    formatters = [
        ("pretty-sorted", lambda d: hubcore.pretty(d)),
        ("pretty-insertion-nl", lambda d: (json.dumps(d, ensure_ascii=False, indent=2)
                                           + "\n").encode("utf-8")),
        ("pretty-insertion", lambda d: json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8")),
        ("pretty1-insertion-nl", lambda d: (json.dumps(d, ensure_ascii=False, indent=1)
                                            + "\n").encode("utf-8")),
        ("compact-sorted", lambda d: hubcore.encoded(d)),
    ]
    chosen = None
    for name, formatter in formatters:
        if formatter(doc) == original_bytes:
            chosen = formatter
            break
    if chosen is None:
        raise UpstreamError("JSON file format does not round-trip through a supported "
                            "canonical form; refusing to rewrite it")
    mutate(doc)
    return chosen(doc)


# --------------------------------------------------------------------------
# version proposal + published-version inventory
# --------------------------------------------------------------------------

def bump_patch(version):
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def used_versions(root, skill_id, registry_entry):
    """Every (id, version) already materialized or published anywhere."""
    root = pathlib.Path(root)
    used = set()
    for prefix in ("", "android/"):
        folder = root / prefix / "packages" / skill_id
        if folder.is_dir():
            used.update(child.name for child in folder.iterdir() if child.is_dir())
    ledger_path = root / LEDGER_REL
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_bytes())
            for row in ledger.get("publications", []):
                for offer in row.get("offers", []):
                    if offer.get("id") == skill_id:
                        used.add(offer.get("version"))
        except (ValueError, TypeError, AttributeError):
            pass  # malformed ledger data is the publisher gate's problem, not ours
    for feed_rel in sorted(cv.FEED_FILES):
        feed_path = root / feed_rel
        if feed_path.is_file():
            try:
                feed = json.loads(feed_path.read_bytes())
                for entry in feed.get("entries", []):
                    if entry.get("id") == skill_id:
                        used.add(entry.get("version"))
            except (ValueError, TypeError, AttributeError):
                pass
    if registry_entry.get("versionTarget"):
        used.add(registry_entry["versionTarget"])
    first_party = registry_entry.get("firstParty") or {}
    for key in ("releasedVersion", "stagedSourceVersion"):
        if first_party.get(key):
            used.add(first_party[key])
    return {v for v in used if isinstance(v, str)}


def propose_version(current_version, used):
    """Deterministic next unused patch version (never reuses a published one)."""
    candidate = bump_patch(current_version)
    for _ in range(1000):
        if candidate not in used:
            return candidate
        candidate = bump_patch(candidate)
    raise UpstreamError(f"cannot propose an unused version after {current_version}")


# --------------------------------------------------------------------------
# showcase evidence maintenance (read-only; output is a proposal map)
# --------------------------------------------------------------------------

def maintain_showcase_evidence(links_doc, skill_id, current_files, candidate_files):
    """Maintain showcase/links.json evidence for one candidate.

    For every evidence record citing sources/<skill_id>/<rel>:
      * unchanged file            -> maintained (record stays valid);
      * changed file, exact cited line block survives UNIQUELY (lines may
        relocate) -> proposed {sha256(candidate file), new lineStart/lineEnd};
      * changed file, block absent or ambiguous -> held needs-editorial-review
        (never a blind hash rewrite, never a relationship-claim change);
      * pinned target URLs are never rewritten, only flagged pinStale when
        they embed the old upstream commit.
    Returns {"records": [...], "held": [...], "proposedCount": n}.
    """
    entries = (links_doc or {}).get("entries", {}).get(skill_id) or {}
    records = []
    held = []
    proposed = 0
    prefix = f"sources/{skill_id}/"
    for link_index, link in enumerate(entries.get("links") or []):
        target_url = ((link.get("target") or {}).get("url")) or ""
        for evidence_index, record in enumerate(link.get("evidence") or []):
            ref = {"linkIndex": link_index, "evidenceIndex": evidence_index,
                   "file": record.get("file")}
            file_rel = record.get("file")
            if not isinstance(file_rel, str) or not file_rel.startswith(prefix):
                held.append(dict(ref, reason="evidence cites a path outside sources/<id>/; "
                                             "editorial review required"))
                continue
            rel = file_rel[len(prefix):]
            current = current_files.get(rel)
            candidate = candidate_files.get(rel)
            if candidate is None:
                held.append(dict(ref, reason="cited file removed by the candidate; editorial "
                                             "review required"))
                continue
            if current is not None and current == candidate:
                records.append(dict(ref, state="maintained"))
                continue
            if current is None:
                held.append(dict(ref, reason="cited file absent from the current staged source"))
                continue
            old_lines = current.decode("utf-8", "strict").splitlines(keepends=True) \
                if _is_utf8(current) else None
            new_lines = candidate.decode("utf-8", "strict").splitlines(keepends=True) \
                if _is_utf8(candidate) else None
            start, end = record.get("lineStart"), record.get("lineEnd")
            if old_lines is None or new_lines is None:
                held.append(dict(ref, reason="cited file is not UTF-8 text; editorial review "
                                             "required"))
                continue
            if not isinstance(start, int) or not isinstance(end, int) \
                    or start < 1 or end < start or end > len(old_lines):
                held.append(dict(ref, reason=f"cited line range {start}..{end} invalid for the "
                                             "current file; editorial review required"))
                continue
            block = old_lines[start - 1:end]
            occurrences = [i for i in range(0, len(new_lines) - len(block) + 1)
                           if new_lines[i:i + len(block)] == block]
            if len(occurrences) != 1:
                held.append(dict(ref, reason=f"the exact cited line block occurs "
                                             f"{len(occurrences)} times in the candidate file; "
                                             "evidence must be re-anchored editorially "
                                             "(needs-editorial-review, never a blind rewrite)",
                                 occurrences=len(occurrences)))
                continue
            new_start = occurrences[0] + 1
            proposed += 1
            records.append(dict(ref, state="proposed",
                                proposed={"file": file_rel,
                                          "sha256": sha256_bytes(candidate),
                                          "lineStart": new_start,
                                          "lineEnd": new_start + len(block) - 1}))
    return {"records": records, "held": held, "proposedCount": proposed}


def _is_utf8(data):
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def apply_evidence_proposals(links_bytes, skill_id, records):
    """Return updated links.json bytes with the proposed evidence applied."""
    proposed = {(r["linkIndex"], r["evidenceIndex"]): r["proposed"]
                for r in records if r.get("state") == "proposed"}
    if not proposed:
        return links_bytes

    def mutate(doc):
        links = doc.get("entries", {}).get(skill_id, {}).get("links", [])
        for (link_index, evidence_index), replacement in sorted(proposed.items()):
            evidence = links[link_index].get("evidence") or []
            record = evidence[evidence_index]
            if record.get("file") != replacement["file"]:
                raise UpstreamError("showcase evidence proposal drifted from the document")
            record["sha256"] = replacement["sha256"]
            record["lineStart"] = replacement["lineStart"]
            record["lineEnd"] = replacement["lineEnd"]

    return rewrite_json_preserving_format(links_bytes, mutate)


# --------------------------------------------------------------------------
# prior guest proof binding (tier 2 reuse; read-only, never fabricated)
# --------------------------------------------------------------------------

def load_prior_proof(root, skill_id, prior_version, prior_content_digest, prior_package_sha256):
    """Verify the real signed prior runtime proof for a scripted skill.

    Binds (publication-design DECISION B3 tier 2): the prior review record
    bytes at reviews/<id>/<priorVersion>.review.json, its production Ed25519
    envelope, reviewStage guest-execution-qualified with execution
    {linux, riscv64, guest-verified}, digest equality with the published
    package, and the ledger-verified publication pin carrying that exact
    (id, version, contentDigest). Any failure makes the proof unavailable
    with reasons; nothing here can invent a proof.
    """
    root = pathlib.Path(root)
    facts = {"available": False, "reasons": [], "reviewSha256": None, "publicationPin": None,
             "keyID": None, "reviewStage": None, "execution": None,
             "priorContentDigest": prior_content_digest, "priorVersion": prior_version}

    def refuse(reason):
        facts["reasons"].append(reason)
        return facts

    record_path = root / "reviews" / skill_id / f"{prior_version}.review.json"
    envelope_path = pathlib.Path(str(record_path) + ".sig")
    if not record_path.is_file() or not envelope_path.is_file():
        return refuse("prior review record or its signature envelope is missing")
    try:
        import build_catalog
        trust = build_catalog.load_trust(root)
        if not trust:
            return refuse("no configured public trust (public-key.json) to verify the prior proof")
        record_bytes = record_path.read_bytes()
        key_id = hubcore.verify_envelope(record_bytes, envelope_path.read_bytes(), trust)
        if key_id == hubcore.FIXTURE_KEY_ID:
            return refuse("prior proof is signed with the fixture identity")
        record = json.loads(record_bytes)
        hubcore.validate_review(record)
    except (hubcore.HubError, ValueError) as error:
        return refuse(f"prior proof verification failed: {error}")
    if record.get("reviewStage") != "guest-execution-qualified":
        return refuse(f"prior review stage is {record.get('reviewStage')!r}, not "
                      "guest-execution-qualified")
    execution = record.get("execution")
    if execution != {"os": "linux", "arch": "riscv64", "evidence": "guest-verified"}:
        return refuse(f"prior execution plane is {execution}, not the real guest proof shape")
    if record.get("contentDigest") != prior_content_digest:
        return refuse("prior review contentDigest does not match the published package")
    if record.get("packageSha256") != prior_package_sha256:
        return refuse("prior review packageSha256 does not match the published archive")
    facts.update({"reviewSha256": sha256_bytes(record_bytes), "keyID": key_id,
                  "reviewStage": record["reviewStage"], "execution": execution})
    try:
        import publication_immutability
        rows = publication_immutability.verify_ledger(root / LEDGER_REL, root)
    except (hubcore.HubError, ValueError, OSError) as error:
        return refuse(f"publication ledger verification failed: {error}")
    pins = sorted({row["publication"] for row in rows
                   if any(offer["id"] == skill_id and offer["version"] == prior_version
                          and offer["contentDigest"] == prior_content_digest
                          for offer in row["offers"])})
    if not pins:
        return refuse("the prior version is not covered by the verified publication ledger")
    facts["available"] = True
    facts["publicationPin"] = pins[-1]
    facts["publicationPins"] = pins
    return facts


# --------------------------------------------------------------------------
# the per-skill planner
# --------------------------------------------------------------------------

def _map_new_upstream_path(upstream_rel, skill_cfg, local_tree, corr):
    """Target local path for a file ADDED by the new upstream commit."""
    for mapping in skill_cfg.get("fileMappings") or []:
        if mapping["upstream"] == upstream_rel:
            return mapping["local"], "fileMapping"
    if PathMatcher(skill_cfg.get("excludedUpstream") or []).match(upstream_rel):
        return None, "excluded"
    for relocation in sorted(skill_cfg.get("relocations") or [],
                             key=lambda r: -len(r["upstreamPrefix"])):
        if upstream_rel.startswith(relocation["upstreamPrefix"]):
            return (relocation["localPrefix"]
                    + upstream_rel[len(relocation["upstreamPrefix"]):]), "relocation"
    return upstream_rel, "identity"


def plan_skill(skill_id, entry, skill_cfg, old_snapshot, new_snapshot, local_tree,
               published_files, published_version, root, today, links_doc,
               root_license_changed=False, prior_proof=None, repo_url=None,
               head_commit=None, pinned_repo_tree=None, head_repo_tree=None,
               pinned_subtree_tree=None, head_subtree_tree=None):
    """Full deterministic candidate plan for ONE drifted tracked skill.

    Returns the plan dict: status, hold reasons (code/detail/repair), file
    actions, candidate facts (tree, digests, fingerprints), proposed version,
    registry/pin deltas, proposed review skeleton and the showcase evidence
    maintenance map. Never writes anything.
    """
    reasons = []
    actions = []
    gates = []

    def hold(code, detail, repair):
        reasons.append({"code": code, "detail": detail, "repair": repair})

    published_version = published_version or entry.get("versionTarget")
    plan = {
        "id": skill_id,
        "repository": repo_url or entry["upstream"]["repository"],
        "upstreamPath": entry["upstream"]["path"],
        "pinnedCommit": entry["upstream"]["commit"],
        "headCommit": head_commit,
        "currentVersion": published_version,
        "today": today,
    }

    corr = derive_correspondence(old_snapshot, local_tree, skill_cfg)
    for problem in corr["problems"]:
        hold(HELD_POLICY, f"{problem['problem']}: {problem['upstream']}"
             + (f" -> {problem.get('local')}" if problem.get("local") else ""),
             problem["detail"])

    if root_license_changed:
        hold(HELD_LICENSE, "the repository-root license file changed between the pinned and "
                           "resolved commits",
             "re-audit the license before any content update; the local license copy is never "
             "regenerated automatically")

    candidate = dict(local_tree)
    mapped_locals = {m["local"] for m in corr["mappings"].values()}

    for upstream_rel in sorted(set(old_snapshot) | set(new_snapshot)):
        old_entry = old_snapshot.get(upstream_rel)
        new_entry = new_snapshot.get(upstream_rel)
        if upstream_rel in corr["excluded"]:
            if old_entry is None and new_entry is not None:
                actions.append({"upstream": upstream_rel, "action": "excluded-added",
                                "pattern": corr["excluded"][upstream_rel]})
            elif (old_entry and new_entry and old_entry["sha"] != new_entry["sha"]):
                actions.append({"upstream": upstream_rel, "action": "excluded-changed",
                                "pattern": corr["excluded"][upstream_rel]})
            continue
        mapping = corr["mappings"].get(upstream_rel)
        if mapping is None:
            # File added by the NEW commit (not present at the pin).
            if new_entry is None:
                continue
            target, rule = _map_new_upstream_path(upstream_rel, skill_cfg, local_tree, corr)
            if target is None:
                actions.append({"upstream": upstream_rel, "action": "excluded-added"})
                continue
            if target in local_tree:
                hold(HELD_ADAPTATION,
                     f"new upstream file {upstream_rel} maps onto existing local path {target}",
                     "curation decision required: merge into or rename around the existing "
                     "Floe-owned file, then declare it in the policy")
                continue
            parent = target.rsplit("/", 1)[0] + "/" if "/" in target else ""
            if rule == "identity":
                if parent:
                    if not any(p.startswith(parent) for p in local_tree):
                        hold(HELD_ADAPTATION,
                             f"new upstream file {upstream_rel} would create the new local "
                             f"area {parent}",
                             "declare a relocation/exclusion in the policy or curate the file "
                             "manually")
                        continue
                else:
                    hold(HELD_ADAPTATION,
                         f"new upstream root-level file {upstream_rel} has no carried local area",
                         "curation decision required: declare where (or whether) this file is "
                         "carried in the policy before it can be imported")
                    continue
            if new_entry["problem"]:
                hold(HELD_UNSAFE, f"new upstream file {upstream_rel}: {new_entry['problem']}",
                     "unsafe content is never carried; curate manually if wanted")
                continue
            candidate[target] = new_entry["data"]
            actions.append({"upstream": upstream_rel, "local": target, "action": "add",
                            "rule": rule, "sha256": sha256_bytes(new_entry["data"])})
            continue

        local_rel = mapping["local"]
        local_data = local_tree.get(local_rel)
        old_data = old_entry["data"] if old_entry else None
        new_data = new_entry["data"] if new_entry else None

        if new_entry and new_entry["problem"] and (old_entry is None
                                                   or old_entry["sha"] != new_entry["sha"]):
            hold(HELD_UNSAFE, f"upstream {upstream_rel}: {new_entry['problem']}",
                 "unsafe content is never carried automatically")
            continue
        if old_entry and old_entry["problem"] and old_data is None and local_data is not None \
                and (new_entry is None or new_entry["sha"] == old_entry["sha"]):
            actions.append({"upstream": upstream_rel, "local": local_rel,
                            "action": "keep", "note": f"pinned-side problem ignored: "
                                                      f"{old_entry['problem']}"})
            continue

        if mapping.get("kind") == "license":
            if new_entry is None or old_data != new_data:
                hold(HELD_LICENSE,
                     f"the upstream license file {upstream_rel} changed or disappeared",
                     "license re-audit required before any carry; license bytes are never "
                     "auto-adopted")
            else:
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "keep-license-unchanged"})
            continue

        if old_entry and new_entry:
            if old_data == new_data:
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "keep",
                                "note": "upstream unchanged at the resolved commit"})
                continue
            if local_data == old_data:
                candidate[local_rel] = new_data
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "carry-new",
                                "sha256Old": sha256_bytes(old_data),
                                "sha256New": sha256_bytes(new_data)})
                continue
            if local_data == new_data:
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "keep-converged"})
                continue
            merged, conflicts = merge_three_way(old_data, new_data, local_data)
            if merged is None:
                hold(HELD_CONFLICT,
                     f"three-way merge conflict in {local_rel} (upstream {upstream_rel})",
                     "resolve the conflict in sources/" + skill_id + "/" + local_rel
                     + " or adjust the policy mapping; the current version stays published")
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "conflict", "conflicts": conflicts})
                continue
            if merged == local_data:
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "keep", "note": "merge result equals the local file"})
            else:
                candidate[local_rel] = merged
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "merge",
                                "sha256Old": sha256_bytes(old_data),
                                "sha256New": sha256_bytes(new_data),
                                "sha256Merged": sha256_bytes(merged)})
            continue

        if old_entry and new_entry is None:
            if local_data == old_data:
                candidate.pop(local_rel, None)
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "remove"})
            else:
                hold(HELD_CONFLICT,
                     f"upstream removed {upstream_rel} but the local copy is adapted",
                     "decide whether the Floe adaptation survives the upstream removal; the "
                     "current version stays published")
                actions.append({"upstream": upstream_rel, "local": local_rel,
                                "action": "removal-conflict"})
            continue

    # --- package gates over the merged candidate -----------------------------
    gate_error = None
    try:
        manifest, _front = hubcore.validate_package_files(dict(candidate), require_notice=True)
        gates.append({"gate": "hubcore.validate_package_files", "passed": True})
    except hubcore.HubError as error:
        gate_error = str(error)
        gates.append({"gate": "hubcore.validate_package_files", "passed": False,
                      "detail": gate_error})
        hold(HELD_UNSAFE, f"candidate tree fails the package gates: {error}",
             "fix the content or the policy mapping; unsafe candidates are never staged")

    # --- published baseline comparisons --------------------------------------
    if published_files is None:
        hold(HELD_BASELINE, f"no published package for {skill_id} {published_version}",
             "the published baseline is required for fingerprint/proof comparisons")
        plan.update({"status": _status(reasons, None), "reasons": reasons,
                     "fileActions": actions, "gateResults": gates})
        return plan

    published_grants = manifest_grants(published_files)
    candidate_grants = manifest_grants(candidate)
    if published_grants != candidate_grants:
        hold(HELD_PERMISSION,
             f"declared grants would change: {json.dumps(published_grants, sort_keys=True)} -> "
             f"{json.dumps(candidate_grants, sort_keys=True)}",
             "new permissions are never silently approved; route through curation/review")
    published_deps = dependency_surface(published_files)
    candidate_deps = dependency_surface(candidate)
    if published_deps != candidate_deps:
        hold(HELD_DEPENDENCY,
             f"dependency surface would change: {published_deps} -> {candidate_deps}",
             "dependency changes require review and guest provisioning alignment")

    exec_fp_published = execution_fingerprint(published_files)
    exec_fp_candidate = execution_fingerprint(candidate)
    instr_fp_published = instruction_code_fingerprint(published_files)
    instr_fp_candidate = instruction_code_fingerprint(candidate)

    merged_digest = hubcore.content_digest(candidate)
    published_digest = hubcore.content_digest(published_files)
    local_matches_published = hubcore.content_digest(local_tree) == published_digest

    exec_fp_changed = {p for p in set(exec_fp_published["includedPaths"])
                       | set(exec_fp_candidate["includedPaths"])
                       if published_files.get(p) != candidate.get(p)}
    plan["stagedSourceMatchesPublished"] = local_matches_published
    plan["executionFingerprint"] = {
        "published": exec_fp_published["digest"],
        "candidate": exec_fp_candidate["digest"],
        "equal": exec_fp_published["digest"] == exec_fp_candidate["digest"],
        "changedPaths": sorted(exec_fp_changed),
    }
    plan["instructionCodeFingerprint"] = {
        "published": instr_fp_published["digest"],
        "candidate": instr_fp_candidate["digest"],
        "equal": instr_fp_published["digest"] == instr_fp_candidate["digest"],
        "changedPaths": sorted(p for p in set(instr_fp_published["details"])
                               | set(instr_fp_candidate["details"])
                               if instr_fp_published["details"].get(p)
                               != instr_fp_candidate["details"].get(p)),
    }

    if merged_digest == published_digest:
        plan.update({"status": _status(reasons, ST_NO_CHANGE), "reasons": reasons,
                     "fileActions": actions, "gateResults": gates,
                     "candidateContentDigest": published_digest,
                     "contentChanged": False,
                     "pinAdvance": ({"from": entry["upstream"]["commit"], "to": head_commit}
                                    if head_commit else None),
                     "note": "carried content is byte-identical to the published package; only "
                             "excluded or non-carried upstream paths drifted"})
        return plan

    if gate_error is not None:
        plan.update({"status": _status(reasons, None), "reasons": reasons,
                     "fileActions": actions, "gateResults": gates, "contentChanged": True})
        return plan

    # --- mechanical updates (version bump + provenance re-pin) ---------------
    proposed_version = propose_version(published_version, used_versions(root, skill_id, entry))
    bumped_manifest, manifest_problem = bump_manifest_version(candidate["floe.json"],
                                                              proposed_version)
    if manifest_problem:
        hold("held-manifest-format", f"floe.json: {manifest_problem}",
             "the manifest must stay in its published canonical formatting")
    else:
        candidate["floe.json"] = bumped_manifest
    provenance_rel = "references/PROVENANCE.md"
    provenance_problem = None
    if provenance_rel in candidate:
        new_provenance, provenance_problem = update_provenance(
            candidate[provenance_rel], entry["upstream"]["commit"], head_commit, today,
            candidate, old_repo_tree=pinned_repo_tree, new_repo_tree=head_repo_tree,
            old_subtree_tree=pinned_subtree_tree, new_subtree_tree=head_subtree_tree)
        if provenance_problem:
            hold(HELD_PROVENANCE, f"references/PROVENANCE.md: {provenance_problem}",
                 "update the provenance manually; the mechanical re-pin requires the strict "
                 "'- Pinned commit:' line and inventory shapes")
        else:
            candidate[provenance_rel] = new_provenance
    if manifest_problem or provenance_problem:
        plan.update({"status": _status(reasons, None), "reasons": reasons,
                     "fileActions": actions, "gateResults": gates, "contentChanged": True,
                     "proposedVersion": proposed_version})
        return plan

    # Re-run the package gates on the FINAL candidate (mechanical bytes included).
    try:
        final_manifest, _ = hubcore.validate_package_files(dict(candidate), require_notice=True)
        gates.append({"gate": "final-candidate-package-gates", "passed": True})
    except hubcore.HubError as error:
        gates.append({"gate": "final-candidate-package-gates", "passed": False,
                      "detail": str(error)})
        hold(HELD_UNSAFE, f"final candidate fails the package gates: {error}",
             "fix the mechanical update inputs")
        plan.update({"status": _status(reasons, None), "reasons": reasons,
                     "fileActions": actions, "gateResults": gates, "contentChanged": True})
        return plan

    final_digest = hubcore.content_digest(candidate)
    if final_digest in _published_digests(root, skill_id):
        hold("held-digest-collision",
             f"the candidate digest equals a published digest of another {skill_id} version",
             "investigate before proposing a new immutable version")
    package_zip = hubcore.make_zip(candidate)

    changed_paths = sorted(p for p in set(published_files) | set(candidate)
                           if published_files.get(p) != candidate.get(p))
    upstream_derived = sorted(mapped_locals | {a["local"] for a in actions
                                               if a.get("action") == "add" and a.get("local")})
    mechanical = [p for p in changed_paths if p in MECHANICAL_LOCAL_PATHS]
    non_upstream_changes = [p for p in changed_paths
                            if p not in upstream_derived and p not in MECHANICAL_LOCAL_PATHS]

    manifest_runtime = final_manifest.get("scriptRuntime", "none")
    exec_equal = plan["executionFingerprint"]["equal"]
    instr_equal = plan["instructionCodeFingerprint"]["equal"]
    tier = None
    if manifest_runtime == "none":
        tier = 1
        if non_upstream_changes:
            hold(HELD_ADAPTATION,
                 f"changed paths outside the upstream-derived set: {non_upstream_changes}",
                 "tier-1 guide-only updates may only change upstream-derived files plus the "
                 "mechanical version/provenance set")
    else:
        tier = 2
        if not exec_equal:
            hold(HELD_RUNTIME,
                 "the execution fingerprint changed: "
                 + ", ".join(plan["executionFingerprint"]["changedPaths"])[:2000],
                 "genuine compatibility qualification (real guest/native proof) is required; "
                 "it is never fabricated and emulation never counts as guest-verified")
        elif not instr_equal:
            hold(HELD_INSTRUCTION_CODE,
                 "code/commands inside changed instruction markdown changed: "
                 + ", ".join(plan["instructionCodeFingerprint"]["changedPaths"])[:2000],
                 "a text extension is not safe by itself: re-qualify the changed commands or "
                 "revert them editorially")
        else:
            proof = prior_proof or {"available": False,
                                    "reasons": ["prior proof facts were not loaded"]}
            if not proof.get("available"):
                hold(HELD_PRIOR_PROOF,
                     "no verifiable prior guest proof to reuse: "
                     + "; ".join(proof.get("reasons") or []),
                     "tier-2 reuse requires the real signed prior guest-qualified review at its "
                     "ledger-verified publication pin")

    # --- showcase evidence maintenance ---------------------------------------
    evidence = maintain_showcase_evidence(links_doc, skill_id, local_tree, candidate)
    for held_record in evidence["held"]:
        hold(HELD_EDITORIAL,
             f"showcase evidence {held_record['file']} "
             f"(link {held_record['linkIndex']}, record {held_record['evidenceIndex']}): "
             f"{held_record['reason']}",
             "editorial re-anchor of showcase/links.json required before publication; hashes "
             "are never blindly rewritten")

    status = _status(reasons, f"eligible-tier{tier}")
    plan.update({
        "status": status,
        "reasons": reasons,
        "fileActions": actions,
        "gateResults": gates,
        "contentChanged": True,
        "tier": tier,
        "changedPaths": changed_paths,
        "showcaseEvidence": evidence,
    })
    if reasons:
        # Held: the current version stays published; no stageable candidate,
        # no version/review/pin proposal is attached (facts above are the
        # actionable repair record).
        return plan
    plan.update({
        "proposedVersion": proposed_version,
        "candidate": {
            "fileCount": len(candidate),
            "totalBytes": sum(len(data) for data in candidate.values()),
            "contentDigest": final_digest,
            "packageSha256": sha256_bytes(package_zip),
            "changedPaths": changed_paths,
            "mechanicalPaths": sorted(mechanical),
            "nonUpstreamChanges": non_upstream_changes,
        },
        "priorProof": (prior_proof or None) if tier == 2 else None,
        "registryDelta": {
            "versionTarget": proposed_version,
            "upstream": {"commit": head_commit, "retrievedAt": today},
        },
        "pinAdvance": {"from": entry["upstream"]["commit"], "to": head_commit},
        "proposedReview": _proposed_review(skill_id, proposed_version, final_digest,
                                           sha256_bytes(package_zip), final_manifest,
                                           tier, entry, head_commit, today, prior_proof,
                                           plan["executionFingerprint"], changed_paths),
    })
    plan["_candidateTree"] = candidate      # consumed by stage; stripped from reports
    plan["_packageZip"] = package_zip
    return plan


def _status(reasons, eligible_status):
    if reasons:
        return reasons[0]["code"]
    return eligible_status or ST_NO_CHANGE


def _published_digests(root, skill_id):
    """contentDigests of every materialized package version of one skill."""
    digests = set()
    root = pathlib.Path(root)
    for prefix in ("", "android/"):
        folder = root / prefix / "packages" / skill_id
        if not folder.is_dir():
            continue
        for version_dir in folder.iterdir():
            archive = version_dir / f"{skill_id}.zip"
            if archive.is_file():
                try:
                    files = hubcore.check_archive_bytes(archive.read_bytes())
                    digests.add(hubcore.content_digest(files))
                except hubcore.HubError:
                    continue
    return digests


def _proposed_review(skill_id, version, content_digest, package_sha256, manifest, tier,
                     entry, head_commit, today, prior_proof, exec_fp, changed_paths):
    """Honest review-record skeleton for the Root-owned signing pipeline.

    Tier 1: a fresh static-content review of the new bytes by the machine
    identity; execution stays {null, n/a, unproven} (nothing executed).
    Tier 2: prior-proof reuse; the record never claims a NEW execution and the
    bilingual notes cite the complete prior binding (DECISION B3).
    """
    capabilities = list(manifest.get("capabilities", []))
    tools = list(manifest.get("tools", []))
    packages = manifest.get("pythonPackages", [])
    pin = entry["upstream"]["commit"]
    if tier == 1:
        notes = {
            "en": (f"Automatic upstream update from {pin[:10]} to {head_commit[:10]}. "
                   f"Guide-only package: deterministic gates passed (package gates, license "
                   f"preservation, no grant/dependency drift); changed paths: "
                   f"{', '.join(changed_paths) or 'none'}. No execution claim."),
            "zh-Hans": (f"自动上游更新：{pin[:10]} → {head_commit[:10]}。纯指导包：确定性门槛全部通过"
                        f"（包门槛、许可证保留、无权限/依赖漂移）；变更路径：{', '.join(changed_paths) or '无'}。"
                        "不包含任何执行声明。"),
        }
        execution = {"os": None, "arch": "n/a", "evidence": "unproven"}
        stage = "static-content-reviewed"
    else:
        proof = prior_proof or {}
        notes = {
            "en": (f"Automatic upstream update from {pin[:10]} to {head_commit[:10]} with an "
                   f"unchanged execution fingerprint ({exec_fp['candidate'][:16]}…). Runtime "
                   f"proof reuse: prior {skill_id} {proof.get('priorVersion')} "
                   f"(contentDigest {str(proof.get('priorContentDigest'))[:16]}…, review sha256 "
                   f"{str(proof.get('reviewSha256'))[:16]}…, publication pin "
                   f"{str(proof.get('publicationPin'))[:10]}) was guest-qualified "
                   f"({proof.get('keyID')}); this record claims NO new execution. Changed "
                   f"paths: {', '.join(changed_paths) or 'none'}."),
            "zh-Hans": (f"自动上游更新：{pin[:10]} → {head_commit[:10]}，执行指纹未变"
                        f"（{exec_fp['candidate'][:16]}…）。运行时证明复用：先前 {skill_id} "
                        f"{proof.get('priorVersion')}（contentDigest "
                        f"{str(proof.get('priorContentDigest'))[:16]}…、评审 sha256 "
                        f"{str(proof.get('reviewSha256'))[:16]}…、发布固定提交 "
                        f"{str(proof.get('publicationPin'))[:10]}）已通过真实客户机验证"
                        f"（{proof.get('keyID')}）；本记录不声明任何新的执行。变更路径："
                        f"{', '.join(changed_paths) or '无'}。"),
        }
        execution = {"os": "linux", "arch": "riscv64", "evidence": "guest-verified"}
        stage = "guest-execution-qualified"
    return {
        "schemaVersion": hubcore.REVIEW_SCHEMA_VERSION,
        "id": skill_id,
        "version": version,
        "contentDigest": content_digest,
        "packageSha256": package_sha256,
        "reviewedCapabilities": sorted(capabilities),
        "reviewedTools": sorted(tools),
        "reviewedPythonPackages": packages,
        "execution": execution,
        "reviewStage": stage,
        "reviewedAt": today,
        "reviewer": MACHINE_REVIEWER,
        "decision": "approve",
        "notes": notes,
    }


# --------------------------------------------------------------------------
# command: check (read-only grouped upstream scan)
# --------------------------------------------------------------------------

def _repo_short(url):
    return url.removeprefix("https://github.com/")


def _engine_semver(tag):
    match = ENGINE_TAG_PATTERN.match(tag)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _tracked_by_repository(policy, entries):
    grouped = {}
    for skill_id in policy["selection"]["tracked"]:
        entry = entries[skill_id]
        grouped.setdefault(entry["upstream"]["repository"], []).append(skill_id)
    return grouped


def _engine_facts(source, policy, entries, pins, root, report_errors):
    facts = []
    root = pathlib.Path(root)
    for name in sorted(policy.get("engineTracking") or {}):
        cfg = policy["engineTracking"][name]
        skill_id = cfg["skillId"]
        url = cfg["repository"]
        entry = entries.get(skill_id) or {}
        upstream = entry.get("upstream") or {}
        pin = upstream.get("commit") or pins.get(_repo_short(url))
        fact = {"name": name, "skillId": skill_id, "repository": url,
                "corpusPath": cfg["corpusPath"], "pinnedCommit": pin,
                "mode": "engine-managed", "candidateConstructed": False,
                "route": cfg["route"], "error": None}
        try:
            head, _ref = source.resolve_ref(url, "HEAD")
            fact["headCommit"] = head
            pinned_tree = source.commit_tree_oid(url, pin, cfg["corpusPath"])
            head_tree = source.commit_tree_oid(url, head, cfg["corpusPath"])
            fact["corpusTreePinned"] = pinned_tree
            fact["corpusTreeHead"] = head_tree
            fact["corpusDrift"] = pinned_tree != head_tree
            tags = source.list_tags(url, "engine-v")
            stable = [(ver, tag, sha) for tag, sha in tags
                      if (ver := _engine_semver(tag)) is not None]
            lock_path = root / cfg["engineLock"]
            lock_version = None
            if lock_path.is_file():
                lock = json.loads(lock_path.read_bytes())
                lock_version = (lock.get("upstream") or {}).get("engineVersion")
            fact["engineLockVersion"] = lock_version
            if stable:
                stable.sort()
                ver, tag, sha = stable[-1]
                fact["latestStableEngineTag"] = tag
                fact["latestStableEngineCommit"] = sha
                fact["latestStableEngineSemver"] = list(ver)
                if lock_version:
                    try:
                        lock_semver = tuple(int(p) for p in lock_version.split("."))
                        fact["newerStableEngineRelease"] = ver > lock_semver
                    except ValueError:
                        fact["newerStableEngineRelease"] = None
            else:
                fact["latestStableEngineTag"] = None
                fact["newerStableEngineRelease"] = False
        except UpstreamError as error:
            fact["error"] = str(error)
            report_errors.append({"scope": f"engine {name}", "error": str(error)})
        facts.append(fact)
    return facts


def _watch_only_facts(source, policy, pins, report_errors):
    facts = []
    for watch in sorted(policy["selection"].get("watchOnly") or [], key=lambda w: w["id"]):
        url = watch["originalRepository"]
        subpath = watch["originalPath"]
        pin = pins.get(_repo_short(url))
        fact = {"id": watch["id"], "originalRepository": url, "originalPath": subpath,
                "originalPinnedCommit": pin, "copyProhibited": True,
                "reason": watch["reason"], "error": None}
        try:
            head, _ref = source.resolve_ref(url, "HEAD")
            fact["headCommit"] = head

            def license_signal(commit):
                subtree = source.list_tree(url, commit, subpath)
                subtree_licenses = sorted(
                    {"path": rel, "blob": blob}
                    for _mode, _type, blob, _size, rel in subtree
                    if LICENSE_NAME_PATTERN.search(rel.rsplit("/", 1)[-1]))
                root_rows = source.list_tree(url, commit, ".")
                root_licenses = sorted(
                    {"path": rel, "blob": blob}
                    for _mode, _type, blob, _size, rel in root_rows
                    if "/" not in rel and LICENSE_NAME_PATTERN.search(rel))
                return {"subtreePresent": bool(subtree),
                        "subtreeLicenseFiles": subtree_licenses,
                        "rootLicenseFiles": root_licenses}

            at_pin = license_signal(pin)
            at_head = license_signal(head)
            fact["atPin"] = at_pin
            fact["atHead"] = at_head
            pin_names = {item["path"] for item in at_pin["subtreeLicenseFiles"]} | \
                        {item["path"] for item in at_pin["rootLicenseFiles"]}
            head_names = {item["path"] for item in at_head["subtreeLicenseFiles"]} | \
                         {item["path"] for item in at_head["rootLicenseFiles"]}
            fact["licenseSignal"] = {
                "licenseAppeared": bool(head_names - pin_names),
                "licenseRemoved": bool(pin_names - head_names),
                "changed": (at_pin["subtreeLicenseFiles"] + at_pin["rootLicenseFiles"])
                           != (at_head["subtreeLicenseFiles"] + at_head["rootLicenseFiles"]),
                "newLicensePaths": sorted(head_names - pin_names),
            }
        except UpstreamError as error:
            fact["error"] = str(error)
            report_errors.append({"scope": f"watch-only {watch['id']}", "error": str(error)})
        facts.append(fact)
    return facts


def run_check(root, inputs, source, today, only=None):
    policy = inputs["policy"]
    entries = inputs["entries"]
    pins = inputs["pins"]
    errors = []
    license_cache = {}

    def root_license_changed(url, paths, pin, head):
        if not pin or pin == head:
            return False
        for path in paths:
            key = (url, path, pin, head)
            if key not in license_cache:
                old_bytes = source.read_file(url, pin, path)
                new_bytes = source.read_file(url, head, path)
                license_cache[key] = old_bytes != new_bytes
            if license_cache[key]:
                return True
        return False

    report = {
        "reportKind": REPORT_KIND_CHECK,
        "reportVersion": REPORT_VERSION,
        "today": today,
        "inputs": _input_digests(root, policy),
        "repositories": [],
        "skills": [],
        "engineTracking": [],
        "watchOnly": [],
        "errors": errors,
    }
    only_ids = set(only) if only else None
    tracked_by_repo = _tracked_by_repository(policy, entries)
    engine_repos = {cfg["repository"] for cfg in (policy.get("engineTracking") or {}).values()}

    for url in sorted(policy["repositories"]):
        cfg = policy["repositories"][url]
        short = _repo_short(url)
        pin = pins.get(short)
        repo_report = {"url": url, "role": cfg["role"], "trackedRef": cfg["trackedRef"],
                       "pinnedCommit": pin, "error": None}
        relevant_ids = sorted(tracked_by_repo.get(url, []))
        if only_ids is not None:
            relevant_ids = [i for i in relevant_ids if i in only_ids]
        watch_here = [w for w in (policy["selection"].get("watchOnly") or [])
                      if w["originalRepository"] == url
                      and (only_ids is None or w["id"] in only_ids)]
        engine_here = [c for c in (policy.get("engineTracking") or {}).values()
                       if c["repository"] == url
                       and (only_ids is None or c["skillId"] in only_ids)]
        if not relevant_ids and not watch_here and not engine_here and cfg["role"] != "watch-only":
            continue
        head = None
        try:
            head, refname = source.resolve_ref(url, cfg["trackedRef"])
            repo_report["headCommit"] = head
            repo_report["resolvedRef"] = refname
            repo_report["headMoved"] = head != pin
            root_license = cfg.get("rootLicense")
            if root_license:
                if head != pin:
                    old_bytes = source.read_file(url, pin, root_license)
                    new_bytes = source.read_file(url, head, root_license)
                    repo_report["rootLicense"] = {
                        "path": root_license,
                        "pinnedSha256": sha256_bytes(old_bytes) if old_bytes is not None else None,
                        "headSha256": sha256_bytes(new_bytes) if new_bytes is not None else None,
                        "changed": (old_bytes or b"\x00absent") != (new_bytes or b"\x00absent"),
                    }
                else:
                    repo_report["rootLicense"] = {"path": root_license, "changed": False,
                                                  "note": "head equals the pin"}
        except UpstreamError as error:
            repo_report["error"] = str(error)
            errors.append({"scope": f"repository {url}", "error": str(error)})
        report["repositories"].append(repo_report)

        for skill_id in relevant_ids:
            entry = entries[skill_id]
            sub = entry["upstream"]["path"]
            entry_pin = entry["upstream"]["commit"]  # validated == effective pin
            license_changed = False
            license_error = None
            if head and not repo_report.get("error"):
                try:
                    license_changed = root_license_changed(url, license_evidence_paths(cfg),
                                                           entry_pin, head)
                except UpstreamError as error:
                    license_error = str(error)
                    errors.append({"scope": f"root license {url}", "error": str(error)})
            skill_report = {"id": skill_id, "mode": "tracked", "repository": url,
                            "upstreamPath": sub, "pinnedCommit": entry_pin,
                            "repositoryDefaultPin": pin, "headCommit": head,
                            "rootLicenseChanged": license_changed}
            if repo_report.get("error") or head is None or license_error:
                skill_report["state"] = ST_ERROR
                skill_report["detail"] = license_error or "the repository head could not be resolved"
            elif license_changed:
                skill_report["state"] = ST_DRIFTED
                skill_report["detail"] = "declared license/notice evidence changed; re-audit required"
            elif head == entry_pin:
                skill_report["state"] = ST_UP_TO_DATE
                skill_report["detail"] = "the repository head equals the entry pin"
            else:
                try:
                    old_tree = source.commit_tree_oid(url, entry_pin, sub)
                    new_tree = source.commit_tree_oid(url, head, sub)
                    skill_report["pinnedSubtreeOid"] = old_tree
                    skill_report["headSubtreeOid"] = new_tree
                    if old_tree is None:
                        skill_report["state"] = ST_ERROR
                        skill_report["detail"] = "the pinned subtree no longer resolves"
                    elif new_tree is None:
                        skill_report["state"] = ST_DRIFTED
                        skill_report["subtreeRemoved"] = True
                        skill_report["detail"] = ("the tracked subpath disappeared at the "
                                                  "resolved head")
                    elif old_tree == new_tree:
                        skill_report["state"] = ST_UP_TO_DATE
                        skill_report["detail"] = ("the repository head moved but the relevant "
                                                  "source subpath tree is unchanged; the pin "
                                                  "never bumps on unrelated commits")
                    else:
                        skill_report["state"] = ST_DRIFTED
                        skill_report["detail"] = "the relevant source subpath tree changed"
                except UpstreamError as error:
                    skill_report["state"] = ST_ERROR
                    skill_report["detail"] = str(error)
                    errors.append({"scope": f"skill {skill_id}", "error": str(error)})
            report["skills"].append(skill_report)

    report["engineTracking"] = [f for f in _engine_facts(source, policy, entries, pins,
                                                         inputs["root"], errors)
                                if only_ids is None or f["skillId"] in only_ids]
    report["watchOnly"] = _watch_only_facts(source, policy, pins, errors)
    if only_ids is not None:
        report["watchOnly"] = [f for f in report["watchOnly"] if f["id"] in only_ids]

    # Coverage: every registry id appears exactly once with its mode.
    engine_ids = {f["skillId"] for f in report["engineTracking"]}
    watch_ids = {f["id"] for f in report["watchOnly"]}
    tracked_ids = {s["id"] for s in report["skills"] if s["mode"] == "tracked"}
    not_tracked = policy["selection"]["notTracked"]
    for skill_id in sorted(not_tracked["builtins"]):
        if only_ids is None or skill_id in only_ids:
            report["skills"].append({"id": skill_id, "mode": "excluded-builtin",
                                     "state": "not-tracked"})
    for skill_id in sorted(not_tracked["firstParty"]):
        if only_ids is None or skill_id in only_ids:
            report["skills"].append({"id": skill_id, "mode": "excluded-first-party",
                                     "state": "not-tracked"})
    for skill_id in sorted(watch_ids):
        report["skills"].append({"id": skill_id, "mode": "watch-only",
                                 "state": "watch-only-signal"})
    for fact in report["engineTracking"]:
        drifted = bool(fact.get("corpusDrift")) or bool(fact.get("newerStableEngineRelease"))
        report["skills"].append({
            "id": fact["skillId"], "mode": "engine-managed",
            "state": ST_DRIFTED if drifted else ST_UP_TO_DATE,
            "detail": ("engine-managed: corpus drift and stable engine release signals are "
                       "reported; candidates are constructed only by the engines pipeline")})
    report["skills"].sort(key=lambda s: s["id"])
    seen_ids = [s["id"] for s in report["skills"]]
    report["counts"] = {
        "registryEntries": len(entries),
        "reportedEntries": len(seen_ids),
        "tracked": len(tracked_ids),
        "engineManaged": len(engine_ids),
        "watchOnly": len(watch_ids),
        "excluded": len(not_tracked["builtins"]) + len(not_tracked["firstParty"]),
        "drifted": sum(1 for s in report["skills"] if s.get("state") == ST_DRIFTED),
        "upToDate": sum(1 for s in report["skills"] if s.get("state") == ST_UP_TO_DATE),
        "error": sum(1 for s in report["skills"] if s.get("state") == ST_ERROR),
    }
    if only_ids is None and len(set(seen_ids)) != len(entries):
        raise UpstreamError("coverage invariant failed: the check report must account for "
                            "every registry entry exactly once")
    return report


def _input_digests(root, policy):
    root = pathlib.Path(root)
    return {
        "policySha256": sha256_bytes(hubcore.encoded(policy)),
        "registrySha256": sha256_bytes((root / REGISTRY_REL).read_bytes()),
        "pinsSha256": sha256_bytes((root / PINS_REL).read_bytes()),
    }


# --------------------------------------------------------------------------
# entry-pins contract consumption (job-a000dc2309224d6b owns the authority)
# --------------------------------------------------------------------------

def load_pins_helper():
    """Prefer the real scripts/upstream_pins.py helper once that lane lands."""
    try:
        import upstream_pins
    except ImportError:
        return None, "scripts/upstream_pins.py not present; using the internal mirror of the settled entry-pins semantics"
    fn = getattr(upstream_pins, "advance_pin_document", None)
    if not callable(fn):
        return None, "scripts/upstream_pins.py has no advance_pin_document; using the internal mirror"
    return fn, "scripts/upstream_pins.py advance_pin_document"


def fallback_advance_pin_document(prior_doc, old_registry, new_registry, accepted_ids, today):
    """Internal mirror of the settled entry-pins advancement semantics.

    Replaced automatically by scripts/upstream_pins.py when present. Rules
    (entry-pins-spec, job-a000dc2309224d6b): exact same registry id set and
    repository identity; only accepted ids may advance their upstream pin;
    held/unaccepted ids keep their exact old commit; per repository, all
    external rows agreeing on one commit compact the repository default and
    drop redundant overrides, mixed commits retain the previous repository
    default and write skillOverrides only for rows differing from it;
    watch-only repository baselines and non-upstream rows are preserved.
    """
    if not isinstance(prior_doc, dict) \
            or set(prior_doc) - {"reviewBaselineDate", "repositories", "skillOverrides"}:
        raise UpstreamError("pins document root keys must be reviewBaselineDate/"
                            "repositories[/skillOverrides]")
    repos = dict(prior_doc.get("repositories") or {})
    old_by_id = {e["id"]: e for e in old_registry["skills"]}
    new_by_id = {e["id"]: e for e in new_registry["skills"]}
    if set(old_by_id) != set(new_by_id):
        raise UpstreamError("pin advancement requires the exact same registry id set")
    accepted = set(accepted_ids)
    effective = {}
    for skill_id in sorted(new_by_id):
        entry = new_by_id[skill_id]
        old_entry = old_by_id[skill_id]
        upstream = entry.get("upstream")
        old_upstream = old_entry.get("upstream")
        if upstream is None and old_upstream is None:
            continue
        if upstream is None or old_upstream is None:
            raise UpstreamError(f"{skill_id}: upstream presence may not change during advancement")
        if upstream["repository"] != old_upstream["repository"]:
            raise UpstreamError(f"{skill_id}: repository identity can never change")
        if upstream["commit"] != old_upstream["commit"] and skill_id not in accepted:
            raise UpstreamError(f"{skill_id}: only accepted ids may advance their upstream pin")
        effective[skill_id] = (upstream["repository"], upstream["commit"])

    overrides = {}
    by_repo = {}
    for skill_id, (url, commit) in effective.items():
        by_repo.setdefault(url, {})[skill_id] = commit
    changed = False
    for url in sorted(by_repo):
        short = _repo_short(url)
        rows = by_repo[url]
        commits = set(rows.values())
        if len(commits) == 1:
            compacted = next(iter(commits))
            if repos.get(short) != compacted:
                changed = True
            repos[short] = compacted
        else:
            default = repos.get(short)
            if default is None:
                raise UpstreamError(f"{url}: mixed entry pins require an existing repository "
                                    "default")
            for skill_id in sorted(rows):
                if rows[skill_id] != default:
                    overrides[skill_id] = {"repository": short, "commit": rows[skill_id]}
    doc = {"reviewBaselineDate": today if changed else prior_doc.get("reviewBaselineDate"),
           "repositories": repos}
    if overrides:
        doc["skillOverrides"] = overrides
    return doc


def advance_pins(prior_bytes, old_registry, new_registry, accepted_ids, today):
    """(new pins bytes, helper label).

    Prefers the entry-pins lane authority (scripts/upstream_pins.py
    advance_pin_document + deterministic_bytes). A semantically unchanged
    document keeps the prior bytes EXACTLY (the live baseline retains its
    historical key order until a real advance replaces it, per the entry-pins
    contract); a real advance serializes with the canonical deterministic
    bytes (sorted keys, indent 2, trailing newline). An empty accepted set is
    never an advance: the prior bytes stay untouched (the review baseline date
    must not move without a real accepted update).
    """
    if not accepted_ids:
        return prior_bytes, "no accepted pin advances; prior pins document preserved"
    helper, label = load_pins_helper()
    try:
        if helper is not None:
            import upstream_pins
            prior_doc = upstream_pins.parse_pins_bytes(prior_bytes)
            new_doc = helper(prior_doc, old_registry, new_registry,
                             sorted(accepted_ids), today)
            if isinstance(new_doc, (bytes, bytearray)):
                return bytes(new_doc), label
        else:
            prior_doc = json.loads(prior_bytes)
            new_doc = fallback_advance_pin_document(prior_doc, old_registry, new_registry,
                                                    sorted(accepted_ids), today)
    except UpstreamError:
        raise
    except Exception as error:  # includes UpstreamPinError: fail closed with its message
        raise UpstreamError(f"pin advancement refused: {error}") from None
    if hubcore.encoded(new_doc) == hubcore.encoded(json.loads(prior_bytes)):
        return prior_bytes, label + " (unchanged; prior bytes preserved)"
    if helper is not None:
        import upstream_pins
        return upstream_pins.deterministic_bytes(new_doc), label
    return hubcore.pretty(new_doc), label


# --------------------------------------------------------------------------
# command: plan
# --------------------------------------------------------------------------

def _resolve_heads(source, policy, check_report, errors):
    """{url: {"head": sha, "ref": name, "error": str|None}} grouped per repo."""
    heads = {}
    check_repos = {r["url"]: r for r in (check_report or {}).get("repositories", [])}
    for url in sorted(policy["repositories"]):
        cfg = policy["repositories"][url]
        fact = check_repos.get(url)
        if fact and fact.get("headCommit") and not fact.get("error"):
            heads[url] = {"head": fact["headCommit"], "ref": fact.get("resolvedRef"),
                          "error": None}
            continue
        try:
            head, ref = source.resolve_ref(url, cfg["trackedRef"])
            heads[url] = {"head": head, "ref": ref, "error": None}
        except UpstreamError as error:
            heads[url] = {"head": None, "ref": None, "error": str(error)}
            errors.append({"scope": f"repository {url}", "error": str(error)})
    return heads


def run_plan(root, inputs, source, today, only=None, check_report=None):
    policy = inputs["policy"]
    entries = inputs["entries"]
    pins = inputs["pins"]
    root = pathlib.Path(root)
    if check_report is not None:
        if check_report.get("reportKind") != REPORT_KIND_CHECK \
                or check_report.get("reportVersion") != REPORT_VERSION:
            raise UpstreamError("--check-report must be a floe-skill-hub-upstream-check v1 report")
        if check_report.get("inputs") != _input_digests(root, policy):
            raise UpstreamError("the check report was produced against different policy/"
                                "registry/pins bytes; re-run check on this tree state")
    links_doc = None
    links_path = root / LINKS_REL
    if links_path.is_file():
        links_doc = json.loads(links_path.read_bytes())

    errors = []
    report = {"reportKind": REPORT_KIND_PLAN, "reportVersion": REPORT_VERSION, "today": today,
              "inputs": _input_digests(root, policy),
              "basedOnCheckReport": check_report is not None,
              "skills": [], "engineTracking": [], "watchOnly": [],
              "acceptance": {"model": "per-entry"}, "errors": errors}
    only_ids = set(only) if only else None
    heads = _resolve_heads(source, policy, check_report, errors)
    tracked_by_repo = _tracked_by_repository(policy, entries)
    license_cache = {}

    def root_license_changed(url, paths, pin, head):
        if not pin or pin == head:
            return False
        for path in paths:
            key = (url, path, pin, head)
            if key not in license_cache:
                old_bytes = source.read_file(url, pin, path)
                new_bytes = source.read_file(url, head, path)
                license_cache[key] = old_bytes != new_bytes
            if license_cache[key]:
                return True
        return False

    for url in sorted(tracked_by_repo):
        head_fact = heads.get(url) or {"head": None, "error": "repository not scanned"}
        head = head_fact.get("head")
        default_pin = pins.get(_repo_short(url))
        for skill_id in sorted(tracked_by_repo[url]):
            if only_ids is not None and skill_id not in only_ids:
                continue
            entry = entries[skill_id]
            subpath = entry["upstream"]["path"]
            pin = entry["upstream"]["commit"]  # validated == effective pin (override-aware)
            license_changed = False
            license_error = None
            if head and not head_fact.get("error"):
                try:
                    license_changed = root_license_changed(
                        url, license_evidence_paths(policy["repositories"].get(url) or {}),
                        pin, head)
                except UpstreamError as error:
                    license_error = str(error)
                    errors.append({"scope": f"root license {url}", "error": str(error)})
            row = {"id": skill_id, "mode": "tracked", "repository": url,
                   "upstreamPath": subpath, "pinnedCommit": pin,
                   "repositoryDefaultPin": default_pin, "headCommit": head,
                   "rootLicenseChanged": license_changed}
            if head_fact.get("error") or head is None or license_error:
                row.update({"status": ST_ERROR,
                            "reasons": [{"code": ST_ERROR,
                                         "detail": license_error or head_fact.get("error"),
                                         "repair": "restore upstream connectivity or the "
                                                   "repository pin"}]})
                report["skills"].append(row)
                continue
            if license_changed:
                row.update({"status": HELD_LICENSE, "contentChanged": False, "pinAdvance": None,
                            "reasons": [{"code": HELD_LICENSE,
                                         "detail": "declared license/notice evidence changed",
                                         "repair": "re-audit licensing before adopting upstream content"}]})
                report["skills"].append(row)
                continue
            if head == pin:
                row.update({"status": ST_UP_TO_DATE, "contentChanged": False,
                            "pinAdvance": None, "reasons": []})
                report["skills"].append(row)
                continue
            try:
                pinned_tree = source.commit_tree_oid(url, pin, subpath)
                head_tree = source.commit_tree_oid(url, head, subpath)
            except UpstreamError as error:
                row.update({"status": ST_ERROR,
                            "reasons": [{"code": ST_ERROR, "detail": str(error),
                                         "repair": "re-run once upstream reads recover"}]})
                report["skills"].append(row)
                continue
            row["pinnedSubtreeOid"] = pinned_tree
            row["headSubtreeOid"] = head_tree
            if head_tree is None:
                row.update({"status": HELD_ADAPTATION, "contentChanged": False, "pinAdvance": None,
                            "reasons": [{"code": HELD_ADAPTATION,
                                         "detail": "the tracked subpath disappeared at the "
                                                   "resolved head",
                                         "repair": "curation decision: relocate or retire the "
                                                   "entry"}]})
                report["skills"].append(row)
                continue
            if pinned_tree == head_tree:
                row.update({"status": ST_NO_CHANGE, "contentChanged": False,
                            "pinAdvance": {"from": pin, "to": head},
                            "pinAdvanceAlongsideAcceptedRepoUpdate": True,
                            "reasons": [],
                            "detail": "the relevant source subpath tree is unchanged; the head "
                                      "move is unrelated commits only"})
                report["skills"].append(row)
                continue
            # Genuine relevant drift: full candidate construction.
            try:
                old_snapshot, _ = snapshot_upstream_tree(source, url, pin, subpath)
                new_snapshot, _ = snapshot_upstream_tree(source, url, head, subpath)
                local_tree = snapshot_local_tree(root, skill_id)
            except (UpstreamError, hubcore.HubError) as error:
                row.update({"status": ST_ERROR,
                            "reasons": [{"code": ST_ERROR, "detail": str(error),
                                         "repair": "fix the fetch/staging problem and re-run"}]})
                report["skills"].append(row)
                continue
            published_version = entry.get("versionTarget")
            published_files = published_package_files(root, skill_id, published_version) \
                if published_version else None
            prior_proof = None
            if published_files is not None \
                    and entry["plannedRuntime"]["scriptRuntime"] != "none":
                zip_rel = hubcore.package_path_for(skill_id, published_version, "ios")
                zip_path = root / zip_rel
                prior_proof = load_prior_proof(
                    root, skill_id, published_version,
                    hubcore.content_digest(published_files),
                    sha256_bytes(zip_path.read_bytes()) if zip_path.is_file() else None)
            try:
                pinned_repo_tree = source.commit_root_tree_oid(url, pin)
                head_repo_tree = source.commit_root_tree_oid(url, head)
            except UpstreamError:
                pinned_repo_tree = head_repo_tree = None
            planned = plan_skill(skill_id, entry, policy["skills"][skill_id],
                                 old_snapshot, new_snapshot, local_tree,
                                 published_files, published_version, root, today, links_doc,
                                 root_license_changed=license_changed,
                                 prior_proof=prior_proof, repo_url=url, head_commit=head,
                                 pinned_repo_tree=pinned_repo_tree, head_repo_tree=head_repo_tree,
                                 pinned_subtree_tree=pinned_tree, head_subtree_tree=head_tree)
            planned.pop("_candidateTree", None)
            planned.pop("_packageZip", None)
            report["skills"].append(planned)

    report["engineTracking"] = _engine_facts(source, policy, entries, pins, root, errors)
    for fact in report["engineTracking"]:
        if only_ids is not None and fact["skillId"] not in only_ids:
            continue
        drifted = bool(fact.get("corpusDrift")) or bool(fact.get("newerStableEngineRelease"))
        report["skills"].append({
            "id": fact["skillId"], "mode": "engine-managed",
            "status": HELD_ENGINE if drifted else ST_UP_TO_DATE,
            "contentChanged": False, "pinAdvance": None,
            "corpusDrift": fact.get("corpusDrift"),
            "latestStableEngineTag": fact.get("latestStableEngineTag"),
            "engineLockVersion": fact.get("engineLockVersion"),
            "newerStableEngineRelease": fact.get("newerStableEngineRelease"),
            "reasons": ([{"code": HELD_ENGINE,
                          "detail": "engine-managed skill: corpus drift "
                                    f"{fact.get('corpusDrift')}, newer stable engine release "
                                    f"{fact.get('newerStableEngineRelease')}",
                          "repair": fact.get("route")}] if drifted else []),
        })
    report["watchOnly"] = _watch_only_facts(source, policy, pins, errors)
    if only_ids is not None:
        report["engineTracking"] = [f for f in report["engineTracking"]
                                    if f["skillId"] in only_ids]
        report["watchOnly"] = [f for f in report["watchOnly"] if f["id"] in only_ids]
        for watch in report["watchOnly"]:
            report["skills"].append({"id": watch["id"], "mode": "watch-only",
                                     "status": "watch-only-signal", "contentChanged": False,
                                     "pinAdvance": None, "reasons": [],
                                     "licenseSignal": watch.get("licenseSignal")})
    else:
        for watch in report["watchOnly"]:
            report["skills"].append({"id": watch["id"], "mode": "watch-only",
                                     "status": "watch-only-signal", "contentChanged": False,
                                     "pinAdvance": None, "reasons": [],
                                     "licenseSignal": watch.get("licenseSignal")})
        not_tracked = policy["selection"]["notTracked"]
        for skill_id in sorted(not_tracked["builtins"]):
            report["skills"].append({"id": skill_id, "mode": "excluded-builtin",
                                     "status": "not-tracked", "contentChanged": False,
                                     "pinAdvance": None, "reasons": []})
        for skill_id in sorted(not_tracked["firstParty"]):
            report["skills"].append({"id": skill_id, "mode": "excluded-first-party",
                                     "status": "not-tracked", "contentChanged": False,
                                     "pinAdvance": None, "reasons": []})
    report["skills"].sort(key=lambda s: s["id"])

    # --- per-entry acceptance summary ----------------------------------------
    eligible = [s["id"] for s in report["skills"]
                if s.get("status") in (ST_ELIGIBLE_T1, ST_ELIGIBLE_T2)]
    repos_with_updates = {s["repository"] for s in report["skills"] if s["id"] in eligible}
    accepted_ids = set(eligible)
    pin_advances = {}
    for skill in report["skills"]:
        if skill["id"] in eligible:
            if skill.get("pinAdvance"):
                pin_advances[skill["id"]] = skill["pinAdvance"]
        elif skill.get("status") == ST_NO_CHANGE and skill.get("repository") in repos_with_updates:
            accepted_ids.add(skill["id"])
            if skill.get("pinAdvance"):
                pin_advances[skill["id"]] = skill["pinAdvance"]
    report["acceptance"].update({
        "eligibleIds": sorted(eligible),
        "acceptedIds": sorted(accepted_ids),
        "pinAdvances": {k: pin_advances[k] for k in sorted(pin_advances)},
        "heldIds": sorted(s["id"] for s in report["skills"]
                          if str(s.get("status", "")).startswith(ST_HELD_PREFIX)),
        "note": ("pin advances apply per entry; no-change entries re-pin only alongside an "
                 "accepted content update of their repository (no pin churn on scans without "
                 "content updates); held entries always keep their exact old pin and version"),
    })
    report["counts"] = {
        "reportedEntries": len(report["skills"]),
        "eligible": len(eligible),
        "noChange": sum(1 for s in report["skills"] if s.get("status") == ST_NO_CHANGE),
        "upToDate": sum(1 for s in report["skills"] if s.get("status") == ST_UP_TO_DATE),
        "held": len(report["acceptance"]["heldIds"]),
        "error": sum(1 for s in report["skills"] if s.get("status") == ST_ERROR),
        "watchOnly": len(report["watchOnly"]),
    }
    return report


# --------------------------------------------------------------------------
# command: stage (materialize candidates; never touches the live publication)
# --------------------------------------------------------------------------

def run_stage(root, inputs, source, plan_report, stage_root):
    policy = inputs["policy"]
    entries = inputs["entries"]
    registry_doc = inputs["registry"]
    root = pathlib.Path(root)
    if plan_report.get("reportKind") != REPORT_KIND_PLAN \
            or plan_report.get("reportVersion") != REPORT_VERSION:
        raise UpstreamError("--plan must be a floe-skill-hub-upstream-plan v1 report")
    if plan_report.get("inputs") != _input_digests(root, policy):
        raise UpstreamError("the plan was produced against different policy/registry/pins "
                            "bytes; re-run plan on this tree state (fail closed)")
    today = plan_report["today"]
    stage_root = pathlib.Path(stage_root)
    if stage_root.resolve() == root.resolve() or root.resolve() in stage_root.resolve().parents:
        raise UpstreamError("the stage root must live outside the Hub checkout")
    if stage_root.exists() and any(stage_root.iterdir()):
        raise UpstreamError(f"stage root is not empty: {stage_root} (single deterministic run)")
    (stage_root / "candidates").mkdir(parents=True)
    (stage_root / "held").mkdir(parents=True)
    (stage_root / "apply" / "files").mkdir(parents=True)

    links_path = root / LINKS_REL
    links_bytes = links_path.read_bytes() if links_path.is_file() else None
    registry_bytes = (root / REGISTRY_REL).read_bytes()
    pins_bytes = (root / PINS_REL).read_bytes()

    skills = plan_report["skills"]
    eligible_rows = [s for s in skills if s.get("status") in (ST_ELIGIBLE_T1, ST_ELIGIBLE_T2)]
    held_rows = [s for s in skills if str(s.get("status", "")).startswith(ST_HELD_PREFIX)]
    accepted_ids = set(plan_report.get("acceptance", {}).get("acceptedIds") or [])
    eligible_ids = {s["id"] for s in eligible_rows}
    unknown_accepted = accepted_ids - {s["id"] for s in skills}
    if unknown_accepted:
        raise UpstreamError(f"plan acceptance references unknown ids: {sorted(unknown_accepted)}")

    import copy
    new_registry = copy.deepcopy(registry_doc)
    new_registry_by_id = {e["id"]: e for e in new_registry["skills"]}
    writes = {}
    deletions = []
    candidates_summary = []
    bumped_versions = {}
    review_stage_counts = {"static-content-reviewed": 0, "prior-proof-reuse": 0}

    for row in eligible_rows:
        skill_id = row["id"]
        entry = entries[skill_id]
        url = row["repository"]
        pin = row["pinnedCommit"]
        head = row["headCommit"]
        old_snapshot, _ = snapshot_upstream_tree(source, url, pin, row["upstreamPath"])
        new_snapshot, _ = snapshot_upstream_tree(source, url, head, row["upstreamPath"])
        local_tree = snapshot_local_tree(root, skill_id)
        published_version = entry.get("versionTarget")
        published_files = published_package_files(root, skill_id, published_version)
        prior_proof = None
        if published_files is not None and entry["plannedRuntime"]["scriptRuntime"] != "none":
            zip_path = root / hubcore.package_path_for(skill_id, published_version, "ios")
            prior_proof = load_prior_proof(
                root, skill_id, published_version,
                hubcore.content_digest(published_files),
                sha256_bytes(zip_path.read_bytes()) if zip_path.is_file() else None)
        try:
            pinned_repo_tree = source.commit_root_tree_oid(url, pin)
            head_repo_tree = source.commit_root_tree_oid(url, head)
        except UpstreamError:
            pinned_repo_tree = head_repo_tree = None
        links_doc = json.loads(links_bytes) if links_bytes is not None else None
        replayed = plan_skill(skill_id, entry, policy["skills"][skill_id],
                              old_snapshot, new_snapshot, local_tree,
                              published_files, published_version, root, today, links_doc,
                              root_license_changed=row.get("rootLicenseChanged", False),
                              prior_proof=prior_proof, repo_url=url, head_commit=head,
                              pinned_repo_tree=pinned_repo_tree, head_repo_tree=head_repo_tree,
                              pinned_subtree_tree=row.get("pinnedSubtreeOid"),
                              head_subtree_tree=row.get("headSubtreeOid"))
        verification = {
            "statusMatch": replayed.get("status") == row.get("status"),
            "digestMatch": (replayed.get("candidate") or {}).get("contentDigest")
                           == (row.get("candidate") or {}).get("contentDigest"),
            "zipShaMatch": (replayed.get("candidate") or {}).get("packageSha256")
                           == (row.get("candidate") or {}).get("packageSha256"),
            "versionMatch": replayed.get("proposedVersion") == row.get("proposedVersion"),
        }
        if not all(verification.values()):
            raise UpstreamError(f"{skill_id}: stage replay diverged from the plan "
                                f"({verification}); refusing to stage non-deterministic input")
        candidate = replayed.pop("_candidateTree")
        package_zip = replayed.pop("_packageZip")
        version = replayed["proposedVersion"]
        base = stage_root / "candidates" / skill_id / version
        (base / "tree").mkdir(parents=True)
        for rel, data in sorted(candidate.items()):
            target = base / "tree" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (base / "package.zip").write_bytes(package_zip)
        replayed["replayVerification"] = verification
        (base / "candidate.json").write_bytes(dump_report(replayed))

        for rel, data in sorted(candidate.items()):
            writes[f"sources/{skill_id}/{rel}"] = data
        for rel in sorted(set(local_tree) - set(candidate)):
            deletions.append(f"sources/{skill_id}/{rel}")
        writes[f"reviews/{skill_id}/{version}.review.json"] = \
            hubcore.encoded(replayed["proposedReview"])
        review_stage_counts["prior-proof-reuse" if replayed.get("tier") == 2
                              else "static-content-reviewed"] += 1
        bumped_versions[skill_id] = {"from": published_version, "to": version}

        reg_entry = new_registry_by_id[skill_id]
        reg_entry["versionTarget"] = version
        reg_entry["upstream"] = dict(reg_entry["upstream"], commit=head, retrievedAt=today)

        evidence = replayed.get("showcaseEvidence") or {}
        proposed = [r for r in evidence.get("records", []) if r.get("state") == "proposed"]
        if proposed:
            if links_bytes is None:
                raise UpstreamError(f"{skill_id}: showcase evidence proposals exist but "
                                    f"{LINKS_REL} is missing")
            links_bytes = apply_evidence_proposals(links_bytes, skill_id,
                                                   evidence["records"])
        candidates_summary.append({
            "id": skill_id, "version": version, "tier": replayed.get("tier"),
            "status": replayed["status"],
            "candidateDir": f"candidates/{skill_id}/{version}",
            "contentDigest": replayed["candidate"]["contentDigest"],
            "packageSha256": replayed["candidate"]["packageSha256"],
            "changedPaths": replayed["candidate"]["changedPaths"],
            "executionFingerprintEqual": replayed["executionFingerprint"]["equal"],
            "instructionCodeFingerprintEqual": replayed["instructionCodeFingerprint"]["equal"],
            "showcaseEvidence": {"maintained": sum(1 for r in evidence.get("records", [])
                                                   if r.get("state") == "maintained"),
                                 "proposed": len(proposed),
                                 "held": len(evidence.get("held", []))},
        })

    # Held records: current version and exact old pin stay intact and published.
    for row in held_rows:
        held_record = {k: v for k, v in row.items() if not k.startswith("_")}
        held_record["publishedVersionIntact"] = True
        (stage_root / "held" / f"{row['id']}.json").write_bytes(dump_report(held_record))

    # Pin-only advances for accepted no-change entries of updated repositories.
    for row in skills:
        skill_id = row["id"]
        if skill_id in eligible_ids or skill_id not in accepted_ids:
            continue
        advance = row.get("pinAdvance")
        if not advance:
            continue
        reg_entry = new_registry_by_id[skill_id]
        reg_entry["upstream"] = dict(reg_entry["upstream"], commit=advance["to"],
                                     retrievedAt=today)

    hubcore.validate_registry(new_registry,
                              expect_counts=inputs.get("expectCounts"))
    writes[REGISTRY_REL] = hubcore.pretty(new_registry)
    new_pins_bytes, helper_label = advance_pins(pins_bytes, registry_doc, new_registry,
                                                accepted_ids, today)
    writes[PINS_REL] = new_pins_bytes
    if links_bytes is not None and links_bytes != (
            links_path.read_bytes() if links_path.is_file() else None):
        writes[LINKS_REL] = links_bytes

    apply_files = stage_root / "apply" / "files"
    manifest_writes = []
    skipped_noops = []
    for rel in sorted(writes):
        data = writes[rel]
        current = root / rel
        if current.is_file() and current.read_bytes() == data:
            skipped_noops.append(rel)  # byte-identical: keep the apply set honest
            continue
        target = apply_files / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest_writes.append({"path": rel, "sha256": sha256_bytes(data), "bytes": len(data)})
    apply_manifest = {
        "schemaVersion": 1,
        "generatedFromPlanSha256": sha256_bytes(dump_report(plan_report)),
        "today": today,
        "pinsHelper": helper_label,
        "acceptedIds": sorted(accepted_ids),
        "writes": manifest_writes,
        "skippedByteIdenticalNoops": skipped_noops,
        "deletions": sorted(deletions),
        "reviewRecords": "new unsigned records only; S/X construction follows the pipeline "
                         "contract (S carries only the new unsigned records, X restores every "
                         "historical pair from base B byte-identically)",
        "ordering": "apply writes and deletions, then run scripts/build_packages.py, then the "
                    "existing CI gates, then the staging commit chain",
    }
    (stage_root / "apply" / "manifest.json").write_bytes(dump_report(apply_manifest))

    hold_reasons = []
    for row in held_rows:
        for reason in row.get("reasons") or []:
            hold_reasons.append({"id": row["id"], "code": reason.get("code"),
                                 "detail": reason.get("detail"), "repair": reason.get("repair")})
    staging_manifest = {
        "reportKind": REPORT_KIND_STAGE,
        "reportVersion": REPORT_VERSION,
        "today": today,
        "inputs": plan_report.get("inputs"),
        "planSha256": sha256_bytes(dump_report(plan_report)),
        "stageRoot": str(stage_root),
        "candidates": candidates_summary,
        "heldIds": sorted(row["id"] for row in held_rows),
        "candidateFacts": {
            "changedSkillIds": sorted(eligible_ids),
            "bumpedVersions": {k: bumped_versions[k] for k in sorted(bumped_versions)},
            "heldSkillIds": sorted(row["id"] for row in held_rows),
            "holdReasons": hold_reasons,
            "pinAdvances": plan_report.get("acceptance", {}).get("pinAdvances", {}),
            "acceptedIds": sorted(accepted_ids),
            "reviewStageCounts": review_stage_counts,
            "executableSubsetUnchanged": {c["id"]: c["executionFingerprintEqual"]
                                          for c in candidates_summary},
            "engineSignals": plan_report.get("engineTracking", []),
        },
        "boundary": ("stage wrote only under the stage root; the live checkout sources/, "
                     "packages/, reviews/, catalog feeds, publication ledger, showcase/ and "
                     "docs/UPSTREAM-PINS.json were not modified; integration, signing, "
                     "ledger append and CAS publication stay with the Root-owned pipeline"),
        "counts": {"staged": len(candidates_summary), "held": len(held_rows),
                   "applyWrites": len(manifest_writes), "applyDeletions": len(deletions)},
    }
    (stage_root / "staging-manifest.json").write_bytes(dump_report(staging_manifest))
    return staging_manifest


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _default_cache():
    base = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    return str(pathlib.Path(base) / "floe-skill-hub-upstream-cache")


def _emit(report, args):
    data = dump_report(report)
    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
    if not args.quiet:
        counts = report.get("counts") or {}
        print(f"[{report.get('reportKind')}] " +
              ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="upstream_updates.py",
        description="Generic upstream tracking and candidate construction core "
                    "(unattended GitHub Actions execution; never signs or publishes).")
    parser.add_argument("command", choices=("check", "plan", "stage", "validate-policy"))
    parser.add_argument("--repo-root", default=str(REPO))
    parser.add_argument("--policy", default=None)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--today", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--only", default=None,
                        help="comma-separated skill ids (check/plan only; stage materializes "
                             "the full plan)")
    parser.add_argument("--git-timeout", type=int, default=600)
    parser.add_argument("--fail-on-error", action="store_true",
                        help="exit 3 when any repository/skill fact is an error state")
    parser.add_argument("--plan", default=None, help="plan report file (stage)")
    parser.add_argument("--stage-root", default=None, help="output directory (stage)")
    parser.add_argument("--check-report", default=None, help="check report file (plan)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.today and not hubcore.DATE_PATTERN.fullmatch(args.today):
        print(json.dumps({"error": "--today must be YYYY-MM-DD"}), file=sys.stderr)
        return 1

    try:
        inputs = load_inputs(args.repo_root, args.policy)
        root = inputs["root"]
        if args.command == "validate-policy":
            result = {"reportKind": "floe-skill-hub-upstream-policy-validation",
                      "reportVersion": REPORT_VERSION, "valid": True,
                      "inputs": _input_digests(root, inputs["policy"]),
                      "selection": {
                          "tracked": len(inputs["policy"]["selection"]["tracked"]),
                          "engineManaged": len(inputs["policy"]["selection"]["engineManaged"]),
                          "watchOnly": len(inputs["policy"]["selection"]["watchOnly"]),
                          "excluded": (len(inputs["policy"]["selection"]["notTracked"]["builtins"])
                                       + len(inputs["policy"]["selection"]["notTracked"]["firstParty"])),
                          "registryEntries": len(inputs["entries"])}}
            try:
                import jsonschema
                schema = load_json_bytes(root / POLICY_SCHEMA_REL, "policy schema")
                jsonschema.validate(inputs["policy"], schema)
                result["jsonschema"] = "passed"
            except ImportError:
                result["jsonschema"] = "library-unavailable (structural validation only)"
            _emit(result, args)
            return 0

        only = [part.strip() for part in args.only.split(",")] if args.only else None
        today = args.today or _today_utc()
        source = GitUpstreamSource(args.cache or _default_cache(), timeout=args.git_timeout)

        if args.command == "check":
            report = run_check(root, inputs, source, today, only=only)
        elif args.command == "plan":
            check_report = None
            if args.check_report:
                check_report = load_json_bytes(args.check_report, "check report")
            report = run_plan(root, inputs, source, today, only=only,
                              check_report=check_report)
        else:  # stage
            if not args.plan or not args.stage_root:
                print(json.dumps({"error": "stage requires --plan and --stage-root"}),
                      file=sys.stderr)
                return 1
            if only:
                print(json.dumps({"error": "stage materializes the full plan; use --only with "
                                           "check/plan"}), file=sys.stderr)
                return 1
            plan_report = load_json_bytes(args.plan, "plan report")
            report = run_stage(root, inputs, source, plan_report, args.stage_root)
        _emit(report, args)
        if args.fail_on_error:
            error_states = [s for s in report.get("skills", []) if s.get("state") == ST_ERROR
                            or s.get("status") == ST_ERROR]
            if report.get("errors") or error_states:
                return 3
        return 0
    except (UpstreamError, hubcore.HubError) as error:
        print(json.dumps({"error": str(error), "failClosed": True}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
