#!/usr/bin/env python3
"""Canonicalize the Floe Impeccable skill source into the Hub package layout.

Stage 2 of the reproducible pipeline (stage 1 = stage1_normalize_skill_source.py,
byte-identical to the reviewed parent-lane normalizer). This stage takes the
staged derivation (`skill/` + audit record) and reshapes it into the canonical,
admitted package: root SKILL.md + floe.json + scripts launcher + references/
(licenses, provenance, audit data, the frozen runtime-dependency descriptor)
plus the read-only engine-data compatibility root the unchanged riscv64 binary
expects (`reference/*.md`, `scripts/command-metadata.json`, `SKILL.md`,
`VERSION`).

Everything is mechanical and asserted; every substitution is counted and fails
closed when its expected occurrence is absent. No maintenance code ships inside
the package. The engine binary is never part of the package bytes.

  python3 build_canonical_package.py \
    --upstream <pinned-upstream-clone> --staging <stage1-out-root> \
    --descriptor <descriptor.v1.json> --launcher <parent launcher file> \
    --engine-lock <ENGINE-LOCK.json> --out <fresh-canonical-package-dir>

Stage 2 refuses an existing non-empty --out directory; it never deletes
caller data. The supported regeneration route is the driver in this
directory:

  sh <hub>/engines/impeccable/build/skill-source/run_pipeline.sh \
     <pinned-upstream-clone-dir> <hub-root> <new-empty-work-root>

Deterministic: the same inputs always produce the same bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CANONICAL_TOP = ("SKILL.md", "floe.json", "references", "assets", "scripts", "agents")
PIN_COMMIT = "4fc2f83e1c8710dba772bfd4523d0efab57737b6"
PIN_TREE = "1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72"
ENGINE_ID = "impeccable-0.1.17+floe.1.0.0"
ENGINE_SHA = "af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b"
ENGINE_BYTES = 5_579_704
CONTRACT_SHA = "baf2453164be6162703af9d671be16da152fa874db53ce95ad5b3516d40de4a3"
DESCRIPTOR_SHA = "cec4a7fade52f6383f74bc9e15972b911552b2672eada138d890e353899be50a"
DESCRIPTOR_BYTES = 563
EXPECTED_REFS = 36
EXPECTED_COMMANDS = 23

OLD_SCRIPT_TOKEN = "<skill-base-dir>/scripts/floe-impeccable"
NEW_SCRIPT_TOKEN = "<skill-base-dir>/scripts/floe-impeccable.sh"

# Prose corrections applied to the root SKILL.md after the mechanical token
# rewrite; each must match exactly once.
SKILL_CORRECTIONS = [
    (
        "1. Run `<skill-base-dir>/scripts/floe-impeccable.sh context` once per session",
        "1. Run `sh <skill-base-dir>/scripts/floe-impeccable.sh context` once per session",
    ),
    (
        "On a Windows shell without `sh`, call `<skill-base-dir>/scripts/floe-impeccable.sh` instead. "
        "The launcher runs the static Floe engine binary that the Floe Skill Hub installed next to it, "
        "bound by digest; it is never downloaded at run time and no Node or other runtime is required.",
        "The launcher runs under the task Linux environment's `/bin/sh`; there is no host or Windows "
        "path. The engine binary is not inside this skill: the Floe Skill Hub provisions it as a "
        "separate digest-bound runtime component into the task's resolved Linux environment (bound in "
        "references/engine-dependency.json) and points the launcher at it. The launcher is never "
        "downloaded and never downloads; until that component is provisioned and probed it exits "
        "127. Say the engine is unavailable in this environment instead of trying to install or fetch "
        "it, and no Node or other runtime is required.",
    ),
]

MAPPING_PARAGRAPH = """### Installed layout (canonical)

