//! `floe-impeccable`: the Floe engine binary.
//!
//! A verb router over the pinned upstream rule engine, in the shape of the
//! upstream `impeccable` binary but with the Floe-owned paths removed rather
//! than silently present:
//!
//! * `snapshot-scan` — the file-based rule pass with the Needs/facts fixpoint
//!   and the coverage receipt (the v1 design-scan contract);
//! * `contract`, `snapshot-schema`, `engine-probe` — the frozen contract and
//!   the launcher handshake;
//! * `detect`, `context`, `ignores`, `detect-csp`, `palette`, `signals` — the
//!   offline upstream static source/HTML and context verbs;
//! * everything that needs Chromium/CDP, the network, a local server, live
//!   rewrite, editor hooks or the upstream installer is refused with a message
//!   that names the Floe owner.
//!
//! Exit codes for `snapshot-scan` are the contract's: 0 clean, 2 findings,
//! 3 needs-facts, 4 inconclusive coverage, 1 failure. A missing measurement is
//! never reported as a clean scan.

mod contract;
mod coverage;
mod error;
mod facts;
mod identity;
mod passthrough;
mod scan;
mod signal;

use std::io::Write;

use impeccable_common::Io;

use crate::error::code;

pub const FLOE_USAGE: &str = "Usage: floe-impeccable <verb> [options]

Floe engine over the pinned pbakaus/impeccable rule core. No network, no
Chromium, no DevTools endpoint, no model-authored JavaScript.

Design scan (the v1 snapshot contract):
  snapshot-scan --snapshot <path> [--identity <path>] [--facts <path>]...
                [--config <path>] [--out <path>] [--round <n>]
  contract                     Print the frozen v1 snapshot/facts contract JSON
  snapshot-schema              Print the producer-facing capture contract

Static source and context scans (offline upstream verbs):
  detect [file-or-dir...]      Scan markup and source for design anti-patterns
  context [--target <path>]    Project context brief (PRODUCT.md, DESIGN.md, ...)
  ignores                      Manage detector ignore rules, files and values
  detect-csp | palette | signals

Identity:
  engine-probe                 Launcher handshake
  --version | -v               Engine and adapter version
  --help | -h                  This help

Exit codes (snapshot-scan): 0 clean, 2 findings, 3 needs-facts,
4 inconclusive coverage, 1 failure. Exit codes (detect): upstream semantics,
0 clean, 2 findings, 1 operational failure.
";

fn main() {
    signal::install_handlers();
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut io = Io::stdio();
    let exit = run(&args, &mut io);
    let _ = io.stdout.flush();
    let _ = io.stderr.flush();
    std::process::exit(exit);
}

/// The verb router. Kept separate from `main` so tests can drive it with a
/// captured `Io` and assert stdout, stderr and the exit code.
pub fn run(args: &[String], io: &mut Io) -> i32 {
    let Some(verb) = args.first().map(String::as_str) else {
        io.out(FLOE_USAGE);
        return 0;
    };
    let rest: Vec<String> = args[1..].to_vec();
    match verb {
        "--help" | "-h" | "help" => {
            io.out(FLOE_USAGE);
            0
        }
        "--version" | "-v" => {
            io.out(&format!("{}\n", contract::version_string()));
            0
        }
        "engine-probe" => {
            io.out(&contract::probe_line());
            0
        }
        "contract" => {
            io.out(contract::CONTRACT_JSON);
            if !contract::CONTRACT_JSON.ends_with('\n') {
                io.out("\n");
            }
            0
        }
        "snapshot-schema" => {
            match serde_json::to_string_pretty(&contract::snapshot_schema_document()) {
                Ok(text) => {
                    io.out(&format!("{text}\n"));
                    0
                }
                Err(e) => {
                    io.err(&format!("cannot serialize the schema document: {e}\n"));
                    1
                }
            }
        }
        "snapshot-scan" => {
            let strings: Vec<String> = rest.clone();
            match scan::parse_args(&strings) {
                Ok(parsed) => {
                    let outcome = scan::run(parsed);
                    // The result document is written to --out (or printed by the
                    // scan itself when no --out was given); stderr carries a
                    // one-line summary a caller can log without page content.
                    io.err(&format!(
                        "floe-impeccable: snapshot-scan status={} verdict={} exit={}\n",
                        outcome.document["status"].as_str().unwrap_or("unknown"),
                        outcome.document["verdict"].as_str().unwrap_or("unknown"),
                        outcome.exit
                    ));
                    outcome.exit
                }
                Err(failure) => refuse(io, &failure),
            }
        }
        "detect" => passthrough::run_detect(&rest, io),
        "ignores" | "ignore" => passthrough::run_ignores(&rest, io),
        "context" => passthrough::run_context(&rest, io),
        "detect-csp" => passthrough::run_detect_csp(&rest, io),
        "palette" => passthrough::run_palette(&rest, io),
        "signals" | "context-signals" => passthrough::run_signals(&rest, io),
        v if passthrough::is_live_verb(v) => refuse_verb(
            io,
            v,
            "Live mode rewrites the page through a local server and is not part of the Floe v1 engine.",
        ),
        v => {
            if let Some(reason) = passthrough::refused_reason(v) {
                return refuse_verb(io, v, reason);
            }
            // Upstream routes a path-shaped first argument to `detect`; keep
            // that shorthand so `floe-impeccable src/` behaves the same way.
            if impeccable_detect::looks_like_detect_target(v, &io.cwd.to_string_lossy()) {
                return passthrough::run_detect(args, io);
            }
            io.err(&format!(
                "Unknown command: \"{v}\"\n\nTo see the supported verbs, run:\n  floe-impeccable --help\n"
            ));
            1
        }
    }
}

fn refuse(io: &mut Io, failure: &error::EngineFailure) -> i32 {
    io.err(&format!("Error [{}]: {}\n", failure.code, failure.message));
    if failure.code == code::USAGE {
        // A usage message is help, not a diagnostic dump.
        return 1;
    }
    if !failure.detail.is_null() {
        if let Ok(detail) = serde_json::to_string(&failure.detail) {
            io.err(&format!("Detail: {detail}\n"));
        }
    }
    1
}

fn refuse_verb(io: &mut Io, verb: &str, reason: &str) -> i32 {
    io.err(&format!("Error [verb-unavailable]: \"{verb}\" is not available in the Floe engine. {reason}\n"));
    1
}
