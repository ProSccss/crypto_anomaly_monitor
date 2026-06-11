from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Snapshot:
    ts: datetime
    symbol: str
    last_price: Decimal
    mark_price: Decimal
    index_price: Decimal
    spot_price: Decimal | None
    open_interest_usd: Decimal
    volume_24h_usd: Decimal
    funding_rate: Decimal
    funding_8h_equivalent: Decimal
    long_ratio: Decimal | None = None
    short_ratio: Decimal | None = None
    basis_bps: Decimal | None = None
    spot_source: str | None = None
    data_quality_score: float | None = None
    data_quality_status: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    source_errors: list[str] = field(default_factory=list)
    raw_payload: dict = field(default_factory=dict)

    def with_quality(self, report) -> "Snapshot":
        return Snapshot(
            ts=self.ts,
            symbol=self.symbol,
            last_price=self.last_price,
            mark_price=self.mark_price,
            index_price=self.index_price,
            spot_price=self.spot_price,
            open_interest_usd=self.open_interest_usd,
            volume_24h_usd=self.volume_24h_usd,
            funding_rate=self.funding_rate,
            funding_8h_equivalent=self.funding_8h_equivalent,
            long_ratio=self.long_ratio,
            short_ratio=self.short_ratio,
            basis_bps=self.basis_bps,
            spot_source=self.spot_source,
            data_quality_score=report.score,
            data_quality_status=report.status,
            missing_fields=report.missing_fields,
            source_errors=report.source_errors,
            raw_payload=self.raw_payload,
        )


@dataclass(frozen=True)
class Liquidation:
    ts: datetime
    symbol: str
    liquidated_side: str
    quantity: Decimal
    price: Decimal
    notional_usd: Decimal
    source_event_id: str
    raw_payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Candle:
    ts: datetime
    symbol: str
    interval: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_base: Decimal
    turnover_usd: Decimal


@dataclass(frozen=True)
class Signal:
    signal_type: str
    score: float
    severity: str
    confidence: float
    evidence: dict[str, float | str | None]


@dataclass(frozen=True)
class FeatureSnapshot:
    ts: datetime
    symbol: str
    timeframe: str
    price_return_15m: float
    price_return_1h: float
    price_return_4h: float
    realized_vol_1h: float
    range_pct_1h: float
    oi_change_15m: float
    oi_change_1h: float
    oi_acceleration: float
    funding_change_1h: float
    funding_acceleration: float
    volume_window_usd_15m: float
    volume_zscore: float
    long_liquidations_1h: float
    short_liquidations_1h: float
    liquidation_imbalance: float
    basis_bps: float
    basis_change_1h: float
    compression_score: float
    leverage_buildup_score: float
    funding_pressure_score: float
    volume_accumulation_score: float
    liquidation_imbalance_score: float
    basis_pressure_score: float
    breakout_pressure: float
    squeeze_probability: float
    breakout_probability: float
    expected_move_score: float
    expected_direction: str
    confidence: float
    components: dict[str, float | str | None] = field(default_factory=dict)
    # V2.6 atomic research features — stored as-is, no composites, no expert weights.
    # Composites (continuation_score etc.) will be built AFTER empirical validation.
    oi_derisking: float = 0.0
    oi_crowding: float = 0.0
    volume_presence: float = 0.0
    volume_weakness: float = 0.0
    liq_fuel: float = 0.0
    funding_overheating: float = 0.0
    funding_cooling: float = 0.0
    price_settling: float = 0.0
    # Raw price movement magnitudes (unsigned) for impulse context
    price_return_15m_abs: float = 0.0
    price_return_1h_abs: float = 0.0
    price_return_4h_abs: float = 0.0


@dataclass(frozen=True)
class PredictiveSetup:
    ts: datetime
    symbol: str
    setup_type: str
    predictive_score: float
    setup_score: float
    expected_move_score: float
    expected_move_probability: float
    expected_direction: str
    estimated_breakout_window: str
    squeeze_probability: float
    breakout_probability: float
    confidence: float
    reasons: list[str]
    components: dict[str, float | str | None]
    # Market regime at the moment of setup creation.
    # PRE_BREAKOUT  — Gate A: price hasn't moved, compression building
    # CONTINUATION  — Gate B: price already moved, squeeze still active
    market_regime: str = "PRE_BREAKOUT"
    # Price context at the moment of setup creation (analytics tag, not gate logic).
    # Derived from abs(price_return_4h):
    #   TREND_COMPRESSION  — >= 5%: price was actively trending over 4h window
    #   RANGE_COMPRESSION  — <  3%: price stable over 4h (classic range setup)
    #   UNKNOWN            — 3–5% grey zone or data unavailable
    setup_context: str = "UNKNOWN"
    status: str = "OPEN"
