from datetime import UTC, datetime

from app.schemas import (
    ContextStats,
    DirectionStats,
    OutcomeDashboardResponse,
    RegimeSummary,
    SymbolStats,
)


def _hit(v) -> float | None:
    return round(float(v) * 100, 1) if v is not None else None


def _f(v) -> float | None:
    return round(float(v), 1) if v is not None else None


def build_dashboard(data: dict) -> OutcomeDashboardResponse:
    """Convert raw outcome_dashboard_data() dict into OutcomeDashboardResponse."""
    regime_map: dict[str, RegimeSummary] = {}
    for r in data["regime_rows"]:
        regime_map[r.market_regime] = RegimeSummary(
            count=r.count,
            avg_return_4h=_f(r.avg_return_4h),
            avg_return_12h=_f(r.avg_return_12h),
            avg_mfe_4h=_f(r.avg_mfe_4h),
            avg_mfe_12h=_f(r.avg_mfe_12h),
            hit_3pct=_hit(r.hit_3pct),
            hit_5pct=_hit(r.hit_5pct),
            hit_10pct=_hit(r.hit_10pct),
        )

    context_breakdown: dict[str, dict[str, ContextStats]] = {}
    for r in data["context_rows"]:
        context_breakdown.setdefault(r.market_regime, {})[r.setup_context] = ContextStats(
            count=r.count,
            avg_mfe_4h=_f(r.avg_mfe_4h),
            hit_5pct=_hit(r.hit_5pct),
        )

    direction_breakdown: dict[str, DirectionStats] = {
        r.setup_direction: DirectionStats(
            count=r.count,
            avg_return_4h=_f(r.avg_return_4h),
            avg_mfe_4h=_f(r.avg_mfe_4h),
            hit_3pct=_hit(r.hit_3pct),
            hit_5pct=_hit(r.hit_5pct),
            hit_10pct=_hit(r.hit_10pct),
        )
        for r in data["direction_rows"]
    }

    symbol_breakdown: dict[str, SymbolStats] = {
        r.symbol: SymbolStats(
            count=r.count,
            avg_return_4h=_f(r.avg_return_4h),
            avg_mfe_4h=_f(r.avg_mfe_4h),
            hit_3pct=_hit(r.hit_3pct),
            hit_5pct=_hit(r.hit_5pct),
            hit_10pct=_hit(r.hit_10pct),
        )
        for r in data["symbol_rows"]
    }

    return OutcomeDashboardResponse(
        as_of=datetime.now(UTC),
        complete_outcomes=data["total"],
        pre_breakout=regime_map.get("PRE_BREAKOUT"),
        continuation=regime_map.get("CONTINUATION"),
        context_breakdown=context_breakdown,
        direction_breakdown=direction_breakdown,
        symbol_breakdown=symbol_breakdown,
    )
