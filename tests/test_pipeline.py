"""Ingestion and validation tests.

The acceptance criteria in PRD §5.1 are the spine of this file, and three of
them are load-bearing enough to say why here:

`test_rth_filter_keeps_exactly_78_bars_of_a_full_sip_session` is the one that
proves the contamination guard works. SIP serves 192 bars a day and 60% of them
are outside the regular session; if this test ever fails open, every feature,
every backtest and every published number downstream is quietly computed on
overnight prices.

`test_sparse_session_is_flagged_but_never_filled` is the no-forward-fill rule
in executable form. A pipeline that repairs a gap produces a price nobody could
have traded at, and the fill simulator will happily trade on it.

`test_window_edge_days_are_excluded_from_coverage_judgement` encodes a mistake
this project actually made: a 9-bar session at a window boundary was read as an
outage, and the correction is the rule rather than a note.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from project_beta.config import DataConfig, RiskConfig, RunConfig
from project_beta.data.pipeline import (
    COVERAGE_FLOOR,
    IngestResult,
    ValidationError,
    coverage,
    dataset_hash,
    filter_session,
    find_duplicates,
    in_regular_session,
    ingest,
    store_path,
    timeframe_minutes,
    validate_bars,
)
from project_beta.data.provider import Bar, NotSupported, OptionContract, Quote

ET = ZoneInfo("America/New_York")

# A quiet week with no holiday and no early close: Mon 24 - Fri 28 August 2026.
WEEK_START = date(2026, 8, 24)
WEEK_END = date(2026, 8, 28)


# ------------------------------------------------------------------ helpers


def _bar(ts: datetime, price: float = 100.0, volume: float = 1000.0) -> Bar:
    return Bar(
        timestamp=ts.astimezone(timezone.utc),
        open=price,
        high=price + 0.5,
        low=price - 0.5,
        close=price + 0.1,
        volume=volume,
        trade_count=10,
        vwap=price,
    )


def _day_of_bars(
    day: date,
    *,
    start_hhmm: tuple[int, int] = (4, 0),
    end_hhmm: tuple[int, int] = (20, 0),
    minutes: int = 5,
    skip: set[tuple[int, int]] | None = None,
) -> list[Bar]:
    """Bars stamped at interval starts in market time, as Alpaca serves them.

    Defaults to the full 04:00-20:00 SIP tape so tests can measure what the
    session filter removes.
    """
    skip = skip or set()
    out: list[Bar] = []
    cursor = datetime(day.year, day.month, day.day, *start_hhmm, tzinfo=ET)
    stop = datetime(day.year, day.month, day.day, *end_hhmm, tzinfo=ET)
    while cursor < stop:
        if (cursor.hour, cursor.minute) not in skip:
            out.append(_bar(cursor))
        cursor += timedelta(minutes=minutes)
    return out


def _rth_day(day: date, *, skip: set[tuple[int, int]] | None = None) -> list[Bar]:
    return _day_of_bars(day, start_hhmm=(9, 30), end_hhmm=(16, 0), skip=skip)


def _config(
    *,
    start: date = WEEK_START,
    end: date = WEEK_END,
    asset_class: str = "equity",
    feed: str | None = "sip",
    session: str = "rth_only",
    symbol: str = "SPY",
    dataset_hash_pin: str | None = None,
) -> RunConfig:
    return RunConfig(
        run_id="test_run",
        mode="backtest",
        data=DataConfig(
            symbol=symbol,
            timeframe="5Min",
            start=start,
            end=end,
            asset_class=asset_class,
            feed=feed,
            session=session,
            dataset_hash=dataset_hash_pin,
        ),
        risk=RiskConfig(max_drawdown=0.15, daily_loss_limit=500.0, max_position=10_000.0),
        walk_forward=None,
    )


class _FakeProvider:
    """Serves a fixed list of bars, unfiltered — the provider contract (§3B.1).

    Deliberately raises NotSupported for quotes and chains rather than
    returning empty lists, so a test that leans on the pipeline degrading
    quietly would fail here instead of passing by accident.
    """

    name = "fake"

    def __init__(self, bars: list[Bar]) -> None:
        self.bars = bars
        self.calls: list[dict] = []

    def get_bars(self, symbol, timeframe, start, end, *, asset_class="equity", feed=None):
        self.calls.append(
            {"symbol": symbol, "timeframe": timeframe, "start": start,
             "end": end, "asset_class": asset_class, "feed": feed}
        )
        return list(self.bars)

    def list_contracts(self, underlying, *, as_of, expiry_start=None,
                       expiry_end=None, status="inactive") -> list[OptionContract]:
        return []

    def get_quotes(self, symbol, start, end, *, asset_class="equity") -> list[Quote]:
        raise NotSupported("fake provider serves no quotes")

    def get_chain_snapshot(self, underlying, as_of) -> dict:
        raise NotSupported("fake provider serves no chain snapshots")

    def authenticate(self) -> None:
        return None


# ------------------------------------------------------------ timeframe


@pytest.mark.parametrize(
    "text,minutes", [("1Min", 1), ("5Min", 5), ("15Min", 15), ("1Hour", 60), ("1Day", 1440)]
)
def test_timeframe_parsing(text: str, minutes: int) -> None:
    assert timeframe_minutes(text) == minutes


def test_unknown_timeframe_raises() -> None:
    with pytest.raises(ValueError):
        timeframe_minutes("5 minutes")


# --------------------------------------------------------- session filter


def test_rth_filter_keeps_exactly_78_bars_of_a_full_sip_session() -> None:
    """PRD §5.1 AC. 192 bars in, 78 out, and the 78 are the right ones.

    Asserting the count alone would pass on an off-by-one window that keeps
    16:00 and drops 09:30, so the boundaries are checked too.
    """
    raw = _day_of_bars(WEEK_END)
    assert len(raw) == 192, "the fixture must be a full SIP tape, 04:00-20:00"

    kept = filter_session(raw, "rth_only")
    assert len(kept) == 78

    first = kept[0].timestamp.astimezone(ET)
    last = kept[-1].timestamp.astimezone(ET)
    assert (first.hour, first.minute) == (9, 30)
    assert (last.hour, last.minute) == (15, 55), "16:00 belongs to the after-hours tape"


def test_session_boundaries_are_half_open() -> None:
    day = WEEK_END
    assert in_regular_session(datetime(2026, 8, 28, 9, 30, tzinfo=ET))
    assert in_regular_session(datetime(2026, 8, 28, 15, 55, tzinfo=ET))
    assert not in_regular_session(datetime(2026, 8, 28, 9, 25, tzinfo=ET))
    assert not in_regular_session(datetime(2026, 8, 28, 16, 0, tzinfo=ET))
    assert not in_regular_session(datetime(2026, 8, 29, 10, 0, tzinfo=ET)), "Saturday"
    assert day.weekday() == 4


def test_filter_respects_an_early_close() -> None:
    """13:00 on the day after Thanksgiving. 42 bars is the whole session."""
    kept = filter_session(_day_of_bars(date(2026, 11, 27)), "rth_only")
    assert len(kept) == 42
    last = kept[-1].timestamp.astimezone(ET)
    assert (last.hour, last.minute) == (12, 55)


def test_naive_timestamps_are_read_as_utc() -> None:
    """Every Alpaca endpoint returns UTC. Guessing local time would move the
    session boundary by the host's offset and silently change what is kept."""
    naive = _bar(datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc))
    naive = Bar(**{**naive.__dict__, "timestamp": datetime(2026, 8, 28, 14, 0)})
    assert in_regular_session(naive.timestamp)  # 10:00 ET
    off_hours = Bar(**{**naive.__dict__, "timestamp": datetime(2026, 8, 28, 8, 0)})
    assert not in_regular_session(off_hours.timestamp)  # 04:00 ET


