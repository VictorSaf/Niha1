import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.exceptions import handle_database_error
from ...core.security import get_admin_user, get_current_user, hash_password
from ...models.models import (
    ActivityLog,
    AuthenticationAttempt,
    AutoTradeMarketSettings,
    AutoTradeRule,
    AutoTradeSettings,
    CashMarketTrade,
    Certificate,
    CertificateStatus,
    CertificateType,
    ContactRequest,
    ContactStatus,
    Entity,
    ExchangeRateSource,
    Jurisdiction,
    KYCStatus,
    MailConfig,
    MailProvider,
    MarketMakerClient,
    MarketMakerType,
    MarketType,
    PriceHistory,
    Order,
    OrderSide,
    OrderStatus,
    ScrapeLibrary,
    ScrapingSource,
    SettlementBatch,
    SettlementStatus,
    SettlementStatusHistory,
    SettlementType,
    SwapRequest,
    SwapStatus,
    TicketStatus,
    User,
    UserRole,
    UserSession,
)
from ...schemas.schemas import (
    ActivityStatsResponse,
    AdminPasswordReset,
    AdminUserFullResponse,
    AdminUserUpdate,
    AuthenticationAttemptResponse,
    AutoTradeMarketSettingsResponse,
    AutoTradeMarketSettingsUpdate,
    AutoTradeSettingsResponse,
    AutoTradeSettingsUpdate,
    ContactRequestUpdate,
    ExchangeRateSourceCreate,
    ExchangeRateSourceUpdate,
    LiquidityStatusResponse,
    MailConfigUpdate,
    MarketMakerSummary,
    MessageResponse,
    ScrapingSourceCreate,
    ScrapingSourceUpdate,
    UserCreate,
    UserResponse,
    UserRoleUpdate,
    UserSessionResponse,
)
from ...services.email_service import TEMPLATE_SAMPLE_DATA, email_service
from ...services.settlement_service import SettlementService, calculate_settlement_progress
from ...services.ticket_service import TicketService
from ...services.ws_utils import get_entity_user_ids
from .backoffice import backoffice_ws_manager
from .client_ws import client_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/contact-requests")
async def get_contact_requests(
    status: Optional[str] = None,
    request_flow: Optional[str] = Query(None, description="Filter by request_flow: 'buyer' or 'introducer'"),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(20, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all contact requests with optional status and request_flow filters.
    """
    query = select(ContactRequest).order_by(ContactRequest.created_at.desc())

    if status:
        query = query.where(ContactRequest.user_role == ContactStatus(status))
    if request_flow:
        query = query.where(ContactRequest.request_flow == request_flow)

    # Get total count
    count_query = select(func.count()).select_from(ContactRequest)
    if status:
        count_query = count_query.where(ContactRequest.user_role == ContactStatus(status))
    if request_flow:
        count_query = count_query.where(ContactRequest.request_flow == request_flow)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    requests = result.scalars().all()

    # Batch-fetch introducer users to compute NDA status (avoids N+1)
    introducer_emails = [
        r.contact_email for r in requests
        if getattr(r, "request_flow", "buyer") == "introducer"
    ]
    introducer_user_map: dict = {}
    if introducer_emails:
        user_result = await db.execute(
            select(User).where(User.email.in_(introducer_emails), User.role.in_([UserRole.TRODUCER, UserRole.PREINTRODUCER, UserRole.INTRODUCER]))
        )
        for u in user_result.scalars().all():
            introducer_user_map[u.email] = u

    # Batch-fetch referrer users (introducers who referred buyers)
    referrer_ids = [
        r.referred_by_user_id for r in requests
        if r.referred_by_user_id
    ]
    referrer_map: dict = {}
    if referrer_ids:
        ref_result = await db.execute(
            select(User).where(User.id.in_(referrer_ids))
        )
        for u in ref_result.scalars().all():
            referrer_map[u.id] = u

    # Batch-fetch buyer PRE_NDA/NDA users (to compute buyer_nda_status)
    buyer_emails = [
        r.contact_email for r in requests
        if getattr(r, "request_flow", "buyer") == "buyer"
    ]
    buyer_user_map: dict = {}
    if buyer_emails:
        bu_result = await db.execute(
            select(User).where(User.email.in_(buyer_emails), User.role.in_([UserRole.PRE_NDA, UserRole.NDA]))
        )
        for u in bu_result.scalars().all():
            buyer_user_map[u.email.lower()] = u

    def _build_request_dict(r: ContactRequest) -> dict:
        d = {
            "id": str(r.id),
            "entity_name": r.entity_name,
            "contact_email": r.contact_email,
            "contact_name": r.contact_name,
            "contact_first_name": r.contact_first_name,
            "contact_last_name": r.contact_last_name,
            "position": r.position,
            "nda_file_name": r.nda_file_name,
            "submitter_ip": r.submitter_ip,
            "user_role": r.user_role.value if r.user_role else "NDA",
            "request_flow": getattr(r, "request_flow", "buyer"),
            "notes": r.notes,
            "created_at": (r.created_at.isoformat() + "Z") if r.created_at else None,
        }
        if d["request_flow"] == "introducer":
            intro_user = introducer_user_map.get(r.contact_email)
            if intro_user:
                if intro_user.nda_file_data:
                    d["introducer_nda_status"] = "uploaded"
                    d["introducer_user_id"] = str(intro_user.id)
                else:
                    d["introducer_nda_status"] = "sent"
                    d["introducer_user_id"] = str(intro_user.id)
            elif r.nda_file_name:
                # NDA was uploaded with the initial form submission
                d["introducer_nda_status"] = "attached"
            else:
                d["introducer_nda_status"] = "not_sent"

        # Always include referred_by info and nda_accepted
        if r.referred_by_user_id:
            d["referred_by_user_id"] = str(r.referred_by_user_id)
            referrer = referrer_map.get(r.referred_by_user_id)
            if referrer:
                d["introducer_name"] = f"{referrer.first_name or ''} {referrer.last_name or ''}".strip()
        if r.referral_code_used:
            d["referral_code_used"] = r.referral_code_used
        d["nda_accepted"] = bool(r.nda_accepted)

        # Buyer NDA status (for buyer requests)
        if d["request_flow"] == "buyer":
            buyer_user = buyer_user_map.get(r.contact_email.lower())
            if r.user_role == ContactStatus.PRE_NDA:
                if buyer_user:
                    d["buyer_nda_status"] = "sent"
                    d["buyer_user_id"] = str(buyer_user.id)
                else:
                    d["buyer_nda_status"] = "not_sent"
            elif r.user_role == ContactStatus.NDA:
                if r.nda_file_data:
                    d["buyer_nda_status"] = "attached"  # NDA uploaded with form
                elif buyer_user and buyer_user.nda_file_data:
                    d["buyer_nda_status"] = "uploaded"  # User uploaded after send-nda
                    d["buyer_user_id"] = str(buyer_user.id)
                else:
                    d["buyer_nda_status"] = "no_nda"

        return d

    return {
        "data": [_build_request_dict(r) for r in requests],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
        },
    }


@router.put("/contact-requests/{request_id}")
async def update_contact_request(
    request_id: str,
    update: ContactRequestUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update a contact request status or notes.
    """
    from uuid import UUID

    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == req_uuid)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact request not found")

    if update.status:
        new_status = ContactStatus(update.status)
        contact.user_role = new_status
        # When rejecting NDA, also set linked user to REJECTED if one exists (created from this request)
        if new_status == ContactStatus.REJECTED:
            user_result = await db.execute(
                select(User).where(User.email == contact.contact_email)
            )
            linked_user = user_result.scalar_one_or_none()
            if linked_user:
                linked_user.role = UserRole.REJECTED
    if update.notes:
        contact.notes = update.notes
    if update.agent_id:
        contact.agent_id = update.agent_id

    try:
        await db.commit()
        await db.refresh(contact)
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "updating contact request", logger) from e

    # Broadcast contact request update to backoffice
    asyncio.create_task(
        backoffice_ws_manager.broadcast(
            "request_updated",
            {
                "id": str(contact.id),
                "entity_name": contact.entity_name,
                "contact_email": contact.contact_email,
                "contact_name": contact.contact_name,
                "position": contact.position,
                "nda_file_name": contact.nda_file_name,
                "submitter_ip": contact.submitter_ip,
                "user_role": contact.user_role.value if contact.user_role else "NDA",
                "request_flow": getattr(contact, "request_flow", "buyer"),
                "notes": contact.notes,
                "created_at": (contact.created_at.isoformat() + "Z")
                if contact.created_at
                else None,
            },
        )
    )

    return {"message": "Contact request updated", "success": True}


@router.delete("/contact-requests/{request_id}")
async def delete_contact_request(
    request_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Delete a contact request permanently.
    Admin only.
    """
    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == req_uuid)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact request not found")

    await db.delete(contact)
    await db.commit()

    # Broadcast deletion to backoffice WebSocket
    asyncio.create_task(
        backoffice_ws_manager.broadcast("request_deleted", {"id": str(request_id)})
    )

    return {"message": "Contact request deleted", "success": True}


@router.post("/users/create-from-request")
async def create_user_from_contact_request(
    request_id: str = Query(..., description="Contact request ID"),  # noqa: B008
    email: str = Query(..., description="User email"),  # noqa: B008
    first_name: str = Query(..., description="First name"),  # noqa: B008
    last_name: str = Query(..., description="Last name"),  # noqa: B008
    mode: str = Query(..., description="Creation mode: 'manual' or 'invitation'"),  # noqa: B008
    password: Optional[str] = Query(  # noqa: B008
        None, description="Password (required for manual mode)"
    ),
    position: Optional[str] = Query(None, description="Position/title"),  # noqa: B008
    target_role: Optional[str] = Query(  # noqa: B008
        "KYC", description="Target role: 'KYC' (buyer flow, creates Entity) or 'INTRODUCER' (no Entity)"
    ),
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a new user from an approved contact request.
    Supports two modes:
    - 'manual': Admin provides password (required, ≥8 chars), user active immediately.
    - 'invitation': Send email invitation after commit; user sets password via link (MailConfig for expiry).
    Creates Entity (name from contact_request, jurisdiction OTHER, KYC PENDING), User (role KYC), sets contact_request.status = KYC. Broadcasts request_updated and user_created on backoffice WebSocket.
    Admin only. All parameters are Query params.
    Returns: { message, success: true, user: { id, email, first_name, last_name, role, entity_id, creation_method } }.
    Errors: 400 (invalid request_id, duplicate email, password validation), 404 (contact request not found), 400/409/500 from handle_database_error (optional details.hint).
    """
    # Validate request_id as UUID
    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    # Get contact request
    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == req_uuid)
    )
    contact_request = result.scalar_one_or_none()
    if not contact_request:
        raise HTTPException(status_code=404, detail="Contact request not found")

    # For buyer requests with NDA: require nda_accepted before creating user
    if (
        contact_request.request_flow == "buyer"
        and contact_request.user_role == ContactStatus.NDA
        and not contact_request.nda_accepted
    ):
        raise HTTPException(
            status_code=400,
            detail="NDA must be accepted before creating user. Review the NDA document first.",
        )

    # Check if user already exists
    existing_result = await db.execute(select(User).where(User.email == email.lower()))
    existing_user = existing_result.scalar_one_or_none()

    if existing_user and existing_user.role not in (UserRole.PRE_NDA, UserRole.NDA):
        raise HTTPException(
            status_code=400, detail="User with this email already exists"
        )

    # Load mail config for invitation expiry (and later for sending)
    cfg_result = await db.execute(
        select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
    )
    mail_row = cfg_result.scalar_one_or_none()
    invitation_expiry_days = (
        mail_row.invitation_token_expiry_days
        if mail_row and mail_row.invitation_token_expiry_days is not None
        else 7
    )

    is_introducer = (target_role or "KYC").upper() == "INTRODUCER"
    entity_id_val = None

    try:
        if not is_introducer:
            # Create entity from contact request (buyer flow)
            entity = Entity(
                name=contact_request.entity_name,
                jurisdiction=Jurisdiction.OTHER,
                kyc_status=KYCStatus.PENDING,
            )
            db.add(entity)
            await db.flush()
            entity_id_val = entity.id

        user_role_val = UserRole.INTRODUCER if is_introducer else UserRole.KYC

        if existing_user and existing_user.role in (UserRole.PRE_NDA, UserRole.NDA):
            # Upgrade existing PRE_NDA/NDA user to KYC
            existing_user.role = user_role_val
            existing_user.entity_id = entity_id_val
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            existing_user.position = position
            existing_user.nda_signed = True
            if mode == "manual" and password:
                existing_user.password_hash = hash_password(password)
                existing_user.must_change_password = False
                existing_user.is_active = True
            elif mode == "invitation":
                # Generate fresh token so invitation email has a valid link
                existing_user.invitation_token = secrets.token_urlsafe(32)
                existing_user.invitation_sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                existing_user.invitation_expires_at = (
                    datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=invitation_expiry_days)
                )
                existing_user.must_change_password = True
                existing_user.is_active = False
            else:
                existing_user.is_active = True
            user = existing_user
        else:
            if mode == "manual":
                if not password or len(password) < 8:
                    raise HTTPException(
                        status_code=400,
                        detail="Password required and must be at least 8 characters",
                    )

                user = User(
                    email=email.lower(),
                    first_name=first_name,
                    last_name=last_name,
                    password_hash=hash_password(password),
                    role=user_role_val,
                    entity_id=entity_id_val,
                    position=position,
                    must_change_password=False,
                    is_active=True,
                    creation_method="manual",
                    created_by=admin_user.id,
                )
            else:
                invitation_token = secrets.token_urlsafe(32)
                user = User(
                    email=email.lower(),
                    first_name=first_name,
                    last_name=last_name,
                    role=user_role_val,
                    entity_id=entity_id_val,
                    position=position,
                    invitation_token=invitation_token,
                    invitation_sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    invitation_expires_at=(
                        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=invitation_expiry_days)
                    ),
                    must_change_password=True,
                    is_active=False,
                    creation_method="invitation",
                    created_by=admin_user.id,
                )

            db.add(user)

        # Generate referral code for INTRODUCER users
        if is_introducer:
            from ...services.referral_codes import get_unique_referral_code

            user.referral_code = await get_unique_referral_code(db)
            user.nda_signed = contact_request.nda_file_data is not None
            user.commission_rate = Decimal("0.010000")  # Default 1%

        # Update contact request user_role to KYC (approved, user created)
        contact_request.user_role = ContactStatus.KYC

        await db.commit()
        await db.refresh(user)
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "create user from contact request", logger) from e

    # Update referral invitation status if this user was referred
    if contact_request.referred_by_user_id:
        try:
            from ...services.invitation_service import mark_invitation_registered

            await mark_invitation_registered(db, contact_request.contact_email, user.id)
            await db.commit()
        except Exception:
            logger.warning(
                "Failed to mark invitation registered for %s (non-blocking)",
                contact_request.contact_email,
            )

    # Send invitation email if applicable
    if mode == "invitation":
        try:
            mail_cfg = None
            if mail_row:
                mail_cfg = {
                    "provider": mail_row.provider.value,
                    "use_env_credentials": mail_row.use_env_credentials,
                    "from_email": mail_row.from_email,
                    "resend_api_key": (
                        mail_row.resend_api_key
                        if not mail_row.use_env_credentials
                        and mail_row.provider == MailProvider.RESEND
                        else None
                    ),
                    "smtp_host": mail_row.smtp_host,
                    "smtp_port": mail_row.smtp_port,
                    "smtp_use_tls": mail_row.smtp_use_tls,
                    "smtp_username": mail_row.smtp_username,
                    "smtp_password": mail_row.smtp_password,
                    "invitation_subject": mail_row.invitation_subject,
                    "invitation_body_html": mail_row.invitation_body_html,
                    "invitation_link_base_url": mail_row.invitation_link_base_url,
                }
            await email_service.send_invitation(
                user.email, user.first_name, user.invitation_token, mail_config=mail_cfg
            )
        except Exception:
            logger.exception(
                "Failed to send invitation email for user %s "
                "(user created, contact request KYC)",
                user.email,
            )

    # Broadcast updates (full payload so realtime hook can replace list item)
    asyncio.create_task(
        backoffice_ws_manager.broadcast(
            "request_updated",
            {
                "id": str(contact_request.id),
                "entity_name": contact_request.entity_name,
                "contact_email": contact_request.contact_email,
                "contact_name": contact_request.contact_name,
                "contact_first_name": contact_request.contact_first_name,
                "contact_last_name": contact_request.contact_last_name,
                "position": contact_request.position,
                "nda_file_name": contact_request.nda_file_name,
                "submitter_ip": contact_request.submitter_ip,
                "user_role": contact_request.user_role.value if contact_request.user_role else "NDA",
                "request_flow": getattr(contact_request, "request_flow", "buyer"),
                "notes": contact_request.notes,
                "created_at": (contact_request.created_at.isoformat() + "Z")
                if contact_request.created_at
                else None,
            },
        )
    )
    asyncio.create_task(
        backoffice_ws_manager.broadcast(
            "user_created",
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value,  # KYC
            },
        )
    )

    return {
        "message": f"User created successfully via {mode}",
        "success": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "entity_id": str(entity_id_val) if entity_id_val else None,
            "creation_method": mode,
        },
    }


@router.get("/contact-requests/{request_id}/nda")
async def download_nda_file(
    request_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Download NDA file for a contact request.
    Serves PDF from database binary storage.
    Admin only.
    """
    try:
        req_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == req_uuid)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact request not found")

    # Check for binary data in database (new storage method)
    if contact.nda_file_data:
        from urllib.parse import quote

        fname = contact.nda_file_name or "nda.pdf"
        ascii_fname = fname.encode("ascii", "replace").decode("ascii")
        utf8_fname = quote(fname)
        return Response(
            content=contact.nda_file_data,
            media_type=contact.nda_file_mime_type or "application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{ascii_fname}\"; filename*=UTF-8''{utf8_fname}"
            },
        )

    # Fallback to filesystem for legacy records
    if contact.nda_file_path and contact.nda_file_name:
        if os.path.exists(contact.nda_file_path):
            return FileResponse(
                path=contact.nda_file_path,
                filename=contact.nda_file_name,
                media_type="application/pdf",
            )

    raise HTTPException(status_code=404, detail="No NDA file attached to this request")


@router.get("/users/{user_id}/nda")
async def download_user_nda(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Download NDA file uploaded by a user (stored on User model). Admin only."""
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.nda_file_data:
        raise HTTPException(status_code=404, detail="No NDA file uploaded")

    from urllib.parse import quote

    filename = user.nda_file_name or "nda.pdf"
    # RFC 5987: use ASCII fallback + UTF-8 encoded filename for non-ASCII chars
    ascii_filename = filename.encode("ascii", "replace").decode("ascii")
    utf8_filename = quote(filename)
    return Response(
        content=user.nda_file_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"
        },
    )


@router.get("/ip-lookup/{ip_address}")
async def ip_whois_lookup(
    ip_address: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
):
    """
    Perform WHOIS/GeoIP lookup for an IP address.
    Uses ip-api.com (free tier, no API key needed).
    Admin only.
    """
    # Validate IP address format (basic check)
    if not ip_address or ip_address in ["None", "null", ""]:
        raise HTTPException(status_code=400, detail="Invalid IP address")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://ip-api.com/json/{ip_address}",
                params={
                    "fields": (
                        "status,message,country,countryCode,region,regionName,"
                        "city,zip,lat,lon,timezone,isp,org,as,query"
                    )
                },
            )
            data = response.json()

        if data.get("status") == "fail":
            raise HTTPException(
                status_code=400, detail=data.get("message", "IP lookup failed")
            )

        return {
            "ip": data.get("query"),
            "country": data.get("country"),
            "country_code": data.get("countryCode"),
            "region": data.get("regionName"),
            "city": data.get("city"),
            "zip": data.get("zip"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "timezone": data.get("timezone"),
            "isp": data.get("isp"),
            "org": data.get("org"),
            "as": data.get("as"),
        }
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="IP lookup timed out") from e
    except Exception as e:
        raise HTTPException(
            status_code=502, detail="IP lookup service unavailable. Please try again later."
        ) from e


