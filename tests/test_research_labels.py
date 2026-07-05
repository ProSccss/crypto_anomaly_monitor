"""IVS-1.2 — research labels: passive storage, zero production coupling."""
import asyncio
import inspect
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


def test_default_structure():
    pytest.importorskip("sqlalchemy")
    from app.repository import Repository

    labels = Repository.default_research_labels()
    assert labels == {
        "scenario": None,
        "lifecycle_phase": None,
        "reversal_candidate": False,
        "notes": "",
    }
    # fresh dict each call — callers can mutate safely
    assert Repository.default_research_labels() is not labels


def test_labels_can_be_stored_and_are_normalized():
    pytest.importorskip("sqlalchemy")
    from app.repository import Repository

    class FakeOutcome:
        research_labels = None

    outcome = FakeOutcome()

    class FakeSession:
        async def get(self, model, pk):
            return outcome

    ok = asyncio.run(
        Repository(FakeSession()).update_research_labels(
            uuid4(), {"scenario": "FAILED_BREAKOUT", "notes": "faded after 2h"}
        )
    )
    assert ok is True
    assert outcome.research_labels == {
        "scenario": "FAILED_BREAKOUT",
        "lifecycle_phase": None,
        "reversal_candidate": False,
        "notes": "faded after 2h",
    }


def test_update_returns_false_for_missing_outcome():
    pytest.importorskip("sqlalchemy")
    from app.repository import Repository

    class FakeSession:
        async def get(self, model, pk):
            return None

    ok = asyncio.run(Repository(FakeSession()).update_research_labels(uuid4(), {}))
    assert ok is False


def test_outcome_creation_works_without_labels():
    """New outcomes are created with research_labels absent (column stays NULL)."""
    pytest.importorskip("sqlalchemy")
    from sqlalchemy.dialects import postgresql

    from app.model_version import CAM_MODEL_VERSION
    from app.models import PredictiveSetupModel
    from app.services.outcome_evaluator import create_outcome_for_setup

    setup = PredictiveSetupModel(
        id=uuid4(),
        instrument_id=uuid4(),
        setup_type="SHORT_SQUEEZE_SETUP",
        predictive_score=Decimal("61.3"),
        expected_move_score=Decimal("60"),
        expected_move_probability=Decimal("55"),
        expected_direction="LONG",
        estimated_breakout_window="1-4h",
        squeeze_probability=Decimal("70"),
        breakout_probability=Decimal("65"),
        confidence=Decimal("0.9"),
        fingerprint="LABUSDT:SHORT_SQUEEZE_SETUP:LONG",
        reasons=[],
        components={},
        market_regime="PRE_BREAKOUT",
        setup_context="RANGE_COMPRESSION",
        model_version=CAM_MODEL_VERSION,
        created_at=datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
    )

    captured = {}

    class FakeSession:
        async def execute(self, stmt):
            captured.update(stmt.compile(dialect=postgresql.dialect()).params)

    asyncio.run(create_outcome_for_setup(FakeSession(), setup))
    assert "research_labels" not in captured
    assert captured["setup_id"] == setup.id


def test_labels_do_not_affect_outcome_calculations():
    """Guard: the evaluator and aggregation queries never touch research_labels."""
    pytest.importorskip("sqlalchemy")
    from app.repository import Repository
    from app.services import outcome_evaluator

    # Evaluator (all outcome calculations) is label-blind.
    assert "research_labels" not in inspect.getsource(outcome_evaluator)

    # Aggregations / report queries are label-blind.
    for method in (
        Repository.outcome_stats,
        Repository.outcome_dashboard_data,
        Repository.feature_research_data,
    ):
        assert "research_labels" not in inspect.getsource(method)
