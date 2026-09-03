"""Alpaca adapter for MarketDataProvider.

Not a thin wrapper, and it was never going to be. Three things make it real
work, all discovered before a line of it was written:

1. **Pagination.** The feed-transfer experiment alone needs roughly 98,000
   bars per feed across the 2021-2026 overlap. Alpaca returns pages with a
   `next_page_token`; a wrapper that reads page one silently returns a
   truncated history, and a truncated history produces a plausible wrong
   answer rather than an error.
2. **Rate limiting.** 200 requests/minute on the Basic tier. Backoff is a
   day-one requirement, not a hardening pass.
3. **Per-asset-class endpoints.** Alpaca versions its data APIs separately:
   /v2 for stocks, /v1beta3 for crypto, /v1beta1 for options. A probe that
   queried all three under /v2 returned zeros and was briefly misread as
   "options data does not exist".

What this adapter deliberately does not do: filter to regular hours, repair
gaps, forward-fill, or cache. Those belong to the pipeline above it, and a
provider that cleans its own output makes the validation layer untestable.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone
from typing import Any, Iterable

import requests

from project_beta.data.provider import (
    Bar,
    NotSupported,
    OptionContract,
    ProviderAuthError,
    Quote,
)

DATA_HOST = "https://data.alpaca.markets"
PAPER_TRADING_HOST = "https://paper-api.alpaca.markets"

# Basic tier: 200 requests/minute. Pace below the limit rather than discovering
# it through 429s — a burst that trips the limiter costs more than it saves.
MIN_SECONDS_BETWEEN_REQUESTS = 0.32
MAX_RETRIES = 5
PAGE_LIMIT = 10_000


def _iso(value: datetime | date) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value.isoformat()


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


class AlpacaProvider:
    """Reads bars and contracts from Alpaca. Paper credentials only."""

    name = "alpaca"

    def __init__(
        self,
        key_id: str | None = None,
        secret_key: str | None = None,
        *,
        data_host: str = DATA_HOST,
        trading_host: str = PAPER_TRADING_HOST,
        session: requests.Session | None = None,
    ) -> None:
        # `is not None`, not `or`. With `or`, an explicitly-passed empty string
        # is falsy and silently falls back to the ambient environment, so a
        # caller asking for "no credentials" quietly gets the real ones. That
        # made the guardrail test below pass only on a machine with no keys
        # set, which is the one machine where the guardrail does not matter.
        self.key_id = (
            key_id if key_id is not None else os.environ.get("APCA_API_KEY_ID", "")
        )
        self.secret_key = (
            secret_key
            if secret_key is not None
            else os.environ.get("APCA_API_SECRET_KEY", "")
        )
        if not self.key_id or not self.secret_key:
            raise ProviderAuthError(
                "APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set. Alpaca "
                "displays the secret once and does not retain it; a lost "
                "secret can only be replaced, and replacing it invalidates "
                "every stored copy."
            )

        # Paper-only enforcement (Outline §8, §20.2 harm 1). The guardrail is
        # here as well as in the execution layer because this is the object
        # that holds the credentials, and a live host reached with them is the
        # exact shape of the accident the charter promises cannot happen.
        if not trading_host.startswith(PAPER_TRADING_HOST):
            raise ValueError(
                f"trading_host must be the paper endpoint ({PAPER_TRADING_HOST}); "
                f"got {trading_host!r}. This project has no live-money code path."
            )

        self.data_host = data_host.rstrip("/")
        self.trading_host = trading_host.rstrip("/")
        self._session = session or requests.Session()
        self._last_request_at = 0.0

    # ------------------------------------------------------------- plumbing

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "accept": "application/json",
        }

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
        self._last_request_at = time.monotonic()

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """One GET, with backoff. Auth failures raise immediately, never retry."""
        delay = 1.0
        last_status = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            resp = self._session.get(
                url, params=params, headers=self._headers(), timeout=30
            )
            last_status = resp.status_code

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (401, 403):
                raise ProviderAuthError(
                    f"{resp.status_code} from {url}. Either the credentials are "
                    "invalid, or this data is not entitled on the Basic tier "
                    "(recent SIP returns 403 by design). Body: "
                    f"{resp.text[:200]}"
                )

            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", delay))
                time.sleep(wait)
                delay = min(delay * 2, 30.0)
                continue

            if 500 <= resp.status_code < 600:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue

            raise RuntimeError(
                f"{resp.status_code} from {url}: {resp.text[:300]}"
            )

        raise RuntimeError(
            f"gave up after {MAX_RETRIES} attempts on {url} (last status {last_status})"
        )

    def _paginate(self, url: str, params: dict[str, Any], key: str) -> Iterable[dict]:
        """Follow next_page_token to exhaustion.

        The page token is the whole point of this method. Stopping at page one
        yields a shorter history that still looks like a history.
        """
        params = dict(params)
        while True:
            payload = self._get(url, params)
            block = payload.get(key) or {}
            if isinstance(block, dict):
                # Multi-symbol shape: {"SPY": [...]}
                for rows in block.values():
                    yield from rows or []
            else:
                yield from block
            token = payload.get("next_page_token")
            if not token:
                return
            params["page_token"] = token

    # ------------------------------------------------------------ interface

    def authenticate(self) -> None:
        """One authenticated call against the paper trading account.

        Learned the hard way: run_market_open.sh checked only that the
        environment variables were non-empty. A credential check that cannot
        fail is not a check, and the key rotation on 2026-09-01 would have
        produced a full session of 403s that read as a successful run.
        """
        resp = self._session.get(
            f"{self.trading_host}/v2/account", headers=self._headers(), timeout=30
        )
        if resp.status_code != 200:
            raise ProviderAuthError(
                f"authentication failed: {resp.status_code} from "
                f"{self.trading_host}/v2/account. Body: {resp.text[:200]}"
            )

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | date,
        end: datetime | date,
        *,
        asset_class: str = "equity",
        feed: str | None = None,
    ) -> list[Bar]:
        params: dict[str, Any] = {
            "timeframe": timeframe,
            "start": _iso(start),
            "end": _iso(end),
            "limit": PAGE_LIMIT,
        }

        if asset_class == "equity":
            if feed not in ("sip", "iex"):
                raise ValueError("equity bars require feed='sip' or feed='iex'")
            url = f"{self.data_host}/v2/stocks/bars"
            params["symbols"] = symbol
            params["feed"] = feed
            params["adjustment"] = "all"
        elif asset_class == "crypto":
            url = f"{self.data_host}/v1beta3/crypto/us/bars"
            params["symbols"] = symbol
        elif asset_class == "option":
            url = f"{self.data_host}/v1beta1/options/bars"
            params["symbols"] = symbol
        else:
            raise ValueError(f"unknown asset_class {asset_class!r}")

        rows = list(self._paginate(url, params, key="bars"))
        return [
            Bar(
                timestamp=_parse_ts(r["t"]),
                open=float(r["o"]),
                high=float(r["h"]),
                low=float(r["l"]),
                close=float(r["c"]),
                volume=float(r["v"]),
                trade_count=r.get("n"),
                vwap=r.get("vw"),
            )
            for r in rows
        ]

    def list_contracts(
        self,
        underlying: str,
        *,
        as_of: date,
        expiry_start: date | None = None,
        expiry_end: date | None = None,
        status: str = "inactive",
    ) -> list[OptionContract]:
        """Enumerate contracts. status='inactive' is what reaches expired ones."""
        url = f"{self.trading_host}/v2/options/contracts"
        params: dict[str, Any] = {
            "underlying_symbols": underlying,
            "status": status,
            "limit": 10_000,
        }
        if expiry_start:
            params["expiration_date_gte"] = expiry_start.isoformat()
        if expiry_end:
            params["expiration_date_lte"] = expiry_end.isoformat()

        out: list[OptionContract] = []
        for row in self._paginate(url, params, key="option_contracts"):
            expiry = date.fromisoformat(row["expiration_date"])
            # Point-in-time correctness (Outline §11): a contract that had not
            # yet been listed on `as_of` was not selectable on `as_of`, however
            # convenient its later bars turn out to be.
            listed = row.get("created_at") or row.get("listing_date")
            if listed and date.fromisoformat(str(listed)[:10]) > as_of:
                continue
            out.append(
                OptionContract(
                    symbol=row["symbol"],
                    underlying=row.get("underlying_symbol", underlying),
                    expiry=expiry,
                    strike=float(row["strike_price"]),
                    right="call" if row["type"] == "call" else "put",
                    status=status,  # type: ignore[arg-type]
                )
            )
        return out

    def get_quotes(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        asset_class: str = "equity",
    ) -> list[Quote]:
        if asset_class == "option":
            raise NotSupported(
                "Alpaca serves no historical options quotes. Spread and "
                "slippage for the options layer are bar-derived proxies and "
                "must be reported as such (Outline §5.8). This is a vendor "
                "limit, not an empty result."
            )
        raise NotSupported(
            "Historical equity quotes are not wired up: nothing in the graded "
            "pipeline consumes them, and an unused code path is an untested "
            "one. Declared in the interface so the gap stays visible."
        )

    def get_chain_snapshot(self, underlying: str, as_of: datetime) -> dict[str, Any]:
        raise NotSupported(
            "Alpaca serves no point-in-time chain snapshot with greeks. The "
            "options layer therefore selects contracts from a deterministic "
            "rule over an as-of universe rather than from a delta surface "
            "(Outline §5.8)."
        )
