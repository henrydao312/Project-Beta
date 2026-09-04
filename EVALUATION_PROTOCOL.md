# Evaluation Protocol

**Status: LOCKED 2026-09-02, before any M-tier model was trained.**

This document fixes how the primary comparison is decided, so the decision rule
cannot be selected after the results are known. Outline §17 criterion 4 requires
a prespecified risk-adjusted metric; this document is that prespecification.
Outline §20.2 harm 3 lists it as a guardrail.

Supporting arithmetic: `scripts/analysis/fold_power.py`.

**Change rule.** Any change after the first M-tier experiment has run requires a
decision-log entry and must be disclosed in the final technical report.

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
