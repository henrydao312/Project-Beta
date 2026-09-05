"""Ingestion and validation - where vendor bars become a dataset we can defend.

This layer sits between `MarketDataProvider` (a pure reader, which by contract
does no filtering and no repair) and everything downstream. It is the only
place session filtering happens, the only place coverage is judged, and the
only place a `dataset_hash` is minted.

Three rules govern the code below, and each one exists because getting it wrong
is a specific, documented way to produce an inflated backtest.

**1. The session filter runs before anything else, and before any feature.**
SIP serves 192 bars a day, 04:00-20:00 ET; roughly 60% of them fall outside the
regular session. Overnight liquidity and spreads behave nothing like 09:30-16:00,
and letting those bars into a moving average is a quiet, permanent contamination
of every result computed after it (Outline §9, PRD §5.1).

**2. A missing bar is a no-trade interval, never missing data.**
Nothing here reindexes, forward-fills, interpolates or repairs. IEX carries a
median 3.16% of consolidated volume, so 5-minute intervals with no IEX trades
genuinely occur - 74-87 bars/day observed against a 78-bar maximum. Options
strikes are sparser still. A filled bar is a price that nobody could have
traded at, and a fill against it is a fill that could not have happened
(Outline §8, PRD §5.9).

**3. Coverage is flagged, never auto-rejected.**
The Week 1 probe first reported "42/42 full sessions, zero gaps"; a second
sample of 42 sessions showed 40/42, and the 9-bar session that looked like an
outage turned out to be a window-edge artifact. So: no assertion of exactly 78
bars, days below 90% flagged for a human, and the first and last day of the
fetch window excluded from the statistics entirely (Outline §9, PRD §5.1).

Duplicates are the one exception. No duplicate timestamp has ever been observed
on any feed, a duplicate would silently double-weight a bar in every feature
computed from it, and there is no honest way to choose between two rows
claiming the same interval. That raises.

Run directly to ingest and store a dataset from a config file:

    python -m project_beta.data.pipeline configs/example_backtest.yaml
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from project_beta.config import RunConfig, load_run_config
from project_beta.data.calendar import (
    REGULAR_OPEN,
    expected_bars,
    is_trading_day,
    session_close,
    trading_days,
)
from project_beta.data.provider import Bar, MarketDataProvider

MARKET_TZ = ZoneInfo("America/New_York")

# Below this fraction of a session's expected bars, a day is flagged for review.
# Not rejected: see rule 3 above. 0.90 is the figure in Outline §9 and PRD §5.1.
COVERAGE_FLOOR = 0.90

_TIMEFRAME_RE = re.compile(r"^(\d+)\s*(Min|Hour|Day)$", re.IGNORECASE)
_TIMEFRAME_MINUTES = {"min": 1, "hour": 60, "day": 24 * 60}


class ValidationError(RuntimeError):
    """The ingested bars have a defect that cannot be reported and worked around.

    Reserved for defects that would corrupt every downstream number rather than
    degrade one day's coverage: duplicate timestamps, unsorted output, a
    dataset_hash that does not match the one the config pinned.
    """


def timeframe_minutes(timeframe: str) -> int:
    """'5Min' -> 5. The bar width, in minutes, as the vendor names it."""
    match = _TIMEFRAME_RE.match(timeframe.strip())
    if not match:
        raise ValueError(
            f"unrecognised timeframe {timeframe!r}; expected forms like "
            "'1Min', '5Min', '15Min', '1Hour', '1Day'"
        )
    count, unit = match.groups()
    return int(count) * _TIMEFRAME_MINUTES[unit.lower()]


# ------------------------------------------------------------ session filter


def to_market_time(ts: datetime) -> datetime:
    """Interpret a bar timestamp in market time.

    A naive timestamp is treated as UTC, which is what every Alpaca endpoint
    returns. Guessing local time here would shift every bar by the sandbox's
    offset and quietly move the session boundary.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(MARKET_TZ)


# Retained so the private name keeps working; the public one is what the
# feature layer imports, since time of day is a feature input and not only a
# filtering concern.
_to_market_time = to_market_time


