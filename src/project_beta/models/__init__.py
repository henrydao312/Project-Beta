"""The two M-tier models, their labels, and their calibration diagnostics.

M1 is the regime classifier; M2 adds the signal-quality model. Both are gates:
they may reject or shrink a candidate the strategy proposed and may never
create, enlarge, or alter one.
"""

from project_beta.models.calibration import (
    CalibrationReport,
    brier_score,
    calibration_report,
)
from project_beta.models.labels import (
    EMBARGO_BARS,
    HORIZON_BARS,
    TREND_STATES,
    RegimeLabel,
    label_distribution,
    label_regimes,
)
from project_beta.models.linear import LogisticRegression, StandardScaler
from project_beta.models.regime import (
    RegimeGate,
    RegimeModel,
    RegimeModelError,
)
from project_beta.models.signal_quality import (
    MIN_VALIDATION_TRADES,
    THRESHOLD_GRID,
    SignalQualityError,
    SignalQualityGate,
    SignalQualityModel,
    TrainingRow,
    training_rows,
)

__all__ = [
    "EMBARGO_BARS",
    "HORIZON_BARS",
    "MIN_VALIDATION_TRADES",
    "THRESHOLD_GRID",
    "TREND_STATES",
    "CalibrationReport",
    "LogisticRegression",
    "RegimeGate",
    "RegimeLabel",
    "RegimeModel",
    "RegimeModelError",
    "SignalQualityError",
    "SignalQualityGate",
    "SignalQualityModel",
    "StandardScaler",
    "TrainingRow",
    "brier_score",
    "calibration_report",
    "label_distribution",
    "label_regimes",
    "training_rows",
]
