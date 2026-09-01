"""RunConfig validation tests.

These are the smoke tests the CI lecture asks for — "does the thing even load?"
— plus the negative cases that make them worth having. A test that only checks
the happy path would pass against a validator that accepts everything.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from project_beta.config import (
    ConfigError,
    DataConfig,
    HaltConfig,
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
    """~14 folds over 2016-06 → 2026-06 at 36/6/6. If this changes, the
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
    evidence after M2 calibration — not a hard-coded behaviour."""
    assert _config().risk.regime_abstain == []
    cfg = _config(risk={"regime_abstain": ["choppy"]})
    cfg.validate()
    assert cfg.risk.regime_abstain == ["choppy"]


def test_missing_required_field_is_reported_clearly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("run_id: x\nmode: backtest\n")
    with pytest.raises(ConfigError, match="missing required field"):
        load_run_config(bad)
