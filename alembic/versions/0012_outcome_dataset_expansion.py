"""Outcome dataset expansion (IVS-1.3)"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Passive measurement fields — data collection only. Computed by the
# OutcomeEvaluator alongside (never instead of) the existing metrics;
# never read by setup selection, scoring, gates, or alerts.
#
# NOTE: mfe_1h / mfe_4h / mae_1h / mae_4h from the IVS-1.3 spec already
# exist since migration 0005 and are NOT re-added here (IVS-1.0 audit).
#
# Semantics (all measured within the setup→4h candle window, matching the
# basis of the existing hit flags):
#   time_to_peak_minutes        — minutes from setup creation to the maximum
#                                 favorable excursion
#   max_drawdown                — largest % retracement of the favorable move
#                                 after its peak (distinct from MAE, which is
#                                 adverse-from-entry)
#   evaluation_duration_minutes — actual observed evaluation window: minutes
#                                 from setup creation to status=complete
#
# Nullable, no defaults, no backfill: old outcomes remain valid with NULLs.


def upgrade() -> None:
    op.add_column(
        "setup_outcomes",
        sa.Column("time_to_peak_minutes", sa.Integer, nullable=True),
    )
    op.add_column(
        "setup_outcomes",
        sa.Column("max_drawdown", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "setup_outcomes",
        sa.Column("evaluation_duration_minutes", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("setup_outcomes", "evaluation_duration_minutes")
    op.drop_column("setup_outcomes", "max_drawdown")
    op.drop_column("setup_outcomes", "time_to_peak_minutes")
