# Statistics and scientific visualization 1.1.0 qualification

Both corrected packages retain their upstream pins and licenses. They use exact Debian 13 Linux/riscv64 dependency declarations and require App 1.7.60 or later; the native declaration/provisioning mechanism was separately qualified on 301/f130 and the relevant execution paths remain unchanged in the completed 302 source.

A real f130 Linux/riscv64 guest (Python 3.13.5, kernel 6.18.56, glibc 2.41) completed a focused own-closure check of both exact packages, after the original signed APT transaction and exact eleven-pin readback. Twenty outer checks passed. Statistics passed all nine full-verifier checks with the original 1e-8 relative tolerance, including assumption screens and diagnostic plots; its missing required matplotlib declaration and corresponding legacy request were corrected without changing numerical scripts, fixtures or tolerances. Visualization passed all seven full-verifier checks with required CJK rendering and real PNG/PDF/SVG outputs, plus eighteen unchanged encoded-density checks against a retained actual guest PNG and edge cases. Import-denial probes actually fired while each full verifier stayed usable with only its own legitimate closure.

The visualization comparator correction preserves raw measured DPI and accounts for integer metric pHYs precision only after a complete bounded pre-IDAT scan establishes an unambiguous valid chunk; both axes and strict non-PNG paths remain covered. Exporters and frozen golden inputs are unchanged. Original failed bootstrap/harness attempts and corrections are retained, rather than relabeled as successful. No App UI, Android device or physical-device acceptance is claimed by these component runs. No external model call was made.

Exact package bindings:

- statistical-analysis 1.1.0: ZIP `f5ae17ae9a7204cfe272ba8b32be8c98e7d719a920f2cd24c5ecd1be20aeaa97`, content `7017038cbc6d2e41e0a9b013fb69ed68b870d9f6061d4298bcd6f93ffe887ddf`.
- scientific-visualization 1.1.0: ZIP `ffd3936c0f6493de7f3613777fb88cc3fd518381c62ef7b55621222fcdf32383`, content `430f1ef3c005eaab1111368dcc854e1be6f3ce71df5e959bc47a3c102cb04751`.

Review signing and catalog publication are separate stages.