def in_regular_session(ts: datetime) -> bool:
    """True if a bar *beginning* at this instant lies inside the regular session.

    Half-open [09:30, close): a 5-minute bar stamped 15:55 is the session's
    last, and one stamped 16:00 belongs to the after-hours tape. Alpaca stamps
    bars with the interval's start, so the comparison is on the start.

    Early closes come from the calendar, not from a constant - measuring a
    13:00 close against 16:00 would drop nothing but would make the day look
    46% covered, and nine such days a year is enough noise to hide a real gap.
    """
    local = to_market_time(ts)
    day = local.date()
    if not is_trading_day(day):
        return False
    return REGULAR_OPEN <= local.time() < session_close(day)


def filter_session(bars: Iterable[Bar], session: str) -> list[Bar]:
    """Apply the session calendar. This is the only place bars are dropped.

    'continuous' keeps everything, and is required for crypto: BTC/USD trades
    24/7, and imposing an RTH window there would discard most of the data and
    invent a session that does not exist.
    """
    if session == "continuous":
        return list(bars)
    if session not in ("rth_only", "extended"):
        raise ValueError(f"unknown session {session!r}")
    if session == "extended":
        # Declared in the config vocabulary but not implemented, and deliberately
        # not silently equivalent to 'continuous': an extended-hours window has
        # its own boundaries (04:00-20:00 ET) and its own justification, and no
        # run in this project has either. config.validate() already refuses it.
        raise ValueError(
            "session='extended' is not implemented. Extended-hours bars are "
            "filtered out at ingestion by decision (Outline §9); enabling them "
            "requires a decision-log entry, not a code path."
        )
    return [b for b in bars if in_regular_session(b.timestamp)]


# ------------------------------------------------------------ coverage stats


@dataclass(frozen=True)
class SessionCoverage:
    """One trading day's bar count against what a complete session would hold."""

    day: date
    observed: int
    expected: int
    is_edge: bool

    @property
    def ratio(self) -> float:
        return self.observed / self.expected if self.expected else 0.0

    @property
    def is_flagged(self) -> bool:
        """Below the floor, and not a window-edge day.

        Edge days are excluded from judgement, not just from the average: the
        9-bar session that prompted this rule was the first day of a fetch
        window, where a partial day is the expected shape of a boundary.
        """
        return not self.is_edge and self.expected > 0 and self.ratio < COVERAGE_FLOOR


@dataclass(frozen=True)
class ValidationReport:
    """What one ingest measured. Written beside every stored dataset.

    This is the "validation report per ingest" in PRD §5.1's acceptance
    criteria. It is deliberately a record of *observations*, not a verdict:
    `flagged_days` and `missing_sessions` are for a human to read, and the only
    thing that stops an ingest is in `ValidationError`.
    """

    symbol: str
    timeframe: str
    asset_class: str
    feed: str | None
    session: str
    requested_start: date
    requested_end: date
    bars_returned: int
    bars_in_session: int
    bars_outside_session: int
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    sessions_observed: int
    sessions_expected: int
    edge_days_excluded: int
    flagged_days: list[SessionCoverage] = field(default_factory=list)
    missing_sessions: list[date] = field(default_factory=list)
    unexpected_sessions: list[date] = field(default_factory=list)
    misaligned_timestamps: int = 0
    min_coverage: float | None = None
    median_coverage: float | None = None
    dataset_hash: str = ""
    generated_at: str = ""

    @property
    def is_clean(self) -> bool:
        return not (self.flagged_days or self.missing_sessions or self.unexpected_sessions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
            "feed": self.feed,
            "session": self.session,
            "requested_start": self.requested_start.isoformat(),
            "requested_end": self.requested_end.isoformat(),
            "bars_returned": self.bars_returned,
            "bars_in_session": self.bars_in_session,
            "bars_outside_session": self.bars_outside_session,
            "first_timestamp": self.first_timestamp.isoformat() if self.first_timestamp else None,
            "last_timestamp": self.last_timestamp.isoformat() if self.last_timestamp else None,
            "sessions_observed": self.sessions_observed,
            "sessions_expected": self.sessions_expected,
            "edge_days_excluded": self.edge_days_excluded,
            "flagged_days": [
                {"day": c.day.isoformat(), "observed": c.observed, "expected": c.expected,
                 "ratio": round(c.ratio, 4)}
                for c in self.flagged_days
            ],
            "missing_sessions": [d.isoformat() for d in self.missing_sessions],
            "unexpected_sessions": [d.isoformat() for d in self.unexpected_sessions],
            "misaligned_timestamps": self.misaligned_timestamps,
            "min_coverage": self.min_coverage,
            "median_coverage": self.median_coverage,
            "dataset_hash": self.dataset_hash,
            "generated_at": self.generated_at,
        }

    def summary(self) -> str:
        label = f"{self.asset_class}/{self.feed}" if self.feed else self.asset_class
        lines = [
            (
                f"{self.symbol} {self.timeframe} [{label}] "
                f"{self.requested_start} to {self.requested_end}"
            ),
            (
                f" bars: {self.bars_in_session} in session "
                f"({self.bars_outside_session} filtered out of {self.bars_returned})"
            ),
        ]
        if self.sessions_expected:
            lines.append(
                f" sessions: {self.sessions_observed}/{self.sessions_expected} present, "
                f"{self.edge_days_excluded} edge days excluded"
            )
            if self.median_coverage is not None:
                lines.append(
                    f" coverage: median {self.median_coverage:.1%}, "
                    f"min {self.min_coverage:.1%}"
                )
        if self.flagged_days:
            lines.append(
                f" ⚠ {len(self.flagged_days)} day(s) below {COVERAGE_FLOOR:.0%} "
                "coverage - review, not reject:"
            )
            for c in self.flagged_days[:10]:
                lines.append(f" {c.day} {c.observed}/{c.expected} ({c.ratio:.0%})")
            if len(self.flagged_days) > 10:
                lines.append(f" ... and {len(self.flagged_days) - 10} more")
        if self.missing_sessions:
            absent = ", ".join(d.isoformat() for d in self.missing_sessions[:5])
            more = " ..." if len(self.missing_sessions) > 5 else ""
            lines.append(
                f" ⚠ {len(self.missing_sessions)} expected session(s) absent: {absent}{more}"
            )
        if self.unexpected_sessions:
            lines.append(
                f" ⚠ {len(self.unexpected_sessions)} session(s) the calendar did not "
                "expect (a closure it does not know about, or a calendar bug): "
                + ", ".join(d.isoformat() for d in self.unexpected_sessions[:5])
            )
        if self.misaligned_timestamps:
            lines.append(
                f" ⚠ {self.misaligned_timestamps} bar(s) off the {self.timeframe} grid"
            )
        lines.append(f" dataset_hash: {self.dataset_hash}")
        return "\n".join(lines)


