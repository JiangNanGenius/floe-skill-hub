#!/usr/bin/env python3
"""Deterministic channel-feed builder (H1). Never touches production secrets.

Usage:
  python3 scripts/build_catalog.py --mode preview --source-commit <X sha40> --out-root DIR
  python3 scripts/build_catalog.py --mode preview --source-commit <X sha40> --check
  python3 scripts/build_catalog.py --mode release --source-commit <X sha40> --check \
      --source-snapshot <frozen X fetch>
  python3 scripts/build_catalog.py --mode release --source-commit <X sha40> \
      --source-snapshot <frozen X fetch> --out-root DIR --sign-env <ENV>
                                          # (coordinator publication run only)
Modes:
  preview  describes all 43 candidates; no entry offers an unqualified install.
  release  includes only qualified entries with verified signed reviews and
           refuses outright when nothing is qualified yet (fail closed). Release
           input (registry/archives/reviews) comes only from --source-snapshot,
           a frozen fetch of the audited X, never from the mutable candidate tree.
Release offer policy: the four App-provided builtin ids (floe-pdf, floe-office,
           floe-network, floe-video) are native App features and are never Hub
           download offers, so a release feed carries every genuinely qualified
           NON-builtin row and never references the four builtin archives or
           reviews. Each admitted offer carries status.published=true in the
           FEED only (a deep-copied status block); the source registry object
           is never mutated and its candidate rows keep published=false.
Android portable-guide projection: a production Android feed entry may carry
minimumAppVersion="0.0.0" ONLY for the frozen known-reviewed portable-guide
ids (ANDROID_PORTABLE_GUIDE_IDS below) when the ACTUAL bound package manifest
re-declared from the exact frozen archive bytes proves instruction-only,
linux-declared, script-free, tool-free, dependency-free content under the
basic workspace capability ceiling, joined to a static-content review with an
empty unproven execution claim. iOS entries are never touched; registries and
archives never change; feeds built over the reviewed original ios-only
manifest baseline rebuild byte-identical through this code. "0.0.0" is a
content-floor SENTINEL: a valid strict semantic version accepted unchanged by
hubcore.validate_catalog and the published schema, below every possible
client version, so it honestly means "no SDK-specific content floor for this
instruction-only package" — never a claim that any old App build supports
the Hub UI or the installed behavior. An entry whose floor already is the
sentinel is never re-projected.
Source semantics: --source-commit is the audited source revision X signed
into the feed as provenance. The immutable publication revision Y that will
contain the emitted feed/ZIP/review bytes is resolved externally by the
publication run (git ref resolution AFTER committing) — this builder never
claims Y and never demands X == Y. --hub-commit is a deprecated alias for
--source-commit with exactly the same meaning.
Trust: review and catalog signatures are verified only against the approved
public trust configuration `public-key.json` (keyID -> public Ed25519 key).
Keys advertised inside a catalog or fixture are never trust. With --sign-env,
the public identity derived from the supplied signing key must equal the
configured production trust key before anything signs; otherwise the run
refuses. The root production catalog.json/catalog.sig and android pair are
written only by the coordinator publication run with the signing secret
present; worker builds target --out-root or --check in memory. This builder
never fabricates a signature and never emits a committed production catalog.
"""
import argparse
import base64
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import dependency_declaration
import hubcore
import catalog_views
import publication_immutability
import runtime_dependency

REPO = pathlib.Path(__file__).resolve().parents[1]


