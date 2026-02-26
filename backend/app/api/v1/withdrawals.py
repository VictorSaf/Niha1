"""
Withdrawals API Endpoints

Provides endpoints for:
- Client: Request withdrawals, view history
- Admin: Review, approve, complete, reject withdrawals
"""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_admin_user, get_current_user
from ...models.models import AssetType, TicketStatus, User, Withdrawal
from ...services import withdrawal_service
from ...services.ticket_service import TicketService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/withdrawals", tags=["withdrawals"])


# =============================================================================
# Pydantic Models
# =============================================================================


class WithdrawalRequest(BaseModel):
    """Request model for withdrawal"""

    asset_type: str = Field(..., description="Asset type: EUR, CEA, or EUA")
    amount: Decimal = Field(..., gt=0, description="Amount to withdraw")
    # EUR specific
    destination_bank: Optional[str] = None
    destination_iban: Optional[str] = None
    destination_swift: Optional[str] = None
    destination_account_holder: Optional[str] = None
    # CEA/EUA specific
    destination_registry: Optional[str] = None
    destination_account_id: Optional[str] = None
    client_notes: Optional[str] = None


class ApproveWithdrawalRequest(BaseModel):
    """Admin approval request"""

    admin_notes: Optional[str] = None


class CompleteWithdrawalRequest(BaseModel):
    """Admin completion request"""

    wire_reference: Optional[str] = None
    admin_notes: Optional[str] = None


class RejectWithdrawalRequest(BaseModel):
    """Admin rejection request"""

    rejection_reason: str = Field(..., min_length=1, description="Reason for rejection")
    admin_notes: Optional[str] = None


class WithdrawalResponse(BaseModel):
    """Response model for withdrawal operations"""

    success: bool
    withdrawal_id: Optional[str] = None
    internal_reference: Optional[str] = None
    amount: Optional[str] = None
    asset_type: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Client Endpoints
# =============================================================================


