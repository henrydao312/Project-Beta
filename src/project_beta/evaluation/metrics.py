"""Performance metrics. One primary, the rest reported without a claim.

EVALUATION_PROTOCOL.md fixes annualised Sharpe, net of costs, as the single
primary metric, and the locking happened before any M-tier model existed. The
Outline previously said "Sharpe or maximum drawdown", which is two chances at
one claim; everything else in this module is therefore computed, reported with
an interval, and explicitly not claimed (protocol §6).

Two conventions, stated because they change the numbers.

**Returns are simple, equity compounds.** A daily return series here is
`(equity_t / equity_{t-1}) - 1`. Sharpe is computed on those simple returns;
drawdown is computed on the compounded equity curve they imply. Mixing log
returns into one and simple into the other is a common and invisible way to
report a drawdown that the strategy never had.

**A degenerate series returns NaN, never zero.** Zero volatility, or fewer
than two observations, means the ratio is undefined. Returning 0.0 would put a
number in a results table that reads as "no edge" when the truth is "no
estimate", and the two are different claims.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

# The protocol's annualisation constant. Equities only; a crypto run trades
# every calendar day, and its own constant travels with its results.
TRADING_DAYS_YEAR = 252
CRYPTO_DAYS_YEAR = 365


def _mean(xs: Sequence[float]) -> float:
    return math.fsum(xs) / len(xs)


def _stdev(xs: Sequence[float]) -> float:
    """Sample standard deviation, Bessel-corrected."""
    if len(xs) < 2:
        return float("nan")
    mu = _mean(xs)
    return math.sqrt(math.fsum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def annualised_sharpe(
    returns: Sequence[float], *, periods_per_year: int = TRADING_DAYS_YEAR
) -> float:
    """The primary metric. NaN where it is undefined rather than zero."""
    if len(returns) < 2:
        return float("nan")
    sd = _stdev(returns)
    if not sd > 0:
        return float("nan")
    return _mean(returns) / sd * math.sqrt(periods_per_year)


def annualised_sortino(
    returns: Sequence[float], *, periods_per_year: int = TRADING_DAYS_YEAR
) -> float:
    """Sharpe's downside-only sibling. Secondary metric, no claim attached."""
    if len(returns) < 2:
        return float("nan")
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("nan")
    dd = math.sqrt(math.fsum(r * r for r in downside) / len(returns))
    if not dd > 0:
        return float("nan")
    return _mean(returns) / dd * math.sqrt(periods_per_year)


def equity_curve(returns: Sequence[float], *, start: float = 1.0) -> list[float]:
    """Compounded equity implied by a simple-return series."""
    equity = [start]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity


def max_drawdown(returns: Sequence[float]) -> float:
    """Largest peak-to-trough fall of the compounded curve, as a positive fraction.

    Reported with an interval and no claim (protocol §1). It is a single-path
    extremum: its sampling distribution is wide, it depends strongly on record
    length, and it has no clean paired estimator, which is exactly why it is
    not the primary metric.
    """
    if not returns:
        return float("nan")
    peak = -math.inf
    worst = 0.0
    for value in equity_curve(returns):
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst


def annualised_return(
    returns: Sequence[float], *, periods_per_year: int = TRADING_DAYS_YEAR
) -> float:
    if not returns:
        return float("nan")
    total = equity_curve(returns)[-1]
    if total <= 0:
        return float("nan")
    return total ** (periods_per_year / len(returns)) - 1.0


def calmar(
    returns: Sequence[float], *, periods_per_year: int = TRADING_DAYS_YEAR
) -> float:
    dd = max_drawdown(returns)
    if not dd > 0 or math.isnan(dd):
        return float("nan")
    return annualised_return(returns, periods_per_year=periods_per_year) / dd


def profit_factor(returns: Sequence[float]) -> float:
    gains = math.fsum(r for r in returns if r > 0)
    losses = -math.fsum(r for r in returns if r < 0)
    if not losses > 0:
        return float("nan")
    return gains / losses


def hit_rate(returns: Sequence[float]) -> float:
    active = [r for r in returns if r != 0.0]
    if not active:
        return float("nan")
    return sum(1 for r in active if r > 0) / len(active)


def exposure(returns: Sequence[float]) -> float:
    """Fraction of days with any position at all.

    Protocol §5 notes that the detectable-effect table assumes continuous
    market exposure and that realised exposure must be measured before any of
    those figures is quoted. This is that measurement, and a long-only
    intraday strategy will sit far below 1.0.
    """
    if not returns:
        return float("nan")
    return sum(1 for r in returns if r != 0.0) / len(returns)


@dataclass(frozen=True)
class PerformanceSummary:
    """One system's out-of-sample record. `sharpe` leads; the rest support it."""

    system: str
    n_days: int
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    profit_factor: float
    hit_rate: float
    exposure: float
    annualised_return: float
    periods_per_year: int

    def to_dict(self, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        """A results row. Provenance travels with it, never beside it.

        Outline §7B seam 3: the comparability caveat belongs in the data. A
        crypto Sharpe without its fold count attached will eventually be read
        as if it carried the equity core's evidentiary weight.
        """
        out: dict[str, Any] = asdict(self)
        if provenance:
            out |= {f"run_{k}": v for k, v in provenance.items()}
        return out


def summarise(
    returns: Sequence[float],
    *,
    system: str,
    periods_per_year: int = TRADING_DAYS_YEAR,
) -> PerformanceSummary:
    return PerformanceSummary(
        system=system,
        n_days=len(returns),
        sharpe=annualised_sharpe(returns, periods_per_year=periods_per_year),
        sortino=annualised_sortino(returns, periods_per_year=periods_per_year),
        max_drawdown=max_drawdown(returns),
        calmar=calmar(returns, periods_per_year=periods_per_year),
        profit_factor=profit_factor(returns),
        hit_rate=hit_rate(returns),
        exposure=exposure(returns),
        annualised_return=annualised_return(returns, periods_per_year=periods_per_year),
        periods_per_year=periods_per_year,
    )
