//! The coverage receipt: what this run actually measured, and what it could not.
//!
//! The pass registry comes from the frozen contract, so the receipt cannot
//! quietly drop a pass. Every pass gets a state; a pass Floe has not
//! implemented is `uncovered` with the reason published in the contract, and
//! an uncovered pass that is `requiredForCleanVerdict` makes an empty finding
//! list `inconclusive` rather than clean. That asymmetry is the whole point:
//! findings are positive evidence, absence of findings is not.

use serde_json::{json, Map, Value};

use crate::contract;

/// What the run observed, feeding the receipt.
#[derive(Debug, Clone, Default)]
pub struct RunObservations {
    /// The core rule pass ran to completion (no engine error).
    pub rule_pass_ran: bool,
    /// Hit-test points still unanswered after the supplied facts.
    pub pending_hit_tests: usize,
    /// Hit-test points asked in total during this invocation.
    pub asked_hit_tests: usize,
    /// Points the producer declared it could not answer.
    pub unanswerable_hit_tests: usize,
    /// Scroll probes the rules asked about.
    pub scroll_probes: usize,
    /// Scroll probes answered by the supplied facts.
    pub scroll_answers: usize,
    /// Computed-style properties the rules read that the capture did not record.
    pub unknown_style_props: Vec<String>,
    /// Snapshot-level capture flags.
    pub text_lines: bool,
    pub animations_recorded: bool,
    pub shadow_trees_recorded: bool,
    pub keyframes_recorded: bool,
    pub linked_css_recorded: bool,
    pub media_elements: usize,
    pub media_elements_with_intrinsics: usize,
    /// The run failed before or during the rule pass.
    pub failed: bool,
    pub failure_code: Option<String>,
}

/// The receipt: the pass list plus the derived blockers.
#[derive(Debug, Clone)]
pub struct Coverage {
    pub passes: Vec<Map<String, Value>>,
    pub uncovered_required: Vec<String>,
    pub unknown_style_props: Vec<String>,
    /// True when every pass that a clean verdict requires is covered.
    pub clean_capable: bool,
}

impl Coverage {
    pub fn document(&self) -> Map<String, Value> {
        let mut m = Map::new();
        m.insert(
            "passes".into(),
            Value::Array(self.passes.iter().map(|p| Value::Object(p.clone())).collect()),
        );
        m.insert(
            "uncoveredRequired".into(),
            Value::Array(self.uncovered_required.iter().map(|s| json!(s)).collect()),
        );
        m.insert(
            "unknownStyleProps".into(),
            Value::Array(self.unknown_style_props.iter().map(|s| json!(s)).collect()),
        );
        m.insert("cleanCapable".into(), json!(self.clean_capable));
        m
    }
}

const COVERED: &str = "covered";
const COMPLETE: &str = "complete";
const PARTIAL: &str = "partial";
const NEEDS_FACTS: &str = "needs-facts";
const UNANSWERED: &str = "unanswered";
const UNCOVERED: &str = "uncovered";
const NOT_RUN: &str = "not-run";
const UNRECORDED: &str = "unrecorded";
const FAILED: &str = "failed";
const NOT_ASKED: &str = "not-asked";

/// States that satisfy a `requiredForCleanVerdict` pass.
fn satisfies_required(state: &str) -> bool {
    matches!(state, COVERED | COMPLETE | NOT_ASKED)
}

pub fn build(obs: &RunObservations) -> Coverage {
    let mut passes: Vec<Map<String, Value>> = Vec::new();
    let mut uncovered_required: Vec<String> = Vec::new();

    for pass in contract::coverage_passes() {
        let id = pass["id"].as_str().unwrap_or("").to_string();
        let required = pass["requiredForCleanVerdict"].as_bool().unwrap_or(false);
        let implemented = pass["implemented"].as_bool().unwrap_or(false);
        let (state, detail): (String, Value) = if !implemented {
            (
                UNCOVERED.to_string(),
                json!({
                    "reason": pass["reason"].as_str().unwrap_or("not implemented in v1"),
                    "implemented": false,
                }),
            )
        } else {
            observed_state(&id, obs, &pass)
        };

        let mut entry = Map::new();
        entry.insert("id".into(), json!(id));
        entry.insert("title".into(), pass["title"].clone());
        entry.insert("state".into(), json!(state));
        entry.insert("requiredForCleanVerdict".into(), json!(required));
        entry.insert("implemented".into(), json!(implemented));
        if let Some(reason) = pass["reason"].as_str() {
            entry.insert("reason".into(), json!(reason));
        }
        if !detail.is_null() {
            entry.insert("detail".into(), detail);
        }
        if required && !satisfies_required(&state) {
            uncovered_required.push(id.clone());
        }
        passes.push(entry);
    }

    let clean_capable = uncovered_required.is_empty() && obs.unknown_style_props.is_empty();
    Coverage {
        passes,
        uncovered_required,
        unknown_style_props: obs.unknown_style_props.clone(),
        clean_capable,
    }
}

