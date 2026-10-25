//! `snapshot-scan` fail-closed behaviour.
//!
//! The rule this suite exists to protect: **a missing measurement is never a
//! clean scan**. Every refusal names a stable error code, every incomplete run
//! keeps its Needs, and an empty finding list stays `inconclusive` while a
//! required coverage pass is uncovered.
//!
//! Test data: the frozen contract fixtures (`data/fixtures/`) plus adapter-only
//! snapshots in `tests/data/` (see `tests/data/README.md` for how the derived
//! facts files were produced and how to regenerate them).

use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::{json, Value};

fn engine() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_floe-impeccable"))
}

fn fixtures() -> PathBuf {
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/data/fixtures"))
}

fn invalid_fixtures() -> PathBuf {
    fixtures().join("invalid")
}

fn test_data() -> PathBuf {
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data"))
}

/// Test output goes inside the cargo target directory (an internal-SSD build
/// cache) rather than a sibling directory, and is unique per test.
fn out_path(name: &str) -> PathBuf {
    let base = std::env::var("CARGO_TARGET_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| std::env::temp_dir());
    let dir = base.join("floe-impeccable-test-out").join(format!("{name}-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("create the test output directory");
    dir.join(format!("{name}.json"))
}

struct Scan {
    code: i32,
    doc: Value,
    stderr: String,
}

fn scan(args: &[&str], out: &Path) -> Scan {
    let mut full: Vec<&str> = vec!["snapshot-scan"];
    full.extend_from_slice(args);
    full.extend_from_slice(&["--out"]);
    let out_str = out.to_str().expect("utf-8 out path").to_string();
    full.push(&out_str);
    let result = Command::new(engine()).args(&full).output().expect("run snapshot-scan");
    let stderr = String::from_utf8_lossy(&result.stderr).to_string();
    let raw = std::fs::read_to_string(out).unwrap_or_else(|e| panic!("no result document at {}: {e}", out.display()));
    Scan {
        code: result.status.code().unwrap_or(-1),
        doc: serde_json::from_str(&raw).expect("the result document must be JSON"),
        stderr,
    }
}

fn pass<'a>(doc: &'a Value, id: &str) -> &'a Value {
    doc["coverage"]["passes"]
        .as_array()
        .unwrap()
        .iter()
        .find(|p| p["id"].as_str() == Some(id))
        .unwrap_or_else(|| panic!("coverage pass {id} is missing from the receipt"))
}

// --------------------------------------------------------------------------
// the fixpoint
// --------------------------------------------------------------------------

#[test]
fn missing_facts_come_back_as_needs_and_never_as_a_clean_scan() {
    let out = out_path("missing-facts");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.code, 3, "needs-facts has its own exit code");
    assert_eq!(result.doc["status"], json!("needs-facts"));
    assert_eq!(result.doc["verdict"], json!("none"));
    assert!(result.doc["findings"].is_null(), "an incomplete run reports no findings");
    let needs = &result.doc["needs"];
    let points = needs["hitTests"].as_array().unwrap();
    assert!(!points.is_empty(), "the rules asked for hit tests");
    assert_eq!(
        needs["hitTestsBits"].as_array().unwrap().len(),
        points.len(),
        "every point carries its exact double bits"
    );
    assert_eq!(pass(&result.doc, "hit-test-fixpoint")["state"], json!("needs-facts"));
    assert_eq!(pass(&result.doc, "core-rule-pass")["state"], json!("needs-facts"));
    // stderr carries one summary line a caller can log; it must not carry page
    // content, attribute values or the finding text.
    assert!(
        result.stderr.contains("status=needs-facts") && result.stderr.contains("exit=3"),
        "stderr must summarise the run: {}",
        result.stderr
    );
    assert!(
        !result.stderr.contains("Body copy"),
        "stderr must not leak snapshot text: {}",
        result.stderr
    );
}

#[test]
fn answered_facts_complete_the_run_and_report_the_real_finding() {
    let out = out_path("answered-positive");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
            "--facts", test_data().join("facts-positive-round2.v1.json").to_str().unwrap(),
            "--round", "2",
        ],
        &out,
    );
    assert_eq!(result.code, 2, "a completed run with findings exits 2");
    assert_eq!(result.doc["status"], json!("complete"));
    assert_eq!(result.doc["verdict"], json!("findings"));
    let counts = &result.doc["findings"]["counts"];
    assert!(counts["total"].as_u64().unwrap() >= 1, "the tiny-text body copy must be reported");
    assert_eq!(counts["byRule"]["tiny-text"].as_u64().unwrap(), 1);
    assert!(result.doc["needs"].is_null(), "a completed run has nothing pending");
    assert_eq!(pass(&result.doc, "hit-test-fixpoint")["state"], json!("covered"));
    assert_eq!(pass(&result.doc, "style-parity")["state"], json!("complete"));
}

