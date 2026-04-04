"""autotrade_ssot — add alignment/rebalance params to market settings

Revision ID: 2026_04_04_autotrade_ssot
Revises: 2026_04_03_userrole_no_troducer
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision: str = "2026_04_04_autotrade_ssot"
down_revision: str = "2026_04_03_app_base_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("alignment_correction_factor", sa.Numeric(5, 2), nullable=False, server_default="0.60"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("alignment_threshold_ticks", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("level_rebalance_depth", sa.Integer(), nullable=False, server_default="5"),
    )


def downgrade() -> None:
    op.drop_column("auto_trade_market_settings", "level_rebalance_depth")
    op.drop_column("auto_trade_market_settings", "alignment_threshold_ticks")
    op.drop_column("auto_trade_market_settings", "alignment_correction_factor")
