"""v2.6 simplify research features: drop composites, add price_return_*_abs"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Columns added by 0006 that we no longer need
_DROP_COLUMNS = [
    "impulse_strength",
    "continuation_score_raw",
    "reversal_score_raw",
    "trend_structure_score_raw",
]

# New raw price-return columns (unsigned, %)
_ADD_COLUMNS = [
    ("price_return_15m_abs", sa.Numeric(8, 4)),
    ("price_return_1h_abs",  sa.Numeric(8, 4)),
    ("price_return_4h_abs",  sa.Numeric(8, 4)),
]


def upgrade() -> None:
    for col in _DROP_COLUMNS:
        op.drop_column("feature_snapshots", col)

    for name, col_type in _ADD_COLUMNS:
        op.add_column(
            "feature_snapshots",
            sa.Column(name, col_type, nullable=True),
        )


def downgrade() -> None:
    for name, _ in reversed(_ADD_COLUMNS):
        op.drop_column("feature_snapshots", name)

    for col in reversed(_DROP_COLUMNS):
        op.add_column(
            "feature_snapshots",
            sa.Column(col, sa.Numeric(6, 2), nullable=True),
        )