fn observed_state(id: &str, obs: &RunObservations, pass: &Value) -> (String, Value) {
    match id {
        "core-rule-pass" => {
            if obs.failed {
                (
                    FAILED.to_string(),
                    json!({ "code": obs.failure_code.clone().unwrap_or_else(|| "engine".into()) }),
                )
            } else if obs.rule_pass_ran && obs.pending_hit_tests == 0 {
                (COVERED.to_string(), json!({ "rounds": 1 }))
            } else if obs.pending_hit_tests > 0 {
                (NEEDS_FACTS.to_string(), json!({ "pendingHitTests": obs.pending_hit_tests }))
            } else {
                (NOT_RUN.to_string(), Value::Null)
            }
        }
        "hit-test-fixpoint" => {
            if obs.failed {
                return (FAILED.to_string(), Value::Null);
            }
            if obs.asked_hit_tests == 0 && obs.pending_hit_tests == 0 {
                return (
                    COVERED.to_string(),
                    json!({ "asked": 0, "note": "no rule asked for a hit test on this page" }),
                );
            }
            if obs.unanswerable_hit_tests > 0 {
                return (
                    UNANSWERED.to_string(),
                    json!({
                        "asked": obs.asked_hit_tests,
                        "unanswerable": obs.unanswerable_hit_tests,
                        "note": "the producer could not answer these points; they are reported, never treated as clean",
                    }),
                );
            }
            if obs.pending_hit_tests > 0 {
                return (
                    NEEDS_FACTS.to_string(),
                    json!({ "asked": obs.asked_hit_tests, "pending": obs.pending_hit_tests }),
                );
            }
            (COVERED.to_string(), json!({ "asked": obs.asked_hit_tests, "answered": obs.asked_hit_tests }))
        }
        "style-parity" => {
            if obs.failed {
                return (FAILED.to_string(), Value::Null);
            }
            if obs.unknown_style_props.is_empty() {
                (
                    COMPLETE.to_string(),
                    json!({ "columns": contract::style_prop_count() }),
                )
            } else {
                (
                    PARTIAL.to_string(),
                    json!({
                        "unknownStyleProps": obs.unknown_style_props,
                        "note": "the rules read these computed-style properties but the capture did not record them",
                    }),
                )
            }
        }
        "scroll-probes" => {
            if obs.failed {
                return (FAILED.to_string(), Value::Null);
            }
            if obs.scroll_probes == 0 {
                return (NOT_ASKED.to_string(), json!({ "asked": 0 }));
            }
            if obs.scroll_answers >= obs.scroll_probes {
                return (
                    COVERED.to_string(),
                    json!({ "asked": obs.scroll_probes, "answered": obs.scroll_answers }),
                );
            }
            (
                UNANSWERED.to_string(),
                json!({
                    "asked": obs.scroll_probes,
                    "answered": obs.scroll_answers,
                    "note": "v1 has no scroll-probe producer; unanswered probes count as hidden upstream and are never reported as clean",
                }),
            )
        }
        "static-html-source-scan" => (
            NOT_RUN.to_string(),
            json!({ "note": "separate verb (detect); a snapshot scan never claims it ran" }),
        ),
        "media-intrinsics" => {
            if obs.media_elements == 0 {
                (NOT_ASKED.to_string(), json!({ "mediaElements": 0 }))
            } else if obs.media_elements_with_intrinsics >= obs.media_elements {
                (
                    COVERED.to_string(),
                    json!({ "mediaElements": obs.media_elements }),
                )
            } else {
                (
                    UNRECORDED.to_string(),
                    json!({
                        "mediaElements": obs.media_elements,
                        "withIntrinsics": obs.media_elements_with_intrinsics,
                    }),
                )
            }
        }
        "animations" => flag_state(obs.animations_recorded, pass),
        "shadow-trees" => flag_state(obs.shadow_trees_recorded, pass),
        "text-lines" => flag_state(obs.text_lines, pass),
        "keyframes-and-linked-css" => {
            let state = match (obs.keyframes_recorded, obs.linked_css_recorded) {
                (true, true) => COVERED,
                (false, false) => UNRECORDED,
                _ => PARTIAL,
            };
            (
                state.to_string(),
                json!({
                    "keyframesRecorded": obs.keyframes_recorded,
                    "linkedCssRecorded": obs.linked_css_recorded,
                }),
            )
        }
        other => (
            NOT_RUN.to_string(),
            json!({ "note": format!("pass {other} has no v1 observation") }),
        ),
    }
}

fn flag_state(recorded: bool, pass: &Value) -> (String, Value) {
    if recorded {
        (COVERED.to_string(), Value::Null)
    } else {
        (
            UNRECORDED.to_string(),
            json!({
                "note": pass["notes"].as_str().unwrap_or("the capture did not record this"),
            }),
        )
    }
}
