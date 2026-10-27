//! `snapshot-scan`: the file-based rule pass with an explicit Needs fixpoint.
//!
//! One invocation is one round. The engine reads a snapshot, an identity and
//! any facts the native producer already answered, runs the pinned upstream
//! rule pass, and writes one result document. When rules ask for measurements
//! the snapshot cannot answer, the run comes back as `needs-facts` with the
//! exact points (and their double bits) — never as a clean scan.
//!
//! Order of gates: budget → parse → schema → identity → facts binding →
//! rule pass → coverage → verdict. Every gate names a stable error code.

use std::path::{Path, PathBuf};
use std::time::Instant;

use serde_json::{json, Map, Value};

use impeccable_core::browser::snapshot::{collect_findings_from_snapshot, PassTrip, SnapshotDom};
use impeccable_core::browser::snapshot::PassLimiter;
use impeccable_core::browser::BrowserConfig;

use crate::contract;
use crate::coverage::{self, RunObservations};
use crate::error::{code, engine_identity, EngineFailure};
use crate::facts::{FactsAccounting, FactsFile};
use crate::identity::{fenced_failure, Identity, IdentityState};
use crate::signal;

#[derive(Debug, Clone)]
pub struct ScanArgs {
    pub snapshot: Option<PathBuf>,
    pub identity: Option<PathBuf>,
    pub facts: Vec<PathBuf>,
    pub config: Option<PathBuf>,
    pub out: Option<PathBuf>,
    pub max_rounds: u32,
    pub max_hit_tests_per_round: usize,
    pub max_hit_tests_total: usize,
    pub max_snapshot_bytes: u64,
    pub timeout_ms: u64,
    /// Explicit unlimited duration (user policy 2026-10-26). Mutually
    /// exclusive with an explicit `--timeout-ms`. Absent flag = frozen
    /// contract default (120000 ms).
    pub no_timeout: bool,
    pub strict_schema: bool,
    pub round: u32,
    /// Test-only: run without an identity. The result then can never be clean,
    /// because an unbound capture proves nothing about a real document.
    pub allow_missing_identity: bool,
}

impl Default for ScanArgs {
    fn default() -> Self {
        let budgets = contract::budgets();
        ScanArgs {
            snapshot: None,
            identity: None,
            facts: Vec::new(),
            config: None,
            out: None,
            max_rounds: budgets.max_rounds,
            max_hit_tests_per_round: budgets.max_hit_tests_per_round,
            max_hit_tests_total: budgets.max_hit_tests_total,
            max_snapshot_bytes: budgets.max_snapshot_bytes,
            timeout_ms: budgets.timeout_ms,
            no_timeout: false,
            strict_schema: true,
            round: 1,
            allow_missing_identity: false,
        }
    }
}

pub const USAGE: &str = "Usage: floe-impeccable snapshot-scan --snapshot <path> [options]

  --snapshot <path>          snapshot document (required)
  --identity <path>          capture identity/binding document
  --facts <path>             answers to an earlier Needs (repeatable)
  --config <path>            BrowserConfig JSON
  --out <path>               result document (stdout when omitted)
  --round <n>                which Needs/facts round this invocation is
  --max-rounds <n>           refuse a round beyond this budget
  --max-hit-tests <n>        per-round hit-test budget
  --max-hit-tests-total <n>  total hit-test budget
  --max-snapshot-bytes <n>   snapshot size budget
  --timeout-ms <n>           deadline for this invocation; 0 is an immediate
                             deadline (NOT unlimited); mutually exclusive
                             with --no-timeout
  --no-timeout               explicit unlimited duration (user policy
                             2026-10-26); the result reports the existing
                             budget.timeoutMs key as JSON null; cooperative
                             cancellation is still honored
  --strict-schema            enforce the v1 schema (default)
  --no-strict-schema         relax the schema gate (fixtures and debugging only)
  --allow-missing-identity   run an isolated synthetic snapshot; the verdict can never be clean

Exit: 0 clean, 2 findings, 3 needs-facts, 4 inconclusive coverage, 1 failure.
";

