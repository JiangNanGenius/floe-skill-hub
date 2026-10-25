//! Capture identity: the binding and fencing gate between the native producer
//! and the engine.
//!
//! A snapshot is only a measurement of one document in one task, session, tab
//! and viewport. Everything the contract requires of that binding is checked
//! here, before any rule runs, and a failure is a refusal rather than a
//! degraded scan:
//!
//! * the native binding fields are all present (`taskId`, `sessionId`, `tabId`,
//!   `documentId`, `captureId`, `documentGeneration`);
//! * the producer is the fixed native script (`producerTrust`) with its exact
//!   bytes bound (`producer.scriptDigest`) — a model-declared or page-declared
//!   trust value is rejected;
//! * the redaction policy was applied (password values, form values and
//!   credential attributes never reach the engine);
//! * the capture is not fenced, and the identity's hostname/viewport/scroll
//!   equal the snapshot's own values.

use serde_json::{json, Map, Value};

use crate::error::{code, EngineFailure};

pub const PRODUCER_TRUST: &str = "native-fixed-script";
pub const REDACTION_POLICY: &str = "floe.impeccable.redaction.v1";
pub const PRODUCER_ENGINE: &str = "WebKit";

/// The identity check outcome recorded in every result document.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IdentityState {
    Verified,
    Absent,
    Mismatch,
    Superseded,
}

impl IdentityState {
    pub fn as_str(&self) -> &'static str {
        match self {
            IdentityState::Verified => "verified",
            IdentityState::Absent => "absent",
            IdentityState::Mismatch => "mismatch",
            IdentityState::Superseded => "superseded",
        }
    }
}

/// The binding a snapshot, its needs and its facts must all agree on.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Binding {
    pub task_id: String,
    pub session_id: String,
    pub tab_id: String,
    pub document_id: String,
    pub capture_id: String,
    pub document_generation: u64,
}

impl Binding {
    fn from_value(v: &Value) -> Result<Binding, Vec<String>> {
        let mut missing = Vec::new();
        let mut text = |key: &str| -> String {
            match v[key].as_str().map(str::to_string) {
                Some(s) if !s.is_empty() => s,
                _ => {
                    missing.push(key.to_string());
                    String::new()
                }
            }
        };
        let binding = Binding {
            task_id: text("taskId"),
            session_id: text("sessionId"),
            tab_id: text("tabId"),
            document_id: text("documentId"),
            capture_id: text("captureId"),
            document_generation: match v["documentGeneration"].as_u64() {
                Some(n) => n,
                None => {
                    missing.push("documentGeneration".to_string());
                    0
                }
            },
        };
        if missing.is_empty() {
            Ok(binding)
        } else {
            Err(missing)
        }
    }

    pub fn document(&self) -> Map<String, Value> {
        let mut m = Map::new();
        m.insert("taskId".into(), json!(self.task_id));
        m.insert("sessionId".into(), json!(self.session_id));
        m.insert("tabId".into(), json!(self.tab_id));
        m.insert("documentId".into(), json!(self.document_id));
        m.insert("captureId".into(), json!(self.capture_id));
        m.insert("documentGeneration".into(), json!(self.document_generation));
        m
    }

    /// The fields two documents must agree on for one to answer the other.
    pub fn matches(&self, other: &Binding) -> Vec<String> {
        let mut differ = Vec::new();
        if self.task_id != other.task_id {
            differ.push("taskId".to_string());
        }
        if self.session_id != other.session_id {
            differ.push("sessionId".to_string());
        }
        if self.tab_id != other.tab_id {
            differ.push("tabId".to_string());
        }
        if self.document_id != other.document_id {
            differ.push("documentId".to_string());
        }
        if self.capture_id != other.capture_id {
            differ.push("captureId".to_string());
        }
        if self.document_generation != other.document_generation {
            differ.push("documentGeneration".to_string());
        }
        differ
    }
}

#[derive(Debug, Clone)]
pub struct Identity {
    pub binding: Binding,
    pub url: String,
    pub hostname: String,
    pub viewport: (f64, f64),
    pub scroll: (f64, f64),
    pub captured_at_ms: u64,
    pub producer_trust: String,
    pub producer_name: String,
    pub producer_version: String,
    pub producer_engine: String,
    pub script_digest: String,
    pub redaction_policy: String,
    pub redaction: Map<String, Value>,
    pub fenced: bool,
    /// An all-zero digest is the documented synthetic fixture marker. It is
    /// surfaced, never silently trusted as a real capture.
    pub synthetic_producer_digest: bool,
}

