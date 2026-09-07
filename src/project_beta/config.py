"""RunConfig - the single specification of a backtest, paper or replay session.

Every result this project publishes traces back to one of these. The validation
below is not ceremony: each rule encodes something that was measured or decided
during Week 1, and would otherwise live only in someone's memory.

This module is architecture seam 2 (Outline §7B seam 2): the fold scheme, the
history floor, the session calendar and the fill model are all configuration
parameterised by asset class. If those are configuration, adding a graded
options track after the course is a YAML file plus data, not a rewrite.

Run directly to validate a config file:

    python -m project_beta.config configs/example_backtest.yaml
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

# Verified 2026-08-30 by direct API probe: SIP 5-minute history begins here.
# 2015 returns nothing on either feed, so this is the true floor, not a guess.
SIP_HISTORY_FLOOR = date(2016, 6, 10)
IEX_HISTORY_FLOOR = date(2021, 6, 10)

# Verified 2026-08-31: BTC/USD 5-minute bars run continuously from at least
# this date. 865 bars per 3-day window against 864 expected for true 24/7.
CRYPTO_HISTORY_FLOOR = date(2021, 6, 10)

# Verified 2026-09-01 by probe_options_start.py. Eighteen contracts across six
# different expiries all clip their first bar into 2024-01-18/19, including a
# June expiry that had been trading for months by January. Eighteen contracts
# cannot coincidentally begin trading in the same two days: this is a hard data
# floor of the same class as the SIP floor above, not a query artifact.
OPTIONS_HISTORY_FLOOR = date(2024, 1, 18)

Mode = Literal["backtest", "paper", "replay"]
Feed = Literal["sip", "iex"]
Session = Literal["rth_only", "extended", "continuous"]
AssetClass = Literal["equity", "crypto", "option"]
Provider = Literal["alpaca"]
FillModel = Literal["bar", "sparse_bar", "quote"]
Tier = Literal["primary", "secondary"]

# Which claim each asset class is permitted to make. Outline §7A. Carried into
# provenance() so the tier travels with the results rather than with the prose.
# The three trend states. `models/labels.py` is the definition; this mirror
# exists because config.py must not import the model layer (the model layer
# imports config), and a config that cannot check its own regime names would
# accept `permitted_regimes: [sideways]` and silently permit nothing.
# `test_guardrails.py::test_the_config_and_the_label_module_agree_on_regimes`
# asserts the two lists stay identical.
TREND_STATES: tuple[str, ...] = ("uptrend", "downtrend", "choppy")

ASSET_CLASS_TIER: dict[str, str] = {
    "equity": "graded_core",
    "crypto": "graded_secondary",
    "option": "validated_execution_layer",
}

_FLOORS: dict[str, date] = {
    "crypto": CRYPTO_HISTORY_FLOOR,
    "option": OPTIONS_HISTORY_FLOOR,
}


class ConfigError(ValueError):
    """Raised when a RunConfig would produce results we could not defend."""


@dataclass(frozen=True)
class DataConfig:
    symbol: str
    timeframe: str
    start: date
    end: date
    asset_class: AssetClass = "equity"
    provider: Provider = "alpaca"
    # Equities only. Alpaca versions its data APIs per asset class, and the
    # sip/iex distinction does not exist for crypto or options - a correction
    # forced by a probe that queried all three under /v2 and got zeros back.
    feed: Feed | None = None
    session: Session = "rth_only"
    dataset_hash: str | None = None

    def history_floor(self) -> date:
        """The earliest date this feed and asset class actually serves."""
        if self.asset_class in _FLOORS:
            return _FLOORS[self.asset_class]
        return SIP_HISTORY_FLOOR if self.feed == "sip" else IEX_HISTORY_FLOOR


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
    # Fraction of equity risked between entry and stop on a single trade. The
    # sizing rule is deterministic and lives in the risk engine, never in a
    # model: Outline §1A's claim is that AI gates trades and never sizes or
    # takes them.
    risk_per_trade: float = 0.005
    halt: HaltConfig = field(default_factory=HaltConfig)
    # Regimes where the signal-quality model abstains rather than participates.
    # This is the fairness mitigation from Outline §20.3 - configuration, not a
    # hard-coded behaviour, so it can be set from evidence after M2 calibration.
    regime_abstain: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionConfig:
    """Seam 5 (Outline §7B seam 5): the fill model is pluggable, not implied.

    'bar' - fill against the bar that triggered the decision.
    'sparse_bar' - same, but an absent bar is a no-trade interval and never a
                   forward-filled price. Required for options (Outline §8) and
                   honest on IEX too, where 5-minute intervals with no trades
                   genuinely occur on a feed carrying ~3% of consolidated volume.
    'quote' - spread-aware fills. No vendor available to this project
                   serves historical options quotes, so this is declared and
                   unimplemented rather than silently absent.
    """

    fill_model: FillModel = "bar"
    commission_per_share: float = 0.0
    slippage_bps: float = 1.0
    # Bars between the decision and the fill. A candidate is generated from a
    # bar's close; filling at that same close is the most common backtest
    # inflation there is, and it looks entirely ordinary in code. One bar is
    # the honest minimum for a system that reads a close and then acts.
    fill_delay_bars: int = 1
    # Multiplies every cost. This is how the 2x and 3x cost-stress runs of
    # EVALUATION_PROTOCOL.md §9 are produced: the same code path, one config
    # value, so the stressed run cannot drift from the headline one.
    cost_multiplier: float = 1.0
    # Bars a position may be held. 78 is one regular session at 5 minutes.
    max_hold_bars: int = 78
    # Flatten before the close. An intraday strategy that holds overnight is
    # taking gap risk it never modelled, and the backtest would credit it with
    # overnight drift the live system was never exposed to.
    flatten_at_session_end: bool = True


@dataclass(frozen=True)
class OptionSelectionConfig:
    """Deterministic single-leg contract selection. Outline §5.8.

    Parameters live here rather than in code so the selection rule is part of
    the run's provenance and can be swept without editing the layer.
    """

    min_dte: int = 7
    max_dte: int = 45
    # Absolute moneyness band, as a fraction of spot: 0.02 means within 2%.
    moneyness_band: float = 0.02
    # Minimum measured bars over the contract's lifetime for it to be
    # considered tradeable. The screen is fitted and tested, never assumed.
    min_bars_in_lifetime: int = 200


@dataclass(frozen=True)
class RegimeLabelConfig:
    """How a regime label is defined. Every value here changes every label.

    These were module defaults until 2026-09-04, which meant two runs with
    materially different labels produced identical `config_hash` values. A
    provenance system that cannot tell those runs apart is not a provenance
    system, so they live here and travel with the results.

    `horizon_bars` is also the embargo length: a label at bar t reads prices up
    to t+horizon, so the last `horizon` bars of every training window are
    dropped. Lengthening the horizon lengthens the embargo, and the runner
    takes that number from here rather than from a constant.
    """

    horizon_bars: int = 78
    # Forward move, in units of the expected move at current volatility, that
    # separates a trend from chop. Scale-free by construction: a 0.3% move is a
    # trend in a calm month and noise in a violent one.
    trend_k: float = 0.5
    # Forward realized volatility, relative to contemporaneous, above which the
    # volatility flag is 'high'.
    vol_k: float = 1.15


@dataclass(frozen=True)
class ModelsConfig:
    """M1 and M2 parameters. Outline §5.1, §5.2; PRD §4.3's `models:` block.

    Nothing here is a model weight - those are fingerprinted by
    `artifact_hash()`. These are the choices made *before* fitting, and each
    one moves every number the ladder reports.
    """

    labels: RegimeLabelConfig = field(default_factory=RegimeLabelConfig)
    # Regimes in which M1 permits participation. The primary strategy is
    # long-only, so a downtrend prediction is a reason to stand aside rather
    # than to reverse.
    permitted_regimes: tuple[str, ...] = ("uptrend",)
    # Size multiplier applied in the high-volatility state. Bounded at 1.0: a
    # gate may shrink a position and may never enlarge one.
    high_vol_size: float = 0.5
    regime_l2: float = 1.0
    signal_quality_l2: float = 1.0
    # Validation trades below which no acceptance threshold is selectable.
    # Picking the cutoff from a handful of surviving trades is how a threshold
    # sweep becomes overfitting.
    min_validation_trades: int = 20


@dataclass(frozen=True)
class StrategyConfig:
    """Which rule set generates candidates, and at what evidentiary tier.

    `tier` is the structural half of Outline §5.3's promise. It is a claim
    status, not the user's product path: secondary families can run through the
    same instrumentation, but a secondary strategy that finds its way into the
    graded ablation would produce a number nobody could defend and nothing
    would have stopped it. The tier travels in the config, into `provenance()`,
    and the harness refuses a graded run for anything but 'primary'.

    `params` lives here rather than in code so the rule set's thresholds are
    part of the run's provenance and can be swept without editing the strategy.
    """

    name: str = "momentum_breakout"
    version: str = "mom_v1"
    tier: Tier = "primary"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WalkForwardConfig:
    """The 30/6/6 scheme: 30 months train, 6 validation, 6 test, stepped by 6.

    The validation window is not decorative. Thresholds - the signal-quality
    acceptance cutoff above all - have to be chosen somewhere, and choosing
    them on the test window is leakage wearing a walk-forward costume. One
    complete fold therefore consumes 42 months, which is the arithmetic behind
    the options tier in Outline §7A.

    Why 30 and not 36. The training window is bound by regime variety, not
    sample size: 30 months still holds ~49,000 five-minute bars, far more than
    a gradient-boosted tree needs, while spanning several regimes. Carving the
    validation window out of the original 36 rather than adding it on top
    preserves 14 equity folds and 4 crypto, so the validation window costs
    nothing. Measured, not asserted: scripts/analysis/fold_power.py.
    """

    train_months: int = 30
    validation_months: int = 6
    test_months: int = 6
    step_months: int = 6

    @property
    def months_per_fold(self) -> int:
        return self.train_months + self.validation_months + self.test_months


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    mode: Mode
    data: DataConfig
    risk: RiskConfig
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    # None means "this run makes no walk-forward performance claim". That is
    # the correct and only shape for options, so absence is meaningful here and
    # a default would quietly erase the distinction.
    walk_forward: WalkForwardConfig | None = None
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    option_selection: OptionSelectionConfig | None = None
    seed: int = 42

    # ---------------------------------------------------------------- checks

    def validate(self) -> None:
        """Raise ConfigError on any combination we could not stand behind.

        Each rule cites why it exists. A rule without a reason is a rule that
        gets deleted the first time it's inconvenient.
        """
        d = self.data

        # -- feed and asset class ------------------------------------------
        if d.asset_class == "equity":
            if d.feed not in ("sip", "iex"):
                raise ConfigError(
                    "equity runs require data.feed of 'sip' or 'iex'. "
                    "SIP for the graded backtest, IEX for the live paper loop."
                )
        elif d.feed is not None:
            raise ConfigError(
                f"data.feed is meaningless for asset_class='{d.asset_class}'. "
                "The sip/iex distinction is an equities concept; Alpaca versions "
                "its data APIs per asset class. Leave it unset."
            )

        # Verified: the free tier serves historical SIP but returns 403 on
        # recent SIP and 409 on SIP streaming. A paper session on SIP would
        # fail at runtime, mid-session, with no data.
        if self.mode == "paper" and d.feed == "sip":
            raise ConfigError(
                "mode='paper' requires feed='iex'. Recent SIP data is not "
                "entitled on the Basic tier (403), and SIP streaming returns "
                "409. See Outline §9."
            )

        floor = d.history_floor()
        if d.start < floor:
            label = d.feed.upper() if d.feed else d.asset_class.upper()
            raise ConfigError(
                f"data.start {d.start} precedes the verified {label} "
                f"history floor of {floor}. Earlier dates return no bars."
            )

        if d.end <= d.start:
            raise ConfigError(f"data.end {d.end} must be after data.start {d.start}.")

        # -- session calendar ----------------------------------------------
        # 60% of SIP bars fall outside 09:30-16:00 ET. Overnight liquidity and
        # spreads behave nothing like the regular session; letting those bars
        # into feature computation is a quiet source of inflated backtests.
        # Options carry extended-hours bars too (1,458 observed against a
        # ~1,377 RTH maximum), so the filter is load-bearing there as well.
        if d.asset_class == "crypto":
            if d.session != "continuous":
                raise ConfigError(
                    "crypto runs require data.session='continuous'. BTC/USD "
                    "trades 24/7; an RTH filter would discard most of the data "
                    "and invent a session that does not exist."
                )
        elif d.session != "rth_only":
            raise ConfigError(
                "data.session must be 'rth_only'. The strategy trades regular "
                "hours; extended-hours bars are filtered at ingestion. "
                "Changing this requires a decision-log entry."
            )

        # -- walk-forward ---------------------------------------------------
        if d.asset_class == "option" and self.walk_forward is not None:
            raise ConfigError(
                "asset_class='option' cannot carry a walk_forward block. "
                f"Options history begins {OPTIONS_HISTORY_FLOOR} - about 31 "
                "months - and one fold at 30/6/6 consumes 42. That is zero "
                "complete folds, and 31 months cannot become 42. Options is a "
                "validated execution layer (Outline §7A): it makes a "
                "fill-feasibility claim with a held-out split, never a "
                "walk-forward performance claim. Remove the block."
            )

        if self.walk_forward is not None:
            wf = self.walk_forward
            if min(
                wf.train_months, wf.validation_months, wf.test_months, wf.step_months
            ) <= 0:
                raise ConfigError("walk_forward periods must all be positive.")

            span_months = self.span_months()
            if span_months < wf.months_per_fold:
                raise ConfigError(
                    f"Date range spans ~{span_months} months, too short for "
                    f"{wf.train_months}m train + {wf.validation_months}m "
                    f"validation + {wf.test_months}m test. "
                    "Shorten the windows or widen the range."
                )

        # -- execution ------------------------------------------------------
        e = self.execution
        if e.fill_model == "quote":
            raise ConfigError(
                "execution.fill_model='quote' is declared but unavailable: no "
                "vendor within this project's budget serves historical options "
                "quotes, so spread and slippage are bar-derived proxies. The "
                "value exists in the interface so the limit is visible "
                "(Outline §7B seam 5), not so it can be selected."
            )
        if d.asset_class == "option" and e.fill_model != "sparse_bar":
            raise ConfigError(
                "asset_class='option' requires execution.fill_model="
                "'sparse_bar'. Options bars are strike-dependent and sparse "
                "(5 to 1,458 per contract lifetime observed). A missing bar is "
                "an interval in which the contract did not trade, never a "
                "forward-filled price - filling it invents a fill that could "
                "not have happened. See Outline §8."
            )
        if e.slippage_bps < 0 or e.commission_per_share < 0:
            raise ConfigError("execution costs must be non-negative.")
        if e.cost_multiplier <= 0:
            raise ConfigError(
                "execution.cost_multiplier must be positive. It exists to "
                "produce the 2x and 3x cost-stress runs (EVALUATION_PROTOCOL "
                "§9); zero would report a frictionless result as if it were "
                "the headline one."
            )
        if e.fill_delay_bars < 1:
            raise ConfigError(
                "execution.fill_delay_bars must be at least 1. A candidate is "
                "generated from a bar's close; filling at that same close "
                "trades on information the decision was made from, which is "
                "the most common way a backtest inflates itself."
            )
        if e.max_hold_bars <= 0:
            raise ConfigError("execution.max_hold_bars must be positive.")

        if d.asset_class == "option" and self.option_selection is None:
            raise ConfigError(
                "asset_class='option' requires an option_selection block. The "
                "contract-selection rule is deterministic and documented "
                "(Outline §5.8); leaving it implicit puts an undocumented rule "
                "into the results."
            )
        if d.asset_class != "option" and self.option_selection is not None:
            raise ConfigError(
                "option_selection applies only to asset_class='option'."
            )

        # -- strategy -------------------------------------------------------
        st = self.strategy
        if st.tier not in ("primary", "secondary"):
            raise ConfigError(
                f"strategy.tier must be 'primary' or 'secondary', got "
                f"{st.tier!r}. The tier decides whether this run's numbers may "
                "enter the graded ablation (Outline §5.3); an unrecognised "
                "value would default to whichever branch was written first."
            )
        if not st.name or not st.version:
            raise ConfigError(
                "strategy.name and strategy.version are both required. The "
                "version is what a results row cites when the rules change "
                "mid-semester and two runs stop being comparable."
            )

        # -- models ---------------------------------------------------------
        m = self.models
        if m.labels.horizon_bars <= 0:
            raise ConfigError(
                "models.labels.horizon_bars must be positive. It is both the "
                "label horizon and the training-window embargo; zero would "
                "leave labels that read the validation window in the training "
                "set."
            )
        if m.labels.trend_k < 0 or m.labels.vol_k <= 0:
            raise ConfigError(
                "models.labels.trend_k must be non-negative and vol_k positive."
            )
        unknown = set(m.permitted_regimes) - set(TREND_STATES)
        if unknown:
            raise ConfigError(
                f"models.permitted_regimes contains unknown states "
                f"{sorted(unknown)}. Known states are {list(TREND_STATES)}; an "
                "unrecognised name would permit nothing and look like a model "
                "that rejects everything."
            )
        if not m.permitted_regimes:
            raise ConfigError(
                "models.permitted_regimes is empty, so M1 would reject every "
                "candidate and the rung would measure abstention rather than "
                "the classifier. State the regimes explicitly."
            )
        if not 0.0 <= m.high_vol_size <= 1.0:
            raise ConfigError(
                "models.high_vol_size must lie in [0, 1]. A gate may reject or "
                "shrink a candidate and may never enlarge one (Outline §1A)."
            )
        if m.regime_l2 < 0 or m.signal_quality_l2 < 0:
            raise ConfigError("model L2 strengths must be non-negative.")
        if m.min_validation_trades < 1:
            raise ConfigError(
                "models.min_validation_trades must be at least 1."
            )

        # -- risk -----------------------------------------------------------
        r = self.risk
        if not 0 < r.max_drawdown < 1:
            raise ConfigError("risk.max_drawdown must be a fraction in (0, 1).")
        if r.daily_loss_limit <= 0 or r.max_position <= 0:
            raise ConfigError("risk limits must be positive.")
        if not 0 < r.risk_per_trade < 1:
            raise ConfigError(
                "risk.risk_per_trade must be a fraction in (0, 1)."
            )
        if r.halt.data_staleness_bars <= 0 or r.halt.max_consecutive_api_errors <= 0:
            raise ConfigError("halt thresholds must be positive.")

    # ------------------------------------------------------------- geometry

    def span_months(self) -> int:
        d = self.data
        return (d.end.year - d.start.year) * 12 + (d.end.month - d.start.month)

    def fold_count(self) -> int:
        """How many complete walk-forward folds this configuration yields.

        Zero is a real answer, not a failure. It is the answer for options, and
        reporting it as zero rather than shortening the scheme to manufacture
        folds is the whole basis of the tier structure (Outline §7A).
        """
        if self.walk_forward is None:
            return 0
        wf = self.walk_forward
        usable = self.span_months() - wf.months_per_fold
        if usable < 0:
            return 0
        return usable // wf.step_months + 1

    # ----------------------------------------------------------- provenance

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["data"]["start"] = self.data.start.isoformat()
        out["data"]["end"] = self.data.end.isoformat()
        return out

    def config_hash(self) -> str:
        """A stable fingerprint of everything that could change a result."""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def provenance(self) -> dict[str, Any]:
        """Seam 3 (Outline §7B seam 3): what every results row must carry.

        The comparability caveat belongs in the data, not in prose around it. A
        crypto number without its fold count beside it is a number that will
        eventually be read as if it carried the core's evidentiary weight.
        """
        wf = self.walk_forward
        return {
            "run_id": self.run_id,
            "asset_class": self.data.asset_class,
            "tier": ASSET_CLASS_TIER[self.data.asset_class],
            "vendor": self.data.provider,
            "feed": self.data.feed,
            "data_start": self.data.start.isoformat(),
            "data_end": self.data.end.isoformat(),
            "fold_scheme": (
                f"{wf.train_months}/{wf.validation_months}/{wf.test_months}"
                f"+{wf.step_months}"
                if wf
                else None
            ),
            "n_folds": self.fold_count(),
            "label_horizon_bars": self.models.labels.horizon_bars,
            "label_trend_k": self.models.labels.trend_k,
            "label_vol_k": self.models.labels.vol_k,
            "permitted_regimes": list(self.models.permitted_regimes),
            "high_vol_size": self.models.high_vol_size,
            "strategy": self.strategy.name,
            "strategy_version": self.strategy.version,
            "strategy_tier": self.strategy.tier,
            "fill_model": self.execution.fill_model,
            "fill_delay_bars": self.execution.fill_delay_bars,
            "cost_multiplier": self.execution.cost_multiplier,
            "dataset_hash": self.data.dataset_hash,
            "config_hash": self.config_hash(),
            "seed": self.seed,
        }


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
            start=_as_date(data_raw["start"], "data.start"),
            end=_as_date(data_raw["end"], "data.end"),
            asset_class=data_raw.get("asset_class", "equity"),
            provider=data_raw.get("provider", "alpaca"),
            feed=data_raw.get("feed"),
            session=data_raw.get("session", "rth_only"),
            dataset_hash=data_raw.get("dataset_hash"),
        )
        risk = RiskConfig(
            max_drawdown=float(risk_raw["max_drawdown"]),
            daily_loss_limit=float(risk_raw["daily_loss_limit"]),
            max_position=float(risk_raw["max_position"]),
            sizing=risk_raw.get("sizing", "vol_adjusted_v1"),
            risk_per_trade=float(risk_raw.get("risk_per_trade", 0.005)),
            halt=HaltConfig(**(risk_raw.get("halt") or {})),
            regime_abstain=list(risk_raw.get("regime_abstain") or []),
        )
        models_raw = dict(raw.get("models") or {})
        labels_raw = dict(models_raw.pop("labels", None) or {})
        models = ModelsConfig(
            labels=RegimeLabelConfig(**labels_raw),
            permitted_regimes=tuple(
                models_raw.pop("permitted_regimes", None) or ("uptrend",)
            ),
            **models_raw,
        )
        strat_raw = raw.get("strategy") or {}
        strategy = StrategyConfig(
            name=strat_raw.get("name", "momentum_breakout"),
            version=strat_raw.get("version", "mom_v1"),
            tier=strat_raw.get("tier", "primary"),
            params=dict(strat_raw.get("params") or {}),
        )
        # Absence is meaningful: no block means no walk-forward claim.
        wf_raw = raw.get("walk_forward")
        wf = WalkForwardConfig(**wf_raw) if wf_raw is not None else None
        sel_raw = raw.get("option_selection")
        selection = OptionSelectionConfig(**sel_raw) if sel_raw is not None else None
        config = RunConfig(
            run_id=raw["run_id"],
            mode=raw["mode"],
            data=data,
            risk=risk,
            strategy=strategy,
            models=models,
            walk_forward=wf,
            execution=ExecutionConfig(**(raw.get("execution") or {})),
            option_selection=selection,
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
    p = cfg.provenance()
    print(f"OK {cfg.run_id} [{p['tier']}]")
    print(f" mode={cfg.mode} asset_class={p['asset_class']} feed={p['feed']}")
    print(f" session={cfg.data.session} fill_model={p['fill_model']}")
    print(
        f" strategy={p['strategy']} {p['strategy_version']} "
        f"[{p['strategy_tier']}]"
    )
    print(f" range={cfg.data.start} to {cfg.data.end} ({cfg.span_months()} months)")
    print(f" fold scheme={p['fold_scheme']} folds={p['n_folds']}")
    print(f" config_hash={p['config_hash']}")
    print(
        f" labels=h{cfg.models.labels.horizon_bars}/"
        f"k{cfg.models.labels.trend_k}/v{cfg.models.labels.vol_k} "
        f"permitted={','.join(cfg.models.permitted_regimes)}"
    )
    if cfg.risk.regime_abstain:
        print(f" abstaining in regimes: {', '.join(cfg.risk.regime_abstain)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
