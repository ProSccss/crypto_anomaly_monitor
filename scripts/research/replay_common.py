"""Shared loading and rendering for lifecycle research tools (IVS-2.2).

DATA TOOLING ONLY. These tools read research_exports CSVs produced by
IVS-2.1 and never touch the application, the database, or CAM. They make
no predictions and no recommendations; they display stored measurements.

Blind-view discipline: everything displayable before annotation is listed
in BLIND_VIEW_FIELDS (whitelist). Outcome information — future_*, mfe_*,
mae_*, time_to_*, after_touch_* — is rendered only by the reveal path.
"""
from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

GRID_TIMEFRAMES = ("1m", "3m", "5m")
GRID_PERIODS = (60, 120, 180, 240)
GRID_EMA_NAMES = [f"ema{p}_{tf}" for tf in GRID_TIMEFRAMES for p in GRID_PERIODS]
STANDARD_EMA_NAMES = ["ema20", "ema50", "ema200"]

PRICE_FIELDS = ["close", "return_15m", "return_1h", "return_4h", "volatility"]
DERIVATIVES_FIELDS = [
    "funding_rate", "funding_change", "open_interest", "oi_change",
    "long_liquidations", "short_liquidations", "liquidation_ratio",
]
CAM_FIELDS = [
    "bp", "sq", "ems", "expected_direction", "setup_detected",
    "setup_type", "market_regime", "setup_context", "confidence",
]

BLIND_VIEW_FIELDS = (
    ["symbol", "timestamp"]
    + PRICE_FIELDS
    + STANDARD_EMA_NAMES
    + [f"price_distance_{n}" for n in STANDARD_EMA_NAMES]
    + GRID_EMA_NAMES
    + [f"price_distance_{n}" for n in GRID_EMA_NAMES]
    + ["nearest_ema", "nearest_ema_distance_percent", "ema_touch_event", "touched_ema"]
    + DERIVATIVES_FIELDS
    + CAM_FIELDS
)

# Anything with these prefixes is outcome information (hidden until reveal).
OUTCOME_FIELD_PREFIXES = (
    "future_", "mfe_", "mae_", "time_to_high", "time_to_low", "after_touch_return_",
)


def default_csv_path(symbol: str) -> Path:
    return Path("research_exports") / f"{symbol.upper()}_replay.csv"


def parse_value(text: str):
    if text == "":
        return None
    if text == "True":
        return True
    if text == "False":
        return False
    try:
        return float(text)
    except ValueError:
        return text


def load_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as handle:
        return [
            {key: parse_value(value) for key, value in raw.items()}
            for raw in csv.DictReader(handle)
        ]


def row_ts(row: dict) -> datetime:
    return datetime.fromisoformat(row["timestamp"])


def parse_time_arg(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def parse_step(text: str) -> int:
    """'30m' → 30, '2h' → 120."""
    text = text.strip().lower()
    if text.endswith("m"):
        return int(text[:-1])
    if text.endswith("h"):
        return int(text[:-1]) * 60
    return int(text)


def find_index_at_or_after(rows: list[dict], target: datetime) -> int | None:
    for i, row in enumerate(rows):
        if row_ts(row) >= target:
            return i
    return None


def fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return str(value)


def render_blind_view(row: dict) -> str:
    """Point-in-time view: ONLY information available at that moment."""
    lines = [
        f"=== {row.get('symbol', '?')} @ {row.get('timestamp', '?')}  [blind view] ===",
        "",
        "PRICE",
    ]
    for field in PRICE_FIELDS:
        lines.append(f"  {field:<28} {fmt(row.get(field))}")

    lines.append("")
    lines.append("EMA (standard)")
    for name in STANDARD_EMA_NAMES:
        lines.append(
            f"  {name:<10} {fmt(row.get(name)):>14}   dist% {fmt(row.get(f'price_distance_{name}'))}"
        )
    lines.append("EMA (LAB research grid)")
    for tf in GRID_TIMEFRAMES:
        for p in GRID_PERIODS:
            name = f"ema{p}_{tf}"
            lines.append(
                f"  {name:<10} {fmt(row.get(name)):>14}   dist% {fmt(row.get(f'price_distance_{name}'))}"
            )
    lines.append(
        f"  nearest: {fmt(row.get('nearest_ema'))} "
        f"({fmt(row.get('nearest_ema_distance_percent'))}%)  "
        f"touch: {fmt(row.get('ema_touch_event'))} {fmt(row.get('touched_ema'))}"
    )

    lines.append("")
    lines.append("DERIVATIVES")
    for field in DERIVATIVES_FIELDS:
        lines.append(f"  {field:<28} {fmt(row.get(field))}")

    lines.append("")
    lines.append("CAM (stored state)")
    for field in CAM_FIELDS:
        lines.append(f"  {field:<28} {fmt(row.get(field))}")

    return "\n".join(lines)


def outcome_fields(row: dict) -> dict:
    return {
        key: value
        for key, value in row.items()
        if key.startswith(OUTCOME_FIELD_PREFIXES)
    }


def render_outcome_view(row: dict) -> str:
    lines = [f"=== OUTCOME @ {row.get('timestamp', '?')}  [reveal] ==="]
    for key, value in outcome_fields(row).items():
        lines.append(f"  {key:<32} {fmt(value)}")
    return "\n".join(lines)


def mean(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


def median(values: list[float]) -> float | None:
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 4)
    return round((clean[mid - 1] + clean[mid]) / 2, 4)


def before_state(row: dict) -> str:
    """Compact pre-event state line set (blind fields only)."""
    lines = [
        f"  price {fmt(row.get('close'))}  nearest_ema {fmt(row.get('nearest_ema'))}"
        f" ({fmt(row.get('nearest_ema_distance_percent'))}%)",
        f"  funding {fmt(row.get('funding_rate'))}  funding_chg {fmt(row.get('funding_change'))}"
        f"  OI {fmt(row.get('open_interest'))}  OI_chg% {fmt(row.get('oi_change'))}",
        f"  CAM: BP {fmt(row.get('bp'))}  SQ {fmt(row.get('sq'))}  EMS {fmt(row.get('ems'))}"
        f"  dir {fmt(row.get('expected_direction'))}  setup {fmt(row.get('setup_detected'))}"
        f" {fmt(row.get('setup_type'))}",
    ]
    return "\n".join(lines)
