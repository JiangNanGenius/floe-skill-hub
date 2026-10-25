//! Facts: the native answers to an engine `Needs`.
//!
//! Three gates run before any answer reaches the rule engine, because a wrong
//! answer is worse than no answer — it turns a missing measurement into a
//! confident finding:
//!
//! 1. **binding**: the facts must carry the same task/session/tab/document/
//!    capture/generation as the snapshot being scanned. Facts from another tab
//!    or a superseded capture are rejected, never merged.
//! 2. **exact point identity**: the upstream hit-test table is keyed by the
//!    IEEE-754 double *bits* of `(x, y)`. When the producer echoes `xBits` /
//!    `yBits`, they are verified against the decimal values; a mismatch means
//!    the point was altered in transit and the whole file is refused.
//! 3. **unanswerable points stay unanswered**: a hit the producer could not
//!    answer is *not* fed to the engine as `top: 0, stack: []`, which upstream
//!    reads as the definitive answer "nothing there". It is held back and
//!    reported, so a missing measurement can never become a clean result.

use serde_json::{json, Map, Value};

use crate::error::{code, EngineFailure};
use crate::identity::Binding;

/// One hit-test answer as the producer sent it.
#[derive(Debug, Clone)]
pub struct HitAnswer {
    pub x: f64,
    pub y: f64,
    pub x_bits: Option<u64>,
    pub y_bits: Option<u64>,
    pub top: u32,
    pub stack: Vec<u32>,
    pub unanswerable: bool,
    pub reason: Option<String>,
}

/// One scroll-probe answer (`shownOnScroll`).
#[derive(Debug, Clone)]
pub struct ScrollAnswer {
    pub el: u32,
    pub shown: bool,
}

#[derive(Debug, Clone, Default)]
pub struct FactsFile {
    pub binding: Option<Binding>,
    pub fenced: bool,
    pub hits: Vec<HitAnswer>,
    pub scroll: Vec<ScrollAnswer>,
    pub source: String,
}

impl FactsFile {
    pub fn parse(raw: &str, source: &str) -> Result<FactsFile, EngineFailure> {
        let v: Value = serde_json::from_str(raw).map_err(|e| {
            EngineFailure::new(code::FACTS_PARSE, format!("{source}: facts are not valid JSON: {e}"))
        })?;
        FactsFile::from_value(&v, source)
    }

    pub fn from_value(v: &Value, source: &str) -> Result<FactsFile, EngineFailure> {
        // The binding is required: a facts file that cannot prove which capture
        // it answers is refused rather than trusted.
        let binding = Binding::parse_required(v).map_err(|missing| {
            EngineFailure::new(
                code::FACTS_BINDING_MISMATCH,
                format!("{source}: facts are missing required binding fields"),
            )
            .with_detail(json!({ "missing": missing }))
        })?;

        let fenced = v["fenced"].as_bool().unwrap_or(false);

        let mut hits = Vec::new();
        for (i, hit) in v["hits"].as_array().cloned().unwrap_or_default().iter().enumerate() {
            let x = hit["x"].as_f64().ok_or_else(|| {
                EngineFailure::new(code::FACTS_PARSE, format!("{source}: hits[{i}].x must be a number"))
            })?;
            let y = hit["y"].as_f64().ok_or_else(|| {
                EngineFailure::new(code::FACTS_PARSE, format!("{source}: hits[{i}].y must be a number"))
            })?;
            let x_bits = read_bits(&hit["xBits"]);
            let y_bits = read_bits(&hit["yBits"]);
            if let Some(expected) = x_bits {
                if expected != x.to_bits() {
                    return Err(EngineFailure::new(
                        code::FACTS_BITS_MISMATCH,
                        format!("{source}: hits[{i}].xBits does not match the decimal x; the point was altered in transit"),
                    )
                    .with_detail(json!({ "index": i, "xBits": expected.to_string(), "xValueBits": x.to_bits().to_string() })));
                }
            }
            if let Some(expected) = y_bits {
                if expected != y.to_bits() {
                    return Err(EngineFailure::new(
                        code::FACTS_BITS_MISMATCH,
                        format!("{source}: hits[{i}].yBits does not match the decimal y; the point was altered in transit"),
                    )
                    .with_detail(json!({ "index": i, "yBits": expected.to_string(), "yValueBits": y.to_bits().to_string() })));
                }
            }
            let stack = hit["stack"]
                .as_array()
                .map(|a| a.iter().filter_map(|n| n.as_u64().map(|n| n as u32)).collect())
                .unwrap_or_default();
            hits.push(HitAnswer {
                x,
                y,
                x_bits,
                y_bits,
                top: hit["top"].as_u64().unwrap_or(0) as u32,
                stack,
                unanswerable: hit["unanswerable"].as_bool().unwrap_or(false),
                reason: hit["reason"].as_str().map(str::to_string),
            });
        }

        let mut scroll = Vec::new();
        for (i, probe) in v["shownOnScroll"].as_array().cloned().unwrap_or_default().iter().enumerate() {
            let el = probe["el"].as_u64().ok_or_else(|| {
                EngineFailure::new(code::FACTS_PARSE, format!("{source}: shownOnScroll[{i}].el must be an element id"))
            })? as u32;
            let shown = probe["shown"].as_bool().ok_or_else(|| {
                EngineFailure::new(code::FACTS_PARSE, format!("{source}: shownOnScroll[{i}].shown must be a boolean"))
            })?;
            scroll.push(ScrollAnswer { el, shown });
        }

        Ok(FactsFile { binding: Some(binding), fenced, hits, scroll, source: source.to_string() })
    }

