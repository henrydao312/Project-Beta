"""The exploratory strategies: MA trend and mean reversion.

These exist for one reason, stated plainly in Outline §5.3: to keep the
Strategy Engine a real interface rather than a single function with a
docstring. A second and third implementation is what proves the seam holds, and
it is what makes continued work after the course a matter of adding a class.

They are `tier = "secondary"`, which is not a label. `assert_gradeable` refuses
them, `build_strategy` refuses to promote them, and the walk-forward harness
will not compute a headline metric for one. They get no cost stress, no
ablation, and no walk-forward claim, so any Sharpe figure from one would look
exactly like a result while having nothing behind it.

They read the same registry as the primary, so they inherit the volume drop
without needing to know about it.
"""

from __future__ import annotations

from typing import Any, Sequence

from project_beta.config import RunConfig
from project_beta.data.provider import Bar
from project_beta.features.registry import FeatureFrame
from project_beta.strategy.base import (
    CandidateTrade,
    Strategy,
    make_trade_id,
    register_strategy,
)


class _SecondaryStrategy(Strategy):
    """Shared candidate construction. The rule is the only difference."""

    tier = "secondary"

    def _emit(
        self,
        *,
        frame: FeatureFrame,
        bars: Sequence[Bar],
        config: RunConfig,
        i: int,
        strength: float,
        stop_distance: float,
    ) -> CandidateTrade | None:
        if stop_distance <= 0:
            return None
        entry = bars[i].close
        stop = entry - stop_distance
        if stop <= 0:
            return None
        return CandidateTrade(
            trade_id=make_trade_id(
                strategy_version=self.config.version,
                symbol=config.data.symbol,
                timestamp=frame.timestamps[i],
                direction="long",
            ),
            timestamp=frame.timestamps[i],
            bar_index=i,
            bar_timeframe=config.data.timeframe,
            asset_class=config.data.asset_class,
            symbol=config.data.symbol,
            direction="long",
            signal_type=self.signal_type,
            signal_strength=strength,
            entry_price_ref=entry,
            stop_price=stop,
            target_price=entry + self.params["target_r_multiple"] * stop_distance,
            features_snapshot_id=frame.snapshot_id(i),
            strategy_version=self.config.version,
            tier=self.tier,
        )


@register_strategy
class MovingAverageTrend(_SecondaryStrategy):
    """Long while the fast average leads the slow one and the slow one rises."""

    name = "ma_trend"
    version = "ma_v1"
    signal_type = "ma_trend"
    required_features = ("ma_gap", "ma_slope_slow", "rv_12")

    @classmethod
    def defaults(cls) -> dict[str, Any]:
        return {
            "min_ma_gap": 0.0005,
            "min_slope": 0.0,
            "stop_vol_mult": 3.0,
            "target_r_multiple": 2.0,
            "cooldown_bars": 78,
        }

    def generate_candidates(
        self, frame: FeatureFrame, bars: Sequence[Bar], config: RunConfig
    ) -> list[CandidateTrade]:
        self.check_features(frame)
        p = self.params
        out: list[CandidateTrade] = []
        last = -10**9
        for i in range(len(bars)):
            row = frame.row(i)
            if row is None or i - last < p["cooldown_bars"]:
                continue
            if row["ma_gap"] <= p["min_ma_gap"] or row["ma_slope_slow"] <= p["min_slope"]:
                continue
            candidate = self._emit(
                frame=frame,
                bars=bars,
                config=config,
                i=i,
                strength=min(1.0, row["ma_gap"] / 0.01),
                stop_distance=p["stop_vol_mult"] * row["rv_12"] * bars[i].close,
            )
            if candidate is not None:
                out.append(candidate)
                last = i
        return out


@register_strategy
class MeanReversion(_SecondaryStrategy):
    """Long near the trailing low while the trend is flat and volatility spikes."""

    name = "mean_reversion"
    version = "mr_v1"
    signal_type = "mean_reversion"
    required_features = ("dist_low_78", "ma_gap", "rv_ratio", "rv_12")

    @classmethod
    def defaults(cls) -> dict[str, Any]:
        return {
            "max_dist_low": 0.001,
            "max_abs_ma_gap": 0.002,
            "min_rv_ratio": 1.3,
            "stop_vol_mult": 2.0,
            "target_r_multiple": 1.5,
            "cooldown_bars": 78,
        }

    def generate_candidates(
        self, frame: FeatureFrame, bars: Sequence[Bar], config: RunConfig
    ) -> list[CandidateTrade]:
        self.check_features(frame)
        p = self.params
        out: list[CandidateTrade] = []
        last = -10**9
        for i in range(len(bars)):
            row = frame.row(i)
            if row is None or i - last < p["cooldown_bars"]:
                continue
            near_low = row["dist_low_78"] <= p["max_dist_low"]
            flat = abs(row["ma_gap"]) <= p["max_abs_ma_gap"]
            stretched = row["rv_ratio"] >= p["min_rv_ratio"]
            if not (near_low and flat and stretched):
                continue
            candidate = self._emit(
                frame=frame,
                bars=bars,
                config=config,
                i=i,
                strength=min(1.0, (row["rv_ratio"] - 1.0) / 2.0),
                stop_distance=p["stop_vol_mult"] * row["rv_12"] * bars[i].close,
            )
            if candidate is not None:
                out.append(candidate)
                last = i
        return out
