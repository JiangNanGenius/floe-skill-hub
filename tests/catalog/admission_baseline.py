#!/usr/bin/env python3
"""Explicit reviewed admission baseline for the REAL-data catalog tests.

The 2026-10 incremental admissions and publications changed the ACTUAL
published truth. Tests that probe the real repository (real registry, real
release feeds, real publication ledger) must compare against this EXPLICIT,
independently reviewed baseline — transcribed here as literals — and never
recompute the same set the implementation under test reads, and never
silently follow whatever the tree happens to contain.

Baseline provenance (Root-signed read-back on branch
codex/skill-hub-auto-updates-20261028, head 3e145cd6cb04b4c36476c3e59a7495e7fad80c64,
2026-10-27/28):

* Selection: 43 registry rows = 39 iOS optional download offers + 4
  App-provided builtins (never download offers). 36 optional rows are also
  Android download offers; exactly 3 optional rows are iOS-only planned
  (impeccable, algorithmic-art, canvas-design — the "final two art skills"
  admitted 2026-10-27 are the iOS-only algorithmic-art + canvas-design).
* All nine mandatory deep IDs are now qualified; every qualified script row
  (the 9 deep + citation-management + sympy) holds a real guest receipt
  (executionVerified true, evidence guest-verified). All 43 rows are
  packaged+reviewed+licenseChecked with frozen adaptation; the candidate
  registry keeps published=false (publication is the signed feed act).
* Cumulative publication ledger: 12 rows across 6 signed publication pins;
  the bootstrap pin e02b3e94 covers 31 offers per channel; the cumulative
  baseline verifies to 39 iOS + 36 Android = 75 facts.
* Frozen engine: component 0.1.17+floe.1.1.1, artifact 5594368 bytes,
  sha256 774333d30d6e54604342182e49853851c7e0ebfa9e92fc4216f4a68872d00a1a.

Same-version published bytes and ledger history remain immutable: this module
only describes the reviewed current truth; it changes nothing.
"""
import json
import os
import pathlib
import subprocess

# --- download-offer identities (explicit literals, 39 / 36) ---------------
IOS_OPTIONAL_OFFER_IDS = frozenset({
    "a11y-audit", "algorithmic-art", "canvas-design", "citation-management",
    "code-to-prd", "composition-patterns", "content-production",
    "copy-editing", "copywriting", "deep-research", "deepread",
    "doc-coauthoring", "exploratory-data-analysis", "floe-email-drafting",
    "floe-file-organizer", "floe-invoice-organizer", "impeccable",
    "internal-comms", "literature-review", "markitdown", "meetings",
    "product-discovery", "product-manager-toolkit", "react-best-practices",
    "requesting-code-review", "research-summarizer",
    "scientific-critical-thinking", "scientific-visualization",
    "social-content", "statistical-analysis", "sympy", "systematic-debugging",
    "test-driven-development", "theme-factory", "ui-design-system",
    "ux-researcher-designer", "web-design-guidelines", "webapp-testing",
    "writing-guidelines",
})
ANDROID_OPTIONAL_OFFER_IDS = frozenset({
    "a11y-audit", "citation-management", "code-to-prd", "composition-patterns",
    "content-production", "copy-editing", "copywriting", "deep-research",
    "deepread", "doc-coauthoring", "exploratory-data-analysis",
    "floe-email-drafting", "floe-file-organizer", "floe-invoice-organizer",
    "internal-comms", "literature-review", "markitdown", "meetings",
    "product-discovery", "product-manager-toolkit", "react-best-practices",
    "requesting-code-review", "research-summarizer",
    "scientific-critical-thinking", "scientific-visualization",
    "social-content", "statistical-analysis", "sympy", "systematic-debugging",
    "test-driven-development", "theme-factory", "ui-design-system",
    "ux-researcher-designer", "web-design-guidelines", "webapp-testing",
    "writing-guidelines",
})
IOS_ONLY_OPTIONAL_IDS = frozenset({"impeccable", "algorithmic-art",
                                   "canvas-design"})
assert IOS_OPTIONAL_OFFER_IDS - ANDROID_OPTIONAL_OFFER_IDS == IOS_ONLY_OPTIONAL_IDS
assert len(IOS_OPTIONAL_OFFER_IDS) == 39 and len(ANDROID_OPTIONAL_OFFER_IDS) == 36

# --- qualified selection / execution truth --------------------------------
EXECUTION_VERIFIED_IDS = frozenset({
    "algorithmic-art", "canvas-design", "citation-management",
    "exploratory-data-analysis", "impeccable", "literature-review",
    "markitdown", "scientific-visualization", "statistical-analysis",
    "sympy", "webapp-testing",
})
DEEP_MANDATORY_IDS = frozenset({
    "algorithmic-art", "canvas-design", "exploratory-data-analysis",
    "impeccable", "literature-review", "markitdown",
    "scientific-visualization", "statistical-analysis", "webapp-testing",
})
SELECTION_ROWS = 43
QUALIFIED_SELECTION = 43          # every candidate row is qualified today
BUILTIN_PROVIDED = 4              # the four App-provided builtins
DOWNLOAD_ELIGIBLE = 39            # qualified selection minus builtins

