"""Shared presentation helpers for Research Console commands (/compare, /topscan).

Everything here formats or selects over values that GateDiagnostics and
SymbolState already carry — no new scores, formulas, or thresholds
(D-009, MODEL FREEZE). "Closeness" is tuple comparison over existing
GateRequirement.gap values, not a computed ranking score.
"""
from __future__ import annotations

from app.services.research_service import (
    GateDiagnostics,
    GateRequirement,
    SymbolAnalysis,
)


def nearest_gate(d: GateDiagnostics) -> tuple[str, list[GateRequirement]] | None:
    """Gate closest to passing: fewest failed conditions (tie → Gate A).

    Returns (label, failed_requirements). None when neither gate has failed
    conditions (cannot normally occur for a symbol without a setup).
    """
    failed_a = [r for r in d.gate_a_requirements if not r.passed]
    failed_b = [r for r in d.gate_b_requirements if not r.passed]
    candidates = [
        (len(failed_a), 0, "Gate A", failed_a),
        (len(failed_b), 1, "Gate B", failed_b),
    ]
    candidates = [c for c in candidates if c[3]]
    if not candidates:
        return None
    _, _, label, failed = min(candidates, key=lambda c: (c[0], c[1]))
    return label, failed


def gate_closeness(d: GateDiagnostics) -> tuple[int, float]:
    """(failed condition count, binding gap) of the nearest gate — for ordering."""
    ng = nearest_gate(d)
    if ng is None:
        return (0, 0.0)
    _, failed = ng
    return (len(failed), max(r.gap for r in failed))


def limiting_reason(d: GateDiagnostics) -> str:
    """Main blocker, from existing diagnostics values only.

    Base conditions block everything; otherwise report the binding constraint
    (largest gap) within the nearest gate.
    """
    if not d.base_ok:
        if d.data_quality != "GOOD":
            return f"data quality {d.data_quality or 'UNKNOWN'}"
        return f"confidence {d.confidence:.2f} below minimum"

    ng = nearest_gate(d)
    if ng is None:
        return "—"
    label, failed = ng
    binding = max(failed, key=lambda r: r.gap)
    return f"{label} — {binding.name.upper()} {binding.actual:.0f} (need ≥{binding.threshold:.0f})"


def symbol_block(analysis: SymbolAnalysis, prefix: str = "") -> str:
    """Compact multi-line summary of one SymbolAnalysis."""
    state = analysis.state

    if state.as_of is None or analysis.diagnostics is None:
        return f"{prefix}{state.symbol}  ⚠️ no data"

    setup = state.setup
    dq = state.data_quality or "UNKNOWN"
    conf = f"{(state.confidence or 0) * 100:.0f}%"
    bp  = f"{state.breakout_probability:.1f}"  if state.breakout_probability  is not None else "—"
    sq  = f"{state.squeeze_probability:.1f}"   if state.squeeze_probability   is not None else "—"
    ems = f"{state.expected_move_score:.1f}"   if state.expected_move_score   is not None else "—"

    lines: list[str] = []
    if setup is not None:
        lines.append(f"{prefix}{state.symbol}  ✅ SETUP")
        lines.append(f"  {setup.setup_type} · {setup.expected_direction}")
        lines.append(f"  {setup.market_regime} · {setup.setup_context}")
        lines.append(f"  {dq} · Conf {conf} · Score {setup.predictive_score:.1f}")
    else:
        lines.append(f"{prefix}{state.symbol}  🚫 no setup")
        lines.append(f"  Dir {state.expected_direction or '—'} · {dq} · Conf {conf}")
    lines.append(f"  BP {bp}  SQ {sq}  EMS {ems}")
    if setup is None:
        lines.append(f"  Limiting: {limiting_reason(analysis.diagnostics)}")

    return "\n".join(lines)
