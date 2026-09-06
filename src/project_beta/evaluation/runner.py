"""The fold runner: one walk-forward fold, all four rungs, nothing shared wrongly.

This is where the pieces meet, and it is the file where a leak would actually
happen. Five rules govern the order of operations, and each is asserted in
`test_models.py`.

**1. Features are computed once, over the whole series.** A feature at bar t
reads bars before t, and some of those precede the fold. That is correct - they
are past bars - and recomputing per fold from a truncated series would give the
first hours of every fold different feature values from the same bars
elsewhere. Causality is a property of the feature functions (verified by the
shift-forward invariance test), not of where a fold starts.

**2. The training window is embargoed.** Regime labels look
`models.labels.horizon_bars` ahead, so the last session of the training window
carries labels that read prices from the validation window. Those rows are
dropped. The leak is small, it improves results, and it leaves no trace.

**3. Thresholds are chosen on validation, never on test.** The signal-quality
cutoff is selected from the validation window's simulated trades. The test
window is opened once, with everything already decided.

**4. Every rung sees the same test window and the same day index.** B1, B2, M1
and M2 are run over identical bars with identical costs, so the pooled series
are paired day for day - which is what the bootstrap in
EVALUATION_PROTOCOL.md §3 requires.

**5. Cost stress re-prices the same decisions; it does not refit.** Condition 3
of the decision rule asks whether the sign of the effect survives 2x costs. The
stressed run therefore replays the test window with the same fitted models, the
same validation-chosen threshold, and the same candidates, changing only what
execution costs. Refitting under stressed costs would change the
signal-quality labels - a trade profitable at 1x and a loss at 2x is a
different training example - and would answer a different question: not "does
this result survive higher costs" but "what would a different system have
done". The first is the robustness check the protocol specifies. This is an
implementation decision and is recorded in the handoff.

Every parameter that moves a number here comes from the RunConfig, so two runs
that differ materially cannot share a `config_hash`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Sequence

from project_beta.config import RunConfig
from project_beta.data.pipeline import to_market_time
from project_beta.data.provider import Bar
from project_beta.evaluation.folds import Fold, generate_folds
from project_beta.evaluation.harness import (
    Comparison,
    FoldReturns,
    ladder,
    pool,
    require_performance_claim,
)
from project_beta.execution.simulator import STARTING_EQUITY, CompositeGate
from project_beta.features.registry import FeatureFrame
from project_beta.models.labels import label_regimes
from project_beta.models.regime import RegimeGate, RegimeModel
from project_beta.models.signal_quality import (
    SignalQualityError,
    SignalQualityGate,
    SignalQualityModel,
    training_rows,
)
from project_beta.strategy.base import Strategy
from project_beta.systems import run_b1, run_backtest

LADDER = ("B1", "B2", "M1", "M2")

# EVALUATION_PROTOCOL.md §9: headline results at the base cost model, with 2x
# and 3x printed alongside rather than in an appendix. These are *factors*
# applied to whatever `execution.cost_multiplier` the run already carries, so a
# run configured at 1.5x base stresses to 3x and 4.5x rather than silently
# dropping back to the default.
STRESS_FACTORS: tuple[float, ...] = (2.0, 3.0)

# Which stressed run condition 3 is evaluated against.
CONDITION_3_FACTOR = 2.0


class FoldTooThin(RuntimeError):
    """A fold could not be run, and the run says so rather than substituting."""


@dataclass
class FoldArtifacts:
    """Everything a fold produced that a Model Card or a reviewer would want."""

    fold: Fold
    regime_model: RegimeModel
    signal_quality: SignalQualityModel | None
    threshold: float
    train_rows: int
    validation_rows: int
    label_distribution: dict[str, int] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def provenance(self) -> dict[str, Any]:
        return {
            "fold": self.fold.index,
            "regime_model_version": self.regime_model.version,
            "regime_artifact_hash": self.regime_model.artifact_hash(),
            "signal_quality_version": (
                self.signal_quality.version if self.signal_quality else None
            ),
            "signal_quality_artifact_hash": (
                self.signal_quality.artifact_hash() if self.signal_quality else None
            ),
            "sq_threshold": self.threshold,
            "train_labelled_rows": self.train_rows,
            "validation_trades": self.validation_rows,
            "train_label_distribution": self.label_distribution,
        }


@dataclass
class FoldRun:
    """One fold at every cost level, plus what fitting it produced.

    `stressed` is keyed by the stress *factor* rather than the absolute
    multiplier, so `stressed[2.0]` is "twice this run's costs" whatever those
    costs were.
    """

    fold: Fold
    base: FoldReturns
    stressed: dict[float, FoldReturns]
    artifacts: FoldArtifacts


def _index_ranges(
    bars: Sequence[Bar], fold: Fold
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Bar-index ranges for the fold's three windows, as half-open pairs."""
    days = [to_market_time(b.timestamp).date() for b in bars]

    def span(lo: date, hi: date) -> tuple[int, int]:
        start = next((i for i, d in enumerate(days) if d >= lo), len(bars))
        end = next((i for i, d in enumerate(days) if d >= hi), len(bars))
        return start, end

    return (
        span(fold.train_start, fold.train_end),
        span(fold.validation_start, fold.validation_end),
        span(fold.test_start, fold.test_end),
    )


