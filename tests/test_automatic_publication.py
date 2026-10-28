#!/usr/bin/env python3
"""Behaviour tests for the automatic-publication cloud orchestration.

Offline only: disposable local Git fixtures, ephemeral public-knowledge test
keys bound to the official key ID (never the production secret), no network,
no push, no model. Covers the whole two-phase data flow with the UNCHANGED
signer subprocessed exactly as the workflows run it — minimal unsigned S ->
fixture-key reviews signing -> metadata-only relay -> X restore of every
historical review pair -> catalog signing -> deterministic feed rebuild ->
Y/H with appended ledger rows -> mocked exact GraphQL CAS and idempotent
resume — plus the load-bearing negative refusals (forged guide body against
the fresh re-derivation, grants/dependency/instruction-code drift, engine and
archive deletion, wrong-key and tampered relay bytes, unknown relay path,
stale live base, already-processed replay, manifest candidateFacts never being
authority) and the workflow privilege/cadence/anchor structural guarantees.
"""
import base64
import copy
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts"))

import automatic_publication as ap  # noqa: E402
import hubcore  # noqa: E402

OFFICIAL_ORIGIN = "https://github.com/JiangNanGenius/floe-skill-hub.git"
TODAY = "2026-10-28"

TEST_SEED = hashlib.sha256(
    b"floe-skill-hub automatic-publication ephemeral TEST key -- NOT production").digest()
FOREIGN_SEED = hashlib.sha256(
    b"floe-skill-hub automatic-publication ephemeral FOREIGN key -- NOT production").digest()


def _key(seed):
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                           serialization.PublicFormat.Raw)
    return key, base64.b64encode(public).decode()


TEST_KEY, TEST_PUB = _key(TEST_SEED)
FOREIGN_KEY, _FOREIGN_PUB = _key(FOREIGN_SEED)
TRUST = {hubcore.PRODUCTION_KEY_ID: TEST_PUB}
GUIDE_ID = "copywriting"
SCRIPT_ID = "sympy"
GUIDE_REPO = "alirezarezvani/claude-skills"
SCRIPT_REPO = "K-Dense-AI/scientific-agent-skills"
GUIDE_OLD = "6d2f02ea077eead1bee5411a31bcc6db5a11a70c"
SCRIPT_OLD = "593377bb048752abb0152deab9fbb1083a6087df"
GUIDE_NEW = "7" * 40
SCRIPT_NEW = "8" * 40
P0_FEED_SOURCE = "1" * 40


