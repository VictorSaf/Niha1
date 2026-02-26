import asyncio
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_db
from ...core.security import get_admin_user
from ...models.models import (
    AMLStatus,
    AssetTransaction,
    AssetType,
    Currency,
    Deposit,
    DepositStatus,
    DocumentStatus,
    Entity,
    EntityHolding,
    KYCDocument,
    KYCStatus,
    TicketStatus,
    Trade,
    TransactionType,
    User,
    UserRole,
    UserSession,
)
from ...services.deposit_service import calculate_business_days, calculate_hold_period
from ...services.document_delivery_service import (
    ACCOUNT_APPROVED_ATTACHMENTS,
    get_document_bytes,
)
from ...schemas.schemas import (
    AddAssetRequest,
    AssetTransactionResponse,
    AssetTypeEnum,
    DepositConfirm,
    DepositCreate,
    EntityAssetsResponse,
    KYCDocumentReview,
    MessageResponse,
    UserApprovalRequest,
)
from ...services.email_service import email_service
from ...services.balance_utils import get_entity_eur_balance, update_entity_balance
from ...services.ticket_service import TicketService
from ...services.ws_utils import get_entity_user_ids

# Constants for deposit validation
MAX_DEPOSIT_AMOUNT = Decimal("100000000")  # 100 million max per deposit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backoffice", tags=["Backoffice"])


# ============== WebSocket Connection Manager ==============


class BackofficeConnectionManager:
    """Manage WebSocket connections for backoffice realtime updates"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: dict):
        """Broadcast an event to all connected clients"""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
backoffice_ws_manager = BackofficeConnectionManager()


@router.websocket("/ws")
async def backoffice_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time backoffice updates.
    Sends heartbeat every 30 seconds to keep connection alive.
    Events are pushed when contact requests or other backoffice data changes.
    Requires a valid admin JWT token via ?token= query param.
    """
    from ...core.database import AsyncSessionLocal
    from ...core.security import RedisManager, verify_token

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return
    if await RedisManager.is_token_blacklisted(token):
        await websocket.close(code=4001, reason="Token invalidated")
        return
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    if not user or not user.is_active:
        await websocket.close(code=4001, reason="Invalid token")
        return
    if user.role != UserRole.ADMIN:
        await websocket.close(code=4003, reason="Admin access required")
        return

    await backoffice_ws_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "message": "Connected to backoffice realtime updates",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Keep connection alive with heartbeat
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json(
                    {"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}
                )
            except Exception:
                break

    except WebSocketDisconnect:
        backoffice_ws_manager.disconnect(websocket)
    except Exception:
        backoffice_ws_manager.disconnect(websocket)


@router.get("/pending-users")
async def get_pending_users(
    admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)  # noqa: B008
):
    """
    Get users awaiting approval (pending status with submitted KYC).
    Admin only.
    """
    # Get pending users in KYC (awaiting backoffice approve/reject after KYC submission)
    query = (
        select(User)
        .where(User.role == UserRole.KYC)
        .where(User.is_active.is_(True))
        .order_by(User.created_at.desc())
    )

    result = await db.execute(query)
    users = result.scalars().all()

    pending_list = []
    for user in users:
        # Count documents
        doc_count_query = (
            select(func.count())
            .select_from(KYCDocument)
            .where(KYCDocument.user_id == user.id)
        )
        doc_result = await db.execute(doc_count_query)
        doc_count = doc_result.scalar()

        # Get entity name if exists
        entity_name = None
        if user.entity_id:
            entity_result = await db.execute(
                select(Entity).where(Entity.id == user.entity_id)
            )
            entity = entity_result.scalar_one_or_none()
            if entity:
                entity_name = entity.name

        pending_list.append(
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "entity_name": entity_name,
                "documents_count": doc_count,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        )

    return pending_list


