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
import dependency_declaration
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

# --- dependency declaration v1 (references/dependencies.json) -------------
# Machine mirror of the native strict decoder (SkillDependency.swift), which
# is the sole authority. Patterns below are GENERATED from
# scripts/dependency_declaration.py so the published document can never drift
# from the producer gate. The per-kind oneOf branches declare the FULL key
# set of each kind (an empty properties + additionalProperties:false branch
# would reject every valid requirement).
DEP_BASE = f"{dependency_declaration.DECLARATION_REL} — official Skill dependency declaration v1"


def _dep_ref(name):
    return {"$ref": f"#/$defs/{name}"}


def _dep_requirement_branch(kind, refs, required):
    return {
        "title": kind,
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": dict({"kind": {"const": kind}}, **refs),
    }


DEP_REQUIREMENT = {
    "type": "object",
    "required": ["kind", "purpose", "required"],
    "description": "Tagged requirement entry carrying exactly the key set of its "
                   "kind; unknown keys (url, command, env, permission, approval, "
                   "sha256, index, registry, script) fail closed in the native "
                   "strict decoder, which is the sole authority.",
    "oneOf": [
        _dep_requirement_branch("pip", {
            "name": _dep_ref("pipName"), "version": _dep_ref("pipVersion"),
            "purpose": _dep_ref("purpose"), "required": _dep_ref("required"),
            "lockfile": _dep_ref("lockfile")},
            ["kind", "name", "version", "purpose", "required"]),
        _dep_requirement_branch("apt", {
            "name": _dep_ref("aptName"), "version": _dep_ref("aptVersion"),
            "purpose": _dep_ref("purpose"), "required": _dep_ref("required")},
            ["kind", "name", "version", "purpose", "required"]),
        _dep_requirement_branch("npm", {
            "name": _dep_ref("npmName"), "version": _dep_ref("npmVersion"),
            "purpose": _dep_ref("purpose"), "required": _dep_ref("required")},
            ["kind", "name", "version", "purpose", "required"]),
        _dep_requirement_branch("font", {
            "name": _dep_ref("fontIdentity"), "version": _dep_ref("fontVersion"),
            "purpose": _dep_ref("purpose"), "required": _dep_ref("required")},
            ["kind", "name", "version", "purpose", "required"]),
        _dep_requirement_branch("runtimeComponent", {
            "componentDescriptorPath": _dep_ref("componentDescriptorPath"),
            "purpose": _dep_ref("purpose"), "required": _dep_ref("required")},
            ["kind", "componentDescriptorPath", "purpose", "required"]),
    ],
}

