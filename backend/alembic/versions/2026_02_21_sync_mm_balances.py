"""Sync market maker balance columns from transaction history

Merge the two branches (cea_balance + kyc_form_data) and sync
denormalized balance columns from asset_transaction history.

Revision ID: 2026_02_21_sync_mm_balances
Revises: 2026_02_21_kyc_form_data, 2026_02_21_cea_balance
Create Date: 2026-02-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "2026_02_21_sync_mm_balances"
down_revision: Union[str, Sequence[str]] = (
    "2026_02_21_kyc_form_data",
    "2026_02_21_cea_balance",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE market_maker_clients mm
        SET cea_balance = COALESCE(
            (SELECT SUM(amount) FROM asset_transactions
             WHERE market_maker_id = mm.id AND certificate_type = 'CEA'), 0),
            eua_balance = COALESCE(
            (SELECT SUM(amount) FROM asset_transactions
             WHERE market_maker_id = mm.id AND certificate_type = 'EUA'), 0)
    """)


def downgrade() -> None:
    # Data-only migration; downgrade is a no-op since we can't restore
    # the previous (stale) column values.
    pass
