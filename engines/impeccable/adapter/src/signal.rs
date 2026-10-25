//! Cooperative cancellation.
//!
//! The guest job lifecycle can cancel a running scan. The rule pass itself is
//! synchronous upstream code with no cancellation points, so the flag is
//! checked between phases (read, parse, identity, facts, rule pass, write).
//! A process killed outright leaves no result document; the caller must treat
//! a missing result as a failure, never as a clean scan.

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

static CANCELLED: AtomicBool = AtomicBool::new(false);
static SIGNAL: AtomicU32 = AtomicU32::new(0);

pub fn cancel_requested() -> bool {
    CANCELLED.load(Ordering::SeqCst)
}

pub fn received_signal() -> u32 {
    SIGNAL.load(Ordering::SeqCst)
}

/// Test seam: mark cancellation without delivering a real signal.
#[cfg(test)]
pub fn request_cancel(signal_number: u32) {
    SIGNAL.store(signal_number, Ordering::SeqCst);
    CANCELLED.store(true, Ordering::SeqCst);
}

#[cfg(unix)]
pub fn install_handlers() {
    use libc::{c_int, c_void, sighandler_t, SIGINT, SIGTERM};
    unsafe extern "C" fn handler(signum: c_int) {
        // Signal-handler safe: only atomic stores, no allocation or locking.
        SIGNAL.store(signum as u32, Ordering::SeqCst);
        CANCELLED.store(true, Ordering::SeqCst);
    }
    unsafe {
        let handler_fn: sighandler_t = handler as *const c_void as sighandler_t;
        libc::signal(SIGTERM, handler_fn);
        libc::signal(SIGINT, handler_fn);
    }
}

#[cfg(not(unix))]
pub fn install_handlers() {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_cancel_request_is_visible_to_the_phase_checkpoints() {
        assert!(!cancel_requested(), "a fresh process starts uncancelled");
        request_cancel(15);
        assert!(cancel_requested());
        assert_eq!(received_signal(), 15);
    }
}
