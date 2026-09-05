"""The execution simulator, the deterministic risk engine, and the gate seam.

This module is where the project's central design claim becomes code. Outline
§1A: AI never takes a trading decision, it gates one. That is implemented as a
strict direction of travel - the strategy proposes candidates, gates may only
*reject* or *shrink* them, and the risk engine sizes them by a deterministic
rule that no model can reach. A gate cannot enlarge a position, cannot move a
stop, and cannot create a candidate. Nothing enforces that by convention: a
`size_multiplier` above 1.0 raises.

**The ablation ladder is this function called four times.** B1 is buy and hold.
B2 is the strategy with no gates. M1 adds the regime gate. M2 adds the
signal-quality gate. Everything else - the fills, the costs, the sizing, the
halt logic, the day alignment - is identical by construction rather than by
care, which is what makes the difference between two rungs attributable to the
component that was added.

**Every system returns a value for every session day**, zero on days it did not
trade. The paired bootstrap needs the two series to be the same days in the
same order (EVALUATION_PROTOCOL.md §3); building them from a shared day index
is what makes that true rather than hoped for.

Three simulation conventions, each chosen against the strategy's interest:

  - **A bar that touches both stop and target counts as a stop.** Five-minute
    bars hide their path, and assuming the favourable order across thousands of
    trades is worth more than any edge the strategy could find.
  - **Fills happen `fill_delay_bars` after the deciding bar**, at that bar's
    open, with slippage applied adversely.
  - **Positions are flattened before the close.** An intraday strategy holding
    overnight collects gap drift it never modelled and was never exposed to
    live.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol, Sequence

from project_beta.config import RunConfig
from project_beta.data.pipeline import to_market_time
from project_beta.data.provider import Bar
from project_beta.execution.fill import BPS, Fill, FillModel, NoFill, build_fill_model
from project_beta.features.registry import FeatureFrame
from project_beta.strategy.base import CandidateTrade

STARTING_EQUITY = 100_000.0

DecisionOutcome = Literal["approved", "reduced", "rejected"]

# PRD §4.2: reason codes come from a fixed, documented enum. Free-text reasons
# cannot be counted, and the failure-analysis assistant's whole job is counting
# them.
REASON_CODES: dict[str, str] = {
    "NO_GATE": "no AI gate is active in this system (B2 rung)",
    "REGIME_PERMITS": "the regime classifier permits participation",
    "REGIME_BLOCKS": "the regime classifier rejects this regime",
    "REGIME_REDUCES": "the regime classifier permits at reduced size",
    "SQ_ABOVE_THRESHOLD": "signal quality is at or above the fold's threshold",
    "SQ_BELOW_THRESHOLD": "signal quality is below the fold's threshold",
    "SQ_ABSTAINED": "the signal-quality model abstains in this regime",
    "RISK_SIZE_CAPPED": "position size was reduced by the max_position cap",
    "RISK_ZERO_SIZE": "risk sizing produced no position",
    "RISK_POSITION_OPEN": "a position was already open",
    "RISK_DAILY_LOSS_HALT": "the daily loss limit halted trading for the day",
    "RISK_DRAWDOWN_HALT": "the max-drawdown kill switch halted the run",
    "NO_BAR_AT_FILL": "no bar existed at the fill interval",
    "FILL_BAR_BEFORE_DECISION": "the fill bar preceded the decision bar",
}


class GateError(ValueError):
    """A gate tried to do something gates are not permitted to do."""


@dataclass(frozen=True)
class GateDecision:
    """What a gate may say about a candidate. Reject, shrink, or permit.

    `size_multiplier` is bounded above at 1.0 by construction. A gate that
    could enlarge a position would be taking a trading decision rather than
    filtering one, and the project's whole framing - and its position outside
    the LLM provider's high-risk financial-decisions category (Outline §20.1) -
    depends on that line holding.
    """

    decision: DecisionOutcome
    reason_codes: tuple[str, ...]
    size_multiplier: float = 1.0
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.size_multiplier <= 1.0:
            raise GateError(
                f"size_multiplier {self.size_multiplier} outside [0, 1]. A gate "
                "may reject or shrink a candidate and may never enlarge one: "
                "gates filter trading decisions, they do not take them."
            )
        unknown = [c for c in self.reason_codes if c not in REASON_CODES]
        if unknown:
            raise GateError(
                f"reason codes {unknown} are not in the documented enum "
                "(PRD §4.2). Free-text reasons cannot be counted, and counting "
                "them is the failure-analysis assistant's entire job."
            )


class Gate(Protocol):
    """One AI component in the ladder. Sees a candidate; may only remove."""

    name: str

    def evaluate(
        self, candidate: CandidateTrade, frame: FeatureFrame, index: int
    ) -> GateDecision:
        ...


class CompositeGate:
    """Gates in series. Any rejection is final; multipliers compound.

    This is how M2 is built from M1: the same regime gate plus one more. The
    ladder's rungs differ by a list element.
    """

    def __init__(self, gates: Sequence[Gate]) -> None:
        self.gates = list(gates)
        self.name = "+".join(g.name for g in self.gates) or "none"

    def evaluate(
        self, candidate: CandidateTrade, frame: FeatureFrame, index: int
    ) -> GateDecision:
        codes: list[str] = []
        multiplier = 1.0
        detail: dict[str, Any] = {}
        for gate in self.gates:
            result = gate.evaluate(candidate, frame, index)
            codes.extend(result.reason_codes)
            detail |= result.detail
            if result.decision == "rejected":
                return GateDecision(
                    decision="rejected",
                    reason_codes=tuple(codes),
                    size_multiplier=0.0,
                    detail=detail,
                )
            multiplier *= result.size_multiplier
        if not self.gates:
            codes.append("NO_GATE")
        return GateDecision(
            decision="reduced" if multiplier < 1.0 else "approved",
            reason_codes=tuple(codes),
            size_multiplier=multiplier,
            detail=detail,
        )


# ------------------------------------------------------------------ results


@dataclass(frozen=True)
class Trade:
    candidate: CandidateTrade
    entry: Fill
    quantity: float
    exit_timestamp: datetime
    exit_bar_index: int
    exit_price: float
    exit_reason: str
    pnl: float
    mae: float
    mfe: float

    @property
    def r_multiple(self) -> float:
        risk = self.candidate.risk_per_unit * self.quantity
        return self.pnl / risk if risk > 0 else float("nan")


@dataclass(frozen=True)
class BacktestResult:
    system: str
    days: list[date]
    daily_returns: list[float]
    equity_curve: list[float]
    trades: list[Trade]
    decisions: list[dict[str, Any]]
    halted: bool
    halt_reason: str | None = None

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def approval_rate(self) -> float:
        if not self.decisions:
            return float("nan")
        approved = sum(1 for d in self.decisions if d["decision"] != "rejected")
        return approved / len(self.decisions)


# -------------------------------------------------------------- the simulator


def session_days(bars: Sequence[Bar]) -> list[date]:
    """Every market date present in the bars, in order, deduplicated.

    The shared day index. Both series in a paired comparison are built from
    this, so alignment is structural rather than checked afterwards.
    """
    seen: dict[date, None] = {}
    for bar in bars:
        seen.setdefault(to_market_time(bar.timestamp).date(), None)
    return list(seen)


def _bar_days(bars: Sequence[Bar]) -> list[date]:
    return [to_market_time(b.timestamp).date() for b in bars]


def _decision_id(run_id: str, trade_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}|{trade_id}"))


def run_backtest(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    candidates: Sequence[CandidateTrade],
    config: RunConfig,
    *,
    system: str,
    gate: Gate | None = None,
    fill_model: FillModel | None = None,
    starting_equity: float = STARTING_EQUITY,
    window: tuple[int, int] | None = None,
) -> BacktestResult:
    """One rung of the ladder. Identical machinery for every system.

    `gate=None` is B2: the strategy and the risk engine, no AI. Passing a gate
    is what makes it M1 or M2, and nothing else about the run changes.

    `window` restricts the simulated range to `bars[start:end]` while leaving
    every index global. That matters: features at the start of a fold's test
    window legitimately read bars from before it - those are past bars, and
    recomputing them from a truncated series would give the first hours of
    every fold different feature values from every other bar in the project.
    What the window does prevent is the simulator trading, or accounting,
    outside the fold it was asked about.
    """
    if len(frame) != len(bars):
        raise ValueError("feature frame and bars must align bar for bar")

    start, stop = window or (0, len(bars))
    if not 0 <= start <= stop <= len(bars):
        raise ValueError(f"window {window} is outside the bar range")

    gates = CompositeGate([gate] if gate is not None else [])
    fills = fill_model or build_fill_model(config)
    execution = config.execution
    risk = config.risk

    by_bar: dict[int, CandidateTrade] = {
        c.bar_index: c for c in candidates if start <= c.bar_index < stop
    }
    days = _bar_days(bars)
    unique_days = session_days(bars[start:stop])

    equity = starting_equity
    peak = equity
    day_open_equity = equity
    day_end_equity: list[float] = []
    trades: list[Trade] = []
    decisions: list[dict[str, Any]] = []
    halted = False
    halt_reason: str | None = None
    day_halted = False

    open_position: dict[str, Any] | None = None
    pending: list[tuple[int, CandidateTrade, GateDecision, float]] = []
    current_day = days[start] if stop > start else None

    def close_day() -> None:
        nonlocal day_open_equity
        day_end_equity.append(equity)
        day_open_equity = equity

    for i in range(start, stop):
        bar = bars[i]
        day = days[i]
        is_last_bar_of_day = i + 1 == stop or days[i + 1] != day
        if day != current_day:
            current_day = day
            day_halted = False

        # -- exits, before anything else on this bar --------------------
        if open_position is not None:
            candidate = open_position["candidate"]
            qty = open_position["quantity"]
            entry_price = open_position["entry"].price
            open_position["mae"] = min(
                open_position["mae"], (bar.low - entry_price) * qty
            )
            open_position["mfe"] = max(
                open_position["mfe"], (bar.high - entry_price) * qty
            )

            exit_price: float | None = None
            reason = ""
            # Stop before target when a single bar touches both. A 5-minute bar
            # hides its path; assuming the favourable order is worth more than
            # any edge the strategy could find.
            if bar.low <= candidate.stop_price:
                exit_price, reason = candidate.stop_price, "stop"
            elif bar.high >= candidate.target_price:
                exit_price, reason = candidate.target_price, "target"
            elif i - open_position["entry"].bar_index >= execution.max_hold_bars:
                exit_price, reason = bar.close, "max_hold"
            elif execution.flatten_at_session_end and is_last_bar_of_day:
                exit_price, reason = bar.close, "session_end"

            if exit_price is not None:
                slip = execution.slippage_bps * execution.cost_multiplier * BPS
                realised = exit_price * (1.0 - slip)
                commission = (
                    execution.commission_per_share * execution.cost_multiplier * qty
                )
                pnl = (realised - entry_price) * qty - commission
                equity += pnl
                peak = max(peak, equity)
                trade = Trade(
                    candidate=candidate,
                    entry=open_position["entry"],
                    quantity=qty,
                    exit_timestamp=bar.timestamp,
                    exit_bar_index=i,
                    exit_price=realised,
                    exit_reason=reason,
                    pnl=pnl,
                    mae=open_position["mae"],
                    mfe=open_position["mfe"],
                )
                trades.append(trade)
                open_position["record"]["outcome"] = {
                    "exit_timestamp": bar.timestamp.isoformat(),
                    "exit_reason": reason,
                    "pnl": pnl,
                    "mae": trade.mae,
                    "mfe": trade.mfe,
                    "r_multiple": trade.r_multiple,
                }
                open_position = None

                # The kill switch. Outline §8A: this halts the run, and a
                # halted run reports the halt rather than quietly ending.
                if peak > 0 and (peak - equity) / peak >= risk.max_drawdown:
                    halted = True
                    halt_reason = "RISK_DRAWDOWN_HALT"
                if equity - day_open_equity <= -risk.daily_loss_limit:
                    day_halted = True

        # -- pending entries -------------------------------------------
        still_pending: list[tuple[int, CandidateTrade, GateDecision, float]] = []
        for fill_index, candidate, verdict, quantity in pending:
            if fill_index != i:
                still_pending.append((fill_index, candidate, verdict, quantity))
                continue
            record = _record_for(candidate, config, verdict, system)
            if halted or day_halted or open_position is not None:
                record["decision"] = "rejected"
                blocked = (
                    "RISK_DRAWDOWN_HALT"
                    if halted
                    else ("RISK_DAILY_LOSS_HALT" if day_halted else "RISK_POSITION_OPEN")
                )
                record["decision_reason_codes"] = [*verdict.reason_codes, blocked]
                decisions.append(record)
                continue
            result = fills.fill(
                candidate, bars, i, side="buy", quantity=quantity
            )
            if isinstance(result, NoFill):
                record["decision"] = "rejected"
                record["decision_reason_codes"] = [
                    *verdict.reason_codes,
                    result.reason_code,
                ]
                record["instrument"]["tradeable"] = False
                decisions.append(record)
                continue
            equity -= result.commission
            record["execution"] = {
                "fill_price": result.price,
                "slippage_bps": result.slippage_bps,
                "commission": result.commission,
                "fill_delay_bars": result.fill_delay_bars,
            }
            decisions.append(record)
            open_position = {
                "candidate": candidate,
                "entry": result,
                "quantity": quantity,
                "mae": 0.0,
                "mfe": 0.0,
                "record": record,
            }
        pending = still_pending

        # -- new candidates --------------------------------------------
        candidate = by_bar.get(i)
        if candidate is not None:
            verdict = gates.evaluate(candidate, frame, i)
            if verdict.decision == "rejected":
                record = _record_for(candidate, config, verdict, system)
                decisions.append(record)
            else:
                quantity, size_codes = _size(
                    candidate, equity, config, verdict.size_multiplier
                )
                verdict = GateDecision(
                    decision=verdict.decision,
                    reason_codes=verdict.reason_codes + tuple(size_codes),
                    size_multiplier=verdict.size_multiplier,
                    detail=verdict.detail,
                )
                if quantity <= 0:
                    record = _record_for(candidate, config, verdict, system)
                    record["decision"] = "rejected"
                    decisions.append(record)
                else:
                    pending.append(
                        (i + execution.fill_delay_bars, candidate, verdict, quantity)
                    )

        if is_last_bar_of_day:
            close_day()

    daily_returns = _to_daily_returns(day_end_equity, starting_equity)
    return BacktestResult(
        system=system,
        days=unique_days[: len(daily_returns)],
        daily_returns=daily_returns,
        equity_curve=day_end_equity,
        trades=trades,
        decisions=decisions,
        halted=halted,
        halt_reason=halt_reason,
    )


def _size(
    candidate: CandidateTrade,
    equity: float,
    config: RunConfig,
    multiplier: float,
) -> tuple[float, list[str]]:
    """Deterministic risk-based sizing. No model reaches this function.

    Risk a fixed fraction of equity between entry and stop, then cap the
    notional at `max_position`. A gate's multiplier can only shrink the result.
    """
    risk = config.risk
    codes: list[str] = []
    per_unit = candidate.risk_per_unit
    if per_unit <= 0:
        return 0.0, ["RISK_ZERO_SIZE"]
    quantity = (equity * risk.risk_per_trade) / per_unit
    capped = risk.max_position / candidate.entry_price_ref
    if quantity > capped:
        quantity = capped
        codes.append("RISK_SIZE_CAPPED")
    quantity *= multiplier
    if quantity <= 0:
        codes.append("RISK_ZERO_SIZE")
    return quantity, codes


def _record_for(
    candidate: CandidateTrade,
    config: RunConfig,
    verdict: GateDecision,
    system: str,
) -> dict[str, Any]:
    """A DecisionRecord (PRD §4.2), the single source of truth for a decision.

    Every field the explanation service may cite has to be here: a claim that
    is not traceable to a field of this record is a release blocker rather than
    a rate to be reported (Outline §20.2 harm 2).
    """
    record: dict[str, Any] = {
        "decision_id": _decision_id(config.run_id, candidate.trade_id),
        "trade_id": candidate.trade_id,
        "timestamp": candidate.timestamp.isoformat(),
        "run_id": config.run_id,
        "system": system,
        "mode": config.mode,
        "asset_class": config.data.asset_class,
        "feed": config.data.feed,
        "vendor": config.data.provider,
        "symbol": candidate.symbol,
        "signal_type": candidate.signal_type,
        "signal_strength": candidate.signal_strength,
        "strategy_version": candidate.strategy_version,
        "decision": verdict.decision,
        "decision_reason_codes": list(verdict.reason_codes),
        "risk": {
            "sizing_rule": config.risk.sizing,
            "risk_per_trade": config.risk.risk_per_trade,
            "size_multiplier": verdict.size_multiplier,
        },
        "instrument": {
            "selected": candidate.symbol,
            "selection_rule": "passthrough_v1",
            "tradeable": True,
        },
        "entry_price_ref": candidate.entry_price_ref,
        "stop_price": candidate.stop_price,
        "target_price": candidate.target_price,
    }
    record |= verdict.detail
    return record


def _to_daily_returns(day_end_equity: Sequence[float], starting: float) -> list[float]:
    out: list[float] = []
    previous = starting
    for value in day_end_equity:
        out.append(value / previous - 1.0 if previous > 0 else 0.0)
        previous = value
    return out
