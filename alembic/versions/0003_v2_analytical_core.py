"""v2 analytical core"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE")),
        sa.Column("bucket_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("open", sa.Numeric(38, 18), nullable=False),
        sa.Column("high", sa.Numeric(38, 18), nullable=False),
        sa.Column("low", sa.Numeric(38, 18), nullable=False),
        sa.Column("close", sa.Numeric(38, 18), nullable=False),
        sa.Column("volume_base", sa.Numeric(38, 18), nullable=False),
        sa.Column("turnover_usd", sa.Numeric(38, 8), nullable=False),
        sa.UniqueConstraint("instrument_id", "bucket_ts", "interval", name="uq_candle_instrument_ts_interval"),
    )
    op.create_index("ix_candle_instrument_ts", "candles", ["instrument_id", "bucket_ts"])
    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE")),
        sa.Column("bucket_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("price_return_15m", sa.Numeric(18, 8), nullable=False),
        sa.Column("price_return_1h", sa.Numeric(18, 8), nullable=False),
        sa.Column("price_return_4h", sa.Numeric(18, 8), nullable=False),
        sa.Column("realized_vol_1h", sa.Numeric(18, 8), nullable=False),
        sa.Column("range_pct_1h", sa.Numeric(18, 8), nullable=False),
        sa.Column("oi_change_15m", sa.Numeric(18, 8), nullable=False),
        sa.Column("oi_change_1h", sa.Numeric(18, 8), nullable=False),
        sa.Column("oi_acceleration", sa.Numeric(18, 8), nullable=False),
        sa.Column("funding_change_1h", sa.Numeric(18, 8), nullable=False),
        sa.Column("funding_acceleration", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume_window_usd_15m", sa.Numeric(38, 8), nullable=False),
        sa.Column("volume_zscore", sa.Numeric(18, 8), nullable=False),
        sa.Column("long_liquidations_1h", sa.Numeric(38, 8), nullable=False),
        sa.Column("short_liquidations_1h", sa.Numeric(38, 8), nullable=False),
        sa.Column("liquidation_imbalance", sa.Numeric(18, 8), nullable=False),
        sa.Column("basis_bps", sa.Numeric(18, 8), nullable=False),
        sa.Column("basis_change_1h", sa.Numeric(18, 8), nullable=False),
        sa.Column("compression_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("leverage_buildup_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("funding_pressure_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("volume_accumulation_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("liquidation_imbalance_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("basis_pressure_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("breakout_pressure", sa.Numeric(6, 2), nullable=False),
        sa.Column("squeeze_probability", sa.Numeric(6, 2), nullable=False),
        sa.Column("breakout_probability", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("components", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("instrument_id", "bucket_ts", "timeframe", name="uq_feature_instrument_ts_timeframe"),
    )
    op.create_index("ix_feature_instrument_ts", "feature_snapshots", ["instrument_id", "bucket_ts"])
    op.create_table(
        "predictive_setups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE")),
        sa.Column("setup_type", sa.String(64), nullable=False),
        sa.Column("predictive_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("expected_move_probability", sa.Numeric(6, 2), nullable=False),
        sa.Column("expected_direction", sa.String(16), nullable=False),
        sa.Column("estimated_breakout_window", sa.String(16), nullable=False),
        sa.Column("squeeze_probability", sa.Numeric(6, 2), nullable=False),
        sa.Column("breakout_probability", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("fingerprint", sa.String(180), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("components", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_predictive_fingerprint_created", "predictive_setups", ["fingerprint", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_predictive_fingerprint_created", table_name="predictive_setups")
    op.drop_table("predictive_setups")
    op.drop_index("ix_feature_instrument_ts", table_name="feature_snapshots")
    op.drop_table("feature_snapshots")
    op.drop_index("ix_candle_instrument_ts", table_name="candles")
    op.drop_table("candles")
