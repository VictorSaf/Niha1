"""SSOT market settings — align fees, liquidity, auto-trade to SSOT values

CEA: €60M total liquidity (€30M bid + €30M ask)
EUA SWAP: €35M liquidity
Daily volume: €200K-€400K
Fees: 1.5% CEA cash, 2.0% swap
Spread: €0.05 CEA, 0.0015 ratio swap
Internal trade intervals: 3min CEA, 7min swap (with variation)

Revision ID: 2026_02_20_ssot_market_settings
Revises: 2026_02_19_platform_settings
Create Date: 2026-02-20
"""

from alembic import op

revision = "2026_02_20_ssot_market_settings"
down_revision = "2026_02_19_platform_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Update trading fees ──────────────────────────────────────────
    # CEA_CASH: 1.5% bid + 1.5% ask
    op.execute("""
        UPDATE trading_fee_configs
        SET bid_fee_rate = 0.015,
            ask_fee_rate = 0.015,
            updated_at = now()
        WHERE market = 'CEA_CASH'
    """)
    # SWAP: 2.0% bid + 2.0% ask (conversion premium)
    op.execute("""
        UPDATE trading_fee_configs
        SET bid_fee_rate = 0.020,
            ask_fee_rate = 0.020,
            updated_at = now()
        WHERE market = 'SWAP'
    """)

    # ── 2. Update AutoTradeMarketSettings ───────────────────────────────
    # CEA_BID: €30M liquidity, tight spread, natural intervals
    op.execute("""
        UPDATE auto_trade_market_settings
        SET target_liquidity = 30000000,
            price_deviation_pct = 1.5,
            avg_order_count = 30,
            min_order_volume_eur = 50000,
            max_order_volume_eur = 3000000,
            volume_variety = 8,
            max_orders_per_price_level = 5,
            interval_seconds = 45,
            internal_trade_interval = 180,
            internal_trade_volume_min = 8000,
            internal_trade_volume_max = 35000,
            avg_spread = 0.05,
            tick_size = 0.01,
            avg_order_count_variation_pct = 15,
            max_orders_per_level_variation_pct = 20,
            min_order_value_variation_pct = 25,
            order_interval_variation_pct = 30,
            updated_at = now()
        WHERE market_key = 'CEA_BID'
    """)

    # CEA_ASK: €30M liquidity, mirror of CEA_BID
    op.execute("""
        UPDATE auto_trade_market_settings
        SET target_liquidity = 30000000,
            price_deviation_pct = 1.5,
            avg_order_count = 30,
            min_order_volume_eur = 50000,
            max_order_volume_eur = 3000000,
            volume_variety = 8,
            max_orders_per_price_level = 5,
            interval_seconds = 45,
            internal_trade_interval = 180,
            internal_trade_volume_min = 8000,
            internal_trade_volume_max = 35000,
            avg_spread = 0.05,
            tick_size = 0.01,
            avg_order_count_variation_pct = 15,
            max_orders_per_level_variation_pct = 20,
            min_order_value_variation_pct = 25,
            order_interval_variation_pct = 30,
            updated_at = now()
        WHERE market_key = 'CEA_ASK'
    """)

    # EUA_SWAP: €35M liquidity, slower interval, tighter ratio spread
    op.execute("""
        UPDATE auto_trade_market_settings
        SET target_liquidity = 35000000,
            price_deviation_pct = 1.0,
            avg_order_count = 20,
            min_order_volume_eur = 50000,
            max_order_volume_eur = 3000000,
            volume_variety = 6,
            max_orders_per_price_level = 4,
            interval_seconds = 90,
            internal_trade_interval = 420,
            internal_trade_volume_min = 15000,
            internal_trade_volume_max = 60000,
            avg_spread = 0.0015,
            tick_size = 0.0001,
            avg_order_count_variation_pct = 15,
            max_orders_per_level_variation_pct = 15,
            min_order_value_variation_pct = 20,
            order_interval_variation_pct = 25,
            updated_at = now()
        WHERE market_key = 'EUA_SWAP'
    """)


def downgrade() -> None:
    # Revert to previous defaults
    op.execute("""
        UPDATE trading_fee_configs
        SET bid_fee_rate = 0.005, ask_fee_rate = 0.005, updated_at = now()
    """)
    op.execute("""
        UPDATE auto_trade_market_settings
        SET target_liquidity = 500000,
            price_deviation_pct = 3.0,
            avg_order_count = 10,
            min_order_volume_eur = 5000,
            max_order_volume_eur = 250000,
            volume_variety = 7,
            max_orders_per_price_level = 4,
            interval_seconds = 60,
            internal_trade_interval = 120,
            internal_trade_volume_min = 10000,
            internal_trade_volume_max = 100000,
            avg_spread = 0.20,
            tick_size = 0.10,
            updated_at = now()
        WHERE market_key IN ('CEA_BID', 'CEA_ASK')
    """)
    op.execute("""
        UPDATE auto_trade_market_settings
        SET target_liquidity = 1000000,
            price_deviation_pct = 2.0,
            avg_order_count = 8,
            min_order_volume_eur = 10000,
            max_order_volume_eur = 500000,
            volume_variety = 5,
            max_orders_per_price_level = 3,
            interval_seconds = 90,
            internal_trade_interval = 300,
            internal_trade_volume_min = 25000,
            internal_trade_volume_max = 200000,
            avg_spread = 0.0050,
            tick_size = 0.0010,
            updated_at = now()
        WHERE market_key = 'EUA_SWAP'
    """)
