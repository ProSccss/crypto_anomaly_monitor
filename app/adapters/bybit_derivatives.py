import logging

import httpx

logger = logging.getLogger(__name__)


class BybitAPIError(RuntimeError):
    pass


class BybitDerivativesClient:
    def __init__(self, rest_url: str, timeout: float = 10.0) -> None:
        self.http = httpx.AsyncClient(base_url=rest_url.rstrip("/"), timeout=timeout)

    async def close(self) -> None:
        await self.http.aclose()

    async def get(self, path: str, params: dict[str, str]) -> dict:
        response = await self.http.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") != 0:
            raise BybitAPIError(f"Bybit error {payload.get('retCode')}: {payload.get('retMsg')}")
        return payload["result"]

    async def fetch_ticker(self, symbol: str) -> dict | None:
        result = await self.get("/v5/market/tickers", {"category": "linear", "symbol": symbol})
        if not result.get("list"):
            logger.warning("ticker_empty_list", extra={"symbol": symbol})
            return None
        return result["list"][0]

    async def fetch_instrument(self, symbol: str) -> dict | None:
        result = await self.get("/v5/market/instruments-info", {"category": "linear", "symbol": symbol})
        if not result.get("list"):
            logger.warning("instrument_empty_list", extra={"symbol": symbol})
            return None
        return result["list"][0]

    async def fetch_ratio(self, symbol: str) -> dict:
        try:
            return await self.get(
                "/v5/market/account-ratio",
                {"category": "linear", "symbol": symbol, "period": "5min", "limit": "1"},
            )
        except (httpx.HTTPError, BybitAPIError, KeyError):
            logger.warning("long_short_ratio_unavailable", extra={"symbol": symbol})
            return {"list": []}

    async def fetch_klines(self, symbol: str, interval: str = "1", limit: int = 240) -> list[list[str]]:
        result = await self.get(
            "/v5/market/kline",
            {"category": "linear", "symbol": symbol, "interval": interval, "limit": str(limit)},
        )
        return result.get("list", [])
