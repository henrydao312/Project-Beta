"""Regime labels, and the design decision behind them.

Outline §5.1 says the three trend states come from "transparent rules on MA
slope and realized-return thresholds". Taken literally - rules evaluated on the
same bar's features - the labels would be a deterministic function of the very
inputs the classifier is given, and M1 would be a model trained to reproduce an
`if` statement. It would fit almost perfectly, add nothing to B2, and the
ablation rung would measure nothing at all.

**So the rule is transparent but forward-looking.** The label at bar t
describes what the next `horizon` bars actually did, scaled by the volatility
known at t:

    scale        = rv_78[t] * sqrt(horizon)      # the move one would expect
    forward move = log(close[t+horizon] / close[t])
    uptrend      if forward move >  trend_k * scale
    downtrend    if forward move < -trend_k * scale
    choppy       otherwise

    vol_flag = high if realized vol over (t, t+horizon] exceeds vol_k * rv_78[t]

The rule is still transparent - two thresholds, no fitting, written above - and
M1 becomes a genuine prediction problem: infer from causal features what the
next session is about to look like. Scaling by contemporaneous volatility
rather than a fixed percentage matters: a 0.3% move is a trend in a calm month
and noise in a violent one, and the folds span both.

**The cost is an embargo, and it is not optional.** A label at bar t reads
prices up to t+horizon, so the last `horizon` bars of any training window carry
labels that peek past its end. `EMBARGO_BARS` is that count, the fold runner
drops those rows, and `test_models.py` asserts it. Skipping the embargo leaks
the first hours of the validation window into training - a small leak that
improves results and leaves no trace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

from project_beta.data.provider import Bar
from project_beta.features.registry import FeatureFrame

# One regular session at the project's 5-minute timeframe. A shorter horizon
# labels noise; a longer one costs a larger embargo and blurs the regime it is
# meant to name.
HORIZON_BARS = 78
EMBARGO_BARS = HORIZON_BARS

TrendState = Literal["uptrend", "downtrend", "choppy"]
VolState = Literal["low", "high"]

TREND_STATES: tuple[TrendState, ...] = ("uptrend", "downtrend", "choppy")
VOL_STATES: tuple[VolState, ...] = ("low", "high")


@dataclass(frozen=True)
class RegimeLabel:
    trend: TrendState
    vol_flag: VolState
    forward_return: float
    forward_vol: float


def label_regimes(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    *,
    horizon: int = HORIZON_BARS,
    trend_k: float = 0.5,
    vol_k: float = 1.15,
) -> list[RegimeLabel | None]:
    """Forward-looking regime labels, aligned bar for bar. None where undefined.

    None appears in two places and both are meaningful: during feature warmup,
    where no contemporaneous volatility exists to scale by, and in the final
    `horizon` bars, where the future the label describes has not happened yet.
    Neither is filled in.
    """
    if "rv_78" not in frame.names:
        raise ValueError(
            "regime labels need rv_78 to scale the forward move. Without a "
            "volatility scale the thresholds would be fixed percentages, and a "
            "0.3% move is a trend in a calm month and noise in a violent one."
        )
    n = len(bars)
    out: list[RegimeLabel | None] = [None] * n
    rv = frame.columns["rv_78"]

    for i in range(n - horizon):
        # A label is only usable where a full feature row exists, so labels are
        # gated on the frame's readiness rather than on rv_78 alone. Otherwise
        # labels would exist on bars the model can never be given, and the two
        # warmups would disagree by the difference between their lookbacks.
        if not frame.is_ready(i):
            continue
        scale_unit = rv[i]
        if scale_unit is None or scale_unit <= 0:
            continue
        start, end = bars[i].close, bars[i + horizon].close
        if start <= 0 or end <= 0:
            continue
        forward_return = math.log(end / start)
        scale = scale_unit * math.sqrt(horizon)

        if forward_return > trend_k * scale:
            trend: TrendState = "uptrend"
        elif forward_return < -trend_k * scale:
            trend = "downtrend"
        else:
            trend = "choppy"

        steps = [
            math.log(bars[j + 1].close / bars[j].close)
            for j in range(i, i + horizon)
            if bars[j].close > 0 and bars[j + 1].close > 0
        ]
        if len(steps) < 2:
            continue
        mean = sum(steps) / len(steps)
        forward_vol = math.sqrt(
            sum((s - mean) ** 2 for s in steps) / (len(steps) - 1)
        )
        vol_flag: VolState = "high" if forward_vol > vol_k * scale_unit else "low"

        out[i] = RegimeLabel(
            trend=trend,
            vol_flag=vol_flag,
            forward_return=forward_return,
            forward_vol=forward_vol,
        )
    return out


def label_distribution(labels: Sequence[RegimeLabel | None]) -> dict[str, int]:
    """Counts per trend state. A fold whose training window saw one regime is a
    reportable fact, not a crash, and the Model Card records it."""
    counts = {state: 0 for state in TREND_STATES}
    for label in labels:
        if label is not None:
            counts[label.trend] += 1
    return counts