#[test]
fn the_overlay_page_reports_occlusion_only_because_the_hit_tests_were_answered() {
    let unanswered = out_path("overlay-unanswered");
    let first = scan(
        &[
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
        ],
        &unanswered,
    );
    assert_eq!(first.code, 3);
    assert!(
        first.doc["findings"].is_null(),
        "without the hit tests the occlusion rule cannot decide anything"
    );

    let answered = out_path("overlay-answered");
    let second = scan(
        &[
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
            "--facts", test_data().join("facts-overlay-round2.v1.json").to_str().unwrap(),
            "--round", "2",
        ],
        &answered,
    );
    assert_eq!(second.code, 2);
    assert_eq!(second.doc["findings"]["counts"]["byRule"]["text-occlusion"].as_u64().unwrap(), 1);
}

#[test]
fn an_empty_finding_list_is_inconclusive_while_required_passes_are_uncovered() {
    let out = out_path("no-findings");
    let result = scan(
        &[
            "--snapshot", test_data().join("snapshot-no-findings.v1.json").to_str().unwrap(),
            "--identity", test_data().join("identity-no-findings.v1.json").to_str().unwrap(),
            "--facts", test_data().join("facts-no-findings-round2.v1.json").to_str().unwrap(),
            "--round", "2",
        ],
        &out,
    );
    assert_eq!(result.code, 4, "inconclusive coverage has its own exit code");
    assert_eq!(result.doc["status"], json!("inconclusive"));
    assert_eq!(result.doc["verdict"], json!("inconclusive"));
    assert_eq!(result.doc["findings"]["counts"]["total"].as_u64().unwrap(), 0);
    let uncovered = result.doc["coverage"]["uncoveredRequired"].as_array().unwrap();
    assert!(!uncovered.is_empty(), "the receipt must name what was not measured");
    let ids: Vec<&str> = uncovered.iter().map(|v| v.as_str().unwrap()).collect();
    for expected in ["pixel-contrast", "reveal-sweep", "cross-origin-iframe", "same-origin-iframe", "script-errors"] {
        assert!(ids.contains(&expected), "{expected} must be listed as uncovered");
    }
    assert_eq!(result.doc["coverage"]["cleanCapable"], json!(false));
}

#[test]
fn points_the_producer_cannot_answer_are_terminal_and_never_clean() {
    // Answer every requested point as unanswerable, exactly as a native side
    // must when the document moved or the point is outside the viewport.
    let first_out = out_path("unanswerable-round1");
    let first = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
        ],
        &first_out,
    );
    assert_eq!(first.code, 3);
    let identity: Value =
        serde_json::from_str(&std::fs::read_to_string(fixtures().join("identity-positive.v1.json")).unwrap()).unwrap();
    let hits: Vec<Value> = first.doc["needs"]["hitTests"]
        .as_array()
        .unwrap()
        .iter()
        .zip(first.doc["needs"]["hitTestsBits"].as_array().unwrap())
        .map(|(point, bits)| {
            json!({
                "x": point[0], "y": point[1],
                "xBits": bits[0], "yBits": bits[1],
                "unanswerable": true,
                "reason": "the document was fenced before the point could be answered",
            })
        })
        .collect();
    let facts = json!({
        "taskId": identity["taskId"], "sessionId": identity["sessionId"], "tabId": identity["tabId"],
        "documentId": identity["documentId"], "captureId": identity["captureId"],
        "documentGeneration": identity["documentGeneration"],
        "hits": hits, "shownOnScroll": [],
    });
    let facts_path = out_path("unanswerable-facts");
    std::fs::write(&facts_path, serde_json::to_string(&facts).unwrap()).unwrap();

    let out = out_path("unanswerable-round2");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
            "--facts", facts_path.to_str().unwrap(),
            "--round", "2",
        ],
        &out,
    );
    assert_eq!(result.code, 4, "an unanswered run is inconclusive, not clean and not needs-facts");
    assert_eq!(result.doc["status"], json!("inconclusive"));
    assert_eq!(result.doc["verdict"], json!("inconclusive"));
    assert_eq!(pass(&result.doc, "hit-test-fixpoint")["state"], json!("unanswered"));
    assert!(
        result.doc["diagnostics"]["unanswerablePending"].as_u64().unwrap() > 0,
        "the receipt must count the points nobody answered"
    );
    assert!(
        result.doc["diagnostics"]["unanswerablePoints"].as_array().unwrap().iter()
            .all(|p| p["reason"].as_str().unwrap_or("").contains("fenced")),
        "each unanswerable point keeps the producer's reason"
    );
}

