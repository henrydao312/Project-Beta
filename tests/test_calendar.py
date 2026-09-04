"""Session calendar tests.

The calendar is only worth having if it is right about the awkward days, so
these are checked against the NYSE's actual published schedule for years the
project's data covers rather than against the rules that generated them.

The early-close cases carry the most weight. A 13:00 close is a complete
session with 42 five-minute bars, and a calendar that thinks it should hold 78
turns nine good days a year into coverage alerts - which is how real outages
get lost in a list nobody reads any more.
"""

from __future__ import annotations

from datetime import date

import pytest

from project_beta.data.calendar import (
    early_closes,
    expected_bars,
    holidays,
    is_trading_day,
    session_close,
    trading_days,
)

# ------------------------------------------------------------- known years


@pytest.mark.parametrize(
    "year,expected",
    [
        # NYSE published schedules. 2021 and 2024 are inside the project's
        # equity window; 2026 is the current year.
        (2021, {date(2021, 1, 1), date(2021, 1, 18), date(2021, 2, 15),
                date(2021, 4, 2), date(2021, 5, 31), date(2021, 7, 5),
                date(2021, 9, 6), date(2021, 11, 25), date(2021, 12, 24)}),
        (2024, {date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19),
                date(2024, 3, 29), date(2024, 5, 27), date(2024, 6, 19),
                date(2024, 7, 4), date(2024, 9, 2), date(2024, 11, 28),
                date(2024, 12, 25)}),
        (2026, {date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
                date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
                date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26),
                date(2026, 12, 25)}),
    ],
)
def test_holidays_match_the_published_schedule(year: int, expected: set) -> None:
    assert holidays(year) == expected


def test_juneteenth_is_absent_before_2022() -> None:
    """It became a market holiday in 2022; June 19 traded before that.

    A calendar that back-projects it would report every pre-2022 Juneteenth as
    a missing session across six years of the equity window.
    """
    assert date(2021, 6, 18) not in holidays(2021) # the Friday it would have moved to
    assert is_trading_day(date(2021, 6, 18))
    assert not is_trading_day(date(2022, 6, 20)) # observed Monday, June 19 a Sunday


def test_new_years_day_on_saturday_closes_nothing() -> None:
    """The one exception to the Saturday-moves-back rule.

    Jan 1 2022 fell on a Saturday and the NYSE traded Friday 31 December 2021
    as a normal session.
    """
    assert date(2021, 12, 31) not in holidays(2021)
    assert is_trading_day(date(2021, 12, 31))


def test_holiday_observed_forward_from_sunday() -> None:
    """July 4 2021 fell on a Sunday; the market closed Monday July 5."""
    assert date(2021, 7, 5) in holidays(2021)
    assert not is_trading_day(date(2021, 7, 5))


def test_trading_day_counts_match_the_exchange() -> None:
    """252 sessions in 2024, 251 in 2026. Off-by-one here is a missing holiday."""
    assert len(trading_days(date(2024, 1, 1), date(2024, 12, 31))) == 252
    assert len(trading_days(date(2026, 1, 1), date(2026, 12, 31))) == 251


# ------------------------------------------------------------ early closes


@pytest.mark.parametrize(
    "day",
    [
        date(2024, 11, 29), # day after Thanksgiving
        date(2024, 7, 3), # July 4 on a Thursday, so the 3rd is a half day
        date(2024, 12, 24), # Christmas Eve on a Tuesday
        date(2026, 11, 27),
        date(2026, 12, 24),
    ],
)
def test_known_early_closes(day: date) -> None:
    assert day in early_closes(day.year)
    assert session_close(day).hour == 13


def test_an_eve_that_is_itself_a_holiday_is_not_an_early_close() -> None:
    """Christmas Day 2021 fell on Saturday, so the market closed Friday the 24th.

    A closed day is not a half day, and counting it as one would put a session
    in the expected calendar that never existed.
    """
    assert date(2021, 12, 24) in holidays(2021)
    assert date(2021, 12, 24) not in early_closes(2021)
    assert not is_trading_day(date(2021, 12, 24))


def test_july_3_is_not_an_early_close_when_it_is_the_observed_holiday() -> None:
    """July 4 2026 falls on a Saturday, so the closure moves to Friday the 3rd."""
    assert date(2026, 7, 3) in holidays(2026)
    assert date(2026, 7, 3) not in early_closes(2026)


# --------------------------------------------------------------- bar counts


def test_expected_bars_full_session() -> None:
    """09:30-16:00 at five minutes is 78 bars. The number every doc quotes."""
    assert expected_bars(date(2026, 8, 28), 5) == 78
    assert expected_bars(date(2026, 8, 28), 1) == 390
    assert expected_bars(date(2026, 8, 28), 15) == 26


def test_expected_bars_early_close() -> None:
    """09:30-13:00 is 42 bars, and a 42-bar half day is complete, not 54% covered."""
    assert expected_bars(date(2026, 11, 27), 5) == 42


def test_expected_bars_is_zero_on_a_non_session() -> None:
    """Zero means 'no session here', and callers must not divide by it."""
    assert expected_bars(date(2026, 12, 25), 5) == 0 # Christmas
    assert expected_bars(date(2026, 8, 29), 5) == 0 # Saturday
