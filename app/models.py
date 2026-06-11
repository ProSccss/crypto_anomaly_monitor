from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    exchange: Mapped[str] = mapped_column(String(32), default="bybit")
    symbol: Mapped[str] = mapped_column(String(64))
    market_type: Mapped[str] = mapped_column(String(32), default="linear_perpetual")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_instrument_exchange_symbol"),)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    mark_price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    index_price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    spot_price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    open_interest_usd: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    volume_24h_usd: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    funding_rate: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    funding_8h_equivalent: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    long_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    short_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)
    basis_bps: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    spot_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    data_quality_status: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    missing_fields: Mapped[list] = mapped_column(JSONB, default=list)
    source_errors: Mapped[list] = mapped_column(JSONB, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    instrument: Mapped[Instrument] = relationship()
    __table_args__ = (
        UniqueConstraint("instrument_id", "ts", name="uq_snapshot_instrument_ts"),
        Index("ix_snapshot_instrument_ts", "instrument_id", "ts"),
    )


class LiquidationEvent(Base):
    __tablename__ = "liquidation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    liquidated_side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    notional_usd: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    source_event_id: Mapped[str] = mapped_column(String(160), unique=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (Index("ix_liquidation_instrument_ts", "instrument_id", "event_ts"),)


class CandleModel(Base):
    __tablename__ = "candles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    bucket_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval: Mapped[str] = mapped_column(String(8))
    open: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    high: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    low: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    close: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    volume_base: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    turnover_usd: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    __table_args__ = (
        UniqueConstraint("instrument_id", "bucket_ts", "interval", name="uq_candle_instrument_ts_interval"),
        Index("ix_candle_instrument_ts", "instrument_id", "bucket_ts"),
    )


class SignalEvent(Base):
    __tablename__ = "signal_events"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    signal_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    fingerprint: Mapped[str] = mapped_column(String(180))
    evidence: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_signal_fingerprint_created", "fingerprint", "created_at"),)


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[UUID] = mapped_column(ForeignKey("signal_events.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeatureSnapshotModel(Base):
    __tablename__ = "feature_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    bucket_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timeframe: Mapped[str] = mapped_column(String(16))
    price_return_15m: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    price_return_1h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    price_return_4h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    realized_vol_1h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    range_pct_1h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    oi_change_15m: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    oi_change_1h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    oi_acceleration: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    funding_change_1h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    funding_acceleration: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    volume_window_usd_15m: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    volume_zscore: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    long_liquidations_1h: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    short_liquidations_1h: Mapped[Decimal] = mapped_column(Numeric(38, 8))
    liquidation_imbalance: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    basis_bps: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    basis_change_1h: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    compression_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    leverage_buildup_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    funding_pressure_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    volume_accumulation_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    liquidation_imbalance_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    basis_pressure_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    breakout_pressure: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    squeeze_probability: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    breakout_probability: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    expected_move_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    expected_direction: Mapped[str] = mapped_column(String(16), default="NEUTRAL")
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    components: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # V2.6 atomic research features (nullable for backward compat with old rows)
    oi_derisking: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    oi_crowding: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    volume_presence: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    volume_weakness: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    liq_fuel: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    funding_overheating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    funding_cooling: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    price_settling: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    price_return_15m_abs: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    price_return_1h_abs: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    price_return_4h_abs: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    __table_args__ = (
        UniqueConstraint("instrument_id", "bucket_ts", "timeframe", name="uq_feature_instrument_ts_timeframe"),
        Index("ix_feature_instrument_ts", "instrument_id", "bucket_ts"),
    )


class PredictiveSetupModel(Base):
    __tablename__ = "predictive_setups"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    setup_type: Mapped[str] = mapped_column(String(64))
    predictive_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    setup_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    expected_move_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    expected_move_probability: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    expected_direction: Mapped[str] = mapped_column(String(16))
    estimated_breakout_window: Mapped[str] = mapped_column(String(16))
    squeeze_probability: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    breakout_probability: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    fingerprint: Mapped[str] = mapped_column(String(180))
    reasons: Mapped[list] = mapped_column(JSONB)
    components: Mapped[dict] = mapped_column(JSONB)
    # PRE_BREAKOUT | CONTINUATION  (see domain.PredictiveSetup for semantics)
    market_regime: Mapped[str] = mapped_column(String(32), default="PRE_BREAKOUT")
    # TREND_COMPRESSION | RANGE_COMPRESSION | UNKNOWN  (analytics tag, not gate logic)
    setup_context: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_predictive_fingerprint_created", "fingerprint", "created_at"),)


class SetupOutcome(Base):
    __tablename__ = "setup_outcomes"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    setup_id: Mapped[UUID] = mapped_column(ForeignKey("predictive_setups.id", ondelete="CASCADE"), unique=True)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))

    # denormalized setup fields for analytics without JOIN
    setup_direction: Mapped[str] = mapped_column(String(16))
    expected_move_score: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    expected_move_score_bucket: Mapped[str] = mapped_column(String(8))
    breakout_probability: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    squeeze_probability: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    setup_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    setup_version: Mapped[str] = mapped_column(String(16), default="V2.5")
    # Denormalized from predictive_setups.market_regime for analytics without JOIN
    market_regime: Mapped[str] = mapped_column(String(32), default="PRE_BREAKOUT")
    # Denormalized from predictive_setups.setup_context for analytics without JOIN
    setup_context: Mapped[str] = mapped_column(String(32), default="UNKNOWN")

    # prices
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    price_1h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    price_4h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    price_12h: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    # returns % with sign accounting for direction
    return_1h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    return_4h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    return_12h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # MFE / MAE per horizon (% from entry_price)
    mfe_1h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mae_1h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mfe_4h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mae_4h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mfe_12h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    mae_12h: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # hit flags computed via mfe_4h
    hit_3pct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hit_5pct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hit_10pct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # minutes to first hit (NULL if not reached)
    time_to_hit_3pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_hit_5pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_hit_10pct: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # status tracking
    status: Mapped[str] = mapped_column(String(16), default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_outcome_status", "status"),
        Index("ix_outcome_setup_created_at", "setup_created_at"),
        Index("ix_outcome_score_bucket", "expected_move_score_bucket"),
        Index("ix_outcome_instrument_id", "instrument_id"),
    )
