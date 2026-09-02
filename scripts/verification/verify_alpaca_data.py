#!/usr/bin/env python3
"""
PROJECT BETA — Week 1 Alpaca market-data verification
=====================================================

Answers the four open questions in Decision_Tracker.md in one run:

  Q1  How far back can 5-minute SPY bars actually be retrieved?
  Q2  Does the "latest 15 minutes" restriction bite?  (THE ONE THAT MATTERS —
      it decides whether the Week 9 live paper loop is viable on the free tier.)
  Q3  How distorted is IEX volume vs. consolidated volume?
      (Decides whether volume-derived features survive — Outline §5.2.)
  Q4  What does the gap / session-coverage profile look like?

Usage
-----
    export APCA_API_KEY_ID=...          # paper keys are fine, and preferred
    export APCA_API_SECRET_KEY=...
    python verify_alpaca_data.py

    # optional extras
    python verify_alpaca_data.py --stream     # definitive real-time check (needs `websockets`)
    python verify_alpaca_data.py --feed sip   # probe whether SIP is entitled on this account

Dependencies: requests (required). yfinance (optional, for Q3).
              websockets (optional, for --stream).

Nothing is written anywhere except ./alpaca_verification_report.json.
Keys are read from the environment and never printed or stored.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

# Alpaca versions its data APIs per asset class. Equities are v2; crypto and
# options are NOT, and hitting them under /v2 returns a bare 404 that looks
# exactly like "no data for this account" — an earlier run of this script
# reported crypto as unavailable for that reason. Keep these separate.
DATA_ROOT = "https://data.alpaca.markets/v2"
CRYPTO_ROOT = "https://data.alpaca.markets/v1beta3"
OPTIONS_ROOT = "https://data.alpaca.markets/v1beta1"
SYMBOL = "SPY"
TIMEFRAME = "5Min"
BARS_PER_RTH_SESSION = 78  # 09:30–16:00 ET = 6.5h = 78 five-minute bars

report: dict = {"symbol": SYMBOL, "timeframe": TIMEFRAME,
                "run_at_utc": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------- plumbing

def auth_headers() -> dict:
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your environment.")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def get(path: str, params: dict, headers: dict,
        root: str = DATA_ROOT) -> tuple[int, dict]:
    """Single GET. Returns (status_code, json_or_error).

    Never raises: a network/proxy/DNS failure comes back as status 0 with a
    message, so one bad probe degrades that section instead of killing the run.

    `root` selects the API version — see the note on CRYPTO_ROOT/OPTIONS_ROOT.
    """
    try:
        r = requests.get(f"{root}{path}", params=params,
                         headers=headers, timeout=30)
    except requests.RequestException as exc:
        return 0, {"raw": f"network error: {exc.__class__.__name__}: {exc}"}
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:500]}
    return r.status_code, body


def fetch_bars(start: str, end: str, headers: dict, feed: str = "iex",
               limit: int = 10000, max_pages: int = 20) -> tuple[list, str | None]:
    """Paginated bar fetch. Returns (bars, error_message)."""
    bars, page_token, pages = [], None, 0
    while pages < max_pages:
        params = {"symbols": SYMBOL, "timeframe": TIMEFRAME, "start": start,
                  "end": end, "limit": limit, "feed": feed, "adjustment": "raw"}
        if page_token:
            params["page_token"] = page_token
        status, body = get("/stocks/bars", params, headers)
        if status != 200:
            msg = body.get("message") or body.get("raw") or str(body)
            return bars, f"HTTP {status}: {msg}"
        bars.extend(body.get("bars", {}).get(SYMBOL, []) or [])
        page_token = body.get("next_page_token")
        pages += 1
        if not page_token:
            break
    return bars, None


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def hr(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


# ------------------------------------------------------- Q1: history depth

def q1_history_depth(headers: dict, feed: str) -> None:
    hr("Q1  How far back do 5-minute bars actually go?")
    print("Probing one mid-month trading week per year (oldest first).\n")

    earliest, per_year = None, {}
    for year in range(2015, datetime.now(timezone.utc).year + 1):
        start = f"{year}-06-10T00:00:00Z"
        end = f"{year}-06-17T00:00:00Z"
        bars, err = fetch_bars(start, end, headers, feed=feed, max_pages=2)
        if err:
            per_year[year] = {"bars": 0, "error": err}
            print(f"  {year}   ERROR   {err}")
            continue
        per_year[year] = {"bars": len(bars)}
        if bars:
            first = parse_ts(bars[0]["t"]).isoformat()
            per_year[year]["first_bar"] = first
            if earliest is None:
                earliest = first
            print(f"  {year}   {len(bars):>6,} bars   first: {first}")
        else:
            print(f"  {year}   {'0':>6} bars   (no data returned)")

    report["q1_history"] = {"earliest_bar_seen": earliest, "by_year": per_year}
    print(f"\n  → Earliest 5-minute bar retrieved: {earliest or 'NONE'}")
    if earliest:
        years = (datetime.now(timezone.utc) - parse_ts(earliest)).days / 365.25
        print(f"  → Usable history: ~{years:.1f} years")
        print("  → Set RunConfig data.start and re-derive the walk-forward folds from this.")


# --------------------------------------------- Q2: recency / the 15-min rule

def q2_recency(headers: dict, feed: str) -> None:
    hr("Q2  Does the 15-minute restriction bite?  ** THE DECISIVE ONE **")
    print("If REST history and the latest-trade endpoint are both ~15+ min stale,")
    print("a 5-minute-bar live loop would be acting ~3 bars late, and Milestone 3")
    print("(Week 9 alpha) needs a different data tier or a longer live bar.\n")

    now = datetime.now(timezone.utc)
    findings = {}

    # (a) most recent bar from the historical/REST endpoint
    start = (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bars, err = fetch_bars(start, now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           headers, feed=feed, max_pages=5)
    if err:
        print(f"  REST bars: ERROR — {err}")
        findings["rest_bars"] = {"error": err}
    elif bars:
        last = parse_ts(bars[-1]["t"])
        lag_min = (now - last).total_seconds() / 60
        findings["rest_bars"] = {"last_bar_utc": last.isoformat(),
                                 "lag_minutes": round(lag_min, 1)}
        print(f"  REST /stocks/bars   last bar {last.isoformat()}  →  {lag_min:.1f} min old")
    else:
        print("  REST bars: none returned in the last 5 days (market closed for a while?)")
        findings["rest_bars"] = {"bars": 0}

    # (b) latest trade + latest quote — the real-time surface
    for name, path in (("latest trade", f"/stocks/{SYMBOL}/trades/latest"),
                       ("latest quote", f"/stocks/{SYMBOL}/quotes/latest")):
        status, body = get(path, {"feed": feed}, headers)
        if status != 200:
            msg = body.get("message") or str(body)[:200]
            print(f"  {name:<14} HTTP {status} — {msg}")
            findings[name.replace(' ', '_')] = {"error": f"HTTP {status}: {msg}"}
            continue
        payload = body.get("trade") or body.get("quote") or {}
        ts = payload.get("t")
        if not ts:
            findings[name.replace(' ', '_')] = {"error": "no timestamp in payload"}
            continue
        lag_min = (now - parse_ts(ts)).total_seconds() / 60
        findings[name.replace(' ', '_')] = {"ts_utc": ts, "lag_minutes": round(lag_min, 1)}
        print(f"  {name:<14} {ts}  →  {lag_min:.1f} min old")

    report["q2_recency"] = findings
    print("\n  → INTERPRETING THIS: run it during regular market hours (09:30–16:00 ET).")
    print("    Lags under ~1 min  = real-time; the Week 9 live loop is fine on this tier.")
    print("    Lags around 15 min = the restriction applies; see PRD §5.9 mitigations.")
    print("    Outside market hours the lag is meaningless — rerun when open.")


# ------------------------------------------------ Q2b: definitive stream test

def q2b_stream(feed: str) -> None:
    hr("Q2b  Real-time stream check (definitive)")
    try:
        import asyncio
        import websockets  # type: ignore
    except ImportError:
        print("  Skipped — pip install websockets to run this.")
        return

    key = os.environ["APCA_API_KEY_ID"]
    secret = os.environ["APCA_API_SECRET_KEY"]
    url = f"wss://stream.data.alpaca.markets/v2/{feed}"

    async def run() -> None:
        try:
            async with websockets.connect(url, open_timeout=15) as ws:
                await ws.recv()  # connection ack
                await ws.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
                auth = json.loads(await ws.recv())
                print(f"  auth: {auth}")
                await ws.send(json.dumps({"action": "subscribe", "bars": [SYMBOL],
                                          "trades": [SYMBOL]}))
                print(f"  subscribed; listening 45s for live {SYMBOL} messages...\n")
                deadline = datetime.now(timezone.utc) + timedelta(seconds=45)
                seen = 0
                while datetime.now(timezone.utc) < deadline:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    except asyncio.TimeoutError:
                        continue
                    for m in msg if isinstance(msg, list) else [msg]:
                        if m.get("T") in ("b", "t") and m.get("S") == SYMBOL:
                            lag = (datetime.now(timezone.utc)
                                   - parse_ts(m["t"])).total_seconds()
                            print(f"    {m['T']} @ {m['t']}  →  {lag:.1f}s old")
                            seen += 1
                            if seen >= 5:
                                report["q2b_stream"] = {"messages_seen": seen,
                                                        "last_lag_seconds": round(lag, 1)}
                                return
                report["q2b_stream"] = {"messages_seen": seen}
                if not seen:
                    print("    No messages. Market closed, or this feed isn't entitled.")
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            print(f"  Stream error: {exc}")
            report["q2b_stream"] = {"error": str(exc)}

    asyncio.run(run())


# ------------------------------------------------- Q3: IEX volume distortion

def q3_volume(headers: dict) -> None:
    hr("Q3  How distorted is IEX volume vs. consolidated volume?")
    print("Volume deltas, VWAP distance and volume confirmation are volume-derived")
    print("features (Outline §5.2). If IEX carries a small share of true volume,")
    print("those features are computed from a biased sample.\n")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=10)
    bars, err = fetch_bars(start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           headers, feed="iex", max_pages=10)
    if err or not bars:
        print(f"  Could not fetch IEX bars: {err or 'none returned'}")
        return

    daily = defaultdict(int)
    for b in bars:
        daily[parse_ts(b["t"]).date().isoformat()] += int(b.get("v", 0))

    print("  IEX volume by day (sum of 5-minute bars):")
    for day in sorted(daily):
        print(f"    {day}   {daily[day]:>14,}")

    result = {"iex_daily_volume": dict(daily)}

    try:
        import yfinance as yf  # type: ignore
        ref = yf.Ticker(SYMBOL).history(start=start.date().isoformat(),
                                        end=end.date().isoformat())
        ratios = []
        print("\n  vs. consolidated daily volume (yfinance reference):")
        for day in sorted(daily):
            match = ref[ref.index.strftime("%Y-%m-%d") == day]
            if match.empty:
                continue
            consolidated = int(match["Volume"].iloc[0])
            if consolidated:
                share = 100 * daily[day] / consolidated
                ratios.append(share)
                print(f"    {day}   IEX {daily[day]:>12,}  /  "
                      f"consolidated {consolidated:>13,}  =  {share:5.2f}%")
        if ratios:
            med = statistics.median(ratios)
            result["iex_share_pct_median"] = round(med, 2)
            result["iex_share_pct_all"] = [round(r, 2) for r in ratios]
            print(f"\n  → Median IEX share of consolidated volume: {med:.2f}%")
            print("  → Read this as: your volume features see roughly this fraction of")
            print("    real market activity. Decide per Outline §5.2 — report the")
            print("    limitation prominently, or drop volume features and say why.")
    except ImportError:
        print("\n  yfinance not installed — skipping the consolidated comparison.")
        print("  pip install yfinance, or compare these totals against any")
        print("  consolidated source you trust for the same dates.")

    report["q3_volume"] = result


# --------------------------------------------------- Q4: coverage and gaps

def q4_coverage(headers: dict, feed: str) -> None:
    hr("Q4  Session coverage and gap profile")
    print("Sampling ~60 days of 5-minute bars to characterise completeness.\n")

    end = datetime.now(timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=60)
    bars, err = fetch_bars(start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           headers, feed=feed, max_pages=20)
    if err or not bars:
        print(f"  Could not fetch bars: {err or 'none returned'}")
        return

    per_day = defaultdict(list)
    for b in bars:
        per_day[parse_ts(b["t"]).date().isoformat()].append(parse_ts(b["t"]))

    counts = {d: len(ts) for d, ts in per_day.items()}
    dupes = {d: len(ts) - len(set(ts)) for d, ts in per_day.items() if len(ts) != len(set(ts))}
    full = sum(1 for c in counts.values() if c >= BARS_PER_RTH_SESSION)
    thin = {d: c for d, c in counts.items() if c < BARS_PER_RTH_SESSION * 0.9}

    print(f"  Trading days with bars     : {len(counts)}")
    print(f"  Days with >= {BARS_PER_RTH_SESSION} bars (full RTH): {full}")
    print(f"  Days below 90% coverage    : {len(thin)}")
    print(f"  Days with duplicate stamps : {len(dupes)}")
    if counts:
        vals = sorted(counts.values())
        print(f"  Bars/day  min {vals[0]}   median {statistics.median(vals):.0f}   max {vals[-1]}")
    if thin:
        print("\n  Thin days (first 10):")
        for d in sorted(thin)[:10]:
            print(f"    {d}   {thin[d]} bars")

    report["q4_coverage"] = {
        "days_with_bars": len(counts), "days_full_rth": full,
        "days_below_90pct": len(thin), "days_with_duplicates": len(dupes),
        "bars_per_day": counts,
    }
    print("\n  → Feeds the §5.1 validation rules and the Week 4 Data Card.")
    print("  → Note: bars outside 09:30–16:00 ET are extended-hours; a count well")
    print("    above 78 means extended-hours bars are included. Decide explicitly")
    print("    whether the strategy trades them, and filter consistently.")


# -------------------------------------------------------- entitlement probe

def probe_sip(headers: dict) -> None:
    """SIP entitlement is NOT one question — historical and recent are sold separately.

    An earlier version probed only a historical date and reported 'SIP is entitled',
    which is misleading: Alpaca's free tier serves historical SIP but rejects recent
    SIP and SIP streaming. Both are checked here, and reported separately.
    """
    hr("Bonus  SIP entitlement — historical and recent are separate questions")

    def classify(err: str | None, n: int, label: str) -> bool | None:
        if err and err.startswith("HTTP 0"):
            print(f"  {label:<12} INCONCLUSIVE — connectivity failure, not an "
                  f"entitlement answer:\n               {err}")
            return None
        if err:
            print(f"  {label:<12} NOT entitled — {err}")
            return False
        print(f"  {label:<12} entitled — {n:,} bars returned")
        return True

    old = datetime.now(timezone.utc) - timedelta(days=5)
    hist_bars, hist_err = fetch_bars(old.strftime("%Y-%m-%dT00:00:00Z"),
                                     old.strftime("%Y-%m-%dT23:59:59Z"),
                                     headers, feed="sip", max_pages=1)
    hist = classify(hist_err, len(hist_bars), "historical")

    now = datetime.now(timezone.utc)
    rec_bars, rec_err = fetch_bars((now - timedelta(minutes=90))
                                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   headers, feed="sip", max_pages=1)
    recent = classify(rec_err, len(rec_bars), "recent")

    report["sip_entitled"] = {"historical": hist, "recent": recent}

    print()
    if hist and recent is False:
        print("  → THE DUAL-FEED CASE. Backtest on SIP (full consolidated volume,")
        print("    deep history); live paper trading must use IEX. Feed differs")
        print("    between training and inference — see Outline §5.2 before")
        print("    building any volume-derived feature.")
    elif hist and recent:
        print("  → Full SIP entitlement. Use feed='sip' everywhere; no mismatch.")
    elif hist is False:
        print("  → IEX only. Volume features see ~3% of market activity (see Q3).")


# ------------------------------------------------- Q5/Q6: crypto and options

CRYPTO_SYMBOL = "BTC/USD"


def q5_crypto(headers: dict) -> None:
    """Crypto trades 24/7 — no RTH filter, no flat-by-EOD, far more events.

    The question is whether the history is deep enough to train and walk-forward
    validate a regime model of its own. Equity-trained regime labels will not
    transfer to crypto volatility.
    """
    hr("Q5  Crypto — history depth and session coverage")

    earliest, per_year = None, {}
    for year in range(2018, datetime.now(timezone.utc).year + 1):
        params = {"symbols": CRYPTO_SYMBOL, "timeframe": TIMEFRAME,
                  "start": f"{year}-06-10T00:00:00Z", "end": f"{year}-06-13T00:00:00Z",
                  "limit": 10000}
        status, body = get("/crypto/us/bars", params, headers, root=CRYPTO_ROOT)
        if status != 200:
            msg = body.get("message") or body.get("raw") or str(body)[:120]
            per_year[year] = {"error": f"HTTP {status}: {msg}"}
            print(f"  {year}   ERROR  {msg[:90]}")
            continue
        bars = body.get("bars", {}).get(CRYPTO_SYMBOL, []) or []
        per_year[year] = {"bars": len(bars)}
        if bars:
            first = bars[0]["t"]
            per_year[year]["first_bar"] = first
            earliest = earliest or first
            print(f"  {year}   {len(bars):>6,} bars over 3 days   first: {first}")
        else:
            print(f"  {year}   {'0':>6} bars")

    report["q5_crypto"] = {"symbol": CRYPTO_SYMBOL, "earliest": earliest, "by_year": per_year}
    if earliest:
        years = (datetime.now(timezone.utc) - parse_ts(earliest)).days / 365.25
        print(f"\n  → Earliest {CRYPTO_SYMBOL} 5-min bar: {earliest}  (~{years:.1f} years)")
        print("  → 3 full days should yield ~864 bars at 5-min if coverage is")
        print("    genuinely 24/7. Materially fewer means gaps worth understanding")
        print("    before treating crypto as a continuous series.")
    else:
        print("\n  → No crypto bars retrieved. Check whether crypto data is")
        print("    entitled on this account before planning a crypto track.")


def q6_options(headers: dict) -> None:
    """Options depth is THE question for the options track.

    If history only reaches ~2024, options cannot be walk-forward backtested
    over ten years and the track becomes paper-forward only — demonstrated
    live, not backtested. That is still legitimate, but it is a different
    claim and it must be written differently in the proposal.
    """
    hr("Q6  Options — contract discovery and historical depth")
    print("Two separate questions: can we enumerate contracts, and how far")
    print("back do their bars go?\n")

    result: dict = {}

    # 1. Contract discovery lives on the TRADING API, not the data API.
    trading_root = "https://paper-api.alpaca.markets/v2"
    expiry_gte = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    expiry_lte = (datetime.now(timezone.utc) + timedelta(days=45)).date().isoformat()
    contract_symbol = None
    try:
        r = requests.get(
            f"{trading_root}/options/contracts",
            params={"underlying_symbols": SYMBOL, "status": "active", "limit": 20,
                    "expiration_date_gte": expiry_gte, "expiration_date_lte": expiry_lte},
            headers=headers, timeout=30,
        )
        if r.status_code == 200:
            contracts = r.json().get("option_contracts", []) or []
            result["contracts_found"] = len(contracts)
            print(f"  Contract discovery: OK — {len(contracts)} {SYMBOL} contracts")
            if contracts:
                contract_symbol = contracts[0].get("symbol")
                print(f"    example: {contract_symbol} "
                      f"(strike {contracts[0].get('strike_price')}, "
                      f"expiry {contracts[0].get('expiration_date')})")
        else:
            body = r.text[:200]
            result["contracts_error"] = f"HTTP {r.status_code}: {body}"
            print(f"  Contract discovery: HTTP {r.status_code} — {body[:120]}")
    except requests.RequestException as exc:
        result["contracts_error"] = f"network error: {exc}"
        print(f"  Contract discovery: network error — {exc}")

    # 2. Historical depth. An earlier version probed ONE near-dated contract
    #    across past years, which can only ever return data for the current
    #    year — a contract does not exist before it is listed. That probe was
    #    structurally incapable of answering "how far back does options data
    #    go", and its empty years were meaningless. For each past year we now
    #    find a contract that EXPIRED in that year and read its bars in the
    #    month before expiry, when it was actually trading.
    print("\n  Historical depth — one expired contract per year:\n")
    earliest, per_year = None, {}
    for year in range(2020, datetime.now(timezone.utc).year + 1):
        entry: dict = {}
        per_year[year] = entry
        try:
            rc = requests.get(
                f"{trading_root}/options/contracts",
                params={"underlying_symbols": SYMBOL, "status": "all", "limit": 5,
                        "expiration_date_gte": f"{year}-06-15",
                        "expiration_date_lte": f"{year}-06-30"},
                headers=headers, timeout=30,
            )
        except requests.RequestException as exc:
            entry["error"] = f"contract lookup network error: {exc}"
            print(f"  {year}   ERROR  {exc}")
            continue
        if rc.status_code != 200:
            entry["error"] = f"contract lookup HTTP {rc.status_code}: {rc.text[:160]}"
            print(f"  {year}   ERROR  contract lookup HTTP {rc.status_code}")
            continue
        found = rc.json().get("option_contracts", []) or []
        if not found:
            entry["contracts"] = 0
            print(f"  {year}   no contracts listed with a June expiry")
            continue

        sym = found[0].get("symbol")
        expiry = found[0].get("expiration_date")
        entry["contract"] = sym
        entry["expiration_date"] = expiry
        status, body = get("/options/bars",
                           {"symbols": sym, "timeframe": TIMEFRAME,
                            "start": f"{year}-05-15T00:00:00Z",
                            "end": f"{expiry}T23:59:59Z", "limit": 10000},
                           headers, root=OPTIONS_ROOT)
        if status != 200:
            msg = body.get("message") or body.get("raw") or str(body)[:160]
            # Recorded, not just printed: the JSON report is what gets read
            # later, and "null" with no error text is indistinguishable from
            # "endpoint fine, no data".
            entry["error"] = f"HTTP {status}: {msg}"
            print(f"  {year}   ERROR  HTTP {status} — {str(msg)[:80]}")
            continue
        bars = body.get("bars", {}).get(sym, []) or []
        entry["bars"] = len(bars)
        if bars:
            entry["first_bar"] = bars[0]["t"]
            earliest = earliest or bars[0]["t"]
            print(f"  {year}   {len(bars):>6,} bars   {sym}   first: {bars[0]['t']}")
        else:
            print(f"  {year}   {'0':>6} bars   {sym}   (endpoint OK, no data)")

    result["depth_by_year"] = per_year
    result["earliest_option_bar"] = earliest
    if contract_symbol:
        result["contract_probed"] = contract_symbol
    print("\n  → Read the ERROR text, not just the counts. An entitlement or")
    print("    subscription message means no options history at all; an")
    print("    empty-but-successful response means the endpoint works and that")
    print("    year genuinely has no data.")

    report["q6_options"] = result
    print("\n  → DECISION THIS FEEDS: if options history is shallow or unentitled,")
    print("    the options track is paper-forward only — demonstrated live, not")
    print("    backtested. Legitimate, but a different claim in the proposal.")


# ------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description="PROJECT BETA Alpaca data verification")
    ap.add_argument("--feed", default="iex", choices=["iex", "sip"],
                    help="Feed for the main probes (default: iex)")
    ap.add_argument("--stream", action="store_true",
                    help="Also run the definitive websocket real-time check")
    ap.add_argument("--assets", action="store_true",
                    help="Also probe crypto and options depth (Q5, Q6)")
    ap.add_argument("--out", default="alpaca_verification_report.json")
    args = ap.parse_args()

    headers = auth_headers()
    print(f"PROJECT BETA — Alpaca data verification   ({SYMBOL} @ {TIMEFRAME}, feed={args.feed})")
    print(f"Run at {report['run_at_utc']}")
    print("Run this DURING market hours (09:30–16:00 ET) for Q2 to mean anything.")

    q1_history_depth(headers, args.feed)
    q2_recency(headers, args.feed)
    if args.stream:
        q2b_stream(args.feed)
    q3_volume(headers)
    q4_coverage(headers, args.feed)
    if args.assets:
        q5_crypto(headers)
        q6_options(headers)
    probe_sip(headers)

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2, default=str)

    hr("Done")
    print(f"  Full results written to {args.out}")
    print("  Paste the console output (or attach the JSON) and we'll settle:")
    print("    • the data-tier decision            (Outline §9)")
    print("    • whether volume features survive   (Outline §5.2)")
    print("    • the Milestone 3 recency risk      (PRD §5.9)")
    print("    • RunConfig data.start + folds      (PRD §4.3)")
    if args.assets:
        print("    • crypto track feasibility          (24/7, its own regime model)")
        print("    • options: backtestable, or paper-forward only?")


if __name__ == "__main__":
    main()
