"""Add setup_context to predictive_setups and setup_outcomes"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# setup_context classifies the price environment at the moment Gate A fires,
# using abs(price_return_4h) as the discriminating signal:
#   TREND_COMPRESSION   — abs(pr4h) >= 5%: price was actively moving in 4h window
#   RANGE_COMPRESSION   — abs(pr4h) <  3%: price stable over 4h (true range setup)
#   UNKNOWN             — abs(pr4h) in 3–5% grey zone or data unavailable
#
# This is a pure analytics tag — does not affect gate logic or scoring.
# Stored in both tables (denormalized) so /performance can filter without JOIN.


def upgrade() -> None:
    op.add_column(
        "predictive_setups",
        sa.Column(
            "setup_context",
            sa.String(32),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.add_column(
        "setup_outcomes",
        sa.Column(
            "setup_context",
            sa.String(32),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.create_index(
        "ix_outcome_setup_context",
        "setup_outcomes",
        ["setup_context"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_setup_context", table_name="setup_outcomes")
    op.drop_column("setup_outcomes", "setup_context")
    op.drop_column("predictive_setups", "setup_context")
