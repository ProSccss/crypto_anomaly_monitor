"""IVS-1.3 — outcome dataset expansion: passive measurements, frozen behavior."""
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

NEW_FIELDS = ("time_to_peak_minutes", "max_drawdown", "evaluation_duration_minutes")

T0 = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def candle(minutes: int, high: float, low: float) -> SimpleNamespace:
    return SimpleNamespace(high=high, low=low, bucket_ts=T0 + timedelta(minutes=minutes))


def test_existing_outcome_creation_still_works():
    """New fields are not part of outcome creation — column stays NULL."""
    pytest.importorskip("sqlalchemy")
    from sqlalchemy.dialects import postgresql

    from app.model_version import CAM_MODEL_VERSION
    from app.models import PredictiveSetupModel
    from app.services.outcome_evaluator import create_outcome_for_setup

    setup = PredictiveSetupModel(
        id=uuid4(),
        instrument_id=uuid4(),
        setup_type="SHORT_SQUEEZE_SETUP",
        predictive_score=Decimal("61.3"),
        expected_move_score=Decimal("60"),
        expected_move_probability=Decimal("55"),
        expected_direction="LONG",
        estimated_breakout_window="1-4h",
        squeeze_probability=Decimal("70"),
        breakout_probability=Decimal("65"),
        confidence=Decimal("0.9"),
        fingerprint="LABUSDT:SHORT_SQUEEZE_SETUP:LONG",
        reasons=[],
        components={},
        market_regime="PRE_BREAKOUT",
        setup_context="RANGE_COMPRESSION",
        model_version=CAM_MODEL_VERSION,
        created_at=T0,
    )

    captured = {}

    class FakeSession:
        async def execute(self, stmt):
            captured.update(stmt.compile(dialect=postgresql.dialect()).params)

    asyncio.run(create_outcome_for_setup(FakeSession(), setup))
    assert captured["setup_id"] == setup.id
    for field in NEW_FIELDS:
        assert field not in captured


def test_existing_mfe_mae_values_unchanged():
    """Pin current _mfe_mae behavior — IVS-1.3 must not alter it."""
    pytest.importorskip("sqlalchemy")
    from app.services.outcome_evaluator import _mfe_mae

    highs = [Decimal("101"), Decimal("105"), Decimal("103")]
    lows = [Decimal("99"), Decimal("98"), Decimal("100")]

    mfe, mae = _mfe_mae(Decimal("100"), "LONG", highs, lows)
    assert mfe == Decimal("5.0")
    assert mae == Decimal("2.0")

    # SHORT: favorable = downside
    mfe_s, mae_s = _mfe_mae(Decimal("100"), "SHORT", highs, lows)
    assert mfe_s == Decimal("2.0")
    assert mae_s == Decimal("5.0")

    # empty window
    assert _mfe_mae(Decimal("100"), "LONG", [], []) == (Decimal("0"), Decimal("0"))


def test_time_to_peak():
    pytest.importorskip("sqlalchemy")
    from app.services.outcome_evaluator import _time_to_peak

    candles = [candle(1, 101, 99), candle(30, 110, 100), candle(60, 104, 96)]
    # LONG: peak high 110 at +30min
    assert _time_to_peak(candles, "LONG", T0) == 30
    # SHORT: favorable extreme is the lowest low 96 at +60min
    assert _time_to_peak(candles, "SHORT", T0) == 60
    assert _time_to_peak([], "LONG", T0) is None
    # peak in the first minute clamps to 1
    assert _time_to_peak([candle(0, 105, 99)], "LONG", T0) == 1


def test_max_drawdown():
    pytest.importorskip("sqlalchemy")
    from app.services.outcome_evaluator import _max_drawdown

    # LONG: peak 110 at +30min, lowest subsequent low 99 → (110-99)/110 = 10%
    candles = [candle(1, 101, 100), candle(30, 110, 105), candle(60, 104, 99)]
    assert _max_drawdown(candles, "LONG") == Decimal("10.0")

    # SHORT: trough 90 at +30min, highest subsequent high 99 → (99-90)/90 = 10%
    candles_s = [candle(1, 101, 95), candle(30, 96, 90), candle(60, 99, 92)]
    assert _max_drawdown(candles_s, "SHORT") == Decimal("10.0")

    # monotonic favorable move, no retracement beyond the peak candle itself
    flat = [candle(1, 100, 100), candle(30, 105, 105)]
    assert _max_drawdown(flat, "LONG") == Decimal("0.0")

    assert _max_drawdown([], "LONG") is None


def test_new_fields_stay_passive():
    """Guard: passive fields are never referenced by model, features, or scoring."""
    from pathlib import Path

    app = Path(__file__).resolve().parent.parent / "app"
    guarded_sources = [
        app / "services" / "predictive.py",   # setup classification
        app / "services" / "features.py",     # feature generation
        app / "services" / "scoring.py",      # scoring
    ]
    for src_path in guarded_sources:
        src = src_path.read_text(encoding="utf-8")
        for field in NEW_FIELDS:
            assert field not in src, f"{field} referenced in {src_path.name}"
