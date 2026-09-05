"""The feature registry - seam 6, and the record of what was removed and why.

Two jobs, and the second one is the reason this is a registry rather than a
module of functions.

**1. Declared data requirements.** Every feature states what kind of data it
needs: bars, quotes, or chain snapshots. The registry checks that against what
the active provider can actually serve, and raises at *config* time. The
failure this prevents is a run that starts, computes twenty features, and dies
four hours in on the twenty-first because Alpaca serves no chain snapshot
(PRD §3B.6). Options-native features - implied volatility, skew, term
structure - are the concrete case: they are what this project would add after
the course, and they are exactly the ones the current vendor cannot feed.

**2. Dropped features stay in the registry.** A feature that was tested and
removed is recorded here with its reason and the decision that removed it, not
deleted. Deleting it loses the finding: six months from now the absence of a
volume feature looks like an oversight rather than the outcome of a
pre-committed experiment. `dropped()` is the source for the Data Card's feature
reference table, and `test_features.py` asserts that no dropped feature can be
computed by accident.

**The volume verdict.** The feed-transfer experiment ran 2026-09-02 over
101,390 aligned SIP/IEX observations. Pre-committed thresholds, fixed before
the run: keep at Spearman >= 0.70 overall and >= 0.60 in every year, drop below
0.50. The best feature reached 0.785 Pearson but 0.664 Spearman; the primary
reached 0.572. The keep list came back empty, which the rule as written
resolves to DROP. Every volume-derived feature below therefore carries
`status="dropped"`, and `test_features.py::test_no_active_feature_is_volume_derived`
stops one coming back through the side door.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Sequence

from project_beta.config import ConfigError
from project_beta.data.provider import Bar

DataRequirement = Literal["bars", "quotes", "chain_snapshots"]
FeatureStatus = Literal["active", "dropped"]

# What each provider can actually serve, as its adapter behaves rather than as
# its marketing describes. Alpaca's get_quotes and get_chain_snapshot both
# raise NotSupported, so 'bars' is the honest capability set.
PROVIDER_CAPABILITIES: dict[str, frozenset[str]] = {
    "alpaca": frozenset({"bars"}),
}

FeatureFn = Callable[[Sequence[Bar]], list[float | None]]


class FeatureUnavailable(ConfigError):
    """A requested feature needs data the active provider cannot serve.

    A subclass of ConfigError because this is a configuration defect and must
    surface at config time. Raising it at runtime, mid-fold, would be the exact
    failure seam 6 exists to prevent.
    """


@dataclass(frozen=True)
class FeatureSpec:
    """One feature, everything about it that a reader or a run needs to know.

    `derivation` is not a comment. PRD §5.2's acceptance criteria require a
    complete feature reference table with derivation tags; keeping the formula
    beside the function is what makes that table generated rather than
    maintained by hand, and therefore what keeps it true.
    """

    name: str
    requires: DataRequirement
    # Bars of history consumed before this feature has its first defined value.
    # The registry takes the maximum across the active set, and the harness
    # discards that many leading rows. A wrong value here is a leak: it lets a
    # partially-warmed feature into a training window.
    lookback: int
    derivation: str
    rationale: str
    fn: FeatureFn | None = None
    volume_derived: bool = False
    status: FeatureStatus = "active"
    dropped_reason: str | None = None
    # None means every asset class. A named set is how an options-native
    # feature is added later without being computed on equities.
    asset_classes: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.status == "active" and self.fn is None:
            raise ValueError(f"active feature {self.name!r} needs an implementation")
        if self.status == "dropped" and not self.dropped_reason:
            raise ValueError(
                f"dropped feature {self.name!r} must record why. A feature "
                "removed without a reason is indistinguishable from one nobody "
                "got round to writing."
            )
        if self.lookback < 0:
            raise ValueError(f"{self.name}: lookback must be non-negative")

    def serves(self, asset_class: str) -> bool:
        return self.asset_classes is None or asset_class in self.asset_classes


@dataclass(frozen=True)
class FeatureFrame:
    """Computed features, aligned bar for bar with the input.

    Columns carry None wherever a feature is not yet defined - during warmup,
    or where an input was degenerate. None is never filled. The same rule that
    governs missing bars governs missing feature values: a number nobody could
    have computed at the time is not a number the model may train on.
    """

    timestamps: list[datetime]
    columns: dict[str, list[float | None]]
    names: tuple[str, ...]
    warmup: int

    def __len__(self) -> int:
        return len(self.timestamps)

    def is_ready(self, i: int) -> bool:
        """True if every column has a value at this index."""
        if i < self.warmup:
            return False
        return all(self.columns[n][i] is not None for n in self.names)

    def row(self, i: int) -> dict[str, float] | None:
        if not self.is_ready(i):
            return None
        return {n: float(self.columns[n][i]) for n in self.names}  # type: ignore[arg-type]

    def snapshot_id(self, i: int) -> str:
        """The `features_snapshot_id` a CandidateTrade carries (PRD §4.1)."""
        return f"feat_{self.timestamps[i].isoformat()}"

    def ready_indices(self) -> list[int]:
        return [i for i in range(len(self)) if self.is_ready(i)]

    def matrix(self, names: Sequence[str] | None = None) -> tuple[list[list[float]], list[int]]:
        """Ready rows as a dense matrix, with the bar index each row came from.

        The index list is returned rather than discarded because every label,
        every fold boundary and every decision record is keyed on the bar, and
        a matrix that has forgotten which bars it came from is a matrix that
        cannot be joined back without guessing.
        """
        cols = tuple(names) if names is not None else self.names
        rows: list[list[float]] = []
        idx: list[int] = []
        for i in range(len(self)):
            if not self.is_ready(i):
                continue
            rows.append([float(self.columns[c][i]) for c in cols])  # type: ignore[arg-type]
            idx.append(i)
        return rows, idx


class FeatureRegistry:
    """The set of features this project knows about, active and dropped."""

    def __init__(self) -> None:
        self._specs: dict[str, FeatureSpec] = {}

    # ------------------------------------------------------------ population

    def register(self, spec: FeatureSpec) -> FeatureSpec:
        if spec.name in self._specs:
            raise ValueError(f"feature {spec.name!r} is already registered")
        self._specs[spec.name] = spec
        return spec

    def get(self, name: str) -> FeatureSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise KeyError(
                f"unknown feature {name!r}. Registered: "
                f"{sorted(self._specs)}"
            ) from None

    def all(self) -> list[FeatureSpec]:
        return [self._specs[n] for n in sorted(self._specs)]

    def active(self, asset_class: str | None = None) -> list[FeatureSpec]:
        out = [s for s in self.all() if s.status == "active"]
        if asset_class is not None:
            out = [s for s in out if s.serves(asset_class)]
        return out

    def dropped(self) -> list[FeatureSpec]:
        return [s for s in self.all() if s.status == "dropped"]

    def names(self, asset_class: str | None = None) -> tuple[str, ...]:
        return tuple(s.name for s in self.active(asset_class))

    def warmup(self, asset_class: str | None = None) -> int:
        specs = self.active(asset_class)
        return max((s.lookback for s in specs), default=0)

    # ------------------------------------------------------------ validation

    def validate_for(
        self,
        provider: str,
        *,
        asset_class: str = "equity",
        names: Sequence[str] | None = None,
    ) -> tuple[str, ...]:
        """Resolve a feature set against a provider. Raises at config time.

        Returns the resolved names so a caller cannot both validate and then
        compute a different set by accident.
        """
        try:
            capabilities = PROVIDER_CAPABILITIES[provider]
        except KeyError:
            raise FeatureUnavailable(
                f"unknown provider {provider!r}; no capability set is declared "
                f"for it. Known: {sorted(PROVIDER_CAPABILITIES)}"
            ) from None

        if names is None:
            selected = self.active(asset_class)
        else:
            selected = [self.get(n) for n in names]

        problems: list[str] = []
        for spec in selected:
            if spec.status == "dropped":
                problems.append(
                    f"{spec.name}: dropped - {spec.dropped_reason}"
                )
                continue
            if not spec.serves(asset_class):
                problems.append(
                    f"{spec.name}: not defined for asset_class={asset_class!r} "
                    f"(serves {sorted(spec.asset_classes or [])})"
                )
                continue
            if spec.requires not in capabilities:
                problems.append(
                    f"{spec.name}: requires {spec.requires!r}, which provider "
                    f"{provider!r} does not serve (it serves "
                    f"{sorted(capabilities)})"
                )
        if problems:
            raise FeatureUnavailable(
                "feature set cannot be satisfied by this run's provider:\n  "
                + "\n  ".join(problems)
            )
        return tuple(s.name for s in selected)

    # ------------------------------------------------------------- computing

    def compute(
        self,
        bars: Sequence[Bar],
        *,
        provider: str = "alpaca",
        asset_class: str = "equity",
        names: Sequence[str] | None = None,
    ) -> FeatureFrame:
        """Compute a validated feature set over session-filtered bars.

        `bars` must already have passed through `filter_session` (PRD §5.1).
        Nothing here re-filters: doing it in two places is how the two places
        eventually disagree.
        """
        resolved = self.validate_for(provider, asset_class=asset_class, names=names)
        columns: dict[str, list[float | None]] = {}
        for name in resolved:
            spec = self.get(name)
            assert spec.fn is not None  # validate_for rejects dropped specs
            values = spec.fn(bars)
            if len(values) != len(bars):
                raise RuntimeError(
                    f"feature {name!r} returned {len(values)} values for "
                    f"{len(bars)} bars; features must align bar for bar"
                )
            columns[name] = values
        return FeatureFrame(
            timestamps=[b.timestamp for b in bars],
            columns=columns,
            names=resolved,
            warmup=max((self.get(n).lookback for n in resolved), default=0),
        )

    # ------------------------------------------------------------ reporting

    def reference_table(self) -> str:
        """The feature reference table PRD §5.2 requires, generated not typed."""
        lines = [
            "| Feature | Status | Requires | Lookback | Derivation |",
            "|---|---|---|---|---|",
        ]
        for spec in self.all():
            status = spec.status
            if spec.status == "dropped":
                status = f"**dropped** - {spec.dropped_reason}"
            lines.append(
                f"| `{spec.name}` | {status} | {spec.requires} | "
                f"{spec.lookback} | {spec.derivation} |"
            )
        return "\n".join(lines)


REGISTRY = FeatureRegistry()
