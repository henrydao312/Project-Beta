"""Unit tests for the feed-transfer experiment's logic.

The experiment itself needs the network and a live entitlement, so it runs on
Henry's machine and not in CI. That is exactly why its arithmetic is tested
here against synthetic bars: the parts that can be wrong quietly — the RTH
filter, the trailing baselines, the verdict thresholds — must not first be
exercised on a run that takes half an hour and produces a number nobody can
check by eye.

The synthetic feeds are built so the right answer is known in advance: IEX is
SPY volume scaled to ~3% with noise, which is precisely the situation the
scale-free design claims to survive.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "experiments" / "transfer_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("transfer_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tc = _load_module()


def _synthetic(days: int = 40, scale: float = 1.0, seed: int = 0,
               noise: float = 0.0) -> pd.DataFrame:
    """Sessions of 5-minute bars with a U-shaped intraday volume profile."""
    rng = np.random.default_rng(seed)
    rows = []
    day = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)  # 09:30 ET
    for d in range(days):
        start = day + timedelta(days=d)
        if start.weekday() >= 5:
            continue
        for i in range(78):
            # U-shape: heavy at the open and close, light midday.
            shape = 1.0 + 2.5 * ((i / 77 - 0.5) ** 2) * 4
            base = 100_000 * shape * rng.lognormal(0, 0.25)
            vol = base * scale
            if noise:
                vol *= rng.lognormal(0, noise)
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=5 * i),
                    "close": 500.0,
                    "volume": float(vol),
                    "trade_count": int(max(1, vol / 200)),
                }
            )
    return pd.DataFrame(rows)


def test_rth_filter_drops_extended_hours_and_weekends() -> None:
    """60% of SIP bars fall outside the regular session. Letting them into
    feature computation is a quiet source of inflated backtests."""
    df = _synthetic(days=5)
    overnight = df.iloc[:3].copy()
    overnight["timestamp"] = overnight["timestamp"] - timedelta(hours=5)  # pre-market
    weekend = df.iloc[:3].copy()
    weekend["timestamp"] = weekend["timestamp"] + timedelta(days=5)  # Saturday
    padded = pd.concat([df, overnight, weekend], ignore_index=True)
    padded["timestamp"] = pd.to_datetime(padded["timestamp"], utc=True)

    out = tc.to_rth(padded)
    assert len(out) == len(df)
    assert out["et"].dt.dayofweek.max() < 5
    assert out["et"].dt.strftime("%H:%M").min() >= "09:30"
    assert out["et"].dt.strftime("%H:%M").max() <= "15:55"


def test_baselines_exclude_the_current_bar() -> None:
    """A feature normalised by a window containing its own bar is mildly
    self-referential, and on a thin feed that shows up as spurious agreement
    between the feeds rather than as an obvious bug."""
    df = tc.to_rth(_synthetic(days=30))
    feats = tc.build_features(df)
    spike = df.copy()
    idx = len(spike) - 1
    spike.loc[idx, "volume"] = spike["volume"].iloc[idx] * 50
    spiked = tc.build_features(spike)
    # The spike must move its own bar's ratio, not the baseline underneath it.
    assert spiked["vol_ratio"].iloc[idx] > feats["vol_ratio"].iloc[idx] * 10
    assert np.isclose(
        spiked["vol_ratio"].iloc[idx - 1], feats["vol_ratio"].iloc[idx - 1]
    )


def test_scale_free_features_survive_a_thirty_fold_volume_difference() -> None:
    """The design claim, tested directly: IEX carries ~3% of consolidated
    volume, and a scale-free feature should not care."""
    sip = tc.build_features(tc.to_rth(_synthetic(days=60, scale=1.0, seed=1)))
    iex = tc.build_features(tc.to_rth(_synthetic(days=60, scale=0.0316, seed=1)))
    stats = tc.compare(sip, iex)
    assert stats[tc.PRIMARY_FEATURE]["spearman"] > 0.99, stats[tc.PRIMARY_FEATURE]


def test_the_experiment_can_return_drop() -> None:
    """The pre-committed drop decision has to be reachable, or it is decoration.

    Independent noise between the feeds is the situation in which IEX would be
    unrepresentative, and the verdict must say so without being asked twice.
    """
    sip = tc.build_features(tc.to_rth(_synthetic(days=60, scale=1.0, seed=2)))
    iex = tc.build_features(tc.to_rth(_synthetic(days=60, scale=0.0316, seed=99)))
    stats = tc.compare(sip, iex)
    call, keep, _ = tc.verdict(stats)
    assert call == "DROP"
    assert keep == []


def test_thresholds_are_ordered_and_recorded() -> None:
    """If DROP ever exceeded KEEP the verdict function would be unreachable in
    one direction, and nobody would notice from the output."""
    assert tc.DROP_RHO < tc.KEEP_RHO
    assert tc.KEEP_RHO_WORST_YEAR <= tc.KEEP_RHO
    assert tc.PRIMARY_FEATURE in tc.FEATURES


def test_alignment_reports_iex_coverage() -> None:
    """An IEX bar absent where SIP has one is a no-trade interval on a thin
    feed, not a gap. The rate is a Data Card finding in its own right."""
    sip = tc.build_features(tc.to_rth(_synthetic(days=20, seed=3)))
    iex = tc.build_features(tc.to_rth(_synthetic(days=20, seed=3))).iloc[::2]
    stats = tc.compare(sip, iex)
    assert 0.4 < stats["_alignment"]["iex_coverage_of_sip"] < 0.6


@pytest.mark.parametrize("bad_start", [tc.OVERLAP_START - timedelta(days=1)])
def test_the_overlap_floor_is_known(bad_start) -> None:
    """IEX history begins 2021-06-10. Asking for less is asking for nothing."""
    assert tc.OVERLAP_START.isoformat() == "2021-06-10"
    assert bad_start < tc.OVERLAP_START


def test_cache_keys_include_the_requested_range() -> None:
    """A short sanity run must not poison the cache for the full run.

    Keyed on the year alone, two months of 2024 fetched during a smoke test
    would be reused by the real run, which would then analyse two months while
    reporting a year. The failure is silent, which is exactly the class of bug
    this experiment exists to rule out on the feature side.
    """
    from datetime import date

    short = tc._cache_path("sip", date(2024, 1, 2), date(2024, 3, 1))
    full = tc._cache_path("sip", date(2024, 1, 1), date(2024, 12, 31))
    assert short != full
    assert "2024-01-02" in short.name and "2024-03-01" in short.name
