# Evaluation Protocol

**Status: LOCKED 2026-09-02, before any M-tier model was trained. Unchanged.**

> **Scope note, 2026-09-08.** This protocol governs the **trading comparison only**. After
> the pivot (`DECISIONS.md` #25) that comparison is no longer the project's primary result;
> it is reported as appendix evidence, and its `no_claim` outcome is the measured reason the
> agent declines to rank strategies. **Nothing in this document is amended, because amending
> a pre-registration after seeing its result is exactly what it exists to prevent.** The
> inspector's evaluation protocol is a separate document.

This document fixes how the primary comparison is decided, so the decision rule
cannot be selected after the results are known. Outline §17 criterion 4 requires
a prespecified risk-adjusted metric; this document is that prespecification.
Outline §20.2 harm 3 lists it as a guardrail.

Supporting arithmetic: `scripts/analysis/fold_power.py`.

**Change rule.** Any change after the first M-tier experiment has run requires a
decision-log entry and must be disclosed in the final technical report.

**Amendment 1, 2026-09-05**, after the first graded run: §3 records how the
pairing is implemented, and §5 records the realised correlation and detection
floor, which falsify that section's assumed table. Neither changes the decision
rule. Read §5 before quoting any figure from it.

---

## 1. The primary comparison

| Field | Value |
|---|---|
| Systems compared | M2 versus B2 |
| Metric | Annualised Sharpe ratio, net of costs |
| Asset class | Equities only (SPY, SIP feed) |
| Direction | ΔSharpe = Sharpe(M2) minus Sharpe(B2) |

Only this comparison is primary.

**Why Sharpe rather than maximum drawdown.** The Outline originally specified
"Sharpe or maximum drawdown", which permits two attempts at one claim. One
metric is now fixed. Maximum drawdown is a single-path extremum: its sampling
distribution is wide, it depends strongly on record length, and it has no clean
paired estimator. Selecting it as primary would give a lower-powered test.
Maximum drawdown is reported as a secondary metric with an interval and no
claim.

## 2. Estimator

1. Run walk-forward at 30/6/6, step 6, over 2016-06-10 onward. Test windows are
   6 months and the step is 6 months, so test windows do not overlap and each
   out-of-sample day is used once.
2. Concatenate the 14 test windows into one out-of-sample daily return series
   per system.
3. Compute the annualised Sharpe of each pooled series and take the difference.

Each fold trains its own model, so the pooled series contains returns from 14
fitted models. This is intended. The pooled series is the out-of-sample record
of the procedure, which is what the claim concerns, rather than of any single
fitted model.

## 3. Test

Paired stationary block bootstrap (Politis and Romano) on the daily difference
series `r_M2 - r_B2`:

- expected block length 10 trading days, to preserve autocorrelation and
  volatility clustering
- 10,000 resamples, seed recorded in the RunConfig
- two-sided 95% percentile interval on ΔSharpe

The test is paired because M2 trades a subset of B2's signals. The shared
component cancels in the difference, which is what makes the comparison
tractable on 84 out-of-sample months.

**Amendment 1, 2026-09-05: how "paired" is implemented.** The wording above
does not say how the pairing is performed, and there are two readings. The
quantity of interest is a difference of two Sharpe ratios, not the Sharpe of a
difference; a Sharpe is a ratio of moments and does not distribute over
subtraction, so the two are different numbers. Each resample therefore draws
**one set of day indices and applies it to both return series**, then recomputes
both Sharpes and takes the difference. Drawing independently per system would
destroy the pairing this section relies on. This is a clarification of an
ambiguous sentence rather than a change to the test; it is recorded here because
the change rule in the header requires it, and because a reader checking the
implementation against this document would otherwise have to guess.

## 4. Decision rule

An improvement is claimed only if all three conditions hold:

1. the 95% bootstrap interval on ΔSharpe excludes zero
2. the point estimate is at least +0.20 annualised Sharpe
3. the sign of the effect survives the 2x cost-stress run (§10.3)

Condition 2 is a materiality floor: without it, a detectable but economically
trivial difference could be reported as an improvement.

If any condition fails, the result is reported as a negative result per Outline
§18, with the interval given rather than a p-value alone.

## 5. Detectable effect size

At 14 folds and 84 non-overlapping out-of-sample months (1,764 daily
observations), the standard error of ΔSharpe depends on the correlation between
the two return series:

| corr(M2, B2) | SE(ΔSharpe) | Minimum detectable |
|---|---|---|
| 0.99 | 0.054 | 0.11 |
| 0.95 | 0.120 | 0.24 |
| 0.90 | 0.169 | 0.34 |
| 0.80 | 0.239 | 0.48 |
| 0.50 | 0.378 | 0.76 |

A true improvement below roughly 0.3 Sharpe is unlikely to be detected by this
design. This is a property of ten years of one instrument. A null result is a
likely and legitimate outcome.

These figures assume independent returns, which intraday strategies are not, so
they are lower bounds on the true error. They also assume continuous market
exposure. Realised exposure must be measured and the figures recomputed before
any of them is quoted.

**Amendment 1, 2026-09-05: the measurement above was made, and it falsifies the
table above.** The table is kept rather than replaced, so what was assumed and
what was measured can both be read.

First graded run, 2026-09-04, `config_hash 5cd99d0d59d6ec80`,
`dataset_hash sha256:ab57353a...`, 1,760 pooled out-of-sample days:

| Comparison | Realised corr | SE(ΔSharpe) | Minimum detectable |
|---|---|---|---|
| **M2 vs B2 (primary)** | **+0.407** | **0.412** | **0.808** |
| M1 vs B2 | +0.453 | 0.396 | 0.776 |
| M2 vs M1 | +0.909 | 0.162 | 0.317 |

The realised correlation on the primary comparison is 0.407, not the 0.95 to
0.99 this section assumed, so the detection floor is **0.808** rather than the
0.24 the table gives at 0.95. The sentence "a true improvement below roughly
0.3 Sharpe is unlikely to be detected" understates the problem by a factor of
roughly three on the comparison it was written for.

**Why the assumption failed.** §3 reasons that M2 trades a subset of B2's
signals so the shared component cancels. The subset relation holds; the subset
is small. Realised exposure was 42.3% for B2 and 13.1% for M2, so M2 traded 231
days against B2's 745. On the 514 days where B2 traded and M2 was flat, B2 has
a return and M2 has a zero, and each of those days adds variance to the
difference rather than cancelling it. **Subset trading only buys power when the
subset is most of the whole.** The assumption held where it was incidental
(M2 vs M1, corr 0.909, floor 0.317) and failed on the primary comparison.

**Consequence for reading the result.** The primary comparison returned
ΔSharpe +0.065 with a 95% interval of [-0.622, +0.793], whose half-width is
essentially the detection floor. That interval means *this design could not
distinguish an effect of plausible size from zero*. It is not evidence that M2
does not help. Any report of the primary comparison must carry the realised
floor beside it.

**A structural point this exposes.** A gate that improves per-trade quality by
trading less is intrinsically hard to validate on a Sharpe difference, because
selectivity destroys the pairing the estimator depends on. The better the gate
is at being selective, the weaker this test becomes.

**What this amendment does not change.** The primary comparison, the metric,
the estimator, the block length, the resample count and the three conditions of
§4 are untouched. Nothing here was decided after seeing which way the result
went; the measurement was mandated by the paragraph directly above it. Logged in
`Decision_Tracker.md` and to be disclosed in the final technical report per the
change rule.

## 6. Multiplicity

One primary comparison. Everything below is reported with intervals and without
claim language.

| Reported | Status |
|---|---|
| B2 vs B1 | Ladder rung, no claim |
| M1 vs B2 | Ladder rung, isolates the regime classifier, no claim |
| M2 vs M1 | Ladder rung, isolates the signal-quality model, no claim |
| Maximum drawdown, Sortino, Calmar, profit factor | Secondary metrics, no claim |
| Per-fold sign count (folds where M2 beats B2, of 14) | Robustness view, no claim |
| Crypto | Graded secondary, 4 folds, minimum detectable ΔSharpe 0.63, fold count printed beside every figure, no significance claim |
| Options | No Sharpe computed or reported. See §7 |

## 7. Non-Sharpe claims

**Options, fill feasibility.** A proportion rather than a ratio of moments, so
the 6-month held-out window supports a usable interval. Reported as a Wilson
score 95% interval on the fill-feasibility rate, broken out by moneyness bucket
and regime, with the selection count beside each. Expected precision is ±3 to ±7
percentage points depending on candidate frequency. The selection rule is fitted
on approximately 19 months, its thresholds chosen on a 6-month validation
window, and the 6-month test window is opened once.

**Explanations, grounding.** 100% of a sample of 50 or more must be traceable to
a DecisionRecord field. Any untraceable claim is a release blocker rather than a
rate to be reported (Outline §20.2 harm 2).

**Decision comprehension.** Per Outline §10.2. n=3 is a usability smoke test and
is reported as such.

## 8. Fairness disaggregation

Per Outline §20.3. ΔSharpe is reported per regime (uptrend, downtrend, choppy)
and per volatility state, each with its observation count. No significance claim
is made on any slice with fewer than 60 out-of-sample trading days; those slices
report the count rather than the ratio. Any regime in which M2 underperforms B2
is reported explicitly and triggers the regime-conditional abstention mitigation
(`risk.regime_abstain`).

## 9. Cost model

Base cost model parameters are in RunConfig (`execution.commission_per_share`,
`execution.slippage_bps`) and are recorded in every results row via
`provenance()`. Headline results are reported at the base model, with 2x and 3x
cost-stress runs printed alongside rather than in an appendix.

---

Enforced by `tests/test_guardrails.py::test_evaluation_protocol_is_locked`.
