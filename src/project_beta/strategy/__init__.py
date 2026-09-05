"""Strategy engine: transparent rule sets that propose candidates.

Importing this package registers every strategy. The primary rule set is
graded; the secondary ones are exploratory and structurally blocked from the
graded ablation by `assert_gradeable`.
"""

from project_beta.strategy import momentum as _momentum  # noqa: F401
from project_beta.strategy import secondary as _secondary  # noqa: F401
from project_beta.strategy.base import (
    STRATEGIES,
    CandidateTrade,
    Strategy,
    StrategyError,
    TierViolation,
    assert_gradeable,
    build_strategy,
    make_trade_id,
    register_strategy,
)

__all__ = [
    "STRATEGIES",
    "CandidateTrade",
    "Strategy",
    "StrategyError",
    "TierViolation",
    "assert_gradeable",
    "build_strategy",
    "make_trade_id",
    "register_strategy",
]
