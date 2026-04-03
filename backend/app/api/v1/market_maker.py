"""Market Maker Admin API endpoints"""

import logging
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_admin_user
from ...models.models import (
    AssetTransaction,
    AutoTradePriceMode,
    AutoTradeQuantityMode,
    AutoTradeRule,
    CertificateType,
    MarketMakerClient,
    MarketMakerType,
    Order,
    OrderSide,
    OrderStatus,
    TicketStatus,
    TransactionType,
    User,
)
from ...schemas.schemas import (
    AssetTransactionCreate,
    AutoTradeRuleCreate,
    AutoTradeRuleResponse,
    AutoTradeRuleUpdate,
    MarketMakerBalance,
    MarketMakerCreate,
    MarketMakerResponse,
    MarketMakerTransactionResponse,
    MarketMakerUpdate,
    ResetPasswordRequest,
)
from ...core.config import settings
from ...services.market_maker_service import MarketMakerService
from ...services.ticket_service import TicketService
from ...services.auto_trade_executor import fill_spread_with_orders, AutoTradeExecutor
from ...models.models import MarketType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market-makers", tags=["Market Makers"])


@router.get("", response_model=List[MarketMakerResponse])
async def list_market_makers(
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(20, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    List all Market Maker clients with current balances and stats.
    Admin-only endpoint.
    """
    # Build query
    query = select(MarketMakerClient).order_by(MarketMakerClient.created_at.desc())

    if is_active is not None:
        query = query.where(MarketMakerClient.is_active == is_active)

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    market_makers = result.scalars().all()

    # Enrich with balances and stats
    response = []
    for mm in market_makers:
        # Get balances
        balances = await MarketMakerService.get_balances(db, mm.id)

        # Format balances for response
        formatted_balances = {
            cert_type: MarketMakerBalance(**balance_data)
            for cert_type, balance_data in balances.items()
        }

        # Get order count
        order_count_result = await db.execute(
            select(func.count(Order.id)).where(Order.market_maker_id == mm.id)
        )
        total_orders = order_count_result.scalar() or 0

        # Get filled orders count (as proxy for trades)
        trade_count_result = await db.execute(
            select(func.count(Order.id)).where(
                and_(Order.market_maker_id == mm.id, Order.status == OrderStatus.FILLED)
            )
        )
        total_trades = trade_count_result.scalar() or 0

        # Extract CEA and EUA balances for frontend compatibility (integers only)
        cea_total = balances.get("CEA", {}).get("total", 0)
        eua_total = balances.get("EUA", {}).get("total", 0)
        cea_balance = int(round(float(cea_total))) if cea_total is not None else None
        eua_balance = int(round(float(eua_total))) if eua_total is not None else None

        response.append(
            MarketMakerResponse(
                id=mm.id,
                user_id=mm.user_id,
                name=mm.name,
                description=mm.description,
                mm_type=mm.mm_type,
                is_active=mm.is_active,
                current_balances=formatted_balances,
                eur_balance=mm.eur_balance,
                cea_balance=Decimal(cea_balance) if cea_balance is not None else None,
                eua_balance=Decimal(eua_balance) if eua_balance is not None else None,
                total_orders=total_orders,
                total_trades=total_trades,
                created_at=mm.created_at,
                updated_at=mm.updated_at,
            )
        )

    return response


@router.post("", response_model=dict)
async def create_market_maker(
    request: Request,
    data: MarketMakerCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create new Market Maker client.
    Admin-only endpoint.

    Returns: {id, ticket_id, message}
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Convert schema enum to model enum
    mm_type = MarketMakerType(data.mm_type.value)

    # Validate constraints based on MM type
    if mm_type == MarketMakerType.CEA_BUYER:
        # CEA_BUYER: Buys CEA with EUR
        if data.initial_balances:
            raise HTTPException(
                status_code=400,
                detail="CEA_BUYER cannot have certificate balances, only EUR",
            )
        if data.initial_eur_balance is None or data.initial_eur_balance <= 0:
            raise HTTPException(
                status_code=400,
                detail="CEA_BUYER must have positive initial_eur_balance",
            )
    elif mm_type == MarketMakerType.CEA_SELLER:
        # CEA_SELLER: Sells CEA for EUR
        if data.initial_eur_balance is not None and data.initial_eur_balance > 0:
            raise HTTPException(
                status_code=400, detail="CEA_SELLER cannot have EUR balance"
            )
        if not data.initial_balances or "CEA" not in data.initial_balances:
            raise HTTPException(
                status_code=400, detail="CEA_SELLER must have initial CEA balance"
            )
        if data.initial_balances["CEA"] <= 0:
            raise HTTPException(
                status_code=400, detail="CEA_SELLER must have positive CEA balance"
            )
        invalid_certs = set(data.initial_balances.keys()) - {"CEA"}
        if invalid_certs:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"CEA_SELLER can only have CEA balance, "
                    f"found: {invalid_certs}"
                ),
            )
    elif mm_type == MarketMakerType.EUA_OFFER:
        # EUA_OFFER: Offers EUA for swap operations
        if data.initial_eur_balance is not None and data.initial_eur_balance > 0:
            raise HTTPException(
                status_code=400,
                detail="EUA_OFFER cannot have EUR balance",
            )
        if not data.initial_balances or "EUA" not in data.initial_balances:
            raise HTTPException(
                status_code=400, detail="EUA_OFFER must have initial EUA balance"
            )
        if data.initial_balances["EUA"] <= 0:
            raise HTTPException(
                status_code=400,
                detail="EUA_OFFER must have positive EUA balance",
            )
    else:
        raise HTTPException(
            status_code=500, detail=f"Unknown market maker type: {mm_type}"
        )

    # Create Market Maker
    mm_client, ticket_id = await MarketMakerService.create_market_maker(
        db=db,
        name=data.name,
        email=data.email,
        description=data.description,
        created_by_id=admin_user.id,
        mm_type=mm_type,
        initial_balances=data.initial_balances,
        initial_eur_balance=data.initial_eur_balance,
    )

    logger.info(
        "Admin %s created Market Maker %s (ID: %s)",
        admin_user.email,
        mm_client.name,
        mm_client.id,
    )

    return {
        "id": str(mm_client.id),
        "ticket_id": ticket_id,
        "message": f"Market Maker '{mm_client.name}' created successfully",
    }


# =============================================================================
# Fill Spread Endpoint (placed before {market_maker_id} routes to avoid 404)
# =============================================================================


@router.post("/fill-spread/{certificate_type}", response_model=dict)
async def fill_spread(
    certificate_type: str,
    quantity_per_level: Decimal = Query(Decimal("100000"), gt=0, description="Quantity to place at each price level (min 100,000)"),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Fill the spread between best bid and best ask with orders at each 0.1 EUR price level.

    This creates market depth by placing orders at every 0.1 EUR step between
    the current best bid and best ask, effectively narrowing the spread.

    - Uses CEA_BUYER market makers for bid orders
    - Uses CEA_SELLER market makers for ask orders

    Admin-only endpoint.
    """
    # Validate certificate type
    try:
        cert_type = CertificateType(certificate_type.upper())
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid certificate_type: {certificate_type}. Must be CEA or EUA",
        ) from e

    # Determine market type
    if cert_type == CertificateType.CEA:
        market_type = MarketType.CEA_CASH
    else:
        market_type = MarketType.SWAP

    # Execute fill spread
    result = await fill_spread_with_orders(
        db=db,
        certificate_type=cert_type,
        market_type=market_type,
        admin_user_id=admin_user.id,
        quantity_per_level=quantity_per_level,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"],
        )

    logger.info(
        f"Admin {admin_user.email} filled spread for {certificate_type}: "
        f"{result['orders_created']} orders created"
    )

    return result


@router.post("/reset-all", response_model=dict)
async def reset_all_market_makers(
    request: ResetPasswordRequest,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Reset all Market Makers: zero balances and delete ALL associated data including:
    - Asset transactions
    - Ticket logs
    - Cash market trades (where MM is involved)
    - Orders placed by MMs

    Keeps MarketMakerClient and User records intact.
    Requires password confirmation.
    Admin-only endpoint.
    """
    # Validate password (from env MM_RESET_PASSWORD; required in production)
    expected = settings.MM_RESET_PASSWORD
    if not expected:
        if not settings.DEBUG:
            raise HTTPException(
                status_code=503,
                detail="MM_RESET_PASSWORD not configured. Set env var to enable reset.",
            )
        expected = "Niha010!"  # dev-only fallback when env unset
    if request.password != expected:
        raise HTTPException(status_code=403, detail="Invalid reset password")

    from ...models.models import CashMarketTrade, CommissionLedger, TicketLog

    # Get all market maker IDs
    mm_result = await db.execute(select(MarketMakerClient.id))
    mm_ids = [row[0] for row in mm_result.fetchall()]

    if not mm_ids:
        return {"message": "No market makers to reset", "reset_count": 0}

    # Use subquery instead of explicit ID list to avoid PostgreSQL's
    # 32,767 parameter limit (auto-trade creates tens of thousands of orders)
    mm_orders_subq = select(Order.id).where(Order.market_maker_id.in_(mm_ids))

    # Subquery for cash_market_trades we are about to delete (MM-related)
    mm_trades_subq = select(CashMarketTrade.id).where(
        CashMarketTrade.market_maker_id.in_(mm_ids)
        | CashMarketTrade.buy_order_id.in_(mm_orders_subq)
        | CashMarketTrade.sell_order_id.in_(mm_orders_subq)
    )

    # 0. Delete commission_ledger rows that reference those trades (FK constraint)
    await db.execute(
        CommissionLedger.__table__.delete().where(
            CommissionLedger.cash_market_trade_id.in_(mm_trades_subq)
        )
    )

    # 1. Delete cash market trades where MM is directly involved
    #    OR where the trade references an MM order
    await db.execute(
        CashMarketTrade.__table__.delete().where(
            CashMarketTrade.market_maker_id.in_(mm_ids)
            | CashMarketTrade.buy_order_id.in_(mm_orders_subq)
            | CashMarketTrade.sell_order_id.in_(mm_orders_subq)
        )
    )

    # Count orders before deleting (for response)
    orders_count_result = await db.execute(
        select(func.count()).select_from(Order).where(Order.market_maker_id.in_(mm_ids))
    )
    orders_deleted = orders_count_result.scalar() or 0

    # 2. Delete all orders placed by MMs
    await db.execute(
        Order.__table__.delete().where(Order.market_maker_id.in_(mm_ids))
    )

    # 3. Delete asset transactions for all MMs
    await db.execute(
        AssetTransaction.__table__.delete().where(
            AssetTransaction.market_maker_id.in_(mm_ids)
        )
    )

    # 4. Delete ticket logs for MM-related tickets
    await db.execute(
        TicketLog.__table__.delete().where(TicketLog.market_maker_id.in_(mm_ids))
    )

    # 5. Reset balances for all MMs (keep entities)
    await db.execute(
        MarketMakerClient.__table__.update()
        .where(MarketMakerClient.id.in_(mm_ids))
        .values(eur_balance=0)
    )

    # Create audit ticket in the same transaction (before commit) so it is persisted.
    # get_db only closes the session and does not commit; create_ticket after commit
    # would run in a new transaction that gets rolled back on close().
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="MM_RESET_ALL",
        entity_type="System",
        entity_id=admin_user.id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        request_payload={
            "action": "reset_all_market_makers",
            "mm_count": len(mm_ids),
            "orders_deleted": orders_deleted,
        },
        tags=["market_maker", "reset", "admin"],
    )

    await db.commit()

    message = (
        f"Successfully reset {len(mm_ids)} market makers. "
        f"Deleted {orders_deleted} orders and associated trades."
    )

    logger.info(
        f"Admin {admin_user.email} reset all Market Makers "
        f"({len(mm_ids)} MMs, {orders_deleted} orders deleted)"
    )

    return {
        "message": message,
        "reset_count": len(mm_ids),
        "orders_deleted": orders_deleted,
        "ticket_id": ticket.ticket_id,
    }


@router.get("/{market_maker_id}", response_model=MarketMakerResponse)
async def get_market_maker(
    market_maker_id: UUID,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get Market Maker details by ID.
    Admin-only endpoint.
    """
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Get balances
    balances = await MarketMakerService.get_balances(db, mm.id)

    # Format balances
    formatted_balances = {
        cert_type: MarketMakerBalance(**balance_data)
        for cert_type, balance_data in balances.items()
    }

    # Get order count
    order_count_result = await db.execute(
        select(func.count(Order.id)).where(Order.market_maker_id == mm.id)
    )
    total_orders = order_count_result.scalar() or 0

    # Get filled orders count
    trade_count_result = await db.execute(
        select(func.count(Order.id)).where(
            and_(Order.market_maker_id == mm.id, Order.status == OrderStatus.FILLED)
        )
    )
    total_trades = trade_count_result.scalar() or 0

    return MarketMakerResponse(
        id=mm.id,
        user_id=mm.user_id,
        name=mm.name,
        description=mm.description,
        is_active=mm.is_active,
        current_balances=formatted_balances,
        total_orders=total_orders,
        total_trades=total_trades,
        created_at=mm.created_at,
        updated_at=mm.updated_at,
    )


@router.put("/{market_maker_id}", response_model=dict)
async def update_market_maker(
    market_maker_id: UUID,
    data: MarketMakerUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update Market Maker details.
    Admin-only endpoint.

    Returns: {ticket_id, message}
    """
    # Get existing MM
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Capture before state
    before_state = await TicketService.get_entity_state(db, "MarketMaker", mm.id)

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mm, field, value)

    await db.commit()
    await db.refresh(mm)

    # Capture after state
    after_state = await TicketService.get_entity_state(db, "MarketMaker", mm.id)

    # Create audit ticket
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="MM_UPDATED",
        entity_type="MarketMaker",
        entity_id=mm.id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        market_maker_id=mm.id,
        request_payload=update_data,
        before_state=before_state,
        after_state=after_state,
        tags=["market_maker", "update"],
    )

    logger.info(
        f"Admin {admin_user.email} updated Market Maker {mm.name} (ID: {mm.id})"
    )

    return {
        "ticket_id": ticket.ticket_id,
        "message": f"Market Maker '{mm.name}' updated successfully",
    }


@router.delete("/{market_maker_id}", response_model=dict)
async def delete_market_maker(
    market_maker_id: UUID,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Soft delete Market Maker (set is_active = False).
    Admin-only endpoint.

    Returns: {ticket_id, message}
    """
    # Get existing MM
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    if not mm.is_active:
        raise HTTPException(status_code=400, detail="Market Maker already inactive")

    # Check for open orders
    open_orders_result = await db.execute(
        select(func.count(Order.id)).where(
            and_(
                Order.market_maker_id == mm.id,
                Order.status.in_([OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]),
            )
        )
    )
    open_orders_count = open_orders_result.scalar() or 0

    if open_orders_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot deactivate Market Maker with {open_orders_count} "
                f"open orders. Cancel orders first."
            ),
        )

    # Capture before state
    before_state = await TicketService.get_entity_state(db, "MarketMaker", mm.id)

    # Soft delete
    mm.is_active = False

    # Also deactivate associated user
    result = await db.execute(select(User).where(User.id == mm.user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active = False

    await db.commit()
    await db.refresh(mm)

    # Capture after state
    after_state = await TicketService.get_entity_state(db, "MarketMaker", mm.id)

    # Create audit ticket
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="MM_DELETED",
        entity_type="MarketMaker",
        entity_id=mm.id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        market_maker_id=mm.id,
        before_state=before_state,
        after_state=after_state,
        tags=["market_maker", "deletion"],
    )

    logger.info(
        f"Admin {admin_user.email} deactivated Market Maker {mm.name} (ID: {mm.id})"
    )

    return {
        "ticket_id": ticket.ticket_id,
        "message": f"Market Maker '{mm.name}' deactivated successfully",
    }


@router.get("/{market_maker_id}/balances", response_model=dict)
async def get_market_maker_balances(
    market_maker_id: UUID,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get current balances for Market Maker.
    Admin-only endpoint.

    Returns: {CEA: {available, locked, total}, EUA: {...}}
    """
    # Verify MM exists
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Get balances
    balances = await MarketMakerService.get_balances(db, market_maker_id)

    # Format for response - balances already includes EUR with locked amounts calculated
    formatted_balances = {
        cert_type: MarketMakerBalance(**balance_data).model_dump()
        for cert_type, balance_data in balances.items()
    }

    return formatted_balances


@router.get(
    "/{market_maker_id}/transactions",
    response_model=List[MarketMakerTransactionResponse],
)
async def list_market_maker_transactions(
    market_maker_id: UUID,
    certificate_type: Optional[str] = None,
    transaction_type: Optional[str] = None,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(50, ge=1, le=100),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    List all transactions for a Market Maker.
    Admin-only endpoint.
    """
    # Verify MM exists
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Build query
    query = (
        select(AssetTransaction)
        .where(AssetTransaction.market_maker_id == market_maker_id)
        .order_by(AssetTransaction.created_at.desc())
    )

    if certificate_type:
        try:
            cert_type_enum = CertificateType(certificate_type)
            query = query.where(AssetTransaction.certificate_type == cert_type_enum)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid certificate_type: {certificate_type}"
            ) from e

    if transaction_type:
        try:
            trans_type_enum = TransactionType(transaction_type)
            query = query.where(AssetTransaction.transaction_type == trans_type_enum)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid transaction_type: {transaction_type}"
            ) from e

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return [
        MarketMakerTransactionResponse(
            id=t.id,
            ticket_id=t.ticket_id,
            market_maker_id=t.market_maker_id,
            certificate_type=t.certificate_type.value,
            transaction_type=t.transaction_type.value,
            amount=t.amount,
            balance_after=t.balance_after,
            notes=t.notes,
            created_by=t.created_by,
            created_at=t.created_at,
        )
        for t in transactions
    ]


@router.post("/{market_maker_id}/transactions", response_model=dict)
async def create_market_maker_transaction(
    market_maker_id: UUID,
    data: AssetTransactionCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create asset transaction (deposit/withdrawal) for Market Maker.
    Admin-only endpoint.

    For withdrawals, validates sufficient available balance.

    Returns: {transaction_id, ticket_id, balance_after, message}
    """
    # Verify MM exists and is active
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    if not mm.is_active:
        raise HTTPException(status_code=400, detail="Market Maker is inactive")

    # Validate certificate type
    try:
        cert_type = CertificateType(data.certificate_type)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid certificate_type: {data.certificate_type}"
        ) from e

    # Validate transaction type
    try:
        trans_type = TransactionType(data.transaction_type)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid transaction_type: {data.transaction_type}"
        ) from e

    # Calculate amount (negative for withdrawals)
    amount = data.amount if trans_type == TransactionType.DEPOSIT else -data.amount

    # For withdrawals, validate sufficient balance
    if trans_type == TransactionType.WITHDRAWAL:
        has_sufficient = await MarketMakerService.validate_sufficient_balance(
            db=db,
            market_maker_id=market_maker_id,
            certificate_type=cert_type,
            required_amount=data.amount,
        )

        if not has_sufficient:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient available balance for "
                    f"{cert_type.value} withdrawal"
                ),
            )

    # Create transaction
    transaction, ticket_id = await MarketMakerService.create_transaction(
        db=db,
        market_maker_id=market_maker_id,
        certificate_type=cert_type,
        transaction_type=trans_type,
        amount=amount,
        notes=data.notes,
        created_by_id=admin_user.id,
    )

    logger.info(
        f"Admin {admin_user.email} created {trans_type.value} transaction "
        f"for Market Maker {mm.name}: {data.amount} {cert_type.value}"
    )

    return {
        "transaction_id": str(transaction.id),
        "ticket_id": ticket_id,
        "balance_after": float(transaction.balance_after),
        "message": (
            f"{trans_type.value.title()} of {data.amount} {cert_type.value} "
            f"completed successfully"
        ),
    }


@router.post("/{market_maker_id}/eur-deposit", response_model=dict)
async def deposit_eur_to_market_maker(
    market_maker_id: UUID,
    amount: Decimal = Query(..., gt=0, description="EUR amount to deposit"),  # noqa: B008
    notes: Optional[str] = Query(None, description="Optional notes"),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Deposit EUR to a Market Maker (typically CEA_BUYER type).
    Admin-only endpoint.

    Returns: {balance_before, balance_after, ticket_id, message}
    """
    # Verify MM exists and is active
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    if not mm.is_active:
        raise HTTPException(status_code=400, detail="Market Maker is inactive")

    balance_before = mm.eur_balance

    # Update EUR balance
    mm.eur_balance = mm.eur_balance + amount
    await db.flush()

    # Create audit ticket
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="MM_EUR_DEPOSIT",
        entity_type="MarketMaker",
        entity_id=mm.id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        request_payload={
            "amount": str(amount),
            "notes": notes,
        },
        before_state={"eur_balance": str(balance_before)},
        after_state={"eur_balance": str(mm.eur_balance)},
        tags=["market_maker", "eur_deposit"],
    )

    await db.commit()

    logger.info(
        f"Admin {admin_user.email} deposited {amount} EUR "
        f"to Market Maker {mm.name} (balance: {balance_before} -> {mm.eur_balance})"
    )

    return {
        "balance_before": float(balance_before),
        "balance_after": float(mm.eur_balance),
        "ticket_id": ticket.ticket_id,
        "message": f"Deposited {amount} EUR to {mm.name}",
    }


@router.post("/{market_maker_id}/eur-withdrawal", response_model=dict)
async def withdraw_eur_from_market_maker(
    market_maker_id: UUID,
    amount: Decimal = Query(..., gt=0, description="EUR amount to withdraw"),  # noqa: B008
    notes: Optional[str] = Query(None, description="Optional notes"),  # noqa: B008
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Withdraw EUR from a Market Maker (typically CEA_BUYER type).
    Admin-only endpoint. Validates sufficient balance.

    Returns: {balance_before, balance_after, ticket_id, message}
    """
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    if not mm.is_active:
        raise HTTPException(status_code=400, detail="Market Maker is inactive")

    if mm.eur_balance < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient EUR balance. Available: {mm.eur_balance}",
        )

    balance_before = mm.eur_balance
    mm.eur_balance = mm.eur_balance - amount
    await db.flush()

    ticket = await TicketService.create_ticket(
        db=db,
        action_type="MM_EUR_WITHDRAWAL",
        entity_type="MarketMaker",
        entity_id=mm.id,
        status=TicketStatus.SUCCESS,
        user_id=admin_user.id,
        request_payload={
            "amount": str(amount),
            "notes": notes,
        },
        before_state={"eur_balance": str(balance_before)},
        after_state={"eur_balance": str(mm.eur_balance)},
        tags=["market_maker", "eur_withdrawal"],
    )

    await db.commit()

    logger.info(
        f"Admin {admin_user.email} withdrew {amount} EUR "
        f"from Market Maker {mm.name} (balance: {balance_before} -> {mm.eur_balance})"
    )

    return {
        "balance_before": float(balance_before),
        "balance_after": float(mm.eur_balance),
        "ticket_id": ticket.ticket_id,
        "message": f"Withdrew {amount} EUR from {mm.name}",
    }


# =============================================================================
# Auto Trade Rule Endpoints
# =============================================================================


@router.get("/auto-trade-rules/monitor", response_model=dict)
async def monitor_auto_trade_rules(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get monitoring status for all auto-trade rules across all market makers.
    Returns health status, last execution time, and next scheduled execution.

    Admin-only endpoint.
    """
    from datetime import datetime, timezone

    # Get all auto trade rules with their market makers
    result = await db.execute(
        select(AutoTradeRule, MarketMakerClient)
        .join(MarketMakerClient, AutoTradeRule.market_maker_id == MarketMakerClient.id)
        .order_by(MarketMakerClient.name, AutoTradeRule.name)
    )
    rows = result.all()

    now = datetime.now(timezone.utc)
    rules_status = []

    for rule, mm in rows:
        # Determine health status
        health = "healthy"
        health_reason = None

        if not rule.enabled:
            health = "disabled"
            health_reason = "Rule is disabled"
        elif not mm.is_active:
            health = "inactive"
            health_reason = "Market maker is inactive"
        elif rule.next_execution_at:
            # Make next_execution_at timezone-aware for comparison
            next_exec = rule.next_execution_at
            if next_exec.tzinfo is None:
                next_exec = next_exec.replace(tzinfo=timezone.utc)

            # If next execution was more than 5 minutes ago, something might be wrong
            overdue_seconds = (now - next_exec).total_seconds()
            if overdue_seconds > 300:  # 5 minutes overdue
                health = "overdue"
                health_reason = f"Overdue by {int(overdue_seconds // 60)} minutes"
            elif overdue_seconds > 60:  # 1 minute overdue
                health = "delayed"
                health_reason = f"Delayed by {int(overdue_seconds)} seconds"

        # Calculate time until next execution
        time_until_next = None
        if rule.next_execution_at and rule.enabled:
            next_exec = rule.next_execution_at
            if next_exec.tzinfo is None:
                next_exec = next_exec.replace(tzinfo=timezone.utc)
            time_until_next = int((next_exec - now).total_seconds())

        rules_status.append({
            "id": str(rule.id),
            "name": rule.name,
            "market_maker_id": str(mm.id),
            "market_maker_name": mm.name,
            "enabled": rule.enabled,
            "side": rule.side.value if rule.side else None,
            "health": health,
            "health_reason": health_reason,
            "last_executed_at": rule.last_executed_at.isoformat() if rule.last_executed_at else None,
            "next_execution_at": rule.next_execution_at.isoformat() if rule.next_execution_at else None,
            "time_until_next_seconds": time_until_next,
            "execution_count": rule.execution_count or 0,
            "interval_seconds": rule.interval_seconds or (rule.interval_minutes * 60 if rule.interval_minutes else 60),
        })

    # Summary stats
    total = len(rules_status)
    enabled = sum(1 for r in rules_status if r["enabled"])
    healthy = sum(1 for r in rules_status if r["health"] == "healthy")
    overdue = sum(1 for r in rules_status if r["health"] == "overdue")

    return {
        "summary": {
            "total_rules": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "healthy": healthy,
            "overdue": overdue,
        },
        "rules": rules_status,
        "timestamp": now.isoformat(),
    }


@router.get(
    "/{market_maker_id}/auto-trade-rules",
    response_model=List[AutoTradeRuleResponse],
)
async def list_auto_trade_rules(
    market_maker_id: UUID,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    List all auto trade rules for a Market Maker.
    Admin-only endpoint.
    """
    # Verify MM exists
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Get all rules
    result = await db.execute(
        select(AutoTradeRule)
        .where(AutoTradeRule.market_maker_id == market_maker_id)
        .order_by(AutoTradeRule.created_at)
    )
    rules = result.scalars().all()

    return [
        AutoTradeRuleResponse(
            id=rule.id,
            market_maker_id=rule.market_maker_id,
            name=rule.name,
            enabled=rule.enabled,
            side=rule.side.value,
            order_type=rule.order_type,
            price_mode=rule.price_mode.value,
            fixed_price=rule.fixed_price,
            spread_from_best=rule.spread_from_best,
            spread_min=rule.spread_min,
            spread_max=rule.spread_max,
            percentage_from_market=rule.percentage_from_market,
            max_price_deviation=rule.max_price_deviation,
            quantity_mode=rule.quantity_mode.value,
            fixed_quantity=rule.fixed_quantity,
            percentage_of_balance=rule.percentage_of_balance,
            min_quantity=rule.min_quantity,
            max_quantity=rule.max_quantity,
            interval_mode=rule.interval_mode,
            interval_minutes=rule.interval_minutes or 1,
            interval_min_minutes=rule.interval_min_minutes,
            interval_max_minutes=rule.interval_max_minutes,
            interval_seconds=rule.interval_seconds,
            interval_min_seconds=rule.interval_min_seconds,
            interval_max_seconds=rule.interval_max_seconds,
            min_balance=rule.min_balance,
            max_active_orders=rule.max_active_orders,
            last_executed_at=rule.last_executed_at,
            next_execution_at=rule.next_execution_at,
            execution_count=rule.execution_count or 0,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        for rule in rules
    ]


@router.post("/{market_maker_id}/auto-trade-rules", response_model=dict)
async def create_auto_trade_rule(
    market_maker_id: UUID,
    data: AutoTradeRuleCreate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a new auto trade rule for a Market Maker.
    Admin-only endpoint.
    """
    # Verify MM exists
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Convert schema enums to model enums
    price_mode = AutoTradePriceMode(data.price_mode.value)
    quantity_mode = AutoTradeQuantityMode(data.quantity_mode.value)
    side = OrderSide(data.side.value)

    # Create rule
    rule = AutoTradeRule(
        market_maker_id=market_maker_id,
        name=data.name,
        enabled=data.enabled,
        side=side,
        order_type=data.order_type,
        price_mode=price_mode,
        fixed_price=data.fixed_price,
        spread_from_best=data.spread_from_best,
        spread_min=data.spread_min,
        spread_max=data.spread_max,
        percentage_from_market=data.percentage_from_market,
        max_price_deviation=data.max_price_deviation,
        quantity_mode=quantity_mode,
        fixed_quantity=data.fixed_quantity,
        percentage_of_balance=data.percentage_of_balance,
        min_quantity=data.min_quantity,
        max_quantity=data.max_quantity,
        interval_mode=data.interval_mode,
        interval_minutes=data.interval_minutes,
        interval_min_minutes=data.interval_min_minutes,
        interval_max_minutes=data.interval_max_minutes,
        min_balance=data.min_balance,
        max_active_orders=data.max_active_orders,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    logger.info(
        f"Admin {admin_user.email} created auto trade rule '{rule.name}' "
        f"for Market Maker {mm.name}"
    )

    return {
        "id": str(rule.id),
        "message": f"Auto trade rule '{rule.name}' created successfully",
    }


@router.put("/{market_maker_id}/auto-trade-rules/{rule_id}", response_model=dict)
async def update_auto_trade_rule(
    market_maker_id: UUID,
    rule_id: UUID,
    data: AutoTradeRuleUpdate,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Update an auto trade rule.
    Admin-only endpoint.
    """
    # Verify MM exists
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Get rule
    result = await db.execute(
        select(AutoTradeRule).where(
            and_(
                AutoTradeRule.id == rule_id,
                AutoTradeRule.market_maker_id == market_maker_id,
            )
        )
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Auto trade rule not found")

    # Update fields
    update_data = data.model_dump(exclude_unset=True)

    # Convert enums if present
    if "price_mode" in update_data and update_data["price_mode"] is not None:
        update_data["price_mode"] = AutoTradePriceMode(update_data["price_mode"].value)
    if "quantity_mode" in update_data and update_data["quantity_mode"] is not None:
        update_data["quantity_mode"] = AutoTradeQuantityMode(
            update_data["quantity_mode"].value
        )
    if "side" in update_data and update_data["side"] is not None:
        update_data["side"] = OrderSide(update_data["side"].value)

    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)

    logger.info(
        f"Admin {admin_user.email} updated auto trade rule '{rule.name}' "
        f"for Market Maker {mm.name}"
    )

    return {
        "id": str(rule.id),
        "message": f"Auto trade rule '{rule.name}' updated successfully",
    }


@router.delete("/{market_maker_id}/auto-trade-rules/{rule_id}", response_model=dict)
async def delete_auto_trade_rule(
    market_maker_id: UUID,
    rule_id: UUID,
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Delete an auto trade rule.
    Admin-only endpoint.
    """
    # Verify MM exists
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(status_code=404, detail="Market Maker not found")

    # Get rule
    result = await db.execute(
        select(AutoTradeRule).where(
            and_(
                AutoTradeRule.id == rule_id,
                AutoTradeRule.market_maker_id == market_maker_id,
            )
        )
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Auto trade rule not found")

    rule_name = rule.name
    await db.delete(rule)
    await db.commit()

    logger.info(
        f"Admin {admin_user.email} deleted auto trade rule '{rule_name}' "
        f"from Market Maker {mm.name}"
    )

    return {
        "message": f"Auto trade rule '{rule_name}' deleted successfully",
    }


# =============================================================================
# Auto Trade Execution Endpoint
# =============================================================================


@router.post("/execute-auto-trade", response_model=dict)
async def execute_auto_trade(
    admin_user: User = Depends(get_admin_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Manually trigger execution of all ready auto-trade rules.

    This executes all enabled rules that are past their scheduled execution time.
    Use this to manually trigger auto-trade without waiting for the background executor.

    Admin-only endpoint.
    """
    results = await AutoTradeExecutor.execute_all_ready_rules(
        db=db,
        admin_user_id=admin_user.id,
    )

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    logger.info(
        f"Admin {admin_user.email} triggered auto-trade execution: "
        f"{len(successful)} successful, {len(failed)} failed"
    )

    return {
        "total_rules_processed": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "results": results,
    }
