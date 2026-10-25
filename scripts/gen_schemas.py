#!/usr/bin/env python3
"""Emit schema/*.json contract documents derived from scripts/hubcore.py.

The hubcore validator is authoritative behaviour; these files are the frozen
published contract that the iOS/Android native owners and the website read.
Regenerating must be byte-stable; scripts/check_catalog.py fails if the
committed schemas drift from the validator's constants.

python3 scripts/gen_schemas.py [--check]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hubcore

REPO = pathlib.Path(__file__).resolve().parents[1]

DRAFT = "https://json-schema.org/draft/2020-12/schema"

VERSION = {"type": "string", "pattern": r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"}
COMMIT = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
HEX64 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
DATE = {"type": "string", "pattern": r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"}
SKILL_ID = {"type": "string", "pattern": r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", "maxLength": 64}
LOCALE_TEXT = {
    "type": "object", "additionalProperties": False,
    "required": ["en", "zh-Hans"],
    "properties": {"en": {"type": "string"}, "zh-Hans": {"type": "string"}},
}
PY_PKG = {
    "type": "object", "additionalProperties": False,
    "required": ["spec", "purpose", "capabilities"],
    "properties": {
        "spec": {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9._+!-]*$",
                 "description": "exact PyPI name==version; ranges/URLs/VCS are rejected"},
        "purpose": {"type": "string", "minLength": 1, "maxLength": 1024},
        "capabilities": {"type": "array", "minItems": 1, "maxItems": 16, "uniqueItems": True,
                         "items": {"type": "string", "pattern": r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$"}},
    },
}
EXECUTION = {
    "type": "object", "additionalProperties": False, "required": ["os", "arch", "evidence"],
    "properties": {
        "os": {"enum": ["linux", "macos", "ios", None]},
        "arch": {"enum": ["riscv64", "x86_64", "aarch64", "n/a", None]},
        "evidence": {"enum": list(hubcore.EXECUTION_EVIDENCE)},
    },
    "description": "Execution OS/architecture, separate from store/install channels. "
                   "unproven is the only value a candidate may carry.",
}
STATUS = {
    "type": "object", "additionalProperties": False,
    "required": ["sourcePinned", "licenseChecked", "adaptation", "packaged",
                 "reviewed", "qualified", "published", "executionVerified"],
    "properties": {
        "sourcePinned": {"type": "boolean"}, "licenseChecked": {"type": "boolean"},
        "adaptation": {"enum": list(hubcore.ADAPTATION_STAGES)}, "packaged": {"type": "boolean"},
        "reviewed": {"type": "boolean"}, "qualified": {"type": "boolean"},
        "published": {"type": "boolean"}, "executionVerified": {"type": "boolean"},
    },
    "description": "Distinct lifecycle states. reviewed=>licenseChecked; "
                   "qualified=>reviewed+packaged; published=>qualified; "
                   "executionVerified=>frozen adaptation. No state may be inferred from a build.",
}
RUNTIME = {
    "type": "object", "additionalProperties": False,
    "required": ["scriptRuntime", "capabilities", "tools", "installPlatforms",
                 "pythonPackagesPlan", "execution"],
    "properties": {
        "scriptRuntime": {"enum": list(hubcore.SCRIPT_RUNTIMES)},
        "capabilities": {"type": "array", "uniqueItems": True,
                         "items": {"enum": list(hubcore.CAPABILITIES)}},
        "tools": {"type": "array", "uniqueItems": True,
                  "items": {"type": "string",
                            "pattern": r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$"}},
        "installPlatforms": {"type": "array", "minItems": 1, "uniqueItems": True,
                             "items": {"enum": list(hubcore.STORE_CHANNELS)},
                             "description": "store channels only (ios|android); the manifest "
                                            "floe.json platforms remain the native enum"},
        "pythonPackagesPlan": {"type": "array", "items": {"type": "string"}},
        "execution": EXECUTION,
    },
}
UPSTREAM = {
    "type": "object", "additionalProperties": False,
    "required": ["repository", "commit", "path", "skillManifestPath", "retrievedAt",
                 "licenseStatus", "licenseEvidencePath", "repositoryLicense", "licenseNote"],
    "properties": {
        "repository": {"type": "string",
                       "pattern": r"^https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$"},
        "commit": COMMIT, "path": {"type": "string", "pattern": "^[^/][^.]*$"},
        "skillManifestPath": {"type": "string"},
        "retrievedAt": DATE,
        "licenseStatus": {"enum": [s for s in hubcore.LICENSE_STATUSES if s != "floe-owned"]},
        "licenseEvidencePath": {"type": ["string", "null"]},
        "repositoryLicense": {"type": "string"},
        "licenseNote": LOCALE_TEXT,
    },
    "description": "A pin is the review baseline, not a blanket license: verified still "
                   "requires the per-file audit at packaging; blocked entries can never package.",
}
FIRSTPARTY = {
    "type": "object", "additionalProperties": False,
    "required": ["repository", "commit", "path", "skillManifestPath", "retrievedAt",
                 "licenseStatus", "licenseEvidencePath", "releasedVersion", "stagedSourceVersion"],
    "properties": {
        "repository": {"type": "string"}, "commit": COMMIT, "path": {"type": "string"},
        "skillManifestPath": {"type": "string"}, "retrievedAt": DATE,
        "licenseStatus": {"const": "floe-owned"}, "licenseEvidencePath": {"type": ["string", "null"]},
        "releasedVersion": {"oneOf": [VERSION, {"type": "null"}]},
        "stagedSourceVersion": {"oneOf": [VERSION, {"type": "null"}]},
    },
    "description": "First-party pin; released and staged versions are recorded separately "
                   "(e.g. floe-office released 1.3.0, staged 1.5.0 — never conflated).",
}
PACKAGE = {
    "type": "object", "additionalProperties": False,
    "required": ["path", "size", "sha256", "contentDigest", "containsScripts"],
    "properties": {
        "path": {"type": "string", "pattern": "^(?:android/)?packages/[a-z][a-z0-9-]*/(?:0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)/[a-z][a-z0-9-]*\\.zip$"},
        "size": {"type": "integer", "minimum": 1, "maximum": 8388608},
        "sha256": HEX64, "contentDigest": HEX64, "containsScripts": {"type": "boolean"},
    },
    "description": "contentDigest = SHA256 over sorted big-endian u64-length-prefixed "
                   "path+bytes of the unpacked files; sha256 = over the exact archive bytes.",
}
REVIEW_REF = {
    "type": "object", "additionalProperties": False,
    "required": ["path", "sha256", "keyID"],
    "properties": {"path": {"type": "string", "pattern": "^reviews/.+\\.review\\.json$"},
                   "sha256": HEX64, "keyID": {"type": "string"}},
}

CATALOG_ENTRY = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "planNumber", "kind", "source", "name", "description", "category",
                 "tags", "deepAdaptation", "upstream", "firstParty", "runtime", "version",
                 "minimumAppVersion", "status", "notes", "package", "review", "installOffer"],
    "properties": {
        "id": SKILL_ID, "planNumber": {"type": "integer", "minimum": 1, "maximum": 43},
        "kind": {"enum": list(hubcore.ENTRY_KINDS)},
        "source": {"enum": list(hubcore.SOURCE_CODES)},
        "name": LOCALE_TEXT, "description": LOCALE_TEXT,
        "category": {"enum": list(hubcore.CATEGORIES)},
        "tags": {"type": "array", "minItems": 2, "maxItems": 12, "uniqueItems": True,
                 "items": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9.-]*$"}},
        "deepAdaptation": {"type": "boolean"},
        "upstream": {"oneOf": [UPSTREAM, {"type": "null"}]},
        "firstParty": {"oneOf": [FIRSTPARTY, {"type": "null"}]},
        "runtime": RUNTIME, "version": VERSION,
        "minimumAppVersion": {"oneOf": [VERSION, {"type": "null"}]},
        "status": STATUS, "notes": LOCALE_TEXT,
        "package": {"oneOf": [PACKAGE, {"type": "null"}]},
        "review": {"oneOf": [REVIEW_REF, {"type": "null"}]},
        "installOffer": {"enum": list(hubcore.INSTALL_OFFERS)},
    },
}

REGISTRY_SCHEMA = {
    "$schema": DRAFT, "$id": "https://github.com/JiangNanGenius/floe-skill-hub/schema/registry.schema.json",
    "title": "Floe Skill Hub candidate registry (catalog/skills.json) — schemaVersion 1",
    "description": "Repository source of truth for the 43 first-release candidates. Unsigned "
                   "source metadata, pretty JSON; only the derived channel feeds are canonical "
                   "and signed. A candidate registry never grants install, review or publication.",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "registry", "publisher", "hub", "categories", "notes", "skills"],
    "properties": {
        "schemaVersion": {"const": hubcore.REGISTRY_SCHEMA_VERSION},
        "registry": {"const": "candidate"},
        "publisher": {"const": "JiangNanGenius"},
        "hub": {"type": "object", "required": ["repository", "channelRoots"]},
        "categories": {"type": "array", "minItems": 7, "maxItems": 7, "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "name"],
            "properties": {"id": {"enum": list(hubcore.CATEGORIES)}, "name": LOCALE_TEXT}}},
        "notes": LOCALE_TEXT,
        "skills": {"type": "array", "minItems": 43, "maxItems": 43, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "planNumber", "kind", "source", "name", "description",
                         "category", "tags", "deepAdaptation", "upstream", "firstParty",
                         "plannedRuntime", "versionTarget", "minimumAppVersion", "status", "notes"],
            "properties": {
                "id": SKILL_ID, "planNumber": {"type": "integer", "minimum": 1, "maximum": 43},
                "kind": {"enum": list(hubcore.ENTRY_KINDS)},
                "source": {"enum": list(hubcore.SOURCE_CODES)},
                "name": LOCALE_TEXT, "description": LOCALE_TEXT,
                "category": {"enum": list(hubcore.CATEGORIES)},
                "tags": {"type": "array", "minItems": 2, "maxItems": 12, "uniqueItems": True,
                         "items": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9.-]*$"}},
                "deepAdaptation": {"type": "boolean"},
                "upstream": {"oneOf": [UPSTREAM, {"type": "null"}]},
                "firstParty": {"oneOf": [FIRSTPARTY, {"type": "null"}]},
                "plannedRuntime": RUNTIME,
                "versionTarget": {"oneOf": [VERSION, {"type": "null"}]},
                "minimumAppVersion": {"oneOf": [VERSION, {"type": "null"}]},
                "status": STATUS, "notes": LOCALE_TEXT}}},
    },
}

CATALOG_SCHEMA = {
    "$schema": DRAFT, "$id": "https://github.com/JiangNanGenius/floe-skill-hub/schema/catalog.schema.json",
    "title": "Floe Skill Hub signed channel feed (catalog.json / android/catalog.json) — schemaVersion 3",
    "description": "Canonical bytes (UTF-8 JSON, sorted keys, \",\"/\":\" separators, no "
                   "trailing newline) signed Ed25519 over the exact bytes; envelope "
                   "catalog.sig = {keyID, signature(base64)} identical to the legacy shape. "
                   "schemaVersion 3 is deliberately outside the old clients' accepted [1,2] "
                   "so they fail closed; they keep the separately produced legacy 4-item view.",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "publisher", "channel", "feedStatus", "hubRepository",
                 "sourceCommit", "permissionPolicy", "entries", "counts"],
    "properties": {
        "schemaVersion": {"const": hubcore.CATALOG_SCHEMA_VERSION},
        "publisher": {"const": "JiangNanGenius"},
        "channel": {"enum": list(hubcore.STORE_CHANNELS)},
        "feedStatus": {"enum": ["production", "fixture"],
                       "description": "fixture feeds never activate a production channel and "
                                      "only bind the fixture-only keyID"},
        "hubRepository": {"const": "JiangNanGenius/floe-skill-hub"},
        "sourceCommit": {"oneOf": [COMMIT, {"type": "null"}],
                         "description": "required for production: the audited source revision X "
                                        "whose content this feed describes (signed provenance). It "
                                        "is not the revision holding the published bytes: the "
                                        "client resolves the immutable publicationCommit Y "
                                        "externally and fetches feed, signature, reviews and "
                                        "archives at Y. X != Y is normal; a feed never carries the "
                                        "hash of the commit that contains it (no self-reference). "
                                        "Null only in fixture feeds."},
        "permissionPolicy": {"type": "object", "const": hubcore.PERMISSION_POLICY},
        "entries": {"type": "array", "minItems": 1, "items": CATALOG_ENTRY},
        "counts": {"type": "object", "additionalProperties": False,
                   "required": ["total", "builtin", "optional", "deepAdaptation",
                                "packaged", "reviewed", "qualified", "offerQualified"],
                   "properties": {k: {"type": "integer", "minimum": 0} for k in
                                  ("total", "builtin", "optional", "deepAdaptation", "packaged",
                                   "reviewed", "qualified", "offerQualified")},
                   "description": "actual per-feed values recomputed from entries; the store "
                                  "must show qualified/visible counts, never the candidate total"},
        "generatedNote": {"type": "string"},
    },
}

REVIEW_SCHEMA = {
    "$schema": DRAFT, "$id": "https://github.com/JiangNanGenius/floe-skill-hub/schema/review.schema.json",
    "title": "Signed publisher review record (reviews/{id}/{version}.review.json)",
    "description": "Canonical bytes, each record additionally signed with a catalog.sig-shaped "
                   ".review.json.sig envelope. Binds ID/version to the exact content it vouched "
                   "for; package or digest changes invalidate it. Review records bind the "
                   "existing grant model — they are not a second permission database and cannot "
                   "be self-issued by a package, README or model parameter.",
    "type": "object", "additionalProperties": False,
    "required": ["schemaVersion", "id", "version", "contentDigest", "packageSha256",
                 "reviewedCapabilities", "reviewedTools", "reviewedPythonPackages",
                 "execution", "reviewStage", "reviewedAt", "reviewer", "decision", "notes"],
    "properties": {
        "schemaVersion": {"const": hubcore.REVIEW_SCHEMA_VERSION},
        "id": SKILL_ID, "version": VERSION,
        "contentDigest": HEX64, "packageSha256": HEX64,
        "reviewedCapabilities": {"type": "array", "uniqueItems": True,
                                 "items": {"enum": list(hubcore.CAPABILITIES)}},
        "reviewedTools": {"type": "array", "uniqueItems": True,
                          "items": {"type": "string", "pattern": r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$"}},
        "reviewedPythonPackages": {"type": "array", "maxItems": 16, "items": PY_PKG},
        "execution": EXECUTION,
        "reviewStage": {"enum": ["static-content-reviewed", "guest-execution-qualified"]},
        "reviewedAt": DATE,
        "reviewer": {"type": "string", "minLength": 1, "maxLength": 64},
        "decision": {"enum": ["approve", "reject"]},
        "notes": LOCALE_TEXT,
    },
}

ENVELOPE_DOC = {
    "$schema": DRAFT,
    "$id": "https://github.com/JiangNanGenius/floe-skill-hub/schema/envelope.schema.json",
    "title": "Signature envelope (catalog.sig / catalog.sig-shaped *.sig / .review.json.sig)",
    "description": "Unchanged from the legacy skill-hub: exactly keyID plus base64 64-byte "
                   "Ed25519 signature over the exact payload bytes. Production keyID is "
                   "'official-2026-09' (pinned in the app trust root; the private key is "
                   "never in this repository). 'fixture-only-2026-10' is a deterministic "
                   "public-seed test identity that can never be a trust root.",
    "type": "object", "additionalProperties": False, "required": ["keyID", "signature"],
    "properties": {"keyID": {"type": "string", "minLength": 1, "maxLength": 64},
                   "signature": {"type": "string", "pattern": "^[A-Za-z0-9+/]{86}=="}},
}

DOCS = {"registry.schema.json": REGISTRY_SCHEMA, "catalog.schema.json": CATALOG_SCHEMA,
        "review.schema.json": REVIEW_SCHEMA, "envelope.schema.json": ENVELOPE_DOC}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = REPO / "schema"
    for name, doc in DOCS.items():
        data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        target = root / name
        if args.check:
            if not target.exists() or target.read_bytes() != data:
                raise SystemExit(f"schema document stale or missing: schema/{name}")
        else:
            root.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print("schemas " + ("verified" if args.check else "emitted") + ": " + ", ".join(sorted(DOCS)))


if __name__ == "__main__":
    main()
