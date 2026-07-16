"""One-off historical 1m candle backfill from Bybit REST (SPEC_CANDLE_BACKFILL).

Usage (inside the api container, DATABASE_URL configured):

    python scripts/backfill_candles.py LABUSDT HUSDT

Rules (per spec):
- INSERT missing bucket_ts only; existing rows are NEVER updated or deleted
  (ON CONFLICT DO NOTHING on the existing unique constraint).
- Idempotent: a re-run inserts nothing new and changes nothing.
- Paginates GET /v5/market/kline (category=linear, interval=1, limit=1000)
  backwards by end-timestamp until the exchange returns no data (= listing).
- Sleeps between requests to respect the public rate limit.
- Derivatives and CAM state are NOT backfilled (irrecoverable / model was
  not running — stays NULL by design).
- No app-code imports, no migrations, MODEL FREEZE untouched.

Safety verification built in: pre-run control sample of existing rows is
re-checked after the run (values must be byte-identical) and row counts
must satisfy before + inserted == after.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import asyncpg
import httpx

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
PAGE_LIMIT = 1000
REQUEST_PAUSE_SECONDS = 0.5    # gentle: the live scanner shares this IP's quota
RATE_LIMIT_RETRIES = 6
RATE_LIMIT_BACKOFF_SECONDS = 5
MAX_PAGES = 5000               # hard stop: ~9.5 years of 1m candles
CONTROL_SAMPLE_SIZE = 500
MAX_GAPS_LISTED = 50

INSERT_SQL = """
INSERT INTO candles (instrument_id, bucket_ts, interval,
                     open, high, low, close, volume_base, turnover_usd)
