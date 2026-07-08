"""Lifecycle replay dataset export (IVS-2.1) — the research microscope.

Builds a chronological, one-row-per-minute replay of a symbol's history:
market data, neutral price measurements, EMA research grid, derivatives,
stored CAM state, future behaviour measurements, and empty research labels.

DATA EXTRACTION + MEASUREMENT + EXPORT ONLY:
- no lifecycle detection, no signals, no classification, no trading rules;
- EMA values and distances are reference measurements, not support/resistance;
- future windows are outcome measurement, not prediction;
- CAM state is read from stored feature_snapshots / predictive_setups —
  never recalculated.

MUST NOT import predictive, scoring, telegram, or alert code
(guarded by tests/test_lifecycle_replay_export.py).
"""
from __future__ import annotations

import csv
import io
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import pstdev

from sqlalchemy.ext.asyncio import AsyncSession

from app.model_version import CAM_MODEL_VERSION
from app.repository import Repository

# ---------------------------------------------------------------------------
# Research constants — measurement configuration only
# ---------------------------------------------------------------------------

# |distance| at or below this % counts as an "EMA touch event" (research
# bookkeeping only — NOT support, resistance, signal, or entry).
TOUCH_THRESHOLD_PERCENT = 0.5

RETURN_WINDOWS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "24h": 1440}
AFTER_TOUCH_WINDOWS = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}
FUTURE_WINDOWS = {"15m": 15, "30m": 30, "1h": 60, "4h": 240, "12h": 720, "24h": 1440}

STANDARD_EMA_PERIODS = (20, 50, 200)          # on the 1m base timeline
GRID_EMA_PERIODS = (60, 120, 180, 240)        # microcap research grid
GRID_TIMEFRAMES = {"1m": 1, "3m": 3, "5m": 5}

VOLATILITY_WINDOW_MINUTES = 60      # rolling stdev of 1m returns
DERIVATIVES_TOLERANCE_MINUTES = 5   # snapshot staleness limit
CAM_TOLERANCE_MINUTES = 5           # feature snapshot staleness limit
CHANGE_LOOKBACK_MINUTES = 60        # funding_change / oi_change basis
LIQUIDATION_WINDOW_MINUTES = 60     # trailing liquidation sums


def _grid_ema_names() -> list[str]:
    return [f"ema{p}_{tf}" for tf in GRID_TIMEFRAMES for p in GRID_EMA_PERIODS]


FIELDS: list[str] = (
    ["symbol", "timestamp", "model_version"]
    + ["open", "high", "low", "close", "volume"]
    + [f"return_{w}" for w in RETURN_WINDOWS]
    + ["volatility", "range_percent", "body_ratio", "upper_wick_ratio", "lower_wick_ratio"]
    + [f"ema{p}" for p in STANDARD_EMA_PERIODS]
    + [f"price_distance_ema{p}" for p in STANDARD_EMA_PERIODS]
    + _grid_ema_names()
    + [f"price_distance_{name}" for name in _grid_ema_names()]
    + ["nearest_ema", "nearest_ema_distance_percent", "ema_touch_event", "touched_ema"]
    + [f"after_touch_return_{w}" for w in AFTER_TOUCH_WINDOWS]
    + ["funding_rate", "funding_change", "open_interest", "oi_change",
       "long_liquidations", "short_liquidations", "liquidation_ratio"]
    + ["bp", "sq", "ems", "expected_direction", "setup_detected", "setup_type",
       "market_regime", "setup_context", "confidence"]
    + [item for w in FUTURE_WINDOWS for item in (
        f"future_max_up_percent_{w}", f"future_max_down_percent_{w}",
        f"mfe_{w}", f"mae_{w}",
        f"time_to_high_minutes_{w}", f"time_to_low_minutes_{w}")]
    + ["scenario_label", "lifecycle_phase", "behaviour_label", "notes"]
)


# ---------------------------------------------------------------------------
# Pure measurement helpers — no I/O, no interpretation
# ---------------------------------------------------------------------------


