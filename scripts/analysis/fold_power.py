"""What a walk-forward scheme can and cannot detect.

Written to answer a specific question: is 48 months per fold required, and would
27 months do instead? The answer is arithmetic, and it belongs in the repo
rather than in a conversation, because the Week 3 evaluation protocol has to
prespecify a decision rule and the rule should be chosen knowing what the data
can support.

Two constraints bind a walk-forward scheme, and they pull in opposite
directions:

  TRAIN window - bound by *regime coverage*, not sample size. At 78 RTH bars a
  day, even an 18-month window holds ~29,000 bars, far more than a gradient
  boosted tree needs for a dozen features. What a short window cannot give is
  variety: market regimes turn over on a scale of months to years, and an
  18-month window can sit entirely inside one. A classifier trained on one
  regime has nothing to say about the others, which defeats the point of M1.

  TEST windows - bound by estimation error on the headline comparison. Sharpe
  measured over n days has standard error roughly sqrt(252/n), so a single
  6-month fold carries SE ~1.4 on an annualised Sharpe. Only the *pooled*
  out-of-sample record is informative, and because M2 is a filtered subset of
  B2 their returns are strongly correlated, so the paired difference is
  estimated far better than either level.

The result below is the useful part: total out-of-sample coverage is capped by
total history, not by fold length, so shortening the fold buys almost no
statistical power while costing half the training window.

Assumptions, all stated so they can be argued with:
  - returns treated as iid for the standard-error formula. Intraday strategies
    are autocorrelated, so the real errors are WORSE than these. Read every
    number here as a floor.
  - rho = 0.90 between filtered and unfiltered returns. Sensitivity printed.
  - "min detectable" is 2 standard errors, roughly a 95% two-sided threshold.

    python scripts/analysis/fold_power.py
"""

from __future__ import annotations

import math

BARS_PER_DAY = 78 # 5-minute bars in a regular session
DAYS_PER_MONTH = 21
TRADING_DAYS_YEAR = 252

# Months of 5-minute history available, measured 2026-09-01 (Outline §9).
SPAN_MONTHS = {"equity": 123, "crypto": 63, "option": 31}

SCHEMES = [
    ("36/6/6 step 6", 36, 6, 6, 6),
    ("30/6/6 step 6", 30, 6, 6, 6),
    ("24/6/6 step 6", 24, 6, 6, 6),
    ("18/3/6 step 6", 18, 3, 6, 6),
    ("15/6/6 step 6", 15, 6, 6, 6),
    ("12/3/3 step 3", 12, 3, 3, 3),
]


def fold_count(span_months: int, train: int, val: int, test: int, step: int) -> int:
    usable = span_months - (train + val + test)
    return 0 if usable < 0 else usable // step + 1


def se_sharpe(n_days: int, sharpe_annual: float = 1.0) -> float:
    """Standard error of an annualised Sharpe estimated from n daily returns."""
    sr_daily = sharpe_annual / math.sqrt(TRADING_DAYS_YEAR)
    return math.sqrt(TRADING_DAYS_YEAR) * math.sqrt((1 + sr_daily**2 / 2) / n_days)


def se_sharpe_difference(n_days: int, rho: float = 0.90) -> float:
    """Standard error of the M-tier minus B2 Sharpe difference.

    The correlation is what makes the comparison tractable. M2 trades a subset
    of B2's signals, so most of the return series is shared and cancels in the
    difference. A project comparing two unrelated strategies would need far
    more data to say anything.
    """
    return se_sharpe(n_days) * math.sqrt(2 * (1 - rho))


# --------------------------------------------------------------------------
# Why the same 31 months supports one claim and not the other.
# --------------------------------------------------------------------------
# The tier labels in Outline §7A are usually defended by definition: a graded
# tier makes a performance claim, a validated execution layer makes a
# capability claim. That is true but it sounds like a choice. It is not. The
# two claims have different estimators, and the estimators need different
# amounts of data by an order of magnitude.
#
# A Sharpe difference is estimated from a noisy ratio of moments, and its
# error falls as 1/sqrt(days). Six months of daily returns gives 126
# observations, which is nothing.
#
# A fill-feasibility rate is a proportion. Its error falls as
# 1/sqrt(selections), and a 6-month window holds hundreds of selections
# rather than 126 daily returns, because several candidates can occur in a
# single session.
#
# So the same held-out window that cannot distinguish a real edge from noise
# can pin a fill rate to a few percentage points. The tier structure is a
# consequence of that arithmetic, not a naming convention.


def proportion_ci_halfwidth(n: int, p: float = 0.80) -> float:
    """Half-width of a 95% normal-approximation interval on a proportion."""
    return 1.96 * math.sqrt(p * (1 - p) / n)


