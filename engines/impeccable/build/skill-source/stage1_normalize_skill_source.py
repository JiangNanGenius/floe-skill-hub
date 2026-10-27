#!/usr/bin/env python3
"""Normalize the pinned upstream Impeccable skill source into the Floe skill source.

The full upstream tree is never vendored. This script reads it from a checkout of
the pinned commit and writes only what the Floe skill package needs, with the
upstream wording preserved and every Floe difference recorded:

  * template placeholders (`{{scripts_path}}`, `{{command_prefix}}`,
    `{{command_hint}}`) are resolved for the Floe launcher;
  * `impeccable <verb>` invocations become `floe-impeccable <verb>`;
  * a per-file Floe note names the verbs in that file which the Floe engine
    refuses, and why (Chromium/CDP, network, live rewrite, editor hooks, the
    upstream installer);
  * references whose whole subject is an unavailable engine path are excluded
    with a recorded reason instead of being normalized into something misleading;
  * SKILL.md carries the authoritative v1 engine surface, the snapshot-scan
    design flow and the coverage limits (no pixel contrast, no reveal sweep, no
    iframe content, and therefore never a "clean" verdict);
  * `command-metadata.json` is filtered to the Floe verb surface, because the
    engine prefers the sibling copy in the skill directory over its embedded one;
  * copyright and the modification record are preserved: upstream LICENSE and
    NOTICE.md are copied verbatim, and MODIFICATIONS.md logs every change with
    per-file digests.

  python3 normalize_skill_source.py --upstream <pinned-source-dir> \
      --out <fresh-staging-root> [--engine-lock <hub>/engines/impeccable/ENGINE-LOCK.json]

This is stage 1 of the public regeneration driver
`run_pipeline.sh <pinned-upstream-clone-dir> <hub-root> <new-empty-work-root>`
in this directory; running it standalone writes only into a fresh --out root
and refuses an existing non-empty one — it never deletes caller data.

Deterministic: the same pinned commit always produces the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

FLOE_LAUNCHER = "floe-impeccable"
ENGINE_VERSION_FILE = "ENGINE_VERSION"

# Verbs the Floe engine exposes. Everything else is refused with a reason.
FLOE_VERBS = {
    "snapshot-scan": "the v1 design scan over a native WebKit snapshot",
    "contract": "prints the frozen snapshot/facts contract",
    "snapshot-schema": "prints the producer-facing capture contract",
    "detect": "static source and markup scan",
    "context": "project context brief (PRODUCT.md, DESIGN.md, surface briefs)",
    "ignores": "detector ignore management",
    "detect-csp": "CSP detection",
    "palette": "palette extraction",
    "signals": "context signals",
    "engine-probe": "launcher handshake",
}

# Verbs the upstream skill text mentions that the Floe engine refuses, with the
# owner or reason. Used to write the per-file note.
REFUSED_VERBS = {
    "live": "live rewrite server (local HTTP server that rewrites the page)",
    "live-server": "live rewrite server",
    "live-wrap": "live rewrite server",
    "live-accept": "live rewrite server",
    "live-session": "live rewrite server",
    "live-manual": "live rewrite server",
    "live-generate": "live rewrite server",
    "live-daemon": "live rewrite server",
    "hook": "editor design hooks",
    "hook-before-edit": "editor design hooks",
    "hooks": "editor design hooks",
    "hook-admin": "editor design hooks",
    "install": "the Floe Skill Hub owns installation (signed catalog, digest-bound engine)",
    "update": "the Floe Skill Hub owns updates",
    "check": "the Floe Skill Hub owns update checks",
    "link": "the Floe Skill Hub owns skill linking",
    "skills": "the Floe Skill Hub owns skill management",
    "doctor": "needs the upstream update host and hook artifacts",
    "pin": "creates harness slash-command shortcuts, which Floe does not use",
    "telemetry": "no upstream telemetry endpoint is contacted",
    "generate-image": "needs the upstream image network service",
    "concept-seed": "needs the upstream card network service",
    "serve-question": "needs a local decision-page server and remote hero assets",
    "component-review": "needs the upstream Chromium/CDP capture service",
    "capture-server": "needs the upstream Chromium/CDP capture service",
    "font-match": "needs the upstream Chromium/CDP font renderer",
    "build-phase": "needs the upstream Chromium/CDP entry renderer",
    "comp-spec": "needs the comp-fidelity capture path",
    "comp-diff": "needs the comp-fidelity capture path",
    "surface-brief": "not part of the Floe v1 engine surface",
    "critique-storage": "not part of the Floe v1 engine surface",
    "embed-prompt": "not part of the Floe v1 engine surface",
}

# References whose entire subject is an unavailable engine path.
EXCLUDED_REFERENCES = {
    "live.md": "live mode rewrites the page through a local server; not in the Floe v1 engine",
    "live-setup.md": "live mode setup; not in the Floe v1 engine",
    "hooks.md": "editor design hooks; not in the Floe v1 engine",
    "component-review.md": "component review needs the upstream Chromium/CDP capture service",
    "doctor.md": "doctor reports drift in upstream hook and update artifacts Floe does not install",
}

FLOE_BANNER = """<!-- Floe adaptation: this file is derived from pbakaus/impeccable
     skill/SKILL.src.md at the pinned commit recorded in SOURCE-LOCK.json.
     Apache-2.0 (upstream) is preserved; Floe changes are listed in
     MODIFICATIONS.md. Do not treat this banner as upstream text. -->

