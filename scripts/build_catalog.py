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

import hubcore
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
        prefix = "" if channel == "ios" else "android/"
        out[prefix + "catalog.json"] = catalog_bytes
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
            if name.endswith("catalog.json"):
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
