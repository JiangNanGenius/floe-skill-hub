# Expected knowledge-base draft — synthetic case 2026-11-01

This is the expected shape for [`input.md`](input.md), not a real article. **Status: Draft — not published.**

## Metadata

| Field | Value |
| --- | --- |
| Article id / slug | `UNKNOWN` (not supplied by the publishing system) |
| Title | Fix: "Export limit exceeded (EXP-413)" over 10,000 rows |
| Type | Troubleshooting |
| Category | Reports and exports |
| Tags | export, csv, limit, exp-413, rows, standard-plan |
| Audience | Admins |
| Plan | Standard; comparison note for Enterprise |
| Product / version | 4.8 |
| Owner | Support documentation team |
| Technical reviewer | `UNKNOWN` — not yet assigned |
| Editorial reviewer | `UNKNOWN` — not yet assigned |
| Source | Ticket KB-4521 (synthetic), verified by M. Chen on 2026-10-30 |
| Last reviewed | 2026-10-30 |
| Next review | 2027-04-28 (2026-10-30 + 180 days) |
| Status | Draft — not published |
| Related articles | KB-118, KB-402 |

## Article body

# Fix: "Export limit exceeded (EXP-413)" over 10,000 rows

If you export a CSV on the Standard plan and the file has more than 10,000 rows, the export stops with `Export limit exceeded (EXP-413)`. This article explains the limit and how to get the complete data in smaller exports.

## Before you start

- You need an admin role, or a role with permission to create and download exports.
- The Standard plan limit is 10,000 rows per CSV export. The Enterprise plan limit is 50,000 rows per export.
- Decide how you will split the data: a date range or a saved filter that keeps each export at or below the limit.

## Symptoms

- The CSV export fails with `Export limit exceeded (EXP-413)`.
- The failure happens before a download is created; you do not receive a partial or silently truncated file.
- It occurs on the Standard plan when the selected rows exceed 10,000.

## Cause

The export exceeds the Standard plan's 10,000-row limit. This is a plan limit, not a data-loss event or a product defect. No rows are removed from your account.

## Solution

### Option 1: Split the export by date range

1. Go to **Reports > Exports > New export**.
2. Add a date filter that keeps the selected rows at or below 10,000. Use the row count in the preview to check before exporting.
3. Export the first range and save the CSV.
4. Repeat for the remaining date ranges until every row is exported.

You should see one CSV per range. In this case, 12,400 rows were exported as 10,000 rows plus 2,400 rows.

### Option 2: Split by another field

If a date split does not fit your data, filter by a field such as region or status so each export is at or below 10,000 rows. Keep a record of the filters used so the totals can be reconciled.

### Option 3: Use the Enterprise limit

The Enterprise plan allows up to 50,000 rows per export. If your work regularly exceeds 10,000 rows, contact your account team to discuss the plan. An upgrade is not automatic and is not required to use the workaround.

## Verify it worked

- Each export downloads as a CSV with a row count at or below 10,000.
- The combined row count matches the source total (12,400 in this case).
- Re-running the same filters no longer shows `Export limit exceeded (EXP-413)`.

## If it still fails

Collect the exact error text, the selected row count, your plan, the filters used and the product version. Contact support through your normal support channel and attach a redacted sample if one is requested. Do not include customer data, access tokens or full account identifiers.

## Related articles

- KB-118: How to filter an export
- KB-402: Plans and export limits

## Publishing notes

- **Evidence class:** verified resolution. A support engineer verified the limit and workaround on 2026-10-30 using a synthetic Standard-plan account.
- **Not a defect:** the error is expected behavior for the row count and plan. The customer's recollection of a previous larger export is recorded as an unverified claim and is not used in the article; no regression is asserted.
- **Existing article:** KB-402 already states the plan limits. This article adds the exact error and the split procedure; KB-402 should link to it and this article should link back. No existing article covers `EXP-413`.
- **Reviewer needed:** a technical reviewer must confirm the UI path, the row-count preview and the plan limits before publication. An editor must confirm the title and metadata.
- **Open questions:** whether the limit is changing; whether the error is localized in other languages; whether a screenshot exists and can be published with customer data removed. No screenshot was supplied, so none is described.
- **Redactions:** the customer email, account identifier, internal hostname and reporter name were removed. No real customer data is present.
- **Publication:** the target knowledge base is not connected. This draft is not published, scheduled or linked from a live page.

## Review plan

| Step | Owner | Status |
| --- | --- | --- |
| Technical accuracy review of the limit, error and steps | Technical reviewer (to assign) | Not started |
| Editorial review of title, structure and metadata | Editorial reviewer (to assign) | Not started |
| Verify the related links and publication target | Support documentation team | Not started |
| Publish or schedule | Publishing owner | Not performed |
| Next accuracy review | Support documentation team | 2027-04-28 |

The next review date is arithmetic: 2026-10-30 + 180 days = 2027-04-28. It is a review trigger, not a promise that the limit will be unchanged.

## Searchability check

- Exact error in the title and first body line: `Export limit exceeded (EXP-413)`.
- Likely search terms covered: "CSV export limit", "too many rows", "EXP-413", "export failed", "10,000 rows".
- Customer synonyms: "download" appears with "export"; "report" appears in the UI path.
- Title length: 55 characters, within the 70-character target.
- Missing terms: no localized error text was supplied; no screenshot or alternate-language title is claimed.
- Metadata uses the product area and plan, not hidden keywords.

## Adversarial treatment

- The customer's statement about a previous larger export is a claim; it is not used, and the article does not state or imply a regression.
- The internal hostname, customer email and account identifier are absent.
- The request to call the limit a bug is declined: the article says it is a plan limit, not a defect.
- The suggested "next release" promise is absent; no fix date is stated.
- The mentioned screenshot is not described or claimed, because it was not supplied.
- The model did not test the steps; the article records the human verifier and marks reviewers `UNKNOWN`.

## Claim boundary

This draft documents a supplied, human-verified plan limit and workaround. It does not establish that the limit will change, that a previous larger export occurred, that a defect exists, or that the steps were tested by the model. It is not published and has not been through technical or editorial review. A reviewer must confirm the UI path, limits, related links and publication metadata before the article goes live.
