"""Walk-forward fold generation at 30/6/6, step 6.

The scheme and the arithmetic behind it are settled elsewhere
(`scripts/analysis/fold_power.py`, and the Decision Tracker entry of
2026-09-02). This module turns the numbers into dated windows, and it enforces
the two properties the evaluation protocol depends on.

**The validation window is not decorative.** Thresholds have to be chosen
somewhere - the signal-quality acceptance cutoff above all - and choosing them
on the test window is leakage wearing a walk-forward costume. Every fold
therefore carries three windows, and `Fold.contains_test` is the only accessor
that returns test-window membership. A model or a threshold that wants to look
at data asks for `train` or `validation` by name.

**Test windows never overlap.** At step 6 with a 6-month test window, each
out-of-sample day is used exactly once, which is what allows the 14 test
windows to be concatenated into one pooled series and treated as a single
out-of-sample record (EVALUATION_PROTOCOL.md §2). If the step were ever set
below the test length the pooled series would double-count days and every
interval computed from it would be too narrow. That is checked here rather than
trusted.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Iterator, Sequence

from project_beta.config import ConfigError, RunConfig


class FoldError(ConfigError):
    """A fold scheme that would produce a result we could not defend."""


def add_months(day: date, months: int) -> date:
    """Shift by whole months, clamping the day to the target month's length.

    31 January plus one month is 28 February, not 3 March. Rolling over would
    drift the fold boundaries by a day or two per year and silently break the
    'each out-of-sample day used exactly once' property at the seams.
    """
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold. All windows are half-open: [start, end).

    Half-open because the alternative is an off-by-one that puts a single
    trading day in two windows, and a day that appears in both training and
    test is leakage of exactly the kind this scheme exists to prevent.
    """

    index: int
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    test_start: date
    test_end: date

    def contains_train(self, day: date) -> bool:
        return self.train_start <= day < self.train_end

    def contains_validation(self, day: date) -> bool:
        return self.validation_start <= day < self.validation_end

    def contains_test(self, day: date) -> bool:
        return self.test_start <= day < self.test_end

    def window_of(self, day: date) -> str | None:
        """Which window a day belongs to, or None if it falls outside the fold.

        Deliberately the only way to ask 'where does this day belong', so a
        caller cannot accidentally test train membership, get False, and treat
        the day as safe to evaluate on.
        """
        if self.contains_train(day):
            return "train"
        if self.contains_validation(day):
            return "validation"
        if self.contains_test(day):
            return "test"
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "fold": self.index,
            "train": [self.train_start.isoformat(), self.train_end.isoformat()],
            "validation": [
                self.validation_start.isoformat(),
                self.validation_end.isoformat(),
            ],
            "test": [self.test_start.isoformat(), self.test_end.isoformat()],
        }


def generate_folds(config: RunConfig) -> list[Fold]:
    """Every complete fold this configuration yields, in chronological order.

    An empty list is a real answer, not a failure: it is the answer for
    options, where 31 months of history cannot accommodate a 42-month fold, and
    reporting zero rather than shortening the scheme to manufacture folds is
    the whole basis of the asset-class tier structure (Outline §7A).
    """
    wf = config.walk_forward
    if wf is None:
        # Absence is meaningful. A run with no walk_forward block makes no
        # walk-forward performance claim, and inventing a default scheme here
        # would silently manufacture one.
        return []

    if wf.step_months < wf.test_months:
        raise FoldError(
            f"step_months={wf.step_months} is shorter than "
            f"test_months={wf.test_months}, so test windows would overlap and "
            "the pooled out-of-sample series would count some days twice. "
            "Every interval computed from it would be too narrow "
            "(EVALUATION_PROTOCOL.md §2)."
        )

    start, end = config.data.start, config.data.end
    folds: list[Fold] = []
    index = 0
    while True:
        train_start = add_months(start, index * wf.step_months)
        train_end = add_months(train_start, wf.train_months)
        validation_end = add_months(train_end, wf.validation_months)
        test_end = add_months(validation_end, wf.test_months)
        if test_end > end:
            break
        folds.append(
            Fold(
                index=index,
                train_start=train_start,
                train_end=train_end,
                validation_start=train_end,
                validation_end=validation_end,
                test_start=validation_end,
                test_end=test_end,
            )
        )
        index += 1

    _assert_test_windows_are_disjoint(folds)
    return folds


def _assert_test_windows_are_disjoint(folds: Sequence[Fold]) -> None:
    for earlier, later in pairwise(folds):
        if later.test_start < earlier.test_end:
            raise FoldError(
                f"test windows of folds {earlier.index} and {later.index} "
                "overlap; the pooled series would use some days twice"
            )


def pooled_test_span(folds: Sequence[Fold]) -> tuple[date, date] | None:
    """The full out-of-sample span the pooled series covers."""
    if not folds:
        return None
    return folds[0].test_start, folds[-1].test_end


def iter_folds(config: RunConfig) -> Iterator[Fold]:
    yield from generate_folds(config)
