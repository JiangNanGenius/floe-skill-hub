//! The frozen v1 contract, embedded at compile time.
//!
//! `build_engine.py` copies `engines/impeccable/contract/` into this crate's
//! `data/` directory and verifies every digest against the frozen files before
//! compiling, so the binary can never disagree with the committed contract:
//! `floe-impeccable contract` prints exactly the bytes the hub tracks, and
//! `snapshot-schema` prints the producer-facing projection of the same file.
//!
//! The coverage pass registry is read from the contract rather than duplicated
//! in Rust, which keeps the receipt honest when a pass is added or removed.

use serde_json::{Map, Value};

pub const CONTRACT_NAME: &str = "floe.impeccable.snapshot";

pub static CONTRACT_JSON: &str = include_str!("../data/snapshot-contract.v1.json");
pub static SNAPSHOT_SCHEMA_JSON: &str = include_str!("../data/producer/snapshot.schema.v1.json");
pub static FACTS_SCHEMA_JSON: &str = include_str!("../data/producer/facts.schema.v1.json");
pub static IDENTITY_SCHEMA_JSON: &str = include_str!("../data/producer/identity.schema.v1.json");
pub static RESULT_SCHEMA_JSON: &str = include_str!("../data/producer/result.schema.v1.json");
pub static STYLE_PROPS_JSON: &str = include_str!("../data/producer/style-props.v1.json");
pub static PSEUDO_PROPS_JSON: &str = include_str!("../data/producer/pseudo-props.v1.json");
pub static STATE_PSEUDOS_JSON: &str = include_str!("../data/producer/state-pseudos.v1.json");
pub static CAPTURE_LIMITS_JSON: &str = include_str!("../data/producer/capture-limits.v1.json");

fn parse(raw: &'static str) -> Value {
    serde_json::from_str(raw).expect("the embedded contract must be valid JSON")
}

/// The whole contract document.
pub fn contract() -> Value {
    parse(CONTRACT_JSON)
}

pub fn contract_version() -> i64 {
    contract()["contractVersion"].as_i64().unwrap_or(1)
}

pub fn engine_block() -> Map<String, Value> {
    contract()["engine"]
        .as_object()
        .cloned()
        .unwrap_or_else(Map::new)
}

pub fn upstream_engine_version() -> String {
    engine_block()["upstreamEngineVersion"]
        .as_str()
        .unwrap_or("unknown")
        .to_string()
}

pub fn upstream_commit() -> String {
    engine_block()["upstreamCommit"]
        .as_str()
        .unwrap_or("unknown")
        .to_string()
}

pub fn adapter_version() -> String {
    option_env!("FLOE_ADAPTER_VERSION")
        .unwrap_or(env!("CARGO_PKG_VERSION"))
        .to_string()
}

/// `impeccable-engine <engine>+floe.<adapter>`: the handshake string the
/// upstream launcher matches (`impeccable-engine*`) with the Floe adapter
/// identity appended, so a Floe engine is never mistaken for a plain upstream
/// one and an upstream launcher still accepts it.
pub fn probe_line() -> String {
    format!(
        "impeccable-engine {}+floe.{}\n",
        upstream_engine_version(),
        adapter_version()
    )
}

/// `<engine>+floe.<adapter>` for `--version`.
pub fn version_string() -> String {
    format!("{}+floe.{}", upstream_engine_version(), adapter_version())
}

pub fn engine_id() -> String {
    format!(
        "impeccable-{}+floe.{}",
        upstream_engine_version(),
        adapter_version()
    )
}

/// The style-property columns the pinned engine reads, in `SnapNode.s` order.
pub fn style_props() -> Vec<String> {
    parse(STYLE_PROPS_JSON)["styleProps"]
        .as_array()
        .map(|a| a.iter().filter_map(|v| v.as_str().map(str::to_string)).collect())
        .unwrap_or_default()
}

pub fn style_prop_count() -> usize {
    style_props().len()
}

/// The coverage pass registry exactly as published in the contract.
pub fn coverage_passes() -> Vec<Value> {
    contract()["coveragePasses"]
        .as_array()
        .cloned()
        .unwrap_or_default()
}

pub fn budgets() -> Budgets {
    let b = &contract()["budgets"];
    Budgets {
        max_snapshot_bytes: b["maxSnapshotBytes"].as_u64().unwrap_or(48 * 1024 * 1024),
        max_elements: b["maxElements"].as_u64().unwrap_or(30_000),
        max_rounds: b["maxRounds"].as_u64().unwrap_or(4) as u32,
        max_hit_tests_per_round: b["maxHitTestsPerRound"].as_u64().unwrap_or(4096) as usize,
        max_hit_tests_total: b["maxHitTestsTotal"].as_u64().unwrap_or(16_384) as usize,
        timeout_ms: b["timeoutMs"].as_u64().unwrap_or(120_000),
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Budgets {
    pub max_snapshot_bytes: u64,
    pub max_elements: u64,
    pub max_rounds: u32,
    pub max_hit_tests_per_round: usize,
    pub max_hit_tests_total: usize,
    pub timeout_ms: u64,
}

/// The producer-facing capture contract printed by `snapshot-schema`.
pub fn snapshot_schema_document() -> Value {
    let limits = parse(CAPTURE_LIMITS_JSON);
    let contract = contract();
    let mut doc = Map::new();
    doc.insert("contract".into(), Value::String(CONTRACT_NAME.into()));
    doc.insert(
        "contractVersion".into(),
        Value::Number(contract["contractVersion"].as_i64().unwrap_or(1).into()),
    );
    doc.insert("schemaStatus".into(), contract["schemaStatus"].clone());
    doc.insert("engine".into(), contract["engine"].clone());
    doc.insert("snapshotVersion".into(), Value::Number(1.into()));
    doc.insert("styleProps".into(), parse(STYLE_PROPS_JSON)["styleProps"].clone());
    doc.insert("pseudoProps".into(), parse(PSEUDO_PROPS_JSON)["pseudoProps"].clone());
    doc.insert("statePseudos".into(), parse(STATE_PSEUDOS_JSON)["statePseudos"].clone());
    doc.insert("limits".into(), limits["floeBudgets"].clone());
    doc.insert("upstreamDefaults".into(), limits["upstreamDefaults"].clone());
    doc.insert("namespaces".into(), limits["namespaces"].clone());
    doc.insert("snapshotSchema".into(), parse(SNAPSHOT_SCHEMA_JSON));
    doc.insert("factsSchema".into(), parse(FACTS_SCHEMA_JSON));
    doc.insert("identitySchema".into(), parse(IDENTITY_SCHEMA_JSON));
    doc.insert("resultSchema".into(), parse(RESULT_SCHEMA_JSON));
    doc.insert("needs".into(), contract["needs"].clone());
    doc.insert("facts".into(), contract["facts"].clone());
    doc.insert("identity".into(), contract["identity"].clone());
    doc.insert("coveragePasses".into(), contract["coveragePasses"].clone());
    doc.insert("verbs".into(), contract["verbs"].clone());
    doc.insert("exitCodes".into(), exit_code_table());
    Value::Object(doc)
}

fn exit_code_table() -> Value {
    let verbs = contract()["verbs"].as_array().cloned().unwrap_or_default();
    verbs
        .iter()
        .find(|v| v["name"].as_str() == Some("snapshot-scan"))
        .map(|v| v["exit"].clone())
        .unwrap_or_else(|| Value::Null)
}
