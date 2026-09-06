"""Execution, cost and risk-engine tests.

The conventions asserted here are the ones chosen *against* the strategy's
interest, and they are the ones that quietly revert under time pressure:

`test_a_bar_touching_both_stop_and_target_counts_as_a_stop` - a 5-minute bar
hides its path. Assuming the favourable order across thousands of trades is
worth more than any edge the strategy could plausibly find.

`test_the_fill_lands_on_a_later_bar_than_the_decision` - filling at the close
that generated the candidate trades on the information the decision was made
from. It is the single most common way a backtest inflates itself and it looks
completely ordinary in code.

`test_a_gate_cannot_enlarge_a_position` - Outline §1A's claim is that AI gates
trades and never takes them. A gate that could add size would be taking one,
and the project's position outside the LLM provider's high-risk
financial-decisions category rests on that line.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from project_beta.config import (
    DataConfig,
    ExecutionConfig,
    RiskConfig,
    RunConfig,
    StrategyConfig,
)
from project_beta.data.provider import Bar
from project_beta.execution.fill import (
    BarFillModel,
    NoFill,
    SparseBarFillModel,
    build_fill_model,
)
from project_beta.execution.simulator import (
    CompositeGate,
    GateDecision,
    GateError,
    run_backtest,
    session_days,
)
from project_beta.features import REGISTRY
from project_beta.features.registry import FeatureFrame
from project_beta.strategy.base import CandidateTrade, make_trade_id
from project_beta.systems import run_b1, run_b2, run_gated

ET = ZoneInfo("America/New_York")
START_EQUITY = 100_000.0


# ------------------------------------------------------------------ fixtures


def _bar(day: date, n: int, *, o: float, h: float, lo: float, c: float) -> Bar:
    ts = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET) + timedelta(minutes=5 * n)
    return Bar(
        timestamp=ts.astimezone(timezone.utc),
        open=o,
        high=h,
        low=lo,
        close=c,
        volume=1000.0,
        trade_count=10,
        vwap=c,
    )


def _flat_day(day: date, n: int = 12, price: float = 100.0) -> list[Bar]:
    return [_bar(day, i, o=price, h=price, lo=price, c=price) for i in range(n)]


def _config(**overrides) -> RunConfig:
    execution = overrides.pop("execution", ExecutionConfig())
    risk = overrides.pop(
        "risk",
        RiskConfig(max_drawdown=0.15, daily_loss_limit=50_000.0, max_position=1_000_000.0),
    )
    return RunConfig(
        run_id="test_exec",
        mode="backtest",
        data=DataConfig(
            symbol="SPY",
            timeframe="5Min",
            start=date(2026, 8, 24),
            end=date(2026, 8, 28),
            feed="sip",
        ),
        risk=risk,
        strategy=StrategyConfig(),
        execution=execution,
        **overrides,
    )


def _candidate(bars, index: int, *, stop: float, target: float) -> CandidateTrade:
    return CandidateTrade(
        trade_id=make_trade_id(
            strategy_version="mom_v1",
            symbol="SPY",
            timestamp=bars[index].timestamp,
            direction="long",
        ),
        timestamp=bars[index].timestamp,
        bar_index=index,
        bar_timeframe="5Min",
        asset_class="equity",
        symbol="SPY",
        direction="long",
        signal_type="momentum_breakout",
        signal_strength=0.6,
        entry_price_ref=bars[index].close,
        stop_price=stop,
        target_price=target,
        features_snapshot_id="feat_test",
        strategy_version="mom_v1",
    )


def _frame(bars) -> FeatureFrame:
    """A frame with no columns: these tests exercise execution, not features."""
    return FeatureFrame(
        timestamps=[b.timestamp for b in bars], columns={}, names=(), warmup=0
    )


def _run(bars, candidates, config=None, gate=None, system="B2"):
    return run_backtest(
        bars,
        _frame(bars),
        candidates,
        config or _config(),
        system=system,
        gate=gate,
    )


# ------------------------------------------------------------------ the delay


def test_the_fill_lands_on_a_later_bar_than_the_decision() -> None:
    day = date(2026, 8, 24)
    bars = [_bar(day, 0, o=100, h=100, lo=100, c=100)]
    bars.append(_bar(day, 1, o=101, h=101, lo=101, c=101))
    bars += [_bar(day, i, o=101, h=101, lo=101, c=101) for i in range(2, 6)]
    result = _run(bars, [_candidate(bars, 0, stop=95.0, target=110.0)])
    trade = result.trades[0] if result.trades else None
    entry = result.decisions[0]["execution"]
    assert entry["fill_delay_bars"] == 1
    # Filled against bar 1's open (101), not bar 0's close (100).
    assert entry["fill_price"] == pytest.approx(101 * (1 + 1e-4), rel=1e-9)
    assert trade is not None and trade.entry.bar_index == 1


def test_slippage_always_works_against_the_trade() -> None:
    """Symmetric or favourable slippage is a way of paying yourself, and over
    thousands of intraday trades it outweighs any edge."""
    day = date(2026, 8, 24)
    bars = _flat_day(day, 6, 100.0)
    model = BarFillModel(ExecutionConfig(slippage_bps=10.0))
    buy = model.fill(_candidate(bars, 0, stop=95, target=110), bars, 1, side="buy", quantity=1)
    assert buy.price > buy.reference_price
    sell = model.fill(_candidate(bars, 0, stop=95, target=110), bars, 1, side="sell", quantity=1)
    assert sell.price < sell.reference_price


def test_the_cost_multiplier_produces_the_stress_run() -> None:
    """Protocol §9: the 2x and 3x runs use the same code path and one config
    value, so the stressed run cannot drift from the headline one."""
    day = date(2026, 8, 24)
    bars = _flat_day(day, 6, 100.0)
    base = BarFillModel(ExecutionConfig(slippage_bps=10.0, commission_per_share=0.01))
    stressed = BarFillModel(
        ExecutionConfig(slippage_bps=10.0, commission_per_share=0.01, cost_multiplier=2.0)
    )
    c = _candidate(bars, 0, stop=95, target=110)
    a = base.fill(c, bars, 1, side="buy", quantity=100)
    b = stressed.fill(c, bars, 1, side="buy", quantity=100)
    assert b.commission == pytest.approx(2 * a.commission)
    assert b.slippage_cost == pytest.approx(2 * a.slippage_cost)


def test_a_fill_past_the_end_of_the_data_is_a_no_fill() -> None:
    day = date(2026, 8, 24)
    bars = _flat_day(day, 3, 100.0)
    result = BarFillModel(ExecutionConfig()).fill(
        _candidate(bars, 0, stop=95, target=110), bars, 9, side="buy", quantity=1
    )
    assert isinstance(result, NoFill) and result.reason_code == "NO_BAR_AT_FILL"


def test_a_candidate_pending_past_the_last_bar_is_still_logged() -> None:
    """A decision the data could not honour is still a decision.

    An approved candidate on the final bar has a fill index one past the end,
    so the loop ends with it still queued. Dropping it silently breaks the
    every-decision-is-logged contract and undercounts rejections exactly at
    fold boundaries, where the count matters most.
    """
    day = date(2026, 8, 24)
    bars = _flat_day(day, 4, 100.0)
    result = _run(bars, [_candidate(bars, len(bars) - 1, stop=95.0, target=110.0)])
    assert len(result.decisions) == 1
    record = result.decisions[0]
    assert record["decision"] == "rejected"
    assert "NO_BAR_AT_FILL" in record["decision_reason_codes"]
    assert record["instrument"]["tradeable"] is False
    assert result.trades == []


def test_the_quote_fill_model_has_no_implementation() -> None:
    """Declared so the vendor limit stays visible, not so it can be selected."""
    config = _config()
    object.__setattr__(config.execution, "fill_model", "quote")
    with pytest.raises(ValueError, match="no implementation"):
        build_fill_model(config)


def test_the_options_fill_model_is_selected_by_config() -> None:
    config = _config(execution=ExecutionConfig(fill_model="sparse_bar"))
    assert isinstance(build_fill_model(config), SparseBarFillModel)


# -------------------------------------------------------------- exit ordering


def test_a_bar_touching_both_stop_and_target_counts_as_a_stop() -> None:
    day = date(2026, 8, 24)
    bars = [
        _bar(day, 0, o=100, h=100, lo=100, c=100),
        _bar(day, 1, o=100, h=100, lo=100, c=100),
        _bar(day, 2, o=100, h=110, lo=95, c=100),  # touches both
        _bar(day, 3, o=100, h=100, lo=100, c=100),
    ]
    result = _run(bars, [_candidate(bars, 0, stop=95.0, target=110.0)])
    assert [t.exit_reason for t in result.trades] == ["stop"]


def test_a_position_is_flattened_before_the_close() -> None:
    """An intraday strategy holding overnight collects gap drift it never
    modelled and was never exposed to live."""
    bars = _flat_day(date(2026, 8, 24), 5, 100.0) + _flat_day(date(2026, 8, 25), 5, 100.0)
    result = _run(bars, [_candidate(bars, 0, stop=90.0, target=120.0)])
    assert [t.exit_reason for t in result.trades] == ["session_end"]
    assert result.trades[0].exit_bar_index == 4


def test_max_hold_bars_closes_a_position_that_never_resolves() -> None:
    bars = _flat_day(date(2026, 8, 24), 12, 100.0)
    config = _config(execution=ExecutionConfig(max_hold_bars=3))
    result = _run(bars, [_candidate(bars, 0, stop=90.0, target=120.0)], config)
    assert [t.exit_reason for t in result.trades] == ["max_hold"]


# ------------------------------------------------------------- the risk engine


def test_position_size_is_capped_by_max_position() -> None:
    bars = _flat_day(date(2026, 8, 24), 6, 100.0)
    config = _config(
        risk=RiskConfig(
            max_drawdown=0.15,
            daily_loss_limit=50_000.0,
            max_position=1_000.0,
            risk_per_trade=0.5,
        )
    )
    result = _run(bars, [_candidate(bars, 0, stop=99.0, target=110.0)], config)
    assert "RISK_SIZE_CAPPED" in result.decisions[0]["decision_reason_codes"]
    assert result.trades[0].quantity == pytest.approx(10.0)


def test_only_one_position_is_open_at_a_time() -> None:
    bars = _flat_day(date(2026, 8, 24), 12, 100.0)
    candidates = [
        _candidate(bars, 0, stop=90.0, target=120.0),
        _candidate(bars, 2, stop=90.0, target=120.0),
    ]
    result = _run(bars, candidates)
    assert len(result.trades) == 1
    assert "RISK_POSITION_OPEN" in result.decisions[1]["decision_reason_codes"]


def test_the_drawdown_kill_switch_halts_the_run() -> None:
    """Outline §8A. A halted run reports the halt rather than quietly ending."""
    day = date(2026, 8, 24)
    bars = [
        _bar(day, 0, o=100, h=100, lo=100, c=100),
        _bar(day, 1, o=100, h=100, lo=100, c=100),
        _bar(day, 2, o=100, h=100, lo=50, c=60),  # deep stop
        _bar(day, 3, o=60, h=60, lo=60, c=60),
        _bar(day, 4, o=60, h=60, lo=60, c=60),
    ]
    config = _config(
        risk=RiskConfig(
            max_drawdown=0.02,
            daily_loss_limit=1_000_000.0,
            max_position=1_000_000.0,
            risk_per_trade=0.5,
        )
    )
    result = _run(bars, [_candidate(bars, 0, stop=90.0, target=120.0)], config)
    assert result.halted
    assert result.halt_reason == "RISK_DRAWDOWN_HALT"


def test_the_daily_loss_limit_stops_the_day_and_not_the_run() -> None:
    losing = [
        _bar(date(2026, 8, 24), 0, o=100, h=100, lo=100, c=100),
        _bar(date(2026, 8, 24), 1, o=100, h=100, lo=100, c=100),
        _bar(date(2026, 8, 24), 2, o=100, h=100, lo=94, c=94),
        _bar(date(2026, 8, 24), 3, o=94, h=94, lo=94, c=94),
        _bar(date(2026, 8, 24), 4, o=94, h=94, lo=94, c=94),
    ]
    quiet = _flat_day(date(2026, 8, 25), 5, 94.0)
    bars = losing + quiet
    config = _config(
        risk=RiskConfig(
            max_drawdown=0.90,
            daily_loss_limit=100.0,
            max_position=1_000_000.0,
            risk_per_trade=0.05,
        )
    )
    candidates = [
        _candidate(bars, 0, stop=95.0, target=120.0),
        _candidate(bars, 3, stop=90.0, target=120.0),   # same day, after the loss
        _candidate(bars, 5, stop=90.0, target=120.0),   # next day, allowed again
    ]
    result = _run(bars, candidates, config)
    assert not result.halted, "a daily limit must not end the run"
    codes = [d["decision_reason_codes"] for d in result.decisions]
    assert any("RISK_DAILY_LOSS_HALT" in c for c in codes)
    assert len(result.trades) >= 2, "the next day trades again"


# ----------------------------------------------------------------- the gates


class _RejectAll:
    name = "reject_all"

    def evaluate(self, candidate, frame, index):
        return GateDecision(decision="rejected", reason_codes=("REGIME_BLOCKS",))


class _HalfSize:
    name = "half"

    def evaluate(self, candidate, frame, index):
        return GateDecision(
            decision="reduced",
            reason_codes=("REGIME_REDUCES",),
            size_multiplier=0.5,
            detail={"regime": {"label": "choppy"}},
        )


class _Enlarge:
    name = "enlarge"

    def evaluate(self, candidate, frame, index):
        return GateDecision(
            decision="approved", reason_codes=("REGIME_PERMITS",), size_multiplier=1.5
        )


def test_a_gate_cannot_enlarge_a_position() -> None:
    with pytest.raises(GateError, match="may reject or shrink"):
        _Enlarge().evaluate(None, None, 0)


def test_a_gate_cannot_invent_a_reason_code() -> None:
    """Free-text reasons cannot be counted, and counting them is the
    failure-analysis assistant's entire job (PRD §4.2)."""
    with pytest.raises(GateError, match="documented enum"):
        GateDecision(decision="approved", reason_codes=("LOOKED_GOOD",))


