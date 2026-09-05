"""Calibration measurement. Required per fold for both M-tier models.

PRD §5.4 and §5.5 both require a calibration curve and a Brier score per fold,
and the reason is specific to how these models are used. The regime classifier
does not just pick a label - its probabilities gate participation, and the
signal-quality model's probability is compared against a threshold chosen on
the validation window. A model that ranks well but is badly calibrated will
have that threshold mean something different in every fold, and the ablation
would then measure threshold drift rather than the model.

The Brier score is the mean squared error of the probability, so lower is
better and 0.25 is what you get from always saying 0.5 on a balanced binary
problem. The reliability curve is what the Model Card shows.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float


@dataclass(frozen=True)
class CalibrationReport:
    brier: float
    bins: tuple[ReliabilityBin, ...]
    n: int
    base_rate: float

    @property
    def expected_calibration_error(self) -> float:
        """Count-weighted mean gap between predicted and observed."""
        if not self.n:
            return float("nan")
        return sum(
            b.count * abs(b.mean_predicted - b.observed_rate) for b in self.bins
        ) / self.n

    def summary(self) -> str:
        lines = [
            f"Brier {self.brier:.4f}  ECE {self.expected_calibration_error:.4f}  "
            f"n={self.n}  base rate {self.base_rate:.3f}",
            "  bin      n   predicted   observed",
        ]
        for b in self.bins:
            if not b.count:
                continue
            lines.append(
                f"  {b.lower:.1f}-{b.upper:.1f} {b.count:6d}      "
                f"{b.mean_predicted:.3f}      {b.observed_rate:.3f}"
            )
        return "\n".join(lines)


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must align")
    if len(probabilities) == 0:
        return float("nan")
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    return float(np.mean((p - y) ** 2))


def calibration_report(
    probabilities: Sequence[float], outcomes: Sequence[int], *, bins: int = 10
) -> CalibrationReport:
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out: list[ReliabilityBin] = []
    for lo, hi in pairwise(edges):
        # Half-open bins, closed at the top edge, so p == 1.0 has a home.
        mask = (p >= lo) & ((p < hi) | ((hi == 1.0) & (p <= hi)))
        count = int(mask.sum())
        out.append(
            ReliabilityBin(
                lower=float(lo),
                upper=float(hi),
                count=count,
                mean_predicted=float(p[mask].mean()) if count else float("nan"),
                observed_rate=float(y[mask].mean()) if count else float("nan"),
            )
        )
    return CalibrationReport(
        brier=brier_score(probabilities, outcomes),
        bins=tuple(out),
        n=len(p),
        base_rate=float(y.mean()) if len(y) else float("nan"),
    )
