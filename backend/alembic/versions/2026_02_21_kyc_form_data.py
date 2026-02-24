"""Add kyc_form_data table for KYC form responses

Stores structured form data filled by users during KYC onboarding:
- PEP declarations, carbon market experience, source of funds,
  tax status, and legal declarations.
- Data feeds into the final KYC PDF generation.

Revision ID: 2026_02_21_kyc_form_data
Revises: 2026_02_21_entity_type_field
Create Date: 2026-02-21
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "2026_02_21_kyc_form_data"
down_revision: Union[str, None] = "2026_02_21_entity_type_field"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kyc_form_data",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True, index=True),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.id"), nullable=True, index=True),
        # Step 1 — PEP & Compliance
        sa.Column("pep_declarations", JSONB, nullable=True),
        # Step 2 — Carbon Market Experience
        sa.Column("has_carbon_experience", sa.Boolean, nullable=True),
        sa.Column("carbon_experience_years", sa.String(20), nullable=True),
        sa.Column("carbon_credits_traded", JSONB, nullable=True),
        sa.Column("investment_objectives", JSONB, nullable=True),
        sa.Column("risk_appetite", sa.String(20), nullable=True),
        # Step 3 — Source of Funds
        sa.Column("source_of_funds", JSONB, nullable=True),
        sa.Column("expected_annual_volume", sa.String(30), nullable=True),
        sa.Column("intended_use_description", sa.Text, nullable=True),
        # Step 4 — Tax Status
        sa.Column("tax_residency_country", sa.String(100), nullable=True),
        sa.Column("subject_to_crs", sa.Boolean, nullable=True),
        # Step 5 — Declarations
        sa.Column("declarations_accepted", JSONB, nullable=True),
        # Metadata
        sa.Column("is_complete", sa.Boolean, default=False),
        sa.Column("is_submitted", sa.Boolean, default=False),
        sa.Column("current_step", sa.Integer, default=1),
        sa.Column("submitted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("kyc_form_data")
