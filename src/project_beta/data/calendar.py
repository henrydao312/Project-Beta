"""The US equity session calendar, derived from rules rather than tabulated.

Why this module exists at all. The coverage rules in Outline §9 and PRD §5.1
are stated per *session*: flag a day below ~90% coverage, exclude window-edge
days, never assert exactly 78 bars. None of that can be computed without
knowing what a full session is on that particular day, and "78 bars" is wrong
on roughly nine days a year - the 13:00 ET early closes, where 42 is full.
Measuring those days against 78 would flag every one of them at 54% and bury
the real outages in a list of false positives.

Why derived and not a table. A hardcoded holiday list is correct until the
first year nobody remembers to extend it, and then it is silently wrong in the
direction of "everything looks fine". The rules below cover 2016-06-10 (the SIP
history floor) onward and extend forward without maintenance.

**What this calendar is not.** It is not an authoritative NYSE calendar. It
does not know about one-off closures - a state funeral, Hurricane Sandy, a
market-wide outage - and it cannot. That is why nothing in the pipeline
*rejects* data on this calendar's say-so. A session in the data that this
calendar did not expect is flagged for review, not dropped; a session this
calendar expected that the data does not have is flagged, not fabricated. The
calendar's job is to make a human look at the right days, and a one-off closure
appearing as "missing session, look at this" is the correct outcome for it.

Sources for the rules: NYSE holiday and hours publications. Verified against
the observed 2026 sessions in the Week 1 coverage probe.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from functools import lru_cache

# Regular session, both feeds, all equity products this project touches.
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
# The only early close the NYSE schedules. Always 13:00 ET, never anything else.
EARLY_CLOSE = time(13, 0)

# Juneteenth became a market holiday in 2022. Before that, June 19 traded.
JUNETEENTH_FIRST_YEAR = 2022


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (Anonymous Gregorian computus).

    Present only because Good Friday is the one market holiday with no fixed
    date and no nth-weekday rule.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    n = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * n) // 451
    month, day = divmod(h + n - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth given weekday of a month. weekday: Monday=0, per date.weekday()."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last given weekday of a month."""
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date, *, shift_saturday_back: bool = True) -> date | None:
    """Map a fixed-date holiday to the day the market actually closes.

    NYSE convention: a holiday on Sunday is observed the following Monday; one
    on Saturday is observed the preceding Friday - with New Year's Day the
    exception, where no Friday closing is taken. Callers pass
    ``shift_saturday_back=False`` for that case, and get None: the market
    simply trades its normal schedule around it.
    """
    if day.weekday() == 5: # Saturday
        return day - timedelta(days=1) if shift_saturday_back else None
    if day.weekday() == 6: # Sunday
        return day + timedelta(days=1)
    return day


@lru_cache(maxsize=64)
def holidays(year: int) -> frozenset[date]:
    """Full-day NYSE closures in a given year, as actually observed."""
    out: set[date] = set()

    new_year = _observed(date(year, 1, 1), shift_saturday_back=False)
    if new_year is not None:
        out.add(new_year)
    # A New Year's Day on Saturday closes the *following* Monday only when it
    # rolls forward, which it cannot; but Jan 1 on Sunday closes Jan 2. Handled
    # by _observed above.

    out.add(_nth_weekday(year, 1, 0, 3)) # MLK Jr Day
    out.add(_nth_weekday(year, 2, 0, 3)) # Washington's Birthday
    out.add(_easter(year) - timedelta(days=2)) # Good Friday
    out.add(_last_weekday(year, 5, 0)) # Memorial Day
    if year >= JUNETEENTH_FIRST_YEAR:
        juneteenth = _observed(date(year, 6, 19))
        if juneteenth is not None:
            out.add(juneteenth)
    independence = _observed(date(year, 7, 4))
    if independence is not None:
        out.add(independence)
    out.add(_nth_weekday(year, 9, 0, 1)) # Labor Day
    out.add(_nth_weekday(year, 11, 3, 4)) # Thanksgiving
    christmas = _observed(date(year, 12, 25))
    if christmas is not None:
        out.add(christmas)

    return frozenset(d for d in out if d.weekday() < 5)


@lru_cache(maxsize=64)
def early_closes(year: int) -> frozenset[date]:
    """Days the NYSE closes at 13:00 ET.

    Three recurring cases: the day after Thanksgiving; July 3 when it is a
    trading day and Independence Day is observed on the 4th; and Christmas Eve
    when it is a trading day. Each is checked against `holidays` so a year
    where the eve is itself the observed closure produces no early close.
    """
    hol = holidays(year)
    out: set[date] = set()

    candidates = [
        _nth_weekday(year, 11, 3, 4) + timedelta(days=1), # day after Thanksgiving
        date(year, 7, 3),
        date(year, 12, 24),
    ]
    for day in candidates:
        if day.weekday() < 5 and day not in hol:
            out.add(day)

    return frozenset(out)


def is_trading_day(day: date) -> bool:
    """True if the regular US equity session runs at all on this date."""
    return day.weekday() < 5 and day not in holidays(day.year)


def session_close(day: date) -> time:
    """The scheduled close for a trading day: 16:00 ET, or 13:00 on an early close."""
    return EARLY_CLOSE if day in early_closes(day.year) else REGULAR_CLOSE


def expected_bars(day: date, timeframe_minutes: int) -> int:
    """How many bars a *complete* regular session yields at this timeframe.

    78 on a normal 5-minute day, 42 on an early close. This is the denominator
    for coverage, and the reason coverage is not measured against a constant.

    Zero on a non-trading day, which callers must treat as "no session here"
    rather than dividing by it.
    """
    if not is_trading_day(day):
        return 0
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    close = session_close(day)
    minutes = (close.hour * 60 + close.minute) - (
        REGULAR_OPEN.hour * 60 + REGULAR_OPEN.minute
    )
    return minutes // timeframe_minutes


def trading_days(start: date, end: date) -> list[date]:
    """Every regular-session date in [start, end], inclusive.

    Used to find sessions the data is missing entirely. A day with no bars at
    all is invisible to any check that iterates over the data, and a full-day
    outage is exactly that shape.
    """
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")
    day = start
    out: list[date] = []
    while day <= end:
        if is_trading_day(day):
            out.append(day)
        day += timedelta(days=1)
    return out
