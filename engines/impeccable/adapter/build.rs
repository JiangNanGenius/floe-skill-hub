//! Records the exact target triple cargo built this binary for, so a result
//! document always names the binary that produced it instead of the triple the
//! contract ships. A host build used for behavioural comparison must not claim
//! to be the guest artifact.

fn main() {
    let target = std::env::var("TARGET").unwrap_or_else(|_| "unknown-target".to_string());
    println!("cargo:rustc-env=FLOE_TARGET_TRIPLE={target}");
    println!("cargo:rerun-if-env-changed=TARGET");
    println!("cargo:rerun-if-changed=build.rs");
}
