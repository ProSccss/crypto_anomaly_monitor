"""Telegram adapter for /analyze SYMBOL.

Thin layer: validates input, calls ResearchService, formats SymbolAnalysis for Telegram.
All analytical logic lives in ResearchService — this file only handles I/O.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.db import SessionFactory
from app.services.research_service import (
    GateDiagnostics,
    GateRequirement,
    ResearchService,
    SymbolAnalysis,
    SymbolState,
)
from app.services.telegram_commands.context import CommandContext


async def handle(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.reply("Usage: /analyze SYMBOL\nExample: /analyze BTCUSDT")
        return

    symbol = ctx.args[0].upper()

    service = ResearchService(ctx.settings)
    async with SessionFactory() as session:
        analysis = await service.get_analysis(symbol, session)

    await ctx.reply(_format(analysis))


# ---------------------------------------------------------------------------
# Formatting — pure functions, no I/O
# ---------------------------------------------------------------------------


def _format(analysis: SymbolAnalysis) -> str:
    state = analysis.state
    lines: list[str] = []

    lines.append(f"🔬 {state.symbol} — Research Analysis")

    if state.as_of is None:
        lines.append("⚠️ No data available for this symbol.")
        lines.append("Symbol is not monitored or has no feature snapshots yet.")
        return "\n".join(lines)

    age_s = int((datetime.now(UTC) - state.as_of.replace(tzinfo=UTC)).total_seconds())
    lines.append(f"⏱ {state.as_of.strftime('%Y-%m-%d %H:%M')} UTC  ({_age_label(age_s)})")

    lines.append("")
    lines.append(_format_state(state))

    if analysis.diagnostics is not None:
        lines.append("")
        lines.append(_format_diagnostics(state, analysis.diagnostics))

    lines.append("")
    lines.append(_format_metrics(state))

    lines.append("")
    lines.append("─" * 28)
    lines.append(_format_hints(state.symbol))

    return "\n".join(lines)


def _format_state(state: SymbolState) -> str:
    dq = state.data_quality or "UNKNOWN"
    conf_pct = f"{(state.confidence or 0) * 100:.0f}%"
    return f"📊 {dq}  Conf: {conf_pct}"


def _format_diagnostics(state: SymbolState, d: GateDiagnostics) -> str:
    lines: list[str] = []

    if not d.base_ok:
        reason = (
            f"conf={d.confidence:.2f} < 0.80"
            if d.confidence < 0.80
            else f"data_quality={d.data_quality}"
        )
        lines.append(f"🚫 NO SETUP — base conditions not met ({reason})")
        return "\n".join(lines)

    setup = state.setup
    if setup is not None:
        regime = setup.market_regime
        ctx_label = setup.setup_context
        direction = setup.expected_direction
        score = setup.predictive_score
        lines.append(f"✅ SETUP DETECTED  [{regime}]")
        lines.append(f"   {setup.setup_type}  ·  {ctx_label}  ·  {direction}")
        lines.append(f"   Score: {score:.1f}")
        lines.append("")
        if regime == "PRE_BREAKOUT":
            lines.append(_format_gate("Gate A ✅", d.gate_a_requirements))
        else:
            lines.append(_format_gate("Gate B ✅", d.gate_b_requirements))
    else:
        lines.append("🚫 NO SETUP")
        lines.append(_format_gate("Gate A", d.gate_a_requirements))
        lines.append(_format_gate("Gate B", d.gate_b_requirements))

    return "\n".join(lines)


def _format_gate(label: str, reqs: tuple[GateRequirement, ...]) -> str:
    parts: list[str] = []
    for r in reqs:
        if r.passed:
            parts.append(f"{r.name}={r.actual} ✓")
        else:
            parts.append(f"{r.name}={r.actual} (need ≥{r.threshold:.0f}, -{r.gap:.1f})")
    return f"  {label}: " + "  ·  ".join(parts)


def _format_metrics(state: SymbolState) -> str:
    bp  = f"{state.breakout_probability:.1f}"  if state.breakout_probability  is not None else "—"
    sq  = f"{state.squeeze_probability:.1f}"   if state.squeeze_probability   is not None else "—"
    ems = f"{state.expected_move_score:.1f}"   if state.expected_move_score   is not None else "—"
    dr  = state.expected_direction or "—"
    return f"📈 BP {bp}  SQ {sq}  EMS {ems}  Dir: {dr}"


def _format_hints(symbol: str) -> str:
    return f"/why {symbol}  — gate diagnostics\n/features {symbol}  — raw feature vector"


def _age_label(seconds: int) -> str:
    if seconds < 120:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    return f"{seconds // 3600}h ago"
