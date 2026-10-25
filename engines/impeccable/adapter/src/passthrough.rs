//! The offline upstream verbs the Floe engine keeps: `detect`, `context` and
//! `ignores`.
//!
//! What is deliberately **not** wired here: the URL/CDP engine (no Chromium
//! dependency for a native page scan), the skill install/update verbs (Floe
//! Skill Hub owns installation and updates), telemetry, image generation, the
//! decision-page server, live mode, the editor hooks and the native capture
//! service. The router in `main.rs` refuses each of those with a message that
//! names the Floe owner instead of failing obscurely.

use impeccable_common::Io;
use impeccable_detect::engines::{EngineError, UrlScan};
use impeccable_detect::{Engines, ScanOptions, UrlEngine};
use impeccable_core::findings::Finding;

/// The static HTML engine the pinned upstream binary registers.
pub fn html_engine() -> &'static impeccable_html::StaticHtmlEngine {
    static HTML: impeccable_html::StaticHtmlEngine = impeccable_html::StaticHtmlEngine {
        static_rule_pack: None,
    };
    &HTML
}

/// Floe has no Chromium and opens no DevTools endpoint. A URL target is a
/// refusal that says what to do instead, not a silent empty result.
pub struct FloeUrlEngine;

impl UrlEngine for FloeUrlEngine {
    fn detect_url(&self, url: &str, _options: &ScanOptions) -> Result<Vec<Finding>, EngineError> {
        Err(EngineError::new(format!(
            "URL scanning is not available in the Floe engine ({url}). \
             Floe scans a page through the native design capture: take a snapshot with the \
             controlled WebKit producer and run `floe-impeccable snapshot-scan`. \
             No Chromium is installed or launched and no DevTools endpoint is opened."
        )))
    }

    fn detect_url_scan(&self, url: &str, options: &ScanOptions) -> Result<UrlScan, EngineError> {
        Err(match self.detect_url(url, options) {
            Err(e) => e,
            Ok(_) => EngineError::new("URL scanning is not available in the Floe engine"),
        })
    }

    fn detect_cdp_scan(
        &self,
        _endpoint: &impeccable_detect::cdp_endpoint::CdpEndpoint,
        _target: Option<&str>,
        _options: &ScanOptions,
    ) -> Result<UrlScan, EngineError> {
        Err(EngineError::new(
            "--cdp is not available in the Floe engine: attaching to a running app through a \
             DevTools endpoint is deliberately not supported. Use the native design capture and \
             `floe-impeccable snapshot-scan`.",
        ))
    }
}

pub fn engines() -> Engines<'static> {
    Engines {
        html: html_engine(),
        url: Some(&FloeUrlEngine),
    }
}

pub fn run_detect(args: &[String], io: &mut Io) -> i32 {
    impeccable_detect::run_detect(args, io, &engines())
}

pub fn run_ignores(args: &[String], io: &mut Io) -> i32 {
    impeccable_detect::run_ignores(args, io)
}

pub fn run_context(args: &[String], io: &mut Io) -> i32 {
    impeccable_context::run_context(args, io)
}

pub fn run_detect_csp(args: &[String], io: &mut Io) -> i32 {
    impeccable_context::run_detect_csp(args, io)
}

pub fn run_palette(args: &[String], io: &mut Io) -> i32 {
    impeccable_context::run_palette(args, io)
}

pub fn run_signals(args: &[String], io: &mut Io) -> i32 {
    impeccable_context::run_signals(args, io)
}

/// Verbs the upstream CLI routes to a network, server, live-rewrite, hook or
/// Chromium/CDP path. Floe owns those concerns, so each one is refused with the
/// reason rather than being linked into the engine at all.
pub fn refused_reason(verb: &str) -> Option<&'static str> {
    let reason = match verb {
        "skills" | "help" | "install" | "link" | "update" | "check" => {
            "Skill installation and updates are owned by the Floe Skill Hub (signed catalog, \
             digest-bound engine). This engine never downloads, installs or updates anything."
        }
        "telemetry" => {
            "Telemetry is disabled in the Floe engine: no upstream endpoint is contacted and the \
             build carries no TLS stack."
        }
        "generate-image" | "concept-seed" | "serve-question" => {
            "This verb needs the upstream network service or a local decision-page server; neither \
             is part of the Floe v1 engine."
        }
        "component-review" | "capture-server" | "font-match" | "build-phase" => {
            "This verb needs the upstream Chromium/CDP capture service. Floe uses the controlled \
             native WebKit design capture and `snapshot-scan` instead."
        }
        "hook" | "hook-before-edit" | "hooks" | "hook-admin" => {
            "Editor hooks are not part of the Floe v1 engine."
        }
        "doctor" | "pin" | "surface-brief" | "critique-storage" | "embed-prompt" => {
            "This verb is not part of the Floe v1 engine surface (context, detect, ignores, \
             detect-csp, palette, signals and snapshot-scan are)."
        }
        "init" => {
            "\"init\" is not an engine command. Install skills from the Floe Skill Hub instead."
        }
        _ => return None,
    };
    Some(reason)
}

pub fn is_live_verb(verb: &str) -> bool {
    verb.starts_with("live")
}
