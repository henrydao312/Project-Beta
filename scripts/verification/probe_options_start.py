#!/usr/bin/env python3
"""Where does Alpaca's options history actually START?

probe_options_depth.py established that options bars EXIST, but it bounded
each query to a 25-day window before expiry, so the "earliest bar seen"
(2024-05-28) is an artifact of the earliest expiry that happened to be in the
list. The true boundary lies somewhere in (2023-12-15, 2024-05-27].

That number decides the options track's scope: the walk-forward protocol is
36 train / 6 val / 6 test = 48 months for a SINGLE fold. Anything under that
means options cannot be backtested under the same protocol as equities.

This script also stops guessing strikes. The expired-contract discovery
endpoint DOES work with status=inactive (proved by the last run), so we
enumerate real contracts and query those.

Run:  cd ~/Desktop/Project-Beta && set -a && . ./.env && set +a && python3 probe_options_start.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

OPTIONS_ROOT = "https://data.alpaca.markets/v1beta1"
TRADING_ROOT = "https://paper-api.alpaca.markets/v2"

# Monthly expiries spanning the unknown boundary, plus one known-good anchor.
EXPIRIES = [
    "2024-01-19", "2024-02-16", "2024-03-15",
    "2024-04-19", "2024-05-17", "2024-06-21",
]

# Look far enough back that the window itself can never be the limiting factor.
LOOKBACK_START = "2023-06-01T00:00:00Z"


def headers() -> dict:
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your environment.")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def contracts_for(h: dict, expiry: str, n: int = 3) -> list[str]:
    """Real contracts for this expiry, taken from the middle of the strike range."""
    syms: list[str] = []
    page_token = None
    while True:
        params = {"underlying_symbols": "SPY", "status": "inactive", "limit": 1000,
                  "expiration_date_gte": expiry, "expiration_date_lte": expiry,
                  "type": "call"}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(f"{TRADING_ROOT}/options/contracts", params=params,
                         headers=h, timeout=30)
        if r.status_code != 200:
            print(f"  discovery HTTP {r.status_code} — {r.text[:120]}")
            return []
        body = r.json()
        syms += [c["symbol"] for c in (body.get("option_contracts") or [])]
        page_token = body.get("next_page_token")
        if not page_token:
            break
    syms.sort()
    if not syms:
        return []
    mid = len(syms) // 2
    return syms[max(0, mid - n // 2): max(0, mid - n // 2) + n]


def main() -> None:
    h = headers()
    out: dict = {"expiries": {}, "lookback_start": LOOKBACK_START}
    earliest = None

    print("=" * 68)
    print("Options history START — real contracts, unbounded lookback")
    print("=" * 68)

    for expiry in EXPIRIES:
        print(f"\n{expiry}")
        syms = contracts_for(h, expiry)
        if not syms:
            print("  no contracts enumerated for this expiry")
            out["expiries"][expiry] = {"contracts": 0}
            continue
        row: dict = {}
        for sym in syms:
            r = requests.get(
                f"{OPTIONS_ROOT}/options/bars",
                params={"symbols": sym, "timeframe": "5Min",
                        "start": LOOKBACK_START, "end": f"{expiry}T23:59:59Z",
                        "limit": 10000},
                headers=h, timeout=30,
            )
            if r.status_code != 200:
                row[sym] = {"http": r.status_code, "message": r.text[:200]}
                print(f"  {sym}   HTTP {r.status_code} — {r.text[:90]}")
                continue
            bars = (r.json().get("bars") or {}).get(sym) or []
            if bars:
                first = bars[0]["t"]
                row[sym] = {"bars": len(bars), "first_bar": first}
                if earliest is None or first < earliest:
                    earliest = first
                print(f"  {sym}   {len(bars):>6,} bars   first: {first}")
            else:
                row[sym] = {"bars": 0}
                print(f"  {sym}   {'0':>6} bars   (endpoint OK, no data)")
        out["expiries"][expiry] = row

    out["earliest_option_bar"] = earliest
    print("\n" + "=" * 68)
    if earliest:
        start = date.fromisoformat(earliest[:10])
        months = (date.today().year - start.year) * 12 + (date.today().month - start.month)
        print(f"Earliest option bar anywhere in this probe: {earliest}")
        print(f"  -> roughly {months} months of options history ({months/12:.1f} years)")
        print(f"  -> walk-forward at 36/6/6 needs 48 months for ONE fold: "
              f"{'OK' if months >= 48 else 'NOT ENOUGH'}")
    else:
        print("No bars retrieved at any expiry in this range.")
    print("=" * 68)

    with open("report_options_start.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote report_options_start.json")


if __name__ == "__main__":
    main()
