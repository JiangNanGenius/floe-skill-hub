# Transport generation 2 official publication

The original official artifact and authenticated receipt came from
[signing run 42484186563](https://github.com/JiangNanGenius/floe-agent/actions/runs/42484186563),
workflow commit `ab48bbcec558f587e0574ac2d1f2c45e0d8769c1`, trusted tooling `75e0df40f0714d3faf9347d8844cec3f2b2d16ab`.
The payload's domain-separated signature and the receipt signature were
independently verified with `official-2026-09`, including all output hashes,
source/tree and current-generation baseline bindings.

- Audited data source: `0ff6a21157d9e7ddf3b6c98f8ad2d809bd0221a6`, tree `41a43e198a6aeb359e31c73a7fc04471d0746dfd`.
- Its immutable tag is `transport-v1-source-g2`; that unsigned signing input
  is kept outside main's publication history.
- Baseline: `d423eabd2e374973ad0f27d50f36e8a430437850`, generation 1.
- Payload SHA-256: `4b35f4167d4ecfa13a1726f2ce5667bfebe5d560a08e8cde5087a40370b11384`.
- Detached envelope SHA-256: `fa6525bff5e8b827e4a903b35103ada0c4726254d5cfdd8188df0ede91e839c1`.
- Issued `2026-11-08T13:16:22Z`; expires `2026-11-15T13:16:22Z`.

Only `releaseAssets=[ghfast.top,gh-proxy.com]` is enabled; rawFiles and Atom
roles retain their prior values. Admission uses complete anonymous downloads
by the actual website delivery caller on both transports, independently
checked against the official GitHub asset ID, URL, integer size and digest:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| Official ARM64 Linux VM asset 711699889 | 328697349 | `2b10d5ed5a2535a47f91c7a9a6d1d375033faeb1518a6711f060c31397df398e` |
| Android Alpha60 full ARM64 asset 723469213 | 164259143 | `66fb6a50e105f31a7801251dcd6b05850e976fe04194a589b91e9ebfa6c6d372` |

The VM's complete SHA-512 additionally matches its native image binding.
Partial/range samples are not the qualification proof. This is website
caller evidence, not a claim that a native App was integrated or installed.
GitHub stays primary; ordinary identity, hash and refusal boundaries stay
in force.

This first role transition uses seven-day validity so the separately
reviewed same-role renewal workflow can exercise a real due renewal to
fourteen days. No clock override or production fixture is used. The new
workflow remains disabled until its Root-owned installation and activation;
this receipt does not claim unattended renewal already ran.

The signed catalogs, review/package history and immutable publication ledger
are unchanged. Public read-back is recorded separately after pushing the
exact signed pair.
