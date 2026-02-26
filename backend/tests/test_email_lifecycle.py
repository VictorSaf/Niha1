"""
Smoke tests for all EmailService methods.
Mocks _send_email so nothing is actually sent — verifies every template
renders without errors and calls _send_email with the expected subject/recipient.

Run: docker compose exec backend pytest tests/test_email_lifecycle.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import EmailService, email_service


@pytest.fixture
def svc():
    """Fresh EmailService instance with sending disabled."""
    service = EmailService()
    service.enabled = False  # safety net
    return service


@pytest.fixture
def mock_send():
    """Patch _send_email to always return True."""
    with patch.object(EmailService, "_send_email", new_callable=AsyncMock, return_value=True) as m:
        yield m


# ── Auth ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_magic_link(svc, mock_send):
    result = await svc.send_magic_link("user@test.com", "tok123")
    assert result is True
    mock_send.assert_called_once()
    assert "user@test.com" in str(mock_send.call_args)


# ── Trading ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_trade_confirmation(svc, mock_send):
    result = await svc.send_trade_confirmation(
        to_email="user@test.com",
        trade_type="BUY",
        certificate_type="CEA",
        quantity=100.0,
        price=7.50,
        total=750.0,
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_swap_match_notification(svc, mock_send):
    result = await svc.send_swap_match_notification(
        to_email="user@test.com",
        from_type="CEA",
        to_type="EUA",
        quantity=500.0,
        rate=0.1177,
    )
    assert result is True
    mock_send.assert_called_once()


# ── Onboarding ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_invitation(svc, mock_send):
    result = await svc.send_invitation(
        to_email="new@test.com",
        first_name="Alice",
        invitation_token="inv-abc",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_account_approved(svc, mock_send):
    result = await svc.send_account_approved("user@test.com", "Bob")
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_kyc_rejected(svc, mock_send):
    result = await svc.send_kyc_rejected(
        to_email="user@test.com",
        first_name="Charlie",
        reason="Documents expired",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_account_funded(svc, mock_send):
    result = await svc.send_account_funded("user@test.com", "Dana")
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_contact_followup(svc, mock_send):
    result = await svc.send_contact_followup("user@test.com", "Acme Corp")
    assert result is True
    mock_send.assert_called_once()


# ── Deposits ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_deposit_announced(svc, mock_send):
    result = await svc.send_deposit_announced(
        to_email="user@test.com",
        first_name="Eve",
        amount=50000.0,
        currency="EUR",
        reference="DEP-2026-001",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_deposit_on_hold(svc, mock_send):
    result = await svc.send_deposit_on_hold(
        to_email="user@test.com",
        first_name="Frank",
        amount=100000.0,
        currency="EUR",
        hold_until="2026-02-15",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_deposit_cleared(svc, mock_send):
    result = await svc.send_deposit_cleared(
        to_email="user@test.com",
        first_name="Grace",
        amount=75000.0,
        currency="EUR",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_deposit_rejected(svc, mock_send):
    result = await svc.send_deposit_rejected(
        to_email="user@test.com",
        first_name="Hank",
        amount=25000.0,
        currency="EUR",
        reason="WIRE_NOT_RECEIVED",
    )
    assert result is True
    mock_send.assert_called_once()


# ── Settlements ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_settlement_created(svc, mock_send):
    result = await svc.send_settlement_created(
        to_email="user@test.com",
        first_name="Ivan",
        batch_reference="STTL-2026-001",
        certificate_type="CEA",
        quantity=200.0,
        expected_date="2026-02-12",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_settlement_status_update(svc, mock_send):
    result = await svc.send_settlement_status_update(
        to_email="user@test.com",
        first_name="Julia",
        batch_reference="STTL-2026-002",
        old_status="PENDING",
        new_status="TRANSFER_INITIATED",
        certificate_type="EUA",
        quantity=1000.0,
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_settlement_completed(svc, mock_send):
    result = await svc.send_settlement_completed(
        to_email="user@test.com",
        first_name="Karl",
        batch_reference="STTL-2026-003",
        certificate_type="CEA",
        quantity=500.0,
        new_balance=1500.0,
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_settlement_failed(svc, mock_send):
    result = await svc.send_settlement_failed(
        to_email="user@test.com",
        first_name="Leo",
        batch_reference="STTL-2026-004",
        certificate_type="EUA",
        quantity=300.0,
        reason="Registry timeout",
    )
    assert result is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_admin_overdue_settlement_alert(svc, mock_send):
    result = await svc.send_admin_overdue_settlement_alert(
        to_email="admin@nihaogroup.com",
        batch_reference="STTL-2026-005",
        entity_name="Carbon Fund LLC",
        certificate_type="CEA",
        quantity=750.0,
        expected_date="2026-02-01",
        days_overdue=7,
        current_status="IN_TRANSIT",
    )
    assert result is True
    mock_send.assert_called_once()


# ── Template usage (used vs NU) ─────────────────────────────────

def test_list_templates_with_usage_deposit_cleared_not_used():
    """deposit_cleared.html is not sent from any app flow; must be reported as not used."""
    with_usage = email_service.list_templates_with_usage()
    deposit_cleared = next((t for t in with_usage if t["name"] == "deposit_cleared.html"), None)
    assert deposit_cleared is not None
    assert deposit_cleared["used"] is False


def test_list_templates_with_usage_every_template_classified():
    """Every template file is either in USED or UNUSED; no drift between code and constants."""
    used = email_service.USED_EMAIL_TEMPLATES
    unused = email_service.UNUSED_EMAIL_TEMPLATES
    assert used.isdisjoint(unused), "USED and UNUSED must not overlap"
    all_names = set(email_service.list_templates())
    for name in all_names:
        assert name in used or name in unused, (
            f"Template {name} must be in USED_EMAIL_TEMPLATES or UNUSED_EMAIL_TEMPLATES"
        )
    assert all_names == used | unused, "Every template must be classified as used or unused"
