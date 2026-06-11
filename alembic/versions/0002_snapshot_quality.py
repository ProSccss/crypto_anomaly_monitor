"""snapshot quality metadata"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_snapshots", sa.Column("spot_source", sa.String(64), nullable=True))
    op.add_column("market_snapshots", sa.Column("data_quality_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("market_snapshots", sa.Column("data_quality_status", sa.String(16), nullable=False, server_default="UNKNOWN"))
    op.add_column("market_snapshots", sa.Column("missing_fields", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("market_snapshots", sa.Column("source_errors", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.alter_column("market_snapshots", "data_quality_status", server_default=None)
    op.alter_column("market_snapshots", "missing_fields", server_default=None)
    op.alter_column("market_snapshots", "source_errors", server_default=None)


def downgrade() -> None:
    op.drop_column("market_snapshots", "source_errors")
    op.drop_column("market_snapshots", "missing_fields")
    op.drop_column("market_snapshots", "data_quality_status")
    op.drop_column("market_snapshots", "data_quality_score")
    op.drop_column("market_snapshots", "spot_source")