impl Identity {
    pub fn parse(raw: &str) -> Result<Identity, EngineFailure> {
        let v: Value = serde_json::from_str(raw)
            .map_err(|e| EngineFailure::new(code::IDENTITY_INVALID, format!("identity is not valid JSON: {e}")))?;
        Identity::from_value(&v)
    }

    pub fn from_value(v: &Value) -> Result<Identity, EngineFailure> {
        let binding = Binding::from_value(v).map_err(|missing| {
            EngineFailure::new(
                code::IDENTITY_INVALID,
                "identity is missing required native binding fields",
            )
            .with_detail(json!({ "missing": missing }))
        })?;

        let url = v["url"].as_str().unwrap_or("").to_string();
        if url.is_empty() {
            return Err(EngineFailure::new(code::IDENTITY_INVALID, "identity.url is required")
                .with_detail(json!({ "missing": ["url"] })));
        }

        let producer_trust = v["producerTrust"].as_str().unwrap_or("").to_string();
        if producer_trust != PRODUCER_TRUST {
            return Err(EngineFailure::new(
                code::IDENTITY_UNTRUSTED_PRODUCER,
                format!(
                    "producerTrust must be \"{PRODUCER_TRUST}\"; only the fixed audited native producer is trusted"
                ),
            )
            .with_detail(json!({ "producerTrust": producer_trust })));
        }

        let producer = &v["producer"];
        let producer_engine = producer["engine"].as_str().unwrap_or("").to_string();
        if producer_engine != PRODUCER_ENGINE {
            return Err(EngineFailure::new(
                code::IDENTITY_UNTRUSTED_PRODUCER,
                format!("producer.engine must be \"{PRODUCER_ENGINE}\""),
            )
            .with_detail(json!({ "producer.engine": producer_engine })));
        }
        let script_digest = producer["scriptDigest"].as_str().unwrap_or("").to_string();
        if !is_sha256_hex(&script_digest) {
            return Err(EngineFailure::new(
                code::IDENTITY_UNTRUSTED_PRODUCER,
                "producer.scriptDigest must be the sha256 of the exact fixed measurement script bytes",
            )
            .with_detail(json!({ "scriptDigestLength": script_digest.len() })));
        }
        let producer_name = producer["name"].as_str().unwrap_or("").to_string();
        let producer_version = producer["version"].as_str().unwrap_or("").to_string();
        if producer_name.is_empty() || producer_version.is_empty() {
            return Err(EngineFailure::new(
                code::IDENTITY_INVALID,
                "producer.name and producer.version are required",
            ));
        }

        let redaction = v["redaction"].as_object().cloned().unwrap_or_default();
        let redaction_policy = redaction["policy"].as_str().unwrap_or("").to_string();
        if redaction_policy != REDACTION_POLICY {
            return Err(EngineFailure::new(
                code::IDENTITY_REDACTION_NOT_APPLIED,
                format!("redaction.policy must be \"{REDACTION_POLICY}\""),
            )
            .with_detail(json!({ "redaction.policy": redaction_policy })));
        }
        if !redaction["applied"].as_bool().unwrap_or(false) {
            return Err(EngineFailure::new(
                code::IDENTITY_REDACTION_NOT_APPLIED,
                "redaction.applied must be true: password values, form values and credential attributes are dropped inside the fixed producer before the snapshot leaves the device",
            ));
        }
        for key in ["passwordInputs", "formValues", "textRuns"] {
            if redaction[key].as_u64().is_none() {
                return Err(EngineFailure::new(
                    code::IDENTITY_REDACTION_NOT_APPLIED,
                    format!("redaction.{key} count is required"),
                ));
            }
        }
        if !redaction["credentialAttributes"].is_array() {
            return Err(EngineFailure::new(
                code::IDENTITY_REDACTION_NOT_APPLIED,
                "redaction.credentialAttributes is required",
            ));
        }

        let fenced = v["fenced"].as_bool().unwrap_or(false);
        let viewport = (
            v["viewport"]["width"].as_f64().unwrap_or(f64::NAN),
            v["viewport"]["height"].as_f64().unwrap_or(f64::NAN),
        );
        let scroll = (
            v["scroll"]["x"].as_f64().unwrap_or(f64::NAN),
            v["scroll"]["y"].as_f64().unwrap_or(f64::NAN),
        );
        if viewport.0.is_nan() || viewport.1.is_nan() || scroll.0.is_nan() || scroll.1.is_nan() {
            return Err(EngineFailure::new(
                code::IDENTITY_INVALID,
                "identity.viewport and identity.scroll must carry numeric width/height/x/y",
            ));
        }

        Ok(Identity {
            binding,
            url,
            hostname: v["hostname"].as_str().unwrap_or("").to_string(),
            viewport,
            scroll,
            captured_at_ms: v["capturedAtMs"].as_u64().unwrap_or(0),
            producer_trust,
            producer_name,
            producer_version,
            producer_engine,
            script_digest: script_digest.clone(),
            redaction_policy,
            redaction,
            fenced,
            synthetic_producer_digest: script_digest.chars().all(|c| c == '0'),
        })
    }