    /// The answers that may reach the engine: bound to `expected`, not fenced,
    /// and actually answered.
    pub fn into_engine_facts(
        self,
        expected: &Binding,
    ) -> Result<(impeccable_core::browser::snapshot::Facts, FactsAccounting), EngineFailure> {
        let binding = self.binding.clone().unwrap_or_default();
        let differ = binding.matches(expected);
        if !differ.is_empty() {
            return Err(EngineFailure::new(
                code::FACTS_BINDING_MISMATCH,
                format!(
                    "{}: facts are bound to a different capture; refusing to merge answers from another task/session/tab/document",
                    self.source
                ),
            )
            .with_detail(json!({ "differingFields": differ, "source": self.source })));
        }
        if self.fenced {
            return Err(EngineFailure::new(
                code::IDENTITY_SUPERSEDED,
                format!("{}: the facts are marked fenced; the capture they answer was invalidated", self.source),
            )
            .with_detail(json!({ "captureId": binding.capture_id })));
        }

        let mut facts = impeccable_core::browser::snapshot::Facts::default();
        let mut unanswerable: Vec<Value> = Vec::new();
        for hit in &self.hits {
            if hit.unanswerable {
                let mut entry = Map::new();
                entry.insert("x".into(), json!(hit.x));
                entry.insert("y".into(), json!(hit.y));
                entry.insert("xBits".into(), json!(hit.x_bits.map(|b| b.to_string())));
                entry.insert("yBits".into(), json!(hit.y_bits.map(|b| b.to_string())));
                if let Some(reason) = &hit.reason {
                    entry.insert("reason".into(), json!(reason));
                }
                entry.insert("source".into(), json!(self.source));
                unanswerable.push(Value::Object(entry));
                continue;
            }
            facts.hits.push(impeccable_core::browser::snapshot::HitTest {
                x: hit.x,
                y: hit.y,
                top: hit.top,
                stack: hit.stack.clone(),
            });
        }
        for probe in &self.scroll {
            facts.shown_on_scroll.push(impeccable_core::browser::snapshot::ScrollShown {
                el: probe.el,
                shown: probe.shown,
            });
        }
        let accounting = FactsAccounting {
            supplied: self.hits.len(),
            answered: facts.hits.len(),
            unanswerable,
            scroll_answers: facts.shown_on_scroll.len(),
            source: self.source.clone(),
        };
        Ok((facts, accounting))
    }
}

/// What one facts file contributed, for the receipt and diagnostics.
#[derive(Debug, Clone, Default)]
pub struct FactsAccounting {
    pub supplied: usize,
    pub answered: usize,
    pub unanswerable: Vec<Value>,
    pub scroll_answers: usize,
    pub source: String,
}

fn read_bits(v: &Value) -> Option<u64> {
    match v {
        Value::Number(n) => n.as_u64(),
        Value::String(s) => s.parse::<u64>().ok(),
        _ => None,
    }
}

impl Binding {
    /// Parse the binding out of a facts document, listing what is missing.
    pub fn parse_required(v: &Value) -> Result<Binding, Vec<String>> {
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
}

impl Default for Binding {
    fn default() -> Self {
        Binding {
            task_id: String::new(),
            session_id: String::new(),
            tab_id: String::new(),
            document_id: String::new(),
            capture_id: String::new(),
            document_generation: 0,
        }
    }
}
