#!/usr/bin/env python3
"""Read-only Hub integrity gate for CI and lanes (H1). Never writes, never signs.

Checks performed (fail closed, aggregate report):
  1. registry structural validation (43/4/39/9, bilingual, statuses, blockers)
  2. upstream pins equal the coordinator's docs/UPSTREAM-PINS.json baselines
     (repository default or reviewed per-entry skillOverrides baseline, exact)
  3. schema documents are byte-stable against the validator (gen_schemas --check)
  4. fixture sample rebuilds identically and every signature/digest/join verifies
  5. production publication, when any production artifact exists, is verified
      standalone from the published bytes: both channel feed+signature pairs,
      each signature exact-byte verified under the configured public-key.json
      trust (never the fixture identity), canonical schema-valid feeds carrying
      a 40-hex audited sourceCommit X (external publication pin Y is where these
      bytes live; X is never compared against a mutable HEAD), and every bound
      package/review re-joined against the actual published archive and record
      bytes. A package embedding references/engine-dependency.json
      additionally binds the managed raw runtime descriptor and artifact bytes
      at Y (strict known-component gate, exact size/SHA/static-ELF). A valid
      publication is NOT invalidated by pending candidate-HEAD changes, and an
      unreviewed candidate can never carry an install offer inside the signed
      feed.
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
import catalog_views as cv
import make_fixture
import runtime_dependency
import upstream_pins

REPO = HERE.parents[1]


def fail(reasons, message):
    reasons.append(message)


def check_pins(reasons):
    """Registry commits vs the coordinator's reviewed pins (per-entry contract).

    Strict byte parsing (duplicate keys, oversized/bad-UTF-8 input, fake
    dates, malformed ids/commits) and effective-pin equality live in
    upstream_pins so trusted lanes share one contract: an entry must equal
    its explicit reviewed skillOverrides baseline, else its repository
    default — exact equality either way, and with no overrides present the
    gate behaves byte-for-byte like the original repository-only check.
    """
    try:
        doc = upstream_pins.load_pins_file(REPO / upstream_pins.PINS_DOC_RELATIVE_PATH)
    except upstream_pins.UpstreamPinError as error:
        fail(reasons, f"docs/UPSTREAM-PINS.json invalid: {error}")
        return
    registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
    try:
        reasons.extend(upstream_pins.check_registry_pins(doc, registry))
    except upstream_pins.UpstreamPinError as error:
        fail(reasons, f"docs/UPSTREAM-PINS.json vs registry pin check failed: {error}")


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
    views = cv.VIEWS if any((REPO / path).exists() for view in cv.FULL_VIEWS
                           for path in cv.FEED_PATHS[view]) else cv.LEGACY_VIEWS
    pairs = [(view, REPO / cv.FEED_PATHS[view][0], REPO / cv.FEED_PATHS[view][1])
             for view in views]
    capability_pairs = [(view, REPO / cv.FEED_PATHS[view][0], REPO / cv.FEED_PATHS[view][1])
                        for view in cv.CAPABILITY_VIEWS]
    if not any(path.exists() or sig.exists() for _, path, sig in pairs + capability_pairs):
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
    verified_full = {}

    def verify_feed_bytes(view, path, sig_path):
        """One signed feed pair verified standalone; returns the feed dict."""
        body = path.read_bytes()
        try:
            key_id = hubcore.verify_envelope(body, sig_path.read_bytes(), public_keys)
        except hubcore.HubError as error:
            fail(reasons, f"{view} catalog signature invalid over the exact bytes: {error}")
            return None
        if key_id == hubcore.FIXTURE_KEY_ID:
            fail(reasons, f"{view} catalog signed with the fixture identity: forbidden")
            return None
        if key_id not in public_keys or (hubcore.PRODUCTION_KEY_ID in public_keys
                                         and key_id != hubcore.PRODUCTION_KEY_ID):
            fail(reasons, f"{view} catalog signed by unexpected identity {key_id!r}; "
                          f"the configured production trust is {sorted(public_keys)}")
            return None
        try:
            feed = json.loads(body)
        except ValueError as error:
            fail(reasons, f"{view} feed is not valid JSON: {error}")
            return None
        if hubcore.encoded(feed) != body:
            fail(reasons, f"{view} feed bytes are not canonical encoding "
                          "(sorted keys, tight separators, UTF-8)")
            return None
        try:
            cv.validate_view(feed, view)
        except hubcore.HubError as error:
            fail(reasons, f"{view} production feed shape invalid: {error}")
            return None
        return feed

    def verify_published_entry(entry, channel):
        """Archive/review/runtime re-join for one published feed entry.

        Capacity derives ONLY from this verified, signed bound entry
        (package.profile, present only in capability feeds), never from a
        URL or the mutable candidate registry.
        """
        field = f"{channel}/{entry['id']}"
        files, manifest, package = None, None, entry["package"]
        if package is not None:
            archive = REPO / package["path"]
            if not archive.is_file():
                fail(reasons, f"{field}: bound archive missing at {package['path']}")
                return
            data = archive.read_bytes()
            if hubcore.sha256_hex(data) != package["sha256"]:
                fail(reasons, f"{field}: archive sha256 does not match the signed feed bytes")
                return
            if len(data) != package["size"]:
                fail(reasons, f"{field}: archive size does not match the signed feed bytes")
                return
            try:
                profile = package.get("profile")
                files = hubcore.check_archive_bytes(data, profile=profile)
                if hubcore.content_digest(files) != package["contentDigest"]:
                    fail(reasons, f"{field}: unpacked contentDigest mismatch")
                    return
                manifest, _ = hubcore.validate_package_files(files, profile=profile)
                if manifest["id"] != entry["id"] or manifest["version"] != entry["version"]:
                    fail(reasons, f"{field}: published archive identity does not match the feed")
                    return
            except hubcore.HubError as error:
                fail(reasons, f"{field}: package gate failed on published bytes: {error}")
                return
        review = entry["review"]
        if review is not None:
            body_record = REPO / review["path"]
            envelope = REPO / (review["path"] + ".sig")
            if not body_record.is_file() or not envelope.is_file():
                fail(reasons, f"{field}: review binding published without record+signature bytes")
                return
            record_bytes = body_record.read_bytes()
            if hubcore.sha256_hex(record_bytes) != review["sha256"]:
                fail(reasons, f"{field}: review record bytes do not match the signed digest")
                return
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
                    return
            except (ValueError, hubcore.HubError) as error:
                fail(reasons, f"{field}: signed review chain failed: {error}")
        # Managed raw runtime artifact binding: when the authenticated
        # package embeds references/engine-dependency.json, the published
        # frozen descriptor at Y must match it byte-identically and the
        # referenced raw artifact must exist at Y with the exact size,
        # SHA-256 and safe static-ELF shape. Reads only the published
        # bytes — never a mutable candidate HEAD.
        if files is not None:
            runtime_blob = files.get(runtime_dependency.EMBEDDED_DESCRIPTOR_REL)
            if runtime_blob is not None:
                try:
                    runtime_dependency.bind_package_descriptor(
                        runtime_blob, REPO, field)
                except hubcore.HubError as error:
                    fail(reasons, f"{field}: runtime artifact binding failed: {error}")

    for channel, path, sig_path in pairs:
        if not path.is_file():
            fail(reasons, f"{channel} channel published but feed missing: {path.relative_to(REPO)}")
            continue
        if not sig_path.is_file():
            fail(reasons, f"{channel} feed published without its signature: "
                          f"{sig_path.relative_to(REPO)} is missing (an absent signature never passes)")
            continue
        feed = verify_feed_bytes(channel, path, sig_path)
        if feed is None:
            continue
        if channel in cv.FULL_VIEWS:
            verified_full[channel] = feed
        for entry in feed["entries"]:
            verify_published_entry(entry, channel)

    # Same-Y signed capability feeds are conditional: any present pair is
    # verified standalone (official identity, canonical, capability shape)
    # and MUST be an exact superset of the corresponding verified standard
    # full feed. Partial pairs and capability-without-full fail closed;
    # absence keeps every historical publication valid.
    for view, path, sig_path in capability_pairs:
        if not path.exists() and not sig_path.exists():
            continue
        if not path.is_file() or not sig_path.is_file():
            fail(reasons, f"{view}: incomplete capability publication (feed or "
                          "signature missing); an absent signature never passes")
            continue
        feed = verify_feed_bytes(view, path, sig_path)
        if feed is None:
            continue
        full_view = cv.full_view_for(view)
        full_feed = verified_full.get(full_view)
        if full_feed is None:
            fail(reasons, f"{view}: capability feed published without a verified "
                          f"standard full feed ({full_view})")
            continue
        try:
            hubcore.validate_capability_projection(feed, full_feed)
        except hubcore.HubError as error:
            fail(reasons, f"{view}: capability projection invalid: {error}")
            continue
        for entry in feed["entries"]:
            verify_published_entry(entry, view)

    if views == cv.VIEWS and all(path.is_file() for _, path, _ in pairs):
        try:
            projection_map = {str(path.relative_to(REPO)): path.read_bytes()
                              for _, path, _ in pairs}
            projection_map.update({str(path.relative_to(REPO)): path.read_bytes()
                                   for _, path, _ in capability_pairs
                                   if path.is_file()})
            cv.assert_projection(projection_map)
        except hubcore.HubError as error:
            fail(reasons, f"catalog projection invalid: {error}")


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
