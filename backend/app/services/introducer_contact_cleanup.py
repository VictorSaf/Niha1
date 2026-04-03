"""Remove orphan introducer-flow contact requests (no linked PREINTRODUCER/INTRODUCER user).

Backoffice Introducer tab lists `contact_requests` with `request_flow='introducer'`.
Deleting a user row (e.g. maintenance SQL) does not cascade to contact requests; this
reconciler deletes rows whose `contact_email` has no user with role PREINTRODUCER or INTRODUCER.

Note: If user creation failed after the contact row was committed, the row may also be removed;
re-submit the introducer application in that rare case.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, exists, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.models import ContactRequest, User, UserRole

logger = logging.getLogger(__name__)


async def reconcile_orphan_introducer_contact_requests(db: AsyncSession) -> int:
    """
    Delete introducer contact requests with no matching introducer user.

    Returns the number of rows deleted (SQLAlchemy 2 rowcount).
    """
    has_introducer_user = (
        select(literal(1))
        .select_from(User)
        .where(
            func.lower(User.email) == func.lower(ContactRequest.contact_email),
            User.role.in_([UserRole.PREINTRODUCER, UserRole.INTRODUCER]),
        )
    )
    stmt = delete(ContactRequest).where(
        ContactRequest.request_flow == "introducer",
        ~exists(has_introducer_user),
    )
    result = await db.execute(stmt)
    deleted = result.rowcount
    if deleted:
        logger.info(
            "Reconciled orphan introducer contact requests: deleted=%s", deleted
        )
    return int(deleted or 0)