def test_a_rejecting_gate_removes_the_trade_but_not_the_record() -> None:
    """A rejection is data. Dropping it would make the approval rate
    unmeasurable and hide the gate's behaviour from failure analysis."""
    bars = _flat_day(date(2026, 8, 24), 8, 100.0)
    candidate = _candidate(bars, 0, stop=90.0, target=120.0)
    gated = _run(bars, [candidate], gate=_RejectAll(), system="M1")
    assert gated.trades == []
    assert len(gated.decisions) == 1
    assert gated.decisions[0]["decision"] == "rejected"
    assert gated.approval_rate == 0.0


def test_a_shrinking_gate_halves_the_position() -> None:
    bars = _flat_day(date(2026, 8, 24), 8, 100.0)
    candidate = _candidate(bars, 0, stop=99.0, target=110.0)
    plain = _run(bars, [candidate])
    reduced = _run(bars, [candidate], gate=_HalfSize(), system="M1")
    assert reduced.trades[0].quantity == pytest.approx(plain.trades[0].quantity / 2)
    assert reduced.decisions[0]["decision"] == "reduced"
    assert reduced.decisions[0]["regime"]["label"] == "choppy"


def test_composite_gates_compound_and_any_rejection_is_final() -> None:
    both = CompositeGate([_HalfSize(), _HalfSize()])
    assert both.evaluate(None, None, 0).size_multiplier == pytest.approx(0.25)
    stopped = CompositeGate([_RejectAll(), _HalfSize()])
    verdict = stopped.evaluate(None, None, 0)
    assert verdict.decision == "rejected" and verdict.size_multiplier == 0.0