def ema_series(closes: list[float], period: int) -> list[float | None]:
    """Standard EMA, SMA-seeded. None until `period` samples exist."""
    if len(closes) < period:
        return [None] * len(closes)
    out: list[float | None] = [None] * (period - 1)
    value = sum(closes[:period]) / period
    out.append(value)
    k = 2 / (period + 1)
    for close in closes[period:]:
        value = close * k + value * (1 - k)
        out.append(value)
    return out


def resample_closes(
    ts_list: list[datetime], closes: list[float], tf_minutes: int
) -> tuple[list[datetime], list[float]]:
    """Aggregate 1m closes into tf-minute bucket closes (real data only).

    Returns (last_1m_ts_of_bucket, bucket_close) per completed-or-final
    bucket, oldest first. The bucket close is the last 1m close within it.
    """
    bucket_last_ts: list[datetime] = []
    bucket_closes: list[float] = []
    current_bucket: datetime | None = None
    for ts, close in zip(ts_list, closes):
        bucket = ts - timedelta(
            minutes=ts.minute % tf_minutes,
            seconds=ts.second,
            microseconds=ts.microsecond,
        )
        if bucket != current_bucket:
            current_bucket = bucket
            bucket_last_ts.append(ts)
            bucket_closes.append(close)
        else:
            bucket_last_ts[-1] = ts
            bucket_closes[-1] = close
    return bucket_last_ts, bucket_closes


def align_to_rows(
    row_ts: list[datetime],
    series_ts: list[datetime],
    series_values: list[float | None],
) -> list[float | None]:
    """For each row timestamp, the latest series value with ts <= row ts.

    A tf-bucket EMA becomes available at the timestamp of the bucket's last
    1m candle — rows inside a still-forming bucket see the previous bucket.
    """
    out: list[float | None] = []
    pointer = -1
    current: float | None = None
    for ts in row_ts:
        while pointer + 1 < len(series_ts) and series_ts[pointer + 1] <= ts:
            pointer += 1
            current = series_values[pointer]
        out.append(current)
    return out


def distance_percent(close: float, ema: float | None) -> float | None:
    """Signed % distance of price from EMA. Negative = price below EMA."""
    if ema is None or ema <= 0:
        return None
    return round((close - ema) / ema * 100, 4)


def future_extremes(
    ts_list: list[datetime],
    highs: list[float],
    lows: list[float],
    window_minutes: int,
) -> list[tuple[float, datetime, float, datetime] | None]:
    """Per index i: (max_high, its_ts, min_low, its_ts) over (t_i, t_i + W].

    None when the window extends past the end of available data (truncated
    windows would understate extremes). Earliest occurrence of each extreme
    is kept so time-to metrics mean 'first time reached'. O(N) via deques.
    """
    n = len(ts_list)
    result: list[tuple[float, datetime, float, datetime] | None] = [None] * n
    if n == 0:
        return result
    last_ts = ts_list[-1]
    max_dq: deque[int] = deque()
    min_dq: deque[int] = deque()
    right = 0
    for i in range(n):
        limit = ts_list[i] + timedelta(minutes=window_minutes)
        while right < n and ts_list[right] <= limit:
            while max_dq and highs[max_dq[-1]] < highs[right]:
                max_dq.pop()
            max_dq.append(right)
            while min_dq and lows[min_dq[-1]] > lows[right]:
                min_dq.pop()
            min_dq.append(right)
            right += 1
        while max_dq and max_dq[0] <= i:
            max_dq.popleft()
        while min_dq and min_dq[0] <= i:
            min_dq.popleft()
        if last_ts < limit or not max_dq or not min_dq:
            continue  # truncated or empty window → None
        hi, lo = max_dq[0], min_dq[0]
        result[i] = (highs[hi], ts_list[hi], lows[lo], ts_list[lo])
    return result


def _minutes(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() / 60)


def _f(value) -> float | None:
    return float(value) if value is not None else None


# ---------------------------------------------------------------------------
# Row builder — pure, operates on plain dict/list inputs (testable without DB)
# ---------------------------------------------------------------------------