def _git(where, *args, check=True):
    proc = subprocess.run(["git", "-C", str(where)] + list(args),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture git failed: {args}: {proc.stderr}")
    return proc.stdout.strip()


def _write(root, rel, data):
    full = pathlib.Path(root) / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def _commit_all(root, message):
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=floe-auto-fixture", "-c", "user.email=fixture@invalid",
         "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# fixture content builders (synthetic packages; never released bytes)
# ---------------------------------------------------------------------------


def _manifest(id_, version, caps, tools, platforms, runtime, packages=()):
    return hubcore.encoded({
        "schemaVersion": 1, "id": id_, "version": version,
        "capabilities": caps, "tools": tools, "platforms": platforms,
        "scriptRuntime": runtime, "pythonPackages": list(packages)})


def _skill_md(id_, body):
    return (f"---\nname: {id_}\ndescription: Isolated automatic-publication test "
            f"sample. Synthetic data, never released content.\n---\n\n{body}\n").encode()


def guide_files(version):
    return {
        "SKILL.md": _skill_md(GUIDE_ID, f"Guide body v{version}: prose only, no code."),
        "floe.json": _manifest(GUIDE_ID, version, ["workspace.read", "workspace.write"],
                               [], ["ios"], "none"),
        "references/NOTICE.md": b"Floe-owned synthetic fixture notice.\n",
    }


def script_files(version, extra_code=False):
    md = f"Scripted body v{version}: prose guidance."
    if extra_code:
        md += "\n\n```bash\nnewly-added-unsafe-command --now\n```\n"
    return {
        "SKILL.md": _skill_md(SCRIPT_ID, md),
        "floe.json": _manifest(
            SCRIPT_ID, version, ["execution.remote", "workspace.read", "workspace.write"],
            ["exec.shell"], ["ios"], "remote",
            packages=[{"spec": "sympy==1.14.0", "purpose": "symbolic math",
                       "capabilities": ["execution.remote"]},
                      {"spec": "mpmath==1.3.0", "purpose": "numeric backend",
                       "capabilities": ["execution.remote"]}]),
        "scripts/solve.py": b"import json\nprint(json.dumps({'fixture': True}))\n",
        "references/NOTICE.md": b"Floe-owned synthetic fixture notice.\n",
    }


def make_record(id_, version, files, *, stage, execution, notes, today=TODAY,
                reviewer="floe-skill-hub-auto-curation"):
    data = hubcore.make_zip(files)
    record = {
        "schemaVersion": 1, "id": id_, "version": version,
        "contentDigest": hubcore.content_digest(files),
        "packageSha256": hubcore.sha256_hex(data),
        "reviewedCapabilities": sorted(json.loads(files["floe.json"])["capabilities"]),
        "reviewedTools": sorted(json.loads(files["floe.json"])["tools"]),
        "reviewedPythonPackages": json.loads(files["floe.json"])["pythonPackages"],
        "execution": execution, "reviewStage": stage,
        "reviewedAt": today, "reviewer": reviewer, "decision": "approve",
        "notes": notes,
    }
    return hubcore.encoded(record), data


def _row(registry, id_):
    return next(e for e in registry["skills"] if e["id"] == id_)


def _unadmit(row):
    row = copy.deepcopy(row)
    row["status"] = dict(row["status"], sourcePinned=row["status"]["sourcePinned"],
                         packaged=False, reviewed=False, qualified=False,
                         published=False, executionVerified=False,
                         adaptation="planned" if row["upstream"] else row["status"]["adaptation"])
    if (row["plannedRuntime"]["execution"] or {}).get("evidence") == "guest-verified":
        row["plannedRuntime"] = dict(
            row["plannedRuntime"],
            execution={"os": None, "arch": "n/a", "evidence": "unproven"})
    return row


class HubFixture(unittest.TestCase):
    """One disposable Hub clone with a published base B and a tracker stage."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-auto-pub-test-")
        self.tmpdir = pathlib.Path(self.tmp.name)
        self.root = self.tmpdir / "hub"
        self.root.mkdir()
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "remote", "add", "origin", OFFICIAL_ORIGIN)
        shutil.copytree(REPO / "scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "schema").mkdir()
        _write(self.root, "schema/placeholder.json", b'{"x":1}')
        _write(self.root, "public-key.json",
               hubcore.encoded({"keyID": hubcore.PRODUCTION_KEY_ID, "publicKey": TEST_PUB}))
        _write(self.root, "catalog/upstream-update-policy.json",
               (REPO / "catalog" / "upstream-update-policy.json").read_bytes())
        # EXPLICIT frozen fixture identity (Root directive 2026-10-28): the
        # candidate rows never inherit live version/pin/grant values, because
        # the live registry legitimately evolves (manual guide publication
        # 1.0.0 -> 1.0.1, platform floors, per-entry pin overrides). Only the
        # structural 43/4/39/9 shape and the frozen-field vocabulary come from
        # the live registry copy.
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        registry["skills"] = [_unadmit(e) for e in registry["skills"]]
        guide = _row(registry, GUIDE_ID)
        script = _row(registry, SCRIPT_ID)
        guide["versionTarget"] = "1.0.0"
        guide["minimumAppVersion"] = "1.7.59"
        guide["upstream"] = dict(guide["upstream"], commit=GUIDE_OLD,
                                 retrievedAt="2026-10-26")
        guide["plannedRuntime"] = dict(
            guide["plannedRuntime"], scriptRuntime="none",
            capabilities=["workspace.read", "workspace.write"], tools=[],
            pythonPackagesPlan=[], installPlatforms=["ios", "android"],
            execution={"os": None, "arch": "n/a", "evidence": "unproven"})
        script["versionTarget"] = "1.0.0"
        script["minimumAppVersion"] = "1.7.59"
        script["upstream"] = dict(script["upstream"], commit=SCRIPT_OLD,
                                  retrievedAt="2026-10-26")
        script["plannedRuntime"] = dict(
            script["plannedRuntime"], scriptRuntime="remote",
            capabilities=["execution.remote", "workspace.read",
                          "workspace.write"],
            tools=["exec.shell"],
            pythonPackagesPlan=["sympy==1.14.0", "mpmath==1.3.0"],
            installPlatforms=["ios", "android"],
            execution={"os": "linux", "arch": "riscv64",
                       "evidence": "guest-verified"})
        for row in (guide, script):
            row["status"] = dict(row["status"], sourcePinned=True,
                                 licenseChecked=True, adaptation="frozen",
                                 packaged=True, reviewed=True, qualified=True,
                                 published=False,
                                 executionVerified=row is script)
        self.registry_base = registry
        pins = json.loads((REPO / "docs" / "UPSTREAM-PINS.json").read_bytes())
        pins["repositories"] = dict(pins["repositories"])
        pins["repositories"][GUIDE_REPO] = GUIDE_OLD
        pins["repositories"][SCRIPT_REPO] = SCRIPT_OLD
        overrides = dict(pins.get("skillOverrides") or {})
        for id_ in (GUIDE_ID, SCRIPT_ID):
            overrides.pop(id_, None)
        if overrides:
            pins["skillOverrides"] = overrides
        else:
            pins.pop("skillOverrides", None)
        self.pins_base = pins
        files_base = {GUIDE_ID: guide_files("1.0.0"), SCRIPT_ID: script_files("1.0.0")}
        self.p0 = self._build_published_base(files_base)

    def tearDown(self):
        self.tmp.cleanup()

    def _build_published_base(self, files_base):
        root = self.root
        for id_, files in files_base.items():
            data = hubcore.make_zip(files)
            for prefix in ("", "android/"):
                _write(root, f"{prefix}packages/{id_}/1.0.0/{id_}.zip", data)
            notes = ({"en": "fixture review", "zh-Hans": "测试审核"}
                     if id_ == GUIDE_ID else None)
            if id_ == GUIDE_ID:
                record, _ = make_record(id_, "1.0.0", files,
                                        stage="static-content-reviewed",
                                        execution={"os": None, "arch": "n/a",
                                                   "evidence": "unproven"},
                                        notes={"en": "fixture guide approval",
                                               "zh-Hans": "测试指南批准"})
            else:
                record, _ = make_record(
                    id_, "1.0.0", files, stage="guest-execution-qualified",
                    execution={"os": "linux", "arch": "riscv64", "evidence": "guest-verified"},
                    notes={"en": "fixture guest qualification",
                           "zh-Hans": "测试客户机资格认证记录"})
            _write(root, f"reviews/{id_}/1.0.0.review.json", record)
            _write(root, f"reviews/{id_}/1.0.0.review.json.sig",
                   hubcore.sign_envelope(record, TEST_KEY, hubcore.PRODUCTION_KEY_ID))
        _write(root, "engines/impeccable/ENGINE-LOCK.json", b'{"engineVersion":"1.0.0"}\n')
        _write(root, "catalog/skills.json", hubcore.pretty(self.registry_base))
        _write(root, "docs/UPSTREAM-PINS.json", hubcore.pretty(self.pins_base))
        for id_, files in files_base.items():
            for rel, data in sorted(files.items()):
                _write(root, f"sources/{id_}/{rel}", data)
        _write(root, ".gitignore", b"__pycache__/\n")
        _commit_all(root, "c0 base data")
        # P0 publication commit: canonical release feeds signed under the test key
        outputs = self._release_feeds(self.registry_base, P0_FEED_SOURCE)
        for rel, data in sorted(outputs.items()):
            _write(root, rel, data)
        for rel in ("catalog.json", "android/catalog.json"):
            sig_rel = rel[: -len(".json")] + ".sig"
            env_bytes = hubcore.sign_envelope(outputs[rel], TEST_KEY,
                                              hubcore.PRODUCTION_KEY_ID)
            _write(root, sig_rel, env_bytes)
        p0 = _commit_all(root, "p0 publication")
        rows = [ap._as_publication(lambda: __import__("publication_immutability")
                                   .build_ledger_row(self.root, p0, channel))
                for channel in ("ios", "android")]
        ledger = __import__("publication_immutability").render_ledger(rows)
        _write(root, "catalog/publication-ledger.json", ledger)
        self.base = _commit_all(root, "b0 ledger")
        return p0

    def _release_feeds(self, registry, source_commit):
        import build_catalog
        return build_catalog.build(registry, "release", source_commit,
                                   self.root, self.root, TRUST)

    # -- helpers used by both fixture modes --------------------------------

    def build_stage(self, *, script_extra_code=False, guide_body_forged=False,
                    guide_grant_change=False, script_dep_change=False,
                    script_runtime_file_change=False, delete_old_review=False,
                    unknown_path=False, deny_engine=False, drop_old_archive=False,
                    manifest_fact_lie=False):
        """Materialize a tracker-shaped stage root re-merged from the fixture."""
        stage = self.tmpdir / "stage"
        (stage / "apply" / "files").mkdir(parents=True, exist_ok=True)
        (stage / "candidates").mkdir(parents=True, exist_ok=True)
        (stage / "held").mkdir(parents=True, exist_ok=True)
        guide_new = guide_files("1.0.1")
        if guide_body_forged:
            guide_new["SKILL.md"] = _skill_md(GUIDE_ID, "FORGED body not in any upstream.")
        if guide_grant_change:
            guide_new["floe.json"] = _manifest(GUIDE_ID, "1.0.1",
                                               ["workspace.read", "workspace.write",
                                                "network"], [], ["ios"], "none")
        script_new = script_files("1.0.1", extra_code=script_extra_code)
        if script_dep_change:
            m = json.loads(script_new["floe.json"])
            m["pythonPackages"] = m["pythonPackages"][:1]
            script_new["floe.json"] = hubcore.encoded(m)
        if script_runtime_file_change:
            script_new["scripts/solve.py"] = b"print('changed runtime byte')\n"
        new_registry = copy.deepcopy(self.registry_base)
        guide_row = _row(new_registry, GUIDE_ID)
        script_row = _row(new_registry, SCRIPT_ID)
        guide_row["versionTarget"] = "1.0.1"
        guide_row["upstream"] = dict(guide_row["upstream"], commit=GUIDE_NEW,
                                     retrievedAt=TODAY)
        script_row["versionTarget"] = "1.0.1"
        script_row["upstream"] = dict(script_row["upstream"], commit=SCRIPT_NEW,
                                      retrievedAt=TODAY)
        for row in new_registry["skills"]:
            if row is guide_row or row is script_row:
                continue
            up = row.get("upstream")
            if up and up["repository"].endswith(GUIDE_REPO):
                row["upstream"] = dict(up, commit=GUIDE_NEW, retrievedAt=TODAY)
            elif up and up["repository"].endswith(SCRIPT_REPO):
                row["upstream"] = dict(up, commit=SCRIPT_NEW, retrievedAt=TODAY)
        new_pins = copy.deepcopy(self.pins_base)
        new_pins["repositories"][GUIDE_REPO] = GUIDE_NEW
        new_pins["repositories"][SCRIPT_REPO] = SCRIPT_NEW

        writes = {
            "sources/copywriting/SKILL.md": guide_new["SKILL.md"],
            "sources/copywriting/floe.json": guide_new["floe.json"],
            "sources/copywriting/references/NOTICE.md": guide_new["references/NOTICE.md"],
            "sources/sympy/SKILL.md": script_new["SKILL.md"],
            "sources/sympy/floe.json": script_new["floe.json"],
            "sources/sympy/scripts/solve.py": script_new["scripts/solve.py"],
            "sources/sympy/references/NOTICE.md": script_new["references/NOTICE.md"],
            "catalog/skills.json": hubcore.pretty(new_registry),
            "docs/UPSTREAM-PINS.json": hubcore.pretty(new_pins),
        }
        guide_rec, guide_zip = make_record(GUIDE_ID, "1.0.1", guide_new,
                                           stage="static-content-reviewed",
                                           execution={"os": None, "arch": "n/a",
                                                      "evidence": "unproven"},
                                           notes={"en": (
                                               "Automatic upstream guide-only update: "
                                               "prose/static content only; upstream "
                                               f"https://github.com/{GUIDE_REPO} at {GUIDE_NEW}; "
                                               "no script runtime, no execution claim. "
                                               "Verified by deterministic package gates, "
                                               "license/notice preservation, effective-pin "
                                               "agreement and a changed-path allowlist against "
                                               "the published version."),
                                               "zh-Hans": ("自动上游纯指南更新：仅正文与静态内容；上游 "
                                                             f"https://github.com/{GUIDE_REPO} 提交 "
                                                             f"{GUIDE_NEW}；无脚本运行时，不作任何执行声明。"
                                                             "已通过确定性包校验、许可与声明保留、有效固定提交一致"
                                                             "及相对已发布版本的变更路径白名单核验。")})
        script_fp = ap.execution_fingerprint({k: v for k, v in script_new.items()})
        prior_record = hubcore.encoded(json.loads(
            (self.root / "reviews" / SCRIPT_ID / "1.0.0.review.json").read_bytes()))
        script_rec, script_zip = make_record(
            SCRIPT_ID, "1.0.1", script_new, stage="guest-execution-qualified",
            execution={"os": "linux", "arch": "riscv64", "evidence": "guest-verified"},
            notes={"en": (
                "Automatic docs-only update of a previously guest-qualified scripted skill; "
                f"reuse of the existing signed proof only — prior sympy@1.0.0 contentDigest "
                f"{json.loads(prior_record)['contentDigest']} review "
                f"{hubcore.sha256_hex(prior_record)} publication pin {self.p0} execution "
                f"fingerprint {script_fp} instruction-code fingerprint "
                f"{ap.instruction_code_fingerprint({k: v for k, v in script_new.items()})}. "
                "No new guest execution was performed or claimed; execution and "
                "instruction-code fingerprints are recomputed byte-identical and the prior "
                "qualified review stays ledger-bound and signature-verified."),
                "zh-Hans": (
                    "自动纯文档更新（此前已通过真机客户机执行资格核验的脚本技能）：仅复用既有签名证明 — "
                    f"先前 sympy@1.0.0 内容摘要 {json.loads(prior_record)['contentDigest']} 审核 "
                    f"{hubcore.sha256_hex(prior_record)} 发布提交 {self.p0} 执行指纹与指令代码指纹"
                    f"{script_fp} 按字节重算完全一致，先前合格审核仍由账本与签名核验绑定。"
                    "本次未执行、也绝不声称任何新的客户机运行。")})
        writes[f"reviews/{GUIDE_ID}/1.0.1.review.json"] = guide_rec
        writes[f"reviews/{SCRIPT_ID}/1.0.1.review.json"] = script_rec
        if unknown_path:
            writes["docs/evil-note.md"] = b"injected\n"
        if deny_engine:
            writes["engines/impeccable/ENGINE-LOCK.json"] = b'{"engineVersion":"9.9.9"}\n'
        if delete_old_review:
            pass  # handled in candidate apply (not deletable there) — see negative test
        deletions = []
        if drop_old_archive:
            deletions.append(f"packages/{GUIDE_ID}/1.0.0/{GUIDE_ID}.zip")
        manifest_writes = []
        for rel, data in sorted(writes.items()):
            target = stage / "apply" / "files" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            manifest_writes.append({"path": rel, "sha256": hubcore.sha256_hex(data),
                                    "bytes": len(data)})
        if delete_old_review:
            manifest_writes = [w for w in manifest_writes]
            deletions.append(f"reviews/{GUIDE_ID}/1.0.0.review.json")
        apply_manifest = {"schemaVersion": 1, "today": TODAY,
                          "writes": manifest_writes, "deletions": deletions}
        (stage / "apply" / "manifest.json").write_bytes(
            hubcore.encoded(apply_manifest))
        for id_, version, tree, zip_bytes in (
                (GUIDE_ID, "1.0.1", guide_new, guide_zip),
                (SCRIPT_ID, "1.0.1", script_new, script_zip)):
            base = stage / "candidates" / id_ / version
            (base / "tree").mkdir(parents=True, exist_ok=True)
            for rel, data in tree.items():
                target = base / "tree" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            (base / "package.zip").write_bytes(zip_bytes)
            (base / "candidate.json").write_bytes(hubcore.encoded({
                "tier": 1 if id_ == GUIDE_ID else 2,
                "proposedVersion": version,
                "proposedReview": json.loads(writes[f"reviews/{id_}/1.0.1.review.json"]),
            }))
        facts = {
            "changedSkillIds": [GUIDE_ID, SCRIPT_ID],
            "bumpedVersions": {GUIDE_ID: {"from": "1.0.0", "to": "1.0.1"},
                               SCRIPT_ID: {"from": "1.0.0", "to": "1.0.1"}},
            "heldSkillIds": [], "holdReasons": [],
            "pinAdvances": {GUIDE_ID: {"from": GUIDE_OLD, "to": GUIDE_NEW},
                            SCRIPT_ID: {"from": SCRIPT_OLD, "to": SCRIPT_NEW}},
            "reviewStageCounts": {"static-content-reviewed": 1, "prior-proof-reuse": 1},
            "executableSubsetUnchanged": {GUIDE_ID: True, SCRIPT_ID: True},
        }
        if manifest_fact_lie:
            facts["reviewStageCounts"] = {"static-content-reviewed": 0,
                                          "prior-proof-reuse": 0}
        (stage / "staging-manifest.json").write_bytes(hubcore.encoded({
            "reportKind": "floe-skill-hub-upstream-stage", "reportVersion": 1,
            "today": TODAY, "candidateFacts": facts}))
        return stage

    # -- git helpers ------------------------------------------------------

    def apply_s(self, stage):
        payload = self.tmpdir / "s-payload"
        ap.build_candidate_payload(self.root, self.base, stage, payload, today=TODAY)
        wt = self.tmpdir / "s-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(wt), str(self.base))
        ap.apply_payload(payload, wt)
        _git(wt, "config", "user.name", "floe-auto-fixture")
        _git(wt, "config", "user.email", "fixture@invalid")
        return wt, _commit_all(wt, "auto-stage S")

    def commit_x(self, wt, s_sha, request, relay):
        xp = self.tmpdir / "x-payload"
        ap.build_x_payload(self.root, self.base, s_sha, request, relay, xp)
        ap.apply_payload(xp, wt)
        return _commit_all(wt, "auto-catalog: X")

    def make_request(self, mode, source_commit):
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        return ap.build_request(mode, source_commit, self.base, policy)

    def run_signer(self, mode, data_sha, out_dir, *, published_y=None):
        data = self.tmpdir / f"data-{mode}"
        if data.exists():
            shutil.rmtree(data)
        data.mkdir()
        _git(data, "init", "-q")
        _git(data, "remote", "add", "origin", OFFICIAL_ORIGIN)
        _git(data, "-c", "gc.auto=0", "fetch", "--depth", "1", "--no-tags",
             str(self.root), data_sha)
        _git(data, "-c", "core.hooksPath=/nonexistent", "checkout", "--quiet",
             "--detach", "FETCH_HEAD")
        tooling = self.tmpdir / "tooling"
        if not tooling.exists():
            tooling.mkdir()
            _git(tooling, "init", "-q")
            _git(tooling, "remote", "add", "origin", OFFICIAL_ORIGIN)
            _git(tooling, "-c", "gc.auto=0", "fetch", "--no-tags", str(self.root),
                 "+refs/heads/main:refs/floe/main")
            _git(tooling, "-c", "core.hooksPath=/nonexistent", "checkout", "--quiet",
                 "--detach", str(self.base))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   FLOE_SKILL_HUB_SIGNING_KEY=base64.b64encode(TEST_SEED).decode())
        argv = [sys.executable, str(tooling / "scripts" / "sign_publication.py"),
                "--mode", mode, "--source-commit", data_sha, "--data", str(data),
                "--tooling", str(tooling), "--out", str(out_dir)]
        if published_y:
            argv += ["--published-y", published_y]
        proc = subprocess.run(argv, capture_output=True, text=True, env=env,
                              cwd=str(self.tmpdir))
        return proc

    def build_relay(self, request_doc, signed_dir, name="relay"):
        relay = self.tmpdir / name
        ap.build_relay_payload(signed_dir, request_doc, relay,
                               info={"runId": "1", "today": TODAY})
        return relay


class TestDeriveAndStageBuild(HubFixture):
    def test_positive_two_candidate_minimal_s(self):
        stage = self.build_stage()
        payload = ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertEqual(payload["appliedSkillIds"], [GUIDE_ID, SCRIPT_ID])
        self.assertEqual(payload["reviewStageCounts"],
                         {"static-content-reviewed": 1, "prior-proof-reuse": 1})
        for rel in (f"packages/{GUIDE_ID}/1.0.1/{GUIDE_ID}.zip",
                    f"android/packages/{GUIDE_ID}/1.0.1/{GUIDE_ID}.zip",
                    f"packages/{SCRIPT_ID}/1.0.1/{SCRIPT_ID}.zip",
                    f"reviews/{GUIDE_ID}/1.0.1.review.json",
                    f"reviews/{SCRIPT_ID}/1.0.1.review.json",
                    "catalog/skills.json", "docs/UPSTREAM-PINS.json"):
            self.assertIn(rel, payload["writes"])
        # minimal S prunes the old pairs but keeps their restored-in-X intent
        self.assertIn(f"reviews/{GUIDE_ID}/1.0.0.review.json", payload["deletions"])
        self.assertIn(f"reviews/{GUIDE_ID}/1.0.0.review.json.sig", payload["deletions"])
        self.assertNotIn(f"reviews/{GUIDE_ID}/1.0.1.review.json", payload["deletions"])

    def test_forged_guide_body_refused_vs_fresh_rederivation(self):
        # The injected FRESH stage is the trusted re-merge; the candidate
        # sources/bytes are forged but self-consistent (valid pin, valid
        # ZIP/review over the forged body).
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        # forge the committed candidate: rewrite the guide body + a matching
        # self-consistent record, keep everything else
        _write(wt, f"sources/{GUIDE_ID}/SKILL.md", _skill_md(GUIDE_ID, "FORGED prose"))
        forged_files = guide_files("1.0.1")
        forged_files["SKILL.md"] = _skill_md(GUIDE_ID, "FORGED prose")
        rec, zip_bytes = make_record(
            GUIDE_ID, "1.0.1", forged_files, stage="static-content-reviewed",
            execution={"os": None, "arch": "n/a", "evidence": "unproven"},
            notes={"en": "forged but self-consistent", "zh-Hans": "伪造但自洽"})
        _write(wt, f"reviews/{GUIDE_ID}/1.0.1.review.json", rec)
        for prefix in ("", "android/"):
            _write(wt, f"{prefix}packages/{GUIDE_ID}/1.0.1/{GUIDE_ID}.zip", zip_bytes)
        forged = _commit_all(wt, "forged candidate")
        self.assertNotEqual(forged, s_sha)
        request_bytes, request = self.make_request("reviews", forged)
        payload = ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        manifest = self._manifest_for(request, payload, stage)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_candidate(self.root, request, manifest,
                                (self.root / "catalog" / "upstream-update-policy.json")
                                .read_bytes(), fresh_stage_root=stage)
        self.assertIn("byte-for-byte", str(raised.exception))

    def _manifest_for(self, request, payload, stage, x=None):
        manifest_extra = ap._manifest_from_payload(payload, "1")
        manifest = {"schemaVersion": ap.SCHEMA_VERSION, "pipeline": ap.PUBLICATION_NAME,
                    "mode": request["mode"],
                    "basePublication": request["basePublication"],
                    "sourceCommit": request["sourceCommit"],
                    "stagingRef": "auto/candidate-test-1",
                    "requestId": request["requestId"], "request": request,
                    "policySha256": request["policySha256"], "createdAtUTC": TODAY,
                    **manifest_extra}
        if x is not None:
            manifest["X"] = x
        return manifest

    def test_grant_change_refused(self):
        stage = self.build_stage(guide_grant_change=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("grants", str(raised.exception).lower())

    def test_dependency_change_refused_for_scripted(self):
        stage = self.build_stage(script_dep_change=True)
        with self.assertRaises(ap.PublicationError):
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)

    def test_scripted_runtime_byte_change_refused(self):
        stage = self.build_stage(script_runtime_file_change=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("fingerprint", str(raised.exception))

    def test_unknown_apply_path_refused(self):
        stage = self.build_stage(unknown_path=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("unclassified", str(raised.exception))

    def test_engine_path_in_apply_refused(self):
        stage = self.build_stage(deny_engine=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("trust-critical", str(raised.exception))

    def test_apply_deletion_of_published_archive_refused(self):
        stage = self.build_stage(drop_old_archive=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("non-DATA", str(raised.exception))

    def test_manifest_counts_never_authority(self):
        stage = self.build_stage(manifest_fact_lie=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("reviewStageCounts", str(raised.exception))

    def test_self_consistent_forged_record_digests_refused(self):
        # a record claiming wrong contentDigest/packageSha256 (but valid
        # structure, machine reviewer and approval) must not stage
        stage = self.build_stage()
        manifest_writes = json.loads((stage / "apply" / "manifest.json").read_bytes())
        rec_rel = f"reviews/{GUIDE_ID}/1.0.1.review.json"
        rec_path = stage / "apply" / "files" / rec_rel
        doc = json.loads(rec_path.read_bytes())
        doc["contentDigest"] = "f" * 64
        forged = hubcore.encoded(doc)
        rec_path.write_bytes(forged)
        for w in manifest_writes["writes"]:
            if w["path"] == rec_rel:
                w["sha256"] = hubcore.sha256_hex(forged)
                w["bytes"] = len(forged)
        (stage / "apply" / "manifest.json").write_bytes(hubcore.encoded(manifest_writes))
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("digests", str(raised.exception))

    def test_injection_code_fence_change_scripted_refused(self):
        stage = self.build_stage(script_extra_code=True)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        self.assertIn("fingerprint", str(raised.exception))


class TestE2ETwoPhase(HubFixture):
    def test_full_flow_reviews_to_cas_and_idempotency(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        request_bytes, request = ap.build_request("reviews", s_sha, self.base, policy)
        payload = ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        manifest = TestDeriveAndStageBuild._manifest_for(self, request, payload, stage)
        verdict = ap.verify_candidate(self.root, request, manifest, policy,
                                      fresh_stage_root=stage)
        self.assertEqual(verdict["status"], "candidate-ok")

        # --- reviews signing through the UNCHANGED signer -------------------
        signed = self.tmpdir / "signed-reviews"
        proc = self.run_signer("reviews", s_sha, signed)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay = self.build_relay(request, signed)
        x_relay_verdict, _ = ap.relay_validate(relay, request, self.root, s_sha)
        self.assertEqual(x_relay_verdict["status"], "relay-ok")

        x_sha = self.commit_x(wt, s_sha, request, relay)
        _git(self.root, "update-ref", "refs/heads/auto/candidate-test", x_sha)
        # every historical pair restored byte-identically
        base_tree = ap.tree_at(self.root, self.base, "base")
        x_tree = ap.tree_at(self.root, x_sha, "X")
        for rel, entry in base_tree.items():
            if rel.startswith("reviews/"):
                self.assertEqual(x_tree.get(rel), entry, rel)
            if rel.startswith("packages/"):
                self.assertEqual(x_tree.get(rel), entry, rel)

        # --- catalog request + signing + feed reconstruction ----------------
        catalog_bytes, catalog_request = ap.build_request("catalog", x_sha, self.base,
                                                          policy)
        catalog_manifest = TestDeriveAndStageBuild._manifest_for(
            self, catalog_request, payload, stage, x=x_sha)
        catalog_manifest["mode"] = "catalog"
        v2 = ap.verify_candidate(self.root, catalog_request, catalog_manifest, policy,
                                 fresh_stage_root=stage)
        self.assertEqual(v2["mode"], "catalog")
        signed_cat = self.tmpdir / "signed-catalog"
        proc = self.run_signer("catalog", x_sha, signed_cat, published_y=self.base)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        x_wt = self.tmpdir / "x-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(x_wt), x_sha)
        feeds = ap.rebuild_feeds(x_wt, x_sha, trust=TRUST)
        relay_cat = ap.build_relay_payload(signed_cat, catalog_request,
                                           self.tmpdir / "relay-cat",
                                           info={"runId": "2", "today": TODAY})
        cat_verdict, _ = ap.relay_validate(self.tmpdir / "relay-cat", catalog_request,
                                           self.root, x_sha, feeds=feeds)
        self.assertEqual(cat_verdict["status"], "relay-ok")

        # Y + H
        y_payload_dir = self.tmpdir / "y-payload"
        ap.build_y_payload(catalog_request, self.tmpdir / "relay-cat", self.root,
                           feeds, y_payload_dir)
        ap.apply_payload(y_payload_dir, x_wt)
        y_sha = _commit_all(x_wt, "auto-publish: Y")
        h_payload = self.tmpdir / "h-payload"
        ap.build_h_payload(self.root, self.base, y_sha, h_payload)
        ap.apply_payload(h_payload, x_wt)
        h_sha = _commit_all(x_wt, "auto-publish: H ledger append")
        chain = ap.verify_publication_diffs(self.root, self.base, x_sha, y_sha, h_sha)
        self.assertEqual(chain["status"], "publication-diffs-ok")
        ledger = json.loads(ap.blob_at(self.root, h_sha, ap.LEDGER_REL, "ledger"))
        self.assertEqual(ledger["publications"][-2]["publication"], y_sha)

        # --- mocked exact CAS + idempotent resume ----------------------------
        state = {"schemaVersion": 1, "processedRequestIds": []}
        calls = []
        reads = iter([self.base, h_sha])

        def fake_transport(query, variables):
            kind = "mutate" if "mutation" in query else "query"
            calls.append((kind, query, variables))
            if kind == "mutate":
                return 200, {"data": {"updateRefs": {
                    "clientMutationId": ap.CAS_MUTATION_ID}}}
            return 200, {"data": {"repository": {
                "id": "REPONODEID", "ref": {"target": {"oid": next(reads)}}}}}

        result = ap.cas_publish(self.base, h_sha, transport=fake_transport)
        self.assertEqual(result["status"], "cas-published")
        # ACTUAL valid schema inputs (live-proven probe shape, not the
        # previously invented refPrefix/refId/oid wire):
        fetch_call = [c for c in calls if c[0] == "query"][0]
        self.assertIn("repository(owner: $owner, name: $name)", fetch_call[1])
        self.assertIn("ref(qualifiedName: $qualifiedName)", fetch_call[1])
        self.assertNotIn("refPrefix", fetch_call[1])
        self.assertEqual(fetch_call[2], {"owner": "JiangNanGenius",
                                         "name": "floe-skill-hub",
                                         "qualifiedName": "refs/heads/main"})
        mutation = [c for c in calls if c[0] == "mutate"][0]
        self.assertIn("UpdateRefsInput!", mutation[1])
        self.assertIn("updateRefs(input: $input)", mutation[1])
        self.assertEqual(mutation[2], {"input": {
            "clientMutationId": ap.CAS_MUTATION_ID,
            "repositoryId": "REPONODEID",
            "refUpdates": [{"name": "refs/heads/main", "beforeOid": self.base,
                            "afterOid": h_sha, "force": False}]}})
        self.assertEqual(
            [c for c in calls if c[0] == "query"][-1][2],
            {"owner": "JiangNanGenius", "name": "floe-skill-hub",
             "qualifiedName": "refs/heads/main"})
        # stale beforeOid refused: second attempt when live already moved
        def stale_transport(query, variables):
            if "mutation" in query:
                return 200, {"errors": [{"message": "Something went while executing"}]}
            return 200, {"data": {"repository": {
                "id": "REPONODEID", "ref": {"target": {"oid": "9" * 40}}}}}
        with self.assertRaises(ap.PublicationError):
            ap.cas_publish(self.base, h_sha, transport=stale_transport)
        # already-published no-op
        def done_transport(query, variables):
            return 200, {"data": {"repository": {
                "id": "REPONODEID", "ref": {"target": {"oid": h_sha}}}}}
        again = ap.cas_publish(self.base, h_sha, transport=done_transport)
        self.assertEqual(again["status"], "cas-already-published")

        # mark processed + replay refusal through the state helpers
        marked = ap.mark_processed(state, catalog_request["requestId"],
                                   extra={"lastPublicationH": h_sha,
                                          "lastPublicationY": y_sha})
        self.assertTrue(ap.already_processed(marked, catalog_request["requestId"]))

    def test_lost_run_resumes_from_committed_x(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _r, request = ap.build_request("reviews", s_sha, self.base, policy)
        proc = self.run_signer("reviews", s_sha, self.tmpdir / "signed-r2")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay = self.build_relay(request, self.tmpdir / "signed-r2", name="relay-r2")
        x_sha = self.commit_x(wt, s_sha, request, relay)
        # simulate a dropped run after X: rebuild catalog request and continue
        _b, catalog_request = ap.build_request("catalog", x_sha, self.base, policy)
        payload = ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        manifest = TestDeriveAndStageBuild._manifest_for(
            self, catalog_request, payload, stage, x=x_sha)
        manifest["mode"] = "catalog"
        verdict = ap.verify_candidate(self.root, catalog_request, manifest, policy,
                                      fresh_stage_root=stage)
        self.assertEqual(verdict["status"], "candidate-ok")

    def test_wrong_key_relay_refused(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _b, request = ap.build_request("reviews", s_sha, self.base, policy)
        proc = self.run_signer("reviews", s_sha, self.tmpdir / "signed-wk")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        signed = self.tmpdir / "signed-wk"
        # re-sign one record with the FOREIGN key but keep the official keyID
        victim = signed / f"reviews/{GUIDE_ID}/1.0.1.review.json"
        envelope = hubcore.sign_envelope(victim.read_bytes(), FOREIGN_KEY,
                                         hubcore.PRODUCTION_KEY_ID)
        (victim.with_name(victim.name + ".sig")).write_bytes(envelope)
        ap.build_relay_payload(signed, request, self.tmpdir / "relay-wk",
                               info={"runId": "1", "today": TODAY})
        with self.assertRaises(ap.PublicationError):
            ap.relay_validate(self.tmpdir / "relay-wk", request, self.root, s_sha)

    def test_stale_base_refused(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _b, request = ap.build_request("reviews", s_sha, self.base, policy)
        payload = ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        manifest = TestDeriveAndStageBuild._manifest_for(self, request, payload, stage)
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_candidate(self.root, request, manifest, policy,
                                fresh_stage_root=stage, expected_base="9" * 40)
        self.assertIn("does not equal the independently resolved live main",
                      str(raised.exception))

    def test_unknown_relay_path_refused(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _b, request = ap.build_request("reviews", s_sha, self.base, policy)
        proc = self.run_signer("reviews", s_sha, self.tmpdir / "signed-up")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay = self.build_relay(request, self.tmpdir / "signed-up", name="relay-up")
        _write(relay, f"signing-relay/requests/{request['requestId']}/packages/evil.zip",
               b"PK\x03\x04evil")
        with self.assertRaises(ap.PublicationError):
            ap.relay_validate(relay, request, self.root, s_sha)

    def test_catalog_x_missing_old_review_pair_refused(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _b, request = ap.build_request("reviews", s_sha, self.base, policy)
        proc = self.run_signer("reviews", s_sha, self.tmpdir / "signed-or")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay = self.build_relay(request, self.tmpdir / "signed-or", name="relay-or")
        _r2, catalog_request = ap.build_request("catalog", s_sha, self.base, policy)
        payload = ap.derive_expected_apply_set(self.root, self.base, stage, today=TODAY)
        manifest = TestDeriveAndStageBuild._manifest_for(
            self, catalog_request, payload, stage, x=s_sha)
        manifest["mode"] = "catalog"
        # s_sha without restored historical pairs is a broken catalog candidate
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_candidate(self.root, catalog_request, manifest, policy,
                                fresh_stage_root=stage)
        self.assertIn("historical", str(raised.exception))


class TestControlPlannerAndState(unittest.TestCase):
    def _request(self):
        policy = b"{}"
        return ap.build_request("reviews", "a" * 40, "b" * 40, policy)

    def test_busy_checkpoint(self):
        _b, request = self._request()
        tmp = tempfile.TemporaryDirectory()
        try:
            payload = pathlib.Path(tmp.name)
            (payload / ap.CONTROL_REQUEST_FILE).write_bytes(_b)
            (payload / ap.CONTROL_CHANGES_FILE).write_bytes(hubcore.encoded({
                "schemaVersion": 1,
                "mirror": [ap.CONTROL_REQUEST_FILE, ap.CONTROL_MANIFEST_FILE,
                           ap.CONTROL_STATE_FILE],
                "appendArchive": [ap.CONTROL_ARCHIVE_PREFIX + request["requestId"] + "/"]}))
            plan = ap.plan_control_update(payload, {"schemaVersion": 1}, request,
                                          "b" * 40, TODAY)
            self.assertEqual(plan["action"], "busy-checkpoint")
        finally:
            tmp.cleanup()

    def test_supersede_stale(self):
        _b, request = self._request()
        plan = ap.plan_control_update(None, {"schemaVersion": 1}, request,
                                      "c" * 40, TODAY)
        # no payload dir: idle/apply without an incoming request
        self.assertIn(plan["action"], ("idle", "apply"))

    def test_prune_bounded(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            rdir = pathlib.Path(tmp.name) / "requests"
            for i in range(ap.PROCESSED_IDS_CAP + 10):
                d = rdir / f"{i:064x}"[:64]
                d.mkdir(parents=True)
                (d / "request.json").write_bytes(b"{}")
            state = {"processedRequestIds": []}
            removed = ap.prune_request_history(rdir, state)
            self.assertTrue(removed)
            self.assertLessEqual(len([p for p in rdir.iterdir() if p.is_dir()]),
                                 ap.REQUEST_HISTORY_KEEP)
        finally:
            tmp.cleanup()

    def test_payload_state_merges_and_history_survives(self):
        """Root regression: real emit -> plan -> write -> read. The freshly
        emitted openRequestId/pipelineStage/holdReasons must land in the
        planned state, processed history must be preserved, and a busy
        checkpoint must never replace in-flight state."""
        tmp = tempfile.TemporaryDirectory()
        try:
            tmpdir = pathlib.Path(tmp.name)
            policy = b'{"policyId":"fixture"}'
            _rb, request = ap.build_request("reviews", "a" * 40, "b" * 40, policy)
            payload_dir = tmpdir / "control"
            result = ap.control_payload(
                payload_dir, base_commit="b" * 40, candidate_commit="a" * 40,
                mode="reviews", staging_ref="auto/candidate-x",
                manifest_extra={"changedSkillIds": ["fixture"],
                                "bumpedVersions": {}, "holdReasons": [
                                    {"id": "held-one", "code": "held-conflict",
                                     "detail": "d", "repair": "r"}],
                                "integrationGaps": []},
                today=TODAY, policy_bytes=policy,
                control_state={"schemaVersion": 1,
                               "processedRequestIds": ["f" * 64]})
            self.assertEqual(result["state"]["pipelineStage"], "reviews-requested")
            # current control branch state carries prior history + an idle root
            current = {"schemaVersion": 1, "processedRequestIds": ["e" * 64],
                       "pipelineStage": "published", "openRequestId": None}
            plan = ap.plan_control_update(payload_dir, current, None, "b" * 40,
                                          TODAY)
            self.assertEqual(plan["action"], "apply")
            out = tmpdir / "planned"
            ap.write_control_plan_output(out, plan)
            written = json.loads((out / "state.json").read_bytes())
            self.assertEqual(written["openRequestId"], request["requestId"])
            self.assertEqual(written["pipelineStage"], "reviews-requested")
            self.assertIn("e" * 64, written["processedRequestIds"])
            self.assertEqual(written["holdReasons"],
                             [{"id": "held-one", "code": "held-conflict",
                               "detail": "d", "repair": "r"}])
            # request/manifest mirrored for the workflow copy step
            self.assertTrue((out / "request.json").is_file())
            self.assertTrue((out / "candidate-manifest.json").is_file())
            # busy: same live base with an open in-flight request keeps state
            inflight = dict(written)
            busy = ap.plan_control_update(payload_dir, inflight, request,
                                          "b" * 40, TODAY)
            self.assertEqual(busy["action"], "busy-checkpoint")
            self.assertEqual(busy["state"]["openRequestId"], request["requestId"])
            self.assertEqual(busy["state"]["pipelineStage"], "reviews-requested")
            self.assertEqual(busy["state"].get("holdReasons"),
                             written.get("holdReasons"))
            self.assertIn("e" * 64, busy["state"]["processedRequestIds"])
        finally:
            tmp.cleanup()

    def test_state_caps(self):
        state = {"processedRequestIds": [str(i) for i in range(100)]}
        merged = ap._state_update(state, {})
        self.assertLessEqual(len(merged["processedRequestIds"]), ap.PROCESSED_IDS_CAP)


class TestUpstreamAncestryProver(unittest.TestCase):
    """Real local-git ancestry proofs including the shallow-cache trap."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-ancestry-")
        self.tmpdir = pathlib.Path(self.tmp.name)
        self.up = self.tmpdir / "upstream"
        self.up.mkdir()
        _git(self.up, "init", "-q", "-b", "main")
        self.cache = self.tmpdir / "cache"
        self.commits = {}
        for name, body in (("old", b"v1\n"), ("new", b"v2\n"), ("later", b"v3\n")):
            _write(self.up, "skills/guide/SKILL.md", body)
            self.commits[name] = _commit_all(self.up, name)
        self.url = "file://" + str(self.up)

    def tearDown(self):
        self.tmp.cleanup()

    def test_legit_ancestry_passes(self):
        proof = ap.prove_upstream_ancestry(self.cache, self.url,
                                           self.commits["old"],
                                           self.commits["new"])
        self.assertEqual(proof["currentHead"], self.commits["later"])
        self.assertTrue(proof["oldAncestorNew"])
        self.assertTrue(proof["newAncestorCurrentHead"])

    def test_depth1_poisoned_cache_still_proves(self):
        # simulate the tracker's --depth 1 blobless cache reuse: a shallow
        # clone of only NEW must NOT false-negative the legitimate update
        poisoned = self.cache / ("repo-" + hubcore.sha256_hex(
            self.url.encode())[:16])
        poisoned.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none",
                        self.url, str(poisoned)], check=True)
        self.assertEqual(_git(poisoned, "rev-parse", "--is-shallow-repository"),
                         "true")
        proof = ap.prove_upstream_ancestry(self.cache, self.url,
                                           self.commits["old"],
                                           self.commits["new"])
        self.assertTrue(proof["unshallowed"])
        self.assertEqual(proof["currentHead"], self.commits["later"])

    def test_old_rollback_refused(self):
        with self.assertRaises(ap.PublicationError) as raised:
            ap.prove_upstream_ancestry(self.cache, self.url,
                                       self.commits["new"], self.commits["old"])
        self.assertIn("not a descendant", str(raised.exception))

    def test_rewritten_head_unreachable_refused(self):
        rewritten = self.tmpdir / "rewritten"
        rewritten.mkdir()
        _git(rewritten, "init", "-q", "-b", "main")
        _write(rewritten, "skills/guide/SKILL.md", b"rewritten root\n")
        _commit_all(rewritten, "rewrite")
        with self.assertRaises(ap.PublicationError) as raised:
            ap.prove_upstream_ancestry(self.cache,
                                       "file://" + str(rewritten),
                                       self.commits["old"], self.commits["new"])
        self.assertIn("unreachable", str(raised.exception))

    def test_unknown_commit_refused_not_misreported(self):
        with self.assertRaises(ap.PublicationError):
            ap.prove_upstream_ancestry(self.cache, self.url,
                                       self.commits["old"], "e" * 40)

    def test_credential_url_refused(self):
        with self.assertRaises(ap.PublicationError):
            ap.prove_upstream_ancestry(self.cache,
                                       "https://user@github.com/x/y",
                                       self.commits["old"], self.commits["new"])


