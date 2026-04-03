"""CEA liquidity depth — widen price band to reach 30M target

price_deviation_pct 1.5% gave only 2 price levels → ~10 orders max → ~15M liquidity.
With 5% deviation: ~6 levels × 5 orders = 30 orders → enough to reach 30M target.
max_orders_per_price_level increased to 8 for additional headroom.

Revision ID: 2026_03_01_cea_liquidity_depth
Revises: 2026_03_01_cea_spread_0_1
Create Date: 2026-03-01

"""
from alembic import op

revision = "2026_03_01_cea_liquidity_depth"
down_revision = "2026_03_01_cea_spread_0_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CEA_BID + CEA_ASK: widen price band (5% vs 1.5%) + more orders per level
    op.execute("""
        UPDATE auto_trade_market_settings
        SET price_deviation_pct = 5.0,
            max_orders_per_price_level = 8,
            updated_at = now()
        WHERE market_key IN ('CEA_BID', 'CEA_ASK')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE auto_trade_market_settings
        SET price_deviation_pct = 1.5,
            max_orders_per_price_level = 5,
            updated_at = now()
        WHERE market_key IN ('CEA_BID', 'CEA_ASK')
    """)
