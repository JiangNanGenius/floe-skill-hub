//! The embedded contract and the engine's own identity.
//!
//! These tests pin the property that matters most for the native side: the
//! binary carries the *committed* contract bytes, so a result document can
//! never describe a contract the hub does not track.

use std::path::PathBuf;
use std::process::Command;

fn engine() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_floe-impeccable"))
}

fn run(args: &[&str]) -> (i32, String, String) {
    let out = Command::new(engine()).args(args).output().expect("run the engine");
    (
        out.status.code().unwrap_or(-1),
        String::from_utf8_lossy(&out.stdout).to_string(),
        String::from_utf8_lossy(&out.stderr).to_string(),
    )
}

fn contract_json() -> serde_json::Value {
    let (code, stdout, _) = run(&["contract"]);
    assert_eq!(code, 0, "the contract verb must succeed");
    serde_json::from_str(&stdout).expect("the contract verb must print JSON")
}

#[test]
fn the_embedded_contract_is_the_committed_contract() {
    let (code, stdout, _) = run(&["contract"]);
    assert_eq!(code, 0);
    let committed = include_str!("../data/snapshot-contract.v1.json");
    // Byte equality, not semantic equality: a staged contract that differs from
    // the tracked one would silently desynchronise the native side.
    assert_eq!(stdout.trim_end(), committed.trim_end());
}

#[test]
fn the_contract_names_one_deliberate_pin() {
    let contract = contract_json();
    let commit = contract["engine"]["upstreamCommit"].as_str().unwrap();
    assert_eq!(commit.len(), 40, "the pin must be a full commit sha");
    assert_eq!(
        contract["provenance"]["upstreamCommit"].as_str().unwrap(),
        commit,
        "the engine block and the provenance block must name the same commit"
    );
    assert_eq!(contract["engine"]["upstreamEngineVersion"].as_str().unwrap(), "0.1.17");
    assert!(
        contract["engine"]["pinAuthority"].as_str().unwrap().contains("UPSTREAM-PINS.json"),
        "the pin authority must be the tracked hub review baseline"
    );
}

#[test]
fn the_schema_is_frozen_and_does_not_claim_engine_validation() {
    let contract = contract_json();
    assert_eq!(contract["schemaStatus"].as_str().unwrap(), "frozen-v1");
    assert_eq!(contract["engineValidation"]["status"].as_str().unwrap(), "pending");
    assert_eq!(
        contract["engineValidation"]["blocksNativeImplementation"].as_bool().unwrap(),
        false
    );
}

#[test]
fn the_property_columns_are_the_pinned_engine_columns() {
    let contract = contract_json();
    let style_props = contract["snapshot"]["styleProps"].as_array().unwrap();
    assert_eq!(style_props.len(), 138, "the pinned engine reads 138 computed-style columns");
    let pseudo = contract["snapshot"]["pseudoProps"].as_array().unwrap();
    assert_eq!(pseudo.len(), 23);
    let states = contract["snapshot"]["statePseudos"].as_array().unwrap();
    assert_eq!(states.len(), 31);

    let (code, stdout, _) = run(&["snapshot-schema"]);
    assert_eq!(code, 0);
    let schema: serde_json::Value = serde_json::from_str(&stdout).expect("schema JSON");
    assert_eq!(schema["styleProps"].as_array().unwrap().len(), 138);
    assert_eq!(schema["snapshotVersion"].as_u64().unwrap(), 1);
    assert!(schema["identitySchema"]["required"]
        .as_array()
        .unwrap()
        .iter()
        .any(|v| v.as_str() == Some("sessionId")));
}

#[test]
fn unimplemented_passes_are_uncovered_and_block_a_clean_verdict() {
    let contract = contract_json();
    let passes = contract["coveragePasses"].as_array().unwrap();
    assert_eq!(passes.len(), 18, "the coverage registry is part of the frozen contract");
    for pass in passes {
        let implemented = pass["implemented"].as_bool().unwrap();
        let states: Vec<String> = pass["states"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| s.as_str().unwrap().to_string())
            .collect();
        if !implemented {
            assert_eq!(states, vec!["uncovered".to_string()], "pass {}", pass["id"]);
            assert!(
                pass["reason"].as_str().map(|r| !r.is_empty()).unwrap_or(false),
                "an uncovered pass must say why: {}",
                pass["id"]
            );
        }
    }
    let blocking: Vec<&str> = passes
        .iter()
        .filter(|p| p["requiredForCleanVerdict"].as_bool().unwrap() && !p["implemented"].as_bool().unwrap())
        .map(|p| p["id"].as_str().unwrap())
        .collect();
    for expected in [
        "pixel-contrast",
        "reveal-sweep",
        "content-hidden-at-rest-measure",
        "script-errors",
        "cross-origin-iframe",
        "same-origin-iframe",
    ] {
        assert!(blocking.contains(&expected), "{expected} must block a clean verdict");
    }
}