- The launcher is `scripts/floe-impeccable.sh`; run it as
  `sh <skill-base-dir>/scripts/floe-impeccable.sh <verb> [args...]` in the task's
  resolved Linux environment. Where this skill or its references show a compact
  `floe-impeccable <verb>`, that is this command.
- The engine's read-only data directory is `references/engine-data/` — a mirror
  of the upstream skill directory (`reference/`, `scripts/command-metadata.json`,
  `SKILL.md`, `VERSION`). Wherever text or engine output says `reference/<name>.md`,
  the installed file is
  `<skill-base-dir>/references/engine-data/reference/<name>.md`. The runtime sets
  `IMPECCABLE_SKILL_DIR` to that root; the launcher defaults to it. Do not move
  or edit files under `references/engine-data/` at run time.
- `references/engine-dependency.json` is the frozen managed runtime-artifact
  descriptor (data, never a permission). Design scans require the provisioned,
  probe-verified engine; without it `snapshot-scan` cannot run."""

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"canonicalization refused: {message}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    require(n == 1, f"prose correction {label}: expected exactly 1 occurrence, found {n}")
    return text.replace(old, new)


SCRIPT_TOKEN_RE = re.compile(r"scripts/floe-impeccable(?![\w.\-])")

# audit-file pointer tokens (the audit data now lives below references/)
POINTER_FIXES = [
    ("at the pinned commit in SOURCE-LOCK.json", "at the pinned commit in references/SOURCE-LOCK.json"),
    ("the pinned commit recorded in SOURCE-LOCK.json", "the pinned commit recorded in references/SOURCE-LOCK.json"),
    ("listed in\n     MODIFICATIONS.md", "listed in\n     references/MODIFICATIONS.md"),
    ("recorded in MODIFICATIONS.md", "recorded in references/MODIFICATIONS.md"),
]


def fix_pointer_tokens(text: str) -> tuple[str, int]:
    n = 0
    for old, new in POINTER_FIXES:
        c = text.count(old)
        if c:
            text = text.replace(old, new)
            n += c
    require(text.count("SOURCE-LOCK.json") == text.count("references/SOURCE-LOCK.json"),
            "an audit pointer token escaped the references/ rewrite")
    require(text.count("MODIFICATIONS.md") == text.count("references/MODIFICATIONS.md"),
            "a modification-record pointer token escaped the references/ rewrite")
    return text, n


def rewrite_scripts_token(text: str) -> tuple[str, int]:
    require("floe-impeccable.sh" not in text, "input text already contains the canonical launcher name")
    matches = SCRIPT_TOKEN_RE.findall(text)
    if matches:
        text = SCRIPT_TOKEN_RE.sub("scripts/floe-impeccable.sh", text)
        require(len(SCRIPT_TOKEN_RE.findall(text)) == 0, "a scripts/floe-impeccable token survived the rename")
        require(text.count("scripts/floe-impeccable.sh.sh") == 0, "double-suffix artifact")
    return text, len(matches)


def make_link_rewriter(accepted: set[str], excluded: dict[str, str]):
    link_target = re.compile(r"\]\(reference/([A-Za-z0-9._-]+\.md)((?:#[A-Za-z0-9._-]+)?)\)")

    def rewrite_links(text: str) -> tuple[str, int, int]:
        rewritten = annotated = 0

        def sub(m: re.Match) -> str:
            nonlocal rewritten, annotated
            name, anchor = m.group(1), m.group(2)
            if name in accepted:
                rewritten += 1
                return f"](references/engine-data/reference/{name}{anchor})"
            if name in excluded:
                annotated += 1
                return (f"](reference/{name}{anchor})<!-- Floe: reference/{name} is not shipped; "
                        f"{excluded[name]} -->")
            raise SystemExit(f"canonicalization refused: link to unknown reference {name!r}")

        return link_target.sub(sub, text), rewritten, annotated

    bare_link = re.compile(r"\]\(([A-Za-z0-9._-]+\.md)(#[A-Za-z0-9._-]+)?\)")

    def annotate_bare_dangling(text: str) -> tuple[str, int]:
        count = 0

        def sub(m: re.Match) -> str:
            nonlocal count
            name = m.group(1)
            if name in accepted:
                return m.group(0)
            if name in excluded:
                count += 1
                return f"{m.group(0)}<!-- Floe: {name} is not shipped; {excluded[name]} -->"
            raise SystemExit(f"canonicalization refused: bare link to unknown file {name!r}")

        return bare_link.sub(sub, text), count

    return rewrite_links, annotate_bare_dangling


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--staging", required=True, type=Path, help="stage1 --out root (contains skill/, LICENSE, ...)")
    ap.add_argument("--descriptor", required=True, type=Path)
    ap.add_argument("--launcher", required=True, type=Path, help="parent scripts/floe-impeccable")
    ap.add_argument("--engine-lock", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    upstream = args.upstream
    commit = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    require(commit == PIN_COMMIT, f"upstream clone must be the pinned commit {PIN_COMMIT}, found {commit}")
    tree = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD^{tree}"],
                          capture_output=True, text=True, check=True).stdout.strip()
    require(tree == PIN_TREE, f"upstream clone tree must be the pinned tree {PIN_TREE}, found {tree}")
    engine_version = (upstream / "ENGINE_VERSION").read_text(encoding="utf-8").strip()
    package_version = json.loads((upstream / "package.json").read_text(encoding="utf-8"))["version"]

    staging = args.staging
    staged_skill = staging / "skill"
    require(staged_skill.is_dir(), "stage1 output has no skill/ directory")

    descriptor_bytes = args.descriptor.read_bytes()
    require(len(descriptor_bytes) == DESCRIPTOR_BYTES
            and sha256_bytes(descriptor_bytes) == DESCRIPTOR_SHA,
            "descriptor.v1.json bytes drifted from the frozen v1 descriptor")
    engine_lock = json.loads(args.engine_lock.read_text(encoding="utf-8"))

    out = args.out
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"canonicalization refused: {out} already exists and is not empty; "
                         "this stage never deletes existing output — run the public driver "
                         "into a fresh work root instead")
    (out / "scripts").mkdir(parents=True)
    (out / "references" / "licenses").mkdir(parents=True)
    (out / "references" / "engine-data" / "reference").mkdir(parents=True)
    (out / "references" / "engine-data" / "scripts").mkdir(parents=True)

    staged_refs = sorted(p.name for p in (staged_skill / "reference").glob("*.md"))
    require(len(staged_refs) == EXPECTED_REFS,
            f"expected {EXPECTED_REFS} accepted references, found {len(staged_refs)}")
    accepted = set(staged_refs)
    stage1_record = json.loads((staging / "MODIFICATIONS.json").read_text(encoding="utf-8"))
    excluded = {Path(e["file"]).name: e["reason"] for e in stage1_record["excludedReferences"]}
    require(len(excluded) == 5, "five excluded references expected")
    metadata = json.loads((staged_skill / "scripts" / "command-metadata.json").read_text(encoding="utf-8"))
    require(len(metadata) == EXPECTED_COMMANDS,
            f"expected {EXPECTED_COMMANDS} commands, found {len(metadata)}")

    rewrite_links, annotate_bare_dangling = make_link_rewriter(accepted, excluded)

    # ---------------- engine-data mirror ----------------
    per_file_stage2: dict[str, dict] = {}
    for name in staged_refs:
        src = (staged_skill / "reference" / name).read_text(encoding="utf-8")
        text, n_scripts = rewrite_scripts_token(src)
        text, n_links, n_excl_links = rewrite_links(text)
        require(n_excl_links == 0, f"reference file {name} links an excluded reference via reference/ prefix")
        text, n_bare = annotate_bare_dangling(text)
        text, n_ptr = fix_pointer_tokens(text)
        if n_scripts or n_links or n_bare or n_ptr:
            per_file_stage2[f"reference/{name}"] = {
                "scriptsPathTokensRenamed": n_scripts, "linksRewritten": n_links,
                "bareDanglingLinksAnnotated": n_bare, "auditPointerTokensRewritten": n_ptr}
        (out / "references" / "engine-data" / "reference" / name).write_text(text, encoding="utf-8")
    require(sorted(p.name for p in (out / "references" / "engine-data" / "reference").glob("*.md"))
            == staged_refs, "engine-data reference set drifted")

    (out / "references" / "engine-data" / "scripts" / "command-metadata.json").write_bytes(
        (staged_skill / "scripts" / "command-metadata.json").read_bytes())
    (out / "references" / "engine-data" / "VERSION").write_bytes((staged_skill / "VERSION").read_bytes())

    # ---------------- root SKILL.md ----------------
    staged_skill_md = (staged_skill / "SKILL.md").read_text(encoding="utf-8")
    fm_end = staged_skill_md.find("\n---\n", 4)
    require(fm_end != -1, "staged SKILL.md frontmatter malformed")
    frontmatter = staged_skill_md[4:fm_end]
    body = staged_skill_md[fm_end + 5:]

    desc_match = re.search(r'^description:\s*"(.*?)"\s*$', frontmatter, re.MULTILINE)
    require(desc_match is not None, "staged SKILL.md description must be a quoted scalar")
    description = desc_match.group(1)
    require('"' not in description and len(description) <= 1024,
            "description must be quote-free and <=1024 chars")
    require(re.search(r"^name:\s*impeccable\s*$", frontmatter, re.MULTILINE) is not None,
            "staged SKILL.md name must be impeccable")
    require("allowed-tools" in frontmatter and "argument-hint" in frontmatter,
            "staged frontmatter unexpectedly already normalized")

    text, n_scripts = rewrite_scripts_token(body)
    text, n_links, n_excl_links = rewrite_links(text)
    require(n_links > 20, f"SKILL.md should rewrite many accepted links, got {n_links}")
    for i, (old, new) in enumerate(SKILL_CORRECTIONS):
        text = replace_once(text, old, new, f"correction-{i}")
    anchor = "(`component-review`,\n`capture-server`, `font-match`, `build-phase`, `comp-spec`, `comp-diff`)."
    require(text.count(anchor) == 1, "banner insertion anchor missing")
    text = text.replace(anchor, anchor + "\n\n" + MAPPING_PARAGRAPH, 1)
    text, n_bare_root = annotate_bare_dangling(text)
    text, n_ptr_root = fix_pointer_tokens(text)

    root_skill = ("---\nname: impeccable\n"
                  f"description: \"{description}\"\n"
                  "---\n" + text)
    (out / "SKILL.md").write_text(root_skill, encoding="utf-8")
    (out / "references" / "engine-data" / "SKILL.md").write_text(root_skill, encoding="utf-8")

    # ---------------- floe.json (canonical bytes) ----------------
    manifest = {
        "schemaVersion": 1, "id": "impeccable", "version": "1.0.0",
        "capabilities": ["browser.interact", "browser.observe", "execution.remote",
                          "workspace.read", "workspace.write"],
        "tools": ["exec.shell"], "platforms": ["ios"], "scriptRuntime": "remote",
        "pythonPackages": [],
    }
    floe_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode("utf-8")
    (out / "floe.json").write_bytes(floe_bytes)

    # ---------------- launcher (scripts/floe-impeccable.sh) ----------------
    launcher_src = args.launcher.read_text(encoding="utf-8")
    old_block = ('dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n\n'
                 ': "${IMPECCABLE_SKILL_DIR:=$(CDPATH= cd -- "$dir/.." && pwd)}"')
    new_block = ('dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n\n'
                 '# Canonical Hub layout: the engine reads the read-only compatibility data root\n'
                 '# at <skill>/references/engine-data (a mirror of the upstream skill directory:\n'
                 '# reference/*.md, scripts/command-metadata.json, SKILL.md, VERSION). An explicit\n'
                 '# IMPECCABLE_SKILL_DIR from the runtime always wins; the parent fallback keeps a\n'
                 '# pre-canonical dev checkout (skill dir carrying reference/) working unchanged.\n'
                 'if [ -z "${IMPECCABLE_SKILL_DIR:-}" ]; then\n'
                 '  if [ -d "$dir/../references/engine-data" ]; then\n'
                 '    IMPECCABLE_SKILL_DIR=$(CDPATH= cd -- "$dir/../references/engine-data" && pwd)\n'
                 '  else\n'
                 '    IMPECCABLE_SKILL_DIR=$(CDPATH= cd -- "$dir/.." && pwd)\n'
                 '  fi\n'
                 'fi')
    require(launcher_src.count(old_block) == 1, "launcher default block must appear exactly once")
    launcher = launcher_src.replace(old_block, new_block)
    old_comment = ("#   IMPECCABLE_SKILL_DIR  the skill directory holding reference/*.md and\n"
                   "#                         command-metadata.json")
    new_comment = ("#   IMPECCABLE_SKILL_DIR  the engine's skill directory holding\n"
                   "#                         reference/*.md and command-metadata.json;\n"
                   "#                         defaults to references/engine-data (canonical\n"
                   "#                         Hub layout); an explicit value always wins")
    require(launcher.count(old_comment) == 1, "launcher header comment block drifted")
    launcher = launcher.replace(old_comment, new_comment)
    (out / "scripts" / "floe-impeccable.sh").write_text(launcher, encoding="utf-8")

    # ---------------- references: licenses, descriptor ----------------
    shutil.copyfile(upstream / "LICENSE", out / "references" / "licenses" / "LICENSE")
    shutil.copyfile(upstream / "NOTICE.md", out / "references" / "licenses" / "NOTICE.md")
    license_note = """# License note (Floe-authored, MPL-2.0)

