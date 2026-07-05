"""IVS-1.1 — model identity stamping on the setup/outcome write path."""
import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.model_version import CAM_MODEL_VERSION


def test_model_version_constant():
    assert CAM_MODEL_VERSION == "CAM_V2.7_FREEZE"


def _domain_setup():
    from app.domain import PredictiveSetup

    return PredictiveSetup(
        ts=datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
        symbol="LABUSDT",
        setup_type="SHORT_SQUEEZE_SETUP",
        predictive_score=61.3,
        setup_score=60.0,
        expected_move_score=60.0,
        expected_move_probability=55.0,
        expected_direction="LONG",
        estimated_breakout_window="1-4h",
        squeeze_probability=70.0,
        breakout_probability=65.0,
        confidence=0.9,
        reasons=["negative funding"],
        components={},
        market_regime="PRE_BREAKOUT",
        setup_context="RANGE_COMPRESSION",
    )


def test_setup_row_stamped_with_model_version():
    pytest.importorskip("sqlalchemy")
    from app.repository import Repository

    class FakeSession:
        row = None

        def add(self, row):
            self.row = row

        async def flush(self):
            pass

    session = FakeSession()
    row = asyncio.run(
        Repository(session).save_predictive_setup(uuid4(), "LABUSDT", _domain_setup())
    )
    assert row is session.row
    assert row.model_version == CAM_MODEL_VERSION


def test_outcome_copies_model_version_from_setup():
    pytest.importorskip("sqlalchemy")
    from sqlalchemy.dialects import postgresql

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
            compiled = stmt.compile(dialect=postgresql.dialect())
            captured.update(compiled.params)

    asyncio.run(create_outcome_for_setup(FakeSession(), setup))
    assert captured["model_version"] == CAM_MODEL_VERSION
    assert captured["setup_id"] == setup.id