class TestProducerIntegration(unittest.TestCase):
    """Positive producer->consumer acceptance against the ACTUAL frozen
    tracker (upstream_updates.run_check/run_plan/run_stage +
    FixtureUpstreamSource from the tracker's own fixtures), then this lane's
    stage-build/verify on the producer's real stage output."""

    EXPECT = (4, 0, 4, 1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-producer-")
        self.tmpdir = pathlib.Path(self.tmp.name)
        sys.path.insert(0, str(HERE))
        import test_upstream_updates as tu
        import upstream_updates as uu
        self.tu, self.uu = tu, uu
        self.root, self.source = tu.build_fixture_world(str(self.tmpdir))
        _write(self.root, "public-key.json",
               hubcore.encoded({"keyID": hubcore.PRODUCTION_KEY_ID,
                                "publicKey": TEST_PUB}))
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "remote", "add", "origin", OFFICIAL_ORIGIN)
        _write(self.root, ".gitignore", b"__pycache__/\n")
        self.base = _commit_all(self.root, "producer world base B")
        self.inputs = uu.load_inputs(self.root, expect_counts=self.EXPECT)
        self.stage = self.tmpdir / "producer-stage"
        check = uu.run_check(self.root, self.inputs, self.source, TODAY)
        plan = uu.run_plan(self.root, self.inputs, self.source, TODAY,
                           check_report=check)
        uu.run_stage(self.root, self.inputs, self.source, plan, self.stage)
        self.policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def _commit_candidate(self):
        payload_dir = self.tmpdir / "producer-payload"
        payload = ap.derive_expected_apply_set(
            self.root, self.base, self.stage, today=TODAY,
            expect_counts=self.EXPECT)
        wt = self.tmpdir / "producer-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(wt), self.base)
        ap.apply_payload(payload_dir if False else self._write_payload(payload), wt)
        s_sha = _commit_all(wt, "producer candidate S")
        return payload, wt, s_sha

    def _write_payload(self, payload):
        out = self.tmpdir / "producer-payload"
        out.mkdir(parents=True, exist_ok=True)
        for rel, data in sorted(payload["writes"].items()):
            ap.write_payload_file(out / "snapshot", rel, data)
        (out / "changes.json").write_bytes(hubcore.pretty(
            {"schemaVersion": 1, **{k: v for k, v in payload.items()
                                    if k != "writes"}}))
        return out

    def test_producer_stage_builds_and_verifies(self):
        payload, wt, s_sha = self._commit_candidate()
        self.assertEqual(payload["appliedSkillIds"], ["fixture-guide"])
        request_bytes, request = ap.build_request("reviews", s_sha, self.base,
                                                  self.policy)
        manifest_extra = ap._manifest_from_payload(payload, "1")
        manifest = {"schemaVersion": ap.SCHEMA_VERSION, "pipeline": ap.PUBLICATION_NAME,
                    "mode": "reviews", "basePublication": self.base,
                    "sourceCommit": s_sha, "stagingRef": "auto/candidate-producer-1",
                    "requestId": request["requestId"], "request": request,
                    "policySha256": request["policySha256"], "createdAtUTC": TODAY,
                    **manifest_extra}
        verdict = ap.verify_candidate(self.root, request, manifest, self.policy,
                                      fresh_stage_root=self.stage,
                                      expect_counts=self.EXPECT)
        self.assertEqual(verdict["status"], "candidate-ok")
        self.assertEqual(verdict["reviewStageCounts"],
                         {"static-content-reviewed": 1, "prior-proof-reuse": 0})

    def test_rederive_pins_selected_new_and_survives_head_advance(self):
        payload, wt, s_sha = self._commit_candidate()
        # 1) rederive against the candidate's OWN selected NEW commit
        fresh1 = self.tmpdir / "fresh-stage-1"
        facts = ap.rederive_candidate(
            self.root, self.base, s_sha, today=TODAY, stage_root=fresh1,
            source=self.source, prove=lambda url, old, new: True,
            expect_counts=self.EXPECT)
        self.assertEqual(facts["targetIds"], ["fixture-guide"])
        request_bytes, request = ap.build_request("reviews", s_sha, self.base,
                                                  self.policy)
        manifest_extra = ap._manifest_from_payload(payload, "1")
        manifest = {"schemaVersion": ap.SCHEMA_VERSION, "pipeline": ap.PUBLICATION_NAME,
                    "mode": "reviews", "basePublication": self.base,
                    "sourceCommit": s_sha, "stagingRef": "auto/candidate-producer-1",
                    "requestId": request["requestId"], "request": request,
                    "policySha256": request["policySha256"], "createdAtUTC": TODAY,
                    **manifest_extra}
        verdict = ap.verify_candidate(self.root, request, manifest, self.policy,
                                      fresh_stage_root=fresh1,
                                      expect_counts=self.EXPECT)
        self.assertEqual(verdict["status"], "candidate-ok")
        # 2) upstream HEAD advances with an UNRELATED commit after staging:
        #    the pinned NEW stays authoritative and verification still passes
        repo = self.source.repos[self.tu.FIXTURE_REPO]
        head_files = dict(repo["commits"][self.tu.HEAD]["files"])
        head_files["UNRELATED/new-doc.md"] = b"unrelated later upstream work\n"
        later = "d" * 40
        repo["commits"][later] = self.tu.commit(head_files)
        repo["head"] = (later, "refs/heads/main")
        fresh2 = self.tmpdir / "fresh-stage-2"
        facts2 = ap.rederive_candidate(
            self.root, self.base, s_sha, today=TODAY, stage_root=fresh2,
            source=self.source, prove=lambda url, old, new: True,
            expect_counts=self.EXPECT)
        self.assertEqual(facts2["repositories"][self.tu.FIXTURE_REPO]["new"],
                         self.tu.HEAD)
        verdict2 = ap.verify_candidate(self.root, request, manifest, self.policy,
                                       fresh_stage_root=fresh2,
                                       expect_counts=self.EXPECT)
        self.assertEqual(verdict2["status"], "candidate-ok")

    def test_rederive_refuses_unproven_ancestry(self):
        payload, wt, s_sha = self._commit_candidate()
        with self.assertRaises(ap.PublicationError):
            ap.rederive_candidate(self.root, self.base, s_sha, today=TODAY,
                                  stage_root=self.tmpdir / "fresh-stage-3",
                                  source=self.source,
                                  prove=lambda url, old, new: False,
                                  expect_counts=self.EXPECT)

    def test_rederive_honors_declared_non_head_tracked_ref(self):
        # policy repositories are keyed by the canonical FULL https URL (the
        # loader validates that shape); a short owner/name lookup silently
        # missed and degraded every declared trackedRef to HEAD. The ancestry
        # prover must receive the committed policy's real trackedRef.
        _payload, _wt, s_sha = self._commit_candidate()
        policy_doc = json.loads(self.policy)
        policy_doc["repositories"][self.tu.FIXTURE_REPO]["trackedRef"] = \
            "refs/heads/quality"
        _write(self.root, "catalog/upstream-update-policy.json",
               hubcore.encoded(policy_doc))
        base2 = _commit_all(self.root,
                            "base with declared non-HEAD trackedRef")
        captured = []
        real = ap.prove_upstream_ancestry

        def spy(cache, url, old, new, *, tracked_ref="HEAD"):
            captured.append((url, old, new, tracked_ref))
            return {"url": url, "old": old, "new": new, "currentHead": new,
                    "oldAncestorNew": True, "newAncestorCurrentHead": True,
                    "unshallowed": False}
        ap.prove_upstream_ancestry = spy
        try:
            facts = ap.rederive_candidate(self.root, base2, s_sha, today=TODAY,
                                          stage_root=self.tmpdir / "ref-stage",
                                          source=self.source, prove=None,
                                          expect_counts=self.EXPECT)
        finally:
            ap.prove_upstream_ancestry = real
        self.assertEqual(facts["targetIds"], ["fixture-guide"])
        self.assertIn((self.tu.FIXTURE_REPO, self.tu.PIN, self.tu.HEAD,
                       "refs/heads/quality"), captured)

    def test_rederive_cli_has_no_remote_or_only_overrides(self):
        import argparse as _argparse
        parser = ap.build_parser()
        sub = None
        for action in parser._actions:
            if isinstance(action, _argparse._SubParsersAction):
                sub = action.choices["rederive-candidate"]
        self.assertIsNotNone(sub)
        opts = " ".join(sorted({o for a in sub._actions for o in a.option_strings}))
        for banned in ("--url", "--origin", "--remote", "--only", "--command",
                       "--ref", "--repository", "--source"):
            self.assertNotIn(banned, opts)


