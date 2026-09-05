"""The feature implementations. Price-derived, scale-free, and strictly causal.

Three constraints shape everything in this file, and each one is a decision
that was made and recorded rather than a style preference.

**Causal by construction.** Every function is written as a forward pass in
which the value at index i reads only bars 0..i. Nothing centres a window,
nothing reverses a list, nothing uses a whole-series statistic - no full-sample
mean, no full-sample standard deviation, no min-max scaling. A single
whole-series normalisation would leak the future into every training row while
leaving the code looking ordinary, which is why the rule is structural here
rather than a review checklist item.
`test_features.py::test_features_are_shift_forward_invariant` verifies it
empirically: computing on the first k bars must reproduce, exactly, the first k
values computed on the whole series.

**Scale-free.** Every feature is a ratio, a log return, or a bounded index.
Backtests run on SIP and the live loop runs on IEX (Outline §9), so a feature
carrying absolute units trains on one distribution and infers on another. Price
levels are the same on both feeds, which is why price-derived ratios are safe;
volume is not, which is why there is none here.

**No volume.** The feed-transfer experiment (2026-09-02) resolved to DROP under
its pre-committed rule. The four tested features are recorded in the registry
with `status="dropped"` rather than deleted. Two consequences that are easy to
get wrong:

  - **VWAP distance is volume-derived and goes too.** VWAP is a price, and the
    distance to it is dimensionless, so it reads as safe. It is not: the
    weights are volumes, and IEX's ~3% share of consolidated volume is not a
    random 3% - it is a different execution mix. The same argument that dropped
    `vol_z` drops `vwap_dist`, and it is registered as dropped for that reason.
  - **The strategy rules lose volume too**, not just the models. A B2 rule such
    as "volume above 1.5x the trailing median" carries the identical
    train/live mismatch. See `strategy/momentum.py`.
"""

from __future__ import annotations

import math
from bisect import bisect_left, insort
from collections import deque
from typing import Sequence

from project_beta.data.calendar import REGULAR_OPEN, session_close
from project_beta.data.pipeline import to_market_time
from project_beta.data.provider import Bar
from project_beta.features.registry import REGISTRY, FeatureSpec

# Window lengths, in bars. At the project's 5-minute timeframe these are one
# hour and one regular session. They are bar counts rather than durations
# because a feature must mean the same thing on a 13:00 early close, where the
# session is 42 bars, as on a full one.
FAST = 12
SLOW = 78

# The transfer-experiment verdict, quoted once so every dropped feature cites
# the same sentence rather than a paraphrase of it.
_VOLUME_VERDICT = (
    "feed-transfer experiment 2026-09-02: no volume feature cleared the "
    "pre-committed keep bar of Spearman >= 0.70 (best 0.664, primary 0.572), "
    "and the empty keep list resolves to DROP. IEX carries a median 3.16% of "
    "consolidated volume and the composition does not transfer bar for bar."
)


# --------------------------------------------------------------- primitives


def _sma(values: Sequence[float | None], window: int) -> list[float | None]:
    """Causal simple moving average. None until the window is full."""
    out: list[float | None] = [None] * len(values)
    total = 0.0
    buf: deque[float] = deque()
    for i, v in enumerate(values):
        if v is None:
            # A gap resets the window rather than being skipped over: averaging
            # across an undefined value silently shortens the lookback.
            buf.clear()
            total = 0.0
            continue
        buf.append(v)
        total += v
        if len(buf) > window:
            total -= buf.popleft()
        if len(buf) == window:
            out[i] = total / window
    return out


def _rolling_std(values: Sequence[float | None], window: int) -> list[float | None]:
    """Causal sample standard deviation over a fixed window."""
    out: list[float | None] = [None] * len(values)
    buf: deque[float] = deque()
    total = 0.0
    total_sq = 0.0
    for i, v in enumerate(values):
        if v is None:
            buf.clear()
            total = total_sq = 0.0
            continue
        buf.append(v)
        total += v
        total_sq += v * v
        if len(buf) > window:
            old = buf.popleft()
            total -= old
            total_sq -= old * old
        if len(buf) == window:
            mean = total / window
            var = max(total_sq / window - mean * mean, 0.0)
            out[i] = math.sqrt(var)
    return out


