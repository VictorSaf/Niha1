"""
CEA Cash Market API Router

Order-driven market with order book, market depth, and FIFO matching.
Trade CEA certificates with EUR.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, text
from sqlalchemy.orm import joinedload

from ...core.database import get_db
from ...core.exceptions import handle_database_error
from ...core.security import get_funded_user
from ...models.models import (
    AssetType,
    CashMarketTrade,
    Entity,
    MarketMakerClient,
    MarketType,
    Order,
    OrderStatus,
    PriceHistory,
    Seller,
    TicketStatus,
    User,
)
from ...services.limit_order_matching import LimitOrderMatcher
from ...services.ticket_service import TicketService
from ...models.models import CertificateType as CertTypeEnum
from ...models.models import OrderSide as OrderSideEnum
from ...schemas.schemas import (
    CashMarketTradeResponse,
    CertificateType,
    MarketDepthPoint,
    MarketDepthResponse,
    MarketOrderRequest,
    MarketStatsResponse,
    MessageResponse,
    OHLCCandle,
    OrderBookLevel,
    OrderBookResponse,
    OrderCreate,
    OrderExecutionResponse,
    OrderFill,
    OrderPreviewRequest,
    OrderPreviewResponse,
    OrderResponse,
    OrderSide,
)
from ..v1.client_ws import client_ws_manager
from ...services.balance_utils import get_entity_eur_balance
from ...services.order_matching import (
    execute_market_buy_order,
    get_effective_fee_rate,
    get_entity_balance,
    get_real_orderbook,
    preview_buy_order,
)

logger = logging.getLogger(__name__)

# Price step for CEA cash market (0.01 EUR)
PRICE_STEP = Decimal("0.01")


def validate_price_step(price: Decimal) -> bool:
    """
    Validate that price respects the quote step of 0.01 EUR.
    Returns True if price is a valid multiple of 0.01.
    """
    # Check if price divided by step is a whole number
    remainder = price % PRICE_STEP
    return remainder == Decimal("0")


router = APIRouter(prefix="/cash-market", tags=["CEA Cash"])


# NOTE: OrderBookSimulator removed - all data is now real from database


@router.get("/orderbook/{certificate_type}", response_model=OrderBookResponse)
async def get_orderbook(
    certificate_type: CertificateType,
    db=Depends(get_db),  # noqa: B008
):
    """
    Get the REAL order book for a specific certificate type.
    Returns bids (buy orders from clients) and asks (sell orders from Market Makers).

    NOTE: Only CEA is supported. Clients can only BUY, Market Makers provide liquidity.
    """
    # Use real order book from database
    orderbook = await get_real_orderbook(db, certificate_type.value)

    return OrderBookResponse(
        certificate_type=orderbook["certificate_type"],
        bids=[OrderBookLevel(**b) for b in orderbook["bids"]],
        asks=[OrderBookLevel(**a) for a in orderbook["asks"]],
        spread=orderbook["spread"],
        best_bid=orderbook["best_bid"],
        best_ask=orderbook["best_ask"],
        last_price=orderbook["last_price"],
        volume_24h=orderbook["volume_24h"],
        change_24h=orderbook["change_24h"],
        high_24h=orderbook.get("high_24h"),
        low_24h=orderbook.get("low_24h"),
    )


@router.get("/depth/{certificate_type}", response_model=MarketDepthResponse)
async def get_market_depth(
    certificate_type: CertificateType,
    db=Depends(get_db),  # noqa: B008
):
    """
    Get REAL market depth data for visualization.
    Returns cumulative quantities at each price level from actual orders.
    """
    orderbook = await get_real_orderbook(db, certificate_type.value)

    # Convert to depth points (already have cumulative from get_real_orderbook)
    bid_depth = [
        {"price": b["price"], "cumulative_quantity": b["cumulative_quantity"]}
        for b in orderbook["bids"]
    ]
    ask_depth = [
        {"price": a["price"], "cumulative_quantity": a["cumulative_quantity"]}
        for a in orderbook["asks"]
    ]

    return MarketDepthResponse(
        certificate_type=certificate_type.value,
        bids=[MarketDepthPoint(**b) for b in bid_depth],
        asks=[MarketDepthPoint(**a) for a in ask_depth],
    )


@router.get("/trades/{certificate_type}", response_model=List[CashMarketTradeResponse])
async def get_recent_trades(
    certificate_type: CertificateType,
    limit: int = Query(50, ge=1, le=5000),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Get recent executed trades for a certificate type. Response includes real `side`
    (aggressor: BUY if buy order was created at or after sell order, else SELL).
    """
    cert_enum = CertTypeEnum.CEA if certificate_type.value == "CEA" else CertTypeEnum.EUA

    result = await db.execute(
        select(CashMarketTrade)
        .where(CashMarketTrade.certificate_type == cert_enum)
        .order_by(CashMarketTrade.executed_at.desc())
        .limit(limit)
        .options(
            joinedload(CashMarketTrade.buy_order),
            joinedload(CashMarketTrade.sell_order),
        )
    )
    trades = result.unique().scalars().all()

    # Uptick/downtick rule: color reflects price direction vs previous trade.
    # Trades are sorted DESC (newest first), so index i+1 is the previous trade in time.
    # For consecutive same-price trades, carry the last known direction (no flicker).
    trades_list = list(trades)
    sides: list[str] = ["BUY"] * len(trades_list)
    last_direction = "BUY"
    # Walk oldest→newest (reverse of the DESC list) to propagate direction correctly
    for i in range(len(trades_list) - 1, -1, -1):
        if i + 1 < len(trades_list):
            cur = float(trades_list[i].price)
            prev = float(trades_list[i + 1].price)
            if cur > prev:
                last_direction = "BUY"
            elif cur < prev:
                last_direction = "SELL"
            # Same price: keep last_direction (carry)
        sides[i] = last_direction

    return [
        CashMarketTradeResponse(
            id=t.id,
            certificate_type=t.certificate_type.value,
            price=float(t.price),
            quantity=int(round(float(t.quantity))),
            side=sides[i],
            executed_at=t.executed_at,
        )
        for i, t in enumerate(trades_list)
    ]