class TestCrashRecovery(HubFixture):
    """The four contract crash fixtures against the committed chain."""

    def _flow(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _rb, request = ap.build_request("reviews", s_sha, self.base, policy)
        payload = ap.derive_expected_apply_set(self.root, self.base, stage,
                                               today=TODAY)
        manifest = TestDeriveAndStageBuild._manifest_for(self, request, payload,
                                                         stage)
        proc = self.run_signer("reviews", s_sha, self.tmpdir / "signed-cr")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay = self.build_relay(request, self.tmpdir / "signed-cr",
                                 name="relay-cr")
        x_sha = self.commit_x(wt, s_sha, request, relay)
        _cb, catalog_request = ap.build_request("catalog", x_sha, self.base,
                                                policy)
        catalog_manifest = TestDeriveAndStageBuild._manifest_for(
            self, catalog_request, payload, stage, x=x_sha)
        catalog_manifest["mode"] = "catalog"
        proc = self.run_signer("catalog", x_sha, self.tmpdir / "signed-cr-cat",
                               published_y=self.base)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay_cat_dir = self.tmpdir / "relay-cr-cat"
        ap.build_relay_payload(self.tmpdir / "signed-cr-cat", catalog_request,
                               relay_cat_dir, info={"runId": "9", "today": TODAY})
        x_wt = self.tmpdir / "x-wt-cr"
        _git(self.root, "worktree", "add", "--detach", "-q", str(x_wt), x_sha)
        feeds = ap.rebuild_feeds(x_wt, x_sha, trust=TRUST)
        ap.build_y_payload(catalog_request, relay_cat_dir, self.root, feeds,
                           self.tmpdir / "y-cr")
        ap.apply_payload(self.tmpdir / "y-cr", x_wt)
        y_sha = _commit_all(x_wt, "Y")
        ap.build_h_payload(self.root, self.base, y_sha, self.tmpdir / "h-cr")
        ap.apply_payload(self.tmpdir / "h-cr", x_wt)
        h_sha = _commit_all(x_wt, "H")
        return dict(stage=stage, policy=policy, s=s_sha, x=x_sha, y=y_sha,
                    h=h_sha, request=request, manifest=manifest,
                    catalog_request=catalog_request,
                    catalog_manifest=catalog_manifest,
                    relay=relay, relay_cat=relay_cat_dir, x_wt=x_wt, wt=wt)

    def test_reviews_tip_s_is_plain_advance(self):
        f = self._flow()
        plan = ap.recover_publish_plan(self.root, f["request"], f["manifest"],
                                       f["policy"], live_main=self.base,
                                       candidate_tip=f["s"],
                                       fresh_stage_root=f["stage"],
                                       relay_dir=f["relay"])
        self.assertEqual(plan["action"], "advance-from-request")

    def test_crash_after_x_push_before_control_write(self):
        f = self._flow()
        plan = ap.recover_publish_plan(self.root, f["request"], f["manifest"],
                                       f["policy"], live_main=self.base,
                                       candidate_tip=f["x"],
                                       fresh_stage_root=f["stage"],
                                       relay_dir=f["relay"])
        self.assertEqual(plan["action"], "reuse-x")
        self.assertEqual(plan["x"], f["x"])
        # and the reused tip passes the standard catalog verification, so the
        # catalog request can be emitted for the SAME committed X
        v = ap.verify_candidate(self.root, f["catalog_request"],
                                f["catalog_manifest"], f["policy"],
                                fresh_stage_root=f["stage"])
        self.assertEqual(v["status"], "candidate-ok")

    def test_forged_x_tip_refused(self):
        f = self._flow()
        forged_wt = self.tmpdir / "forged-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(forged_wt),
             f["x"])
        victim = forged_wt / "reviews" / GUIDE_ID / "1.0.0.review.json"
        doc = json.loads(victim.read_bytes())
        doc["notes"] = {"en": "tampered history", "zh-Hans": "篡改历史"}
        victim.write_bytes(hubcore.encoded(doc))
        forged_x = _commit_all(forged_wt, "forged X")
        with self.assertRaises(ap.PublicationError):
            ap.recover_publish_plan(self.root, f["request"], f["manifest"],
                                    f["policy"], live_main=self.base,
                                    candidate_tip=forged_x,
                                    fresh_stage_root=f["stage"],
                                    relay_dir=f["relay"])

    def test_crash_after_h_push_before_cas(self):
        f = self._flow()
        plan = ap.recover_publish_plan(self.root, f["catalog_request"],
                                       f["catalog_manifest"], f["policy"],
                                       live_main=self.base,
                                       candidate_tip=f["h"],
                                       fresh_stage_root=f["stage"],
                                       relay_dir=f["relay_cat"],
                                       x_root=f["x_wt"])
        self.assertEqual(plan["action"], "cas-existing-h")
        self.assertEqual(plan["h"], f["h"])
        self.assertEqual(plan["proof"]["chain"]["status"], "publication-diffs-ok")
        reads = iter([self.base, f["h"]])

        def transport(query, variables):
            if "mutation" in query:
                self.assertEqual(variables["input"]["refUpdates"],
                                 [{"name": "refs/heads/main",
                                   "beforeOid": self.base,
                                   "afterOid": plan["h"], "force": False}])
                return 200, {"data": {"updateRefs": {
                    "clientMutationId": ap.CAS_MUTATION_ID}}}
            return 200, {"data": {"repository": {
                "id": "N", "ref": {"target": {"oid": next(reads)}}}}}
        result = ap.cas_publish(self.base, plan["h"], transport=transport)
        self.assertEqual(result["status"], "cas-published")

    def test_crash_after_cas_before_close(self):
        f = self._flow()
        plan = ap.recover_publish_plan(self.root, f["catalog_request"],
                                       f["catalog_manifest"], f["policy"],
                                       live_main=f["h"],
                                       candidate_tip=f["h"],
                                       fresh_stage_root=f["stage"],
                                       relay_dir=f["relay_cat"],
                                       x_root=f["x_wt"])
        self.assertEqual(plan["action"], "close-published")
        state = ap.mark_processed({"schemaVersion": 1}, f["catalog_request"]["requestId"],
                                  extra={"lastPublicationH": f["h"]})
        self.assertTrue(ap.already_processed(state,
                                             f["catalog_request"]["requestId"]))

    def _moved_live_main(self):
        side = self.tmpdir / "moved-side"
        _git(self.root, "worktree", "add", "--detach", "-q", str(side), self.base)
        _write(side, "sources/copywriting/manual.md", b"manual advance\n")
        return _commit_all(side, "manual advance of main")

    def test_stale_live_main_blocks_reviews_advance(self):
        # tip == S but live main already moved: a reviews advance may only
        # resume while main still equals the request base (the later CAS could
        # never land on it anyway; the fresh scan must supersede, never resume)
        f = self._flow()
        moved = self._moved_live_main()
        with self.assertRaises(ap.PublicationError) as raised:
            ap.recover_publish_plan(self.root, f["request"], f["manifest"],
                                    f["policy"], live_main=moved,
                                    candidate_tip=f["s"],
                                    fresh_stage_root=f["stage"],
                                    relay_dir=f["relay"])
        self.assertIn("reviews request base", str(raised.exception))

    def test_stale_live_main_blocks_reviews_reuse_x(self):
        f = self._flow()
        moved = self._moved_live_main()
        with self.assertRaises(ap.PublicationError) as raised:
            ap.recover_publish_plan(self.root, f["request"], f["manifest"],
                                    f["policy"], live_main=moved,
                                    candidate_tip=f["x"],
                                    fresh_stage_root=f["stage"],
                                    relay_dir=f["relay"])
        self.assertIn("reviews request base", str(raised.exception))

    def test_stale_live_main_blocks_catalog_advance_from_x(self):
        # catalog request, tip == X == sourceCommit but live main moved: the
        # advance-from-request path must not re-drive the signing flow either
        f = self._flow()
        moved = self._moved_live_main()
        with self.assertRaises(ap.PublicationError) as raised:
            ap.recover_publish_plan(self.root, f["catalog_request"],
                                    f["catalog_manifest"], f["policy"],
                                    live_main=moved, candidate_tip=f["x"],
                                    fresh_stage_root=f["stage"],
                                    relay_dir=f["relay_cat"], x_root=f["x_wt"])
        self.assertIn("catalog request base", str(raised.exception))

    def test_published_close_keeps_running_despite_base_moved(self):
        # the intentional exception: live main ALREADY equals H is exactly the
        # published close, proven with the SAME full chain proof
        f = self._flow()
        plan = ap.recover_publish_plan(self.root, f["catalog_request"],
                                       f["catalog_manifest"], f["policy"],
                                       live_main=f["h"], candidate_tip=f["h"],
                                       fresh_stage_root=f["stage"],
                                       relay_dir=f["relay_cat"],
                                       x_root=f["x_wt"])
        self.assertEqual(plan["action"], "close-published")
        self.assertEqual(plan["proof"]["candidate"]["status"], "candidate-ok")

    def test_unrelated_live_main_holds_never_forces(self):
        f = self._flow()
        side = self.tmpdir / "side-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(side), self.base)
        _write(side, "sources/copywriting/unrelated.md", b"manual work\n")
        other = _commit_all(side, "unrelated manual advance")
        with self.assertRaises(ap.PublicationError) as raised:
            ap.recover_publish_plan(self.root, f["catalog_request"],
                                    f["catalog_manifest"], f["policy"],
                                    live_main=other, candidate_tip=f["h"],
                                    fresh_stage_root=f["stage"],
                                    relay_dir=f["relay_cat"], x_root=f["x_wt"])
        self.assertIn("never force", str(raised.exception))

    def test_h_recovery_without_proof_inputs_refused(self):
        f = self._flow()
        with self.assertRaises(ap.PublicationError) as raised:
            ap.recover_publish_plan(self.root, f["catalog_request"],
                                    f["catalog_manifest"], f["policy"],
                                    live_main=self.base,
                                    candidate_tip=f["h"],
                                    fresh_stage_root=f["stage"])
        self.assertIn("requires the catalog relay", str(raised.exception))

    def test_ledger_prefix_violation_refused(self):
        f = self._flow()
        # H' with reordered ledger rows: append-only prefix proof must refuse
        bad_wt = self.tmpdir / "bad-h-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(bad_wt), f["y"])
        ledger_path = bad_wt / "catalog" / "publication-ledger.json"
        doc = json.loads(ledger_path.read_bytes())
        doc["publications"] = list(reversed(doc["publications"]))
        ledger_path.write_bytes(hubcore.encoded(doc))
        bad_h = _commit_all(bad_wt, "bad H")
        with self.assertRaises(ap.PublicationError):
            ap.verify_publication_diffs(self.root, self.base, f["x"], f["y"],
                                        bad_h)


