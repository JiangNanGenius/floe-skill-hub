//! Failure identity: every refusal names a stable code so the native side can
//! branch on it instead of parsing prose. The codes are part of the v1
//! contract (`SNAPSHOT-CONTRACT.md` §7).

use serde_json::{json, Map, Value};

use crate::contract;

/// The stable error codes this engine emits.
pub mod code {
    pub const USAGE: &str = "usage";
    pub const IO: &str = "io";
    pub const SNAPSHOT_PARSE: &str = "snapshot-parse";
    pub const SNAPSHOT_VERSION_UNSUPPORTED: &str = "snapshot-version-unsupported";
    pub const SCHEMA_MISMATCH: &str = "schema-mismatch";
    pub const IDENTITY_INVALID: &str = "identity-invalid";
    pub const IDENTITY_MISMATCH: &str = "identity-mismatch";
    pub const IDENTITY_UNTRUSTED_PRODUCER: &str = "identity-untrusted-producer";
    pub const IDENTITY_REDACTION_NOT_APPLIED: &str = "identity-redaction-not-applied";
    pub const IDENTITY_SUPERSEDED: &str = "identity-superseded";
    pub const FACTS_PARSE: &str = "facts-parse";
    pub const FACTS_BINDING_MISMATCH: &str = "facts-binding-mismatch";
    pub const FACTS_BITS_MISMATCH: &str = "facts-bits-mismatch";
    pub const BUDGET_EXCEEDED: &str = "budget-exceeded";
    pub const TIMEOUT: &str = "timeout";
    pub const CANCELLED: &str = "cancelled";
    pub const ENGINE: &str = "engine";
}

#[derive(Debug, Clone)]
pub struct EngineFailure {
    pub code: &'static str,
    pub message: String,
    /// Extra structured detail (the offending field names, the exceeded budget,
    /// the mismatching values). Never carries page text or attribute values.
    pub detail: Value,
}

impl EngineFailure {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        EngineFailure { code, message: message.into(), detail: Value::Null }
    }

    pub fn with_detail(mut self, detail: Value) -> Self {
        self.detail = detail;
        self
    }

    /// The `error` object of a result document.
    pub fn document(&self) -> Map<String, Value> {
        let mut m = Map::new();
        m.insert("code".into(), json!(self.code));
        m.insert("message".into(), json!(self.message));
        if !self.detail.is_null() {
            m.insert("detail".into(), self.detail.clone());
        }
        m
    }
}

/// The engine identity block every result document carries, so a result can
/// never be read apart from the binary and the pinned source that produced it.
///
/// `targetTriple` is the triple this binary was actually built for (from
/// `build.rs`), not the triple the contract ships: a host build used for
/// behavioural comparison must not present itself as the guest artifact.
pub fn engine_identity() -> Map<String, Value> {
    let mut block = contract::engine_block();
    block.insert("engineId".into(), json!(contract::engine_id()));
    block.insert("adapterCrateVersion".into(), json!(contract::adapter_version()));
    block.insert("contractTargetTriple".into(), block.get("targetTriple").cloned().unwrap_or(Value::Null));
    block.insert("targetTriple".into(), json!(actual_target_triple()));
    block.insert("runtimeExecution".into(), json!(runtime_execution_state()));
    block
}

/// The triple cargo built this binary for.
pub fn actual_target_triple() -> &'static str {
    option_env!("FLOE_TARGET_TRIPLE").unwrap_or("unknown-target")
}

/// Whether this binary is the shipped guest artifact or a host comparison build.
/// Static verification (ELF, ABI) and runtime execution are separate facts; a
/// host run never proves the guest path.
pub fn runtime_execution_state() -> &'static str {
    if cfg!(all(target_arch = "riscv64", target_os = "linux")) {
        "riscv64-linux"
    } else {
        "host-comparison-build"
    }
}
