import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandleModel, MarketSnapshot, PredictiveSetupModel, SetupOutcome

logger = logging.getLogger(__name__)

SETUP_VERSION = "V2.5"
HORIZONS = [1, 4, 12]  # hours


def _score_bucket(score: Decimal) -> str:
    s = float(score)
    if s < 50:
        return "0-50"
    elif s < 60:
        return "50-60"
    elif s < 70:
        return "60-70"
    elif s < 80:
        return "70-80"
    elif s < 90:
        return "80-90"
    return "90-100"


def _directional_return(entry: Decimal, exit_price: Decimal, direction: str) -> Decimal:
    pct = (exit_price - entry) / entry * 100
    if direction == "SHORT":
        pct = -pct
    return Decimal(str(round(float(pct), 4)))


def _mfe_mae(
    entry: Decimal,
    direction: str,
    highs: list[Decimal],
    lows: list[Decimal],
) -> tuple[Decimal, Decimal]:
    if not highs or not lows:
        return Decimal("0"), Decimal("0")
    entry_f = float(entry)
    if direction == "LONG":
        mfe = (max(float(h) for h in highs) - entry_f) / entry_f * 100
        mae = (entry_f - min(float(l) for l in lows)) / entry_f * 100
    else:  # SHORT or NEUTRAL
        mfe = (entry_f - min(float(l) for l in lows)) / entry_f * 100
        mae = (max(float(h) for h in highs) - entry_f) / entry_f * 100
    return Decimal(str(round(mfe, 4))), Decimal(str(round(max(mae, 0), 4)))


async def _nearest_price(
    session: AsyncSession,
    instrument_id: UUID,
    target_ts: datetime,
    tolerance_minutes: int = 5,
) -> Decimal | None:
    window_start = target_ts - timedelta(minutes=tolerance_minutes)
    window_end = target_ts + timedelta(minutes=tolerance_minutes)
    row = await session.scalar(
        select(MarketSnapshot.mark_price)
        .where(
            MarketSnapshot.instrument_id == instrument_id,
            MarketSnapshot.ts >= window_start,
            MarketSnapshot.ts <= window_end,
        )
        .order_by(func.abs(func.extract("epoch", MarketSnapshot.ts - target_ts)))
        .limit(1)
    )
    return Decimal(str(row)) if row is not None else None


async def _candles_in_window(
    session: AsyncSession,
    instrument_id: UUID,
    start: datetime,
    end: datetime,
    interval: str = "1",
) -> list[CandleModel]:
    return list(
        await session.scalars(
            select(CandleModel)
            .where(
                CandleModel.instrument_id == instrument_id,
                CandleModel.bucket_ts >= start,
                CandleModel.bucket_ts <= end,
                CandleModel.interval == interval,
            )
            .order_by(CandleModel.bucket_ts)
        )
    )


# ---------------------------------------------------------------------------
# IVS-1.3 passive measurements — labels, not inputs.
# Computed within the setup→4h window (same basis as hit flags).
# NEUTRAL follows the existing _mfe_mae convention (treated as SHORT).
# ---------------------------------------------------------------------------


def _peak_index(candles: list[CandleModel], direction: str) -> int:
    """Index of the maximum favorable excursion candle."""
    if direction == "LONG":
        return max(range(len(candles)), key=lambda i: float(candles[i].high))
    return min(range(len(candles)), key=lambda i: float(candles[i].low))


def _time_to_peak(candles: list[CandleModel], direction: str, setup_ts: datetime) -> int | None:
    """Minutes from setup creation to the maximum favorable excursion."""
    if not candles:
        return None
    peak_ts = candles[_peak_index(candles, direction)].bucket_ts
    return max(1, int((peak_ts - setup_ts).total_seconds() / 60))


def _max_drawdown(candles: list[CandleModel], direction: str) -> Decimal | None:
    """Largest % retracement of the favorable move after (and within) its
    peak candle. Distinct from MAE, which measures adverse-from-entry."""
    if not candles:
        return None
    idx = _peak_index(candles, direction)
    if direction == "LONG":
        peak = float(candles[idx].high)
        if peak <= 0:
            return None
        dd = (peak - min(float(c.low) for c in candles[idx:])) / peak * 100
    else:
        trough = float(candles[idx].low)
        if trough <= 0:
            return None
        dd = (max(float(c.high) for c in candles[idx:]) - trough) / trough * 100
    return Decimal(str(round(max(dd, 0.0), 4)))


def _time_to_hit(
    candles: list[CandleModel],
    entry: Decimal,
    direction: str,
    threshold_pct: float,
    setup_ts: datetime,
) -> int | None:
    entry_f = float(entry)
    for c in candles:
        if direction == "LONG":
            current_mfe = (float(c.high) - entry_f) / entry_f * 100
        else:
            current_mfe = (entry_f - float(c.low)) / entry_f * 100
        if current_mfe >= threshold_pct:
            elapsed = (c.bucket_ts - setup_ts).total_seconds() / 60
            return max(1, int(elapsed))
    return None