def test_dst_boundary_is_handled_in_market_time() -> None:
    """13:30 UTC is 09:30 ET in winter and 08:30 ET in summer.

    A filter written against a fixed UTC window would drop the first hour of
    every summer session, or admit an hour of pre-market every winter one.
    """
    winter_open = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)   # 09:30 EST
    summer_open = datetime(2026, 7, 6, 13, 30, tzinfo=timezone.utc)   # 09:30 EDT
    assert in_regular_session(winter_open)
    assert in_regular_session(summer_open)
    assert not in_regular_session(datetime(2026, 7, 6, 12, 30, tzinfo=timezone.utc))


def test_crypto_continuous_session_filters_nothing() -> None:
    """BTC/USD trades 24/7; an RTH window there would discard most of the data."""
    raw = _day_of_bars(date(2026, 8, 29))  # a Saturday
    assert filter_session(raw, "continuous") == raw


def test_extended_session_is_refused_rather_than_aliased() -> None:
    """Not silently equivalent to 'continuous'. Enabling it is a decision."""
    with pytest.raises(ValueError, match="not implemented"):
        filter_session(_day_of_bars(WEEK_END), "extended")


# ------------------------------------------------------------ no repair


def test_sparse_session_is_flagged_but_never_filled() -> None:
    """The no-trade-interval rule (Outline §8, PRD §5.9).

    An IEX day of 74 bars against a 78-bar maximum is normal — the feed carries
    ~3% of consolidated volume. The pipeline reports the shortfall and returns
    74 bars. Returning 78 would mean four prices that no trade ever set.
    """
    skip = {(10, 0), (10, 5), (13, 30), (14, 45)}
    raw = _rth_day(WEEK_END, skip=skip)
    kept = filter_session(raw, "rth_only")
    assert len(kept) == 78 - len(skip) == 74
    stamps = {(b.timestamp.astimezone(ET).hour, b.timestamp.astimezone(ET).minute) for b in kept}
    assert stamps.isdisjoint(skip), "a skipped interval must stay absent"


