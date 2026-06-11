"""Add market_regime to predictive_setups and setup_outcomes"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Allowed values (enforced at application level, not DB constraint —
# keeps migrations simple and allows future taxonomy extension without DDL).
# Current values: PRE_BREAKOUT | CONTINUATION


def upgrade() -> None:
    op.add_column(
        "predictive_setups",
        sa.Column(
            "market_regime",
            sa.String(32),
            nullable=False,
            server_default="PRE_BREAKOUT",
        ),
    )
    op.add_column(
        "setup_outcomes",
        sa.Column(
            "market_regime",
            sa.String(32),
            nullable=False,
            server_default="PRE_BREAKOUT",
        ),
    )
    # Index on setup_outcomes for fast filtering in /performance and /calibration
    op.create_index(
        "ix_outcome_market_regime",
        "setup_outcomes",
        ["market_regime"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_market_regime", table_name="setup_outcomes")
    op.drop_column("setup_outcomes", "market_regime")
    op.drop_column("predictive_setups", "market_regime")
