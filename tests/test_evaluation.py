"""Evaluation tests: folds, metrics, the paired bootstrap, and the decision rule.

The decision-rule tests are the ones that matter most, because the rule is the
project's defence against the most natural failure in applied research -
looking at the answer and then choosing the test. EVALUATION_PROTOCOL.md was
locked on 2026-09-02, before any M-tier model existed, and these encode all
three of its conditions:

  1. the 95% bootstrap interval on ΔSharpe excludes zero
  2. the point estimate is at least +0.20 annualised Sharpe
  3. the sign survives the 2x cost-stress run

`test_a_significant_but_trivial_difference_is_not_an_improvement` is condition
2 in executable form, and it is the one a busy semester would quietly drop.
`test_the_fold_count_matches_the_published_figures` guards the arithmetic every
document in the repo quotes.
"""

from __future__ import annotations

import math
import random
from datetime import date
from itertools import pairwise

import pytest

from project_beta.config import (
    DataConfig,
    RiskConfig,
    RunConfig,
    StrategyConfig,
    WalkForwardConfig,
    load_run_config,
)
from project_beta.evaluation.bootstrap import (
    BootstrapError,
    paired_sharpe_difference,
    stationary_block_indices,
)
from project_beta.evaluation.folds import (
    FoldError,
    add_months,
    generate_folds,
    pooled_test_span,
)
from project_beta.evaluation.harness import (
    MATERIALITY_FLOOR,
    FoldReturns,
    SharpeNotApplicable,
    compare,
    fold_sign_count,
    ladder,
    periods_per_year,
    pool,
    pooled_days,
    require_performance_claim,
)
from project_beta.evaluation.metrics import (
    annualised_sharpe,
    calmar,
    exposure,
    hit_rate,
    max_drawdown,
    profit_factor,
    summarise,
)
from project_beta.strategy import TierViolation
from project_beta.strategy.momentum import MomentumBreakout
from project_beta.strategy.secondary import MovingAverageTrend

RESAMPLES = 200  # the protocol's 10,000 is for results, not for a test suite


DEFAULT_WF = WalkForwardConfig()


def _config(
    *,
    asset_class: str = "equity",
    start: date = date(2016, 6, 10),
    end: date = date(2026, 6, 30),
    walk_forward: WalkForwardConfig | None = DEFAULT_WF,
    feed: str | None = "sip",
    session: str = "rth_only",
    strategy: StrategyConfig | None = None,
) -> RunConfig:
    return RunConfig(
        run_id="test_eval",
        mode="backtest",
        data=DataConfig(
            symbol="SPY",
            timeframe="5Min",
            start=start,
            end=end,
            asset_class=asset_class,
            feed=feed,
            session=session,
        ),
        risk=RiskConfig(max_drawdown=0.15, daily_loss_limit=500.0, max_position=10_000.0),
        strategy=strategy or StrategyConfig(),
        walk_forward=walk_forward,
    )


# ------------------------------------------------------------------- folds


def test_the_fold_count_matches_the_published_figures() -> None:
    """14 equity, 4 crypto, 0 options. Every document in the repo quotes these,
    and the tier structure rests on the third being zero."""
    assert len(generate_folds(load_run_config("configs/example_backtest.yaml"))) == 14
    assert len(generate_folds(load_run_config("configs/example_crypto.yaml"))) == 4
    assert len(generate_folds(load_run_config("configs/example_options.yaml"))) == 0


def test_folds_agree_with_the_config_arithmetic() -> None:
    """Two independent implementations of the same count. If they diverge, one
    of them is wrong and the published figures came from whichever ran."""
    for name in ("example_backtest", "example_crypto", "example_options"):
        config = load_run_config(f"configs/{name}.yaml")
        assert len(generate_folds(config)) == config.fold_count()


def test_every_fold_orders_train_then_validation_then_test() -> None:
    for fold in generate_folds(_config()):
        assert fold.train_start < fold.train_end == fold.validation_start
        assert fold.validation_start < fold.validation_end == fold.test_start
        assert fold.test_start < fold.test_end


def test_test_windows_never_overlap() -> None:
    """Each out-of-sample day is used exactly once, which is what lets the
    fourteen test windows be pooled into one series (protocol §2)."""
    folds = generate_folds(_config())
    for earlier, later in pairwise(folds):
        assert later.test_start >= earlier.test_end