def test_a_74_bar_iex_day_is_within_the_observed_range_and_not_flagged() -> None:
    """74-87 bars/day is the measured IEX range; 74/78 is 94.9%, above the floor.

    Measured on an interior day: a day at the window edge is excluded from the
    statistics entirely, so it could not demonstrate anything about the floor.
    """
    config = _config(feed="iex")
    bars = _rth_day(date(2026, 8, 26), skip={(10, 0), (10, 5), (13, 30), (14, 45)})
    report = validate_bars(bars, config=config, raw_count=len(bars))
    assert report.flagged_days == []
    assert report.min_coverage == pytest.approx(74 / 78)


# ------------------------------------------------------------- coverage


def test_coverage_flags_below_the_floor_without_rejecting() -> None:
    """Flag for review, never auto-reject (Outline §9). A 50-bar day is 64%."""
    bars = sorted(
        _rth_day(date(2026, 8, 25))[:50] + _rth_day(date(2026, 8, 26)),
        key=lambda b: b.timestamp,
    )
    report = validate_bars(bars, config=_config(), raw_count=len(bars))
    flagged = {c.day for c in report.flagged_days}
    assert date(2026, 8, 25) in flagged
    assert date(2026, 8, 26) not in flagged
    assert report.min_coverage < COVERAGE_FLOOR
    # The point of the rule: nothing raised, and every bar is still there.
    assert report.bars_in_session == len(bars)


def test_window_edge_days_are_excluded_from_coverage_judgement() -> None:
    """A 9-bar session at a window boundary is a boundary artifact, not an outage.

    This is the correction from 2026-09-01, and the reason the fetch window's
    first and last days are excluded from the statistics rather than explained
    away in prose each time they appear.
    """
    bars = sorted(
        _rth_day(WEEK_START)[:9] + _rth_day(date(2026, 8, 25)),
        key=lambda b: b.timestamp,
    )
    report = validate_bars(bars, config=_config(), raw_count=len(bars))
    assert report.flagged_days == [], "the edge day must not be flagged"
    assert report.edge_days_excluded == 1
    assert report.min_coverage == pytest.approx(1.0), (
        "an excluded day must not enter the statistics either"
    )