def _rolling_extreme(values: Sequence[float], window: int, *, largest: bool) -> list[float | None]:
    """Causal rolling max or min in O(n), via a monotonic deque."""
    out: list[float | None] = [None] * len(values)
    dq: deque[int] = deque()
    for i, v in enumerate(values):
        while dq and ((values[dq[-1]] <= v) if largest else (values[dq[-1]] >= v)):
            dq.pop()
        dq.append(i)
        if dq[0] <= i - window:
            dq.popleft()
        if i >= window - 1:
            out[i] = values[dq[0]]
    return out


def _rolling_median(values: Sequence[float | None], window: int) -> list[float | None]:
    """Causal rolling median. Median, not mean: true range is heavy-tailed, and
    one halt or one gap open would drag a mean enough to suppress the very
    expansion the feature is meant to detect."""
    out: list[float | None] = [None] * len(values)
    buf: deque[float] = deque()
    ordered: list[float] = []
    for i, v in enumerate(values):
        if v is None:
            buf.clear()
            ordered.clear()
            continue
        buf.append(v)
        insort(ordered, v)
        if len(buf) > window:
            old = buf.popleft()
            del ordered[bisect_left(ordered, old)]
        if len(buf) == window:
            mid = window // 2
            out[i] = (
                ordered[mid]
                if window % 2
                else 0.5 * (ordered[mid - 1] + ordered[mid])
            )
    return out


def _log_returns(bars: Sequence[Bar]) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    for i in range(1, len(bars)):
        prev, cur = bars[i - 1].close, bars[i].close
        if prev > 0 and cur > 0:
            out[i] = math.log(cur / prev)
    return out


def _true_range(bars: Sequence[Bar]) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    for i in range(1, len(bars)):
        b, prev_close = bars[i], bars[i - 1].close
        out[i] = max(
            b.high - b.low,
            abs(b.high - prev_close),
            abs(b.low - prev_close),
        )
    return out


def _ratio(numer: float, denom: float) -> float | None:
    """Guarded division. None rather than inf: an undefined value is honest,
    and an infinity propagates silently into a model as a very large number."""
    return numer / denom if denom > 0 else None


# ------------------------------------------------------------ feature bodies


def _feat_ret(window: int):
    def fn(bars: Sequence[Bar]) -> list[float | None]:
        out: list[float | None] = [None] * len(bars)
        for i in range(window, len(bars)):
            prev, cur = bars[i - window].close, bars[i].close
            if prev > 0 and cur > 0:
                out[i] = math.log(cur / prev)
        return out

    return fn


def _feat_rv(window: int):
    def fn(bars: Sequence[Bar]) -> list[float | None]:
        return _rolling_std(_log_returns(bars), window)

    return fn


def _feat_rv_ratio(bars: Sequence[Bar]) -> list[float | None]:
    rets = _log_returns(bars)
    fast = _rolling_std(rets, FAST)
    slow = _rolling_std(rets, SLOW)
    out: list[float | None] = [None] * len(bars)
    for i in range(len(bars)):
        f, s = fast[i], slow[i]
        if f is not None and s is not None:
            out[i] = _ratio(f, s)
    return out


def _feat_ma_gap(bars: Sequence[Bar]) -> list[float | None]:
    closes = [b.close for b in bars]
    fast = _sma(closes, FAST)
    slow = _sma(closes, SLOW)
    out: list[float | None] = [None] * len(bars)
    for i in range(len(bars)):
        f, s = fast[i], slow[i]
        if f is not None and s is not None:
            out[i] = _ratio(f - s, s)
    return out


def _feat_ma_slope(window: int):
    def fn(bars: Sequence[Bar]) -> list[float | None]:
        ma = _sma([b.close for b in bars], window)
        out: list[float | None] = [None] * len(bars)
        for i in range(window, len(bars)):
            now, then = ma[i], ma[i - window]
            if now is not None and then is not None:
                out[i] = _ratio(now - then, then)
        return out

    return fn


