"""initial schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("market_type", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("exchange", "symbol", name="uq_instrument_exchange_symbol"),
    )
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE")),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("mark_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("index_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("spot_price", sa.Numeric(38, 18)),
        sa.Column("open_interest_usd", sa.Numeric(38, 8), nullable=False),
        sa.Column("volume_24h_usd", sa.Numeric(38, 8), nullable=False),
        sa.Column("funding_rate", sa.Numeric(24, 12), nullable=False),
        sa.Column("funding_8h_equivalent", sa.Numeric(24, 12), nullable=False),
        sa.Column("long_ratio", sa.Numeric(18, 10)),
        sa.Column("short_ratio", sa.Numeric(18, 10)),
        sa.Column("basis_bps", sa.Numeric(18, 6)),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("instrument_id", "ts", name="uq_snapshot_instrument_ts"),
    )
    op.create_index("ix_snapshot_instrument_ts", "market_snapshots", ["instrument_id", "ts"])
    op.create_table(
        "liquidation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE")),
        sa.Column("event_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("liquidated_side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("price", sa.Numeric(38, 18), nullable=False),
        sa.Column("notional_usd", sa.Numeric(38, 8), nullable=False),
        sa.Column("source_event_id", sa.String(160), unique=True, nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_liquidation_instrument_ts", "liquidation_events", ["instrument_id", "event_ts"])
    op.create_table(
        "signal_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("instruments.id", ondelete="CASCADE")),
        sa.Column("signal_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("fingerprint", sa.String(180), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_signal_fingerprint_created", "signal_events", ["fingerprint", "created_at"])
    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signal_events.id", ondelete="CASCADE")),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_deliveries")
    op.drop_index("ix_signal_fingerprint_created", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_index("ix_liquidation_instrument_ts", table_name="liquidation_events")
    op.drop_table("liquidation_events")
    op.drop_index("ix_snapshot_instrument_ts", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_table("instruments")
