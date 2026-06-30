"""Infrastructure → domain boundary for feature data.

Maps FeatureSnapshotModel (SQLAlchemy, Decimal fields) to FeatureSnapshot (domain, float fields).
Used by: ResearchService, Backtester (future), tests.
"""
from __future__ import annotations

from app.domain import FeatureSnapshot
from app.models import FeatureSnapshotModel


def to_feature_snapshot(symbol: str, model: FeatureSnapshotModel) -> FeatureSnapshot:
    """Convert a stored FeatureSnapshotModel back to a domain FeatureSnapshot.

    V2.6 atomic research features are nullable in DB for backward compatibility
    with rows written before V2.6 — default to 0.0 when absent.
    """
    return FeatureSnapshot(
        ts=model.bucket_ts,
        symbol=symbol,
        timeframe=model.timeframe,
        price_return_15m=float(model.price_return_15m),
        price_return_1h=float(model.price_return_1h),
        price_return_4h=float(model.price_return_4h),
        realized_vol_1h=float(model.realized_vol_1h),
        range_pct_1h=float(model.range_pct_1h),
        oi_change_15m=float(model.oi_change_15m),
        oi_change_1h=float(model.oi_change_1h),
        oi_acceleration=float(model.oi_acceleration),
        funding_change_1h=float(model.funding_change_1h),
        funding_acceleration=float(model.funding_acceleration),
        volume_window_usd_15m=float(model.volume_window_usd_15m),
        volume_zscore=float(model.volume_zscore),
        long_liquidations_1h=float(model.long_liquidations_1h),
        short_liquidations_1h=float(model.short_liquidations_1h),
        liquidation_imbalance=float(model.liquidation_imbalance),
        basis_bps=float(model.basis_bps),
        basis_change_1h=float(model.basis_change_1h),
        compression_score=float(model.compression_score),
        leverage_buildup_score=float(model.leverage_buildup_score),
        funding_pressure_score=float(model.funding_pressure_score),
        volume_accumulation_score=float(model.volume_accumulation_score),
        liquidation_imbalance_score=float(model.liquidation_imbalance_score),
        basis_pressure_score=float(model.basis_pressure_score),
        breakout_pressure=float(model.breakout_pressure),
        squeeze_probability=float(model.squeeze_probability),
        breakout_probability=float(model.breakout_probability),
        expected_move_score=float(model.expected_move_score),
        expected_direction=model.expected_direction,
        confidence=float(model.confidence),
        components=dict(model.components),
        # V2.6 atomic research features — nullable for backward compat
        oi_derisking=float(model.oi_derisking or 0),
        oi_crowding=float(model.oi_crowding or 0),
        volume_presence=float(model.volume_presence or 0),
        volume_weakness=float(model.volume_weakness or 0),
        liq_fuel=float(model.liq_fuel or 0),
        funding_overheating=float(model.funding_overheating or 0),
        funding_cooling=float(model.funding_cooling or 0),
        price_settling=float(model.price_settling or 0),
        price_return_15m_abs=float(model.price_return_15m_abs or 0),
        price_return_1h_abs=float(model.price_return_1h_abs or 0),
        price_return_4h_abs=float(model.price_return_4h_abs or 0),
    )