def test_an_ungated_system_records_that_fact() -> None:
    """B2 has no AI in the path, and its records say so rather than being
    silent about it."""
    bars = _flat_day(date(2026, 8, 24), 8, 100.0)
    result = _run(bars, [_candidate(bars, 0, stop=99.0, target=110.0)])
    assert "NO_GATE" in result.decisions[0]["decision_reason_codes"]


# --------------------------------------------------------------- the ladder


def test_every_system_reports_the_same_days(bars_and_frame) -> None:
    """The paired bootstrap needs the same days in the same order. Building
    both series from a shared day index makes that structural."""
    bars, frame, config, strategy = bars_and_frame
    b1 = run_b1(bars, config)
    b2 = run_b2(bars, frame, config, strategy)
    m1 = run_gated(bars, frame, config, strategy, _HalfSize(), system="M1")
    assert b1.days == b2.days == m1.days == session_days(bars)
    assert len(b1.daily_returns) == len(b2.daily_returns) == len(m1.daily_returns)


def test_a_gate_can_only_remove_what_b2_would_have_taken(bars_and_frame) -> None:
    """The pairing that makes the comparison tractable: M-tier systems trade a
    subset of B2's signals, so the shared component cancels in the difference."""
    bars, frame, config, strategy = bars_and_frame
    b2 = run_b2(bars, frame, config, strategy)
    m1 = run_gated(bars, frame, config, strategy, _RejectAll(), system="M1")
    b2_ids = {t.candidate.trade_id for t in b2.trades}
    m1_ids = {t.candidate.trade_id for t in m1.trades}
    assert m1_ids <= b2_ids
    assert m1.trades == []