def test_no_assertion_of_exactly_78_bars() -> None:
    """The v2.1 criterion that was correct for SIP and wrong for IEX.

    Two full weeks where no day is complete and nothing raises: shortfall is a
    property of the feed, not an error condition.
    """
    bars: list[Bar] = []
    for offset in range(1, 4):  # Tue-Thu, interior days only
        bars += _rth_day(WEEK_START + timedelta(days=offset), skip={(11, 0), (11, 5)})
    report = validate_bars(sorted(bars, key=lambda b: b.timestamp),
                           config=_config(), raw_count=len(bars))
    assert report.flagged_days == []
    assert report.median_coverage == pytest.approx(76 / 78)


def test_a_missing_interior_session_is_reported() -> None:
    """A full-day outage has no bars at all, so nothing that iterates over the
    data can see it. It only appears against the calendar."""
    bars = sorted(
        _rth_day(date(2026, 8, 25)) + _rth_day(date(2026, 8, 27)),
        key=lambda b: b.timestamp,
    )
    report = validate_bars(bars, config=_config(), raw_count=len(bars))
    assert report.missing_sessions == [date(2026, 8, 26)]
    assert not report.is_clean


def test_a_missing_edge_session_is_not_reported() -> None:
    """The window's own boundaries are not evidence of an outage."""
    bars = sorted(
        _rth_day(date(2026, 8, 25)) + _rth_day(date(2026, 8, 26))
        + _rth_day(date(2026, 8, 27)),
        key=lambda b: b.timestamp,
    )
    report = validate_bars(bars, config=_config(), raw_count=len(bars))
    assert report.missing_sessions == []


def test_a_session_the_calendar_did_not_expect_is_surfaced() -> None:
    """Either a closure the calendar does not know about, or a calendar bug.

    Both need a human, and neither may cause bars to be dropped: the calendar
    is not authoritative over the data.
    """
    bars = sorted(
        _rth_day(date(2026, 8, 25)) + _rth_day(date(2026, 8, 29)),  # a Saturday
        key=lambda b: b.timestamp,
    )
    kept = filter_session(bars, "rth_only")
    assert len(kept) == 78, "the Saturday bars are filtered, not reported as a session"

    # Bypassing the filter, as a continuous-session run would: the day is still
    # visible to the coverage pass and surfaces rather than being dropped.
    report = validate_bars(bars, config=_config(), raw_count=len(bars))
    assert date(2026, 8, 29) in report.unexpected_sessions


def test_crypto_runs_produce_no_session_statistics() -> None:
    """There is no session to be complete or incomplete about."""
    config = _config(asset_class="crypto", feed=None, session="continuous",
                     symbol="BTC/USD", start=date(2026, 8, 24), end=date(2026, 8, 28))
    bars = _day_of_bars(date(2026, 8, 29), start_hhmm=(0, 0), end_hhmm=(23, 55))
    report = validate_bars(bars, config=config, raw_count=len(bars))
    assert coverage(bars, timeframe="5Min", requested_start=config.data.start,
                    requested_end=config.data.end, session="continuous") == []
    assert report.flagged_days == []
    assert report.missing_sessions == []
    assert report.sessions_expected == 0


def test_misaligned_timestamps_are_counted() -> None:
    """A 5-minute bar stamped 09:32 is from a different grid, not a late bar."""
    bars = _rth_day(WEEK_END)
    bars.append(_bar(datetime(2026, 8, 28, 9, 32, tzinfo=ET)))
    bars.sort(key=lambda b: b.timestamp)
    report = validate_bars(bars, config=_config(), raw_count=len(bars))
    assert report.misaligned_timestamps == 1


# ----------------------------------------------------------- hard failures


