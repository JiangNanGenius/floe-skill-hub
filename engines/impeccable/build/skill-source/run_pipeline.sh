#!/bin/sh
# Public regeneration driver for the canonical Floe Impeccable Hub package
# (sources/impeccable, packaged version 1.1.1).
#
#   sh <hub>/engines/impeccable/build/skill-source/run_pipeline.sh \
#      <pinned-upstream-clone-dir> <hub-root> <new-empty-work-root>
#
# Inputs (all explicit; nothing is inferred from the caller's environment):
#   <pinned-upstream-clone-dir>  clean git checkout of pbakaus/impeccable at
#       commit 4fc2f83e1c8710dba772bfd4523d0efab57737b6 / tree
#       1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72 (verified fail-closed).
#   <hub-root>                   floe-skill-hub root. Read strictly read-only:
#       engines/impeccable/ENGINE-LOCK.json, engines/impeccable/
#       runtime-dependency/descriptor.v1.json, catalog/skills.json and the
#       authoritative helper code under scripts/.
#   <new-empty-work-root>        fresh directory owned by THIS run. Created if
#       absent. An existing directory is claimed only while empty; an existing
#       NON-EMPTY directory is refused unless it carries the
#       FLOE-IMPECCABLE-WORKROOT.json sentinel written by a previous run of
#       this driver AND that sentinel's "allowReplace" has been explicitly set
#       to true (the sentinel modification). Even then only the sentinel's own
#       owned children listed below are replaced — never this root itself and
#       never foreign content inside it.
#
# Outputs, all under <new-empty-work-root>:
#   staging/sources/impeccable   stage 1 (normalized derivation)
#   canonical/                   stage 2 = the candidate sources/impeccable bytes
#   gate/                        authoritative Hub helper gate (isolated mirror)
#   report-stage1.json report-stage2.json report-gate.json
#   pipeline-summary.json        run identity + canonical digests
#   FLOE-IMPECCABLE-WORKROOT.json  ownership sentinel
#
# This command NEVER writes <hub-root>/sources/impeccable or
# <hub-root>/packages. Adoption is an explicit human step after review:
#   diff -r <hub-root>/sources/impeccable <work-root>/canonical
# and a manual copy if accepted.
#
# Deterministic: re-running against the same pin into a second fresh root
# produces byte-identical canonical/ output.
#
# Maintenance layout note: this driver, stage1_normalize_skill_source.py,
# build_canonical_package.py, gate_check.py and the launcher build input
# impeccable-launcher-parent form the committed public maintenance tooling for
# the package; none of it ships inside the installed package.
set -eu

PIN_COMMIT=4fc2f83e1c8710dba772bfd4523d0efab57737b6
PIN_TREE=1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72
SENTINEL=FLOE-IMPECCABLE-WORKROOT.json
PYTHON=${PYTHON:-python3}

fail() { echo "run_pipeline: refused: $*" >&2; exit 2; }

[ "$#" -eq 3 ] || fail "usage: run_pipeline.sh <pinned-upstream-clone-dir> <hub-root> <new-empty-work-root>"
UPSTREAM=$1; HUB=$2; WORK=$3

[ -d "$UPSTREAM" ] || fail "no such upstream directory: $UPSTREAM"
[ -d "$HUB" ]      || fail "no such hub root: $HUB"
[ -L "$WORK" ]     && fail "work root must not be a symbolic link: $WORK"
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# --- hub inputs must be present (fail closed; read-only from here on) ---
for f in engines/impeccable/ENGINE-LOCK.json \
         engines/impeccable/runtime-dependency/descriptor.v1.json \
         catalog/skills.json scripts/hubcore.py scripts/build_packages.py; do
  [ -f "$HUB/$f" ] || fail "hub input missing: $HUB/$f"
done
for f in stage1_normalize_skill_source.py build_canonical_package.py \
         gate_check.py impeccable-launcher-parent; do
  [ -f "$DIR/$f" ] || fail "maintenance tool missing beside the driver: $f"
done

# --- pin verification: exact commit, exact tree, clean worktree ---
[ -d "$UPSTREAM/skill" ] || fail "no skill/ directory in the upstream clone"
for f in ENGINE_VERSION package.json LICENSE NOTICE.md skill/SKILL.src.md \
         skill/scripts/command-metadata.json; do
  [ -f "$UPSTREAM/$f" ] || fail "pinned input missing from the upstream clone: $UPSTREAM/$f"
done
git -C "$UPSTREAM" rev-parse HEAD >/dev/null 2>&1 || fail "upstream directory is not a git checkout"
HEAD=$(git -C "$UPSTREAM" rev-parse HEAD)
TREE=$(git -C "$UPSTREAM" rev-parse 'HEAD^{tree}')
[ "$HEAD" = "$PIN_COMMIT" ] || fail "upstream HEAD $HEAD is not the pinned commit $PIN_COMMIT"
[ "$TREE" = "$PIN_TREE" ]   || fail "upstream tree $TREE is not the pinned tree $PIN_TREE"
if [ -n "$(git -C "$UPSTREAM" status --porcelain)" ]; then
  fail "upstream worktree at $PIN_COMMIT is not clean (tracked or untracked drift can change package bytes)"
fi

# --- work root safety: owned fresh area only; never overwrite foreign data ---
HUBR=$(CDPATH= cd -- "$HUB" && pwd -P)
UPR=$(CDPATH= cd -- "$UPSTREAM" && pwd -P)
# real-path of the (possibly notional) work root, symlinks and .. resolved
WORKR=$(CDPATH= "$PYTHON" -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$WORK")
case "$WORKR" in
  "$HUBR"|"$HUBR/"*) fail "unsafe output: work root $WORK resolves inside the hub tree ($HUBR); the hub stays read-only for this command";;
  "$UPR"|"$UPR/"*)   fail "unsafe output: work root $WORK resolves inside the upstream clone ($UPR)";;