@router.get("/ohlc/{certificate_type}", response_model=List[OHLCCandle])
async def get_ohlc(
    certificate_type: CertificateType,
    interval: int = Query(900, ge=60, le=2592000),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Get OHLC candlestick data aggregated from executed trades.
    `interval` is bucket size in seconds (default 900 = 15m).
    """
    cert_enum = CertTypeEnum.CEA if certificate_type.value == "CEA" else CertTypeEnum.EUA

    result = await db.execute(
        text("""
            SELECT
                FLOOR(EXTRACT(EPOCH FROM executed_at) / :interval)::bigint * :interval AS time,
                (array_agg(price ORDER BY executed_at ASC))[1] AS open,
                MAX(price) AS high,
                MIN(price) AS low,
                (array_agg(price ORDER BY executed_at DESC))[1] AS close,
                SUM(quantity) AS volume
            FROM cash_market_trades
            WHERE certificate_type = :cert_type
            GROUP BY time
            ORDER BY time ASC
        """),
        {"interval": interval, "cert_type": cert_enum.value},
    )
    rows = result.fetchall()

    return [
        OHLCCandle(
            time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
        for row in rows
    ]


@router.get("/stats/{certificate_type}", response_model=MarketStatsResponse)
async def get_market_stats(
    certificate_type: CertificateType,
    db=Depends(get_db),  # noqa: B008
):
    """
    Get REAL market statistics for a certificate type from database.
    """
    orderbook = await get_real_orderbook(db, certificate_type.value)

    # Get 24h trade stats from database - use naive UTC for DB query
    cert_enum = CertTypeEnum.CEA if certificate_type.value == "CEA" else CertTypeEnum.EUA
    yesterday = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

    result = await db.execute(
        select(CashMarketTrade)
        .where(
            and_(
                CashMarketTrade.certificate_type == cert_enum,
                CashMarketTrade.executed_at >= yesterday,
            )
        )
    )
    trades_24h = result.scalars().all()

    # Calculate real stats
    if trades_24h:
        prices = [float(t.price) for t in trades_24h]
        volumes = [float(t.quantity) for t in trades_24h]
        high_24h = max(prices)
        low_24h = min(prices)
        volume_24h = sum(volumes)
        # Change calculation: compare last trade to first trade in 24h
        change_24h = round(((prices[0] - prices[-1]) / prices[-1]) * 100, 2) if len(prices) > 1 else 0.0
    else:
        high_24h = orderbook["last_price"]
        low_24h = orderbook["last_price"]
        volume_24h = 0
        change_24h = 0.0

    return MarketStatsResponse(
        certificate_type=certificate_type.value,
        last_price=orderbook["last_price"],
        change_24h=change_24h,
        high_24h=high_24h,
        low_24h=low_24h,
        volume_24h=int(round(volume_24h)) if trades_24h else 0,
        total_bids=len(orderbook["bids"]),
        total_asks=len(orderbook["asks"]),
    )


@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: OrderCreate,
    current_user: User = Depends(get_funded_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Place a new order in the cash market.
    Creates a real order in the database linked to the user's entity.
    FUNDED or ADMIN only.

    RULE: Regular clients can only place BUY orders (no speculation).
    Market Makers have full freedom (BID and ASK).
    """
    if not current_user.entity_id:
        raise HTTPException(
            status_code=400, detail="User must have an entity to place orders"
        )

    # Check if user is a Market Maker (they have full freedom)
    mm_result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.user_id == current_user.id)
    )
    is_market_maker = mm_result.scalar_one_or_none() is not None

    # Regular clients can only BUY - no speculation allowed
    if not is_market_maker and order.side.value == "SELL":
        raise HTTPException(
            status_code=403,
            detail="Regular clients can only place BUY orders. SELL orders are reserved for Market Makers."
        )

    # Validate price step (0.01 EUR)
    price = Decimal(str(order.price))
    if not validate_price_step(price):
        raise HTTPException(
            status_code=400,
            detail=f"Price must be a multiple of {PRICE_STEP} EUR. Got {order.price}, expected values like 9.30, 9.31, 9.50, etc."
        )

    try:
        # Create the order in database
        new_order = Order(
            market=MarketType.CEA_CASH,
            entity_id=current_user.entity_id,
            certificate_type=CertTypeEnum(order.certificate_type.value),
            side=OrderSideEnum(order.side.value),
            price=Decimal(str(order.price)),
            quantity=Decimal(str(order.quantity)),
            filled_quantity=Decimal("0"),
            status=OrderStatus.OPEN,
        )

        db.add(new_order)
        await db.flush()  # Get order ID before ticket creation

        # Create audit ticket for order placement
        await TicketService.create_ticket(
            db=db,
            action_type="ORDER_PLACED",
            entity_type="Order",
            entity_id=new_order.id,
            status=TicketStatus.SUCCESS,
            user_id=current_user.id,
            request_payload={
                "certificate_type": order.certificate_type.value,
                "side": order.side.value,
                "price": float(order.price),
                "quantity": float(order.quantity),
            },
            response_data={
                "order_id": str(new_order.id),
                "status": new_order.status.value,
            },
            tags=["order", "cash_market", order.side.value.lower()],
        )

        # Try to match the order against the book immediately
        # This ensures we never have crossing orders (negative spread)
        matching_result = await LimitOrderMatcher.match_incoming_order(
            db=db,
            incoming_order=new_order,
            user_id=current_user.id,
        )

        await db.commit()
        await db.refresh(new_order)

        # Notify all connected clients that the order book changed
        asyncio.create_task(client_ws_manager.broadcast_to_all(
            {"type": "orderbook_updated", "data": {"certificate_type": new_order.certificate_type.value}},
        ))
        # Push each new trade so ticker and ACTIVITY update in sync (same source, streaming)
        for m in matching_result.matches:
            exec_at = m.executed_at
            asyncio.create_task(client_ws_manager.broadcast_to_all({
                "type": "trade_executed",
                "data": {
                    "id": str(m.trade_id),
                    "certificate_type": new_order.certificate_type.value,
                    "price": float(m.price),
                    "quantity": int(round(float(m.quantity))),
                    "side": new_order.side.value,
                    "executed_at": exec_at.isoformat() if hasattr(exec_at, "isoformat") else str(exec_at),
                },
            }))

        return OrderResponse(
            id=new_order.id,
            entity_id=new_order.entity_id,
            certificate_type=new_order.certificate_type.value,
            side=new_order.side.value,
            price=float(new_order.price),
            quantity=int(round(float(new_order.quantity))),
            filled_quantity=int(round(float(new_order.filled_quantity or 0))),
            remaining_quantity=int(round(float(new_order.quantity - (new_order.filled_quantity or 0)))),
            status=new_order.status.value,
            created_at=new_order.created_at,
            updated_at=new_order.updated_at,
        )
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        if "redis" in str(e).lower() or "connection" in str(e).lower():
            logger.error("Order placement failed (Redis/ticket): %s", e, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="Ticket service temporarily unavailable. Please try again.",
            ) from e
        raise handle_database_error(e, "place order", logger) from e


