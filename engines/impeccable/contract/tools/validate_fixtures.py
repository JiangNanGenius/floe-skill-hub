#!/usr/bin/env python3
"""Coherence gate for the v1 snapshot/facts contract artifacts.

Checks that the generated schema, the property columns, the fixtures and the
contract document agree with each other and with the pinned upstream source,
and that every "invalid" fixture is invalid for the reason it claims.

  validate_fixtures.py --contract <contract-dir> --upstream <pinned-source-dir>

Exit 0 when every check passes; exit 1 with a JSON report otherwise. The
report is deterministic, so it can be filed as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    print(json.dumps({"error": "python jsonschema is required"}, indent=2))
    raise SystemExit(1)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rust_list(text: str, name: str) -> list[str]:
    m = re.search(r"pub\s+const\s+" + re.escape(name) + r"\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];", text, re.DOTALL)
    if not m:
        raise SystemExit(f"missing Rust const {name}")
    return re.findall(r'"((?:[^"\\]|\\.)*)"', re.sub(r"//[^\n]*", "", m.group(1)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--upstream", required=True, type=Path)
    args = ap.parse_args()

    c = args.contract
    checks: list[dict] = []
    failures: list[str] = []

    def check(name: str, ok: bool, detail: object = None) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    contract = load(c / "snapshot-contract.v1.json")
    style_props = load(c / "producer/style-props.v1.json")["styleProps"]
    pseudo_props = load(c / "producer/pseudo-props.v1.json")["pseudoProps"]
    state_pseudos = load(c / "producer/state-pseudos.v1.json")["statePseudos"]
    limits = load(c / "producer/capture-limits.v1.json")
    snap_schema = load(c / "producer/snapshot.schema.v1.json")
    facts_schema = load(c / "producer/facts.schema.v1.json")
    identity_schema = load(c / "producer/identity.schema.v1.json")
    result_schema = load(c / "producer/result.schema.v1.json")

    # 1. the pinned source is still the source of truth for the columns
    rust = (args.upstream / "crates/foundation/src/browser/snapshot.rs").read_text(encoding="utf-8")
    check("styleProps match pinned Rust STYLE_PROPS", rust_list(rust, "STYLE_PROPS") == style_props,
          {"count": len(style_props)})
    check("pseudoProps match pinned Rust PSEUDO_PROPS", rust_list(rust, "PSEUDO_PROPS") == pseudo_props,
          {"count": len(pseudo_props)})
    check("engineVersion matches pinned ENGINE_VERSION",
          (args.upstream / "ENGINE_VERSION").read_text(encoding="utf-8").strip()
          == contract["engine"]["upstreamEngineVersion"],
          contract["engine"]["upstreamEngineVersion"])

    # 2. contract/schema internal agreement
    check("contract styleProps equal producer styleProps", contract["snapshot"]["styleProps"] == style_props)
    check("schema styleProps minItems equals column count",
          snap_schema["properties"]["styleProps"]["minItems"] == len(style_props))
    check("schema element style column is exactly one index per prop",
          snap_schema["properties"]["els"]["items"]["properties"]["s"]["minItems"] == len(style_props)
          and snap_schema["properties"]["els"]["items"]["properties"]["s"]["maxItems"] == len(style_props))
    check("schema state enum covers every state pseudo",
          set(snap_schema["properties"]["els"]["items"]["properties"]["st"]["items"]["enum"])
          == set(state_pseudos) | {"undefined"})
    check("budgets agree between contract and capture limits",
          contract["budgets"]["maxSnapshotBytes"] == limits["floeBudgets"]["maxSnapshotBytes"]
          and contract["budgets"]["maxRounds"] == limits["floeBudgets"]["maxRounds"]
          and contract["budgets"]["maxHitTestsTotal"] == limits["floeBudgets"]["maxHitTestsTotal"])
    check("upstream caps recorded", limits["upstreamDefaults"] == {"maxElements": 30000, "maxBytes": 50331648},
          limits["upstreamDefaults"])
    check("every coverage pass has an id, states and a clean-verdict flag",
          all(p.get("id") and p.get("states") and isinstance(p.get("requiredForCleanVerdict"), bool)
              for p in contract["coveragePasses"]),
          {"passes": len(contract["coveragePasses"])})
    unimplemented_required = [p["id"] for p in contract["coveragePasses"]
                              if p["requiredForCleanVerdict"] and not p["implemented"]]
    check("unimplemented passes that block a clean verdict are recorded",
          len(unimplemented_required) >= 5, unimplemented_required)
    check("no unimplemented pass claims a covered state",
          all("covered" not in p["states"] for p in contract["coveragePasses"] if not p["implemented"]))

    # 3. positive/needs fixtures validate and carry full style columns
    validator = jsonschema.Draft202012Validator(snap_schema)
    facts_validator = jsonschema.Draft202012Validator(facts_schema)
    identity_validator = jsonschema.Draft202012Validator(identity_schema)
    result_validator = jsonschema.Draft202012Validator(result_schema)

    for name in ("snapshot-positive.v1.json", "snapshot-needs-hit-tests.v1.json"):
        doc = load(c / "fixtures" / name)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        check(f"{name} validates against snapshot.schema.v1", not errs,
              [{"path": list(map(str, e.path)), "message": e.message[:160]} for e in errs[:5]])
        check(f"{name} carries one style index per column",
              all(len(el.get("s", [])) == len(style_props) for el in doc["els"]),
              {"elements": len(doc["els"])})
        check(f"{name} styleProps column list is the contract list", doc["styleProps"] == style_props)
        check(f"{name} pseudoProps column list is the contract list", doc["pseudoProps"] == pseudo_props)
        check(f"{name} declares snapshot version 1", doc.get("v") == 1)
        ids = {i + 1 for i in range(len(doc["els"]))}
        check(f"{name} parent/child ids resolve inside the element table",
              doc["documentElement"] in ids and (doc["body"] in ids if doc["body"] else True)
              and all((el.get("p") in ids) for el in doc["els"] if el.get("p")),
              {"documentElement": doc["documentElement"], "body": doc["body"]})
        check(f"{name} child lists reference known ids or text",
              all((isinstance(ch, int) and ch in ids) or isinstance(ch, (str, list))
                  for el in doc["els"] for ch in el.get("c", [])))

    for name in ("identity-positive.v1.json", "identity-needs.v1.json"):
        doc = load(c / "fixtures" / name)
        errs = sorted(identity_validator.iter_errors(doc), key=lambda e: list(e.path))
        check(f"{name} validates against identity.schema.v1", not errs,
              [{"path": list(map(str, e.path)), "message": e.message[:160]} for e in errs[:5]])
        required_binding = ["taskId", "sessionId", "tabId", "documentId", "captureId", "documentGeneration"]
        check(f"{name} carries the full native binding",
              all(doc.get(k) not in (None, "") for k in required_binding),
              {k: doc.get(k) for k in required_binding})
        check(f"{name} binds the viewport and scroll",
              isinstance(doc.get("viewport"), dict) and "width" in doc["viewport"] and "height" in doc["viewport"]
              and isinstance(doc.get("scroll"), dict) and "x" in doc["scroll"] and "y" in doc["scroll"])
        check(f"{name} claims only the fixed native producer",
              doc.get("producerTrust") == "native-fixed-script"
              and doc.get("producer", {}).get("engine") == "WebKit"
              and bool(doc.get("producer", {}).get("scriptDigest")))
        check(f"{name} records an applied redaction policy",
              doc.get("redaction", {}).get("applied") is True
              and doc.get("redaction", {}).get("policy") == "floe.impeccable.redaction.v1",
              doc.get("redaction"))

    binding_keys = ["taskId", "sessionId", "tabId", "documentId", "captureId"]
    needs_identity = load(c / "fixtures/identity-needs.v1.json")
    for name in ("facts-hit-tests.v1.json", "facts-shown-on-scroll.v1.json"):
        doc = load(c / "fixtures" / name)
        errs = sorted(facts_validator.iter_errors(doc), key=lambda e: list(e.path))
        check(f"{name} validates against facts.schema.v1", not errs,
              [{"path": list(map(str, e.path)), "message": e.message[:160]} for e in errs[:5]])
        check(f"{name} is bound to the identity the needs were issued for",
              all(doc.get(k) == needs_identity.get(k) for k in binding_keys),
              {k: doc.get(k) for k in binding_keys})

    # 4. identity binding really binds the fixture snapshots
    pos = load(c / "fixtures/snapshot-positive.v1.json")
    idpos = load(c / "fixtures/identity-positive.v1.json")
    check("positive identity binds hostname and viewport to the snapshot",
          idpos["hostname"] == pos["hostname"]
          and idpos["viewport"] == {"width": pos["innerWidth"], "height": pos["innerHeight"]}
          and idpos["scroll"] == {"x": pos["scrollX"], "y": pos["scrollY"]})

    # 5. every invalid fixture fails for its declared reason
    invalid = c / "fixtures/invalid"
    truncated = invalid / "snapshot-truncated.v1.json"
    try:
        json.loads(truncated.read_text(encoding="utf-8"))
        check("truncated snapshot is not parseable JSON", False)
    except json.JSONDecodeError as exc:
        check("truncated snapshot is not parseable JSON", True, str(exc)[:120])

    bad_version = load(invalid / "snapshot-bad-version.v1.json")
    errs = list(validator.iter_errors(bad_version))
    check("unsupported snapshot version is rejected by the schema",
          any(e.schema.get("const") == 1 for e in errs), {"v": bad_version.get("v")})

    mismatch = load(invalid / "snapshot-style-column-mismatch.v1.json")
    errs = list(validator.iter_errors(mismatch))
    check("shortened styleProps column list is rejected by the schema", bool(errs),
          [e.message[:120] for e in errs[:2]])

    bad_identity = load(invalid / "identity-mismatch.v1.json")
    check("mismatched identity really differs from the snapshot binding",
          bad_identity["hostname"] != pos["hostname"]
          or bad_identity["viewport"] != {"width": pos["innerWidth"], "height": pos["innerHeight"]})

    stale = load(invalid / "facts-stale-capture.v1.json")
    check("stale facts carry a different captureId than the needs identity",
          stale["captureId"] != needs_identity["captureId"])

    for name, dropped in (("identity-missing-session-binding.v1.json", ["sessionId", "tabId"]),):
        doc = load(invalid / name)
        errs = list(identity_validator.iter_errors(doc))
        required_errors = [e.message[:120] for e in errs if e.validator == "required"]
        check(f"{name} is rejected for the missing binding fields", bool(required_errors),
              {"dropped": dropped, "requiredErrors": required_errors})
        check(f"{name} really omits {dropped}", all(k not in doc for k in dropped))

    no_redaction = load(invalid / "identity-redaction-not-applied.v1.json")
    errs = list(identity_validator.iter_errors(no_redaction))
    check("identity without an applied redaction policy is rejected by the schema", bool(errs),
          [e.message[:100] for e in errs[:2]])

    model_trust = load(invalid / "identity-model-declared-trust.v1.json")
    errs = list(identity_validator.iter_errors(model_trust))
    check("model-declared producer trust is rejected by the schema",
          any(e.validator == "const" for e in errs), model_trust.get("producerTrust"))

    fenced = load(invalid / "identity-fenced.v1.json")
    check("a fenced capture identity is marked fenced", fenced.get("fenced") is True)

    other_tab = load(invalid / "facts-other-tab.v1.json")
    check("facts from another tab/session do not match the needs identity",
          other_tab["tabId"] != needs_identity["tabId"] or other_tab["sessionId"] != needs_identity["sessionId"])

    bits_doc = load(invalid / "facts-bits-mismatch.v1.json")
    errs = list(facts_validator.iter_errors(bits_doc))
    check("bits-mismatch facts still validate structurally (the adapter must catch the bit drift)",
          not errs, "structural validation cannot catch a wrong xBits; the engine check is the gate")

    # 6. result schema sanity
    check("result schema requires status, verdict and coverage",
          set(result_schema["required"]) >= {"status", "verdict", "coverage"})
    check("result schema forbids a clean verdict outside the documented enum",
          result_schema["properties"]["verdict"]["enum"] == ["clean", "findings", "inconclusive", "none"])

    # 7. contract status and the single deliberate pin
    check("schema is frozen for native implementation",
          contract.get("schemaStatus") == "frozen-v1"
          and contract.get("engineValidation", {}).get("status") == "pending"
          and contract.get("engineValidation", {}).get("blocksNativeImplementation") is False)
    hex40 = re.compile(r"^[0-9a-f]{40}$")
    check("one deliberate upstream pin, no mixed bytes",
          bool(hex40.match(str(contract["engine"]["upstreamCommit"])))
          and bool(hex40.match(str(contract["provenance"]["upstreamCommit"])))
          and contract["engine"]["upstreamCommit"] == contract["provenance"]["upstreamCommit"]
          and bool(hex40.match(str(contract["provenance"]["upstreamTree"]))),
          {"commit": contract["engine"]["upstreamCommit"], "tree": contract["provenance"]["upstreamTree"]})
    check("pin authority is the tracked hub review baseline",
          "UPSTREAM-PINS.json" in contract["engine"].get("pinAuthority", ""),
          contract["engine"].get("pinAuthority"))
    check("identity contract requires the native binding and fencing fields",
          {"taskId", "sessionId", "tabId", "documentId", "captureId", "documentGeneration",
           "viewport.width", "viewport.height", "scroll.x", "scroll.y",
           "producerTrust", "producer.scriptDigest", "redaction.policy", "redaction.applied"}
          <= set(contract["identity"]["requiredFields"]))
    check("identity contract states the privacy obligations",
          len(contract["identity"].get("privacy", [])) >= 4 and len(contract["identity"].get("fencing", [])) >= 3)
    check("excluded upstream paths are recorded with an owner",
          all(p.get("owner") and p.get("reason") for p in contract["excludedUpstreamPaths"]),
          [p["path"] for p in contract["excludedUpstreamPaths"]])

    digests = {
        "snapshot-contract.v1.json": sha256(c / "snapshot-contract.v1.json"),
        "producer/snapshot.schema.v1.json": sha256(c / "producer/snapshot.schema.v1.json"),
        "producer/facts.schema.v1.json": sha256(c / "producer/facts.schema.v1.json"),
        "producer/identity.schema.v1.json": sha256(c / "producer/identity.schema.v1.json"),
        "producer/result.schema.v1.json": sha256(c / "producer/result.schema.v1.json"),
        "producer/style-props.v1.json": sha256(c / "producer/style-props.v1.json"),
        "producer/pseudo-props.v1.json": sha256(c / "producer/pseudo-props.v1.json"),
        "producer/state-pseudos.v1.json": sha256(c / "producer/state-pseudos.v1.json"),
        "producer/capture-limits.v1.json": sha256(c / "producer/capture-limits.v1.json"),
        "fixtures/snapshot-positive.v1.json": sha256(c / "fixtures/snapshot-positive.v1.json"),
        "fixtures/snapshot-needs-hit-tests.v1.json": sha256(c / "fixtures/snapshot-needs-hit-tests.v1.json"),
        "fixtures/config-default.v1.json": sha256(c / "fixtures/config-default.v1.json"),
        "fixtures/identity-positive.v1.json": sha256(c / "fixtures/identity-positive.v1.json"),
        "fixtures/identity-needs.v1.json": sha256(c / "fixtures/identity-needs.v1.json"),
        "fixtures/facts-hit-tests.v1.json": sha256(c / "fixtures/facts-hit-tests.v1.json"),
        "fixtures/facts-shown-on-scroll.v1.json": sha256(c / "fixtures/facts-shown-on-scroll.v1.json"),
    }
    for p in sorted((invalid).glob("*.json")):
        digests[f"fixtures/invalid/{p.name}"] = sha256(p)

    report = {
        "contractDir": str(c),
        "upstream": str(args.upstream),
        "upstreamCommit": contract["provenance"]["upstreamCommit"],
        "upstreamTree": contract["provenance"]["upstreamTree"],
        "engineVersion": contract["engine"]["upstreamEngineVersion"],
        "adapterVersion": contract["engine"]["floeAdapterVersion"],
        "contractVersion": contract["contractVersion"],
        "checksTotal": len(checks),
        "checksPassed": sum(1 for x in checks if x["ok"]),
        "failures": failures,
        "unimplementedRequiredPasses": unimplemented_required,
        "digests": digests,
        "checks": checks,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
