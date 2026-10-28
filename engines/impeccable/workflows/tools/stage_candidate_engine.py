#!/usr/bin/env python3
"""Stage a caller-owned candidate engine tree for the updater workflow.

`build/build_engine.py` resolves its inputs module-relative to its own
location: `ENGINE-LOCK.json`, `adapter/`, `patches/` and `contract/`. The
tracked lock names the reviewed pin, so invoking the tracked builder on a
changed candidate fails `verify_pin` (source HEAD vs the OLD lock) before any
preflight runs. This tool stages a temporary engine tree — a strict byte copy
of the reviewed build inputs plus the candidate lock, with ONLY the candidate
identity fields of the staged contract rewritten — so the staged builder
verifies the candidate against the candidate pin.

The staged tree is laid out as a minimal hub view so every module-relative
path in the staged builder resolves inside the temp root:

  <out>/LICENSE                              copy of the tracked hub LICENSE
  <out>/engines/impeccable/ENGINE-LOCK.json  the staged candidate lock (verbatim)
  <out>/engines/impeccable/build/            byte copy of the tracked builder
  <out>/engines/impeccable/adapter/          byte copy, except the identity
      literals pinned by the trusted Rust contract tests and the
      candidate-only host-target anchors of the rule-pass harness (see below)
  <out>/engines/impeccable/patches/          byte copy
  <out>/engines/impeccable/contract/         byte copy, with the candidate
      identity fields in snapshot-contract.v1.json
      (engine.upstreamCommit/upstreamTree/upstreamEngineVersion/engineId/
      floeAdapterVersion, provenance.upstreamCommit/upstreamTree/
      engineVersionFile and the engine-probe verb's documented stdout)
      rewritten to the candidate identity; every other field, and every
      other file, is byte-identical to the tracked contract.

The FLOE-owned Rust tests are part of the trusted evidence: they pin the
published identity as literals (`tests/contract_embedded.rs`,
`tests/snapshot_scan.rs` and the engine/diagnostics identity lines of the
recorded `tests/data/expected-*.json` results) so an unintended bump fails the
suite. Those exact anchored lines in the staged TEMP copies — and nothing
else — are projected from the authenticated published identity to the
authenticated candidate identity, because the staged contract and binary carry
the candidate identity; every other test byte, assertion and behaviour check
stays the tracked byte. A changed trusted-test shape fails closed before any
test byte is written, and staging the published pin itself is a byte-identical
no-op. The rewritten test bytes are hashed into the receipt like the contract.

One further candidate-only projection fixes host-test portability in the
staged TEMP copy of `tests/rule_pass_limiter.rs` (the tracked test and the
production comparator stay strict): the recorded rule-pass goldens name the
build host that produced them (`aarch64-apple-darwin`), while the hosted
adapter suite compiles for whatever cargo target the runner has
(`x86_64-unknown-linux-gnu`). The staged harness asserts the observed result
names the actual cargo target exported by `adapter/build.rs`
(`env!("FLOE_TARGET_TRIPLE")`), asserts the recorded golden names its trusted
archived target (a single safe value derived from BOTH frozen goldens;
disagreement or an unsafe literal fails closed), then projects the expected
golden's target to the actual cargo target and keeps the field in the exact
comparison. This binding is applied only to a NEW candidate identity: staging
the published pin keeps every staged test byte identical to the tracked byte
and records old-to-old change entries.

The full projected set is exactly what `build_engine.verify_contract_identity`
checks — the real hosted preflight run 40622397082 failed because the earlier
projection carried the four upstream keys but not the engine-probe version
stdout. The projected values are never taken from caller strings: the
component identity is derived by the adapter's own canonical helper
(`adapter/tools/sync_contract_identity.py`, a trusted Root-frozen staging
module) from the candidate lock's `upstream.engineVersion` plus the adapter
crate Cargo.toml version — the single component version constant the binary
embeds — and the candidate lock's `engineId` / `floe.adapterVersion` are
authenticated against that derivation, so a lock whose identity shape or
current version disagrees fails closed before anything is written.

Nothing under the tracked engine dir, the tracked lock, the frozen contract,
the frozen binary or `sources/impeccable` is modified. The tool refuses a
non-empty or symlinked output root and validates every candidate identity
shape before writing. It never deletes caller data.

  stage_candidate_engine.py --engine-dir engines/impeccable \
      --candidate-lock <staged ENGINE-LOCK.json> --out <fresh temp hub root>
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

HEX40 = re.compile(r"[0-9a-f]{40}")
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
# A cargo target triple embedded verbatim in generated Rust must be a plain
# lowercase triple: no quote, backslash, newline or format character can reach
# the staged source. `unknown-target` is the build.rs fallback, not a real
# build target, so it is not trusted for the archived-golden binding either.
SAFE_TARGET_TRIPLE = re.compile(r"[a-z0-9_]+(?:-[a-z0-9_]+)+")

ENGINE_IDENTITY_FIELDS = (
    ("engine", "upstreamCommit"),
    ("engine", "upstreamTree"),
    ("engine", "upstreamEngineVersion"),
    ("engine", "engineId"),
    ("provenance", "upstreamCommit"),
    ("provenance", "upstreamTree"),
    ("provenance", "engineVersionFile"),
)


def fail(message: str, **detail) -> int:
    print(json.dumps({"ok": False, "error": message, **detail}, indent=2))
    return 2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_tree(src: Path, dst: Path) -> dict:
    """Byte copy src -> dst; returns {relative: sha256} for every file.

    Symbolic links are refused, never followed: the staged tree must be
    plain files so the staged builder cannot be redirected at tracked
    content."""
    digests = {}
    for path in sorted(src.rglob("*")):
        if path.is_symlink():
            raise SystemExit(json.dumps({"ok": False,
                                         "error": f"refusing to stage a symbolic link: {path}"}))
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise SystemExit(json.dumps({"ok": False,
                                         "error": f"refusing to overwrite a symbolic link: {target}"}))
        shutil.copyfile(path, target)
        digests[str(rel)] = sha256_file(target)
        if digests[str(rel)] != sha256_file(path):
            raise SystemExit(json.dumps({"ok": False,
                                         "error": f"copy drifted while staging: {rel}"}))
    return digests


def validate_identity(lock: dict) -> dict:
    upstream = lock.get("upstream")
    if not isinstance(upstream, dict):
        raise ValueError("candidate lock has no upstream object")
    commit = upstream.get("commit")
    tree = upstream.get("tree")
    version = upstream.get("engineVersion")
    engine_id = lock.get("engineId")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise ValueError(f"candidate lock upstream.commit is not a 40-hex sha: {commit!r}")
    if not isinstance(tree, str) or not HEX40.fullmatch(tree):
        raise ValueError(f"candidate lock upstream.tree is not a 40-hex sha: {tree!r}")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError(f"candidate lock upstream.engineVersion is not dotted-semver: {version!r}")
    if not isinstance(engine_id, str) or not engine_id.startswith("impeccable-"):
        raise ValueError(f"candidate lock engineId is missing or malformed: {engine_id!r}")
    return {"commit": commit, "tree": tree, "version": version, "engineId": engine_id}


def load_identity_sync_helper(engine_dir: Path):
    """Import the adapter's canonical identity sync formula from the engine
    tree. It is a trusted Root-frozen staging module (stdlib only, no side
    effects at import) and the single authority for the derivation the
    shipped binary and the build identity gate both use."""
    helper_path = engine_dir / "adapter" / "tools" / "sync_contract_identity.py"
    if not helper_path.is_file():
        raise ValueError(f"the canonical identity sync helper is missing: {helper_path}")
    spec = importlib.util.spec_from_file_location("floe_sync_contract_identity", helper_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load the canonical identity sync helper: {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_component_identity(engine_dir: Path, identity: dict) -> tuple:
    """The canonical component identity for this candidate: the lock's
    validated engineVersion plus the adapter crate Cargo.toml version, read
    through the adapter's own helper. Caller-supplied strings are never a
    projection source; the lock's engineId/floe.adapterVersion are only
    authenticated against this derivation."""
    sync = load_identity_sync_helper(engine_dir)
    try:
        adapter_version = sync.crate_version(engine_dir / "adapter")
    except SystemExit as error:
        raise ValueError(f"cannot read the adapter crate version: {error}") from None
    expected = sync.expected_identity(
        {"engine": {"upstreamEngineVersion": identity["version"]}}, adapter_version)
    return sync, adapter_version, expected


def authenticate_lock_identity(lock: dict, identity: dict, expected: dict) -> None:
    """Fail closed when the candidate lock's identity strings disagree with
    the canonical derivation (lock version + crate component version)."""
    if identity["engineId"] != expected["engineId"]:
        raise ValueError(
            "the candidate lock engineId is not the canonical component identity "
            "derived from its upstream.engineVersion and the adapter crate Cargo.toml "
            f"version: lock says {identity['engineId']!r}, derived {expected['engineId']!r}")
    floe = lock.get("floe")
    if isinstance(floe, dict):
        floe_adapter = floe.get("adapterVersion")
        if floe_adapter is not None and floe_adapter != expected["floeAdapterVersion"]:
            raise ValueError(
                "the candidate lock floe.adapterVersion disagrees with the adapter "
                f"crate Cargo.toml version: lock says {floe_adapter!r}, "
                f"crate says {expected['floeAdapterVersion']!r}")


def probe_stdout_value(expected: dict) -> str:
    """The parsed-form probe stdout the identity gate expects: the helper's
    documented JSON escape becomes the real newline the binary prints."""
    return expected["engineProbeStdout"].replace("\\n", "\n")


def set_probe_verb_stdout(doc: dict, value: str) -> None:
    verbs = doc.get("verbs")
    if not isinstance(verbs, list):
        raise ValueError("tracked contract has no verbs array carrying the engine-probe identity")
    matches = [verb for verb in verbs
               if isinstance(verb, dict) and verb.get("name") == "engine-probe"]
    if len(matches) != 1:
        raise ValueError("the tracked contract must carry exactly one engine-probe verb, "
                         f"found {len(matches)}")
    if not isinstance(matches[0].get("stdout"), str):
        raise ValueError("the tracked engine-probe verb has no stdout example to project")
    matches[0]["stdout"] = value


def rewrite_contract_identity(contract_dir: Path, identity: dict, expected: dict) -> list:
    """Copy the contract, rewrite only the candidate identity fields, and
    return {field, before, after} for each change."""
    target = contract_dir / "snapshot-contract.v1.json"
    doc = json.loads(target.read_text(encoding="utf-8"))
    changes = []
    for section, key in ENGINE_IDENTITY_FIELDS:
        node = doc.get(section)
        if not isinstance(node, dict) or key not in node:
            raise ValueError(f"tracked contract is missing {section}.{key}")
        before = node[key]
        after = {
            ("engine", "upstreamCommit"): identity["commit"],
            ("engine", "upstreamTree"): identity["tree"],
            ("engine", "upstreamEngineVersion"): identity["version"],
            ("engine", "engineId"): expected["engineId"],
            ("provenance", "upstreamCommit"): identity["commit"],
            ("provenance", "upstreamTree"): identity["tree"],
            ("provenance", "engineVersionFile"): identity["version"],
        }[(section, key)]
        node[key] = after
        changes.append({"field": f"{section}.{key}", "before": before, "after": after})
    engine_node = doc.get("engine")
    if not isinstance(engine_node, dict) or "floeAdapterVersion" not in engine_node:
        raise ValueError("tracked contract is missing engine.floeAdapterVersion")
    changes.append({"field": "engine.floeAdapterVersion",
                    "before": engine_node["floeAdapterVersion"],
                    "after": expected["floeAdapterVersion"]})
    engine_node["floeAdapterVersion"] = expected["floeAdapterVersion"]
    before_probe = next((verb.get("stdout") for verb in doc.get("verbs", [])
                         if isinstance(verb, dict) and verb.get("name") == "engine-probe"), None)
    set_probe_verb_stdout(doc, probe_stdout_value(expected))
    changes.append({"field": "verbs[engine-probe].stdout",
                    "before": before_probe, "after": probe_stdout_value(expected)})
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changes


def verify_staged_identity(staged_contract_path: Path, identity: dict,
                           adapter_version: str, expected: dict) -> None:
    """Mirror of build_engine.verify_contract_identity's field checks over the
    written staged contract: if the staged tree would not pass the unchanged
    builder identity gate, this staging itself must fail closed."""
    doc = json.loads(staged_contract_path.read_text(encoding="utf-8"))
    engine = doc.get("engine", {})
    problems = []
    if engine.get("upstreamEngineVersion") != identity["version"]:
        problems.append("staged engine.upstreamEngineVersion drifted from the candidate lock")
    if engine.get("upstreamCommit") != identity["commit"]:
        problems.append("staged engine.upstreamCommit drifted from the candidate lock")
    if engine.get("engineId") != expected["engineId"]:
        problems.append(f"staged engine.engineId is {engine.get('engineId')!r}, "
                        f"must be {expected['engineId']!r}")
    if engine.get("floeAdapterVersion") != adapter_version:
        problems.append(f"staged engine.floeAdapterVersion is {engine.get('floeAdapterVersion')!r}, "
                        f"must be the crate version {adapter_version!r}")
    probe_verb = next((verb for verb in doc.get("verbs", [])
                       if isinstance(verb, dict) and verb.get("name") == "engine-probe"), None)
    want = probe_stdout_value(expected)
    if probe_verb is None or probe_verb.get("stdout") != want:
        problems.append(f"staged verbs[engine-probe].stdout is "
                        f"{probe_verb.get('stdout') if probe_verb else None!r}, must be {want!r}")
    if problems:
        raise ValueError("; ".join(problems))


# The trusted Rust tests that carry the pin identity as literals, plus the
# staged rule-pass harness whose host-target binding is candidate-only. Identity
# entries are whole source lines; the fifth file's host anchors are whole
# source blocks. Each ledger entry records the exact published and candidate
# form the tracked/staged TEMP bytes must carry.
TEST_IDENTITY_FILES = (
    "tests/contract_embedded.rs",
    "tests/snapshot_scan.rs",
    "tests/data/expected-large-shape.v1.json",
    "tests/data/expected-admission-exactcap.v1.json",
    # fifth projected file: candidate-only host-target binding of the staged
    # rule-pass harness (the whole tracked test is the published pin's byte)
    "tests/rule_pass_limiter.rs",
)


def published_test_identity(engine_dir: Path, adapter_version: str) -> dict:
    """The published identity the trusted tests pin, from the frozen contract.

    The unstaged tests assert the identity of the contract the binary embeds,
    so their literals are authenticated against the tracked contract and the
    same canonical component formula the candidate projection uses. A contract
    whose identity is not self-consistent fails closed instead of yielding a
    plausible-but-wrong literal to rewrite."""
    contract_path = engine_dir / "contract" / "snapshot-contract.v1.json"
    doc = json.loads(contract_path.read_text(encoding="utf-8"))
    engine = doc.get("engine")
    if not isinstance(engine, dict):
        raise ValueError("the tracked contract has no engine object")
    commit = engine.get("upstreamCommit")
    tree = engine.get("upstreamTree")
    version = engine.get("upstreamEngineVersion")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise ValueError(f"tracked contract engine.upstreamCommit is not a 40-hex sha: {commit!r}")
    if not isinstance(tree, str) or not HEX40.fullmatch(tree):
        raise ValueError(f"tracked contract engine.upstreamTree is not a 40-hex sha: {tree!r}")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError(f"tracked contract engine.upstreamEngineVersion is not dotted-semver: {version!r}")
    component = f"{version}+floe.{adapter_version}"
    probe = next((verb.get("stdout") for verb in doc.get("verbs", [])
                  if isinstance(verb, dict) and verb.get("name") == "engine-probe"), None)
    problems = []
    if engine.get("engineId") != f"impeccable-{component}":
        problems.append(f"tracked contract engine.engineId is {engine.get('engineId')!r}, "
                        f"must be the canonical impeccable-{component}")
    if engine.get("floeAdapterVersion") != adapter_version:
        problems.append(f"tracked contract engine.floeAdapterVersion is "
                        f"{engine.get('floeAdapterVersion')!r}, must be the crate version "
                        f"{adapter_version!r}")
    if probe != f"impeccable-engine {component}\n":
        problems.append(f"tracked contract engine-probe stdout is {probe!r}, must be "
                        f"'impeccable-engine {component}\\n'")
    if problems:
        raise ValueError("; ".join(problems))
    return {"commit": commit, "tree": tree, "version": version, "component": component}


def archived_test_target(tracked_adapter: Path) -> str:
    """The single trusted build target the frozen rule-pass goldens recorded.

    Both goldens were captured by the same pre-patch host build, so they must
    name the same safe cargo-style triple. A disagreement means one golden was
    re-recorded without the other; an unsafe literal could break out of the
    generated Rust string. Both fail closed before any test byte is written."""
    targets = {}
    for name in ("expected-large-shape.v1.json", "expected-admission-exactcap.v1.json"):
        path = tracked_adapter / "tests" / "data" / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        engine = doc.get("engine")
        target = engine.get("targetTriple") if isinstance(engine, dict) else None
        if (not isinstance(target, str) or not SAFE_TARGET_TRIPLE.fullmatch(target)
                or target == "unknown-target"):
            raise ValueError(
                f"the frozen rule-pass golden {name} does not carry a safe trusted "
                f"engine.targetTriple: {target!r}")
        targets[name] = target
    unique = set(targets.values())
    if len(unique) != 1:
        raise ValueError(
            "the frozen rule-pass goldens disagree about their trusted archived "
            f"build target: {targets!r}")
    return unique.pop()


def test_identity_rewrites(published: dict, identity: dict, component: str) -> list:
    """The exact trusted-test lines that pin identity, in published and
    candidate form. Only these literals move; the surrounding assertions stay
    the reviewed bytes."""
    pub_version = published["version"]
    pub_commit = published["commit"]
    pub_tree = published["tree"]
    pub_component = published["component"]
    version = identity["version"]
    commit = identity["commit"]
    tree = identity["tree"]
    rewrites = [
        {"file": "tests/contract_embedded.rs", "occurrences": 1,
         "pinned": ('    assert_eq!(contract["engine"]["upstreamEngineVersion"]'
                    f'.as_str().unwrap(), "{pub_version}");'),
         "projected": ('    assert_eq!(contract["engine"]["upstreamEngineVersion"]'
                       f'.as_str().unwrap(), "{version}");')},
        {"file": "tests/contract_embedded.rs", "occurrences": 1,
         "pinned": f'    assert_eq!(stdout, "impeccable-engine {pub_component}\\n");',
         "projected": f'    assert_eq!(stdout, "impeccable-engine {component}\\n");'},
        {"file": "tests/contract_embedded.rs", "occurrences": 1,
         "pinned": f'    assert_eq!(stdout, "{pub_component}\\n");',
         "projected": f'    assert_eq!(stdout, "{component}\\n");'},
        {"file": "tests/snapshot_scan.rs", "occurrences": 1,
         "pinned": (f'    assert_eq!(result.doc["engine"]["upstreamEngineVersion"], '
                    f'json!("{pub_version}"));'),
         "projected": (f'    assert_eq!(result.doc["engine"]["upstreamEngineVersion"], '
                       f'json!("{version}"));')},
        {"file": "tests/snapshot_scan.rs", "occurrences": 1,
         "pinned": f'    assert_eq!(engine["upstreamEngineVersion"], json!("{pub_version}"));',
         "projected": f'    assert_eq!(engine["upstreamEngineVersion"], json!("{version}"));'},
        {"file": "tests/snapshot_scan.rs", "occurrences": 1,
         "pinned": f'    assert_eq!(engine["engineId"], json!("impeccable-{pub_component}"));',
         "projected": f'    assert_eq!(engine["engineId"], json!("impeccable-{component}"));'},
    ]
    for name in ("expected-large-shape.v1.json", "expected-admission-exactcap.v1.json"):
        # The rule-pass goldens record the engine block AND a diagnostics block
        # mirroring the same contract identity; the Rust test normalizes only
        # the engine block's engineId/adapter versions away, so both blocks
        # must carry the candidate pin while the historical recorded engineId
        # (normalized by the test) stays the recorded byte.
        rewrites.extend([
            {"file": f"tests/data/{name}", "occurrences": 1,
             "pinned": f'    "upstreamEngineVersion": "{pub_version}",',
             "projected": f'    "upstreamEngineVersion": "{version}",'},
            {"file": f"tests/data/{name}", "occurrences": 2,
             "pinned": f'    "upstreamCommit": "{pub_commit}",',
             "projected": f'    "upstreamCommit": "{commit}",'},
            {"file": f"tests/data/{name}", "occurrences": 1,
             "pinned": f'    "upstreamTree": "{pub_tree}",',
             "projected": f'    "upstreamTree": "{tree}",'},
            {"file": f"tests/data/{name}", "occurrences": 1,
             "pinned": f'    "engineVersion": "{pub_version}",',
             "projected": f'    "engineVersion": "{version}",'},
        ])
    return rewrites


def host_target_rewrites(archived_target: str) -> list:
    """The candidate-only host harness anchors in `tests/rule_pass_limiter.rs`.

    The recorded goldens were captured on the archived host target, but the
    hosted adapter suite compiles for the runner's own cargo target. The staged
    TEMP copy therefore (1) asserts the observed result names the actual cargo
    target the adapter `build.rs` exported, (2) asserts the recorded golden
    names the single trusted archived target, and (3) projects the EXPECTED
    golden's `engine.targetTriple` to the actual cargo target. The field is
    KEPT in `normalize()` so the rest of the golden comparison stays exact.

    These are whole-source-block anchors: the exact occurrence count and exact
    reverse projection are validated before writing, like the identity lines.
    """
    observed = "        let observed = normalize(doc(&result).clone());\n"
    observed_projected = (
        "        assert_eq!(\n"
        '            doc(&result)["engine"]["targetTriple"],\n'
        '            json!(env!("FLOE_TARGET_TRIPLE")),\n'
        '            "{name}: the candidate result names the build host target"\n'
        "        );\n"
        + observed
    )
    golden = (
        "        let golden: Value = serde_json::from_str(\n"
        '            &std::fs::read_to_string(test_data().join(expected)).expect("golden exists"),\n'
        "        )\n"
        '        .expect("golden JSON");\n'
        "        let golden = normalize(golden);\n"
    )
    golden_projected = (
        "        let mut golden: Value = serde_json::from_str(\n"
        '            &std::fs::read_to_string(test_data().join(expected)).expect("golden exists"),\n'
        "        )\n"
        '        .expect("golden JSON");\n'
        "        assert_eq!(\n"
        '            golden["engine"]["targetTriple"],\n'
        f'            json!("{archived_target}"),\n'
        '            "{name}: the recorded reference names its trusted archived build target"\n'
        "        );\n"
        '        golden["engine"]["targetTriple"] = json!(env!("FLOE_TARGET_TRIPLE"));\n'
        "        let golden = normalize(golden);\n"
    )
    return [
        {"file": "tests/rule_pass_limiter.rs", "occurrences": 1,
         "pinned": observed, "projected": observed_projected},
        {"file": "tests/rule_pass_limiter.rs", "occurrences": 1,
         "pinned": golden, "projected": golden_projected},
    ]


def project_staged_test_identity(tracked_adapter: Path, staged_adapter: Path,
                                 published: dict, identity: dict,
                                 expected: dict) -> tuple:
    """Project the published identity literals of the trusted tests onto the
    authenticated candidate identity, plus the candidate-only host target
    binding of the staged rule-pass harness.

    Every file and every anchored line is validated (exact occurrence count,
    exact reverse projection) before the first byte is written, so a changed
    trusted-test shape — or a projection that would move a non-identity byte —
    fails closed with the staged tree untouched. Returns the change list,
    per-file hash bindings and the host-binding receipt block; staging the
    published pin is a byte-identical no-op and is verified to be one."""
    component = expected["engineId"].removeprefix("impeccable-")
    current_is_published = (identity["commit"] == published["commit"]
                            and identity["tree"] == published["tree"]
                            and identity["version"] == published["version"])
    archived_target = archived_test_target(tracked_adapter)
    rewrites = test_identity_rewrites(published, identity, component)
    host_rewrites = host_target_rewrites(archived_target)
    if current_is_published:
        # The published pin must reproduce every tracked test byte exactly:
        # the host binding is candidate-only, so its recorded anchors are
        # old-to-old entries for this staging.
        host_rewrites = [{**entry, "projected": entry["pinned"]}
                         for entry in host_rewrites]
    rewrites.extend(host_rewrites)
    pending = {}
    changes = []
    for entry in rewrites:
        rel = entry["file"]
        if rel not in TEST_IDENTITY_FILES:
            raise ValueError(f"identity projection names an untrusted file: {rel}")
        path = staged_adapter / rel
        if path.is_symlink():
            raise ValueError(f"refusing to rewrite a symbolic link: {rel}")
        if not path.is_file():
            raise ValueError(f"the trusted test file is missing: {rel}")
        text = pending.get(rel)
        if text is None:
            text = path.read_bytes().decode("utf-8")
        found = text.count(entry["pinned"])
        if found != entry["occurrences"]:
            raise ValueError(
                f"the trusted test shape changed: {rel} carries {found} "
                f"occurrence(s) of the pinned anchor, expected "
                f"{entry['occurrences']}: {entry['pinned']!r}")
        projected = text.replace(entry["pinned"], entry["projected"])
        if entry["projected"] != entry["pinned"]:
            if projected.count(entry["projected"]) != entry["occurrences"]:
                raise ValueError(
                    f"the projected anchor did not land exactly "
                    f"{entry['occurrences']} time(s) in {rel}")
            if projected.replace(entry["projected"], entry["pinned"]) != text:
                raise ValueError(
                    f"the projection would move non-projected bytes in {rel}: "
                    f"{entry['pinned']!r}")
        pending[rel] = projected
        changes.append({"file": rel, "occurrences": entry["occurrences"],
                        "pinned": entry["pinned"], "projected": entry["projected"],
                        "changed": entry["projected"] != entry["pinned"]})
    for rel in TEST_IDENTITY_FILES:
        if rel not in pending:
            raise ValueError(f"the trusted test identity shape is incomplete: {rel} was not projected")
        if rel.endswith(".json"):
            try:
                json.loads(pending[rel])
            except json.JSONDecodeError as error:
                raise ValueError(f"the projected test golden is not valid JSON: {rel}: {error}") from None
    for rel, text in pending.items():
        (staged_adapter / rel).write_bytes(text.encode("utf-8"))

    files = {}
    problems = []
    for rel in TEST_IDENTITY_FILES:
        staged_path = staged_adapter / rel
        tracked_path = tracked_adapter / rel
        tracked_sha = sha256_file(tracked_path) if tracked_path.is_file() else None
        staged_sha = sha256_file(staged_path)
        files[rel] = {"trackedSha256": tracked_sha, "stagedSha256": staged_sha,
                      "changed": tracked_sha != staged_sha}
        if current_is_published and staged_sha != tracked_sha:
            problems.append(f"staging the published identity changed the trusted test bytes: {rel}")
    if problems:
        raise ValueError("; ".join(problems))
    host_binding = {
        "file": "tests/rule_pass_limiter.rs",
        "archivedTarget": archived_target,
        "compileTargetExpression": 'env!("FLOE_TARGET_TRIPLE")',
        "applied": not current_is_published,
        "note": "candidate-only host-test portability: the staged TEMP harness asserts "
                "the observed result names the actual cargo target exported by "
                "adapter/build.rs, asserts the recorded golden names its single trusted "
                "archived target, and projects that expected golden field to the actual "
                "cargo target while keeping it in the exact comparison. The tracked test, "
                "the production comparator and the riscv verification target stay strict; "
                "staging the published pin keeps every test byte identical.",
    }
    return changes, files, host_binding


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-dir", required=True, type=Path,
                    help="tracked engines/impeccable (read-only)")
    ap.add_argument("--candidate-lock", required=True, type=Path,
                    help="the staged candidate ENGINE-LOCK.json (already updated)")
    ap.add_argument("--out", required=True, type=Path,
                    help="fresh temp root of the staged hub view")
    args = ap.parse_args()

    # The original path is checked for symlinks BEFORE resolve(): resolve()
    # follows links, which would hide a symlinked output root. Intermediate
    # symlinked ancestors (e.g. the macOS /var -> /private/var temp prefix)
    # are allowed; the inside-tree guards below run on resolved paths.
    raw_out = Path(args.out).expanduser()
    if raw_out.is_symlink():
        return fail("the staged output root must not be a symbolic link", out=str(raw_out))
    out = raw_out.resolve()
    engine_dir = Path(args.engine_dir).expanduser().resolve()
    candidate_lock = Path(args.candidate_lock).expanduser().resolve()
    hub_root = engine_dir.parent.parent

    def inside(child: Path, parent: Path) -> bool:
        return child == parent or parent in child.parents

    if inside(out, engine_dir):
        return fail("the staged output root must not resolve inside the tracked engine dir",
                    out=str(out), engineDir=str(engine_dir))
    if inside(out, hub_root):
        return fail("the staged output root must not resolve inside the tracked hub tree",
                    out=str(out), hubRoot=str(hub_root))
    if out == candidate_lock:
        return fail("the staged output root must not be the candidate lock file itself",
                    out=str(out))

    if out.exists() and any(out.iterdir()):
        return fail("the staged output root already exists and is not empty; "
                    "this tool never deletes existing output", out=str(out))
    for required in ("build", "adapter", "patches", "contract"):
        if not (engine_dir / required).is_dir():
            return fail(f"tracked engine input missing: {engine_dir / required}")
    if not (hub_root / "LICENSE").is_file():
        return fail(f"tracked hub LICENSE missing: {hub_root / 'LICENSE'}")
    if not candidate_lock.is_file():
        return fail(f"candidate lock missing: {candidate_lock}")

    try:
        lock = json.loads(candidate_lock.read_text(encoding="utf-8"))
        identity = validate_identity(lock)
        _, adapter_version, expected = derive_component_identity(engine_dir, identity)
        authenticate_lock_identity(lock, identity, expected)
    except (json.JSONDecodeError, ValueError) as error:
        return fail(f"candidate lock is unusable: {error}")

    staged_engine = out / "engines" / "impeccable"
    staged_engine.mkdir(parents=True, exist_ok=True)

    copies = {}
    for name in ("build", "adapter", "patches", "contract"):
        copies[name] = copy_tree(engine_dir / name, staged_engine / name)
    shutil.copyfile(candidate_lock, staged_engine / "ENGINE-LOCK.json")
    shutil.copyfile(hub_root / "LICENSE", out / "LICENSE")

    try:
        changes = rewrite_contract_identity(staged_engine / "contract", identity, expected)
        verify_staged_identity(staged_engine / "contract" / "snapshot-contract.v1.json",
                               identity, adapter_version, expected)
    except (ValueError, json.JSONDecodeError) as error:
        return fail(f"staging the candidate contract identity failed: {error}",
                    stagedRoot=str(out))

    try:
        published = published_test_identity(engine_dir, adapter_version)
        test_changes, test_files, host_binding = project_staged_test_identity(
            engine_dir / "adapter", staged_engine / "adapter",
            published, identity, expected)
    except (ValueError, json.JSONDecodeError) as error:
        return fail(f"staging the candidate test identity failed: {error}",
                    stagedRoot=str(out))

    print(json.dumps({
        "ok": True,
        "stagedRoot": str(out),
        "stagedBuilder": str(staged_engine / "build" / "build_engine.py"),
        "engineDir": str(engine_dir),
        "candidate": identity,
        "adapterVersion": adapter_version,
        "componentVersion": expected["engineId"].removeprefix("impeccable-"),
        "identitySelfCheck": "passed",
        "contractChanges": changes,
        "trackedContractSha256": sha256_file(engine_dir / "contract" / "snapshot-contract.v1.json"),
        "stagedContractSha256": sha256_file(staged_engine / "contract" / "snapshot-contract.v1.json"),
        "copiedFiles": {name: len(files) for name, files in copies.items()},
        "stagedTestIdentity": {
            "published": published,
            "files": test_files,
            "changes": test_changes,
            "hostTargetBinding": host_binding,
            "note": "the trusted Rust contract tests pin the published identity as literals; "
                    "only those anchored lines in the staged TEMP copies carry the authenticated "
                    "candidate identity, every other test byte is the tracked byte, and staging "
                    "the published pin itself is a byte-identical no-op. The fifth file's "
                    "host-target binding is candidate-only and is never applied to the frozen "
                    "tracked test or to the production comparator.",
        },
        "note": "tracked lock, tracked contract, frozen binary and sources/impeccable are untouched; "
                "only the staged temp tree carries the candidate identity, derived from the "
                "candidate lock version plus the adapter crate Cargo.toml component version",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