def test_duplicate_timestamps_raise() -> None:
    """No duplicate has ever been observed, a duplicate double-weights itself in
    every feature computed from it, and there is no honest way to pick one."""
    bars = _rth_day(WEEK_END)
    bars.append(bars[10])
    bars.sort(key=lambda b: b.timestamp)
    assert len(find_duplicates(bars)) == 1
    with pytest.raises(ValidationError, match="duplicate"):
        validate_bars(bars, config=_config(), raw_count=len(bars))


def test_unsorted_bars_raise() -> None:
    """The provider contract is oldest-first and every window downstream assumes it."""
    bars = _rth_day(WEEK_END)
    bars[0], bars[5] = bars[5], bars[0]
    with pytest.raises(ValidationError, match="ascending"):
        validate_bars(bars, config=_config(), raw_count=len(bars))


def test_a_pinned_dataset_hash_that_does_not_match_raises() -> None:
    """The reproduction check working. The remedy is never to update the pin."""
    bars = _rth_day(date(2026, 8, 25))
    config = _config(dataset_hash_pin="sha256:" + "0" * 64)
    with pytest.raises(ValidationError, match="dataset_hash mismatch"):
        validate_bars(bars, config=config, raw_count=len(bars))


def test_a_pinned_dataset_hash_that_matches_passes() -> None:
    bars = _rth_day(date(2026, 8, 25))
    digest = dataset_hash(bars, symbol="SPY", timeframe="5Min",
                          asset_class="equity", feed="sip", session="rth_only")
    report = validate_bars(bars, config=_config(dataset_hash_pin=digest),
                           raw_count=len(bars))
    assert report.dataset_hash == digest


# ------------------------------------------------------------ dataset hash


def test_identical_inputs_produce_an_identical_hash() -> None:
    """PRD §5.1 AC, and the whole basis of reproduction without redistribution."""
    a = _rth_day(date(2026, 8, 25))
    b = _rth_day(date(2026, 8, 25))
    kw = {"symbol": "SPY", "timeframe": "5Min", "asset_class": "equity",
          "feed": "sip", "session": "rth_only"}
    assert dataset_hash(a, **kw) == dataset_hash(b, **kw)


def test_the_hash_distinguishes_the_feed() -> None:
    """The same window on SIP and on IEX is two datasets, not one.

    A hash blind to this would let a feed mismatch — the project's largest
    open data risk (§5.2) — pass a reproduction check unnoticed.
    """
    bars = _rth_day(date(2026, 8, 25))
    kw = {"symbol": "SPY", "timeframe": "5Min", "asset_class": "equity",
          "session": "rth_only"}
    assert dataset_hash(bars, feed="sip", **kw) != dataset_hash(bars, feed="iex", **kw)


def test_the_hash_changes_when_a_single_price_changes() -> None:
    bars = _rth_day(date(2026, 8, 25))
    kw = {"symbol": "SPY", "timeframe": "5Min", "asset_class": "equity",
          "feed": "sip", "session": "rth_only"}
    before = dataset_hash(bars, **kw)
    bars[7] = Bar(**{**bars[7].__dict__, "close": bars[7].close + 0.01})
    assert dataset_hash(bars, **kw) != before


def test_the_hash_ignores_bar_metadata_that_is_not_price_or_volume() -> None:
    """trade_count and vwap are vendor conveniences, absent on some endpoints.

    Hashing them would make a dataset's identity depend on which endpoint
    served it rather than on what the market did.
    """
    bars = _rth_day(date(2026, 8, 25))
    kw = {"symbol": "SPY", "timeframe": "5Min", "asset_class": "equity",
          "feed": "sip", "session": "rth_only"}
    before = dataset_hash(bars, **kw)
    stripped = [Bar(**{**b.__dict__, "trade_count": None, "vwap": None}) for b in bars]
    assert dataset_hash(stripped, **kw) == before


# ----------------------------------------------------------------- ingest


