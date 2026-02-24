"""Add entity_type column to entities table

Stores the legal entity type (e.g. "Limited Company", "LLP", "Corporation")
so that generated PDFs (MSA, Custody, Derivatives, NDA) can use the real
entity type instead of a hardcoded "Limited Company" placeholder.

Revision ID: 2026_02_21_entity_type_field
Revises: 2026_02_20_realistic_volume_caps
Create Date: 2026-02-21
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

revision = "2026_02_21_entity_type_field"
down_revision: Union[str, None] = "2026_02_20_realistic_volume_caps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column("entity_type", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("entities", "entity_type")
