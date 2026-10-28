#!/usr/bin/env python3
"""Regression for the Impeccable candidate preflight (patch application audit).

Real failure (updater run 40614187492): applying the tracked patch set to the
upstream 0.1.18 candidate (commit f29cd24fdecfa5612e35e34c1c868d4a3fca930c)
exited 2 with "a patch left reject or original files behind" although every
hunk had applied successfully (exit 0) at a pure line offset with exact
context — GNU patch's default backup-on-mismatch semantics leave a `.orig`
copy of the pristine file behind for every offset-applied hunk, and the audit
treated those legitimate backups as conflicts.

The repair in `engines/impeccable/build/build_engine.py::apply_patches` pins
the application contract on `patch(1)` itself instead of on backup side
effects:

* `--fuzz=0`    — a hunk whose context no longer matches exactly (the true
                  conflict signal) now fails the dry-run gate and must be
                  rebased; it can never be placed by dropping context lines
                  (the patch(1) default fuzz factor is 2);
* `--no-backup-if-mismatch` — an offset-only application is legitimate and
                  leaves no `.orig` artifact behind;

while the fail-closed scan for any surviving `.rej`/`.orig` file, the
`with fuzz`/`FAILED` output guards and the post-conditions
(`verify_patch_effects`) stay untouched, so real rejects still fail the build.
The published 0.1.17 bytes (pin, contract, binary, receipts) are not changed:
the patch digests applied here remain exactly those recorded in the frozen
dist PROVENANCE manifest.

Stdlib only. Run:

    python3 tests/test_impeccable_candidate_preflight.py

Set TMPDIR outside the hub checkout first (as for the other impeccable tests).
The real patch-set probes against both the frozen 0.1.17 pin and the 0.1.18
candidate additionally require a local clone of the public upstream
(pbakaus/impeccable) containing those commits; point
FLOE_IMPECCABLE_UPSTREAM_CLONE at it to enable them. Without it they skip.
The probes export each tree with `git archive` into an ephemeral temp dir;
they never write into the clone.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "engines" / "impeccable" / "build" / "build_engine.py"
TRACKED_PATCH_DIR = REPO / "engines" / "impeccable" / "patches"
TRACKED_LOCK = REPO / "engines" / "impeccable" / "ENGINE-LOCK.json"
FROZEN_PROVENANCE = (
    REPO / "engines" / "impeccable" / "dist" / "impeccable-0.1.17+floe.1.1.1"
    / "riscv64gc-unknown-linux-musl" / "PROVENANCE.json"
)

# Public upstream identities for the real patch-set probes. The frozen pin is
# read from the tracked lock; the candidate is the historical 0.1.18 release
# commit that triggered run 40614187492.
CANDIDATE_COMMIT = "f29cd24fdecfa5612e35e34c1c868d4a3fca930c"
CANDIDATE_TREE = "dd704e4fe593e595f274637332aa1ee35060bace"
CANDIDATE_VERSION = "0.1.18"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_engine_under_test", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_apply(module, patch_dir, tree):
    """Call the real apply_patches with output captured; returns (result, stdout)."""
    old = module.PATCH_DIR
    module.PATCH_DIR = Path(patch_dir)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            applied = module.apply_patches(Path(tree))
    finally:
        module.PATCH_DIR = old
    return applied, buf.getvalue()


def artifacts(tree: Path) -> list[str]:
    return sorted(str(p.relative_to(tree))
                  for p in list(tree.rglob("*.rej")) + list(tree.rglob("*.orig")))


BASE_FILE = "l1\nl2\nl3\nX\nl5\nl6\nl7\nl8\nl9\nl10\n"
# A minimal unified patch in the tracked patches' style: hunk anchored at
# line 3, exact context l3/l5, replaces X with Y.
CLEAN_PATCH = """diff --git a/f.txt b/f.txt
--- a/f.txt
+++ b/f.txt
@@ -3,3 +3,3 @@
 l3
-X
+Y
 l5
