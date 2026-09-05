"""Feature layer tests. Two of these are load-bearing; the rest support them.

`test_features_are_shift_forward_invariant` is the leakage test PRD §5.2's
acceptance criteria require, as a property rather than a spot check. Computing
the whole series and computing a prefix must agree exactly on the overlap. Any
whole-sample statistic - a mean, a standard deviation, a min-max scaler, a
centred window, a `reversed()` - breaks it immediately, and nothing else in the
suite would notice. Floats are compared exactly and deliberately: a causal
implementation performs identical operations in identical order, so a tolerance
here would hide the very reordering the test exists to catch.

`test_active_features_ignore_volume_entirely` is the volume drop as a property
rather than a naming convention. Multiplying every bar's volume, trade count
and VWAP by an arbitrary factor must not move a single feature value. A feature
could be named innocently and still read `bar.volume`; this catches that, and
it is the check that would fail if the IEX transfer problem crept back in
through a helper.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from project_beta.data.provider import Bar
from project_beta.features import REGISTRY, FeatureSpec, FeatureUnavailable
from project_beta.features.registry import FeatureRegistry

ET = ZoneInfo("America/New_York")

# A full trading week with no holiday and no early close.
WEEK = [date(2026, 8, 24) + timedelta(days=n) for n in range(5)]
# Thanksgiving 2026 is 26 November; the 27th is the 13:00 early close.
EARLY_CLOSE_DAY = date(2026, 11, 27)


# ------------------------------------------------------------------ fixtures


def _session_bars(day: date, price: float, rng: random.Random) -> tuple[list[Bar], float]:
    """One regular session of 5-minute bars on a seeded random walk."""
    bars: list[Bar] = []
    cursor = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET)
    stop = datetime(day.year, day.month, day.day, 16, 0, tzinfo=ET)
    while cursor < stop:
        step = rng.gauss(0.0, 0.15)
        open_, close = price, price + step
        high = max(open_, close) + abs(rng.gauss(0.0, 0.08))
        low = min(open_, close) - abs(rng.gauss(0.0, 0.08))
        bars.append(
            Bar(
                timestamp=cursor.astimezone(timezone.utc),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=rng.uniform(500.0, 5000.0),
                trade_count=rng.randint(5, 200),
                vwap=(high + low + close) / 3,
            )
        )
        price = close
        cursor += timedelta(minutes=5)
    return bars, price


def _bars(days: list[date] | None = None, seed: int = 7) -> list[Bar]:
    rng = random.Random(seed)
    price = 550.0
    out: list[Bar] = []
    for day in days or WEEK:
        session, price = _session_bars(day, price, rng)
        out.extend(session)
    return out


@pytest.fixture(scope="module")
def bars() -> list[Bar]:
    return _bars()


# --------------------------------------------------------------- the leakage test


@pytest.mark.parametrize("k", [2, 27, 28, 29, 78, 156, 200, 300])
def test_features_are_shift_forward_invariant(bars: list[Bar], k: int) -> None:
    """A feature at bar t must not change when bars after t arrive.

    This is Outline §11's leakage rule in executable form. It is a property
    test, not an example: it holds for every feature and every prefix length,
    including the awkward lengths where a Wilder seed window is exactly full.
    """
    full = REGISTRY.compute(bars)
    prefix = REGISTRY.compute(bars[:k])
    for name in REGISTRY.names():
        assert prefix.columns[name] == full.columns[name][:k], (
            f"{name} changed retroactively when later bars arrived: "
            f"the value at some bar before {k} depends on data after it"
        )


def test_active_features_ignore_volume_entirely(bars: list[Bar]) -> None:
    """The volume drop, verified by construction rather than by naming.

    Feed-transfer verdict 2026-09-02. SIP and IEX differ by roughly 30x in
    volume magnitude and by composition; a feature that reads volume trains on
    one distribution and infers on another. Scaling volume, trade count and
    VWAP by a large factor must leave every feature value untouched.
    """
    scaled = [
        Bar(
            timestamp=b.timestamp,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume * 31.6,
            trade_count=(b.trade_count or 0) * 29,
            vwap=(b.vwap or 0.0) * 1.5,
        )
        for b in bars
    ]
    assert REGISTRY.compute(scaled).columns == REGISTRY.compute(bars).columns


# ------------------------------------------------------------ the volume record


def test_no_active_feature_is_volume_derived() -> None:
    offenders = [s.name for s in REGISTRY.active() if s.volume_derived]
    assert not offenders, (
        "the feed-transfer experiment dropped volume-derived features "
        f"(2026-09-02); these are active again: {offenders}. Reinstating one "
        "requires a decision-log entry, not an edit here."
    )


def test_dropped_volume_features_are_recorded_rather_than_deleted() -> None:
    """The finding is the artifact. Deleting the features loses it."""
    dropped = {s.name: s for s in REGISTRY.dropped()}
    for name in ("vol_tod", "vol_ratio", "vol_z", "trades_ratio"):
        assert name in dropped, f"{name} must remain on record as dropped"
        assert "2026-09-02" in (dropped[name].dropped_reason or "")

    assert "vwap_dist" in dropped, (
        "VWAP distance is volume-weighted and falls under the same rule; "
        "leaving it unregistered makes the decision invisible"
    )


def test_selecting_a_dropped_feature_is_refused() -> None:
    with pytest.raises(FeatureUnavailable, match="dropped"):
        REGISTRY.validate_for("alpaca", names=["ret_1", "vol_z"])


# ---------------------------------------------------- seam 6: declared requirements


def test_chain_snapshot_feature_is_refused_at_config_time() -> None:
    """PRD §3B.6 acceptance criterion, exactly as written.

    The point is *when* this fails. Alpaca raises NotSupported for a chain
    snapshot at call time; discovering that four hours into a fold is the
    failure the registry exists to move forward.
    """
    registry = FeatureRegistry()
    registry.register(
        FeatureSpec(
            name="iv_skew",
            requires="chain_snapshots",
            lookback=0,
            derivation="25-delta put IV minus 25-delta call IV",
            rationale="options-native feature; unavailable on this vendor",
            fn=lambda bars: [None] * len(bars),
        )
    )
    with pytest.raises(FeatureUnavailable, match="chain_snapshots"):
        registry.validate_for("alpaca", asset_class="option")


def test_quote_feature_is_refused_against_alpaca() -> None:
    registry = FeatureRegistry()
    registry.register(
        FeatureSpec(
            name="spread_bps",
            requires="quotes",
            lookback=0,
            derivation="(ask - bid) / mid * 10000",
            rationale="needs historical quotes, which Alpaca does not serve",
            fn=lambda bars: [None] * len(bars),
        )
    )
    with pytest.raises(FeatureUnavailable, match="quotes"):
        registry.validate_for("alpaca")


def test_unknown_provider_is_refused_rather_than_assumed_capable() -> None:
    with pytest.raises(FeatureUnavailable, match="unknown provider"):
        REGISTRY.validate_for("polygon")


def test_tod_frac_is_not_computed_for_crypto() -> None:
    """A 24/7 tape has no session, so 'fraction of session elapsed' has no
    referent. Excluding it is different from it being missing."""
    assert "tod_frac" in REGISTRY.names("equity")
    assert "tod_frac" not in REGISTRY.names("crypto")
    with pytest.raises(FeatureUnavailable, match="asset_class"):
        REGISTRY.validate_for("alpaca", asset_class="crypto", names=["tod_frac"])


# ------------------------------------------------------------------ warmup


def test_warmup_rows_are_never_ready(bars: list[Bar]) -> None:
    frame = REGISTRY.compute(bars)
    assert frame.warmup > 0
    for i in range(frame.warmup):
        assert not frame.is_ready(i)
        assert frame.row(i) is None
    assert frame.is_ready(len(bars) - 1), "features must be defined after warmup"


def test_ready_rows_carry_every_active_column(bars: list[Bar]) -> None:
    frame = REGISTRY.compute(bars)
    row = frame.row(frame.ready_indices()[0])
    assert row is not None
    assert set(row) == set(REGISTRY.names())


def test_matrix_keeps_the_bar_index_each_row_came_from(bars: list[Bar]) -> None:
    """Labels, folds and decision records are all keyed on the bar. A matrix
    that has forgotten its indices cannot be joined back without guessing."""
    frame = REGISTRY.compute(bars)
    rows, idx = frame.matrix()
    assert len(rows) == len(idx) == len(frame.ready_indices())
    assert all(len(r) == len(REGISTRY.names()) for r in rows)
    first = frame.row(idx[0])
    assert first is not None
    assert rows[0] == [first[n] for n in REGISTRY.names()]


def test_snapshot_id_identifies_the_bar(bars: list[Bar]) -> None:
    frame = REGISTRY.compute(bars)
    assert frame.snapshot_id(200).startswith("feat_")
    assert frame.snapshot_id(200) != frame.snapshot_id(201)


# ------------------------------------------------------- individual behaviour


def test_adx_stays_within_its_defined_range(bars: list[Bar]) -> None:
    values = [v for v in REGISTRY.compute(bars).columns["adx_14"] if v is not None]
    assert values, "ADX must be defined somewhere in a five-day series"
    assert all(0.0 <= v <= 100.0 for v in values)


def test_dist_high_is_positive_only_on_a_genuine_breakout() -> None:
    """The window excludes the current bar, so a close above it is a real break
    of the trailing range rather than a bar that closed at its own high.

    An earlier version measured against a window containing the current bar.
    The close is bounded above by that bar's own high, so the feature could
    essentially never reach zero and the strategy fired on nothing. The sign
    convention is load-bearing: inverted, it becomes a mean-reversion rule
    wearing a momentum name.
    """
    rng = random.Random(3)
    rising = []
    cursor = datetime(2026, 8, 24, 9, 30, tzinfo=ET)
    for n in range(120):
        price = 100.0 + n
        rising.append(
            Bar(
                timestamp=(cursor + timedelta(minutes=5 * n)).astimezone(timezone.utc),
                open=price,
                high=price,
                low=price - 0.5,
                close=price,
                volume=rng.uniform(1.0, 2.0),
            )
        )
    breaking = REGISTRY.compute(rising).columns["dist_high_78"]
    assert breaking[-1] is not None and breaking[-1] > 0.0

    # A flat tape never breaks its own range: the value sits at zero, never above.
    flat = [
        Bar(
            timestamp=(
                datetime(2026, 8, 24, 9, 30, tzinfo=ET) + timedelta(minutes=5 * n)
            ).astimezone(timezone.utc),
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=1000.0,
        )
        for n in range(120)
    ]
    values = [v for v in REGISTRY.compute(flat).columns["dist_high_78"] if v is not None]
    assert values and all(v == 0.0 for v in values)


def test_tod_frac_spans_the_full_range_on_an_early_close() -> None:
    """Measured against the day's own close, so a 13:00 session still runs
    0 to 1. Against a fixed 16:00 it would top out near 0.54 and teach the
    model that those days end at lunchtime."""
    bars: list[Bar] = []
    cursor = datetime(2026, 11, 27, 9, 30, tzinfo=ET)
    stop = datetime(2026, 11, 27, 13, 0, tzinfo=ET)
    price = 100.0
    while cursor < stop:
        bars.append(
            Bar(
                timestamp=cursor.astimezone(timezone.utc),
                open=price,
                high=price + 0.2,
                low=price - 0.2,
                close=price,
                volume=1000.0,
            )
        )
        cursor += timedelta(minutes=5)
    values = [
        v for v in REGISTRY.compute(bars, names=["tod_frac"]).columns["tod_frac"]
        if v is not None
    ]
    assert len(values) == 42, "a 13:00 close is 42 five-minute bars"
    assert values[0] == 0.0
    assert values[-1] == pytest.approx(41 / 42, abs=1e-9)


# ---------------------------------------------------------------- reporting


def test_reference_table_lists_every_feature_with_its_derivation() -> None:
    """PRD §5.2 requires a complete feature reference table with derivation
    tags. Generating it from the registry is what keeps it true."""
    table = REGISTRY.reference_table()
    for spec in REGISTRY.all():
        assert f"`{spec.name}`" in table
        assert spec.derivation in table
    assert "**dropped**" in table


def test_every_registered_feature_states_why_it_exists() -> None:
    for spec in REGISTRY.all():
        assert spec.rationale, f"{spec.name} has no rationale"
        assert spec.derivation, f"{spec.name} has no derivation"


def test_registry_refuses_a_duplicate_registration() -> None:
    registry = FeatureRegistry()
    spec = FeatureSpec(
        name="x",
        requires="bars",
        lookback=0,
        derivation="x",
        rationale="x",
        fn=lambda bars: [None] * len(bars),
    )
    registry.register(spec)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)


def test_a_dropped_feature_must_record_its_reason() -> None:
    with pytest.raises(ValueError, match="must record why"):
        FeatureSpec(
            name="mystery",
            requires="bars",
            lookback=0,
            derivation="?",
            rationale="?",
            status="dropped",
        )
