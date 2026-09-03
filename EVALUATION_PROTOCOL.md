# Evaluation Protocol — locked 2026-09-02

**Status: LOCKED, before any M-tier model has been trained.**

This document fixes how the headline comparison is decided, so that the
decision rule cannot be chosen after the numbers are known. Outline §17
criterion 4 promises "at least one **prespecified** risk-adjusted metric"; this
is that prespecification. Outline §20.2 harm 3 lists "prespecified primary
metric fixed before M1 experiments" as a guardrail, and a guardrail with no
document behind it is a sentence.

Every number here is derived in `scripts/analysis/fold_power.py`.

**Change rule.** Any change to this document after the first M-tier experiment
has run requires a decision-log entry and must be disclosed in the final
technical report. Changing it silently would invalidate every other
pre-commitment in the project, including the feed-transfer verdict that has
already been honoured against the project's own preference.

---

## 1. The primary comparison — one metric, one test, one pair

| | |
|---|---|
| **Systems compared** | **M2 versus B2** (Outline §7). Nothing else is primary |
| **Metric** | **Annualised Sharpe ratio**, net of costs |
| **Asset class** | **Equities only** (SPY, SIP feed). The primary claim rests here |
| **Direction** | ΔSharpe = Sharpe(M2) − Sharpe(B2) |

**Why Sharpe and not maximum drawdown.** The Outline said "Sharpe *or* maximum
drawdown", which is two chances at one claim. One is now chosen. Sharpe wins
because maximum drawdown is a single-path extremum: its sampling distribution
is wide, strongly dependent on the length of the record, and has no clean
paired estimator. Choosing it as primary would give a *worse*-powered test, not
a gentler one. **Maximum drawdown is reported as a secondary metric with a
bootstrap interval and no claim language.**

## 2. The estimator

1. Run walk-forward at **30/6/6, step 6** over 2016-06-10 onward. Test windows
   are 6 months and the step is 6 months, so **test windows do not overlap** and
   each out-of-sample day is used exactly once.
2. Concatenate the 14 test windows into a single out-of-sample daily return
   series per system.
3. Compute the annualised Sharpe of each pooled series, and their difference.

**Why pooling is correct here, since a reader will ask.** Each fold trains its
own model, so the pooled series splices returns produced by 14 different fitted
models. That is not a defect; it is what walk-forward measures. The pooled
series is the realised out-of-sample track record of *the procedure*, which is
the thing being claimed, rather than of any one fitted model.

## 3. The test

**Paired stationary block bootstrap** (Politis and Romano) on the daily
difference series `r_M2 − r_B2`:

- expected block length **10 trading days**, to preserve the autocorrelation
  and volatility clustering that an iid bootstrap would destroy
- **10,000 resamples**, seed recorded in the RunConfig
- **two-sided 95%** percentile interval on ΔSharpe

Paired, because M2 trades a filtered subset of B2's signals. Most of the return
series is shared and cancels in the difference, which is the only reason this
comparison is tractable at all on 84 out-of-sample months.

## 4. The decision rule

**An improvement is claimed only if all three hold:**

1. the 95% bootstrap interval on ΔSharpe **excludes zero**;
2. the point estimate is **at least +0.20** annualised Sharpe;
3. the sign of the effect **survives the 2x cost-stress run** (§10.3).

Condition 2 is a materiality floor. Without it, a statistically detectable but
economically trivial difference could be reported as a win, which is true and
misleading at the same time.

**If any condition fails, the result is reported as a negative result**, framed
per Outline §18, with the interval given rather than a p-value alone.

## 5. What this design can and cannot detect

At 14 folds and 84 non-overlapping out-of-sample months (1,764 daily
observations), the standard error of ΔSharpe depends on how correlated the two
return series are:

| corr(M2, B2) | SE(ΔSharpe) | Minimum detectable |
|---|---|---|
| 0.99 | 0.054 | 0.11 |
| 0.95 | 0.120 | 0.24 |
| **0.90** | **0.169** | **0.34** |
| 0.80 | 0.239 | 0.48 |
| 0.50 | 0.378 | 0.76 |

**Stated plainly: a true improvement smaller than roughly 0.3 Sharpe is very
unlikely to be detected by this design.** That is a property of ten years of
one instrument, not a flaw in the method, and it is written down here rather
than discovered in Week 13. A null result is a likely outcome and a legitimate
one.

These figures assume iid returns, which intraday strategies are not, so treat
them as a floor. They also assume the strategy is in the market throughout;
**measure realised exposure and recompute before quoting any of them.**

## 6. Multiplicity — what is not a second shot

Exactly one primary comparison exists. Everything below is reported with
intervals and without claim language:

| Reported | Status |
|---|---|
| B2 vs B1 | Ladder rung. No claim |
| M1 vs B2 | Ladder rung, and the isolation of the regime classifier's contribution. No claim |
| M2 vs M1 | Ladder rung, isolating the signal-quality model. No claim |
| Maximum drawdown, Sortino, Calmar, profit factor | Secondary metrics. No claim |
| Per-fold sign count (folds where M2 beats B2, out of 14) | Robustness view. No claim |
| Crypto | Graded secondary, 4 folds. **Minimum detectable ΔSharpe 0.63.** Fold count printed beside every figure. No significance claim |
| Options | **No Sharpe is computed or reported.** See §7 |

## 7. Non-Sharpe claims

**Options — fill feasibility.** A proportion, not a ratio of moments, so the
same 6-month held-out window that is useless for Sharpe supports a real
interval. Reported as a **Wilson score 95% interval** on the fill-feasibility
rate, broken out by moneyness bucket and regime, with the selection count
beside each. Expected precision is ±3 to ±7 percentage points depending on
candidate frequency. The selection rule is fitted on ~19 months, its thresholds
chosen on a ~6-month validation window, and the ~6-month test window is opened
once (`Options_Plan.md` §4).

**Explanations — grounding.** 100% of a >=50-sample audit must be traceable to
a DecisionRecord field. Any untraceable claim is a release blocker, not a rate
to be reported (Outline §20.2 harm 2).

**Decision comprehension.** Per Outline §10.2. n=3 is a usability smoke test and
is reported as such, never as a study.

## 8. Fairness disaggregation (Outline §20.3)

ΔSharpe is reported per regime (uptrend, downtrend, choppy) and per volatility
state, each with its observation count. **No significance claim is made on any
slice with fewer than 60 out-of-sample trading days**; those slices report the
count rather than the ratio. Any regime in which M2 underperforms B2 is
reported explicitly rather than averaged away, and is the trigger for the
regime-conditional abstention mitigation (`risk.regime_abstain`).

## 9. Cost model

The base cost model parameters live in RunConfig (`execution.commission_per_share`,
`execution.slippage_bps`) and are recorded in every results row via
`provenance()`. Headline results are reported at the base model, with **2x and
3x cost-stress runs printed alongside**, not in an appendix.

---

**Locked:** 2026-09-02, before any M-tier model existed.
**Enforced by:** `tests/test_guardrails.py::test_evaluation_protocol_is_locked`.
