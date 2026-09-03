"""MarketDataProvider — the vendor-agnostic data interface (seam 1).

This is the most consequential design decision in the data layer, and the
reason it is written before any vendor code:

    Define the full interface including what the current vendor cannot do.

Shape the interface around one vendor's limits and those limits stop being
limits and become architecture. Alpaca serves no historical options quotes and
no point-in-time chain snapshot; both are declared here anyway, and the Alpaca
adapter raises NotSupported for them. The pipeline then degrades loudly rather
than quietly working around a gap it has forgotten is a gap.

NotSupported is a typed error and never an empty result. An empty list from
get_quotes would flow downstream as "no quotes in this window", which is a
statement about the market. It is in fact a statement about the vendor, and the
two must never be confused.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol, runtime_checkable


class NotSupported(RuntimeError):
    """The provider cannot serve this call, and no fallback is honest.

    Raised by an adapter for a capability the interface declares but the vendor
    does not offer. Callers may catch it to degrade deliberately; nothing may
    swallow it and continue as though the data were merely empty.
    """


class ProviderAuthError(RuntimeError):
    """Credentials were rejected.

    Separate from NotSupported because the remedy is different and because a
    run of 403s otherwise looks exactly like a run that found no data. A key
    rotation on 2026-09-01 would have produced precisely that.
    """


@dataclass(frozen=True)
class Bar:
    """One OHLCV bar as the vendor served it. No filtering, no forward fill."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int | None = None
    vwap: float | None = None


@dataclass(frozen=True)
class Quote:
    timestamp: datetime
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float


@dataclass(frozen=True)
class OptionContract:
    """A contract as it existed at enumeration time.

    `status` matters: expired contracts are only discoverable with
    status='inactive', which is what turned the options track from
    "hand-built OCC symbology required" into a supported API call.
    """

    symbol: str
    underlying: str
    expiry: date
    strike: float
    right: Literal["call", "put"]
    status: Literal["active", "inactive"]


@runtime_checkable
class MarketDataProvider(Protocol):
    """Every data source this project can read, present and future.

    Implementations must be pure readers: no caching policy, no RTH filtering,
    no gap repair. Those are pipeline concerns, and a provider that quietly
    cleans its output makes the validation layer untestable.
    """

    name: str

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
        """Historical bars, paginated to completion, oldest first."""
        ...

    def list_contracts(
        self,
        underlying: str,
        *,
        as_of: date,
        expiry_start: date | None = None,
        expiry_end: date | None = None,
        status: str = "inactive",
    ) -> list[OptionContract]:
        """The option universe as it stood on `as_of`.

        `as_of` is not decoration. Selecting contracts because they turn out to
        have bars is look-ahead bias in its purest form, and it is the most
        likely correctness bug in this project (Outline §11). The parameter is
        mandatory so that a caller cannot forget the question.
        """
        ...

    def get_quotes(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        asset_class: str = "equity",
    ) -> list[Quote]:
        """Historical bid/ask. Declared so its absence is visible."""
        ...

    def get_chain_snapshot(self, underlying: str, as_of: datetime) -> dict[str, Any]:
        """Full chain with greeks at a point in time. Declared, not available."""
        ...

    def authenticate(self) -> None:
        """One authenticated call. Raise ProviderAuthError on anything but success.

        A check that credentials are non-empty is not a check. This exists so a
        run fails at startup instead of producing a full session of 403s that
        looks, in the logs, like a successful run that found nothing.
        """
        ...
