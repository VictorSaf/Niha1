"""Add cea_balance to market_maker_clients

Revision ID: 2026_02_21_cea_balance
Revises: 2026_02_20_realistic_volume_caps
Create Date: 2026-02-21
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "2026_02_21_cea_balance"
down_revision: Union[str, None] = "2026_02_20_realistic_volume_caps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_maker_clients",
        sa.Column("cea_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("market_maker_clients", "cea_balance")
