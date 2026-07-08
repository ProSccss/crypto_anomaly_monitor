"""IVS-2.1 — lifecycle replay export: measurement math, alignment, isolation."""
import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "app" / "services" / "lifecycle_replay_export.py"
)

T0 = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def make_candles(n, close_fn=lambda i: 100.0, high_fn=None, low_fn=None):
    candles = []
    for i in range(n):
        close = close_fn(i)
        candles.append({
            "ts": T0 + timedelta(minutes=i),
            "open": close,
            "high": high_fn(i) if high_fn else close,
            "low": low_fn(i) if low_fn else close,
            "close": close,
            "volume": 1000.0,
        })
    return candles


def build(candles, **kw):
    from app.services.lifecycle_replay_export import build_rows

    return build_rows(
        "LABUSDT", candles,
        kw.get("snapshots", []), kw.get("liquidations", []),
        kw.get("features", []), kw.get("setups", []),
    )


def test_chronological_order():
    pytest.importorskip("sqlalchemy")
    candles = make_candles(10)
    shuffled = [candles[i] for i in (4, 0, 7, 2, 9, 1, 8, 3, 6, 5)]
    rows = build(shuffled)
    stamps = [r["timestamp"] for r in rows]
    assert stamps == sorted(stamps)
    assert len(rows) == 10


def test_null_handling():
    pytest.importorskip("sqlalchemy")
    rows = build(make_candles(5))  # no snapshots/features/liq/setups, EMAs unfilled
    row = rows[-1]
    # derivatives + CAM absent → NULL
    for field in ("funding_rate", "funding_change", "open_interest", "oi_change",
                  "liquidation_ratio", "bp", "sq", "ems", "expected_direction",
                  "confidence", "setup_type", "market_regime", "setup_context"):
        assert row[field] is None, field
    assert row["setup_detected"] is False
    # EMAs need 20+ samples → NULL, so no nearest/touch
    assert row["ema20"] is None and row["nearest_ema"] is None
    assert row["ema_touch_event"] is False and row["touched_ema"] is None
    # 24h return impossible with 5 candles
    assert row["return_24h"] is None
    # annotation layer always NULL
    for field in ("scenario_label", "lifecycle_phase", "behaviour_label", "notes"):
        assert row[field] is None, field


def test_ema_calculation():
    pytest.importorskip("sqlalchemy")
    from app.services.lifecycle_replay_export import ema_series

    # SMA seed (1+2+3)/3 = 2, k = 0.5:  4*0.5+2*0.5 = 3;  5*0.5+3*0.5 = 4
    assert ema_series([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]
    assert ema_series([1, 2], 3) == [None, None]


def test_distance_calculation():
    pytest.importorskip("sqlalchemy")
    from app.services.lifecycle_replay_export import distance_percent

    assert distance_percent(102.0, 100.0) == 2.0
    assert distance_percent(97.6, 100.0) == -2.4
    assert distance_percent(100.0, None) is None


def test_timeframe_alignment_no_lookahead():
    pytest.importorskip("sqlalchemy")
    from app.services.lifecycle_replay_export import align_to_rows, resample_closes

    ts = [T0 + timedelta(minutes=i) for i in range(9)]        # 12:00 .. 12:08
    closes = [float(i) for i in range(9)]
    bucket_ts, bucket_closes = resample_closes(ts, closes, 3)
    # buckets 12:00/12:03/12:06 close at 12:02/12:05/12:08 with closes 2/5/8
    assert bucket_ts == [ts[2], ts[5], ts[8]]
    assert bucket_closes == [2.0, 5.0, 8.0]

    aligned = align_to_rows(ts, bucket_ts, bucket_closes)
    # rows inside a forming bucket see the previous completed bucket only
    assert aligned == [None, None, 2.0, 2.0, 2.0, 5.0, 5.0, 5.0, 8.0]


def test_future_window_math():
    pytest.importorskip("sqlalchemy")
    # flat 100, spike high 110 at +10m, dip low 95 at +20m, 40 candles
    candles = make_candles(
        40,
        high_fn=lambda i: 110.0 if i == 10 else 100.0,
        low_fn=lambda i: 95.0 if i == 20 else 100.0,
    )
    rows = build(candles)
    row0 = rows[0]
    # 30m window from t0 sees both extremes
    assert row0["future_max_up_percent_30m"] == 10.0
    assert row0["future_max_down_percent_30m"] == 5.0
    assert row0["time_to_high_minutes_30m"] == 10
    assert row0["time_to_low_minutes_30m"] == 20
    # 15m window sees the spike but not the dip
    assert row0["future_max_up_percent_15m"] == 10.0
    assert row0["future_max_down_percent_15m"] == 0.0
    # truncated windows at the tail are NULL, not understated
    assert rows[-1]["future_max_up_percent_15m"] is None
    assert row0["future_max_up_percent_24h"] is None  # only 40m of data
    # mfe/mae need a stored CAM direction; none supplied → NULL
    assert row0["mfe_30m"] is None and row0["mae_30m"] is None


def test_touch_and_after_touch_returns():
    pytest.importorskip("sqlalchemy")
    # constant closes → ema20 == close → distance 0 → touch from row 19
    rows = build(make_candles(30))
    row19 = rows[19]
    assert row19["ema20"] == 100.0
    assert row19["nearest_ema"] == "ema20"
    assert row19["nearest_ema_distance_percent"] == 0.0
    assert row19["ema_touch_event"] is True
    assert row19["touched_ema"] == "ema20"
    assert row19["after_touch_return_5m"] == 0.0     # flat future
    assert row19["after_touch_return_4h"] is None    # no candle 4h ahead
    # pre-EMA rows: no touch, no after-touch values
    assert rows[0]["ema_touch_event"] is False
    assert rows[0]["after_touch_return_5m"] is None


def test_cam_state_and_direction_oriented_mfe():
    pytest.importorskip("sqlalchemy")
    candles = make_candles(
        40,
        high_fn=lambda i: 110.0 if i == 10 else 100.0,
        low_fn=lambda i: 95.0 if i == 20 else 100.0,
    )
    features = [{"ts": T0, "bp": 30.0, "sq": 40.0, "ems": 25.0,
                 "direction": "SHORT", "confidence": 0.9}]
    setups = [{"ts": T0, "setup_type": "LONG_SQUEEZE_SETUP",
               "market_regime": "CONTINUATION", "setup_context": "TREND_COMPRESSION"}]
    rows = build(candles, features=features, setups=setups)
    row0 = rows[0]
    assert row0["bp"] == 30.0 and row0["expected_direction"] == "SHORT"
    assert row0["setup_detected"] is True and row0["setup_type"] == "LONG_SQUEEZE_SETUP"
    assert rows[1]["setup_detected"] is False
    # SHORT: mfe = down move, mae = up move
    assert row0["mfe_30m"] == 5.0 and row0["mae_30m"] == 10.0
    # stale feature (>5 min) → CAM NULL
    assert rows[10]["bp"] is None


def test_static_guard_no_forbidden_imports():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden = ("predictive", "scoring", "telegram", "alert")
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        for module in modules:
            for bad in forbidden:
                assert bad not in module, f"forbidden import '{module}'"
