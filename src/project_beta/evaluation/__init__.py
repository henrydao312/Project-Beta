"""Evaluation: folds, metrics, the paired bootstrap, and the locked decision rule.

EVALUATION_PROTOCOL.md is the specification this package implements. It was
locked on 2026-09-02, before any M-tier model existed, and its change rule
requires a decision-log entry plus disclosure in the final report.
"""

from project_beta.evaluation.bootstrap import (
    EXPECTED_BLOCK_DAYS,
    RESAMPLES,
    BootstrapError,
    Interval,
    paired_sharpe_difference,
)
from project_beta.evaluation.folds import Fold, FoldError, generate_folds
from project_beta.evaluation.harness import (
    MATERIALITY_FLOOR,
    PRIMARY_COMPARISON,
    Comparison,
    FoldReturns,
    SharpeNotApplicable,
    compare,
    ladder,
    pool,
    require_performance_claim,
)
from project_beta.evaluation.metrics import (
    PerformanceSummary,
    annualised_sharpe,
    max_drawdown,
    summarise,
)
from project_beta.evaluation.runner import (
    CONDITION_3_FACTOR,
    STRESS_FACTORS,
    FoldRun,
    FoldTooThin,
    artifacts_of,
    base_folds,
    evaluate,
    run_fold,
    run_walk_forward,
    stressed_config,
    stressed_folds,
)

__all__ = [
    "CONDITION_3_FACTOR",
    "EXPECTED_BLOCK_DAYS",
    "MATERIALITY_FLOOR",
    "PRIMARY_COMPARISON",
    "RESAMPLES",
    "STRESS_FACTORS",
    "BootstrapError",
    "Comparison",
    "Fold",
    "FoldError",
    "FoldReturns",
    "FoldRun",
    "FoldTooThin",
    "Interval",
    "PerformanceSummary",
    "SharpeNotApplicable",
    "annualised_sharpe",
    "artifacts_of",
    "base_folds",
    "compare",
    "evaluate",
    "generate_folds",
    "ladder",
    "max_drawdown",
    "paired_sharpe_difference",
    "pool",
    "require_performance_claim",
    "run_fold",
    "run_walk_forward",
    "stressed_config",
    "stressed_folds",
    "summarise",
]
