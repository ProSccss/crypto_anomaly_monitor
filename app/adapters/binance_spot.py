import logging
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)


class BinanceSpotClient:
    def __init__(self, rest_url: str, timeout: float = 10.0) -> None:
        self.http = httpx.AsyncClient(base_url=rest_url.rstrip("/"), timeout=timeout)

    async def close(self) -> None:
        await self.http.aclose()

    async def fetch_ticker(self, symbol: str) -> dict | None:
        try:
            response = await self.http.get("/api/v3/ticker/price", params={"symbol": symbol})
            if response.status_code == 400:
                logger.info("binance_spot_pair_not_listed", extra={"symbol": symbol, "body": response.text[:200]})
                return None
            response.raise_for_status()
            payload = response.json()
            if payload.get("symbol") != symbol or not payload.get("price"):
                logger.warning("binance_spot_ticker_invalid", extra={"symbol": symbol, "payload": payload})
                return None
            Decimal(payload["price"])
            return payload
        except httpx.HTTPStatusError:
            logger.exception("binance_spot_ticker_http_error", extra={"symbol": symbol})
            return None
        except httpx.HTTPError:
            logger.exception("binance_spot_ticker_network_error", extra={"symbol": symbol})
            return None
        except (ValueError, TypeError):
            logger.exception("binance_spot_ticker_parse_error", extra={"symbol": symbol})
            return None