## Floe v1 engine surface

This skill runs the Floe Impeccable engine (`scripts/floe-impeccable`), a static
riscv64 Linux binary built from the pinned upstream commit. It has **no network,
no Chromium, no DevTools endpoint and no arbitrary JavaScript evaluation**.

Available verbs: `context`, `detect`, `ignores`, `detect-csp`, `palette`,
`signals`, and the Floe `snapshot-scan` / `contract` / `snapshot-schema`.

Not available in v1 (the launcher and engine refuse each with a reason): live
mode, editor hooks, skill `install`/`update`/`check`/`link` (the Floe Skill Hub
owns those), `doctor`, `pin`, telemetry, image generation, the decision-page
server, and every Chromium/CDP capture verb (`component-review`,
`capture-server`, `font-match`, `build-phase`, `comp-spec`, `comp-diff`).

### Design scans of a rendered page

A page scan is a controlled data hand-off, not a browser session:

1. the native side captures a snapshot with the fixed, audited WebKit
   measurement producer (redacted, bound to the current task/session/tab/
   document/viewport);
2. `floe-impeccable snapshot-scan --snapshot <file> --identity <file> --out
   <file>` runs the pinned upstream rule core over it;

   The launcher's default scan route has **no engine deadline**: it appends
   `--no-timeout` (result `budget.timeoutMs` is null) unless you explicitly
   choose a timeout flag. An explicit `--timeout-ms <n>` (including `0`, which
   means an immediate typed timeout) always passes through untouched, and
   `--no-timeout` with `--timeout-ms` is still refused. This policy covers the
   engine deadline only; the existing caller/task wait and cancel controls are
   unchanged. Hit-test, round and byte caps are unchanged and must never be
   widened by the caller.
3. when the rules need measurements the snapshot cannot answer, the engine
   returns `needs-facts` (exit 3) with the exact points; the native side answers
   from the same document and the scan is re-run with `--facts`;
4. the result carries `findings`, a `coverage` receipt and a `verdict`.

**Never read an empty finding list as a clean page.** v1 cannot measure pixel
contrast, scroll-revealed content, content hidden at rest, console/script errors
or any iframe content, so a run with nothing to report is `verdict:
"inconclusive"` (exit 4) with `coverage.uncoveredRequired` naming the gaps.
Report those gaps to the user instead of claiming the page passed. Navigation,
reload, a viewport change or a scroll invalidates the snapshot and every answer
issued for it.

Interactions with the page (navigate, click, type, screenshot) keep using the
existing Floe browser tools; this engine only reads the handed-off measurement.
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# The Floe provider profile, in the shape of upstream's PROVIDER_PLACEHOLDERS
# (scripts/lib/utils.js). Floe's harness reads AGENTS.md and asks through its own
# question tool, and skills are not slash commands, so command_prefix is empty.
FLOE_PROVIDER = {
    "model": "the model",
    "config_file": "AGENTS.md",
    "ask_instruction": "Ask with the `question` tool and wait for the answer before continuing.",
    "command_prefix": "",
}
SCRIPTS_PATH = "<skill-base-dir>/scripts"
REFERENCE_PATH = "<skill-base-dir>/reference"

