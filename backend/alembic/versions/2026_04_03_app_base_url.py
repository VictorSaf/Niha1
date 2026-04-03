"""Add app_base_url to mail_config (feature: server URL setting)

Adds a dedicated app_base_url column to mail_config.
All backend URL-building code prefers this over invitation_link_base_url,
with fallback to invitation_link_base_url for backward compatibility.

Revision ID: 2026_04_03_app_base_url
Revises: 2026_04_03_userrole_no_troducer
Create Date: 2026-04-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2026_04_03_app_base_url"
down_revision: Union[str, None] = "2026_04_03_userrole_no_troducer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mail_config",
        sa.Column("app_base_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mail_config", "app_base_url")