def _feat_adx(period: int = 14):
    """Wilder's ADX. Trend strength without direction, and dimensionless.

    Included where a raw moving-average slope is not enough: slope says how
    fast price moved, ADX says whether the move was orderly. The regime
    classifier's 'choppy' state is exactly the case where slope is small but
    noisy, and a directionless strength index separates it from a genuine flat
    trend far better than a second slope term would.
    """

    def fn(bars: Sequence[Bar]) -> list[float | None]:
        n = len(bars)
        out: list[float | None] = [None] * n
        # The first ADX sits at index 2*period-1, so 2*period bars is the exact
        # requirement. An off-by-one here breaks shift-forward invariance at
        # precisely one series length, which is the kind of defect that passes
        # every test written by hand and fails the property test.
        if n < 2 * period:
            return out

        tr = _true_range(bars)
        plus_dm: list[float] = [0.0] * n
        minus_dm: list[float] = [0.0] * n
        for i in range(1, n):
            up = bars[i].high - bars[i - 1].high
            down = bars[i - 1].low - bars[i].low
            plus_dm[i] = up if (up > down and up > 0) else 0.0
            minus_dm[i] = down if (down > up and down > 0) else 0.0

        # Wilder smoothing, seeded on the first `period` observations. Indices
        # 1..period inclusive, so the first smoothed value sits at `period`.
        atr = sum(t or 0.0 for t in tr[1 : period + 1])
        sp = sum(plus_dm[1 : period + 1])
        sm = sum(minus_dm[1 : period + 1])

        dx: list[float | None] = [None] * n
        for i in range(period, n):
            if i > period:
                atr = atr - atr / period + (tr[i] or 0.0)
                sp = sp - sp / period + plus_dm[i]
                sm = sm - sm / period + minus_dm[i]
            if atr <= 0:
                continue
            plus_di = 100.0 * sp / atr
            minus_di = 100.0 * sm / atr
            denom = plus_di + minus_di
            if denom > 0:
                dx[i] = 100.0 * abs(plus_di - minus_di) / denom

        # ADX is a Wilder average of DX, seeded on its first `period` values.
        window = [d for d in dx[period : 2 * period] if d is not None]
        if len(window) < period:
            return out
        adx = sum(window) / period
        out[2 * period - 1] = adx
        for i in range(2 * period, n):
            d = dx[i]
            if d is None:
                out[i] = adx
                continue
            adx = (adx * (period - 1) + d) / period
            out[i] = adx
        return out

    return fn


def _feat_range_expansion(bars: Sequence[Bar]) -> list[float | None]:
    tr = _true_range(bars)
    med = _rolling_median(tr, SLOW)
    out: list[float | None] = [None] * len(bars)
    for i in range(len(bars)):
        t, m = tr[i], med[i]
        if t is not None and m is not None:
            out[i] = _ratio(t, m)
    return out


def _feat_dist_extreme(*, high: bool):
    """Distance from the *prior* window's extreme, as a fraction of price.

    Two decisions here, and the first one was a bug before it was a decision.

    **The window excludes the current bar.** Comparing a close against a window
    that contains the current bar's own high makes a breakout almost
    unreachable: the close is bounded above by the high of the same bar, so the
    feature could only reach zero on a bar that closed exactly at its own high
    while that high was also the window maximum. The rule fired on roughly
    nothing, which a threshold sweep would have quietly papered over. Measured
    against the previous 78 bars, a positive value means the close broke the
    trailing range - the Donchian sense, and the one the strategy means.

    **It is a distance, not a boolean.** A 'made a new high' flag would
    hard-code the strategy's trigger into the model's input and leave the
    regime classifier unable to tell a marginal break from a decisive one.
    """

    def fn(bars: Sequence[Bar]) -> list[float | None]:
        series = [b.high for b in bars] if high else [b.low for b in bars]
        ext = _rolling_extreme(series, SLOW, largest=high)
        out: list[float | None] = [None] * len(bars)
        for i in range(1, len(bars)):
            e = ext[i - 1]  # the window ending at the previous bar
            if e is not None and bars[i].close > 0:
                out[i] = (bars[i].close - e) / bars[i].close
        return out

    return fn


