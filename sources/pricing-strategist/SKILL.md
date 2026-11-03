---
name: pricing-strategist
description: "Use when designing or revisiting product pricing — selecting a pricing model (subscription seat-based, usage-based, value-based, freemium, or hybrid), running Van Westendorp Price Sensitivity Meter analysis on WTP survey data, or designing Good/Better/Best packaging tiers. Recommends a model and a price range with trade-offs, never a single number. For Commercial leads, Product Marketing, and CMOs at the pricing-design moment — not deal-by-deal discounting, not brand positioning."
---

# pricing-strategist

## Floe runtime adaptation (read first)

- Adapted for Floe from the MIT-licensed upstream skill recorded in `references/PROVENANCE.md`; the pricing-model, Van Westendorp PSM and Good/Better/Best frameworks and the deterministic calculations are preserved. Per-file changes are recorded in `references/ADAPTATION-NOTES.md`.
- The bundled Python scripts run **only** in the task's resolved Linux environment through `exec.shell`, with explicit task/workspace/environment ownership and the session → project → shared → base write-layer resolution. There is no host interpreter path, no language alias, no `python.local` mode and no self-install.
- All scripts are standard-library only (`pythonPackages: []`). They make **no network, model, provider or SaaS call**; the reference documents contain reading links but the tools never fetch them.
- Input is one user-supplied `.json` file inside an explicit `--root` workspace directory. Symlinks, hard links, directories, URLs, traversal, non-UTF-8 content, duplicate JSON keys, non-finite numbers, oversized files and out-of-range values are refused with exit code 2. Reports go to **stdout only**; the scripts never create or overwrite files.
- Execution evidence for this build: the shipped 12-check verifier and the three fixture CLIs passed in a real Linux/riscv64 component guest (TinyEMU, kernel 6.18.56, CPython 3.13.5; standard-library-only `-S` closure confirmed with byte-identical output). The record is in `references/PROVENANCE.md`. That is component-guest evidence only — it is not App install, Simulator, physical-device, Android, remote-Linux, signing or publication proof, and it says nothing about market validity. Host runs are developer/static evidence only; synthetic fixtures are not market research and `--sample` output is not a real pricing recommendation.

## Purpose

Help Commercial, Product Marketing, and CMO functions answer three questions at the pricing-design moment:

1. **Which pricing model fits this product + customer + market?** (subscription seat-based, usage-based, value-based, freemium, hybrid)
2. **What does the customer actually pay before it feels too expensive?** (Van Westendorp PSM on WTP survey responses)
3. **How should we package this into tiers?** (Good / Better / Best — with anti-pattern detection)

The skill recommends **a model and a range**. The human picks the number, owns the trade-offs, and runs the GTM.

## When to use

- Launching a new SaaS / API / AI tool and choosing the first pricing model
- Revisiting pricing after 18+ months of GTM data (model shift, not just price increase)
- Designing or redesigning tier packaging (Good/Better/Best, Bronze/Silver/Gold)
- You have Van Westendorp survey data and want the optimal price range
- A board / exec is asking "what should we charge?" and you need the structured answer
- You suspect your packaging has anti-patterns (decoy tier, feature dump, no upgrade trigger)

**Do not use for:**
- Per-deal discount approval → `deal-desk`
- Strategic CMO positioning, brand, category creation → `c-level-advisor/cmo-advisor`
- Whole-company revenue strategy → `c-level-advisor/cro-advisor`
- Technical-sale enablement → `business-growth/sales-engineer`

## Workflow

### Step 1 — Assess customer context

Fill `assets/pricing_brief_template.md` (≈ 20 min). Capture: industry, deal size avg, customer count, value drivers, adoption curve, consumption pattern (seat / usage / value / hybrid), competitor models.

### Step 2 — Pick the pricing model

Run `python3 scripts/pricing_model_picker.py --input brief.json --profile saas --output markdown --root .`. Output ranks 5 models by fit-score 0-100 with trade-offs. Decision logic is deterministic: low usage variance + high seat-attach → subscription wins; power-law usage + variable customer value → usage-based wins.