def test_pooled_span_is_the_documented_seven_years() -> None:
    span = pooled_test_span(generate_folds(_config()))
    assert span is not None
    start, end = span
    months = (end.year - start.year) * 12 + end.month - start.month
    assert months == 84, "protocol §5 quotes 84 out-of-sample months"


def test_a_step_shorter_than_the_test_window_is_refused() -> None:
    """Overlapping test windows would double-count days and every interval
    computed from the pooled series would be too narrow."""
    config = _config(walk_forward=WalkForwardConfig(step_months=3))
    with pytest.raises(FoldError, match="overlap"):
        generate_folds(config)


def test_absence_of_a_walk_forward_block_yields_no_folds() -> None:
    """Absence is meaningful. Inventing a default scheme here would silently
    manufacture a performance claim for a run that declined to make one."""
    assert generate_folds(_config(walk_forward=None)) == []


def test_month_arithmetic_clamps_rather_than_rolling_over() -> None:
    """31 January plus a month is 28 February. Rolling into March would drift
    the fold boundaries and break the disjointness at the seams."""
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2026, 6, 10), 42) == date(2029, 12, 10)


def test_window_of_is_the_only_membership_question() -> None:
    fold = generate_folds(_config())[0]
    assert fold.window_of(fold.train_start) == "train"
    assert fold.window_of(fold.validation_start) == "validation"
    assert fold.window_of(fold.test_start) == "test"
    assert fold.window_of(fold.test_end) is None


# ----------------------------------------------------------------- metrics


def test_sharpe_of_a_known_series() -> None:
    returns = [0.01, -0.005, 0.02, 0.0, 0.015]
    expected = (
        sum(returns) / len(returns)
        / (sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / 4) ** 0.5
        * math.sqrt(252)
    )
    assert annualised_sharpe(returns) == pytest.approx(expected)


def test_a_degenerate_series_gives_nan_rather_than_zero() -> None:
    """0.0 in a results table reads as 'no edge'. The truth is 'no estimate',
    and they are different claims."""
    assert math.isnan(annualised_sharpe([0.01, 0.01, 0.01]))
    assert math.isnan(annualised_sharpe([0.01]))


def test_max_drawdown_of_a_known_path() -> None:
    """Up 20%, down 50% from the peak, back up: the answer is 0.5."""
    assert max_drawdown([0.2, -0.5, 0.1]) == pytest.approx(0.5)
    assert max_drawdown([0.01, 0.01, 0.01]) == pytest.approx(0.0)


def test_secondary_metrics_behave() -> None:
    returns = [0.02, -0.01, 0.03, 0.0, -0.005]
    assert profit_factor(returns) == pytest.approx(0.05 / 0.015)
    assert hit_rate(returns) == pytest.approx(0.5)
    assert exposure(returns) == pytest.approx(0.8)
    assert calmar(returns) > 0


def test_crypto_annualises_on_365_days() -> None:
    """A 24/7 tape has no weekends. Annualising it on 252 would inflate its
    Sharpe by about 20% against the equity core it is compared with."""
    equity = _config()
    crypto = _config(
        asset_class="crypto",
        feed=None,
        session="continuous",
        start=date(2021, 6, 10),
        end=date(2026, 8, 31),
    )
    assert periods_per_year(equity) == 252
    assert periods_per_year(crypto) == 365


def test_summary_carries_provenance_into_the_row() -> None:
    """Outline §7B seam 3: the comparability caveat belongs in the data. A
    crypto Sharpe without its fold count will be read as if it were the core's."""
    row = summarise([0.01, -0.02, 0.03], system="B2").to_dict(_config().provenance())
    assert row["system"] == "B2"
    assert row["run_n_folds"] == 14
    assert row["run_tier"] == "graded_core"


# --------------------------------------------------------------- bootstrap


def _paired_series(n: int = 1000, shift: float = 0.0, seed: int = 5):
    """A control series and a treatment that adds a constant daily shift.

    A constant makes the two series perfectly correlated, which is the extreme
    of the pairing that makes this comparison tractable at all, and gives a
    tight interval whose centre is easy to reason about.
    """
    rng = random.Random(seed)
    control = [rng.gauss(0.0004, 0.01) for _ in range(n)]
    return [c + shift for c in control], control