/// Parse `snapshot-scan` arguments.
pub fn parse_args(args: &[String]) -> Result<ScanArgs, EngineFailure> {
    let mut parsed = ScanArgs::default();
    let mut explicit_timeout_flag_seen = false;
    let mut i = 0;
    let value = |i: &mut usize, flag: &str| -> Result<String, EngineFailure> {
        *i += 1;
        args.get(*i).cloned().ok_or_else(|| {
            EngineFailure::new(code::USAGE, format!("{flag} requires a value\n{USAGE}"))
        })
    };
    while i < args.len() {
        let arg = args[i].clone();
        match arg.as_str() {
            "--snapshot" => parsed.snapshot = Some(PathBuf::from(value(&mut i, "--snapshot")?)),
            "--identity" => parsed.identity = Some(PathBuf::from(value(&mut i, "--identity")?)),
            "--facts" => parsed.facts.push(PathBuf::from(value(&mut i, "--facts")?)),
            "--config" => parsed.config = Some(PathBuf::from(value(&mut i, "--config")?)),
            "--out" => parsed.out = Some(PathBuf::from(value(&mut i, "--out")?)),
            "--round" => parsed.round = parse_u32(&value(&mut i, "--round")?, "--round")?,
            "--max-rounds" => parsed.max_rounds = parse_u32(&value(&mut i, "--max-rounds")?, "--max-rounds")?,
            "--max-hit-tests" => {
                parsed.max_hit_tests_per_round = parse_usize(&value(&mut i, "--max-hit-tests")?, "--max-hit-tests")?
            }
            "--max-hit-tests-total" => {
                parsed.max_hit_tests_total =
                    parse_usize(&value(&mut i, "--max-hit-tests-total")?, "--max-hit-tests-total")?
            }
            "--max-snapshot-bytes" => {
                parsed.max_snapshot_bytes =
                    parse_u64(&value(&mut i, "--max-snapshot-bytes")?, "--max-snapshot-bytes")?
            }
            "--timeout-ms" => {
                explicit_timeout_flag_seen = true;
                parsed.timeout_ms = parse_u64(&value(&mut i, "--timeout-ms")?, "--timeout-ms")?;
            }
            "--no-timeout" => parsed.no_timeout = true,
            "--strict-schema" => parsed.strict_schema = true,
            "--no-strict-schema" => parsed.strict_schema = false,
            "--allow-missing-identity" => parsed.allow_missing_identity = true,
            "--help" | "-h" => return Err(EngineFailure::new(code::USAGE, USAGE.to_string())),
            other => {
                return Err(EngineFailure::new(
                    code::USAGE,
                    format!("snapshot-scan: unknown argument \"{other}\"\n{USAGE}"),
                ))
            }
        }
        i += 1;
    }
    if parsed.snapshot.is_none() {
        return Err(EngineFailure::new(code::USAGE, format!("snapshot-scan requires --snapshot\n{USAGE}")));
    }
    if parsed.round == 0 {
        return Err(EngineFailure::new(code::USAGE, "--round must be at least 1"));
    }
    if parsed.no_timeout && explicit_timeout_flag_seen {
        return Err(EngineFailure::new(
            code::USAGE,
            "--no-timeout and --timeout-ms are mutually exclusive",
        ));
    }
    Ok(parsed)
}

fn parse_u32(s: &str, flag: &str) -> Result<u32, EngineFailure> {
    s.parse::<u32>().map_err(|_| EngineFailure::new(code::USAGE, format!("{flag} requires an integer")))
}

fn parse_usize(s: &str, flag: &str) -> Result<usize, EngineFailure> {
    s.parse::<usize>().map_err(|_| EngineFailure::new(code::USAGE, format!("{flag} requires an integer")))
}

fn parse_u64(s: &str, flag: &str) -> Result<u64, EngineFailure> {
    s.parse::<u64>().map_err(|_| EngineFailure::new(code::USAGE, format!("{flag} requires an integer")))
}

/// The outcome of one invocation.
pub struct ScanOutcome {
    pub exit: i32,
    pub document: Value,
}

pub fn run(args: ScanArgs) -> ScanOutcome {
    let started = Instant::now();
    // Explicit --no-timeout means no deadline at all (the result document
    // reports budget.timeoutMs as JSON null). Any other invocation keeps its
    // integer deadline: --timeout-ms <n> exactly as given (0 = immediate),
    // no flag = the frozen contract default.
    let deadline_ms = if args.no_timeout { None } else { Some(args.timeout_ms) };
    let mut ctx = ScanContext::new(args, started, deadline_ms);
    match ctx.execute() {
        Ok(outcome) => outcome,
        Err(failure) => ctx.failure_outcome(&failure),
    }
}

struct ScanContext {
    args: ScanArgs,
    started: Instant,
    deadline_ms: Option<u64>,
    identity: Option<Identity>,
    identity_state: IdentityState,
    identity_mismatches: Vec<String>,
    budget: BudgetUse,
}

#[derive(Debug, Default, Clone)]
struct BudgetUse {
    snapshot_bytes: u64,
    elements: usize,
    rounds: u32,
    hit_tests_asked: usize,
    hit_tests_answered: usize,
    exceeded: Vec<String>,
}