def find_duplicates(bars: Sequence[Bar]) -> list[datetime]:
    """Timestamps appearing more than once, oldest first."""
    counts = Counter(b.timestamp for b in bars)
    return sorted(ts for ts, n in counts.items() if n > 1)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def coverage(
    bars: Sequence[Bar],
    *,
    timeframe: str,
    requested_start: date,
    requested_end: date,
    session: str,
) -> list[SessionCoverage]:
    """Per-session bar counts, with the window's edge days marked.

    Edge days are marked rather than dropped so the report can say how many
    were excluded. Silently discarding them would make the statistics
    unauditable, which is how the "42/42, zero gaps" claim survived as long as
    it did.
    """
    if session == "continuous":
        return []
    minutes = timeframe_minutes(timeframe)
    per_day: Counter[date] = Counter(
        to_market_time(b.timestamp).date() for b in bars
    )
    return [
        SessionCoverage(
            day=day,
            observed=observed,
            expected=expected_bars(day, minutes),
            is_edge=day <= requested_start or day >= requested_end,
        )
        for day, observed in sorted(per_day.items())
    ]


def _misaligned(bars: Sequence[Bar], timeframe: str) -> int:
    """Bars that do not sit on the timeframe grid measured from the session open.

    A 5-minute bar stamped 09:32 is not a late bar, it is a bar from a
    different grid, and averaging it with the others is meaningless. Counted
    rather than raised: on a vendor that has never produced one, a count of
    zero in every report is the evidence, and a sudden non-zero is the signal.
    """
    minutes = timeframe_minutes(timeframe)
    if minutes <= 0 or minutes > 60:
        return 0
    bad = 0
    for b in bars:
        local = to_market_time(b.timestamp)
        offset = (local.hour * 60 + local.minute) - (
            REGULAR_OPEN.hour * 60 + REGULAR_OPEN.minute
        )
        if local.second or local.microsecond or offset % minutes:
            bad += 1
    return bad


# -------------------------------------------------------------- dataset hash


