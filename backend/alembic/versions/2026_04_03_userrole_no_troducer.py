"""Drop TRODUCER from PostgreSQL userrole enum (feature 0072)

Application code no longer defines TRODUCER; rows were migrated to PREINTRODUCER
in 2026_04_02_troducer_preintro. PostgreSQL cannot DROP an enum value in place,
so we recreate the type without TRODUCER and reattach users.role.

Revision ID must stay ≤32 chars (alembic_version.version_num).

Revision ID: 2026_04_03_userrole_no_troducer
Revises: 2026_04_02_troducer_preintro
Create Date: 2026-04-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "2026_04_03_userrole_no_troducer"
down_revision: Union[str, None] = "2026_04_02_troducer_preintro"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match backend/app/models/models.py UserRole (no TRODUCER)
_USERROLE_VALUES_NO_TRODUCER = (
    "ADMIN",
    "MM",
    "INTRODUCER",
    "PRE_NDA",
    "PREINTRODUCER",
    "NDA",
    "REJECTED",
    "KYC",
    "APPROVED",
    "FUNDING",
    "AML",
    "CEA",
    "CEA_SETTLE",
    "SWAP",
    "EUA_SETTLE",
    "EUA",
)


def upgrade() -> None:
    literals = ", ".join(repr(v) for v in _USERROLE_VALUES_NO_TRODUCER)
    op.execute(
        """
        UPDATE users SET role = 'PREINTRODUCER'::userrole
        WHERE role::text = 'TRODUCER';
        """
    )
    op.execute(
        f"""
        CREATE TYPE userrole_new AS ENUM ({literals});
        """
    )
    op.execute(
        """
        ALTER TABLE users
          ALTER COLUMN role DROP DEFAULT,
          ALTER COLUMN role TYPE userrole_new
            USING (
              CASE role::text
                WHEN 'TRODUCER' THEN 'PREINTRODUCER'::userrole_new
                ELSE role::text::userrole_new
              END
            );
        """
    )
    op.execute("DROP TYPE userrole;")
    op.execute("ALTER TYPE userrole_new RENAME TO userrole;")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'NDA'::userrole;")


def downgrade() -> None:
    # Restoring the old enum with TRODUCER would require another full type swap;
    # no app code uses TRODUCER anymore.
    pass
