"""expected move scanner fields"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feature_snapshots", sa.Column("expected_move_score", sa.Numeric(6, 2), nullable=False, server_default="0"))
    op.add_column("feature_snapshots", sa.Column("expected_direction", sa.String(16), nullable=False, server_default="NEUTRAL"))
    op.add_column("predictive_setups", sa.Column("setup_score", sa.Numeric(6, 2), nullable=False, server_default="0"))
    op.add_column("predictive_setups", sa.Column("expected_move_score", sa.Numeric(6, 2), nullable=False, server_default="0"))
    op.alter_column("feature_snapshots", "expected_move_score", server_default=None)
    op.alter_column("feature_snapshots", "expected_direction", server_default=None)
    op.alter_column("predictive_setups", "setup_score", server_default=None)
    op.alter_column("predictive_setups", "expected_move_score", server_default=None)


def downgrade() -> None:
    op.drop_column("predictive_setups", "expected_move_score")
    op.drop_column("predictive_setups", "setup_score")
    op.drop_column("feature_snapshots", "expected_direction")
    op.drop_column("feature_snapshots", "expected_move_score")