async def evaluate_pending_outcomes(session: AsyncSession) -> None:
    now = datetime.now(UTC)

    # load outcomes that are not yet complete and old enough to have at least entry_price
    rows = list(
        await session.scalars(
            select(SetupOutcome)
            .where(SetupOutcome.status != "complete")
            # only process setups that are at least 2 minutes old (entry_price window)
            .where(SetupOutcome.setup_created_at <= now - timedelta(minutes=2))
        )
    )

    if not rows:
        return

    logger.info("outcome_evaluator_processing", extra={"count": len(rows)})

    for outcome in rows:
        try:
            await _evaluate_one(session, outcome, now)
        except Exception:
            logger.exception("outcome_evaluation_failed", extra={"setup_id": str(outcome.setup_id)})

    await session.flush()


async def _evaluate_one(session: AsyncSession, outcome: SetupOutcome, now: datetime) -> None:
    setup_ts = outcome.setup_created_at
    direction = outcome.setup_direction

    # --- entry_price ---
    if outcome.entry_price is None:
        entry = await _nearest_price(session, outcome.instrument_id, setup_ts, tolerance_minutes=5)
        if entry is None:
            return
        outcome.entry_price = entry

    entry = outcome.entry_price

    updates: dict = {}

    # --- per-horizon prices, returns, MFE/MAE ---
    for hours in HORIZONS:
        target_ts = setup_ts + timedelta(hours=hours)
        if target_ts > now:
            continue  # not yet reached

        price_field = f"price_{hours}h"
        if getattr(outcome, price_field) is not None:
            continue  # already filled

        price = await _nearest_price(session, outcome.instrument_id, target_ts, tolerance_minutes=5)
        if price is None:
            continue

        ret = _directional_return(entry, price, direction)
        candles = await _candles_in_window(session, outcome.instrument_id, setup_ts, target_ts)
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        mfe, mae = _mfe_mae(entry, direction, highs, lows)

        updates[price_field] = price
        updates[f"return_{hours}h"] = ret
        updates[f"mfe_{hours}h"] = mfe
        updates[f"mae_{hours}h"] = mae

        # hit flags and time_to_hit are computed once when 4h data arrives
        if hours == 4:
            hit_3 = bool(mfe >= Decimal("3"))
            hit_5 = bool(mfe >= Decimal("5"))
            hit_10 = bool(mfe >= Decimal("10"))
            updates["hit_3pct"] = hit_3
            updates["hit_5pct"] = hit_5
            updates["hit_10pct"] = hit_10

            if direction != "NEUTRAL":
                updates["time_to_hit_3pct"] = _time_to_hit(candles, entry, direction, 3.0, setup_ts) if hit_3 else None
                updates["time_to_hit_5pct"] = _time_to_hit(candles, entry, direction, 5.0, setup_ts) if hit_5 else None
                updates["time_to_hit_10pct"] = _time_to_hit(candles, entry, direction, 10.0, setup_ts) if hit_10 else None

            # IVS-1.3 passive measurements — isolated so a failure here can
            # never block the existing metric fills above.
            try:
                updates["time_to_peak_minutes"] = _time_to_peak(candles, direction, setup_ts)
                updates["max_drawdown"] = _max_drawdown(candles, direction)
            except Exception:
                logger.exception("ivs_passive_metrics_failed", extra={"setup_id": str(outcome.setup_id)})

    # apply in-memory updates
    for field, value in updates.items():
        setattr(outcome, field, value)

    # determine new status
    filled_hours = sum(
        1 for h in HORIZONS if getattr(outcome, f"price_{h}h") is not None
    )
    if filled_hours == len(HORIZONS):
        outcome.status = "complete"
        outcome.resolved_at = now
        # IVS-1.3: actual observed evaluation window (passive measurement)
        outcome.evaluation_duration_minutes = int((now - setup_ts).total_seconds() / 60)
    elif filled_hours > 0 or outcome.entry_price is not None:
        outcome.status = "partial"


async def create_outcome_for_setup(session: AsyncSession, setup: PredictiveSetupModel) -> None:
    """Called immediately after a valid setup is saved."""
    bucket = _score_bucket(setup.expected_move_score)
    stmt = insert(SetupOutcome).values(
        id=uuid4(),
        setup_id=setup.id,
        instrument_id=setup.instrument_id,
        setup_direction=setup.expected_direction,
        expected_move_score=setup.expected_move_score,
        expected_move_score_bucket=bucket,
        breakout_probability=setup.breakout_probability,
        squeeze_probability=setup.squeeze_probability,
        confidence=setup.confidence,
        setup_created_at=setup.created_at,
        setup_version=SETUP_VERSION,
        market_regime=setup.market_regime,
        setup_context=setup.setup_context,
        model_version=setup.model_version,
        status="pending",
        created_at=datetime.now(UTC),
    ).on_conflict_do_nothing(index_elements=["setup_id"])
    await session.execute(stmt)
