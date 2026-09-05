"""The ablation ladder as runnable systems. Outline §7, four rungs.

    B1  buy and hold
    B2  momentum breakout + the deterministic risk layer
    M1  B2 + the regime classifier
    M2  M1 + the signal-quality model

Only the gate list differs between B2, M1 and M2. Same bars, same features,
same candidates, same fills, same costs, same sizing, same halt logic, same day
index. That is what makes the difference between two rungs attributable to the
component that was added rather than to anything else that moved.

**B1 is fully invested and the others are not**, and the comparison has to say
so. A long-only intraday strategy is flat most of the time, so its realised
exposure is a fraction of B1's. Sharpe is exposure-neutral in the sense that it
scales with the return series it is given, but drawdown and total return are
not, and a reader comparing them without the exposure figure beside them will
draw the wrong conclusion. `PerformanceSummary.exposure` is computed for every
system for exactly this reason, and EVALUATION_PROTOCOL.md §5 requires realised
exposure to be measured before the detectable-effect figures are quoted.
"""

from __future__ import annotations

from typing import Sequence

from project_beta.config import RunConfig
from project_beta.data.provider import Bar
from project_beta.execution.fill import BPS
from project_beta.execution.simulator import (
    STARTING_EQUITY,
    BacktestResult,
    Gate,
    _bar_days,
    _to_daily_returns,
    run_backtest,
    session_days,
)
from project_beta.features.registry import FeatureFrame
from project_beta.strategy.base import Strategy


def run_b1(
    bars: Sequence[Bar],
    config: RunConfig,
    *,
    starting_equity: float = STARTING_EQUITY,
) -> BacktestResult:
    """Buy and hold, marked to market at each session close.

    Costs are charged once on entry and once on exit, at the same slippage and
    commission the strategy pays. Giving the benchmark free execution would
    make every comparison against it flattering by exactly the amount the
    strategy's trading costs.
    """
    if not bars:
        return BacktestResult(
            system="B1",
            days=[],
            daily_returns=[],
            equity_curve=[],
            trades=[],
            decisions=[],
            halted=False,
        )

    execution = config.execution
    slip = execution.slippage_bps * execution.cost_multiplier * BPS
    commission_rate = execution.commission_per_share * execution.cost_multiplier

    entry = bars[0].open * (1.0 + slip)
    quantity = starting_equity / entry
    cash = starting_equity - quantity * entry - quantity * commission_rate

    days = _bar_days(bars)
    unique_days = session_days(bars)
    day_end_equity: list[float] = []
    for i, bar in enumerate(bars):
        if i + 1 == len(bars) or days[i + 1] != days[i]:
            mark = bar.close
            if i + 1 == len(bars):
                # The final mark is an exit, so it pays the exit costs. A
                # buy-and-hold curve that never sells reports a position it
                # could not have liquidated at that price.
                mark = bar.close * (1.0 - slip) - commission_rate
            day_end_equity.append(cash + quantity * mark)

    returns = _to_daily_returns(day_end_equity, starting_equity)
    return BacktestResult(
        system="B1",
        days=unique_days[: len(returns)],
        daily_returns=returns,
        equity_curve=day_end_equity,
        trades=[],
        decisions=[],
        halted=False,
    )


def run_b2(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    config: RunConfig,
    strategy: Strategy,
    *,
    starting_equity: float = STARTING_EQUITY,
) -> BacktestResult:
    """The strategy and the risk layer, with no AI in the path at all.

    The control for the whole ladder. Every M-tier number is a difference from
    this one, so it has to be a real system rather than a straw man: it gets
    the same sizing rule, the same stops, the same costs and the same halt
    logic that M2 gets.
    """
    candidates = strategy.generate_candidates(frame, bars, config)
    return run_backtest(
        bars,
        frame,
        candidates,
        config,
        system="B2",
        gate=None,
        starting_equity=starting_equity,
    )


def run_gated(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    config: RunConfig,
    strategy: Strategy,
    gate: Gate,
    *,
    system: str,
    starting_equity: float = STARTING_EQUITY,
) -> BacktestResult:
    """M1 or M2: B2 with one or two gates in front of the risk engine.

    The candidates are generated once and identically; the gate only ever sees
    a candidate B2 would also have taken. That is what makes M-vs-B a paired
    comparison in the statistical sense (EVALUATION_PROTOCOL.md §3) rather than
    a comparison of two different strategies.
    """
    candidates = strategy.generate_candidates(frame, bars, config)
    return run_backtest(
        bars,
        frame,
        candidates,
        config,
        system=system,
        gate=gate,
        starting_equity=starting_equity,
    )
