#!/bin/sh
# Floe Impeccable launcher.
#
# Runs the Floe engine binary for THIS machine's OS and architecture, including
# the riscv64 Linux guest that the upstream launcher does not know about
# (upstream maps only arm64 and x64 and otherwise tries to download a release
# asset from github.com).
#
# Differences from the upstream launcher, all deliberate:
#
#   * riscv64 is a first-class architecture (linux-riscv64), so the Floe Linux
#     guest resolves a real binary instead of failing with "unknown arch";
#   * there is NO download path and NO user cache. Skill and engine installation
#     and updates are owned by the Floe Skill Hub (signed catalog, digest-bound
#     engine). A missing binary is a hard failure that names the expected
#     location, never a network fetch;
#   * an optional digest gate re-verifies the binary against the engine
#     directory's SHA256SUMS before exec (FLOE_IMPECCABLE_VERIFY_DIGEST=1). The
#     native installer already verifies the digest at install time, so the
#     default is off: hashing a multi-megabyte binary on an emulated guest costs
#     real time on every invocation;
#   * the upstream engine-probe handshake is kept for untrusted candidates
#   * `snapshot-scan` gets `--no-timeout` by default unless the caller
#     chose a timeout flag; explicit choices always pass through untouched
#     (see "Floe default scan policy" below);
#     (a binary found on PATH), so a same-named binary from another tool is
#     never exec'd blindly.
#
# Environment the engine expects (set here, before any exec):
#   IMPECCABLE_SKILL_DIR  the engine's skill directory holding
#                         reference/*.md and command-metadata.json;
#                         defaults to references/engine-data (canonical
#                         Hub layout); an explicit value always wins
#   IMPECCABLE_SELF       how the binary should name itself in printed commands
#
# Exit codes: 0 from the engine; 127 when no engine binary can be resolved.
set -eu

dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Canonical Hub layout: the engine reads the read-only compatibility data root
# at <skill>/references/engine-data (a mirror of the upstream skill directory:
# reference/*.md, scripts/command-metadata.json, SKILL.md, VERSION). An explicit
# IMPECCABLE_SKILL_DIR from the runtime always wins; the parent fallback keeps a
# pre-canonical dev checkout (skill dir carrying reference/) working unchanged.
if [ -z "${IMPECCABLE_SKILL_DIR:-}" ]; then
  if [ -d "$dir/../references/engine-data" ]; then
    IMPECCABLE_SKILL_DIR=$(CDPATH= cd -- "$dir/../references/engine-data" && pwd)
  else
    IMPECCABLE_SKILL_DIR=$(CDPATH= cd -- "$dir/.." && pwd)
  fi
fi
: "${IMPECCABLE_SELF:=$0}"
export IMPECCABLE_SKILL_DIR IMPECCABLE_SELF

# Floe default scan policy (user policy, 2026-10-27): an ordinary Impeccable
# design scan has NO engine deadline. This policy is about the engine
# deadline only; existing caller/task wait and cancel controls are what
# bound a scan run and stay unchanged. The raw engine CLI keeps its frozen
# 120000 ms default unchanged; this launcher, the skill's normal scan route,
# appends `--no-timeout` ONLY when the caller asked for `snapshot-scan` and
# chose no timeout flag at all. Every explicit caller choice passes through
# untouched and wins: `--timeout-ms 0` stays an immediate typed timeout, an
# explicit finite `--timeout-ms <n>` stays that finite budget, an explicit
# `--no-timeout` stays as given, and the engine's mutual-exclusion refusal of
# `--no-timeout` together with `--timeout-ms` is never bypassed here. Hit-test,
# round and byte caps are untouched by this policy; only the wall-clock
# deadline is removed, and the result then reports `budget.timeoutMs: null`.
# An engine build that predates `--no-timeout` fails closed on the appended
# flag (typed argument error) — there is no silent fallback to an old binary.
if [ "${1:-}" = "snapshot-scan" ]; then
  floe_has_timeout=0
  for floe_arg in "$@"; do
    case "$floe_arg" in
      --timeout-ms|--timeout-ms=*|--no-timeout) floe_has_timeout=1; break ;;
    esac
  done
  if [ "$floe_has_timeout" = 0 ]; then set -- "$@" --no-timeout; fi
fi

case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin) os=darwin ;;
  Linux) os=linux ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT) os=windows ;;
  *) os=unknown ;;
esac

case "$(uname -m 2>/dev/null || echo unknown)" in
  arm64|aarch64) arch=arm64 ;;
  x86_64|amd64) arch=x64 ;;
  riscv64) arch=riscv64 ;;
  *) arch=unknown ;;
esac

case "$os-$arch" in
  linux-riscv64) triple=riscv64gc-unknown-linux-musl ;;
  linux-arm64) triple=aarch64-unknown-linux-gnu ;;
  linux-x64) triple=x86_64-unknown-linux-gnu ;;
  darwin-arm64) triple=aarch64-apple-darwin ;;
  darwin-x64) triple=x86_64-apple-darwin ;;
  *) triple="" ;;
esac