    /// Compare the identity against the snapshot it claims to describe. Any
    /// difference means the identity belongs to another document, viewport or
    /// scroll position, so the snapshot cannot be scanned under it.
    pub fn verify_against_snapshot(
        &self,
        snapshot_hostname: &str,
        inner_width: f64,
        inner_height: f64,
        scroll_x: f64,
        scroll_y: f64,
    ) -> Result<(), EngineFailure> {
        let mut mismatches: Vec<Value> = Vec::new();
        if self.hostname != snapshot_hostname {
            mismatches.push(json!({ "field": "hostname" }));
        }
        if self.viewport.0 != inner_width || self.viewport.1 != inner_height {
            mismatches.push(json!({
                "field": "viewport",
                "identity": [self.viewport.0, self.viewport.1],
                "snapshot": [inner_width, inner_height],
            }));
        }
        if self.scroll.0 != scroll_x || self.scroll.1 != scroll_y {
            mismatches.push(json!({
                "field": "scroll",
                "identity": [self.scroll.0, self.scroll.1],
                "snapshot": [scroll_x, scroll_y],
            }));
        }
        if !mismatches.is_empty() {
            return Err(EngineFailure::new(
                code::IDENTITY_MISMATCH,
                "identity does not bind this snapshot (hostname, viewport or scroll differ)",
            )
            .with_detail(json!({ "mismatches": mismatches })));
        }
        Ok(())
    }

    pub fn document(&self) -> Map<String, Value> {
        let mut m = self.binding.document();
        m.insert("url".into(), json!(self.url));
        m.insert("hostname".into(), json!(self.hostname));
        m.insert("viewport".into(), json!({ "width": self.viewport.0, "height": self.viewport.1 }));
        m.insert("scroll".into(), json!({ "x": self.scroll.0, "y": self.scroll.1 }));
        m.insert("capturedAtMs".into(), json!(self.captured_at_ms));
        m.insert("producerTrust".into(), json!(self.producer_trust));
        m.insert(
            "producer".into(),
            json!({
                "name": self.producer_name,
                "version": self.producer_version,
                "engine": self.producer_engine,
                "scriptDigest": self.script_digest,
            }),
        );
        m.insert("redaction".into(), Value::Object(self.redaction.clone()));
        m.insert("fenced".into(), json!(self.fenced));
        m
    }
}

fn is_sha256_hex(s: &str) -> bool {
    s.len() == 64 && s.chars().all(|c| c.is_ascii_hexdigit())
}

/// A fenced capture is one the native side invalidated (navigation, reload, a
/// document generation bump, a viewport or scroll change). Refusing it is the
/// fence; reporting `superseded` keeps the reason visible.
pub fn fenced_failure(identity: &Identity) -> EngineFailure {
    EngineFailure::new(
        code::IDENTITY_SUPERSEDED,
        "the capture is fenced: navigation, reload, a document generation bump or a viewport/scroll change invalidated this snapshot",
    )
    .with_detail(json!({
        "captureId": identity.binding.capture_id,
        "documentGeneration": identity.binding.document_generation,
        "fenced": identity.fenced,
    }))
}
