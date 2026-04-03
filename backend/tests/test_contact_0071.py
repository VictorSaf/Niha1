"""
Tests for feature 0071: PREINTRODUCER referral code flow (Login → NDA → code entry → introducer NDA invitation → INTRODUCER).

- validate_code: valid code, invalid code, rate limit 429
- create_introducer_nda_request: valid referral_code, no NDA file → INTRODUCER user created (NDA attached in email), introducer_nda_invitation sent with NDA attachment

Run: docker compose exec backend pytest tests/test_contact_0071.py -v
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import RedisManager
from app.main import app
from app.models.models import User
from app.services.referral_codes import get_unique_referral_code
from app.models.models import UserRole


_CODE_RATE_LIMIT = 5
_REDIS_KEY_PREFIX = "code_validation:"


async def _clear_code_validation_rate_limit():
    """Clear rate limit for typical test client IP so validate_code tests don't get 429."""
    try:
        r = await RedisManager.get_redis()
        for key in await r.keys(_REDIS_KEY_PREFIX + "*"):
            await r.delete(key)
    except Exception:
        pass


async def _create_preintroducer_with_referral_code() -> str:
    """Create a PREINTRODUCER user with a unique referral code. Returns the code (8 chars)."""
    async with AsyncSessionLocal() as db:
        code = await get_unique_referral_code(db)
        user = User(
            email=f"preintro-{code[:4]}@test0071.example.com",
            first_name="Test",
            last_name="PreIntro",
            role=UserRole.PREINTRODUCER,
            referral_code=code,
            is_active=True,
            nda_signed=True,
        )
        db.add(user)
        await db.commit()
        return code


@pytest.mark.asyncio
async def test_validate_code_valid():
    """POST /contact/validate-code with valid PREINTRODUCER code returns valid: true, type: preintroducer."""
    await _clear_code_validation_rate_limit()
    code = await _create_preintroducer_with_referral_code()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/contact/validate-code",
            data={"code": code},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    assert data.get("type") == "preintroducer"


@pytest.mark.asyncio
async def test_validate_code_invalid():
    """POST /contact/validate-code with invalid code returns valid: false."""
    await _clear_code_validation_rate_limit()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/contact/validate-code",
            data={"code": "INVALID1"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is False
    assert "type" not in data or data.get("type") is None


@pytest.mark.asyncio
async def test_validate_code_rate_limit_429():
    """After 5 requests, the 6th returns 429."""
    await _clear_code_validation_rate_limit()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for i in range(_CODE_RATE_LIMIT + 1):
            resp = await client.post(
                "/api/v1/contact/validate-code",
                data={"code": "RATELIM1"},
            )
            if i < _CODE_RATE_LIMIT:
                assert resp.status_code == 200, f"Request {i+1}: {resp.text}"
            else:
                assert resp.status_code == 429, f"Expected 429 on request {i+1}: {resp.text}"


@pytest.mark.asyncio
async def test_introducer_nda_request_creates_introducer_and_sends_email():
    """POST /contact/introducer-nda-request with valid referral_code, no NDA file:
    creates User INTRODUCER (NDA attached in email) and calls send_introducer_nda_invitation with nda_attachments.
    """
    await _clear_code_validation_rate_limit()
    code = await _create_preintroducer_with_referral_code()
    # Use unique email per run so duplicate check does not see leftover data from other tests
    contact_email = f"new-intro-0071-{code[:4]}@test0071.example.com"

    with patch(
        "app.api.v1.contact.get_document_bytes",
        new_callable=AsyncMock,
        return_value=(b"fake-nda-pdf", "nda.pdf"),
    ), patch(
        "app.api.v1.contact.email_service.send_introducer_nda_invitation",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_send:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                "/api/v1/contact/introducer-nda-request",
                data={
                    "entity_name": "Test Entity 0071",
                    "contact_email": contact_email,
                    "contact_first_name": "New",
                    "contact_last_name": "Intro",
                    "position": "",
                    "referral_code": code,
                    "request_flow": "introducer",
                },
            )
    assert resp.status_code == 200, resp.text

    # INTRODUCER user created (NDA sent attached in email)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == contact_email.lower())
        )
        user = result.scalar_one_or_none()
    assert user is not None, "Expected INTRODUCER user to be created"
    assert user.role == UserRole.INTRODUCER
    assert user.nda_signed is True
    assert user.invitation_token is not None

    # Email sent with NDA attachment
    mock_send.assert_called_once()
    # Positional: to_email, first_name, invitation_token
    assert mock_send.call_args[0][0] == contact_email.lower()
    call_kw = mock_send.call_args[1]
    assert call_kw.get("nda_attachments") is not None
    assert len(call_kw["nda_attachments"]) == 1
    assert call_kw["nda_attachments"][0]["filename"] == "nda.pdf"
    assert call_kw["nda_attachments"][0]["content"] == b"fake-nda-pdf"


@pytest.mark.asyncio
async def test_introducer_nda_request_503_when_nda_pdf_fails():
    """POST /contact/introducer-nda-request when get_document_bytes fails returns 503 and does not create user."""
    await _clear_code_validation_rate_limit()
    code = await _create_preintroducer_with_referral_code()
    contact_email = f"no-nda-pdf-0071-{code[:4]}@test0071.example.com"

    with patch(
        "app.api.v1.contact.get_document_bytes",
        new_callable=AsyncMock,
        side_effect=Exception("NDA generation failed"),
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                "/api/v1/contact/introducer-nda-request",
                data={
                    "entity_name": "Test",
                    "contact_email": contact_email,
                    "contact_first_name": "No",
                    "contact_last_name": "Pdf",
                    "position": "",
                    "referral_code": code,
                    "request_flow": "introducer",
                },
            )
    assert resp.status_code == 503, resp.text
    assert "Unable to prepare invitation" in (resp.json().get("detail") or "")

    # User must not exist
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == contact_email.lower())
        )
        user = result.scalar_one_or_none()
    assert user is None, "User must not be created when NDA PDF generation fails"


@pytest.mark.asyncio
async def test_introducer_nda_request_duplicate_email_409():
    """POST /contact/introducer-nda-request with same email twice (valid referral, no NDA): second returns 409."""
    await _clear_code_validation_rate_limit()
    code = await _create_preintroducer_with_referral_code()
    # Unique email per run so first request always succeeds
    contact_email = f"dup-0071-{code[:4]}@test0071.example.com"

    with patch(
        "app.api.v1.contact.get_document_bytes",
        new_callable=AsyncMock,
        return_value=(b"fake-nda-pdf", "nda.pdf"),
    ), patch(
        "app.api.v1.contact.email_service.send_introducer_nda_invitation",
        new_callable=AsyncMock,
        return_value=True,
    ):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp1 = await client.post(
                "/api/v1/contact/introducer-nda-request",
                data={
                    "entity_name": "Dup",
                    "contact_email": contact_email,
                    "contact_first_name": "First",
                    "contact_last_name": "Submit",
                    "position": "",
                    "referral_code": code,
                    "request_flow": "introducer",
                },
            )
    assert resp1.status_code == 200, resp1.text

    # Second request with same email but new referral code: should get 409 (user already exists)
    code2 = await _create_preintroducer_with_referral_code()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp2 = await client.post(
            "/api/v1/contact/introducer-nda-request",
            data={
                "entity_name": "Dup",
                "contact_email": contact_email,
                "contact_first_name": "Second",
                "contact_last_name": "Submit",
                "position": "",
                "referral_code": code2,
                "request_flow": "introducer",
            },
        )
    assert resp2.status_code == 409, resp2.text
    assert "already exists" in (resp2.json().get("detail") or "").lower()