// --------------------------------------------------------------------------
// snapshot gates
// --------------------------------------------------------------------------

#[test]
fn a_truncated_snapshot_is_a_parse_failure() {
    let out = out_path("truncated");
    let result = scan(
        &[
            "--snapshot", invalid_fixtures().join("snapshot-truncated.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["status"], json!("failed"));
    assert_eq!(result.doc["verdict"], json!("none"));
    assert_eq!(result.doc["error"]["code"], json!("snapshot-parse"));
    assert!(result.doc["findings"].is_null());
}

#[test]
fn an_unsupported_snapshot_version_is_refused() {
    let out = out_path("bad-version");
    let result = scan(
        &[
            "--snapshot", invalid_fixtures().join("snapshot-bad-version.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("snapshot-version-unsupported"));
    assert_eq!(result.doc["error"]["detail"]["snapshotVersion"], json!(99));
}

#[test]
fn a_shortened_style_column_list_is_a_schema_mismatch() {
    let out = out_path("column-mismatch");
    let result = scan(
        &[
            "--snapshot", invalid_fixtures().join("snapshot-style-column-mismatch.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("schema-mismatch"));
    assert_eq!(result.doc["error"]["detail"]["engineColumns"], json!(138));
}

#[test]
fn a_capture_that_recorded_no_style_columns_reports_partial_parity_not_a_pass() {
    // Drop every recorded style column and relax the schema gate: the rules
    // still run, but the receipt must say the measurement was not there.
    let source: Value = serde_json::from_str(
        &std::fs::read_to_string(fixtures().join("snapshot-positive.v1.json")).unwrap(),
    )
    .unwrap();
    let mut stripped = source.clone();
    stripped["styleProps"] = json!([]);
    for el in stripped["els"].as_array_mut().unwrap() {
        el["s"] = json!([]);
    }
    let snapshot_path = out_path("no-style-columns-snapshot");
    std::fs::write(&snapshot_path, serde_json::to_string(&stripped).unwrap()).unwrap();

    let out = out_path("no-style-columns");
    let result = scan(
        &[
            "--snapshot", snapshot_path.to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
            "--no-strict-schema",
        ],
        &out,
    );
    assert_ne!(result.doc["verdict"], json!("clean"));
    let parity = pass(&result.doc, "style-parity");
    assert_eq!(parity["state"], json!("partial"));
    let unknown = result.doc["coverage"]["unknownStyleProps"].as_array().unwrap();
    assert!(!unknown.is_empty(), "the engine must name the properties the capture did not record");
    assert_eq!(result.doc["diagnostics"]["strictSchema"], json!(false));
}

// --------------------------------------------------------------------------
// identity, binding and privacy gates
// --------------------------------------------------------------------------

fn identity_case(name: &str, fixture: &str, expected_code: &str, expected_state: &str) {
    let out = out_path(name);
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--identity", invalid_fixtures().join(fixture).to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.code, 1, "{name} must be refused");
    assert_eq!(result.doc["status"], json!("failed"), "{name}");
    assert_eq!(result.doc["error"]["code"], json!(expected_code), "{name}");
    assert_eq!(result.doc["identityCheck"]["state"], json!(expected_state), "{name}");
    assert!(result.doc["findings"].is_null(), "{name} must not return findings");
}

#[test]
fn an_identity_that_binds_another_viewport_is_refused() {
    identity_case("identity-mismatch", "identity-mismatch.v1.json", "identity-mismatch", "mismatch");
}

#[test]
fn an_identity_without_the_session_binding_is_refused() {
    identity_case(
        "identity-missing-binding",
        "identity-missing-session-binding.v1.json",
        "identity-invalid",
        "absent",
    );
}

#[test]
fn a_capture_without_an_applied_redaction_policy_is_refused() {
    identity_case(
        "identity-redaction",
        "identity-redaction-not-applied.v1.json",
        "identity-redaction-not-applied",
        "absent",
    );
}

#[test]
fn model_declared_producer_trust_is_refused() {
    identity_case(
        "identity-model-trust",
        "identity-model-declared-trust.v1.json",
        "identity-untrusted-producer",
        "absent",
    );
}

#[test]
fn a_fenced_capture_is_superseded() {
    identity_case("identity-fenced", "identity-fenced.v1.json", "identity-superseded", "superseded");
}

#[test]
fn a_scan_without_an_identity_is_refused_unless_it_is_declared_isolated() {
    let out = out_path("no-identity");
    let result = scan(
        &["--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap()],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("identity-invalid"));

    let isolated = out_path("isolated-identity");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--allow-missing-identity",
        ],
        &isolated,
    );
    assert_eq!(result.code, 3, "an isolated fixture still runs and still asks for facts");
    assert_eq!(result.doc["identityCheck"]["state"], json!("absent"));
    assert_ne!(result.doc["verdict"], json!("clean"));
}

#[test]
fn a_synthetic_producer_digest_is_surfaced_not_silently_trusted() {
    let out = out_path("synthetic-digest");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.doc["identityCheck"]["syntheticProducerDigest"], json!(true));
}

// --------------------------------------------------------------------------
// facts gates
// --------------------------------------------------------------------------

fn facts_case(name: &str, fixture: &str, expected_code: &str) {
    let out = out_path(name);
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
            "--facts", invalid_fixtures().join(fixture).to_str().unwrap(),
        ],
        &out,
    );
    assert_eq!(result.code, 1, "{name} must be refused");
    assert_eq!(result.doc["error"]["code"], json!(expected_code), "{name}: {}", result.doc["error"]["message"]);
    assert!(result.doc["findings"].is_null(), "{name} must not return findings");
}

#[test]
fn facts_whose_point_bits_drifted_are_refused() {
    facts_case("facts-bits", "facts-bits-mismatch.v1.json", "facts-bits-mismatch");
}

#[test]
fn facts_from_a_superseded_capture_are_refused() {
    facts_case("facts-stale", "facts-stale-capture.v1.json", "facts-binding-mismatch");
}

#[test]
fn facts_from_another_tab_or_session_are_refused() {
    facts_case("facts-other-tab", "facts-other-tab.v1.json", "facts-binding-mismatch");
}

#[test]
fn facts_without_a_verified_identity_are_refused() {
    let out = out_path("facts-no-identity");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--facts", test_data().join("facts-overlay-round2.v1.json").to_str().unwrap(),
            "--allow-missing-identity",
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("facts-binding-mismatch"));
}

// --------------------------------------------------------------------------
// budgets, timeout and determinism
// --------------------------------------------------------------------------

#[test]
fn an_oversized_snapshot_exceeds_the_budget() {
    let out = out_path("budget-bytes");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
            "--max-snapshot-bytes", "4096",
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("budget-exceeded"));
    assert_eq!(result.doc["error"]["detail"]["maxSnapshotBytes"], json!(4096));
}

#[test]
fn a_round_beyond_the_budget_is_refused_before_any_rule_runs() {
    let out = out_path("budget-rounds");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
            "--round", "9",
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("budget-exceeded"));
    assert_eq!(result.doc["error"]["detail"]["maxRounds"], json!(4));
}

#[test]
fn an_exhausted_deadline_is_reported_as_a_timeout() {
    let out = out_path("timeout");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
            "--timeout-ms", "0",
        ],
        &out,
    );
    assert_eq!(result.code, 1);
    assert_eq!(result.doc["error"]["code"], json!("timeout"));
    assert_eq!(result.doc["status"], json!("failed"));
}

#[test]
fn the_same_inputs_produce_the_same_result_document() {
    let snapshot = fixtures().join("snapshot-positive.v1.json");
    let identity = fixtures().join("identity-positive.v1.json");
    let facts = test_data().join("facts-positive-round2.v1.json");
    let args = |out: &Path| -> Vec<String> {
        vec![
            "--snapshot".into(), snapshot.to_str().unwrap().into(),
            "--identity".into(), identity.to_str().unwrap().into(),
            "--facts".into(), facts.to_str().unwrap().into(),
            "--round".into(), "2".into(),
            "--out".into(), out.to_str().unwrap().into(),
        ]
    };
    let first_out = out_path("determinism-a");
    let second_out = out_path("determinism-b");
    let run_with = |out: &Path| {
        let argv: Vec<String> = args(out);
        Command::new(engine())
            .arg("snapshot-scan")
            .args(&argv)
            .output()
            .expect("run snapshot-scan")
    };
    let first_run = run_with(&first_out);
    let second_run = run_with(&second_out);
    assert_eq!(first_run.status.code(), second_run.status.code());
    assert_eq!(first_run.status.code(), Some(2));

    let load = |path: &Path| -> Value {
        serde_json::from_str(&std::fs::read_to_string(path).unwrap()).expect("result JSON")
    };
    let strip = |mut doc: Value| -> Value {
        // Wall clock and absolute paths are the only legitimate differences.
        doc["budget"]["elapsedMs"] = json!(0);
        doc["diagnostics"]["factsFiles"] = json!([]);
        doc
    };
    assert_eq!(strip(load(&first_out)), strip(load(&second_out)));
}

#[test]
fn a_cancelled_run_never_leaves_a_clean_result_behind() {
    // Real signal, real process: the guest job lifecycle cancels with SIGTERM.
    // Either the handler lands and the engine writes an explicit failure, or the
    // run finished first; in neither case may a clean verdict survive.
    let out = out_path("cancelled");
    let mut child = Command::new(engine())
        .arg("snapshot-scan")
        .args([
            "--snapshot", fixtures().join("snapshot-needs-hit-tests.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-needs.v1.json").to_str().unwrap(),
            "--timeout-ms", "120000",
            "--out", out.to_str().unwrap(),
        ])
        .spawn()
        .expect("spawn the engine");
    #[cfg(unix)]
    unsafe {
        libc::kill(child.id() as i32, libc::SIGTERM);
    }
    let status = child.wait().expect("wait for the engine");
    if out.exists() {
        let doc: Value = serde_json::from_str(&std::fs::read_to_string(&out).unwrap()).expect("result JSON");
        assert_ne!(doc["verdict"], json!("clean"), "a cancelled run must not report a clean page");
        if doc["status"] == json!("failed") {
            assert!(
                doc["error"]["code"] == json!("cancelled") || doc["error"]["code"] == json!("timeout"),
                "a cancelled failure names its code: {}",
                doc["error"]
            );
        }
    } else {
        // Killed before it could write: a missing result is a failure the caller
        // must treat as such, never as a clean scan.
        assert!(!status.success(), "a killed run must not exit successfully");
    }
}

// --------------------------------------------------------------------------
// coverage receipt content
// --------------------------------------------------------------------------

#[test]
fn the_receipt_accounts_for_every_contracted_pass() {
    let out = out_path("receipt");
    let result = scan(
        &[
            "--snapshot", test_data().join("snapshot-media-intrinsics.v1.json").to_str().unwrap(),
            "--identity", test_data().join("identity-media.v1.json").to_str().unwrap(),
            "--facts", test_data().join("facts-media-round2.v1.json").to_str().unwrap(),
            "--round", "2",
        ],
        &out,
    );
    let passes = result.doc["coverage"]["passes"].as_array().unwrap();
    assert_eq!(passes.len(), 18, "every contracted pass appears in the receipt");
    for p in passes {
        assert!(p["id"].as_str().is_some());
        assert!(p["state"].as_str().is_some(), "pass {} has no state", p["id"]);
        assert!(p["requiredForCleanVerdict"].is_boolean());
    }
    assert_eq!(pass(&result.doc, "media-intrinsics")["state"], json!("covered"));
    assert_eq!(pass(&result.doc, "text-lines")["state"], json!("covered"));
    assert_eq!(pass(&result.doc, "animations")["state"], json!("covered"));
    assert_eq!(pass(&result.doc, "shadow-trees")["state"], json!("covered"));
    assert_eq!(pass(&result.doc, "static-html-source-scan")["state"], json!("not-run"));
    assert_eq!(pass(&result.doc, "scroll-probes")["state"], json!("not-asked"));
    for uncovered in ["pixel-contrast", "reveal-sweep", "cross-origin-iframe", "same-origin-iframe"] {
        assert_eq!(pass(&result.doc, uncovered)["state"], json!("uncovered"));
        assert!(pass(&result.doc, uncovered)["reason"].as_str().unwrap().len() > 10);
    }
    assert_eq!(result.doc["engine"]["upstreamEngineVersion"], json!("0.1.17"));
    assert_eq!(result.doc["contract"], json!("floe.impeccable.snapshot"));
}

#[test]
fn the_engine_identity_travels_with_every_result() {
    let out = out_path("engine-identity");
    let result = scan(
        &[
            "--snapshot", fixtures().join("snapshot-positive.v1.json").to_str().unwrap(),
            "--identity", fixtures().join("identity-positive.v1.json").to_str().unwrap(),
        ],
        &out,
    );
    let engine = &result.doc["engine"];
    assert_eq!(engine["binary"], json!("floe-impeccable"));
    assert_eq!(engine["upstreamEngineVersion"], json!("0.1.17"));
    assert_eq!(engine["targetTriple"].as_str().unwrap().len() > 5, true);
    assert_eq!(engine["upstreamCommit"].as_str().unwrap().len(), 40);
    assert_eq!(engine["engineId"], json!("impeccable-0.1.17+floe.1.0.0"));
}
