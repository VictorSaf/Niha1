"""Logging and Audit Trail API endpoints"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_db
from ...core.security import get_admin_user
from ...models.models import Entity, MarketMakerClient, TicketLog, TicketStatus, User
from ...schemas.schemas import TicketLogResponse, TicketLogStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logging", tags=["Logging & Audit"])


@router.get("/tickets", response_model=Dict[str, Any])
async def list_tickets(
    # Date range filters
    start_date: Optional[datetime] = Query(  # noqa: B008
        None, description="Filter tickets from this date"
    ),
    end_date: Optional[datetime] = Query(  # noqa: B008
        None, description="Filter tickets until this date"
    ),
    # Entity filters
    action_type: Optional[str] = Query(  # noqa: B008
        None, description="Filter by action type (e.g., ORDER_PLACED)"
    ),
    entity_type: Optional[str] = Query(  # noqa: B008
        None, description="Filter by entity type (e.g., Order, User)"
    ),
    entity_id: Optional[UUID] = Query(None, description="Filter by specific entity ID"),  # noqa: B008
    # Actor filters
    user_id: Optional[UUID] = Query(  # noqa: B008
        None, description="Filter by user who performed action"
    ),
    market_maker_id: Optional[UUID] = Query(None, description="Filter by market maker"),  # noqa: B008
    # Status filter
    status: Optional[TicketStatus] = Query(  # noqa: B008
        None, description="Filter by status (SUCCESS/FAILED)"
    ),
    # Search filters
    search: Optional[str] = Query(  # noqa: B008
        None, description="Search in ticket_id, action_type, entity_type"
    ),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),  # noqa: B008
    # Pagination
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    List all audit tickets with comprehensive filtering.

    Supports filtering by:
    - Date range (start_date, end_date)
    - Action type (ORDER_PLACED, MM_CREATED, etc.)
    - Entity type and ID
    - User or Market Maker
    - Status (SUCCESS/FAILED)
    - Text search
    - Tags

    Returns paginated results with total count.
    """
    # Build base query with eager loading for user/entity/MM enrichment
    query = select(TicketLog).options(
        selectinload(TicketLog.user).selectinload(User.entity),
        selectinload(TicketLog.market_maker),
    )
    filters = []

    # Date range filters
    if start_date:
        filters.append(TicketLog.timestamp >= start_date)
    if end_date:
        filters.append(TicketLog.timestamp <= end_date)

    # Action and entity filters
    if action_type:
        filters.append(TicketLog.action_type == action_type)
    if entity_type:
        filters.append(TicketLog.entity_type == entity_type)
    if entity_id:
        filters.append(TicketLog.entity_id == entity_id)

    # Actor filters
    if user_id:
        filters.append(TicketLog.user_id == user_id)
    if market_maker_id:
        filters.append(TicketLog.market_maker_id == market_maker_id)

    # Status filter
    if status:
        filters.append(TicketLog.status == status)

    # Search filter - search in ticket_id, action_type, entity_type
    if search:
        search_pattern = f"%{search}%"
        filters.append(
            or_(
                TicketLog.ticket_id.ilike(search_pattern),
                TicketLog.action_type.ilike(search_pattern),
                TicketLog.entity_type.ilike(search_pattern),
            )
        )

    # Tags filter
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
        # Check if any of the provided tags are in the ticket's tags array
        filters.append(TicketLog.tags.overlap(tag_list))

    # Apply all filters
    if filters:
        query = query.where(and_(*filters))

    # Order by timestamp descending (most recent first)
    query = query.order_by(desc(TicketLog.timestamp))

    # Get total count
    count_query = select(func.count()).select_from(TicketLog)
    if filters:
        count_query = count_query.where(and_(*filters))

    result = await db.execute(count_query)
    total = result.scalar()

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    tickets = result.scalars().all()

    # Build enriched response with user/entity/MM info
    tickets_data = []
    for ticket in tickets:
        base = TicketLogResponse.model_validate(ticket).model_dump()
        # Enrich with user info
        user = ticket.user
        if user:
            base["user_email"] = user.email
            base["user_role"] = user.role.value if user.role else None
            entity = user.entity
            base["user_company"] = entity.name if entity else None
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            base["user_full_name"] = full_name or user.email
        else:
            base["user_email"] = None
            base["user_role"] = None
            base["user_company"] = None
            base["user_full_name"] = None
        # Enrich with market maker info
        mm = ticket.market_maker
        base["mm_name"] = mm.name if mm else None

        # For TRADE_EXECUTED tickets, resolve buyer/seller MM and entity names
        if ticket.action_type == "TRADE_EXECUTED" and ticket.response_data:
            r = ticket.response_data
            for key, uid, name_key in [
                ("buyer_mm_id", "buyer_mm_id", "buyer_mm_name"),
                ("seller_mm_id", "seller_mm_id", "seller_mm_name"),
                ("buyer_entity_id", "buyer_entity_id", "buyer_entity_name"),
                ("seller_entity_id", "seller_entity_id", "seller_entity_name"),
            ]:
                raw = r.get(key)
                if not raw:
                    continue
                try:
                    u = UUID(raw) if isinstance(raw, str) else raw
                except (TypeError, ValueError):
                    continue
                if "entity" in key:
                    result = await db.execute(select(Entity.name).where(Entity.id == u))
                else:
                    result = await db.execute(
                        select(MarketMakerClient.name).where(MarketMakerClient.id == u)
                    )
                val = result.scalar()
                if val is not None:
                    base[name_key] = val

        tickets_data.append(base)

    return {
        "tickets": tickets_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


@router.get("/tickets/{ticket_id}", response_model=TicketLogResponse)
async def get_ticket_details(
    ticket_id: str,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get full details for a specific ticket.

    Returns complete ticket information including:
    - All metadata
    - Request/response payloads
    - Before/after states
    - Related tickets
    - Tags
    """
    result = await db.execute(select(TicketLog).where(TicketLog.ticket_id == ticket_id))
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    return TicketLogResponse.model_validate(ticket)


@router.get("/stats", response_model=TicketLogStats)
async def get_logging_stats(
    # Date range for stats
    start_date: Optional[datetime] = Query(None, description="Stats from this date"),  # noqa: B008
    end_date: Optional[datetime] = Query(None, description="Stats until this date"),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get dashboard statistics for audit logs.

    Returns:
    - Total action count
    - Success/failure counts
    - Breakdown by action type
    - Top users by action count
    - Actions over time (daily aggregation)
    """
    # Build base query with date filters
    filters = []
    if start_date:
        filters.append(TicketLog.timestamp >= start_date)
    if end_date:
        filters.append(TicketLog.timestamp <= end_date)

    # Total actions
    count_query = select(func.count()).select_from(TicketLog)
    if filters:
        count_query = count_query.where(and_(*filters))

    result = await db.execute(count_query)
    total_actions = result.scalar()

    # Success/failure counts
    success_query = (
        select(func.count())
        .select_from(TicketLog)
        .where(TicketLog.status == TicketStatus.SUCCESS)
    )
    failed_query = (
        select(func.count())
        .select_from(TicketLog)
        .where(TicketLog.status == TicketStatus.FAILED)
    )

    if filters:
        success_query = success_query.where(and_(*filters))
        failed_query = failed_query.where(and_(*filters))

    result = await db.execute(success_query)
    success_count = result.scalar()

    result = await db.execute(failed_query)
    failed_count = result.scalar()

    # Breakdown by action type
    action_type_query = (
        select(TicketLog.action_type, func.count().label("count"))
        .group_by(TicketLog.action_type)
        .order_by(desc("count"))
    )

    if filters:
        action_type_query = action_type_query.where(and_(*filters))

    result = await db.execute(action_type_query)
    by_action_type = {row.action_type: row.count for row in result}

    # Top users by action count (join with Entity for company name)
    user_query = (
        select(
            TicketLog.user_id,
            User.email,
            Entity.name.label("company_name"),
            func.count().label("action_count"),
        )
        .join(User, TicketLog.user_id == User.id, isouter=True)
        .join(Entity, User.entity_id == Entity.id, isouter=True)
        .group_by(TicketLog.user_id, User.email, Entity.name)
        .order_by(desc("action_count"))
        .limit(10)
    )

    if filters:
        user_query = user_query.where(and_(*filters))

    result = await db.execute(user_query)
    by_user = [
        {
            "user_id": str(row.user_id) if row.user_id else None,
            "email": row.email,
            "company_name": row.company_name,
            "action_count": row.action_count,
        }
        for row in result
    ]

    # Actions over time (daily aggregation for last 30 days if no date range specified)
    # Use naive UTC for DB query
    if not start_date:
        time_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    else:
        time_start = start_date

    time_query = (
        select(
            func.date(TicketLog.timestamp).label("date"), func.count().label("count")
        )
        .where(TicketLog.timestamp >= time_start)
        .group_by(func.date(TicketLog.timestamp))
        .order_by("date")
    )

    if end_date:
        time_query = time_query.where(TicketLog.timestamp <= end_date)

    result = await db.execute(time_query)
    actions_over_time = [
        {"date": row.date.isoformat(), "count": row.count} for row in result
    ]

    return TicketLogStats(
        total_actions=total_actions,
        success_count=success_count,
        failed_count=failed_count,
        by_action_type=by_action_type,
        by_user=by_user,
        actions_over_time=actions_over_time,
    )


@router.get("/market-maker-actions", response_model=Dict[str, Any])
async def list_market_maker_actions(
    market_maker_id: Optional[UUID] = Query(None, description="Filter by specific MM"),  # noqa: B008
    start_date: Optional[datetime] = Query(None, description="From date"),  # noqa: B008
    end_date: Optional[datetime] = Query(None, description="Until date"),  # noqa: B008
    status: Optional[TicketStatus] = Query(None, description="Filter by status"),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Pre-filtered view for Market Maker actions.

    Shows only tickets where market_maker_id is not null.
    Useful for monitoring MM activity, order placements, balance changes.
    """
    # Build query - filter for MM actions only
    query = select(TicketLog).where(TicketLog.market_maker_id.isnot(None))
    filters = [TicketLog.market_maker_id.isnot(None)]

    # Additional filters
    if market_maker_id:
        filters.append(TicketLog.market_maker_id == market_maker_id)
    if start_date:
        filters.append(TicketLog.timestamp >= start_date)
    if end_date:
        filters.append(TicketLog.timestamp <= end_date)
    if status:
        filters.append(TicketLog.status == status)

    # Apply filters
    query = query.where(and_(*filters))
    query = query.order_by(desc(TicketLog.timestamp))

    # Get total count
    count_query = select(func.count()).select_from(TicketLog).where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    tickets = result.scalars().all()

    # Convert to response format
    tickets_data = [TicketLogResponse.model_validate(ticket) for ticket in tickets]

    return {
        "tickets": tickets_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


@router.get("/failed-actions", response_model=Dict[str, Any])
async def list_failed_actions(
    start_date: Optional[datetime] = Query(None, description="From date"),  # noqa: B008
    end_date: Optional[datetime] = Query(None, description="Until date"),  # noqa: B008
    action_type: Optional[str] = Query(None, description="Filter by action type"),  # noqa: B008
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),  # noqa: B008
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Pre-filtered view for failed actions.

    Shows only tickets with status=FAILED.
    Critical for monitoring system errors, failed operations, and debugging.
    """
    # Build query - filter for failed actions only
    filters = [TicketLog.status == TicketStatus.FAILED]

    # Additional filters
    if start_date:
        filters.append(TicketLog.timestamp >= start_date)
    if end_date:
        filters.append(TicketLog.timestamp <= end_date)
    if action_type:
        filters.append(TicketLog.action_type == action_type)
    if entity_type:
        filters.append(TicketLog.entity_type == entity_type)

    # Apply filters
    query = select(TicketLog).where(and_(*filters))
    query = query.order_by(desc(TicketLog.timestamp))

    # Get total count
    count_query = select(func.count()).select_from(TicketLog).where(and_(*filters))
    result = await db.execute(count_query)
    total = result.scalar()

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    tickets = result.scalars().all()

    # Convert to response format
    tickets_data = [TicketLogResponse.model_validate(ticket) for ticket in tickets]

    return {
        "tickets": tickets_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }
