#!/usr/bin/env python3
"""Emit the fixture-only signed iOS/Android catalog samples for native owners.

Output layout mirrors the production contract exactly, rooted at
tests/catalog/fixtures/ :
  catalog.json / catalog.sig / packages/...       (iOS channel)
  android/catalog.json / android/catalog.sig / android/packages/...
  reviews/<id>/<version>.review.json(+.sig)
  fixture-public-key.json / FIXTURE-ONLY.md

Everything here is signed with a deterministic public-knowledge ephemeral key
(keyID "fixture-only-2026-10"). The seed string lives in hubcore: the
signature proves only wire-shape and verification mechanics. It is not a
trust root, not a review, not a publication, and must never be compiled into
trustedKeys. python3 scripts/make_fixture.py [--check] re-emits or verifies.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hubcore

REPO = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO / "tests" / "catalog" / "fixtures"
MARKER = """# FIXTURE ONLY — not a catalog, not a trust root

These files exist so the iOS main thread (A1) and the Android mainline lane
can build and test their schemaVersion-3 parsers, Ed25519 envelope
verification, review-binding chain, package gates and install-offer rules
against the exact wire shape **before** any qualified production content
exists.

- Signed with the deterministic ephemeral key `fixture-only-2026-10`. Its
  private seed is public knowledge (see `scripts/hubcore.py`), so nothing
  signed here attests to any real review, quality, license or publication.
- Every entry id starts with `fixture-` and every feed sets
  `feedStatus: "fixture"`; production parsers must reject fixture feeds when
  asked to activate a production channel, and the fixture key must only ever
  be loaded through an explicitly test-only trust map.
- The layout mirrors the production contract: iOS channel at the bundle root,
  Android channel under `android/`, reviews under `reviews/`, archives
  under `packages/{id}/{version}/{id}.zip`.