impl ScanContext {
    fn new(args: ScanArgs, started: Instant, deadline_ms: Option<u64>) -> ScanContext {
        ScanContext {
            args,
            started,
            deadline_ms,
            identity: None,
            identity_state: IdentityState::Absent,
            identity_mismatches: Vec::new(),
            budget: BudgetUse::default(),
        }
    }

    fn elapsed_ms(&self) -> u64 {
        self.started.elapsed().as_millis() as u64
    }

    /// Deadline and cancellation are checked between phases. A rule pass that
    /// overruns is reported when it returns; a process killed by the job
    /// supervisor leaves no result document, which the caller must treat as a
    /// failure rather than as a clean scan.
    fn checkpoint(&self, phase: &str) -> Result<(), EngineFailure> {
        if signal::cancel_requested() {
            return Err(EngineFailure::new(
                code::CANCELLED,
                format!("cancelled during {phase} (signal {})", signal::received_signal()),
            ));
        }
        if let Some(deadline_ms) = self.deadline_ms {
            if self.elapsed_ms() > deadline_ms {
                return Err(EngineFailure::new(
                    code::TIMEOUT,
                    format!("{phase} exceeded the {deadline_ms} ms budget"),
                )
                .with_detail(json!({ "phase": phase, "elapsedMs": self.elapsed_ms() })));
            }
        }
        Ok(())
    }

