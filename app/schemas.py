from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts: datetime
    last_price: Decimal
    mark_price: Decimal
    spot_price: Decimal | None
    open_interest_usd: Decimal
    funding_rate: Decimal
    funding_8h_equivalent: Decimal
    basis_bps: Decimal | None
    spot_source: str | None
    data_quality_score: Decimal | None
    data_quality_status: str


class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    signal_type: str
    severity: str
    score: Decimal
    confidence: Decimal
    evidence: dict
    created_at: datetime


class FeatureSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bucket_ts: datetime
    timeframe: str
    price_return_15m: Decimal
    price_return_1h: Decimal
    price_return_4h: Decimal
    realized_vol_1h: Decimal
    range_pct_1h: Decimal
    oi_change_15m: Decimal
    oi_change_1h: Decimal
    oi_acceleration: Decimal
    funding_change_1h: Decimal
    funding_acceleration: Decimal
    volume_window_usd_15m: Decimal
    volume_zscore: Decimal
    liquidation_imbalance: Decimal
    compression_score: Decimal
    leverage_buildup_score: Decimal
    breakout_pressure: Decimal
    squeeze_probability: Decimal
    breakout_probability: Decimal
    expected_move_score: Decimal
    expected_direction: str
    confidence: Decimal
    components: dict


class PredictiveSetupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    setup_type: str
    predictive_score: Decimal
    setup_score: Decimal
    expected_move_score: Decimal
    expected_move_probability: Decimal
    expected_direction: str
    estimated_breakout_window: str
    squeeze_probability: Decimal
    breakout_probability: Decimal
    confidence: Decimal
    reasons: list[str]
    components: dict
    market_regime: str
    setup_context: str
    status: str
    created_at: datetime


class ScannerItemResponse(BaseModel):
    symbol: str
    expected_move_score: Decimal
    expected_direction: str
    breakout_probability: Decimal
    squeeze_probability: Decimal
    confidence: Decimal
    data_quality_status: str | None = None
    updated_at: datetime | None = None


class FeatureBucket(BaseModel):
    count: int
    avg_return_4h: float | None
    avg_mfe_4h: float | None
    avg_mae_4h: float | None
    hit_rate_3pct: float | None
    hit_rate_5pct: float | None
    hit_rate_10pct: float | None


class FeatureResearchItem(BaseModel):
    feature: str
    total_observations: int
    buckets: dict[str, FeatureBucket]


class FeatureResearchResponse(BaseModel):
    total_complete_outcomes: int
    note: str
    features: list[FeatureResearchItem]


class BucketStats(BaseModel):
    count: int
    avg_return_1h: float | None
    avg_return_4h: float | None
    avg_return_12h: float | None
    avg_mfe_4h: float | None
    hit_rate_3pct: float | None
    hit_rate_5pct: float | None
    hit_rate_10pct: float | None
    avg_time_to_hit_5pct_minutes: float | None


class PerformanceResponse(BaseModel):
    total_setups: int
    complete_outcomes: int
    partial_outcomes: int
    hit_threshold_pct: float
    market_regime: str | None   # None = all regimes combined
    setup_context: str | None   # None = all contexts combined
    hit_rate_long: float | None
    hit_rate_short: float | None
    by_breakout_probability: dict[str, BucketStats]
    by_expected_move_score: dict[str, BucketStats]


class CalibrationBucket(BaseModel):
    count: int
    avg_actual_return_4h: float | None
    avg_mfe_4h: float | None
    avg_mae_4h: float | None
    hit_rate_5pct: float | None
    avg_time_to_hit_5pct_minutes: float | None


class CalibrationResponse(BaseModel):
    total_complete: int
    market_regime: str | None   # None = all regimes combined
    setup_context: str | None   # None = all contexts combined
    by_expected_move_score: dict[str, CalibrationBucket]
    note: str


# ── V2.7 Observability ────────────────────────────────────────────────────────

class GateAStatus(BaseModel):
    """Gate A evaluation: bp>=25 AND sq>=30 AND conf>=0.80 AND dq=GOOD."""
    status: str                    # "PASS" | "FAIL" | "NO_DATA"
    bp: float | None = None
    sq: float | None = None
    bp_gap: float | None = None   # > 0 means bp still needs this much more
    sq_gap: float | None = None   # > 0 means sq still needs this much more


class GateBStatus(BaseModel):
    """Gate B evaluation: sq>=45 AND ems>=40 AND vol>=50 AND conf>=0.80 AND dq=GOOD."""
    status: str                     # "PASS" | "FAIL" | "NO_DATA"
    sq: float | None = None
    ems: float | None = None
    vol_pct: float | None = None
    sq_gap: float | None = None    # > 0 means sq still needs this much more
    ems_gap: float | None = None
    vol_gap: float | None = None


class RegimeAuditItem(BaseModel):
    symbol: str
    updated_at: datetime | None = None
    data_quality: str | None = None
    confidence: float | None = None
    breakout_probability: float | None = None
    squeeze_probability: float | None = None
    expected_move_score: float | None = None
    volume_percentile: float | None = None
    price_return_4h: float | None = None
    market_regime: str | None = None   # set only if a gate passes
    gate_a: GateAStatus
    gate_b: GateBStatus


class RegimeAuditResponse(BaseModel):
    as_of: datetime
    pre_breakout_candidates: int
    continuation_candidates: int
    symbols: list[RegimeAuditItem]


class DirectionCondition(BaseModel):
    funding_pct_8h: float
    long_ratio: float
    short_ratio: float
    expected_direction: str
    long_squeeze_eligible: bool    # funding<=-0.15 OR short_ratio>=0.60
    short_squeeze_eligible: bool   # funding>=0.15  OR long_ratio>=0.60
    neutral_breakout_eligible: bool  # expected_direction==NEUTRAL
    any_direction_met: bool


class WhyNotResponse(BaseModel):
    symbol: str
    updated_at: datetime | None = None
    gate_a: GateAStatus
    gate_b: GateBStatus
    direction: DirectionCondition | None = None   # populated when a gate passes
    verdict: str
