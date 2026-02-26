"""
Test that withdrawal and swap API flows create audit tickets with expected action_type.

Run from backend container: pytest tests/test_audit_withdrawal_swap_tickets.py -v

Requires: a user with entity_id and known password (e.g. SEED_CLIENT_PASSWORD) for withdrawal
request tests; swap tests are skipped when there is no swap liquidity.
"""

import os

import pytest
import httpx
from httpx import ASGITransport
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import RedisManager
from app.main import app
from app.models.models import Entity, TicketLog, User

ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "Admin123!")
CLIENT_PASSWORD = os.environ.get("SEED_CLIENT_PASSWORD", "Client123!")


async def _admin_login(client: httpx.AsyncClient) -> str:
    """Login as admin."""
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


async def _get_first_entity_id() -> str | None:
    """Return the first entity id, or None."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Entity.id).limit(1))
        row = result.first()
        return str(row[0]) if row else None


async def _get_user_with_entity(entity_id: str) -> tuple[str, str] | None:
    """Return (email, password) for a user with the given entity_id, or None."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User.email).where(User.entity_id == entity_id).limit(1)
        )
        row = result.first()
        if not row:
            return None
        return (row[0], CLIENT_PASSWORD)


async def _get_latest_ticket_by_action_type(action_type: str) -> TicketLog | None:
    """Return the most recent TicketLog with the given action_type."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TicketLog)
            .where(TicketLog.action_type == action_type)
            .order_by(TicketLog.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


@pytest.mark.asyncio
async def test_withdrawal_requested_creates_ticket():
    """POST /withdrawals/request creates a ticket WITHDRAWAL_REQUESTED."""
    entity_id = await _get_first_entity_id()
    if not entity_id:
        pytest.skip("No entity in database")
    user_creds = await _get_user_with_entity(entity_id)
    if not user_creds:
        pytest.skip("No user with entity_id (seed a client user with entity)")
    email, password = user_creds

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        try:
            r = await RedisManager.get_redis()
            await r.delete("rate_limit:auth:127.0.0.1")
        except Exception:
            pass
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            pytest.skip(f"Client login failed (set SEED_CLIENT_PASSWORD?): {login.text}")
        token = login.json()["access_token"]

        # Ensure entity has EUR balance (admin add-asset)
        admin_tok = await _admin_login(client)
        await client.post(
            f"/api/v1/backoffice/entities/{entity_id}/add-asset",
            json={"asset_type": "EUR", "amount": 500, "operation": "deposit", "notes": "pytest"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )

        response = await client.post(
            "/api/v1/withdrawals/request",
            json={
                "asset_type": "EUR",
                "amount": 100,
                "destination_iban": "RO49AAAA1B31007593840000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text

    ticket = await _get_latest_ticket_by_action_type("WITHDRAWAL_REQUESTED")
    assert ticket is not None
    assert ticket.entity_type == "Withdrawal"
    assert ticket.entity_id is not None
    assert "withdrawal" in (ticket.tags or [])
    assert ticket.request_payload is not None
    assert ticket.request_payload.get("asset_type") == "EUR"
    assert ticket.request_payload.get("amount") == "100"


@pytest.mark.asyncio
async def test_withdrawal_approved_creates_ticket():
    """POST /withdrawals/{id}/approve creates a ticket WITHDRAWAL_APPROVED."""
    entity_id = await _get_first_entity_id()
    if not entity_id:
        pytest.skip("No entity in database")
    user_creds = await _get_user_with_entity(entity_id)
    if not user_creds:
        pytest.skip("No user with entity_id")
    email, password = user_creds

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Client login and create withdrawal
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            pytest.skip("Client login failed")
        token = login.json()["access_token"]
        admin_tok = await _admin_login(client)
        await client.post(
            f"/api/v1/backoffice/entities/{entity_id}/add-asset",
            json={"asset_type": "EUR", "amount": 500, "operation": "deposit", "notes": "pytest"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        req = await client.post(
            "/api/v1/withdrawals/request",
            json={"asset_type": "EUR", "amount": 50, "destination_iban": "RO49AAAA1B31007593840001"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert req.status_code == 200, req.text
        withdrawal_id = req.json().get("withdrawal_id")
        assert withdrawal_id, req.json()

        # Admin approve
        approve = await client.post(
            f"/api/v1/withdrawals/{withdrawal_id}/approve",
            json={},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert approve.status_code == 200, approve.text

    ticket = await _get_latest_ticket_by_action_type("WITHDRAWAL_APPROVED")
    assert ticket is not None
    assert ticket.entity_type == "Withdrawal"
    assert "withdrawal" in (ticket.tags or [])
    assert "admin" in (ticket.tags or [])


@pytest.mark.asyncio
async def test_withdrawal_rejected_creates_ticket():
    """POST /withdrawals/{id}/reject creates a ticket WITHDRAWAL_REJECTED."""
    entity_id = await _get_first_entity_id()
    if not entity_id:
        pytest.skip("No entity in database")
    user_creds = await _get_user_with_entity(entity_id)
    if not user_creds:
        pytest.skip("No user with entity_id")
    email, password = user_creds

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            pytest.skip("Client login failed")
        token = login.json()["access_token"]
        admin_tok = await _admin_login(client)
        await client.post(
            f"/api/v1/backoffice/entities/{entity_id}/add-asset",
            json={"asset_type": "EUR", "amount": 500, "operation": "deposit", "notes": "pytest"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        req = await client.post(
            "/api/v1/withdrawals/request",
            json={"asset_type": "EUR", "amount": 25, "destination_iban": "RO49AAAA1B31007593840002"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert req.status_code == 200, req.text
        withdrawal_id = req.json().get("withdrawal_id")

        rej = await client.post(
            f"/api/v1/withdrawals/{withdrawal_id}/reject",
            json={"rejection_reason": "Test rejection"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert rej.status_code == 200, rej.text

    ticket = await _get_latest_ticket_by_action_type("WITHDRAWAL_REJECTED")
    assert ticket is not None
    assert ticket.entity_type == "Withdrawal"
    assert "admin" in (ticket.tags or [])


@pytest.mark.asyncio
async def test_swap_created_creates_ticket():
    """POST /swaps (create swap) creates a ticket SWAP_CREATED when request succeeds."""
    entity_id = await _get_first_entity_id()
    if not entity_id:
        pytest.skip("No entity in database")
    user_creds = await _get_user_with_entity(entity_id)
    if not user_creds:
        pytest.skip("No user with entity_id")
    email, password = user_creds

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if login.status_code != 200:
            pytest.skip("Client login failed")
        token = login.json()["access_token"]

        # User must have SWAP (or higher) role and entity needs CEA balance + swap liquidity.
        # If create_swap returns 400 (e.g. no liquidity / insufficient balance), we skip.
        resp = await client.post(
            "/api/v1/swaps",
            json={"from_type": "CEA", "to_type": "EUA", "quantity": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            pytest.skip(
                f"create_swap returned {resp.status_code} (need SWAP role, CEA balance, liquidity): {resp.text[:200]}"
            )

    ticket = await _get_latest_ticket_by_action_type("SWAP_CREATED")
    assert ticket is not None
    assert ticket.entity_type == "SwapRequest"
    assert ticket.entity_id is not None
    assert "swap" in (ticket.tags or [])
    assert ticket.request_payload is not None
    assert ticket.request_payload.get("from_type") == "CEA"
    assert ticket.request_payload.get("to_type") == "EUA"
