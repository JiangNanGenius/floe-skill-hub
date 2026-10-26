#!/usr/bin/env python3
"""Strict validator for official Skill `references/dependencies.json` (v1).

Python mirror of the NATIVE STRICT DECODER, which is the sole authority:
FloeAgent/Sources/FloeSkills/SkillDependency.swift (schemaVersion 1). This
module copies its grammar exactly — same exact key sets, same ASCII pattern
sets, same limits, same fail-closed order of checks — so the Hub producer
gate accepts exactly what the frozen native client accepts and rejects what
it rejects. It invents NO new semantics; where the native decoder is the
reference, comments cite the Swift function mirrored.

The declaration is DATA, never authority: it can never mint a command, URL,
script, environment value, permission or approval (no such field exists).
It is decoded only from bytes of the digest-verified official curated
snapshot; here, from the already-gated package file set.

Used by:
  * scripts/build_packages.py — staged-source preflight (fail closed);
  * scripts/build_catalog.py — the same gate re-run on frozen X snapshot
    archives at the publication boundary;
  * tests/catalog/test_dependency_declaration.py — mirror-accuracy corpus.

Nothing here widens ordinary Skill ZIP gates; a dependency declaration adds
no artifact allowance. The managed runtime-component descriptor keeps its
own strict decoder + allowlist (scripts/runtime_dependency.py) unchanged.
"""
import json
import re

import hubcore
import runtime_dependency

# --- frozen v1 constants (mirror SkillDependency.swift) -------------------
DECLARATION_REL = "references/dependencies.json"
MAX_DECLARATION_BYTES = 65_536          # native maximumDeclarationBytes
SCHEMA_VERSION = 1                      # native frozenSchemaVersion
MAX_PROFILES = 8                        # native maximumProfiles
MAX_REQUIREMENTS_PER_PROFILE = 32       # native maximumRequirementsPerProfile
MAX_PURPOSE_BYTES = 200                 # native maximumPurposeBytes
TARGET_OS = "linux"                     # native frozenTargetOS
SUPPORTED_ARCHITECTURES = frozenset({"riscv64", "arm64", "x86_64", "any"})
MIN_CAPABLE_APP_VERSION = "1.7.60"      # native minimumCapableAppVersion (candidate)
COMPONENT_DESCRIPTOR_REL = runtime_dependency.EMBEDDED_DESCRIPTOR_REL

# Exact top-level requirement key set per tagged kind (mirror Kind.exactKeys).
REQUIREMENT_KEYS = {
    "pip": frozenset({"kind", "name", "version", "purpose", "required", "lockfile"}),
    "apt": frozenset({"kind", "name", "version", "purpose", "required"}),
    "npm": frozenset({"kind", "name", "version", "purpose", "required"}),
    "font": frozenset({"kind", "name", "version", "purpose", "required"}),
    "runtimeComponent": frozenset({"kind", "componentDescriptorPath", "purpose", "required"}),
}

# --- ASCII pattern mirrors (SkillDependency.swift MARK: - Patterns) --------
# PyPI name [A-Za-z0-9][A-Za-z0-9._-]*, max 128 (native isValidPipName).
PIP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# Single exact PEP 440 version tail allowing * + ! (native isValidPipVersion).
PIP_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.*+!_-]{0,127}")
# Debian identity [a-z0-9][a-z0-9+._-]* (native isValidAptName).
APT_NAME = re.compile(r"[a-z0-9][a-z0-9+._-]{0,127}")
# Exact Debian version body [A-Za-z0-9][A-Za-z0-9+~:.+-]*, epoch stripped by caller.
APT_VERSION_BODY = re.compile(r"[A-Za-z0-9][A-Za-z0-9+~:.+-]{0,127}")
# npm scope/name charsets (native isValidNpmName).
NPM_NAME = re.compile(r"(?:@[a-z0-9-~][a-z0-9-._~]{0,63}/)?[a-z0-9-~][a-z0-9-._~]{0,127}")
# Font apt identity fonts- + Debian identity (native isValidFontIdentity).
FONT_IDENTITY = re.compile(r"fonts-[a-z0-9][a-z0-9+._-]{0,127}")
# Profile id grammar = SkillIdentifier (native isValidProfileID).
PROFILE_ID = hubcore.ID_PATTERN

_LOCK_PATH_ALLOWED = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/")


def _fail(field, message):
    raise hubcore.HubError(f"{field}: {message}")


def is_valid_pip_name(value):
    return isinstance(value, str) and PIP_NAME.fullmatch(value) is not None


def is_valid_pip_version(value):
    return isinstance(value, str) and PIP_VERSION.fullmatch(value) is not None


def is_valid_apt_name(value):
    return isinstance(value, str) and APT_NAME.fullmatch(value) is not None


