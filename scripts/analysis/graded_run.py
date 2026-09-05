"""The graded equity run: fetch real SIP bars, walk forward, print the ladder.

This is the first time M1 and M2 meet real data. Everything before it was
synthetic, and a synthetic result says nothing about whether the models work -
only that the machinery does not manufacture an answer.

**Run it on macOS, not in the Cowork sandbox.** The sandbox cannot reach
data.alpaca.markets. See the usage block at the bottom of this docstring.

Two phases, separated on purpose:

    fetch   Pull SIP 5-minute bars year by year into data/raw/graded/.
            Cached and resumable: a failure in year eight costs year eight,
            not the whole decade. Nothing here is committed - data/raw/ is
            gitignored, and Alpaca's terms forbid redistributing bars.

    run     Load the cache through the ordinary ingestion path (RTH filter,
            coverage rules, dataset_hash), compute features once, then walk
            forward: fit per fold, choose the threshold on validation, open
            the test window once, replay it at 2x and 3x costs.

The run goes through `ingest()` rather than reading the cache directly, so the
graded dataset is filtered and hashed by exactly the same code as every other
dataset in this project. A separate path here would be a separate set of bugs.

**It also answers the redundancy question**, which is the thing to look at
before deciding anything about M1. B2 already filters on `ma_gap > 0`, and the
regime classifier reads `ma_gap` among its features, so M1 may be re-stating a
condition B2 has already applied. Three diagnostics measure that directly.
They are diagnostics only: nothing here feeds the graded ladder.

Usage, from the repo root, on the Mac:

    source .venv/bin/activate
    set -a && . ./.env && set +a
    python scripts/analysis/graded_run.py --all

For a fast look first, with a non-protocol resample count:

    python scripts/analysis/graded_run.py --all --resamples 500

The headline number must be produced at the protocol's 10,000 resamples
(EVALUATION_PROTOCOL.md §3), which is the default. Anything lower is a preview
and must not be quoted.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from project_beta.config import RunConfig, load_run_config  # noqa: E402
from project_beta.data.alpaca import AlpacaProvider  # noqa: E402
from project_beta.data.pipeline import (  # noqa: E402
    ingest,
    read_parquet,
    write_parquet,
)
from project_beta.data.provider import Bar, ProviderAuthError  # noqa: E402
from project_beta.evaluation.harness import pool  # noqa: E402
from project_beta.evaluation.metrics import summarise  # noqa: E402
from project_beta.evaluation.runner import (  # noqa: E402
    artifacts_of,
    base_folds,
    evaluate,
    stressed_folds,
)
from project_beta.features import REGISTRY  # noqa: E402
from project_beta.models.labels import label_regimes  # noqa: E402
from project_beta.strategy.base import build_strategy  # noqa: E402

CACHE_DIR = REPO_ROOT / "data" / "raw" / "graded"
ARTIFACT_DIR = REPO_ROOT / "artifacts"
DEFAULT_CONFIG = REPO_ROOT / "configs" / "example_backtest.yaml"


# ------------------------------------------------------------------- fetching


def _cache_path(config: RunConfig, year: int) -> Path:
    d = config.data
    # BTC/USD carries a slash, which a path would read as a directory. The same
    # substitution pipeline.store_path already makes, for the same reason.
    symbol = d.symbol.replace("/", "-")
    return CACHE_DIR / f"{symbol}_{d.feed}_{d.timeframe}_{year}.parquet"


def fetch(config: RunConfig, *, force: bool = False) -> None:
    """Pull the decade year by year. Idempotent: existing years are skipped."""
    d = config.data
    provider = AlpacaProvider()
    provider.authenticate()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for year in range(d.start.year, d.end.year + 1):
        lo = max(d.start, date(year, 1, 1))
        hi = min(d.end, date(year, 12, 31))
        if lo > hi:
            continue
        path = _cache_path(config, year)
        if path.exists() and not force:
            print(f"  {year}: cached ({path.stat().st_size // 1024} KB)")
            continue

        started = time.time()
        bars = provider.get_bars(
            d.symbol, d.timeframe, lo, hi, asset_class=d.asset_class, feed=d.feed
        )
        if not bars:
            print(f"  {year}: no bars returned")
            continue
        write_parquet(bars, path)
        print(
            f"  {year}: {len(bars):>7,} bars in {time.time() - started:5.1f}s "
            f"-> {path.name}"
        )


class CachedProvider:
    """Serves the fetched years back to `ingest()` as an ordinary provider.

    A pure reader, like every other provider: no filtering, no repair, no
    gap-filling. That is the pipeline's job, and this exists so the graded
    dataset takes the same validated path as everything else rather than a
    shortcut that skips the session filter.
    """

    name = "alpaca"

    def __init__(self, config: RunConfig) -> None:
        self.config = config

    def get_bars(self, symbol, timeframe, start, end, *, asset_class="equity", feed=None):
        bars: list[Bar] = []
        missing: list[int] = []
        for year in range(start.year, end.year + 1):
            path = _cache_path(self.config, year)
            if not path.exists():
                missing.append(year)
                continue
            bars.extend(read_parquet(path))
        if missing:
            raise SystemExit(
                f"missing cached years {missing}. Run with --fetch first; the "
                "sandbox cannot reach data.alpaca.markets, so this must run on "
                "the Mac with credentials loaded."
            )
        lo = datetime.combine(start, datetime.min.time())
        hi = datetime.combine(end, datetime.max.time())
        return [
            b for b in sorted(bars, key=lambda b: b.timestamp)
            if lo.date() <= b.timestamp.date() <= hi.date()
        ]

    def authenticate(self) -> None:
        return None


# ---------------------------------------------------------------- diagnostics


def redundancy_report(bars, frame, config: RunConfig, strategy) -> dict:
    """Does M1 re-state a filter B2 has already applied?

    Three measurements, each answering a different form of the question:

      permitted_rate   of the candidates B2 actually produced, what fraction
                       does the regime gate let through. Near 1.0 means the
                       gate is not filtering anything.

      agreement        how often M1's predicted trend label matches B2's own
                       `ma_gap > 0` condition on the same bar. Near 1.0 means
                       the classifier has learned to restate the rule.

      would_reject     of the candidates B2 *would* have produced with its
                       trend filter removed, how many M1 blocks. This is the
                       one that separates "the classifier is useless" from
                       "the classifier had nothing left to reject". A high
                       number here with a high permitted_rate above means the
                       information is real and B2 simply got there first.

    Diagnostic only. Nothing here touches the graded ladder.
    """
    from project_beta.evaluation.folds import generate_folds
    from project_beta.evaluation.runner import _index_ranges
    from project_beta.models.regime import RegimeModel

    fold = generate_folds(config)[0]
    (train_lo, train_hi), _, (test_lo, test_hi) = _index_ranges(bars, fold)
    labels = label_regimes(
        bars, frame,
        horizon=config.models.labels.horizon_bars,
        trend_k=config.models.labels.trend_k,
        vol_k=config.models.labels.vol_k,
    )
    model = RegimeModel.fit(
        frame, labels,
        range(train_lo, max(train_lo, train_hi - config.models.labels.horizon_bars)),
        l2=config.models.regime_l2,
    )
    permitted = set(config.models.permitted_regimes)

    def label_at(i: int) -> str | None:
        row = frame.row(i)
        if row is None:
            return None
        return model.predict_row([row[n] for n in frame.names])["label"]

    narrow = [
        c for c in strategy.generate_candidates(frame, bars, config)
        if test_lo <= c.bar_index < test_hi
    ]
    wide_config = replace(
        config,
        strategy=replace(
            config.strategy,
            params={**config.strategy.params, "min_ma_gap": -1e9},
        ),
    )
    wide = [
        c for c in build_strategy(wide_config).generate_candidates(frame, bars, wide_config)
        if test_lo <= c.bar_index < test_hi
    ]

    narrow_labels = [label_at(c.bar_index) for c in narrow]
    wide_labels = [label_at(c.bar_index) for c in wide]
    n_permit = sum(1 for lab in narrow_labels if lab in permitted)

    agree = total = 0
    for i in range(test_lo, test_hi):
        row = frame.row(i)
        lab = label_at(i)
        if row is None or lab is None:
            continue
        total += 1
        agree += int((lab in permitted) == (row["ma_gap"] > config.strategy.params.get("min_ma_gap", 0.0)))

    return {
        "b2_candidates": len(narrow),
        "m1_permitted": n_permit,
        "permitted_rate": n_permit / len(narrow) if narrow else None,
        "label_vs_ma_gap_agreement": agree / total if total else None,
        "candidates_without_b2_trend_filter": len(wide),
        "of_those_m1_would_reject": sum(1 for lab in wide_labels if lab not in permitted),
    }


# ---------------------------------------------------------------------- run


def run(config: RunConfig, *, resamples: int, skip_diagnostics: bool) -> dict:
    started = time.time()
    result = ingest(config, CachedProvider(config), store=True)
    bars = result.bars
    print(result.report.summary())
    print(f"\ndataset_hash {result.report.dataset_hash}")
    print(f"stored       {result.path}")

    config = replace(config, data=replace(config.data, dataset_hash=result.report.dataset_hash))
    frame = REGISTRY.compute(bars)
    strategy = build_strategy(config)
    print(f"\n{len(bars):,} RTH bars, {len(frame.names)} features, warmup {frame.warmup}")
    print(f"folds {config.fold_count()}   config_hash {config.config_hash()}")

    diagnostics = {}
    if not skip_diagnostics:
        print("\n--- redundancy diagnostics (fold 0 test window) ---")
        diagnostics = redundancy_report(bars, frame, config, strategy)
        for k, v in diagnostics.items():
            print(f"  {k:36s} {v if not isinstance(v, float) else f'{v:.3f}'}")

    print(f"\n--- walk-forward, {resamples:,} resamples ---")
    comparisons, runs = evaluate(bars, frame, config, strategy, resamples=resamples)
    if not runs:
        raise SystemExit("no folds ran; nothing to report")

    folds = base_folds(runs)
    print()
    for art in artifacts_of(runs):
        print(
            f"  fold {art.fold.index:>2} {art.fold.test_start} to {art.fold.test_end}"
            f"  train_rows={art.train_rows:>4}  val_trades={art.validation_rows:>4}"
            f"  threshold={art.threshold:.3f}  labels={art.label_distribution}"
        )

    print()
    summaries = {}
    for system in ("B1", "B2", "M1", "M2"):
        m = summarise(pool(folds, system), system=system)
        summaries[system] = m
        print(
            f"  {system}: sharpe={m.sharpe:+.3f}  maxDD={m.max_drawdown:6.2%}  "
            f"exposure={m.exposure:6.1%}  n={m.n_days}"
        )

    print()
    for factor in (2.0, 3.0):
        sf = stressed_folds(runs, factor)
        line = "  ".join(
            f"{s}={summarise(pool(sf, s), system=s).sharpe:+.3f}"
            for s in ("B2", "M1", "M2")
        )
        print(f"  {factor:.0f}x costs: {line}")

    print()
    for c in comparisons:
        print(c.summary())
        print()

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "provenance": config.provenance(),
        "dataset_hash": result.report.dataset_hash,
        "n_bars": len(bars),
        "n_folds": len(runs),
        "resamples": resamples,
        "redundancy": diagnostics,
        "summaries": {k: v.to_dict() for k, v in summaries.items()},
        "comparisons": [c.to_dict(config.provenance()) for c in comparisons],
        "folds": [a.provenance() for a in artifacts_of(runs)],
        "elapsed_seconds": round(time.time() - started, 1),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACT_DIR / f"graded_run_{config.config_hash()}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(f"results written to {out.relative_to(REPO_ROOT)}")
    print(f"elapsed {payload['elapsed_seconds']}s")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fetch", action="store_true", help="fetch bars only")
    parser.add_argument("--run", action="store_true", help="analyse cached bars only")
    parser.add_argument("--all", action="store_true", help="fetch then run")
    parser.add_argument("--force-fetch", action="store_true", help="ignore the cache")
    parser.add_argument(
        "--resamples", type=int, default=10_000,
        help="bootstrap resamples; 10,000 is the protocol figure and the default",
    )
    parser.add_argument("--skip-diagnostics", action="store_true")
    args = parser.parse_args(argv)

    if not (args.fetch or args.run or args.all):
        parser.error("choose one of --fetch, --run, --all")

    config = load_run_config(args.config)
    print(f"config {args.config.name}  {config.run_id}  [{config.provenance()['tier']}]")
    print(f"{config.data.symbol} {config.data.timeframe} {config.data.feed} "
          f"{config.data.start} to {config.data.end}\n")

    if args.fetch or args.all:
        try:
            fetch(config, force=args.force_fetch)
        except ProviderAuthError as exc:
            raise SystemExit(
                f"credentials: {exc}\n"
                "Load them first:  set -a && . ./.env && set +a"
            ) from exc

    if args.run or args.all:
        if args.resamples != 10_000:
            print(
                f"\nNOTE: {args.resamples:,} resamples is a preview. The graded "
                "figure requires 10,000 (EVALUATION_PROTOCOL.md §3).\n"
            )
        run(config, resamples=args.resamples, skip_diagnostics=args.skip_diagnostics)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