# Upstream IMPECCABLE_SUBCOMMANDS (scripts/lib/utils.js), the commands audit and
# critique suggest as next steps.
FLOE_SUBCOMMANDS = [
    "adapt", "animate", "audit", "bolder", "clarify", "colorize",
    "critique", "delight", "distill", "document", "harden", "layout",
    "onboard", "optimize", "overdrive", "polish", "quieter", "shape", "typeset",
]
AVAILABLE_COMMANDS = ", ".join(f"impeccable {name}" for name in FLOE_SUBCOMMANDS)
COMMAND_HINT = "|".join(FLOE_SUBCOMMANDS)

# Commands whose whole flow depends on an engine path Floe does not ship.
EXCLUDED_COMMANDS = {
    "live": "live mode rewrites the page through a local server; not in the Floe v1 engine",
}


def resolve_placeholders(text: str) -> tuple[str, dict]:
    """Resolve every upstream template placeholder for the Floe provider."""
    counts = {
        key: len(re.findall(r"\{\{" + key + r"\}\}", text))
        for key in ("scripts_path", "reference_path", "command_prefix", "command_hint",
                    "ask_instruction", "available_commands", "config_file", "model")
    }
    text = text.replace("{{scripts_path}}", SCRIPTS_PATH)
    text = text.replace("{{reference_path}}", REFERENCE_PATH)
    text = text.replace("{{available_commands}}", AVAILABLE_COMMANDS)
    text = text.replace("{{command_hint}}", COMMAND_HINT)
    text = text.replace("{{model}}", FLOE_PROVIDER["model"])
    text = text.replace("{{config_file}}", FLOE_PROVIDER["config_file"])
    text = text.replace("{{ask_instruction}}", FLOE_PROVIDER["ask_instruction"])
    text = text.replace("{{command_prefix}}impeccable", "impeccable")
    text = text.replace("{{command_prefix}}", FLOE_PROVIDER["command_prefix"])
    return text, {k: v for k, v in counts.items() if v}


# Upstream sentences that state behaviour Floe deliberately changed. Each is
# replaced verbatim and recorded in MODIFICATIONS.json, so a reader is never told
# the engine downloads itself or that an unavailable path still exists.
FLOE_TEXT_CORRECTIONS = [
    (
        "The launcher runs a self-contained binary that ships next to it or is "
        "downloaded once on first run; no Node or other runtime is required.",
        "The launcher runs the static Floe engine binary that the Floe Skill Hub "
        "installed next to it, bound by digest; it is never downloaded at run time "
        "and no Node or other runtime is required.",
    ),
]


def apply_text_corrections(text: str) -> tuple[str, list[str]]:
    applied = []
    for old, new in FLOE_TEXT_CORRECTIONS:
        if old in text:
            text = text.replace(old, new)
            applied.append(old[:60] + "...")
    return text, applied


def rewrite_invocations(text: str) -> tuple[str, dict]:
    """Point every engine invocation at the Floe launcher.

    Only real invocation shapes are rewritten (`npx impeccable <verb>`, a backticked
    `impeccable <verb>`, the launcher path and its Windows sibling), so prose such
    as "the impeccable craft" is left alone.
    """
    counts = {}

    def note(key: str, n: int) -> None:
        if n:
            counts[key] = counts.get(key, 0) + n

    # The launcher itself, including the Windows sibling the Floe package drops.
    text, n = re.subn(rf"{re.escape(SCRIPTS_PATH)}/impeccable\.cmd", f"{SCRIPTS_PATH}/{FLOE_LAUNCHER}", text)
    note("launcher.cmd", n)
    text, n = re.subn(rf"{re.escape(SCRIPTS_PATH)}/impeccable(?![\w.-])", f"{SCRIPTS_PATH}/{FLOE_LAUNCHER}", text)
    note("launcher", n)
    text, n = re.subn(r"(?<![\w/.-])impeccable\.cmd(?![\w.-])", FLOE_LAUNCHER, text)
    note("launcher.cmd-bare", n)

    # `npx impeccable <verb>` and a backticked `impeccable <verb>`.
    text, n = re.subn(r"npx\s+impeccable\s+(?=[a-z][\w-]*)", f"{FLOE_LAUNCHER} ", text)
    note("npx", n)
    text, n = re.subn(r"`impeccable\s+(?=[a-z][\w-]*)", f"`{FLOE_LAUNCHER} ", text)
    note("backticked", n)
    text, n = re.subn(r"(?<![\w/.-])npx impeccable(?![\w-])", FLOE_LAUNCHER, text)
    note("npx-bare", n)

    # The allowed-tools frontmatter entries are Floe's own launcher pattern.
    text, n = re.subn(r"\s*-\s*Bash\(npx [^\n]*\)\n", "\n", text)
    note("allowed-tools-npx-removed", n)
    return text, counts


