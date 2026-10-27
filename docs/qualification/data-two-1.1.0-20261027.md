# EDA and Markdown conversion 1.1.0 qualification

Both packages retain upstream pins and licenses. Their executable scripts and synthetic fixtures are unchanged from the reviewed adaptations except for the manifest-derived verifier version label. The new declarations pin Debian 13 Linux/riscv64 dependencies; minimum App version is 1.7.60, whose native provisioning mechanism was separately qualified on source f1307f0d.

A real f130 Linux/riscv64 guest ran Python 3.13.5 on kernel 6.18.56 and glibc 2.41. The signed APT transaction and exact package read-back are retained privately. The complete EDA and Markdown verifiers passed; EDA's pandas/stdlib cross-check was consistent at tolerance 1e-9. Markdown conversion exercised XLSX, extractable-text PDF, CSV, TSV, JSON, TXT and PPTX; encrypted and scanned PDF refusals remained explicit. Native DOCX, protected-PDF and OCR execution were outside this component qualification.

A separate ten-case run restricted imports to each package's own declared closure plus the base environment. Both denial probes fired, both full verifiers passed, and the selected conversion/profile cases passed. Original failed harness attempts and their corrections are retained; they are not relabeled as successful. No external model call, App UI, Android device or physical-device acceptance is claimed here.

Exact package bindings:

- exploratory-data-analysis 1.1.0: ZIP `3ecb4b254cc361660ef1f3765d35ee90295420ea2fde3ae78de0cdb403e4140a`, content `b3a3944f0e22768d140e8801b68fca36b7897305de1c9dc1fa28181159324ad7`.
- markitdown 1.1.0: ZIP `54001b75a4782d17121aa78932e27aca3e30b497d238acc271b1076c823963b2`, content `46c7fd620183066f463228754897dd55820a971bd4c5f4b214a673d99bd981b3`.

Review signatures and catalog publication are separate stages.