def test_the_bootstrap_is_reproducible_from_the_seed() -> None:
    """The protocol requires the seed to be recorded in the RunConfig; that is
    only meaningful if it determines the answer."""
    a, b = _paired_series(shift=0.0001)
    first = paired_sharpe_difference(a, b, seed=42, resamples=RESAMPLES)
    second = paired_sharpe_difference(a, b, seed=42, resamples=RESAMPLES)
    other = paired_sharpe_difference(a, b, seed=43, resamples=RESAMPLES)
    assert (first.low, first.high, first.point) == (second.low, second.high, second.point)
    assert (other.low, other.high) != (first.low, first.high)


def test_misaligned_series_are_refused() -> None:
    """Silently accepting them would break the pairing and widen the interval
    with no visible symptom."""
    with pytest.raises(BootstrapError, match="aligned"):
        paired_sharpe_difference([0.01] * 10, [0.01] * 9, seed=42)


def test_the_interval_contains_the_point_estimate() -> None:
    a, b = _paired_series(shift=0.0002)
    interval = paired_sharpe_difference(a, b, seed=42, resamples=RESAMPLES)
    assert interval.low <= interval.point <= interval.high


def test_identical_series_give_a_zero_difference() -> None:
    a, _ = _paired_series()
    interval = paired_sharpe_difference(a, a, seed=42, resamples=50)
    assert interval.point == pytest.approx(0.0, abs=1e-12)
    assert not interval.excludes_zero


def test_block_lengths_average_the_requested_expectation() -> None:
    """Politis-Romano blocks are geometric with mean `expected_block`. Fixed
    blocks would make the resampled series non-stationary at the boundaries."""
    import numpy as np

    rng = np.random.default_rng(0)
    breaks = 0
    draws = 40
    n = 500
    for _ in range(draws):
        idx = stationary_block_indices(n, expected_block=10, rng=rng)
        breaks += sum(1 for a, b in pairwise(idx) if b != (a + 1) % n)
    mean_block = (draws * n) / max(breaks, 1)
    assert 6.0 < mean_block < 16.0


# ----------------------------------------------------------- the two refusals


def test_options_cannot_be_given_a_sharpe() -> None:
    """31 months, zero folds. NaN would get filled in later by somebody;
    an exception will not."""
    config = _config(
        asset_class="option",
        feed=None,
        start=date(2024, 1, 18),
        end=date(2026, 8, 31),
        walk_forward=None,
    )
    with pytest.raises(SharpeNotApplicable, match="no strategy-performance claim"):
        require_performance_claim(config)


def test_a_configuration_with_no_folds_cannot_make_a_claim() -> None:
    short = _config(start=date(2024, 1, 2), end=date(2026, 1, 2))
    with pytest.raises(SharpeNotApplicable, match="no complete walk-forward fold"):
        require_performance_claim(short)


def test_an_exploratory_strategy_cannot_reach_the_harness() -> None:
    """Outline §5.3 and PRD §5.14, structurally rather than by documentation."""
    strategy = MovingAverageTrend(StrategyConfig(name="ma_trend", tier="secondary"))
    with pytest.raises(TierViolation):
        require_performance_claim(_config(), strategy)
    require_performance_claim(_config(), MomentumBreakout())


# ------------------------------------------------------------- pooled series


def _fold_returns(
    n_per_fold: int = 250,
    *,
    shift: float = 0.0,
    n_folds: int = 4,
    seed: int = 9,
) -> list[FoldReturns]:
    rng = random.Random(seed)
    folds = generate_folds(_config())[:n_folds]
    out: list[FoldReturns] = []
    for f in folds:
        control = [rng.gauss(0.0004, 0.01) for _ in range(n_per_fold)]
        days = [f"{f.index}-{i}" for i in range(n_per_fold)]
        out.append(
            FoldReturns(
                fold=f,
                days=days,
                returns={
                    "B1": [rng.gauss(0.0003, 0.011) for _ in range(n_per_fold)],
                    "B2": control,
                    "M1": [c + shift / 2 for c in control],
                    "M2": [c + shift for c in control],
                },
            )
        )
    return out


def test_pooling_concatenates_the_test_windows_in_order() -> None:
    fr = _fold_returns(n_per_fold=10)
    pooled = pool(fr, "B2")
    assert pooled == [r for f in fr for r in f.returns["B2"]]
    assert len(pooled) == 40


def test_a_repeated_out_of_sample_day_is_refused() -> None:
    """Every interval computed from a series with a duplicated day is too
    narrow, and nothing about the number would look wrong."""
    fr = _fold_returns(n_per_fold=5, n_folds=2)
    clashing = [
        FoldReturns(fold=f.fold, days=["same"] * 5, returns=f.returns) for f in fr
    ]
    with pytest.raises(ValueError, match="repeated day"):
        pooled_days(clashing)


