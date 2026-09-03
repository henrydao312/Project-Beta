# Options Plan — how options enter PROJECT BETA, and what each route costs

**Written 2026-09-02.** Answers one question: if options are to be part of what
the system *learns from*, rather than only part of how it executes, what is the
cheapest route that does not damage the graded core?

Companion documents: `Project_Outline.md` §5.8, §7A, §7B · `Upgrade_Path.md` ·
`scripts/analysis/fold_power.py` (the arithmetic behind every number here).

---

## 0. The constraint that governs everything

> **A feature must exist across the whole training window, or it truncates the
> training window to the feature's own history.**

Add a feature computed from Alpaca's options bars, which begin 2024-01-18, and
the equity training window collapses from 122 months to 31. Options would then
have been paid for by demoting the graded core, which is the opposite of the
trade anybody intended. This single line rules out the obvious approach and
sets the shape of everything below: **the only options information worth
feeding the models is options information with deep history.**

## 1. Two different questions live under "include options"

**(A) Trade options, model options.** Options becomes the instrument, with its
own signal model. Needs long options history for training. Covered in §3 below
and rejected on cost, scope and schedule.

**(B) Let the options market inform the models that already exist.** Implied
volatility, term structure and skew are the options market's view *of SPY*, and
the regime classifier is exactly the component that should consume such a view.
This is the cheap question, and it is the better research question.

Everything in §2 answers (B).

## 2. Three routes, cheapest first

### Tier 1 — Cboe published volatility indices. Recommended.

Free CSV downloads, no registration. VIX runs from 1990, which covers the full
2016-2026 equity window with three decades to spare. VVIX and VIX9D are on the
same page. These are computed directly from SPX option prices, so this is the
options market itself and not a proxy for it.

Features worth building, all scale-free in the sense of §5.2:

| Feature | What it is | Why it might matter to M1 |
|---|---|---|
| `iv_level_z` | VIX standardised against a trailing window | Implied vol as a regime descriptor, independent of realised vol |
| `iv_term_slope` | VIX9D / VIX | Backwardation is a stress signal that tends to lead realised vol |
| `vol_of_vol` | VVIX / VIX | Tail demand; distinguishes a calm high-vol regime from a fragile one |
| `iv_return_asym` | VIX change against same-day SPY return | The vol/return relationship differs by regime, which is the thing M1 classifies |

**Point-in-time rule.** These are daily closes. Use the **previous session's**
value, forward-filled across the day, never the current one. That is both the
leakage guard and the honest choice, since the value is not knowable intraday.

**Cost: $0. New vendors: zero. Training-window damage: none.**

### Tier 2 — Volatility ETFs through the provider already built.

VIXY, VXX and UVXY are ordinary ETFs, so Alpaca serves them on the same
5-minute SIP bars from 2016-06-10: same feed, same licence already audited,
same `get_bars` call, same `MarketDataProvider`. This buys **intraday**
granularity where Tier 1 only offers daily.

They track VIX *futures*, not spot VIX, so they carry roll decay. That is
acceptable for a feature, since nothing trades them here, and it must be stated
in the Model Card rather than glossed. Probe one symbol for history depth
before committing, the way every other data question in this project was
closed.

**Cost: $0. New vendors: zero.**

### Tier 3 — Alpaca options bars as features. Phase 2.

Put/call volume ratio and at-the-money contract volume, computed from the
contract bars already available. Free, but only from 2024-01-18, so it
truncates. Legitimate **only** as a clearly labelled side experiment on the
2024-2026 subperiod, reported with its own fold count of effectively one. It
is also Week 10 scope stacked on top of the options execution layer, in the
week the plan review already marks as the first place the schedule breaks.

## 3. Buying deeper options history — considered and declined

Deeper intraday options history exists and is purchasable:

| Vendor | Price | Intraday depth | Folds at 42-month scheme |
|---|---|---|---|
| ORATS 1-minute | $199/mo, or $1,500 one-time + $1-2k AWS transfer | Aug 2020 onward, ~6 years | ~6 |
| FlashAlpha | tier price unstated, up to $1,199/mo | minute resolution from Jan 2017 | ~13 |
| Massive (Polygon) Options Advanced | $199/mo | 5+ years | ~3 |
| Alpaca (current) | $0 | 2024-01-18, 31 months | **0** |

Five reasons the spend does not help this project, none of which are about
whether the money is available:

1. **Options trains no model.** M1 and M2 score the underlying; contract
   selection is deterministic and downstream. More options history improves
   nothing already being built. It only unlocks a *new* graded track.
