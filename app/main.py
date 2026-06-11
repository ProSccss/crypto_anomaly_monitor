from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.logging_config import configure_logging
from app.models import FeatureSnapshotModel, Instrument, MarketSnapshot, PredictiveSetupModel, SignalEvent
from app.repository import Repository
from app.schemas import (
    BucketStats,
    CalibrationBucket,
    CalibrationResponse,
    DirectionCondition,
    FeatureBucket,
    FeatureResearchItem,
    FeatureResearchResponse,
    FeatureSnapshotResponse,
    GateAStatus,
    GateBStatus,
    PerformanceResponse,
    PredictiveSetupResponse,
    RegimeAuditItem,
    RegimeAuditResponse,
    ScannerItemResponse,
    SignalResponse,
    SnapshotResponse,
    WhyNotResponse,
)
from app.services.monitor import MonitorService

configure_logging(settings.log_level)
monitor = MonitorService(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await monitor.start()
    yield
    await monitor.stop()


app = FastAPI(title="Crypto Derivatives Anomaly Monitor", version="0.1.0", lifespan=lifespan)


async def _instrument(session: AsyncSession, symbol: str) -> Instrument:
    item = await session.scalar(
        select(Instrument).where(Instrument.exchange == "bybit", Instrument.symbol == symbol.upper())
    )
    if not item:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return item


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "symbols": settings.monitored_symbols}


@app.get("/snapshots/{symbol}", response_model=list[SnapshotResponse])
async def snapshots(
    symbol: str,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    instrument = await _instrument(session, symbol)
    return (
        await session.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.instrument_id == instrument.id)
            .order_by(desc(MarketSnapshot.ts))
            .limit(limit)
        )
    ).all()


