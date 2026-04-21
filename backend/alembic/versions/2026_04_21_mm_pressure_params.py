"""mm_pressure_params — add pressure model columns to auto_trade_market_settings

Revision ID: 2026_04_21_mm_pressure_params
Revises: 2026_04_04_autotrade_ssot
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision: str = "2026_04_21_mm_pressure_params"
down_revision: str = "2026_04_04_autotrade_ssot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("pressure_momentum", sa.Numeric(4, 2), nullable=False, server_default="0.70"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("pressure_sigma", sa.Numeric(4, 2), nullable=False, server_default="0.25"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("reversion_alpha", sa.Numeric(4, 2), nullable=False, server_default="0.20"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("band_amplitude_ticks", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("auto_trade_market_settings", "band_amplitude_ticks")
    op.drop_column("auto_trade_market_settings", "reversion_alpha")
    op.drop_column("auto_trade_market_settings", "pressure_sigma")
    op.drop_column("auto_trade_market_settings", "pressure_momentum")
