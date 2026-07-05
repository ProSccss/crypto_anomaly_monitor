"""Add research_labels to setup_outcomes (IVS-1.2)"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# Passive research annotation storage — written only by research tooling,
# never read by the scanner, evaluator, alerts, or scoring.
#
# Canonical structure (normalized at write time by Repository):
#   {
#     "scenario": null,
#     "lifecycle_phase": null,
#     "reversal_candidate": false,
#     "notes": ""
#   }
#
# Nullable, no backfill: NULL = never labeled (pre-IVS-1.2 or untouched).


def upgrade() -> None:
    op.add_column(
        "setup_outcomes",
        sa.Column("research_labels", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("setup_outcomes", "research_labels")
