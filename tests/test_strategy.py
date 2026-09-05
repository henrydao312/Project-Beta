"""Strategy engine tests.

Three of these guard promises made elsewhere in the project documents.

`test_candidate_list_is_byte_identical_across_runs` is PRD §5.3's acceptance
criterion. It would fail on a random `trade_id`, which is the reproducibility
defect that no result would ever reveal - every price, every threshold and
every timestamp would agree, and the diff would still be non-empty.

`test_momentum_has_no_volume_confirmation_term` is the other half of the
feed-transfer verdict. Dropping volume from the models and leaving it in the
strategy rules would mean the live system fires at different moments than the
backtested one, in construction rather than by chance.

`test_secondary_strategy_cannot_enter_a_graded_comparison` is Outline §5.3 and
PRD §5.14 made structural. The exploratory strategies carry no walk-forward
validation and no cost stress, so a Sharpe from one would look exactly like a
result.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from project_beta.config import (
    DataConfig,
    RiskConfig,
    RunConfig,
    StrategyConfig,
)
from project_beta.data.provider import Bar
from project_beta.features import REGISTRY
from project_beta.strategy import (
    CandidateTrade,
    StrategyError,
    TierViolation,
    assert_gradeable,
    build_strategy,
)
from project_beta.strategy.momentum import MomentumBreakout
from project_beta.strategy.secondary import MeanReversion, MovingAverageTrend

ET = ZoneInfo("America/New_York")
DAYS = [date(2026, 8, 24) + timedelta(days=n) for n in range(5)] + [
    date(2026, 8, 31) + timedelta(days=n) for n in range(5)
]


# ------------------------------------------------------------------ fixtures


def _trending_bars(seed: int = 11, drift: float = 0.045) -> list[Bar]:
    """A seeded walk with mild upward drift, so breakouts actually occur.

    Drift rather than noise: a pure random walk produces breakouts too, but
    intermittently enough that a threshold test becomes a test of the seed.
    """
    rng = random.Random(seed)
    price = 550.0
    out: list[Bar] = []
    for day in DAYS:
        cursor = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)
        stop = datetime(day.year, day.month, day.day, 16, 0, tzinfo=ET)
        while cursor < stop:
            step = rng.gauss(drift, 0.22)
            open_, close = price, price + step
            out.append(
                Bar(
                    timestamp=cursor.astimezone(timezone.utc),
                    open=open_,
                    high=max(open_, close) + abs(rng.gauss(0.0, 0.10)),
                    low=min(open_, close) - abs(rng.gauss(0.0, 0.10)),
                    close=close,
                    volume=rng.uniform(500.0, 5000.0),
                    trade_count=rng.randint(5, 200),
                    vwap=close,
                )
            )
            price = close
            cursor += timedelta(minutes=5)
    return out


def _config(**overrides) -> RunConfig:
    strategy = overrides.pop("strategy", StrategyConfig())
    return RunConfig(
        run_id="test_strategy",
        mode="backtest",
        data=DataConfig(
            symbol="SPY",
            timeframe="5Min",
            start=date(2026, 8, 24),
            end=date(2026, 9, 4),
            asset_class="equity",
            feed="sip",
        ),
        risk=RiskConfig(max_drawdown=0.15, daily_loss_limit=500.0, max_position=10_000.0),
        strategy=strategy,
        **overrides,
    )


@pytest.fixture(scope="module")
def bars() -> list[Bar]:
    return _trending_bars()


@pytest.fixture(scope="module")
def frame(bars):
    return REGISTRY.compute(bars)


def _candidates(bars, frame, strategy=None, config=None):
    strategy = strategy or MomentumBreakout()
    return strategy.generate_candidates(frame, bars, config or _config())


# --------------------------------------------------------------- determinism


def test_the_strategy_fires_at_all(bars, frame) -> None:
    """A guard on the other tests: a rule set that never fires passes every
    determinism and safety check trivially."""
    assert len(_candidates(bars, frame)) >= 3


def test_candidate_list_is_byte_identical_across_runs(bars, frame) -> None:
    """PRD §5.3: same data + config => byte-identical candidate list."""
    first = [c.to_dict() for c in _candidates(bars, frame)]
    second = [c.to_dict() for c in _candidates(bars, frame)]
    assert first == second


def test_trade_ids_are_derived_rather_than_drawn(bars, frame) -> None:
    """uuid5 over identifying fields, so two runs agree and a diff means
    something. uuid4 would break reproducibility invisibly."""
    from project_beta.strategy.base import make_trade_id

    for candidate in _candidates(bars, frame):
        assert candidate.trade_id == make_trade_id(
            strategy_version=candidate.strategy_version,
            symbol=candidate.symbol,
            timestamp=candidate.timestamp,
            direction=candidate.direction,
        )


# ------------------------------------------------------------- the volume rule


def test_momentum_has_no_volume_confirmation_term() -> None:
    dropped = {s.name for s in REGISTRY.dropped()}
    assert not set(MomentumBreakout.required_features) & dropped
    assert not any(
        REGISTRY.get(f).volume_derived for f in MomentumBreakout.required_features
    )


def test_candidates_are_unchanged_when_volume_is_rescaled(bars, frame) -> None:
    """The live feed carries ~3% of the backtest feed's volume. If any rule
    read it, the live system would fire at different moments than the
    validated one - a difference in construction, not in luck."""
    rescaled = [
        Bar(
            timestamp=b.timestamp,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume * 31.6,
            trade_count=(b.trade_count or 0) * 29,
            vwap=(b.vwap or 0.0) * 1.5,
        )
        for b in bars
    ]
    baseline = [c.to_dict() for c in _candidates(bars, frame)]
    other = [c.to_dict() for c in _candidates(rescaled, REGISTRY.compute(rescaled))]
    assert other == baseline


# ------------------------------------------------------------------- leakage


def test_candidates_reference_the_deciding_bars_close(bars, frame) -> None:
    """Decide on the close, execute later. The execution layer applies
    fill_delay_bars; generating and filling on the same bar is the most common
    backtest inflation there is."""
    for c in _candidates(bars, frame):
        assert c.entry_price_ref == bars[c.bar_index].close
        assert c.timestamp == bars[c.bar_index].timestamp
        assert c.features_snapshot_id == frame.snapshot_id(c.bar_index)


def test_no_candidate_is_generated_during_warmup(bars, frame) -> None:
    assert all(c.bar_index >= frame.warmup for c in _candidates(bars, frame))


def test_cooldown_is_enforced(bars, frame) -> None:
    """Without it the candidate count measures trend persistence rather than
    signal frequency, and the ablation reports that count."""
    strategy = MomentumBreakout(StrategyConfig(params={"cooldown_bars": 30}))
    indices = [c.bar_index for c in _candidates(bars, frame, strategy)]
    assert all(b - a >= 30 for a, b in pairwise(indices))


# ------------------------------------------------------------------ the tier


def test_secondary_strategy_cannot_enter_a_graded_comparison() -> None:
    assert_gradeable(MomentumBreakout())
    for cls in (MovingAverageTrend, MeanReversion):
        with pytest.raises(TierViolation, match="graded ablation"):
            assert_gradeable(cls(StrategyConfig(name=cls.name, tier="secondary")))


def test_a_config_cannot_promote_an_exploratory_strategy() -> None:
    """Otherwise the structural block is a YAML edit away from gone."""
    config = _config(strategy=StrategyConfig(name="ma_trend", tier="primary"))
    with pytest.raises(StrategyError, match="cannot promote"):
        build_strategy(config)


def test_the_primary_strategy_may_be_demoted() -> None:
    """Demotion is safe and occasionally useful: it is how a parameter sweep
    runs without any chance of its numbers reaching the ladder."""
    config = _config(
        strategy=StrategyConfig(name="momentum_breakout", tier="secondary")
    )
    strategy = build_strategy(config)
    assert strategy.tier == "secondary"
    with pytest.raises(TierViolation):
        assert_gradeable(strategy)


def test_candidates_carry_their_tier(bars, frame) -> None:
    """So a stray results row can be traced back rather than trusted."""
    assert {c.tier for c in _candidates(bars, frame)} == {"primary"}


def test_provenance_carries_the_strategy_and_its_tier() -> None:
    p = _config().provenance()
    assert p["strategy"] == "momentum_breakout"
    assert p["strategy_version"] == "mom_v1"
    assert p["strategy_tier"] == "primary"


# ------------------------------------------------------------- configuration


def test_unknown_parameter_is_refused_rather_than_ignored() -> None:
    """A misspelled threshold would otherwise leave the run reporting
    parameters it did not use."""
    with pytest.raises(StrategyError, match="unknown params"):
        MomentumBreakout(StrategyConfig(params={"min_adxx": 25.0}))


def test_unknown_strategy_name_is_refused() -> None:
    with pytest.raises(StrategyError, match="unknown strategy"):
        build_strategy(_config(strategy=StrategyConfig(name="nope")))


def test_a_strategy_missing_its_features_fails_loudly(bars) -> None:
    """A dropped feature must break the rule that used it, not default it."""
    partial = REGISTRY.compute(bars, names=["ret_1", "rv_12"])
    with pytest.raises(StrategyError, match="requires"):
        MomentumBreakout().generate_candidates(partial, bars, _config())


def test_thresholds_change_the_candidate_count(bars, frame) -> None:
    """Evidence that the parameters are read from the config rather than
    baked into the rules."""
    loose = MomentumBreakout(StrategyConfig(params={"min_adx": 0.0, "min_range_expansion": 0.0}))
    strict = MomentumBreakout(StrategyConfig(params={"min_adx": 60.0}))
    assert len(_candidates(bars, frame, loose)) > len(_candidates(bars, frame, strict))


# ------------------------------------------------------- the candidate contract


def test_every_candidate_is_internally_consistent(bars, frame) -> None:
    for c in _candidates(bars, frame):
        assert 0.0 <= c.signal_strength <= 1.0
        assert c.stop_price < c.entry_price_ref < c.target_price
        assert c.risk_per_unit > 0
        assert c.stop_price > 0


def _candidate(**overrides) -> CandidateTrade:
    base = dict(
        trade_id="t",
        timestamp=datetime(2026, 8, 24, 14, 0, tzinfo=timezone.utc),
        bar_index=200,
        bar_timeframe="5Min",
        asset_class="equity",
        symbol="SPY",
        direction="long",
        signal_strength=0.5,
        signal_type="momentum_breakout",
        entry_price_ref=550.0,
        stop_price=545.0,
        target_price=560.0,
        features_snapshot_id="feat_x",
        strategy_version="mom_v1",
    )
    base.update(overrides)
    return CandidateTrade(**base)


def test_candidate_rejects_an_inverted_stop() -> None:
    with pytest.raises(ValueError, match="stop < entry < target"):
        _candidate(stop_price=555.0)


def test_candidate_rejects_a_zero_risk_trade() -> None:
    """It divides by zero in every R multiple downstream."""
    with pytest.raises(ValueError, match=r"zero-risk|stop < entry"):
        _candidate(stop_price=550.0)


def test_candidate_rejects_an_unbounded_signal_strength() -> None:
    """It becomes a weight in position sizing."""
    with pytest.raises(ValueError, match="signal_strength"):
        _candidate(signal_strength=1.4)


def test_short_candidate_orientation_is_checked() -> None:
    ok = _candidate(direction="short", stop_price=555.0, target_price=540.0)
    assert ok.risk_per_unit == pytest.approx(5.0)
    with pytest.raises(ValueError, match="target < entry < stop"):
        _candidate(direction="short", stop_price=545.0, target_price=560.0)


# ----------------------------------------------------------- the seam itself


@pytest.mark.parametrize("cls", [MovingAverageTrend, MeanReversion])
def test_secondary_strategies_use_the_same_interface(bars, frame, cls) -> None:
    """The seam's whole purpose: a second implementation that needed no change
    to the engine, and inherits the volume drop through the registry."""
    strategy = cls(StrategyConfig(name=cls.name, version=cls.version, tier="secondary"))
    candidates = strategy.generate_candidates(frame, bars, _config())
    assert all(isinstance(c, CandidateTrade) for c in candidates)
    assert all(c.tier == "secondary" for c in candidates)
    assert not any(REGISTRY.get(f).volume_derived for f in cls.required_features)