Regenerate (never hand-edit): `python3 scripts/make_fixture.py`
Verify unchanged: `python3 scripts/make_fixture.py --check`
"""


def _status(**kw):
    s = {"sourcePinned": True, "licenseChecked": True, "adaptation": "in-progress",
         "packaged": False, "reviewed": False, "qualified": False,
         "published": False, "executionVerified": False}
    s.update(kw)
    return s


def _runtime(**kw):
    r = {"scriptRuntime": "none", "capabilities": [], "tools": [],
         "installPlatforms": ["ios", "android"], "pythonPackagesPlan": [],
         "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}}
    r.update(kw)
    return r


def fixture_sources():
    """Synthetic package sources; never copied from any upstream skill."""
    guide = {
        "SKILL.md": (b"---\nname: fixture-guide\ndescription: Fixture-only read"
                     b"-only guide sample. Never install as production content.\n"
                     b"---\n\nThis is a FIXTURE sample guide. It declares no\n"
                     b"scripts and claims no execution capability.\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": "fixture-guide", "version": "1.0.0",
            "capabilities": [], "tools": [], "platforms": ["ios"],
            "scriptRuntime": "none", "pythonPackages": []}),
        "references/NOTICE.md": b"Fixture-only sample notice. No upstream work is represented.\n",
    }
    script_files = {
        "SKILL.md": (b"---\nname: fixture-script\ndescription: Fixture-only script"
                     b" sample executed via exec.shell in the task Linux guest.\n---\n\n"
                     b"Run scripts/echo.py through the existing task Linux\n"
                     b"environment. Fixture-only: execution is NOT verified.\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": "fixture-script", "version": "1.0.0",
            "capabilities": ["execution.remote", "workspace.read"],
            "tools": ["exec.shell"], "platforms": ["ios"],
            "scriptRuntime": "remote", "pythonPackages": []}),
        "scripts/echo.py": (b"""import sys\nprint("fixture-only sample; runs only through exec.shell")\nsys.exit(0)\n"""),
        "references/NOTICE.md": b"Fixture-only sample. The script is never executed by the builder.\n",
    }
    reviewed = {
        "SKILL.md": (b"---\nname: fixture-reviewed\ndescription: Fixture-only sample"
                     b" with a simulated signed review record.\n---\n\nExercises the"
                     b" signed review-binding chain only. The attached\nreview is a"
                     b" fixture artifact, not a real review decision.\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": "fixture-reviewed", "version": "1.0.0",
            "capabilities": ["execution.remote", "workspace.read", "workspace.write"],
            "tools": ["exec.shell"], "platforms": ["ios"],
            "scriptRuntime": "remote", "pythonPackages": []}),
        "scripts/report.py": (b"""import json\nprint(json.dumps({"fixture": True, "verifiedExecution": False}))\n"""),
        "references/NOTICE.md": b"Fixture-only sample review-binding material.\n",
    }
    return {"fixture-guide": guide, "fixture-script": script_files,
            "fixture-reviewed": reviewed}


def _entry(id_, plan, desc_en, desc_zh, runtime, status, package=None, review=None,
           offer="none"):
    reg = {
        "id": id_, "planNumber": plan, "kind": "optional", "source": "F",
        "name": {"en": id_.replace("fixture-", "Fixture ").title(),
                 "zh-Hans": f"契约夹具 {id_}"},
        "description": {"en": desc_en, "zh-Hans": desc_zh},
        "category": "productivity-organization", "tags": ["fixture", "sample"],
        "deepAdaptation": False, "upstream": None, "firstParty": None,
        "plannedRuntime": runtime, "versionTarget": "1.0.0",
        "minimumAppVersion": "1.7.0" if package else None,
        "status": status,
        "notes": {"en": "Fixture-only sample for native integration testing; not content, not review.",
                  "zh-Hans": "仅用于原生集成测试的契约夹具；不是内容，也不是审核。"},
    }
    return hubcore.catalog_entry(reg, package=package, review=review, install_offer=offer)


def build_outputs():
    sources = fixture_sources()
    archives = {}
    digests = {}
    for id_, files in sources.items():
        hubcore.validate_package_files(files)
        data = hubcore.make_zip(files)
        archives[id_] = data
        digests[id_] = {
            "size": len(data), "sha256": hubcore.sha256_hex(data),
            "contentDigest": hubcore.content_digest(files),
            "containsScripts": any(n.startswith("scripts/") for n in files),
        }

    review_record = {
        "schemaVersion": 1, "id": "fixture-reviewed", "version": "1.0.0",
        "contentDigest": digests["fixture-reviewed"]["contentDigest"],
        "packageSha256": digests["fixture-reviewed"]["sha256"],
        "reviewedCapabilities": ["execution.remote", "workspace.read", "workspace.write"],
        "reviewedTools": ["exec.shell"],
        "reviewedPythonPackages": [],
        "execution": {"os": "linux", "arch": "riscv64", "evidence": "unproven"},
        "reviewStage": "static-content-reviewed",
        "reviewedAt": "2026-10-26",
        "reviewer": "fixture-synthetic-reviewer",
        "decision": "approve",
        "notes": {"en": "SIMULATED review record inside a fixture feed; proves the binding chain shape only.",
                  "zh-Hans": "夹具目录中的模拟审核记录；仅证明绑定链字段形状。"},
    }
    record_bytes = hubcore.encoded(review_record)
    review_path = "reviews/fixture-reviewed/1.0.0.review.json"
    review_block = {"path": review_path, "sha256": hubcore.sha256_hex(record_bytes),
                    "keyID": hubcore.FIXTURE_KEY_ID}

    guide_entry = _entry(
        "fixture-guide", 1,
        "Fixture-only read-only guide sample with no scripts and no execution claim.",
        "仅契约夹具：只读指南样本，无脚本、无执行声明。",
        _runtime(), _status(), offer="none")
    script_entry = _entry(
        "fixture-script", 2,
        "Fixture-only script sample packaged and bound, but deliberately unreviewed.",
        "仅契约夹具：脚本样本已打包绑定但未审核，不得提供安装。",
        _runtime(scriptRuntime="remote",
                 capabilities=["execution.remote", "workspace.read"],
                 tools=["exec.shell"],
                 execution={"os": "linux", "arch": "riscv64", "evidence": "unproven"}),
        _status(adaptation="frozen", packaged=True),
        package=None, offer="none")
    script_entry["package"] = {**digests["fixture-script"],
                               "path": hubcore.package_path_for("fixture-script", "1.0.0", "ios")}
    script_entry["minimumAppVersion"] = "1.7.0"
    reviewed_entry = _entry(
        "fixture-reviewed", 3,
        "Fixture-only sample carrying a simulated signed review record.",
        "仅契约夹具：带模拟签名审核记录的样本。",
        _runtime(scriptRuntime="remote",
                 capabilities=["execution.remote", "workspace.read", "workspace.write"],
                 tools=["exec.shell"],
                 execution={"os": "linux", "arch": "riscv64", "evidence": "unproven"}),
        _status(adaptation="frozen", packaged=True, reviewed=True),
        package=None, review=review_block, offer="fixture-simulated")
    reviewed_entry["package"] = {**digests["fixture-reviewed"],
                                 "path": hubcore.package_path_for("fixture-reviewed", "1.0.0", "ios")}
    reviewed_entry["minimumAppVersion"] = "1.7.0"

    entries = [guide_entry, script_entry, reviewed_entry]
    ios = hubcore.build_catalog({"publisher": "JiangNanGenius"}, "ios", "fixture", entries, None)
    ios_bytes = hubcore.encoded(ios)
    hubcore.validate_catalog(json.loads(ios_bytes), channel="ios", allow_fixture=True)

    android_entries = []
    for entry in entries:
        view = json.loads(hubcore.encoded(entry))
        if "android" not in view["runtime"]["installPlatforms"]:
            continue
        view["version"] = "1.0.0"
        if view["package"]:
            view["package"]["path"] = hubcore.package_path_for(
                view["id"], "1.0.0", "android")
        if view["minimumAppVersion"] is None:
            view["minimumAppVersion"] = "1.7.0"
        android_entries.append(view)
    android = hubcore.build_catalog({"publisher": "JiangNanGenius"}, "android", "fixture",
                                    android_entries, None)
    android_bytes = hubcore.encoded(android)
    hubcore.validate_catalog(json.loads(android_bytes), channel="android", allow_fixture=True)

    key = hubcore.fixture_private_key()
    outputs = {
        "FIXTURE-ONLY.md": MARKER.encode(),
        "fixture-public-key.json": hubcore.encoded({
            "keyID": hubcore.FIXTURE_KEY_ID,
            "publicKey": hubcore.fixture_public_b64(),
            "fixtureOnly": True,
            "notATrustRoot": True}),
        "catalog.json": ios_bytes,
        "catalog.sig": hubcore.sign_envelope(ios_bytes, key, hubcore.FIXTURE_KEY_ID),
        "android/catalog.json": android_bytes,
        "android/catalog.sig": hubcore.sign_envelope(android_bytes, key, hubcore.FIXTURE_KEY_ID),
        "reviews/fixture-reviewed/1.0.0.review.json": record_bytes,
        review_path + ".sig": hubcore.sign_envelope(record_bytes, key, hubcore.FIXTURE_KEY_ID),
    }
    for id_, data in archives.items():
        outputs["packages/" + id_ + "/1.0.0/" + id_ + ".zip"] = data
        outputs["android/packages/" + id_ + "/1.0.0/" + id_ + ".zip"] = data
    return outputs


def verify(outputs):
    public = {hubcore.FIXTURE_KEY_ID: hubcore.fixture_public_b64()}
    for channel, prefix in (("ios", ""), ("android", "android/")):
        body = outputs[prefix + "catalog.json"]
        hubcore.verify_envelope(body, outputs[prefix + "catalog.sig"], public)
        feed = json.loads(body)
        hubcore.validate_catalog(feed, channel=channel if channel != "ios" else "ios",
                                 allow_fixture=True)
        for entry in feed["entries"]:
            if entry["package"]:
                data = outputs[entry["package"]["path"] if not entry["package"]["path"].startswith("android")
                               else entry["package"]["path"]]
                files = hubcore.check_archive_bytes(data)
                if hubcore.sha256_hex(data) != entry["package"]["sha256"]:
                    raise hubcore.HubError("fixture archive sha256 mismatch")
                if len(data) != entry["package"]["size"]:
                    raise hubcore.HubError("fixture archive size mismatch")
                if hubcore.content_digest(files) != entry["package"]["contentDigest"]:
                    raise hubcore.HubError("fixture contentDigest mismatch")
            if entry["review"]:
                record = outputs[entry["review"]["path"]]
                hubcore.verify_envelope(record, outputs[entry["review"]["path"] + ".sig"], public)
                parsed = json.loads(record)
                hubcore.validate_review(parsed)
                if entry["review"]["sha256"] != hubcore.sha256_hex(record):
                    raise hubcore.HubError("fixture review digest mismatch")
                if entry["installOffer"] != "fixture-simulated":
                    raise hubcore.HubError("fixture review without simulated offer")
                for reg_entry in json.loads((REPO / "catalog" / "skills.json").read_bytes())["skills"]:
                    if reg_entry["id"] == entry["id"]:
                        raise hubcore.HubError("fixture id collides with the registry")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build_outputs()
    verify(outputs)
    if args.check:
        stale = []
        for name, data in outputs.items():
            path = FIXTURE_ROOT / name
            if not path.exists() or path.read_bytes() != data:
                stale.append(name)
        if stale:
            raise SystemExit("fixture files stale: " + ", ".join(stale))
        print("fixture catalog verified (read-only): " + f"{len(outputs)} files")
        return
    for name, data in outputs.items():
        target = FIXTURE_ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print("emitted fixture-only signed sample: " + f"{len(outputs)} files under {FIXTURE_ROOT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