#[test]
fn the_identity_contract_requires_the_native_binding_and_redaction() {
    let contract = contract_json();
    let required: Vec<&str> = contract["identity"]["requiredFields"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect();
    for field in [
        "taskId",
        "sessionId",
        "tabId",
        "documentId",
        "captureId",
        "documentGeneration",
        "viewport.width",
        "viewport.height",
        "scroll.x",
        "scroll.y",
        "producerTrust",
        "producer.scriptDigest",
        "redaction.policy",
        "redaction.applied",
    ] {
        assert!(required.contains(&field), "{field} must be a required identity field");
    }
    let privacy: Vec<&str> = contract["identity"]["privacy"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect();
    assert!(privacy.iter().any(|p| p.contains("no arbitrary")), "the privacy rules must forbid arbitrary JavaScript");
    assert!(privacy.iter().any(|p| p.contains("redacted")), "the privacy rules must require redaction");
    let fencing = contract["identity"]["fencing"].as_array().unwrap();
    assert!(fencing.len() >= 3, "navigation and view changes must fence the capture");
}

#[test]
fn the_probe_and_version_identify_the_floe_adapter() {
    // Pinned literal: an unintended version bump must fail here, and the
    // derived consistency test below must stay green (see Root review
    // 2026-10-27: the shipped contract once carried a stale 1.0.0 probe
    // example while the binary printed 1.1.0).
    let (code, stdout, _) = run(&["engine-probe"]);
    assert_eq!(code, 0);
    assert_eq!(stdout, "impeccable-engine 0.1.17+floe.1.1.1\n");

    let (code, stdout, _) = run(&["--version"]);
    assert_eq!(code, 0);
    assert_eq!(stdout, "0.1.17+floe.1.1.1\n");
}

#[test]
fn the_contract_engine_probe_example_is_the_live_probe() {
    // The contract's documented handshake and the binary's actual stdout are
    // one identity: both must be derived from the same component version
    // constant (the adapter crate version plus the contract's
    // engine.upstreamEngineVersion). No hand-copied literal may sit between
    // them: this test fails for any drift, including a stale example.
    let contract: serde_json::Value =
        serde_json::from_str(include_str!("../data/snapshot-contract.v1.json"))
            .expect("the embedded contract must be valid JSON");

    let (code, live_probe, _) = run(&["engine-probe"]);
    assert_eq!(code, 0);
    let (code, live_version, _) = run(&["--version"]);
    assert_eq!(code, 0);
    let live_version = live_version.trim_end_matches('\n');

    let example = contract["verbs"]
        .as_array()
        .expect("verbs array")
        .iter()
        .find(|v| v["name"].as_str() == Some("engine-probe"))
        .expect("the contract documents the engine-probe verb")["stdout"]
        .as_str()
        .expect("the engine-probe verb must document its stdout");
    assert_eq!(
        example, live_probe,
        "the contract's engine-probe example must equal the live probe bytes"
    );
    assert_eq!(
        live_probe,
        format!("impeccable-engine {live_version}\n"),
        "the launcher handshake format is exactly `impeccable-engine <componentVersion>\\n`"
    );

    let engine = &contract["engine"];
    assert_eq!(
        engine["engineId"].as_str().unwrap(),
        format!("impeccable-{live_version}"),
        "the contract engineId must equal the version the binary prints"
    );
    let adapter = live_version
        .split_once("+floe.")
        .expect("the component version is <engine>+floe.<adapter>")
        .1;
    assert_eq!(
        engine["floeAdapterVersion"].as_str().unwrap(),
        adapter,
        "the contract floeAdapterVersion must equal the adapter part of the live version"
    );
    assert_eq!(
        live_version,
        format!(
            "{}+floe.{}",
            engine["upstreamEngineVersion"].as_str().unwrap(),
            adapter
        ),
        "--version must be built from the contract's upstream engine version and the adapter version"
    );
}

#[test]
fn floe_owned_upstream_paths_are_refused_not_silently_present() {
    for (verb, expected) in [
        ("update", "Floe Skill Hub"),
        ("install", "Floe Skill Hub"),
        ("skills", "Floe Skill Hub"),
        ("telemetry", "Telemetry is disabled"),
        ("generate-image", "network service"),
        ("capture-server", "Chromium/CDP"),
        ("component-review", "Chromium/CDP"),
        ("live-server", "Live mode"),
        ("hook", "Editor hooks"),
    ] {
        let (code, stdout, stderr) = run(&[verb]);
        assert_eq!(code, 1, "{verb} must be refused");
        assert!(stdout.is_empty(), "{verb} must not print a normal result");
        assert!(
            stderr.contains(expected),
            "{verb} must name its Floe owner, got: {stderr}"
        );
        assert!(stderr.contains("verb-unavailable"), "{verb} must carry a stable code");
    }
}

#[test]
fn a_url_target_is_refused_without_chromium() {
    let (code, _stdout, stderr) = run(&["detect", "https://example.com/"]);
    assert_ne!(code, 0, "a URL scan must not report success");
    assert!(
        stderr.contains("URL scanning is not available in the Floe engine")
            || stderr.contains("No Chromium is installed"),
        "the refusal must explain the native capture path, got: {stderr}"
    );
}

#[test]
fn unknown_verbs_and_usage_errors_keep_a_stable_shape() {
    let (code, _, stderr) = run(&["definitely-not-a-verb"]);
    assert_eq!(code, 1);
    assert!(stderr.contains("Unknown command"));

    let (code, _, stderr) = run(&["snapshot-scan"]);
    assert_eq!(code, 1);
    assert!(stderr.contains("requires --snapshot"), "{stderr}");

    let (code, stdout, _) = run(&["--help"]);
    assert_eq!(code, 0);
    assert!(stdout.contains("snapshot-scan") && stdout.contains("detect"));
    assert!(
        !stdout.contains("  install ") && !stdout.contains("  update "),
        "the Floe usage must not advertise verbs this engine refuses"
    );
}