def build_rows(
    symbol: str,
    candles: list[dict],        # {ts, open, high, low, close, volume} floats
    snapshots: list[dict],      # {ts, funding_rate, open_interest}
    liquidations: list[dict],   # {ts, side, notional}
    features: list[dict],       # {ts, bp, sq, ems, direction, confidence}
    setups: list[dict],         # {ts, setup_type, market_regime, setup_context}
) -> list[dict]:
    candles = sorted(candles, key=lambda c: c["ts"])
    snapshots = sorted(snapshots, key=lambda s: s["ts"])
    liquidations = sorted(liquidations, key=lambda x: x["ts"])
    features = sorted(features, key=lambda f: f["ts"])

    ts_list = [c["ts"] for c in candles]
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    close_by_ts = {c["ts"]: c["close"] for c in candles}

    # --- EMA layers (precomputed series) ---
    standard_emas = {p: ema_series(closes, p) for p in STANDARD_EMA_PERIODS}
    grid: dict[str, list[float | None]] = {}
    for tf_name, tf_minutes in GRID_TIMEFRAMES.items():
        if tf_minutes == 1:
            for p in GRID_EMA_PERIODS:
                grid[f"ema{p}_{tf_name}"] = ema_series(closes, p)
        else:
            bucket_ts, bucket_closes = resample_closes(ts_list, closes, tf_minutes)
            for p in GRID_EMA_PERIODS:
                series = ema_series(bucket_closes, p)
                grid[f"ema{p}_{tf_name}"] = align_to_rows(ts_list, bucket_ts, series)

    # --- future extremes per window (precomputed) ---
    futures = {w: future_extremes(ts_list, highs, lows, m) for w, m in FUTURE_WINDOWS.items()}

    # --- setup events by minute ---
    setups_by_ts = {s["ts"].replace(second=0, microsecond=0): s for s in setups}

    # --- pointers for time-aligned auxiliary series ---
    snap_ptr = snap_change_ptr = feat_ptr = liq_lo = liq_hi = 0

    rows: list[dict] = []
    for i, candle in enumerate(candles):
        ts = candle["ts"]
        close = candle["close"]
        row: dict = {
            "symbol": symbol,
            "timestamp": ts.isoformat(),
            "model_version": CAM_MODEL_VERSION,
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": close,
            "volume": candle["volume"],
        }

        # --- returns (past-looking) ---
        for name, minutes in RETURN_WINDOWS.items():
            past = close_by_ts.get(ts - timedelta(minutes=minutes))
            row[f"return_{name}"] = (
                round((close - past) / past * 100, 4) if past else None
            )

        # --- volatility: stdev of 1m returns over trailing window ---
        window_returns = []
        j = i
        while j > 0 and ts_list[j - 1] >= ts - timedelta(minutes=VOLATILITY_WINDOW_MINUTES):
            prev_close = closes[j - 1]
            if prev_close > 0:
                window_returns.append((closes[j] - prev_close) / prev_close * 100)
            j -= 1
        row["volatility"] = round(pstdev(window_returns), 4) if len(window_returns) >= 2 else None

        # --- candle shape ---
        candle_range = candle["high"] - candle["low"]
        row["range_percent"] = round(candle_range / close * 100, 4) if close > 0 else None
        if candle_range > 0:
            row["body_ratio"] = round(abs(close - candle["open"]) / candle_range, 4)
            row["upper_wick_ratio"] = round(
                (candle["high"] - max(candle["open"], close)) / candle_range, 4)
            row["lower_wick_ratio"] = round(
                (min(candle["open"], close) - candle["low"]) / candle_range, 4)
        else:
            row["body_ratio"] = row["upper_wick_ratio"] = row["lower_wick_ratio"] = None

        # --- standard EMAs ---
        for p in STANDARD_EMA_PERIODS:
            ema = standard_emas[p][i]
            row[f"ema{p}"] = round(ema, 8) if ema is not None else None
            row[f"price_distance_ema{p}"] = distance_percent(close, ema)

        # --- microcap grid ---
        for name, series in grid.items():
            ema = series[i]
            row[name] = round(ema, 8) if ema is not None else None
            row[f"price_distance_{name}"] = distance_percent(close, ema)

        # --- nearest EMA + touch event ---
        distances = {}
        for p in STANDARD_EMA_PERIODS:
            distances[f"ema{p}"] = row[f"price_distance_ema{p}"]
        for name in grid:
            distances[name] = row[f"price_distance_{name}"]
        present = {k: v for k, v in distances.items() if v is not None}
        if present:
            nearest = min(present, key=lambda k: abs(present[k]))
            row["nearest_ema"] = nearest
            row["nearest_ema_distance_percent"] = present[nearest]
            touched = abs(present[nearest]) <= TOUCH_THRESHOLD_PERCENT
            row["ema_touch_event"] = touched
            row["touched_ema"] = nearest if touched else None
        else:
            row["nearest_ema"] = row["nearest_ema_distance_percent"] = None
            row["ema_touch_event"] = False
            row["touched_ema"] = None

        # --- after-touch future returns ---
        for name, minutes in AFTER_TOUCH_WINDOWS.items():
            value = None
            if row["ema_touch_event"] and close > 0:
                future_close = close_by_ts.get(ts + timedelta(minutes=minutes))
                if future_close is not None:
                    value = round((future_close - close) / close * 100, 4)
            row[f"after_touch_return_{name}"] = value

        # --- derivatives (latest snapshot at/before ts, within tolerance) ---
        while snap_ptr + 1 < len(snapshots) and snapshots[snap_ptr + 1]["ts"] <= ts:
            snap_ptr += 1
        snap = snapshots[snap_ptr] if snapshots and snapshots[snap_ptr]["ts"] <= ts else None
        if snap and ts - snap["ts"] <= timedelta(minutes=DERIVATIVES_TOLERANCE_MINUTES):
            row["funding_rate"] = snap["funding_rate"]
            row["open_interest"] = snap["open_interest"]
            target = ts - timedelta(minutes=CHANGE_LOOKBACK_MINUTES)
            while (snap_change_ptr + 1 < len(snapshots)
                   and snapshots[snap_change_ptr + 1]["ts"] <= target):
                snap_change_ptr += 1
            earlier = (
                snapshots[snap_change_ptr]
                if snapshots and snapshots[snap_change_ptr]["ts"] <= target
                and target - snapshots[snap_change_ptr]["ts"]
                <= timedelta(minutes=DERIVATIVES_TOLERANCE_MINUTES)
                else None
            )
            if earlier is not None:
                fr, oi = earlier["funding_rate"], earlier["open_interest"]
                row["funding_change"] = (
                    round(snap["funding_rate"] - fr, 10)
                    if None not in (snap["funding_rate"], fr) else None)
                row["oi_change"] = (
                    round((snap["open_interest"] - oi) / oi * 100, 4)
                    if None not in (snap["open_interest"], oi) and oi > 0 else None)
            else:
                row["funding_change"] = row["oi_change"] = None
        else:
            row["funding_rate"] = row["funding_change"] = None
            row["open_interest"] = row["oi_change"] = None

        # --- trailing liquidation sums ---
        window_start = ts - timedelta(minutes=LIQUIDATION_WINDOW_MINUTES)
        while liq_lo < len(liquidations) and liquidations[liq_lo]["ts"] < window_start:
            liq_lo += 1
        while liq_hi < len(liquidations) and liquidations[liq_hi]["ts"] <= ts:
            liq_hi += 1
        longs = shorts = 0.0
        for liq in liquidations[liq_lo:liq_hi]:
            if liq["side"] == "long":
                longs += liq["notional"]
            else:
                shorts += liq["notional"]
        row["long_liquidations"] = round(longs, 2)
        row["short_liquidations"] = round(shorts, 2)
        total = longs + shorts
        row["liquidation_ratio"] = round(longs / total, 4) if total > 0 else None

        # --- CAM state (stored values only, no recalculation) ---
        while feat_ptr + 1 < len(features) and features[feat_ptr + 1]["ts"] <= ts:
            feat_ptr += 1
        feat = features[feat_ptr] if features and features[feat_ptr]["ts"] <= ts else None
        if feat and ts - feat["ts"] <= timedelta(minutes=CAM_TOLERANCE_MINUTES):
            row["bp"] = feat["bp"]
            row["sq"] = feat["sq"]
            row["ems"] = feat["ems"]
            row["expected_direction"] = feat["direction"]
            row["confidence"] = feat["confidence"]
        else:
            row["bp"] = row["sq"] = row["ems"] = None
            row["expected_direction"] = row["confidence"] = None

        setup = setups_by_ts.get(ts)
        row["setup_detected"] = setup is not None
        row["setup_type"] = setup["setup_type"] if setup else None
        row["market_regime"] = setup["market_regime"] if setup else None
        row["setup_context"] = setup["setup_context"] if setup else None

        # --- future behaviour (measurement, not prediction) ---
        direction = row["expected_direction"]
        for w in FUTURE_WINDOWS:
            extremes = futures[w][i]
            up = down = tth = ttl = None
            if extremes is not None and close > 0:
                max_h, ts_h, min_l, ts_l = extremes
                up = round((max_h - close) / close * 100, 4)
                down = round((close - min_l) / close * 100, 4)
                tth = _minutes(ts_h, ts)
                ttl = _minutes(ts_l, ts)
            row[f"future_max_up_percent_{w}"] = up
            row[f"future_max_down_percent_{w}"] = down
            # MFE/MAE oriented by the STORED CAM direction (no interpretation;
            # NULL when direction is absent or NEUTRAL)
            if up is not None and direction == "LONG":
                row[f"mfe_{w}"], row[f"mae_{w}"] = up, down
            elif up is not None and direction == "SHORT":
                row[f"mfe_{w}"], row[f"mae_{w}"] = down, up
            else:
                row[f"mfe_{w}"] = row[f"mae_{w}"] = None
            row[f"time_to_high_minutes_{w}"] = tth
            row[f"time_to_low_minutes_{w}"] = ttl

        # --- research annotation layer (always NULL, manual only) ---
        row["scenario_label"] = None
        row["lifecycle_phase"] = None
        row["behaviour_label"] = None
        row["notes"] = None

        rows.append(row)

    return rows


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if row[k] is None else row[k]) for k in FIELDS})
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Service — read-only orchestration
# ---------------------------------------------------------------------------