def test_the_backtest_is_deterministic(bars_and_frame) -> None:
    bars, frame, config, strategy = bars_and_frame
    first = run_b2(bars, frame, config, strategy)
    second = run_b2(bars, frame, config, strategy)
    assert first.daily_returns == second.daily_returns
    assert first.equity_curve == second.equity_curve
    assert [t.pnl for t in first.trades] == [t.pnl for t in second.trades]


def test_buy_and_hold_pays_the_same_costs_the_strategy_pays() -> None:
    """Giving the benchmark free execution flatters every comparison against
    it by exactly the strategy's trading costs."""
    bars = _flat_day(date(2026, 8, 24), 6, 100.0) + _flat_day(date(2026, 8, 25), 6, 100.0)
    config = _config(execution=ExecutionConfig(slippage_bps=50.0))
    free = _config(execution=ExecutionConfig(slippage_bps=0.0))
    assert run_b1(bars, config).equity_curve[-1] < run_b1(bars, free).equity_curve[-1]
    assert run_b1(bars, free).equity_curve[-1] == pytest.approx(START_EQUITY)


def test_the_decision_record_carries_its_mandatory_provenance(bars_and_frame) -> None:
    """PRD §4.2: asset_class, feed and vendor are mandatory. A record without
    them cannot be traced back to the data it came from."""
    bars, frame, config, strategy = bars_and_frame
    record = run_b2(bars, frame, config, strategy).decisions[0]
    for key in ("asset_class", "feed", "vendor", "run_id", "decision_id", "trade_id"):
        assert record[key] is not None, key
    assert record["instrument"]["selection_rule"] == "passthrough_v1"
    assert record["instrument"]["tradeable"] is True