fail_no_engine() {
  echo "floe-impeccable: no engine binary for $os-$arch (triple ${triple:-unknown})." >&2
  echo "Looked for: \${FLOE_IMPECCABLE_ENGINE}, \${FLOE_IMPECCABLE_ENGINE_DIR}/$triple/floe-impeccable, $dir/../engines/*/$triple/floe-impeccable, and floe-impeccable on PATH." >&2
  echo "The Floe engine is installed and updated only by the Floe Skill Hub (signed catalog, digest-bound). This launcher never downloads one." >&2
  echo "Install the engine from the Hub, or set FLOE_IMPECCABLE_ENGINE to the verified binary path." >&2
  exit 127
}

# True when the candidate answers the engine handshake. Used only for candidates
# this launcher does not already trust (a binary found on PATH).
probe_ok() {
  probe_out=$(FLOE_IMPECCABLE_LAUNCHER_PROBE=1 "$1" engine-probe 2>/dev/null) || return 1
  case "$probe_out" in
    impeccable-engine*) return 0 ;;
  esac
  return 1
}

verify_digest() {
  candidate=$1
  engine_dir=$(dirname "$candidate")
  sums="$engine_dir/SHA256SUMS.txt"
  [ -f "$sums" ] || {
    echo "floe-impeccable: FLOE_IMPECCABLE_VERIFY_DIGEST=1 but $sums is missing; refusing to exec an unverifiable engine." >&2
    return 1
  }
  expected=$(awk '/ floe-impeccable$/ { print $1; exit }' "$sums" 2>/dev/null || true)
  [ -n "$expected" ] || {
    echo "floe-impeccable: no floe-impeccable entry in $sums; refusing to exec." >&2
    return 1
  }
  actual=""
  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$candidate" | cut -d' ' -f1)
  elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$candidate" | cut -d' ' -f1)
  else
    echo "floe-impeccable: no sha256 tool available; refusing to exec without the requested digest check." >&2
    return 1
  fi
  if [ "$actual" != "$expected" ]; then
    echo "floe-impeccable: digest mismatch for $candidate" >&2
    echo "  expected $expected" >&2
    echo "  actual   $actual" >&2
    return 1
  fi
  return 0
}

try_candidate() {
  candidate=$1
  shift
  if [ $# -gt 0 ]; then trusted=$1; shift; else trusted=1; fi
  [ -n "$candidate" ] || return 1
  if [ -f "$candidate" ] && [ ! -x "$candidate" ]; then
    # Lost the executable bit in transit (zip extraction, some copiers).
    chmod +x "$candidate" 2>/dev/null || true
  fi
  [ -x "$candidate" ] || return 1
  if [ "$trusted" != 1 ] && ! probe_ok "$candidate"; then
    return 1
  fi
  if [ "${FLOE_IMPECCABLE_VERIFY_DIGEST:-0}" = 1 ] && ! verify_digest "$candidate"; then
    exit 127
  fi
  exec "$candidate" "$@"
}

# 1. An explicit path from the Floe runtime or installer (already digest-bound).
if [ -n "${FLOE_IMPECCABLE_ENGINE:-}" ]; then
  try_candidate "$FLOE_IMPECCABLE_ENGINE" 1 "$@" || :
  echo "floe-impeccable: FLOE_IMPECCABLE_ENGINE=$FLOE_IMPECCABLE_ENGINE is not an executable engine binary." >&2
  echo "The Floe engine is installed and updated only by the Floe Skill Hub (signed catalog, digest-bound). This launcher never downloads one." >&2
  exit 127
fi

# 2. An engine directory chosen by the runtime, resolved by triple.
if [ -n "${FLOE_IMPECCABLE_ENGINE_DIR:-}" ] && [ -n "$triple" ]; then
  try_candidate "$FLOE_IMPECCABLE_ENGINE_DIR/$triple/floe-impeccable" 1 "$@" || :
  try_candidate "$FLOE_IMPECCABLE_ENGINE_DIR/floe-impeccable" 1 "$@" || :
fi

# 3. A Hub-installed layout next to this skill: engines/<engineId>/<triple>/.
if [ -n "$triple" ]; then
  for engine_root in "$dir/../engines" "$dir/../../engines" "$IMPECCABLE_SKILL_DIR/../engines"; do
    [ -d "$engine_root" ] || continue
    for versioned in "$engine_root"/impeccable/dist/*; do
      [ -d "$versioned" ] || continue
      try_candidate "$versioned/$triple/floe-impeccable" 1 "$@" || :
    done
    for versioned in "$engine_root"/*; do
      [ -d "$versioned" ] || continue
      try_candidate "$versioned/$triple/floe-impeccable" 1 "$@" || :
    done
  done
fi

# 4. A binary already on PATH, accepted only after the handshake.
probing=${FLOE_IMPECCABLE_LAUNCHER_PROBE:-}
if [ -z "$probing" ] && command -v floe-impeccable >/dev/null 2>&1; then
  path_candidate=$(command -v floe-impeccable)
  if [ "$path_candidate" != "$0" ]; then
    try_candidate "$path_candidate" 0 "$@" || :
  fi
fi

fail_no_engine