    fn execute(&mut self) -> Result<ScanOutcome, EngineFailure> {
        self.checkpoint("startup")?;

        let snapshot_path = self.args.snapshot.clone().expect("--snapshot is required");
        let raw = read_capped(&snapshot_path, self.args.max_snapshot_bytes, &mut self.budget)?;
        self.checkpoint("snapshot read")?;

        // Round budget: the caller drives the fixpoint, so the round number is
        // an input the engine enforces rather than a counter it owns.
        if self.args.round > self.args.max_rounds {
            return Err(EngineFailure::new(
                code::BUDGET_EXCEEDED,
                format!(
                    "round {} exceeds the --max-rounds budget of {}",
                    self.args.round, self.args.max_rounds
                ),
            )
            .with_detail(json!({ "round": self.args.round, "maxRounds": self.args.max_rounds })));
        }

        let dom = self.parse_snapshot(&raw)?;
        self.checkpoint("snapshot parse")?;

        // Identity gate (before any facts are trusted).
        self.load_identity(&dom)?;
        self.checkpoint("identity")?;

        // Facts gate.
        let accounting = self.load_facts(&dom)?;
        self.checkpoint("facts")?;

        let config = self.load_config()?;

        // Early unique-miss admission for this pass: the per-round cap, plus
        // what the total budget still admits after the answered facts. The
        // limiter trips at the first NEW unique miss beyond the cap — exactly
        // when the post-hoc `pending > max` check below would have refused the
        // same input — but caught before the expensive work completes.
        let answered: usize = accounting.iter().map(|a| a.answered).sum();
        let admission = self
            .args
            .max_hit_tests_per_round
            .min(self.args.max_hit_tests_total.saturating_sub(answered));
        dom.set_pass_limiter(Some(Box::new(AdapterLimiter {
            deadline: self
                .deadline_ms
                .map(|d| self.started + std::time::Duration::from_millis(d)),
            admission,
        })));

        // The rule pass.
        let run = collect_findings_from_snapshot(&dom, &config);

        // A typed trip discards the partial pass and reports the truthful
        // failure document; partial findings are never presented as a scan.
        // The unique misses the pass stored were drained into the Needs the
        // collector returns, so the honest counters come from there (reading
        // the DOM after the drain would report zero stored). Checked before
        // the phase checkpoint so an in-pass stop is reported with its stage
        // counters, not shadowed by the checkpoint's plainer refusal.
        let stored_misses = match &run {
            Ok(_) => 0usize,
            Err(needs) => needs.hit_tests.len(),
        };
        if let Some(trip) = dom.take_pass_trip() {
            return Err(match trip {
                PassTrip::Cancelled => EngineFailure::new(
                    code::CANCELLED,
                    format!("cancelled during rule pass (signal {})", signal::received_signal()),
                )
                .with_detail(json!({
                    "phase": "rule pass",
                    "elapsedMs": self.elapsed_ms(),
                    "elementsDone": dom.elements_done(),
                    "missesRecorded": stored_misses,
                })),
                // The deadline document keeps the checkpoint's exact shape
                // ({phase, elapsedMs}): the frozen timeout golden records
                // exactly these two keys.
                PassTrip::Deadline => EngineFailure::new(
                    code::TIMEOUT,
                    format!(
                        "rule pass exceeded the {} ms budget",
                        self.deadline_ms.unwrap_or(0)
                    ),
                )
                .with_detail(json!({
                    "phase": "rule pass",
                    "elapsedMs": self.elapsed_ms(),
                })),
                PassTrip::HitTestBudget => EngineFailure::new(
                    code::BUDGET_EXCEEDED,
                    "hit-test budget exceeded: maxHitTestsPerRound (admission stopped at the cap; a further unique point was attempted)"
                )
                .with_detail(json!({
                    "asked": stored_misses + dom.attempted_over_cap(),
                    "pending": stored_misses,
                    "attemptedOverCap": dom.attempted_over_cap(),
                    "maxPerRound": self.args.max_hit_tests_per_round,
                    "maxTotal": self.args.max_hit_tests_total,
                    "exceeded": ["maxHitTestsPerRound"],
                    "elementsDone": dom.elements_done(),
                    "phase": "rule pass",
                })),
            });
        }
        // A stop that arrived after the pass's last cooperative check is
        // still reported here (plainer shape, no stage counters).
        self.checkpoint("rule pass")?;

        let scroll_probes = dom.take_scroll_probes();
        let unknown_style_props = dom.unknown_style_props();
        let pending = match &run {
            Ok(_) => Vec::new(),
            Err(needs) => needs.hit_tests.clone(),
        };

        // Which pending points did the producer already declare unanswerable?
        let unanswerable_keys: Vec<(u64, u64)> = accounting
            .iter()
            .flat_map(|a| a.unanswerable.iter())
            .filter_map(|entry| {
                let x = entry["x"].as_f64()?;
                let y = entry["y"].as_f64()?;
                Some((x.to_bits(), y.to_bits()))
            })
            .collect();
        let unanswerable_pending = pending
            .iter()
            .filter(|[x, y]| unanswerable_keys.contains(&(x.to_bits(), y.to_bits())))
            .count();
        let hit_tests_answered: usize = accounting.iter().map(|a| a.answered).sum();
        self.budget.rounds = self.args.round;
        self.budget.hit_tests_asked = pending.len() + hit_tests_answered;
        self.budget.hit_tests_answered = hit_tests_answered;

        if pending.len() > self.args.max_hit_tests_per_round {
            self.budget.exceeded.push("maxHitTestsPerRound".to_string());
        }
        if self.budget.hit_tests_asked > self.args.max_hit_tests_total {
            self.budget.exceeded.push("maxHitTestsTotal".to_string());
        }
        if !self.budget.exceeded.is_empty() {
            return Err(EngineFailure::new(
                code::BUDGET_EXCEEDED,
                format!("hit-test budget exceeded: {}", self.budget.exceeded.join(", ")),
            )
            .with_detail(json!({
                "asked": self.budget.hit_tests_asked,
                "pending": pending.len(),
                "maxPerRound": self.args.max_hit_tests_per_round,
                "maxTotal": self.args.max_hit_tests_total,
                "exceeded": self.budget.exceeded,
            })));
        }

        let observations = self.observations(&dom, &raw, &pending, unanswerable_pending,
                                             scroll_probes.len(), &accounting, &unknown_style_props,
                                             run.is_ok());

        let findings_value = match &run {
            Ok(result) => Some(serde_json::to_value(result).unwrap_or_else(|_| json!({ "groups": [], "pageLevel": [] }))),
            Err(_) => None,
        };
        let counts = findings_value.as_ref().map(count_findings);

        let coverage = coverage::build(&observations);
        let needs_document = if pending.is_empty() && scroll_probes.is_empty() {
            None
        } else {
            Some(needs_json(&pending, &scroll_probes, self.args.round))
        };

        let finding_count = counts
            .as_ref()
            .and_then(|c| c["total"].as_u64())
            .unwrap_or(0);

        let (status, verdict, exit) = if !pending.is_empty() {
            if unanswerable_pending == pending.len() {
                // Every outstanding point was declared unanswerable: re-running
                // with the same facts cannot progress, so this is terminal and
                // still not a clean result.
                ("inconclusive", "inconclusive", 4)
            } else {
                ("needs-facts", "none", 3)
            }
        } else if finding_count > 0 {
            ("complete", "findings", 2)
        } else if coverage.clean_capable && self.identity_state == IdentityState::Verified {
            ("complete", "clean", 0)
        } else {
            ("inconclusive", "inconclusive", 4)
        };

        let mut document = Map::new();
        document.insert("contract".into(), json!(contract::CONTRACT_NAME));
        document.insert("contractVersion".into(), json!(contract::contract_version()));
        document.insert("status".into(), json!(status));
        document.insert("verdict".into(), json!(verdict));
        document.insert("engine".into(), Value::Object(engine_identity()));
        document.insert(
            "identity".into(),
            match &self.identity {
                Some(identity) => Value::Object(identity.document()),
                None => Value::Null,
            },
        );
        document.insert("identityCheck".into(), self.identity_check_document());
        document.insert("budget".into(), self.budget_document());
        document.insert("coverage".into(), Value::Object(coverage.document()));
        document.insert("needs".into(), needs_document.map(Value::Object).unwrap_or(Value::Null));
        document.insert(
            "findings".into(),
            match (&findings_value, &counts) {
                (Some(findings), Some(counts)) => {
                    let mut m = findings.as_object().cloned().unwrap_or_default();
                    m.insert("counts".into(), counts.clone());
                    Value::Object(m)
                }
                _ => Value::Null,
            },
        );
        document.insert("diagnostics".into(), self.diagnostics(&accounting, unanswerable_pending, &unknown_style_props));
        document.insert("error".into(), Value::Null);

        let out = Value::Object(document);
        self.write_result(&out)?;
        Ok(ScanOutcome { exit, document: out })
    }