def _feat_tod_frac(bars: Sequence[Bar]) -> list[float | None]:
    """Fraction of the regular session elapsed, in [0, 1).

    Measured against the day's own close, so a 13:00 early close spans the same
    0-to-1 range as a full session. Measuring against a fixed 16:00 would map
    every early-close bar into the first half of the range and teach the model
    that those days end at lunchtime.
    """
    open_minutes = REGULAR_OPEN.hour * 60 + REGULAR_OPEN.minute
    out: list[float | None] = [None] * len(bars)
    for i, b in enumerate(bars):
        local = to_market_time(b.timestamp)
        close = session_close(local.date())
        span = (close.hour * 60 + close.minute) - open_minutes
        elapsed = (local.hour * 60 + local.minute) - open_minutes
        if span > 0 and 0 <= elapsed < span:
            out[i] = elapsed / span
    return out


# ----------------------------------------------------------------- registry


def _register_all(registry=REGISTRY) -> None:
    """Populate the registry. Called once at import of `project_beta.features`."""

    reg = registry.register

    reg(FeatureSpec(
        name="ret_1",
        requires="bars",
        lookback=1,
        derivation="log(close_t / close_{t-1})",
        rationale="the bar's own move; the base term every other return scales against",
        fn=_feat_ret(1),
    ))
    reg(FeatureSpec(
        name="ret_12",
        requires="bars",
        lookback=FAST,
        derivation=f"log(close_t / close_{{t-{FAST}}})",
        rationale="one hour of drift at the 5-minute timeframe; the momentum term",
        fn=_feat_ret(FAST),
    ))
    reg(FeatureSpec(
        name="rv_12",
        requires="bars",
        lookback=FAST,
        derivation=f"stdev(log returns, {FAST} bars)",
        rationale="short-horizon realized volatility; the sizing and stop input",
        fn=_feat_rv(FAST),
    ))
    reg(FeatureSpec(
        name="rv_78",
        requires="bars",
        lookback=SLOW,
        derivation=f"stdev(log returns, {SLOW} bars)",
        rationale="session-length realized volatility; the volatility-flag input",
        fn=_feat_rv(SLOW),
    ))
    reg(FeatureSpec(
        name="rv_ratio",
        requires="bars",
        lookback=SLOW,
        derivation=f"stdev(returns, {FAST}) / stdev(returns, {SLOW})",
        rationale=(
            "volatility expanding or contracting relative to itself. Scale-free "
            "twice over, and the cleanest available proxy for a regime turning"
        ),
        fn=_feat_rv_ratio,
    ))
    reg(FeatureSpec(
        name="ma_gap",
        requires="bars",
        lookback=SLOW,
        derivation=f"(SMA_{FAST} - SMA_{SLOW}) / SMA_{SLOW}",
        rationale="trend direction and separation, normalised by price level",
        fn=_feat_ma_gap,
    ))
    reg(FeatureSpec(
        name="ma_slope_fast",
        requires="bars",
        lookback=2 * FAST - 1,
        derivation=f"(SMA_{FAST},t - SMA_{FAST},t-{FAST}) / SMA_{FAST},t-{FAST}",
        rationale="short-horizon trend slope; the primary trend-state label input",
        fn=_feat_ma_slope(FAST),
    ))
    reg(FeatureSpec(
        name="ma_slope_slow",
        requires="bars",
        lookback=2 * SLOW - 1,
        derivation=f"(SMA_{SLOW},t - SMA_{SLOW},t-{SLOW}) / SMA_{SLOW},t-{SLOW}",
        rationale="session-horizon trend slope; separates a pullback from a turn",
        fn=_feat_ma_slope(SLOW),
    ))
    reg(FeatureSpec(
        name="adx_14",
        requires="bars",
        lookback=27,
        derivation="Wilder ADX, period 14",
        rationale="trend strength without direction; separates choppy from flat",
        fn=_feat_adx(14),
    ))
    reg(FeatureSpec(
        name="range_expansion",
        requires="bars",
        lookback=SLOW,
        derivation=f"true_range_t / median(true_range, {SLOW} bars)",
        rationale="today's range against its own recent norm; a breakout's fuel",
        fn=_feat_range_expansion,
    ))
    reg(FeatureSpec(
        name="dist_high_78",
        requires="bars",
        lookback=SLOW,
        derivation=f"(close_t - max(high, bars t-{SLOW}..t-1)) / close_t",
        rationale=(
            "distance past the trailing high, excluding the current bar; "
            "positive is a breakout"
        ),
        fn=_feat_dist_extreme(high=True),
    ))
    reg(FeatureSpec(
        name="dist_low_78",
        requires="bars",
        lookback=SLOW,
        derivation=f"(close_t - min(low, bars t-{SLOW}..t-1)) / close_t",
        rationale=(
            "distance past the trailing low, excluding the current bar; "
            "negative is a breakdown, and the mean-reversion trigger"
        ),
        fn=_feat_dist_extreme(high=False),
    ))
    reg(FeatureSpec(
        name="tod_frac",
        requires="bars",
        lookback=0,
        derivation="(minutes since 09:30 ET) / (session length that day)",
        rationale=(
            "intraday seasonality is real and feed-invariant: the open and the "
            "close behave differently from midday on any feed"
        ),
        fn=_feat_tod_frac,
        # Meaningless where there is no session. Crypto runs continuous, and a
        # 'fraction of the session elapsed' on a 24/7 tape would be a number
        # with no referent rather than a missing one.
        asset_classes=frozenset({"equity", "option"}),
    ))

    # ------------------------------------------------------------- dropped

    for name, derivation in (
        ("vol_tod", "volume_t / median(volume at this time of day, 20 sessions)"),
        ("vol_ratio", f"volume_t / median(volume, {SLOW} bars)"),
        ("vol_z", f"(volume_t - mean(volume, {SLOW})) / stdev(volume, {SLOW})"),
        ("trades_ratio", f"trade_count_t / median(trade_count, {SLOW} bars)"),
    ):
        reg(FeatureSpec(
            name=name,
            requires="bars",
            lookback=SLOW,
            derivation=derivation,
            rationale="tested for feed transfer and removed; retained as a record",
            volume_derived=True,
            status="dropped",
            dropped_reason=_VOLUME_VERDICT,
        ))

    reg(FeatureSpec(
        name="vwap_dist",
        requires="bars",
        lookback=0,
        derivation="(close_t - vwap_t) / vwap_t",
        rationale="tested by extension of the volume rule and removed",
        volume_derived=True,
        status="dropped",
        dropped_reason=(
            "volume-derived by construction: the distance is dimensionless but "
            "the weights are volumes, and IEX's ~3% share is a different "
            "execution mix rather than a random sample of it. Dropped by the "
            "same rule as the four tested volume features, extended rather "
            "than re-run - recorded here so the extension is visible and can "
            "be reversed by a decision-log entry if the rule is ever revisited."
        ),
    ))

    reg(FeatureSpec(
        name="iv_rank",
        requires="chain_snapshots",
        lookback=0,
        derivation="percentile rank of ATM implied volatility over 1 year",
        rationale=(
            "not built, and registered anyway: it is the concrete case seam 6 "
            "exists for. Alpaca serves no chain snapshot, so selecting this "
            "feature must fail at config time with a vendor explanation rather "
            "than four hours into a run"
        ),
        status="dropped",
        dropped_reason=(
            "requires chain_snapshots, which no provider available to this "
            "project serves (Alpaca raises NotSupported). A post-course "
            "vendor with a chain snapshot makes this a registration change, "
            "not a pipeline change - Outline §7B seam 6"
        ),
        asset_classes=frozenset({"option"}),
    ))


_register_all()
