from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain import Liquidation, Snapshot
from app.services.features import FeatureEngine

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def snap(minutes_ago: int, price: str, oi: str, funding: str, volume: str) -> Snapshot:
    value = Decimal(price)
    return Snapshot(
        ts=NOW - timedelta(minutes=minutes_ago),
        symbol="LABUSDT",
        last_price=value,
        mark_price=value,
        index_price=value,
        spot_price=value,
        open_interest_usd=Decimal(oi),
        volume_24h_usd=Decimal(volume),
        funding_rate=Decimal(funding),
        funding_8h_equivalent=Decimal(funding),
        long_ratio=Decimal(".5"),
        short_ratio=Decimal(".5"),
        basis_bps=Decimal("20"),
        spot_source="binance_spot_ticker",
        data_quality_score=95,
        data_quality_status="GOOD",
        raw_payload={"spot_source": "binance_spot_ticker", "ratio": {"buyRatio": "0.5"}},
    )


def test_feature_engine_calculates_acceleration_and_probabilities() -> None:
    snapshots = [
        snap(240, "1.00", "1000000", "-0.0005", "10000000"),
        snap(60, "1.00", "1100000", "-0.0010", "10100000"),
        snap(45, "1.002", "1120000", "-0.0015", "10150000"),
        snap(30, "1.001", "1140000", "-0.0020", "10200000"),
        snap(15, "1.003", "1160000", "-0.0028", "10280000"),
        snap(0, "1.004", "1250000", "-0.0040", "10450000"),
    ]
    liquidations = [
        Liquidation(NOW - timedelta(minutes=10), "LABUSDT", "short", Decimal("1"), Decimal("1"), Decimal("150000"), "a"),
        Liquidation(NOW - timedelta(minutes=5), "LABUSDT", "long", Decimal("1"), Decimal("1"), Decimal("25000"), "b"),
    ]

    feature = FeatureEngine().calculate(snapshots, liquidations)

    assert feature is not None
    assert feature.oi_change_1h > 10
    assert feature.oi_acceleration > 0
    assert feature.funding_acceleration < 0
    assert feature.liquidation_imbalance > 0
    assert feature.squeeze_probability > 0
    assert feature.breakout_probability > 0
    assert feature.expected_move_score > 0
    assert feature.expected_direction in {"LONG", "SHORT", "NEUTRAL"}