def load_trust(root=REPO):
    """Approved PUBLIC trust configuration only: public-key.json at the repo
    root (shape identical to the legacy skill-hub key file). Returns
    {keyID: base64 raw public key}. Fail-closed empty map when no trust file
    is configured — release builds then refuse any signed review rather than
    trusting catalog-advertised material."""
    path = pathlib.Path(root) / "public-key.json"
    if not path.is_file():
        return {}
    doc = json.loads(path.read_bytes())
    if not isinstance(doc, dict) or set(doc) != {"keyID", "publicKey"}:
        raise hubcore.HubError("public-key.json must contain exactly keyID and publicKey")
    key_id = doc["keyID"]
    if not isinstance(key_id, str) or not 1 <= len(key_id) <= 64:
        raise hubcore.HubError("public-key.json keyID must be a 1-64 character string")
    if key_id == hubcore.FIXTURE_KEY_ID:
        raise hubcore.HubError("the fixture identity can never be the configured trust root")
    try:
        raw = base64.b64decode(doc["publicKey"], validate=True)
    except Exception:
        raise hubcore.HubError("public-key.json publicKey must be strict base64") from None
    if len(raw) != 32:
        raise hubcore.HubError("public-key.json publicKey must decode to a raw 32-byte Ed25519 key")
    return {key_id: doc["publicKey"]}


def load_registry(root=REPO):
    return json.loads((pathlib.Path(root) / "catalog" / "skills.json").read_bytes())


def bind_package(entry, packages_root):
    """Compute the released package binding from immutable archive bytes.

    When the archive embeds references/engine-dependency.json (the managed raw
    runtime descriptor), it is strictly validated against the frozen tree
    descriptor and the actual artifact bytes at packages_root — the same
    immutable root the archive itself came from (release: the frozen X
    snapshot; preview: the candidate tree).
    """
    if not entry["status"]["packaged"]:
        return None, None, None
    if entry["upstream"] and entry["upstream"]["licenseStatus"] == "blocked-no-upstream-license":
        raise hubcore.HubError(f"{entry['id']}: license-blocked entries can never be packaged")
    version = entry["versionTarget"]
    bindings = {}
    for channel in entry["plannedRuntime"]["installPlatforms"]:
        rel = hubcore.package_path_for(entry["id"], version, channel)
        archive = packages_root / rel
        if not archive.is_file():
            raise hubcore.HubError(f"{entry['id']}: packaged entry has no archive at {rel}")
        data = archive.read_bytes()
        files = hubcore.check_archive_bytes(data)
        manifest, _ = hubcore.validate_package_files(files)
        if manifest["id"] != entry["id"] or manifest["version"] != version:
            raise hubcore.HubError(f"{entry['id']}: archive identity drift")
        planned_caps = set(entry["plannedRuntime"]["capabilities"])
        if not set(manifest["capabilities"]) <= planned_caps:
            raise hubcore.HubError(f"{entry['id']}: archive declares capabilities outside the plan")
        planned_tools = set(entry["plannedRuntime"]["tools"])
        if not set(manifest["tools"]) <= planned_tools:
            raise hubcore.HubError(f"{entry['id']}: archive declares tools outside the plan")
        bindings[channel] = {
            "path": rel,
            "size": len(data),
            "sha256": hubcore.sha256_hex(data),
            "contentDigest": hubcore.content_digest(files),
            "containsScripts": any(n.startswith("scripts/") for n in files),
        }
    runtime_blob = files.get(runtime_dependency.EMBEDDED_DESCRIPTOR_REL)
    if runtime_blob is not None:
        runtime_dependency.bind_package_descriptor(runtime_blob, packages_root, entry["id"])
    # Re-run the author-contract preflight on the exact frozen bytes this
    # release would publish (never trust the producer's earlier pass): a
    # declaration must still mirror the native decoder and the entry must
    # carry the raised minimumAppVersion for the new native behavior.
    dependency_declaration.assert_declaration_gates(entry, files, entry["id"])
    return bindings, manifest, files


