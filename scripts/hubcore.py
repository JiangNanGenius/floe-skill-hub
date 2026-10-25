#!/usr/bin/env python3
"""Floe Skill Hub core contracts (MPL-2.0, Floe-authored tooling).

Single source of truth for:
  * canonical bytes shared with the legacy skill-hub envelope
    (json.dumps ensure_ascii=False, sort_keys=True, separators=(",",":"), UTF-8);
  * Ed25519 signing/verification envelopes {"keyID","signature"} (base64);
  * deterministic ZIP packaging identical to skill-hub/build.py
    (ZIP_STORED, 1980-01-01, create_system=3, external_attr=0o100644<<16, sorted);
  * contentDigest = SHA256 over sorted big-endian length-prefixed path+data;
  * the package rejection gates that mirror the native validator
    (paths, symlinks, native payloads, sizes, counts, floe.json/SKILL.md);
  * registry, channel-feed and review-record structural validation;
  * the deterministic fixture-only ephemeral key (never a trust root).

This module never executes package code and never reads production secrets.
"""
import base64
import hashlib
import io
import json
import re
import struct
import unicodedata
import zipfile

# --------------------------------------------------------------------------
# shared primitives (byte-compatible with the legacy skill-hub build)
# --------------------------------------------------------------------------

VERSION_PATTERN = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
HEX64_PATTERN = re.compile(r"[0-9a-f]{64}")
DATE_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")  # SkillIdentifier grammar
TOOL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
PY_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
PY_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+!-]*$")

CAPABILITIES = (
    "workspace.read", "workspace.write", "workspace.delete", "network",
    "browser.observe", "browser.interact", "credentials",
    "javascript.local", "python.local", "execution.remote",
)
PLATFORMS = ("ios", "macos", "linux")
STORE_CHANNELS = ("ios", "android")  # install channels are feeds, not native SkillPlatform values
SCRIPT_RUNTIMES = ("none", "javascriptcore", "python.local", "remote")

SOURCE_CODES = ("F", "A", "V", "R", "K", "S", "I")
CATEGORIES = (
    "office-documents", "writing-communication", "web-development",
    "research-data", "design-creation", "product-requirements",
    "productivity-organization",
)
ENTRY_KINDS = ("builtin", "optional")
LICENSE_STATUSES = (
    "verified", "pending-per-item-audit", "blocked-no-upstream-license", "floe-owned",
)
ADAPTATION_STAGES = ("awaiting-implementation", "planned", "in-progress", "frozen")
EXECUTION_EVIDENCE = ("unproven", "guest-verified")
INSTALL_OFFERS = ("none", "qualified", "fixture-simulated")

# package gates: the strictest active value between the native validator and
# the signed-archive staging limits.
MAX_PACKAGE_FILES = 128
MAX_FILE_BYTES = 2_097_152
MAX_TOTAL_BYTES = 8_388_608
MAX_SKILL_MD_BYTES = 262_144
MAX_FLOE_JSON_BYTES = 65_536
MAX_PATH_BYTES = 512
MAX_PY_PACKAGES = 16

ALLOWED_TOP_LEVEL = ("SKILL.md", "floe.json", "references", "assets", "scripts", "agents")
FORBIDDEN_EXTENSIONS = ("dylib", "so", "wasm", "framework", "bundle", "a", "o")
NATIVE_MAGICS = (
    b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce",
    b"\xca\xfe\xba\xbe", b"\x7fELF", b"\x00asm",
)

PRODUCTION_KEY_ID = "official-2026-09"   # identity reference only; the private key is never in this repo
FIXTURE_KEY_ID = "fixture-only-2026-10"  # deterministic ephemeral test key; never a trust root
FIXTURE_SEED_LABEL = (
    b"floe-skill-hub fixture-only ephemeral Ed25519 key 2026-10 "
    b"-- NOT a trust root -- NOT production material"
)
RESERVED_BUILTIN_IDS = ("floe-pdf", "floe-office", "floe-network", "floe-video")

REGISTRY_SCHEMA_VERSION = 1
CATALOG_SCHEMA_VERSION = 3          # outside [1,2]: old clients fail closed by design
LEGACY_CATALOG_SCHEMA_VERSION = 2   # the four-item compatibility shape
REVIEW_SCHEMA_VERSION = 1

BIDI_LOCALES = ("en", "zh-Hans")


class HubError(ValueError):
    """A fail-closed contract violation with a single clear message."""


def encoded(value):
    """Canonical bytes: identical to the legacy skill-hub `encoded()`."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def pretty(value):
    """Human-review bytes for checked-in source-of-truth JSON (registry)."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def content_digest(files):
    """SHA256 over sorted big-endian length-prefixed path+data pairs."""
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        path = name.encode("utf-8")
        digest.update(struct.pack(">Q", len(path)) + path)
        digest.update(struct.pack(">Q", len(data)) + data)
    return digest.hexdigest()


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def require_version(value, field="version"):
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise HubError(f"invalid {field}: {value!r} (strict X.Y.Z, no leading zeros)")
    return value


def require_hex64(value, field):
    if not isinstance(value, str) or not HEX64_PATTERN.fullmatch(value):
        raise HubError(f"invalid {field}: expected 64 lowercase hex")
    return value


def require_commit(value, field):
    if not isinstance(value, str) or not COMMIT_PATTERN.fullmatch(value):
        raise HubError(f"invalid {field}: expected 40 lowercase hex")
    return value


def require_date(value, field):
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        raise HubError(f"invalid {field}: expected YYYY-MM-DD")
    return value


def has_cjk(text):
    """True Unicode check: at least one CJK Unified Ideograph (no regex escapes)."""
    return any(0x4E00 <= ord(ch) <= 0x9FFF for ch in text)


def require_bilingual(value, field, allow_empty=False):
    if not isinstance(value, dict) or any(
            not isinstance(v, str) for v in value.values()):
        raise HubError(f"{field} must be a locale->string dictionary")
    extra = set(value) - set(BIDI_LOCALES)
    if extra:
        raise HubError(f"{field} has locales outside the contract: {sorted(extra)}")
    for locale in BIDI_LOCALES:
        text = value.get(locale, "")
        if not text.strip() and not allow_empty:
            raise HubError(f"{field} requires nonempty {locale} text")
    return value