def stressed_config(config: RunConfig, factor: float) -> RunConfig:
    """The same run, priced at `factor` times its own cost model.

    Only `execution.cost_multiplier` moves. Everything else - the fold scheme,
    the thresholds, the seed - is identical, so the stressed run's
    `config_hash` differs from the base run's by exactly the thing that
    differs.
    """
    if factor <= 0:
        raise ValueError("a cost-stress factor must be positive")
    execution = replace(
        config.execution,
        cost_multiplier=config.execution.cost_multiplier * factor,
    )
    return replace(config, execution=execution)


def run_fold(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    config: RunConfig,
    strategy: Strategy,
    fold: Fold,
    *,
    starting_equity: float = STARTING_EQUITY,
    stress_factors: Sequence[float] = STRESS_FACTORS,
) -> FoldRun:
    """Fit on train, choose the threshold on validation, evaluate once on test.

    The test window is then replayed at each stress factor with the same fitted
    models, so condition 3 of the decision rule has something to evaluate.
    """
    (train_lo, train_hi), (val_lo, val_hi), (test_lo, test_hi) = _index_ranges(bars, fold)
    if test_hi <= test_lo:
        raise FoldTooThin(f"fold {fold.index} has no test bars")

    settings = config.models
    candidates = strategy.generate_candidates(frame, bars, config)

    # -- 1. the regime model, on embargoed training rows -------------------
    labels = label_regimes(
        bars,
        frame,
        horizon=settings.labels.horizon_bars,
        trend_k=settings.labels.trend_k,
        vol_k=settings.labels.vol_k,
    )
    # The embargo is the label horizon, taken from the config rather than a
    # constant: lengthening the horizon must lengthen the embargo, and a
    # constant would let the two drift apart silently.
    embargo = settings.labels.horizon_bars
    embargoed_hi = max(train_lo, train_hi - embargo)
    train_indices = range(train_lo, embargoed_hi)
    regime_model = RegimeModel.fit(
        frame,
        labels,
        train_indices,
        asset_class=config.data.asset_class,
        l2=settings.regime_l2,
    )
    regime_model.evaluate(frame, labels, range(val_lo, val_hi))

    # -- 2. the signal-quality model, on simulated training trades ---------
    train_run = run_backtest(
        bars, frame, candidates, config, system="B2_train",
        window=(train_lo, train_hi), starting_equity=starting_equity,
    )
    validation_run = run_backtest(
        bars, frame, candidates, config, system="B2_validation",
        window=(val_lo, val_hi), starting_equity=starting_equity,
    )
    train_examples = training_rows(train_run, frame, regime_model)
    validation_examples = training_rows(validation_run, frame, regime_model)

    signal_quality: SignalQualityModel | None = None
    threshold = 0.0
    if train_examples:
        n_features = len(frame.names) + 1 + 3
        signal_quality = SignalQualityModel.fit(
            train_examples,
            feature_names=tuple(range(n_features)),
            l2=settings.signal_quality_l2,
        )
        # The one line that keeps the walk-forward honest: validation only.
        threshold = signal_quality.choose_threshold(
            validation_examples, min_trades=settings.min_validation_trades
        )
        signal_quality.evaluate(validation_examples)

    # -- 3. the test window, opened once, then re-priced -------------------
    gates = _build_gates(config, regime_model, signal_quality)
    base = _test_window(
        bars, frame, candidates, config, fold, gates,
        window=(test_lo, test_hi), starting_equity=starting_equity,
    )
    stressed = {
        factor: _test_window(
            bars, frame, candidates, stressed_config(config, factor), fold, gates,
            window=(test_lo, test_hi), starting_equity=starting_equity,
        )
        for factor in stress_factors
    }

    artifacts = FoldArtifacts(
        fold=fold,
        regime_model=regime_model,
        signal_quality=signal_quality,
        threshold=threshold,
        train_rows=len(train_examples),
        validation_rows=len(validation_examples),
        label_distribution=regime_model.train_distribution,
        diagnostics={
            "embargoed_bars": train_hi - embargoed_hi,
            "stress_factors": list(stress_factors),
            "threshold_scores": (
                signal_quality.threshold_scores if signal_quality else {}
            ),
        },
    )
    return FoldRun(fold=fold, base=base, stressed=stressed, artifacts=artifacts)