def test_a_resolved_trade_writes_its_outcome_back_to_the_record(bars_and_frame) -> None:
    """The explanation service may only cite fields of this record, so the
    outcome has to be in it (Outline §20.2 harm 2)."""
    bars, frame, config, strategy = bars_and_frame
    result = run_b2(bars, frame, config, strategy)
    resolved = [d for d in result.decisions if "outcome" in d]
    assert resolved
    outcome = resolved[0]["outcome"]
    assert set(outcome) >= {"exit_reason", "pnl", "mae", "mfe", "r_multiple"}


# ------------------------------------------------------------------- fixture


@pytest.fixture(scope="module")
def bars_and_frame():
    import random

    from project_beta.strategy.momentum import MomentumBreakout

    rng = random.Random(11)
    price = 550.0
    bars: list[Bar] = []
    day = date(2026, 3, 2)
    while len(bars) < 78 * 30:
        if day.weekday() < 5:
            cursor = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)
            stop = cursor.replace(hour=16, minute=0)
            while cursor < stop:
                step = rng.gauss(0.012, 0.22)
                o, c = price, price + step
                bars.append(
                    Bar(
                        timestamp=cursor.astimezone(timezone.utc),
                        open=o,
                        high=max(o, c) + abs(rng.gauss(0.0, 0.1)),
                        low=min(o, c) - abs(rng.gauss(0.0, 0.1)),
                        close=c,
                        volume=1000.0,
                    )
                )
                price = c
                cursor += timedelta(minutes=5)
        day += timedelta(days=1)
    config = _config()
    return bars, REGISTRY.compute(bars), config, MomentumBreakout()