def dataset_hash(bars: Sequence[Bar], *, symbol: str, timeframe: str,
                 asset_class: str, feed: str | None, session: str) -> str:
    """A content fingerprint of the session-filtered bars, plus what they are.

    This is what makes reproduction verifiable without redistributing the data
    (Outline §17.7, §20.5): the repo ships a re-fetch script and this hash, and
    a reader who fetches the same window with their own credentials can prove
    they hold the same dataset.

    Hashed from the bar values, not the stored file. Parquet writers embed
    library versions and choose encodings; two byte-different files can hold
    identical data, and a hash over bytes would report a difference that does
    not exist. `repr` of a float is the shortest string that round-trips, so
    the digest is stable across platforms without inventing a rounding rule
    that would itself have to be justified.

    The header line matters as much as the rows. The same bars fetched as SIP
    and as IEX are different datasets, and a hash that could not tell them
    apart would let a feed mismatch pass a reproduction check.
    """
    digest = hashlib.sha256()
    header = f"{symbol}|{timeframe}|{asset_class}|{feed or '-'}|{session}\n"
    digest.update(header.encode())
    for b in bars:
        ts = b.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        row = (
            f"{ts.astimezone(timezone.utc).isoformat()}|{b.open!r}|{b.high!r}|"
            f"{b.low!r}|{b.close!r}|{b.volume!r}\n"
        )
        digest.update(row.encode())
    return f"sha256:{digest.hexdigest()}"


# -------------------------------------------------------------------- store


def bars_to_rows(bars: Iterable[Bar]) -> list[dict[str, Any]]:
    """Bars as plain dicts, UTC, for a DataFrame or a JSON dump."""
    rows = []
    for b in bars:
        ts = b.timestamp if b.timestamp.tzinfo else b.timestamp.replace(tzinfo=timezone.utc)
        rows.append(
            {
                "timestamp": ts.astimezone(timezone.utc),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "trade_count": b.trade_count,
                "vwap": b.vwap,
            }
        )
    return rows


def write_parquet(bars: Sequence[Bar], path: str | Path) -> Path:
    """Write the bar store. pandas and pyarrow are imported here, not at module
    load, so the pure-python validation logic above stays testable in an
    environment that has neither."""
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(bars_to_rows(bars)).to_parquet(path, index=False)
    return path


def read_parquet(path: str | Path) -> list[Bar]:
    """Read a stored dataset back into Bars, for verifying a `dataset_hash`."""
    import pandas as pd

    frame = pd.read_parquet(path)
    out: list[Bar] = []
    for row in frame.to_dict("records"):
        ts = row["timestamp"]
        out.append(
            Bar(
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                trade_count=None if row.get("trade_count") is None else int(row["trade_count"]),
                vwap=None if row.get("vwap") is None else float(row["vwap"]),
            )
        )
    return out


def store_path(config: RunConfig, digest: str, root: str | Path = "data/processed") -> Path:
    """Where a dataset lands. data/processed/ is gitignored - see §20.5."""
    d = config.data
    tag = d.feed or d.asset_class
    short = digest.split(":")[-1][:12]
    return Path(root) / f"{d.symbol.replace('/', '-')}_{d.timeframe}_{tag}_{d.start}_{d.end}_{short}.parquet"


# ------------------------------------------------------------------- ingest


@dataclass(frozen=True)
class IngestResult:
    bars: list[Bar]
    report: ValidationReport
    path: Path | None = None
    report_path: Path | None = None