# --- publication ledger (cumulative, immutable history) --------------------
BOOTSTRAP_PIN = "e02b3e9478c6ddc1261d5c987ac0ca5457beb916"
BOOTSTRAP_OFFERS_PER_CHANNEL = 31
PUBLICATION_PINS = (
    "0061804bb54b5162d3430d7a191bb46b80565585",
    "079d547b19262c5458d00a40eb2a9d96ec56e228",
    "416d0fa8249542f36767dc9b4236f020cc1a7981",
    "5a8c191f38afb9920da31cc113be5bb482094a3a",
    "a3f3e1f83e89863c4bd8cab9ac6108b1959c6d6b",
    BOOTSTRAP_PIN,
)
CUMULATIVE_FACTS = 75             # 39 iOS + 36 Android verified facts

# --- the reviewed 2026-10-28 ledger as IMMUTABLE historical data -------------
# The cumulative ledger above is the reviewed truth AT this exact commit; it
# is preserved by reading the ledger BLOB at this content-addressed commit,
# never by re-deriving it from the live working tree (which legitimately
# grows with every authorized append). The live ledger must still contain
# every one of these rows unchanged; appends may only ADD rows.
REVIEWED_BASELINE_COMMIT = "3e145cd6cb04b4c36476c3e59a7495e7fad80c64"
REVIEWED_LEDGER_REL = "catalog/publication-ledger.json"
# sha256 of the canonical ledger bytes committed at REVIEWED_BASELINE_COMMIT
# (independent Root review read-back 2026-10-28; verified, not derived).
REVIEWED_LEDGER_SHA256 = (
    "a6b36da41470dd8a066735d6aff35838cb3f5c36b2b7177f5c12a627d839b6a7")
REVIEWED_LEDGER_ROWS = 12         # 6 pins x (ios + android)
REVIEWED_LEDGER_PINS = 6          # exactly len(PUBLICATION_PINS) at B

# --- frozen engine artifact (descriptor-bound, read-only test input) -------
FROZEN_ENGINE_COMPONENT_VERSION = "0.1.17+floe.1.1.1"
FROZEN_ENGINE_MINIMUM_APP_VERSION = "1.7.60"
FROZEN_ENGINE_ARTIFACT_REL = (
    "engines/impeccable/dist/impeccable-0.1.17+floe.1.1.1/"
    "riscv64gc-unknown-linux-musl/floe-impeccable")
FROZEN_ENGINE_ARTIFACT_BYTES = 5594368
FROZEN_ENGINE_ARTIFACT_SHA256 = (
    "774333d30d6e54604342182e49853851c7e0ebfa9e92fc4216f4a68872d00a1a")


def load_ledger(root):
    """Read the committed publication ledger (production data, read-only)."""
    return json.loads((pathlib.Path(root) / "catalog" /
                       "publication-ledger.json").read_bytes())


def reviewed_ledger_blob(root):
    """Exact committed bytes of the ledger at the immutable reviewed commit.

    Read-only Git plumbing against the content-addressed commit
    REVIEWED_BASELINE_COMMIT with inherited GIT_* overrides, hook paths,
    system/global config and replacement refs all neutralized, mirroring the
    production reader's posture. The blob never changes: a later append to
    the live ledger cannot mutate a historical Git object.
    """
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_NO_REPLACE_OBJECTS": "1"})
    proc = subprocess.run(
        ["git", "-C", str(root), "-c", "core.hooksPath=" + os.devnull,
         "-c", "core.fsmonitor=false", "show",
         f"{REVIEWED_BASELINE_COMMIT}:{REVIEWED_LEDGER_REL}"],
        capture_output=True, env=env)
    if proc.returncode != 0:
        raise AssertionError(
            "reviewed baseline ledger unreadable at "
            f"{REVIEWED_BASELINE_COMMIT[:10]} (verification stays "
            "fail-closed): " + proc.stderr.decode("utf-8", "replace").strip())
    return proc.stdout


def ensure_pinned_commits_available(root, commits=None):
    """Make the trusted Git objects for ledger pins readable in this checkout.

    The publication-immutability guardrail verifies ledger rows against Git
    objects at their pinned publication commits.  A CI job checked out with
    actions/checkout default ``fetch-depth: 1`` has only HEAD's objects, so
    those trusted reads fail on the environment, NOT on the content.  This
    helper completes the checkout (full history of the fetched refs) and
    fails closed if a pinned commit still cannot be read: it never weakens
    or skips the verification, and it is a no-op in a normal full clone.
    """
    root = pathlib.Path(root)
    if commits is None:
        commits = set(PUBLICATION_PINS)
    else:
        commits = set(commits)
    # The reviewed-baseline commit is a required trusted object too: the
    # historical ledger blob is read at that exact content-addressed commit.
    commits.add(REVIEWED_BASELINE_COMMIT)

    def _has(commit):
        return subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{commit}^{{commit}}"],
            capture_output=True).returncode == 0

    missing = [c for c in sorted(commits) if not _has(c)]
    if missing and subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True).stdout.strip() == "true":
        fetch = subprocess.run(["git", "-C", str(root), "fetch", "--unshallow",
                                "origin"], capture_output=True, text=True)
        if fetch.returncode != 0:
            raise AssertionError(
                "shallow checkout and history fetch failed: "
                + (fetch.stderr or fetch.stdout))
        missing = [c for c in sorted(commits) if not _has(c)]
    if missing:
        raise AssertionError(
            "pinned publication commits unreadable in this checkout "
            "(ledger verification stays fail-closed): " + ", ".join(missing))
