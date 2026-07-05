"""Add model_version to predictive_setups and setup_outcomes (IVS-1.1)"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# CAM model identity tracking — storage metadata only.
# Written from app/model_version.py (CAM_MODEL_VERSION) at row creation.
#
# Deliberately nullable with NO historical backfill:
#   NULL = row predates version tracking (pre-IVS-1.1).
# Historical rows carry setup_outcomes.setup_version = "V2.5", which was a
# hardcoded constant never bumped for V2.6/V2.7 — backfilling model_version
# from it would launder wrong data into a new column. setup_version is kept
# unchanged for compatibility.


def upgrade() -> None:
    op.add_column(
        "predictive_setups",
        sa.Column("model_version", sa.String(32), nullable=True),
    )
    op.add_column(
        "setup_outcomes",
        sa.Column("model_version", sa.String(32), nullable=True),
    )
    # Index on setup_outcomes for per-model filtering in future validation
    # queries (same pattern as market_regime / setup_context).
    op.create_index(
        "ix_outcome_model_version",
        "setup_outcomes",
        ["model_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_model_version", table_name="setup_outcomes")
    op.drop_column("setup_outcomes", "model_version")
    op.drop_column("predictive_setups", "model_version")
