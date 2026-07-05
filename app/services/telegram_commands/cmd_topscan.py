"""Telegram adapter for /topscan — Research Console market radar.

Thin layer: calls ResearchService for every monitored symbol and shows the
top entries. All analytical logic lives in ResearchService (D-009) — ordering
is tuple comparison over existing analysis values (setup presence, gate
closeness from existing gaps, expected_move_score, confidence). No new
scores, thresholds, or recommendations.
"""
from __future__ import annotations

from app.db import SessionFactory
from app.services.research_service import ResearchService, SymbolAnalysis
from app.services.telegram_commands.context import CommandContext
from app.services.telegram_commands.formatting import gate_closeness, symbol_block

_TOP_N = 5


async def handle(ctx: CommandContext) -> None:
    symbols = ctx.settings.monitored_symbols
    if not symbols:
        await ctx.reply("No monitored symbols configured.")
        return

    service = ResearchService(ctx.settings)
    async with SessionFactory() as session:
        analyses = [await service.get_analysis(sym, session) for sym in symbols]

    await ctx.reply(_format(analyses))


# ---------------------------------------------------------------------------
# Ordering — existing analysis values only (no ranking formula)
# ---------------------------------------------------------------------------


def _sort_key(analysis: SymbolAnalysis) -> tuple:
    """Ascending sort key.

    Tiers: active setup → base OK (gates pending) → base failed → no data.
    Within a tier: closest gate completion (fewest failed conditions, then
    smallest binding gap), then higher expected_move_score, then confidence.
    """
    s = analysis.state
    d = analysis.diagnostics

    if s.as_of is None or d is None:
        tier, closeness = 3, (99, float("inf"))
    elif s.setup is not None:
        tier, closeness = 0, (0, 0.0)
    elif d.base_ok:
        tier, closeness = 1, gate_closeness(d)
    else:
        tier, closeness = 2, gate_closeness(d)

    return (
        tier,
        closeness[0],
        closeness[1],
        -(s.expected_move_score or 0.0),
        -(s.confidence or 0.0),
    )


# ---------------------------------------------------------------------------
# Formatting — pure functions, no I/O
# ---------------------------------------------------------------------------


def _format(analyses: list[SymbolAnalysis]) -> str:
    ordered = sorted(analyses, key=_sort_key)
    with_data = [a for a in analyses if a.state.as_of is not None]
    setups = [a for a in analyses if a.state.setup is not None]

    lines: list[str] = [
        "📡 TOPSCAN — market radar",
        f"{len(analyses)} monitored · {len(with_data)} with data · {len(setups)} active setups",
    ]

    for rank, analysis in enumerate(ordered[:_TOP_N], start=1):
        lines.append("")
        lines.append(symbol_block(analysis, prefix=f"{rank}. "))

    remaining = len(ordered) - _TOP_N
    if remaining > 0:
        lines += ["", f"(+{remaining} more not shown)"]

    lines += ["", "─" * 28, "/analyze SYMBOL — full analysis\n/why SYMBOL — setup drivers"]
    return "\n".join(lines)