@router.get("/dashboard")
async def get_admin_dashboard(
    _admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get admin dashboard statistics.
    """
    # Contact requests by user_role
    new_contacts = await db.execute(
        select(func.count())
        .select_from(ContactRequest)
        .where(ContactRequest.user_role == ContactStatus.NDA)
    )
    new_count = new_contacts.scalar()

    total_contacts = await db.execute(select(func.count()).select_from(ContactRequest))
    total_count = total_contacts.scalar()

    # Entities count
    entities_result = await db.execute(select(func.count()).select_from(Entity))
    entities_count = entities_result.scalar()

    # Users count
    users_result = await db.execute(select(func.count()).select_from(User))
    users_count = users_result.scalar()

    return {
        "contact_requests": {"new": new_count, "total": total_count},
        "entities": entities_count,
        "users": users_count,
        "recent_activity": [],  # Would include recent trades, logins, etc.
    }


@router.get("/entities")
async def get_entities(
    _admin_user: User = Depends(get_admin_user),  # noqa: B008
    kyc_status: Optional[str] = None,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(20, ge=1, le=100),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all registered entities with optional KYC filter.
    """
    query = select(Entity).order_by(Entity.created_at.desc())

    if kyc_status:
        query = query.where(Entity.kyc_status == kyc_status)

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    entities = result.scalars().all()

    return {
        "data": [
            {
                "id": str(e.id),
                "name": e.name,
                "legal_name": e.legal_name,
                "jurisdiction": e.jurisdiction.value,
                "verified": e.verified,
                "kyc_status": e.kyc_status.value,
                "created_at": e.created_at.isoformat(),
            }
            for e in entities
        ]
    }


@router.put("/entities/{entity_id}/kyc")
async def update_entity_kyc(
    entity_id: str,
    kyc_status: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update entity KYC status.
    Admin only.
    """
    from ...models.models import KYCStatus

    result = await db.execute(select(Entity).where(Entity.id == UUID(entity_id)))
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity.kyc_status = KYCStatus(kyc_status)
    if kyc_status == "approved":
        entity.verified = True
        # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
        entity.kyc_approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        entity.kyc_approved_by = admin_user.id

    await db.commit()

    return {"message": "Entity KYC status updated", "success": True}


# ==================== User Management ====================


@router.get("/users")
async def get_users(
    role: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(20, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get users with optional filters.
    Admin only. By default returns only active users. Use role=DISABLED to list
    deactivated users (soft-deleted; kept for ticketing, transactions, etc.).
    Excludes Market Maker users (they have their own management page).
    """
    # Subquery to find user IDs that are Market Makers
    mm_user_ids = select(MarketMakerClient.user_id).where(
        MarketMakerClient.user_id.isnot(None)
    ).scalar_subquery()

    if role == "DISABLED":
        query = select(User).where(
            User.is_active.is_(False),
            User.id.notin_(mm_user_ids)
        ).order_by(User.created_at.desc())
        count_query = select(func.count()).select_from(User).where(
            User.is_active.is_(False),
            User.id.notin_(mm_user_ids)
        )
    else:
        query = select(User).where(
            User.is_active.is_(True),
            User.id.notin_(mm_user_ids)
        ).order_by(User.created_at.desc())
        count_query = select(func.count()).select_from(User).where(
            User.is_active.is_(True),
            User.id.notin_(mm_user_ids)
        )
        if role:
            query = query.where(User.role == UserRole(role))
            count_query = count_query.where(User.role == UserRole(role))

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term))
            | (User.first_name.ilike(search_term))
            | (User.last_name.ilike(search_term))
        )
        count_query = count_query.where(
            (User.email.ilike(search_term))
            | (User.first_name.ilike(search_term))
            | (User.last_name.ilike(search_term))
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    users = result.scalars().all()

    # Get entity names and approval timestamps
    user_list = []
    for user in users:
        entity_name = None
        kyc_approved_at = None
        if user.entity_id:
            entity_result = await db.execute(
                select(Entity).where(Entity.id == user.entity_id)
            )
            entity = entity_result.scalar_one_or_none()
            if entity:
                entity_name = entity.name
                kyc_approved_at = (
                    entity.kyc_approved_at.isoformat()
                    if entity.kyc_approved_at
                    else None
                )

        user_data = UserResponse.model_validate(user).model_dump()
        user_data["entity_name"] = entity_name
        user_data["kyc_approved_at"] = kyc_approved_at
        user_list.append(user_data)

    return {
        "data": user_list,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
        },
    }


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a new user with password or send invitation email.
    Admin only.
    If password is provided, user is created with that password.
    If password is not provided, an invitation email is sent.

    Note: For roles that require an entity (APPROVED and higher), an entity
    will be auto-created if entity_id is not provided.
    """
    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == user_data.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="User with this email already exists"
        )

    # Roles that need an entity to report deposits
    ROLES_REQUIRING_ENTITY = {
        UserRole.APPROVED, UserRole.FUNDING, UserRole.AML,
        UserRole.CEA, UserRole.CEA_SETTLE, UserRole.SWAP,
        UserRole.EUA_SETTLE, UserRole.EUA, UserRole.MM,
    }

    entity_id = user_data.entity_id

    # Auto-create entity for roles that require it
    if user_data.role in ROLES_REQUIRING_ENTITY and not entity_id:
        entity = Entity(
            name=f"{user_data.first_name} {user_data.last_name}",
            jurisdiction=Jurisdiction.OTHER,
            kyc_status=KYCStatus.APPROVED if user_data.role == UserRole.APPROVED else KYCStatus.PENDING,
        )
        db.add(entity)
        await db.flush()
        entity_id = entity.id

    # Auto-generate referral code for PREINTRODUCER and TRODUCER
    referral_code = None
    if user_data.role in (UserRole.PREINTRODUCER, UserRole.TRODUCER):
        from ...services.referral_codes import get_unique_referral_code
        referral_code = await get_unique_referral_code(db)

    # TRODUCER/INTRODUCER created by admin: mark NDA as signed (no NDA required)
    nda_signed = user_data.role in (UserRole.TRODUCER, UserRole.INTRODUCER)

    # Create user with or without password
    if user_data.password:
        # Create user with password directly
        user = User(
            email=user_data.email.lower(),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            password_hash=hash_password(user_data.password),
            role=user_data.role,
            entity_id=entity_id,
            position=user_data.position,
            referral_code=referral_code,
            nda_signed=nda_signed,
            must_change_password=False,  # Password already set by admin
            is_active=True,
        )
    else:
        # Generate invitation token for email invite
        invitation_token = secrets.token_urlsafe(32)
        user = User(
            email=user_data.email.lower(),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            entity_id=entity_id,
            position=user_data.position,
            referral_code=referral_code,
            nda_signed=nda_signed,
            invitation_token=invitation_token,
            # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
            invitation_sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
            must_change_password=True,
        )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send welcome email to TRODUCER when created with a password
    if user_data.password and user_data.role == UserRole.TRODUCER:
        cfg_result = await db.execute(
            select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
        )
        mail_row = cfg_result.scalar_one_or_none()
        mail_cfg = None
        if mail_row:
            mail_cfg = {
                "provider": mail_row.provider.value,
                "use_env_credentials": mail_row.use_env_credentials,
                "from_email": mail_row.from_email,
                "resend_api_key": (
                    mail_row.resend_api_key
                    if not mail_row.use_env_credentials
                    and mail_row.provider == MailProvider.RESEND
                    else None
                ),
                "smtp_host": mail_row.smtp_host,
                "smtp_port": mail_row.smtp_port,
                "smtp_use_tls": mail_row.smtp_use_tls,
                "smtp_username": mail_row.smtp_username,
                "smtp_password": mail_row.smtp_password,
                "invitation_link_base_url": mail_row.invitation_link_base_url,
            }
        try:
            await email_service.send_troducer_welcome(user.email, user.first_name, mail_config=mail_cfg)
        except Exception:
            logger.exception("Failed to send welcome email to TRODUCER %s", user.email)

    # Send invitation email only if no password was provided
    if not user_data.password:
        # Load mail config so emails use the correct URL and credentials
        cfg_result = await db.execute(
            select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
        )
        mail_row = cfg_result.scalar_one_or_none()
        mail_cfg = None
        if mail_row:
            mail_cfg = {
                "provider": mail_row.provider.value,
                "use_env_credentials": mail_row.use_env_credentials,
                "from_email": mail_row.from_email,
                "resend_api_key": (
                    mail_row.resend_api_key
                    if not mail_row.use_env_credentials
                    and mail_row.provider == MailProvider.RESEND
                    else None
                ),
                "smtp_host": mail_row.smtp_host,
                "smtp_port": mail_row.smtp_port,
                "smtp_use_tls": mail_row.smtp_use_tls,
                "smtp_username": mail_row.smtp_username,
                "smtp_password": mail_row.smtp_password,
                "invitation_link_base_url": mail_row.invitation_link_base_url,
            }
        try:
            if user_data.role == UserRole.TRODUCER:
                invitation_expiry_days = (
                    mail_row.invitation_token_expiry_days
                    if mail_row and mail_row.invitation_token_expiry_days is not None
                    else 14
                )
                nda_pdf_path = os.path.join(
                    os.path.dirname(__file__), "..", "..", "..", "uploads", "nda", "NDA-Niha-signed.pdf"
                )
                await email_service.send_introducer_nda_invitation(
                    user.email, user.first_name, user.invitation_token,
                    nda_pdf_path, expiry_days=invitation_expiry_days, mail_config=mail_cfg,
                )
            else:
                await email_service.send_invitation(
                    user.email, user.first_name, user.invitation_token, mail_config=mail_cfg,
                )
        except Exception:
            logger.exception("Failed to send invitation email to %s", user.email)

    return UserResponse.model_validate(user)


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get user details by ID.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get entity info
    entity_name = None
    if user.entity_id:
        entity_result = await db.execute(
            select(Entity).where(Entity.id == user.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            entity_name = entity.name

    user_data = UserResponse.model_validate(user).model_dump()
    user_data["entity_name"] = entity_name

    return user_data


@router.put("/users/{user_id}/role", response_model=MessageResponse)
async def change_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Change a user's role.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    old_role = user.role.value
    user.role = role_update.role

    # ── Auto-settle pending batches when crossing settlement gates ──
    batches_settled = 0
    if user.entity_id:
        role_order = [
            "NDA", "KYC", "APPROVED", "FUNDING", "AML",
            "CEA", "CEA_SETTLE", "SWAP", "EUA_SETTLE", "EUA",
        ]
        old_idx = role_order.index(old_role) if old_role in role_order else -1
        new_idx = role_order.index(role_update.role.value) if role_update.role.value in role_order else -1

        cea_settle_idx = role_order.index("CEA_SETTLE")  # 6
        eua_settle_idx = role_order.index("EUA_SETTLE")  # 8

        settlement_gates: list[tuple[int, SettlementType]] = []

        # Crossing past CEA_SETTLE → settle CEA_PURCHASE batches
        if old_idx <= cea_settle_idx < new_idx:
            settlement_gates.append((cea_settle_idx, SettlementType.CEA_PURCHASE))

        # Crossing past EUA_SETTLE → settle SWAP_CEA_TO_EUA batches
        if old_idx <= eua_settle_idx < new_idx:
            settlement_gates.append((eua_settle_idx, SettlementType.SWAP_CEA_TO_EUA))

        for _gate_idx, stype in settlement_gates:
            pending_r = await db.execute(
                select(SettlementBatch).where(
                    SettlementBatch.entity_id == user.entity_id,
                    SettlementBatch.settlement_type == stype,
                    SettlementBatch.status.notin_([
                        SettlementStatus.SETTLED, SettlementStatus.FAILED,
                    ]),
                )
            )
            for batch in pending_r.scalars().all():
                batch.status = SettlementStatus.SETTLED
                batch.actual_settlement_date = datetime.now(timezone.utc).replace(tzinfo=None)
                batch.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.add(SettlementStatusHistory(
                    settlement_batch_id=batch.id,
                    status=SettlementStatus.SETTLED,
                    notes=f"Auto-settled: admin advanced role from {old_role} to {role_update.role.value}",
                    updated_by=admin_user.id,
                ))
                batches_settled += 1

    await db.commit()

    # Notify the affected client so their UI updates immediately
    asyncio.create_task(client_ws_manager.broadcast_to_users(
        [UUID(user_id)],
        {"type": "role_updated", "data": {"role": role_update.role.value, "old_role": old_role}},
    ))

    msg = f"User role changed from {old_role} to {role_update.role.value}"
    if batches_settled:
        msg += f" ({batches_settled} settlement batch{'es' if batches_settled > 1 else ''} auto-settled)"
    return MessageResponse(message=msg)


class BulkRoleChangeRequest(BaseModel):
    user_ids: list[str] = Field(..., min_length=1, max_length=50)
    role: UserRole


@router.post("/users/bulk-role-change", response_model=MessageResponse)
async def bulk_change_role(
    payload: BulkRoleChangeRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Change role for multiple users at once. Admin only. Max 50 users per request."""
    changed = 0
    skipped = 0
    for uid in payload.user_ids:
        try:
            result = await db.execute(select(User).where(User.id == UUID(uid)))
            user = result.scalar_one_or_none()
            if not user or user.id == admin_user.id or user.role == payload.role:
                skipped += 1
                continue
            user.role = payload.role
            changed += 1
        except Exception:
            skipped += 1

    await db.commit()
    return MessageResponse(
        message=f"Bulk role change complete: {changed} updated, {skipped} skipped"
    )


@router.post("/users/bulk-deactivate", response_model=MessageResponse)
async def bulk_deactivate(
    payload: BulkRoleChangeRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate multiple users at once. Admin only."""
    deactivated = 0
    skipped = 0
    for uid in payload.user_ids:
        try:
            result = await db.execute(select(User).where(User.id == UUID(uid)))
            user = result.scalar_one_or_none()
            if not user or user.id == admin_user.id or not user.is_active:
                skipped += 1
                continue
            user.is_active = False
            deactivated += 1
        except Exception:
            skipped += 1

    await db.commit()
    return MessageResponse(
        message=f"Bulk deactivate complete: {deactivated} deactivated, {skipped} skipped"
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Deactivate a user account.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin_user.id:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    user.is_active = False
    await db.commit()

    # Force-logout the deactivated user immediately
    asyncio.create_task(client_ws_manager.broadcast_to_users(
        [UUID(user_id)],
        {"type": "user_deactivated", "data": {}},
    ))

    return MessageResponse(message=f"User {user.email} has been deactivated")


@router.get("/users/{user_id}/full", response_model=AdminUserFullResponse)
async def get_user_full_details(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get comprehensive user details including auth history and stats.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get entity name
    entity_name = None
    if user.entity_id:
        entity_result = await db.execute(
            select(Entity).where(Entity.id == user.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            entity_name = entity.name

    # Get auth attempts
    auth_query = (
        select(AuthenticationAttempt)
        .where(AuthenticationAttempt.email == user.email)
        .order_by(AuthenticationAttempt.created_at.desc())
        .limit(50)
    )
    auth_result = await db.execute(auth_query)
    auth_attempts = auth_result.scalars().all()

    # Count total logins
    login_count_result = await db.execute(
        select(func.count())
        .select_from(AuthenticationAttempt)
        .where(AuthenticationAttempt.email == user.email)
        .where(AuthenticationAttempt.success.is_(True))
    )
    login_count = login_count_result.scalar() or 0

    # Get last login IP
    last_login_ip = None
    if auth_attempts:
        for attempt in auth_attempts:
            if attempt.success and attempt.ip_address:
                last_login_ip = attempt.ip_address
                break

    # Failed logins in last 24h - use naive UTC for DB query
    yesterday = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    failed_24h_result = await db.execute(
        select(func.count())
        .select_from(AuthenticationAttempt)
        .where(AuthenticationAttempt.email == user.email)
        .where(AuthenticationAttempt.success.is_(False))
        .where(AuthenticationAttempt.created_at >= yesterday)
    )
    failed_login_count_24h = failed_24h_result.scalar() or 0

    # Get sessions
    sessions_query = (
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.started_at.desc())
        .limit(20)
    )
    sessions_result = await db.execute(sessions_query)
    sessions = sessions_result.scalars().all()

    return AdminUserFullResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        position=user.position,
        phone=user.phone,
        role=user.role.value,
        entity_id=user.entity_id,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        last_login=user.last_login,
        created_at=user.created_at,
        entity_name=entity_name,
        password_set=user.password_hash is not None,
        login_count=login_count,
        last_login_ip=last_login_ip,
        failed_login_count_24h=failed_login_count_24h,
        sessions=[UserSessionResponse.model_validate(s) for s in sessions],
        auth_history=[
            AuthenticationAttemptResponse.model_validate(a) for a in auth_attempts
        ],
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_full(
    user_id: str,
    update: AdminUserUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update any user field.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check email uniqueness if changing email
    if update.email and update.email.lower() != user.email:
        existing = await db.execute(
            select(User).where(User.email == update.email.lower())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="Email already in use by another user"
            )
        user.email = update.email.lower()

    if update.first_name is not None:
        user.first_name = update.first_name
    if update.last_name is not None:
        user.last_name = update.last_name
    if update.position is not None:
        user.position = update.position
    if update.phone is not None:
        user.phone = update.phone
    if update.role is not None:
        if user.id == admin_user.id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        user.role = update.role
    if update.is_active is not None:
        if user.id == admin_user.id and not update.is_active:
            raise HTTPException(
                status_code=400, detail="Cannot deactivate your own account"
            )
        user.is_active = update.is_active
    if update.entity_id is not None:
        # Verify entity exists
        entity_result = await db.execute(
            select(Entity).where(Entity.id == update.entity_id)
        )
        if not entity_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Entity not found")
        user.entity_id = update.entity_id

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/create-entity", response_model=MessageResponse)
async def create_entity_for_user(
    user_id: str,
    entity_name: Optional[str] = Query(None, description="Entity name (defaults to user's full name)"),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create and link an entity for a user who doesn't have one.
    This is useful for users created directly without going through contact request flow.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.entity_id:
        # Already has entity
        entity_result = await db.execute(
            select(Entity).where(Entity.id == user.entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        return MessageResponse(
            message=f"User already has entity: {entity.name if entity else 'unknown'}"
        )

    # Create new entity
    name = entity_name or f"{user.first_name} {user.last_name}"
    entity = Entity(
        name=name,
        jurisdiction=Jurisdiction.OTHER,
        kyc_status=KYCStatus.APPROVED,  # If user is APPROVED, entity should be too
    )
    db.add(entity)
    await db.flush()

    user.entity_id = entity.id
    await db.commit()

    return MessageResponse(message=f"Created entity '{name}' and linked to user")


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def admin_reset_password(
    user_id: str,
    reset: AdminPasswordReset,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Reset a user's password.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(reset.new_password)
    user.must_change_password = reset.force_change

    await db.commit()

    return MessageResponse(
        message=(
            f"Password reset for {user.email}. "
            f"Force change on login: {reset.force_change}"
        )
    )


@router.get("/users/{user_id}/auth-history")
async def get_user_auth_history(
    user_id: str,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get authentication history for a specific user.
    Admin only.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count total
    count_query = (
        select(func.count())
        .select_from(AuthenticationAttempt)
        .where(AuthenticationAttempt.email == user.email)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated auth attempts
    offset = (page - 1) * per_page
    auth_query = (
        select(AuthenticationAttempt)
        .where(AuthenticationAttempt.email == user.email)
        .order_by(AuthenticationAttempt.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    auth_result = await db.execute(auth_query)
    auth_attempts = auth_result.scalars().all()

    return {
        "data": [
            {
                "id": str(a.id),
                "user_id": str(a.user_id) if a.user_id else None,
                "email": a.email,
                "success": a.success,
                "method": a.method.value,
                "ip_address": a.ip_address,
                "user_agent": a.user_agent,
                "failure_reason": a.failure_reason,
                "created_at": a.created_at.isoformat(),
            }
            for a in auth_attempts
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
        },
    }


# ==================== Activity Logs ====================


@router.get("/activity-logs")
async def get_activity_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get activity logs with optional filters.
    Admin only.
    """
    query = select(ActivityLog).order_by(ActivityLog.created_at.desc())

    if user_id:
        query = query.where(ActivityLog.user_id == UUID(user_id))
    if action:
        query = query.where(ActivityLog.action == action)

    # Count total
    count_query = select(func.count()).select_from(ActivityLog)
    if user_id:
        count_query = count_query.where(ActivityLog.user_id == UUID(user_id))
    if action:
        count_query = count_query.where(ActivityLog.action == action)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    logs = result.scalars().all()

    # Get user info for each log
    logs_with_user = []
    for log in logs:
        user_result = await db.execute(select(User).where(User.id == log.user_id))
        user = user_result.scalar_one_or_none()

        log_data = {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "user_email": user.email if user else None,
            "action": log.action,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        logs_with_user.append(log_data)

    return {
        "data": logs_with_user,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
        },
    }


@router.get("/activity-logs/stats", response_model=ActivityStatsResponse)
async def get_activity_stats(
    admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)  # noqa: B008
):
    """
    Get activity statistics.
    Admin only.
    """
    # Total users
    total_users_result = await db.execute(select(func.count()).select_from(User))
    total_users = total_users_result.scalar()

    # Users by role
    users_by_role = {}
    for role in UserRole:
        role_count_result = await db.execute(
            select(func.count()).select_from(User).where(User.role == role)
        )
        users_by_role[role.value] = role_count_result.scalar()

    # Active sessions
    active_sessions_result = await db.execute(
        select(func.count())
        .select_from(UserSession)
        .where(UserSession.is_active.is_(True))
    )
    active_sessions = active_sessions_result.scalar()

    # Logins today - use naive UTC for DB query
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    logins_today_result = await db.execute(
        select(func.count())
        .select_from(ActivityLog)
        .where(ActivityLog.action == "login")
        .where(ActivityLog.created_at >= today_start)
    )
    logins_today = logins_today_result.scalar()

    # Average session duration (from completed sessions)
    avg_duration_result = await db.execute(
        select(func.avg(UserSession.duration_seconds)).where(
            UserSession.duration_seconds.isnot(None)
        )
    )
    avg_duration = avg_duration_result.scalar() or 0

    return ActivityStatsResponse(
        total_users=total_users,
        users_by_role=users_by_role,
        active_sessions=active_sessions,
        logins_today=logins_today,
        avg_session_duration=float(avg_duration),
    )