class TestCasGraphQLWire(unittest.TestCase):
    """The CAS wire must be the ACTUAL live-proven GitHub GraphQL schema:
    repository(owner,name){id ref(qualifiedName){target{oid}}} plus
    updateRefs(input: UpdateRefsInput!) with named RefUpdate entries. Tests
    pin the real query/variable inputs, not an invented shape."""

    B = "a" * 40
    H = "b" * 40

    def test_query_text_is_the_live_proven_schema(self):
        fetch, mutate = ap._graphql_queries()
        self.assertIn("repository(owner: $owner, name: $name)", fetch)
        self.assertIn("ref(qualifiedName: $qualifiedName) { target { oid } }",
                      fetch)
        self.assertIn(" id ", fetch)
        self.assertNotIn("refPrefix", fetch)
        self.assertNotIn("refId", fetch)
        self.assertEqual(mutate, "mutation casPublish($input: UpdateRefsInput!) "
                                 "{ updateRefs(input: $input) "
                                 "{ clientMutationId } }")

    def test_cas_inputs_match_the_proven_probe_shape(self):
        calls = []
        reads = iter([self.B, self.H])

        def transport(query, variables):
            calls.append((query, variables))
            if "mutation" in query:
                return 200, {"data": {"updateRefs": {
                    "clientMutationId": ap.CAS_MUTATION_ID}}}
            return 200, {"data": {"repository": {
                "id": "REPO_NODE", "ref": {"target": {"oid": next(reads)}}}}}
        result = ap.cas_publish(self.B, self.H, transport=transport)
        self.assertEqual(result["status"], "cas-published")
        fetches = [c for c in calls if "mutation" not in c[0]]
        mutations = [c for c in calls if "mutation" in c[0]]
        self.assertEqual(len(fetches), 2)
        self.assertEqual(len(mutations), 1)
        for _q, vars_ in fetches:
            self.assertEqual(vars_, {"owner": "JiangNanGenius",
                                     "name": "floe-skill-hub",
                                     "qualifiedName": "refs/heads/main"})
        self.assertEqual(mutations[0][1], {"input": {
            "clientMutationId": ap.CAS_MUTATION_ID,
            "repositoryId": "REPO_NODE",
            "refUpdates": [{"name": "refs/heads/main", "beforeOid": self.B,
                            "afterOid": self.H, "force": False}]}})

    def test_missing_repository_node_id_holds(self):
        def transport(query, variables):
            return 200, {"data": {"repository": {
                "id": None, "ref": {"target": {"oid": self.B}}}}}
        with self.assertRaises(ap.PublicationError) as raised:
            ap.cas_publish(self.B, self.H, transport=transport)
        self.assertIn("repository node id", str(raised.exception))

    def test_missing_main_ref_is_unusable_never_forced(self):
        def transport(query, variables):
            return 200, {"data": {"repository": {"id": "R", "ref": None}}}
        with self.assertRaises(ap.PublicationError):
            ap.cas_publish(self.B, self.H, transport=transport)

    def test_graphql_errors_at_http_200_refused(self):
        def transport(query, variables):
            return 200, {"errors": [{"message": "Field 'refPrefix' doesn't exist"}]}
        with self.assertRaises(ap.PublicationError):
            ap.cas_publish(self.B, self.H, transport=transport)

    def test_dry_run_plan_carries_no_private_references(self):
        plan = ap.cas_publish(self.B, self.H, dry_run=True)
        self.assertEqual(plan["status"], "cas-planned")
        self.assertEqual(plan["beforeOid"], self.B)
        self.assertEqual(plan["afterOid"], self.H)
        self.assertIs(plan["force"], False)
        blob = json.dumps(plan)
        for token in ("ROOT-LIVE", "PIPELINE-CONTRACT", "DECISION"):
            self.assertNotIn(token, blob)