@app.get("/signals/{symbol}", response_model=list[SignalResponse])
async def signals(
    symbol: str,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    instrument = await _instrument(session, symbol)
    return (
        await session.scalars(
            select(SignalEvent)
            .where(SignalEvent.instrument_id == instrument.id)
            .order_by(desc(SignalEvent.created_at))
            .limit(limit)
        )
    ).all()


@app.get("/features/{symbol}", response_model=list[FeatureSnapshotResponse])
async def features(
    symbol: str,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    instrument = await _instrument(session, symbol)
    return (
        await session.scalars(
            select(FeatureSnapshotModel)
            .where(FeatureSnapshotModel.instrument_id == instrument.id)
            .order_by(desc(FeatureSnapshotModel.bucket_ts))
            .limit(limit)
        )
    ).all()


@app.get("/setups/{symbol}", response_model=list[PredictiveSetupResponse])
async def setups(
    symbol: str,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    instrument = await _instrument(session, symbol)
    return (
        await session.scalars(
            select(PredictiveSetupModel)
            .where(PredictiveSetupModel.instrument_id == instrument.id)
            .order_by(desc(PredictiveSetupModel.created_at))
            .limit(limit)
        )
    ).all()


_SCORE_BUCKETS = ["0-50", "50-60", "60-70", "70-80", "80-90", "90-100"]
_BP_RANGES = [
    ("50-60", 50, 60),
    ("60-70", 60, 70),
    ("70-80", 70, 80),
    ("80-90", 80, 90),
    ("90-100", 90, 101),
]


def _safe_float(v) -> float | None:
    return float(v) if v is not None else None


def _bucket_stats_from_rows(rows, filter_fn) -> BucketStats:
    matched = [r for r in rows if filter_fn(r)]
    if not matched:
        return BucketStats(
            count=0,
            avg_return_1h=None,
            avg_return_4h=None,
            avg_return_12h=None,
            avg_mfe_4h=None,
            hit_rate_3pct=None,
            hit_rate_5pct=None,
            hit_rate_10pct=None,
            avg_time_to_hit_5pct_minutes=None,
        )
    n = len(matched)

    def avg(attr):
        vals = [_safe_float(getattr(r, attr)) for r in matched if getattr(r, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    def hit_rate(attr):
        vals = [r for r in matched if getattr(r, attr) is not None]
        if not vals:
            return None
        return sum(1 for r in vals if getattr(r, attr)) / len(vals)

    return BucketStats(
        count=n,
        avg_return_1h=avg("return_1h"),
        avg_return_4h=avg("return_4h"),
        avg_return_12h=avg("return_12h"),
        avg_mfe_4h=avg("mfe_4h"),
        hit_rate_3pct=hit_rate("hit_3pct"),
        hit_rate_5pct=hit_rate("hit_5pct"),
        hit_rate_10pct=hit_rate("hit_10pct"),
        avg_time_to_hit_5pct_minutes=avg("time_to_hit_5pct"),
    )


_RESEARCH_FEATURES = [
    "oi_derisking",
    "oi_crowding",
    "volume_presence",
    "volume_weakness",
    "liq_fuel",
    "funding_overheating",
    "funding_cooling",
    "price_settling",
    "price_return_15m_abs",
    "price_return_1h_abs",
    "price_return_4h_abs",
]

_RESEARCH_BUCKETS = [
    ("0-20",   0,  20),
    ("20-40",  20, 40),
    ("40-60",  40, 60),
    ("60-80",  60, 80),
    ("80-100", 80, 101),
]


def _compute_bucket(rows: list[dict], feature: str, lo: float, hi: float) -> FeatureBucket:
    matched = [r for r in rows if r.get(feature) is not None and lo <= r[feature] < hi]
    n = len(matched)
    if n == 0:
        return FeatureBucket(
            count=0, avg_return_4h=None, avg_mfe_4h=None, avg_mae_4h=None,
            hit_rate_3pct=None, hit_rate_5pct=None, hit_rate_10pct=None,
        )

    def _avg(key: str) -> float | None:
        vals = [r[key] for r in matched if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    def _hit_rate(key: str) -> float | None:
        vals = [r[key] for r in matched if r.get(key) is not None]
        return round(sum(1 for v in vals if v) / len(vals), 4) if vals else None

    return FeatureBucket(
        count=n,
        avg_return_4h=_avg("return_4h"),
        avg_mfe_4h=_avg("mfe_4h"),
        avg_mae_4h=_avg("mae_4h"),
        hit_rate_3pct=_hit_rate("hit_3pct"),
        hit_rate_5pct=_hit_rate("hit_5pct"),
        hit_rate_10pct=_hit_rate("hit_10pct"),
    )


@app.get("/feature_research", response_model=FeatureResearchResponse)
async def feature_research(session: AsyncSession = Depends(get_session)):
    repo = Repository(session)
    rows = await repo.feature_research_data()

    items: list[FeatureResearchItem] = []
    for feature in _RESEARCH_FEATURES:
        buckets: dict[str, FeatureBucket] = {}
        obs = [r for r in rows if r.get(feature) is not None]
        for label, lo, hi in _RESEARCH_BUCKETS:
            buckets[label] = _compute_bucket(rows, feature, lo, hi)
        items.append(FeatureResearchItem(
            feature=feature,
            total_observations=len(obs),
            buckets=buckets,
        ))

    return FeatureResearchResponse(
        total_complete_outcomes=len(rows),
        note=(
            "Each bucket shows outcomes for setups where the feature was in that range "
            "at setup creation time. Accumulate 20+ observations per bucket for meaningful statistics."
        ),
        features=items,
    )


_VALID_REGIMES = {"PRE_BREAKOUT", "CONTINUATION"}
_VALID_CONTEXTS = {"TREND_COMPRESSION", "RANGE_COMPRESSION", "UNKNOWN"}


def _validate_regime(regime: str | None) -> str | None:
    if regime is not None and regime not in _VALID_REGIMES:
        raise HTTPException(
            status_code=422,
            detail=f"market_regime must be one of {sorted(_VALID_REGIMES)} or omitted",
        )
    return regime


def _validate_context(context: str | None) -> str | None:
    if context is not None and context not in _VALID_CONTEXTS:
        raise HTTPException(
            status_code=422,
            detail=f"setup_context must be one of {sorted(_VALID_CONTEXTS)} or omitted",
        )
    return context


@app.get("/performance", response_model=PerformanceResponse)
async def performance(
    market_regime: str | None = Query(None, description="Filter by PRE_BREAKOUT or CONTINUATION"),
    setup_context: str | None = Query(None, description="Filter by TREND_COMPRESSION, RANGE_COMPRESSION or UNKNOWN"),
    session: AsyncSession = Depends(get_session),
):
    regime = _validate_regime(market_regime)
    context = _validate_context(setup_context)
    repo = Repository(session)
    data = await repo.outcome_stats(market_regime=regime, setup_context=context)

    # score bucket stats (pre-aggregated from DB)
    score_bucket_map: dict[str, BucketStats] = {}
    for row in data["score_buckets"]:
        score_bucket_map[row.expected_move_score_bucket] = BucketStats(
            count=row.cnt,
            avg_return_1h=_safe_float(row.avg_ret_1h),
            avg_return_4h=_safe_float(row.avg_ret_4h),
            avg_return_12h=_safe_float(row.avg_ret_12h),
            avg_mfe_4h=_safe_float(row.avg_mfe_4h),
            hit_rate_3pct=_safe_float(row.hit_rate_3pct),
            hit_rate_5pct=_safe_float(row.hit_rate_5pct),
            hit_rate_10pct=_safe_float(row.hit_rate_10pct),
            avg_time_to_hit_5pct_minutes=_safe_float(row.avg_time_5pct),
        )
    by_score = {b: score_bucket_map.get(b, BucketStats(count=0, avg_return_1h=None, avg_return_4h=None, avg_return_12h=None, avg_mfe_4h=None, hit_rate_3pct=None, hit_rate_5pct=None, hit_rate_10pct=None, avg_time_to_hit_5pct_minutes=None)) for b in _SCORE_BUCKETS}

    # breakout_probability bucket stats (computed in Python from raw rows)
    bp_rows = data["bp_rows"]
    by_bp: dict[str, BucketStats] = {}
    for label, lo, hi in _BP_RANGES:
        by_bp[label] = _bucket_stats_from_rows(bp_rows, lambda r, lo=lo, hi=hi: lo <= float(r.breakout_probability) < hi)

    # directional hit rates (5pct threshold)
    def _hit_rate(row) -> float | None:
        total = row.total or 0
        hits = float(row.hits) if row.hits is not None else 0
        return hits / total if total > 0 else None

    return PerformanceResponse(
        total_setups=data["total_setups"],
        complete_outcomes=data["complete"],
        partial_outcomes=data["partial"],
        hit_threshold_pct=5.0,
        market_regime=regime,
        setup_context=context,
        hit_rate_long=_hit_rate(data["long_direction"]),
        hit_rate_short=_hit_rate(data["short_direction"]),
        by_breakout_probability=by_bp,
        by_expected_move_score=by_score,
    )


@app.get("/calibration", response_model=CalibrationResponse)
async def calibration(
    market_regime: str | None = Query(None, description="Filter by PRE_BREAKOUT or CONTINUATION"),
    setup_context: str | None = Query(None, description="Filter by TREND_COMPRESSION, RANGE_COMPRESSION or UNKNOWN"),
    session: AsyncSession = Depends(get_session),
):
    regime = _validate_regime(market_regime)
    context = _validate_context(setup_context)
    repo = Repository(session)
    data = await repo.outcome_stats(market_regime=regime, setup_context=context)

    score_bucket_map: dict[str, CalibrationBucket] = {}
    for row in data["score_buckets"]:
        score_bucket_map[row.expected_move_score_bucket] = CalibrationBucket(
            count=row.cnt,
            avg_actual_return_4h=_safe_float(row.avg_ret_4h),
            avg_mfe_4h=_safe_float(row.avg_mfe_4h),
            avg_mae_4h=_safe_float(row.avg_mae_4h),
            hit_rate_5pct=_safe_float(row.hit_rate_5pct),
            avg_time_to_hit_5pct_minutes=_safe_float(row.avg_time_5pct),
        )

    by_score = {
        b: score_bucket_map.get(
            b,
            CalibrationBucket(count=0, avg_actual_return_4h=None, avg_mfe_4h=None, avg_mae_4h=None, hit_rate_5pct=None, avg_time_to_hit_5pct_minutes=None),
        )
        for b in _SCORE_BUCKETS
    }

    return CalibrationResponse(
        total_complete=data["complete"],
        market_regime=regime,
        setup_context=context,
        by_expected_move_score=by_score,
        note="Accumulate 50+ complete outcomes per bucket for statistically significant results.",
    )


@app.get("/scanner", response_model=list[ScannerItemResponse])
async def scanner(session: AsyncSession = Depends(get_session)):
    repo = Repository(session)
    rows = []
    for symbol, feature in await repo.latest_feature_by_symbol(settings.monitored_symbols):
        if feature is None:
            rows.append(
                {
                    "symbol": symbol,
                    "expected_move_score": 0,
                    "expected_direction": "NEUTRAL",
                    "breakout_probability": 0,
                    "squeeze_probability": 0,
                    "confidence": 0,
                    "data_quality_status": None,
                    "updated_at": None,
                }
            )
            continue
        rows.append(
            {
                "symbol": symbol,
                "expected_move_score": feature.expected_move_score,
                "expected_direction": feature.expected_direction,
                "breakout_probability": feature.breakout_probability,
                "squeeze_probability": feature.squeeze_probability,
                "confidence": feature.confidence,
                "data_quality_status": feature.components.get("data_quality_status"),
                "updated_at": feature.bucket_ts,
            }
        )
    return sorted(rows, key=lambda item: item["expected_move_score"], reverse=True)


# ── V2.7 Observability ────────────────────────────────────────────────────────

# Gate thresholds (mirrors PredictiveEngine._market_regime — read-only copy for API)
_GATE_A_BP  = 25.0
_GATE_A_SQ  = 30.0
_GATE_B_SQ  = 45.0
_GATE_B_EMS = 40.0
_GATE_B_VOL = 50.0


def _extract_feature_metrics(feature: FeatureSnapshotModel) -> dict:
    """Extract typed floats from a FeatureSnapshotModel for gate evaluation."""
    return {
        "bp":       float(feature.breakout_probability),
        "sq":       float(feature.squeeze_probability),
        "ems":      float(feature.expected_move_score),
        "conf":     float(feature.confidence),
        "vol_pct":  float(feature.components.get("volume_percentile") or 0.0),
        "dq":       feature.components.get("data_quality_status"),
        "funding":  float(feature.components.get("funding_pct_8h") or 0.0),
        "long_r":   float(feature.components.get("long_ratio")  or 0.0),
        "short_r":  float(feature.components.get("short_ratio") or 0.0),
        "pr4h":     float(feature.price_return_4h),
        "exp_dir":  feature.expected_direction,
    }


def _eval_gate_a(m: dict, base_ok: bool) -> tuple[GateAStatus, bool]:
    bp, sq = m["bp"], m["sq"]
    passed = base_ok and bp >= _GATE_A_BP and sq >= _GATE_A_SQ
    status = GateAStatus(
        status="PASS" if passed else "FAIL",
        bp=round(bp, 1),
        sq=round(sq, 1),
        bp_gap=0.0 if passed else round(max(0.0, _GATE_A_BP - bp), 1),
        sq_gap=0.0 if passed else round(max(0.0, _GATE_A_SQ - sq), 1),
    )
    return status, passed


def _eval_gate_b(m: dict, base_ok: bool) -> tuple[GateBStatus, bool]:
    sq, ems, vol = m["sq"], m["ems"], m["vol_pct"]
    passed = base_ok and sq >= _GATE_B_SQ and ems >= _GATE_B_EMS and vol >= _GATE_B_VOL
    status = GateBStatus(
        status="PASS" if passed else "FAIL",
        sq=round(sq, 1),
        ems=round(ems, 1),
        vol_pct=round(vol, 1),
        sq_gap=0.0  if passed else round(max(0.0, _GATE_B_SQ  - sq),  1),
        ems_gap=0.0 if passed else round(max(0.0, _GATE_B_EMS - ems), 1),
        vol_gap=0.0 if passed else round(max(0.0, _GATE_B_VOL - vol), 1),
    )
    return status, passed


def _eval_direction(m: dict) -> DirectionCondition:
    funding, long_r, short_r, exp_dir = m["funding"], m["long_r"], m["short_r"], m["exp_dir"]
    dir_long    = funding <= -0.15 or short_r >= 0.60
    dir_short   = funding >=  0.15 or long_r  >= 0.60
    dir_neutral = exp_dir == "NEUTRAL"
    return DirectionCondition(
        funding_pct_8h=round(funding, 4),
        long_ratio=round(long_r, 3),
        short_ratio=round(short_r, 3),
        expected_direction=exp_dir,
        long_squeeze_eligible=dir_long,
        short_squeeze_eligible=dir_short,
        neutral_breakout_eligible=dir_neutral,
        any_direction_met=dir_long or dir_short or dir_neutral,
    )


@app.get("/regime_audit", response_model=RegimeAuditResponse)
async def regime_audit(session: AsyncSession = Depends(get_session)):
    """Show current Gate A / Gate B status for every monitored symbol.

    Answers: which symbols are near or inside a gate right now?
    Sorted by proximity — passing symbols first, then by combined bp+sq score.
    """
    repo = Repository(session)
    symbol_features = await repo.latest_feature_by_symbol(settings.monitored_symbols)

    items: list[RegimeAuditItem] = []
    pre_breakout_count = 0
    continuation_count = 0

    for symbol, feature in symbol_features:
        if feature is None:
            items.append(RegimeAuditItem(
                symbol=symbol,
                gate_a=GateAStatus(status="NO_DATA"),
                gate_b=GateBStatus(status="NO_DATA"),
            ))
            continue

        m = _extract_feature_metrics(feature)
        base_ok = m["conf"] >= 0.80 and m["dq"] == "GOOD"

        gate_a, a_pass = _eval_gate_a(m, base_ok)
        gate_b, b_pass = _eval_gate_b(m, base_ok)

        regime: str | None = None
        if a_pass:
            regime = "PRE_BREAKOUT"
            pre_breakout_count += 1
        elif b_pass:
            regime = "CONTINUATION"
            continuation_count += 1

        items.append(RegimeAuditItem(
            symbol=symbol,
            updated_at=feature.bucket_ts,
            data_quality=m["dq"],
            confidence=round(m["conf"], 3),
            breakout_probability=round(m["bp"], 1),
            squeeze_probability=round(m["sq"], 1),
            expected_move_score=round(m["ems"], 1),
            volume_percentile=round(m["vol_pct"], 1),
            price_return_4h=round(m["pr4h"], 2),
            market_regime=regime,
            gate_a=gate_a,
            gate_b=gate_b,
        ))

    # Sort: passing gates first, then by bp+sq proximity to Gate A thresholds
    items.sort(key=lambda x: (
        0 if x.market_regime else 1,
        -((x.breakout_probability or 0) + (x.squeeze_probability or 0)),
    ))

    return RegimeAuditResponse(
        as_of=datetime.now(UTC),
        pre_breakout_candidates=pre_breakout_count,
        continuation_candidates=continuation_count,
        symbols=items,
    )


@app.get("/why_not/{symbol}", response_model=WhyNotResponse)
async def why_not(symbol: str, session: AsyncSession = Depends(get_session)):
    """Explain why a setup is NOT being created for this symbol right now.

    Walks every condition in the pipeline in order:
      1. Base conditions (confidence, data_quality)
      2. Gate A (PRE_BREAKOUT)
      3. Gate B (CONTINUATION)
      4. Direction condition (if any gate passes)
    Returns a plain-English verdict.
    """
    symbol = symbol.upper()
    symbol_features = await repo_from_session(session, symbol)
    if symbol_features is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not monitored or has no feature data")

    feature, m = symbol_features
    base_ok = m["conf"] >= 0.80 and m["dq"] == "GOOD"

    gate_a, a_pass = _eval_gate_a(m, base_ok)
    gate_b, b_pass = _eval_gate_b(m, base_ok)

    direction: DirectionCondition | None = None
    verdict: str

    if not base_ok:
        issues: list[str] = []
        if m["conf"] < 0.80:
            issues.append(f"confidence {m['conf']:.3f} < 0.80 required")
        if m["dq"] != "GOOD":
            issues.append(f"data_quality='{m['dq']}' (requires GOOD)")
        verdict = "Base conditions fail — " + "; ".join(issues) + "."

    elif a_pass or b_pass:
        direction = _eval_direction(m)
        regime = "PRE_BREAKOUT" if a_pass else "CONTINUATION"
        if not direction.any_direction_met:
            verdict = (
                f"{regime} gate PASSES but no direction condition is met. "
                f"Need funding≤-0.15% OR funding≥0.15% OR ratio≥0.60 OR direction=NEUTRAL. "
                f"Current: funding={m['funding']:+.4f}%, "
                f"long_ratio={m['long_r']:.2f}, short_ratio={m['short_r']:.2f}."
            )
        elif regime == "CONTINUATION":
            # CONTINUATION also requires predictive_score >= 40 (== ems here)
            if m["ems"] < _GATE_B_EMS:
                verdict = (
                    f"CONTINUATION gate passes and direction met, "
                    f"but EMS {m['ems']:.1f} < PREDICTIVE_SCORE_MIN {_GATE_B_EMS:.0f}. "
                    f"Need EMS +{_GATE_B_EMS - m['ems']:.1f} more."
                )
            else:
                verdict = (
                    f"All conditions met ({regime}). "
                    "Setup will be created on the next 60-second poll cycle."
                )
        else:
            verdict = (
                f"All conditions met ({regime}). "
                "Setup will be created on the next 60-second poll cycle."
            )

    else:
        # Both gates fail — list what's missing for each
        missing_a: list[str] = []
        if not base_ok:
            pass  # handled above
        if m["bp"] < _GATE_A_BP:
            missing_a.append(f"bp +{_GATE_A_BP - m['bp']:.1f}")
        if m["sq"] < _GATE_A_SQ:
            missing_a.append(f"sq +{_GATE_A_SQ - m['sq']:.1f}")

        missing_b: list[str] = []
        if m["sq"]  < _GATE_B_SQ:
            missing_b.append(f"sq +{_GATE_B_SQ  - m['sq']:.1f}")
        if m["ems"] < _GATE_B_EMS:
            missing_b.append(f"ems +{_GATE_B_EMS - m['ems']:.1f}")
        if m["vol_pct"] < _GATE_B_VOL:
            missing_b.append(f"vol +{_GATE_B_VOL - m['vol_pct']:.1f}")

        verdict = (
            f"Both gates fail. "
            f"Gate A (PRE_BREAKOUT) missing: {', '.join(missing_a) or 'none'}. "
            f"Gate B (CONTINUATION) missing: {', '.join(missing_b) or 'none'}."
        )

    return WhyNotResponse(
        symbol=symbol,
        updated_at=feature.bucket_ts,
        gate_a=gate_a,
        gate_b=gate_b,
        direction=direction,
        verdict=verdict,
    )


async def repo_from_session(session: AsyncSession, symbol: str):
    """Helper: return (feature, metrics) for symbol or None if not found."""
    repo = Repository(session)
    pairs = await repo.latest_feature_by_symbol([symbol])
    if not pairs:
        return None
    _, feature = pairs[0]
    if feature is None:
        return None
    return feature, _extract_feature_metrics(feature)