def _build_gates(
    config: RunConfig,
    regime_model: RegimeModel,
    signal_quality: SignalQualityModel | None,
) -> dict[str, Any]:
    """B2, M1 and M2 as a gate list. The rungs differ by a list element."""
    settings = config.models
    regime_gate = RegimeGate(
        regime_model,
        permitted=settings.permitted_regimes,
        high_vol_size=settings.high_vol_size,
    )
    gates: dict[str, Any] = {"B2": None, "M1": regime_gate}
    if signal_quality is None:
        # No signal-quality model means M2 has nothing to add, so it *is* M1 on
        # this fold. Reporting that is truthful; silently dropping the fold
        # would bias the pooled series toward folds where the model trained.
        gates["M2"] = regime_gate
    else:
        gates["M2"] = CompositeGate(
            [
                regime_gate,
                SignalQualityGate(
                    signal_quality,
                    regime_model,
                    abstain_regimes=config.risk.regime_abstain,
                ),
            ]
        )
    return gates


def _test_window(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    candidates: Sequence[Any],
    config: RunConfig,
    fold: Fold,
    gates: dict[str, Any],
    *,
    window: tuple[int, int],
    starting_equity: float,
) -> FoldReturns:
    """Run every rung over one test window at this config's cost model."""
    test_lo, test_hi = window
    b1 = run_b1(bars[test_lo:test_hi], config, starting_equity=starting_equity)
    returns: dict[str, list[float]] = {"B1": b1.daily_returns}
    for system, gate in gates.items():
        result = run_backtest(
            bars, frame, candidates, config,
            system=system, gate=gate, window=window,
            starting_equity=starting_equity,
        )
        returns[system] = result.daily_returns

    lengths = {len(v) for v in returns.values()}
    if len(lengths) != 1:
        raise FoldTooThin(
            f"fold {fold.index}: rungs produced different day counts {lengths}. "
            "The paired bootstrap requires the same days in the same order."
        )
    return FoldReturns(fold=fold, days=b1.days, returns=returns)


@dataclass(frozen=True)
class SkippedFold:
    """A fold the data could not support, kept rather than dropped.

    A skipped fold that leaves no trace turns a smaller study into a larger
    one's label: fourteen folds were configured, eleven ran, and the results
    row still says fourteen unless something carries the difference.
    """

    index: int
    test_start: date
    test_end: date
    error: str
    message: str

    def provenance(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "error": self.error,
            "message": self.message,
        }