class TestReadbackInterface(unittest.TestCase):
    """CLI/interface shape: recover argv stays UNCHANGED for the workflow
    binding, while the direct published-chain check can no longer run
    proof-light and verify-public gained only an optional base."""

    def _choices(self):
        import argparse as _argparse
        sub = next(a for a in ap.build_parser()._actions
                   if isinstance(a, _argparse._SubParsersAction))
        return sub.choices

    def test_recover_argv_shape_unchanged(self):
        opts = {o for a in self._choices()["recover"]._actions
                for o in a.option_strings} - {"-h", "--help"}
        self.assertEqual(opts, {"--repo-root", "--request-file",
                                "--manifest-file", "--live-main",
                                "--candidate-tip", "--stage-root",
                                "--relay-dir", "--x-root"})

    def test_verify_published_chain_requires_full_candidate_inputs(self):
        required = {o for a in self._choices()["verify-published-chain"]._actions
                    if a.required for o in a.option_strings}
        self.assertIn("--stage-root", required)
        self.assertIn("--manifest-file", required)

    def test_verify_public_base_commit_is_optional(self):
        c = self._choices()["verify-public"]
        required = {o for a in c._actions if a.required for o in a.option_strings}
        self.assertEqual(required, {"--head-commit", "--x-commit"})
        opts = {o for a in c._actions for o in a.option_strings}
        self.assertIn("--base-commit", opts)

    def test_published_chain_api_holds_without_candidate_proof(self):
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_published_chain("/nonexistent-root", "a" * 40, "b" * 40,
                                      "c" * 40, "d" * 40, {}, None,
                                      x_root=None, fresh_stage_root=None,
                                      manifest_doc=None)
        self.assertIn("full candidate proof is required", str(raised.exception))

    def test_module_carries_no_private_design_references(self):
        src = pathlib.Path(ap.__file__).read_text(encoding="utf-8")
        for token in ("ROOT-LIVE", "PIPELINE-CONTRACT", "DECISION.json",
                      "publication-design", "skill-hub-auto-update",
                      "Local/Private", "job-0", "job-1", "job-4", "job-5"):
            self.assertNotIn(token, src)
        self.assertIsNone(re.search(r"\bRoot\b", src),
                          "public module must not attribute behavior to a "
                          "personal reviewer identity")


