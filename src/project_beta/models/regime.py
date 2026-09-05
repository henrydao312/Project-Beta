"""M1 - the market-regime classifier, and the gate that puts it in the path.

Ladder rung M1 is B2 plus this. The model reads the causal feature row at the
candidate's bar and predicts which of three trend states the next session is in
(plus a binary volatility flag); the gate lets the candidate through only in a
permitted state, and halves the size in the high-volatility state.

**The gate can only remove.** That is not a property of this implementation, it
is enforced by `GateDecision`: a size multiplier above 1.0 raises. Outline §1A
claims AI never takes a trading decision here, only filters one, and that claim
has to be true in the code rather than in the prose.

**Two models, not one crossed model.** Three trend states crossed with two
volatility states is six classes, and on the thinner folds several of them
would hold a few dozen examples. Outline §5.1 chose 3+1 for exactly that
reason: the classes stay populated and each stays interpretable.

**No options-trained variant exists, and that is asserted.** PRD §5.4. Options
history is 31 months inside close to a single market regime; a classifier
trained or tested there would have almost no regime variety to learn from, and
its existence would invite exactly the cross-asset comparison the tier
structure refuses.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from project_beta.execution.simulator import GateDecision
from project_beta.features.registry import FeatureFrame
from project_beta.models.calibration import CalibrationReport, calibration_report
from project_beta.models.labels import TREND_STATES, RegimeLabel, label_distribution
from project_beta.models.linear import LogisticRegression
from project_beta.strategy.base import CandidateTrade

MODEL_VERSION = "regime_lr_v1"


class RegimeModelError(RuntimeError):
    """The regime model was asked for something it must not provide."""


@dataclass
class RegimeModel:
    """Fitted trend and volatility classifiers, plus their fold diagnostics."""

    feature_names: tuple[str, ...]
    trend: LogisticRegression
    volatility: LogisticRegression
    version: str = MODEL_VERSION
    train_distribution: dict[str, int] = field(default_factory=dict)
    calibration: dict[str, CalibrationReport] = field(default_factory=dict)

    # ---------------------------------------------------------------- fitting

    @classmethod
    def fit(
        cls,
        frame: FeatureFrame,
        labels: Sequence[RegimeLabel | None],
        indices: Sequence[int],
        *,
        asset_class: str = "equity",
        l2: float = 1.0,
    ) -> "RegimeModel":
        """Fit on the given bar indices only. The caller owns the embargo.

        `indices` is the training window minus its embargoed tail. Passing the
        whole window would train on labels that read prices from the validation
        window, which is the leak this design creates and the fold runner
        removes.
        """
        if asset_class == "option":
            raise RegimeModelError(
                "no options-trained regime classifier exists (PRD §5.4). "
                "Options history is 31 months inside close to a single market "
                "regime, so there is almost no regime variety to learn; a "
                "model fitted there would invite the cross-asset comparison "
                "the tier structure refuses (Outline §7A)."
            )
        rows, kept = _matrix(frame, labels, indices)
        if not rows:
            raise RegimeModelError(
                "no labelled training rows. Either the window is shorter than "
                "the feature warmup, or the embargo has removed all of it."
            )
        X = np.asarray(rows, dtype=float)
        trend_y = [labels[i].trend for i in kept]  # type: ignore[union-attr]
        vol_y = [labels[i].vol_flag for i in kept]  # type: ignore[union-attr]

        model = cls(
            feature_names=frame.names,
            trend=LogisticRegression(l2=l2).fit(X, trend_y),
            volatility=LogisticRegression(l2=l2).fit(X, vol_y),
            train_distribution=label_distribution([labels[i] for i in kept]),
        )
        return model

    # -------------------------------------------------------------- inference

    def predict_row(self, row: Sequence[float]) -> dict[str, Any]:
        """The `regime` block of a DecisionRecord (PRD §4.2).

        `probs` carries every state name as a key while the record asserts only
        the one in `label`. The grounding checker treats values as claims and
        keys as vocabulary; conflating them silently accepts a wrong regime
        claim.
        """
        X = np.asarray([list(row)], dtype=float)
        probs = self.trend.proba_dict(X)[0]
        vol_probs = self.volatility.proba_dict(X)[0]
        label = max(probs, key=probs.get)
        vol_flag = max(vol_probs, key=vol_probs.get)
        return {
            "label": label,
            "probs": {state: probs.get(state, 0.0) for state in TREND_STATES},
            "vol_flag": vol_flag,
            "vol_prob": vol_probs.get(vol_flag, 0.0),
            "model_version": self.version,
        }

    def artifact_hash(self) -> str:
        """A fingerprint of the fitted weights, for `models.regime.artifact_hash`.

        Two runs quoting the same model version but different weights is the
        failure this catches, and a results table cannot show it any other way.
        """
        payload = b"".join(
            np.ascontiguousarray(a, dtype=np.float64).tobytes()
            for a in (
                self.trend.weights_,
                self.trend.bias_,
                self.volatility.weights_,
                self.volatility.bias_,
            )
            if a is not None
        )
        return "sha256:" + hashlib.sha256(payload).hexdigest()[:16]

    # ------------------------------------------------------------ diagnostics

    def evaluate(
        self,
        frame: FeatureFrame,
        labels: Sequence[RegimeLabel | None],
        indices: Sequence[int],
    ) -> dict[str, CalibrationReport]:
        """Per-fold calibration, required by PRD §5.4's acceptance criteria.

        Reported per trend state one-vs-rest, because a three-class model can
        be well calibrated on the majority state and badly calibrated on the
        one that actually gates trades.
        """
        rows, kept = _matrix(frame, labels, indices)
        if not rows:
            return {}
        X = np.asarray(rows, dtype=float)
        probs = self.trend.proba_dict(X)
        out: dict[str, CalibrationReport] = {}
        for state in TREND_STATES:
            p = [row.get(state, 0.0) for row in probs]
            y = [int(labels[i].trend == state) for i in kept]  # type: ignore[union-attr]
            out[state] = calibration_report(p, y)
        self.calibration = out
        return out


def _matrix(
    frame: FeatureFrame,
    labels: Sequence[RegimeLabel | None],
    indices: Sequence[int],
) -> tuple[list[list[float]], list[int]]:
    rows: list[list[float]] = []
    kept: list[int] = []
    for i in indices:
        row = frame.row(i)
        if row is None or labels[i] is None:
            continue
        rows.append([row[name] for name in frame.names])
        kept.append(i)
    return rows, kept


# ---------------------------------------------------------------------- gate


class RegimeGate:
    """M1's contribution to the ladder: participate only in permitted regimes.

    Defaults are long-only-friendly by design - the primary strategy is
    long-only, so a downtrend prediction is a reason to stand aside rather than
    to reverse. `permitted` is a parameter so the abstention set can be set
    from evidence after calibration rather than by assumption.
    """

    name = "regime"

    def __init__(
        self,
        model: RegimeModel,
        *,
        permitted: Sequence[str] = ("uptrend",),
        min_probability: float = 0.0,
        high_vol_size: float = 0.5,
    ) -> None:
        if not 0.0 <= high_vol_size <= 1.0:
            raise ValueError("high_vol_size must lie in [0, 1]: a gate may only shrink")
        unknown = set(permitted) - set(TREND_STATES)
        if unknown:
            raise ValueError(f"unknown regime states {sorted(unknown)}")
        self.model = model
        self.permitted = tuple(permitted)
        self.min_probability = min_probability
        self.high_vol_size = high_vol_size

    def evaluate(
        self, candidate: CandidateTrade, frame: FeatureFrame, index: int
    ) -> GateDecision:
        row = frame.row(index)
        if row is None:
            # No feature row means no basis for an opinion. Standing aside is
            # the honest answer; permitting by default would let unwarmed bars
            # through the one component meant to be judging them.
            return GateDecision(
                decision="rejected",
                reason_codes=("REGIME_BLOCKS",),
                size_multiplier=0.0,
                detail={"regime": {"label": None, "model_version": self.model.version}},
            )
        prediction = self.model.predict_row([row[n] for n in frame.names])
        detail = {"regime": prediction}
        permitted = (
            prediction["label"] in self.permitted
            and prediction["probs"].get(prediction["label"], 0.0) >= self.min_probability
        )
        if not permitted:
            return GateDecision(
                decision="rejected",
                reason_codes=("REGIME_BLOCKS",),
                size_multiplier=0.0,
                detail=detail,
            )
        if prediction["vol_flag"] == "high" and self.high_vol_size < 1.0:
            return GateDecision(
                decision="reduced",
                reason_codes=("REGIME_PERMITS", "REGIME_REDUCES"),
                size_multiplier=self.high_vol_size,
                detail=detail,
            )
        return GateDecision(
            decision="approved", reason_codes=("REGIME_PERMITS",), detail=detail
        )
