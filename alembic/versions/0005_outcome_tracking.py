"""outcome tracking"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "setup_outcomes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("setup_id", UUID(as_uuid=True), sa.ForeignKey("predictive_setups.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("instrument_id", UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),

        sa.Column("setup_direction", sa.String(16), nullable=False),
        sa.Column("expected_move_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("expected_move_score_bucket", sa.String(8), nullable=False),
        sa.Column("breakout_probability", sa.Numeric(8, 4), nullable=False),
        sa.Column("squeeze_probability", sa.Numeric(8, 4), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("setup_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("setup_version", sa.String(16), nullable=False, server_default="V2.5"),

        sa.Column("entry_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("price_1h", sa.Numeric(20, 8), nullable=True),
        sa.Column("price_4h", sa.Numeric(20, 8), nullable=True),
        sa.Column("price_12h", sa.Numeric(20, 8), nullable=True),

        sa.Column("return_1h", sa.Numeric(10, 4), nullable=True),
        sa.Column("return_4h", sa.Numeric(10, 4), nullable=True),
        sa.Column("return_12h", sa.Numeric(10, 4), nullable=True),

        sa.Column("mfe_1h", sa.Numeric(10, 4), nullable=True),
        sa.Column("mae_1h", sa.Numeric(10, 4), nullable=True),
        sa.Column("mfe_4h", sa.Numeric(10, 4), nullable=True),
        sa.Column("mae_4h", sa.Numeric(10, 4), nullable=True),
        sa.Column("mfe_12h", sa.Numeric(10, 4), nullable=True),
        sa.Column("mae_12h", sa.Numeric(10, 4), nullable=True),

        sa.Column("hit_3pct", sa.Boolean, nullable=True),
        sa.Column("hit_5pct", sa.Boolean, nullable=True),
        sa.Column("hit_10pct", sa.Boolean, nullable=True),

        sa.Column("time_to_hit_3pct", sa.Integer, nullable=True),
        sa.Column("time_to_hit_5pct", sa.Integer, nullable=True),
        sa.Column("time_to_hit_10pct", sa.Integer, nullable=True),

        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_outcome_status", "setup_outcomes", ["status"])
    op.create_index("ix_outcome_setup_created_at", "setup_outcomes", ["setup_created_at"])
    op.create_index("ix_outcome_score_bucket", "setup_outcomes", ["expected_move_score_bucket"])
    op.create_index("ix_outcome_instrument_id", "setup_outcomes", ["instrument_id"])


def downgrade() -> None:
    op.drop_index("ix_outcome_instrument_id", "setup_outcomes")
    op.drop_index("ix_outcome_score_bucket", "setup_outcomes")
    op.drop_index("ix_outcome_setup_created_at", "setup_outcomes")
    op.drop_index("ix_outcome_status", "setup_outcomes")
    op.drop_table("setup_outcomes")