def bind_review(entry, reviews_root, public_keys, package_binding=None, manifest=None,
                channel="ios"):
    review_path = f"reviews/{entry['id']}/{entry['versionTarget']}.review.json"
    body = reviews_root / review_path
    sig = reviews_root / (review_path + ".sig")
    if not entry["status"]["reviewed"]:
        if body.exists() or sig.exists():
            raise hubcore.HubError(f"{entry['id']}: review records exist but status is not reviewed")
        return None
    if not body.is_file() or not sig.is_file():
        raise hubcore.HubError(f"{entry['id']}: reviewed entry requires the record and its .sig")
    record_bytes = body.read_bytes()
    if hubcore.encoded(json.loads(record_bytes)) != record_bytes:
        raise hubcore.HubError(f"{entry['id']}: review record must be canonical bytes")
    key_id = hubcore.verify_envelope(record_bytes, sig.read_bytes(), public_keys)
    record = json.loads(record_bytes)
    hubcore.validate_review(record)
    if record["id"] != entry["id"] or record["version"] != entry["versionTarget"]:
        raise hubcore.HubError(f"{entry['id']}: review identity drift")
    if package_binding is None or manifest is None:
        raise hubcore.HubError(f"{entry['id']}: a review requires the actual package binding")
    # Join the signed record to the REAL archive and manifest for this build —
    # never to the registry's planned placeholders or the signature alone.
    hubcore.join_review(record, manifest, package_binding, f"{entry['id']}")
    return {"path": review_path, "sha256": hubcore.sha256_hex(record_bytes), "keyID": key_id}


# ---------------------------------------------------------------------------
# Android portable-guide floor projection (server feed policy only)
# ---------------------------------------------------------------------------
#
# Root decision (2026-10-28, the user's Android fast path; final revision the
# same day): the Android marketing version domain (0.1.0-alpha.x) must never
# inherit the iOS 1.7.59 content floor for known-reviewed, instruction-only
# portable guides that carry no App-SDK-specific code, tools or dependencies.
# The projection encodes that as the valid string floor "0.0.0" — a content-
# floor sentinel every client version clears — NOT null: the unchanged
# hubcore.validate_catalog clause "packaged entries require
# minimumAppVersion" and the native schema-3 decoder both reject a null floor,
# and neither the validator nor the schema is relaxed for this. The waiver is
# pinned by EXACT literal ids here, in trusted tooling — the same pattern as
# sign_publication's MANDATORY_DEEP_IDS — never by a registry relabel, a
# candidate-supplied allow flag or the planned runtime; a new or unrecognized
# curated id can never inherit the waiver automatically. Eligibility is
# evaluated ONLY against the actual bound frozen package and review that
# bind_package/bind_review joined for this exact feed build (re-hashed here so
# a mid-run byte disagreement fails closed); every other case — scripted
# packages, non-empty tools or pythonPackages, capabilities beyond the basic
# ceiling, an ios-only manifest, a wrong review stage, a guest execution
# claim, a missing binding — keeps the registry floor byte-unchanged. The iOS
# feed never enters this path, licenses and the permission policy do not move,
# and tools/capability/discovery enforcement stays in the unchanged
# join/install validators that already governed these entries. An entry
# already carrying the sentinel floor is never re-projected.
ANDROID_PORTABLE_GUIDE_IDS = frozenset({
    "construction-estimate-builder", "construction-change-order-processor",
    "construction-bid-compass", "variance-analysis", "review-contract",
    "proposal-builder", "hiring-screener", "process-mapper", "senior-pm",
    "lesson-plan-builder", "study-plan-scheduler", "k12-check-for-understanding",
    "travel-points-calculator",
    "a11y-audit", "code-to-prd", "composition-patterns", "content-production",
    "copy-editing", "copywriting", "deep-research", "deepread",
    "doc-coauthoring", "floe-email-drafting", "floe-file-organizer",
    "floe-invoice-organizer", "internal-comms", "meetings", "product-discovery",
    "product-manager-toolkit", "react-best-practices", "requesting-code-review",
    "research-summarizer", "scientific-critical-thinking", "social-content",
    "systematic-debugging", "test-driven-development", "theme-factory",
    "ui-design-system", "ux-researcher-designer", "web-design-guidelines",
    "writing-guidelines",
})
ANDROID_PORTABLE_GUIDE_CAPABILITY_CEILING = frozenset(
    {"workspace.read", "workspace.write"})
ANDROID_PORTABLE_GUIDE_REVIEW_STAGE = "static-content-reviewed"
ANDROID_PORTABLE_GUIDE_EXECUTION = {"os": None, "arch": "n/a", "evidence": "unproven"}
# The projected floor: a strict X.Y.Z string (passes require_version, the
# unchanged validator clause for packaged entries and the published schema
# unchanged) whose value is deliberately below every possible client version,
# so it asserts "no SDK-specific content floor for this instruction-only
# guide" and nothing about any old build's Hub UI or installer support.
ANDROID_PORTABLE_GUIDE_CONTENT_FLOOR = "0.0.0"


