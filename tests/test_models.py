"""M1 and M2: the models, the gates, and the four rules that keep folds honest.

The leakage tests are the point of this file. Three of them assert structure
rather than behaviour, because the defects they catch improve results and leave
no trace:

`test_the_training_window_is_embargoed` - regime labels read HORIZON_BARS
ahead, so the last session of a training window carries labels computed from
validation-window prices. The runner drops those rows; this asserts it by
capturing the indices the model was actually fitted on.

`test_the_threshold_is_chosen_on_validation_rows_only` - the whole reason the
30/6/6 scheme carries a validation window. This captures the rows handed to
`choose_threshold` and asserts none of them come from the test window.

`test_the_scaler_is_fitted_on_training_data_only` - fitting a scaler on train
and test together leaks the test window's location and spread into every
training row, and is the single most common defect in walk-forward code.

`test_no_signal_quality_rejection_occurs_in_an_abstaining_regime` is PRD §5.5's
named acceptance criterion, and Outline §20.3's fairness mitigation as
something that runs rather than something that was promised.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from project_beta.config import (
    DataConfig,
    ModelsConfig,
    RegimeLabelConfig,
    RiskConfig,
    RunConfig,
    StrategyConfig,
    WalkForwardConfig,
)
from project_beta.data.calendar import is_trading_day
from project_beta.data.provider import Bar
from project_beta.evaluation.folds import generate_folds
from project_beta.evaluation.runner import (
    CONDITION_3_FACTOR,
    _index_ranges,
    base_folds,
    evaluate,
    run_fold,
    run_walk_forward,
    stressed_config,
    stressed_folds,
)
from project_beta.execution.simulator import CompositeGate
from project_beta.features import REGISTRY
from project_beta.models.calibration import brier_score, calibration_report
from project_beta.models.labels import (
    EMBARGO_BARS,
    HORIZON_BARS,
    TREND_STATES,
    label_distribution,
    label_regimes,
)
from project_beta.models.linear import LogisticRegression, StandardScaler
from project_beta.models.regime import RegimeGate, RegimeModel, RegimeModelError
from project_beta.models.signal_quality import (
    SignalQualityGate,
    SignalQualityModel,
    TrainingRow,
)
from project_beta.strategy.momentum import MomentumBreakout

ET = ZoneInfo("America/New_York")


# ------------------------------------------------------------------ fixtures


def _series(start: date, end: date, seed: int = 4) -> list[Bar]:
    rng = random.Random(seed)
    price, bars, vol = 400.0, [], 0.20
    day = start
    while day < end:
        if is_trading_day(day):
            vol = max(0.08, min(0.45, vol + rng.gauss(0.0, 0.012)))
            drift = rng.gauss(0.0, 0.02)
            cursor = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)
            stop = cursor.replace(hour=16, minute=0)
            while cursor < stop:
                step = rng.gauss(drift, vol)
                o, c = price, max(1.0, price + step)
                bars.append(
                    Bar(
                        timestamp=cursor.astimezone(timezone.utc),
                        open=o,
                        high=max(o, c) + abs(rng.gauss(0.0, vol * 0.4)),
                        low=min(o, c) - abs(rng.gauss(0.0, vol * 0.4)),
                        close=c,
                        volume=rng.uniform(1e3, 1e4),
                        trade_count=50,
                        vwap=c,
                    )
                )
                price = c
                cursor += timedelta(minutes=5)
        day += timedelta(days=1)
    return bars


def _config(start: date, end: date) -> RunConfig:
    return RunConfig(
        run_id="test_models",
        mode="backtest",
        data=DataConfig(symbol="SPY", timeframe="5Min", start=start, end=end, feed="sip"),
        risk=RiskConfig(
            max_drawdown=0.25,
            daily_loss_limit=3000.0,
            max_position=200_000.0,
            risk_per_trade=0.01,
        ),
        strategy=StrategyConfig(),
        walk_forward=WalkForwardConfig(
            train_months=12, validation_months=3, test_months=3, step_months=3
        ),
    )


@pytest.fixture(scope="module")
def world():
    start, end = date(2022, 1, 3), date(2023, 10, 3)
    bars = _series(start, end)
    config = _config(start, end)
    return bars, REGISTRY.compute(bars), config, MomentumBreakout()


# -------------------------------------------------------------------- labels


def test_labels_describe_the_future_rather_than_the_present(world) -> None:
    """Contemporaneous labels would make M1 a model trained to reproduce an
    `if` statement: near-perfect fit, nothing added over B2, an ablation rung
    that measures nothing."""
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    i = next(i for i, value in enumerate(labels) if value is not None)
    label = labels[i]
    assert label is not None
    expected = math.log(bars[i + HORIZON_BARS].close / bars[i].close)
    assert label.forward_return == pytest.approx(expected)


def test_the_final_bars_carry_no_label(world) -> None:
    """The future they would describe has not happened. It is not filled in."""
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    assert all(label is None for label in labels[-HORIZON_BARS:])


def test_labels_are_absent_during_feature_warmup(world) -> None:
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    assert all(label is None for label in labels[: frame.warmup])


def test_all_three_trend_states_occur(world) -> None:
    """A labelling scheme that produces two states in two years is a scheme
    whose thresholds are wrong, and the classifier would inherit that."""
    bars, frame, _, _ = world
    counts = label_distribution(label_regimes(bars, frame))
    assert set(counts) == set(TREND_STATES)
    assert all(v > 0 for v in counts.values())


def test_labelling_needs_a_volatility_scale(world) -> None:
    """Fixed percentage thresholds would call a 0.3% move a trend in a calm
    month and noise in a violent one, and the folds span both."""
    bars, _, _, _ = world
    bare = REGISTRY.compute(bars, names=["ret_1"])
    with pytest.raises(ValueError, match="rv_78"):
        label_regimes(bars, bare)


# ------------------------------------------------------------------- leakage


def test_the_training_window_is_embargoed(world, monkeypatch) -> None:
    """Regime labels read HORIZON_BARS ahead, so the last session of the
    training window peeks into validation. Those rows must be dropped."""
    bars, frame, config, strategy = world
    fold = generate_folds(config)[0]
    (_, train_hi), _, _ = _index_ranges(bars, fold)

    captured: dict[str, list[int]] = {}
    original = RegimeModel.fit.__func__

    def spy(cls, frame_, labels_, indices, **kwargs):
        captured["indices"] = list(indices)
        return original(cls, frame_, labels_, indices, **kwargs)

    monkeypatch.setattr(RegimeModel, "fit", classmethod(spy))
    run = run_fold(bars, frame, config, strategy, fold, stress_factors=())

    used = captured["indices"]
    assert used, "the regime model must be fitted on something"
    assert max(used) < train_hi - EMBARGO_BARS + 1
    assert run.artifacts.diagnostics["embargoed_bars"] == EMBARGO_BARS
    assert EMBARGO_BARS == config.models.labels.horizon_bars, (
        "the embargo is the label horizon; a constant that can drift from the "
        "config would silently stop matching it"
    )


def test_the_threshold_is_chosen_on_validation_rows_only(world, monkeypatch) -> None:
    """Choosing the acceptance cutoff on the test window is leakage wearing a
    walk-forward costume, and it is what the validation window exists for."""
    bars, frame, config, strategy = world
    fold = generate_folds(config)[1]
    _, (val_lo, val_hi), (test_lo, test_hi) = _index_ranges(bars, fold)

    seen: dict[str, list[int]] = {}
    original = SignalQualityModel.choose_threshold

    def spy(self, validation_rows, **kwargs):
        seen["indices"] = [r.bar_index for r in validation_rows]
        return original(self, validation_rows, **kwargs)

    monkeypatch.setattr(SignalQualityModel, "choose_threshold", spy)
    run_fold(bars, frame, config, strategy, fold, stress_factors=())

    indices = seen.get("indices", [])
    assert indices, "the threshold must be chosen from real validation trades"
    assert all(val_lo <= i < val_hi for i in indices)
    assert not any(test_lo <= i < test_hi for i in indices)


def test_the_scaler_is_fitted_on_training_data_only() -> None:
    """Fitting on train and test together leaks the test window's location and
    spread into every training row. It improves results and leaves no trace."""
    scaler = StandardScaler()
    train = np.array([[0.0], [2.0]])
    scaler.fit(train)
    mean, scale = scaler.mean.copy(), scaler.scale.copy()
    scaler.transform(np.array([[1000.0], [-1000.0]]))
    assert np.array_equal(scaler.mean, mean)
    assert np.array_equal(scaler.scale, scale)


def test_a_constant_column_does_not_poison_the_weights() -> None:
    """Dividing by a zero spread gives NaN, and one NaN destroys every weight
    update after it."""
    X = np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0], [4.0, 5.0]])
    model = LogisticRegression().fit(X, [0, 0, 1, 1])
    assert np.all(np.isfinite(model.predict_proba(X)))


# ------------------------------------------------------------- the M1 model


def test_no_options_trained_regime_classifier_can_exist(world) -> None:
    """PRD §5.4. 31 months inside close to a single regime is not regime
    variety, and the model's existence would invite the cross-asset comparison
    the tier structure refuses."""
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    with pytest.raises(RegimeModelError, match="no options-trained"):
        RegimeModel.fit(frame, labels, range(200, 400), asset_class="option")


def test_the_regime_block_names_every_state_but_asserts_one(world) -> None:
    """PRD §4.2: `probs` carries every state as a key while only `label` is a
    claim. A grounding check that treats keys as permitted values would
    silently accept a wrong regime claim."""
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    model = RegimeModel.fit(frame, labels, range(frame.warmup, 4000))
    row = frame.row(5000)
    prediction = model.predict_row([row[n] for n in frame.names])
    assert set(prediction["probs"]) == set(TREND_STATES)
    assert prediction["label"] in TREND_STATES
    assert prediction["probs"][prediction["label"]] == max(prediction["probs"].values())
    assert prediction["vol_flag"] in ("low", "high")
    assert prediction["model_version"] == "regime_lr_v1"


def test_the_regime_model_is_fingerprinted(world) -> None:
    """Two runs quoting the same model version with different weights is what
    this catches, and a results table cannot show it any other way."""
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    a = RegimeModel.fit(frame, labels, range(frame.warmup, 4000))
    b = RegimeModel.fit(frame, labels, range(frame.warmup, 4000))
    c = RegimeModel.fit(frame, labels, range(frame.warmup, 6000))
    assert a.artifact_hash() == b.artifact_hash()
    assert a.artifact_hash() != c.artifact_hash()
    assert a.artifact_hash().startswith("sha256:")


def test_a_single_regime_training_window_is_reported_not_crashed() -> None:
    """A fold that saw one regime is a real and reportable state."""
    X = np.array([[0.0], [1.0], [2.0]])
    model = LogisticRegression().fit(X, ["uptrend"] * 3)
    assert model.classes_ == ["uptrend"]
    assert model.predict(X) == ["uptrend"] * 3


def test_the_regime_gate_may_only_shrink() -> None:
    with pytest.raises(ValueError, match="only shrink"):
        RegimeGate(object(), high_vol_size=1.5)
    with pytest.raises(ValueError, match="unknown regime"):
        RegimeGate(object(), permitted=("sideways",))


# ------------------------------------------------------------- the M2 model


def _rows(n: int, *, good_above: float, width: int = 1) -> list[TrainingRow]:
    """Rows whose first feature predicts the outcome, so the fitted model's
    probability is monotone in it and a threshold sweep is meaningful.

    `width` pads to whatever the real feature vector length is, because a gate
    hands the model a full row and a model fitted on one column would simply
    fail to multiply.
    """
    rng = random.Random(1)
    out = []
    for i in range(n):
        x = rng.uniform(0.0, 1.0)
        profitable = int(x > good_above)
        out.append(
            TrainingRow(
                bar_index=i,
                features=[x] + [0.0] * (width - 1),
                profitable=profitable,
                target_first=profitable,
                r_multiple=2.0 if profitable else -1.0,
                regime="uptrend",
            )
        )
    return out


def test_the_threshold_comes_from_the_grid() -> None:
    """A fixed grid rather than a continuous optimisation, so the choice is
    auditable and identical across folds."""
    from project_beta.models.signal_quality import THRESHOLD_GRID

    rows = _rows(400, good_above=0.5)
    model = SignalQualityModel.fit(rows, feature_names=("x",))
    threshold = model.choose_threshold(rows)
    assert threshold in THRESHOLD_GRID or threshold == 0.0


def test_too_few_validation_trades_accepts_everything() -> None:
    """Picking the noisiest cutoff is how a threshold sweep becomes
    overfitting. With nothing to judge, M2 equals M1 on that fold and the run
    says so."""
    rows = _rows(400, good_above=0.5)
    model = SignalQualityModel.fit(rows, feature_names=("x",))
    assert model.choose_threshold(rows[:5]) == 0.0


def test_both_probabilities_are_recorded_but_only_one_gates() -> None:
    """Gating on both would be two thresholds, two chances to pass, and no way
    to attribute which mattered."""
    rows = _rows(300, good_above=0.4)
    model = SignalQualityModel.fit(rows, feature_names=("x",))
    scored = model.score([0.9])
    assert set(scored) >= {"p_profit", "p_target_before_stop", "model_version", "threshold"}
    assert 0.0 <= scored["p_profit"] <= 1.0


def test_no_signal_quality_rejection_occurs_in_an_abstaining_regime(world) -> None:
    """PRD §5.5's named acceptance criterion, and Outline §20.3's fairness
    mitigation as something that runs rather than something promised."""
    bars, frame, config, strategy = world
    labels = label_regimes(bars, frame)
    regime_model = RegimeModel.fit(frame, labels, range(frame.warmup, 6000))
    width = len(frame.names) + 1 + len(TREND_STATES)
    rows = _rows(300, good_above=0.4, width=width)
    sq = SignalQualityModel.fit(rows, feature_names=tuple(range(width)))
    sq.threshold = 1.01  # rejects everything it is allowed to reject

    index = 8000
    prediction = regime_model.predict_row(
        [frame.row(index)[n] for n in frame.names]
    )
    gate = SignalQualityGate(
        sq, regime_model, abstain_regimes=(prediction["label"],)
    )
    candidates = strategy.generate_candidates(frame, bars, config)
    candidate = candidates[0]

    verdict = gate.evaluate(candidate, frame, index)
    assert verdict.decision == "approved"
    assert "SQ_ABSTAINED" in verdict.reason_codes
    assert verdict.detail["signal_quality"]["abstained"] is True

    # The same gate, without the abstention, does reject - so the test is
    # measuring the abstention rather than a model that never rejects.
    strict = SignalQualityGate(sq, regime_model, abstain_regimes=())
    assert strict.evaluate(candidate, frame, index).decision == "rejected"


def test_an_unknown_abstention_regime_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown regimes"):
        SignalQualityGate(object(), object(), abstain_regimes=("sideways",))


# ---------------------------------------------------------------- calibration


def test_brier_rewards_a_confident_correct_prediction() -> None:
    assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_a_calibration_report_covers_every_observation() -> None:
    report = calibration_report([0.05, 0.45, 0.55, 1.0], [0, 0, 1, 1])
    assert report.n == 4
    assert sum(b.count for b in report.bins) == 4, "p == 1.0 must have a bin"
    assert report.base_rate == pytest.approx(0.5)


# ------------------------------------------------------------------ the ladder


def test_each_rung_trades_a_subset_of_the_one_below(world) -> None:
    """M2 filters M1, which filters B2. That nesting is what makes the
    comparison paired in the statistical sense."""
    bars, frame, config, strategy = world
    runs = run_walk_forward(bars, frame, config, strategy, stress_factors=()).runs
    assert runs, "the fixture must yield at least one fold"
    for run in runs:
        assert set(run.base.returns) == {"B1", "B2", "M1", "M2"}
        assert len({len(v) for v in run.base.returns.values()}) == 1


def test_a_fold_is_reproducible(world) -> None:
    """Same bars, same config, same weights, same returns. Every published
    number has to be reproducible from a config hash."""
    bars, frame, config, strategy = world
    fold = generate_folds(config)[0]
    first = run_fold(bars, frame, config, strategy, fold, stress_factors=())
    second = run_fold(bars, frame, config, strategy, fold, stress_factors=())
    assert first.base.returns == second.base.returns
    assert (
        first.artifacts.regime_model.artifact_hash()
        == second.artifacts.regime_model.artifact_hash()
    )
    assert first.artifacts.threshold == second.artifacts.threshold


def test_fold_artifacts_carry_what_a_model_card_needs(world) -> None:
    bars, frame, config, strategy = world
    run = run_fold(
        bars, frame, config, strategy, generate_folds(config)[0], stress_factors=()
    )
    provenance = run.artifacts.provenance()
    for key in (
        "regime_model_version",
        "regime_artifact_hash",
        "sq_threshold",
        "train_label_distribution",
        "train_labelled_rows",
    ):
        assert provenance[key] is not None, key


def test_composed_gates_make_m2_from_m1(world) -> None:
    """M2 is M1 plus one component, expressed as a list element rather than a
    second code path."""
    bars, frame, _, _ = world
    labels = label_regimes(bars, frame)
    regime_model = RegimeModel.fit(frame, labels, range(frame.warmup, 6000))
    regime_gate = RegimeGate(regime_model)
    sq = SignalQualityModel.fit(_rows(300, good_above=0.4), feature_names=("x",))
    composed = CompositeGate([regime_gate, SignalQualityGate(sq, regime_model)])
    assert composed.name == "regime+signal_quality"


# ------------------------------------------------- cost stress (2026-09-04)


def test_stressing_a_config_moves_only_the_price() -> None:
    """The stressed run must differ from the headline run by exactly the thing
    that differs, so a reader comparing two rows knows what changed."""
    config = _config(date(2022, 1, 3), date(2023, 10, 3))
    stressed = stressed_config(config, 2.0)
    assert stressed.execution.cost_multiplier == 2.0
    assert stressed.config_hash() != config.config_hash()
    assert stressed.seed == config.seed
    assert stressed.walk_forward == config.walk_forward
    assert stressed.models == config.models


def test_the_stress_factor_is_relative_to_the_run_it_stresses() -> None:
    """A run already configured at 1.5x costs must stress to 3x, not silently
    drop back to the default cost model."""
    config = _config(date(2022, 1, 3), date(2023, 10, 3))
    dear = replace(config, execution=replace(config.execution, cost_multiplier=1.5))
    assert stressed_config(dear, 2.0).execution.cost_multiplier == pytest.approx(3.0)
    assert stressed_config(config, 1.0).execution.cost_multiplier == pytest.approx(1.0)


def test_higher_costs_produce_a_different_and_worse_record(world) -> None:
    bars, frame, config, strategy = world
    run = run_fold(bars, frame, config, strategy, generate_folds(config)[0])
    base = run.base.returns["B2"]
    stressed = run.stressed[2.0].returns["B2"]
    assert len(base) == len(stressed), "stress must not change the day index"
    assert base != stressed, "doubling costs must move the returns"
    assert sum(stressed) < sum(base), "doubling costs cannot help"


def test_cost_stress_re_prices_rather_than_refits(world) -> None:
    """Condition 3 asks whether *this* result survives higher costs. Refitting
    would change the signal-quality labels - a trade profitable at 1x and a
    loss at 2x is a different training example - and would answer a different
    question: what a different system would have done."""
    bars, frame, config, strategy = world
    fold = generate_folds(config)[0]
    without = run_fold(bars, frame, config, strategy, fold, stress_factors=())
    with_stress = run_fold(bars, frame, config, strategy, fold, stress_factors=(2.0,))

    assert (
        without.artifacts.regime_model.artifact_hash()
        == with_stress.artifacts.regime_model.artifact_hash()
    )
    assert without.artifacts.threshold == with_stress.artifacts.threshold
    assert without.base.returns == with_stress.base.returns


def test_a_fold_that_cannot_run_is_recorded_rather_than_dropped(world) -> None:
    """A silently skipped fold turns a smaller study into a larger one's label.

    Truncating the bars leaves the later folds with no test data. Those folds
    must come back as skipped, with an index and a reason, and the expected
    count must still equal the number the configuration yielded.
    """
    bars, frame, config, strategy = world
    cut = len(bars) // 2
    walk = run_walk_forward(
        bars[:cut], frame, config, strategy, stress_factors=()
    )
    assert walk.skipped, "truncated data must leave at least one fold unrun"
    assert walk.expected == len(walk.runs) + len(walk.skipped)
    first = walk.skipped[0]
    assert first.error in {"FoldTooThin", "SignalQualityError"}
    assert first.message
    provenance = walk.provenance()
    assert provenance["n_folds_expected"] == walk.expected
    assert provenance["n_folds_ran"] == len(walk.runs)
    assert len(provenance["skipped_folds"]) == len(walk.skipped)


def test_a_missing_stress_factor_is_named_rather_than_assumed(world) -> None:
    bars, frame, config, strategy = world
    runs = run_walk_forward(bars, frame, config, strategy, stress_factors=(2.0,)).runs
    assert stressed_folds(runs, 2.0)
    with pytest.raises(KeyError, match=r"3\.0x cost-stress"):
        stressed_folds(runs, 3.0)


def test_condition_three_can_now_be_evaluated(world) -> None:
    """Before the cost-stress runs were wired in, every primary comparison
    failed with 'no 2x cost-stress run supplied' - correct behaviour and a
    permanently unmeetable bar. The condition must now pass or fail on
    evidence."""
    bars, frame, config, strategy = world
    comparisons, walk = evaluate(
        bars, frame, config, strategy, stress_factors=(2.0,), resamples=100
    )
    assert walk.runs and comparisons
    primary = [c for c in comparisons if c.is_primary]
    assert len(primary) == 1
    assert primary[0].cost_stress_point is not None
    assert not any("cost-stress run supplied" in f for f in primary[0].failures)


def test_the_ladder_still_reports_one_primary_comparison(world) -> None:
    bars, frame, config, strategy = world
    comparisons, _ = evaluate(
        bars, frame, config, strategy, stress_factors=(2.0,), resamples=100
    )
    assert [(c.treatment, c.control) for c in comparisons] == [
        ("B2", "B1"),
        ("M1", "B2"),
        ("M2", "M1"),
        ("M2", "B2"),
    ]
    assert sum(c.is_primary for c in comparisons) == 1
    assert CONDITION_3_FACTOR == 2.0


# --------------------------------------- the runner reads the config (item 4)


def test_the_embargo_follows_the_configured_label_horizon(world) -> None:
    """A constant would let the embargo drift away from the horizon it is
    supposed to match, and the leak would reappear silently."""
    bars, frame, config, strategy = world
    short = replace(
        config, models=ModelsConfig(labels=RegimeLabelConfig(horizon_bars=40))
    )
    run = run_fold(
        bars, frame, short, strategy, generate_folds(short)[0], stress_factors=()
    )
    assert run.artifacts.diagnostics["embargoed_bars"] == 40


def test_permitted_regimes_come_from_the_config(world) -> None:
    """Not from a default argument on `run_fold`, where no results row would
    ever record what was used.

    The comparison is against a config permitting only `downtrend`, and that
    choice is deliberate. Widening from `uptrend` to all three states changes
    nothing on this fixture, because the momentum breakout carries its own
    trend filter (`ma_gap > 0`) and every candidate it produces is already
    predicted `uptrend`. That overlap is real and worth knowing - it is why M1
    can look like a no-op against B2 - but it makes widening a weak test of
    whether the config was read. Narrowing to a regime the strategy never
    trades in is unambiguous.
    """
    bars, frame, config, strategy = world
    fold = generate_folds(config)[0]
    permitted = run_fold(bars, frame, config, strategy, fold, stress_factors=())
    contrary = replace(config, models=ModelsConfig(permitted_regimes=("downtrend",)))
    blocked = run_fold(bars, frame, contrary, strategy, fold, stress_factors=())

    permitted_days = sum(1 for r in permitted.base.returns["M1"] if r != 0.0)
    blocked_days = sum(1 for r in blocked.base.returns["M1"] if r != 0.0)
    assert permitted_days > 0, "the fixture must trade something under M1"
    assert blocked_days == 0, (
        "permitting only a regime the strategy never enters must block every "
        "candidate; if it does not, the config never reached the gate"
    )


def test_the_gate_is_constructed_from_the_config(world) -> None:
    """The direct form of the check above, without depending on what the
    market happened to do."""
    _, _, config, _ = world
    from project_beta.evaluation.runner import _build_gates

    wide = replace(
        config, models=ModelsConfig(permitted_regimes=("uptrend", "choppy"), high_vol_size=0.25)
    )
    gate = _build_gates(wide, object(), None)["M1"]
    assert gate.permitted == ("uptrend", "choppy")
    assert gate.high_vol_size == 0.25


def test_the_regime_l2_strength_reaches_the_model(world) -> None:
    bars, frame, config, strategy = world
    fold = generate_folds(config)[0]
    light = run_fold(bars, frame, config, strategy, fold, stress_factors=())
    heavy = run_fold(
        bars,
        frame,
        replace(config, models=ModelsConfig(regime_l2=500.0)),
        strategy,
        fold,
        stress_factors=(),
    )
    assert (
        light.artifacts.regime_model.artifact_hash()
        != heavy.artifacts.regime_model.artifact_hash()
    )


def test_base_folds_and_stressed_folds_stay_aligned(world) -> None:
    """The paired bootstrap needs the same days in the same order, and a
    stressed series that drifted would widen every interval invisibly."""
    bars, frame, config, strategy = world
    runs = run_walk_forward(bars, frame, config, strategy, stress_factors=(2.0,)).runs
    for base, stressed in zip(base_folds(runs), stressed_folds(runs, 2.0), strict=True):
        assert base.days == stressed.days
        assert set(base.returns) == set(stressed.returns)
