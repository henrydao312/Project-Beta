#!/usr/bin/env python3
"""Does Alpaca have HISTORICAL options data, or only current contracts?

The --assets run answered "no contracts listed" for every past year, which is
NOT the same as "no options history". Alpaca's contract-discovery endpoint may
simply not return expired contracts. Those two situations lead to opposite
scope decisions:

  * discovery-only limitation -> options CAN be backtested; we name contracts
    ourselves from the OCC symbology instead of enumerating them.
  * data genuinely absent -> the options track is paper-forward only:
    demonstrated live, never backtested. Legitimate, but a different claim in
    the proposal and a different row in the ablation table.

So this script skips discovery entirely and asks the bars endpoint directly,
using hand-built OCC symbols for past monthly expiries.

OCC symbol format: SPY + YYMMDD + C|P + strike x 1000, zero-padded to 8.
    SPY 2024-06-21 540 call -> SPY240621C00540000

Run: python3 probe_options_depth.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

OPTIONS_ROOT = "https://data.alpaca.markets/v1beta1"
TRADING_ROOT = "https://paper-api.alpaca.markets/v2"

# Third-Friday monthly expiries, with a spread of strikes bracketing roughly
# where SPY traded at the time. Several strikes per expiry so a single bad
# guess cannot be mistaken for "no data".
EXPIRIES: list[tuple[str, list[int]]] = [
    ("2023-06-16", [400, 420, 440]),
    ("2023-12-15", [450, 470, 480]),
    ("2024-06-21", [520, 540, 560]),
    ("2024-12-20", [580, 600, 620]),
    ("2025-06-20", [580, 600, 620]),
    ("2025-12-19", [620, 650, 680]),
    ("2026-06-18", [640, 670, 700]),
]


def headers() -> dict:
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your environment.")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def occ(expiry: str, strike: int, right: str = "C") -> str:
    y, m, d = expiry.split("-")
    return f"SPY{y[2:]}{m}{d}{right}{strike * 1000:08d}"


def main() -> None:
    h = headers()
    out: dict = {"expiries": {}}

    print("=" * 68)
    print("Options historical depth - hand-built OCC symbols, no discovery")
    print("=" * 68)

    earliest = None
    for expiry, strikes in EXPIRIES:
        exp = date.fromisoformat(expiry)
        start = (exp - timedelta(days=25)).isoformat()
        row: dict = {}
        hit = False
        for strike in strikes:
            sym = occ(expiry, strike)
            try:
                r = requests.get(
                    f"{OPTIONS_ROOT}/options/bars",
                    params={"symbols": sym, "timeframe": "5Min",
                            "start": f"{start}T00:00:00Z",
                            "end": f"{expiry}T23:59:59Z", "limit": 10000},
                    headers=h, timeout=30,
                )
            except requests.RequestException as exc:
                row[sym] = {"error": f"network: {exc.__class__.__name__}"}
                continue
            if r.status_code != 200:
                body = r.text[:200]
                row[sym] = {"http": r.status_code, "message": body}
                print(f" {sym} HTTP {r.status_code} - {body[:90]}")
                continue
            bars = (r.json().get("bars") or {}).get(sym) or []
            row[sym] = {"bars": len(bars)}
            if bars:
                hit = True
                first = bars[0]["t"]
                row[sym]["first_bar"] = first
                earliest = earliest or first
                print(f" {sym} {len(bars):>6,} bars first: {first}")
            else:
                print(f" {sym} {'0':>6} bars (endpoint OK, no data)")
        out["expiries"][expiry] = row
        print(f" -> {expiry}: {'DATA PRESENT' if hit else 'no data'}\n")

    # Can expired contracts be enumerated at all, under any parameters?
    print("-" * 68)
    print("Contract discovery for an expired window (status=inactive):")
    try:
        r = requests.get(
            f"{TRADING_ROOT}/options/contracts",
            params={"underlying_symbols": "SPY", "status": "inactive", "limit": 5,
                    "expiration_date_gte": "2025-06-01",
                    "expiration_date_lte": "2025-06-30"},
            headers=h, timeout=30,
        )
        found = (r.json().get("option_contracts") or []) if r.status_code == 200 else []
        out["expired_discovery"] = {"http": r.status_code, "count": len(found),
                                    "body": None if found else r.text[:200]}
        print(f" HTTP {r.status_code} - {len(found)} contracts")
        for c in found[:3]:
            print(f" {c.get('symbol')} expiry {c.get('expiration_date')}")
    except requests.RequestException as exc:
        out["expired_discovery"] = {"error": str(exc)}
        print(f" network error: {exc}")

    out["earliest_option_bar"] = earliest
    print("\n" + "=" * 68)
    if earliest:
        print(f"VERDICT: options history EXISTS, earliest bar seen {earliest}")
        print(" -> The --assets run's zeros were a discovery limitation, not")
        print(" missing data. Options can be backtested; contracts must be")
        print(" named via OCC symbology rather than enumerated.")
    else:
        print("VERDICT: no historical option bars retrieved at any expiry.")
        print(" -> Read the HTTP/message lines above. A subscription or")
        print(" entitlement message means the options track is")
        print(" PAPER-FORWARD ONLY - demonstrated live, never backtested.")
    print("=" * 68)

    with open("report_options_depth.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote report_options_depth.json")


if __name__ == "__main__":
    main()