### Step 3 — Validate WTP with Van Westendorp PSM

If you have survey data (all 4 questions per respondent: too cheap / bargain / getting expensive / too expensive), run `python3 scripts/wtp_analyzer.py --input survey.json --output markdown --root .`. Output: 4 intersection points (OPP, IDP, PMC, PME) and the Range of Acceptable Prices.

A respondent with a missing or non-numeric answer is refused rather than silently counted as zero. Inconsistent ordering (`too_cheap ≤ bargain ≤ getting_expensive ≤ too_expensive`) is reported as a warning so the respondent can be screened before reporting.

PSM gives a **range**, not the price. See `references/van_westendorp_methodology.md` for common misinterpretations.

### Step 4 — Design packaging

Run `python3 scripts/packaging_designer.py --input features.json --profile saas --output markdown --root .`. Output: 3-tier Good/Better/Best assignment with anti-pattern flags (decoy tier, feature dump, no upgrade trigger, Bronze loss leader, Enterprise no-anchor).

### Step 5 — Decide

Take model + range + packaging into the pricing committee. Skill does not commit the number — you do.

## Scripts

- `scripts/_pricing_io.py` — Floe-added bounded root-confined JSON input, validation and stdout helpers (no network, no writes, no subprocess).
- `scripts/pricing_model_picker.py` — 5-model fit scorer (subscription / usage / value / freemium / hybrid)
- `scripts/wtp_analyzer.py` — Van Westendorp PSM implementation
- `scripts/packaging_designer.py` — Good/Better/Best tier designer with anti-pattern detection
- `scripts/verify_pricing_skills.py` — Floe-added deterministic offline self-check over synthetic fixtures

All scripts: standard library only. `--help` and `--sample` work on all four. A run reads at most 2 MiB of JSON, at most 20,000 PSM respondents, at most 2,000 features and at most 50 segments. These caps bound runtime; they are not a claim that a sample of that size is statistically valid.

## Quick example

```bash
# Emits a scored 5-model pricing-fit recommendation for the built-in synthetic example.
# Run from the installed package root inside the task's Linux environment.
python3 scripts/pricing_model_picker.py --sample
```

## References

- `references/saas_pricing_canon.md` — Skok, Tunguz, Campbell, Ramanujam, BVP, Shevlin, Stanford GSB
- `references/van_westendorp_methodology.md` — original 1976 paper, NMS refinement, Conjoint.ly, Sawtooth, ESOMAR, Lipovetsky, Decision Analyst
- `references/packaging_anti_patterns.md` — ProfitWell, OpenView, BVP vertical SaaS, Ramanujam, Poyar, SaaS Capital
- `references/ADAPTATION-NOTES.md` — Floe keep/modify/add/exclude record
- `references/PROVENANCE.md` and `references/licenses/` — upstream pin, license and file inventory

## Assumptions

- Pricing decisions are joint: Commercial owns the model + tier shape, Product owns the features-per-tier, Finance owns the discount envelope, Legal owns the contract.
- Van Westendorp PSM is a **directional** tool. N ≥ 30 minimum, N ≥ 100 preferred. Below 30, the script emits a sample-size warning.
- "Value-based pricing" requires a measurable customer value driver (revenue lift, cost saved, time recovered). If you can't measure it, don't pick value-based.
- Industry profiles tune defaults — they don't override your data.
- This is a decision-support skill, not a price oracle. Output is a model + range, never the number.
- All four PSM answers are required per respondent. A partial row is a data-quality error, not a zero response.

## Anti-patterns

