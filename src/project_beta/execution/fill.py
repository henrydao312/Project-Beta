"""Fill models - seam 5. How a decision becomes a price, and when it does not.

`FillModel.fill(candidate, bars, index) -> Fill | NoFill`. Three
implementations are declared; two are built.

**bar_v1 (equities, crypto).** Fill at the open of the bar `fill_delay_bars`
after the deciding bar, with slippage applied against the trade. Using the
deciding bar's own close would trade on the information the decision was made
from - the most common backtest inflation there is, and invisible in code.

**sparse_bar_v1 (options).** Identical, except that an absent bar at the fill
interval is a NoFill rather than a forward-filled price. Options bars are
strike-dependent and sparse - 5 to 1,458 per contract lifetime observed - and a
fill against a fabricated bar is a fill that could not have happened. On IEX
this is honest too: 5-minute intervals with no trades genuinely occur on a feed
carrying a median 3.16% of consolidated volume.

**quote_v1.** Declared and deliberately unimplemented. No vendor within this
project's budget serves historical options quotes, so spread and slippage are
bar-derived proxies. The value exists in the interface so the limit is visible
(Outline §7B seam 5), not so it can be selected; `config.validate()` refuses it.

**A NoFill is a result, not an error.** It is the raw material of the options
fill-feasibility study (PRD §5.6), and dropping those records would turn a
measured feasibility rate into a survivorship-filtered one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from project_beta.config import ExecutionConfig, RunConfig
from project_beta.data.provider import Bar
from project_beta.strategy.base import CandidateTrade

BPS = 1e-4


@dataclass(frozen=True)
class Fill:
    timestamp: datetime
    bar_index: int
    price: float
    reference_price: float
    slippage_bps: float
    commission: float
    fill_delay_bars: int

    @property
    def slippage_cost(self) -> float:
        """Per-unit cost of the adverse price, always non-negative."""
        return abs(self.price - self.reference_price)


@dataclass(frozen=True)
class NoFill:
    reason: str
    reason_code: str


class FillModel(Protocol):
    name: str

    def fill(
        self,
        candidate: CandidateTrade,
        bars: Sequence[Bar],
        index: int,
        *,
        side: str,
        quantity: float,
    ) -> Fill | NoFill:
        ...


def _priced(
    *,
    bar: Bar,
    index: int,
    side: str,
    quantity: float,
    execution: ExecutionConfig,
    delay: int,
) -> Fill:
    """Apply slippage against the trade and commission per unit.

    Slippage always hurts: a buy fills above the reference, a sell below it.
    Symmetric or favourable slippage is a way of paying yourself, and over
    thousands of intraday trades it is worth more than any edge the strategy
    could find.
    """
    slippage_bps = execution.slippage_bps * execution.cost_multiplier
    reference = bar.open
    direction = 1.0 if side == "buy" else -1.0
    price = reference * (1.0 + direction * slippage_bps * BPS)
    commission = (
        execution.commission_per_share * execution.cost_multiplier * abs(quantity)
    )
    return Fill(
        timestamp=bar.timestamp,
        bar_index=index,
        price=price,
        reference_price=reference,
        slippage_bps=slippage_bps,
        commission=commission,
        fill_delay_bars=delay,
    )


class BarFillModel:
    """Equities and crypto. Every bar in the window exists by construction."""

    name = "bar_v1"

    def __init__(self, execution: ExecutionConfig) -> None:
        self.execution = execution

    def fill(
        self,
        candidate: CandidateTrade,
        bars: Sequence[Bar],
        index: int,
        *,
        side: str,
        quantity: float,
    ) -> Fill | NoFill:
        if index >= len(bars):
            return NoFill(
                reason="the fill interval lies beyond the end of the data",
                reason_code="NO_BAR_AT_FILL",
            )
        return _priced(
            bar=bars[index],
            index=index,
            side=side,
            quantity=quantity,
            execution=self.execution,
            delay=self.execution.fill_delay_bars,
        )


class SparseBarFillModel(BarFillModel):
    """Options. An absent bar is a no-trade interval, never a price.

    The distinction only becomes visible once bars are indexed by time rather
    than by position, which is why this subclass carries the check even though
    it currently shares its parent's behaviour on a dense series: a caller that
    hands it a gapped series gets a NoFill, and a caller that hands the parent
    the same series gets a fill against whatever bar happened to be next.
    """

    name = "sparse_bar_v1"

    def fill(
        self,
        candidate: CandidateTrade,
        bars: Sequence[Bar],
        index: int,
        *,
        side: str,
        quantity: float,
    ) -> Fill | NoFill:
        if index >= len(bars):
            return NoFill(
                reason=(
                    "no bar exists at the fill interval; the contract did not "
                    "trade. This is a result, not an error - it is the raw "
                    "material of the fill-feasibility rate (PRD §5.6)."
                ),
                reason_code="NO_BAR_AT_FILL",
            )
        expected = candidate.timestamp
        actual = bars[index].timestamp
        if actual < expected:
            return NoFill(
                reason="the fill bar precedes the decision bar",
                reason_code="FILL_BAR_BEFORE_DECISION",
            )
        return super().fill(candidate, bars, index, side=side, quantity=quantity)


def build_fill_model(config: RunConfig) -> FillModel:
    """Resolve the config's fill model. `quote` is refused at config time."""
    models: dict[str, type[BarFillModel]] = {
        "bar": BarFillModel,
        "sparse_bar": SparseBarFillModel,
    }
    try:
        return models[config.execution.fill_model](config.execution)
    except KeyError:
        raise ValueError(
            f"fill model {config.execution.fill_model!r} has no implementation. "
            "'quote' is declared in the interface so the vendor limit stays "
            "visible, and config.validate() refuses it."
        ) from None
