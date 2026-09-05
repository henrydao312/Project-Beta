"""M2 - the signal-quality model, its threshold, and its abstention.

Ladder rung M2 is M1 plus this. The model scores each candidate the strategy
proposed and the regime gate permitted, and the gate drops the ones scoring
below a threshold.

**Labels come from simulated outcomes under the evaluation cost model**, not
from raw price moves (PRD §5.5). A trade that would have been profitable gross
and a loss after slippage and commission is a negative example, because it is a
negative example. Training on gross outcomes teaches the model to like trades
the system cannot actually make money on.

**The threshold is chosen on the validation window and never on the test
window.** This is the entire reason the 30/6/6 scheme carries a validation
window at all: something has to pick the cutoff, and picking it on the test
window is leakage wearing a walk-forward costume. `choose_threshold` takes
validation data only, and `test_models.py` asserts the fold runner never hands
it test-window rows.

**Abstention is a mitigation, not a disclaimer.** Outline §20.3 requires a
fairness check across regimes and one action to take when a regime fails it.
Where per-regime evaluation shows M2 underperforming B2, that regime goes in
`risk.regime_abstain`, and in that regime this gate stops rejecting: the
candidate passes through exactly as B2 would have taken it. The alternative -
noting the underperformance in the report and shipping it anyway - is what the
requirement exists to prevent.

**Two outputs, one gate.** `p_profit` and `p_target_before_stop` are both
recorded in the DecisionRecord; only `p_profit` gates. Gating on both would be
two thresholds, two chances to pass, and no way to attribute which mattered.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from project_beta.execution.simulator import BacktestResult, GateDecision
from project_beta.features.registry import FeatureFrame
from project_beta.models.calibration import CalibrationReport, calibration_report
from project_beta.models.labels import TREND_STATES
from project_beta.models.linear import LogisticRegression
from project_beta.models.regime import RegimeModel
from project_beta.strategy.base import CandidateTrade

MODEL_VERSION = "sq_lr_v1"

# The grid the acceptance cutoff is chosen from, on the validation window. A
# fixed grid rather than a continuous optimisation so the choice is auditable
# and identical across folds.
THRESHOLD_GRID: tuple[float, ...] = tuple(round(0.30 + 0.025 * i, 3) for i in range(21))

# Below this many validation trades a threshold is not selectable: the score
# would be noise, and picking the noisiest cutoff is how a threshold sweep
# turns into overfitting.
MIN_VALIDATION_TRADES = 20


class SignalQualityError(RuntimeError):
    pass


def feature_vector(
    row: dict[str, float],
    names: Sequence[str],
    candidate_strength: float,
    regime: dict[str, Any],
) -> list[float]:
    """The model's inputs: the causal feature row, the signal, the regime.

    Outline §5.2 lists regime probabilities, signal strength, realized
    volatility, volume confirmation and trend strength. Volume confirmation is
    absent, and its absence is the feed-transfer verdict of 2026-09-02 rather
    than an oversight; the rest are here.
    """
    probs = regime.get("probs") or {}
    return (
        [row[n] for n in names]
        + [candidate_strength]
        + [float(probs.get(state, 0.0)) for state in TREND_STATES]
    )


@dataclass
class TrainingRow:
    bar_index: int
    features: list[float]
    profitable: int
    target_first: int
    r_multiple: float
    regime: str


@dataclass
class SignalQualityModel:
    feature_names: tuple[str, ...]
    profit: LogisticRegression
    target_first: LogisticRegression
    threshold: float = 0.5
    version: str = MODEL_VERSION
    calibration: CalibrationReport | None = None
    threshold_scores: dict[float, float] = field(default_factory=dict)

    @classmethod
    def fit(
        cls, rows: Sequence[TrainingRow], *, feature_names: Sequence[str], l2: float = 1.0
    ) -> "SignalQualityModel":
        if not rows:
            raise SignalQualityError(
                "no training rows: the training window produced no resolved "
                "trades, so there is nothing to learn what a good one looks like"
            )
        X = np.asarray([r.features for r in rows], dtype=float)
        return cls(
            feature_names=tuple(feature_names),
            profit=LogisticRegression(l2=l2).fit(X, [r.profitable for r in rows]),
            target_first=LogisticRegression(l2=l2).fit(X, [r.target_first for r in rows]),
        )

    # -------------------------------------------------------------- inference

    def score(self, features: Sequence[float]) -> dict[str, Any]:
        """The `signal_quality` block of a DecisionRecord (PRD §4.2)."""
        X = np.asarray([list(features)], dtype=float)
        return {
            "p_profit": _probability_of_one(self.profit, X),
            "p_target_before_stop": _probability_of_one(self.target_first, X),
            "model_version": self.version,
            "threshold": self.threshold,
        }

    def artifact_hash(self) -> str:
        payload = b"".join(
            np.ascontiguousarray(a, dtype=np.float64).tobytes()
            for a in (
                self.profit.weights_,
                self.profit.bias_,
                self.target_first.weights_,
                self.target_first.bias_,
            )
            if a is not None
        )
        return "sha256:" + hashlib.sha256(payload).hexdigest()[:16]

    # -------------------------------------------------------------- threshold

    def choose_threshold(
        self,
        validation_rows: Sequence[TrainingRow],
        *,
        grid: Sequence[float] = THRESHOLD_GRID,
        min_trades: int = MIN_VALIDATION_TRADES,
    ) -> float:
        """Pick the acceptance cutoff on validation data. Never on test data.

        The score is the trade-level information ratio of the surviving
        trades - mean R over standard deviation of R, times the square root of
        the count. The count term is what stops the grid selecting a threshold
        so strict that three lucky trades survive it, which is the failure mode
        of picking the highest mean alone.
        """
        if any(r.bar_index < 0 for r in validation_rows):
            raise SignalQualityError("validation rows carry invalid bar indices")
        scores: dict[float, float] = {}
        for threshold in grid:
            kept = [
                r
                for r in validation_rows
                if _probability_of_one(
                    self.profit, np.asarray([r.features], dtype=float)
                )
                >= threshold
            ]
            if len(kept) < min_trades:
                continue
            values = [r.r_multiple for r in kept]
            mean = float(np.mean(values))
            sd = float(np.std(values, ddof=1))
            if not sd > 0:
                continue
            scores[threshold] = mean / sd * float(np.sqrt(len(values)))

        self.threshold_scores = scores
        if not scores:
            # No cutoff had enough surviving trades to judge. Accepting
            # everything makes M2 equal M1 on this fold, which is a truthful
            # "this fold gave the model nothing to work with" rather than a
            # threshold picked from noise.
            self.threshold = 0.0
            return self.threshold
        self.threshold = max(scores, key=lambda t: (scores[t], -t))
        return self.threshold

    def evaluate(self, rows: Sequence[TrainingRow]) -> CalibrationReport:
        """Per-fold calibration, required by PRD §5.5's acceptance criteria."""
        if not rows:
            return calibration_report([], [])
        X = np.asarray([r.features for r in rows], dtype=float)
        p = [_probability_of_one(self.profit, X[i : i + 1]) for i in range(len(rows))]
        self.calibration = calibration_report(p, [r.profitable for r in rows])
        return self.calibration


