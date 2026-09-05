"""Paired stationary block bootstrap. EVALUATION_PROTOCOL.md §3, implemented.

The protocol specifies: Politis-Romano stationary block bootstrap on the daily
difference series, expected block length 10 trading days, 10,000 resamples,
seed recorded in the RunConfig, two-sided 95% percentile interval on the Sharpe
difference.

**How "paired" is implemented, and why it matters.** The quantity of interest
is a difference of two Sharpe ratios, not the Sharpe of a difference - those
are different numbers, because a Sharpe is a ratio of moments and does not
distribute over subtraction. So each resample draws one set of day indices and
applies it to *both* return series, then recomputes both Sharpes and takes the
difference. Drawing independently for the two systems would destroy the pairing
that makes this comparison tractable at all: M2 trades a subset of B2's
signals, most of the return series is shared, and it is the shared component
cancelling that lets 84 out-of-sample months say anything. This reading is
recorded here because it is an implementation choice the protocol's wording
does not spell out; changing it later requires a decision-log entry under the
protocol's change rule.

**Why blocks rather than plain resampling.** Daily returns are autocorrelated
and their volatility clusters. An i.i.d. bootstrap would break both, understate
the variance of the statistic, and hand back an interval that is too narrow -
the failure mode that turns a null result into a claimed improvement.

**Why *stationary* blocks.** Fixed-length blocks make the resampled series
non-stationary in a way that depends on where the block boundaries land.
Politis and Romano's geometric block length removes that artifact at the cost
of nothing that matters here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from project_beta.evaluation.metrics import TRADING_DAYS_YEAR

# Protocol §3. Not parameters to sweep: they were fixed before any M-tier model
# existed, and moving them after a result is known is precisely what the
# prespecification exists to prevent.
EXPECTED_BLOCK_DAYS = 10
RESAMPLES = 10_000
ALPHA = 0.05


class BootstrapError(ValueError):
    """The inputs cannot support the test the protocol specifies."""


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float
    resamples: int
    expected_block: int
    seed: int
    alpha: float

    @property
    def excludes_zero(self) -> bool:
        return self.low > 0.0 or self.high < 0.0

    def __str__(self) -> str:
        pct = round((1 - self.alpha) * 100)
        return f"{self.point:+.3f} [{self.low:+.3f}, {self.high:+.3f}] ({pct}%)"


def stationary_block_indices(
    n: int, *, expected_block: int, rng: np.random.Generator
) -> np.ndarray:
    """One resample's worth of day indices, wrapping at the end of the series.

    Politis-Romano: start somewhere at random; at each step, with probability
    1/expected_block start a new block at a fresh random position, otherwise
    advance one day. Block lengths are therefore geometric with the requested
    mean, and the resampled series is stationary.
    """
    if n < 2:
        raise BootstrapError("a bootstrap needs at least two observations")
    p = 1.0 / expected_block
    idx = np.empty(n, dtype=np.int64)
    current = int(rng.integers(n))
    starts = rng.random(n) < p
    jumps = rng.integers(0, n, size=n)
    for t in range(n):
        if t and starts[t]:
            current = jumps[t]
        idx[t] = current
        current = (current + 1) % n
    return idx


def _sharpe(matrix: np.ndarray, periods_per_year: int) -> np.ndarray:
    """Annualised Sharpe along axis 1, NaN where the series is degenerate."""
    sd = matrix.std(axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = matrix.mean(axis=1) / sd * np.sqrt(periods_per_year)
    return np.where(sd > 0, out, np.nan)


def paired_sharpe_difference(
    treatment: Sequence[float],
    control: Sequence[float],
    *,
    seed: int,
    resamples: int = RESAMPLES,
    expected_block: int = EXPECTED_BLOCK_DAYS,
    alpha: float = ALPHA,
    periods_per_year: int = TRADING_DAYS_YEAR,
) -> Interval:
    """Point estimate and percentile interval for Sharpe(treatment) - Sharpe(control).

    `treatment` and `control` must be the same days in the same order. Silently
    accepting mismatched lengths would break the pairing and widen the interval
    without any visible symptom.
    """
    a = np.asarray(treatment, dtype=float)
    b = np.asarray(control, dtype=float)
    if a.shape != b.shape:
        raise BootstrapError(
            f"paired test needs aligned series: got {a.shape} and {b.shape}. "
            "These must be the same out-of-sample days, in order."
        )
    if a.size < 2:
        raise BootstrapError("a bootstrap needs at least two observations")

    rng = np.random.default_rng(seed)
    n = a.size
    draws = np.empty(resamples, dtype=float)
    for r in range(resamples):
        idx = stationary_block_indices(n, expected_block=expected_block, rng=rng)
        pair = np.vstack((a[idx], b[idx]))
        sharpes = _sharpe(pair, periods_per_year)
        draws[r] = sharpes[0] - sharpes[1]

    finite = draws[np.isfinite(draws)]
    if finite.size < resamples // 2:
        raise BootstrapError(
            f"only {finite.size} of {resamples} resamples produced a defined "
            "Sharpe difference; the input series are too degenerate for this "
            "test to mean anything"
        )

    observed = _sharpe(np.vstack((a, b)), periods_per_year)
    point = float(observed[0] - observed[1])
    low, high = np.percentile(finite, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return Interval(
        point=point,
        low=float(low),
        high=float(high),
        resamples=resamples,
        expected_block=expected_block,
        seed=seed,
        alpha=alpha,
    )