class TestPublicReadback(HubFixture):
    """The post-publish readback proves ONLY against the locally authenticated
    committed H objects: byte-exact feed/sig/ledger, production crypto, the
    FULL ledger re-verified over the committed pins, the base append-only
    prefix, and both-channel newest-row coverage. Reuses the ORIGINAL 43-shape
    full-publication fixture (real signer subprocess), never a hardcoded live
    version."""

    def _publish_full(self):
        stage = self.build_stage()
        wt, s_sha = self.apply_s(stage)
        policy = (self.root / "catalog" / "upstream-update-policy.json").read_bytes()
        _rb, request = ap.build_request("reviews", s_sha, self.base, policy)
        proc = self.run_signer("reviews", s_sha, self.tmpdir / "signed-rb")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay = self.build_relay(request, self.tmpdir / "signed-rb",
                                 name="relay-rb")
        x_sha = self.commit_x(wt, s_sha, request, relay)
        _cb, catalog_request = ap.build_request("catalog", x_sha, self.base,
                                                policy)
        proc = self.run_signer("catalog", x_sha, self.tmpdir / "signed-rb-cat",
                               published_y=self.base)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        relay_cat = self.tmpdir / "relay-rb-cat"
        ap.build_relay_payload(self.tmpdir / "signed-rb-cat", catalog_request,
                               relay_cat, info={"runId": "3", "today": TODAY})
        x_wt = self.tmpdir / "x-wt-rb"
        _git(self.root, "worktree", "add", "--detach", "-q", str(x_wt), x_sha)
        feeds = ap.rebuild_feeds(x_wt, x_sha, trust=TRUST)
        y_dir = self.tmpdir / "y-rb"
        ap.build_y_payload(catalog_request, relay_cat, self.root, feeds, y_dir)
        ap.apply_payload(y_dir, x_wt)
        y_sha = _commit_all(x_wt, "auto-publish: Y")
        h_dir = self.tmpdir / "h-rb"
        ap.build_h_payload(self.root, self.base, y_sha, h_dir)
        ap.apply_payload(h_dir, x_wt)
        h_sha = _commit_all(x_wt, "auto-publish: H")
        return dict(s=s_sha, x=x_sha, y=y_sha, h=h_sha, request=request,
                    catalog_request=catalog_request)

    def _server(self, tamper=None):
        """Tokenless raw-read simulation over the fixture's committed objects."""
        prefix = ap.RAW_HOST + "/" + ap.at.OFFICIAL_HUB_REPO + "/"

        def transport(url):
            if not url.startswith(prefix):
                raise ap.PublicationError("fixture raw host serves only the "
                                          "official hub repository")
            ref, _, rel = url[len(prefix):].partition("/")
            data = ap.blob_at(self.root, ref, rel, "fixture raw " + rel)
            if data is None:
                raise ap.PublicationError("fixture raw host: 404 for " + url)
            if tamper is not None:
                return tamper(ref, rel, data)
            return data
        return transport

    def test_positive_full_publication_readback(self):
        f = self._publish_full()
        verdict = ap.verify_public_main(f["h"], f["x"], trust_root=self.root,
                                       base_commit=self.base,
                                       transport=self._server())
        self.assertEqual(verdict["status"], "public-verified")
        self.assertEqual(verdict["head"], f["h"])
        self.assertEqual(verdict["sourceX"], f["x"])
        for channel in ("ios", "android"):
            self.assertTrue(verdict["feeds"][channel]["byteExactWithH"])
            self.assertEqual(verdict["feeds"][channel]["signatureKeyId"],
                             hubcore.PRODUCTION_KEY_ID)
        self.assertTrue(verdict["ledgerCryptoVerified"])
        self.assertEqual(verdict["newestRowCoverage"],
                         {"android": f["y"], "ios": f["y"]})
        self.assertIn("append-only prefix", verdict["ledgerPrefix"])
        self.assertEqual(verdict["ledgerRows"], 4)  # 2 base + 2 published now

    def test_missing_channel_object_fails_closed(self):
        f = self._publish_full()

        def drop(ref, rel, data):
            if rel == "android/catalog.json":
                raise ap.PublicationError("fixture raw host: 404 (missing channel)")
            return data
        with self.assertRaises(ap.PublicationError):
            ap.verify_public_main(f["h"], f["x"], trust_root=self.root,
                                  base_commit=self.base,
                                  transport=self._server(drop))

    def test_wrong_body_not_byte_exact_fails_closed(self):
        f = self._publish_full()
        old_feed = ap.blob_at(self.root, self.p0, "catalog.json", "p0 feed")

        def swap(ref, rel, data):
            return old_feed if rel == "catalog.json" else data
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_public_main(f["h"], f["x"], trust_root=self.root,
                                  base_commit=self.base,
                                  transport=self._server(swap))
        self.assertIn("byte-exact", str(raised.exception))

    def test_ledger_dropping_newest_channel_row_fails_closed(self):
        # H_bad commits base rows + ONLY the ios newest row: byte-exact,
        # per-row crypto and the base prefix all still pass; the both-channel
        # newest coverage proof is what refuses it
        f = self._publish_full()
        base_rows, new_rows, _expected = ap.expected_ledger_bytes(
            self.root, self.base, f["y"])
        tampered = ap.pi.render_ledger(
            base_rows + [r for r in new_rows if r["channel"] == "ios"])
        bad_wt = self.tmpdir / "bad-h-readback"
        _git(self.root, "worktree", "add", "--detach", "-q", str(bad_wt),
             f["h"])
        _write(bad_wt, "catalog/publication-ledger.json", tampered)
        h_bad = _commit_all(bad_wt, "bad H: android newest row dropped")
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_public_main(h_bad, f["x"], trust_root=self.root,
                                  base_commit=self.base,
                                  transport=self._server())
        self.assertIn("quote the digest", str(raised.exception))

    def test_old_row_rewrite_fails_closed(self):
        f = self._publish_full()
        doc = json.loads(ap.blob_at(self.root, f["h"], ap.LEDGER_REL,
                                    "h ledger"))
        doc["publications"][0]["feedSha256"] = "0" * 64
        tampered = ap.pi.render_ledger(doc["publications"],
                                       description=doc["description"])
        bad_wt = self.tmpdir / "bad-oldrows-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(bad_wt),
             f["h"])
        _write(bad_wt, "catalog/publication-ledger.json", tampered)
        h_bad = _commit_all(bad_wt, "bad H: historical row rewritten")
        # even with the bytes matching its own committed tree, the FULL
        # cryptographic ledger re-verification over the committed pins
        # refuses the stale row
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_public_main(h_bad, f["x"], trust_root=self.root,
                                  base_commit=self.base,
                                  transport=self._server())
        self.assertIn("ledger", str(raised.exception).lower())

    def test_base_rows_replaced_refused_by_prefix_proof(self):
        # drop the first base row: the remaining rows all verify
        # cryptographically and the newest rows still cover both channels,
        # so ONLY the explicit append-only prefix proof can refuse this
        f = self._publish_full()
        base_rows, new_rows, _expected = ap.expected_ledger_bytes(
            self.root, self.base, f["y"])
        tampered = ap.pi.render_ledger(base_rows[1:] + new_rows)
        bad_wt = self.tmpdir / "bad-prefix-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(bad_wt),
             f["h"])
        _write(bad_wt, "catalog/publication-ledger.json", tampered)
        h_bad = _commit_all(bad_wt, "bad H: base row deleted")
        with self.assertRaises(ap.PublicationError) as raised:
            ap.verify_public_main(h_bad, f["x"], trust_root=self.root,
                                  base_commit=self.base,
                                  transport=self._server())
        self.assertIn("anchor", str(raised.exception))

    def test_wrong_key_signature_fails_closed(self):
        f = self._publish_full()
        fk_wt = self.tmpdir / "fk-h-wt"
        _git(self.root, "worktree", "add", "--detach", "-q", str(fk_wt), f["h"])
        feed = (fk_wt / "android" / "catalog.json").read_bytes()
        (fk_wt / "android" / "catalog.sig").write_bytes(
            hubcore.sign_envelope(feed, FOREIGN_KEY, hubcore.PRODUCTION_KEY_ID))
        h_fk = _commit_all(fk_wt, "H with foreign-key android signature")
        with self.assertRaises(ap.PublicationError):
            ap.verify_public_main(h_fk, f["x"], trust_root=self.root,
                                  base_commit=self.base,
                                  transport=self._server())


class TestWorkflowStructure(unittest.TestCase):
    TRACKER = REPO / ".github" / "workflows" / "skill-hub-upstream-tracker.yml"
    PUBLISHER = REPO / ".github" / "workflows" / "skill-hub-auto-publish.yml"
    APP = REPO / "automation" / "workflows" / "floe-skill-hub-auto-publication.yml"

    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML unavailable in this runner environment")
        import yaml
        self.yaml = yaml
        self.tracker = yaml.safe_load(self.TRACKER.read_text())
        self.publisher = yaml.safe_load(self.PUBLISHER.read_text())
        self.app = yaml.safe_load(self.APP.read_text())

    def test_all_exist_and_guarded(self):
        for doc in (self.tracker, self.publisher, self.app):
            for job in doc["jobs"].values():
                self.assertIn("vars.FLOE_SKILL_HUB_AUTO", job.get("if", ""))

    def test_cadences(self):
        tracker_crons = self.tracker[True]["schedule"]  # 'on' parses as boolean True
        self.assertEqual(len(tracker_crons), 1)
        minute, hour = tracker_crons[0]["cron"].split()[0], tracker_crons[0]["cron"].split()[1]
        self.assertNotEqual(minute, "0")
        self.assertEqual(len(hour.split(",")), 4)
        pub = self.publisher[True]["schedule"][0]["cron"].split()
        self.assertEqual(pub[1], "*")
        self.assertNotEqual(pub[0].split(",")[0], "0")
        app = self.app[True]["schedule"][0]["cron"].split()
        self.assertNotEqual(app[0].split(",")[0], "0")

    def test_no_secrets_in_hub_workflows(self):
        for path in (self.TRACKER, self.PUBLISHER):
            text = path.read_text()
            self.assertNotIn("FLOE_SKILL_HUB_SIGNING_KEY", text)

    def test_app_secret_appears_in_exactly_two_sign_steps(self):
        text = self.APP.read_text()
        self.assertEqual(text.count("FLOE_SKILL_HUB_SIGNING_KEY:"), 2)
        jobs = self.app["jobs"]
        self.assertEqual(jobs["orchestrate"]["permissions"]["contents"], "read")
        self.assertEqual(jobs["sign-reviews"]["permissions"]["contents"], "read")
        self.assertEqual(jobs["sign-catalog"]["permissions"]["contents"], "read")
        self.assertEqual(jobs["relay"]["permissions"]["contents"], "write")
        for job in ("orchestrate", "sign-reviews", "sign-catalog"):
            steps = " ".join(json.dumps(jobs[job].get("env") or {}) +
                             " ".join(json.dumps(s) for s in jobs[job]["steps"]))
            if job == "orchestrate":
                self.assertNotIn("SIGNING_KEY", steps)

    def test_app_relay_only_scoped_branch(self):
        text = self.APP.read_text()
        self.assertIn("${RELAY_BRANCH}:refs/heads/${RELAY_BRANCH}", text)
        self.assertIn("group: floe-skill-hub-signing", text)
        self.assertIn("ANCHOR_PENDING_ROOT_REVIEW", text)
        self.assertNotIn("ANCHOR_PENDING", self.TRACKER.read_text())
        self.assertNotIn("ANCHOR_PENDING", self.PUBLISHER.read_text())
        for line in text.splitlines():
            if "run:" in line or "script" in line:
                self.assertNotIn("refs/heads/main", line)

    def test_pinned_actions_only(self):
        for path in (self.TRACKER, self.PUBLISHER, self.APP):
            for line in path.read_text().splitlines():
                if "uses: actions/" in line:
                    ref = line.split("uses:")[1].strip().split("@")[1].split("#")[0].strip()
                    self.assertRegex(ref, r"^[0-9a-f]{40}$", line)

    def test_publisher_cas_uses_env_token_only(self):
        text = self.PUBLISHER.read_text()
        self.assertIn("--token-env GITHUB_TOKEN", text)
        expr = chr(36) + chr(123) + chr(123) + " secrets.GITHUB_TOKEN " + chr(125) + chr(125)
        self.assertIn("GITHUB_TOKEN: " + expr, text)
        self.assertIn("python3 scripts/automatic_publication.py cas", text)
        self.assertIn("verify-public", text)

    def test_workflows_run_on_github_hosted_only(self):
        for path in (self.TRACKER, self.PUBLISHER, self.APP):
            text = path.read_text()
            self.assertNotIn("self-hosted", text)
            self.assertIn("ubuntu-latest", text)

    def test_no_workflow_run_trigger_assumptions(self):
        for path in (self.TRACKER, self.PUBLISHER, self.APP):
            self.assertNotIn("push:", path.read_text())



