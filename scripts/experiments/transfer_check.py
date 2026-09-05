"""SIP/IEX feed-transfer experiment. Outline §5.2, PRD §5.2 AC.

THE PROBLEM. The graded backtest trains on SIP consolidated bars. The live
paper loop reads IEX, which carries a median 3.16% of consolidated volume
(2.79-3.78% across six sessions, measured 2026-08-30 - structural, not noise).
A feature built on absolute volume would therefore train on values roughly
thirty times larger than it meets at inference and fail silently on deployment,
producing a system that backtests well and trades badly for a reason nothing in
the results would reveal.

THE DESIGN RESPONSE. Every volume-derived feature is scale-free: a ratio or a
standardised score against a trailing window on the same feed, never a raw
count. That is a design decision, and a design decision is an assumption until
somebody measures it.

WHAT THIS SCRIPT DOES. Computes the scale-free volume features from both feeds
over the 2021-2026 overlap, aligns them bar by bar, and reports how closely
they agree. The thresholds below were fixed BEFORE the first run, which is the
only thing that stops the verdict being chosen after seeing the answer. If you
change them, change them in a commit of their own with a decision-log entry, so
the change is visible rather than absorbed.

PUBLICATION SAFETY. The artifact this writes is assembled field by field from
computed scalars: correlations, rank correlations, KS statistics, counts, and
quantiles of standardised (unitless) features. Raw bars and per-session volume
never enter it, because nothing in the writer can reach them. Cached bars live
under data/raw/, which is gitignored. See Outline §20.5, and the incident on
2026-09-01 that made this paragraph necessary.

    # sanity pass first, two months, a few hundred requests
    python scripts/experiments/transfer_check.py --start 2024-01-02 --end 2024-03-01

    # the real run
    python scripts/experiments/transfer_check.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from project_beta.data.alpaca import AlpacaProvider
from project_beta.data.provider import ProviderAuthError

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "raw" / "transfer_check"
ARTIFACT_DIR = REPO_ROOT / "artifacts"

SYMBOL = "SPY"
TIMEFRAME = "5Min"

# The overlap. IEX history begins 2021-06-10; SIP recent data is not entitled
# on the Basic tier, so the window stops short of today rather than discovering
# that as a 403 two hours into a fetch.
OVERLAP_START = date(2021, 6, 10)
DEFAULT_END = date.today() - timedelta(days=3)

# Regular session, US Eastern. Applied before any feature is computed: 60% of
# SIP bars fall outside it and behave nothing like the regular session.
RTH_START = "09:30"
RTH_END = "15:55" # last 5-minute bar opens at 15:55 and closes the session

SESSION_BARS = 78
TOD_LOOKBACK_SESSIONS = 20

# --------------------------------------------------------------------------
# PRE-COMMITTED DECISION THRESHOLDS. Fixed 2026-09-02, before the first run.
# --------------------------------------------------------------------------
# The primary feature is vol_tod: volume against the median for the same
# time-of-day slot over the trailing 20 sessions. It is primary because
# intraday volume has a pronounced U-shape, and any scale-free feature that
# ignores time of day mostly measures the clock rather than the market.
PRIMARY_FEATURE = "vol_tod"
KEEP_RHO = 0.70 # Spearman over the full overlap, AND
KEEP_RHO_WORST_YEAR = 0.60 # in every calendar year, so one good year cannot carry it
DROP_RHO = 0.50


def _cache_path(feed: str, lo: date, hi: date) -> Path:
    """Cache key includes the requested range, not just the year.

    Keying on the year alone was a silent-truncation bug: a short sanity run
    over two months of 2024 would write sip_2024.parquet holding two months,
    and the full run would then reuse it and analyse two months while
    reporting a year. Wrong quietly, which is the failure mode this whole
    script exists to prevent elsewhere.
    """
    return CACHE_DIR / f"{feed}_{lo.isoformat()}_{hi.isoformat()}.parquet"


def fetch_year(provider: AlpacaProvider, feed: str, year: int,
               start: date, end: date) -> pd.DataFrame:
    """One calendar year of bars, cached. Fetching is chunked by year so a
    failure at 90% costs one year rather than the whole run."""
    lo = max(start, date(year, 1, 1))
    hi = min(end, date(year, 12, 31))
    if lo > hi:
        return pd.DataFrame()

    path = _cache_path(feed, lo, hi)
    if path.exists():
        return pd.read_parquet(path)

    bars = provider.get_bars(SYMBOL, TIMEFRAME, lo, hi, asset_class="equity", feed=feed)
    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
            "trade_count": [b.trade_count for b in bars],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def load_feed(provider: AlpacaProvider, feed: str,
              start: date, end: date) -> pd.DataFrame:
    frames = [
        fetch_year(provider, feed, y, start, end)
        for y in range(start.year, end.year + 1)
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        raise SystemExit(f"no bars returned for feed={feed}")
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def to_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to the regular session, in Eastern time, before any feature."""
    out = df.copy()
    out["et"] = out["timestamp"].dt.tz_convert("America/New_York")
    out = out[out["et"].dt.dayofweek < 5]
    out = out.set_index("et").between_time(RTH_START, RTH_END).reset_index()
    out["session"] = out["et"].dt.date
    out["slot"] = out["et"].dt.strftime("%H:%M")
    return out.reset_index(drop=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Scale-free volume features only.

    Every baseline is trailing and shifted by one bar. A feature normalised by
    a window that includes its own bar is mildly self-referential, and on a
    thin feed that shows up as spurious agreement between the feeds rather than
    as an obvious bug.
    """
    out = df[["et", "session", "slot"]].copy()
    v = df["volume"].astype(float)
    out["volume"] = v
    prior = v.shift(1)

    med = prior.rolling(SESSION_BARS, min_periods=SESSION_BARS // 2).median()
    mean = prior.rolling(SESSION_BARS, min_periods=SESSION_BARS // 2).mean()
    std = prior.rolling(SESSION_BARS, min_periods=SESSION_BARS // 2).std()

    out["vol_ratio"] = v / med.replace(0, np.nan)
    out["vol_z"] = (v - mean) / std.replace(0, np.nan)

    # Time-of-day baseline: the median volume in this same slot over the
    # trailing N sessions, excluding today. Intraday volume is U-shaped, and a
    # feature that ignores that mostly reports the time.
    by_slot = df.assign(volume=v).pivot_table(
        index="session", columns="slot", values="volume", aggfunc="sum"
    )
    tod_med = by_slot.shift(1).rolling(TOD_LOOKBACK_SESSIONS, min_periods=5).median()
    tod_long = tod_med.stack(future_stack=True).rename("tod_med").reset_index()
    out = out.merge(tod_long, on=["session", "slot"], how="left")
    # Compute from out's own volume column rather than from a positional array:
    # a merge that ever stopped preserving left order would otherwise pair each
    # bar with someone else's baseline, silently.
    out["vol_tod"] = out["volume"] / out["tod_med"].replace(0, np.nan)
    out = out.drop(columns=["tod_med", "volume"])

    if df["trade_count"].notna().any():
        n = df["trade_count"].astype(float)
        n_med = n.shift(1).rolling(SESSION_BARS, min_periods=SESSION_BARS // 2).median()
        out["trades_ratio"] = n / n_med.replace(0, np.nan)

    return out


FEATURES = ["vol_tod", "vol_ratio", "vol_z", "trades_ratio"]


def _spearman(a: pd.Series, b: pd.Series) -> float:
    """Rank correlation, computed as Pearson on ranks.

    pandas routes its own spearman option through scipy, and scipy is a large
    dependency to add for one line of arithmetic. Spearman is Pearson on ranks
    by definition, so it is written out here for the same reason the KS
    statistic below is.
    """
    ra = a.rank().to_numpy()
    rb = b.rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def _ks_statistic(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample KS statistic, written out to avoid a scipy dependency."""
    grid = np.sort(np.unique(np.concatenate([a, b])))
    ca = np.searchsorted(np.sort(a), grid, side="right") / a.size
    cb = np.searchsorted(np.sort(b), grid, side="right") / b.size
    return float(np.max(np.abs(ca - cb)))


def compare(sip: pd.DataFrame, iex: pd.DataFrame) -> dict:
    merged = sip.merge(iex, on="et", suffixes=("_sip", "_iex"))
    stats: dict = {}

    for feat in FEATURES:
        cs, ci = f"{feat}_sip", f"{feat}_iex"
        if cs not in merged or ci not in merged:
            continue
        pair = merged[["et", cs, ci]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(pair) < 500:
            stats[feat] = {"n": len(pair), "note": "too few aligned bars"}
            continue

        a = pair[cs].to_numpy()
        b = pair[ci].to_numpy()
        per_year = {
            str(int(y)): round(_spearman(g[cs], g[ci]), 4)
            for y, g in pair.groupby(pair["et"].dt.year)
            if len(g) >= 200
        }
        stats[feat] = {
            "n": len(pair),
            "pearson": round(float(np.corrcoef(a, b)[0, 1]), 4),
            "spearman": round(_spearman(pair[cs], pair[ci]), 4),
            "ks_statistic": round(_ks_statistic(a, b), 4),
            "spearman_by_year": per_year,
            "worst_year_spearman": round(min(per_year.values()), 4) if per_year else None,
            # Quantiles of the standardised feature: unitless by construction,
            # so they describe shape without carrying vendor volume.
            "standardised_quantiles": {
                "sip": [round(float(x), 4) for x in np.quantile(
                    (a - a.mean()) / a.std(), [0.01, 0.25, 0.5, 0.75, 0.99])],
                "iex": [round(float(x), 4) for x in np.quantile(
                    (b - b.mean()) / b.std(), [0.01, 0.25, 0.5, 0.75, 0.99])],
            },
        }

    stats["_alignment"] = {
        "sip_bars": len(sip),
        "iex_bars": len(iex),
        "aligned_bars": len(merged),
        # An IEX bar absent where SIP has one is a no-trade interval on a feed
        # carrying ~3% of volume, not a gap in the data. Reported because the
        # rate itself is a finding for the Data Card.
        "iex_coverage_of_sip": round(len(merged) / max(len(sip), 1), 4),
    }
    return stats


def verdict(stats: dict) -> tuple[str, list[str], str]:
    primary = stats.get(PRIMARY_FEATURE, {})
    rho = primary.get("spearman")
    worst = primary.get("worst_year_spearman")

    if rho is None:
        return "INCONCLUSIVE", [], "primary feature could not be computed"

    if rho >= KEEP_RHO and (worst is None or worst >= KEEP_RHO_WORST_YEAR):
        keep = [
            f for f in FEATURES
            if stats.get(f, {}).get("spearman", 0) >= KEEP_RHO
        ]
        return (
            "KEEP",
            keep,
            f"{PRIMARY_FEATURE} agrees across feeds (rho={rho}, worst year "
            f"{worst}). Publish the correlation in the Data Card and every "
            f"Model Card. Features below the threshold are still dropped.",
        )

    if rho < DROP_RHO:
        return (
            "DROP",
            [],
            f"{PRIMARY_FEATURE} rho={rho} is below the pre-committed floor of "
            f"{DROP_RHO}. Drop volume-derived features entirely. The Model Card "
            f"records that IEX proved unrepresentative of consolidated volume. "
            f"This was decided before the number was known.",
        )

    keep = [f for f in FEATURES if stats.get(f, {}).get("spearman", 0) >= KEEP_RHO]
    return (
        "PARTIAL",
        keep,
        f"{PRIMARY_FEATURE} rho={rho} sits between {DROP_RHO} and {KEEP_RHO}. "
        f"Keep only features clearing {KEEP_RHO}; if that list is empty, treat "
        f"this as DROP. Record the ambiguity rather than resolving it by taste.",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=date.fromisoformat, default=OVERLAP_START)
    ap.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END)
    ap.add_argument("--out", type=Path, default=ARTIFACT_DIR)
    args = ap.parse_args()

    if args.start < OVERLAP_START:
        raise SystemExit(f"IEX history begins {OVERLAP_START}; nothing before it.")

    try:
        provider = AlpacaProvider()
        provider.authenticate()
    except ProviderAuthError as exc:
        raise SystemExit(f"credentials: {exc}") from exc

    print(f"window {args.start} to {args.end}")
    frames = {}
    for feed in ("sip", "iex"):
        print(f" fetching {feed} ...", flush=True)
        raw = load_feed(provider, feed, args.start, args.end)
        rth = to_rth(raw)
        print(f" {len(raw):,} bars, {len(rth):,} after the RTH filter")
        frames[feed] = build_features(rth)

    stats = compare(frames["sip"], frames["iex"])
    call, keep, rationale = verdict(stats)

    artifact = {
        "experiment": "sip_iex_feed_transfer",
        "spec": "Outline §5.2",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "session": "rth_only",
        "window": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "thresholds_precommitted": {
            "primary_feature": PRIMARY_FEATURE,
            "keep_spearman": KEEP_RHO,
            "keep_worst_year_spearman": KEEP_RHO_WORST_YEAR,
            "drop_spearman": DROP_RHO,
            "fixed_on": "2026-09-02",
        },
        "statistics": stats,
        "verdict": call,
        "features_retained": keep,
        "rationale": rationale,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        json.dumps(artifact["window"], sort_keys=True).encode()
    ).hexdigest()[:8]
    path = args.out / f"transfer_check_{digest}.json"
    path.write_text(json.dumps(artifact, indent=2))

    print()
    for feat in FEATURES:
        s = stats.get(feat)
        if not s or "spearman" not in s:
            continue
        marker = " <- primary" if feat == PRIMARY_FEATURE else ""
        print(f" {feat:<14} n={s['n']:>7,} pearson={s['pearson']:>6} "
              f"spearman={s['spearman']:>6} worst yr={s['worst_year_spearman']}"
              f" KS={s['ks_statistic']}{marker}")
    a = stats["_alignment"]
    print(f"\n IEX bars present where SIP has one: {a['iex_coverage_of_sip']:.1%}")
    print(f"\n VERDICT: {call}")
    print(f" {rationale}")
    print(f"\n artifact: {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
