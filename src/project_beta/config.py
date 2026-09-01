"""RunConfig — the single specification of a backtest, paper or replay session.

Every result this project publishes traces back to one of these. The validation
below is not ceremony: each rule encodes something that was measured or decided
during Week 1, and would otherwise live only in someone's memory.

Run directly to validate a config file:

    python -m project_beta.config configs/example_backtest.yaml
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

# Verified 2026-08-30 by direct API probe: SIP 5-minute history begins here.
# 2015 returns nothing on either feed, so this is the true floor, not a guess.
SIP_HISTORY_FLOOR = date(2016, 6, 10)
IEX_HISTORY_FLOOR = date(2021, 6, 10)

Mode = Literal["backtest", "paper", "replay"]
Feed = Literal["sip", "iex"]
Session = Literal["rth_only", "extended"]
Tier = Literal["primary", "secondary"]


class ConfigError(ValueError):
    """Raised when a RunConfig would produce results we could not defend."""


@dataclass(frozen=True)
class DataConfig:
    symbol: str
    timeframe: str
    feed: Feed
    session: Session
    start: date
    end: date
    dataset_hash: str | None = None


@dataclass(frozen=True)
class HaltConfig:
    """Thresholds for the auto-halt triggers. See PRD §5.8A."""

    data_staleness_bars: int = 3
    max_consecutive_api_errors: int = 5
    auto_halt_enabled: bool = True


@dataclass(frozen=True)
class RiskConfig:
    max_drawdown: float
    daily_loss_limit: float
    max_position: float
    sizing: str = "vol_adjusted_v1"
    halt: HaltConfig = field(default_factory=HaltConfig)
    # Regimes where the signal-quality model abstains rather than participates.
    # This is the fairness mitigation from Outline §20.3 — configuration, not a
    # hard-coded behaviour, so it can be set from evidence after M2 calibration.
    regime_abstain: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WalkForwardConfig:
    train_months: int = 36
    test_months: int = 6
    step_months: int = 6


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    mode: Mode
    data: DataConfig
    risk: RiskConfig
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    seed: int = 42

    # ---------------------------------------------------------------- checks

    def validate(self) -> None:
        """Raise ConfigError on any combination we could not stand behind.

        Each rule cites why it exists. A rule without a reason is a rule that
        gets deleted the first time it's inconvenient.
        """
        d = self.data

        # Verified: the free tier serves historical SIP but returns 403 on
        # recent SIP and 409 on SIP streaming. A paper session on SIP would
        # fail at runtime, mid-session, with no data.
        if self.mode == "paper" and d.feed == "sip":
            raise ConfigError(
                "mode='paper' requires feed='iex'. Recent SIP data is not "
                "entitled on the Basic tier (403), and SIP streaming returns "
                "409. See Outline §9."
            )

        floor = SIP_HISTORY_FLOOR if d.feed == "sip" else IEX_HISTORY_FLOOR
        if d.start < floor:
            raise ConfigError(
                f"data.start {d.start} precedes the verified {d.feed.upper()} "
                f"history floor of {floor}. Earlier dates return no bars."
            )

        if d.end <= d.start:
            raise ConfigError(f"data.end {d.end} must be after data.start {d.start}.")

        # 60% of SIP bars fall outside 09:30-16:00 ET. Overnight liquidity and
        # spreads behave nothing like the regular session; letting those bars
        # into feature computation is a quiet source of inflated backtests.
        if d.session != "rth_only":
            raise ConfigError(
                "data.session must be 'rth_only'. The strategy trades regular "
                "hours; extended-hours bars are filtered at ingestion. "
                "Changing this requires a decision-log entry."
            )

        wf = self.walk_forward
        if min(wf.train_months, wf.test_months, wf.step_months) <= 0:
            raise ConfigError("walk_forward periods must all be positive.")

        span_months = (d.end.year - d.start.year) * 12 + (d.end.month - d.start.month)
        if span_months < wf.train_months + wf.test_months:
            raise ConfigError(
                f"Date range spans ~{span_months} months, too short for "
                f"{wf.train_months}m train + {wf.test_months}m test. "
                "Shorten the windows or widen the range."
            )

        r = self.risk
        if not 0 < r.max_drawdown < 1:
            raise ConfigError("risk.max_drawdown must be a fraction in (0, 1).")
        if r.daily_loss_limit <= 0 or r.max_position <= 0:
            raise ConfigError("risk limits must be positive.")
        if r.halt.data_staleness_bars <= 0 or r.halt.max_consecutive_api_errors <= 0:
            raise ConfigError("halt thresholds must be positive.")

    def fold_count(self) -> int:
        """How many walk-forward folds this configuration yields."""
        wf = self.walk_forward
        span = (self.data.end.year - self.data.start.year) * 12 + (
            self.data.end.month - self.data.start.month
        )
        usable = span - wf.train_months - wf.test_months
        return max(0, usable // wf.step_months) + 1


# -------------------------------------------------------------------- loading


def _as_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigError(f"{field_name}: expected YYYY-MM-DD, got {value!r}") from exc


def load_run_config(path: str | Path) -> RunConfig:
    """Load and validate a RunConfig from YAML. Raises ConfigError if invalid."""
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a YAML mapping at the top level.")

    try:
        data_raw = raw["data"]
        risk_raw = raw["risk"]
        data = DataConfig(
            symbol=data_raw["symbol"],
            timeframe=data_raw["timeframe"],
            feed=data_raw["feed"],
            session=data_raw.get("session", "rth_only"),
            start=_as_date(data_raw["start"], "data.start"),
            end=_as_date(data_raw["end"], "data.end"),
            dataset_hash=data_raw.get("dataset_hash"),
        )
        risk = RiskConfig(
            max_drawdown=float(risk_raw["max_drawdown"]),
            daily_loss_limit=float(risk_raw["daily_loss_limit"]),
            max_position=float(risk_raw["max_position"]),
            sizing=risk_raw.get("sizing", "vol_adjusted_v1"),
            halt=HaltConfig(**(risk_raw.get("halt") or {})),
            regime_abstain=list(risk_raw.get("regime_abstain") or []),
        )
        wf = WalkForwardConfig(**(raw.get("walk_forward") or {}))
        config = RunConfig(
            run_id=raw["run_id"],
            mode=raw["mode"],
            data=data,
            risk=risk,
            walk_forward=wf,
            seed=int(raw.get("seed", 42)),
        )
    except KeyError as exc:
        raise ConfigError(f"{path}: missing required field {exc}") from exc
    except TypeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc

    config.validate()
    return config


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m project_beta.config <config.yaml>", file=sys.stderr)
        return 2
    try:
        cfg = load_run_config(args[0])
    except ConfigError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK  {cfg.run_id}")
    print(f"    mode={cfg.mode}  feed={cfg.data.feed}  session={cfg.data.session}")
    print(f"    range={cfg.data.start} → {cfg.data.end}")
    print(f"    walk-forward folds: {cfg.fold_count()}")
    if cfg.risk.regime_abstain:
        print(f"    abstaining in regimes: {', '.join(cfg.risk.regime_abstain)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
