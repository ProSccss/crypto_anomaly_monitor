"""v2.6 raw research features on feature_snapshots"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_COLUMNS = [
    "impulse_strength",
    "oi_derisking",
    "oi_crowding",
    "volume_presence",
    "volume_weakness",
    "liq_fuel",
    "funding_overheating",
    "funding_cooling",
    "price_settling",
    "continuation_score_raw",
    "reversal_score_raw",
    "trend_structure_score_raw",
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.add_column(
            "feature_snapshots",
            sa.Column(col, sa.Numeric(6, 2), nullable=True),
        )


def downgrade() -> None:
    for col in reversed(_COLUMNS):
        op.drop_column("feature_snapshots", col)
