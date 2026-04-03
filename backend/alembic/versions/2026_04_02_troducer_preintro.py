"""Migrate legacy TRODUCER users to PREINTRODUCER (feature 0072)

The TRODUCER role is removed from application code. Existing rows are updated
before deploy. A follow-up migration removes the TRODUCER enum label from PostgreSQL.

Revision ID must stay ≤32 chars (alembic_version.version_num).

Revision ID: 2026_04_02_troducer_preintro
Revises: 2026_03_01_cea_liquidity_depth
Create Date: 2026-04-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "2026_04_02_troducer_preintro"
down_revision: Union[str, None] = "2026_03_01_cea_liquidity_depth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'PREINTRODUCER' WHERE role = 'TRODUCER'")


def downgrade() -> None:
    # Not reversible: we cannot distinguish PREINTRODUCER rows migrated from TRODUCER
    # from natively created PREINTRODUCER users.
    pass