@dataclass(frozen=True)
class WalkForward:
    """The folds that ran, and the folds that did not, with the reason."""

    runs: list[FoldRun]
    skipped: list[SkippedFold]

    @property
    def expected(self) -> int:
        """Folds the configuration yielded, whether or not they ran."""
        return len(self.runs) + len(self.skipped)

    def provenance(self) -> dict[str, Any]:
        return {
            "n_folds_expected": self.expected,
            "n_folds_ran": len(self.runs),
            "n_folds_skipped": len(self.skipped),
            "skipped_folds": [s.provenance() for s in self.skipped],
        }


def run_walk_forward(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    config: RunConfig,
    strategy: Strategy,
    *,
    starting_equity: float = STARTING_EQUITY,
    stress_factors: Sequence[float] = STRESS_FACTORS,
) -> WalkForward:
    """Every fold the configuration yields, in order, at every cost level.

    Refuses before it starts if the run may not make a performance claim: an
    exploratory strategy, or an asset class with no folds.
    """
    require_performance_claim(config, strategy)
    runs: list[FoldRun] = []
    skipped: list[SkippedFold] = []
    for fold in generate_folds(config):
        try:
            runs.append(
                run_fold(
                    bars, frame, config, strategy, fold,
                    starting_equity=starting_equity,
                    stress_factors=stress_factors,
                )
            )
        except (FoldTooThin, SignalQualityError) as exc:
            # A fold with no test bars is a data gap, not a result. It is
            # skipped, and it is recorded with its index and its reason, so
            # the expected-versus-ran count travels with the figures instead
            # of being quietly absorbed into a smaller study.
            skipped.append(
                SkippedFold(
                    index=fold.index,
                    test_start=fold.test_start,
                    test_end=fold.test_end,
                    error=type(exc).__name__,
                    message=str(exc),
                )
            )
    return WalkForward(runs=runs, skipped=skipped)


# ------------------------------------------------------------------ pooling


def base_folds(runs: Sequence[FoldRun]) -> list[FoldReturns]:
    return [r.base for r in runs]


def stressed_folds(runs: Sequence[FoldRun], factor: float) -> list[FoldReturns]:
    missing = [r.fold.index for r in runs if factor not in r.stressed]
    if missing:
        raise KeyError(
            f"no {factor}x cost-stress run for folds {missing}. Condition 3 of "
            "the decision rule cannot be evaluated without one, and an "
            "unevaluated condition is a failed one."
        )
    return [r.stressed[factor] for r in runs]


def artifacts_of(runs: Sequence[FoldRun]) -> list[FoldArtifacts]:
    return [r.artifacts for r in runs]


def evaluate(
    bars: Sequence[Bar],
    frame: FeatureFrame,
    config: RunConfig,
    strategy: Strategy,
    *,
    starting_equity: float = STARTING_EQUITY,
    stress_factors: Sequence[float] = STRESS_FACTORS,
    condition_3_factor: float = CONDITION_3_FACTOR,
    resamples: int | None = None,
) -> tuple[list[Comparison], WalkForward]:
    """The whole graded run: walk forward, then the four-rung ladder.

    This is the entry point that closes the loop. Before it existed, every
    primary comparison failed condition 3 with "no cost-stress run supplied" -
    which was correct behaviour and a permanently unmeetable bar.
    """
    walk = run_walk_forward(
        bars, frame, config, strategy,
        starting_equity=starting_equity,
        stress_factors=stress_factors,
    )
    if not walk.runs:
        return [], walk

    base = base_folds(walk.runs)
    stress = stressed_folds(walk.runs, condition_3_factor)
    cost_stress_returns = {
        system: pool(stress, system) for system in LADDER
    }
    comparisons = ladder(
        base,
        config=config,
        strategy=strategy,
        cost_stress_returns=cost_stress_returns,
        resamples=resamples,
    )
    return comparisons, walk