def test_ingest_filters_then_validates() -> None:
    """The order matters: coverage measured before filtering would score the
    session against bars that are about to be discarded."""
    raw: list[Bar] = []
    for offset in range(5):
        raw += _day_of_bars(WEEK_START + timedelta(days=offset))
    provider = _FakeProvider(sorted(raw, key=lambda b: b.timestamp))

    result = ingest(_config(), provider, store=False)

    assert isinstance(result, IngestResult)
    assert result.report.bars_returned == 5 * 192
    assert result.report.bars_in_session == 5 * 78
    assert result.report.bars_outside_session == 5 * (192 - 78)
    assert result.report.flagged_days == []
    assert result.report.missing_sessions == []
    assert result.report.dataset_hash.startswith("sha256:")
    assert result.path is None


def test_ingest_passes_the_asset_class_and_feed_to_the_provider() -> None:
    """A provider that guessed the endpoint from the symbol would work for SPY
    and silently fetch the wrong API for BTC/USD."""
    provider = _FakeProvider(_rth_day(date(2026, 8, 25)))
    ingest(_config(feed="iex"), provider, store=False)
    assert provider.calls[0]["asset_class"] == "equity"
    assert provider.calls[0]["feed"] == "iex"


def test_ingest_refuses_a_config_the_account_cannot_serve() -> None:
    """SIP recent data returns 403; a paper run on SIP fails mid-session.

    Caught at ingest rather than at the first empty response.
    """
    from project_beta.config import ConfigError

    bad = RunConfig(
        run_id="paper_on_sip",
        mode="paper",
        data=DataConfig(symbol="SPY", timeframe="5Min", start=WEEK_START,
                        end=WEEK_END, feed="sip"),
        risk=RiskConfig(max_drawdown=0.15, daily_loss_limit=500.0, max_position=10_000.0),
    )
    with pytest.raises(ConfigError, match="paper"):
        ingest(bad, _FakeProvider([]), store=False)


def test_store_path_carries_the_identifying_facts() -> None:
    """A stored file must be identifiable without opening it, and a crypto pair's
    slash must not create a directory."""
    config = _config(asset_class="crypto", feed=None, session="continuous",
                     symbol="BTC/USD")
    path = store_path(config, "sha256:" + "ab" * 32)
    assert path.parent.name == "processed"
    assert "BTC-USD" in path.name and "crypto" in path.name
    assert path.name.endswith(".parquet")


# ------------------------------------------------------------- parquet io


def test_parquet_round_trip_preserves_the_dataset_hash(tmp_path) -> None:
    """Storage must not be able to change a dataset's identity.

    Skipped where pyarrow is absent: the validation logic above is pure Python
    on purpose, so it stays testable in an environment without it.
    """
    pytest.importorskip("pyarrow")
    from project_beta.data.pipeline import read_parquet, write_parquet

    bars = _rth_day(date(2026, 8, 25))
    kw = {"symbol": "SPY", "timeframe": "5Min", "asset_class": "equity",
          "feed": "sip", "session": "rth_only"}
    path = write_parquet(bars, tmp_path / "bars.parquet")
    assert dataset_hash(read_parquet(path), **kw) == dataset_hash(bars, **kw)


def test_ingest_writes_a_validation_report_beside_the_dataset(tmp_path) -> None:
    """PRD §5.1 AC: a validation report per ingest.

    On disk rather than on the console, so "did coverage degrade since the last
    fetch" is a question that can still be asked next week.
    """
    pytest.importorskip("pyarrow")
    import json

    raw: list[Bar] = []
    for offset in range(5):
        raw += _day_of_bars(WEEK_START + timedelta(days=offset))
    provider = _FakeProvider(sorted(raw, key=lambda b: b.timestamp))

    result = ingest(_config(), provider, store=True, root=tmp_path)

    assert result.path is not None and result.path.exists()
    assert result.report_path is not None and result.report_path.exists()
    written = json.loads(result.report_path.read_text())
    assert written["dataset_hash"] == result.report.dataset_hash
    assert written["bars_in_session"] == 5 * 78
    assert written["feed"] == "sip"