# ==================== Scraping Sources ====================
# CRUD + test/refresh for price-scraping sources (EUA/CEA). Consumed by Settings UI.
# See docs/api/ADMIN_SCRAPING_API.md for request/response examples.


@router.get("/scraping-sources")
async def get_scraping_sources(
    admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)  # noqa: B008
):
    """
    Get all scraping source configurations.
    Admin only.
    """
    query = select(ScrapingSource).order_by(ScrapingSource.created_at.desc())
    result = await db.execute(query)
    sources = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.url,
            "certificate_type": s.certificate_type.value,
            "scrape_library": s.scrape_library.value
            if s.scrape_library
            else ScrapeLibrary.HTTPX.value,
            "is_active": s.is_active,
            "is_primary": s.is_primary,
            "scrape_interval_minutes": s.scrape_interval_minutes,
            "last_scrape_at": (s.last_scrape_at.isoformat() + "Z")
            if s.last_scrape_at
            else None,
            "last_scrape_status": s.last_scrape_status.value
            if s.last_scrape_status
            else None,
            "last_price": float(s.last_price) if s.last_price else None,
            "last_price_eur": float(s.last_price_eur) if s.last_price_eur else None,
            "last_exchange_rate": float(s.last_exchange_rate)
            if s.last_exchange_rate
            else None,
            "config": s.config,
            "created_at": s.created_at.isoformat() + "Z",
            "updated_at": s.updated_at.isoformat() + "Z",
        }
        for s in sources
    ]