def _probability_of_one(model: LogisticRegression, X: np.ndarray) -> float:
    proba = model.predict_proba(X)
    if len(model.classes_) < 2:
        # A window in which every trade had the same outcome. Reporting the
        # base rate is honest; reporting 0.5 would invent uncertainty.
        return float(model.classes_[0]) if model.classes_ else 0.5
    return float(proba[0, model.classes_.index(1)])


# ------------------------------------------------------------ training rows


def training_rows(
    result: BacktestResult,
    frame: FeatureFrame,
    regime_model: RegimeModel,
    *,
    indices: set[int] | None = None,
) -> list[TrainingRow]:
    """Turn a B2 run's resolved trades into labelled examples.

    Only resolved trades count. An unresolved position at the end of a window
    has no outcome, and assigning it one - a loss, a zero - would teach the
    model about the window boundary rather than about the market.
    """
    rows: list[TrainingRow] = []
    for trade in result.trades:
        i = trade.candidate.bar_index
        if indices is not None and i not in indices:
            continue
        row = frame.row(i)
        if row is None:
            continue
        regime = regime_model.predict_row([row[n] for n in frame.names])
        rows.append(
            TrainingRow(
                bar_index=i,
                features=feature_vector(
                    row, frame.names, trade.candidate.signal_strength, regime
                ),
                profitable=int(trade.pnl > 0),
                target_first=int(trade.exit_reason == "target"),
                r_multiple=trade.r_multiple,
                regime=regime["label"],
            )
        )
    return rows


# ---------------------------------------------------------------------- gate


class SignalQualityGate:
    """M2's contribution: drop the candidates the model scores below the cutoff.

    Holds the regime model because the score reads regime probabilities and
    because abstention is defined per regime. That is the same fitted regime
    model M1 uses, so M2 really is M1 plus one component.
    """

    name = "signal_quality"

    def __init__(
        self,
        model: SignalQualityModel,
        regime_model: RegimeModel,
        *,
        abstain_regimes: Sequence[str] = (),
    ) -> None:
        unknown = set(abstain_regimes) - set(TREND_STATES)
        if unknown:
            raise ValueError(f"unknown regimes in abstention list: {sorted(unknown)}")
        self.model = model
        self.regime_model = regime_model
        self.abstain_regimes = tuple(abstain_regimes)

    def evaluate(
        self, candidate: CandidateTrade, frame: FeatureFrame, index: int
    ) -> GateDecision:
        row = frame.row(index)
        if row is None:
            return GateDecision(
                decision="rejected",
                reason_codes=("SQ_BELOW_THRESHOLD",),
                size_multiplier=0.0,
            )
        regime = self.regime_model.predict_row([row[n] for n in frame.names])
        scored = self.model.score(
            feature_vector(row, frame.names, candidate.signal_strength, regime)
        )
        detail = {"signal_quality": scored}

        if regime["label"] in self.abstain_regimes:
            # Outline §20.3's mitigation. The score is still recorded, so the
            # abstention is auditable and its cost measurable; it simply does
            # not gate.
            scored["abstained"] = True
            return GateDecision(
                decision="approved", reason_codes=("SQ_ABSTAINED",), detail=detail
            )

        if scored["p_profit"] < self.model.threshold:
            return GateDecision(
                decision="rejected",
                reason_codes=("SQ_BELOW_THRESHOLD",),
                size_multiplier=0.0,
                detail=detail,
            )
        return GateDecision(
            decision="approved", reason_codes=("SQ_ABOVE_THRESHOLD",), detail=detail
        )
