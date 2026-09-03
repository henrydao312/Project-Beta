"""MarketDataProvider seam tests.

Two of these matter more than the rest.

`test_a_second_adapter_satisfies_the_protocol` is what proves the seam is real
rather than decorative: if only one class can satisfy the interface, the
interface is Alpaca with extra steps, and the post-course vendor swap
(Upgrade_Path §2.1) is a rewrite rather than a configuration change.

`test_unsupported_capabilities_raise_rather_than_return_empty` is what keeps a
vendor limit from turning into a market observation. An empty quote list flows
downstream as "the spread was unobservable here". A NotSupported does not flow
anywhere at all, which is the correct behaviour.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from project_beta.data.alpaca import PAPER_TRADING_HOST, AlpacaProvider
from project_beta.data.provider import (
    Bar,
    MarketDataProvider,
    NotSupported,
    OptionContract,
    ProviderAuthError,
    Quote,
)

CREDS = {"key_id": "PKTESTKEYID0000000000", "secret_key": "testsecret0000000000"}


# --------------------------------------------------------------- fake HTTP


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self._payload


class _FakeSession:
    """Serves a scripted list of responses and records the params it was given."""

    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params=None, headers=None, timeout=None) -> _FakeResponse:
        self.calls.append({"url": url, "params": dict(params or {})})
        if not self._responses:
            raise AssertionError(f"unexpected extra request to {url}")
        return self._responses.pop(0)


def _bar_page(token: str | None, n: int, hour_offset: int = 0) -> _FakeResponse:
    rows = [
        {
            "t": f"2024-03-04T{14 + hour_offset:02d}:{i:02d}:00Z",
            "o": 1.0,
            "h": 2.0,
            "l": 0.5,
            "c": 1.5,
            "v": 100 + i,
            "n": 7,
            "vw": 1.4,
        }
        for i in range(n)
    ]
    return _FakeResponse(200, {"bars": {"SPY": rows}, "next_page_token": token})


def _provider(responses: list[_FakeResponse]) -> tuple[AlpacaProvider, _FakeSession]:
    session = _FakeSession(responses)
    provider = AlpacaProvider(session=session, **CREDS)
    provider._last_request_at = 0.0
    return provider, session


# ------------------------------------------------------------- the seam


class _StubProvider:
    """A second implementation, deliberately unrelated to Alpaca.

    It exists only to be type-checked against the Protocol. If this class ever
    needs an Alpaca-shaped concession to satisfy the interface, the interface
    has leaked a vendor assumption and should be changed, not this stub.
    """

    name = "stub"

    def get_bars(self, symbol, timeframe, start, end, *, asset_class="equity", feed=None):
        return [
            Bar(
                timestamp=datetime(2024, 3, 4, 14, 30, tzinfo=timezone.utc),
                open=1.0,
                high=2.0,
                low=0.5,
                close=1.5,
                volume=100.0,
            )
        ]

    def list_contracts(
        self, underlying, *, as_of, expiry_start=None, expiry_end=None, status="inactive"
    ):
        return [
            OptionContract(
                symbol="SPY240419C00500000",
                underlying=underlying,
                expiry=date(2024, 4, 19),
                strike=500.0,
                right="call",
                status="inactive",
            )
        ]

    def get_quotes(self, symbol, start, end, *, asset_class="equity"):
        return [
            Quote(
                timestamp=datetime(2024, 3, 4, 14, 30, tzinfo=timezone.utc),
                bid_price=1.0,
                bid_size=10.0,
                ask_price=1.1,
                ask_size=10.0,
            )
        ]

    def get_chain_snapshot(self, underlying, as_of):
        return {}

    def authenticate(self) -> None:
        return None


def test_a_second_adapter_satisfies_the_protocol() -> None:
    """The test that makes the seam real rather than aspirational."""
    stub = _StubProvider()
    assert isinstance(stub, MarketDataProvider)
    assert stub.get_quotes("SPY", datetime.now(timezone.utc), datetime.now(timezone.utc))


def test_the_alpaca_adapter_also_satisfies_the_protocol() -> None:
    provider, _ = _provider([])
    assert isinstance(provider, MarketDataProvider)


# ------------------------------------------------------- declared, absent


@pytest.mark.parametrize("asset_class", ["equity", "option"])
def test_unsupported_capabilities_raise_rather_than_return_empty(asset_class) -> None:
    """A vendor limit must never arrive downstream as a market observation."""
    provider, _ = _provider([])
    now = datetime.now(timezone.utc)
    with pytest.raises(NotSupported):
        provider.get_quotes("SPY", now, now, asset_class=asset_class)


def test_chain_snapshot_is_declared_and_unavailable() -> None:
    provider, _ = _provider([])
    with pytest.raises(NotSupported, match="point-in-time chain"):
        provider.get_chain_snapshot("SPY", datetime.now(timezone.utc))


def test_not_supported_is_not_swallowed_as_a_generic_value_error() -> None:
    """Typed, so a caller can distinguish it from a bad argument."""
    assert issubclass(NotSupported, RuntimeError)
    assert not issubclass(NotSupported, ValueError)


# ------------------------------------------------------------ pagination


def test_get_bars_follows_every_page() -> None:
    """Stopping at page one returns a shorter history that still looks like one.

    The transfer experiment needs ~98,000 bars per feed; a single page is
    10,000. Truncation here would produce a plausible wrong correlation rather
    than an error, which is the worst failure mode available.
    """
    provider, session = _provider(
        [_bar_page("tok1", 3), _bar_page("tok2", 3, 1), _bar_page(None, 2, 2)]
    )
    bars = provider.get_bars(
        "SPY", "5Min", date(2024, 3, 4), date(2024, 3, 5), feed="sip"
    )
    assert len(bars) == 8
    assert len(session.calls) == 3
    assert session.calls[1]["params"]["page_token"] == "tok1"
    assert session.calls[2]["params"]["page_token"] == "tok2"


def test_bars_are_returned_unfiltered() -> None:
    """The provider is a pure reader. RTH filtering happens in the pipeline,
    where it can be tested; a provider that cleans its own output makes the
    validation layer untestable."""
    provider, _ = _provider([_bar_page(None, 4)])
    bars = provider.get_bars(
        "SPY", "5Min", date(2024, 3, 4), date(2024, 3, 5), feed="iex"
    )
    assert len(bars) == 4
    assert all(isinstance(b, Bar) for b in bars)


# ------------------------------------------- per-asset-class endpoints


@pytest.mark.parametrize(
    ("asset_class", "fragment", "feed"),
    [
        ("equity", "/v2/stocks/bars", "sip"),
        ("crypto", "/v1beta3/crypto/us/bars", None),
        ("option", "/v1beta1/options/bars", None),
    ],
)
def test_each_asset_class_uses_its_own_versioned_endpoint(
    asset_class, fragment, feed
) -> None:
    """A probe that queried all three under /v2 returned zeros, and the zeros
    were briefly misread as 'options data does not exist'."""
    provider, session = _provider([_bar_page(None, 1)])
    provider.get_bars(
        "SPY", "5Min", date(2024, 3, 4), date(2024, 3, 5),
        asset_class=asset_class, feed=feed,
    )
    assert fragment in session.calls[0]["url"]


def test_equity_bars_require_an_explicit_feed() -> None:
    """SIP and IEX are different datasets. Defaulting one would put an
    unrecorded feed into a result (Outline §9)."""
    provider, _ = _provider([])
    with pytest.raises(ValueError, match="feed"):
        provider.get_bars("SPY", "5Min", date(2024, 3, 4), date(2024, 3, 5))


# ------------------------------------------------------------ guardrails


def test_missing_credentials_fail_loudly_at_construction(monkeypatch) -> None:
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    with pytest.raises(ProviderAuthError, match="APCA_API_KEY_ID"):
        AlpacaProvider(key_id="", secret_key="", session=_FakeSession([]))


def test_explicit_empty_credentials_are_not_backfilled_from_the_environment(
    monkeypatch,
) -> None:
    """Asking for no credentials must not quietly hand back the real ones.

    This is the test that caught the bug: written against `or`, it passed only
    on a machine with no keys exported, which is precisely the machine where
    the guardrail is irrelevant. A guardrail that is only exercised where it
    cannot fire is not a guardrail.
    """
    monkeypatch.setenv("APCA_API_KEY_ID", "PKAMBIENTKEY000000000")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "ambientsecret0000000")
    with pytest.raises(ProviderAuthError):
        AlpacaProvider(key_id="", secret_key="", session=_FakeSession([]))


def test_credentials_fall_back_to_the_environment_when_unset(monkeypatch) -> None:
    """The fallback still works; it just requires asking for it with None."""
    monkeypatch.setenv("APCA_API_KEY_ID", "PKAMBIENTKEY000000000")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "ambientsecret0000000")
    provider = AlpacaProvider(session=_FakeSession([]))
    assert provider.key_id == "PKAMBIENTKEY000000000"


def test_a_non_paper_trading_host_is_rejected() -> None:
    """Outline §20.2 harm 1: there is no live-money code path, and the object
    holding the credentials is the right place to make that structural."""
    with pytest.raises(ValueError, match="paper endpoint"):
        AlpacaProvider(
            session=_FakeSession([]),
            trading_host="https://api.alpaca.markets",
            **CREDS,
        )


def test_authenticate_rejects_a_non_200() -> None:
    """A check that credentials are non-empty is not a check.

    The key rotation on 2026-09-01 would otherwise have produced a full session
    of 403s that read, in the logs, exactly like a successful run.
    """
    provider, _ = _provider([_FakeResponse(403, text="forbidden")])
    with pytest.raises(ProviderAuthError, match="authentication failed"):
        provider.authenticate()


def test_authenticate_accepts_a_200() -> None:
    provider, session = _provider([_FakeResponse(200, {"status": "ACTIVE"})])
    provider.authenticate()
    assert session.calls[0]["url"] == f"{PAPER_TRADING_HOST}/v2/account"


def test_auth_failures_are_not_retried() -> None:
    """403 on the Basic tier is a design fact (recent SIP), not a transient.
    Retrying it wastes the rate-limit budget and hides the cause."""
    provider, session = _provider([_FakeResponse(403, text="not entitled")])
    with pytest.raises(ProviderAuthError):
        provider.get_bars("SPY", "5Min", date(2024, 3, 4), date(2024, 3, 5), feed="sip")
    assert len(session.calls) == 1


def test_rate_limit_responses_are_retried_then_succeed() -> None:
    limited = _FakeResponse(429)
    limited.headers["Retry-After"] = "0"
    provider, session = _provider([limited, _bar_page(None, 2)])
    bars = provider.get_bars(
        "SPY", "5Min", date(2024, 3, 4), date(2024, 3, 5), feed="sip"
    )
    assert len(bars) == 2
    assert len(session.calls) == 2


# ------------------------------------------------- point-in-time universe


def test_contracts_listed_after_the_as_of_date_are_excluded() -> None:
    """Selecting a contract because it turns out to have bars is look-ahead
    bias in its purest form, and the most likely correctness bug in this
    project (Outline §11)."""
    payload = {
        "option_contracts": [
            {
                "symbol": "SPY240419C00500000",
                "underlying_symbol": "SPY",
                "expiration_date": "2024-04-19",
                "strike_price": "500",
                "type": "call",
                "created_at": "2024-01-20T00:00:00Z",
            },
            {
                "symbol": "SPY240419C00510000",
                "underlying_symbol": "SPY",
                "expiration_date": "2024-04-19",
                "strike_price": "510",
                "type": "call",
                "created_at": "2024-03-01T00:00:00Z",
            },
        ],
        "next_page_token": None,
    }
    provider, _ = _provider([_FakeResponse(200, payload)])
    contracts = provider.list_contracts("SPY", as_of=date(2024, 2, 1))
    assert [c.strike for c in contracts] == [500.0]