@router.post("/scraping-sources")
async def create_scraping_source(
    source_data: ScrapingSourceCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a new scraping source.
    Admin only.
    """
    source = ScrapingSource(
        name=source_data.name,
        url=source_data.url,
        certificate_type=source_data.certificate_type,
        scrape_library=source_data.scrape_library,
        scrape_interval_minutes=source_data.scrape_interval_minutes,
        config=source_data.config,
        is_active=True,
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    return {
        "id": str(source.id),
        "name": source.name,
        "url": source.url,
        "certificate_type": source.certificate_type.value,
        "scrape_library": source.scrape_library.value
        if source.scrape_library
        else ScrapeLibrary.HTTPX.value,
        "is_active": source.is_active,
        "is_primary": source.is_primary,
        "scrape_interval_minutes": source.scrape_interval_minutes,
        "last_scrape_at": source.last_scrape_at.isoformat()
        if source.last_scrape_at
        else None,
        "last_scrape_status": source.last_scrape_status.value
        if source.last_scrape_status
        else None,
        "last_price": float(source.last_price) if source.last_price else None,
        "last_price_eur": float(source.last_price_eur)
        if source.last_price_eur
        else None,
        "last_exchange_rate": float(source.last_exchange_rate)
        if source.last_exchange_rate
        else None,
        "config": source.config,
        "created_at": source.created_at.isoformat(),
        "updated_at": source.updated_at.isoformat(),
    }


@router.put("/scraping-sources/{source_id}")
async def update_scraping_source(
    source_id: str,
    update: ScrapingSourceUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update a scraping source configuration.
    Admin only.
    """
    result = await db.execute(
        select(ScrapingSource).where(ScrapingSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    # If marking as primary, unset other primary sources with same certificate_type
    if update.is_primary:
        from sqlalchemy import update as sql_update
        await db.execute(
            sql_update(ScrapingSource)
            .where(
                ScrapingSource.certificate_type == source.certificate_type,
                ScrapingSource.id != source.id,
            )
            .values(is_primary=False)
        )

    if update.name is not None:
        source.name = update.name
    if update.url is not None:
        source.url = update.url
    if update.scrape_library is not None:
        source.scrape_library = update.scrape_library
    if update.is_active is not None:
        source.is_active = update.is_active
    if update.is_primary is not None:
        source.is_primary = update.is_primary
    if update.scrape_interval_minutes is not None:
        source.scrape_interval_minutes = update.scrape_interval_minutes
    if update.config is not None:
        source.config = update.config

    # If we just unset primary, auto-promote another active source
    if update.is_primary is False:
        next_result = await db.execute(
            select(ScrapingSource)
            .where(
                ScrapingSource.certificate_type == source.certificate_type,
                ScrapingSource.is_active.is_(True),
                ScrapingSource.id != source.id,
            )
            .order_by(ScrapingSource.created_at.asc())
            .limit(1)
        )
        next_source = next_result.scalar_one_or_none()
        if next_source:
            next_source.is_primary = True

    await db.commit()

    return {"message": "Scraping source updated", "success": True}


def _scraping_error_status(e: Exception) -> tuple[int, str]:
    """Map scraping exceptions to (status_code, detail) with safe error messages."""
    err_str = str(e).lower().strip()
    # Rate limiting - return 429 with user-friendly message
    if "429" in err_str or "rate limit" in err_str or "too many requests" in err_str:
        return (429, "Rate limited by source. Please wait a few minutes before retrying.")
    if "timeout" in err_str or "timed out" in err_str:
        return (504, "Request timed out. Please try again later.")
    if "connection" in err_str or "connect" in err_str or "connection refused" in err_str:
        return (502, "Connection error. Check if the source is accessible.")
    return (500, "Scraping failed. Check URL, selectors, and network.")


@router.post("/scraping-sources/{source_id}/test")
async def test_scraping_source(
    source_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Test a scraping source by running a single scrape.
    Admin only.
    """
    from ...services.price_scraper import price_scraper

    result = await db.execute(
        select(ScrapingSource).where(ScrapingSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    try:
        price = await price_scraper.scrape_source(source)
        return {"success": True, "message": "Scrape successful", "price": price}
    except Exception as e:
        logger.exception(
            "Scraping source test failed: source_id=%s, source=%s",
            source_id,
            source.name,
        )
        status, detail = _scraping_error_status(e)
        return {"success": False, "message": detail, "price": None}


@router.post("/scraping-sources/{source_id}/refresh", response_model=MessageResponse)
async def refresh_scraping_source(
    source_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Force refresh prices from a scraping source.
    For carboncredits.com sources, refreshes all carboncredits.com sources in one request (0026).
    Admin only.
    """
    from ...services.price_scraper import price_scraper

    result = await db.execute(
        select(ScrapingSource).where(ScrapingSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    try:
        from ...services.price_scraper import is_carboncredits_url

        if source.url and is_carboncredits_url(source.url):
            # One request updates all carboncredits.com sources (0026)
            all_active = await db.execute(
                select(ScrapingSource).where(
                    ScrapingSource.is_active.is_(True),
                    ScrapingSource.url.isnot(None),
                )
            )
            carboncredits_sources = [
                s for s in all_active.scalars().all()
                if is_carboncredits_url(s.url)
            ]
            await price_scraper.refresh_carboncredits_sources(
                db, carboncredits_sources
            )
        else:
            await price_scraper.refresh_source(source, db)
        return MessageResponse(message="Prices refreshed successfully")
    except Exception as e:
        logger.exception(
            "Scraping source refresh failed: source_id=%s, source=%s",
            source_id,
            source.name,
        )
        status, detail = _scraping_error_status(e)
        raise HTTPException(status_code=status, detail=detail) from e


@router.delete("/scraping-sources/{source_id}", response_model=MessageResponse)
async def delete_scraping_source(
    source_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Delete a scraping source.
    Admin only.
    """
    result = await db.execute(
        select(ScrapingSource).where(ScrapingSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    await db.delete(source)
    await db.commit()

    return MessageResponse(
        message=f"Scraping source '{source.name}' deleted successfully"
    )


@router.get("/scraping-sources/{source_id}/history")
async def get_scraping_source_history(
    source_id: str,
    hours: int = Query(24, ge=1, le=8760),
    _admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get price history for a specific scraping source.

    For periods <= 168h (7d): returns raw data points.
    For periods > 168h: returns daily averages for performance.
    """
    result = await db.execute(
        select(ScrapingSource).where(ScrapingSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    use_daily = hours > 168

    if use_daily:
        day_col = func.date_trunc("day", PriceHistory.recorded_at)
        history_result = await db.execute(
            select(
                day_col.label("day"),
                func.avg(PriceHistory.price).label("avg_price"),
            )
            .where(
                PriceHistory.source == source.name,
                PriceHistory.recorded_at >= since,
            )
            .group_by(day_col)
            .order_by(day_col.asc())
        )
        rows = history_result.all()
        points = [
            {
                "price": round(float(row.avg_price), 4),
                "recorded_at": row.day.isoformat() + "Z",
            }
            for row in rows
        ]
    else:
        history_result = await db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.source == source.name,
                PriceHistory.recorded_at >= since,
            )
            .order_by(PriceHistory.recorded_at.asc())
        )
        records = history_result.scalars().all()
        points = [
            {
                "price": float(r.price),
                "recorded_at": r.recorded_at.isoformat() + "Z",
            }
            for r in records
        ]

    return {
        "source_id": source_id,
        "source_name": source.name,
        "certificate_type": source.certificate_type.value,
        "currency": "EUR" if source.certificate_type == CertificateType.EUA else "CNY",
        "points": points,
    }


@router.delete("/scraping-sources/{source_id}/history")
async def reset_scraping_source_history(
    source_id: str,
    _admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all price history for a scraping source and seed a single point at current price."""
    result = await db.execute(
        select(ScrapingSource).where(ScrapingSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Scraping source not found")

    try:
        # Delete all history for this source
        await db.execute(
            delete(PriceHistory).where(PriceHistory.source == source.name)
        )

        # Seed a single point at the current price (if available)
        if source.last_price is not None:
            seed = PriceHistory(
                certificate_type=source.certificate_type,
                price=source.last_price,
                currency="EUR" if source.certificate_type == CertificateType.EUA else "CNY",
                source=source.name,
            )
            db.add(seed)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"message": "Price history reset", "success": True}


# ==================== Exchange Rate Sources ====================


@router.get("/exchange-rate-sources")
async def get_exchange_rate_sources(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get all exchange rate source configurations.
    Admin only.
    """
    query = select(ExchangeRateSource).order_by(ExchangeRateSource.created_at.desc())
    result = await db.execute(query)
    sources = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "name": s.name,
            "from_currency": s.from_currency,
            "to_currency": s.to_currency,
            "url": s.url,
            "scrape_library": s.scrape_library.value
            if s.scrape_library
            else ScrapeLibrary.HTTPX.value,
            "is_active": s.is_active,
            "is_primary": s.is_primary,
            "scrape_interval_minutes": s.scrape_interval_minutes,
            "last_rate": float(s.last_rate) if s.last_rate else None,
            "last_scraped_at": (s.last_scraped_at.isoformat() + "Z")
            if s.last_scraped_at
            else None,
            "last_scrape_status": s.last_scrape_status.value
            if s.last_scrape_status
            else None,
            "config": s.config,
            "created_at": s.created_at.isoformat() + "Z",
            "updated_at": s.updated_at.isoformat() + "Z",
        }
        for s in sources
    ]


@router.post("/exchange-rate-sources")
async def create_exchange_rate_source(
    source_data: ExchangeRateSourceCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a new exchange rate source.
    Admin only.
    """
    from sqlalchemy import update

    # If marking as primary, unset other primary sources for same pair
    if source_data.is_primary:
        await db.execute(
            update(ExchangeRateSource)
            .where(
                ExchangeRateSource.from_currency == source_data.from_currency.upper(),
                ExchangeRateSource.to_currency == source_data.to_currency.upper(),
            )
            .values(is_primary=False)
        )

    source = ExchangeRateSource(
        name=source_data.name,
        from_currency=source_data.from_currency.upper(),
        to_currency=source_data.to_currency.upper(),
        url=source_data.url,
        scrape_library=source_data.scrape_library,
        scrape_interval_minutes=source_data.scrape_interval_minutes,
        is_primary=source_data.is_primary,
        config=source_data.config,
        is_active=True,
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    return {
        "id": str(source.id),
        "name": source.name,
        "from_currency": source.from_currency,
        "to_currency": source.to_currency,
        "url": source.url,
        "scrape_library": source.scrape_library.value,
        "is_active": source.is_active,
        "is_primary": source.is_primary,
        "scrape_interval_minutes": source.scrape_interval_minutes,
        "last_rate": None,
        "last_scraped_at": None,
        "last_scrape_status": None,
        "config": source.config,
        "created_at": source.created_at.isoformat() + "Z",
        "updated_at": source.updated_at.isoformat() + "Z",
    }


@router.put("/exchange-rate-sources/{source_id}")
async def update_exchange_rate_source(
    source_id: str,
    update_data: ExchangeRateSourceUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Update an exchange rate source configuration."""
    from sqlalchemy import update

    result = await db.execute(
        select(ExchangeRateSource).where(ExchangeRateSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Exchange rate source not found")

    # If marking as primary, unset other primary sources
    if update_data.is_primary:
        await db.execute(
            update(ExchangeRateSource)
            .where(
                ExchangeRateSource.from_currency == source.from_currency,
                ExchangeRateSource.to_currency == source.to_currency,
                ExchangeRateSource.id != source.id,
            )
            .values(is_primary=False)
        )

    if update_data.name is not None:
        source.name = update_data.name
    if update_data.url is not None:
        source.url = update_data.url
    if update_data.scrape_library is not None:
        source.scrape_library = update_data.scrape_library
    if update_data.is_active is not None:
        source.is_active = update_data.is_active
    if update_data.is_primary is not None:
        source.is_primary = update_data.is_primary
    if update_data.scrape_interval_minutes is not None:
        source.scrape_interval_minutes = update_data.scrape_interval_minutes
    if update_data.config is not None:
        source.config = update_data.config

    # If we just unset primary, auto-promote another active source
    if update_data.is_primary is False:
        next_result = await db.execute(
            select(ExchangeRateSource)
            .where(
                ExchangeRateSource.from_currency == source.from_currency,
                ExchangeRateSource.to_currency == source.to_currency,
                ExchangeRateSource.is_active.is_(True),
                ExchangeRateSource.id != source.id,
            )
            .order_by(ExchangeRateSource.created_at.asc())
            .limit(1)
        )
        next_source = next_result.scalar_one_or_none()
        if next_source:
            next_source.is_primary = True

    await db.commit()
    return MessageResponse(message="Exchange rate source updated successfully")


@router.post("/exchange-rate-sources/{source_id}/test")
async def test_exchange_rate_source(
    source_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Test an exchange rate source by fetching current rate."""
    from ...services.price_scraper import price_scraper

    result = await db.execute(
        select(ExchangeRateSource).where(ExchangeRateSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Exchange rate source not found")

    try:
        rate = await price_scraper.scrape_exchange_rate(source)
        return {"success": True, "message": "Rate fetched successfully", "rate": rate}
    except Exception as e:
        logger.exception("Exchange rate source test failed")
        return {"success": False, "message": str(e), "rate": None}


@router.post("/exchange-rate-sources/{source_id}/refresh")
async def refresh_exchange_rate_source(
    source_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Force refresh exchange rate from a source."""
    from ...services.price_scraper import price_scraper

    result = await db.execute(
        select(ExchangeRateSource).where(ExchangeRateSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Exchange rate source not found")

    try:
        await price_scraper.refresh_exchange_rate_source(source, db)
        return MessageResponse(message="Exchange rate refreshed successfully")
    except Exception as e:
        logger.exception("Exchange rate refresh failed")
        status_code = 408 if "timeout" in str(e).lower() else 500
        detail = "Request timed out" if status_code == 408 else "Exchange rate refresh failed"
        raise HTTPException(status_code=status_code, detail=detail) from e


@router.delete("/exchange-rate-sources/{source_id}")
async def delete_exchange_rate_source(
    source_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Delete an exchange rate source."""
    result = await db.execute(
        select(ExchangeRateSource).where(ExchangeRateSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Exchange rate source not found")

    await db.delete(source)
    await db.commit()

    return MessageResponse(
        message=f"Exchange rate source '{source.name}' deleted successfully"
    )


@router.get("/exchange-rate-sources/{source_id}/history")
async def get_exchange_rate_history(
    source_id: str,
    hours: int = Query(24, ge=1, le=168),
    _admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get exchange rate history for a specific source."""
    from ...models.models import ExchangeRateHistory

    result = await db.execute(
        select(ExchangeRateSource).where(ExchangeRateSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Exchange rate source not found")

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    history_result = await db.execute(
        select(ExchangeRateHistory)
        .where(
            ExchangeRateHistory.source == source.name,
            ExchangeRateHistory.recorded_at >= since,
        )
        .order_by(ExchangeRateHistory.recorded_at.asc())
    )
    records = history_result.scalars().all()

    return {
        "source_id": source_id,
        "source_name": source.name,
        "pair": f"{source.from_currency}/{source.to_currency}",
        "points": [
            {
                "rate": float(r.rate),
                "recorded_at": r.recorded_at.isoformat() + "Z",
            }
            for r in records
        ],
    }


@router.delete("/exchange-rate-sources/{source_id}/history")
async def reset_exchange_rate_history(
    source_id: str,
    _admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all exchange rate history for a source and seed a point at current rate."""
    from ...models.models import ExchangeRateHistory

    result = await db.execute(
        select(ExchangeRateSource).where(ExchangeRateSource.id == UUID(source_id))
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Exchange rate source not found")

    try:
        await db.execute(
            delete(ExchangeRateHistory).where(ExchangeRateHistory.source == source.name)
        )
        if source.last_rate is not None:
            seed = ExchangeRateHistory(
                from_currency=source.from_currency,
                to_currency=source.to_currency,
                rate=source.last_rate,
                source=source.name,
            )
            db.add(seed)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"message": "Exchange rate history reset", "success": True}


# ==================== Mail & Auth Settings ====================


@router.get("/settings/mail")
async def get_mail_settings(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get mail (and invitation) configuration. Single row; returns defaults/empty if none.
    Admin only. API key and SMTP password are never returned (masked).
    """
    result = await db.execute(
        select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {
            "id": None,
            "provider": "resend",
            "use_env_credentials": True,
            "from_email": "",
            "resend_api_key": None,
            "smtp_host": None,
            "smtp_port": None,
            "smtp_use_tls": True,
            "smtp_username": None,
            "smtp_password": None,
            "invitation_subject": None,
            "invitation_body_html": None,
            "invitation_link_base_url": None,
            "invitation_token_expiry_days": 7,
            "verification_method": None,
            "auth_method": None,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": str(row.id),
        "provider": row.provider.value,
        "use_env_credentials": row.use_env_credentials,
        "from_email": row.from_email,
        "resend_api_key": "********" if row.resend_api_key else None,
        "smtp_host": row.smtp_host,
        "smtp_port": row.smtp_port,
        "smtp_use_tls": row.smtp_use_tls,
        "smtp_username": row.smtp_username,
        "smtp_password": "********" if row.smtp_password else None,
        "invitation_subject": row.invitation_subject,
        "invitation_body_html": row.invitation_body_html,
        "invitation_link_base_url": row.invitation_link_base_url,
        "invitation_token_expiry_days": row.invitation_token_expiry_days or 7,
        "verification_method": row.verification_method,
        "auth_method": row.auth_method,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.put("/settings/mail")
async def update_mail_settings(
    update: MailConfigUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create or update mail configuration (single row). Admin only.
    """
    try:
        result = await db.execute(
            select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
        )
        row = result.scalar_one_or_none()

        if not row:
            row = MailConfig(
                provider=MailProvider.RESEND,
                use_env_credentials=True,
                from_email="",
            )
            db.add(row)
            await db.flush()

        if update.provider is not None:
            row.provider = MailProvider(update.provider.value)
        if update.use_env_credentials is not None:
            row.use_env_credentials = update.use_env_credentials
        if update.from_email is not None:
            row.from_email = update.from_email
        if update.resend_api_key is not None and update.resend_api_key != "********":
            row.resend_api_key = update.resend_api_key
        if update.smtp_host is not None:
            row.smtp_host = update.smtp_host
        if update.smtp_port is not None:
            row.smtp_port = update.smtp_port
        if update.smtp_use_tls is not None:
            row.smtp_use_tls = update.smtp_use_tls
        if update.smtp_username is not None:
            row.smtp_username = update.smtp_username
        if update.smtp_password is not None and update.smtp_password != "********":
            row.smtp_password = update.smtp_password
        if update.invitation_subject is not None:
            row.invitation_subject = update.invitation_subject
        if update.invitation_body_html is not None:
            row.invitation_body_html = update.invitation_body_html
        if update.invitation_link_base_url is not None:
            # Pydantic MailConfigUpdate already strips trailing slash and validates URL
            row.invitation_link_base_url = update.invitation_link_base_url
        if update.invitation_token_expiry_days is not None:
            row.invitation_token_expiry_days = update.invitation_token_expiry_days
        if update.verification_method is not None:
            row.verification_method = update.verification_method
        if update.auth_method is not None:
            row.auth_method = update.auth_method

        await db.commit()
        await db.refresh(row)
        return {"message": "Mail settings updated", "success": True}
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "update mail settings", logger) from e


@router.post("/settings/mail/test-email")
async def send_test_email(
    request: dict,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Send a test email to verify mail delivery configuration. Admin only."""
    test_email = request.get("test_email", "").strip()
    if not test_email or "@" not in test_email:
        raise HTTPException(status_code=422, detail="Valid email address required")

    # Load current mail config from DB
    result = await db.execute(
        select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
    )
    mail_row = result.scalar_one_or_none()

    mail_cfg = None
    if mail_row:
        mail_cfg = {
            "provider": mail_row.provider.value,
            "use_env_credentials": mail_row.use_env_credentials,
            "from_email": mail_row.from_email,
            "resend_api_key": (
                mail_row.resend_api_key
                if not mail_row.use_env_credentials
                and mail_row.provider == MailProvider.RESEND
                else None
            ),
            "smtp_host": mail_row.smtp_host,
            "smtp_port": mail_row.smtp_port,
            "smtp_use_tls": mail_row.smtp_use_tls,
            "smtp_username": mail_row.smtp_username,
            "smtp_password": mail_row.smtp_password,
        }

    success = await email_service.send_test_email(test_email, mail_config=mail_cfg)
    if success:
        return {"success": True, "message": f"Test email sent to {test_email}"}
    else:
        return {"success": False, "message": "Failed to send test email. Check server logs for details."}


@router.get("/settings/mail/templates")
async def list_email_templates(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
):
    """List all available email template names. Admin only."""
    return {"templates": email_service.list_templates()}


@router.get("/settings/mail/preview/{template_name}")
async def preview_email_template(
    template_name: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
):
    """Render email template with sample data and return HTML. Admin only."""
    available = email_service.list_templates()
    if template_name not in available:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    sample_data = TEMPLATE_SAMPLE_DATA.get(template_name, {})
    html = email_service.render_template(template_name, **sample_data)
    return HTMLResponse(content=html)


# ==================== Market Overview ====================


@router.get("/market-overview")
async def get_market_overview(
    admin_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)  # noqa: B008
):
    """
    Get market overview statistics.
    Top 20 CEA sell orders and top 20 swap orders by value.
    Admin only.
    """
    # Top 20 CEA sell orders (available certificates)
    cea_query = (
        select(Certificate)
        .where(Certificate.certificate_type == CertificateType.CEA)
        .where(Certificate.status == CertificateStatus.AVAILABLE)
        .order_by((Certificate.quantity * Certificate.unit_price).desc())
        .limit(20)
    )
    cea_result = await db.execute(cea_query)
    cea_certificates = cea_result.scalars().all()

    # Calculate total CEA value (convert to USD - CEA is in CNY, roughly 0.14 USD/CNY)
    cea_value_cny = sum(
        float(c.quantity) * float(c.unit_price) for c in cea_certificates
    )
    cea_value_usd = cea_value_cny * 0.14  # Approximate CNY to USD conversion

    # Top 20 swap orders (open swaps)
    swap_query = (
        select(SwapRequest)
        .where(SwapRequest.status == SwapStatus.OPEN)
        .order_by(SwapRequest.quantity.desc())
        .limit(20)
    )
    swap_result = await db.execute(swap_query)
    swap_requests = swap_result.scalars().all()

    # Calculate swap value - use approximate prices
    # EUA ~€75 (~$80), CEA ~¥100 (~$14)
    swap_value_usd = 0
    for swap in swap_requests:
        if swap.from_type == CertificateType.EUA:
            # EUA to CEA swap - value in EUA
            swap_value_usd += float(swap.quantity) * 80  # ~$80 per EUA
        else:
            # CEA to EUA swap - value in CEA
            swap_value_usd += float(swap.quantity) * 14  # ~$14 per CEA

    return {
        "top_20_cea_value_usd": round(cea_value_usd, 2),
        "top_20_swap_value_usd": round(swap_value_usd, 2),
    }


# ============================================================================
# Auto Trade Settings Endpoints (Global Liquidity Limits)
# ============================================================================


@router.get("/auto-trade-settings", response_model=list[AutoTradeSettingsResponse])
async def get_auto_trade_settings(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Get all auto trade settings (one per certificate type)."""
    result = await db.execute(select(AutoTradeSettings))
    settings = result.scalars().all()
    return list(settings)


@router.get(
    "/auto-trade-settings/{certificate_type}",
    response_model=AutoTradeSettingsResponse,
)
async def get_auto_trade_settings_by_type(
    certificate_type: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Get auto trade settings for a specific certificate type."""
    cert_type = certificate_type.upper()
    if cert_type not in ("CEA", "EUA"):
        raise HTTPException(status_code=400, detail="Invalid certificate type. Must be CEA or EUA.")

    result = await db.execute(
        select(AutoTradeSettings).where(AutoTradeSettings.certificate_type == cert_type)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings not found for {cert_type}")

    return settings


@router.put(
    "/auto-trade-settings/{certificate_type}",
    response_model=AutoTradeSettingsResponse,
)
async def update_auto_trade_settings(
    certificate_type: str,
    updates: AutoTradeSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Update auto trade settings for a certificate type."""
    cert_type = certificate_type.upper()
    if cert_type not in ("CEA", "EUA"):
        raise HTTPException(status_code=400, detail="Invalid certificate type. Must be CEA or EUA.")

    result = await db.execute(
        select(AutoTradeSettings).where(AutoTradeSettings.certificate_type == cert_type)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings not found for {cert_type}")

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        await db.commit()
        await db.refresh(settings)
        return settings
    except Exception as e:
        await db.rollback()
        handle_database_error(e, "updating auto trade settings")


@router.get(
    "/auto-trade-settings/{certificate_type}/liquidity",
    response_model=LiquidityStatusResponse,
)
async def get_liquidity_status(
    certificate_type: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Get current liquidity status for a certificate type."""
    cert_type = certificate_type.upper()
    if cert_type not in ("CEA", "EUA"):
        raise HTTPException(status_code=400, detail="Invalid certificate type. Must be CEA or EUA.")

    # Get settings
    result = await db.execute(
        select(AutoTradeSettings).where(AutoTradeSettings.certificate_type == cert_type)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings not found for {cert_type}")

    # Map string to enum
    cert_type_enum = CertificateType.CEA if cert_type == "CEA" else CertificateType.EUA

    # Calculate current ASK liquidity (SELL orders)
    ask_result = await db.execute(
        select(func.sum(Order.price * (Order.quantity - Order.filled_quantity)))
        .where(
            Order.certificate_type == cert_type_enum,
            Order.side == OrderSide.SELL,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.market_maker_id.isnot(None),  # Only MM orders
        )
    )
    ask_liquidity = ask_result.scalar() or 0

    # Calculate current BID liquidity (BUY orders)
    bid_result = await db.execute(
        select(func.sum(Order.price * (Order.quantity - Order.filled_quantity)))
        .where(
            Order.certificate_type == cert_type_enum,
            Order.side == OrderSide.BUY,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.market_maker_id.isnot(None),  # Only MM orders
        )
    )
    bid_liquidity = bid_result.scalar() or 0

    # Calculate percentages
    ask_percentage = None
    bid_percentage = None

    if settings.target_ask_liquidity and settings.target_ask_liquidity > 0:
        ask_percentage = (ask_liquidity / settings.target_ask_liquidity) * 100

    if settings.target_bid_liquidity and settings.target_bid_liquidity > 0:
        bid_percentage = (bid_liquidity / settings.target_bid_liquidity) * 100

    return LiquidityStatusResponse(
        certificate_type=cert_type,
        ask_liquidity=ask_liquidity,
        bid_liquidity=bid_liquidity,
        target_ask_liquidity=settings.target_ask_liquidity,
        target_bid_liquidity=settings.target_bid_liquidity,
        ask_percentage=ask_percentage,
        bid_percentage=bid_percentage,
        liquidity_limit_enabled=settings.liquidity_limit_enabled,
    )


# ============================================================================
# Auto Trade Market Settings Endpoints (Per-market-side settings)
# ============================================================================

# Mapping from market_key to market maker types
MARKET_KEY_TO_MM_TYPES = {
    "CEA_BID": [MarketMakerType.CEA_BUYER],
    "CEA_ASK": [MarketMakerType.CEA_SELLER],
    "EUA_SWAP": [MarketMakerType.EUA_OFFER],
}


async def _check_is_online(db: AsyncSession, market_key: str) -> bool:
    """Check if any auto-trade rules for this market are actively running.

    A market is considered "online" if:
    - Settings are enabled AND
    - At least one enabled rule exists with recent execution activity
    """
    mm_types = MARKET_KEY_TO_MM_TYPES.get(market_key, [])
    if not mm_types:
        return False

    # Get market makers for this market
    mm_result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.mm_type.in_(mm_types))
    )
    market_makers = list(mm_result.scalars().all())
    if not market_makers:
        return False

    # Check if any enabled rules exist with recent activity
    mm_ids = [mm.id for mm in market_makers]
    rules_result = await db.execute(
        select(AutoTradeRule).where(
            AutoTradeRule.market_maker_id.in_(mm_ids),
            AutoTradeRule.enabled == True,  # noqa: E712
        )
    )
    enabled_rules = list(rules_result.scalars().all())

    if not enabled_rules:
        return False

    # Check if any rule has been executed recently (within 2x its interval)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for rule in enabled_rules:
        if rule.last_executed_at:
            interval = rule.interval_seconds or 60
            max_gap = timedelta(seconds=interval * 2)
            if (now - rule.last_executed_at) < max_gap:
                return True

    return False


def _build_market_settings_response(
    settings: AutoTradeMarketSettings,
    market_makers: list,
    current_liquidity,
    liquidity_percentage,
    is_online: bool,
) -> AutoTradeMarketSettingsResponse:
    """Build a standardized AutoTradeMarketSettingsResponse from a settings model."""
    return AutoTradeMarketSettingsResponse(
        id=settings.id,
        market_key=settings.market_key,
        enabled=settings.enabled,
        target_liquidity=settings.target_liquidity,
        price_deviation_pct=settings.price_deviation_pct,
        avg_order_count=settings.avg_order_count,
        min_order_volume_eur=settings.min_order_volume_eur,
        volume_variety=settings.volume_variety,
        avg_order_count_variation_pct=settings.avg_order_count_variation_pct,
        max_orders_per_price_level=settings.max_orders_per_price_level,
        max_orders_per_level_variation_pct=settings.max_orders_per_level_variation_pct,
        min_order_value_variation_pct=settings.min_order_value_variation_pct,
        interval_seconds=settings.interval_seconds,
        order_interval_variation_pct=settings.order_interval_variation_pct,
        max_order_volume_eur=settings.max_order_volume_eur,
        max_liquidity_threshold=settings.max_liquidity_threshold,
        internal_trade_interval=settings.internal_trade_interval,
        internal_trade_volume_min=settings.internal_trade_volume_min,
        internal_trade_volume_max=settings.internal_trade_volume_max,
        avg_spread=settings.avg_spread,
        tick_size=settings.tick_size,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
        market_makers=[MarketMakerSummary(id=mm.id, name=mm.name, is_active=mm.is_active) for mm in market_makers],
        current_liquidity=current_liquidity,
        liquidity_percentage=liquidity_percentage,
        is_online=is_online,
    )


@router.get("/auto-trade-status")
async def get_auto_trade_status(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """
    Get executor status: running state, last/next cycle, results summary, and rules overview.
    Polled by the frontend to display the read-only timer.
    """
    from app.services.auto_trade_executor import get_executor_status

    status = get_executor_status()

    # Add live rules summary from DB
    rules_result = await db.execute(select(AutoTradeRule))
    all_rules = list(rules_result.scalars().all())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    status["rules_summary"] = {
        "total": len(all_rules),
        "enabled": sum(1 for r in all_rules if r.enabled),
        "ready_to_execute": sum(
            1 for r in all_rules
            if r.enabled and (r.next_execution_at is None or r.next_execution_at <= now)
        ),
    }

    return status


@router.get("/auto-trade-market-settings", response_model=list[AutoTradeMarketSettingsResponse])
async def get_all_market_settings(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Get all per-market-side auto trade settings with associated market makers."""
    result = await db.execute(select(AutoTradeMarketSettings))
    all_settings = list(result.scalars().all())

    responses = []
    for settings in all_settings:
        # Get associated market makers based on market_key
        mm_types = MARKET_KEY_TO_MM_TYPES.get(settings.market_key, [])
        mm_result = await db.execute(
            select(MarketMakerClient).where(MarketMakerClient.mm_type.in_(mm_types))
        )
        market_makers = list(mm_result.scalars().all())

        # Calculate current liquidity
        current_liquidity = await _calculate_market_liquidity(db, settings.market_key)
        liquidity_percentage = None
        if settings.target_liquidity and settings.target_liquidity > 0:
            from decimal import Decimal
            liquidity_percentage = (current_liquidity / settings.target_liquidity) * Decimal("100")

        # Check if auto-trader is actively running
        is_online = settings.enabled and await _check_is_online(db, settings.market_key)

        responses.append(_build_market_settings_response(
            settings, market_makers, current_liquidity, liquidity_percentage, is_online
        ))

    return responses


@router.post("/auto-trade-market-settings/refresh-cea")
async def refresh_cea_market(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Refresh CEA Cash market: cancel all MM orders, fetch scraped price,
    and recreate BID + ASK orders from the auto-trade market settings.

    Rules:
    - best_bid = scraped CEA price (rounded to 0.1)
    - best_ask = best_bid + 0.1
    - BID orders placed from best_bid downward (each -0.1 EUR)
    - ASK orders placed from best_ask upward (each +0.1 EUR)
    - Contiguous price levels (no gaps > 0.1)
    - Respects avg_order_count, max_orders_per_price_level, min/max order volume
    """
    import random
    from sqlalchemy import and_
    from app.services.price_scraper import price_scraper

    try:
        # 1. Cancel all OPEN/PARTIALLY_FILLED CEA_CASH MM orders
        cancel_result = await db.execute(
            select(Order).where(
                and_(
                    Order.market == MarketType.CEA_CASH,
                    Order.market_maker_id.isnot(None),
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                )
            )
        )
        orders_to_cancel = list(cancel_result.scalars().all())
        orders_cancelled = len(orders_to_cancel)

        for order in orders_to_cancel:
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.flush()

        # 2. Fetch scraped CEA price
        prices = await price_scraper.get_current_prices()
        cea_price_raw = Decimal(str(prices["cea"]["price"]))
        # Round to nearest 0.1
        cea_price = (cea_price_raw / Decimal("0.1")).quantize(Decimal("1")) * Decimal("0.1")

        # Mean-reversion price deviation:
        # - Read last deviation from Redis; decay it 60% + add small noise
        # - Large deviations die quickly: +18% → ~+7% → ~+3% → ~+1%
        # - Fresh start (no history): standard gauss(0, 0.07)
        from app.core.security import RedisManager
        DECAY_FACTOR = 0.4       # keep 40% of previous deviation
        NOISE_SIGMA = 0.03       # small random noise on each refresh
        MAX_DEVIATION = 0.20     # hard cap ±20%
        REDIS_KEY = "cea:last_deviation"

        try:
            r = await RedisManager.get_redis()
            last_raw = await r.get(REDIS_KEY)
            if last_raw is not None:
                last_dev = float(last_raw)
                # Decay toward zero + fresh noise
                deviation_pct = last_dev * DECAY_FACTOR + random.gauss(0, NOISE_SIGMA)
            else:
                # First call or expired — fresh deviation
                deviation_pct = random.gauss(0, 0.07)
            deviation_pct = max(-MAX_DEVIATION, min(MAX_DEVIATION, deviation_pct))
            # Store for next call (TTL 1h — resets if nobody refreshes for a while)
            await r.set(REDIS_KEY, str(round(deviation_pct, 6)), ex=3600)
        except Exception:
            # Redis unavailable — fallback to stateless gauss
            deviation_pct = max(-MAX_DEVIATION, min(MAX_DEVIATION, random.gauss(0, 0.07)))

        mid_price = cea_price * (1 + Decimal(str(round(deviation_pct, 4))))
        mid_price = (mid_price / Decimal("0.1")).quantize(Decimal("1")) * Decimal("0.1")

        best_bid = mid_price
        best_ask = mid_price + Decimal("0.1")

        # 3. Load market settings for CEA_BID and CEA_ASK
        bid_settings_result = await db.execute(
            select(AutoTradeMarketSettings).where(AutoTradeMarketSettings.market_key == "CEA_BID")
        )
        bid_settings = bid_settings_result.scalar_one_or_none()

        ask_settings_result = await db.execute(
            select(AutoTradeMarketSettings).where(AutoTradeMarketSettings.market_key == "CEA_ASK")
        )
        ask_settings = ask_settings_result.scalar_one_or_none()

        if not bid_settings or not ask_settings:
            raise HTTPException(status_code=404, detail="CEA_BID or CEA_ASK settings not found")

        # 4. Get active market makers
        buyer_result = await db.execute(
            select(MarketMakerClient).where(
                and_(
                    MarketMakerClient.is_active.is_(True),
                    MarketMakerClient.mm_type == MarketMakerType.CEA_BUYER,
                )
            )
        )
        buyers = list(buyer_result.scalars().all())

        seller_result = await db.execute(
            select(MarketMakerClient).where(
                and_(
                    MarketMakerClient.is_active.is_(True),
                    MarketMakerClient.mm_type == MarketMakerType.CEA_SELLER,
                )
            )
        )
        sellers = list(seller_result.scalars().all())

        if not buyers or not sellers:
            raise HTTPException(status_code=400, detail="No active CEA_BUYER or CEA_SELLER market makers")

        bid_orders_created = 0
        ask_orders_created = 0
        price_step = Decimal("0.1")

        from app.services.auto_trade_executor import AutoTradeExecutor

        # Helper: generate volume using log-normal distribution from settings
        def _lognormal_volume(settings):
            return AutoTradeExecutor.calculate_order_volume_with_variety(
                min_volume_eur=settings.min_order_volume_eur,
                volume_variety=settings.volume_variety or 5,
                target_liquidity=settings.target_liquidity,
                current_liquidity=Decimal("0"),
                avg_order_count=settings.avg_order_count or 10,
                max_volume_eur=settings.max_order_volume_eur,
            )

        # 5. Create BID orders (from best_bid downward)
        bid_target = bid_settings.target_liquidity or Decimal("50000000")
        bid_max_orders = int(bid_settings.avg_order_count or 200) * 2  # safety cap
        bid_max_per_level = bid_settings.max_orders_per_price_level or 3
        bid_depth_pct = bid_settings.price_deviation_pct or Decimal("5.0")
        bid_worst_price = best_bid * (Decimal("1") - bid_depth_pct / Decimal("100"))
        bid_worst_price = max(bid_worst_price, Decimal("0.1"))

        current_price = best_bid
        orders_at_level = 0
        max_at_this_level = random.randint(1, bid_max_per_level)
        buyer_idx = 0
        bid_liquidity_eur = Decimal("0")

        for _ in range(bid_max_orders):
            if current_price < bid_worst_price or bid_liquidity_eur >= bid_target:
                break

            if orders_at_level >= max_at_this_level:
                current_price -= price_step
                current_price = current_price.quantize(Decimal("0.1"))
                orders_at_level = 0
                max_at_this_level = random.randint(1, bid_max_per_level)
                if current_price < bid_worst_price:
                    break

            # Log-normal volume, capped by remaining budget
            remaining = bid_target - bid_liquidity_eur
            order_value_eur = min(_lognormal_volume(bid_settings), remaining)
            if order_value_eur < (bid_settings.min_order_volume_eur or Decimal("1")):
                break

            quantity = (order_value_eur / current_price).quantize(Decimal("1"))
            if quantity < 1:
                quantity = Decimal("1")

            mm = buyers[buyer_idx % len(buyers)]
            buyer_idx += 1

            order = Order(
                market=MarketType.CEA_CASH,
                market_maker_id=mm.id,
                certificate_type=CertificateType.CEA,
                side=OrderSide.BUY,
                price=current_price,
                quantity=quantity,
                filled_quantity=Decimal("0"),
                status=OrderStatus.OPEN,
            )
            db.add(order)
            bid_orders_created += 1
            orders_at_level += 1
            bid_liquidity_eur += current_price * quantity

        # 6. Create ASK orders (from best_ask upward)
        ask_target = ask_settings.target_liquidity or Decimal("90000000")
        ask_max_orders = int(ask_settings.avg_order_count or 200) * 2  # safety cap
        ask_max_per_level = ask_settings.max_orders_per_price_level or 3
        ask_depth_pct = ask_settings.price_deviation_pct or Decimal("5.0")
        ask_worst_price = best_ask * (Decimal("1") + ask_depth_pct / Decimal("100"))

        current_price = best_ask
        orders_at_level = 0
        max_at_this_level = random.randint(1, ask_max_per_level)
        seller_idx = 0
        ask_liquidity_eur = Decimal("0")

        for _ in range(ask_max_orders):
            if ask_liquidity_eur >= ask_target:
                break

            if orders_at_level >= max_at_this_level:
                current_price += price_step
                current_price = current_price.quantize(Decimal("0.1"))
                orders_at_level = 0
                max_at_this_level = random.randint(1, ask_max_per_level)

            if current_price > ask_worst_price:
                break

            # Log-normal volume, capped by remaining budget
            remaining = ask_target - ask_liquidity_eur
            order_value_eur = min(_lognormal_volume(ask_settings), remaining)
            if order_value_eur < (ask_settings.min_order_volume_eur or Decimal("1")):
                break

            quantity = (order_value_eur / current_price).quantize(Decimal("1"))
            if quantity < 1:
                quantity = Decimal("1")

            mm = sellers[seller_idx % len(sellers)]
            seller_idx += 1

            order = Order(
                market=MarketType.CEA_CASH,
                market_maker_id=mm.id,
                certificate_type=CertificateType.CEA,
                side=OrderSide.SELL,
                price=current_price,
                quantity=quantity,
                filled_quantity=Decimal("0"),
                status=OrderStatus.OPEN,
            )
            db.add(order)
            ask_orders_created += 1
            orders_at_level += 1
            ask_liquidity_eur += current_price * quantity

        await db.commit()

        return {
            "success": True,
            "orders_cancelled": orders_cancelled,
            "cea_price_eur": str(cea_price),
            "new_best_bid": str(best_bid),
            "mid_price_eur": str(mid_price),
            "price_deviation_pct": str(round(deviation_pct * 100, 1)),
            "new_best_ask": str(best_ask),
            "bid_orders_created": bid_orders_created,
            "ask_orders_created": ask_orders_created,
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error refreshing CEA market: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh CEA market. Please try again.")


@router.post("/auto-trade-market-settings/refresh-swap")
async def refresh_swap_market(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Refresh SWAP EUA market: cancel all MM swap orders, fetch scraped prices,
    and recreate ASK orders with structured ratio band.

    Rules:
    - base_ratio = scraped_cea / scraped_eua
    - best_ratio = base_ratio * 1.15 (top of book, most favorable for user)
    - worst_ratio = best_ratio * 0.75 (25% variation band)
    - ASK orders placed from best_ratio DOWNWARD to worst_ratio (each -0.0001)
    - Only SELL orders (EUA_OFFER market makers)
    - Respects target_liquidity (90M EUR cap), min/max order volume
    - Liquidity measured as: remaining_eua_qty * eua_price_eur
    """
    import random
    from sqlalchemy import and_
    from app.services.price_scraper import price_scraper

    try:
        # 1. Cancel all OPEN/PARTIALLY_FILLED SWAP MM orders
        cancel_result = await db.execute(
            select(Order).where(
                and_(
                    Order.market == MarketType.SWAP,
                    Order.market_maker_id.isnot(None),
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                )
            )
        )
        orders_to_cancel = list(cancel_result.scalars().all())
        orders_cancelled = len(orders_to_cancel)

        for order in orders_to_cancel:
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.flush()

        # 2. Fetch scraped prices
        prices = await price_scraper.get_current_prices()
        cea_price = Decimal(str(prices["cea"]["price"]))
        eua_price = Decimal(str(prices["eua"]["price"]))

        if eua_price <= 0:
            raise HTTPException(status_code=400, detail="Invalid EUA price from scraper")

        base_ratio = (cea_price / eua_price).quantize(Decimal("0.0001"))

        # 3. Structured ratio band: best = base +15%, worst = best -25%
        best_ratio = (base_ratio * Decimal("1.15")).quantize(Decimal("0.0001"))
        worst_ratio = (best_ratio * Decimal("0.75")).quantize(Decimal("0.0001"))

        # 4. Load EUA_SWAP market settings
        settings_result = await db.execute(
            select(AutoTradeMarketSettings).where(AutoTradeMarketSettings.market_key == "EUA_SWAP")
        )
        swap_settings = settings_result.scalar_one_or_none()
        if not swap_settings:
            raise HTTPException(status_code=404, detail="EUA_SWAP settings not found")

        # 5. Load active EUA_OFFER market makers
        mm_result = await db.execute(
            select(MarketMakerClient).where(
                and_(
                    MarketMakerClient.is_active.is_(True),
                    MarketMakerClient.mm_type == MarketMakerType.EUA_OFFER,
                )
            )
        )
        eua_mms = list(mm_result.scalars().all())
        if not eua_mms:
            raise HTTPException(status_code=400, detail="No active EUA_OFFER market makers")

        # 6. Create ASK orders from best_ratio DOWNWARD to worst_ratio
        from app.services.auto_trade_executor import AutoTradeExecutor

        target_liquidity_eur = swap_settings.target_liquidity or Decimal("90000000")
        max_orders = int(swap_settings.avg_order_count or 100) * 2  # safety cap
        ratio_step = Decimal("0.0001")
        swap_max_per_level = swap_settings.max_orders_per_price_level or 3

        def _swap_lognormal_volume():
            return AutoTradeExecutor.calculate_order_volume_with_variety(
                min_volume_eur=swap_settings.min_order_volume_eur or Decimal("200000"),
                volume_variety=swap_settings.volume_variety or 5,
                target_liquidity=swap_settings.target_liquidity,
                current_liquidity=Decimal("0"),
                avg_order_count=swap_settings.avg_order_count or 10,
                max_volume_eur=swap_settings.max_order_volume_eur,
            )

        current_ratio = best_ratio
        orders_at_level = 0
        max_at_this_level = random.randint(1, swap_max_per_level)
        mm_idx = 0
        liquidity_eur = Decimal("0")
        orders_created = 0
        min_vol = swap_settings.min_order_volume_eur or Decimal("200000")

        for _ in range(max_orders):
            if liquidity_eur >= target_liquidity_eur:
                break
            if current_ratio < worst_ratio:
                break

            if orders_at_level >= max_at_this_level:
                current_ratio -= ratio_step
                current_ratio = current_ratio.quantize(Decimal("0.0001"))
                orders_at_level = 0
                max_at_this_level = random.randint(1, swap_max_per_level)

            # Log-normal volume, capped by remaining budget
            remaining = target_liquidity_eur - liquidity_eur
            order_value_eur = min(_swap_lognormal_volume(), remaining)
            if order_value_eur < min_vol:
                break

            # eua_quantity = volume_eur / eua_price_eur (whole certificates)
            eua_quantity = (order_value_eur / eua_price).quantize(Decimal("1"))
            if eua_quantity < 1:
                eua_quantity = Decimal("1")

            mm = eua_mms[mm_idx % len(eua_mms)]
            mm_idx += 1

            order = Order(
                market=MarketType.SWAP,
                market_maker_id=mm.id,
                certificate_type=CertificateType.EUA,
                side=OrderSide.SELL,
                price=current_ratio,
                quantity=eua_quantity,
                filled_quantity=Decimal("0"),
                status=OrderStatus.OPEN,
            )
            db.add(order)
            orders_created += 1
            orders_at_level += 1
            liquidity_eur += eua_quantity * eua_price

        await db.commit()

        return {
            "success": True,
            "orders_cancelled": orders_cancelled,
            "cea_price_eur": str(cea_price),
            "eua_price_eur": str(eua_price),
            "base_ratio": str(base_ratio),
            "best_ratio": str(best_ratio),
            "worst_ratio": str(worst_ratio),
            "orders_created": orders_created,
            "liquidity_eur": str(liquidity_eur.quantize(Decimal("1"))),
            "target_liquidity_eur": str(target_liquidity_eur),
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error refreshing SWAP market: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh SWAP market. Please try again.")


@router.post("/auto-trade-market-settings/place-random-order")
async def place_random_order(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Smart MM order placement with priority-based decisions:
      Step 0: Gather context (orderbook, liquidity, scraped price)
      Step 1: Spread correction — pre-step, fills gaps if spread > 0.1
      Step 2: Price alignment — market-crossing orders if mid deviates from scraped price
      Step 3: Liquidity bias — limit orders toward the side with largest deficit
      Step 4: Normal random — fallback, 1 in 10 is market-crossing
    """
    import random
    from sqlalchemy import and_, text
    from app.services.limit_order_matching import LimitOrderMatcher
    from app.core.security import RedisManager
    from app.services.price_scraper import price_scraper

    _PS = Decimal("0.1")  # price step
    _MIN_VOL = Decimal("200000")
    _MAX_VOL = Decimal("5000000")
    _PRICE_ALIGN_ABS = Decimal("0.5")   # EUR absolute deviation threshold
    _PRICE_ALIGN_REL = Decimal("0.05")  # 5% relative deviation threshold

    def _rand_vol(lo=_MIN_VOL, hi=_MAX_VOL):
        return Decimal(str(round(random.uniform(float(lo), float(hi)), 2)))

    def _qty(vol, price):
        q = (vol / price).quantize(Decimal("1"))
        return max(q, Decimal("1"))

    def _pick_mm(mms):
        return random.choice(mms)

    try:
        # ════════════════════════════════════════════════════════════════
        # STEP 0: Gather context
        # ════════════════════════════════════════════════════════════════
        # Exclude zombie orders (remainder < 1) from best bid/ask calculation
        _MIN_CERT = Decimal("1")
        best_bid_r = await db.execute(
            select(func.max(Order.price)).where(and_(
                Order.market == MarketType.CEA_CASH, Order.certificate_type == CertificateType.CEA,
                Order.side == OrderSide.BUY, Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                (Order.quantity - Order.filled_quantity) >= _MIN_CERT,
            ))
        )
        best_bid = best_bid_r.scalar()

        best_ask_r = await db.execute(
            select(func.min(Order.price)).where(and_(
                Order.market == MarketType.CEA_CASH, Order.certificate_type == CertificateType.CEA,
                Order.side == OrderSide.SELL, Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                (Order.quantity - Order.filled_quantity) >= _MIN_CERT,
            ))
        )
        best_ask = best_ask_r.scalar()

        if not best_bid or not best_ask:
            raise HTTPException(status_code=400, detail="No orderbook — run Refresh CEA first")

        # Active market makers (both types)
        buyers_r = await db.execute(select(MarketMakerClient).where(and_(
            MarketMakerClient.is_active.is_(True), MarketMakerClient.mm_type == MarketMakerType.CEA_BUYER)))
        cea_buyers = list(buyers_r.scalars().all())
        sellers_r = await db.execute(select(MarketMakerClient).where(and_(
            MarketMakerClient.is_active.is_(True), MarketMakerClient.mm_type == MarketMakerType.CEA_SELLER)))
        cea_sellers = list(sellers_r.scalars().all())
        if not cea_buyers or not cea_sellers:
            raise HTTPException(status_code=400, detail="No active CEA market makers")

        # Liquidity per side (exclude zombie orders with < 1 remaining)
        liq_r = await db.execute(text("""
            SELECT o.side, COALESCE(SUM(o.price * (o.quantity - o.filled_quantity)), 0) as val
            FROM orders o
            WHERE o.market = 'CEA_CASH' AND o.status IN ('OPEN','PARTIALLY_FILLED')
              AND o.market_maker_id IS NOT NULL
              AND (o.quantity - o.filled_quantity) >= 1
            GROUP BY o.side
        """))
        liq_map = {r.side: Decimal(str(r.val)) for r in liq_r.fetchall()}
        bid_liq = liq_map.get("BUY", Decimal("0"))
        ask_liq = liq_map.get("SELL", Decimal("0"))

        # Targets from AutoTradeMarketSettings
        settings_r = await db.execute(
            select(AutoTradeMarketSettings).where(
                AutoTradeMarketSettings.market_key.in_(["CEA_BID", "CEA_ASK"])
            )
        )
        settings_map = {s.market_key: s for s in settings_r.scalars().all()}
        bid_target = settings_map.get("CEA_BID")
        ask_target = settings_map.get("CEA_ASK")
        bid_target_eur = bid_target.target_liquidity if bid_target else Decimal("50000000")
        ask_target_eur = ask_target.target_liquidity if ask_target else Decimal("90000000")

        # Scraped CEA price
        scraped_cea = None
        try:
            prices = await price_scraper.get_current_prices()
            raw = Decimal(str(prices["cea"]["price"]))
            scraped_cea = (raw / _PS).quantize(Decimal("1")) * _PS  # round to 0.1
        except Exception:
            pass  # skip price alignment if scraper fails

        # Redis counter for deterministic 1-in-10 market orders
        try:
            redis_conn = await RedisManager.get_redis()
            order_counter = await redis_conn.incr("random_order_counter")
        except Exception:
            order_counter = random.randint(1, 10)

        # Existing price levels for gap detection (exclude zombie orders)
        bid_levels_r = await db.execute(text("""
            SELECT DISTINCT price FROM orders
            WHERE market = 'CEA_CASH' AND side = 'BUY'
              AND status IN ('OPEN','PARTIALLY_FILLED')
              AND (quantity - filled_quantity) >= 1
            ORDER BY price DESC
        """))
        bid_levels = [Decimal(str(r[0])) for r in bid_levels_r.fetchall()]

        ask_levels_r = await db.execute(text("""
            SELECT DISTINCT price FROM orders
            WHERE market = 'CEA_CASH' AND side = 'SELL'
              AND status IN ('OPEN','PARTIALLY_FILLED')
              AND (quantity - filled_quantity) >= 1
            ORDER BY price ASC
        """))
        ask_levels = [Decimal(str(r[0])) for r in ask_levels_r.fetchall()]

        bid_levels_set = set(bid_levels)
        ask_levels_set = set(ask_levels)

        # ════════════════════════════════════════════════════════════════
        # STEP 1 (pre-step): Spread + gap correction
        # ════════════════════════════════════════════════════════════════
        spread_orders_placed = []

        def _add_correction(side_val, price_val, mms):
            """Place a corrective limit order and track it."""
            mm = _pick_mm(mms)
            vol = _rand_vol(_MIN_VOL, Decimal("1000000"))
            pq = price_val.quantize(_PS)
            db.add(Order(
                market=MarketType.CEA_CASH, market_maker_id=mm.id,
                certificate_type=CertificateType.CEA, side=side_val,
                price=pq, quantity=_qty(vol, pq),
                filled_quantity=Decimal("0"), status=OrderStatus.OPEN,
            ))
            spread_orders_placed.append(f"{side_val.value}@{pq}")
            # Track in sets so gap detection skips these
            if side_val == OrderSide.BUY:
                bid_levels_set.add(pq)
            else:
                ask_levels_set.add(pq)

        # ── 1a: Spread → scraped price ──
        # Target: best_bid = scraped_cea, best_ask = scraped_cea + 0.1
        if scraped_cea and scraped_cea > 0:
            target_bid = scraped_cea.quantize(_PS)
            target_ask = (scraped_cea + _PS).quantize(_PS)
        else:
            mid_fallback = ((best_bid + best_ask) / 2).quantize(_PS)
            target_bid = mid_fallback
            target_ask = (mid_fallback + _PS).quantize(_PS)

        # Fill BUY levels upward toward target_bid (but never at/above best_ask)
        buy_ceiling = min(target_bid, (best_ask - _PS).quantize(_PS))
        if best_bid < buy_ceiling:
            p = (best_bid + _PS).quantize(_PS)
            while p <= buy_ceiling:
                if p not in bid_levels_set:
                    _add_correction(OrderSide.BUY, p, cea_buyers)
                p = (p + _PS).quantize(_PS)
            best_bid = buy_ceiling

        # Fill SELL levels downward toward target_ask (but never at/below best_bid)
        sell_floor = max(target_ask, (best_bid + _PS).quantize(_PS))
        if best_ask > sell_floor:
            p = (best_ask - _PS).quantize(_PS)
            while p >= sell_floor:
                if p not in ask_levels_set:
                    _add_correction(OrderSide.SELL, p, cea_sellers)
                p = (p - _PS).quantize(_PS)
            best_ask = sell_floor

        # ── 1b: Fill BID gaps (walk top→bottom) ──
        # Refresh bid_levels to include orders added in 1a
        all_bid = sorted(bid_levels_set, reverse=True)
        for i in range(len(all_bid) - 1):
            high = all_bid[i]
            low = all_bid[i + 1]
            gap_p = (high - _PS).quantize(_PS)
            while gap_p > low:
                if gap_p not in bid_levels_set:
                    _add_correction(OrderSide.BUY, gap_p, cea_buyers)
                gap_p = (gap_p - _PS).quantize(_PS)

        # ── 1c: Fill ASK gaps (walk bottom→top) ──
        all_ask = sorted(ask_levels_set)
        for i in range(len(all_ask) - 1):
            low = all_ask[i]
            high = all_ask[i + 1]
            gap_p = (low + _PS).quantize(_PS)
            while gap_p < high:
                if gap_p not in ask_levels_set:
                    _add_correction(OrderSide.SELL, gap_p, cea_sellers)
                gap_p = (gap_p + _PS).quantize(_PS)

        if spread_orders_placed:
            await db.flush()

        # ════════════════════════════════════════════════════════════════
        # STEPS 2-4: Decide main order (first match wins)
        # ════════════════════════════════════════════════════════════════
        action = "normal_random"
        side = None
        is_market_like = False
        price = None
        decision_mid = None
        price_deviation_eur = None

        # ── STEP 2: Price alignment ──
        if scraped_cea and scraped_cea > 0:
            mid = (best_bid + best_ask) / 2
            decision_mid = mid
            deviation = mid - scraped_cea
            abs_dev = abs(deviation)
            rel_dev = abs_dev / scraped_cea
            price_deviation_eur = deviation

            if abs_dev > _PRICE_ALIGN_ABS or rel_dev > _PRICE_ALIGN_REL:
                action = "price_alignment"
                is_market_like = True
                if deviation > 0:
                    # Mid too high → SELL at best_bid to push price down
                    side = OrderSide.SELL
                    price = best_bid
                else:
                    # Mid too low → BUY at best_ask to push price up
                    side = OrderSide.BUY
                    price = best_ask

        # ── STEP 2.5: Liquidity reduction ──
        # When a side exceeds its target, place a market-crossing order to
        # consume the excess (SELL @ best_bid eats BID liquidity, BUY @ best_ask eats ASK).
        if action == "normal_random":
            bid_excess = max(Decimal("0"), bid_liq - bid_target_eur)
            ask_excess = max(Decimal("0"), ask_liq - ask_target_eur)

            if bid_excess > 0 or ask_excess > 0:
                action = "liquidity_reduction"
                is_market_like = True
                bid_excess_ratio = bid_excess / bid_target_eur if bid_target_eur > 0 else Decimal("0")
                ask_excess_ratio = ask_excess / ask_target_eur if ask_target_eur > 0 else Decimal("0")

                if bid_excess_ratio >= ask_excess_ratio:
                    # BID side has more excess → SELL at best_bid to consume BUY orders
                    side = OrderSide.SELL
                    price = best_bid
                else:
                    # ASK side has more excess → BUY at best_ask to consume SELL orders
                    side = OrderSide.BUY
                    price = best_ask

        # ── STEP 3: Liquidity bias ──
        if action == "normal_random":
            bid_deficit = max(Decimal("0"), bid_target_eur - bid_liq)
            ask_deficit = max(Decimal("0"), ask_target_eur - ask_liq)

            if bid_deficit > 0 or ask_deficit > 0:
                action = "liquidity_bias"
                bid_ratio = bid_deficit / bid_target_eur if bid_target_eur > 0 else Decimal("0")
                ask_ratio = ask_deficit / ask_target_eur if ask_target_eur > 0 else Decimal("0")

                if bid_ratio >= ask_ratio:
                    side = OrderSide.BUY
                    offset = random.randint(0, 2)
                    price = (best_bid - _PS * offset).quantize(_PS)
                else:
                    side = OrderSide.SELL
                    offset = random.randint(0, 2)
                    price = (best_ask + _PS * offset).quantize(_PS)

        # ── STEP 4: Normal random ──
        if action == "normal_random":
            is_market_like = (order_counter % 10 == 0)
            side = random.choice([OrderSide.BUY, OrderSide.SELL])
            if side == OrderSide.BUY:
                if is_market_like:
                    price = best_ask
                else:
                    price = (best_bid - _PS * random.randint(0, 3)).quantize(_PS)
            else:
                if is_market_like:
                    price = best_bid
                else:
                    price = (best_ask + _PS * random.randint(0, 3)).quantize(_PS)

        # ════════════════════════════════════════════════════════════════
        # Place the main order
        # ════════════════════════════════════════════════════════════════
        price = max(price, _PS).quantize(_PS)
        mm = _pick_mm(cea_buyers if side == OrderSide.BUY else cea_sellers)

        # Volume — cap at deficit/excess to avoid overshooting
        if action == "liquidity_reduction":
            excess = bid_excess if side == OrderSide.SELL else ask_excess
            vol_hi = min(_MAX_VOL, max(_MIN_VOL, excess))
            volume_eur = _rand_vol(_MIN_VOL, vol_hi)
        elif action == "liquidity_bias":
            deficit = bid_deficit if side == OrderSide.BUY else ask_deficit
            vol_hi = min(_MAX_VOL, max(_MIN_VOL, deficit))
            volume_eur = _rand_vol(_MIN_VOL, vol_hi)
        else:
            volume_eur = _rand_vol()

        quantity = _qty(volume_eur, price)

        order = Order(
            market=MarketType.CEA_CASH, market_maker_id=mm.id,
            certificate_type=CertificateType.CEA, side=side,
            price=price, quantity=quantity,
            filled_quantity=Decimal("0"), status=OrderStatus.OPEN,
        )
        db.add(order)
        await db.flush()

        # Create audit ticket for the order
        order_ticket = await TicketService.create_ticket(
            db=db,
            action_type="AUTO_TRADE_ORDER_PLACED",
            entity_type="Order",
            entity_id=order.id,
            status=TicketStatus.SUCCESS,
            user_id=current_user.id,
            market_maker_id=mm.id,
            request_payload={
                "action": action,
                "side": side.value,
                "is_market_like": is_market_like,
            },
            response_data={
                "order_id": str(order.id),
                "price": str(price),
                "quantity": str(quantity),
                "certificate_type": "CEA",
            },
            tags=["auto_trade", "order", side.value.lower()],
        )
        order.ticket_id = order_ticket.ticket_id

        # Match if market-crossing
        trades_matched = 0
        if is_market_like:
            result = await LimitOrderMatcher.match_incoming_order(
                db=db, incoming_order=order, user_id=current_user.id,
            )
            trades_matched = result.trades_created if result else 0

            # Cancel unfilled remainder of market-crossing orders.
            # Without this, a partially-filled BUY@best_ask lingers on the
            # BID side at the ASK price, collapsing the spread to zero.
            if order.status != OrderStatus.FILLED:
                order.status = OrderStatus.CANCELLED

        await db.commit()

        # ════════════════════════════════════════════════════════════════
        # Response (backward-compatible + new fields)
        # ════════════════════════════════════════════════════════════════
        return {
            "success": True,
            "action": action,
            "side": side.value,
            "price": str(price),
            "quantity": str(quantity),
            "volume_eur": str(volume_eur),
            "is_market_like": is_market_like,
            "trades_matched": trades_matched,
            "market_maker": mm.name,
            "status": order.status.value,
            "spread_corrected": bool(spread_orders_placed),
            "spread_orders": spread_orders_placed,
            "scraped_price": str(scraped_cea) if scraped_cea else None,
            "mid_orderbook": str(decision_mid.quantize(_PS)) if decision_mid else str(((best_bid + best_ask) / 2).quantize(_PS)),
            "price_deviation_eur": str(price_deviation_eur.quantize(Decimal("0.01"))) if price_deviation_eur is not None else None,
            "bid_liquidity_pct": str(round(bid_liq / bid_target_eur * 100, 1)) if bid_target_eur > 0 else None,
            "ask_liquidity_pct": str(round(ask_liq / ask_target_eur * 100, 1)) if ask_target_eur > 0 else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error placing random order: {e}")
        raise HTTPException(status_code=500, detail="Failed to place random order. Please try again.")


async def _place_random_swap_order_internal(db: AsyncSession) -> dict:
    """
    Reactive SWAP auto-trade: fill the gap between best_ratio and current top-of-book.

    Called after execute_swap to refill consumed ASK liquidity. Also exposed via endpoint.
    Places orders from best_ratio (base*1.15) DOWN to the current highest offer in the book,
    using 0.0001 tick steps. Respects 90M EUR liquidity cap.
    Returns dict with result info, or {"skipped": True} if no replenishment needed.
    """
    import random
    from decimal import Decimal
    from sqlalchemy import and_
    from app.services.price_scraper import price_scraper

    _MIN_VOL = Decimal("200000")
    _MAX_VOL = Decimal("5000000")
    _MAX_REPLENISH_ORDERS = 50  # safety cap per call

    # 1. Load settings
    settings_r = await db.execute(
        select(AutoTradeMarketSettings).where(AutoTradeMarketSettings.market_key == "EUA_SWAP")
    )
    swap_settings = settings_r.scalar_one_or_none()
    if not swap_settings or not swap_settings.enabled:
        return {"skipped": True, "reason": "EUA_SWAP settings disabled or not found"}

    target_eur = swap_settings.target_liquidity or Decimal("90000000")

    # 2. Fetch scraped prices
    try:
        prices = await price_scraper.get_current_prices()
        cea_price = Decimal(str(prices["cea"]["price"]))
        eua_price = Decimal(str(prices["eua"]["price"]))
    except Exception:
        cea_price = Decimal("13.0")
        eua_price = Decimal("75.0")

    if eua_price <= 0:
        return {"skipped": True, "reason": "Invalid EUA price"}

    base_ratio = (cea_price / eua_price).quantize(Decimal("0.0001"))
    best_ratio = (base_ratio * Decimal("1.15")).quantize(Decimal("0.0001"))
    worst_ratio = (best_ratio * Decimal("0.75")).quantize(Decimal("0.0001"))

    # 3. Calculate current SWAP liquidity in EUR
    liq_r = await db.execute(
        select(func.sum(Order.quantity - Order.filled_quantity))
        .where(
            Order.market == MarketType.SWAP,
            Order.side == OrderSide.SELL,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.market_maker_id.isnot(None),
        )
    )
    remaining_eua = Decimal(str(liq_r.scalar() or 0))
    current_liq_eur = remaining_eua * eua_price

    # 4. Check if replenishment needed (>= 95% of target → skip)
    if current_liq_eur >= target_eur * Decimal("0.95"):
        return {
            "skipped": True,
            "reason": "Liquidity at target",
            "current_pct": str(round(current_liq_eur / target_eur * 100, 1)),
        }

    # 5. Load active EUA_OFFER market makers
    mm_r = await db.execute(
        select(MarketMakerClient).where(
            and_(
                MarketMakerClient.is_active.is_(True),
                MarketMakerClient.mm_type == MarketMakerType.EUA_OFFER,
            )
        )
    )
    eua_mms = list(mm_r.scalars().all())
    if not eua_mms:
        return {"skipped": True, "reason": "No active EUA_OFFER market makers"}

    # 6. Find current best (highest) ratio in the order book
    best_book_r = await db.execute(
        select(func.max(Order.price))
        .where(
            Order.market == MarketType.SWAP,
            Order.side == OrderSide.SELL,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.market_maker_id.isnot(None),
        )
    )
    current_best_in_book = best_book_r.scalar()
    if current_best_in_book is not None:
        current_best_in_book = Decimal(str(current_best_in_book))
    else:
        # Book is empty — fill from best down to worst
        current_best_in_book = worst_ratio

    # 7. Place orders from best_ratio DOWN to current top-of-book (fill the gap)
    ratio_step = Decimal("0.0001")

    if best_ratio > current_best_in_book:
        # Gap exists above current book — fill from best_ratio down to existing top
        start_ratio = best_ratio
        stop_ratio = current_best_in_book + ratio_step  # don't duplicate existing top
    else:
        # No gap — replenish volume at best_ratio (1-3 orders)
        start_ratio = best_ratio
        stop_ratio = best_ratio  # single level

    orders_created = 0
    liquidity_added_eur = Decimal("0")
    current_ratio = start_ratio
    orders_at_level = 0
    max_at_this_level = random.randint(1, 3)

    for _ in range(_MAX_REPLENISH_ORDERS):
        if current_liq_eur + liquidity_added_eur >= target_eur:
            break
        if current_ratio < stop_ratio and current_ratio < worst_ratio:
            break

        if orders_at_level >= max_at_this_level:
            current_ratio -= ratio_step
            current_ratio = current_ratio.quantize(Decimal("0.0001"))
            orders_at_level = 0
            max_at_this_level = random.randint(1, 3)
            # Re-check after stepping down
            if current_ratio < stop_ratio and current_ratio < worst_ratio:
                break

        # Volume: cap by remaining deficit
        remaining_deficit = target_eur - (current_liq_eur + liquidity_added_eur)
        volume_eur = Decimal(str(round(random.uniform(float(_MIN_VOL), float(_MAX_VOL)), 2)))
        volume_eur = min(volume_eur, remaining_deficit)
        if volume_eur < _MIN_VOL:
            break

        eua_quantity = (volume_eur / eua_price).quantize(Decimal("1"))
        if eua_quantity < 1:
            eua_quantity = Decimal("1")

        mm = random.choice(eua_mms)

        order = Order(
            market=MarketType.SWAP,
            market_maker_id=mm.id,
            certificate_type=CertificateType.EUA,
            side=OrderSide.SELL,
            price=current_ratio,
            quantity=eua_quantity,
            filled_quantity=Decimal("0"),
            status=OrderStatus.OPEN,
        )
        db.add(order)
        orders_created += 1
        orders_at_level += 1
        liquidity_added_eur += eua_quantity * eua_price

    if orders_created > 0:
        await db.flush()

    return {
        "success": True,
        "action": "swap_replenishment",
        "best_ratio": str(best_ratio),
        "gap_from": str(start_ratio),
        "gap_to": str(stop_ratio),
        "orders_created": orders_created,
        "liquidity_added_eur": str(liquidity_added_eur.quantize(Decimal("1"))),
        "total_liquidity_eur": str((current_liq_eur + liquidity_added_eur).quantize(Decimal("1"))),
        "current_liquidity_pct": str(round((current_liq_eur + liquidity_added_eur) / target_eur * 100, 1)),
    }


async def _delayed_swap_replenishment():
    """
    Background task: place replenishment orders one at a time with random 5-15s delays.
    Uses its own DB session (request session is closed by the time this runs).
    Each order is committed individually so it's immediately visible in the order book.
    """
    import asyncio
    import random
    from decimal import Decimal

    from sqlalchemy import and_
    from app.core.database import AsyncSessionLocal
    from app.services.price_scraper import price_scraper

    _MIN_VOL = Decimal("200000")
    _MAX_VOL = Decimal("5000000")
    _MAX_REPLENISH_ORDERS = 50

    try:
        async with AsyncSessionLocal() as db:
            # 1. Load settings
            settings_r = await db.execute(
                select(AutoTradeMarketSettings).where(
                    AutoTradeMarketSettings.market_key == "EUA_SWAP"
                )
            )
            swap_settings = settings_r.scalar_one_or_none()
            if not swap_settings or not swap_settings.enabled:
                logger.info("Delayed replenishment skipped: EUA_SWAP disabled")
                return

            target_eur = swap_settings.target_liquidity or Decimal("90000000")

            # 2. Fetch scraped prices
            try:
                prices = await price_scraper.get_current_prices()
                cea_price = Decimal(str(prices["cea"]["price"]))
                eua_price = Decimal(str(prices["eua"]["price"]))
            except Exception:
                cea_price = Decimal("13.0")
                eua_price = Decimal("75.0")

            if eua_price <= 0:
                logger.info("Delayed replenishment skipped: invalid EUA price")
                return

            base_ratio = (cea_price / eua_price).quantize(Decimal("0.0001"))
            best_ratio = (base_ratio * Decimal("1.15")).quantize(Decimal("0.0001"))
            worst_ratio = (best_ratio * Decimal("0.75")).quantize(Decimal("0.0001"))

            # 3. Current liquidity
            liq_r = await db.execute(
                select(func.sum(Order.quantity - Order.filled_quantity)).where(
                    Order.market == MarketType.SWAP,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),
                )
            )
            remaining_eua = Decimal(str(liq_r.scalar() or 0))
            current_liq_eur = remaining_eua * eua_price

            if current_liq_eur >= target_eur * Decimal("0.95"):
                logger.info("Delayed replenishment skipped: liquidity at target")
                return

            # 4. Load market makers
            mm_r = await db.execute(
                select(MarketMakerClient).where(
                    and_(
                        MarketMakerClient.is_active.is_(True),
                        MarketMakerClient.mm_type == MarketMakerType.EUA_OFFER,
                    )
                )
            )
            eua_mms = list(mm_r.scalars().all())
            if not eua_mms:
                logger.info("Delayed replenishment skipped: no EUA_OFFER MMs")
                return

            # 5. Find current best ratio in book
            best_book_r = await db.execute(
                select(func.max(Order.price)).where(
                    Order.market == MarketType.SWAP,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),
                )
            )
            current_best_in_book = best_book_r.scalar()
            if current_best_in_book is not None:
                current_best_in_book = Decimal(str(current_best_in_book))
            else:
                current_best_in_book = worst_ratio

            # 6. Determine gap range
            ratio_step = Decimal("0.0001")
            if best_ratio > current_best_in_book:
                start_ratio = best_ratio
                stop_ratio = current_best_in_book + ratio_step
            else:
                start_ratio = best_ratio
                stop_ratio = best_ratio

            # 7. Place orders one at a time with delays
            orders_created = 0
            liquidity_added_eur = Decimal("0")
            current_ratio = start_ratio
            orders_at_level = 0
            max_at_this_level = random.randint(1, 3)

            for _ in range(_MAX_REPLENISH_ORDERS):
                if current_liq_eur + liquidity_added_eur >= target_eur:
                    break
                if current_ratio < stop_ratio and current_ratio < worst_ratio:
                    break

                if orders_at_level >= max_at_this_level:
                    current_ratio -= ratio_step
                    current_ratio = current_ratio.quantize(Decimal("0.0001"))
                    orders_at_level = 0
                    max_at_this_level = random.randint(1, 3)
                    if current_ratio < stop_ratio and current_ratio < worst_ratio:
                        break

                remaining_deficit = target_eur - (current_liq_eur + liquidity_added_eur)
                volume_eur = Decimal(str(round(random.uniform(float(_MIN_VOL), float(_MAX_VOL)), 2)))
                volume_eur = min(volume_eur, remaining_deficit)
                if volume_eur < _MIN_VOL:
                    break

                eua_quantity = (volume_eur / eua_price).quantize(Decimal("1"))
                if eua_quantity < 1:
                    eua_quantity = Decimal("1")

                mm = random.choice(eua_mms)

                order = Order(
                    market=MarketType.SWAP,
                    market_maker_id=mm.id,
                    certificate_type=CertificateType.EUA,
                    side=OrderSide.SELL,
                    price=current_ratio,
                    quantity=eua_quantity,
                    filled_quantity=Decimal("0"),
                    status=OrderStatus.OPEN,
                )
                db.add(order)
                await db.commit()

                orders_created += 1
                orders_at_level += 1
                liquidity_added_eur += eua_quantity * eua_price

                logger.info(
                    f"Delayed replenishment: order #{orders_created} at ratio {current_ratio}, "
                    f"+{eua_quantity * eua_price:.0f} EUR"
                )

                # Random delay 5-15 seconds between orders
                delay = random.uniform(5, 15)
                await asyncio.sleep(delay)

            logger.info(
                f"Delayed replenishment complete: {orders_created} orders, "
                f"+{liquidity_added_eur.quantize(Decimal('1'))} EUR"
            )

    except Exception as e:
        logger.error(f"Delayed swap replenishment failed: {e}", exc_info=True)


@router.post("/auto-trade-market-settings/place-random-swap-order")
async def place_random_swap_order(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Reactive SWAP replenishment: fill the gap between best_ratio and current top-of-book.

    - ASK only (SELL EUA)
    - Orders placed from best_ratio (base*1.15) DOWN to current book top
    - Tick step 0.0001, respects 90M EUR liquidity cap
    """
    try:
        result = await _place_random_swap_order_internal(db)
        if result.get("skipped"):
            return result
        await db.commit()
        return result

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error placing random swap order: {e}")
        raise HTTPException(status_code=500, detail="Failed to place random swap order. Please try again.")


@router.get("/auto-trade-market-settings/mm-activity")
async def get_mm_activity(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """
    Aggregated trade activity feed.
    Groups trades by aggressor order and returns VWAP, total qty, total EUR.
    """
    from sqlalchemy.orm import selectinload
    from collections import defaultdict

    trades_result = await db.execute(
        select(CashMarketTrade)
        .where(CashMarketTrade.certificate_type == CertificateType.CEA)
        .options(selectinload(CashMarketTrade.buy_order), selectinload(CashMarketTrade.sell_order))
        .order_by(CashMarketTrade.executed_at.desc())
        .limit(limit * 5)  # fetch more to group properly
    )
    trades = list(trades_result.scalars().all())

    # Group trades by aggressor order
    groups: dict[str, list] = defaultdict(list)
    for t in trades:
        aggressor_side = None
        if t.buy_order and t.sell_order:
            if (t.buy_order.created_at or t.executed_at) >= (t.sell_order.created_at or t.executed_at):
                aggressor_side = "BUY"
            else:
                aggressor_side = "SELL"

        if aggressor_side is None:
            continue  # skip trades without both orders loaded

        aggressor_order_id = str(t.buy_order_id) if aggressor_side == "BUY" else str(t.sell_order_id)
        groups[aggressor_order_id].append((t, aggressor_side))

    # Build aggregated activity
    activity = []
    for _order_id, group_trades in groups.items():
        total_qty = sum(float(t.quantity) for t, _ in group_trades)
        if total_qty <= 0:
            continue  # skip zero-quantity groups
        total_eur = sum(float(t.price) * float(t.quantity) for t, _ in group_trades)
        vwap = total_eur / total_qty
        latest_ts = max((t.executed_at for t, _ in group_trades if t.executed_at), default=None)
        side = group_trades[0][1]  # aggressor side (same for all in group)

        activity.append({
            "side": side,
            "total_quantity": round(total_qty),
            "vwap": round(vwap, 4),
            "total_eur": round(total_eur, 2),
            "fill_count": len(group_trades),
            "timestamp": (latest_ts.isoformat() + "Z") if latest_ts else None,
        })

    # Sort by timestamp descending
    activity.sort(key=lambda x: x["timestamp"] or "", reverse=True)

    return activity[:limit]


@router.get("/auto-trade-market-settings/{market_key}", response_model=AutoTradeMarketSettingsResponse)
async def get_market_settings(
    market_key: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Get auto trade settings for a specific market side."""
    market_key_upper = market_key.upper()
    if market_key_upper not in MARKET_KEY_TO_MM_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market_key. Must be one of: {list(MARKET_KEY_TO_MM_TYPES.keys())}"
        )

    result = await db.execute(
        select(AutoTradeMarketSettings).where(AutoTradeMarketSettings.market_key == market_key_upper)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail=f"Settings for {market_key_upper} not found")

    # Get associated market makers
    mm_types = MARKET_KEY_TO_MM_TYPES.get(market_key_upper, [])
    mm_result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.mm_type.in_(mm_types))
    )
    market_makers = list(mm_result.scalars().all())

    # Calculate current liquidity
    current_liquidity = await _calculate_market_liquidity(db, market_key_upper)
    liquidity_percentage = None
    if settings.target_liquidity and settings.target_liquidity > 0:
        from decimal import Decimal
        liquidity_percentage = (current_liquidity / settings.target_liquidity) * Decimal("100")

    # Check if auto-trader is actively running
    is_online = settings.enabled and await _check_is_online(db, market_key_upper)

    return _build_market_settings_response(
        settings, market_makers, current_liquidity, liquidity_percentage, is_online
    )


@router.put("/auto-trade-market-settings/{market_key}", response_model=AutoTradeMarketSettingsResponse)
async def update_market_settings(
    market_key: str,
    updates: AutoTradeMarketSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_admin_user),
):
    """Update auto trade settings for a specific market side."""
    market_key_upper = market_key.upper()
    if market_key_upper not in MARKET_KEY_TO_MM_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market_key. Must be one of: {list(MARKET_KEY_TO_MM_TYPES.keys())}"
        )

    try:
        result = await db.execute(
            select(AutoTradeMarketSettings).where(AutoTradeMarketSettings.market_key == market_key_upper)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            raise HTTPException(status_code=404, detail=f"Settings for {market_key_upper} not found")

        # Update fields
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)

        settings.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # Get associated market makers
        mm_types = MARKET_KEY_TO_MM_TYPES.get(market_key_upper, [])
        mm_result = await db.execute(
            select(MarketMakerClient).where(MarketMakerClient.mm_type.in_(mm_types))
        )
        market_makers = list(mm_result.scalars().all())

        # Create/update auto-trade rules for each market maker
        await _sync_auto_trade_rules(db, settings, market_makers, market_key_upper)

        await db.commit()
        await db.refresh(settings)

        # Calculate current liquidity
        current_liquidity = await _calculate_market_liquidity(db, market_key_upper)
        liquidity_percentage = None
        if settings.target_liquidity and settings.target_liquidity > 0:
            from decimal import Decimal
            liquidity_percentage = (current_liquidity / settings.target_liquidity) * Decimal("100")

        # Check if auto-trader is actively running
        is_online = settings.enabled and await _check_is_online(db, market_key_upper)

        return _build_market_settings_response(
            settings, market_makers, current_liquidity, liquidity_percentage, is_online
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        handle_database_error(e, "updating market settings")


async def _calculate_market_liquidity(db: AsyncSession, market_key: str) -> "Decimal":
    """Calculate current liquidity for a market side in EUR.

    For CEA markets: SUM(price_EUR * remaining_qty)  — price is already EUR.
    For EUA_SWAP:    SUM(remaining_eua_qty) * scraped_eua_price_EUR
                     (price field = ratio, NOT EUR, so we use scraped EUA price)
    """
    from decimal import Decimal

    if market_key == "EUA_SWAP":
        # SWAP: liquidity = remaining EUA quantity * current EUA price in EUR
        from app.services.price_scraper import price_scraper

        try:
            prices = await price_scraper.get_current_prices()
            eua_price = Decimal(str(prices["eua"]["price"]))
        except Exception:
            eua_price = Decimal("75.0")  # fallback BASE_EUA_EUR

        result = await db.execute(
            select(func.sum(Order.quantity - Order.filled_quantity))
            .where(
                Order.market == MarketType.SWAP,
                Order.side == OrderSide.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                Order.market_maker_id.isnot(None),
            )
        )
        remaining_eua = Decimal(str(result.scalar() or 0))
        return remaining_eua * eua_price

    # Map market_key to certificate_type and side
    if market_key == "CEA_BID":
        cert_type = CertificateType.CEA
        side = OrderSide.BUY
    elif market_key == "CEA_ASK":
        cert_type = CertificateType.CEA
        side = OrderSide.SELL
    else:
        return Decimal("0")

    # Calculate: SUM(price * remaining_quantity) for open MM orders
    result = await db.execute(
        select(func.sum(Order.price * (Order.quantity - Order.filled_quantity)))
        .where(
            Order.certificate_type == cert_type,
            Order.side == side,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.market_maker_id.isnot(None),
        )
    )
    return Decimal(str(result.scalar() or 0))


async def _sync_auto_trade_rules(
    db: AsyncSession,
    settings: AutoTradeMarketSettings,
    market_makers: list,
    market_key: str
) -> None:
    """Create or update auto-trade rules for each market maker based on market settings.

    Each market maker gets one rule that mirrors the market settings.
    Rules are created if they don't exist, or updated if they do.
    """
    from app.models.models import AutoTradeRule, AutoTradePriceMode, AutoTradeQuantityMode

    # Determine order side based on market key
    if market_key == "CEA_BID":
        side = OrderSide.BUY
        rule_name_prefix = "Liquidity Engine BID"
    elif market_key == "CEA_ASK":
        side = OrderSide.SELL
        rule_name_prefix = "Liquidity Engine ASK"
    elif market_key == "EUA_SWAP":
        side = OrderSide.SELL  # Swap offers are sells
        rule_name_prefix = "Liquidity Engine SWAP"
    else:
        return

    for mm in market_makers:
        # Check if rule already exists for this market maker and side
        rule_result = await db.execute(
            select(AutoTradeRule).where(
                AutoTradeRule.market_maker_id == mm.id,
                AutoTradeRule.side == side,
                AutoTradeRule.name.like("Liquidity Engine%")
            )
        )
        rule = rule_result.scalar_one_or_none()

        # Calculate min quantity based on target liquidity and avg_order_count
        min_quantity = None
        if settings.target_liquidity and settings.avg_order_count:
            from decimal import Decimal
            # Each order should be roughly target / avg_order_count EUR value
            # Assuming price ~70 EUR/CEA for quantity calculation
            avg_order_value = settings.target_liquidity / Decimal(str(settings.avg_order_count))
            min_quantity = max(Decimal("1"), avg_order_value / Decimal("70"))

        if rule:
            # Update existing rule
            rule.enabled = settings.enabled
            rule.interval_seconds = settings.interval_seconds
            rule.price_mode = AutoTradePriceMode.RANDOM_SPREAD
            rule.spread_min = settings.price_deviation_pct or Decimal("0.01")
            rule.spread_max = (settings.price_deviation_pct or Decimal("0.01")) * Decimal("3")
            rule.max_price_deviation = settings.price_deviation_pct
            rule.quantity_mode = AutoTradeQuantityMode.RANDOM_RANGE
            rule.min_quantity = min_quantity or Decimal("1")
            rule.max_quantity = (min_quantity or Decimal("1")) * Decimal(str(1 + (settings.volume_variety or 0.5)))
            rule.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            # Schedule next execution if enabled
            if settings.enabled and not rule.next_execution_at:
                rule.next_execution_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            # Create new rule
            rule = AutoTradeRule(
                market_maker_id=mm.id,
                name=f"{rule_name_prefix} - {mm.name}",
                enabled=settings.enabled,
                side=side,
                order_type="LIMIT",
                price_mode=AutoTradePriceMode.RANDOM_SPREAD,
                spread_min=settings.price_deviation_pct or Decimal("0.01"),
                spread_max=(settings.price_deviation_pct or Decimal("0.01")) * Decimal("3"),
                max_price_deviation=settings.price_deviation_pct,
                quantity_mode=AutoTradeQuantityMode.RANDOM_RANGE,
                min_quantity=min_quantity or Decimal("1"),
                max_quantity=(min_quantity or Decimal("1")) * Decimal(str(1 + (settings.volume_variety or 0.5))),
                interval_mode="fixed",
                interval_seconds=settings.interval_seconds,
                next_execution_at=datetime.now(timezone.utc).replace(tzinfo=None) if settings.enabled else None,
            )
            db.add(rule)


# ============================================================================
# ADMIN TESTING TOOLS
# ============================================================================

class AdminRoleUpdateRequest(BaseModel):
    """Request to change admin's own role for testing"""
    role: str


class AdminCreditRequest(BaseModel):
    """Request to credit assets to admin's own entity"""
    asset_type: str  # EUR, CEA, EUA
    amount: Decimal = Field(..., gt=0)


class EntityBalancesResponse(BaseModel):
    """Response with entity balances"""
    eur: Decimal
    cea: Decimal
    eua: Decimal


@router.put("/me/role", response_model=UserResponse)
async def update_my_role(
    request: AdminRoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update admin's own role for testing purposes.

    This allows admins to test the platform from different user perspectives
    by temporarily changing their role.

    Note: Uses get_current_user instead of get_admin_user to allow
    restoring ADMIN role even when currently in a different role.
    Only the original admin user (by email) can use this endpoint.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"update_my_role called with role={request.role} by {current_user.email}")

    # Security: Only allow the designated admin email to use this endpoint
    ADMIN_EMAILS = ["admin@nihaogroup.com"]  # Add more as needed
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(
            status_code=403,
            detail="Only designated admin users can change their role for testing"
        )

    try:
        # Validate role
        role_upper = request.role.upper()
        valid_roles = [r.value for r in UserRole]
        if role_upper not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {valid_roles}"
            )

        # Re-fetch user in current session to avoid detached instance error
        result = await db.execute(select(User).where(User.id == current_user.id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update role
        user.role = UserRole(role_upper)
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await db.refresh(user)

        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            position=user.position,
            role=user.role.value,
            entity_id=user.entity_id,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            nda_signed=user.nda_signed,
            referral_code=user.referral_code,
            last_login=user.last_login,
            created_at=user.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating admin role: {e}")
        await db.rollback()
        raise handle_database_error(e, "updating admin role") from e


@router.post("/me/credit", response_model=EntityBalancesResponse)
async def credit_my_entity(
    request: AdminCreditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Credit assets to admin's own entity for testing purposes.

    This allows admins to quickly add EUR, CEA, or EUA to their entity
    for testing trading functionality.
    """
    from app.models.models import AssetType, TransactionType
    from app.services.balance_utils import update_entity_balance, get_entity_balance

    try:
        # Check admin has an entity
        if not current_user.entity_id:
            raise HTTPException(
                status_code=400,
                detail="Admin user does not have an associated entity. Create one first."
            )

        # Validate asset type
        asset_type_upper = request.asset_type.upper()
        try:
            asset_type = AssetType(asset_type_upper)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid asset type. Must be one of: EUR, CEA, EUA"
            )

        # Credit the entity using ADJUSTMENT type (for admin credits)
        await update_entity_balance(
            db=db,
            entity_id=current_user.entity_id,
            asset_type=asset_type,
            amount=request.amount,
            transaction_type=TransactionType.ADJUSTMENT,
            created_by=current_user.id,
            notes=f"Admin testing credit: {request.amount} {asset_type_upper}",
        )

        await db.commit()

        # Get all balances
        eur_balance = await get_entity_balance(db, current_user.entity_id, AssetType.EUR)
        cea_balance = await get_entity_balance(db, current_user.entity_id, AssetType.CEA)
        eua_balance = await get_entity_balance(db, current_user.entity_id, AssetType.EUA)

        return EntityBalancesResponse(
            eur=eur_balance,
            cea=cea_balance,
            eua=eua_balance,
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "crediting admin entity") from e


@router.get("/me/balances", response_model=EntityBalancesResponse)
async def get_my_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Get admin's entity balances."""
    from app.models.models import AssetType
    from app.services.balance_utils import get_entity_balance

    try:
        if not current_user.entity_id:
            raise HTTPException(
                status_code=400,
                detail="Admin user does not have an associated entity."
            )

        eur_balance = await get_entity_balance(db, current_user.entity_id, AssetType.EUR)
        cea_balance = await get_entity_balance(db, current_user.entity_id, AssetType.CEA)
        eua_balance = await get_entity_balance(db, current_user.entity_id, AssetType.EUA)

        return EntityBalancesResponse(
            eur=eur_balance,
            cea=cea_balance,
            eua=eua_balance,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e, "getting admin balances") from e


# ==================== Settlement Management ====================


@router.get("/settlements/pending")
async def get_admin_pending_settlements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Get all pending settlement batches across ALL entities (Admin only).

    Returns non-SETTLED, non-FAILED settlement batches with entity names
    and primary user contact info for each entity.
    """
    try:
        from ...services.settlement_service import get_pending_settlements as _get_pending

        # Fetch all pending batches (entity_id=None returns all)
        batches = await _get_pending(db=db, entity_id=None)

        # Collect unique entity IDs and fetch one user per entity
        entity_ids = list({b.entity_id for b in batches if b.entity_id})
        user_map: dict[UUID, User] = {}
        if entity_ids:
            from sqlalchemy.orm import load_only

            user_result = await db.execute(
                select(User)
                .where(User.entity_id.in_(entity_ids))
                .options(load_only(User.id, User.entity_id, User.email, User.role))
                .distinct(User.entity_id)
                .order_by(User.entity_id, User.created_at.asc())
            )
            for u in user_result.scalars().all():
                if u.entity_id and u.entity_id not in user_map:
                    user_map[u.entity_id] = u

        result = []
        for batch in batches:
            progress = calculate_settlement_progress(batch)
            entity_name = batch.entity.legal_name if batch.entity else "Unknown"
            user = user_map.get(batch.entity_id) if batch.entity_id else None

            result.append({
                "id": str(batch.id),
                "batch_reference": batch.batch_reference,
                "entity_name": entity_name,
                "settlement_type": batch.settlement_type.value,
                "status": batch.status.value,
                "asset_type": batch.asset_type.value,
                "quantity": int(round(float(batch.quantity))),
                "price": float(batch.price),
                "total_value_eur": float(batch.total_value_eur),
                "expected_settlement_date": batch.expected_settlement_date.isoformat(),
                "actual_settlement_date": (
                    batch.actual_settlement_date.isoformat()
                    if batch.actual_settlement_date else None
                ),
                "progress_percent": progress,
                "user_email": user.email if user else None,
                "user_role": user.role.value if user and user.role else None,
                "created_at": batch.created_at.isoformat(),
                "updated_at": batch.updated_at.isoformat(),
            })

        return {"data": result, "count": len(result)}

    except Exception as e:
        raise handle_database_error(e, "get admin pending settlements") from e


@router.post("/settlements/{batch_id}/settle")
async def settle_batch_now(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Instantly settle a single settlement batch (Admin only).

    - Sets status to SETTLED with audit trail
    - Credits EntityHolding via finalize_settlement
    - Triggers role transitions (CEA_SETTLE→SWAP or EUA_SETTLE→EUA)
    """
    try:
        result = await db.execute(
            select(SettlementBatch).where(SettlementBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()

        if not batch:
            raise HTTPException(status_code=404, detail="Settlement batch not found")

        if batch.status in (SettlementStatus.SETTLED, SettlementStatus.FAILED):
            raise HTTPException(
                status_code=400,
                detail=f"Batch already {batch.status.value} — cannot settle"
            )

        old_status = batch.status.value

        # 1. Update status to SETTLED
        batch.status = SettlementStatus.SETTLED
        batch.actual_settlement_date = datetime.now(timezone.utc).replace(tzinfo=None)
        batch.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # 2. Add audit trail
        db.add(SettlementStatusHistory(
            settlement_batch_id=batch.id,
            status=SettlementStatus.SETTLED,
            notes=f"Instant settle by admin (was {old_status})",
            updated_by=current_user.id,
        ))

        # 3. Finalize — credit EntityHolding + create AssetTransaction
        await SettlementService.finalize_settlement(db, batch, current_user.id)

        # Flush so role transition queries see the SETTLED status
        await db.flush()

        # 4. Trigger role transitions
        from ...services.role_transitions import (
            transition_cea_settle_to_swap_if_all_cea_settled,
            transition_eua_settle_to_eua_if_all_swap_settled,
            transition_swap_to_eua_settle_if_cea_zero,
        )

        entity_id = batch.entity_id
        roles_changed = 0
        if batch.settlement_type == SettlementType.CEA_PURCHASE:
            roles_changed += await transition_cea_settle_to_swap_if_all_cea_settled(
                db, entity_id
            )
        elif batch.settlement_type == SettlementType.SWAP_CEA_TO_EUA:
            roles_changed += await transition_swap_to_eua_settle_if_cea_zero(
                db, entity_id
            )
            roles_changed += await transition_eua_settle_to_eua_if_all_swap_settled(
                db, entity_id
            )

        await db.commit()

        # Notify entity users via WebSocket
        try:
            user_ids = await get_entity_user_ids(db, entity_id)
            if user_ids:
                asyncio.create_task(client_ws_manager.broadcast_to_users(
                    user_ids,
                    {
                        "type": "settlement_updated",
                        "data": {
                            "batch_id": str(batch.id),
                            "status": "SETTLED",
                            "batch_reference": batch.batch_reference,
                        },
                    },
                ))
                asyncio.create_task(client_ws_manager.broadcast_to_users(
                    user_ids,
                    {"type": "balance_updated", "data": {"source": "settlement_completed"}},
                ))
            # Notify backoffice admins
            asyncio.create_task(backoffice_ws_manager.broadcast(
                "settlement_settled",
                {
                    "batch_id": str(batch.id),
                    "batch_reference": batch.batch_reference,
                    "entity_id": str(entity_id),
                    "settled_by": str(current_user.id),
                },
            ))
        except Exception as ws_err:
            logger.warning(f"Failed to send settlement WS notification: {ws_err}")

        msg = f"Settlement {batch.batch_reference} settled instantly ({old_status} → SETTLED)"
        if roles_changed:
            msg += f", {roles_changed} user role(s) advanced"

        logger.info(msg)
        return {"message": msg, "batch_reference": batch.batch_reference}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "settle batch now") from e


# ── Referral / Introducer Management ──────────────────────────────────────


@router.post("/users/create-preintroducer")
async def create_preintroducer(
    email: str = Query(...),  # noqa: B008
    first_name: str = Query(...),  # noqa: B008
    last_name: str = Query(...),  # noqa: B008
    mode: str = Query(...),  # noqa: B008
    password: Optional[str] = Query(None),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Create a PREINTRODUCER user with auto-generated referral code."""
    from ...services.referral_codes import get_unique_referral_code

    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    referral_code = await get_unique_referral_code(db)

    # Load mail config for invitation expiry
    cfg_result = await db.execute(
        select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
    )
    mail_row = cfg_result.scalar_one_or_none()
    invitation_expiry_days = (
        mail_row.invitation_token_expiry_days
        if mail_row and mail_row.invitation_token_expiry_days is not None
        else 7
    )

    if mode == "manual":
        if not password or len(password) < 8:
            raise HTTPException(status_code=400, detail="Password required (min 8 chars)")
        user = User(
            email=email.lower(),
            first_name=first_name,
            last_name=last_name,
            password_hash=hash_password(password),
            role=UserRole.PREINTRODUCER,
            referral_code=referral_code,
            must_change_password=False,
            is_active=True,
            creation_method="manual",
            created_by=admin_user.id,
        )
    else:
        invitation_token = secrets.token_urlsafe(32)
        user = User(
            email=email.lower(),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.PREINTRODUCER,
            referral_code=referral_code,
            invitation_token=invitation_token,
            invitation_sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
            invitation_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=invitation_expiry_days),
            must_change_password=True,
            is_active=False,
            creation_method="invitation",
            created_by=admin_user.id,
        )

    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "creating preintroducer", logger) from e

    return {
        "message": "PREINTRODUCER created",
        "success": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "referral_code": user.referral_code,
        },
    }


@router.post("/introducer/{request_id}/send-nda")
async def send_introducer_nda(
    request_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """For introducer requests without NDA: create user as TRODUCER(nda_signed=false), send invitation email."""
    from ...services.referral_codes import get_unique_referral_code

    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == UUID(request_id))
    )
    contact_request = result.scalar_one_or_none()
    if not contact_request:
        raise HTTPException(status_code=404, detail="Contact request not found")

    existing = await db.execute(select(User).where(User.email == contact_request.contact_email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Load mail config
    cfg_result = await db.execute(
        select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
    )
    mail_row = cfg_result.scalar_one_or_none()
    invitation_expiry_days = (
        mail_row.invitation_token_expiry_days
        if mail_row and mail_row.invitation_token_expiry_days is not None
        else 14
    )

    invitation_token = secrets.token_urlsafe(32)
    referral_code = await get_unique_referral_code(db)

    user = User(
        email=contact_request.contact_email,
        first_name=contact_request.contact_first_name or "",
        last_name=contact_request.contact_last_name or "",
        role=UserRole.TRODUCER,
        referral_code=referral_code,
        nda_signed=False,
        invitation_token=invitation_token,
        invitation_sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
        invitation_expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=invitation_expiry_days),
        must_change_password=True,
        is_active=False,
        creation_method="invitation",
        created_by=admin_user.id,
    )

    try:
        db.add(user)
        # Keep user_role as NDA so the request stays visible in backoffice
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "creating introducer (send NDA)", logger) from e

    # Send NDA invitation email with PDF attachment
    try:
        mail_cfg = None
        if mail_row:
            mail_cfg = {
                "provider": mail_row.provider.value,
                "use_env_credentials": mail_row.use_env_credentials,
                "from_email": mail_row.from_email,
                "resend_api_key": (
                    mail_row.resend_api_key
                    if not mail_row.use_env_credentials
                    and mail_row.provider == MailProvider.RESEND
                    else None
                ),
                "smtp_host": mail_row.smtp_host,
                "smtp_port": mail_row.smtp_port,
                "smtp_use_tls": mail_row.smtp_use_tls,
                "smtp_username": mail_row.smtp_username,
                "smtp_password": mail_row.smtp_password,
                "invitation_link_base_url": mail_row.invitation_link_base_url,
            }
        nda_pdf_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads", "nda", "NDA-Niha-signed.pdf")
        await email_service.send_introducer_nda_invitation(
            user.email, user.first_name, user.invitation_token,
            nda_pdf_path, expiry_days=invitation_expiry_days, mail_config=mail_cfg,
        )
    except Exception:
        logger.exception("Failed to send NDA email for introducer %s", user.email)

    asyncio.create_task(
        backoffice_ws_manager.broadcast("request_updated", {
            "id": str(contact_request.id),
            "user_role": "NDA",
            "request_flow": contact_request.request_flow,
            "introducer_nda_status": "sent",
            "introducer_user_id": str(user.id),
        })
    )

    return {"message": "NDA sent to introducer", "success": True}


@router.post("/buyer/{request_id}/send-nda")
async def send_buyer_nda(
    request_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """For buyer requests without NDA (PRE_NDA): create PRE_NDA user, send NDA invitation email."""
    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == UUID(request_id))
    )
    contact_request = result.scalar_one_or_none()
    if not contact_request:
        raise HTTPException(status_code=404, detail="Contact request not found")

    if contact_request.user_role != ContactStatus.PRE_NDA:
        raise HTTPException(status_code=400, detail="Contact request is not in PRE_NDA status")

    # Check user doesn't already exist
    existing = await db.execute(select(User).where(User.email == contact_request.contact_email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Load mail config
    cfg_result = await db.execute(
        select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
    )
    mail_row = cfg_result.scalar_one_or_none()
    invitation_expiry_days = (
        mail_row.invitation_token_expiry_days
        if mail_row and mail_row.invitation_token_expiry_days is not None
        else 14
    )

    invitation_token = secrets.token_urlsafe(32)

    user = User(
        email=contact_request.contact_email.lower(),
        first_name=contact_request.contact_first_name or "",
        last_name=contact_request.contact_last_name or "",
        role=UserRole.PRE_NDA,
        nda_signed=False,
        invitation_token=invitation_token,
        invitation_sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
        invitation_expires_at=(
            datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=invitation_expiry_days)
        ),
        must_change_password=True,
        is_active=False,
        creation_method="invitation",
        created_by=admin_user.id,
    )

    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "creating PRE_NDA buyer (send NDA)", logger) from e

    # Send PRE_NDA invitation email with NDA PDF
    try:
        mail_cfg = None
        if mail_row:
            mail_cfg = {
                "provider": mail_row.provider.value,
                "use_env_credentials": mail_row.use_env_credentials,
                "from_email": mail_row.from_email,
                "resend_api_key": (
                    mail_row.resend_api_key
                    if not mail_row.use_env_credentials
                    and mail_row.provider == MailProvider.RESEND
                    else None
                ),
                "smtp_host": mail_row.smtp_host,
                "smtp_port": mail_row.smtp_port,
                "smtp_use_tls": mail_row.smtp_use_tls,
                "smtp_username": mail_row.smtp_username,
                "smtp_password": mail_row.smtp_password,
                "invitation_link_base_url": mail_row.invitation_link_base_url,
            }
        nda_pdf_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "uploads", "nda", "NDA-Niha-signed.pdf"
        )
        await email_service.send_pre_nda_invitation(
            user.email, user.first_name, user.invitation_token,
            nda_pdf_path, expiry_days=invitation_expiry_days, mail_config=mail_cfg,
        )
    except Exception:
        logger.exception("Failed to send NDA email for buyer %s", user.email)

    asyncio.create_task(
        backoffice_ws_manager.broadcast("request_updated", {
            "id": str(contact_request.id),
            "user_role": "PRE_NDA",
            "request_flow": "buyer",
            "buyer_nda_status": "sent",
            "buyer_user_id": str(user.id),
        })
    )

    return {"message": "NDA sent to buyer", "success": True}


@router.put("/introducer/{user_id}/approve-nda")
async def approve_introducer_nda(
    user_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Mark a TRODUCER or PRE_NDA user's NDA as signed, upgrade accordingly, activate user, update ContactRequest, send confirmation."""
    result = await db.execute(
        select(User).where(
            User.id == UUID(user_id),
            User.role.in_([UserRole.TRODUCER, UserRole.PREINTRODUCER, UserRole.PRE_NDA]),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Troducer/PREINTRODUCER/PRE_NDA user not found")

    is_pre_nda = user.role == UserRole.PRE_NDA
    request_flow = "buyer" if is_pre_nda else "introducer"

    # Find the associated contact request
    cr_result = await db.execute(
        select(ContactRequest).where(
            ContactRequest.contact_email == user.email,
            ContactRequest.request_flow == request_flow,
        )
    )
    contact_request = cr_result.scalar_one_or_none()

    try:
        if is_pre_nda:
            user.role = UserRole.NDA
        else:
            # TRODUCER or PREINTRODUCER (form-submitted, NDA pending) → INTRODUCER
            user.role = UserRole.INTRODUCER
            user.commission_rate = Decimal("0.010000")  # Default 1%
        user.nda_signed = True
        user.is_active = True
        if contact_request:
            contact_request.user_role = ContactStatus.KYC
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "approving NDA") from e

    # Send confirmation email
    try:
        cfg_result = await db.execute(
            select(MailConfig).order_by(MailConfig.updated_at.desc()).limit(1)
        )
        mail_row = cfg_result.scalar_one_or_none()
        mail_cfg = None
        if mail_row:
            mail_cfg = {
                "provider": mail_row.provider.value,
                "use_env_credentials": mail_row.use_env_credentials,
                "from_email": mail_row.from_email,
                "resend_api_key": (
                    mail_row.resend_api_key
                    if not mail_row.use_env_credentials
                    and mail_row.provider == MailProvider.RESEND
                    else None
                ),
                "smtp_host": mail_row.smtp_host,
                "smtp_port": mail_row.smtp_port,
                "smtp_use_tls": mail_row.smtp_use_tls,
                "smtp_username": mail_row.smtp_username,
                "smtp_password": mail_row.smtp_password,
                "invitation_link_base_url": mail_row.invitation_link_base_url,
            }
        if is_pre_nda:
            await email_service.send_pre_nda_approved(user.email, user.first_name, mail_config=mail_cfg)
        else:
            await email_service.send_introducer_approved(user.email, user.first_name, mail_config=mail_cfg)
    except Exception:
        logger.exception("Failed to send NDA approval email to %s", user.email)

    # Broadcast WS event so request disappears from backoffice list
    if contact_request:
        asyncio.create_task(
            backoffice_ws_manager.broadcast("request_updated", {
                "id": str(contact_request.id),
                "user_role": "KYC",
                "request_flow": request_flow,
            })
        )

    return {"message": "NDA approved", "success": True}


@router.put("/contact-requests/{request_id}/accept-nda")
async def accept_contact_request_nda(
    request_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Mark a contact request's NDA as accepted by admin after review."""
    result = await db.execute(
        select(ContactRequest).where(ContactRequest.id == UUID(request_id))
    )
    contact_request = result.scalar_one_or_none()
    if not contact_request:
        raise HTTPException(status_code=404, detail="Contact request not found")

    if contact_request.user_role != ContactStatus.NDA:
        raise HTTPException(status_code=400, detail="Contact request must be in NDA status to accept NDA")

    # Check NDA file exists (either on ContactRequest or on linked user)
    has_nda = bool(contact_request.nda_file_data)
    if not has_nda:
        user_result = await db.execute(
            select(User).where(
                User.email == contact_request.contact_email.lower(),
                User.nda_file_data.isnot(None),
            )
        )
        linked_user = user_result.scalar_one_or_none()
        if linked_user:
            has_nda = True

    if not has_nda:
        raise HTTPException(status_code=400, detail="No NDA document found to accept")

    try:
        contact_request.nda_accepted = True
        contact_request.nda_accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        contact_request.nda_accepted_by = admin_user.id
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise handle_database_error(e, "accepting NDA", logger) from e

    asyncio.create_task(
        backoffice_ws_manager.broadcast("request_updated", {
            "id": str(contact_request.id),
            "nda_accepted": True,
        })
    )

    return {"message": "NDA accepted", "success": True}


# ==================== Commission Management ====================


@router.get("/commissions")
async def list_all_commissions(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    """List all commissions across all introducers. Admin only."""
    from ...models.models import CommissionLedger, CommissionStatus

    query = (
        select(CommissionLedger)
        .order_by(CommissionLedger.created_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(CommissionLedger.status == CommissionStatus(status))
    result = await db.execute(query)
    entries = result.scalars().all()

    # Get introducer and referred user info
    response = []
    for e in entries:
        introducer = await db.get(User, e.introducer_user_id)
        referred = await db.get(User, e.referred_user_id)
        response.append(
            {
                "id": str(e.id),
                "introducer_user_id": str(e.introducer_user_id),
                "introducer_name": (
                    f"{introducer.first_name} {introducer.last_name}".strip()
                    if introducer
                    else "Unknown"
                ),
                "referred_user_id": str(e.referred_user_id),
                "referred_name": (
                    f"{referred.first_name} {referred.last_name}".strip()
                    if referred
                    else "Unknown"
                ),
                "trade_eur_value": f"{e.trade_eur_value:.2f}",
                "commission_rate": str(e.commission_rate),
                "commission_eur": f"{e.commission_eur:.2f}",
                "status": e.status.value,
                "trade_executed_at": e.trade_executed_at.isoformat() + "Z",
                "created_at": e.created_at.isoformat() + "Z",
                "confirmed_at": (
                    (e.confirmed_at.isoformat() + "Z") if e.confirmed_at else None
                ),
                "paid_at": (e.paid_at.isoformat() + "Z") if e.paid_at else None,
                "notes": e.notes,
            }
        )

    return response


@router.put("/commissions/{commission_id}/confirm")
async def confirm_commission(
    commission_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Confirm a pending commission (PENDING -> CONFIRMED). Admin only."""
    from ...models.models import CommissionLedger, CommissionStatus

    entry = await db.get(CommissionLedger, UUID(commission_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Commission not found")
    if entry.status != CommissionStatus.PENDING:
        raise HTTPException(
            status_code=400, detail=f"Commission is {entry.status.value}, not pending"
        )

    entry.status = CommissionStatus.CONFIRMED
    entry.confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    entry.confirmed_by = admin_user.id
    await db.commit()

    return {"message": "Commission confirmed", "success": True}


@router.put("/commissions/{commission_id}/mark-paid")
async def mark_commission_paid(
    commission_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Mark a confirmed commission as paid (CONFIRMED -> PAID). Admin only."""
    from ...models.models import CommissionLedger, CommissionStatus

    entry = await db.get(CommissionLedger, UUID(commission_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Commission not found")
    if entry.status != CommissionStatus.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail=f"Commission is {entry.status.value}, not confirmed",
        )

    entry.status = CommissionStatus.PAID
    entry.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    return {"message": "Commission marked as paid", "success": True}


@router.put("/users/{user_id}/commission-rate")
async def set_commission_rate(
    user_id: str,
    body: dict,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Set per-introducer commission rate. Admin only."""
    user = await db.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rate_str = body.get("rate")
    if rate_str is None:
        raise HTTPException(status_code=400, detail="Missing 'rate' in body")

    try:
        rate = Decimal(rate_str)
        if rate < 0 or rate > 1:
            raise ValueError("Rate must be between 0 and 1")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid rate. Must be a number between 0 and 1.") from e

    user.commission_rate = rate
    await db.commit()

    return {"message": f"Commission rate set to {rate}", "success": True}
