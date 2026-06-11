import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import websockets

from app.adapters.binance_spot import BinanceSpotClient
from app.adapters.bybit_derivatives import BybitDerivativesClient
from app.adapters.bybit_spot import BybitSpotClient
from app.domain import Candle, Liquidation, Snapshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpotReference:
    price: Decimal | None
    source: str
    payload: dict | None = None


class BybitClient:
    def __init__(
        self,
        rest_url: str,
        ws_url: str,
        binance_spot_rest_url: str = "https://api.binance.com",
        timeout: float = 10.0,
    ) -> None:
        self.rest_url = rest_url.rstrip("/")
        self.ws_url = ws_url
        self.binance_spot_rest_url = binance_spot_rest_url.rstrip("/")
        self.derivatives = BybitDerivativesClient(self.rest_url, timeout)
        self.bybit_spot = BybitSpotClient(self.derivatives)
        self.binance_spot = BinanceSpotClient(self.binance_spot_rest_url, timeout)

    async def close(self) -> None:
        await self.derivatives.close()
        await self.binance_spot.close()

    async def _get(self, path: str, params: dict[str, str]) -> dict:
        return await self.derivatives.get(path, params)

    async def fetch_snapshot(self, symbol: str) -> Snapshot:
        derivative, ratio, instrument = await asyncio.gather(
            self.derivatives.fetch_ticker(symbol),
            self.derivatives.fetch_ratio(symbol),
            self.derivatives.fetch_instrument(symbol),
        )
        ticker = derivative
        mark = Decimal(ticker["markPrice"])
        spot_reference = await self._fetch_spot_reference(symbol, ticker)
        spot = spot_reference.price
        basis_bps = ((mark - spot) / spot * Decimal("10000")) if spot and spot > 0 else None
        ratio_item = ratio.get("list", [{}])[0]
        ts = datetime.now(UTC).replace(microsecond=0)
        instrument_item = instrument
        funding_interval_minutes = Decimal(instrument_item.get("fundingInterval", "480")) or Decimal("480")
        funding_rate = Decimal(ticker["fundingRate"])
        raw = {
            "derivative": ticker,
            "spot": spot_reference.payload,
            "spot_source": spot_reference.source,
            "ratio": ratio_item,
            "instrument": instrument_item,
        }
        return Snapshot(
            ts=ts,
            symbol=symbol,
            last_price=Decimal(ticker["lastPrice"]),
            mark_price=mark,
            index_price=Decimal(ticker["indexPrice"]),
            spot_price=spot,
            open_interest_usd=Decimal(ticker["openInterestValue"]),
            volume_24h_usd=Decimal(ticker["turnover24h"]),
            funding_rate=funding_rate,
            funding_8h_equivalent=funding_rate * Decimal("480") / funding_interval_minutes,
            long_ratio=Decimal(ratio_item["buyRatio"]) if ratio_item.get("buyRatio") else None,
            short_ratio=Decimal(ratio_item["sellRatio"]) if ratio_item.get("sellRatio") else None,
            basis_bps=basis_bps,
            spot_source=spot_reference.source,
            raw_payload=raw,
        )

    async def fetch_candles(self, symbol: str, interval: str = "1", limit: int = 240) -> list[Candle]:
        rows = await self.derivatives.fetch_klines(symbol, interval, limit)
        candles: list[Candle] = []
        for row in rows:
            candles.append(
                Candle(
                    ts=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
                    symbol=symbol,
                    interval=interval,
                    open=Decimal(row[1]),
                    high=Decimal(row[2]),
                    low=Decimal(row[3]),
                    close=Decimal(row[4]),
                    volume_base=Decimal(row[5]),
                    turnover_usd=Decimal(row[6]),
                )
            )
        return sorted(candles, key=lambda item: item.ts)

    async def _fetch_spot_reference(self, symbol: str, derivative_ticker: dict) -> SpotReference:
        spot_ticker = await self.bybit_spot.fetch_ticker(symbol)
        if spot_ticker:
            return SpotReference(Decimal(spot_ticker["lastPrice"]), "bybit_spot_ticker", spot_ticker)

        binance_ticker = await self.binance_spot.fetch_ticker(symbol)
        if binance_ticker:
            return SpotReference(Decimal(binance_ticker["price"]), "binance_spot_ticker", binance_ticker)

        index_price = derivative_ticker.get("indexPrice")
        if index_price:
            return SpotReference(Decimal(index_price), "bybit_derivatives_index_price", None)

        return SpotReference(None, "unavailable", None)

    async def liquidation_stream(self, symbols: list[str]) -> AsyncIterator[Liquidation]:
        delay = 1
        while True:
            try:
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as socket:
                    await socket.send(
                        json.dumps({"op": "subscribe", "args": [f"allLiquidation.{s}" for s in symbols]})
                    )
                    delay = 1
                    async for message in socket:
                        payload = json.loads(message)
                        if not payload.get("topic", "").startswith("allLiquidation."):
                            continue
                        for item in payload.get("data", []):
                            event_ts = datetime.fromtimestamp(int(item["T"]) / 1000, tz=UTC)
                            quantity = Decimal(item["v"])
                            price = Decimal(item["p"])
                            identity = f"{item['s']}:{item['T']}:{item['S']}:{item['v']}:{item['p']}"
                            yield Liquidation(
                                ts=event_ts,
                                symbol=item["s"],
                                liquidated_side="long" if item["S"] == "Buy" else "short",
                                quantity=quantity,
                                price=price,
                                notional_usd=quantity * price,
                                source_event_id=hashlib.sha256(identity.encode()).hexdigest(),
                                raw_payload=item,
                            )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("liquidation_stream_error")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
