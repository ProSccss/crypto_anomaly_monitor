from decimal import Decimal

import pytest

from app.adapters.bybit import BybitClient


class StubBybitClient(BybitClient):
    def __init__(
        self,
        responses: dict[tuple[str, str], dict],
        binance_responses: dict[str, dict] | None = None,
    ) -> None:
        self.responses = responses
        self.binance_responses = binance_responses or {}
        super().__init__("https://example.test", "wss://example.test")

    async def close(self) -> None:
        return None

    async def _lookup(self, path: str, category: str, symbol: str) -> dict:
        return self.responses[(path, f"{category}:{symbol}")]

    async def fetch_derivative_ticker(self, symbol: str) -> dict:
        return (await self._lookup("/v5/market/tickers", "linear", symbol))["list"][0]

    async def fetch_instrument(self, symbol: str) -> dict:
        return (await self._lookup("/v5/market/instruments-info", "linear", symbol))["list"][0]

    async def fetch_ratio(self, symbol: str) -> dict:
        return await self._lookup("/v5/market/account-ratio", "linear", symbol)

    async def fetch_bybit_spot_ticker(self, symbol: str) -> dict | None:
        spot_instrument = await self._lookup("/v5/market/instruments-info", "spot", symbol)
        if not spot_instrument["list"]:
            return None
        return (await self._lookup("/v5/market/tickers", "spot", symbol))["list"][0]

    async def fetch_binance_spot_ticker(self, symbol: str) -> dict | None:
        return self.binance_responses.get(symbol)

    async def fetch_snapshot(self, symbol: str):
        self.derivatives.fetch_ticker = self.fetch_derivative_ticker
        self.derivatives.fetch_instrument = self.fetch_instrument
        self.derivatives.fetch_ratio = self.fetch_ratio
        self.bybit_spot.fetch_ticker = self.fetch_bybit_spot_ticker
        self.binance_spot.fetch_ticker = self.fetch_binance_spot_ticker
        return await super().fetch_snapshot(symbol)


def linear_ticker() -> dict:
    return {
        "symbol": "LABUSDT",
        "lastPrice": "1.1000",
        "markPrice": "1.1200",
        "indexPrice": "1.0000",
        "openInterestValue": "1000000",
        "turnover24h": "10000000",
        "fundingRate": "0.0001",
    }


@pytest.mark.asyncio
async def test_fetch_snapshot_uses_bybit_spot_last_price_when_pair_exists() -> None:
    client = StubBybitClient(
        {
            ("/v5/market/tickers", "linear:LABUSDT"): {"list": [linear_ticker()]},
            ("/v5/market/account-ratio", "linear:LABUSDT"): {"list": []},
            ("/v5/market/instruments-info", "linear:LABUSDT"): {"list": [{"fundingInterval": "480"}]},
            ("/v5/market/instruments-info", "spot:LABUSDT"): {"list": [{"symbol": "LABUSDT"}]},
            ("/v5/market/tickers", "spot:LABUSDT"): {"list": [{"symbol": "LABUSDT", "lastPrice": "1.0500"}]},
        }
    )
    try:
        snapshot = await client.fetch_snapshot("LABUSDT")
    finally:
        await client.close()

    assert snapshot.spot_price == Decimal("1.0500")
    assert snapshot.raw_payload["spot_source"] == "bybit_spot_ticker"
    assert snapshot.basis_bps == Decimal("666.6666666666666666666666667")


@pytest.mark.asyncio
async def test_fetch_snapshot_falls_back_to_index_price_when_spot_pair_is_not_listed() -> None:
    client = StubBybitClient(
        {
            ("/v5/market/tickers", "linear:LABUSDT"): {"list": [linear_ticker()]},
            ("/v5/market/account-ratio", "linear:LABUSDT"): {"list": []},
            ("/v5/market/instruments-info", "linear:LABUSDT"): {"list": [{"fundingInterval": "480"}]},
            ("/v5/market/instruments-info", "spot:LABUSDT"): {"list": []},
        }
    )
    try:
        snapshot = await client.fetch_snapshot("LABUSDT")
    finally:
        await client.close()

    assert snapshot.spot_price == Decimal("1.0000")
    assert snapshot.raw_payload["spot_source"] == "bybit_derivatives_index_price"
    assert snapshot.basis_bps == Decimal("1200.0000")


@pytest.mark.asyncio
async def test_fetch_snapshot_uses_binance_spot_before_index_price() -> None:
    client = StubBybitClient(
        {
            ("/v5/market/tickers", "linear:TRBUSDT"): {"list": [{**linear_ticker(), "symbol": "TRBUSDT"}]},
            ("/v5/market/account-ratio", "linear:TRBUSDT"): {"list": []},
            ("/v5/market/instruments-info", "linear:TRBUSDT"): {"list": [{"fundingInterval": "480"}]},
            ("/v5/market/instruments-info", "spot:TRBUSDT"): {"list": []},
        },
        binance_responses={"TRBUSDT": {"symbol": "TRBUSDT", "price": "1.0800"}},
    )
    try:
        snapshot = await client.fetch_snapshot("TRBUSDT")
    finally:
        await client.close()

    assert snapshot.spot_price == Decimal("1.0800")
    assert snapshot.raw_payload["spot_source"] == "binance_spot_ticker"
    assert snapshot.basis_bps == Decimal("370.3703703703703703703703704")
