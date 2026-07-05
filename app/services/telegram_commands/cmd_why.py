"""Telegram adapter for /why SYMBOL.

Thin layer: validates input, calls ResearchService, formats SymbolAnalysis
into a WHY explanation. All analytical logic lives in ResearchService (D-009) —
this file only formats existing research data and computes nothing new.
"""
from __future__ import annotations

from app.db import SessionFactory
from app.services.research_service import (
    GateRequirement,
    ResearchService,
    SymbolAnalysis,
)
from app.services.telegram_commands.context import CommandContext


async def handle(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.reply("Usage: /why SYMBOL\nExample: /why BTCUSDT")
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
    d = analysis.diagnostics

    lines: list[str] = [f"🧠 WHY {state.symbol}"]

    if state.as_of is None or d is None:
        lines.append("⚠️ No data available for this symbol.")
        lines.append("Symbol is not monitored or has no feature snapshots yet.")
        return "\n".join(lines)

    setup = state.setup

    # Direction
    direction = setup.expected_direction if setup else (state.expected_direction or "—")
    lines += ["", "Direction:", direction]

    # Main drivers — the model's own reason list; feature-level signal otherwise
    lines += ["", "Main drivers:", ""]
    if setup is not None:
        for reason in setup.reasons:
            lines.append(f"🟢 {_sentence(reason)}")
    else:
        lines.append("— no active setup, model produced no drivers")

    # Base conditions gate everything downstream
    if not d.base_ok:
        reason = (
            f"confidence {d.confidence:.2f} below minimum"
            if d.data_quality == "GOOD"
            else f"data quality {d.data_quality or 'UNKNOWN'}"
        )
        lines += ["", f"🚫 Base conditions not met ({reason})"]

    # Gate diagnostics
    lines += ["", "Gate diagnostics:", ""]
    lines += _gate_block("Gate A", d.gate_a_passed, d.gate_a_requirements)
    lines.append("")
    lines += _gate_block("Gate B", d.gate_b_passed, d.gate_b_requirements)

    # Risks
    lines += ["", "Risks:", ""]
    risks = _risks(analysis)
    lines += risks if risks else ["— none identified"]

    # Conclusion
    lines += ["", "Conclusion:", "", _conclusion(analysis)]

    return "\n".join(lines)


def _gate_block(label: str, passed: bool, reqs: tuple[GateRequirement, ...]) -> list[str]:
    lines = [f"{label}: {'✅' if passed else '✗'}"]
    for r in reqs:
        if r.passed:
            lines.append(f"{r.name.upper()} {r.actual:.0f} ✓")
        else:
            lines.append(f"{r.name.upper()} {r.actual:.0f} ✗ (need ≥{r.threshold:.0f})")
    return lines


def _risks(analysis: SymbolAnalysis) -> list[str]:
    d = analysis.diagnostics
    setup = analysis.state.setup
    risks: list[str] = []

    if d.data_quality != "GOOD":
        risks.append(f"🔴 Data quality {d.data_quality or 'UNKNOWN'}")
        risks.append("Feature values may be unreliable")

    if setup is not None:
        # Documented finding (PROJECT_STATUS.md): PRE_BREAKOUT + RANGE_COMPRESSION
        # is currently the weakest observed setup family.
        if setup.market_regime == "PRE_BREAKOUT" and setup.setup_context == "RANGE_COMPRESSION":
            risks.append("🔴 RANGE_COMPRESSION")
            risks.append("Historical outcomes weaker")
        elif setup.setup_context == "UNKNOWN":
            risks.append("🟡 Price context UNKNOWN")
            risks.append("4h environment unclear")

    return risks


def _conclusion(analysis: SymbolAnalysis) -> str:
    d = analysis.diagnostics
    setup = analysis.state.setup

    if setup is not None:
        base = (
            f"Setup active: {setup.setup_type} "
            f"[{setup.market_regime} · {setup.setup_context}] "
            f"score {setup.predictive_score:.1f}"
        )
        if _risks(analysis):
            return base + "\nSetup exists but carries the risks listed above"
        return base

    if not d.base_ok:
        return "No setup — base conditions not met"
    return "No setup — no gate fully passed (see diagnostics above)"


def _sentence(reason: str) -> str:
    """Capitalize first letter only — reason strings come from the model as-is."""
    return reason[:1].upper() + reason[1:] if reason else reason