"""


class SyntheticApplyPatchTests(unittest.TestCase):
    """Behavior of the repaired apply contract, independent of upstream size."""

    def setUp(self):
        self.module = load_builder()
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-preflight-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pdir = self.tmp / "patches"
        self.pdir.mkdir()
        (self.pdir / "0000-synthetic.patch").write_text(CLEAN_PATCH)
        self.tree = self.tmp / "tree"

    def make_tree(self, text: str) -> Path:
        self.tree.mkdir()
        (self.tree / "f.txt").write_text(text)
        return self.tree

    def shift_head(self, text: str, n: int) -> str:
        pad = "".join(f"pad{i}\n" for i in range(n))
        return pad + text

    def expected(self):
        return BASE_FILE.replace("X\n", "Y\n")

    def test_clean_application_applies_and_reports_digest(self):
        tree = self.make_tree(BASE_FILE)
        applied, out = run_apply(self.module, self.pdir, tree)
        self.assertEqual([e["patch"] for e in applied], ["0000-synthetic.patch"])
        digest = hashlib.sha256((self.pdir / "0000-synthetic.patch").read_bytes()).hexdigest()
        self.assertEqual(applied[0]["sha256"], digest)
        self.assertEqual((tree / "f.txt").read_text(), self.expected())
        self.assertEqual(artifacts(tree), [])
        self.assertIn("applied with exact context", out)

    def test_offset_only_application_is_accepted_without_artifacts(self):
        # Exactly the hosted run 40614187492 shape: context matches fully but
        # every hunk lands at a shifted line, and the patch binary would by
        # default leave a .orig backup of the pristine file behind.
        tree = self.make_tree(self.shift_head(BASE_FILE, 3))
        applied, out = run_apply(self.module, self.pdir, tree)
        self.assertEqual(len(applied), 1)
        self.assertEqual((tree / "f.txt").read_text(), self.shift_head(self.expected(), 3))
        self.assertEqual(artifacts(tree), [], "offset application must not leave backups/rejects")

    def test_fuzz_needed_hunk_fails_closed_and_leaves_file_untouched(self):
        # An interloping line inside the declared context: only a FUZZY match
        # could place this hunk. The repaired contract must refuse it at the
        # dry-run gate instead of silently building a shifted edit.
        tree = self.make_tree("l3\nQ\nX\nl5\n")
        before = (tree / "f.txt").read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            run_apply(self.module, self.pdir, tree)
        self.assertEqual(ctx.exception.code, 2)
        self.assertEqual((tree / "f.txt").read_bytes(), before,
                         "a refused patch must not modify the tree")

    def test_true_reject_fails_closed(self):
        tree = self.make_tree("nothing\nat\nall\nhere\n")
        with self.assertRaises(SystemExit) as ctx:
            run_apply(self.module, self.pdir, tree)
        self.assertEqual(ctx.exception.code, 2)

    def test_surviving_orig_or_rej_artifact_is_fatal(self):
        # The fail-closed artifact scan stays: stale reject/original files
        # (whatever produced them) abort the build even when the patch itself
        # applies.
        tree = self.make_tree(BASE_FILE)
        (tree / "stale.rs.orig").write_text("junk")
        with self.assertRaises(SystemExit) as ctx:
            run_apply(self.module, self.pdir, tree)
        self.assertEqual(ctx.exception.code, 2)

    def test_reapplying_an_already_applied_patch_fails(self):
        tree = self.make_tree(BASE_FILE)
        run_apply(self.module, self.pdir, tree)
        with self.assertRaises(SystemExit):
            run_apply(self.module, self.pdir, tree)

    def test_dry_run_gate_error_text_directs_a_rebase(self):
        tree = self.make_tree("l3\nQ\nX\nl5\n")
        buf = io.StringIO()
        old = self.module.PATCH_DIR
        self.module.PATCH_DIR = self.pdir
        try:
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    self.module.apply_patches(tree)
        finally:
            self.module.PATCH_DIR = old
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("no longer applies", payload["error"])
        self.assertIn("rebase", payload["error"])
        self.assertEqual(payload["patch"], "0000-synthetic.patch")

    def test_fuzzy_or_failed_output_is_fatal_even_with_exit_zero(self):
        # Parsing defense-in-depth: if a patch binary ever reported success
        # while its own output showed fuzzy placement or a FAILED hunk, the
        # build must still stop.
        tree = self.make_tree(BASE_FILE)
        for marker, message in (
            ("patching file f.txt\nHunk #1 succeeded at 2 with fuzz 1.\n", "fuzz"),
            ("patching file f.txt\nHunk #1 FAILED at 3.\n", "hunk failed"),
        ):
            fake = subprocess.CompletedProcess([], 0, marker, "")
            with mock.patch.object(self.module.subprocess, "run", return_value=fake):
                with self.assertRaises(SystemExit, msg=message):
                    self.module.apply_patches(tree)

    def test_every_patch_invocation_pins_the_application_contract(self):
        tree = self.make_tree(self.shift_head(BASE_FILE, 2))
        calls = []
        real_run = self.module.subprocess.run

        def spy(cmd, *a, **k):
            calls.append(list(cmd))
            return real_run(cmd, *a, **k)

        old = self.module.PATCH_DIR
        self.module.PATCH_DIR = self.pdir
        try:
            with mock.patch.object(self.module.subprocess, "run", side_effect=spy):
                with redirect_stdout(io.StringIO()):
                    self.module.apply_patches(tree)
        finally:
            self.module.PATCH_DIR = old
        self.assertEqual(len(calls), 2, "dry-run plus real apply")
        for argv in calls:
            self.assertIn("-p1", argv)
            self.assertIn("--forward", argv)
            self.assertIn("--fuzz=0", argv, "fuzzy placement must be impossible")
            self.assertIn("--no-backup-if-mismatch", argv,
                          "offset application must not create mismatch backups")
        self.assertIn("--dry-run", calls[0])
        self.assertNotIn("--dry-run", calls[1])


class RealPatchSetProbeTests(unittest.TestCase):
    """Apply the TRACKED patch set to the real frozen pin and to the 0.1.18
    candidate export, through the same repaired code path.

    Requires a local clone of the public upstream containing both commits;
    point FLOE_IMPECCABLE_UPSTREAM_CLONE at it. Without the clone (or without
    the optional candidate commit) these probes skip.
    """

    @classmethod
    def setUpClass(cls):
        clone = os.environ.get("FLOE_IMPECCABLE_UPSTREAM_CLONE", "")
        cls.clone = Path(clone) if clone else None
        if cls.clone is not None and not (cls.clone / ".git").exists():
            raise unittest.SkipTest("FLOE_IMPECCABLE_UPSTREAM_CLONE is not a git clone")

    def require_clone(self):
        if self.clone is None:
            self.skipTest("set FLOE_IMPECCABLE_UPSTREAM_CLONE to a pbakaus/impeccable "
                          "clone carrying the pinned commits to run the real patch-set probes")

    def setUp(self):
        self.module = load_builder()
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-real-probe-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def export(self, commit: str) -> Path:
        tree = self.tmp / f"export-{commit[:8]}"
        tree.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(self.clone), "archive", "--format=tar", commit],
            capture_output=True)
        if archive.returncode != 0:
            self.skipTest(f"clone does not carry commit {commit} (optional probe)")
        extract = subprocess.run(["tar", "-x", "-C", str(tree)], input=archive.stdout,
                                 capture_output=True)
        self.assertEqual(extract.returncode, 0, extract.stderr[-500:])
        count = sum(1 for p in tree.rglob("*") if p.is_file())
        self.assertGreater(count, 1000, "exported tree looks truncated")
        return tree

    def tracked_manifest(self):
        prov = json.loads(FROZEN_PROVENANCE.read_text())
        return [(e["patch"], e["sha256"]) for e in prov["floe"]["patches"]]

    def test_tracked_patches_apply_to_frozen_0_1_17_pin(self):
        self.require_clone()
        lock = json.loads(TRACKED_LOCK.read_text())
        commit, tree_hash = lock["upstream"]["commit"], lock["upstream"]["tree"]
        head = subprocess.run(["git", "-C", str(self.clone), "rev-parse", f"{commit}^{{tree}}"],
                              capture_output=True, text=True).stdout.strip()
        if head != tree_hash:
            self.skipTest(f"clone tree of the frozen pin differs ({head})")
        tree = self.export(commit)
        self.assertEqual((tree / "ENGINE_VERSION").read_text().strip(),
                         lock["upstream"]["engineVersion"])
        applied, out = run_apply(self.module, TRACKED_PATCH_DIR, tree)
        self.assertEqual(applied, [{"patch": n, "sha256": d} for n, d in self.tracked_manifest()],
                         "applied patch digests must match the frozen published manifest")
        self.assertEqual(artifacts(tree), [])
        self.assertNotIn("offset", out, "the frozen pin applies at its exact declared lines")

    def test_tracked_patches_apply_to_candidate_0_1_18_without_artifacts(self):
        self.require_clone()
        head = subprocess.run(["git", "-C", str(self.clone), "rev-parse", f"{CANDIDATE_COMMIT}^{{tree}}"],
                              capture_output=True, text=True).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            self.skipTest("clone does not carry the 0.1.18 candidate commit")
        self.assertEqual(head, CANDIDATE_TREE, "candidate tree drifted from run 40614187492")
        tree = self.export(CANDIDATE_COMMIT)
        self.assertEqual((tree / "ENGINE_VERSION").read_text().strip(), CANDIDATE_VERSION)
        applied, _ = run_apply(self.module, TRACKED_PATCH_DIR, tree)
        self.assertEqual(applied, [{"patch": n, "sha256": d} for n, d in self.tracked_manifest()])
        self.assertEqual(artifacts(tree), [],
                         "run 40614187492 regression: offset application must not fail the audit")
        snapshot = (tree / "crates/foundation/src/browser/snapshot.rs").read_text()
        driver = (tree / "crates/core/src/browser/driver.rs").read_text()
        # Offset hunks landed with the upstream 0.1.18 additions intact —
        # both sides of every offset region coexist in the patched file.
        self.assertIn("pub trait PassLimiter", snapshot)
        self.assertIn("pretty_wrap", snapshot)
        self.assertIn("cooperative_stop!", driver)
        self.assertIn("TextWrapRules::default()", driver)


if __name__ == "__main__":
    unittest.main(verbosity=2)