def assert_no_placeholders(text: str, rel: str) -> None:
    left = sorted(set(re.findall(r"\{\{[a-z_]+\}\}", text)))
    if left:
        raise SystemExit(f"{rel}: unresolved upstream placeholders remain: {left}")
    # A substitution that interpolated a missing regex group shows up as a bare
    # "None" glued to the next token. Prose such as "Nonetheless" must not trip it.
    for artifact in ("Nonefloe-", "Noneimpeccable", "None<skill-base-dir>", "None{{", "None`"):
        if artifact in text:
            raise SystemExit(f"{rel}: a substitution produced a Python None artifact ({artifact})")
    if "npx impeccable" in text:
        raise SystemExit(f"{rel}: an npx invocation survived the rewrite")


def refused_verbs_in(text: str) -> list[str]:
    found = []
    for verb in REFUSED_VERBS:
        if re.search(rf"(?<![\w-]){re.escape(verb)}(?![\w-])", text):
            found.append(verb)
    return sorted(found, key=lambda v: (-len(v), v))


def floe_note(rel: str, refused: list[str]) -> str:
    lines = [
        "",
        "<!-- Floe adaptation note (not upstream text): this file is derived from",
        f"     pbakaus/impeccable skill/{rel} at the pinned commit in SOURCE-LOCK.json.",
        "     Apache-2.0 upstream; Floe changes are recorded in MODIFICATIONS.md. -->",
        "",
        "> **Floe v1 engine surface.** The following upstream verbs referenced in this",
        "> file are not available in the Floe engine, which refuses each with a reason:",
        ">",
    ]
    for verb in refused:
        lines.append(f"> - `{verb}` — {REFUSED_VERBS[verb]}")
    lines += [
        ">",
        "> Skip those steps rather than substituting another tool, and say so in the",
        "> reply. Design scans of a rendered page use `floe-impeccable snapshot-scan`",
        "> with a native WebKit snapshot; see the Floe v1 engine surface in SKILL.md.",
        "",
    ]
    return "\n".join(lines)


