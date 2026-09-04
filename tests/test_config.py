"""RunConfig validation tests.

These are the smoke tests the CI lecture asks for - "does the thing even load?"
 - plus the negative cases that make them worth having. A test that only checks
the happy path would pass against a validator that accepts everything.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from project_beta.config import (
    ASSET_CLASS_TIER,
    OPTIONS_HISTORY_FLOOR,
    ConfigError,
    DataConfig,
    ExecutionConfig,
    HaltConfig,
    OptionSelectionConfig,
    RiskConfig,
    RunConfig,
    WalkForwardConfig,
    load_run_config,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "example_backtest.yaml"


def _config(**overrides) -> RunConfig:
    """A valid baseline config, with targeted overrides for negative cases."""
    data_kwargs = {
        "symbol": "SPY",
        "timeframe": "5Min",
        "feed": "sip",
        "session": "rth_only",
        "start": date(2016, 6, 10),
        "end": date(2026, 6, 30),
    }
    data_kwargs.update(overrides.pop("data", {}))
    risk_kwargs = {
        "max_drawdown": 0.15,
        "daily_loss_limit": 500.0,
        "max_position": 10_000.0,
        "halt": HaltConfig(),
    }
    risk_kwargs.update(overrides.pop("risk", {}))
    return RunConfig(
        run_id=overrides.pop("run_id", "test_run"),
        mode=overrides.pop("mode", "backtest"),
        data=DataConfig(**data_kwargs),
        risk=RiskConfig(**risk_kwargs),
        walk_forward=WalkForwardConfig(**overrides.pop("walk_forward", {})),
        execution=overrides.pop("execution", ExecutionConfig()),
    )


# ------------------------------------------------------------------- smoke


def test_package_imports() -> None:
    """The cheapest possible question: does it load at all?"""
    import project_beta

    assert project_beta.__version__


def test_example_config_loads_and_validates() -> None:
    cfg = load_run_config(EXAMPLE)
    assert cfg.data.symbol == "SPY"
    assert cfg.data.feed == "sip"
    assert cfg.data.session == "rth_only"


def test_example_config_yields_the_expected_fold_count() -> None:
    """~14 folds over 2016-06 → 2026-06 at 30/6/6. If this changes, the
    evaluation plan in the project documents changed too."""
    cfg = load_run_config(EXAMPLE)
    assert 12 <= cfg.fold_count() <= 16, f"got {cfg.fold_count()} folds"


# --------------------------------------------------------- negative cases


def test_paper_mode_rejects_sip_feed() -> None:
    """Verified 2026-08-30: recent SIP returns 403, SIP streaming returns 409.

    Catching this at config time turns a mid-session runtime failure into an
    error before anything starts.
    """
    with pytest.raises(ConfigError, match="requires feed='iex'"):
        _config(mode="paper", data={"feed": "sip"}).validate()


def test_start_before_the_verified_history_floor_is_rejected() -> None:
    with pytest.raises(ConfigError, match="history floor"):
        _config(data={"start": date(2015, 1, 1)}).validate()


def test_iex_floor_is_later_than_sip_floor() -> None:
    """IEX history begins 2021-06; SIP begins 2016-06. A date valid for one
    feed is not automatically valid for the other."""
    _config(data={"feed": "iex", "start": date(2021, 6, 10)}).validate()
    with pytest.raises(ConfigError, match="history floor"):
        _config(data={"feed": "iex", "start": date(2016, 6, 10)}).validate()


def test_extended_hours_session_is_rejected() -> None:
    """60% of SIP bars are outside regular hours and behave nothing like them."""
    with pytest.raises(ConfigError, match="rth_only"):
        _config(data={"session": "extended"}).validate()


def test_date_range_too_short_for_the_walk_forward_windows() -> None:
    with pytest.raises(ConfigError, match="too short"):
        _config(data={"end": date(2017, 6, 30)}).validate()


def test_implausible_risk_limits_are_rejected() -> None:
    with pytest.raises(ConfigError, match="max_drawdown"):
        _config(risk={"max_drawdown": 1.5}).validate()


def test_halt_thresholds_must_be_positive() -> None:
    """Halt control is a guardrail; a zero threshold silently disables it."""
    with pytest.raises(ConfigError, match="halt thresholds"):
        _config(risk={"halt": HaltConfig(data_staleness_bars=0)}).validate()


def test_regime_abstain_defaults_to_empty_and_accepts_regimes() -> None:
    """The fairness mitigation (Outline §20.3) is configuration, set from
    evidence after M2 calibration - not a hard-coded behaviour."""
    assert _config().risk.regime_abstain == []
    cfg = _config(risk={"regime_abstain": ["choppy"]})
    cfg.validate()
    assert cfg.risk.regime_abstain == ["choppy"]


def test_missing_required_field_is_reported_clearly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("run_id: x\nmode: backtest\n")
    with pytest.raises(ConfigError, match="missing required field"):
        load_run_config(bad)


# ------------------------------------------------- asset-class parameterisation
#
# Added with seam 2 (Outline §7B seam 2). The tier a track is allowed to claim is
# set by measured history, so the config layer is where that arithmetic gets
# enforced rather than remembered.

def _crypto(**overrides) -> RunConfig:
    data_kwargs = {
        "symbol": "BTC/USD",
        "timeframe": "5Min",
        "asset_class": "crypto",
        "session": "continuous",
        "start": date(2021, 6, 10),
        "end": date(2026, 8, 31),
    }
    data_kwargs.update(overrides.pop("data", {}))
    return RunConfig(
        run_id="test_crypto",
        mode="backtest",
        data=DataConfig(**data_kwargs),
        risk=RiskConfig(max_drawdown=0.2, daily_loss_limit=500.0, max_position=5000.0),
        walk_forward=WalkForwardConfig(**overrides.pop("walk_forward", {})),
    )


def _options(**overrides) -> RunConfig:
    data_kwargs = {
        "symbol": "SPY",
        "timeframe": "5Min",
        "asset_class": "option",
        "session": "rth_only",
        "start": OPTIONS_HISTORY_FLOOR,
        "end": date(2026, 8, 31),
    }
    data_kwargs.update(overrides.pop("data", {}))
    return RunConfig(
        run_id="test_options",
        mode="backtest",
        data=DataConfig(**data_kwargs),
        risk=RiskConfig(max_drawdown=0.2, daily_loss_limit=500.0, max_position=5000.0),
        walk_forward=overrides.pop("walk_forward", None),
        execution=overrides.pop(
            "execution", ExecutionConfig(fill_model="sparse_bar")
        ),
        option_selection=overrides.pop("option_selection", OptionSelectionConfig()),
    )


def test_options_cannot_carry_a_walk_forward_block() -> None:
    """31 months of history, 42 months to a fold. The rule states the
    arithmetic so it cannot be quietly relaxed later (Outline §7A)."""
    with pytest.raises(ConfigError, match="42"):
        _options(walk_forward=WalkForwardConfig()).validate()


def test_an_options_run_without_folds_is_valid_and_reports_zero() -> None:
    """Zero is a real answer, not a failure. It is the basis of the tier."""
    cfg = _options()
    cfg.validate()
    assert cfg.fold_count() == 0
    assert cfg.provenance()["tier"] == "validated_execution_layer"
    assert cfg.provenance()["fold_scheme"] is None


def test_options_require_the_sparse_bar_fill_model() -> None:
    """A missing options bar is a no-trade interval, never a forward-filled
    price. Filling it invents a fill that could not have happened (§8)."""
    with pytest.raises(ConfigError, match="sparse_bar"):
        _options(execution=ExecutionConfig(fill_model="bar")).validate()


def test_options_require_an_explicit_selection_rule() -> None:
    with pytest.raises(ConfigError, match="option_selection"):
        _options(option_selection=None).validate()


def test_the_quote_fill_model_is_declared_but_unavailable() -> None:
    """Seam 5 exists so the vendor limit is visible, not so it can be chosen."""
    with pytest.raises(ConfigError, match="quote"):
        _config(execution=ExecutionConfig(fill_model="quote")).validate()


def test_crypto_requires_a_continuous_session() -> None:
    """BTC/USD trades 24/7; an RTH filter would invent a session."""
    with pytest.raises(ConfigError, match="continuous"):
        _crypto(data={"session": "rth_only"}).validate()


def test_crypto_yields_about_four_folds() -> None:
    """~63 months at 30/6/6. The fold count travels with every crypto number
    precisely because four is not fourteen (Outline §7A)."""
    cfg = _crypto()
    cfg.validate()
    assert 3 <= cfg.fold_count() <= 5, f"got {cfg.fold_count()}"
    assert cfg.provenance()["tier"] == "graded_secondary"


def test_a_feed_is_meaningless_outside_equities() -> None:
    """Alpaca versions its data APIs per asset class; sip/iex is an equities
    concept. A probe that ignored this returned zeros for options."""
    with pytest.raises(ConfigError, match="meaningless"):
        _crypto(data={"feed": "iex"}).validate()


def test_equity_runs_require_an_explicit_feed() -> None:
    with pytest.raises(ConfigError, match="feed"):
        _config(data={"feed": None}).validate()


def test_each_asset_class_history_floor_is_enforced() -> None:
    with pytest.raises(ConfigError, match="history floor"):
        _options(data={"start": date(2023, 6, 1)}).validate()
    with pytest.raises(ConfigError, match="history floor"):
        _crypto(data={"start": date(2019, 1, 1)}).validate()


# ------------------------------------------------------------- provenance


def test_provenance_carries_everything_a_results_row_needs() -> None:
    """Seam 3: the comparability caveat belongs in the data, not in the prose
    around it. A crypto number without its fold count beside it will eventually
    be read as if it carried the core's evidentiary weight."""
    p = _config().provenance()
    for key in (
        "asset_class",
        "tier",
        "vendor",
        "feed",
        "data_start",
        "fold_scheme",
        "n_folds",
        "config_hash",
    ):
        assert key in p, f"provenance is missing {key}"
    assert p["asset_class"] == "equity"
    assert p["tier"] == ASSET_CLASS_TIER["equity"]
    assert p["n_folds"] > 0


def test_config_hash_is_stable_and_sensitive() -> None:
    """Reproducibility depends on being able to say two runs had the same
    configuration, and on noticing when they did not."""
    assert _config().config_hash() == _config().config_hash()
    assert _config().config_hash() != _config(run_id="other").config_hash()


def test_the_walk_forward_scheme_reserves_a_validation_window() -> None:
    """30/6/6 means train/validation/test. Thresholds have to be chosen
    somewhere, and choosing them on the test window is leakage wearing a
    walk-forward costume."""
    wf = WalkForwardConfig()
    assert wf.validation_months > 0
    assert wf.months_per_fold == 42