    fn parse_snapshot(&self, raw: &str) -> Result<SnapshotDom, EngineFailure> {
        let dom = SnapshotDom::from_json(raw).map_err(|e| {
            EngineFailure::new(code::SNAPSHOT_PARSE, format!("snapshot did not parse: {e}"))
        })?;
        let snap = &dom.snap;
        if self.args.strict_schema {
            if snap.v != 1 {
                return Err(EngineFailure::new(
                    code::SNAPSHOT_VERSION_UNSUPPORTED,
                    format!("snapshot version {} is not supported by contract v1 (expected 1)", snap.v),
                )
                .with_detail(json!({ "snapshotVersion": snap.v, "supported": [1] })));
            }
            let expected = contract::style_prop_count();
            if snap.style_props.len() != expected {
                return Err(EngineFailure::new(
                    code::SCHEMA_MISMATCH,
                    format!(
                        "snapshot styleProps carries {} columns; the pinned engine reads {expected}",
                        snap.style_props.len()
                    ),
                )
                .with_detail(json!({
                    "snapshotColumns": snap.style_props.len(),
                    "engineColumns": expected,
                })));
            }
            for (index, el) in snap.els.iter().enumerate() {
                if el.style.len() != expected {
                    return Err(EngineFailure::new(
                        code::SCHEMA_MISMATCH,
                        format!(
                            "element {} carries {} style values; the snapshot declares {} columns",
                            index + 1,
                            el.style.len(),
                            snap.style_props.len()
                        ),
                    )
                    .with_detail(json!({
                        "elementId": index + 1,
                        "styleValues": el.style.len(),
                        "declaredColumns": snap.style_props.len(),
                    })));
                }
            }
        }
        if snap.els.len() as u64 > contract::budgets().max_elements {
            return Err(EngineFailure::new(
                code::BUDGET_EXCEEDED,
                format!("snapshot carries {} elements; the budget is {}", snap.els.len(), contract::budgets().max_elements),
            )
            .with_detail(json!({ "elements": snap.els.len(), "maxElements": contract::budgets().max_elements })));
        }
        Ok(dom)
    }

    fn load_identity(&mut self, dom: &SnapshotDom) -> Result<(), EngineFailure> {
        match &self.args.identity {
            None => {
                if !self.args.allow_missing_identity {
                    return Err(EngineFailure::new(
                        code::IDENTITY_INVALID,
                        "snapshot-scan requires --identity (or --allow-missing-identity for an isolated synthetic fixture; the verdict can then never be clean)",
                    ));
                }
                self.identity_state = IdentityState::Absent;
                self.identity_mismatches.push("identity document absent".to_string());
                Ok(())
            }
            Some(path) => {
                let raw = std::fs::read_to_string(path).map_err(|e| {
                    EngineFailure::new(code::IO, format!("cannot read identity {}: {e}", path.display()))
                })?;
                let identity = Identity::parse(&raw)?;
                if identity.fenced {
                    self.identity = Some(identity.clone());
                    self.identity_state = IdentityState::Superseded;
                    return Err(fenced_failure(&identity));
                }
                let snap = &dom.snap;
                match identity.verify_against_snapshot(
                    &snap.hostname,
                    snap.inner_width,
                    snap.inner_height,
                    snap.scroll_x,
                    snap.scroll_y,
                ) {
                    Ok(()) => {
                        self.identity_state = IdentityState::Verified;
                        self.identity = Some(identity);
                        Ok(())
                    }
                    Err(failure) => {
                        self.identity = Some(identity);
                        self.identity_state = IdentityState::Mismatch;
                        self.identity_mismatches.push("snapshot binding differs from the identity".to_string());
                        Err(failure)
                    }
                }
            }
        }
    }