def is_valid_apt_version(value):
    """([0-9]+:)?[A-Za-z0-9][A-Za-z0-9+~:.+-]* with a <=128-byte body."""
    if not isinstance(value, str):
        return False
    body = value
    if ":" in value:
        epoch, _, rest = value.partition(":")
        if not epoch or not epoch.isascii() or not epoch.isdigit():
            return False
        body = rest
    return APT_VERSION_BODY.fullmatch(body) is not None


def is_valid_npm_name(value):
    return isinstance(value, str) and NPM_NAME.fullmatch(value) is not None


def is_valid_npm_version(value):
    """Exact semver X.Y.Z[-tail]; total <= 64 chars; no '+' anywhere.

    Mirrors native isValidNpmVersion: core is exactly three dot-separated
    ASCII-digit parts (leading zeros tolerated), optional non-empty tail of
    [0-9A-Za-z.-] after the FIRST '-'; '+' and space reject anywhere.
    """
    if not isinstance(value, str) or not value:
        return False
    if len(value) > 64 or "+" in value or " " in value:
        return False
    core, _, tail = value.partition("-")
    parts = core.split(".")
    if len(parts) != 3 or any(not p or not p.isascii() or not p.isdigit() for p in parts):
        return False
    if "-" in value:
        if not tail:
            return False
        return all(c.isascii() and (c.isalnum() or c in ".-") for c in tail)
    return True


def is_valid_font_identity(value):
    return isinstance(value, str) and FONT_IDENTITY.fullmatch(value) is not None


def is_valid_profile_id(value):
    # Native isValidProfileID delegates to SkillIdentifier.validate: non-empty,
    # <= 64 characters, leading letter, lowercase/number/'-' only, no trailing
    # '-' and no '--' (the latter two are already implied by ID_PATTERN).
    return (isinstance(value, str) and 0 < len(value) <= 64
            and PROFILE_ID.fullmatch(value) is not None)


def is_package_local_lock_path(value):
    """Mirror of native isPackageLocalLockPath (procedural, byte-exact)."""
    if not isinstance(value, str):
        return False
    raw = value.encode("utf-8", "surrogatepass")
    if len(raw) > 256 or not value.startswith("references/") \
            or not value.endswith(".txt"):
        return False
    if " " in value or "\"" in value or "\0" in value:
        return False
    parts = value.split("/")
    if len(parts) < 2 or parts[0] != "references":
        return False
    if any(part in ("", ".", "..") for part in parts):
        return False
    return all(char in _LOCK_PATH_ALLOWED for char in value)


def is_valid_purpose(value):
    """1..200 UTF-8 bytes; no leading/trailing whitespace; no control chars.

    Mirrors native isValidPurpose (trimmed == value, byte bound, control-char
    screen via NSCharacterSet.controlCharacters == Unicode category Cc).
    """
    if not isinstance(value, str) or not value:
        return False
    if len(value.encode("utf-8")) > MAX_PURPOSE_BYTES:
        return False
    if value != value.strip():
        return False
    import unicodedata
    return all(unicodedata.category(char) != "Cc" for char in value)


# --- strict decode (mirror SkillDependency.decode / decodeRequirement) ------


def _exact_keys(obj, allowed, required, field):
    keys = set(obj)
    unknown = keys - set(allowed)
    if unknown:
        _fail(field, f"unknown fields {sorted(unknown)}")
    missing = set(required) - keys
    if missing:
        _fail(field, f"missing required fields {sorted(missing)}")


def _string(obj, key, field):
    value = obj.get(key)
    if not isinstance(value, str):
        _fail(field, f"{key!r} must be a string")
    return value


def _boolean(obj, key, field):
    value = obj.get(key)
    if not isinstance(value, bool):
        _fail(field, f"{key!r} must be a boolean")
    return value


