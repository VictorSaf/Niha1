"""
Deposits API - AML Hold Management

Endpoints for deposit lifecycle:
- Client: Announce deposits, view status
- Admin: Confirm, clear, reject deposits

All deposit management routes with AML hold support.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_admin_user, get_approved_user
from ...models.models import Currency, DepositStatus, TicketStatus, User, UserRole
from ...schemas.schemas import MessageResponse
from ...services import deposit_service
from ...services.deposit_service import DepositNotFoundError, InvalidDepositStateError
from ...services.document_delivery_service import (
    DEPOSIT_ANNOUNCED_ATTACHMENTS,
    get_document_bytes,
)
from ...services.ticket_service import TicketService
from .backoffice import backoffice_ws_manager
from .client_ws import client_ws_manager
from ...services.ws_utils import get_entity_user_ids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deposits", tags=["Deposits"])


# ============== Pydantic Models for API ==============


class CurrencyEnum(str, Enum):
    EUR = "EUR"
    USD = "USD"
    CNY = "CNY"
    HKD = "HKD"


class HoldTypeEnum(str, Enum):
    FIRST_DEPOSIT = "FIRST_DEPOSIT"
    SUBSEQUENT = "SUBSEQUENT"
    LARGE_AMOUNT = "LARGE_AMOUNT"


class AMLStatusEnum(str, Enum):
    PENDING = "PENDING"
    ON_HOLD = "ON_HOLD"
    CLEARED = "CLEARED"
    REJECTED = "REJECTED"


class DepositStatusEnum(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ON_HOLD = "on_hold"
    CLEARED = "cleared"
    REJECTED = "rejected"


class RejectionReasonEnum(str, Enum):
    WIRE_NOT_RECEIVED = "WIRE_NOT_RECEIVED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    SOURCE_VERIFICATION_FAILED = "SOURCE_VERIFICATION_FAILED"
    AML_FLAG = "AML_FLAG"
    SANCTIONS_HIT = "SANCTIONS_HIT"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    OTHER = "OTHER"


class AnnounceDepositRequest(BaseModel):
    """Request to announce a wire transfer"""

    amount: Decimal = Field(..., gt=0, description="Amount being sent")
    currency: CurrencyEnum = Field(default=CurrencyEnum.EUR)
    source_bank: Optional[str] = Field(None, max_length=255)
    source_iban: Optional[str] = Field(None, max_length=50)
    source_swift: Optional[str] = Field(None, max_length=20)
    client_notes: Optional[str] = None


class ConfirmDepositRequest(BaseModel):
    """Admin request to confirm wire receipt"""

    actual_amount: Decimal = Field(..., gt=0, description="Actual amount received")
    actual_currency: CurrencyEnum = Field(default=CurrencyEnum.EUR)
    wire_reference: Optional[str] = Field(None, max_length=100)
    bank_reference: Optional[str] = Field(None, max_length=100)
    admin_notes: Optional[str] = None


class ClearDepositRequest(BaseModel):
    """Admin request to clear a deposit early"""

    admin_notes: Optional[str] = None
    force_clear: bool = Field(default=False, description="Clear before hold expires")


class RejectDepositRequest(BaseModel):
    """Admin request to reject a deposit"""

    reason: RejectionReasonEnum
    admin_notes: Optional[str] = None


class WireInstructionsResponse(BaseModel):
    """Bank wire instructions for client"""

    bank_name: str = "Niha Exchange Bank Partner"
    iban: str = "DE89 3704 0044 0532 0130 00"
    swift_bic: str = "COBADEFFXXX"
    beneficiary: str = "Niha Carbon Exchange Ltd"
    reference_format: str = "NIHA-{entity_code}-{date}"
    important_notes: List[str] = [
        "Include reference in wire transfer memo",
        "Wire from company bank account only",
        "Processing time: 1-3 business days after receipt",
    ]


class DepositDetailResponse(BaseModel):
    """Detailed deposit response"""

    id: str
    entity_id: str
    entity_name: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None

    # Reported by client
    reported_amount: Optional[float] = None
    reported_currency: Optional[str] = None
    source_bank: Optional[str] = None
    source_iban: Optional[str] = None
    source_swift: Optional[str] = None
    client_notes: Optional[str] = None

    # Confirmed by admin
    amount: Optional[float] = None
    currency: Optional[str] = None
    wire_reference: Optional[str] = None
    bank_reference: Optional[str] = None

    # Status
    status: str
    user_role: Optional[str] = None  # Reporting user's role (client status); FUNDING when announced
    aml_status: Optional[str] = None
    hold_type: Optional[str] = None
    hold_days_required: Optional[int] = None
    hold_expires_at: Optional[str] = None

    # Timestamps
    reported_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    cleared_at: Optional[str] = None
    rejected_at: Optional[str] = None

    # Audit trail
    confirmed_by: Optional[str] = None
    cleared_by: Optional[str] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    admin_notes: Optional[str] = None
    ticket_id: Optional[str] = None  # Ticket ID for the deposit announcement

    class Config:
        from_attributes = True


class DepositListResponse(BaseModel):
    """List of deposits with pagination"""

    deposits: List[DepositDetailResponse]
    total: int
    has_more: bool


class DepositStatsResponse(BaseModel):
    """Deposit statistics for dashboard"""

    pending_count: int
    on_hold_count: int
    on_hold_total: float
    cleared_count: int
    cleared_total: float
    rejected_count: int
    expired_holds_count: int


class HoldCalculationResponse(BaseModel):
    """Preview of hold period calculation"""

    hold_type: str
    hold_days: int
    estimated_release_date: str
    reason: str


# ============== Helper Functions ==============


def deposit_to_response(deposit, include_entity: bool = True, include_relations: bool = True) -> DepositDetailResponse:
    """Convert Deposit model to DepositDetailResponse. Sets user_role from deposit.user.role when present (client status; FUNDING when announced).

    Args:
        deposit: Deposit model instance
        include_entity: Include entity name in response
        include_relations: If False, skip all relationship access (avoids async lazy loading issues)
    """
    entity_name = None
    user_email = None
    user_role = None
    confirmed_by_name = None
    cleared_by_name = None
    rejected_by_name = None

    # Only access relationships if include_relations is True (they must be eager loaded)
    if include_relations:
        if include_entity and hasattr(deposit, "entity") and deposit.entity:
            entity_name = deposit.entity.name

        if hasattr(deposit, "user") and deposit.user:
            user_email = deposit.user.email
            user_role = deposit.user.role.value

        if hasattr(deposit, "confirmed_by_user") and deposit.confirmed_by_user:
            confirmed_by_name = deposit.confirmed_by_user.email

        if hasattr(deposit, "cleared_by_admin") and deposit.cleared_by_admin:
            cleared_by_name = deposit.cleared_by_admin.email

        if hasattr(deposit, "rejected_by_admin") and deposit.rejected_by_admin:
            rejected_by_name = deposit.rejected_by_admin.email

    return DepositDetailResponse(
        id=str(deposit.id),
        entity_id=str(deposit.entity_id),
        entity_name=entity_name,
        user_id=str(deposit.user_id) if deposit.user_id else None,
        user_email=user_email,
        reported_amount=float(deposit.reported_amount)
        if deposit.reported_amount
        else None,
        reported_currency=deposit.reported_currency.value
        if deposit.reported_currency
        else None,
        source_bank=deposit.source_bank,
        source_iban=deposit.source_iban,
        source_swift=deposit.source_swift,
        client_notes=deposit.client_notes,
        amount=float(deposit.amount) if deposit.amount else None,
        currency=deposit.currency.value if deposit.currency else None,
        wire_reference=deposit.wire_reference,
        bank_reference=deposit.bank_reference,
        status=deposit.status.value,
        user_role=user_role,
        aml_status=deposit.aml_status,
        hold_type=deposit.hold_type,
        hold_days_required=deposit.hold_days_required,
        hold_expires_at=deposit.hold_expires_at.isoformat() + "Z"
        if deposit.hold_expires_at
        else None,
        reported_at=deposit.reported_at.isoformat() + "Z"
        if deposit.reported_at
        else None,
        confirmed_at=deposit.confirmed_at.isoformat() + "Z"
        if deposit.confirmed_at
        else None,
        cleared_at=deposit.cleared_at.isoformat() + "Z" if deposit.cleared_at else None,
        rejected_at=deposit.rejected_at.isoformat() + "Z"
        if deposit.rejected_at
        else None,
        confirmed_by=confirmed_by_name,
        cleared_by=cleared_by_name,
        rejected_by=rejected_by_name,
        rejection_reason=deposit.rejection_reason,
        admin_notes=deposit.admin_notes,
        ticket_id=deposit.ticket_id,
    )


# ============== Client Endpoints ==============


@router.get("/wire-instructions", response_model=WireInstructionsResponse)
async def get_wire_instructions(current_user: User = Depends(get_approved_user)):  # noqa: B008
    """
    Get wire transfer instructions for the client.
    APPROVED, FUNDED, or ADMIN only (PENDING cannot access).
    """
    return WireInstructionsResponse()


@router.post("/announce", response_model=DepositDetailResponse)
async def announce_deposit(
    request: AnnounceDepositRequest,
    current_user: User = Depends(get_approved_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Announce a wire transfer deposit.

    Client calls this after initiating a wire transfer to notify
    the platform of the incoming funds. APPROVED, FUNDED, or ADMIN only.
    """
    if not current_user.entity_id:
        raise HTTPException(
            status_code=400,
            detail="User must be associated with an entity to make deposits",
        )

    deposit = await deposit_service.announce_deposit(
        db=db,
        entity_id=current_user.entity_id,
        user_id=current_user.id,
        reported_amount=request.amount,
        reported_currency=Currency(request.currency.value),
        source_bank=request.source_bank,
        source_iban=request.source_iban,
        source_swift=request.source_swift,
        client_notes=request.client_notes,
    )

    await db.commit()

    # Broadcast to backoffice
    await backoffice_ws_manager.broadcast(
        "deposit_announced",
        {
            "deposit_id": str(deposit.id),
            "entity_id": str(deposit.entity_id),
            "amount": float(request.amount),
            "currency": request.currency.value,
        },
    )

    # Deposit announcement confirmation email with funding docs (fire-and-forget)
    try:
        from ...services.email_service import email_service as _email_svc

        attachments = []
        for doc_id in DEPOSIT_ANNOUNCED_ATTACHMENTS:
            try:
                content, filename = await get_document_bytes(
                    doc_id, current_user, db, role_override=UserRole.FUNDING
                )
                attachments.append({"filename": filename, "content": content})
            except (ValueError, FileNotFoundError) as e:
                logger.warning(
                    "Could not attach %s to deposit_announced email for user %s: %s",
                    doc_id,
                    current_user.id,
                    e,
                )
        await _email_svc.send_deposit_announced(
            to_email=current_user.email,
            first_name=current_user.first_name or "Client",
            amount=float(request.amount),
            currency=request.currency.value,
            reference=request.source_bank or "",
            attachments=attachments if attachments else None,
        )
    except Exception:
        logger.debug("Deposit announced email failed for user %s", current_user.id)

    return deposit_to_response(deposit, include_entity=False, include_relations=False)