    fn load_facts(&self, dom: &SnapshotDom) -> Result<Vec<FactsAccounting>, EngineFailure> {
        let mut accounting = Vec::new();
        let expected = self.identity.as_ref().map(|i| i.binding.clone());
        for path in &self.args.facts {
            let raw = std::fs::read_to_string(path).map_err(|e| {
                EngineFailure::new(code::IO, format!("cannot read facts {}: {e}", path.display()))
            })?;
            let source = path.display().to_string();
            let parsed = FactsFile::parse(&raw, &source)?;
            match &expected {
                Some(binding) => {
                    let (facts, entry) = parsed.into_engine_facts(binding)?;
                    dom.add_facts(&facts);
                    accounting.push(entry);
                }
                None => {
                    // Without a verified identity there is nothing to bind the
                    // answers to; accepting them would let one capture answer
                    // for another.
                    return Err(EngineFailure::new(
                        code::FACTS_BINDING_MISMATCH,
                        format!("{source}: facts require a verified identity binding; none is present"),
                    ));
                }
            }
        }
        Ok(accounting)
    }

    fn load_config(&self) -> Result<BrowserConfig, EngineFailure> {
        match &self.args.config {
            None => Ok(BrowserConfig::default()),
            Some(path) => {
                let raw = std::fs::read_to_string(path).map_err(|e| {
                    EngineFailure::new(code::IO, format!("cannot read config {}: {e}", path.display()))
                })?;
                serde_json::from_str::<BrowserConfig>(&raw)
                    .map_err(|e| EngineFailure::new(code::SCHEMA_MISMATCH, format!("config did not parse: {e}")))
            }
        }
    }

    fn observations(
        &self,
        dom: &SnapshotDom,
        raw: &str,
        pending: &[[f64; 2]],
        unanswerable_pending: usize,
        scroll_probes: usize,
        accounting: &[FactsAccounting],
        unknown_style_props: &[String],
        rule_pass_ran: bool,
    ) -> RunObservations {
        let snap = &dom.snap;
        let mut media_elements = 0usize;
        let mut media_with_intrinsics = 0usize;
        for el in &snap.els {
            let tag = el.tag.to_ascii_uppercase();
            if el.ns == 0 && matches!(tag.as_str(), "IMG" | "VIDEO" | "CANVAS" | "PICTURE") {
                media_elements += 1;
                if el.media.is_some() {
                    media_with_intrinsics += 1;
                }
            }
        }
        let scroll_answers: usize = accounting.iter().map(|a| a.scroll_answers).sum();
        RunObservations {
            rule_pass_ran,
            pending_hit_tests: pending.len().saturating_sub(unanswerable_pending),
            asked_hit_tests: pending.len() + accounting.iter().map(|a| a.answered).sum::<usize>(),
            unanswerable_hit_tests: unanswerable_pending,
            scroll_probes,
            scroll_answers,
            unknown_style_props: unknown_style_props.to_vec(),
            text_lines: snap.text_lines,
            animations_recorded: snap.animations_recorded,
            shadow_trees_recorded: snap.shadow_trees_recorded,
            keyframes_recorded: top_level_key_present(raw, "keyframes"),
            linked_css_recorded: top_level_key_present(raw, "linkedCss"),
            media_elements,
            media_elements_with_intrinsics: media_with_intrinsics,
            failed: false,
            failure_code: None,
        }
    }

    fn identity_check_document(&self) -> Value {
        json!({
            "state": self.identity_state.as_str(),
            "mismatches": self.identity_mismatches,
            "syntheticProducerDigest": self.identity.as_ref().map(|i| i.synthetic_producer_digest).unwrap_or(false),
            "redactionPolicy": self.identity.as_ref().map(|i| i.redaction_policy.clone()),
            "producerTrust": self.identity.as_ref().map(|i| i.producer_trust.clone()),
        })
    }

