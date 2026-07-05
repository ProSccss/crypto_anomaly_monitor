"""IVS-1.4 — research export: extraction only, NULL-safe, model-decoupled."""
import ast
import csv
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

EXPORT_PATH = Path(__file__).resolve().parent.parent / "app" / "services" / "research_export.py"

T0 = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def _setup(**kw):
    base = dict(
        id=uuid4(),
        created_at=T0,
        model_version="CAM_V2.7_FREEZE",
        setup_type="SHORT_SQUEEZE_SETUP",
        expected_direction="LONG",
        predictive_score=Decimal("61.3"),
        expected_move_score=Decimal("60"),
        confidence=Decimal("0.9"),
        market_regime="PRE_BREAKOUT",
        setup_context="RANGE_COMPRESSION",
        components={"funding_pct_8h": -0.2},
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _outcome(**kw):
    base = dict(
        status="complete",
        hit_5pct=True,
        hit_10pct=False,
        mfe_1h=Decimal("3.2"),
        mfe_4h=Decimal("6.1"),
        mae_1h=Decimal("1.0"),
        mae_4h=Decimal("2.4"),
        time_to_peak_minutes=95,
        max_drawdown=Decimal("2.8"),
        evaluation_duration_minutes=725,
        research_labels={"scenario": "CLEAN_BREAKOUT", "lifecycle_phase": None,
                         "reversal_candidate": False, "notes": ""},
    )
    base.update(kw)
    return SimpleNamespace(**base)


INSTRUMENT = SimpleNamespace(symbol="LABUSDT")


def test_export_contains_all_entities():
    pytest.importorskip("sqlalchemy")
    from app.services.research_export import FIELDS, build_row

    row = build_row(_outcome(), _setup(), INSTRUMENT)
    assert set(row) == set(FIELDS)
    assert row["symbol"] == "LABUSDT"                       # instrument
    assert row["setup_type"] == "SHORT_SQUEEZE_SETUP"       # setup
    assert row["model_version"] == "CAM_V2.7_FREEZE"
    assert row["event_ts"] == "2026-07-05T12:00:00+00:00"
    assert row["hit_5pct"] is True                          # outcome
    assert row["mfe_4h"] == 6.1
    assert row["time_to_peak_minutes"] == 95                # IVS-1.3 fields
    assert row["max_drawdown"] == 2.8
    assert row["research_labels"]["scenario"] == "CLEAN_BREAKOUT"  # labels


def test_old_rows_with_nulls_export_successfully():
    pytest.importorskip("sqlalchemy")
    from app.services.research_export import build_row, rows_to_csv, rows_to_json

    old = build_row(
        _outcome(research_labels=None, time_to_peak_minutes=None, max_drawdown=None,
                 evaluation_duration_minutes=None, mfe_1h=None, mae_1h=None,
                 hit_5pct=None, hit_10pct=None, status="partial"),
        _setup(model_version=None),
        INSTRUMENT,
    )
    assert old["model_version"] is None
    assert old["research_labels"] is None
    assert old["time_to_peak_minutes"] is None

    # both serializers accept NULL-heavy rows
    parsed = json.loads(rows_to_json([old]))
    assert parsed[0]["model_version"] is None       # null preserved, not backfilled
    csv_text = rows_to_csv([old])
    assert len(csv_text.splitlines()) == 2          # header + 1 row


def test_json_preserves_structure():
    pytest.importorskip("sqlalchemy")
    from app.services.research_export import build_row, rows_to_json

    rows = [build_row(_outcome(), _setup(), INSTRUMENT)]
    parsed = json.loads(rows_to_json(rows))
    assert parsed == rows  # lossless round-trip
    assert parsed[0]["components"] == {"funding_pct_8h": -0.2}  # nested, untransformed
    assert parsed[0]["research_labels"]["reversal_candidate"] is False


def test_csv_is_flat_research_table():
    pytest.importorskip("sqlalchemy")
    from app.services.research_export import FIELDS, build_row, rows_to_csv

    rows = [
        build_row(_outcome(), _setup(), INSTRUMENT),
        build_row(_outcome(hit_5pct=False), _setup(expected_direction="SHORT"), INSTRUMENT),
    ]
    reader = csv.reader(io.StringIO(rows_to_csv(rows)))
    lines = list(reader)
    assert lines[0] == FIELDS                     # header = declared schema
    assert len(lines) == 3                        # header + 2 data rows
    assert all(len(line) == len(FIELDS) for line in lines)
    # nested dicts are JSON-encoded cells, still machine-readable
    labels_cell = lines[1][FIELDS.index("research_labels")]
    assert json.loads(labels_cell)["scenario"] == "CLEAN_BREAKOUT"


def test_static_guard_no_model_imports():
    """research_export must never import predictive, scoring, or features."""
    tree = ast.parse(EXPORT_PATH.read_text(encoding="utf-8"))
    forbidden = ("predictive", "scoring", "features")
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        for module in modules:
            for bad in forbidden:
                assert bad not in module, f"forbidden import '{module}' in research_export.py"