@router.post("/request", response_model=WithdrawalResponse)
async def request_withdrawal(
    request: WithdrawalRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Request a withdrawal.

    For EUR: Requires destination_iban (bank details optional but recommended)
    For CEA/EUA: Requires destination_registry and destination_account_id
    """
    if not current_user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with an entity to request withdrawals",
        )

    # Validate asset type
    try:
        asset_type = AssetType(request.asset_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid asset type. Must be one of: EUR, CEA, EUA",
        ) from e

    result = await withdrawal_service.request_withdrawal(
        db=db,
        entity_id=current_user.entity_id,
        user_id=current_user.id,
        asset_type=asset_type,
        amount=request.amount,
        destination_bank=request.destination_bank,
        destination_iban=request.destination_iban,
        destination_swift=request.destination_swift,
        destination_account_holder=request.destination_account_holder,
        destination_registry=request.destination_registry,
        destination_account_id=request.destination_account_id,
        client_notes=request.client_notes,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to create withdrawal request"),
        )

    def _mask_destination(s: Optional[str]) -> Optional[str]:
        if not s or len(s) < 4:
            return "****" if s else None
        return s[:4] + "****"

    await TicketService.create_ticket(
        db=db,
        action_type="WITHDRAWAL_REQUESTED",
        entity_type="Withdrawal",
        entity_id=UUID(result["withdrawal_id"]),
        status=TicketStatus.SUCCESS,
        user_id=current_user.id,
        request_payload={
            "asset_type": request.asset_type,
            "amount": str(request.amount),
            "destination_iban": _mask_destination(request.destination_iban),
            "destination_registry": request.destination_registry,
            "destination_account_id": _mask_destination(request.destination_account_id),
        },
        response_data={
            "internal_reference": result.get("internal_reference"),
            "status": result.get("status"),
        },
        tags=["withdrawal", "client"],
    )
    await db.commit()

    # Withdrawal confirmation email (fire-and-forget)
    try:
        from ...services.email_service import email_service as _email_svc
        await _email_svc.send_withdrawal_requested(
            to_email=current_user.email,
            first_name=current_user.first_name or "",
            amount=float(request.amount),
            currency=request.asset_type,
        )
    except Exception:
        logger.debug("Withdrawal request email failed for user %s", current_user.id)

    return result


@router.get("/my-withdrawals")
async def get_my_withdrawals(
    current_user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Get withdrawal history for current user's entity"""
    if not current_user.entity_id:
        return []

    withdrawals = await withdrawal_service.get_entity_withdrawals(
        db=db,
        entity_id=current_user.entity_id,
    )
    return withdrawals


# =============================================================================
# Admin Endpoints
# =============================================================================


@router.get("/pending")
async def get_pending_withdrawals(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Get all pending withdrawal requests (admin only)"""
    return await withdrawal_service.get_pending_withdrawals(db)


@router.get("/processing")
async def get_processing_withdrawals(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Get all withdrawals currently being processed (admin only)"""
    return await withdrawal_service.get_processing_withdrawals(db)


@router.get("/stats")
async def get_withdrawal_stats(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Get withdrawal statistics (admin only)"""
    return await withdrawal_service.get_withdrawal_stats(db)


@router.post("/{withdrawal_id}/approve", response_model=WithdrawalResponse)
async def approve_withdrawal(
    withdrawal_id: UUID,
    request: ApproveWithdrawalRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Approve a pending withdrawal and move to processing (admin only)"""
    result = await withdrawal_service.approve_withdrawal(
        db=db,
        withdrawal_id=withdrawal_id,
        admin_id=admin_user.id,
        admin_notes=request.admin_notes,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to approve withdrawal"),
        )

    w = (await db.execute(select(Withdrawal).where(Withdrawal.id == withdrawal_id))).scalar_one_or_none()
    await TicketService.create_ticket(
        db=db,
        action_type="WITHDRAWAL_APPROVED",
        entity_type="Withdrawal",
        entity_id=withdrawal_id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        request_payload={"admin_notes": request.admin_notes},
        response_data={
            **result,
            "amount": str(w.amount) if w else None,
            "asset_type": w.asset_type.value if w else None,
        },
        tags=["withdrawal", "admin"],
    )
    await db.commit()

    # Withdrawal approved email (fire-and-forget)
    if result.get("success"):
        try:
            from sqlalchemy import select as _sel
            from ...services.email_service import email_service as _email_svc
            w = (await db.execute(_sel(Withdrawal).where(Withdrawal.id == withdrawal_id))).scalar_one_or_none()
            if w:
                u = (await db.execute(_sel(User).where(User.entity_id == w.entity_id))).scalars().first()
                if u:
                    await _email_svc.send_withdrawal_approved(
                        to_email=u.email, first_name=u.first_name or "",
                        amount=float(w.amount), currency=w.asset_type.value if w.asset_type else "EUR",
                    )
        except Exception:
            logger.debug("Withdrawal approved email failed for %s", withdrawal_id)

    return result


@router.post("/{withdrawal_id}/complete", response_model=WithdrawalResponse)
async def complete_withdrawal(
    withdrawal_id: UUID,
    request: CompleteWithdrawalRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Complete a withdrawal (mark as transferred) (admin only)"""
    result = await withdrawal_service.complete_withdrawal(
        db=db,
        withdrawal_id=withdrawal_id,
        admin_id=admin_user.id,
        wire_reference=request.wire_reference,
        admin_notes=request.admin_notes,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to complete withdrawal"),
        )

    w = (await db.execute(select(Withdrawal).where(Withdrawal.id == withdrawal_id))).scalar_one_or_none()
    await TicketService.create_ticket(
        db=db,
        action_type="WITHDRAWAL_COMPLETED",
        entity_type="Withdrawal",
        entity_id=withdrawal_id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        request_payload={
            "wire_reference": request.wire_reference,
            "admin_notes": request.admin_notes,
        },
        response_data={
            **result,
            "amount": str(w.amount) if w else None,
            "asset_type": w.asset_type.value if w else None,
        },
        tags=["withdrawal", "admin"],
    )
    await db.commit()

    # Withdrawal completed email (fire-and-forget)
    if result.get("success"):
        try:
            from sqlalchemy import select as _sel
            from ...services.email_service import email_service as _email_svc
            w = (await db.execute(_sel(Withdrawal).where(Withdrawal.id == withdrawal_id))).scalar_one_or_none()
            if w:
                u = (await db.execute(_sel(User).where(User.entity_id == w.entity_id))).scalars().first()
                if u:
                    await _email_svc.send_withdrawal_completed(
                        to_email=u.email, first_name=u.first_name or "",
                        amount=float(w.amount), currency=w.asset_type.value if w.asset_type else "EUR",
                        wire_reference=request.wire_reference or "",
                    )
        except Exception:
            logger.debug("Withdrawal completed email failed for %s", withdrawal_id)

    return result


@router.post("/{withdrawal_id}/reject", response_model=WithdrawalResponse)
async def reject_withdrawal(
    withdrawal_id: UUID,
    request: RejectWithdrawalRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Reject a withdrawal and refund the reserved balance (admin only)"""
    result = await withdrawal_service.reject_withdrawal(
        db=db,
        withdrawal_id=withdrawal_id,
        admin_id=admin_user.id,
        rejection_reason=request.rejection_reason,
        admin_notes=request.admin_notes,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to reject withdrawal"),
        )

    w = (await db.execute(select(Withdrawal).where(Withdrawal.id == withdrawal_id))).scalar_one_or_none()
    await TicketService.create_ticket(
        db=db,
        action_type="WITHDRAWAL_REJECTED",
        entity_type="Withdrawal",
        entity_id=withdrawal_id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        request_payload={
            "rejection_reason": request.rejection_reason,
            "admin_notes": request.admin_notes,
        },
        response_data={
            **result,
            "amount": str(w.amount) if w else None,
            "asset_type": w.asset_type.value if w else None,
        },
        tags=["withdrawal", "admin"],
    )
    await db.commit()

    # Withdrawal rejected email (fire-and-forget)
    if result.get("success"):
        try:
            from sqlalchemy import select as _sel
            from ...services.email_service import email_service as _email_svc
            w = (await db.execute(_sel(Withdrawal).where(Withdrawal.id == withdrawal_id))).scalar_one_or_none()
            if w:
                u = (await db.execute(_sel(User).where(User.entity_id == w.entity_id))).scalars().first()
                if u:
                    await _email_svc.send_withdrawal_rejected(
                        to_email=u.email, first_name=u.first_name or "",
                        amount=float(w.amount), currency=w.asset_type.value if w.asset_type else "EUR",
                        reason=request.rejection_reason or "",
                    )
        except Exception:
            logger.debug("Withdrawal rejected email failed for %s", withdrawal_id)

    return result