2. **It lands in Weeks 9-10**, already the two most overloaded weeks.
3. **A second vendor is a second train/live feed mismatch.** Execution stays on
   Alpaca, so the models would train on one vendor's bars and fill against
   another's. That is the §5.2 problem again, on the track with the least
   evidence behind it, and it would need its own transfer experiment.
4. **A second licensing audit before the repo goes public in Week 12.**
   Polygon's §5(d) bars derivative works "including any investment strategy",
   and ORATS would need the same read.
5. It is a $200 to $3,500 spend that upgrades a **label**, not the evidence.

**Prominence is a separate axis from grading tier.** Options can take most of
the engineering attention and headline the Week 12 demo without changing tier.

## 4. Fitting 31 months to train / validation / test

It fits, for the right thing. The 36-month training window exists because M1
and M2 are learned models needing *regime variety*, which is a calendar
property rather than a sample-size one. The options selection rule has four
scalar parameters. Sample-size requirements scale with what is being fitted.

| Window | Dates | Months | Purpose |
|---|---|---|---|
| Fit | 2024-01-18 to 2025-08-31 | ~19 | Measure liquidity by moneyness bucket |
| Validate | 2025-09-01 to 2026-02-28 | ~6 | Sweep the screen thresholds, choose one |
| Test | 2026-03-01 to 2026-08-31 | ~6 | Frozen rule, opened once |

**This is stricter than the current plan.** §5.8 fits on ~25 months and tests
on ~6 with no validation window, which means the screen thresholds get chosen
on the window that is then reported. Same leakage the equity harness was
corrected for.

## 5. Why that same window supports one claim and not the other

The tier labels in §7A read like a naming convention. They are not. The two
claims use different estimators, and the estimators need different amounts of
data by an order of magnitude.

**As a performance claim.** A Sharpe difference is a noisy ratio of moments;
its error falls as 1/sqrt(days). Six months is 126 daily returns, giving a
minimum detectable difference of **1.27 Sharpe**. Nothing this project could
plausibly find is that large, so the fold could only ever confirm the null.

**As a capability claim.** A fill-feasibility rate is a proportion; its error
falls as 1/sqrt(selections), and a 6-month window holds hundreds of selections
because several candidates occur per session.

| Candidates/day | Selections | 95% CI on the fill rate |
|---|---|---|
| 1 | 126 | ±7.0 pp |
| 2 | 252 | ±4.9 pp |
| 3 | 378 | ±4.0 pp |
| 5 | 630 | ±3.1 pp |

A fill rate to within a few points is a real result. That contrast is the
defence of the tier structure, and it is arithmetic rather than taste.

## 6. Adding it without damaging the ablation

Do not fold implied-volatility features into M1 silently, or the contribution
becomes unmeasurable. Add a rung:

| # | System | Price/volume features | IV features | Signal AI |
|---|---|---|---|---|
| B1 | Buy and hold | – | – | – |
| B2 | Momentum breakout + risk layer | – | – | – |
| M1 | B2 + regime classifier | ✓ | – | – |
| **M1v** | **M1 + implied-volatility features** | ✓ | **✓** | – |
| M2 | Best of M1/M1v + signal-quality model | ✓ | ? | ✓ |

If the IV features add nothing, that is a publishable negative result on a
genuinely interesting question: **does the options market's implied view of
volatility improve regime classification over realised volatility alone?**
That is a better question than a graded options track would have answered.

## 7. Costs to accept before starting

- **A new row in the §20.1 licensing audit.** Cboe index data carries its own
  terms and the repo goes public in Week 12.
- **New scope** in a semester with three weeks already over capacity. Tier 1 is
  roughly half a day: fetch a few CSVs, join on date, shift one session,
  register the features. Tier 2 adds a probe and one more symbol.
- **Seam 6 gets exercised.** The feature registry with declared data
  requirements exists for exactly this, and it is currently unscheduled.

## 8. The gate

**Proceed with Tier 1 only if, by end of Week 4:** the feed-transfer experiment
has concluded, and B1/B2 plus the walk-forward harness are running.

Otherwise Tier 1 moves to Phase 2 alongside the options upgrade path. Tier 3 is
Phase 2 regardless. Buying data is declined at any point in the course.

---

**Sources:** [Cboe VIX historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data/) ·
[Cboe put/call ratio archive](https://www.cboe.com/data/putcallratio.aspx) ·
[ORATS 1-minute data](https://orats.com/one-minute-data) ·
[Best Options Data APIs 2026](https://flashalpha.com/articles/best-options-data-apis-2026)