DEPENDENCIES_SCHEMA = {
    "$schema": DRAFT,
    "$id": "https://github.com/JiangNanGenius/floe-skill-hub/schema/dependencies.schema.json",
    "title": f"Floe official Skill dependency declaration v1 ({DEP_BASE})",
    "description": "Machine-readable mirror of the native strict decoder in "
                   "FloeAgent/Sources/FloeSkills/SkillDependency.swift (the sole "
                   "authority), generated from scripts/dependency_declaration.py. "
                   "The file lives inside the canonical Skill package, so the "
                   "signed contentDigest covers its bytes and every referenced "
                   "lock. Declaration is DATA: no URL, command, script, "
                   "environment, registry, permission or approval field exists. "
                   "A package carrying this file must raise the entry's "
                   "minimumAppVersion to at least the first capable build "
                   f"({dependency_declaration.MIN_CAPABLE_APP_VERSION}).",
    "type": "object",
    "additionalProperties": False,
    "required": ["schemaVersion", "profiles"],
    "properties": {
        "schemaVersion": {
            "type": "integer",
            "const": dependency_declaration.SCHEMA_VERSION,
            "description": "Parser compatibility version only; exactly 1. Not the "
                           "Skill package version (floe.json id/version stays the "
                           "single package authority).",
        },
        "profiles": {
            "type": "array",
            "minItems": 1,
            "maxItems": dependency_declaration.MAX_PROFILES,
            "description": "1-8 profiles; unique ids; automatic provisioning binds "
                           "to the task's resolved Linux guest environment (no "
                           "target picker, execution never rerouted).",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "target", "requirements"],
                "properties": {
                    "id": {"type": "string", "pattern": dependency_declaration.PROFILE_ID.pattern,
                           "description": "Unique profile slug (SkillIdentifier grammar)."},
                    "target": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["os", "architectures"],
                        "properties": {
                            "os": {"const": dependency_declaration.TARGET_OS},
                            "architectures": {
                                "type": "array", "minItems": 1, "maxItems": 4,
                                "uniqueItems": True,
                                "items": {"enum": sorted(dependency_declaration.SUPPORTED_ARCHITECTURES)},
                            },
                        },
                    },
                    "requirements": {
                        "type": "array", "minItems": 1,
                        "maxItems": dependency_declaration.MAX_REQUIREMENTS_PER_PROFILE,
                        "items": DEP_REQUIREMENT,
                    },
                },
            },
        },
    },
    "$defs": {
        "pipName": {"type": "string", "pattern": f"^{dependency_declaration.PIP_NAME.pattern}$",
                    "description": "PyPI distribution name; extras, ranges, URLs, paths "
                                   "and VCS references are rejected."},
        "pipVersion": {"type": "string",
                       "pattern": f"^{dependency_declaration.PIP_VERSION.pattern}$",
                       "description": "One exact PEP 440 version tail ([A-Za-z0-9.*+!_-]*, "
                                      "epoch/local markers verbatim, no operators/ranges)."},
        "aptName": {"type": "string", "pattern": f"^{dependency_declaration.APT_NAME.pattern}$",
                    "description": "Debian source package identity."},
        "aptVersion": {"type": "string",
                       "pattern": f"^(?:[0-9]+:)?{dependency_declaration.APT_VERSION_BODY.pattern}$",
                       "description": "Exact Debian version, epoch preserved; "
                                      "+dfsg/-rev/+tilde/repack suffixes stay part of the pin."},
        "fontVersion": {"type": "string",
                        "pattern": f"^(?:[0-9]+:)?{dependency_declaration.APT_VERSION_BODY.pattern}$",
                        "description": "Same exact Debian version class as the apt kind."},
        "npmName": {"type": "string", "pattern": f"^{dependency_declaration.NPM_NAME.pattern}$",
                    "description": "npm name, optionally @scope/ scoped."},
        "npmVersion": {"type": "string", "maxLength": 64,
                       "pattern": r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$",
                       "description": "Exact semver X.Y.Z with optional prerelease tail; "
                                      "'+' build metadata is rejected, matching the native decoder."},
        "fontIdentity": {"type": "string",
                         "pattern": f"^{dependency_declaration.FONT_IDENTITY.pattern}$",
                         "description": "Exactly one Debian font package identity "
                                        "(fonts- prefix)."},
        "lockfile": {"type": "string",
                     "pattern": r"^references/[A-Za-z0-9._/-]{1,255}\.txt$",
                     "not": {"pattern": r"\.\."},
                     "description": "Package-local lock reference (pip kind only). Its bytes "
                                    "are covered by the package contentDigest."},
        "componentDescriptorPath": {"const": dependency_declaration.COMPONENT_DESCRIPTOR_REL,
                                    "description": "The frozen runtime-component descriptor "
                                                   "path; identity/version/digest come only from "
                                                   "the pinned descriptor through the existing "
                                                   "managed allowlist (today exactly "
                                                   "impeccable-engine)."},
        "purpose": {"type": "string", "minLength": 1,
                    "maxLength": dependency_declaration.MAX_PURPOSE_BYTES,
                    "description": "1-200 bytes of model-safe text; no leading/trailing "
                                   "whitespace and no control characters (native decoder "
                                   "rules beyond this document)."},
        "required": {"type": "boolean",
                     "description": "true gates that skill's dependency-aware exec.shell "
                                    "invocation until the requirement is verified ready."},
    },
}

DOCS = {"registry.schema.json": REGISTRY_SCHEMA, "catalog.schema.json": CATALOG_SCHEMA,
        "review.schema.json": REVIEW_SCHEMA, "envelope.schema.json": ENVELOPE_DOC,
        "dependencies.schema.json": DEPENDENCIES_SCHEMA}


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