`LICENSE` and `NOTICE.md` in this directory are the upstream `pbakaus/impeccable`
files verbatim (Apache-2.0, pinned commit in `../SOURCE-LOCK.json`). They cover
the upstream skill content preserved under `../engine-data/` (SKILL.md,
reference/*.md, scripts/command-metadata.json) and every derived instruction
text in this package.

Floe-authored files in this package (`scripts/floe-impeccable.sh`,
`../PROVENANCE.md`, `../SOURCE-LOCK.json`, `../MODIFICATIONS.json`,
`../MODIFICATIONS.md`, this note, and the engine-data root placement) are
MPL-2.0 under the Floe Skill Hub repository license. Nothing here relicenses
upstream content, and no full upstream tree is vendored — see
`../SOURCE-LOCK.json` (`notVendored`). The engine binary is a separate
digest-bound runtime artifact (`../engine-dependency.json`) and never enters
this package.
"""
    (out / "references" / "licenses" / "LICENSE-NOTE.md").write_text(license_note, encoding="utf-8")
    (out / "references" / "engine-dependency.json").write_bytes(descriptor_bytes)

    canonicalization = {
        "rootSkill": {"scriptsPathTokensRenamed": n_scripts, "linksRewritten": n_links,
                       "excludedReferencePrefixLinksAnnotated": n_excl_links,
                       "bareDanglingLinksAnnotated": n_bare_root,
                       "auditPointerTokensRewritten": n_ptr_root,
                       "proseCorrections": [
                           "setup invocation gains explicit `sh` and the canonical .sh launcher name",
                           "launcher sentence replaced with the managed-provisioning truth (Hub-staged, "
                           "digest-bound, never downloaded, exit 127 before a provisioned+probed engine)",
                           "installed-layout mapping paragraph inserted"]},
        "frontmatter": {"normalized": "name + description scalars only; allowed-tools/Bash/argument-hint/"
                                       "user-invocable/license fields removed (Floe grants come from floe.json "
                                       "and the runtime; the upstream license is preserved under "
                                       "references/licenses/)"},
        "engineDataMirror": {"referenceFiles": len(staged_refs), "commands": EXPECTED_COMMANDS,
                              "perFile": per_file_stage2},
        "launcher": {"parentSha256": sha256_file(args.launcher),
                      "canonicalSha256": sha256_file(out / "scripts" / "floe-impeccable.sh"),
                      "change": "IMPECCABLE_SKILL_DIR default moved to the canonical read-only data root "
                                "references/engine-data, with explicit-value override first and a "
                                "dev-checkout fallback; comments updated; resolution order, digest gate and "
                                "no-download behaviour unchanged"},
        "movedOut": ["LICENSE/NOTICE.md (package root) -> references/licenses/",
                      "README.md -> references/PROVENANCE.md",
                      "SOURCE-LOCK.json / MODIFICATIONS.json / MODIFICATIONS.md -> references/",
                      "scripts/normalize_skill_source.py -> hub maintenance tooling "
                      "(engines/impeccable/build/skill-source/), never inside the installed package"],
        "descriptor": {"path": "references/engine-dependency.json", "bytes": DESCRIPTOR_BYTES,
                        "sha256": DESCRIPTOR_SHA,
                        "authority": "frozen managed runtime artifact descriptor v1 "
                                     "(engines/impeccable/runtime-dependency/, coordinator 2026-10-26)"},
    }

    # ---------------- MODIFICATIONS.json / .md ----------------
    record = dict(stage1_record)
    record["canonicalization"] = canonicalization
    record["stage1Output"] = {
        "skillMdSha256": sha256_file(staged_skill / "SKILL.md"),
        "versionSha256": sha256_file(staged_skill / "VERSION"),
        "commandMetadataSha256": sha256_file(staged_skill / "scripts" / "command-metadata.json"),
    }
    record.pop("sourceLock", None)

    provenance = f"""# Provenance: Floe Impeccable canonical skill package

Derived from `pbakaus/impeccable` commit `{PIN_COMMIT}` (tree `{PIN_TREE}`),
engine version `{engine_version}`, upstream skill package version
`{package_version}`; Apache-2.0 (see `licenses/`). Pin authority: hub
`docs/UPSTREAM-PINS.json`. Two reproducible stages produce every byte (the
maintenance tooling is committed Hub code under
`engines/impeccable/build/skill-source/`; `SOURCE-LOCK.json` records the
exact public regeneration command; nothing here was hand-edited):

1. **normalize** (`engines/impeccable/build/skill-source/stage1_normalize_skill_source.py`,
   the parent-lane normalizer with portability fixes): resolves upstream template
   placeholders for the Floe provider, rewrites `impeccable`/`npx impeccable`
   invocations to the Floe launcher, adds the per-file Floe surface notes,
   accepts 36 references, excludes 5 (live, live-setup, hooks, component-review,
   doctor), keeps the 23 engine-carriable commands in `command-metadata.json`.
2. **canonicalize** (this pipeline): normalizes the SKILL.md frontmatter to
   `name`+`description` scalars, renames the launcher to
   `scripts/floe-impeccable.sh` (the remote-runtime script rule), points every
   explicit path at the canonical name, rewrites accepted `reference/*.md` links
   to `references/engine-data/reference/*.md` (the actual installed paths),
   annotates links to excluded references, inserts the installed-layout
   mapping, replaces the launcher sentence with the managed-provisioning truth,
   mirrors the normalized corpus under `references/engine-data/` (the read-only
   skill dir the unchanged binary expects), and moves all audit data below
   `references/`. `MODIFICATIONS.json` records every count and digest.

Engine: `floe-impeccable` static riscv64 ELF, sha256 `{ENGINE_SHA}`,
{ENGINE_BYTES} bytes — **never inside this package**. The binding is the frozen
managed runtime artifact descriptor `references/engine-dependency.json`
(sha256 `{DESCRIPTOR_SHA}`, {DESCRIPTOR_BYTES} bytes, seven fields, no URLs, no
commands). Capture contract digest: `{CONTRACT_SHA}`.

Verified boundaries: the artifact is verified under reference riscv64 emulation
and on host parity only (see `engines/impeccable/HANDOFF.md` in the hub); the
Floe TinyEMU guest run, the native probe, App acceptance and publication are
pending and owned by the release owner. This package is staged candidate
content: no review, qualification or publication claim.
"""
    (out / "references" / "PROVENANCE.md").write_text(provenance, encoding="utf-8")

    md = f"""# Modification record — canonical Floe Impeccable package

Stage 1 (normalize) records are embedded verbatim in `MODIFICATIONS.json`
(`skillFile`, `commandMetadata`, `acceptedReferences`, `excludedReferences`).
Stage 2 (canonicalize) changed, per file counts in `canonicalization`:

- SKILL.md: {n_scripts} explicit launcher-path tokens renamed to
  `floe-impeccable.sh`; {n_links} accepted `reference/*.md` links rewritten to
  `references/engine-data/reference/*.md`; {n_excl_links} excluded-reference
  links annotated in place; {n_bare_root} bare dangling links annotated; two
  prose corrections applied; the installed-layout mapping inserted; the
  frontmatter reduced to `name` + `description` (provider `allowed-tools`,
  `argument-hint`, `user-invocable`, `license` removed).
- `references/engine-data/`: read-only mirror the unchanged engine expects
  (`SKILL.md`, `VERSION`, 36 `reference/*.md`, `scripts/command-metadata.json`
  with 23 commands). Per-file stage-2 counts in `MODIFICATIONS.json`.
- Launcher `scripts/floe-impeccable.sh` ({sha256_file(out / 'scripts' / 'floe-impeccable.sh')}):
  default `IMPECCABLE_SKILL_DIR` is now the engine-data root (explicit value
  wins; dev-checkout fallback). Resolution, digest gate and no-download
  behaviour are unchanged ({sha256_file(args.launcher)} was the parent bytes).
- Moved below `references/`: upstream `LICENSE`, `NOTICE.md`, the source lock,
  the modification record, a Floe license note, and the new
  `PROVENANCE.md`. The maintenance normalizer left the installed package.
- Added `references/engine-dependency.json`: byte-identical copy of the frozen
  managed runtime artifact descriptor v1 ({DESCRIPTOR_SHA}).

Upstream pin: `{PIN_COMMIT}` / `{PIN_TREE}`; engine `{engine_version}`;
upstream package `{package_version}`. Five references remain excluded by
design (live, live-setup, hooks, component-review, doctor) and one command
(`live`) dropped from the metadata — see `MODIFICATIONS.json`.
"""
    (out / "references" / "MODIFICATIONS.md").write_text(md, encoding="utf-8")

    record["regenerate"] = ("sh <hub>/engines/impeccable/build/skill-source/run_pipeline.sh "
                            "<pinned-upstream-clone-dir> <hub-root> <new-empty-work-root> "
                            "(stage1 + stage2 + authoritative Hub helper gate; canonical bytes are "
                            "emitted at <work-root>/canonical and adopted into <hub>/sources/impeccable "
                            "only by a reviewed manual copy; existing non-empty output is refused, "
                            "never deleted)")

    # ---------------- SOURCE-LOCK.json (final pass over all bytes) ----------------
    stage1_lock = json.loads((staging / "SOURCE-LOCK.json").read_text(encoding="utf-8"))
    (out / "references" / "MODIFICATIONS.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def digest_map() -> dict[str, str]:
        files = {}
        for path in sorted(out.rglob("*")):
            require(not path.is_symlink(), f"symlink in canonical output: {path}")
            if path.is_file():
                files[path.relative_to(out).as_posix()] = sha256_file(path)
        return files

    derived = digest_map()
    lock = {
        "role": "source lock for the canonical Floe Impeccable skill package and its paired engine",
        "upstream": dict(stage1_lock["upstream"], tree=engine_lock.get("upstream", {}).get("tree", PIN_TREE)),
        "pairing": {
            "rule": "the skill source, the engine artifact and the descriptor come from this one commit",
            "engineLock": "engines/impeccable/ENGINE-LOCK.json",
            "engineId": engine_lock.get("engineId", ENGINE_ID),
            "engineArtifact": {
                "hubPath": ("engines/impeccable/dist/impeccable-0.1.17+floe.1.0.0/"
                            "riscv64gc-unknown-linux-musl/floe-impeccable"),
                "sha256": ENGINE_SHA, "bytes": ENGINE_BYTES,
                "format": "static ELF64 little-endian RISC-V EXEC (musl, stripped)"},
            "runtimeDescriptor": {"path": "references/engine-dependency.json",
                                   "sha256": DESCRIPTOR_SHA, "bytes": DESCRIPTOR_BYTES,
                                   "authority": "frozen managed runtime artifact descriptor v1 "
                                                "(engines/impeccable/runtime-dependency/)"},
            "captureContractSha256": CONTRACT_SHA,
            "skillVersionFile": engine_version,
        },
        "canonicalLayout": {
            "rootEntriesAllowed": list(CANONICAL_TOP),
            "rootEntriesPresent": sorted({k.split("/")[0] for k in derived}),
            "engineDataRoot": "references/engine-data",
            "engineDataReadBy": "IMPECCABLE_SKILL_DIR (runtime-set; launcher default)",
            "launcher": "scripts/floe-impeccable.sh",
            "packagedVersion": "1.0.0",
            "containsNativeBinary": False,
        },
        "notVendored": list(stage1_lock["notVendored"])
                       + ["maintenance normalizer and canonicalizer "
                          "(hub tooling under engines/impeccable/build/skill-source/)"],
        "vendoredVerbatim": {
            "references/licenses/LICENSE": sha256_file(out / "references" / "licenses" / "LICENSE"),
            "references/licenses/NOTICE.md": sha256_file(out / "references" / "licenses" / "NOTICE.md"),
            "references/engine-dependency.json": DESCRIPTOR_SHA,
        },
        "regenerate": record["regenerate"],
    }

    def write_lock(files_map: dict[str, str]) -> None:
        payload = dict(lock, derivedFiles=files_map, derivedFileCount=len(files_map))
        (out / "references" / "SOURCE-LOCK.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # the lock carries the digest of every file except itself (self-digest is
    # impossible); record the package file count separately.
    files_excl_lock = {k: v for k, v in derived.items()
                       if k != "references/SOURCE-LOCK.json"}
    write_lock(files_excl_lock)
    # nothing else changed, so the map is stable now; verify once
    final = digest_map()
    stable = {k: v for k, v in final.items() if k != "references/SOURCE-LOCK.json"}
    require(stable == files_excl_lock, "derived digests unstable after the lock write")
    total_bytes = sum((out / k).stat().st_size for k in final)

    summary = {
        "ok": True,
        "out": str(out),
        "files": len(final),
        "totalBytes": total_bytes,
        "rootEntries": sorted({k.split("/")[0] for k in final}),
        "acceptedReferences": len(staged_refs),
        "commands": EXPECTED_COMMANDS,
        "descriptor": {"bytes": len(descriptor_bytes), "sha256": sha256_bytes(descriptor_bytes)},
        "launcher": canonicalization["launcher"],
        "skillSha256": final["SKILL.md"],
        "floeJsonSha256": final["floe.json"],
        "engineVersion": engine_version,
        "packageVersion": package_version,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
