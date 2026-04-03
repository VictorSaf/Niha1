"""CEA spread 0.1 EUR — target spread and tick for cash market

Align CEA_BID and CEA_ASK avg_spread and tick_size with refresh_cea_market
and place_random_order (both use 0.1 EUR spread/tick).
AutoTradeExecutor will then consistently target 0.1 spread.

Revision ID: 2026_03_01_cea_spread_0_1
Revises: 2026_02_21_sync_mm_balances
Create Date: 2026-03-01
"""

from alembic import op

revision = "2026_03_01_cea_spread_0_1"
down_revision = "2026_02_21_sync_mm_balances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE auto_trade_market_settings
        SET avg_spread = 0.1,
            tick_size = 0.1,
            updated_at = now()
        WHERE market_key IN ('CEA_BID', 'CEA_ASK')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE auto_trade_market_settings
        SET avg_spread = 0.05,
            tick_size = 0.01,
            updated_at = now()
        WHERE market_key IN ('CEA_BID', 'CEA_ASK')
    """)
