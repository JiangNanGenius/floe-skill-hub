#!/usr/bin/env python3
"""Read-only showcase content gate for the Hub website-client lane (H7).

Validates the frozen v1 presentation contract in showcase/CONTRACT.md:

  showcase/skills.json   editorial records (overview/useCases/examples/cover/gallery)
  showcase/links.json    evidence-backed cross-skill reference audits
  showcase/media/        original or licensed media (bounds + magic-MIME + SVG safety)

This tool NEVER writes, NEVER executes fetched source, image code or packages,
and NEVER touches catalog facts beyond a read-only join against
catalog/skills.json (names for the alt-derivation rule and the registry id set).

Checks (fail closed, aggregate report):
  1. skills.json shape: exact top-level keys, schemaVersion 1, editorPicks
     unique / <= 12 / subset of entries, entries join the 43-registry id set
     (orphans and missing reported, never auto-qualified)
  2. editorial shape: exact keys, bilingual plain {en, zh-Hans} text with
     bounds and no control characters, useCases/examples <= 12, example
     {prompt, output} pairs, media reference shape and strict relative paths
     under showcase/media/ (no URL / traversal / backslash / control char /
     symlink / empty component)
  3. media tree: <= 256 files, <= 4 MiB per file, <= 32 MiB total, PNG /
     JPEG / WebP / SVG magic bytes only, SVGs free of scripts, event
     handlers, foreignObject, DTD/entities and external fetch references;
     every media path component (ancestors included) must be free of
     symlinks, and malformed reference shapes are rejected in a controlled
     way (never a crash)
  4. links.json shape: exact top-level keys, integer schemaVersion 1 (bools
     excluded), auditStatus audited/pending, <= 32 links per entry, relation
     references/optional/requires, hub targets joined against the registry,
     external-skill targets pinned to HTTPS GitHub source URLs, evidence
     records naming existing strict relative repo files with 64-hex sha256,
     1-based ordered integer line bounds (bools excluded) and no symlinked
     path component; all JSON documents reject duplicate keys
  5. requires-graph: bounded walk (depth <= 4, nodes <= 64) proving no
     required-dependency cycle exists
  6. editorial hygiene: catalog curation ratings never leak into editorial
     text; an explicit alt never duplicates the canonical basic metadata

Exit 0 = all gates pass; non-zero with a precise reason list.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[2]
SHOWCASE = REPO / "showcase"
MEDIA_ROOT = SHOWCASE / "media"

LIMIT_JSON_BYTES = 2 * 1024 * 1024        # 2 MiB per JSON document
LIMIT_MEDIA_FILE_BYTES = 4 * 1024 * 1024  # 4 MiB per media file
LIMIT_MEDIA_TOTAL_BYTES = 32 * 1024 * 1024  # 32 MiB media total
LIMIT_MEDIA_FILES = 256
LIMIT_PICKS = 12
LIMIT_ARRAY = 12
LIMIT_LINKS = 32
LIMIT_EVIDENCE = 8
LIMIT_TEXT = 4000

ID_GRAMMAR = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MEDIA_KINDS = {"illustration", "example-output", "app-screenshot"}
RELATIONS = {"references", "optional", "requires"}
RATING_LEAK = re.compile(r"[★☆]|editorial score|curat(ed|ion) (score|rating)", re.I)

SVG_NS = "http://www.w3.org/2000/svg"
MAGIC = (
    ("png", b"\x89PNG\r\n\x1a\n"),
    ("jpeg", b"\xff\xd8\xff"),
    ("webp", b"RIFF"),
)


def fail(reasons, message):
    reasons.append(message)


def is_int(value):
    """True only for a genuine int (bools are explicitly excluded)."""
    return isinstance(value, int) and not isinstance(value, bool)


def no_duplicate_keys(pairs):
    """object_pairs_hook rejecting duplicate keys instead of last-wins."""
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def has_symlink_component(path):
    """True if any ancestor or leaf component below REPO is a symlink."""
    try:
        rel = path.relative_to(REPO)
    except ValueError:
        return True
    current = REPO
    for part in rel.parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def ensure_no_symlink(path, where, reasons):
    if has_symlink_component(path):
        fail(reasons, f"{where}: symlinked path component is not allowed")
        return False
    return True


def load_json(path, reasons):
    where = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
    if not ensure_no_symlink(path, where, reasons):
        return None, None
    try:
        raw = path.read_bytes()
    except OSError as exc:
        fail(reasons, f"{where}: unreadable: {exc}")
        return None, None
    if len(raw) > LIMIT_JSON_BYTES:
        fail(reasons, f"{where}: {len(raw)} bytes exceeds 2 MiB JSON bound")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(reasons, f"{where}: invalid UTF-8 JSON: {exc}")
        return None, raw
    try:
        return json.loads(text, object_pairs_hook=no_duplicate_keys), raw
    except ValueError as exc:
        fail(reasons, f"{where}: invalid JSON: {exc}")
        return None, raw


def check_bilingual(node, where, reasons, required=True):
    """A bilingual plain-text field is exactly {en, zh-Hans} of bounded strings."""
    if node is None:
        if required:
            fail(reasons, f"{where}: missing bilingual object")
        return None
    if not isinstance(node, dict) or set(node.keys()) != {"en", "zh-Hans"}:
        fail(reasons, f"{where}: keys must be exactly {{en, zh-Hans}}")
        return None
    for lang in ("en", "zh-Hans"):
        value = node[lang]
        if not isinstance(value, str) or not value.strip():
            fail(reasons, f"{where}.{lang}: must be a non-empty plain string")
            continue
        if len(value) > LIMIT_TEXT:
            fail(reasons, f"{where}.{lang}: {len(value)} chars exceeds {LIMIT_TEXT}")
        if CONTROL.search(value):
            fail(reasons, f"{where}.{lang}: contains control characters")
        if value != value.strip():
            fail(reasons, f"{where}.{lang}: leading/trailing whitespace")
        if RATING_LEAK.search(value):
            fail(reasons, f"{where}.{lang}: catalog curation rating material leaked into editorial text")
    return node


def check_media_ref(ref, where, reasons):
    """Validate one media reference object; return its repo-relative path or None."""
    if not isinstance(ref, dict):
        fail(reasons, f"{where}: media reference must be an object")
        return None
    allowed = {"path", "kind", "credit", "alt", "caption"}
    if not set(ref.keys()) <= allowed or not {"path", "kind", "credit"} <= set(ref.keys()):
        fail(reasons, f"{where}: keys must be path/kind/credit plus optional alt/caption")
    kind = ref.get("kind")
    if kind not in MEDIA_KINDS:
        fail(reasons, f"{where}.kind: {kind!r} not in {sorted(MEDIA_KINDS)}")
    path = ref.get("path")
    rel = None
    if not isinstance(path, str) or not path:
        fail(reasons, f"{where}.path: must be a non-empty string")
    else:
        rel = check_media_path(path, f"{where}.path", reasons)
    credit = check_bilingual(ref.get("credit"), f"{where}.credit", reasons)
    alt = check_bilingual(ref.get("alt"), f"{where}.alt", reasons, required=False)
    caption = check_bilingual(ref.get("caption"), f"{where}.caption", reasons, required=False)
    if kind in ("example-output", "app-screenshot") and caption is None:
        fail(reasons, f"{where}.caption: required for non-illustration media")
    if credit:
        for lang in ("en", "zh-Hans"):
            if lang in credit and len(credit[lang]) > 600:
                fail(reasons, f"{where}.credit.{lang}: exceeds 600 chars")
    return rel


def check_media_path(path, where, reasons):
    """Strict relative file under showcase/media/. Returns the relative path."""
    if CONTROL.search(path):
        fail(reasons, f"{where}: control characters")
        return None
    if "\\" in path:
        fail(reasons, f"{where}: backslash not allowed")
        return None
    if "://" in path or path.startswith("//"):
        fail(reasons, f"{where}: URL not allowed")
        return None
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        fail(reasons, f"{where}: empty, '.' or '..' component")
        return None
    if len(parts) < 3 or parts[0] != "showcase" or parts[1] != "media":
        fail(reasons, f"{where}: must live under showcase/media/")
        return None
    target = REPO / path
    try:
        if not ensure_no_symlink(target, where, reasons):
            return None
        if not target.is_file():
            fail(reasons, f"{where}: file does not exist")
            return None
    except OSError as exc:
        fail(reasons, f"{where}: {exc}")
        return None
    return path


def magic_kind(data):
    for name, sig in MAGIC:
        if data.startswith(sig):
            if name == "webp":
                if len(data) >= 12 and data[8:12] == b"WEBP":
                    return name
                return None
            return name
    return None


def check_svg(data, where, reasons):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        fail(reasons, f"{where}: SVG is not UTF-8 text")
        return
    if "<svg" not in text:
        fail(reasons, f"{where}: no <svg> root")
    lowered = text.lower()
    for banned, label in (("<script", "script element"), ("<foreignobject", "foreignObject")):
        if banned in lowered:
            fail(reasons, f"{where}: SVG contains {label}")
    if "<!doctype" in lowered or "<!entity" in lowered:
        fail(reasons, f"{where}: SVG contains DTD/entity declaration")
    if re.search(r"\son[a-zA-Z]+\s*=", text):
        fail(reasons, f"{where}: SVG contains an event handler attribute")
    if re.search(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)[a-zA-Z]+;", text):
        fail(reasons, f"{where}: SVG contains a non-standard entity reference")
    for match in re.finditer(r"(?:xlink:href|href)\s*=\s*[\"']([^\"']*)[\"']", text):
        if not match.group(1).startswith("#"):
            fail(reasons, f"{where}: SVG external href {match.group(1)!r}")
    for match in re.finditer(r"url\(([^)]*)\)", text):
        if not match.group(1).strip().startswith("#"):
            fail(reasons, f"{where}: SVG external url() {match.group(1)!r}")
    if re.search(r"@import", text, re.I):
        fail(reasons, f"{where}: SVG contains @import")
    for match in re.finditer(r"https?://[^\s\"'<>()]+", text):
        if match.group(0) != SVG_NS:
            fail(reasons, f"{where}: SVG external reference {match.group(0)!r}")


def check_media_tree(reasons):
    referenced = set()
    count = 0
    total = 0
    if not MEDIA_ROOT.is_dir():
        fail(reasons, "showcase/media: missing directory")
        return referenced
    ensure_no_symlink(MEDIA_ROOT, "showcase/media", reasons)
    for path in sorted(MEDIA_ROOT.rglob("*")):
        try:
            if not ensure_no_symlink(path, str(path.relative_to(REPO)), reasons):
                continue
            if not path.is_file():
                continue
        except OSError as exc:
            fail(reasons, f"{path.relative_to(REPO)}: {exc}")
            continue
        count += 1
        size = path.stat().st_size
        total += size
        rel = str(path.relative_to(REPO))
        referenced.add(rel)
        if size > LIMIT_MEDIA_FILE_BYTES:
            fail(reasons, f"{rel}: {size} bytes exceeds 4 MiB per-file bound")
        data = path.read_bytes()
        kind = magic_kind(data)
        if kind is None:
            stripped = data.lstrip()
            if stripped.startswith(b"<") and b"<svg" in data[:4096]:
                check_svg(data, rel, reasons)
            else:
                fail(reasons, f"{rel}: unsupported media type (magic bytes not PNG/JPEG/WebP/SVG)")
        elif kind == "svg":
            check_svg(data, rel, reasons)
    if count > LIMIT_MEDIA_FILES:
        fail(reasons, f"showcase/media: {count} files exceeds 256 file bound")
    if total > LIMIT_MEDIA_TOTAL_BYTES:
        fail(reasons, f"showcase/media: {total} bytes exceeds 32 MiB total bound")
    return referenced


def check_skills(reasons, registry_ids, canonical_names):
    doc, _ = load_json(SHOWCASE / "skills.json", reasons)
    if not isinstance(doc, dict):
        return None
    if set(doc.keys()) != {"schemaVersion", "editorPicks", "entries"}:
        fail(reasons, "showcase/skills.json: top-level keys must be exactly schemaVersion/editorPicks/entries")
    if not (is_int(doc.get("schemaVersion")) and doc["schemaVersion"] == 1):
        fail(reasons, "showcase/skills.json: schemaVersion must be the integer 1")
    picks = doc.get("editorPicks")
    if not isinstance(picks, list) or len(picks) > LIMIT_PICKS or len(set(picks)) != len(picks):
        fail(reasons, "showcase/skills.json: editorPicks must be a unique list of at most 12")
        picks = []
    entries = doc.get("entries")
    if not isinstance(entries, dict):
        fail(reasons, "showcase/skills.json: entries must be an object keyed by skill id")
        return doc
    for pick in picks:
        if not isinstance(pick, str) or pick not in entries:
            fail(reasons, f"showcase/skills.json: editorPick {pick!r} has no entry")
    for sid in entries:
        if not ID_GRAMMAR.match(sid):
            fail(reasons, f"showcase/skills.json: id {sid!r} does not match catalog id grammar")
    orphan = sorted(set(entries) - registry_ids)
    missing = sorted(registry_ids - set(entries))
    if orphan:
        fail(reasons, f"showcase/skills.json: entries not in the catalog registry (pending orphans): {orphan}")
    if missing:
        fail(reasons, f"showcase/skills.json: registry ids without editorial entries: {missing}")
    media_paths = set()
    for sid, editorial in entries.items():
        where = f"showcase/skills.json entries[{sid!r}]"
        if not isinstance(editorial, dict) or set(editorial.keys()) != {"overview", "useCases", "examples", "cover", "gallery"}:
            fail(reasons, f"{where}: keys must be exactly overview/useCases/examples/cover/gallery")
            continue
        check_bilingual(editorial.get("overview"), f"{where}.overview", reasons)
        use_cases = editorial.get("useCases")
        if not isinstance(use_cases, list) or len(use_cases) > LIMIT_ARRAY:
            fail(reasons, f"{where}.useCases: must be a list of at most {LIMIT_ARRAY}")
        else:
            for i, uc in enumerate(use_cases):
                check_bilingual(uc, f"{where}.useCases[{i}]", reasons)
        examples = editorial.get("examples")
        if not isinstance(examples, list) or len(examples) > LIMIT_ARRAY:
            fail(reasons, f"{where}.examples: must be a list of at most {LIMIT_ARRAY}")
        else:
            for i, ex in enumerate(examples):
                if not isinstance(ex, dict) or set(ex.keys()) != {"prompt", "output"}:
                    fail(reasons, f"{where}.examples[{i}]: keys must be exactly prompt/output")
                    continue
                check_bilingual(ex.get("prompt"), f"{where}.examples[{i}].prompt", reasons)
                check_bilingual(ex.get("output"), f"{where}.examples[{i}].output", reasons)
        cover = editorial.get("cover")
        if cover is not None:
            rel = check_media_ref(cover, f"{where}.cover", reasons)
            if rel:
                media_paths.add(rel)
            if isinstance(cover, dict) and cover.get("alt") and sid in canonical_names:
                name = canonical_names[sid]
                for lang in ("en", "zh-Hans"):
                    if cover["alt"].get(lang) == name.get(lang):
                        fail(reasons, f"{where}.cover.alt.{lang}: duplicates the canonical basic name; omit alt to derive it")
        gallery = editorial.get("gallery")
        if not isinstance(gallery, list) or len(gallery) > LIMIT_ARRAY:
            fail(reasons, f"{where}.gallery: must be a list of at most {LIMIT_ARRAY}")
        else:
            for i, ref in enumerate(gallery):
                rel = check_media_ref(ref, f"{where}.gallery[{i}]", reasons)
                if rel:
                    media_paths.add(rel)
    on_disk = {str(p.relative_to(REPO)) for p in MEDIA_ROOT.rglob("*") if p.is_file()}
    for rel in sorted(on_disk - media_paths):
        fail(reasons, f"showcase/media: unreferenced media file {rel}")
    return doc


def check_url_pinned(url, where, reasons):
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        fail(reasons, f"{where}: must be an HTTPS GitHub source URL")
        return
    parsed = urllib.parse.urlparse(url)
    segments = [seg for seg in parsed.path.split("/") if seg]
    if parsed.netloc != "github.com" or len(segments) < 2:
        fail(reasons, f"{where}: not a GitHub repository URL")
        return
    if not any(re.fullmatch(r"[0-9a-f]{40}", seg) for seg in segments):
        fail(reasons, f"{where}: URL must pin an explicit 40-hex commit")


def check_evidence(records, where, reasons):
    if not isinstance(records, list) or not (1 <= len(records) <= LIMIT_EVIDENCE):
        fail(reasons, f"{where}: evidence must hold 1..{LIMIT_EVIDENCE} records")
        return
    for i, rec in enumerate(records):
        w = f"{where}[{i}]"
        if not isinstance(rec, dict) or set(rec.keys()) != {"file", "sha256", "lineStart", "lineEnd"}:
            fail(reasons, f"{w}: keys must be exactly file/sha256/lineStart/lineEnd")
            continue
        name = rec["file"]
        if (not isinstance(name, str) or CONTROL.search(name) or "\\" in name
                or "://" in name or name.startswith("/")):
            fail(reasons, f"{w}.file: not a strict relative repository path")
            continue
        parts = name.split("/")
        if any(part in ("", ".", "..") for part in parts):
            fail(reasons, f"{w}.file: empty, '.' or '..' component")
            continue
        target = REPO / name
        try:
            if not ensure_no_symlink(target, f"{w}.file", reasons):
                continue
            if not target.is_file():
                fail(reasons, f"{w}.file: missing")
                continue
        except OSError as exc:
            fail(reasons, f"{w}.file: {exc}")
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if rec["sha256"] != digest:
            fail(reasons, f"{w}.sha256: recorded {rec['sha256'][:12]}.. but actual is {digest[:12]}..")
        start, end = rec["lineStart"], rec["lineEnd"]
        if not (is_int(start) and is_int(end) and 1 <= start <= end):
            fail(reasons, f"{w}: lineStart/lineEnd must be 1-based ordered ints (bools excluded)")
            continue
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            lines = None
        if lines is not None and end > len(lines):
            fail(reasons, f"{w}.lineEnd {end} beyond file length {len(lines)}")


def check_links(reasons, registry_ids):
    doc, _ = load_json(SHOWCASE / "links.json", reasons)
    if not isinstance(doc, dict):
        return None
    if set(doc.keys()) != {"schemaVersion", "entries"}:
        fail(reasons, "showcase/links.json: top-level keys must be exactly schemaVersion/entries")
    if not (is_int(doc.get("schemaVersion")) and doc["schemaVersion"] == 1):
        fail(reasons, "showcase/links.json: schemaVersion must be the integer 1")
    entries = doc.get("entries")
    if not isinstance(entries, dict):
        fail(reasons, "showcase/links.json: entries must be an object keyed by skill id")
        return doc
    for sid in entries:
        if sid not in registry_ids:
            fail(reasons, f"showcase/links.json: entry {sid!r} is not a registry id")
    requires_graph = {sid: [] for sid in entries}
    for sid, audit in entries.items():
        where = f"showcase/links.json entries[{sid!r}]"
        if not isinstance(audit, dict) or set(audit.keys()) != {"auditStatus", "links"}:
            fail(reasons, f"{where}: keys must be exactly auditStatus/links")
            continue
        if audit["auditStatus"] not in ("audited", "pending"):
            fail(reasons, f"{where}.auditStatus: must be audited or pending")
        links = audit["links"]
        if not isinstance(links, list) or len(links) > LIMIT_LINKS:
            fail(reasons, f"{where}.links: must be a list of at most {LIMIT_LINKS}")
            continue
        for i, link in enumerate(links):
            w = f"{where}.links[{i}]"
            if not isinstance(link, dict) or not set(link.keys()) <= {"relation", "target", "evidence", "notes"} \
                    or not {"relation", "target", "evidence"} <= set(link.keys()):
                fail(reasons, f"{w}: keys must be relation/target/evidence plus optional notes")
                continue
            if link["relation"] not in RELATIONS:
                fail(reasons, f"{w}.relation: must be one of {sorted(RELATIONS)}")
            target = link["target"]
            if not isinstance(target, dict) or "kind" not in target:
                fail(reasons, f"{w}.target: must carry kind")
            elif target["kind"] == "hub":
                if (set(target.keys()) != {"kind", "id"}
                        or not isinstance(target.get("id"), str)
                        or target["id"] not in registry_ids):
                    fail(reasons, f"{w}.target: internal target must be exactly {{kind: hub, id}} with a registry id")
                elif target["id"] == sid:
                    fail(reasons, f"{w}.target: self-reference is not allowed")
                if link["relation"] == "requires" and isinstance(target.get("id"), str):
                    requires_graph.setdefault(sid, []).append(target.get("id"))
            elif target["kind"] == "external-skill":
                if set(target.keys()) != {"kind", "label", "url"}:
                    fail(reasons, f"{w}.target: external target must be exactly {{kind, label, url}}")
                else:
                    check_bilingual(target.get("label"), f"{w}.target.label", reasons)
                    check_url_pinned(target.get("url"), f"{w}.target.url", reasons)
            else:
                fail(reasons, f"{w}.target.kind: unknown kind {target['kind']!r}")
            check_evidence(link["evidence"], f"{w}.evidence", reasons)
            if "notes" in link:
                check_bilingual(link["notes"], f"{w}.notes", reasons, required=False)
    detect_required_cycles(requires_graph, reasons)
    return doc


def detect_required_cycles(graph, reasons):
    """Bounded requires-graph walk; a required cycle is a hard failure."""
    VISIT_BOUND = 64
    DEPTH_BOUND = 4

    def walk(start):
        stack, seen = [(start, [start], 0)], set()
        while stack:
            node, path, depth = stack.pop()
            if node in seen:
                continue
            if len(seen) >= VISIT_BOUND:
                fail(reasons, f"showcase/links.json: required dependency graph exceeds {VISIT_BOUND}-node audit bound from {start}")
                return None
            seen.add(node)
            if depth >= DEPTH_BOUND:
                if graph.get(node):
                    fail(reasons, f"showcase/links.json: required dependency graph exceeds depth-{DEPTH_BOUND} audit bound from {start}")
                continue
            for nxt in graph.get(node, []):
                if nxt == start:
                    return path + [nxt]
                if nxt in path:
                    continue
                stack.append((nxt, path + [nxt], depth + 1))
        return None

    reported = set()
    for start in sorted(graph):
        cycle = walk(start)
        if cycle:
            rotations = [tuple(cycle[i:-1] + cycle[:i]) for i in range(len(cycle) - 1)]
            canonical = min(rotations) if rotations else tuple(cycle)
            if canonical in reported:
                continue
            reported.add(canonical)
            fail(reasons, f"showcase/links.json: required dependency cycle detected: {' -> '.join(cycle)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args(argv)

    reasons = []
    registry_doc, _ = load_json(REPO / "catalog" / "skills.json", reasons)
    registry_ids, canonical_names = set(), {}
    if isinstance(registry_doc, dict) and isinstance(registry_doc.get("skills"), list):
        for skill in registry_doc["skills"]:
            if isinstance(skill, dict) and isinstance(skill.get("id"), str):
                registry_ids.add(skill["id"])
                name = skill.get("name")
                if isinstance(name, dict):
                    canonical_names[skill["id"]] = name
    # The registry is the single source of truth for ids; the first release
    # covers 43 records, and a future registry change flows through without
    # website-side plan-id lists (see showcase/CONTRACT.md ownership).
    if not registry_ids:
        fail(reasons, "catalog/skills.json: no registry ids found for the showcase join")

    check_media_tree(reasons)
    skills_doc = check_skills(reasons, registry_ids, canonical_names)
    links_doc = check_links(reasons, registry_ids)

    skills_entries = skills_doc.get("entries", {}) if isinstance(skills_doc, dict) else {}
    links_entries = links_doc.get("entries", {}) if isinstance(links_doc, dict) else {}
    print(f"showcase gate: registry={len(registry_ids)} "
          f"editorial={len(skills_entries)} audited-links={len(links_entries)}")

    if reasons:
        print(f"FAIL ({len(reasons)} reason(s)):", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("OK: showcase skills.json, links.json and media satisfy the frozen v1 contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
