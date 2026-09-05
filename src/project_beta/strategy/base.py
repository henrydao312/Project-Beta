"""The strategy interface, the CandidateTrade contract, and the tier guard.

A strategy here is a *transparent rule set*, and the word transparent is doing
work: no model, no fit, no learned parameter. Its whole output is a list of
candidates, and everything downstream - the regime classifier, the
signal-quality model, the risk engine - can only ever *remove* or *shrink*
candidates it produced. That direction is the project's central design claim
(Outline §1A): AI never takes a trading decision, it gates one.

Two rules in this module exist because breaking them would be invisible.

**Determinism, including the identifiers.** PRD §5.3's acceptance criterion is
that the same data and config produce a byte-identical candidate list.
`trade_id` is a UUID, and a random UUID would break that on every run while
every value that mattered stayed identical - a reproducibility failure that no
result would reveal. Ids are therefore UUID5 over the fields that identify the
candidate, so two runs of the same configuration produce the same ids and a
diff of two candidate lists is meaningful.

**Decide on the close, execute later.** A candidate is stamped with the bar
whose close triggered it, and is never executed at that close. The execution
layer applies `fill_delay_bars` (default 1). Generating and filling on the same
bar is the most common backtest inflation there is, and it looks completely
ordinary in code.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, Sequence

from project_beta.config import RunConfig, StrategyConfig
from project_beta.data.provider import Bar
from project_beta.features.registry import FeatureFrame

Direction = Literal["long", "short"]

# A fixed namespace so ids are stable across processes, machines and semesters.
# uuid5 is a hash, not a draw: the same inputs give the same id forever.
TRADE_NAMESPACE = uuid.UUID("6f3c1c2a-8a4e-5c1b-9d2f-0b1a7c4e51d0")


class StrategyError(RuntimeError):
    """A strategy cannot run as configured."""


class TierViolation(RuntimeError):
    """A secondary strategy was offered to a graded comparison.

    Separate from StrategyError because this is an evaluation-integrity
    failure, not a configuration one. Outline §5.3 and PRD §5.14 promise that
    the exploratory strategies are structurally blocked from the graded
    ablation rather than merely documented as off-limits; this is that
    structure, and `assert_gradeable` is the only door.
    """


@dataclass(frozen=True)
class CandidateTrade:
    """PRD §4.1. What the rule set proposes, before any gate has seen it.

    `signal_strength` is an ordinal score in [0, 1], not a probability, and the
    distinction is load-bearing. The probability of a good outcome is what the
    signal-quality model produces (PRD §5.5); if the rule set also claimed to
    emit one, two different numbers would compete for the same meaning in the
    decision record and the ablation would no longer isolate the model.
    """

    trade_id: str
    timestamp: datetime
    bar_index: int
    bar_timeframe: str
    asset_class: str
    symbol: str
    direction: Direction
    signal_type: str
    signal_strength: float
    entry_price_ref: float
    stop_price: float
    target_price: float
    features_snapshot_id: str
    strategy_version: str
    tier: str = "primary"

    def __post_init__(self) -> None:
        if not 0.0 <= self.signal_strength <= 1.0:
            raise ValueError(
                f"signal_strength {self.signal_strength} outside [0, 1]; it is "
                "an ordinal score, and an unbounded one would silently become "
                "a weight in downstream sizing"
            )
        risk = abs(self.entry_price_ref - self.stop_price)
        if risk <= 0:
            raise ValueError(
                "stop_price must differ from entry_price_ref: a zero-risk "
                "trade divides by zero in every R-multiple downstream"
            )
        if self.direction == "long":
            if not self.stop_price < self.entry_price_ref < self.target_price:
                raise ValueError("long candidate needs stop < entry < target")
        elif not self.target_price < self.entry_price_ref < self.stop_price:
            raise ValueError("short candidate needs target < entry < stop")

    @property
    def risk_per_unit(self) -> float:
        """Entry-to-stop distance. The denominator of every R multiple."""
        return abs(self.entry_price_ref - self.stop_price)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["timestamp"] = self.timestamp.isoformat()
        return out


def make_trade_id(
    *, strategy_version: str, symbol: str, timestamp: datetime, direction: str
) -> str:
    """A deterministic id. See the module docstring on why this is not uuid4."""
    key = f"{strategy_version}|{symbol}|{timestamp.isoformat()}|{direction}"
    return str(uuid.uuid5(TRADE_NAMESPACE, key))


class Strategy(ABC):
    """`generate_candidates(features, bars) -> list[CandidateTrade]`.

    Subclasses declare the features they read. The declaration is checked
    against the frame before anything runs, so a strategy that quietly depends
    on a feature the registry dropped fails loudly rather than reading None.
    """

    name: str = ""
    version: str = ""
    tier: str = "primary"
    signal_type: str = ""
    required_features: tuple[str, ...] = ()

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig(
            name=self.name, version=self.version, tier=self.tier
        )
        self.params = {**self.defaults(), **dict(self.config.params)}
        unknown = set(self.config.params) - set(self.defaults())
        if unknown:
            raise StrategyError(
                f"{self.name}: unknown params {sorted(unknown)}. A misspelled "
                f"parameter would otherwise be silently ignored and the run "
                f"would report thresholds it did not use. Known: "
                f"{sorted(self.defaults())}"
            )
        # The config's tier wins over the class default so a run can demote a
        # strategy, but never promote one: see assert_gradeable.
        self.tier = self.config.tier

    @classmethod
    def defaults(cls) -> dict[str, Any]:
        return {}

    def check_features(self, frame: FeatureFrame) -> None:
        missing = [f for f in self.required_features if f not in frame.names]
        if missing:
            raise StrategyError(
                f"{self.name} requires {missing}, absent from this feature "
                f"frame (it has {list(frame.names)}). A dropped feature is the "
                "usual cause; the rule that used it needs removing too, not "
                "defaulting."
            )

    @abstractmethod
    def generate_candidates(
        self, frame: FeatureFrame, bars: Sequence[Bar], config: RunConfig
    ) -> list[CandidateTrade]:
        """Candidates in bar order. Deterministic for the same inputs."""


# ------------------------------------------------------------------ registry

STRATEGIES: dict[str, type[Strategy]] = {}


def register_strategy(cls: type[Strategy]) -> type[Strategy]:
    if cls.name in STRATEGIES:
        raise ValueError(f"strategy {cls.name!r} is already registered")
    STRATEGIES[cls.name] = cls
    return cls


def build_strategy(config: RunConfig) -> Strategy:
    """Resolve a RunConfig's strategy block into a strategy instance."""
    try:
        cls = STRATEGIES[config.strategy.name]
    except KeyError:
        raise StrategyError(
            f"unknown strategy {config.strategy.name!r}. Registered: "
            f"{sorted(STRATEGIES)}"
        ) from None
    if config.strategy.tier == "primary" and cls.tier != "primary":
        raise StrategyError(
            f"strategy {cls.name!r} is exploratory (Outline §5.3) and a config "
            "cannot promote it to tier='primary'. Demoting a primary strategy "
            "to 'secondary' is allowed; the reverse would let an unvalidated "
            "rule set into the graded ablation by editing a YAML file."
        )
    return cls(config.strategy)


def assert_gradeable(strategy: Strategy) -> None:
    """The only door into a graded comparison. Raises TierViolation otherwise.

    Called by the walk-forward harness before it will compute a headline
    metric. PRD §5.14: secondary strategies are structurally blocked from the
    graded ablation, not documented as off-limits.
    """
    if strategy.tier != "primary":
        raise TierViolation(
            f"strategy {strategy.name!r} is tier={strategy.tier!r} and cannot "
            "enter the graded ablation. Secondary strategies exist to keep the "
            "Strategy Engine interface honest and to support post-course work "
            "(Outline §5.3); they carry no walk-forward validation, no cost "
            "stress and no ablation, so a number from one would look like a "
            "result and have nothing behind it."
        )