def insert_note_after_frontmatter(text: str, note: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            cut = text.find("\n", end + 1)
            return text[: cut + 1] + note + text[cut + 1 :]
    return note + text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--commit", default=None, help="override the upstream commit recorded in the lock")
    ap.add_argument("--tree", default=None, help="override the upstream tree recorded in the lock")
    ap.add_argument("--engine-lock", default=None, type=Path,
                    help="explicit hub ENGINE-LOCK.json (default: walk up from --out, dev layout only)")
    args = ap.parse_args()

    upstream_skill = args.upstream / "skill"
    if not upstream_skill.is_dir():
        print(json.dumps({"ok": False, "error": "no skill/ directory in the pinned source"}))
        return 2
    engine_version = (args.upstream / ENGINE_VERSION_FILE).read_text(encoding="utf-8").strip()
    package_version = json.loads((args.upstream / "package.json").read_text(encoding="utf-8"))["version"]

    out = args.out
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"stage 1 refused: {out} already exists and is not empty; "
                         "this tool never deletes existing output — run into a fresh work root")
    skill_out = out / "skill"
    if skill_out.exists() and any(skill_out.iterdir()):
        raise SystemExit(f"stage 1 refused: {skill_out} already exists and is not empty")
    (skill_out / "reference").mkdir(parents=True)
    (skill_out / "scripts").mkdir(parents=True)

    modifications: list[dict] = []

    # 1. SKILL.md from SKILL.src.md, with the Floe banner as the authority.
    source = (upstream_skill / "SKILL.src.md").read_text(encoding="utf-8")
    text, placeholders = resolve_placeholders(source)
    text, invocations = rewrite_invocations(text)
    text, corrections = apply_text_corrections(text)
    refused = refused_verbs_in(text)
    body = insert_note_after_frontmatter(text, FLOE_BANNER)
    assert_no_placeholders(body, "skill/SKILL.md")
    (skill_out / "SKILL.md").write_text(body, encoding="utf-8")
    modifications.append({
        "file": "skill/SKILL.md",
        "upstream": "skill/SKILL.src.md",
        "upstreamSha256": sha256_text(source),
        "floeSha256": sha256_text(body),
        "placeholdersResolved": placeholders,
        "invocationsRewritten": invocations,
        "refusedVerbsMentioned": refused,
        "changes": [
            "resolved {{scripts_path}}/{{command_prefix}}/{{command_hint}} for the Floe launcher",
            "rewrote `impeccable <verb>` and `npx impeccable <verb>` to `floe-impeccable <verb>`",
            "inserted the Floe v1 engine surface, the snapshot-scan design flow and the coverage limits",
            "documented the Floe default scan policy: the launcher appends `--no-timeout` to "
            "`snapshot-scan` only when the caller chose no timeout flag; explicit timeout choices "
            "(including `--timeout-ms 0`) and every cap are unchanged",
        ],
    })

    # 2. References: accept and normalize, or exclude with a reason.
    accepted, excluded = [], []
    for path in sorted((upstream_skill / "reference").glob("*.md")):
        rel = f"reference/{path.name}"
        source_text = path.read_text(encoding="utf-8")
        if path.name in EXCLUDED_REFERENCES:
            excluded.append({"file": rel, "reason": EXCLUDED_REFERENCES[path.name],
                             "upstreamSha256": sha256_text(source_text)})
            continue
        text, placeholders = resolve_placeholders(source_text)
        text, invocations = rewrite_invocations(text)
        text, corrections = apply_text_corrections(text)
        refused = refused_verbs_in(text)
        note = floe_note(rel, refused) if refused else (
            "\n<!-- Floe adaptation note (not upstream text): derived from\n"
            f"     pbakaus/impeccable skill/{rel} at the pinned commit in SOURCE-LOCK.json.\n"
            "     Apache-2.0 upstream; Floe changes are recorded in MODIFICATIONS.md. -->\n\n"
        )
        body = insert_note_after_frontmatter(text, note)
        assert_no_placeholders(body, f"skill/{rel}")
        # Internal links stay relative and keep working; rewrite only links that
        # point at an excluded reference so nothing dangles.
        dangling = []
        for name in EXCLUDED_REFERENCES:
            pattern = f"](reference/{name})"
            if pattern in body:
                dangling.append(name)
                body = body.replace(
                    pattern,
                    f"](reference/{name})<!-- Floe: reference/{name} is not shipped; "
                    f"{EXCLUDED_REFERENCES[name]} -->",
                )
        (skill_out / "reference" / path.name).write_text(body, encoding="utf-8")
        accepted.append({
            "file": f"skill/{rel}",
            "upstream": f"skill/{rel}",
            "upstreamSha256": sha256_text(source_text),
            "floeSha256": sha256_text(body),
            "placeholdersResolved": placeholders,
            "invocationsRewritten": invocations,
            "textCorrections": corrections,
            "refusedVerbsMentioned": refused,
            "danglingLinksAnnotated": dangling,
        })

    # 3. command-metadata.json filtered to the Floe surface. The engine prefers
    #    the sibling copy in the skill directory over its embedded one.
    metadata_source = upstream_skill / "scripts" / "command-metadata.json"
    metadata = json.loads(metadata_source.read_text(encoding="utf-8"))
    filtered = {}
    dropped = []
    for name, entry in metadata.items():
        if name in EXCLUDED_COMMANDS:
            dropped.append({"command": name, "reason": EXCLUDED_COMMANDS[name]})
        else:
            filtered[name] = entry
    filtered_text = json.dumps(filtered, indent=2, ensure_ascii=False) + "\n"
    (skill_out / "scripts" / "command-metadata.json").write_text(filtered_text, encoding="utf-8")
    modifications.append({
        "file": "skill/scripts/command-metadata.json",
        "upstream": "skill/scripts/command-metadata.json",
        "upstreamSha256": sha256_file(metadata_source),
        "floeSha256": sha256_text(filtered_text),
        "changes": [
            f"kept {len(filtered)} commands the Floe engine can carry out",
            f"dropped {len(dropped)} commands whose flow needs an unavailable engine path",
            "the engine prefers this sibling copy over its embedded command-metadata.json",
        ],
        "keptCommands": sorted(filtered),
        "droppedCommands": dropped,
    })

    # 4. VERSION pairs the skill with the engine build.
    (skill_out / "VERSION").write_text(engine_version + "\n", encoding="utf-8")

    # 5. Upstream licence and notices, verbatim.
    shutil.copyfile(args.upstream / "LICENSE", out / "LICENSE")
    shutil.copyfile(args.upstream / "NOTICE.md", out / "NOTICE.md")

    # 6. The source lock: the pin this derivation came from, plus a digest of
    #    every file written, so a reviewer can tell a re-run from a hand edit.
    engine_lock_path = args.engine_lock if args.engine_lock is not None \
        else out.parent.parent / "engines" / "impeccable" / "ENGINE-LOCK.json"
    engine_lock = json.loads(engine_lock_path.read_text(encoding="utf-8")) if engine_lock_path.is_file() else {}
    upstream_pin = engine_lock.get("upstream", {})
    lock = {
        "role": "source lock for the Floe Impeccable skill source and its paired engine",
        "upstream": {
            "project": "pbakaus/impeccable",
            "repository": upstream_pin.get("repository", "https://github.com/pbakaus/impeccable"),
            "commit": args.commit or upstream_pin.get("commit"),
            "tree": args.tree or upstream_pin.get("tree"),
            "engineVersion": engine_version,
            "skillPackageVersion": package_version,
            "commitDate": upstream_pin.get("commitDate"),
            "commitSubject": upstream_pin.get("commitSubject"),
            "license": "Apache-2.0",
            "pinAuthority": upstream_pin.get("pinAuthority", "floe-skill-hub docs/UPSTREAM-PINS.json"),
        },
        "pairing": {
            "rule": "the skill source and every engine artifact come from this one commit",
            "engineLock": "engines/impeccable/ENGINE-LOCK.json",
            "engineId": engine_lock.get("engineId"),
            "skillVersionFile": engine_version,
        },
        "notVendored": [
            "browser-bundle/", "crates/", "cli/", "extension/", "plugin/", "ui/", "vscode/",
            "cursor-plugin/", "demos/", "tests/", "scripts/", "docs/",
        ],
        "vendoredVerbatim": {
            "LICENSE": sha256_file(out / "LICENSE"),
            "NOTICE.md": sha256_file(out / "NOTICE.md"),
        },
        "regenerate": (
            "sh <hub>/engines/impeccable/build/skill-source/run_pipeline.sh "
            "<pinned-upstream-clone-dir> <hub-root> <new-empty-work-root> "
            "(stage1 + stage2 + gate; canonical bytes land in <work-root>/canonical)"
        ),
    }

    # 7. The modification record.
    record = {
        "derivedFrom": {
            "project": "pbakaus/impeccable",
            "skillPackageVersion": package_version,
            "engineVersion": engine_version,
            "note": "the commit and tree are recorded in SOURCE-LOCK.json",
        },
        "upstreamLicense": "Apache-2.0 (LICENSE and NOTICE.md copied verbatim)",
        "floeLicenseForNewFiles": "MPL-2.0 for Floe-authored files (the launcher, this script, SOURCE-LOCK.json, README.md)",
        "skillFile": modifications[0],
        "commandMetadata": modifications[1],
        "acceptedReferences": accepted,
        "excludedReferences": excluded,
        "regenerate": ("sh <hub>/engines/impeccable/build/skill-source/run_pipeline.sh "
                       "<pinned-upstream-clone-dir> <hub-root> <new-empty-work-root>"),
    }
    lines = [
        "# Modification record: Floe skill source derived from pbakaus/impeccable",
        "",
        f"Upstream skill package version **{package_version}**, engine version **{engine_version}**,",
        "Apache-2.0. `LICENSE` and `NOTICE.md` in this directory are the upstream files",
        "verbatim. The commit and tree are in `SOURCE-LOCK.json`; `MODIFICATIONS.json` is",
        "the machine-readable form of this record with per-file digests.",
        "",
        "Floe-authored files in this directory (`scripts/floe-impeccable`,",
        "`scripts/normalize_skill_source.py`, `SOURCE-LOCK.json`, `README.md`, this file)",
        "are MPL-2.0. Nothing here relicenses upstream content.",
        "",
        "## What changed in every derived file",
        "",
        "1. `{{scripts_path}}/impeccable` became `<skill-base-dir>/scripts/floe-impeccable`;",
        "   `{{command_prefix}}` and `{{command_hint}}` were resolved for Floe.",
        "2. `impeccable <verb>` and `npx impeccable <verb>` became `floe-impeccable <verb>`.",
        "3. Each file carries a Floe adaptation note naming the upstream verbs it mentions",
        "   that the Floe engine refuses, with the reason.",
        "4. Upstream sentences that describe behaviour Floe changed (the launcher downloading",
        "   an engine on first run) are replaced verbatim and logged as `textCorrections`.",
        "5. `SKILL.md` carries the authoritative Floe v1 engine surface, the `snapshot-scan`",
        "   design flow and the coverage limits (no pixel contrast, no reveal sweep, no",
        "   iframe content, therefore never a clean verdict).",
        "6. Links to an excluded reference are annotated in place instead of dangling.",
        "",
        "## SKILL.md",
        "",
        f"- placeholders resolved: {modifications[0]['placeholdersResolved']}",
        f"- invocations rewritten: {modifications[0]['invocationsRewritten']}",
        f"- refused verbs mentioned: {', '.join(modifications[0]['refusedVerbsMentioned']) or 'none'}",
        "",
        "## command-metadata.json",
        "",
        f"- kept ({len(filtered)}): {', '.join(sorted(filtered))}",
        f"- dropped ({len(dropped)}): " + (", ".join(f"`{d['command']}` ({d['reason']})" for d in dropped) or "none"),
        "",
        f"## Accepted references ({len(accepted)})",
        "",
        "| File | Invocations rewritten | Refused verbs mentioned |",
        "| --- | --- | --- |",
    ]
    for entry in accepted:
        lines.append(
            f"| `{entry['file']}` | {entry['invocationsRewritten']} | "
            f"{', '.join(entry['refusedVerbsMentioned']) or '—'} |"
        )
    lines += ["", f"## Excluded references ({len(excluded)})", "", "| File | Reason |", "| --- | --- |"]
    for entry in excluded:
        lines.append(f"| `{entry['file']}` | {entry['reason']} |")
    lines += [
        "",
        "## Not vendored",
        "",
        "The upstream `browser-bundle/`, `crates/`, `cli/`, `extension/`, `plugin/`, `ui/`,",
        "`vscode/`, `cursor-plugin/`, `demos/` and `tests/` trees are not copied here. The",
        "engine is built from the pinned commit by `engines/impeccable/build/build_engine.py`",
        "and shipped separately as a digest-bound Linux dependency; the skill package carries",
        "instructions, audited scripts and references only, never a native binary.",
        "",
    ]
    (out / "MODIFICATIONS.md").write_text("\n".join(lines), encoding="utf-8")

    derived = {}
    for path in sorted((out / "skill").rglob("*")):
        if path.is_file():
            derived[str(path.relative_to(out))] = sha256_file(path)
    for extra in ("MODIFICATIONS.json", "MODIFICATIONS.md",
                  "scripts/floe-impeccable", "scripts/normalize_skill_source.py"):
        candidate = out / extra
        if candidate.is_file():
            derived[extra] = sha256_file(candidate)
    lock["derivedFiles"] = derived
    lock["derivedFileCount"] = len(derived)
    record["sourceLock"] = "SOURCE-LOCK.json"
    (out / "MODIFICATIONS.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "SOURCE-LOCK.json").write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "derivedFiles": len(derived),
        "sourceLockCommit": lock["upstream"]["commit"],
        "out": str(out),
        "engineVersion": engine_version,
        "skillPackageVersion": package_version,
        "acceptedReferences": len(accepted),
        "excludedReferences": len(excluded),
        "commandMetadataKept": len(filtered),
        "commandMetadataDropped": [d["command"] for d in dropped],
        "skillInvocationsRewritten": modifications[0]["invocationsRewritten"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
