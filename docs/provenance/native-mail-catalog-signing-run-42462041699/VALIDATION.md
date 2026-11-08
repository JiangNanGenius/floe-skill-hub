# Native mail Skill publication validation

New offer: `floe-native-mail` 1.0.0, iOS only, minimum App 1.7.79.
Audited source X: `604b51de96a92e16a1720bcd35f10771b6a7e984`.
Previous published main: `270b79617faffa94b321965c77d3c123777b09c1`.

The deterministic 22,661-byte instruction package has SHA-256
`7481b5003ab5c126eafa7fe28a4b610008497bd6659077519d040ae75aba1018`.
Its seven native tool names were checked against immutable App tag v1.7.79.
The package contains no scripts or native executables and claims no new
live-account or App runtime qualification. All declared grants are bound by
the approved review. The record and four feed views verify under the existing
`official-2026-09` trust key; all 312 signing outputs were checked against the
authenticated receipt, and historical offer digests remain unchanged.

The full `scripts/check_catalog.py` run reports three existing upstream-pin
baseline mismatches for business-pulse, invoice-chase and payroll-prep. The
same three failures were reproduced using the unchanged registry and pin
document at the previous published main above. This change adds no pin
mismatch and does not alter those entries or their pin policy. Package,
review/signature, feed binding and publication-immutability checks for the
new native-mail offer passed. The global check is not reported as green.
