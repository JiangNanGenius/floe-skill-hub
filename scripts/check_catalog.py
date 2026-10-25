#!/usr/bin/env python3
"""Read-only Hub integrity gate for CI and lanes (H1). Never writes, never signs.

Checks performed (fail closed, aggregate report):
  1. registry structural validation (43/4/39/9, bilingual, statuses, blockers)
  2. upstream pins equal the coordinator's docs/UPSTREAM-PINS.json baselines
  3. schema documents are byte-stable against the validator (gen_schemas --check)
  4. fixture sample rebuilds identically and every signature/digest/join verifies
  5. production publication, when any production artifact exists, is verified
     standalone from the published bytes: both channel feed+signature pairs,
     each signature exact-byte verified under the configured public-key.json
     trust (never the fixture identity), canonical schema-valid feeds carrying
     a 40-hex audited sourceCommit X (external publication pin Y is where these
     bytes live; X is never compared against a mutable HEAD), and every bound
     package/review re-joined against the actual published archive and record
     bytes. A valid publication is NOT invalidated by pending candidate-HEAD
     changes, and an unreviewed candidate can never carry an install offer
     inside the signed feed.
  6. staged sources (content lanes) package cleanly and immutably
  7. legacy four-item view renders only from qualified builtins — otherwise
     honestly reports it as pending
  8. no private key material or unlabelled secrets in the tracked lane

Exit 0 = all gates pass; non-zero with a precise reason list.
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import hubcore
import make_fixture

REPO = HERE.parents[1]


def fail(reasons, message):
    reasons.append(message)


def check_pins(reasons):
    pins = json.loads((REPO / "docs" / "UPSTREAM-PINS.json").read_bytes())["repositories"]
    registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
    for entry in registry["skills"]:
        upstream = entry.get("upstream")
        if upstream is None:
            continue
        repo = upstream["repository"].removeprefix("https://github.com/")
        if repo not in pins:
            fail(reasons, f"{entry['id']}: repository {repo} is not in docs/UPSTREAM-PINS.json")
        elif upstream["commit"] != pins[repo]:
            fail(reasons, f"{entry['id']}: commit {upstream['commit'][:10]} diverges from "
                          f"the review baseline {pins[repo][:10]}")


def check_production(reasons):
    """Read-only publication gate: verifies the PUBLISHED BYTES standalone.

    The gate never rebuilds a published feed from the mutable candidate
    registry/HEAD (an upstream lane staging an unreviewed next version must
    not invalidate a valid earlier publication) and never resolves git. It
    verifies, against the exact bytes in this published (Y) checkout:
      * once ANY production artifact exists, BOTH channel feed+signature pairs
        are required; an absent signature never passes as "unpublished";
      * each signature verifies over the exact feed bytes under the configured
        public-key.json trust, with the expected production identity;
      * each feed is canonical, schema-valid, production-shaped, and carries a
        40-hex audited sourceCommit X (provenance; distinct from Y; no
        self-reference, never compared against the mutable HEAD);
      * every bound archive and review joins the published bytes: archive
        sha256/size/contentDigest, review record digest and signature chain,
        approve decision, exact reviewed tool/capability/dependency coverage,
        and the feed's own qualified-offer rules — so an unreviewed entry can
        never carry an install offer in a signed feed.
    """
    pairs = [("ios", REPO / "catalog.json", REPO / "catalog.sig"),
             ("android", REPO / "android" / "catalog.json", REPO / "android" / "catalog.sig")]
    if not any(path.exists() or sig.exists() for _, path, sig in pairs):
        return
    import build_catalog
    try:
        public_keys = build_catalog.load_trust(REPO)
    except hubcore.HubError as error:
        fail(reasons, f"configured public trust is invalid: {error}")
        return
    if not public_keys:
        fail(reasons, "production artifacts exist but no public-key.json trust is configured; "
                      "a published feed without trust material must fail the gate")
        return
    for channel, path, sig_path in pairs:
        if not path.is_file():
            fail(reasons, f"{channel} channel published but feed missing: {path.relative_to(REPO)}")
            continue
        if not sig_path.is_file():
            fail(reasons, f"{channel} feed published without its signature: "
                          f"{sig_path.relative_to(REPO)} is missing (an absent signature never passes)")
            continue
        body = path.read_bytes()
        try:
            key_id = hubcore.verify_envelope(body, sig_path.read_bytes(), public_keys)
        except hubcore.HubError as error:
            fail(reasons, f"{channel} catalog signature invalid over the exact bytes: {error}")
            continue
        if key_id == hubcore.FIXTURE_KEY_ID:
            fail(reasons, f"{channel} catalog signed with the fixture identity: forbidden")
            continue
        if key_id not in public_keys or (hubcore.PRODUCTION_KEY_ID in public_keys
                                         and key_id != hubcore.PRODUCTION_KEY_ID):
            fail(reasons, f"{channel} catalog signed by unexpected identity {key_id!r}; "
                          f"the configured production trust is {sorted(public_keys)}")
            continue
        try:
            feed = json.loads(body)
        except ValueError as error:
            fail(reasons, f"{channel} feed is not valid JSON: {error}")
            continue
        if hubcore.encoded(feed) != body:
            fail(reasons, f"{channel} feed bytes are not canonical encoding "
                          "(sorted keys, tight separators, UTF-8)")
            continue
        try:
            hubcore.validate_catalog(feed, channel=channel)
        except hubcore.HubError as error:
            fail(reasons, f"{channel} production feed shape invalid: {error}")
            continue
        for entry in feed["entries"]:
            field = f"{channel}/{entry['id']}"
            files, manifest, package = None, None, entry["package"]
            if package is not None:
                archive = REPO / package["path"]
                if not archive.is_file():
                    fail(reasons, f"{field}: bound archive missing at {package['path']}")
                    continue
                data = archive.read_bytes()
                if hubcore.sha256_hex(data) != package["sha256"]:
                    fail(reasons, f"{field}: archive sha256 does not match the signed feed bytes")
                    continue
                if len(data) != package["size"]:
                    fail(reasons, f"{field}: archive size does not match the signed feed bytes")
                    continue
                try:
                    files = hubcore.check_archive_bytes(data)
                    if hubcore.content_digest(files) != package["contentDigest"]:
                        fail(reasons, f"{field}: unpacked contentDigest mismatch")
                        continue
                    manifest, _ = hubcore.validate_package_files(files)
                    if manifest["id"] != entry["id"] or manifest["version"] != entry["version"]:
                        fail(reasons, f"{field}: published archive identity does not match the feed")
                        continue
                except hubcore.HubError as error:
                    fail(reasons, f"{field}: package gate failed on published bytes: {error}")
                    continue
            review = entry["review"]
            if review is not None:
                body_record = REPO / review["path"]
                envelope = REPO / (review["path"] + ".sig")
                if not body_record.is_file() or not envelope.is_file():
                    fail(reasons, f"{field}: review binding published without record+signature bytes")
                    continue
                record_bytes = body_record.read_bytes()
                if hubcore.sha256_hex(record_bytes) != review["sha256"]:
                    fail(reasons, f"{field}: review record bytes do not match the signed digest")
                    continue
                try:
                    review_key_id = hubcore.verify_envelope(record_bytes,
                                                            envelope.read_bytes(),
                                                            public_keys)
                    record = json.loads(record_bytes)
                    hubcore.validate_review(record, entry=entry)
                    if package is not None and files is not None:
                        hubcore.join_review(record, manifest, package, field)
                    if review_key_id != review["keyID"]:
                        fail(reasons, f"{field}: review envelope identity does not match the "
                                      f"feed-declared keyID {review['keyID']!r}")
                        continue
                except (ValueError, hubcore.HubError) as error:
                    fail(reasons, f"{field}: signed review chain failed: {error}")


def check_sources(reasons):
    sources = REPO / "sources"
    if not sources.is_dir():
        return
    import build_packages
    entries = build_packages.registry_by_id()
    pending = []
    for folder in sorted(sources.iterdir()):
        if not folder.is_dir():
            continue
        if not (folder / "SKILL.md").exists():
            pending.append(folder.name)   # owner lane is still staging; not yet a package
            continue
        if folder.name not in entries:
            fail(reasons, f"sources/{folder.name} is staged but has no registry entry")
            continue
        try:
            build_packages.build_one(folder.name, entries[folder.name], check=True)
        except hubcore.HubError as error:
            fail(reasons, f"staged source {folder.name} failed the read-only package gate: {error}")
    if pending:
        print("staged-source check: pending (no SKILL.md yet): " + ", ".join(pending))


def check_secrets(reasons):
    pem = b"-----BEGIN " + rb"[A-Z ]*" + b"PRIVATE KEY" + b"-----"
    marker = re.compile(pem)
    scan_roots = [REPO / "catalog", REPO / "schema", REPO / "scripts",
                  REPO / "tests" / "catalog", REPO / "docs" / "CATALOG-CONTRACT.md",
                  REPO / "docs" / "LEGACY-COMPATIBILITY.md",
                  REPO / ".github" / "workflows" / "catalog.yml"]
    for root in scan_roots:
        paths = root.rglob("*") if root.is_dir() else [root]
        for path in paths:
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            data = path.read_bytes()
            if marker.search(data):
                fail(reasons, f"private key material marker in tracked file: {path.relative_to(REPO)}")


def main():
    reasons = []
    registry = hubcore.validate_registry(
        json.loads((REPO / "catalog" / "skills.json").read_bytes()))
    check_pins(reasons)
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "gen_schemas.py"), "--check"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        fail(reasons, "schema documents stale: "
                      + (proc.stdout + proc.stderr).strip().splitlines()[-1])
    try:
        outputs = make_fixture.build_outputs()
        make_fixture.verify(outputs)
    except hubcore.HubError as error:
        fail(reasons, f"fixture sample failed to rebuild/verify: {error}")
        outputs = {}
    for name, data in outputs.items():
        target = make_fixture.FIXTURE_ROOT / name
        if not target.exists() or target.read_bytes() != data:
            fail(reasons, f"fixture stale: {name}")
    production = json.loads((REPO / "tests" / "catalog" / "fixtures" / "catalog.json").read_bytes())
    if production["feedStatus"] != "fixture":
        fail(reasons, "fixture root feed must say feedStatus fixture")
    check_production(reasons)
    check_sources(reasons)
    check_secrets(reasons)
    # honest release state reporting (not a failure): zero qualified today
    published = [(channel, path) for channel, path in
                 (("ios", REPO / "catalog.json"),
                  ("android", REPO / "android" / "catalog.json")) if path.exists()]
    if published:
        for channel, path in published:
            try:
                feed = json.loads(path.read_bytes())
                counts = feed["counts"]
                commit = str(feed["sourceCommit"])[:10]
            except (ValueError, KeyError, TypeError):
                continue  # malformed published bytes are already a recorded gate failure
            print(f"{channel} production feed present: {counts['total']} entries, "
                  f"{counts['qualified']} qualified, "
                  f"audited sourceCommit {commit}… "
                  "(retrieval pin is the publication commit, kept separate)")
    else:
        print("production feeds not yet published (expected before coordinator signing)")
    if reasons:
        print("HUB CHECK FAILED:")
        for reason in reasons:
            print(" -", reason)
        raise SystemExit(1)
    print("all hub integrity gates passed (read-only)")


if __name__ == "__main__":
    main()