def require_id(value, field="id"):
    if (not isinstance(value, str) or len(value) > 64
            or not ID_PATTERN.fullmatch(value) or "--" in value
            or value.endswith("-")):
        raise HubError(f"invalid {field}: {value!r}")
    return value


# --------------------------------------------------------------------------
# Ed25519 envelope (shape identical to the legacy catalog.sig)
# --------------------------------------------------------------------------

def _load_ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature
    except ImportError as error:  # fail closed with actionable guidance
        raise HubError(
            "cryptography is required for signing/verification "
            "(python3 -m pip install cryptography)") from error
    return Ed25519PrivateKey, Ed25519PublicKey, serialization, InvalidSignature


def sign_envelope(payload_bytes, private_key, key_id):
    _, _, serialization, _ = _load_ed25519()
    raw = private_key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption())
    if key_id == PRODUCTION_KEY_ID and len(raw) != 32:
        raise HubError("production identity requires a raw 32-byte key")
    signature = private_key.sign(payload_bytes)
    return encoded({"keyID": key_id,
                    "signature": base64.b64encode(signature).decode()})


def verify_envelope(payload_bytes, envelope_bytes, public_keys_by_id):
    _, Ed25519PublicKey, _, InvalidSignature = _load_ed25519()
    envelope = json.loads(envelope_bytes)
    if not isinstance(envelope, dict) or set(envelope) != {"keyID", "signature"}:
        raise HubError("invalid signature envelope shape")
    key_b64 = public_keys_by_id.get(envelope["keyID"])
    if key_b64 is None:
        raise HubError(f"unknown signing keyID: {envelope['keyID']!r}")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64, validate=True))
        key.verify(base64.b64decode(envelope["signature"], validate=True), payload_bytes)
    except (InvalidSignature, ValueError):
        raise HubError("signature verification failed") from None
    return envelope["keyID"]


def fixture_private_key():
    """Deterministic ephemeral test key derived from a public label.

    The seed is public knowledge, so this signature proves only wire-shape and
    verification mechanics. It can never vouch for real review or publication
    and must never be installed as a trust root.
    """
    Ed25519PrivateKey, _, _, _ = _load_ed25519()
    seed = hashlib.sha256(FIXTURE_SEED_LABEL).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def fixture_public_b64():
    _, _, serialization, _ = _load_ed25519()
    key = fixture_private_key()
    raw = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


# --------------------------------------------------------------------------
# deterministic ZIP + the package rejection gates
# --------------------------------------------------------------------------