class LifecycleReplayExportService:
    """READ ONLY. Loads stored history and emits the replay dataset."""

    async def fetch_rows(self, symbol: str, session: AsyncSession) -> list[dict]:
        data = await Repository(session).lifecycle_replay_data(symbol.upper())
        candles = [
            {"ts": c.bucket_ts, "open": _f(c.open), "high": _f(c.high),
             "low": _f(c.low), "close": _f(c.close), "volume": _f(c.volume_base)}
            for c in data["candles"]
        ]
        snapshots = [
            {"ts": s.ts, "funding_rate": _f(s.funding_rate),
             "open_interest": _f(s.open_interest_usd)}
            for s in data["snapshots"]
        ]
        liquidations = [
            {"ts": e.event_ts, "side": e.liquidated_side, "notional": _f(e.notional_usd)}
            for e in data["liquidations"]
        ]
        features = [
            {"ts": f.bucket_ts, "bp": _f(f.breakout_probability),
             "sq": _f(f.squeeze_probability), "ems": _f(f.expected_move_score),
             "direction": f.expected_direction, "confidence": _f(f.confidence)}
            for f in data["features"]
        ]
        setups = [
            {"ts": s.created_at, "setup_type": s.setup_type,
             "market_regime": s.market_regime, "setup_context": s.setup_context}
            for s in data["setups"]
        ]
        return build_rows(symbol.upper(), candles, snapshots, liquidations, features, setups)

    async def export_csv(self, symbol: str, session: AsyncSession) -> str:
        return rows_to_csv(await self.fetch_rows(symbol, session))