esac
if [ -e "$WORK" ] && [ ! -d "$WORK" ]; then
  fail "work root exists but is not a directory: $WORK"
fi
write_sentinel() {
  # $1: absolute claimed root
  "$PYTHON" - "$1/$SENTINEL" <<'PY'
import json, sys
payload = {
    "driver": "engines/impeccable/build/skill-source/run_pipeline.sh",
    "pinnedCommit": "4fc2f83e1c8710dba772bfd4523d0efab57737b6",
    "pinnedTree": "1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72",
    "ownedChildren": ["staging", "canonical", "gate",
                      "report-stage1.json", "report-stage2.json",
                      "report-gate.json", "pipeline-summary.json"],
    "allowReplace": False,
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY
}
if [ ! -d "$WORK" ]; then
  mkdir -p "$WORK"
  write_sentinel "$WORKR"
elif [ -z "$(ls -A "$WORK")" ]; then
  write_sentinel "$WORKR"
else
  if [ ! -f "$WORK/$SENTINEL" ]; then
    fail "existing non-empty directory without $SENTINEL — this driver never overwrites or deletes foreign content; choose a fresh work root"
  fi
  if ! "$PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if d.get("allowReplace") is True and d.get("driver","").endswith("run_pipeline.sh") and d.get("pinnedCommit")=="4fc2f83e1c8710dba772bfd4523d0efab57737b6" else 1)' "$WORK/$SENTINEL"; then
    fail "the claimed work root still holds a previous run's output; to rebuild in place, MODIFY the sentinel: set \"allowReplace\": true in $WORK/$SENTINEL (only this driver's own owned children are ever replaced)"
  fi
  for owned in staging canonical gate report-stage1.json report-stage2.json report-gate.json pipeline-summary.json; do
    case "$owned" in
      */*|.|..) fail "sentinel owned-child name is not a plain entry: $owned";;
    esac
    [ -e "$WORK/$owned" ] && [ ! -L "$WORK/$owned" ] && rm -rf -- "$WORK/$owned"
    [ -L "$WORK/$owned" ] && fail "owned child $owned is a symbolic link; refusing to delete through it"
  done
  # one-time acknowledgement: re-arm the sentinel so a third run refuses again
  write_sentinel "$WORKR"
fi

# --- stage 1: normalize the pinned upstream source ---
mkdir -p "$WORK/staging/sources"
"$PYTHON" "$DIR/stage1_normalize_skill_source.py" \
  --upstream "$UPSTREAM" \
  --out "$WORK/staging/sources/impeccable" \
  --engine-lock "$HUBR/engines/impeccable/ENGINE-LOCK.json" \
  --commit "$PIN_COMMIT" --tree "$PIN_TREE" \
  > "$WORK/report-stage1.json"

# --- stage 2: canonicalize into the package layout ---
"$PYTHON" "$DIR/build_canonical_package.py" \
  --upstream "$UPSTREAM" \
  --staging "$WORK/staging/sources/impeccable" \
  --descriptor "$HUBR/engines/impeccable/runtime-dependency/descriptor.v1.json" \
  --launcher "$DIR/impeccable-launcher-parent" \
  --engine-lock "$HUBR/engines/impeccable/ENGINE-LOCK.json" \
  --out "$WORK/canonical" \
  > "$WORK/report-stage2.json"

# --- gate: authoritative Hub helper battery (isolated, read-only over the hub) ---
mkdir -p "$WORK/gate"
"$PYTHON" "$DIR/gate_check.py" \
  --package "$WORK/canonical" --hub "$HUBR" --work "$WORK/gate" \
  > "$WORK/report-gate.json"

# --- run summary (digest of every canonical file + identities) ---
WR=$(CDPATH= cd -- "$WORK" && pwd)
"$PYTHON" - "$WR" "$HUBR" <<'PY'
import hashlib, json, pathlib, subprocess, sys
work, hub = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
canonical = work / "canonical"
files = {}
for path in sorted(canonical.rglob("*")):
    if path.is_symlink():
        raise SystemExit(f"symlink in canonical output: {path}")
    if path.is_file():
        files[path.relative_to(canonical).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
def git(root, *args):
    if not (root / ".git").exists():
        return ""   # plain snapshot: never disclose an enclosing repo's commit
    try:
        return subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""
stage2 = json.loads((work / "report-stage2.json").read_text(encoding="utf-8"))
summary = {
    "role": "regeneration run summary (NOT the shipped package; the package lock is canonical/references/SOURCE-LOCK.json)",
    "pinnedUpstream": {"commit": "4fc2f83e1c8710dba772bfd4523d0efab57737b6",
                       "tree": "1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72"},
    "hubCommit": git(hub, "rev-parse", "HEAD"),
    "canonicalFiles": len(files),
    "canonicalTotalBytes": sum((canonical / k).stat().st_size for k in files),
    "canonicalSha256": files,
    "contentDigest": json.loads((work / "report-gate.json").read_text(encoding="utf-8")).get("contentDigest"),
    "skillSha256": stage2.get("skillSha256"),
    "descriptor": stage2.get("descriptor"),
    "nextStep": "review canonical/ (diff -r against <hub>/sources/impeccable), then copy manually if accepted; this driver never wrote the hub",
}
(work / "pipeline-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("canonicalFiles", "canonicalTotalBytes", "contentDigest", "hubCommit")},
                 indent=2, sort_keys=True))
PY

echo "canonical output: $(CDPATH= cd -- "$WORK/canonical" && pwd)"
echo "This run did NOT write $HUBR/sources/impeccable. Review with 'diff -r', then copy manually only if accepted."