def _decode_requirement(obj, field):
    if not isinstance(obj, dict):
        _fail(field, "requirement must be an object")
    kind = _string(obj, "kind", field)
    if kind not in REQUIREMENT_KEYS:
        _fail(field, f"unsupported kind {kind!r}")
    exact = REQUIREMENT_KEYS[kind]
    _exact_keys(obj, exact, [key for key in exact if key != "lockfile"], field)
    purpose = _string(obj, "purpose", field)
    if not is_valid_purpose(purpose):
        _fail(field, "purpose must be 1-200 bytes of model-safe text")
    required = _boolean(obj, "required", field)

    name = ""
    version = None
    lockfile = None
    descriptor_path = None
    if kind == "pip":
        name = _string(obj, "name", field)
        if not is_valid_pip_name(name):
            _fail(field, f"invalid pip name {name!r}")
        version = _string(obj, "version", field)
        if not is_valid_pip_version(version):
            _fail(field, f"invalid pip version {version!r}")
        if "lockfile" in obj:
            lockfile = _string(obj, "lockfile", field)
            if not is_package_local_lock_path(lockfile):
                _fail(field, f"lock path rejected: {lockfile!r}")
    elif kind in ("apt", "npm", "font"):
        name = _string(obj, "name", field)
        version = _string(obj, "version", field)
        if kind == "apt":
            if not is_valid_apt_name(name):
                _fail(field, f"invalid apt name {name!r}")
            if not is_valid_apt_version(version):
                _fail(field, f"invalid apt version {version!r}")
        elif kind == "npm":
            if not is_valid_npm_name(name):
                _fail(field, f"invalid npm name {name!r}")
            if not is_valid_npm_version(version):
                _fail(field, f"invalid npm version {version!r}")
        else:
            if not is_valid_font_identity(name):
                _fail(field, f"invalid font identity {name!r}")
            if not is_valid_apt_version(version):
                _fail(field, f"invalid font version {version!r}")
    else:  # runtimeComponent
        candidate = _string(obj, "componentDescriptorPath", field)
        if candidate != COMPONENT_DESCRIPTOR_REL:
            _fail(field, f"descriptor path rejected: {candidate!r}")
        descriptor_path = candidate
        # Identity arrives from the pinned descriptor at cross-validation,
        # never from the requirement bytes (native comment).
    return {
        "kind": kind,
        "name": name,
        "version": version,
        "purpose": purpose,
        "required": required,
        "lockfile": lockfile,
        "componentDescriptorPath": descriptor_path,
    }


def validate_declaration(value, field="dependencies.json"):
    """Strictly validate one parsed declaration VALUE (fail closed).

    Mirrors the native decoder: exact key sets at every level, schemaVersion
    exactly the integer 1, 1..8 unique profiles, frozen target, 1..32 unique
    (kind,name) requirements per profile, per-kind grammar. Returns the
    normalized declaration dict on success.
    """
    if not isinstance(value, dict):
        _fail(field, "declaration must be an object")
    _exact_keys(value, {"schemaVersion", "profiles"}, {"schemaVersion", "profiles"}, field)
    schema_version = value["schemaVersion"]
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        _fail(field, f"schemaVersion must be the integer {SCHEMA_VERSION}")
    if schema_version > SCHEMA_VERSION:
        _fail(field, f"unsupported schemaVersion {schema_version} "
                     f"(this contract supports exactly {SCHEMA_VERSION})")
    if schema_version < SCHEMA_VERSION:
        _fail(field, f"schemaVersion must be exactly {SCHEMA_VERSION}")

    profiles = value["profiles"]
    if not isinstance(profiles, list) or not profiles:
        _fail(field, "profiles must be a non-empty array")
    if len(profiles) > MAX_PROFILES:
        _fail(field, f"declaration carries {len(profiles)} profiles; at most "
                     f"{MAX_PROFILES} are allowed")
    seen_profile_ids = set()
    normalized_profiles = []
    for index, raw_profile in enumerate(profiles):
        path = f"{field}.profiles[{index}]"
        if not isinstance(raw_profile, dict):
            _fail(path, "profile must be an object")
        _exact_keys(raw_profile, {"id", "target", "requirements"},
                    {"id", "target", "requirements"}, path)
        profile_id = _string(raw_profile, "id", path)
        if not is_valid_profile_id(profile_id):
            _fail(path, f"invalid profile id {profile_id!r}")
        if profile_id in seen_profile_ids:
            _fail(path, f"duplicate profile id {profile_id!r}")
        seen_profile_ids.add(profile_id)
        target = raw_profile["target"]
        if not isinstance(target, dict):
            _fail(f"{path}.target", "target must be an object")
        _exact_keys(target, {"os", "architectures"}, {"os", "architectures"},
                    f"{path}.target")
        os_name = _string(target, "os", f"{path}.target")
        if os_name != TARGET_OS:
            _fail(f"{path}.target", f"unsupported target os {os_name!r}")
        architectures = target["architectures"]
        if (not isinstance(architectures, list) or not architectures
                or len(architectures) > 4):
            _fail(f"{path}.target", "architectures must be a non-empty array of "
                                    "at most 4 entries")
        seen_arch = set()
        for arch in architectures:
            if not isinstance(arch, str) or arch not in SUPPORTED_ARCHITECTURES \
                    or arch in seen_arch:
                _fail(f"{path}.target",
                      f"invalid or duplicate architecture {arch!r}")
            seen_arch.add(arch)
        requirements = raw_profile["requirements"]
        if not isinstance(requirements, list) or not requirements:
            _fail(f"{path}.requirements", "requirements must be a non-empty array")
        if len(requirements) > MAX_REQUIREMENTS_PER_PROFILE:
            _fail(path, f"profile carries {len(requirements)} requirements; at most "
                        f"{MAX_REQUIREMENTS_PER_PROFILE} are allowed")
        seen_requirements = set()
        normalized_requirements = []
        for req_index, raw_requirement in enumerate(requirements):
            requirement = _decode_requirement(
                raw_requirement, f"{path}.requirements[{req_index}]")
            identity = f"{requirement['kind']}:{requirement['name']}"
            if identity in seen_requirements:
                _fail(f"{path}.requirements[{req_index}]",
                      f"duplicate requirement {identity!r}")
            seen_requirements.add(identity)
            normalized_requirements.append(requirement)
        normalized_profiles.append({
            "id": profile_id,
            "target": {"os": os_name, "architectures": list(architectures)},
            "requirements": normalized_requirements,
        })
    return {"schemaVersion": SCHEMA_VERSION, "profiles": normalized_profiles}