@router.put("/users/{user_id}/approve", response_model=MessageResponse)
async def approve_user(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Approve KYC: user.role KYC → APPROVED. User gets access to funding page.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != UserRole.KYC:
        raise HTTPException(
            status_code=400,
            detail=f"User is not in KYC review (current role: {user.role.value})",
        )

    user.role = UserRole.APPROVED

    # Update entity KYC status if exists
    if user.entity_id:
        entity_result = await db.execute(
            select(Entity).where(Entity.id == user.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            entity.kyc_status = KYCStatus.APPROVED
            # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
            entity.kyc_approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            entity.kyc_approved_by = admin_user.id
            entity.verified = True

    await db.commit()

    # Send approval email with contract documents (MSA, Custody, Fee Schedule, Risk Disclosure, Derivatives)
    try:
        # Re-fetch user with entity for document generation
        user_result = await db.execute(
            select(User).options(selectinload(User.entity)).where(User.id == UUID(user_id))
        )
        user_with_entity = user_result.scalar_one_or_none()
        attachments = []
        if user_with_entity:
            for doc_id in ACCOUNT_APPROVED_ATTACHMENTS:
                try:
                    content, filename = await get_document_bytes(doc_id, user_with_entity, db)
                    attachments.append({"filename": filename, "content": content})
                except (ValueError, FileNotFoundError) as e:
                    logger.warning(
                        "Could not attach %s to account_approved email for user %s: %s",
                        doc_id,
                        user_id,
                        e,
                    )
        await email_service.send_account_approved(
            user.email,
            user.first_name or "",
            attachments=attachments if attachments else None,
        )
    except Exception:
        pass  # Don't fail if email fails

    return MessageResponse(message=f"User {user.email} has been approved")


@router.put("/users/{user_id}/reject", response_model=MessageResponse)
async def reject_user(
    user_id: str,
    rejection: UserApprovalRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Reject KYC: set user.role to REJECTED and entity KYC status to rejected.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = UserRole.REJECTED

    # Update entity KYC status if exists
    if user.entity_id:
        entity_result = await db.execute(
            select(Entity).where(Entity.id == user.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            entity.kyc_status = KYCStatus.REJECTED

    await db.commit()

    # KYC rejection email (fire-and-forget)
    try:
        from ...services.email_service import email_service as _email_svc
        await _email_svc.send_kyc_rejected(
            to_email=user.email,
            first_name=user.first_name or "",
            reason=rejection.notes or "",
        )
    except Exception:
        logger.debug("KYC rejection email failed for user %s", user.id)

    return MessageResponse(message=f"User {user.email} has been rejected")


@router.get("/kyc-documents")
async def get_all_kyc_documents(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all KYC documents, optionally filtered by user or status.
    Admin only.
    """
    query = select(KYCDocument).order_by(KYCDocument.created_at.desc())

    if user_id:
        query = query.where(KYCDocument.user_id == UUID(user_id))

    if status:
        try:
            doc_status = DocumentStatus(status)
        except ValueError as e:
            valid_values = [s.value for s in DocumentStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_values}",
            ) from e
        query = query.where(KYCDocument.status == doc_status)

    result = await db.execute(query)
    documents = result.scalars().all()

    docs_with_user = []
    for doc in documents:
        # Get user info
        user_result = await db.execute(select(User).where(User.id == doc.user_id))
        user = user_result.scalar_one_or_none()

        docs_with_user.append(
            {
                "id": str(doc.id),
                "user_id": str(doc.user_id),
                "user_email": user.email if user else None,
                "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip()
                if user
                else None,
                "entity_id": str(doc.entity_id) if doc.entity_id else None,
                "document_type": doc.document_type.value,
                "file_name": doc.file_name,
                "mime_type": doc.mime_type,
                "status": doc.status.value,
                "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
                "notes": doc.notes,
                "created_at": doc.created_at.isoformat(),
            }
        )

    return docs_with_user


@router.put("/kyc-documents/{document_id}/review", response_model=MessageResponse)
async def review_kyc_document(
    document_id: str,
    review: KYCDocumentReview,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Review (approve/reject) a KYC document.
    Admin only.
    """
    result = await db.execute(
        select(KYCDocument).where(KYCDocument.id == UUID(document_id))
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = review.status
    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    document.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    document.reviewed_by = admin_user.id
    if review.notes:
        document.notes = review.notes

    await db.commit()

    # Broadcast KYC document review event
    await backoffice_ws_manager.broadcast(
        "kyc_document_reviewed",
        {
            "document_id": str(document.id),
            "user_id": str(document.user_id),
            "document_type": document.document_type.value,
            "status": document.status.value,
            "notes": document.notes,
            "reviewed_at": document.reviewed_at.isoformat()
            if document.reviewed_at
            else None,
        },
    )

    # Notify the document owner so their UI updates
    from .client_ws import client_ws_manager

    asyncio.create_task(client_ws_manager.broadcast_to_users(
        [document.user_id],
        {"type": "kyc_status_updated", "data": {"status": review.status.value, "document_id": str(document.id)}},
    ))

    return MessageResponse(message=f"Document has been {review.status.value}")


@router.get("/kyc-documents/{document_id}/content")
async def get_document_content(
    document_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get KYC document content for preview/download.
    Returns file with appropriate Content-Type for inline viewing.
    Admin only.
    """
    result = await db.execute(
        select(KYCDocument).where(KYCDocument.id == UUID(document_id))
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.file_path or not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    return FileResponse(
        path=document.file_path,
        filename=document.file_name,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{document.file_name}"'},
    )


@router.get("/users/{user_id}/sessions")
async def get_user_sessions(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get a user's session history.
    Admin only.
    """
    query = (
        select(UserSession)
        .where(UserSession.user_id == UUID(user_id))
        .order_by(UserSession.started_at.desc())
        .limit(100)
    )

    result = await db.execute(query)
    sessions = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_seconds": s.duration_seconds,
            "is_active": s.is_active,
        }
        for s in sessions
    ]


@router.get("/users/{user_id}/trades")
async def get_user_trades(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get a user's trading history.
    Admin only.
    """
    # Get user's entity
    user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = user_result.scalar_one_or_none()

    if not user or not user.entity_id:
        return []

    # Get trades where user's entity is buyer or seller
    query = (
        select(Trade)
        .where(
            (Trade.buyer_entity_id == user.entity_id)
            | (Trade.seller_entity_id == user.entity_id)
        )
        .order_by(Trade.created_at.desc())
        .limit(100)
    )

    result = await db.execute(query)
    trades = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "trade_type": t.trade_type.value,
            "certificate_type": t.certificate_type.value,
            "quantity": int(round(float(t.quantity))),
            "price_per_unit": float(t.price_per_unit),
            "total_value": float(t.total_value),
            "status": t.status.value,
            "is_buyer": str(t.buyer_entity_id) == str(user.entity_id),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in trades
    ]


# ============== DEPOSIT MANAGEMENT ==============


@router.get("/deposits")
async def get_all_deposits(
    status: Optional[str] = None,
    entity_id: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all deposits, optionally filtered by status or entity_id. Admin only.

    Query: status (optional), entity_id (optional UUID). Returns list of deposit objects
    (id, entity_id, entity_name, user_email, user_role, amount, currency, status, ...).
    Uses selectinload(Deposit.entity), selectinload(Deposit.user), and a single batch query for fallback users
    (deposits without reporting user) to avoid N+1.
    """
    query = (
        select(Deposit)
        .options(selectinload(Deposit.entity), selectinload(Deposit.user))
        .order_by(Deposit.created_at.desc())
    )

    if status:
        try:
            dep_status = DepositStatus(status)
        except ValueError as e:
            valid_values = [s.value for s in DepositStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_values}",
            ) from e
        query = query.where(Deposit.status == dep_status)

    if entity_id:
        query = query.where(Deposit.entity_id == UUID(entity_id))

    result = await db.execute(query)
    deposits = result.scalars().all()

    # Batch-fetch first user per entity for deposits without reporting user
    entity_ids_needing_fallback = list(
        {d.entity_id for d in deposits if not d.user_id and d.entity_id}
    )
    fallback_user_by_entity: dict[UUID, User] = {}
    if entity_ids_needing_fallback:
        fallback_result = await db.execute(
            select(User)
            .where(User.entity_id.in_(entity_ids_needing_fallback))
            .order_by(User.entity_id, User.created_at.asc())
        )
        seen: set[UUID] = set()
        for u in fallback_result.scalars().all():
            if u.entity_id and u.entity_id not in seen:
                seen.add(u.entity_id)
                fallback_user_by_entity[u.entity_id] = u

    deposits_with_entity = []
    for dep in deposits:
        entity = dep.entity
        reporting_user = dep.user
        user_email = None
        user_role = None
        if reporting_user:
            user_email = reporting_user.email
            user_role = reporting_user.role.value
        elif dep.entity_id and dep.entity_id in fallback_user_by_entity:
            u = fallback_user_by_entity[dep.entity_id]
            user_email = u.email
            user_role = u.role.value

        deposits_with_entity.append(
            {
                "id": str(dep.id),
                "entity_id": str(dep.entity_id),
                "entity_name": (entity.name if entity else None) or "—",
                "user_email": user_email or "",
                "user_role": user_role,
                "reported_amount": float(dep.reported_amount)
                if dep.reported_amount is not None
                else None,
                "reported_currency": dep.reported_currency.value
                if dep.reported_currency is not None
                else None,
                "amount": float(dep.amount) if dep.amount else None,
                "currency": dep.currency.value if dep.currency else None,
                "wire_reference": dep.wire_reference,
                "bank_reference": dep.bank_reference,
                "status": dep.status.value,
                "reported_at": (dep.reported_at.isoformat() + "Z")
                if dep.reported_at
                else None,
                "confirmed_at": (dep.confirmed_at.isoformat() + "Z")
                if dep.confirmed_at
                else None,
                "confirmed_by": str(dep.confirmed_by) if dep.confirmed_by else None,
                "notes": dep.notes,
                "created_at": dep.created_at.isoformat() + "Z",
            }
        )

    return deposits_with_entity


@router.post("/deposits", response_model=MessageResponse)
async def create_deposit(
    deposit_data: DepositCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create and confirm a deposit for an entity (direct create, no client announce).

    Use when backoffice receives a wire transfer **without** a prior client
    announce. Credited immediately; no AML hold. No user role transitions.

    For the 0010 flow (announce → confirm → clear), use instead:
    - Client: POST /deposits/announce (APPROVED→FUNDING).
    - Admin: POST /deposits/{id}/confirm (deposit_service, ON_HOLD, FUNDING→AML)
      or PUT /backoffice/deposits/{id}/confirm (immediate confirm, FUNDING→AML).
    - Admin: POST /deposits/{id}/clear when hold expires (AML→CEA).
    Admin only.
    """
    # Validate deposit amount
    deposit_amount = Decimal(str(deposit_data.amount))
    if deposit_amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be positive")
    if deposit_amount > MAX_DEPOSIT_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Deposit amount exceeds maximum allowed "
                f"({MAX_DEPOSIT_AMOUNT:,.2f})"
            ),
        )

    # Verify entity exists with row lock to prevent race conditions
    entity_result = await db.execute(
        select(Entity).where(Entity.id == deposit_data.entity_id).with_for_update()
    )
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Validate currency - cannot mix currencies in the same entity balance
    deposit_currency = Currency(deposit_data.currency.value)
    if entity.balance_currency and entity.balance_currency != deposit_currency:
        if entity.balance_amount and entity.balance_amount > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Currency mismatch: entity has existing balance in "
                    f"{entity.balance_currency.value}, cannot add "
                    f"{deposit_currency.value}. Please use the same currency "
                    f"or zero the balance first."
                ),
            )

    # Generate bank reference using cryptographically secure random
    import secrets
    import string

    chars = string.ascii_uppercase + string.digits
    bank_ref = f"DEP-{''.join(secrets.choice(chars) for _ in range(8))}"

    # Create deposit record
    deposit = Deposit(
        entity_id=deposit_data.entity_id,
        amount=deposit_amount,
        currency=deposit_currency,
        wire_reference=deposit_data.wire_reference,
        bank_reference=bank_ref,
        status=DepositStatus.CONFIRMED,
        # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
        confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        confirmed_by=admin_user.id,
        notes=deposit_data.notes,
    )
    db.add(deposit)

    # Update entity balance atomically using the locked row
    entity.balance_amount = (entity.balance_amount or Decimal("0")) + deposit_amount
    entity.balance_currency = deposit_currency
    entity.total_deposited = (entity.total_deposited or Decimal("0")) + deposit_amount

    # Find users for this entity (for notification only; no role transitions on direct create)
    users_result = await db.execute(select(User).where(User.entity_id == entity.id))
    users = users_result.scalars().all()

    await db.commit()

    # Send notification email to entity users
    for user in users:
        try:
            await email_service.send_account_funded(user.email, user.first_name)
        except Exception:
            pass

    return MessageResponse(
        message=(
            f"Deposit of {deposit_data.amount} {deposit_data.currency.value} "
            f"confirmed for {entity.name}."
        )
    )


@router.get("/deposits/{deposit_id}")
async def get_deposit(
    deposit_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get a specific deposit's details.
    Admin only.
    """
    result = await db.execute(select(Deposit).where(Deposit.id == UUID(deposit_id)))
    deposit = result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    # Get entity info
    entity_result = await db.execute(
        select(Entity).where(Entity.id == deposit.entity_id)
    )
    entity = entity_result.scalar_one_or_none()

    return {
        "id": str(deposit.id),
        "entity_id": str(deposit.entity_id),
        "entity_name": entity.name if entity else None,
        "reported_amount": float(deposit.reported_amount)
        if deposit.reported_amount
        else None,
        "reported_currency": deposit.reported_currency.value
        if deposit.reported_currency
        else None,
        "amount": float(deposit.amount) if deposit.amount else None,
        "currency": deposit.currency.value if deposit.currency else None,
        "wire_reference": deposit.wire_reference,
        "bank_reference": deposit.bank_reference,
        "status": deposit.status.value,
        "reported_at": (deposit.reported_at.isoformat() + "Z")
        if deposit.reported_at
        else None,
        "confirmed_at": (deposit.confirmed_at.isoformat() + "Z")
        if deposit.confirmed_at
        else None,
        "confirmed_by": str(deposit.confirmed_by) if deposit.confirmed_by else None,
        "notes": deposit.notes,
        "created_at": deposit.created_at.isoformat() + "Z",
    }


@router.put("/deposits/{deposit_id}/confirm", response_model=MessageResponse)
async def confirm_pending_deposit(
    deposit_id: str,
    confirmation: DepositConfirm,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Confirm a pending deposit (client-announced) with actual received amount.

    Use when the client has announced via POST /deposits/announce and the
    deposit is PENDING. Sets deposit to ON_HOLD with AML hold period calculated,
    and transitions user FUNDING → AML. Funds are NOT credited until clear_deposit.
    Admin only.
    """
    # Get deposit with row lock
    result = await db.execute(
        select(Deposit).where(Deposit.id == UUID(deposit_id)).with_for_update()
    )
    deposit = result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    if deposit.status != DepositStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit is not pending (current status: {deposit.status.value})",
        )

    # Get entity with row lock
    entity_result = await db.execute(
        select(Entity).where(Entity.id == deposit.entity_id).with_for_update()
    )
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Validate and set confirmed amount
    confirmed_amount = Decimal(str(confirmation.amount))
    if confirmed_amount <= 0:
        raise HTTPException(status_code=400, detail="Confirmed amount must be positive")
    if confirmed_amount > MAX_DEPOSIT_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds maximum allowed ({MAX_DEPOSIT_AMOUNT:,.2f})",
        )

    confirmed_currency = Currency(confirmation.currency.value)

    # Calculate AML hold period
    hold_type, hold_days = await calculate_hold_period(
        db, deposit.entity_id, confirmed_amount
    )
    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    hold_expires_at = calculate_business_days(now, hold_days)

    # Update deposit with confirmed values - set to ON_HOLD for AML review
    deposit.amount = confirmed_amount
    deposit.currency = confirmed_currency
    deposit.status = DepositStatus.ON_HOLD
    deposit.hold_type = hold_type.value
    deposit.hold_days_required = hold_days
    deposit.hold_expires_at = hold_expires_at
    deposit.aml_status = AMLStatus.ON_HOLD.value
    deposit.confirmed_at = now
    deposit.confirmed_by = admin_user.id
    if confirmation.notes:
        deposit.notes = confirmation.notes

    # NOTE: Funds are NOT credited yet - they will be credited when clear_deposit is called
    # after AML review is complete. Entity balance is NOT updated here.

    # Role transition: FUNDING → AML when backoffice confirms transfer (client waits for AML)
    users_result = await db.execute(
        select(User).where(
            User.entity_id == entity.id,
            User.role == UserRole.FUNDING,
        )
    )
    users = users_result.scalars().all()
    upgraded_count = len(users)
    for u in users:
        u.role = UserRole.AML
    await db.flush()

    await db.commit()

    # Send AML review notification emails (FUNDING → AML)
    for user in users:
        try:
            await email_service.send_aml_review_started(
                user.email, user.first_name or "",
                amount=float(confirmed_amount), currency=confirmed_currency.value,
            )
        except Exception:
            pass

    # Broadcast WebSocket event
    await backoffice_ws_manager.broadcast(
        "deposit_confirmed",
        {
            "deposit_id": str(deposit.id),
            "entity_id": str(entity.id),
            "entity_name": entity.name,
            "amount": float(confirmed_amount),
            "currency": confirmed_currency.value,
            "hold_type": hold_type.value,
            "hold_days": hold_days,
            "hold_expires_at": hold_expires_at.isoformat(),
        },
    )

    return MessageResponse(
        message=(
            f"Deposit confirmed and placed ON_HOLD: {confirmed_amount} {confirmed_currency.value} "
            f"for {entity.name}. Hold: {hold_type.value} ({hold_days} days, expires {hold_expires_at.date()}). "
            f"{upgraded_count} user(s) upgraded to AML."
        )
    )


@router.put("/deposits/{deposit_id}/reject", response_model=MessageResponse)
async def reject_pending_deposit(
    deposit_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Reject a pending deposit.
    Admin only.
    """
    result = await db.execute(select(Deposit).where(Deposit.id == UUID(deposit_id)))
    deposit = result.scalar_one_or_none()

    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    if deposit.status != DepositStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit is not pending (current status: {deposit.status.value})",
        )

    deposit.status = DepositStatus.REJECTED
    await db.commit()

    # Deposit rejection email (fire-and-forget)
    try:
        from ...services.email_service import email_service as _email_svc
        user_result = await db.execute(select(User).where(User.entity_id == deposit.entity_id))
        user = user_result.scalars().first()
        if user:
            await _email_svc.send_deposit_rejected(
                to_email=user.email,
                first_name=user.first_name or "",
                amount=float(deposit.amount),
                currency=deposit.currency or "EUR",
                reason="REJECTED_BY_ADMIN",
            )
    except Exception:
        logger.debug("Deposit rejection email failed for deposit %s", deposit_id)

    return MessageResponse(message="Deposit rejected")


@router.post("/entities/{entity_id}/sync-balance", response_model=MessageResponse)
async def sync_entity_balance(
    entity_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Sync entity.balance_amount to EntityHolding (EUR).
    Used to fix cases where balance was credited to Entity but not EntityHolding.
    Admin only.
    """
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    if not entity.balance_amount or entity.balance_amount <= 0:
        raise HTTPException(status_code=400, detail="Entity has no balance to sync")

    # Check current EntityHolding EUR balance
    holding_result = await db.execute(
        select(EntityHolding).where(
            EntityHolding.entity_id == entity.id,
            EntityHolding.asset_type == AssetType.EUR,
        )
    )
    holding = holding_result.scalar_one_or_none()
    current_holding_balance = Decimal(str(holding.quantity)) if holding else Decimal("0")

    # Calculate difference
    target_balance = Decimal(str(entity.balance_amount))
    difference = target_balance - current_holding_balance

    if difference <= 0:
        return MessageResponse(
            message=f"EntityHolding already has {current_holding_balance} EUR (entity.balance_amount: {target_balance}). No sync needed."
        )

    # Credit the difference to EntityHolding
    await update_entity_balance(
        db=db,
        entity_id=entity.id,
        asset_type=AssetType.EUR,
        amount=difference,
        transaction_type=TransactionType.ADJUSTMENT,
        created_by=admin_user.id,
        reference="balance_sync",
        notes=f"Sync entity.balance_amount to EntityHolding (+{difference} EUR)",
    )

    await db.commit()

    return MessageResponse(
        message=f"Synced {difference} EUR to EntityHolding for {entity.name}. New balance: {target_balance} EUR"
    )


@router.get("/entities/{entity_id}/balance")
async def get_entity_balance(
    entity_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get an entity's balance and deposit history.
    Admin only.
    """
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Count deposits
    deposit_count_result = await db.execute(
        select(func.count())
        .select_from(Deposit)
        .where(
            Deposit.entity_id == entity.id, Deposit.status == DepositStatus.CONFIRMED
        )
    )
    deposit_count = deposit_count_result.scalar()

    return {
        "entity_id": str(entity.id),
        "entity_name": entity.name,
        "balance_amount": float(entity.balance_amount or 0),
        "balance_currency": entity.balance_currency.value
        if entity.balance_currency
        else None,
        "total_deposited": float(entity.total_deposited or 0),
        "deposit_count": deposit_count,
    }


@router.get("/users/{user_id}/deposits")
async def get_user_deposits(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all deposits for a user's entity.
    Admin only.
    """
    # Get user's entity
    user_result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = user_result.scalar_one_or_none()

    if not user or not user.entity_id:
        return []

    # Get deposits for entity
    query = (
        select(Deposit)
        .where(Deposit.entity_id == user.entity_id)
        .order_by(Deposit.created_at.desc())
    )

    result = await db.execute(query)
    deposits = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "entity_id": str(d.entity_id),
            "amount": float(d.amount),
            "currency": d.currency.value,
            "wire_reference": d.wire_reference,
            "bank_reference": d.bank_reference,
            "status": d.status.value,
            "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in deposits
    ]


# ============== Asset Management Endpoints ==============


@router.post("/entities/{entity_id}/add-asset", response_model=MessageResponse)
async def add_asset_to_entity(
    entity_id: str,
    asset_request: AddAssetRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Deposit or withdraw EUR, CEA, or EUA for an entity.
    Request body: asset_type, amount (positive), operation ('deposit'|'withdraw', default 'deposit'), optional reference, notes.
    Withdraw: validates sufficient balance; returns 400 'Insufficient balance' if amount would exceed holding.
    Creates AssetTransaction (DEPOSIT or WITHDRAWAL) and updates EntityHolding.quantity. For EUR, also updates Entity.balance_amount and total_deposited (deposit only). Admin only.
    """
    # Validate entity exists
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Map schema enum to model enum
    asset_type_map = {
        AssetTypeEnum.EUR: AssetType.EUR,
        AssetTypeEnum.CEA: AssetType.CEA,
        AssetTypeEnum.EUA: AssetType.EUA,
    }
    model_asset_type = asset_type_map[asset_request.asset_type]

    # Get or create EntityHolding record
    holding_result = await db.execute(
        select(EntityHolding).where(
            EntityHolding.entity_id == UUID(entity_id),
            EntityHolding.asset_type == model_asset_type,
        )
    )
    holding = holding_result.scalar_one_or_none()

    if not holding:
        holding = EntityHolding(
            entity_id=UUID(entity_id),
            asset_type=model_asset_type,
            quantity=Decimal("0"),
        )
        db.add(holding)
        await db.flush()  # Get the holding ID

    balance_before = Decimal(str(holding.quantity))
    # CEA/EUA: whole certificates only — round amount to integer
    raw_amount = float(asset_request.amount)
    if model_asset_type in (AssetType.CEA, AssetType.EUA):
        amount_abs = Decimal(str(int(round(raw_amount))))
        if amount_abs <= 0:
            raise HTTPException(
                status_code=400, detail="CEA/EUA amount must be a positive whole number"
            )
    else:
        amount_abs = Decimal(str(asset_request.amount))
    is_withdraw = asset_request.operation == "withdraw"

    if is_withdraw:
        # For CEA/EUA, the displayed balance is floor(actual), so if the user
        # withdraws the full displayed amount, it may be slightly more than the
        # fractional holding (e.g. withdraw 608808 when holding is 608807.89).
        # In that case, withdraw the entire actual balance instead of failing.
        if model_asset_type in (AssetType.CEA, AssetType.EUA):
            displayed_balance = Decimal(str(int(float(balance_before))))
            if amount_abs == displayed_balance or amount_abs >= balance_before:
                # Full withdrawal — drain the actual holding (including dust)
                amount_debit = -balance_before
            elif amount_abs > displayed_balance:
                raise HTTPException(
                    status_code=400, detail="Insufficient balance"
                )
            else:
                amount_debit = -amount_abs
        else:
            amount_debit = -amount_abs
            if balance_before + amount_debit < 0:
                raise HTTPException(
                    status_code=400, detail="Insufficient balance"
                )
        balance_after = balance_before + amount_debit
        transaction_type = TransactionType.WITHDRAWAL
        amount_for_tx = amount_debit
    else:
        balance_after = balance_before + amount_abs
        transaction_type = TransactionType.DEPOSIT
        amount_for_tx = amount_abs

    # Update holding
    holding.quantity = balance_after
    holding.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create audit transaction
    transaction = AssetTransaction(
        entity_id=UUID(entity_id),
        asset_type=model_asset_type,
        transaction_type=transaction_type,
        amount=amount_for_tx,
        balance_before=balance_before,
        balance_after=balance_after,
        reference=asset_request.reference,
        notes=asset_request.notes,
        created_by=admin_user.id,
    )
    db.add(transaction)
    await db.flush()  # Get transaction.id for ticket

    action_type = (
        "ENTITY_ASSET_WITHDRAWAL" if is_withdraw else "ENTITY_ASSET_DEPOSIT"
    )
    tags = ["entity_asset", "withdrawal" if is_withdraw else "deposit"]
    await TicketService.create_ticket(
        db=db,
        action_type=action_type,
        entity_type="AssetTransaction",
        entity_id=transaction.id,
        user_id=admin_user.id,
        status=TicketStatus.SUCCESS,
        after_state={
            "asset_type": model_asset_type.value,
            "amount": str(amount_for_tx),
            "balance_before": str(balance_before),
            "balance_after": str(balance_after),
            "operation": "withdraw" if is_withdraw else "deposit",
        },
        tags=tags,
    )

    # If EUR, update Entity.balance_amount for compatibility
    if model_asset_type == AssetType.EUR:
        entity.balance_amount = balance_after
        entity.balance_currency = Currency.EUR
        if not is_withdraw:
            entity.total_deposited = (
                entity.total_deposited or Decimal("0")
            ) + amount_abs

    await db.commit()

    # Notify entity users so their dashboard/balance refreshes
    from .client_ws import client_ws_manager

    user_ids = await get_entity_user_ids(db, UUID(entity_id))
    if user_ids:
        asyncio.create_task(client_ws_manager.broadcast_to_users(
            user_ids,
            {"type": "balance_updated", "data": {"source": "admin_asset_adjustment"}},
        ))

    asset_label = {
        AssetType.EUR: "EUR",
        AssetType.CEA: "CEA certificates",
        AssetType.EUA: "EUA certificates",
    }[model_asset_type]

    # CEA/EUA: show whole number in message; EUR: show 2 decimals
    if model_asset_type in (AssetType.CEA, AssetType.EUA):
        amt_str = f"{int(round(float(asset_request.amount))):,}"
    else:
        amt_str = f"{asset_request.amount:,.2f}"
    if is_withdraw:
        msg = (
            f"Successfully withdrew {amt_str} {asset_label} "
            f"from {entity.name}"
        )
    else:
        msg = (
            f"Successfully added {amt_str} {asset_label} "
            f"to {entity.name}"
        )
    return MessageResponse(message=msg)


@router.get("/entities/{entity_id}/assets", response_model=EntityAssetsResponse)
async def get_entity_assets(
    entity_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all asset balances for an entity (EUR, CEA, EUA) plus recent_transactions
    (last 50 add-asset operations). Used by User Detail Deposit & Withdrawal History.
    Admin only.
    """
    # Validate entity exists
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Get all holdings
    holdings_result = await db.execute(
        select(EntityHolding).where(EntityHolding.entity_id == UUID(entity_id))
    )
    holdings = holdings_result.scalars().all()

    # Build balance map
    balances = {
        AssetType.EUR: Decimal("0"),
        AssetType.CEA: Decimal("0"),
        AssetType.EUA: Decimal("0"),
    }
    for h in holdings:
        balances[h.asset_type] = h.quantity

    # Use shared EUR logic (EntityHolding + Entity.balance_amount fallback); pass entity and eur to avoid extra queries
    balances[AssetType.EUR] = await get_entity_eur_balance(
        db, UUID(entity_id), entity=entity, eur_holding_quantity=balances[AssetType.EUR]
    )

    # Get recent transactions (limit aligned with frontend unified history cap)
    RECENT_ASSET_TRANSACTIONS_LIMIT = 50
    transactions_result = await db.execute(
        select(AssetTransaction)
        .where(AssetTransaction.entity_id == UUID(entity_id))
        .order_by(AssetTransaction.created_at.desc())
        .limit(RECENT_ASSET_TRANSACTIONS_LIMIT)
    )
    transactions = transactions_result.scalars().all()

    def _amt(v, at: AssetType) -> float:
        return int(float(v)) if at in (AssetType.CEA, AssetType.EUA) else float(v)

    return EntityAssetsResponse(
        entity_id=UUID(entity_id),
        entity_name=entity.name,
        eur_balance=float(balances[AssetType.EUR]),
        cea_balance=int(float(balances[AssetType.CEA])),
        eua_balance=int(float(balances[AssetType.EUA])),
        recent_transactions=[
            AssetTransactionResponse(
                id=t.id,
                entity_id=t.entity_id,
                asset_type=t.asset_type,
                transaction_type=t.transaction_type,
                amount=_amt(t.amount, t.asset_type),
                balance_before=_amt(t.balance_before, t.asset_type),
                balance_after=_amt(t.balance_after, t.asset_type),
                reference=t.reference,
                notes=t.notes,
                created_by=t.created_by,
                created_at=t.created_at,
            )
            for t in transactions
        ],
    )


@router.get("/entities/{entity_id}/transactions")
async def get_entity_transactions(
    entity_id: str,
    asset_type: Optional[AssetTypeEnum] = None,
    limit: int = Query(50, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get transaction history for an entity.
    Admin only.
    """
    # Validate entity exists
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Build query
    query = select(AssetTransaction).where(
        AssetTransaction.entity_id == UUID(entity_id)
    )

    if asset_type:
        asset_type_map = {
            AssetTypeEnum.EUR: AssetType.EUR,
            AssetTypeEnum.CEA: AssetType.CEA,
            AssetTypeEnum.EUA: AssetType.EUA,
        }
        query = query.where(AssetTransaction.asset_type == asset_type_map[asset_type])

    query = query.order_by(AssetTransaction.created_at.desc()).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    def _amt(v, at) -> float:
        return int(round(float(v))) if at in (AssetType.CEA, AssetType.EUA) else float(v)

    return [
        {
            "id": str(t.id),
            "entity_id": str(t.entity_id),
            "asset_type": t.asset_type.value,
            "transaction_type": t.transaction_type.value,
            "amount": _amt(t.amount, t.asset_type),
            "balance_before": _amt(t.balance_before, t.asset_type),
            "balance_after": _amt(t.balance_after, t.asset_type),
            "reference": t.reference,
            "notes": t.notes,
            "created_by": str(t.created_by),
            "created_at": t.created_at.isoformat(),
        }
        for t in transactions
    ]


# =============================================================================
# Asset Balance Update (Admin Edit Assets)
# =============================================================================


class UpdateAssetRequest(BaseModel):
    """Request to update an entity's asset balance"""

    new_balance: float = Field(
        ..., ge=0, description="New balance value (must be >= 0)"
    )
    notes: Optional[str] = Field(
        None, max_length=500, description="Admin notes for audit"
    )
    reference: Optional[str] = Field(
        None, max_length=100, description="Reference for tracking"
    )


@router.put("/entities/{entity_id}/assets/{asset_type}")
async def update_asset_balance(
    entity_id: str,
    asset_type: AssetTypeEnum,
    request: UpdateAssetRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update an entity's asset balance to a specific value.
    Creates an audit trail transaction.
    Admin only.
    """
    # Validate entity exists
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Map schema enum to model enum
    asset_type_map = {
        AssetTypeEnum.EUR: AssetType.EUR,
        AssetTypeEnum.CEA: AssetType.CEA,
        AssetTypeEnum.EUA: AssetType.EUA,
    }
    model_asset_type = asset_type_map[asset_type]

    # Get or create holding
    holding_result = await db.execute(
        select(EntityHolding).where(
            EntityHolding.entity_id == UUID(entity_id),
            EntityHolding.asset_type == model_asset_type,
        )
    )
    holding = holding_result.scalar_one_or_none()

    balance_before = Decimal("0")
    if holding:
        balance_before = holding.quantity
    else:
        # Create new holding
        holding = EntityHolding(
            entity_id=UUID(entity_id),
            asset_type=model_asset_type,
            quantity=Decimal("0"),
        )
        db.add(holding)

    new_balance = Decimal(str(request.new_balance))
    delta = new_balance - balance_before

    # Update the holding
    holding.quantity = new_balance
    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    holding.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create audit transaction
    transaction = AssetTransaction(
        entity_id=UUID(entity_id),
        asset_type=model_asset_type,
        transaction_type=TransactionType.ADJUSTMENT,
        amount=abs(delta),
        balance_before=balance_before,
        balance_after=new_balance,
        reference=request.reference,
        notes=request.notes or f"Admin adjustment by {admin_user.email}",
        created_by=admin_user.id,
    )
    db.add(transaction)

    # If EUR, also update Entity.balance_amount for backward compatibility
    if model_asset_type == AssetType.EUR:
        entity.balance_amount = new_balance

    await db.commit()

    asset_labels = {"EUR": "EUR", "CEA": "CEA", "EUA": "EUA"}
    asset_label = asset_labels.get(asset_type.value, asset_type.value)
    direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"

    return MessageResponse(
        message=(
            f"Successfully updated {entity.name}'s {asset_label} balance from "
            f"{float(balance_before):,.2f} to {float(new_balance):,.2f} "
            f"({direction} by {abs(float(delta)):,.2f})"
        )
    )


# =============================================================================
# Entity Orders Management (Admin)
# =============================================================================


@router.get("/entities/{entity_id}/orders")
async def get_entity_orders(
    entity_id: str,
    status: Optional[str] = Query(  # noqa: B008
        None, description="Filter by status: OPEN, PARTIALLY_FILLED, FILLED, CANCELLED"
    ),
    certificate_type: Optional[str] = Query(  # noqa: B008
        None, description="Filter by certificate type: EUA, CEA"
    ),
    limit: int = Query(50, le=200),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all orders for an entity.
    Admin only.
    """
    from ...models.models import CertificateType as ModelCertificateType
    from ...models.models import Order
    from ...models.models import OrderStatus as ModelOrderStatus

    # Validate entity exists
    entity_result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = entity_result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Build query
    query = select(Order).where(Order.entity_id == UUID(entity_id))

    if status:
        try:
            status_enum = ModelOrderStatus(status)
            query = query.where(Order.status == status_enum)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status}"
            ) from e

    if certificate_type:
        try:
            cert_type_enum = ModelCertificateType(certificate_type)
            query = query.where(Order.certificate_type == cert_type_enum)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid certificate_type: {certificate_type}"
            ) from e

    query = query.order_by(Order.created_at.desc()).limit(limit)

    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        {
            "id": str(o.id),
            "entity_id": str(o.entity_id) if o.entity_id else None,
            "certificate_type": o.certificate_type.value,
            "side": o.side.value,
            "price": float(o.price),
            "quantity": int(round(float(o.quantity))),
            "filled_quantity": int(round(float(o.filled_quantity or 0))),
            "remaining_quantity": int(round(float(o.quantity - (o.filled_quantity or 0)))),
            "status": o.status.value,
            "created_at": o.created_at.isoformat(),
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        }
        for o in orders
    ]


@router.delete("/orders/{order_id}")
async def admin_cancel_order(
    order_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Cancel any order (admin only).
    Only OPEN or PARTIALLY_FILLED orders can be cancelled.
    """
    from ...models.models import Order
    from ...models.models import OrderStatus as ModelOrderStatus

    # Get the order
    result = await db.execute(select(Order).where(Order.id == UUID(order_id)))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if order can be cancelled
    if order.status not in [ModelOrderStatus.OPEN, ModelOrderStatus.PARTIALLY_FILLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status {order.status.value}",
        )

    # Cancel the order
    order.status = ModelOrderStatus.CANCELLED
    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()

    return MessageResponse(message=f"Order {order_id} cancelled successfully")


@router.put("/orders/{order_id}")
async def admin_update_order(
    order_id: str,
    update: dict,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update an order's price or quantity (admin only).
    Only OPEN orders can be updated.
    Quantity can only be reduced, not increased.
    """
    from ...models.models import Order
    from ...models.models import OrderStatus as ModelOrderStatus

    # Get the order
    result = await db.execute(select(Order).where(Order.id == UUID(order_id)))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if order can be updated
    if order.status != ModelOrderStatus.OPEN:
        raise HTTPException(
            status_code=400,
            detail=f"Can only update OPEN orders. Current status: {order.status.value}",
        )

    # Update price if provided
    if "price" in update and update["price"] is not None:
        new_price = float(update["price"])
        if new_price <= 0:
            raise HTTPException(status_code=400, detail="Price must be greater than 0")
        order.price = Decimal(str(new_price))

    # Update quantity if provided (CEA cash market: whole certificates only)
    if "quantity" in update and update["quantity"] is not None:
        new_quantity = float(update["quantity"])
        if new_quantity <= 0:
            raise HTTPException(
                status_code=400, detail="Quantity must be greater than 0"
            )
        if new_quantity != int(round(new_quantity)):
            raise HTTPException(
                status_code=400,
                detail="CEA quantity must be a whole number (no fractional certificates)",
            )
        quantity_int = int(round(new_quantity))
        if quantity_int < float(order.filled_quantity):
            filled = float(order.filled_quantity)
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reduce quantity below filled amount ({filled})",
            )
        order.quantity = Decimal(str(quantity_int))

    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()

    return {
        "id": str(order.id),
        "entity_id": str(order.entity_id) if order.entity_id else None,
        "certificate_type": order.certificate_type.value,
        "side": order.side.value,
        "price": float(order.price),
        "quantity": int(round(float(order.quantity))),
        "filled_quantity": int(round(float(order.filled_quantity or 0))),
        "remaining_quantity": int(round(float(order.quantity - (order.filled_quantity or 0)))),
        "status": order.status.value,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "message": "Order updated successfully",
    }
