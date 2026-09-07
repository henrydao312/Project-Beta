"""The walk-forward harness: what may be compared, and what the result means.

This module holds the two refusals that keep the evaluation honest, and the
decision rule that was locked before any M-tier model existed.

**Refusal 1 - tier.** `assert_gradeable` (strategy layer) is called before any
headline metric is computed. Secondary strategies may be selectable product
paths, but until a family has passed the full pre-registered protocol, a Sharpe
from one would look exactly like a result while having nothing behind it
(Outline §5.3, PRD §5.14).

**Refusal 2 - asset class.** Options makes no walk-forward performance claim.
It has zero complete folds at 30/6/6, because 31 months of history cannot
accommodate a 42-month fold, and shortening the scheme to manufacture folds is
explicitly declined (Outline §7A). `SharpeNotApplicable` is raised rather than
NaN returned: a NaN in a results table gets filled in later by somebody.

**The decision rule is not selected after the fact.** All three conditions in
EVALUATION_PROTOCOL.md §4 must hold, including the +0.20 materiality floor,
and the cost-stress sign check. `compare()` reports a verdict of
`no_claim` with the interval attached whenever any of them fails - which
Outline §18 treats as a legitimate outcome rather than a disappointment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from project_beta.config import RunConfig
from project_beta.evaluation.bootstrap import Interval, paired_sharpe_difference
from project_beta.evaluation.folds import Fold, generate_folds
from project_beta.evaluation.metrics import (
    CRYPTO_DAYS_YEAR,
    TRADING_DAYS_YEAR,
    PerformanceSummary,
    annualised_sharpe,
    summarise,
)
from project_beta.strategy.base import Strategy, assert_gradeable

# Protocol §4 condition 2. A materiality floor: without it, a detectable but
# economically trivial difference could be reported as an improvement.
MATERIALITY_FLOOR = 0.20

# Protocol §6. Only one comparison is primary; everything else is a ladder rung
# or a secondary metric, reported with an interval and without claim language.
PRIMARY_COMPARISON = ("M2", "B2")

# Protocol §8. Below this many out-of-sample days a slice reports its count
# rather than a ratio, and never a significance claim.
MIN_SLICE_DAYS = 60


class SharpeNotApplicable(RuntimeError):
    """A Sharpe was requested for a track that makes no performance claim."""


def periods_per_year(config: RunConfig) -> int:
    """252 for equities, 365 for crypto: a 24/7 tape has no weekends.

    Annualising crypto on 252 would inflate its Sharpe by about 20% against
    the equity core it is meant to be compared with.
    """
    return CRYPTO_DAYS_YEAR if config.data.asset_class == "crypto" else TRADING_DAYS_YEAR


def require_performance_claim(config: RunConfig, strategy: Strategy | None = None) -> None:
    """The only door to a headline metric. Both refusals, in one place."""
    if strategy is not None:
        assert_gradeable(strategy)
    if config.data.asset_class == "option":
        raise SharpeNotApplicable(
            "asset_class='option' makes no strategy-performance claim. Options "
            "history begins 2024-01-18, which is 31 months and zero complete "
            "folds at 30/6/6; shortening the scheme for one asset class was "
            "explicitly declined (Outline §7A). The options track reports "
            "fill feasibility as a Wilson interval on a proportion, which the "
            "same held-out window supports comfortably - see "
            "EVALUATION_PROTOCOL.md §7."
        )
    if not generate_folds(config):
        raise SharpeNotApplicable(
            f"this configuration yields no complete walk-forward fold "
            f"({config.span_months()} months of history). A pooled "
            "out-of-sample series cannot be built, so no performance claim is "
            "available."
        )


# --------------------------------------------------------------- pooled series


@dataclass(frozen=True)
class FoldReturns:
    """One fold's out-of-sample daily returns, per system.

    Keyed by system name so the ladder's four rungs travel together and cannot
    be misaligned by day when they are pooled.
    """

    fold: Fold
    days: list[Any]
    returns: dict[str, list[float]]

    def __post_init__(self) -> None:
        for system, series in self.returns.items():
            if len(series) != len(self.days):
                raise ValueError(
                    f"fold {self.fold.index}: system {system!r} has "
                    f"{len(series)} returns for {len(self.days)} days"
                )


def pool(fold_returns: Sequence[FoldReturns], system: str) -> list[float]:
    """Concatenate the test windows into one out-of-sample series.

    Protocol §2: each fold trains its own model, so the pooled series contains
    returns from fourteen fitted models. That is intended. The series is the
    out-of-sample record *of the procedure*, which is what the claim concerns,
    rather than of any single fitted model.
    """
    out: list[float] = []
    for fr in sorted(fold_returns, key=lambda f: f.fold.index):
        try:
            out.extend(fr.returns[system])
        except KeyError:
            raise KeyError(
                f"fold {fr.fold.index} has no returns for system {system!r}; "
                f"it has {sorted(fr.returns)}"
            ) from None
    return out


def pooled_days(fold_returns: Sequence[FoldReturns]) -> list[Any]:
    out: list[Any] = []
    for fr in sorted(fold_returns, key=lambda f: f.fold.index):
        out.extend(fr.days)
    if len(set(map(str, out))) != len(out):
        raise ValueError(
            "the pooled out-of-sample series contains a repeated day. Test "
            "windows must not overlap, or every interval computed from this "
            "series is too narrow (EVALUATION_PROTOCOL.md §2)."
        )
    return out


# ------------------------------------------------------------- the comparison


@dataclass(frozen=True)
class Comparison:
    """One ladder comparison. Only M2-vs-B2 carries a verdict worth the name."""

    treatment: str
    control: str
    interval: Interval
    treatment_summary: PerformanceSummary
    control_summary: PerformanceSummary
    is_primary: bool
    fold_sign_count: tuple[int, int] | None = None
    cost_stress_point: float | None = None
    failures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def claims_improvement(self) -> bool:
        return self.is_primary and not self.failures

    @property
    def verdict(self) -> str:
        if not self.is_primary:
            return "no_claim (ladder rung, protocol §6)"
        return "improvement" if not self.failures else "no_claim"

    def summary(self) -> str:
        lines = [
            f"{self.treatment} vs {self.control}: ΔSharpe {self.interval}",
            f"  {self.treatment}: Sharpe {self.treatment_summary.sharpe:+.3f} "
            f"over {self.treatment_summary.n_days} days "
            f"(exposure {self.treatment_summary.exposure:.1%})",
            f"  {self.control}: Sharpe {self.control_summary.sharpe:+.3f} "
            f"over {self.control_summary.n_days} days "
            f"(exposure {self.control_summary.exposure:.1%})",
        ]
        if self.fold_sign_count is not None:
            won, total = self.fold_sign_count
            lines.append(f"  folds won: {won}/{total} (robustness view, no claim)")
        if self.cost_stress_point is not None:
            lines.append(f"  2x cost stress: ΔSharpe {self.cost_stress_point:+.3f}")
        lines.append(f"  verdict: {self.verdict}")
        for reason in self.failures:
            lines.append(f"    - {reason}")
        return "\n".join(lines)

    def to_dict(self, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        row = {
            "treatment": self.treatment,
            "control": self.control,
            "delta_sharpe": self.interval.point,
            "ci_low": self.interval.low,
            "ci_high": self.interval.high,
            "resamples": self.interval.resamples,
            "expected_block": self.interval.expected_block,
            "bootstrap_seed": self.interval.seed,
            "is_primary": self.is_primary,
            "verdict": self.verdict,
            "failures": list(self.failures),
            "cost_stress_delta_sharpe": self.cost_stress_point,
            "folds_won": self.fold_sign_count[0] if self.fold_sign_count else None,
            "folds_total": self.fold_sign_count[1] if self.fold_sign_count else None,
        }
        if provenance:
            row |= {f"run_{k}": v for k, v in provenance.items()}
        return row


def fold_sign_count(
    fold_returns: Sequence[FoldReturns],
    treatment: str,
    control: str,
    *,
    ppy: int = TRADING_DAYS_YEAR,
) -> tuple[int, int]:
    """Folds in which the treatment's Sharpe beat the control's.

    Protocol §6 lists this as a robustness view with no claim attached. A
    single fold is 126 days and carries a standard error near 1.4 on an
    annualised Sharpe, so the count is a shape, not a test.
    """
    won = 0
    total = 0
    for fr in fold_returns:
        t = annualised_sharpe(fr.returns[treatment], periods_per_year=ppy)
        c = annualised_sharpe(fr.returns[control], periods_per_year=ppy)
        if t == t and c == c:  # both defined
            total += 1
            won += int(t > c)
    return won, total


def compare(
    fold_returns: Sequence[FoldReturns],
    *,
    treatment: str,
    control: str,
    config: RunConfig,
    strategy: Strategy | None = None,
    cost_stress_returns: dict[str, list[float]] | None = None,
    resamples: int | None = None,
) -> Comparison:
    """Run one ladder comparison under the locked protocol.

    The three conditions of §4 are evaluated for the primary comparison only.
    A ladder rung (B2 vs B1, M1 vs B2, M2 vs M1) gets the same interval and no
    verdict, because claiming on four comparisons is claiming four times.
    """
    require_performance_claim(config, strategy)
    pooled_days(fold_returns)  # raises if the test windows overlapped

    ppy = periods_per_year(config)
    t_series = pool(fold_returns, treatment)
    c_series = pool(fold_returns, control)

    kwargs: dict[str, Any] = {"seed": config.seed, "periods_per_year": ppy}
    if resamples is not None:
        kwargs["resamples"] = resamples
    interval = paired_sharpe_difference(t_series, c_series, **kwargs)

    is_primary = (treatment, control) == PRIMARY_COMPARISON
    stress_point: float | None = None
    if cost_stress_returns is not None:
        stress_point = annualised_sharpe(
            cost_stress_returns[treatment], periods_per_year=ppy
        ) - annualised_sharpe(cost_stress_returns[control], periods_per_year=ppy)

    failures: list[str] = []
    if is_primary:
        # Condition 1: the interval excludes zero.
        if not interval.excludes_zero:
            failures.append(
                f"95% interval [{interval.low:+.3f}, {interval.high:+.3f}] "
                "includes zero (protocol §4.1)"
            )
        # Condition 2: the materiality floor.
        if interval.point < MATERIALITY_FLOOR:
            failures.append(
                f"point estimate {interval.point:+.3f} is below the "
                f"+{MATERIALITY_FLOOR:.2f} materiality floor (protocol §4.2)"
            )
        # Condition 3: the sign survives 2x costs.
        if stress_point is None:
            failures.append(
                "no 2x cost-stress run supplied; condition 3 cannot be "
                "evaluated and an unevaluated condition is a failed one "
                "(protocol §4.3)"
            )
        elif (stress_point > 0) != (interval.point > 0):
            failures.append(
                f"sign does not survive 2x costs: base {interval.point:+.3f}, "
                f"stressed {stress_point:+.3f} (protocol §4.3)"
            )

    return Comparison(
        treatment=treatment,
        control=control,
        interval=interval,
        treatment_summary=summarise(t_series, system=treatment, periods_per_year=ppy),
        control_summary=summarise(c_series, system=control, periods_per_year=ppy),
        is_primary=is_primary,
        fold_sign_count=fold_sign_count(fold_returns, treatment, control, ppy=ppy),
        cost_stress_point=stress_point,
        failures=tuple(failures),
    )


def ladder(
    fold_returns: Sequence[FoldReturns],
    *,
    config: RunConfig,
    strategy: Strategy | None = None,
    cost_stress_returns: dict[str, list[float]] | None = None,
    resamples: int | None = None,
) -> list[Comparison]:
    """The four-rung ablation of Outline §7, in order, with one primary.

    B1 -> B2 -> M1 -> M2. The rungs isolate what each component adds; only
    M2 vs B2 carries a claim.
    """
    rungs = [("B2", "B1"), ("M1", "B2"), ("M2", "M1"), PRIMARY_COMPARISON]
    return [
        compare(
            fold_returns,
            treatment=t,
            control=c,
            config=config,
            strategy=strategy,
            cost_stress_returns=cost_stress_returns if (t, c) == PRIMARY_COMPARISON else None,
            resamples=resamples,
        )
        for t, c in rungs
    ]