@router.get("/orders/my", response_model=List[OrderResponse])
async def get_my_orders(
    status: Optional[str] = Query(  # noqa: B008
        None, description="Filter by status: OPEN, FILLED, CANCELLED"
    ),
    certificate_type: Optional[CertificateType] = None,
    current_user: User = Depends(get_funded_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Get the current user's orders from the database.
    Returns orders linked to the user's entity. FUNDED or ADMIN only.
    """
    if not current_user.entity_id:
        return []  # User has no entity, no orders

    # Build query
    query = select(Order).where(Order.entity_id == current_user.entity_id)

    # Apply filters
    if status:
        try:
            status_enum = OrderStatus(status)
            query = query.where(Order.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter

    if certificate_type:
        query = query.where(
            Order.certificate_type == CertTypeEnum(certificate_type.value)
        )

    # Order by most recent first
    query = query.order_by(Order.created_at.desc()).limit(100)

    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        OrderResponse(
            id=o.id,
            entity_id=o.entity_id,
            certificate_type=o.certificate_type.value,
            side=o.side.value,
            price=float(o.price),
            quantity=int(round(float(o.quantity))),
            filled_quantity=int(round(float(o.filled_quantity or 0))),
            remaining_quantity=int(round(float(o.quantity - (o.filled_quantity or 0)))),
            status=o.status.value,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )
        for o in orders
    ]


@router.delete("/orders/{order_id}", response_model=MessageResponse)
async def cancel_order(
    order_id: str, current_user: User = Depends(get_funded_user), db=Depends(get_db)  # noqa: B008
):
    """
    Cancel an open order.

    RULE: Regular clients CANNOT cancel orders - they can only MODIFY price.
    Only Market Makers can cancel orders.
    """
    if not current_user.entity_id:
        raise HTTPException(status_code=400, detail="User must have an entity")

    # Check if user is a Market Maker (only they can cancel)
    mm_result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.user_id == current_user.id)
    )
    is_market_maker = mm_result.scalar_one_or_none() is not None

    if not is_market_maker:
        raise HTTPException(
            status_code=403,
            detail="Order cancellation is not allowed. You can only modify the price of your order."
        )

    # Find the order
    try:
        order_uuid = uuid.UUID(order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid order ID") from e

    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Verify ownership (Market Maker must own the order)
    if order.entity_id != current_user.entity_id and order.market_maker_id is None:
        raise HTTPException(
            status_code=403, detail="Not authorized to cancel this order"
        )

    # Check if order can be cancelled
    if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status {order.status.value}",
        )

    # Capture before state
    before_state = {
        "status": order.status.value,
        "filled_quantity": float(order.filled_quantity) if order.filled_quantity else 0,
    }

    # Cancel the order
    order.status = OrderStatus.CANCELLED
    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create audit ticket for order cancellation
    ticket = await TicketService.create_ticket(
        db=db,
        action_type="ORDER_CANCELLED",
        entity_type="Order",
        entity_id=order.id,
        status=TicketStatus.SUCCESS,
        user_id=current_user.id,
        request_payload={"order_id": order_id},
        response_data={"cancelled_at": datetime.now(timezone.utc).isoformat()},  # isoformat is string, OK
        before_state=before_state,
        after_state={"status": "CANCELLED"},
        tags=["order", "cancel"],
    )

    await db.commit()

    # Notify all connected clients that the order book changed
    asyncio.create_task(client_ws_manager.broadcast_to_all(
        {"type": "orderbook_updated", "data": {"certificate_type": order.certificate_type.value}},
    ))

    return MessageResponse(
        message=f"Order {order_id} cancelled. Ticket: {ticket.ticket_id}", success=True
    )


class OrderModifyRequest(BaseModel):
    """Request to modify an existing order's price"""
    new_price: float = Field(..., gt=0, description="New limit price for the order")


@router.put("/orders/{order_id}/price", response_model=OrderResponse)
async def modify_order_price(
    order_id: str,
    request: OrderModifyRequest,
    current_user: User = Depends(get_funded_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Modify the price of an open order.

    RULE: Regular clients can modify price but NOT cancel orders.
    This is the only way for clients to adjust their position.
    """
    if not current_user.entity_id:
        raise HTTPException(status_code=400, detail="User must have an entity")

    # Find the order
    try:
        order_uuid = uuid.UUID(order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid order ID") from e

    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Verify ownership
    if order.entity_id != current_user.entity_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this order"
        )

    # Check if order can be modified
    if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify order with status {order.status.value}",
        )

    # Capture before state
    before_state = {
        "price": float(order.price),
        "status": order.status.value,
    }

    # Update the price
    old_price = float(order.price)
    order.price = Decimal(str(request.new_price))
    # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
    order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Create audit ticket for order modification
    await TicketService.create_ticket(
        db=db,
        action_type="ORDER_MODIFIED",
        entity_type="Order",
        entity_id=order.id,
        status=TicketStatus.SUCCESS,
        user_id=current_user.id,
        request_payload={
            "order_id": order_id,
            "new_price": request.new_price,
        },
        response_data={
            "old_price": old_price,
            "new_price": request.new_price,
            "modified_at": datetime.now(timezone.utc).isoformat(),
        },
        before_state=before_state,
        after_state={"price": request.new_price},
        tags=["order", "modify", "price_change"],
    )

    await db.commit()
    await db.refresh(order)

    # Notify all connected clients that the order book changed
    asyncio.create_task(client_ws_manager.broadcast_to_all(
        {"type": "orderbook_updated", "data": {"certificate_type": order.certificate_type.value}},
    ))

    return OrderResponse(
        id=order.id,
        entity_id=order.entity_id,
        certificate_type=order.certificate_type.value,
        side=order.side.value,
        price=float(order.price),
        quantity=int(round(float(order.quantity))),
        filled_quantity=int(round(float(order.filled_quantity or 0))),
        remaining_quantity=int(round(float(order.quantity - (order.filled_quantity or 0)))),
        status=order.status.value,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


# ====================
# REAL CEA ORDER BOOK ENDPOINTS
# ====================


@router.get("/cea/orderbook", response_model=OrderBookResponse)
async def get_cea_orderbook(db=Depends(get_db)):  # noqa: B008
    """
    Get the real CEA order book from database.
    Returns sell orders from registered sellers sorted by price-time priority (FIFO).
    """
    # Fetch real CEA sell orders sorted by:
    # price ASC (best price first), then by time ASC (FIFO)
    result = await db.execute(
        select(Order, Seller)
        .join(Seller, Order.seller_id == Seller.id)
        .where(
            and_(
                Order.certificate_type == CertTypeEnum.CEA,
                Order.side == OrderSideEnum.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        .order_by(Order.price.asc(), Order.created_at.asc())
    )
    orders = result.all()

    # Aggregate orders by price level for display
    price_levels = {}
    for order, seller in orders:
        remaining = float(order.quantity) - float(order.filled_quantity)
        price_key = float(order.price)
        if price_key not in price_levels:
            price_levels[price_key] = {
                "price": price_key,
                "quantity": 0,
                "order_count": 0,
                "cumulative_quantity": 0,
                "seller_codes": [],
            }
        price_levels[price_key]["quantity"] += remaining
        price_levels[price_key]["order_count"] += 1
        price_levels[price_key]["seller_codes"].append(seller.client_code)

    # Convert to sorted list and calculate cumulative (CEA quantities as integers)
    asks = sorted(price_levels.values(), key=lambda x: x["price"])
    cumulative = 0
    for ask in asks:
        cumulative += ask["quantity"]
        ask["cumulative_quantity"] = int(round(cumulative))
        ask["quantity"] = int(round(ask["quantity"]))

    # Calculate market stats
    best_ask = asks[0]["price"] if asks else None
    last_price = best_ask if best_ask else 63.0  # Default CEA price
    total_volume = sum(a["quantity"] for a in asks)

    return OrderBookResponse(
        certificate_type="CEA",
        bids=[],  # No real bids yet - buyers come from entities
        asks=[
            OrderBookLevel(
                price=a["price"],
                quantity=a["quantity"],
                order_count=a["order_count"],
                cumulative_quantity=a["cumulative_quantity"],
            )
            for a in asks
        ],
        spread=None,
        best_bid=None,
        best_ask=best_ask,
        last_price=last_price,
        volume_24h=total_volume,
        change_24h=0.0,  # TODO: Calculate from real 24h trade data
    )


@router.get("/cea/sellers")
async def get_cea_sellers(db=Depends(get_db)):  # noqa: B008
    """
    Get all CEA sellers with their available inventory.
    """
    result = await db.execute(
        select(Seller).where(Seller.is_active.is_(True)).order_by(Seller.client_code)
    )
    sellers = result.scalars().all()

    return [
        {
            "client_code": s.client_code,
            "name": s.name,
            "company_name": s.company_name,
            "cea_balance": int(float(s.cea_balance)) if s.cea_balance else 0,
            "cea_sold": int(float(s.cea_sold)) if s.cea_sold else 0,
            "total_transactions": s.total_transactions or 0,
        }
        for s in sellers
    ]


@router.post("/cea/buy")
async def buy_cea_fifo(amount_eur: float, entity_id: str, db=Depends(get_db)):  # noqa: B008
    """
    Execute a CEA buy order using FIFO price-time priority matching.

    This creates multiple transactions with multiple sellers to fill a single buy order.
    The buyer spends their entire cash balance to buy CEA from all available sellers.

    Algorithm:
    1. Fetch all open CEA sell orders sorted by price ASC (best price),
       then created_at ASC (FIFO)
    2. Match against orders until buyer's funds are exhausted or no more orders
    3. Create CashMarketTrade for each matched order
    4. Update seller statistics
    """
    # CNY to EUR conversion rate
    CNY_TO_EUR = 0.127

    # Fetch entity to verify balance
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    available_balance = float(entity.balance_amount or 0)
    if available_balance <= 0:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Use the minimum of requested amount and available balance
    spending_amount = min(amount_eur, available_balance)

    # Fetch all open CEA sell orders sorted by price-time priority (FIFO)
    result = await db.execute(
        select(Order, Seller)
        .join(Seller, Order.seller_id == Seller.id)
        .where(
            and_(
                Order.certificate_type == CertTypeEnum.CEA,
                Order.side == OrderSideEnum.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        .order_by(Order.price.asc(), Order.created_at.asc())
    )
    sell_orders = result.all()

    if not sell_orders:
        raise HTTPException(status_code=400, detail="No CEA sellers available")

    # Execute FIFO matching
    remaining_eur = spending_amount
    trades_executed = []
    total_cea_bought = 0

    for order, seller in sell_orders:
        if remaining_eur <= 0:
            break

        order_price_cny = float(order.price)
        order_price_eur = order_price_cny * CNY_TO_EUR
        remaining_qty = float(order.quantity) - float(order.filled_quantity)

        if remaining_qty <= 0:
            continue

        # Calculate how much we can buy from this order
        max_qty_by_funds = remaining_eur / order_price_eur
        qty_to_buy = min(max_qty_by_funds, remaining_qty)
        cost_eur = qty_to_buy * order_price_eur

        # Create the trade record
        trade = CashMarketTrade(
            buy_order_id=None,  # Will be set if we create a buy order record
            sell_order_id=order.id,
            certificate_type=CertTypeEnum.CEA,
            price=Decimal(str(order_price_cny)),
            quantity=Decimal(str(qty_to_buy)),
            # Use naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(trade)

        # Persist trade price in price_history for chart data
        db.add(PriceHistory(
            certificate_type=CertTypeEnum.CEA,
            price=Decimal(str(order_price_cny)),
            currency="EUR",
            source="trade_execution",
            recorded_at=trade.executed_at,
        ))

        # Update the sell order
        order.filled_quantity = Decimal(str(float(order.filled_quantity) + qty_to_buy))
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        # Update seller statistics
        seller.cea_sold = Decimal(str(float(seller.cea_sold or 0) + qty_to_buy))
        seller.total_transactions = (seller.total_transactions or 0) + 1

        # Track the trade
        trades_executed.append(
            {
                "seller_code": seller.client_code,
                "seller_name": seller.name,
                "quantity": round(qty_to_buy, 2),
                "price_cny": round(order_price_cny, 4),
                "price_eur": round(order_price_eur, 4),
                "cost_eur": round(cost_eur, 2),
            }
        )

        remaining_eur -= cost_eur
        total_cea_bought += qty_to_buy

    # Update entity balance
    spent_amount = spending_amount - remaining_eur
    entity.balance_amount = Decimal(str(available_balance - spent_amount))

    await db.commit()

    return {
        "success": True,
        "message": (
            f"Purchased {round(total_cea_bought, 2)} CEA "
            f"from {len(trades_executed)} sellers"
        ),
        "total_cea_bought": round(total_cea_bought, 2),
        "total_spent_eur": round(spent_amount, 2),
        "remaining_balance_eur": round(available_balance - spent_amount, 2),
        "transactions": trades_executed,
    }


# ====================
# NEW REAL TRADING ENDPOINTS
# ====================


@router.get("/real/orderbook/{certificate_type}", response_model=OrderBookResponse)
async def get_real_orderbook_endpoint(
    certificate_type: CertificateType, db=Depends(get_db)  # noqa: B008
):
    """
    Get the real order book from database.
    Returns both bids (buy orders) and asks (sell orders).
    """
    orderbook = await get_real_orderbook(db, certificate_type.value)

    return OrderBookResponse(
        certificate_type=orderbook["certificate_type"],
        bids=[OrderBookLevel(**b) for b in orderbook["bids"]],
        asks=[OrderBookLevel(**a) for a in orderbook["asks"]],
        spread=orderbook["spread"],
        best_bid=orderbook["best_bid"],
        best_ask=orderbook["best_ask"],
        last_price=orderbook["last_price"],
        volume_24h=orderbook["volume_24h"],
        change_24h=orderbook["change_24h"],
        high_24h=orderbook.get("high_24h"),
        low_24h=orderbook.get("low_24h"),
    )


@router.get("/user/balances")
async def get_user_balances(
    current_user: User = Depends(get_funded_user), db=Depends(get_db)  # noqa: B008
):
    """
    Get the current user's asset balances (EUR, CEA, EUA). FUNDED or ADMIN only.

    EUR uses get_entity_eur_balance (EntityHolding + Entity.balance_amount fallback)
    so the value matches Backoffice and Dashboard. CEA/EUA from EntityHolding only.
    """
    if not current_user.entity_id:
        return {
            "entity_id": None,
            "eur_balance": 0,
            "cea_balance": 0,
            "eua_balance": 0,
        }

    eur_balance = await get_entity_eur_balance(db, current_user.entity_id)
    cea_balance = await get_entity_balance(db, current_user.entity_id, AssetType.CEA)
    eua_balance = await get_entity_balance(db, current_user.entity_id, AssetType.EUA)

    return {
        "entity_id": str(current_user.entity_id),
        "eur_balance": float(eur_balance),
        "cea_balance": int(float(cea_balance)),
        "eua_balance": int(float(eua_balance)),
    }


@router.post("/order/preview", response_model=OrderPreviewResponse)
async def preview_order(
    request: OrderPreviewRequest,
    current_user: User = Depends(get_funded_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Preview an order before execution. FUNDED or ADMIN only.

    Shows the expected fills, fees, and final cost without placing the order.
    Useful for showing the user what they'll get before they commit.
    """
    if not current_user.entity_id:
        raise HTTPException(status_code=400, detail="User must have an entity to trade")

    # Get available balance
    available_eur = await get_entity_eur_balance(db, current_user.entity_id)

    # Only support BUY for now (CEA market)
    if request.side != OrderSide.BUY:
        raise HTTPException(
            status_code=400, detail="Only BUY orders are currently supported"
        )

    if request.certificate_type != CertificateType.CEA:
        raise HTTPException(
            status_code=400, detail="Only CEA trading is currently supported"
        )

    # Convert to Decimal
    amount_eur = Decimal(str(request.amount_eur)) if request.amount_eur else None
    quantity = Decimal(str(request.quantity)) if request.quantity else None
    limit_price = Decimal(str(request.limit_price)) if request.limit_price else None

    # Get effective fee rate for this entity
    fee_rate = await get_effective_fee_rate(
        db, MarketType.CEA_CASH, "BID", current_user.entity_id
    )

    # Get preview
    preview = await preview_buy_order(
        db=db,
        entity_id=current_user.entity_id,
        amount_eur=amount_eur,
        quantity=quantity,
        limit_price=limit_price,
        order_type=request.order_type.value,
        all_or_none=request.all_or_none,
    )

    return OrderPreviewResponse(
        certificate_type=request.certificate_type.value,
        side=request.side.value,
        order_type=request.order_type.value,
        amount_eur=float(amount_eur) if amount_eur else None,
        quantity_requested=int(round(float(quantity))) if quantity else None,
        limit_price=float(limit_price) if limit_price else None,
        all_or_none=request.all_or_none,
        fills=[
            OrderFill(
                seller_code=f.seller_code,
                price=float(f.price_eur),
                quantity=int(round(float(f.quantity))),
                cost=float(f.cost_eur),
            )
            for f in preview.fills
        ],
        total_quantity=int(round(float(preview.total_quantity))),
        total_cost_gross=float(preview.total_cost_gross),
        weighted_avg_price=float(preview.weighted_avg_price),
        best_price=float(preview.best_price) if preview.best_price else None,
        worst_price=float(preview.worst_price) if preview.worst_price else None,
        platform_fee_rate=float(fee_rate),
        platform_fee_amount=float(preview.platform_fee_amount),
        total_cost_net=float(preview.total_cost_net),
        net_price_per_unit=float(preview.net_price_per_unit),
        available_balance=float(available_eur),
        remaining_balance=float(available_eur - preview.total_cost_net),
        can_execute=preview.can_execute,
        execution_message=preview.execution_message,
        partial_fill=preview.partial_fill,
        will_be_placed_in_book=preview.will_be_placed_in_book,
    )


@router.post("/order/market", response_model=OrderExecutionResponse)
async def execute_market_order(
    request: MarketOrderRequest,
    current_user: User = Depends(get_funded_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Execute a market order immediately at best available prices. FUNDED or ADMIN only.

    Market orders are filled immediately using FIFO price-time priority.
    A 0.5% platform fee is charged on the transaction value.
    """
    logger.info(
        f"Market order request: user={current_user.email}, side={request.side.value}, "
        f"cert={request.certificate_type.value}, amount_eur={request.amount_eur}, qty={request.quantity}"
    )

    if not current_user.entity_id:
        raise HTTPException(status_code=400, detail="User must have an entity to trade")

    # Only support BUY for now
    if request.side != OrderSide.BUY:
        raise HTTPException(
            status_code=400, detail="Only BUY orders are currently supported"
        )

    if request.certificate_type != CertificateType.CEA:
        raise HTTPException(
            status_code=400, detail="Only CEA trading is currently supported"
        )

    # Convert to Decimal
    amount_eur = Decimal(str(request.amount_eur)) if request.amount_eur else None
    quantity = Decimal(str(request.quantity)) if request.quantity else None

    # Execute the order
    result = await execute_market_buy_order(
        db=db,
        entity_id=current_user.entity_id,
        user_id=current_user.id,
        amount_eur=amount_eur,
        quantity=quantity,
        all_or_none=request.all_or_none,
    )

    logger.info(
        f"Market order executed: user={current_user.email}, success={result.success}, "
        f"qty={result.total_quantity}, cost={result.total_cost_net}, trades={len(result.fills)}"
    )

    # Notify user via WebSocket so all pages refresh balances in real-time
    if result.success:
        async def _send_balance_update():
            await asyncio.sleep(0.15)  # small delay for DB commit visibility
            await client_ws_manager.broadcast_to_users(
                [current_user.id],
                {
                    "type": "balance_updated",
                    "data": {
                        "eur_balance": float(result.eur_balance),
                        "cea_balance": int(float(result.certificate_balance)),
                        "source": "trade_executed",
                    },
                },
            )
        asyncio.create_task(_send_balance_update())

    # Broadcast each trade so chart and activity feed update instantly
    if result.success:
        for fill in result.fills:
            asyncio.create_task(client_ws_manager.broadcast_to_all({
                "type": "trade_executed",
                "data": {
                    "id": "",
                    "certificate_type": request.certificate_type.value,
                    "price": float(fill.price),
                    "quantity": int(round(float(fill.quantity))),
                    "side": "BUY",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                },
            }))

    # Notify all connected clients that the order book changed (after any trade execution)
    asyncio.create_task(client_ws_manager.broadcast_to_all(
        {"type": "orderbook_updated", "data": {"certificate_type": request.certificate_type.value}},
    ))

    # Trade confirmation email to buyer (fire-and-forget)
    if result.success:
        try:
            from ...services.email_service import email_service as _email_svc
            await _email_svc.send_trade_confirmation(
                to_email=current_user.email,
                trade_type="BUY",
                certificate_type=request.certificate_type.value,
                quantity=float(result.total_quantity),
                price=float(result.weighted_avg_price),
                total=float(result.total_cost_net),
            )
        except Exception:
            logger.debug("Trade confirmation email failed for user %s", current_user.id)

    return OrderExecutionResponse(
        success=result.success,
        order_id=result.order_id,
        message=result.message,
        certificate_type=request.certificate_type.value,
        side=request.side.value,
        order_type="MARKET",
        total_quantity=int(round(float(result.total_quantity))),
        total_cost_gross=float(result.total_cost_gross),
        platform_fee=float(result.platform_fee),
        total_cost_net=float(result.total_cost_net),
        weighted_avg_price=float(result.weighted_avg_price),
        trades=[
            OrderFill(
                seller_code=f.seller_code,
                price=float(f.price_eur),
                quantity=int(round(float(f.quantity))),
                cost=float(f.cost_eur),
            )
            for f in result.fills
        ],
        eur_balance=float(result.eur_balance),
        certificate_balance=int(float(result.certificate_balance)),
    )
