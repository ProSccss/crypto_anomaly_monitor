"""ResearchExportService — read-only research dataset extraction (IVS-1.4).

DATA EXTRACTION ONLY: joins setups, outcomes, and research labels into flat
rows and serializes them to JSON or CSV for Research LAB validation.

- No analytics, no statistics, no predictions, no scenario calculation.
- NULLs are preserved: null in JSON, empty cell in CSV.
- Labels and components are passed through untransformed.
- MUST NOT import PredictiveEngine, scoring, or feature generation
  (guarded by tests/test_research_export.py).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import Repository

# Flat export schema — one row per setup/outcome pair, in this column order.
FIELDS = [
    # identity (predictive_setups.id = CAM Event ID, IVS-1.1)
    "setup_id",
    "symbol",
    "model_version",
    "event_ts",
    # setup data
    "setup_type",
    "expected_direction",
    "predictive_score",
    "expected_move_score",
    "confidence",
    # market context
    "market_regime",
    "setup_context",
    "components",
    # outcome data
    "outcome_status",
    "hit_5pct",
    "hit_10pct",
    "mfe_1h",
    "mfe_4h",
    "mae_1h",
    "mae_4h",
    "time_to_peak_minutes",
    "max_drawdown",
    "evaluation_duration_minutes",
    # research
    "research_labels",
]


def _num(value: Decimal | None) -> float | None:
    """Decimal → float for serialization. None stays None."""
    return float(value) if value is not None else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def build_row(outcome, setup, instrument) -> dict:
    """Flatten one (outcome, setup, instrument) triple. Pure, no I/O."""
    return {
        "setup_id": str(setup.id),
        "symbol": instrument.symbol,
        "model_version": setup.model_version,
        "event_ts": _iso(setup.created_at),
        "setup_type": setup.setup_type,
        "expected_direction": setup.expected_direction,
        "predictive_score": _num(setup.predictive_score),
        "expected_move_score": _num(setup.expected_move_score),
        "confidence": _num(setup.confidence),
        "market_regime": setup.market_regime,
        "setup_context": setup.setup_context,
        "components": setup.components,
        "outcome_status": outcome.status,
        "hit_5pct": outcome.hit_5pct,
        "hit_10pct": outcome.hit_10pct,
        "mfe_1h": _num(outcome.mfe_1h),
        "mfe_4h": _num(outcome.mfe_4h),
        "mae_1h": _num(outcome.mae_1h),
        "mae_4h": _num(outcome.mae_4h),
        "time_to_peak_minutes": outcome.time_to_peak_minutes,
        "max_drawdown": _num(outcome.max_drawdown),
        "evaluation_duration_minutes": outcome.evaluation_duration_minutes,
        "research_labels": outcome.research_labels,
    }


def rows_to_json(rows: list[dict]) -> str:
    """JSON export — nested structures (components, labels) kept intact."""
    return json.dumps(rows, ensure_ascii=False, indent=2)


def rows_to_csv(rows: list[dict]) -> str:
    """CSV export — flat research table, one line per row.

    Nested dicts are JSON-encoded into their cell; None becomes an empty
    cell (standard CSV null representation).
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_cell(row[key]) for key in FIELDS})
    return buf.getvalue()


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


class ResearchExportService:
    """Read-only export orchestration. No caching, no state."""

    async def fetch_rows(self, session: AsyncSession) -> list[dict]:
        triples = await Repository(session).research_dataset()
        return [build_row(outcome, setup, instrument) for outcome, setup, instrument in triples]

    async def export_json(self, session: AsyncSession) -> str:
        return rows_to_json(await self.fetch_rows(session))

    async def export_csv(self, session: AsyncSession) -> str:
        return rows_to_csv(await self.fetch_rows(session))
