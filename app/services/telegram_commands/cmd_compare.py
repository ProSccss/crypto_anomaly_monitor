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
from app.services.research_service import ResearchService, SymbolAnalysis
from app.services.telegram_commands.context import CommandContext
from app.services.telegram_commands.formatting import symbol_block

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
        lines.append(symbol_block(analysis))

    lines += ["", "─" * 28, "/analyze SYMBOL — full analysis\n/why SYMBOL — setup drivers"]
    return "\n".join(lines)