def android_portable_guide_eligible(manifest, review_record):
    """True only when the bound facts prove portable instruction-only content.

    Pure over the given dicts (mutates nothing): the manifest must declare the
    linux platform with scriptRuntime "none", no tools, no pythonPackages and
    capabilities inside the basic workspace ceiling, and the review record
    must be static-content-reviewed carrying the empty unproven execution
    claim. Any absent or extra feature returns False and the caller keeps the
    registry floor unchanged.
    """
    if manifest.get("scriptRuntime") != "none":
        return False
    if "linux" not in (manifest.get("platforms") or []):
        return False
    if manifest.get("tools") or manifest.get("pythonPackages"):
        return False
    if not set(manifest.get("capabilities") or []) <= ANDROID_PORTABLE_GUIDE_CAPABILITY_CEILING:
        return False
    if review_record.get("reviewStage") != ANDROID_PORTABLE_GUIDE_REVIEW_STAGE:
        return False
    if review_record.get("execution") != ANDROID_PORTABLE_GUIDE_EXECUTION:
        return False
    return True


def _rebound_portable_guide_facts(entry, packages_root, reviews_root):
    """Re-read and re-gate the exact bound bytes behind one feed entry.

    bind_package/bind_review validated these paths earlier in the same run;
    the re-hash proves the projection sees the identical immutable bytes, and
    the author-contract, review-shape and archive-join gates re-run on those
    bytes before any floor may be waived. Any disagreement raises fail closed.
    """
    package = entry["package"]
    try:
        data = (packages_root / package["path"]).read_bytes()
    except OSError as error:
        raise hubcore.HubError(
            f"{entry['id']}: projection cannot read the bound archive: {error}") from None
    if len(data) != package["size"] or hubcore.sha256_hex(data) != package["sha256"]:
        raise hubcore.HubError(f"{entry['id']}: bound archive bytes drifted during the feed build")
    files = hubcore.check_archive_bytes(data)
    if hubcore.content_digest(files) != package["contentDigest"]:
        raise hubcore.HubError(
            f"{entry['id']}: bound archive contentDigest drifted during the feed build")
    manifest, _ = hubcore.validate_package_files(files)
    if manifest["id"] != entry["id"] or manifest["version"] != entry["version"]:
        raise hubcore.HubError(f"{entry['id']}: projection archive identity drift")
    review = entry["review"]
    try:
        record_bytes = (reviews_root / review["path"]).read_bytes()
    except OSError as error:
        raise hubcore.HubError(
            f"{entry['id']}: projection cannot read the bound review: {error}") from None
    if hubcore.sha256_hex(record_bytes) != review["sha256"]:
        raise hubcore.HubError(f"{entry['id']}: bound review bytes drifted during the feed build")
    record = json.loads(record_bytes)
    if hubcore.encoded(record) != record_bytes:
        raise hubcore.HubError(f"{entry['id']}: review record must be canonical bytes")
    hubcore.validate_review(record)
    hubcore.join_review(record, manifest, package, entry["id"])
    return manifest, record


def project_android_portable_guide_feed(feed, packages_root, reviews_root):
    """Return a projected copy of the validated Android feed, or None.

    Pure: `feed` and every nested structure stay untouched. None (keep the
    caller's exact bytes) is returned when no entry's floor is genuinely
    waivable, so the reviewed original ios-only-manifest publication
    rebuilds byte-identical through this code path. When a projection
    does occur, only the eligible Android entry's minimumAppVersion becomes
    the content-floor sentinel "0.0.0" — a valid strict X.Y.Z string the
    unchanged validator and schema accept — and the caller re-runs the FULL
    unchanged hubcore.validate_catalog over the projected bytes. An entry
    already carrying the sentinel is never re-projected; nothing else about
    archive, review, version, status or offers moves.
    """
    entries = []
    changed = False
    for entry in feed["entries"]:
        if (entry["id"] in ANDROID_PORTABLE_GUIDE_IDS and entry["package"] is not None
                and entry["review"] is not None
                and entry["minimumAppVersion"] not in
                (None, ANDROID_PORTABLE_GUIDE_CONTENT_FLOOR)):
            manifest, record = _rebound_portable_guide_facts(entry, packages_root,
                                                             reviews_root)
            if android_portable_guide_eligible(manifest, record):
                entry = dict(entry,
                             minimumAppVersion=ANDROID_PORTABLE_GUIDE_CONTENT_FLOOR)
                changed = True
        entries.append(entry)
    if not changed:
        return None
    return dict(feed, entries=entries)


