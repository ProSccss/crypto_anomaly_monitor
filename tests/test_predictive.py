from datetime import UTC, datetime

from app.domain import FeatureSnapshot
from app.services.predictive import PredictiveEngine


def feature(**overrides) -> FeatureSnapshot:
    values = dict(
        ts=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
        symbol="LABUSDT",
        timeframe="15m",
        price_return_15m=0.5,
        price_return_1h=1.0,
        price_return_4h=2.0,
        realized_vol_1h=0.4,
        range_pct_1h=1.2,
        oi_change_15m=8.0,
        oi_change_1h=18.0,
        oi_acceleration=6.0,
        funding_change_1h=-0.2,
        funding_acceleration=-0.15,
        volume_window_usd_15m=250000,
        volume_zscore=2.5,
        long_liquidations_1h=20000,
        short_liquidations_1h=160000,
        liquidation_imbalance=0.78,
        basis_bps=50,
        basis_change_1h=30,
        compression_score=70,
        leverage_buildup_score=80,
        funding_pressure_score=75,
        volume_accumulation_score=65,
        liquidation_imbalance_score=70,
        basis_pressure_score=45,
        breakout_pressure=72,
        squeeze_probability=78,
        breakout_probability=74,
        expected_move_score=84,
        expected_direction="LONG",
        confidence=0.9,
        components={
            "funding_pct_8h": -0.45,
            "price_extension_penalty": 0,
            "volume_percentile": 85,
            "short_ratio": 0.62,
            "long_ratio": 0.38,
            "data_quality_status": "GOOD",
        },
    )
    values.update(overrides)
    return FeatureSnapshot(**values)


def test_predictive_engine_classifies_short_squeeze_setup() -> None:
    setup = PredictiveEngine(60).classify(feature())

    assert setup is not None
    assert setup.setup_type == "SHORT_SQUEEZE_SETUP"
    assert setup.expected_direction == "LONG"
    assert setup.expected_move_score == 84
    assert setup.expected_move_probability > 60
    assert "OI acceleration" in setup.reasons


def test_predictive_engine_returns_none_below_threshold() -> None:
    setup = PredictiveEngine(90).classify(
        feature(
            leverage_buildup_score=10,
            breakout_pressure=10,
            squeeze_probability=10,
            breakout_probability=10,
            expected_move_score=10,
        )
    )
    assert setup is None


def test_predictive_engine_requires_good_data_quality() -> None:
    setup = PredictiveEngine(60).classify(feature(components={"funding_pct_8h": -0.45, "volume_percentile": 90, "data_quality_status": "DEGRADED"}))
    assert setup is None
