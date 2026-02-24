"""Add daily volume cap to auto_trade_market_settings

Adds columns for daily volume tracking and capping:
- daily_volume_cap_eur: max EUR volume of internal trades per day (NULL = no cap)
- daily_volume_used_eur: accumulated volume today (resets at midnight UTC)
- daily_volume_reset_at: next midnight UTC reset timestamp

Default caps based on SSOT daily volume target (€200K-€400K total):
- CEA_BID: €100,000/day
- CEA_ASK: €100,000/day
- EUA_SWAP: €150,000/day
- Total: €350,000/day

Revision ID: 2026_02_20_daily_volume_cap
Revises: 2026_02_20_ssot_market_settings
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import datetime, timezone

revision = "2026_02_20_daily_volume_cap"
down_revision = "2026_02_20_ssot_market_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add daily volume tracking columns
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("daily_volume_cap_eur", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column(
            "daily_volume_used_eur",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("daily_volume_reset_at", sa.DateTime, nullable=True),
    )

    # Set default daily volume caps per market
    # SSOT target: €200K-€400K total daily volume across all markets
    conn = op.get_bind()

    # CEA_BID: €100,000/day
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 100000, "
            "    daily_volume_used_eur = 0 "
            "WHERE market_key = 'CEA_BID'"
        )
    )

    # CEA_ASK: €100,000/day
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 100000, "
            "    daily_volume_used_eur = 0 "
            "WHERE market_key = 'CEA_ASK'"
        )
    )

    # EUA_SWAP: €150,000/day
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 150000, "
            "    daily_volume_used_eur = 0 "
            "WHERE market_key = 'EUA_SWAP'"
        )
    )


def downgrade() -> None:
    op.drop_column("auto_trade_market_settings", "daily_volume_reset_at")
    op.drop_column("auto_trade_market_settings", "daily_volume_used_eur")
    op.drop_column("auto_trade_market_settings", "daily_volume_cap_eur")