def options_claim_power() -> None:
    print()
    print("The options held-out window: 6 months, two different questions")
    print()
    print(" As a PERFORMANCE claim (Sharpe difference, daily returns):")
    n_days = 6 * DAYS_PER_MONTH
    sed = se_sharpe_difference(n_days)
    print(f" {n_days} observations, SE = {sed:.2f}, "
          f"min detectable = {2 * sed:.2f} Sharpe")
    print(" Nothing this project could plausibly find is that large.")
    print()
    print(" As a CAPABILITY claim (fill-feasibility rate, per selection):")
    print(f" {'candidates/day':>16}{'selections':>12}{'95% CI':>12}")
    for per_day in (1, 2, 3, 5):
        n = int(6 * DAYS_PER_MONTH * per_day)
        hw = proportion_ci_halfwidth(n)
        print(f" {per_day:>16}{n:>12}{'+/- ' + format(100 * hw, '.1f') + ' pp':>12}")
    print(" A fill rate reported to within a few points is a real result.")
    print()
    print(" Proposed three-way split across the 31 months (2024-01-18 to 2026-08):")
    print(" fit 2024-01-18 to 2025-08-31 ~19 months")
    print(" validate 2025-09-01 to 2026-02-28 ~6 months")
    print(" test 2026-03-01 to 2026-08-31 ~6 months, opened once")
    print(" Legitimate because the selection rule has four scalar parameters,")
    print(" not a learned model. Sample-size requirements scale with what is")
    print(" being fitted. This is also stricter than the current plan, which")
    print(" fits on ~25 months and tests on ~6 with no validation window, and")
    print(" therefore picks its thresholds on the window it reports.")


def main() -> int:
    print("Fold schemes, by what they cost and what they buy")
    print(f"{'scheme':<16}{'train bars':>12}{'eq':>5}{'cr':>4}{'op':>4}"
          f"{'eq OOS mo':>11}{'SE(dSR)':>10}{'min detect':>12}")
    print("-" * 74)
    for label, train, val, test, step in SCHEMES:
        counts = {
            k: fold_count(v, train, val, test, step) for k, v in SPAN_MONTHS.items()
        }
        train_bars = train * DAYS_PER_MONTH * BARS_PER_DAY
        # Test windows only stop overlapping once the step matches the test
        # length. Overlapping test windows re-use the same days and add no
        # independent evidence, so credit the smaller of the two.
        oos_months = counts["equity"] * min(step, test)
        n_days = oos_months * DAYS_PER_MONTH
        sed = se_sharpe_difference(n_days) if n_days else float("nan")
        print(
            f"{label:<16}{train_bars:>12,}{counts['equity']:>5}{counts['crypto']:>4}"
            f"{counts['option']:>4}{oos_months:>11}{sed:>10.3f}{2 * sed:>12.2f}"
        )

    print()
    print("Read the two right-hand columns together with the left one.")
    print("Halving the fold length moves the detectable effect from ~0.35 to")
    print("~0.30 Sharpe, because total out-of-sample coverage is capped by total")
    print("history rather than by fold length. It halves the training window to")
    print("buy that. The trade is bad in both directions at once.")

    print()
    print("Per track, at 30/6/6 step 6:")
    print(f"{'track':<9}{'folds':>6}{'OOS mo':>8}{'obs':>7}{'SE(dSR)':>10}{'min detect':>12}")
    for track, span in SPAN_MONTHS.items():
        folds = fold_count(span, 30, 6, 6, 6)
        oos = folds * 6
        if not oos:
            print(f"{track:<9}{folds:>6}{oos:>8}{'-':>7}{'-':>10}{'no claim':>12}")
            continue
        n = oos * DAYS_PER_MONTH
        sed = se_sharpe_difference(n)
        print(f"{track:<9}{folds:>6}{oos:>8}{n:>7}{sed:>10.3f}{2 * sed:>12.2f}")

    print()
    print("Options forced into a 27-month scheme (18/3/6, step 6):")
    folds = fold_count(SPAN_MONTHS["option"], 18, 3, 6, 6)
    oos = folds * 6
    n = oos * DAYS_PER_MONTH
    sed = se_sharpe_difference(n)
    print(f" {folds} fold, {oos} out-of-sample months, {n} observations")
    print(f" SE(dSharpe) = {sed:.2f}, min detectable difference = {2 * sed:.2f} Sharpe")
    print(" One fold is not walk-forward. It is a single train/test split, which")
    print(" is what the validated execution layer already is and already says.")
    print(" A detectable threshold above 1.2 Sharpe exceeds any effect this")
    print(" project could plausibly find, so the fold could only ever confirm")
    print(" the null. And its test window sits inside one broad regime.")

    options_claim_power()

    print()
    print("Sensitivity of the equity result to the correlation assumption:")
    n_eq = fold_count(123, 30, 6, 6, 6) * 6 * DAYS_PER_MONTH
    for rho in (0.99, 0.95, 0.90, 0.80, 0.50):
        sed = se_sharpe_difference(n_eq, rho)
        print(f" rho={rho:<5} SE(dSR)={sed:.3f} min detectable={2 * sed:.2f}")
    print()
    print("Caveat that matters for the write-up: these use daily returns of a")
    print("strategy assumed to be in the market throughout. A strategy holding")
    print("positions only part of the time has fewer effective observations, so")
    print("measure the realised exposure and recompute before quoting a number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