def parse_declaration(data, field=DECLARATION_REL):
    """Parse raw declaration bytes and strict-validate the value.

    Any valid JSON object encoding is accepted exactly like the native
    JSONSerialization-based decoder (no canonical-byte requirement: the
    package contentDigest already binds the exact bytes).
    """
    if isinstance(data, (bytes, bytearray)):
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            _fail(field, "declaration must be valid UTF-8 bytes")
    elif isinstance(data, str):
        text = data
    else:
        _fail(field, "declaration must be JSON bytes")
    try:
        value = json.loads(text)
    except ValueError as error:
        _fail(field, f"declaration is not valid JSON: {error}")
    return validate_declaration(value, field)


def cross_validate(declaration, package_files, field=DECLARATION_REL):
    """Mirror of native SkillDependency.validate over the package file set.

    Every declared lock must be a package-local path present in the signed
    bytes; every runtime-component requirement must reference the frozen
    descriptor path whose bytes themselves strict-decode through the
    unchanged managed runtime-component gate.
    """
    for profile in declaration["profiles"]:
        for requirement in profile["requirements"]:
            lock = requirement["lockfile"]
            if lock is not None:
                if not is_package_local_lock_path(lock):
                    _fail(field, f"lock path rejected: {lock!r}")
                if lock not in package_files:
                    _fail(field, f"declared lock file {lock!r} is not present "
                                 f"in the package")
            descriptor_path = requirement["componentDescriptorPath"]
            if descriptor_path is not None:
                if descriptor_path != COMPONENT_DESCRIPTOR_REL:
                    _fail(field, f"descriptor path rejected: {descriptor_path!r}")
                descriptor_bytes = package_files.get(descriptor_path)
                if descriptor_bytes is None:
                    _fail(field, f"declared runtime-component descriptor "
                                 f"{descriptor_path!r} is not present in the package")
                runtime_dependency.parse_descriptor(descriptor_bytes, field)
    return declaration


def version_at_least(version, minimum):
    """Strict-semver tuple comparison over already-validated version strings."""
    left = tuple(int(part) for part in version.split("."))
    right = tuple(int(part) for part in minimum.split("."))
    return left >= right


def assert_declaration_gates(entry, package_files, field=None):
    """Package preflight + publisher gate for one registry entry (fail closed).

    Returns the validated declaration when the package carries one, else None.

    Gate 1 (native contract): a staged `references/dependencies.json` must
    strict-decode exactly like the frozen native decoder and cross-validate
    against the package file set (locks + frozen descriptor present).
    Gate 2 (publisher minApp gate, frozen guide): a package carrying a new
    dependency declaration needs the new native provisioning behavior, so the
    entry's existing minimumAppVersion must be set and >= the first capable
    build (candidate 1.7.60). An entry without a declaration is untouched by
    this gate.
    """
    blob = package_files.get(DECLARATION_REL)
    if blob is None:
        return None
    field = field or f"{entry.get('id', '?')}/{DECLARATION_REL}"
    declaration = cross_validate(parse_declaration(blob, field), package_files, field)
    minimum = entry.get("minimumAppVersion")
    if minimum is None:
        _fail(field, f"package carries a dependency declaration but the entry "
                     f"has no minimumAppVersion; raise it to at least "
                     f"{MIN_CAPABLE_APP_VERSION} (the first capable build)")
    hubcore.require_version(minimum, "minimumAppVersion")
    if not version_at_least(minimum, MIN_CAPABLE_APP_VERSION):
        _fail(field, f"dependency declaration requires minimumAppVersion >= "
                     f"{MIN_CAPABLE_APP_VERSION} (the first capable build); "
                     f"the entry carries {minimum!r}")
    return declaration