def write_report(report: ValidationReport, path: str | Path) -> Path:
    """Write the validation report beside its dataset.

    PRD §5.1 requires a validation report per ingest. It is written as JSON
    rather than printed because the coverage figures have to be comparable
    across ingests - "did this window degrade relative to the last one" is not
    a question you can ask of console output that scrolled away.

    It lands in `data/processed/`, which is gitignored: bar counts and session
    timestamps are vendor-derived, and the same redistribution constraint that
    keeps the bars out of the repo covers figures computed from them
    (Outline §20.1, §20.5).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return path


def validate_bars(
    bars: Sequence[Bar],
    *,
    config: RunConfig,
    raw_count: int | None = None,
) -> ValidationReport:
    """Measure session-filtered bars against the coverage rules. No mutation.

    Raises only on duplicates and on a dataset_hash the config pinned and the
    data does not match. Everything else is reported.
    """
    d = config.data
    duplicates = find_duplicates(bars)
    if duplicates:
        shown = ", ".join(ts.isoformat() for ts in duplicates[:5])
        raise ValidationError(
            f"{len(duplicates)} duplicate timestamp(s) in {d.symbol} "
            f"{d.timeframe}: {shown}. No duplicate has ever been observed on "
            "this vendor, and a duplicated bar double-weights itself in every "
            "feature computed from it. Investigate the fetch, do not de-dupe "
            "and continue."
        )

    ordered = sorted(bars, key=lambda b: b.timestamp)
    if [b.timestamp for b in ordered] != [b.timestamp for b in bars]:
        raise ValidationError(
            "bars are not in ascending timestamp order. The provider contract "
            "is oldest-first, and every downstream window assumes it."
        )

    days = coverage(
        bars,
        timeframe=d.timeframe,
        requested_start=d.start,
        requested_end=d.end,
        session=d.session,
    )
    scored = [c for c in days if not c.is_edge and c.expected > 0]
    ratios = [c.ratio for c in scored]
    observed_days = {c.day for c in days}

    if d.session == "continuous":
        expected_days: list[date] = []
        missing: list[date] = []
        unexpected: list[date] = []
    else:
        expected_days = trading_days(d.start, d.end)
        interior = [
            day for day in expected_days if d.start < day < d.end
        ]
        missing = [day for day in interior if day not in observed_days]
        unexpected = [day for day in sorted(observed_days) if not is_trading_day(day)]

    digest = dataset_hash(
        bars,
        symbol=d.symbol,
        timeframe=d.timeframe,
        asset_class=d.asset_class,
        feed=d.feed,
        session=d.session,
    )
    if d.dataset_hash and d.dataset_hash != digest:
        raise ValidationError(
            f"dataset_hash mismatch. The config pins {d.dataset_hash}; these "
            f"bars hash to {digest}. Either the vendor revised the window or "
            "the fetch parameters differ. Do not overwrite the pin to make "
            "this pass - that is the check working."
        )

    return ValidationReport(
        symbol=d.symbol,
        timeframe=d.timeframe,
        asset_class=d.asset_class,
        feed=d.feed,
        session=d.session,
        requested_start=d.start,
        requested_end=d.end,
        bars_returned=raw_count if raw_count is not None else len(bars),
        bars_in_session=len(bars),
        bars_outside_session=(raw_count - len(bars)) if raw_count is not None else 0,
        first_timestamp=bars[0].timestamp if bars else None,
        last_timestamp=bars[-1].timestamp if bars else None,
        sessions_observed=len(observed_days),
        sessions_expected=len(expected_days),
        edge_days_excluded=len(days) - len(scored),
        flagged_days=[c for c in days if c.is_flagged],
        missing_sessions=missing,
        unexpected_sessions=unexpected,
        misaligned_timestamps=_misaligned(bars, d.timeframe) if d.session != "continuous" else 0,
        min_coverage=min(ratios) if ratios else None,
        median_coverage=_median(ratios) if ratios else None,
        dataset_hash=digest,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def ingest(
    config: RunConfig,
    provider: MarketDataProvider,
    *,
    store: bool = True,
    root: str | Path = "data/processed",
) -> IngestResult:
    """Fetch, filter, validate and store one dataset.

    The order is not negotiable: fetch raw, filter the session, then validate
    what remains. Validating before filtering would measure coverage against
    bars that are about to be discarded; filtering after feature computation is
    the contamination this whole layer exists to prevent.
    """
    config.validate()
    d = config.data
    raw = provider.get_bars(
        d.symbol,
        d.timeframe,
        d.start,
        d.end,
        asset_class=d.asset_class,
        feed=d.feed,
    )
    filtered = filter_session(raw, d.session)
    report = validate_bars(filtered, config=config, raw_count=len(raw))

    path: Path | None = None
    report_path: Path | None = None
    if store:
        path = write_parquet(filtered, store_path(config, report.dataset_hash, root))
        report_path = write_report(report, path.with_suffix(".report.json"))
    return IngestResult(bars=filtered, report=report, path=path, report_path=report_path)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m project_beta.data.pipeline <config.yaml>", file=sys.stderr)
        return 2
    from project_beta.data.alpaca import AlpacaProvider

    config = load_run_config(args[0])
    provider = AlpacaProvider()
    provider.authenticate()
    result = ingest(config, provider)
    print(result.report.summary())
    if result.path:
        print(f" stored: {result.path}")
        print(f" report: {result.report_path}")
    return 0 if result.report.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
