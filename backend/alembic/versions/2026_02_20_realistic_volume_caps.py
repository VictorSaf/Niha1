"""Adjust daily volume caps and price depth to realistic values

Previous caps (€100K-€150K/day) were too low — internal trades at 180s intervals
would hit the cap in ~3 hours. Realistic caps allow full-day trading:
- CEA_BID: €750,000/day (~35 trades × €20K avg)
- CEA_ASK: €750,000/day
- EUA_SWAP: €600,000/day (~17 trades × €35K avg)
- Total: ~€2.1M/day across all markets

Also adjusts price_deviation_pct for natural order book depth:
- CEA (BID+ASK): 4% (was 1.5%) — at €75 CEA = €3 depth, 30 orders across 30 levels
- EUA_SWAP: 2.5% (was 1%) — ratio 0.12 ± 0.003

Revision ID: 2026_02_20_realistic_volume_caps
Revises: 2026_02_20_daily_volume_cap
Create Date: 2026-02-20
"""

from alembic import op
from sqlalchemy import text

revision = "2026_02_20_realistic_volume_caps"
down_revision = "2026_02_20_daily_volume_cap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # CEA_BID: cap €750K/day, price depth 4%
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 750000, "
            "    price_deviation_pct = 4.0 "
            "WHERE market_key = 'CEA_BID'"
        )
    )

    # CEA_ASK: cap €750K/day, price depth 4%
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 750000, "
            "    price_deviation_pct = 4.0 "
            "WHERE market_key = 'CEA_ASK'"
        )
    )

    # EUA_SWAP: cap €600K/day, price depth 2.5%
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 600000, "
            "    price_deviation_pct = 2.5 "
            "WHERE market_key = 'EUA_SWAP'"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Revert to previous values
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 100000, "
            "    price_deviation_pct = 1.5 "
            "WHERE market_key = 'CEA_BID'"
        )
    )
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 100000, "
            "    price_deviation_pct = 1.5 "
            "WHERE market_key = 'CEA_ASK'"
        )
    )
    conn.execute(
        text(
            "UPDATE auto_trade_market_settings "
            "SET daily_volume_cap_eur = 150000, "
            "    price_deviation_pct = 1.0 "
            "WHERE market_key = 'EUA_SWAP'"
        )
    )
