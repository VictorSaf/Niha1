"""Tests for introducer contact request orphan reconciliation (feature 0073)."""

import uuid

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.models import ContactRequest, ContactStatus, User, UserRole
from app.services.introducer_contact_cleanup import (
    reconcile_orphan_introducer_contact_requests,
)
from app.services.referral_codes import get_unique_referral_code


@pytest.mark.asyncio
async def test_reconcile_deletes_introducer_request_without_matching_user():
    email = f"orphan-{uuid.uuid4().hex[:8]}@test-intro-cleanup.example.com"
    async with AsyncSessionLocal() as db:
        cr = ContactRequest(
            entity_name="Orphan Co",
            contact_email=email,
            contact_first_name="O",
            contact_last_name="R",
            position="Test",
            user_role=ContactStatus.NDA,
            request_flow="introducer",
        )
        db.add(cr)
        await db.commit()
        req_id = cr.id

    async with AsyncSessionLocal() as db:
        n = await reconcile_orphan_introducer_contact_requests(db)
        await db.commit()
        assert n >= 1

    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(ContactRequest).where(ContactRequest.id == req_id)
        )
        assert row.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_reconcile_keeps_introducer_request_when_preintroducer_exists():
    email = f"kept-{uuid.uuid4().hex[:8]}@test-intro-cleanup.example.com"
    async with AsyncSessionLocal() as db:
        code = await get_unique_referral_code(db)
        u = User(
            email=email,
            first_name="K",
            last_name="T",
            role=UserRole.PREINTRODUCER,
            referral_code=code,
            is_active=True,
            nda_signed=False,
        )
        db.add(u)
        cr = ContactRequest(
            entity_name="Kept Co",
            contact_email=email,
            contact_first_name="K",
            contact_last_name="T",
            position="Test",
            user_role=ContactStatus.NDA,
            request_flow="introducer",
        )
        db.add(cr)
        await db.commit()
        req_id = cr.id

    async with AsyncSessionLocal() as db:
        n = await reconcile_orphan_introducer_contact_requests(db)
        await db.commit()
        assert n == 0

    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(ContactRequest).where(ContactRequest.id == req_id)
        )
        assert row.scalar_one_or_none() is not None

    # cleanup
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(ContactRequest).where(ContactRequest.id == req_id))
        c = r.scalar_one()
        await db.delete(c)
        r2 = await db.execute(select(User).where(User.email == email))
        u2 = r2.scalar_one()
        await db.delete(u2)
        await db.commit()
