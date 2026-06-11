from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain import Candle, FeatureSnapshot, Liquidation, PredictiveSetup, Signal, Snapshot
from app.models import (
    AlertDelivery,
    CandleModel,
    FeatureSnapshotModel,
    Instrument,
    LiquidationEvent,
    MarketSnapshot,
    PredictiveSetupModel,
    SetupOutcome,
    SignalEvent,
)


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_instrument(self, symbol: str) -> Instrument:
        instrument = await self.session.scalar(
            select(Instrument).where(Instrument.exchange == "bybit", Instrument.symbol == symbol)
        )
        if instrument:
            return instrument
        instrument = Instrument(exchange="bybit", symbol=symbol)
        self.session.add(instrument)
        await self.session.flush()
        return instrument

    async def save_snapshot(self, instrument_id: UUID, item: Snapshot) -> None:
        self.session.add(
            MarketSnapshot(
                instrument_id=instrument_id,
                ts=item.ts,
                last_price=item.last_price,
                mark_price=item.mark_price,
                index_price=item.index_price,
                spot_price=item.spot_price,
                open_interest_usd=item.open_interest_usd,
                volume_24h_usd=item.volume_24h_usd,
                funding_rate=item.funding_rate,
                funding_8h_equivalent=item.funding_8h_equivalent,
                long_ratio=item.long_ratio,
                short_ratio=item.short_ratio,
                basis_bps=item.basis_bps,
                spot_source=item.spot_source,
                data_quality_score=Decimal(str(item.data_quality_score)) if item.data_quality_score is not None else None,
                data_quality_status=item.data_quality_status or "UNKNOWN",
                missing_fields=item.missing_fields,
                source_errors=item.source_errors,
                raw_payload=item.raw_payload,
            )
        )

    async def save_liquidation(self, instrument_id: UUID, item: Liquidation) -> None:
        statement = insert(LiquidationEvent).values(
            instrument_id=instrument_id,
            event_ts=item.ts,
            liquidated_side=item.liquidated_side,
            quantity=item.quantity,
            price=item.price,
            notional_usd=item.notional_usd,
            source_event_id=item.source_event_id,
            raw_payload=item.raw_payload,
        ).on_conflict_do_nothing(index_elements=["source_event_id"])
        await self.session.execute(statement)

    async def save_candles(self, instrument_id: UUID, candles: list[Candle]) -> None:
        for item in candles:
            statement = insert(CandleModel).values(
                instrument_id=instrument_id,
                bucket_ts=item.ts,
                interval=item.interval,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume_base=item.volume_base,
                turnover_usd=item.turnover_usd,
            ).on_conflict_do_nothing(constraint="uq_candle_instrument_ts_interval")
            await self.session.execute(statement)

    async def candles(self, instrument_id: UUID, hours: int = 4, interval: str = "1") -> list[Candle]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        rows = (
            await self.session.scalars(
                select(CandleModel)
                .where(
                    CandleModel.instrument_id == instrument_id,
                    CandleModel.bucket_ts >= since,
                    CandleModel.interval == interval,
                )
                .order_by(CandleModel.bucket_ts)
            )
        ).all()
        return [
            Candle(
                ts=row.bucket_ts,
                symbol="",
                interval=row.interval,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume_base=row.volume_base,
                turnover_usd=row.turnover_usd,
            )
            for row in rows
        ]

    async def snapshots(self, instrument_id: UUID, hours: int) -> list[Snapshot]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        rows = (
            await self.session.scalars(
                select(MarketSnapshot)
                .options(joinedload(MarketSnapshot.instrument))
                .where(MarketSnapshot.instrument_id == instrument_id, MarketSnapshot.ts >= since)
                .order_by(MarketSnapshot.ts)
            )
        ).all()
        return [
            Snapshot(
                ts=row.ts,
                symbol=row.instrument.symbol,
                last_price=row.last_price,
                mark_price=row.mark_price,
                index_price=row.index_price,
                spot_price=row.spot_price,
                open_interest_usd=row.open_interest_usd,
                volume_24h_usd=row.volume_24h_usd,
                funding_rate=row.funding_rate,
                funding_8h_equivalent=row.funding_8h_equivalent,
                long_ratio=row.long_ratio,
                short_ratio=row.short_ratio,
                basis_bps=row.basis_bps,
                spot_source=row.spot_source,
                data_quality_score=float(row.data_quality_score) if row.data_quality_score is not None else None,
                data_quality_status=row.data_quality_status,
                missing_fields=row.missing_fields or [],
                source_errors=row.source_errors or [],
                raw_payload=row.raw_payload,
            )
            for row in rows
        ]

    async def liquidations(self, instrument_id: UUID, hours: int = 1) -> list[Liquidation]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        rows = (
            await self.session.scalars(
                select(LiquidationEvent)
                .where(LiquidationEvent.instrument_id == instrument_id, LiquidationEvent.event_ts >= since)
                .order_by(LiquidationEvent.event_ts)
            )
        ).all()
        return [
            Liquidation(
                ts=row.event_ts,
                symbol="",
                liquidated_side=row.liquidated_side,
                quantity=row.quantity,
                price=row.price,
                notional_usd=row.notional_usd,
                source_event_id=row.source_event_id,
                raw_payload=row.raw_payload,
            )
            for row in rows
        ]

    async def save_signal(self, instrument_id: UUID, symbol: str, item: Signal) -> SignalEvent:
        now = datetime.now(UTC)
        row = SignalEvent(
            instrument_id=instrument_id,
            signal_type=item.signal_type,
            severity=item.severity,
            score=Decimal(str(round(item.score, 2))),
            confidence=Decimal(str(round(item.confidence, 4))),
            fingerprint=f"{symbol}:{item.signal_type}",
            evidence=item.evidence,
            created_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def is_in_cooldown(self, fingerprint: str, minutes: int) -> bool:
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        return (
            await self.session.scalar(
                select(SignalEvent.id)
                .where(SignalEvent.fingerprint == fingerprint, SignalEvent.notified_at >= since)
                .order_by(desc(SignalEvent.notified_at))
                .limit(1)
            )
        ) is not None

    async def record_delivery(self, event: SignalEvent, status: str, detail: str | None = None) -> None:
        now = datetime.now(UTC)
        self.session.add(
            AlertDelivery(signal_id=event.id, channel="telegram", status=status, detail=detail, created_at=now)
        )
        if status == "sent":
            event.notified_at = now

    async def save_feature_snapshot(self, instrument_id: UUID, item: FeatureSnapshot) -> None:
        values = {
            "instrument_id": instrument_id,
            "bucket_ts": item.ts,
            "timeframe": item.timeframe,
            "price_return_15m": self._decimal(item.price_return_15m),
            "price_return_1h": self._decimal(item.price_return_1h),
            "price_return_4h": self._decimal(item.price_return_4h),
            "realized_vol_1h": self._decimal(item.realized_vol_1h),
            "range_pct_1h": self._decimal(item.range_pct_1h),
            "oi_change_15m": self._decimal(item.oi_change_15m),
            "oi_change_1h": self._decimal(item.oi_change_1h),
            "oi_acceleration": self._decimal(item.oi_acceleration),
            "funding_change_1h": self._decimal(item.funding_change_1h),
            "funding_acceleration": self._decimal(item.funding_acceleration),
            "volume_window_usd_15m": self._decimal(item.volume_window_usd_15m),
            "volume_zscore": self._decimal(item.volume_zscore),
            "long_liquidations_1h": self._decimal(item.long_liquidations_1h),
            "short_liquidations_1h": self._decimal(item.short_liquidations_1h),
            "liquidation_imbalance": self._decimal(item.liquidation_imbalance),
            "basis_bps": self._decimal(item.basis_bps),
            "basis_change_1h": self._decimal(item.basis_change_1h),
            "compression_score": self._decimal(item.compression_score),
            "leverage_buildup_score": self._decimal(item.leverage_buildup_score),
            "funding_pressure_score": self._decimal(item.funding_pressure_score),
            "volume_accumulation_score": self._decimal(item.volume_accumulation_score),
            "liquidation_imbalance_score": self._decimal(item.liquidation_imbalance_score),
            "basis_pressure_score": self._decimal(item.basis_pressure_score),
            "breakout_pressure": self._decimal(item.breakout_pressure),
            "squeeze_probability": self._decimal(item.squeeze_probability),
            "breakout_probability": self._decimal(item.breakout_probability),
            "expected_move_score": self._decimal(item.expected_move_score),
            "expected_direction": item.expected_direction,
            "confidence": self._decimal(item.confidence),
            "components": item.components,
            "created_at": datetime.now(UTC),
            # V2.6 atomic research features (no composites, no expert weights)
            "oi_derisking":             self._decimal(item.oi_derisking),
            "oi_crowding":              self._decimal(item.oi_crowding),
            "volume_presence":          self._decimal(item.volume_presence),
            "volume_weakness":          self._decimal(item.volume_weakness),
            "liq_fuel":                 self._decimal(item.liq_fuel),
            "funding_overheating":      self._decimal(item.funding_overheating),
            "funding_cooling":          self._decimal(item.funding_cooling),
            "price_settling":           self._decimal(item.price_settling),
            "price_return_15m_abs":     self._decimal(item.price_return_15m_abs),
            "price_return_1h_abs":      self._decimal(item.price_return_1h_abs),
            "price_return_4h_abs":      self._decimal(item.price_return_4h_abs),
        }
        statement = insert(FeatureSnapshotModel).values(**values).on_conflict_do_nothing(
            constraint="uq_feature_instrument_ts_timeframe"
        )
        await self.session.execute(statement)

    async def feature_snapshots(self, instrument_id: UUID, hours: int = 24) -> list[FeatureSnapshotModel]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        return (
            await self.session.scalars(
                select(FeatureSnapshotModel)
                .where(FeatureSnapshotModel.instrument_id == instrument_id, FeatureSnapshotModel.bucket_ts >= since)
                .order_by(FeatureSnapshotModel.bucket_ts)
            )
        ).all()

    async def save_predictive_setup(self, instrument_id: UUID, symbol: str, item: PredictiveSetup) -> PredictiveSetupModel:
        row = PredictiveSetupModel(
            instrument_id=instrument_id,
            setup_type=item.setup_type,
            predictive_score=self._decimal(item.predictive_score),
            setup_score=self._decimal(item.setup_score),
            expected_move_score=self._decimal(item.expected_move_score),
            expected_move_probability=self._decimal(item.expected_move_probability),
            expected_direction=item.expected_direction,
            estimated_breakout_window=item.estimated_breakout_window,
            squeeze_probability=self._decimal(item.squeeze_probability),
            breakout_probability=self._decimal(item.breakout_probability),
            confidence=self._decimal(item.confidence),
            fingerprint=f"{symbol}:{item.setup_type}:{item.expected_direction}",
            reasons=item.reasons,
            components=item.components,
            market_regime=item.market_regime,
            setup_context=item.setup_context,
            status=item.status,
            created_at=item.ts,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def is_setup_in_cooldown(self, fingerprint: str, minutes: int) -> bool:
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        return (
            await self.session.scalar(
                select(PredictiveSetupModel.id)
                .where(PredictiveSetupModel.fingerprint == fingerprint, PredictiveSetupModel.created_at >= since)
                .order_by(desc(PredictiveSetupModel.created_at))
                .limit(1)
            )
        ) is not None

    async def record_predictive_delivery(self, event: PredictiveSetupModel, status: str) -> None:
        if status == "sent":
            event.notified_at = datetime.now(UTC)

    async def latest_feature_by_symbol(self, symbols: list[str]) -> list[tuple[str, FeatureSnapshotModel | None]]:
        result: list[tuple[str, FeatureSnapshotModel | None]] = []
        for symbol in symbols:
            instrument = await self.session.scalar(
                select(Instrument).where(Instrument.exchange == "bybit", Instrument.symbol == symbol)
            )
            if not instrument:
                result.append((symbol, None))
                continue
            feature = await self.session.scalar(
                select(FeatureSnapshotModel)
                .where(FeatureSnapshotModel.instrument_id == instrument.id)
                .order_by(desc(FeatureSnapshotModel.bucket_ts))
                .limit(1)
            )
            result.append((symbol, feature))
        return result

    async def feature_research_data(self) -> list[dict]:
        """Return complete outcomes paired with their V2.6 research features.

        Matches each setup_outcome to the nearest feature_snapshot by timestamp.
        Used by /feature_research to compute per-feature bucket statistics.
        """
        outcomes = list(
            await self.session.scalars(
                select(SetupOutcome).where(SetupOutcome.status == "complete")
            )
        )
        if not outcomes:
            return []

        result = []
        for outcome in outcomes:
            # Find closest feature_snapshot within ±3 min of setup creation
            window = timedelta(minutes=3)
            fs = await self.session.scalar(
                select(FeatureSnapshotModel)
                .where(
                    FeatureSnapshotModel.instrument_id == outcome.instrument_id,
                    FeatureSnapshotModel.bucket_ts >= outcome.setup_created_at - window,
                    FeatureSnapshotModel.bucket_ts <= outcome.setup_created_at + window,
                    FeatureSnapshotModel.oi_derisking.is_not(None),  # only V2.6 rows
                )
                .order_by(
                    func.abs(func.extract("epoch", FeatureSnapshotModel.bucket_ts - outcome.setup_created_at))
                )
                .limit(1)
            )
            if fs is None:
                continue

            result.append({
                # outcome fields
                "return_4h":  float(outcome.return_4h)  if outcome.return_4h  is not None else None,
                "mfe_4h":     float(outcome.mfe_4h)     if outcome.mfe_4h     is not None else None,
                "mae_4h":     float(outcome.mae_4h)     if outcome.mae_4h     is not None else None,
                "hit_3pct":   outcome.hit_3pct,
                "hit_5pct":   outcome.hit_5pct,
                "hit_10pct":  outcome.hit_10pct,
                # V2.6 atomic research features
                "oi_derisking":             float(fs.oi_derisking)         if fs.oi_derisking         is not None else None,
                "oi_crowding":              float(fs.oi_crowding)          if fs.oi_crowding          is not None else None,
                "volume_presence":          float(fs.volume_presence)      if fs.volume_presence      is not None else None,
                "volume_weakness":          float(fs.volume_weakness)      if fs.volume_weakness      is not None else None,
                "liq_fuel":                 float(fs.liq_fuel)             if fs.liq_fuel             is not None else None,
                "funding_overheating":      float(fs.funding_overheating)  if fs.funding_overheating  is not None else None,
                "funding_cooling":          float(fs.funding_cooling)      if fs.funding_cooling      is not None else None,
                "price_settling":           float(fs.price_settling)       if fs.price_settling       is not None else None,
                "price_return_15m_abs":     float(fs.price_return_15m_abs) if fs.price_return_15m_abs is not None else None,
                "price_return_1h_abs":      float(fs.price_return_1h_abs)  if fs.price_return_1h_abs  is not None else None,
                "price_return_4h_abs":      float(fs.price_return_4h_abs)  if fs.price_return_4h_abs  is not None else None,
            })

        return result

    async def outcome_stats(
        self,
        market_regime: str | None = None,
        setup_context: str | None = None,
    ) -> dict:
        """Raw aggregate data for /performance and /calibration endpoints.

        market_regime: if provided, all queries are filtered to that regime.
                       None means "all regimes combined".
        setup_context: if provided, further filters by price context tag.
                       None means "all contexts combined".
        """

        # PostgreSQL-safe boolean → float aggregation via CASE WHEN
        def _bool_to_float(col):
            """AVG(CASE WHEN col IS TRUE THEN 1.0 WHEN col IS FALSE THEN 0.0 ELSE NULL END)"""
            return func.avg(case((col.is_(True), 1.0), (col.is_(False), 0.0), else_=None))

        def _bool_sum(col):
            """SUM(CASE WHEN col IS TRUE THEN 1 ELSE 0 END) — NULLs treated as 0"""
            return func.sum(case((col.is_(True), 1), else_=0))

        def _filter_clauses():
            """Return all active filter clauses as a list for .where(*clauses) unpacking."""
            clauses = []
            if market_regime is not None:
                clauses.append(SetupOutcome.market_regime == market_regime)
            if setup_context is not None:
                clauses.append(SetupOutcome.setup_context == setup_context)
            return clauses

        regime_clauses = _filter_clauses()

        total_setups = (await self.session.scalar(
            select(func.count()).select_from(SetupOutcome).where(*regime_clauses)
        )) or 0
        complete = (await self.session.scalar(
            select(func.count()).select_from(SetupOutcome)
            .where(SetupOutcome.status == "complete", *regime_clauses)
        )) or 0
        partial = (await self.session.scalar(
            select(func.count()).select_from(SetupOutcome)
            .where(SetupOutcome.status == "partial", *regime_clauses)
        )) or 0

        # per expected_move_score_bucket aggregates (pre-aggregated in DB)
        bucket_rows = (
            await self.session.execute(
                select(
                    SetupOutcome.expected_move_score_bucket,
                    func.count().label("cnt"),
                    func.avg(SetupOutcome.return_1h).label("avg_ret_1h"),
                    func.avg(SetupOutcome.return_4h).label("avg_ret_4h"),
                    func.avg(SetupOutcome.return_12h).label("avg_ret_12h"),
                    func.avg(SetupOutcome.mfe_4h).label("avg_mfe_4h"),
                    func.avg(SetupOutcome.mae_4h).label("avg_mae_4h"),
                    _bool_to_float(SetupOutcome.hit_3pct).label("hit_rate_3pct"),
                    _bool_to_float(SetupOutcome.hit_5pct).label("hit_rate_5pct"),
                    _bool_to_float(SetupOutcome.hit_10pct).label("hit_rate_10pct"),
                    func.avg(SetupOutcome.time_to_hit_5pct).label("avg_time_5pct"),
                )
                .where(SetupOutcome.status == "complete", *regime_clauses)
                .group_by(SetupOutcome.expected_move_score_bucket)
            )
        ).all()

        # raw rows for breakout_probability bucketing (done in Python)
        bp_rows = (
            await self.session.execute(
                select(
                    SetupOutcome.breakout_probability,
                    SetupOutcome.return_1h,
                    SetupOutcome.return_4h,
                    SetupOutcome.return_12h,
                    SetupOutcome.mfe_4h,
                    SetupOutcome.hit_3pct,
                    SetupOutcome.hit_5pct,
                    SetupOutcome.hit_10pct,
                    SetupOutcome.time_to_hit_5pct,
                )
                .where(SetupOutcome.status == "complete", *regime_clauses)
            )
        ).all()

        # directional hit rates at 5 pct threshold
        long_row = (
            await self.session.execute(
                select(
                    func.count().label("total"),
                    _bool_sum(SetupOutcome.hit_5pct).label("hits"),
                )
                .where(
                    SetupOutcome.status == "complete",
                    SetupOutcome.setup_direction == "LONG",
                    *regime_clauses,
                )
            )
        ).one()
        short_row = (
            await self.session.execute(
                select(
                    func.count().label("total"),
                    _bool_sum(SetupOutcome.hit_5pct).label("hits"),
                )
                .where(
                    SetupOutcome.status == "complete",
                    SetupOutcome.setup_direction == "SHORT",
                    *regime_clauses,
                )
            )
        ).one()

        return {
            "total_setups": total_setups,
            "complete": complete,
            "partial": partial,
            "score_buckets": bucket_rows,
            "bp_rows": bp_rows,
            "long_direction": long_row,
            "short_direction": short_row,
        }

    @staticmethod
    def _decimal(value: float | int | Decimal) -> Decimal:
        return Decimal(str(round(float(value), 8)))
