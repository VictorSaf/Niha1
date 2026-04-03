"""Referral code generation, validation, and consumption."""

import secrets
import string
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.models import User, UserRole

# Code alphabet: uppercase + lowercase + digits + specials
_ALPHA = string.ascii_letters + string.digits
_SPECIALS = "$!@"
_CODE_LENGTH = 8


def generate_referral_code() -> str:
    """Generate an 8-char code with at least one special character."""
    while True:
        # Generate 7 alphanumeric chars + 1 forced special
        base = [secrets.choice(_ALPHA) for _ in range(_CODE_LENGTH - 1)]
        base.append(secrets.choice(_SPECIALS))
        # Shuffle to randomize special char position
        code_chars = list(base)
        secrets.SystemRandom().shuffle(code_chars)
        return "".join(code_chars)


async def get_unique_referral_code(db: AsyncSession) -> str:
    """Generate a referral code that doesn't collide with existing ones."""
    for _ in range(10):
        code = generate_referral_code()
        result = await db.execute(
            select(User.id).where(User.referral_code == code)
        )
        if result.scalar_one_or_none() is None:
            return code
    raise RuntimeError("Failed to generate unique referral code after 10 attempts")


async def validate_referral_code(
    db: AsyncSession, code: str
) -> dict | None:
    """
    Validate a referral code.
    Returns { user_id, type: 'preintroducer' | 'introducer' } or None if invalid.
    """
    result = await db.execute(
        select(User).where(
            User.referral_code == code,
            User.is_active.is_(True),
            User.role.in_([UserRole.PREINTRODUCER, UserRole.INTRODUCER]),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return None

    role_to_type = {
        UserRole.PREINTRODUCER: "preintroducer",
        UserRole.INTRODUCER: "introducer",
    }
    return {"user_id": user.id, "type": role_to_type[user.role]}


async def consume_referral_code(db: AsyncSession, code: str) -> UUID | None:
    """
    Consume a referral code: return the owner's user_id and regenerate their code.
    Uses FOR UPDATE row lock to prevent concurrent consumption of the same code.
    Returns the owner's user_id, or None if code invalid/already consumed.
    """
    result = await db.execute(
        select(User)
        .where(
            User.referral_code == code,
            User.is_active.is_(True),
            User.role.in_([UserRole.PREINTRODUCER, UserRole.INTRODUCER]),
        )
        .with_for_update()
    )
    user = result.scalar_one_or_none()
    if not user:
        return None

    owner_id = user.id
    # All roles: regenerate code for next referral
    user.referral_code = await get_unique_referral_code(db)
    # Don't commit here -- caller manages the transaction
    return owner_id
