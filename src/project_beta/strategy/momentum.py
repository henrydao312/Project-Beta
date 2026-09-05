"""Momentum breakout - the primary strategy, and the only one graded.

The rule, in one sentence: when price closes above the high of its previous
session-length window, while the fast average sits above the slow one, the
trend is orderly enough to register on ADX, and the bar's own range is wide
relative to its recent norm - propose a long.

**There is no volume confirmation term, and its absence is the design.** The
obvious fifth condition is "and volume is above its trailing median", which is
in most textbook statements of this pattern. It is not here because the
feed-transfer experiment (2026-09-02) dropped volume-derived features, and the
argument that removed them from the models removes them from the rules for the
same reason: backtests read SIP, the live loop reads IEX, and IEX carries a
median 3.16% of consolidated volume with a different execution mix. A rule
reading "volume above 1.5x the trailing median" would fire at different times
live than it did in the backtest, so the strategy's live behaviour would differ
*in construction* from the thing that was validated. Dropping the term costs
some selectivity. Keeping it would cost the ability to claim the backtest
describes the live system, which is the whole point of the exercise.

**Four thresholds, all in the config.** Sweeping them is a new YAML file, and
the values used are stamped into `provenance()` with every results row. They
are chosen on the validation window of each fold, never on the test window.
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


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


@register_strategy
class MomentumBreakout(Strategy):
    name = "momentum_breakout"
    version = "mom_v1"
    tier = "primary"
    signal_type = "momentum_breakout"
    required_features = (
        "dist_high_78",
        "ma_gap",
        "adx_14",
        "range_expansion",
        "rv_12",
    )

    @classmethod
    def defaults(cls) -> dict[str, Any]:
        return {
            # How far past the trailing high a close must reach, as a
            # fraction of price. `dist_high_78` measures the previous 78 bars
            # and excludes the current one, so 0.0 means "closed at or above
            # the trailing range" - a real breakout, not a bar that merely
            # closed at its own high. A *negative* value would turn this into
            # a "near the high" strategy, which is a different claim and needs
            # a decision-log entry rather than a parameter change.
            "breakout_tolerance": 0.0,
            # Trend filter. Positive means the fast average is above the slow.
            "min_ma_gap": 0.0,
            # Wilder's conventional "trending" floor. Below it, price is moving
            # without direction and a breakout is noise.
            "min_adx": 20.0,
            # The bar's true range against its trailing median. 1.0 is an
            # ordinary bar; a breakout on an ordinary bar is usually a drift.
            "min_range_expansion": 1.2,
            # Stop distance in units of short-horizon realized volatility.
            "stop_vol_mult": 3.0,
            # Target as a multiple of the entry-to-stop distance.
            "target_r_multiple": 2.0,
            # Bars to wait before proposing again. Without it a sustained
            # breakout proposes on every bar, and the candidate count - which
            # the ablation reports - would measure trend persistence rather
            # than signal frequency.
            "cooldown_bars": 12,
            # Long-only by default. B1 is buy and hold, so a long-only primary
            # keeps the ladder's rungs comparable in direction; enabling shorts
            # is a separate claim and needs its own decision-log entry.
            "allow_short": False,
        }

    # ------------------------------------------------------------- scoring

    def _strength(self, adx: float, expansion: float) -> float:
        """An ordinal score in [0, 1]. Not a probability - see CandidateTrade.

        Two terms, equally weighted, each saturating: ADX at 50 (decisively
        trending by any convention) and range expansion at 3x its median. The
        saturation matters. Without it one enormous bar would dominate the
        score, and the score feeds position sizing.
        """
        trend = _clamp01((adx - self.params["min_adx"]) / 30.0)
        fuel = _clamp01((expansion - 1.0) / 2.0)
        return round(0.5 * trend + 0.5 * fuel, 6)

    # ------------------------------------------------------------ generation

    def generate_candidates(
        self, frame: FeatureFrame, bars: Sequence[Bar], config: RunConfig
    ) -> list[CandidateTrade]:
        self.check_features(frame)
        p = self.params
        out: list[CandidateTrade] = []
        last_bar = -10**9

        for i in range(len(bars)):
            row = frame.row(i)
            if row is None:
                continue
            if i - last_bar < p["cooldown_bars"]:
                continue

            long_break = row["dist_high_78"] >= p["breakout_tolerance"]
            trend_up = row["ma_gap"] > p["min_ma_gap"]
            orderly = row["adx_14"] >= p["min_adx"]
            wide = row["range_expansion"] >= p["min_range_expansion"]
            if not (long_break and trend_up and orderly and wide):
                continue

            entry = bars[i].close
            # Stop scaled by realized volatility rather than a fixed
            # percentage: a fixed stop is a different strategy in a calm month
            # than in a violent one, and the walk-forward folds span both.
            stop_distance = p["stop_vol_mult"] * row["rv_12"] * entry
            if stop_distance <= 0:
                # Zero realized volatility over twelve bars means a flat tape.
                # No defensible stop exists, so no candidate. Skipping is the
                # honest answer; a floor would invent a risk number.
                continue
            stop = entry - stop_distance
            target = entry + p["target_r_multiple"] * stop_distance
            if stop <= 0:
                continue

            out.append(
                CandidateTrade(
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
                    signal_strength=self._strength(
                        row["adx_14"], row["range_expansion"]
                    ),
                    entry_price_ref=entry,
                    stop_price=stop,
                    target_price=target,
                    features_snapshot_id=frame.snapshot_id(i),
                    strategy_version=self.config.version,
                    tier=self.tier,
                )
            )
            last_bar = i

        return out