    fn budget_document(&self) -> Value {
        json!({
            "snapshotBytes": self.budget.snapshot_bytes,
            "elements": self.budget.elements,
            "rounds": self.budget.rounds,
            "maxRounds": self.args.max_rounds,
            "hitTestsAsked": self.budget.hit_tests_asked,
            "hitTestsAnswered": self.budget.hit_tests_answered,
            "maxHitTestsPerRound": self.args.max_hit_tests_per_round,
            "maxHitTestsTotal": self.args.max_hit_tests_total,
            "maxSnapshotBytes": self.args.max_snapshot_bytes,
            // Same existing key, three honest states: explicit --no-timeout →
            // JSON null (actual effective: no deadline); explicit
            // --timeout-ms <n> → integer n (0 = immediate deadline, never
            // re-read as unlimited); no flag → the frozen default 120000.
            // Never a stale 120000 under --no-timeout, never 0, never a
            // synthetic huge cap. No new top-level result keys.
            "timeoutMs": if self.args.no_timeout { Value::Null } else { json!(self.args.timeout_ms) },
            "elapsedMs": self.elapsed_ms(),
            "exceeded": self.budget.exceeded,
        })
    }

    fn diagnostics(
        &self,
        accounting: &[FactsAccounting],
        unanswerable_pending: usize,
        unknown_style_props: &[String],
    ) -> Value {
        let facts_sources: Vec<Value> = accounting
            .iter()
            .map(|a| {
                json!({
                    "source": a.source,
                    "supplied": a.supplied,
                    "answered": a.answered,
                    "unanswerable": a.unanswerable.len(),
                    "scrollAnswers": a.scroll_answers,
                })
            })
            .collect();
        let unanswerable_points: Vec<Value> =
            accounting.iter().flat_map(|a| a.unanswerable.iter().cloned()).collect();
        json!({
            "strictSchema": self.args.strict_schema,
            "allowMissingIdentity": self.args.allow_missing_identity,
            "round": self.args.round,
            "factsFiles": facts_sources,
            "unanswerablePoints": unanswerable_points,
            "unanswerablePending": unanswerable_pending,
            "unknownStyleProps": unknown_style_props,
            "upstreamCommit": contract::upstream_commit(),
            "engineVersion": contract::upstream_engine_version(),
            "note": "a missing measurement is reported, never presented as a clean scan",
        })
    }

    fn write_result(&self, document: &Value) -> Result<(), EngineFailure> {
        let text = serde_json::to_string_pretty(document)
            .map_err(|e| EngineFailure::new(code::ENGINE, format!("cannot serialize the result: {e}")))?;
        match &self.args.out {
            Some(path) => {
                if let Some(parent) = path.parent() {
                    if !parent.as_os_str().is_empty() {
                        std::fs::create_dir_all(parent).map_err(|e| {
                            EngineFailure::new(code::IO, format!("cannot create {}: {e}", parent.display()))
                        })?;
                    }
                }
                // Stage then rename, so a reader never sees a half-written result.
                let staged = path.with_extension("part");
                std::fs::write(&staged, text.as_bytes())
                    .map_err(|e| EngineFailure::new(code::IO, format!("cannot write {}: {e}", staged.display())))?;
                std::fs::rename(&staged, path)
                    .map_err(|e| EngineFailure::new(code::IO, format!("cannot commit {}: {e}", path.display())))?;
                Ok(())
            }
            None => {
                println!("{text}");
                Ok(())
            }
        }
    }

    /// A refusal still produces a result document, so the caller always has a
    /// machine-readable reason instead of only an exit code.
    fn failure_outcome(&self, failure: &EngineFailure) -> ScanOutcome {
        let observations = RunObservations {
            failed: true,
            failure_code: Some(failure.code.to_string()),
            unknown_style_props: Vec::new(),
            ..RunObservations::default()
        };
        let coverage = coverage::build(&observations);
        let mut document = Map::new();
        document.insert("contract".into(), json!(contract::CONTRACT_NAME));
        document.insert("contractVersion".into(), json!(contract::contract_version()));
        document.insert("status".into(), json!("failed"));
        document.insert("verdict".into(), json!("none"));
        document.insert("engine".into(), Value::Object(engine_identity()));
        document.insert(
            "identity".into(),
            match &self.identity {
                Some(identity) => Value::Object(identity.document()),
                None => Value::Null,
            },
        );
        document.insert("identityCheck".into(), self.identity_check_document());
        document.insert("budget".into(), self.budget_document());
        document.insert("coverage".into(), Value::Object(coverage.document()));
        document.insert("needs".into(), Value::Null);
        document.insert("findings".into(), Value::Null);
        document.insert("diagnostics".into(), json!({ "strictSchema": self.args.strict_schema }));
        document.insert("error".into(), Value::Object(failure.document()));
        let value = Value::Object(document);
        // Best effort: a failure document is still written when --out was given.
        let _ = self.write_result(&value);
        ScanOutcome { exit: 1, document: value }
    }
}