class TestCatalogRequestParser(unittest.TestCase):
    def test_catalog_request_requires_independently_resolved_base(self):
        parser = ap.build_parser()
        argv = ["emit-catalog-request", "--repo-root", ".",
                "--x-commit", "2" * 40, "--stage-root", "stage",
                "--manifest-file", "manifest.json", "--candidate-ref",
                "auto/candidate-fixture", "--out", "out",
                "--today", "2026-10-28"]
        args = parser.parse_args(argv + ["--expected-base", "1" * 40])
        self.assertEqual(args.expected_base, "1" * 40)
        with self.assertRaises(SystemExit) as caught:
            parser.parse_args(argv)
        self.assertEqual(caught.exception.code, 2)

class TestHeldStateZeroWriteStage(unittest.TestCase):
    """Actual held-state CLI over the real producer-shaped stage layout.

    Positive: the genuine held-only cloud stage (tracker run 40641535335,
    counts applyWrites=0/held=1) carries an EMPTY ordered writes list and
    must yield an actionable control state through the same CLI invocation
    the workflow runs. Negatives: a missing or non-list ordered write list,
    eligible candidates behind zero-write facts, a staged candidate tree
    against lying facts, a no-holds no-op scan, and manifest digest drift
    must all still refuse with the strict fail-closed messages.
    """

    HOLD_REASONS = [{
        "code": "held-engine-managed",
        "detail": "engine-managed skill: corpus drift True, "
                  "newer stable engine release True",
        "id": "impeccable",
        "repair": "sources/impeccable is regenerated only by the pinned "
                  "two-stage engines/impeccable pipeline; engine updates "
                  "run through .github/workflows/impeccable-engine-updater.yml; "
                  "this tracker reports signals and holds, it never "
                  "constructs an impeccable candidate",
    }]

    def _stage(self, tmp, *, writes="empty", facts_overrides=None,
               apply_overrides=None, with_held_record=True,
               candidate_tree=False, apply_files=None):
        stage = pathlib.Path(tmp) / "stage"
        stage.mkdir()
        (stage / "apply").mkdir()
        manifest_writes = []
        if writes == "entries":
            for rel, data in sorted((apply_files or {}).items()):
                target = stage / "apply" / "files" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                manifest_writes.append({"path": rel,
                                        "sha256": hubcore.sha256_hex(data),
                                        "bytes": len(data)})
        apply_doc = {"schemaVersion": 1,
                     "generatedFromPlanSha256": "e3f50a69282c935901d445a20d4"
                     "af165c24da87a3f43161c6619848895111d0b",
                     "today": TODAY, "pinsHelper": "advance_pins:v1",
                     "acceptedIds": [], "deletions": [],
                     "skippedByteIdenticalNoops":
                         ["catalog/skills.json", "docs/UPSTREAM-PINS.json"],
                     "reviewRecords": "new unsigned records only",
                     "ordering": "apply writes and deletions, then rebuild "
                                 "feeds, then CI gates, then staging commit"}
        if writes == "empty":
            apply_doc["writes"] = []
        elif writes == "entries":
            apply_doc["writes"] = manifest_writes
        elif writes == "legacy-files-alias":
            apply_doc["files"] = [{"path": rel,
                                   "sha256": hubcore.sha256_hex(data)}
                                  for rel, data in sorted(
                                      (apply_files or {}).items())]
            for rel, data in sorted((apply_files or {}).items()):
                target = stage / "apply" / "files" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        elif writes == "missing":
            pass
        elif writes == "nonlist":
            apply_doc["writes"] = {}
        elif writes == "null":
            apply_doc["writes"] = None
        elif writes == "bad-digest":
            apply_doc["writes"] = [{"path": "catalog/skills.json",
                                    "sha256": "f" * 64}]
            target = stage / "apply" / "files" / "catalog/skills.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"{\"skills\":[]}\n")
        else:
            raise AssertionError(f"unknown writes shape {writes!r}")
        apply_doc.update(apply_overrides or {})
        (stage / "apply" / "manifest.json").write_bytes(
            hubcore.encoded(apply_doc))
        facts = {"changedSkillIds": [], "bumpedVersions": {},
                 "heldSkillIds": ["impeccable"] if with_held_record else [],
                 "holdReasons": list(self.HOLD_REASONS)
                 if with_held_record else [],
                 "pinAdvances": {}, "acceptedIds": [],
                 "reviewStageCounts": {"prior-proof-reuse": 0,
                                       "static-content-reviewed": 0},
                 "executableSubsetUnchanged": {}, "engineSignals": []}
        if candidate_tree:
            base = stage / "candidates" / GUIDE_ID / "1.0.1"
            (base / "tree" / "SKILL.md").parent.mkdir(parents=True)
            (base / "tree" / "SKILL.md").write_bytes(b"# drift\n")
            (base / "package.zip").write_bytes(b"PK\x03\x04fixture")
            (base / "candidate.json").write_bytes(hubcore.encoded({
                "tier": 1, "proposedVersion": "1.0.1",
                "proposedReview": {"id": GUIDE_ID}}))
            facts["changedSkillIds"] = []  # lying facts: tree exists anyway
        facts.update(facts_overrides or {})
        (stage / "staging-manifest.json").write_bytes(hubcore.encoded({
            "reportKind": "floe-skill-hub-upstream-stage", "reportVersion": 1,
            "today": TODAY,
            "inputs": {"pinsSha256": "687750b17d080d5ebea0d95fa84a30951e86"
                                     "b725c778864834ee36df0792297a",
                       "policySha256": "abe51ebb49c09f5bc6a230117c90fb408b78"
                                       "dbb7d301cceac186dc764eda51e9",
                       "registrySha256": "8b1d933ad7eff40d7e1f306c30598eb14e"
                                         "b0cb290aafdda25361ae27abc91935"},
            "planSha256": apply_doc["generatedFromPlanSha256"],
            "stageRoot": str(stage), "candidates": [],
            "heldIds": ["impeccable"] if with_held_record else [],
            "candidateFacts": facts,
            "boundary": "stage wrote only under the stage root",
            "counts": {"staged": 1 if candidate_tree else 0,
                       "held": 1 if with_held_record else 0,
                       "applyWrites": len(apply_doc.get("writes", [])
                                          if isinstance(
                                              apply_doc.get("writes"), list)
                                          else []),
                       "applyDeletions": 0}}))
        if with_held_record:
            held_dir = stage / "held"
            held_dir.mkdir()
            (held_dir / "impeccable.json").write_bytes(hubcore.encoded({
                "id": "impeccable", "tier": "engine-managed",
                "upstream": {"repository": "https://github.com/pbakaus/"
                                           "impeccable"},
                "publishedVersionIntact": True}))
        return stage

    def _run_cli(self, stage, tmp, state_doc="{}"):
        control = pathlib.Path(tmp) / "control"
        state_file = pathlib.Path(tmp) / "current-state.json"
        state_file.write_text(state_doc)
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "automatic_publication.py"),
             "held-state", "--stage-root", str(stage), "--out", str(control),
             "--today", TODAY, "--state-file", str(state_file)],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        return proc, control

    def test_cli_accepts_producer_shaped_zero_write_held_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="empty")
            proc, control = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            summary = json.loads(proc.stdout)
            self.assertEqual(summary["status"], "held-state-built")
            self.assertEqual(summary["holdCount"], 1)
            files = sorted(p.name for p in control.iterdir())
            self.assertEqual(files, ["control-changes.json", "state.json"])
            state = json.loads((control / "state.json").read_bytes())
            self.assertEqual(state["pipelineStage"], "held")
            self.assertEqual(state["lastCheckUTC"], TODAY)
            self.assertEqual(state["holdReasons"], self.HOLD_REASONS)
            self.assertEqual(state["integrationGaps"], [])
            self.assertIsNone(state["openRequestId"])
            changes = json.loads((control / "control-changes.json").read_bytes())
            self.assertEqual(changes["mirror"], ["state.json"])
            self.assertTrue(changes["closeOpenRequest"])

    def test_cli_preserves_prior_open_request_and_processed_ids(self):
        prior = {"openRequestId": "req-abc", "processedRequestIds": ["req-old"]}
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="empty")
            proc, control = self._run_cli(stage, tmp, state_doc=json.dumps(prior))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            state = json.loads((control / "state.json").read_bytes())
            self.assertEqual(state["openRequestId"], "req-abc")
            self.assertEqual(state["processedRequestIds"], ["req-old"])
            self.assertEqual(state["pipelineStage"], "held")
            changes = json.loads((control / "control-changes.json").read_bytes())
            self.assertFalse(changes["closeOpenRequest"])

    def test_cli_legacy_files_alias_nonempty_still_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="legacy-files-alias",
                                apply_files={"catalog/skills.json":
                                             b"{\"skills\":[]}\n"})
            proc, _ = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["holdCount"], 1)

    def test_cli_missing_ordered_list_key_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="missing")
            proc, control = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("apply/manifest.json carries no ordered write list",
                          proc.stderr)
            self.assertTrue(proc.stderr.startswith(
                "automatic-publication: refusing: "))
            self.assertFalse(control.exists())

    def test_cli_non_list_and_null_writes_refuse(self):
        for shape in ("nonlist", "null"):
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as tmp:
                stage = self._stage(tmp, writes=shape)
                proc, _ = self._run_cli(stage, tmp)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("carries no ordered write list", proc.stderr)

    def test_cli_facts_drift_with_candidates_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="empty", facts_overrides={
                "changedSkillIds": [GUIDE_ID],
                "bumpedVersions": {GUIDE_ID: {"from": "1.0.0",
                                              "to": "1.0.1"}}})
            proc, _ = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("stage carries candidates; use the candidate "
                          "request path", proc.stderr)

    def test_cli_candidate_tree_with_lying_facts_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="empty", candidate_tree=True)
            proc, _ = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("stage carries candidates; use the candidate "
                          "request path", proc.stderr)

    def test_cli_zero_write_without_holds_refuses_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="empty", with_held_record=False)
            proc, _ = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("nothing staged to hold; this is a no-op scan",
                          proc.stderr)

    def test_cli_digest_drift_gate_still_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self._stage(tmp, writes="bad-digest")
            proc, _ = self._run_cli(stage, tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("drifted from its manifest digest", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