def make_zip(files):
    """Byte-deterministic archive, identical construction to the legacy builder."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def _safe_relative(name):
    if (not isinstance(name, str) or not name or name.startswith("/")
            or name.startswith(".") or "\\" in name or "\0" in name
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise HubError(f"unsafe package path: {name!r}")
    if len(name.encode("utf-8")) > MAX_PATH_BYTES:
        raise HubError(f"path exceeds {MAX_PATH_BYTES} bytes: {name!r}")
    top = name.split("/")[0]
    if top not in ALLOWED_TOP_LEVEL:
        raise HubError(f"unsupported top-level path: {name!r}")
    if top in ("SKILL.md", "floe.json") and name != top:
        raise HubError(f"{top} must be exactly at the package root: {name!r}")


def reject_native_payload(name, data):
    leaf = name.split("/")[-1]
    extension = leaf.rsplit(".", 1)[-1].lower() if "." in leaf else ""
    if extension in FORBIDDEN_EXTENSIONS:
        raise HubError(f"forbidden native extension: {name!r}")
    bundle_dirs = {"framework", "bundle", "xcframework", "app"}
    for part in name.split("/")[:-1]:
        if part.rsplit(".", 1)[-1].lower() in bundle_dirs and "." in part:
            raise HubError(f"native bundle directory in package: {name!r}")
    for magic in NATIVE_MAGICS:
        if data.startswith(magic):
            raise HubError(f"native payload magic in {name!r}")


def parse_frontmatter(markdown_bytes):
    """The native SKILL.md contract: unquoted-optional scalar frontmatter."""
    try:
        text = markdown_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HubError("SKILL.md must be UTF-8") from None
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise HubError("SKILL.md requires opening frontmatter")
    end = normalized.find("\n---\n", 4)
    if end == -1:
        raise HubError("SKILL.md requires closing frontmatter")
    frontmatter = normalized[4:end]
    body = normalized[end + 5:].strip()
    if not body:
        raise HubError("SKILL.md instructions body must not be empty")
    values = {}
    for line in frontmatter.split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        if "\t" in line or ":" not in line:
            raise HubError("SKILL.md frontmatter must be scalar key: value lines")
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if not key or not raw:
            raise HubError("SKILL.md frontmatter empty key or value")
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        values[key] = raw
    if "name" not in values or "description" not in values:
        raise HubError("SKILL.md frontmatter requires name and description")
    if len(values["description"]) > 1024:
        raise HubError("SKILL.md description exceeds 1024 characters")
    return values, body


def parse_manifest(manifest_bytes):
    """floe.json: native schemaVersion-1 contract with an exact key set."""
    object_value = json.loads(manifest_bytes)
    if not isinstance(object_value, dict):
        raise HubError("floe.json top level must be an object")
    allowed = {"schemaVersion", "id", "version", "capabilities", "tools",
               "platforms", "scriptRuntime", "pythonPackages"}
    unknown = set(object_value) - allowed
    if unknown:
        raise HubError(f"floe.json unknown fields: {sorted(unknown)}")
    if object_value.get("schemaVersion") != 1:
        raise HubError("floe.json schemaVersion must be 1")
    require_id(object_value.get("id", ""), "floe.json id")
    require_version(object_value.get("version"), "floe.json version")
    for field, universe in (("capabilities", CAPABILITIES), ("platforms", PLATFORMS)):
        value = object_value.get(field, [])
        if not isinstance(value, list) or any(v not in universe for v in value):
            raise HubError(f"floe.json {field} contains unknown values")
        if len(set(value)) != len(value):
            raise HubError(f"floe.json {field} must be unique")
    if not object_value.get("platforms"):
        raise HubError("floe.json platforms must be non-empty")
    tools = object_value.get("tools", [])
    if not isinstance(tools, list) or any(not TOOL_PATTERN.fullmatch(t) for t in tools):
        raise HubError("floe.json tools must be dotted names")
    if len(set(tools)) != len(tools):
        raise HubError("floe.json tools must be unique")
    runtime = object_value.get("scriptRuntime", "none")
    if runtime not in SCRIPT_RUNTIMES:
        raise HubError(f"floe.json unknown scriptRuntime: {runtime!r}")
    packages = object_value.get("pythonPackages", [])
    if not isinstance(packages, list) or len(packages) > MAX_PY_PACKAGES:
        raise HubError("floe.json pythonPackages limit exceeded")
    seen_specs = set()
    for package in packages:
        if not isinstance(package, dict) or set(package) != {"spec", "purpose", "capabilities"}:
            raise HubError("pythonPackages entries need spec/purpose/capabilities")
        spec = package["spec"]
        if spec.lower() in seen_specs:
            raise HubError(f"pythonPackages duplicate spec: {spec!r}")
        seen_specs.add(spec.lower())
        if "== " in spec or spec.count("==") != 1:
            raise HubError(f"pythonPackages require exact name==version: {spec!r}")
        name, _, version = spec.partition("==")
        if (not PY_NAME_PATTERN.fullmatch(name) or not PY_VERSION_PATTERN.fullmatch(version)
                or not version):
            raise HubError(f"pythonPackages require exact name==version: {spec!r}")
        purpose = package["purpose"].strip()
        if not purpose or len(purpose.encode("utf-8")) > 1024:
            raise HubError("pythonPackages purpose must be 1-1024 bytes")
        capabilities = package["capabilities"]
        if (not 1 <= len(capabilities) <= 16 or len(set(capabilities)) != len(capabilities)
                or any(not re.fullmatch(r"[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+", c)
                       for c in capabilities)):
            raise HubError("pythonPackages capabilities must be 1-16 unique dotted lowercase names")
    capabilities_set = set(object_value.get("capabilities", []))
    if packages and not (
            (runtime == "python.local" and "python.local" in capabilities_set
             and "exec.localPython" in tools)
            or (runtime == "remote" and "execution.remote" in capabilities_set
                and "exec.shell" in tools)):
        raise HubError("pythonPackages require a declared script runtime and its execution tool")
    return object_value


_SCRIPT_EXTENSIONS = {
    "none": (),
    "javascriptcore": ("js", "mjs"),
    "python.local": ("py",),
    "remote": ("js", "mjs", "py", "sh"),
}
_LOCAL_PYTHON_FORBIDDEN = (
    "import pip", "from pip", "ensurepip", "pip._internal",
    "subprocess", "os.system(", "import ctypes", "from ctypes",
    "import cffi", "from cffi",
)


def validate_package_files(files, require_notice=True):
    """Full package gate over {path: bytes}. Returns (manifest, skill_name).

    Mirrors the native validator plus the Hub distribution rules (upstream
    license/notice preservation). Raises HubError on any violation; code is
    never executed here.
    """
    if not files or len(files) > MAX_PACKAGE_FILES:
        raise HubError(f"package file count must be 1..{MAX_PACKAGE_FILES}")
    total = 0
    folded_seen = set()
    for name, data in files.items():
        _safe_relative(name)
        if not isinstance(data, bytes):
            raise HubError(f"package content must be bytes: {name!r}")
        reject_native_payload(name, data)
        folded = unicodedata.normalize("NFC", name).casefold()
        if folded in folded_seen:
            raise HubError(f"duplicate path after NFC/case folding: {name!r}")
        folded_seen.add(folded)
        if len(data) > MAX_FILE_BYTES:
            raise HubError(f"file exceeds {MAX_FILE_BYTES} bytes: {name!r}")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HubError(f"package exceeds {MAX_TOTAL_BYTES} bytes")
        if name == "SKILL.md" and len(data) > MAX_SKILL_MD_BYTES:
            raise HubError("SKILL.md exceeds 256 KiB")
        if name == "floe.json" and len(data) > MAX_FLOE_JSON_BYTES:
            raise HubError("floe.json exceeds 64 KiB")
    if "SKILL.md" not in files:
        raise HubError("package requires SKILL.md")
    if "floe.json" not in files:
        raise HubError("Hub packages always ship floe.json")
    if len(files["SKILL.md"].splitlines()) and files["SKILL.md"].startswith(b"PK"):
        raise HubError("SKILL.md looks like an archive")
    frontmatter, _ = parse_frontmatter(files["SKILL.md"])
    manifest = parse_manifest(files["floe.json"])
    if frontmatter["name"] != manifest["id"]:
        raise HubError("SKILL.md name must match floe.json id")
    runtime = manifest["scriptRuntime"]
    scripts = [n for n in files if n.startswith("scripts/")]
    if scripts:
        if runtime == "none":
            raise HubError("scripts require an explicit runtime")
        for script in scripts:
            extension = script.rsplit(".", 1)[-1].lower()
            if extension not in _SCRIPT_EXTENSIONS[runtime]:
                raise HubError(f"script {script!r} incompatible with runtime {runtime}")
        if runtime == "python.local":
            script_bytes = sum(len(files[s]) for s in scripts)
            if script_bytes > 196_608:
                raise HubError("bundled Python exceeds the 192 KiB runtime prompt limit")
            for script in scripts:
                source = files[script].decode("utf-8", "strict")
                lowered = source.lower()
                marker = next((m for m in _LOCAL_PYTHON_FORBIDDEN if m in lowered), None)
                if marker:
                    raise HubError(f"Python script {script!r} contains prohibited marker {marker!r}")
    elif runtime != "none":
        raise HubError("runtime declared but scripts/ is empty")
    if require_notice:
        notices = [n for n in files
                   if n.startswith("references/") and re.search(
                       r"(license|notice|copying)", n.rsplit("/", 1)[-1], re.I)]
        if not notices:
            raise HubError("Hub packages must preserve the upstream license under references/")
    return manifest, frontmatter


def check_archive_bytes(data, require_notice=True):
    """Unpack with rejection gates: file-only entries, symlink rejection,
    duplicates, path safety and sizes. Returns {path: bytes}."""
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    raise HubError("package must contain files only")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise HubError(f"symbolic links are not allowed: {info.filename!r}")
                name = info.filename
                _safe_relative(name)
                if name in files:
                    raise HubError(f"duplicate package entry: {name!r}")
                if info.file_size > MAX_FILE_BYTES:
                    raise HubError(f"entry exceeds {MAX_FILE_BYTES} bytes: {name!r}")
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    raise HubError(f"entry size mismatch: {name!r}")
                files[name] = payload
    except zipfile.BadZipFile:
        raise HubError("corrupt package archive") from None
    if not files or len(files) > MAX_PACKAGE_FILES:
        raise HubError(f"archive file count violation: {len(files)}")
    if len(data) > MAX_TOTAL_BYTES:
        raise HubError("archive exceeds 8 MiB")
    validate_package_files(files, require_notice=require_notice)
    return files


def package_path_for(id_, version, channel):
    """Channel-relative immutable archive path per the integration contract."""
    prefix = "" if channel == "ios" else channel + "/"
    return f"{prefix}packages/{id_}/{version}/{id_}.zip"


# --------------------------------------------------------------------------
# registry validation
# --------------------------------------------------------------------------

REQUIRED_ENTRY_FIELDS = (
    "id", "planNumber", "kind", "source", "name", "description", "category",
    "tags", "deepAdaptation", "upstream", "firstParty", "plannedRuntime",
    "versionTarget", "minimumAppVersion", "status", "notes",
)


def _validate_pin_block(block, field, require_path):
    if block is None:
        return
    for key in ("repository", "commit", "path", "skillManifestPath", "retrievedAt"):
        if key not in block:
            raise HubError(f"{field} missing {key}")
    repository = block["repository"]
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", repository):
        raise HubError(f"{field}.repository must be an https GitHub repository URL")
    require_commit(block["commit"], f"{field}.commit")
    require_date(block["retrievedAt"], f"{field}.retrievedAt")
    for key in ("path", "skillManifestPath"):
        value = block[key]
        if (not isinstance(value, str) or not value
                or value.startswith("/") or any(p in ("", ".", "..") for p in value.split("/"))):
            raise HubError(f"{field}.{key} must be a clean repository-relative path")
    if require_path and not block["skillManifestPath"].endswith("SKILL.md"):
        raise HubError(f"{field}.skillManifestPath must end with SKILL.md")
    if require_path and not block["skillManifestPath"].startswith(block["path"] + "/"):
        raise HubError(f"{field}.skillManifestPath must live under the pinned skill path")


def _validate_status(entry, field):
    status = entry["status"]
    allowed = {"sourcePinned", "licenseChecked", "adaptation", "packaged",
               "reviewed", "qualified", "published", "executionVerified"}
    if not isinstance(status, dict) or set(status) != allowed:
        raise HubError(f"{field}.status keys must be exactly {sorted(allowed)}")
    for boolean in allowed - {"adaptation"}:
        if not isinstance(status[boolean], bool):
            raise HubError(f"{field}.status.{boolean} must be boolean")
    if status["adaptation"] not in ADAPTATION_STAGES:
        raise HubError(f"{field}.status.adaptation unknown")
    if status["reviewed"] and not status["licenseChecked"]:
        raise HubError(f"{field}: reviewed entries require a completed license check")
    if status["qualified"] and not (status["reviewed"] and status["packaged"]):
        raise HubError(f"{field}: qualified requires reviewed and packaged")
    if status["published"] and not status["qualified"]:
        raise HubError(f"{field}: published requires qualified")
    if status["executionVerified"] and status["adaptation"] != "frozen":
        raise HubError(f"{field}: executionVerified requires frozen adaptation")
    if status["packaged"] and status["adaptation"] not in ("frozen", "in-progress"):
        raise HubError(f"{field}: packaged requires adaptation in-progress or frozen")


def validate_registry(registry, expect_counts=(43, 4, 39, 9)):
    """Fail-closed structural validation of catalog/skills.json content."""
    total, builtins, optionals, deep = expect_counts
    allowed_root = {"schemaVersion", "registry", "publisher", "hub",
                    "categories", "notes", "skills"}
    if not isinstance(registry, dict) or set(registry) - allowed_root:
        raise HubError("registry root keys mismatch")
    if registry.get("schemaVersion") != REGISTRY_SCHEMA_VERSION:
        raise HubError(f"registry schemaVersion must be {REGISTRY_SCHEMA_VERSION}")
    if registry.get("registry") != "candidate":
        raise HubError("registry must declare registry=='candidate' until coordinator promotion")
    if registry.get("publisher") != "JiangNanGenius":
        raise HubError("registry publisher mismatch")
    hub = registry.get("hub")
    if not isinstance(hub, dict) or hub.get("repository") != "JiangNanGenius/floe-skill-hub":
        raise HubError("registry hub identity mismatch")
    channels = hub.get("channelRoots")
    if channels != {"ios": ".", "android": "android"}:
        raise HubError("registry channelRoots must match the integration contract")
    categories = registry.get("categories")
    if not isinstance(categories, list) or {c["id"] for c in categories} != set(CATEGORIES):
        raise HubError("registry categories must cover exactly the seven plan categories")
    for category in categories:
        require_bilingual(category.get("name", {}), f"category {category.get('id')} name")
    skills = registry.get("skills")
    if not isinstance(skills, list) or len(skills) != total:
        raise HubError(f"registry must contain exactly {total} candidate entries")
    seen_ids, seen_plan = set(), set()
    kind_count = {"builtin": 0, "optional": 0}
    deep_count = 0
    for entry in skills:
        field = f"registry entry {entry.get('id', '?')}"
        if set(entry) - set(REQUIRED_ENTRY_FIELDS) or set(entry) != set(REQUIRED_ENTRY_FIELDS):
            raise HubError(f"{field} keys must be exactly the fixed registry shape")
        require_id(entry["id"])
        if entry["id"] in seen_ids:
            raise HubError(f"{field}: duplicate id")
        seen_ids.add(entry["id"])
        plan = entry["planNumber"]
        if not isinstance(plan, int) or not 1 <= plan <= total or plan in seen_plan:
            raise HubError(f"{field}: planNumber must be a unique 1..{total} row")
        seen_plan.add(plan)
        if entry["kind"] not in ENTRY_KINDS or entry["source"] not in SOURCE_CODES:
            raise HubError(f"{field}: kind/source outside the contract")
        kind_count[entry["kind"]] += 1
        builtin_id = entry["id"] in RESERVED_BUILTIN_IDS
        if builtin_id != (entry["kind"] == "builtin"):
            raise HubError(f"{field}: reserved official ids and builtin kind must agree")
        require_bilingual(entry["name"], f"{field} name")
        require_bilingual(entry["description"], f"{field} description")
        zh_name = entry["name"]["zh-Hans"]
        if zh_name != entry["name"]["en"] and not has_cjk(zh_name):
            raise HubError(f"{field}: the Simplified Chinese display name must be translated "
                           "unless it intentionally equals the brand name")
        if entry["category"] not in CATEGORIES:
            raise HubError(f"{field}: unknown category")
        tags = entry["tags"]
        if (not isinstance(tags, list) or not 2 <= len(tags) <= 12
                or len(set(tags)) != len(tags)
                or any(not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", t) for t in tags)):
            raise HubError(f"{field}: tags must be 2-12 unique lowercase slugs")
        if not isinstance(entry["deepAdaptation"], bool):
            raise HubError(f"{field}: deepAdaptation must be boolean")
        deep_count += int(entry["deepAdaptation"])
        if entry["upstream"] is not None and entry["firstParty"] is not None:
            raise HubError(f"{field}: upstream and firstParty must be mutually exclusive")
        if entry["upstream"] is not None:
            block = entry["upstream"]
            _validate_pin_block(block, f"{field}.upstream", require_path=True)
            if block.get("repository", "").endswith("/floe-agent"):
                raise HubError(f"{field}: upstream block must not carry first-party pins")
            if block.get("licenseStatus") not in LICENSE_STATUSES or block["licenseStatus"] == "floe-owned":
                raise HubError(f"{field}.upstream.licenseStatus invalid")
            evidence = block.get("licenseEvidencePath")
            if block["licenseStatus"] == "verified" and not evidence:
                raise HubError(f"{field}: verified license requires evidence path")
            if evidence is not None and evidence != "" and (
                    evidence.startswith("/") or ".." in evidence.split("/")):
                raise HubError(f"{field}: licenseEvidencePath must be repo-relative")
            if block["licenseStatus"] == "blocked-no-upstream-license":
                if entry["status"]["licenseChecked"]:
                    raise HubError(f"{field}: blocked license cannot be marked checked")
                if entry["notes"].get("en", "").strip() == "" or entry["notes"].get("zh-Hans", "").strip() == "":
                    raise HubError(f"{field}: license blockers require bilingual reasons")
        if entry["firstParty"] is not None:
            _validate_pin_block(entry["firstParty"], f"{field}.firstParty", require_path=False)
            if entry["source"] != "F" or entry["kind"] != "builtin":
                raise HubError(f"{field}: firstParty pins belong to builtin F entries")
            if entry["firstParty"].get("licenseStatus") != "floe-owned":
                raise HubError(f"{field}: first-party entries are floe-owned")
            released = entry["firstParty"].get("releasedVersion")
            staged = entry["firstParty"].get("stagedSourceVersion")
            for value in (released, staged):
                if value is not None:
                    require_version(value, "firstParty version")
        planned = entry["plannedRuntime"]
        if not isinstance(planned, dict):
            raise HubError(f"{field}: plannedRuntime required")
        if planned.get("scriptRuntime") not in SCRIPT_RUNTIMES:
            raise HubError(f"{field}: plannedRuntime.scriptRuntime unknown")
        for list_field, universe in (("capabilities", CAPABILITIES),
                                     ("installPlatforms", STORE_CHANNELS)):
            value = planned.get(list_field)
            if not isinstance(value, list) or any(v not in universe for v in value) \
                    or len(set(value)) != len(value):
                raise HubError(f"{field}: plannedRuntime.{list_field} invalid")
        tools = planned.get("tools")
        if not isinstance(tools, list) or any(not TOOL_PATTERN.fullmatch(t) for t in tools) \
                or len(set(tools)) != len(tools):
            raise HubError(f"{field}: plannedRuntime.tools invalid")
        runtime = planned["scriptRuntime"]
        needs_exec = runtime != "none"
        if needs_exec and ("execution.remote" not in planned["capabilities"]
                           or "exec.shell" not in tools):
            raise HubError(f"{field}: script runtimes declare execution.remote + exec.shell")
        if not needs_exec and ("execution.remote" in planned["capabilities"]
                               or "exec.shell" in tools):
            raise HubError(f"{field}: guide-only entries must not declare execution")
        dependencies = planned.get("pythonPackagesPlan")
        if not isinstance(dependencies, list) or any(not isinstance(d, str) for d in dependencies):
            raise HubError(f"{field}: pythonPackagesPlan is a string list of planned specs")
        execution = planned.get("execution")
        if not isinstance(execution, dict) or set(execution) != {"os", "arch", "evidence"}:
            raise HubError(f"{field}: plannedRuntime.execution needs os/arch/evidence")
        if needs_exec:
            if execution["os"] not in PLATFORMS + (None,) or execution["arch"] not in (
                    "riscv64", "x86_64", "aarch64", "n/a", None):
                raise HubError(f"{field}: planned execution os/arch invalid")
            if execution["evidence"] not in EXECUTION_EVIDENCE:
                raise HubError(f"{field}: planned execution evidence invalid")
            if execution["evidence"] == "guest-verified" and entry["status"]["executionVerified"] is False:
                raise HubError(f"{field}: guest-verified evidence requires status.executionVerified")
        else:
            if execution != {"os": None, "arch": "n/a", "evidence": "unproven"}:
                raise HubError(f"{field}: guide-only entries carry no execution claim")
        require_bilingual(entry["notes"], f"{field} notes", allow_empty=True)
        if entry["versionTarget"] is not None:
            require_version(entry["versionTarget"], "versionTarget")
        if entry["minimumAppVersion"] is not None:
            require_version(entry["minimumAppVersion"], "minimumAppVersion")
        _validate_status(entry, field)
    if kind_count["builtin"] != builtins or kind_count["optional"] != optionals:
        raise HubError(f"registry kind counts wrong: {kind_count}")
    if deep_count != deep:
        raise HubError(f"registry must mark exactly {deep} deep adaptations")
    return registry


# --------------------------------------------------------------------------
# catalog (channel feed) building
# --------------------------------------------------------------------------

PERMISSION_POLICY = {
    "automaticInstallWhenReviewedAndGranted": True,
    "deltaOnlyApproval": True,
    "selfApprovalProhibited": True,
    "userDisabledAndRemovedPriority": "user",
    "temporaryTaskCeiling": "client-enforced",
}


def catalog_entry(registry_entry, package=None, review=None, install_offer="none"):
    """Render one feed entry from the registry plus released facts."""
    entry = {
        "id": registry_entry["id"],
        "planNumber": registry_entry["planNumber"],
        "kind": registry_entry["kind"],
        "source": registry_entry["source"],
        "name": registry_entry["name"],
        "description": registry_entry["description"],
        "category": registry_entry["category"],
        "tags": registry_entry["tags"],
        "deepAdaptation": registry_entry["deepAdaptation"],
        "upstream": registry_entry["upstream"],
        "firstParty": registry_entry["firstParty"],
        "runtime": registry_entry["plannedRuntime"],
        "version": registry_entry["versionTarget"],
        "minimumAppVersion": registry_entry["minimumAppVersion"],
        "status": registry_entry["status"],
        "notes": registry_entry["notes"],
        "package": package,
        "review": review,
        "installOffer": install_offer,
    }
    return entry


def build_catalog(registry, channel, feed_status, entries, source_commit,
                  generated_note=None):
    """Deterministic channel feed body (caller signs the exact bytes).

    `source_commit` is the audited source revision X whose content this feed
    describes — signed provenance. It is NOT and never contains the hash of
    the commit Y that holds the published feed/signature/archive bytes; the
    client resolves Y externally and fetches every artifact at Y. X is
    normally an ancestor of Y and X != Y is the normal, expected shape.
    """
    if channel not in ("ios", "android"):
        raise HubError("channel must be ios or android")
    if feed_status not in ("production", "fixture"):
        raise HubError("feedStatus must be production or fixture")
    if feed_status == "production":
        if source_commit is None:
            raise HubError("production feeds must bind the audited source commit (X)")
        require_commit(source_commit, "source_commit")
    elif source_commit is not None:
        raise HubError("fixture feeds never carry a source commit binding")
    counts = {
        "total": len(entries),
        "builtin": sum(1 for e in entries if e["kind"] == "builtin"),
        "optional": sum(1 for e in entries if e["kind"] == "optional"),
        "deepAdaptation": sum(1 for e in entries if e["deepAdaptation"]),
        "packaged": sum(1 for e in entries if e["package"]),
        "reviewed": sum(1 for e in entries if e["review"]),
        "qualified": sum(1 for e in entries if e["status"]["qualified"]),
        "offerQualified": sum(1 for e in entries if e["installOffer"] == "qualified"),
    }
    catalog = {
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "publisher": "JiangNanGenius",
        "channel": channel,
        "feedStatus": feed_status,
        "hubRepository": "JiangNanGenius/floe-skill-hub",
        "sourceCommit": source_commit,
        "permissionPolicy": PERMISSION_POLICY,
        "entries": entries,
        "counts": counts,
    }
    if generated_note:
        catalog["generatedNote"] = generated_note
    return catalog


def validate_catalog(catalog, channel=None, allow_fixture=False):
    if not isinstance(catalog, dict):
        raise HubError("catalog must be an object")
    required = {"schemaVersion", "publisher", "channel", "feedStatus",
                "hubRepository", "sourceCommit", "permissionPolicy",
                "entries", "counts"}
    if set(catalog) - required - {"generatedNote"} or set(catalog) < required:
        raise HubError("catalog root keys mismatch")
    if catalog["schemaVersion"] != CATALOG_SCHEMA_VERSION:
        raise HubError(f"catalog schemaVersion must be {CATALOG_SCHEMA_VERSION}")
    if catalog["publisher"] != "JiangNanGenius":
        raise HubError("catalog publisher mismatch")
    if channel and catalog["channel"] != channel:
        raise HubError("catalog channel mismatch")
    if catalog["channel"] not in ("ios", "android"):
        raise HubError("catalog channel unknown")
    if catalog["feedStatus"] == "fixture" and not allow_fixture:
        raise HubError("fixture feeds never validate in production mode")
    if catalog["feedStatus"] not in ("production", "fixture"):
        raise HubError("catalog feedStatus unknown")
    commit = catalog["sourceCommit"]
    if commit is not None:
        require_commit(commit, "sourceCommit")
    if catalog["feedStatus"] == "production" and commit is None:
        raise HubError("production catalogs bind the audited source commit (X); "
                       "artifact retrieval pins the separately resolved publication commit (Y)")
    if catalog["permissionPolicy"] != PERMISSION_POLICY:
        raise HubError("catalog permissionPolicy drifted from the fixed contract")
    entries = catalog["entries"]
    seen = set()
    for entry in entries:
        field = f"catalog entry {entry.get('id', '?')}"
        required_entry = (set(REQUIRED_ENTRY_FIELDS)
                          - {"plannedRuntime", "versionTarget"}
                          | {"runtime", "version", "package", "review", "installOffer"})
        if set(entry) != required_entry:
            raise HubError(f"{field} keys must be exactly the fixed feed shape")
        require_id(entry["id"])
        if entry["id"] in seen:
            raise HubError(f"{field}: duplicate id in feed")
        seen.add(entry["id"])
        if catalog["channel"] not in entry["runtime"]["installPlatforms"]:
            raise HubError(f"{field}: entry installPlatforms must include the feed channel")
        if entry["installOffer"] not in INSTALL_OFFERS:
            raise HubError(f"{field}: unknown installOffer")
        if entry["installOffer"] == "fixture-simulated":
            if catalog["feedStatus"] != "fixture":
                raise HubError(f"{field}: fixture offers require a fixture feed")
            if not entry["id"].startswith("fixture-"):
                raise HubError(f"{field}: fixture offers require fixture- ids")
        if entry["installOffer"] == "qualified":
            if catalog["feedStatus"] != "production":
                raise HubError(f"{field}: qualified offers never appear in fixture feeds")
            if not entry["package"] or not entry["review"]:
                raise HubError(f"{field}: qualified offers require package and review")
            if not entry["status"]["qualified"]:
                raise HubError(f"{field}: qualified offer without qualified status")
        package = entry["package"]
        if package is not None:
            if set(package) != {"path", "size", "sha256", "contentDigest", "containsScripts"}:
                raise HubError(f"{field}: package binding keys mismatch")
            expected = package_path_for(entry["id"], entry["version"], catalog["channel"])
            if package["path"] != expected:
                raise HubError(f"{field}: package path must be {expected}")
            if not isinstance(package["size"], int) or isinstance(package["size"], bool) \
                    or not 0 < package["size"] <= MAX_TOTAL_BYTES:
                raise HubError(f"{field}: package size invalid")
            require_hex64(package["sha256"], f"{field} sha256")
            require_hex64(package["contentDigest"], f"{field} contentDigest")
            if not isinstance(package["containsScripts"], bool):
                raise HubError(f"{field}: containsScripts must be boolean")
        review = entry["review"]
        if review is not None:
            if set(review) != {"path", "sha256", "keyID"}:
                raise HubError(f"{field}: review binding keys mismatch")
            if not review["path"].startswith("reviews/") or not review["path"].endswith(".review.json"):
                raise HubError(f"{field}: review path must be reviews/<id>/<version>.review.json")
            expected_path = f"reviews/{entry['id']}/{entry['version']}.review.json"
            if review["path"] != expected_path:
                raise HubError(f"{field}: review path must be {expected_path}")
            require_hex64(review["sha256"], f"{field} review sha256")
            if catalog["feedStatus"] == "production":
                if review["keyID"] == FIXTURE_KEY_ID:
                    raise HubError(f"{field}: fixture review can never back a production entry")
            elif review["keyID"] != FIXTURE_KEY_ID:
                raise HubError(f"{field}: fixture feeds only bind fixture reviews")
        if entry["package"] is None and entry["review"] is not None:
            raise HubError(f"{field}: review binding requires a package")
        if entry["status"]["reviewed"] and entry["review"] is None:
            raise HubError(f"{field}: reviewed status requires a review binding")
        if entry["status"]["qualified"] and (entry["package"] is None
                                             or entry["review"] is None):
            raise HubError(f"{field}: qualified requires package and review")
        if entry["minimumAppVersion"] is not None:
            require_version(entry["minimumAppVersion"], f"{field} minimumAppVersion")
        if entry["package"] is not None and entry["minimumAppVersion"] is None:
            raise HubError(f"{field}: packaged entries require minimumAppVersion")
    counts = catalog["counts"]
    recomputed = {
        "total": len(entries),
        "builtin": sum(1 for e in entries if e["kind"] == "builtin"),
        "optional": sum(1 for e in entries if e["kind"] == "optional"),
        "deepAdaptation": sum(1 for e in entries if e["deepAdaptation"]),
        "packaged": sum(1 for e in entries if e["package"]),
        "reviewed": sum(1 for e in entries if e["review"]),
        "qualified": sum(1 for e in entries if e["status"]["qualified"]),
        "offerQualified": sum(1 for e in entries if e["installOffer"] == "qualified"),
    }
    if counts != recomputed:
        raise HubError(f"catalog counts drifted: {counts} != {recomputed}")
    return catalog


# --------------------------------------------------------------------------
# review records
# --------------------------------------------------------------------------

def validate_review(record, entry=None):
    required = {"schemaVersion", "id", "version", "contentDigest", "packageSha256",
                "reviewedCapabilities", "reviewedTools", "reviewedPythonPackages",
                "execution", "reviewStage", "reviewedAt", "reviewer", "decision",
                "notes"}
    if not isinstance(record, dict) or set(record) != required:
        raise HubError("review record keys mismatch")
    if record["schemaVersion"] != REVIEW_SCHEMA_VERSION:
        raise HubError("review schemaVersion must be 1")
    require_id(record["id"], "review id")
    require_version(record["version"], "review version")
    require_hex64(record["contentDigest"], "review contentDigest")
    require_hex64(record["packageSha256"], "review packageSha256")
    for field, universe in (("reviewedCapabilities", CAPABILITIES),):
        value = record[field]
        if not isinstance(value, list) or any(v not in universe for v in value) \
                or len(set(value)) != len(value):
            raise HubError(f"review {field} invalid")
    tools = record["reviewedTools"]
    if not isinstance(tools, list) or any(not TOOL_PATTERN.fullmatch(t) for t in tools) \
            or len(set(tools)) != len(tools):
        raise HubError("review reviewedTools invalid")
    packages = record["reviewedPythonPackages"]
    if not isinstance(packages, list) or len(packages) > MAX_PY_PACKAGES:
        raise HubError("review reviewedPythonPackages invalid")
    for package in packages:
        if not isinstance(package, dict) or set(package) != {"spec", "purpose", "capabilities"}:
            raise HubError("reviewed package entries mirror the floe.json shape")
        if "== " not in package["spec"] and "==" not in package["spec"]:
            raise HubError("reviewed packages must be exact name==version specs")
    execution = record["execution"]
    if not isinstance(execution, dict) or set(execution) != {"os", "arch", "evidence"}:
        raise HubError("review execution needs os/arch/evidence")
    if execution["os"] not in ("linux", "macos", "ios", None):
        raise HubError("review execution os unknown")
    if execution["arch"] not in ("riscv64", "x86_64", "aarch64", "n/a", None):
        raise HubError("review execution arch unknown")
    if execution["evidence"] not in EXECUTION_EVIDENCE:
        raise HubError("review execution evidence unknown")
    if record["reviewStage"] not in ("static-content-reviewed", "guest-execution-qualified"):
        raise HubError("review reviewStage unknown")
    require_date(record["reviewedAt"], "review reviewedAt")
    if not isinstance(record["reviewer"], str) or not 1 <= len(record["reviewer"]) <= 64:
        raise HubError("review reviewer must be 1-64 characters")
    if record["decision"] not in ("approve", "reject"):
        raise HubError("review decision unknown")
    require_bilingual(record["notes"], "review notes")
    if record["reviewStage"] == "guest-execution-qualified" and execution["evidence"] != "guest-verified":
        raise HubError("guest-execution-qualified requires guest-verified execution evidence")
    if entry is not None:
        if record["id"] != entry["id"] or record["version"] != entry["version"]:
            raise HubError("review identity drift against the catalog entry")
        if entry["package"] and record["contentDigest"] != entry["package"]["contentDigest"]:
            raise HubError("review contentDigest does not match the bound package")
        if entry["package"] and record["packageSha256"] != entry["package"]["sha256"]:
            raise HubError("review packageSha256 does not match the bound archive")
        declared = set(entry["runtime"]["capabilities"]) | set(entry["runtime"]["tools"])
        requested = set(record["reviewedCapabilities"]) | set(record["reviewedTools"])
        if not requested <= declared:
            raise HubError("review must bind the tools/capabilities the entry declared, not exceed them")
    return record


def join_review(record, manifest, package_binding, field):
    """Bind a verified review record to the real archive, not the plan.

    The record must vouch for exactly these bytes (contentDigest/packageSha256),
    cover exactly the manifest's declared capabilities/tools/dependencies
    (nothing unreviewed, nothing granted outside the manifest), carry an
    approve decision, and keep the execution plane consistent with the
    manifest's declared runtime. The native client repeats these checks
    independently against the signed catalog and downloaded bytes.
    """
    if record["id"] != manifest["id"] or record["version"] != manifest["version"]:
        raise HubError(f"{field}: review identity does not match the packaged manifest")
    if record["contentDigest"] != package_binding["contentDigest"]:
        raise HubError(f"{field}: review contentDigest does not match the actual package bytes")
    if record["packageSha256"] != package_binding["sha256"]:
        raise HubError(f"{field}: review packageSha256 does not match the actual archive")
    if record["decision"] != "approve":
        raise HubError(f"{field}: only an approve decision can bind a qualified entry")
    if set(record["reviewedCapabilities"]) != set(manifest["capabilities"]):
        raise HubError(f"{field}: review must cover exactly the manifest's declared capabilities")
    if set(record["reviewedTools"]) != set(manifest["tools"]):
        raise HubError(f"{field}: review must cover exactly the manifest's declared tools")
    reviewed_specs = {p["spec"].lower() for p in record["reviewedPythonPackages"]}
    manifest_specs = {p["spec"].lower() for p in manifest["pythonPackages"]}
    if reviewed_specs != manifest_specs:
        raise HubError(f"{field}: review must cover exactly the manifest's declared dependencies")
    execution = record["execution"]
    if manifest["scriptRuntime"] == "none":
        if execution != {"os": None, "arch": "n/a", "evidence": "unproven"}:
            raise HubError(f"{field}: a guide-only package review must carry no execution claim")
    else:
        if execution["os"] != "linux":
            raise HubError(f"{field}: script packages execute only in the task Linux environment")
        if execution["evidence"] == "guest-verified" and record["reviewStage"] != "guest-execution-qualified":
            raise HubError(f"{field}: guest-verified evidence requires the qualified review stage")
    return record


def review_digest(record_bytes):
    """The binding digest published in the catalog review block."""
    return sha256_hex(record_bytes)


# --------------------------------------------------------------------------
# legacy four-item compatibility view
# --------------------------------------------------------------------------

def build_legacy_view(catalog_bytes):
    """Render the old-shape schemaVersion-2 catalog from a production feed.

    Exactly the four reserved ids, old path prefix 'skill-hub/packages/...'
    (the old repo location), publisher and released package facts only.
    New candidates never enter this decoder.
    """
    catalog = json.loads(catalog_bytes)
    validate_catalog(catalog, channel="ios", allow_fixture=False)
    legacy_packages = []
    for entry in catalog["entries"]:
        if entry["id"] not in RESERVED_BUILTIN_IDS:
            continue
        if not entry["package"] or not entry["status"]["qualified"]:
            raise HubError(
                f"legacy view: {entry['id']} has no qualified package; the "
                "compatibility view must reuse released bytes, not candidates")
        package = entry["package"]
        legacy_packages.append({
            "contentDigest": package["contentDigest"],
            "id": entry["id"],
            "minimumAppVersion": entry["minimumAppVersion"],
            "path": "skill-hub/packages/" + package["path"],
            "releaseNotes": {
                "en": entry["notes"]["en"] or entry["description"]["en"],
                "zh-Hans": entry["notes"]["zh-Hans"] or entry["description"]["zh-Hans"],
            },
            "sha256": package["sha256"],
            "size": package["size"],
            "version": entry["version"],
        })
    if {p["id"] for p in legacy_packages} != set(RESERVED_BUILTIN_IDS):
        raise HubError("legacy view requires all four reserved guides")
    legacy_packages.sort(key=lambda p: p["id"])
    return encoded({"schemaVersion": LEGACY_CATALOG_SCHEMA_VERSION,
                    "publisher": "JiangNanGenius",
                    "packages": legacy_packages,
                    "models": []})