def project_legacy_catalog(registry, feed):
    """Keep the original planning cohort readable by 1...43 clients.

    The input is already fully bound and validated; projection preserves each
    retained row byte-for-byte in structure and recomputes only feed counts.
    Production registry validation pins each legacy number to its original id.
    """
    rows = [entry for entry in feed["entries"]
            if entry["planNumber"] <= len(hubcore.LEGACY_PLAN_IDS)]
    return hubcore.build_catalog(
        registry, feed["channel"], feed["feedStatus"], rows,
        feed["sourceCommit"], generated_note=feed.get("generatedNote"))


def build(registry, mode, source_commit, packages_root, reviews_root, public_keys):
    out = {}
    for channel in ("ios", "android"):
        entries = []
        for reg_entry in sorted(registry["skills"], key=lambda e: e["planNumber"]):
            planned = reg_entry["plannedRuntime"]
            if channel not in planned["installPlatforms"]:
                continue
            package = None
            review = None
            offer = "none"
            if mode == "release":
                if not reg_entry["status"]["qualified"]:
                    continue  # a release catalog carries only qualified entries
                if hubcore.is_download_offer_excluded(reg_entry["id"]):
                    # App-provided builtins are native App features, never Hub
                    # download offers; their registry rows stay valid,
                    # reviewable data but are not admitted to the feed.
                    continue
                package_bindings, manifest, files = bind_package(reg_entry, packages_root)
                if package_bindings is None:
                    raise hubcore.HubError(
                        f"{reg_entry['id']}: qualified entry is missing its package binding")
                package = package_bindings[channel]
                review = bind_review(reg_entry, reviews_root, public_keys,
                                     package_binding=package, manifest=manifest,
                                     channel=channel)
                if review is None:
                    raise hubcore.HubError(
                        f"{reg_entry['id']}: release requires a verified review")
                offer = "qualified"
                # A qualified feed entry ships the reviewed package's actual
                # manifest values, never the registry's planned placeholders.
                runtime = dict(reg_entry["plannedRuntime"])
                runtime["scriptRuntime"] = manifest["scriptRuntime"]
                runtime["capabilities"] = manifest["capabilities"]
                runtime["tools"] = manifest["tools"]
                runtime["pythonPackagesPlan"] = [p["spec"] for p in manifest["pythonPackages"]]
                runtime["installPlatforms"] = [channel]
                # The signed release feed is the publication act itself: every
                # qualified download offer carries published=true HERE, while
                # the candidate registry blob keeps asserting only source
                # progress (published stays false there — the website
                # candidate pipeline refuses a published claim in registry
                # data). The status block is deep-copied so the caller's
                # registry object is never mutated.
                reg_entry = dict(reg_entry, plannedRuntime=runtime,
                                 status=dict(reg_entry["status"], published=True))
                # Stage BOTH the exact validated frozen descriptor bytes and
                # the raw artifact bytes into the publication output, each at
                # its exact descriptor-relative path, so a fresh output root
                # (Y) can bind the runtime package standalone without any
                # manual descriptor copy. The bytes come ONLY from the frozen
                # X snapshot already validated by bind_package — never from a
                # mutable checkout (a stale/tampered candidate-tree descriptor
                # can therefore never leak into Y) — and never via a broad
                # recursive engine copy.
                runtime_blob = files.get(runtime_dependency.EMBEDDED_DESCRIPTOR_REL)
                if runtime_blob is not None:
                    descriptor = runtime_dependency.parse_descriptor(
                        runtime_blob, reg_entry["id"])
                    artifact_rel = descriptor["artifact"]["path"]
                    frozen_bytes = runtime_dependency.load_frozen_descriptor_bytes(
                        packages_root, reg_entry["id"])
                    if frozen_bytes != runtime_blob:
                        raise hubcore.HubError(
                            f"{reg_entry['id']}: frozen snapshot descriptor "
                            f"disagrees with the authenticated embedded descriptor")
                    out[runtime_dependency.FROZEN_DESCRIPTOR_REL] = frozen_bytes
                    out[artifact_rel] = runtime_dependency.load_artifact(
                        packages_root, descriptor, reg_entry["id"])
            elif reg_entry["status"]["packaged"]:
                package_bindings, manifest, _files = bind_package(reg_entry, packages_root)
                if package_bindings is not None:
                    package = package_bindings[channel]
                    review = bind_review(reg_entry, reviews_root, public_keys,
                                         package_binding=package, manifest=manifest,
                                         channel=channel)
            entries.append(hubcore.catalog_entry(
                reg_entry, package=package, review=review, install_offer=offer))
        if mode == "release" and not entries:
            raise hubcore.HubError(
                "release mode refuses to emit an empty catalog: no entry is qualified yet")
        feed = hubcore.build_catalog(registry, channel, "production", entries,
                                     source_commit)
        catalog_bytes = hubcore.encoded(feed)
        hubcore.validate_catalog(json.loads(catalog_bytes), channel=channel)
        if channel == "android":
            # The floor-retaining feed above validated in full; projecting the
            # Android content floor re-gates the exact bound package/review
            # bytes per entry first, and returns None (caller's bytes kept)
            # unless a frozen portable guide genuinely qualifies. The sentinel
            # floor is a valid non-null version string, so the FINAL projected
            # bytes are put back through the same unchanged validate_catalog
            # — nothing is published that the current validator or schema
            # would reject. The iOS feed never reaches this call.
            projected = project_android_portable_guide_feed(feed, packages_root,
                                                            reviews_root)
            if projected is not None:
                catalog_bytes = hubcore.encoded(projected)
                hubcore.validate_catalog(json.loads(catalog_bytes), channel=channel)
        # Complete and legacy views share the same bound rows, source X and
        # archive/review identities. Older clients never receive row 44+.
        full_feed = json.loads(catalog_bytes)
        legacy_feed = project_legacy_catalog(registry, full_feed)
        hubcore.validate_catalog(legacy_feed, channel=channel)
        prefix = "" if channel == "ios" else "android/"
        out[prefix + "catalog-full.json"] = catalog_bytes
        out[prefix + "catalog.json"] = hubcore.encoded(legacy_feed)
    catalog_views.assert_projection(out)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preview", "release"), default="preview")
    parser.add_argument("--source-commit", dest="source_commit", default=None,
                        help="audited source revision X signed into the feed "
                             "(never the publication commit Y)")
    parser.add_argument("--hub-commit", dest="source_commit", default=None,
                        help="deprecated alias for --source-commit (same meaning: X)")
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--source-snapshot", default=None,
                        help="frozen fetch of the audited source commit X (git archive X): "
                             "in release mode the registry, archives and review records are "
                             "read ONLY from this snapshot, so the claimed X honestly binds "
                             "the payload inputs instead of the mutable candidate tree")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--publication-ledger", default=None,
                        help="cumulative publication ledger (default "
                             "catalog/publication-ledger.json under the tooling "
                             "root); mandatory once production history exists")
    parser.add_argument("--published-y", default=None,
                        help="independently resolved 40-hex publication commit Y "
                             "carrying the current published feeds; the immutability "
                             "baseline is then read from that pin instead of the "
                             "tooling working tree, so a stale tooling checkout can "
                             "never hide published history")
    parser.add_argument("--sign-env", default=None,
                        help="environment variable holding the base64 raw Ed25519 "
                             "production key; only honored for a real publication run "
                             "whose derived public identity matches public-key.json")
    args = parser.parse_args()
    commit = args.source_commit
    if commit is None:
        # The feed must always carry the audited source commit X it describes.
        # A published checkout's commit Y is resolved externally by the
        # publication run and never demanded here (no self-reference).
        raise SystemExit("--source-commit (audited source revision X) is required; "
                         "it is provenance, not the commit that will contain the output")
    if args.mode == "release" and args.source_snapshot is None:
        # Honest X binding: a release payload may not be silently regenerated
        # from the mutable candidate tree while claiming an arbitrary X.
        raise SystemExit(
            "release builds require --source-snapshot DIR: a frozen fetch of the audited "
            "source revision X (for example `git archive <X> | tar -x -C DIR`). The "
            "builder then uses exactly the content X names for registry, archives and "
            "review records, and never the pending candidate HEAD.")
    inputs_root = (pathlib.Path(args.source_snapshot)
                   if args.source_snapshot else REPO)
    if not (inputs_root / "catalog" / "skills.json").is_file():
        raise SystemExit(f"source snapshot has no catalog/skills.json: {inputs_root}")
    registry = hubcore.validate_registry(load_registry(inputs_root))
    try:
        public_keys = load_trust(REPO)
    except hubcore.HubError as error:
        raise SystemExit(f"configured public trust is invalid: {error}")
    outputs = build(registry, args.mode, commit, inputs_root, inputs_root, public_keys)
    if args.mode == "release":
        # Publication-boundary immutability: refuse any candidate offer that
        # reuses an already-published (id, version) with a different package
        # contentDigest, even re-signable bytes. The baseline is cumulative
        # and anchored to the signed published bytes at their pinned
        # publication commits, read from the TOOLING root (REPO) — never from
        # the caller's data snapshot X, never from the candidate
        # registry/ledger and never from a caller-supplied review. Production
        # history with a missing or stale ledger fails closed; only a genuine
        # first publication (no verified history anywhere) passes an empty
        # baseline.
        baseline = publication_immutability.build_validated_baseline(
            REPO, args.publication_ledger, args.published_y)
        publication_immutability.assert_immutable_publication(outputs, baseline)
    if args.sign_env:
        value = os.environ.get(args.sign_env)
        if not value:
            raise SystemExit(f"{args.sign_env} is not present; refusing to fabricate a signature")
        key_bytes = base64.b64decode(value, validate=True)
        if len(key_bytes) != 32:
            raise SystemExit(f"{args.sign_env} must hold a base64 raw 32-byte Ed25519 key")
        Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
        key = Ed25519PrivateKey.from_private_bytes(key_bytes)
        derived = base64.b64encode(key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        if hubcore.PRODUCTION_KEY_ID not in public_keys:
            raise SystemExit("refusing to sign: public-key.json does not configure the "
                             f"production trust identity {hubcore.PRODUCTION_KEY_ID!r}")
        if public_keys[hubcore.PRODUCTION_KEY_ID] != derived:
            raise SystemExit("refusing to sign: the signing key's public identity does not "
                             "match the configured trust in public-key.json")
        for name in list(outputs):
            if name in catalog_views.FEED_FILES:
                sig_name = name[: -len(".json")] + ".sig"
                outputs[sig_name] = hubcore.sign_envelope(outputs[name], key,
                                                           hubcore.PRODUCTION_KEY_ID)
    if args.check:
        stale = []
        for name, data in outputs.items():
            path = REPO / name
            if not path.exists() or path.read_bytes() != data:
                stale.append(name)
        if stale:
            raise SystemExit("stale or missing generated catalog outputs: " + ", ".join(stale))
        print("catalog candidate build verified (read-only): " + ", ".join(sorted(outputs)))
        return
    if args.out_root is None:
        raise SystemExit("provide --out-root DIR or --check; this builder never writes the repo root"
                         " without the coordinator publication flags")
    root = pathlib.Path(args.out_root)
    for name, data in outputs.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print("built " + ", ".join(sorted(outputs)))


if __name__ == "__main__":
    main()