- **Recommending a specific number.** This skill emits a model and a range. Final price is a human commercial decision involving deal-desk policy, competitive intel, and strategic intent that this skill cannot know.
- **Using PSM with N < 30.** Statistical noise dominates. The script warns; respect the warning.
- **Treating PSM as "the price."** PSM gives a Range of Acceptable Prices (RAP) and an Optimal Price Point (OPP). Test the range in market, don't anchor on a single intersection.
- **Picking value-based pricing without a measurable value metric.** Without instrumentation to show customer ROI, value-based collapses into "whatever they'll pay" — which is just bad usage-based pricing.
- **Designing tiers before picking a model.** Tier structure depends on the model. Run pricing_model_picker first.
- **Packaging "feature dumps" into the Best tier.** If Best has 3x the features for 2x the price, customers buy Better and never upgrade. See `packaging_anti_patterns.md`.
- **Hidden usage-based pricing inside subscription tiers.** "Up to 100k API calls/mo, then $X per 1k" disguised as a "Pro tier" is two pricing models in one. Customers notice. Pick one.
- **Confusing this skill with deal-desk.** Pricing strategy = the menu. Deal-desk = approving discounts off the menu. Different decision, different cadence, different owner.
- **Treating `--sample` output as market evidence.** The built-in data is synthetic. It demonstrates the tool, not a customer's willingness to pay.
- **Running these scripts on the native host or through a language alias.** That bypasses the declared runtime and is not Floe execution evidence.

## Distinct from

- **deal-desk** — per-deal discount approval, MEDDIC, deal scoring. Operates daily on existing pricing.
- **c-level-advisor/cmo-advisor** — strategic positioning, brand, category. Pricing strategist consumes positioning as input, doesn't generate it.
- **c-level-advisor/cro-advisor** — full-funnel revenue strategy, comp plans, territory design. Pricing strategist is one input to CRO.
- **business-growth/sales-engineer** — technical sale, POC scoping. Sales engineering operates after pricing is set.

## Forcing-question library (Matt Pocock grill discipline)

Walk these one at a time in conversation; do not bundle them. Recommended answer + canon citation per question.

1. **"Is your customer paying for outcomes, seats, or usage?"**
   Recommended: outcomes (value-based) if you can measure them; usage if marginal cost is variable; seats only if usage is roughly flat per user.
   Canon: Ramanujam 2016 (*Monetizing Innovation*) — Mistake #1 of 9: seat-based pricing on a usage-variable product caps TAM at ~20% of WTP.

2. **"Do you have a measurable value metric, or are you guessing?"**
   Recommended: instrument the value metric BEFORE going to market with value-based pricing.
   Canon: Patrick Campbell / ProfitWell research — value-based without instrumentation collapses into bad usage-based pricing.

3. **"What's the variance in customer usage across your top decile vs. median?"**
   Recommended: variance > 10x → usage-based wins; variance < 3x → subscription wins; in between → hybrid with usage overage.
   Canon: Kyle Poyar (*Growth Unhinged*) — high-variance products lose 60%+ of revenue on flat-rate plans.

4. **"What's your competitor's pricing model, and why are you choosing the same or different?"**
   Recommended: surface the differentiation hypothesis explicitly. Identical pricing = identical value claim.
   Canon: David Skok (*For Entrepreneurs*) — pricing is a positioning signal.

5. **"What sample size do you have for WTP analysis, and is it segmented?"**
   Recommended: N≥30 per segment for PSM, N≥100 for conjoint.
   Canon: van Westendorp 1976 / Sawtooth Software methodology — sub-30 PSM is statistical noise.

6. **"What's the ONE feature that forces a tier upgrade?"**
   Recommended: every Better and Best tier needs a single non-negotiable upgrade trigger.
   Canon: Ramanujam (*Monetizing Innovation*) — Mistake #4: tiers with no clear differentiator make 70% of customers pick the cheapest.

Walk depth-first. Lock 1-3 before opening 4-6. After all 6 are answered, invoke `pricing_model_picker.py` → `wtp_analyzer.py` → `packaging_designer.py` in sequence.

## Environment verification

Run the shipped deterministic self-check inside the resolved Linux environment before using real data:

```bash
python3 scripts/verify_pricing_skills.py
```

Expected: JSON `"ok": true`, exit 0, 12 checks and 0 failures. It covers scoring/tier invariants, exact PSM equivalence against an independent reference, malformed and malicious inputs, path gates, stdout-only behavior and deterministic output. A green result proves the scripts on that interpreter; it does not prove market validity. This build's real Linux/riscv64 component-guest qualification is recorded in `references/PROVENANCE.md`.
