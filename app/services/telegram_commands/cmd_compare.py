"""Telegram adapter for /compare SYMBOL SYMBOL [SYMBOL...].

Thin layer: validates input, calls ResearchService per symbol, formats a
side-by-side comparison. All analytical logic lives in ResearchService (D-009) —
this file only formats and orders existing analysis values.

Uses get_analysis() rather than get_batch_states() because the comparison
shows the main limiting reason, which requires GateDiagnostics (only present
in SymbolAnalysis).
"""
from __future__ import annotations

from app.db import SessionFactory
from app.services.research_service import (
    GateDiagnostics,
    GateRequirement,
    ResearchService,
    SymbolAnalysis,
)
from app.services.telegram_commands.context import CommandContext

_MAX_SYMBOLS = 8


async def handle(ctx: CommandContext) -> None:
    # dedupe while preserving order
    symbols = list(dict.fromkeys(a.upper() for a in ctx.args))

    if len(symbols) < 2:
        await ctx.reply(
            "Usage: /compare SYMBOL SYMBOL [SYMBOL...]\n"
            "Example: /compare LABUSDT HUSDT BTCUSDT"
        )
        return

    if len(symbols) > _MAX_SYMBOLS:
        await ctx.reply(f"Too many symbols — maximum {_MAX_SYMBOLS} per comparison.")
        return

    service = ResearchService(ctx.settings)
    async with SessionFactory() as session:
        analyses = [await service.get_analysis(sym, session) for sym in symbols]

    await ctx.reply(_format(analyses))


# ---------------------------------------------------------------------------
# Ordering — existing analysis values only (no new scoring formula)
# ---------------------------------------------------------------------------


def _sort_key(analysis: SymbolAnalysis) -> tuple[int, float, float]:
    """Priority: active setup, then confidence, then existing score.

    Tuple comparison over values the analysis already carries:
    predictive_score for setups, expected_move_score otherwise.
    """
    s = analysis.state
    return (
        1 if s.setup is not None else 0,
        s.confidence or 0.0,
        s.setup.predictive_score if s.setup is not None else (s.expected_move_score or 0.0),
    )


# ---------------------------------------------------------------------------
# Formatting — pure functions, no I/O
# ---------------------------------------------------------------------------


def _format(analyses: list[SymbolAnalysis]) -> str:
    ordered = sorted(analyses, key=_sort_key, reverse=True)

    lines: list[str] = [f"🆚 COMPARE ({len(ordered)} symbols)"]
    for analysis in ordered:
        lines.append("")
        lines.append(_format_symbol(analysis))

    lines += ["", "─" * 28, "/analyze SYMBOL — full analysis\n/why SYMBOL — setup drivers"]
    return "\n".join(lines)


def _format_symbol(analysis: SymbolAnalysis) -> str:
    state = analysis.state

    if state.as_of is None or analysis.diagnostics is None:
        return f"{state.symbol}  ⚠️ no data"

    setup = state.setup
    dq = state.data_quality or "UNKNOWN"
    conf = f"{(state.confidence or 0) * 100:.0f}%"
    bp  = f"{state.breakout_probability:.1f}"  if state.breakout_probability  is not None else "—"
    sq  = f"{state.squeeze_probability:.1f}"   if state.squeeze_probability   is not None else "—"
    ems = f"{state.expected_move_score:.1f}"   if state.expected_move_score   is not None else "—"

    lines: list[str] = []
    if setup is not None:
        lines.append(f"{state.symbol}  ✅ SETUP")
        lines.append(f"  {setup.setup_type} · {setup.expected_direction}")
        lines.append(f"  {setup.market_regime} · {setup.setup_context}")
        lines.append(f"  {dq} · Conf {conf} · Score {setup.predictive_score:.1f}")
    else:
        lines.append(f"{state.symbol}  🚫 no setup")
        lines.append(f"  Dir {state.expected_direction or '—'} · {dq} · Conf {conf}")
    lines.append(f"  BP {bp}  SQ {sq}  EMS {ems}")
    if setup is None:
        lines.append(f"  Limiting: {_limiting_reason(analysis.diagnostics)}")

    return "\n".join(lines)


def _limiting_reason(d: GateDiagnostics) -> str:
    """Main blocker, from existing diagnostics values only.

    Base conditions block everything; otherwise report the binding constraint
    (largest gap) within the gate closest to passing (fewest failed conditions).
    """
    if not d.base_ok:
        if d.data_quality != "GOOD":
            return f"data quality {d.data_quality or 'UNKNOWN'}"
        return f"confidence {d.confidence:.2f} below minimum"

    failed_a = [r for r in d.gate_a_requirements if not r.passed]
    failed_b = [r for r in d.gate_b_requirements if not r.passed]

    # A gate with no failed conditions but not passed cannot occur when
    # base_ok is True (see GateDiagnostics construction); guard anyway.
    candidates = [(len(failed_a), failed_a, "Gate A"), (len(failed_b), failed_b, "Gate B")]
    candidates = [c for c in candidates if c[1]]
    if not candidates:
        return "—"

    _, failed, label = min(candidates, key=lambda c: c[0])
    binding: GateRequirement = max(failed, key=lambda r: r.gap)
    return f"{label} — {binding.name.upper()} {binding.actual:.0f} (need ≥{binding.threshold:.0f})"