fn read_capped(path: &Path, cap: u64, budget: &mut BudgetUse) -> Result<String, EngineFailure> {
    let metadata = std::fs::metadata(path)
        .map_err(|e| EngineFailure::new(code::IO, format!("cannot read {}: {e}", path.display())))?;
    let size = metadata.len();
    budget.snapshot_bytes = size;
    if size > cap {
        budget.exceeded.push("maxSnapshotBytes".to_string());
        return Err(EngineFailure::new(
            code::BUDGET_EXCEEDED,
            format!("snapshot is {size} bytes; the budget is {cap}"),
        )
        .with_detail(json!({ "snapshotBytes": size, "maxSnapshotBytes": cap })));
    }
    std::fs::read_to_string(path)
        .map_err(|e| EngineFailure::new(code::IO, format!("cannot read {}: {e}", path.display())))
}

fn needs_json(pending: &[[f64; 2]], scroll_probes: &[u32], round: u32) -> Map<String, Value> {
    let mut m = Map::new();
    m.insert(
        "hitTests".into(),
        Value::Array(pending.iter().map(|[x, y]| json!([x, y])).collect()),
    );
    m.insert(
        "hitTestsBits".into(),
        Value::Array(
            pending
                .iter()
                .map(|[x, y]| json!([x.to_bits().to_string(), y.to_bits().to_string()]))
                .collect(),
        ),
    );
    m.insert("scrollProbes".into(), Value::Array(scroll_probes.iter().map(|el| json!(el)).collect()));
    m.insert("round".into(), json!(round));
    m.insert(
        "note".into(),
        json!("answer these points on the same document identity, then re-run with --facts; a missing measurement is never a clean result"),
    );
    m
}

fn count_findings(findings: &Value) -> Value {
    let page_level = findings["pageLevel"].as_array().map(|a| a.len()).unwrap_or(0);
    let mut grouped = 0usize;
    let mut elements = 0usize;
    let mut by_rule: Map<String, Value> = Map::new();
    if let Some(groups) = findings["groups"].as_array() {
        elements = groups.len();
        for group in groups {
            if let Some(list) = group["findings"].as_array() {
                grouped += list.len();
                for finding in list {
                    if let Some(rule) = finding["type"].as_str() {
                        let entry = by_rule.entry(rule.to_string()).or_insert(json!(0));
                        *entry = json!(entry.as_u64().unwrap_or(0) + 1);
                    }
                }
            }
        }
    }
    for finding in findings["pageLevel"].as_array().map(|a| a.as_slice()).unwrap_or(&[]) {
        if let Some(rule) = finding["type"].as_str() {
            let entry = by_rule.entry(rule.to_string()).or_insert(json!(0));
            *entry = json!(entry.as_u64().unwrap_or(0) + 1);
        }
    }
    json!({
        "total": grouped + page_level,
        "grouped": grouped,
        "pageLevel": page_level,
        "elements": elements,
        "byRule": Value::Object(by_rule),
    })
}

/// The cooperative limiter the adapter installs for the rule pass: the live
/// cancel flag, the effective deadline (None under --no-timeout), and the
/// unique-miss admission cap for this round.
struct AdapterLimiter {
    deadline: Option<Instant>,
    admission: usize,
}

impl PassLimiter for AdapterLimiter {
    fn cancelled(&self) -> bool {
        signal::cancel_requested()
    }

    fn deadline_exceeded(&self) -> bool {
        match self.deadline {
            Some(deadline) => Instant::now() > deadline,
            None => false,
        }
    }

    fn max_unique_misses(&self) -> Option<usize> {
        Some(self.admission)
    }
}

/// Whether `key` appears as a top-level member of the snapshot object.
///
/// One pass over the bytes with depth and string-escape tracking: precise
/// enough to distinguish "recorded an empty list" from "not recorded", and
/// cheap enough for a 48 MiB capture inside a 256 MB emulated guest.
pub fn top_level_key_present(raw: &str, key: &str) -> bool {
    let bytes = raw.as_bytes();
    let mut depth = 0usize;
    let mut in_string = false;
    let mut escaped = false;
    let mut start = 0usize;
    for (i, &b) in bytes.iter().enumerate() {
        if in_string {
            if escaped {
                escaped = false;
                continue;
            }
            match b {
                b'\\' => escaped = true,
                b'"' => {
                    in_string = false;
                    if depth == 1 {
                        let name = &raw[start..i];
                        if name == key {
                            return true;
                        }
                    }
                }
                _ => {}
            }
            continue;
        }
        match b {
            b'"' => {
                in_string = true;
                start = i + 1;
            }
            b'{' | b'[' => depth += 1,
            b'}' | b']' => depth = depth.saturating_sub(1),
            _ => {}
        }
    }
    false
}