def test_a_missing_system_is_named_rather_than_skipped() -> None:
    fr = _fold_returns(n_per_fold=5, n_folds=1)
    with pytest.raises(KeyError, match="M3"):
        pool(fr, "M3")


def test_fold_returns_must_align_with_their_days() -> None:
    fold = generate_folds(_config())[0]
    with pytest.raises(ValueError, match="returns for"):
        FoldReturns(fold=fold, days=[1, 2, 3], returns={"B2": [0.1, 0.2]})


# ------------------------------------------------------- the decision rule


def _compare(shift: float, *, stress_shift: float | None = None, **kw):
    fr = _fold_returns(shift=shift)
    stress = None
    if stress_shift is not None:
        base = pool(fr, "B2")
        stress = {"B2": base, "M2": [b + stress_shift for b in base]}
    return compare(
        fr,
        treatment="M2",
        control="B2",
        config=_config(),
        cost_stress_returns=stress,
        resamples=RESAMPLES,
        **kw,
    )


def test_a_real_material_improvement_is_claimed() -> None:
    """All three conditions hold, so the verdict is an improvement."""
    result = _compare(0.00016, stress_shift=0.00012)
    assert result.interval.point >= MATERIALITY_FLOOR
    assert result.interval.excludes_zero
    assert result.failures == ()
    assert result.verdict == "improvement"
    assert result.claims_improvement


def test_a_significant_but_trivial_difference_is_not_an_improvement() -> None:
    """Protocol §4 condition 2, the materiality floor. Without it a detectable
    but economically meaningless difference would be reported as a win, and
    this is the condition a busy semester would quietly drop."""
    result = _compare(0.00002, stress_shift=0.00002)
    assert result.interval.excludes_zero, "the effect is detectable"
    assert 0 < result.interval.point < MATERIALITY_FLOOR
    assert result.verdict == "no_claim"
    assert any("materiality floor" in f for f in result.failures)


def test_an_interval_spanning_zero_is_not_an_improvement() -> None:
    result = _compare(0.0, stress_shift=0.0)
    assert result.verdict == "no_claim"
    assert any("includes zero" in f for f in result.failures)


def test_an_effect_that_dies_under_cost_stress_is_not_an_improvement() -> None:
    """Protocol §4 condition 3. Base costs are optimistic by construction."""
    result = _compare(0.00016, stress_shift=-0.00016)
    assert any("2x costs" in f for f in result.failures)
    assert result.verdict == "no_claim"


def test_a_missing_cost_stress_run_fails_the_condition() -> None:
    """An unevaluated condition is a failed one, not a skipped one."""
    result = _compare(0.00016)
    assert any("cost-stress" in f for f in result.failures)
    assert result.verdict == "no_claim"


def test_ladder_rungs_carry_no_claim() -> None:
    """Protocol §6: one primary comparison. Claiming on four comparisons is
    claiming four times."""
    rungs = ladder(_fold_returns(shift=0.0002), config=_config(), resamples=RESAMPLES)
    assert [(c.treatment, c.control) for c in rungs] == [
        ("B2", "B1"),
        ("M1", "B2"),
        ("M2", "M1"),
        ("M2", "B2"),
    ]
    for rung in rungs[:3]:
        assert not rung.is_primary
        assert not rung.claims_improvement
        assert "ladder rung" in rung.verdict
    assert rungs[-1].is_primary


def test_fold_sign_count_is_reported_as_a_shape_not_a_test() -> None:
    fr = _fold_returns(shift=0.001)
    won, total = fold_sign_count(fr, "M2", "B2")
    assert total == 4 and won == 4
    result = compare(
        fr, treatment="M2", control="B2", config=_config(), resamples=50
    )
    assert result.fold_sign_count == (4, 4)
    assert "folds won: 4/4" in result.summary()


def test_a_comparison_row_carries_its_provenance() -> None:
    result = _compare(0.0001, stress_shift=0.0001)
    row = result.to_dict(_config().provenance())
    assert row["run_strategy_tier"] == "primary"
    assert row["run_fold_scheme"] == "30/6/6+6"
    assert row["bootstrap_seed"] == 42
    assert row["verdict"] in {"improvement", "no_claim"}
