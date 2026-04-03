"""
Tests for POST /admin/users/create-preintroducer (Backoffice → Users → Pre-Introducer).

Run: docker compose exec backend pytest tests/test_create_preintroducer.py -v
"""

import os
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import RedisManager
from app.main import app
from app.models.models import ContactRequest, User, UserRole

ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "Admin123!")


async def _admin_login(client: httpx.AsyncClient) -> str:
    try:
        r = await RedisManager.get_redis()
        await r.delete("rate_limit:auth:127.0.0.1")
    except Exception:
        pass
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nihaogroup.com", "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_create_preintroducer_sends_nda_email_and_persists_user_and_contact_request():
    email = f"preintro-api-{uuid.uuid4().hex[:10]}@test-create-preintro.example.com"

    with patch(
        "app.api.v1.admin.get_document_bytes",
        new_callable=AsyncMock,
        return_value=(b"fake-nda-pdf", "nda.pdf"),
    ), patch(
        "app.api.v1.admin.email_service.send_introducer_nda_invitation",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_send:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            token = await _admin_login(client)
            resp = await client.post(
                "/api/v1/admin/users/create-preintroducer",
                params={
                    "email": email,
                    "first_name": "Pat",
                    "last_name": "AdminIntro",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["user"]["email"] == email.lower()
    assert data["user"]["role"] == "PREINTRODUCER"
    assert "contact_request_id" in data

    mock_send.assert_called_once()
    assert mock_send.call_args is not None
    assert mock_send.call_args.kwargs.get("nda_attachments") is not None

    async with AsyncSessionLocal() as db:
        u = (
            await db.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        assert u is not None
        assert u.role == UserRole.PREINTRODUCER
        assert u.nda_signed is False
        cr = (
            await db.execute(
                select(ContactRequest).where(ContactRequest.contact_email == email.lower())
            )
        ).scalar_one_or_none()
        assert cr is not None
        assert cr.request_flow == "introducer"
        await db.delete(cr)
        await db.delete(u)
        await db.commit()


@pytest.mark.asyncio
async def test_create_preintroducer_rolls_back_when_email_fails():
    email = f"preintro-fail-{uuid.uuid4().hex[:10]}@test-create-preintro.example.com"

    with patch(
        "app.api.v1.admin.get_document_bytes",
        new_callable=AsyncMock,
        return_value=(b"fake-nda-pdf", "nda.pdf"),
    ), patch(
        "app.api.v1.admin.email_service.send_introducer_nda_invitation",
        new_callable=AsyncMock,
        side_effect=RuntimeError("SMTP unavailable"),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            token = await _admin_login(client)
            resp = await client.post(
                "/api/v1/admin/users/create-preintroducer",
                params={
                    "email": email,
                    "first_name": "X",
                    "last_name": "Y",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 503, resp.text

    async with AsyncSessionLocal() as db:
        u = (
            await db.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        assert u is None
        cr = (
            await db.execute(
                select(ContactRequest).where(ContactRequest.contact_email == email.lower())
            )
        ).scalar_one_or_none()
        assert cr is None


@pytest.mark.asyncio
async def test_create_preintroducer_503_when_nda_pdf_fails():
    """NDA PDF generation failure returns 503 and does not persist a user."""
    email = f"preintro-pdf-{uuid.uuid4().hex[:10]}@test-create-preintro.example.com"

    with patch(
        "app.api.v1.admin.get_document_bytes",
        new_callable=AsyncMock,
        side_effect=OSError("nda generation failed"),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            token = await _admin_login(client)
            resp = await client.post(
                "/api/v1/admin/users/create-preintroducer",
                params={
                    "email": email,
                    "first_name": "A",
                    "last_name": "B",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 503, resp.text

    async with AsyncSessionLocal() as db:
        u = (
            await db.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        assert u is None