VALUES ($1, $2, '1', $3, $4, $5, $6, $7, $8)
ON CONFLICT ON CONSTRAINT uq_candle_instrument_ts_interval DO NOTHING
"""


def _db_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://monitor:monitor@localhost:5432/monitor")
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _minute_floor(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _gaps(minutes: set[datetime], start: datetime, end: datetime) -> list[tuple[datetime, datetime, int]]:
    """Contiguous missing ranges (start_ts, end_ts, missing_count) in [start, end]."""
    gaps = []
    gap_start = None
    current = start
    while current <= end:
        missing = current not in minutes
        if missing and gap_start is None:
            gap_start = current
        elif not missing and gap_start is not None:
            gaps.append((gap_start, current - timedelta(minutes=1),
                         int((current - gap_start).total_seconds() // 60)))
            gap_start = None
        current += timedelta(minutes=1)
    if gap_start is not None:
        gaps.append((gap_start, end, int((end - gap_start).total_seconds() // 60) + 1))
    return gaps


async def _fetch_page(client: httpx.AsyncClient, symbol: str, end_ms: int) -> list[list[str]]:
    for attempt in range(RATE_LIMIT_RETRIES):
        response = await client.get(BYBIT_KLINE_URL, params={
            "category": "linear", "symbol": symbol, "interval": "1",
            "limit": PAGE_LIMIT, "end": end_ms,
        })
        if response.status_code == 429:
            await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1))
            continue
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") == 0:
            return payload["result"]["list"]  # newest first
        message = payload.get("retMsg", "")
        if payload.get("retCode") == 10006 or "Too many" in message or "Rate" in message:
            wait = RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
            print(f"  rate limited, backing off {wait}s")
            await asyncio.sleep(wait)
            continue
        raise RuntimeError(f"Bybit error for {symbol}: {message}")
    raise RuntimeError(f"persistent rate limiting for {symbol}, aborting page fetch")


async def backfill_symbol(conn: asyncpg.Connection, client: httpx.AsyncClient, symbol: str) -> None:
    print(f"\n{'=' * 60}\nBACKFILL {symbol}\n{'=' * 60}")

    instrument_id = await conn.fetchval(
        "SELECT id FROM instruments WHERE exchange = 'bybit' AND symbol = $1", symbol)
    if instrument_id is None:
        print(f"  SKIP: instrument {symbol} not found in DB")
        return

    rows = await conn.fetch(
        "SELECT bucket_ts FROM candles WHERE instrument_id = $1 AND interval = '1'",
        instrument_id)
    existing = {r["bucket_ts"] for r in rows}
    count_before = len(existing)

    # control sample: values of pre-existing rows must survive untouched
    control = await conn.fetch(
        """SELECT bucket_ts, open, high, low, close, volume_base FROM candles
           WHERE instrument_id = $1 AND interval = '1'
           ORDER BY bucket_ts LIMIT $2""",
        instrument_id, CONTROL_SAMPLE_SIZE)

    now = _minute_floor(datetime.now(UTC))
    pre_min = min(existing) if existing else None
    pre_gaps = _gaps(existing, pre_min, now) if pre_min else []
    print(f"  existing rows: {count_before}"
          + (f", span {pre_min} → {now}, known gaps: {len(pre_gaps)}" if pre_min else ""))

    # --- paginate backwards from now to listing ---
    inserted_total = 0
    end_ms = int(now.timestamp() * 1000) + 59_999
    oldest_seen: datetime | None = None
    for page in range(MAX_PAGES):
        candles = await _fetch_page(client, symbol, end_ms)
        if not candles:
            break
        batch = []
        for row in candles:
            ts = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
            if oldest_seen is None or ts < oldest_seen:
                oldest_seen = ts
            if ts in existing:
                continue
            batch.append((
                instrument_id, ts,
                Decimal(row[1]), Decimal(row[2]), Decimal(row[3]), Decimal(row[4]),
                Decimal(row[5]), Decimal(row[6]),
            ))
            existing.add(ts)
        if batch:
            await conn.executemany(INSERT_SQL, batch)
            inserted_total += len(batch)
        if page % 25 == 0:
            print(f"  page {page:>4}: fetched to {oldest_seen}, inserted so far {inserted_total}")
        end_ms = int(candles[-1][0]) - 1  # continue before oldest row of this page
        await asyncio.sleep(REQUEST_PAUSE_SECONDS)
    else:
        print(f"  WARNING: MAX_PAGES={MAX_PAGES} reached before listing")

    listing = oldest_seen or pre_min
    if listing is None:
        print("  no data returned by exchange and none stored — nothing to do")
        return

    # --- per-gap fill report ---
    if pre_min:
        filled_in_gaps = 0
        for gap_start, gap_end, missing in pre_gaps:
            got = sum(
                1 for k in range(missing)
                if (gap_start + timedelta(minutes=k)) in existing
            )
            filled_in_gaps += got
            if got:
                print(f"  gap {gap_start} → {gap_end} ({missing}m): inserted {got}m")
        history_extension = inserted_total - filled_in_gaps
        print(f"  history extension before {pre_min}: {history_extension}m inserted")

    # --- verification: existing rows untouched ---
    count_after = await conn.fetchval(
        "SELECT count(*) FROM candles WHERE instrument_id = $1 AND interval = '1'",
        instrument_id)
    control_ok = True
    for sample in control:
        current = await conn.fetchrow(
            """SELECT open, high, low, close, volume_base FROM candles
               WHERE instrument_id = $1 AND interval = '1' AND bucket_ts = $2""",
            instrument_id, sample["bucket_ts"])
        if current is None or any(current[k] != sample[k]
                                  for k in ("open", "high", "low", "close", "volume_base")):
            control_ok = False
            print(f"  CONTROL FAIL at {sample['bucket_ts']}")
    # The live scanner inserts fresh candles concurrently, so count_after may
    # exceed before+inserted by a few rows; it must never be below it.
    scanner_extra = count_after - (count_before + inserted_total)
    counts_ok = scanner_extra >= 0
    print(f"  verification: counts {'PASS' if counts_ok else 'FAIL'} "
          f"({count_before} + {inserted_total} inserted = {count_before + inserted_total}, "
          f"actual {count_after}, concurrent scanner rows: {scanner_extra}), "
          f"control sample ({len(control)} rows) {'PASS' if control_ok else 'FAIL'}")

    # --- coverage + remaining gaps ---
    total_minutes = int((now - listing).total_seconds() // 60) + 1
    coverage_before = count_before / total_minutes * 100
    coverage_after = len(existing) / total_minutes * 100
    print(f"  listing (earliest candle): {listing}")
    print(f"  coverage vs listing→now:   before {coverage_before:.2f}%  →  after {coverage_after:.2f}%")

    remaining = _gaps(existing, listing, now)
    print(f"  remaining gaps: {len(remaining)}"
          f" ({sum(g[2] for g in remaining)}m total — exchange-side gaps are acceptable)")
    for gap_start, gap_end, missing in remaining[:MAX_GAPS_LISTED]:
        print(f"    {gap_start} → {gap_end}  ({missing}m)")
    if len(remaining) > MAX_GAPS_LISTED:
        print(f"    ... and {len(remaining) - MAX_GAPS_LISTED} more")


async def main() -> None:
    symbols = [s.upper() for s in sys.argv[1:]]
    if not symbols:
        print("usage: python scripts/backfill_candles.py SYMBOL [SYMBOL...]")
        sys.exit(1)
    conn = await asyncpg.connect(_db_dsn())
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for symbol in symbols:
                await backfill_symbol(conn, client, symbol)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
