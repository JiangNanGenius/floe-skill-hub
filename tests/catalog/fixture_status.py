#!/usr/bin/env python3
"""Shared staging helper for isolated publication fixtures.

Since the 2026-10-28 reviewed admission baseline the REAL catalog/skills.json
carries packaged+reviewed for all 43 rows and qualified for all 43 (11 of them
executionVerified from real guest receipts). Temp-tree publication and
signing-bridge fixtures derive from that file but deliberately stage only
their own small qualified synthetic set; every other row in such a fixture
tree must therefore be explicitly demoted to the unadmitted candidate state
(the tree has no archives or signed reviews for them, and the release builder
correctly refuses qualified rows without bindings). This helper constructs
that fixture state in memory — the repository registry file is never touched,
and no validator or gate is weakened: it makes the fixtures say exactly what
they mean.
"""
import copy


def stage_unadmitted_fixture(registry):
    reg = copy.deepcopy(registry)
    for entry in reg["skills"]:
        entry["status"] = dict(entry["status"], packaged=False, reviewed=False,
                               qualified=False, published=False,
                               executionVerified=False)
        planned = entry["plannedRuntime"]
        if planned["scriptRuntime"] != "none":
            entry["plannedRuntime"] = dict(
                planned, execution=dict(planned["execution"], evidence="unproven"))
    return reg