@router.get("/my-deposits", response_model=DepositListResponse)
async def get_my_deposits(
    status: Optional[DepositStatusEnum] = None,
    limit: int = Query(default=20, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    current_user: User = Depends(get_approved_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get deposits for the current user's entity. APPROVED, FUNDED, or ADMIN only.
    """
    if not current_user.entity_id:
        return DepositListResponse(deposits=[], total=0, has_more=False)

    status_filter = None
    if status:
        status_filter = DepositStatus(status.value)

    deposits = await deposit_service.get_entity_deposits(
        db=db,
        entity_id=current_user.entity_id,
        status=status_filter,
        limit=limit + 1,  # Get one extra to check has_more
        offset=offset,
    )

    has_more = len(deposits) > limit
    if has_more:
        deposits = deposits[:limit]

    return DepositListResponse(
        deposits=[deposit_to_response(d, include_entity=False) for d in deposits],
        total=len(deposits),
        has_more=has_more,
    )


@router.get("/preview-hold", response_model=HoldCalculationResponse)
async def preview_hold_period(
    amount: Decimal = Query(..., gt=0),  # noqa: B008
    current_user: User = Depends(get_approved_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Preview the hold period for a potential deposit.
    APPROVED, FUNDED, or ADMIN only.

    Helps clients understand how long their funds will be held
    before being available for trading.
    """
    if not current_user.entity_id:
        raise HTTPException(
            status_code=400, detail="User must be associated with an entity"
        )

    hold_type, hold_days = await deposit_service.calculate_hold_period(
        db=db, entity_id=current_user.entity_id, amount=amount
    )

    # Use naive UTC for date calculation
    release_date = deposit_service.calculate_business_days(datetime.now(timezone.utc).replace(tzinfo=None), hold_days)

    reasons = {
        "FIRST_DEPOSIT": "First deposit requires extended verification",
        "LARGE_AMOUNT": "Large deposits (>€500,000) require extended verification",
        "SUBSEQUENT": "Standard processing for established clients",
    }

    return HoldCalculationResponse(
        hold_type=hold_type.value,
        hold_days=hold_days,
        estimated_release_date=release_date.isoformat() + "Z",
        reason=reasons.get(hold_type.value, "Standard hold period"),
    )


# ============== Admin Endpoints ==============


@router.get("/pending", response_model=DepositListResponse)
async def get_pending_deposits(
    limit: int = Query(default=50, le=200),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all pending deposits awaiting confirmation.
    Admin only.
    """
    deposits = await deposit_service.get_pending_deposits(
        db=db, limit=limit + 1, offset=offset
    )

    has_more = len(deposits) > limit
    if has_more:
        deposits = deposits[:limit]

    return DepositListResponse(
        deposits=[deposit_to_response(d) for d in deposits],
        total=len(deposits),
        has_more=has_more,
    )


@router.get("/on-hold", response_model=DepositListResponse)
async def get_on_hold_deposits(
    include_expired: bool = Query(default=False),  # noqa: B008
    limit: int = Query(default=50, le=200),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get deposits currently on AML hold.
    Admin only.
    """
    deposits = await deposit_service.get_on_hold_deposits(
        db=db, include_expired=include_expired, limit=limit + 1, offset=offset
    )

    has_more = len(deposits) > limit
    if has_more:
        deposits = deposits[:limit]

    return DepositListResponse(
        deposits=[deposit_to_response(d) for d in deposits],
        total=len(deposits),
        has_more=has_more,
    )


@router.get("/stats", response_model=DepositStatsResponse)
async def get_deposit_stats(
    entity_id: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get deposit statistics for dashboard.
    Admin only.
    """
    entity_uuid = UUID(entity_id) if entity_id else None
    stats = await deposit_service.get_deposit_statistics(db, entity_uuid)
    return DepositStatsResponse(**stats)


@router.get("/{deposit_id}", response_model=DepositDetailResponse)
async def get_deposit(
    deposit_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get detailed deposit information.
    Admin only.
    """
    deposit = await deposit_service.get_deposit_by_id(db, UUID(deposit_id))

    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    return deposit_to_response(deposit)


@router.post("/{deposit_id}/confirm", response_model=DepositDetailResponse)
async def confirm_deposit(
    deposit_id: str,
    request: ConfirmDepositRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Confirm receipt of wire transfer and start AML hold.
    Admin only.

    This confirms the wire was received and calculates the hold period.
    The deposit transitions to ON_HOLD status.
    """
    try:
        deposit = await deposit_service.confirm_deposit(
            db=db,
            deposit_id=UUID(deposit_id),
            admin_id=admin_user.id,
            actual_amount=request.actual_amount,
            actual_currency=Currency(request.actual_currency.value),
            wire_reference=request.wire_reference,
            bank_reference=request.bank_reference,
            admin_notes=request.admin_notes,
        )

        # Create audit ticket for deposit confirmation
        ticket = await TicketService.create_ticket(
            db=db,
            action_type="DEPOSIT_CONFIRMED",
            entity_type="Deposit",
            entity_id=deposit.id,
            status=TicketStatus.SUCCESS,
            user_id=admin_user.id,
            request_payload={
                "deposit_id": deposit_id,
                "actual_amount": float(request.actual_amount),
                "actual_currency": request.actual_currency.value,
            },
            response_data={
                "status": deposit.status.value if deposit.status else "ON_HOLD",
                "hold_type": deposit.hold_type,
                "hold_expires_at": deposit.hold_expires_at.isoformat()
                if deposit.hold_expires_at
                else None,
            },
            tags=["deposit", "confirm", "admin"],
        )

        await db.commit()

        # Broadcast WebSocket event
        await backoffice_ws_manager.broadcast(
            "deposit_on_hold",
            {
                "deposit_id": str(deposit.id),
                "entity_id": str(deposit.entity_id),
                "amount": float(deposit.amount),
                "hold_type": deposit.hold_type,
                "ticket_id": ticket.ticket_id,
                "hold_expires_at": deposit.hold_expires_at.isoformat()
                if deposit.hold_expires_at
                else None,
            },
        )

        # Notify entity users so their funding page updates
        entity_user_ids = await get_entity_user_ids(db, deposit.entity_id)
        if entity_user_ids:
            asyncio.create_task(client_ws_manager.broadcast_to_users(
                entity_user_ids,
                {"type": "deposit_status_updated", "data": {"deposit_id": str(deposit.id), "status": "ON_HOLD"}},
            ))

        # Deposit on-hold email to entity users (fire-and-forget)
        try:
            from ...services.email_service import email_service as _email_svc
            _entity_users = await db.execute(
                select(User).where(User.entity_id == deposit.entity_id, User.is_active == True)  # noqa: E712
            )
            for _eu in _entity_users.scalars().all():
                if _eu.email:
                    await _email_svc.send_deposit_on_hold(
                        to_email=_eu.email,
                        first_name=_eu.first_name or "Client",
                        amount=float(deposit.confirmed_amount or deposit.amount),
                        currency="EUR",
                        hold_until=deposit.hold_expires_at.strftime("%Y-%m-%d") if deposit.hold_expires_at else "TBD",
                    )
        except Exception:
            logger.debug("Deposit on-hold email failed for deposit %s", deposit.id)

        # Reload with relationships
        deposit = await deposit_service.get_deposit_by_id(db, deposit.id)
        return deposit_to_response(deposit)

    except DepositNotFoundError as e:
        raise HTTPException(status_code=404, detail="Deposit not found") from e
    except InvalidDepositStateError as e:
        raise HTTPException(status_code=400, detail="Invalid request. Please check your input.") from e


@router.post("/{deposit_id}/clear", response_model=DepositDetailResponse)
async def clear_deposit(
    deposit_id: str,
    request: ClearDepositRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Clear deposit and credit funds to entity balance.
    Admin only.

    Can be called:
    - Automatically when hold expires
    - Manually with force_clear=True before hold expires
    """
    try:
        deposit, upgraded_user_ids = await deposit_service.clear_deposit(
            db=db,
            deposit_id=UUID(deposit_id),
            admin_id=admin_user.id,
            admin_notes=request.admin_notes,
            force_clear=request.force_clear,
        )

        # Create audit ticket for deposit clearing
        ticket = await TicketService.create_ticket(
            db=db,
            action_type="DEPOSIT_CLEARED",
            entity_type="Deposit",
            entity_id=deposit.id,
            status=TicketStatus.SUCCESS,
            user_id=admin_user.id,
            request_payload={
                "deposit_id": deposit_id,
                "force_clear": request.force_clear,
            },
            response_data={
                "amount": float(deposit.amount) if deposit.amount else 0,
                "currency": deposit.currency.value if deposit.currency else None,
                "upgraded_users": len(upgraded_user_ids),
            },
            tags=["deposit", "clear", "admin"],
        )

        await db.commit()

        # Reload with relationships for entity name
        deposit = await deposit_service.get_deposit_by_id(db, deposit.id)
        await backoffice_ws_manager.broadcast(
            "deposit_cleared",
            {
                "deposit_id": str(deposit.id),
                "entity_id": str(deposit.entity_id),
                "entity_name": deposit.entity.name if deposit.entity else None,
                "amount": float(deposit.amount) if deposit.amount else 0,
                "currency": deposit.currency.value if deposit.currency else None,
                "upgraded_users": len(upgraded_user_ids),
                "ticket_id": ticket.ticket_id,
            },
        )
        # Notify upgraded users (AML→CEA) so client can refetch /users/me and update UI
        if upgraded_user_ids:
            await client_ws_manager.broadcast_to_users(
                upgraded_user_ids,
                {"type": "role_updated", "data": {"role": "CEA", "entity_id": str(deposit.entity_id)}},
            )

        # Trading activated email to upgraded users AML→CEA (fire-and-forget)
        if upgraded_user_ids:
            try:
                from ...services.email_service import email_service as _email_svc
                _upgraded_users = await db.execute(
                    select(User).where(User.id.in_(upgraded_user_ids))
                )
                for _uu in _upgraded_users.scalars().all():
                    if _uu.email:
                        await _email_svc.send_trading_activated(
                            to_email=_uu.email,
                            first_name=_uu.first_name or "",
                            amount=float(deposit.amount) if deposit.amount else 0,
                            currency=deposit.currency.value if deposit.currency else "EUR",
                        )
            except Exception:
                logger.debug("Trading activated email failed for deposit %s", deposit.id)

        return deposit_to_response(deposit)

    except DepositNotFoundError as e:
        raise HTTPException(status_code=404, detail="Deposit not found") from e
    except InvalidDepositStateError as e:
        raise HTTPException(status_code=400, detail="Invalid request. Please check your input.") from e


@router.post("/{deposit_id}/reject", response_model=DepositDetailResponse)
async def reject_deposit(
    deposit_id: str,
    request: RejectDepositRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Reject a deposit for AML or other reasons.
    Admin only.
    """
    try:
        deposit = await deposit_service.reject_deposit(
            db=db,
            deposit_id=UUID(deposit_id),
            admin_id=admin_user.id,
            rejection_reason=request.reason.value,
            admin_notes=request.admin_notes,
        )

        await db.commit()

        # Broadcast WebSocket event
        await backoffice_ws_manager.broadcast(
            "deposit_rejected",
            {
                "deposit_id": str(deposit.id),
                "entity_id": str(deposit.entity_id),
                "reason": request.reason.value,
            },
        )

        # Notify entity users so their funding page updates
        entity_user_ids = await get_entity_user_ids(db, deposit.entity_id)
        if entity_user_ids:
            asyncio.create_task(client_ws_manager.broadcast_to_users(
                entity_user_ids,
                {"type": "deposit_status_updated", "data": {"deposit_id": str(deposit.id), "status": "REJECTED"}},
            ))

        # Deposit rejected email to entity users (fire-and-forget)
        try:
            from ...services.email_service import email_service as _email_svc
            _entity_users = await db.execute(
                select(User).where(User.entity_id == deposit.entity_id, User.is_active == True)  # noqa: E712
            )
            for _eu in _entity_users.scalars().all():
                if _eu.email:
                    await _email_svc.send_deposit_rejected(
                        to_email=_eu.email,
                        first_name=_eu.first_name or "Client",
                        amount=float(deposit.amount) if deposit.amount else 0,
                        currency=deposit.currency.value if deposit.currency else "EUR",
                        reason=request.reason.value,
                    )
        except Exception:
            logger.debug("Deposit rejected email failed for deposit %s", deposit.id)

        # Reload with relationships
        deposit = await deposit_service.get_deposit_by_id(db, deposit.id)
        return deposit_to_response(deposit)

    except DepositNotFoundError as e:
        raise HTTPException(status_code=404, detail="Deposit not found") from e
    except InvalidDepositStateError as e:
        raise HTTPException(status_code=400, detail="Invalid request. Please check your input.") from e


@router.post("/process-expired-holds", response_model=MessageResponse)
async def process_expired_holds(
    admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)  # noqa: B008
):
    """
    Manually trigger processing of expired holds.
    Admin only.

    This is normally done by a background job, but can be triggered
    manually for immediate processing.
    """
    cleared_count = await deposit_service.process_expired_holds(
        db=db, system_admin_id=admin_user.id
    )

    await db.commit()

    return MessageResponse(message=f"Processed {cleared_count} expired hold(s)")
