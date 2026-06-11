import logging

import httpx

from app.adapters.bybit_derivatives import BybitAPIError, BybitDerivativesClient

logger = logging.getLogger(__name__)


class BybitSpotClient:
    def __init__(self, client: BybitDerivativesClient) -> None:
        self.client = client

    async def fetch_ticker(self, symbol: str) -> dict | None:
        if not await self.has_symbol(symbol):
            logger.info("spot_pair_not_listed", extra={"symbol": symbol, "source": "bybit"})
            return None
        try:
            result = await self.client.get("/v5/market/tickers", {"category": "spot", "symbol": symbol})
            items = result.get("list") or []
            if not items:
                logger.warning("spot_ticker_empty", extra={"symbol": symbol, "source": "bybit"})
                return None
            ticker = items[0]
            if not ticker.get("lastPrice"):
                logger.warning("spot_ticker_missing_last_price", extra={"symbol": symbol, "source": "bybit"})
                return None
            return ticker
        except (httpx.HTTPError, BybitAPIError, KeyError, IndexError, ValueError):
            logger.exception("spot_ticker_unavailable", extra={"symbol": symbol, "source": "bybit"})
            return None

    async def has_symbol(self, symbol: str) -> bool:
        try:
            result = await self.client.get("/v5/market/instruments-info", {"category": "spot", "symbol": symbol})
            return bool(result.get("list"))
        except BybitAPIError as exc:
            logger.info("spot_instrument_lookup_failed", extra={"symbol": symbol, "source": "bybit", "error": str(exc)})
            return False
        except httpx.HTTPError:
            logger.exception("spot_instrument_lookup_http_error", extra={"symbol": symbol, "source": "bybit"})
            return False
        except (KeyError, TypeError, ValueError):
            logger.exception("spot_instrument_lookup_parse_error", extra={"symbol": symbol, "source": "bybit"})
            return False

