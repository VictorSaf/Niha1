"""
Order Matching Service

FIFO price-time priority matching engine for the CEA Cash market.
Handles order preview, market orders, and limit orders with proper fee calculations.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.models import (
    AssetTransaction,
    AssetType,
    CashMarketTrade,
    CertificateType,
    Entity,
    EntityFeeOverride,
    EntityHolding,
    MarketType,
    Order,
    OrderSide,
    OrderStatus,
    PriceHistory,
    Seller,
    TradingFeeConfig,
    TransactionType,
)
from ..services.currency_service import currency_service
from ..services.balance_utils import get_entity_eur_balance
from ..services.settlement_service import SettlementService

logger = logging.getLogger(__name__)

# Default platform fee rate: 0.5% (fallback if no config exists)
DEFAULT_FEE_RATE = Decimal("0.005")


async def get_effective_fee_rate(
    db: AsyncSession,
    market: MarketType,
    side: str,
    entity_id: Optional[UUID] = None,
) -> Decimal:
    """
    Get the effective fee rate for a transaction.

    Priority:
    1. Entity override (if exists and has value for this side)
    2. Market default from trading_fee_configs
    3. Hardcoded fallback (0.5%)

    Args:
        db: Database session
        market: Market type (CEA_CASH or SWAP)
        side: "BID" or "ASK"
        entity_id: Optional entity ID to check for overrides

    Returns:
        Decimal: Fee rate (e.g., 0.005 for 0.5%)
    """
    side_upper = side.upper()

    # 1. Check for entity override
    if entity_id:
        result = await db.execute(
            select(EntityFeeOverride).where(
                and_(
                    EntityFeeOverride.entity_id == entity_id,
                    EntityFeeOverride.market == market,
                    EntityFeeOverride.is_active.is_(True),
                )
            )
        )
        override = result.scalar_one_or_none()

        if override:
            override_rate = (
                override.bid_fee_rate if side_upper == "BID" else override.ask_fee_rate
            )
            if override_rate is not None:
                return Decimal(str(override_rate))

    # 2. Get market default
    result = await db.execute(
        select(TradingFeeConfig).where(TradingFeeConfig.market == market)
    )
    config = result.scalar_one_or_none()

    if config:
        return (
            Decimal(str(config.bid_fee_rate))
            if side_upper == "BID"
            else Decimal(str(config.ask_fee_rate))
        )

    # 3. Fallback to default
    return DEFAULT_FEE_RATE

# EUR migration date - orders created before this are in CNY, after are in EUR
# Set to deployment date of this feature
EUR_MIGRATION_DATE = datetime(2026, 1, 21)


@dataclass
class OrderFillResult:
    """Result of a single fill from the order book"""

    order_id: UUID
    seller_code: str
    price: Decimal  # Price in CNY
    price_eur: Decimal  # Price in EUR
    quantity: Decimal
    cost_eur: Decimal


@dataclass
class OrderPreviewResult:
    """Result of order preview calculation"""

    fills: List[OrderFillResult]
    total_quantity: Decimal
    total_cost_gross: Decimal
    weighted_avg_price: Decimal
    best_price: Optional[Decimal]
    worst_price: Optional[Decimal]
    platform_fee_amount: Decimal
    total_cost_net: Decimal
    net_price_per_unit: Decimal
    can_execute: bool
    execution_message: str
    partial_fill: bool
    will_be_placed_in_book: bool = False  # True for LIMIT orders waiting in book


async def normalize_order_price_to_eur(order: Order) -> Decimal:
    """
    Convert order price to EUR regardless of storage format.

    Strategy:
    - Orders created after EUR_MIGRATION_DATE: Already in EUR
    - Legacy orders (before migration): Stored in CNY, convert to EUR

    Args:
        order: Order object

    Returns:
        Decimal: Price in EUR
    """
    order_price = Decimal(str(order.price))

    # Check if this is a legacy order (before EUR migration)
    if order.created_at < EUR_MIGRATION_DATE:
        # Legacy order - stored in CNY, convert to EUR
        rate = await currency_service.get_rate("CNY", "EUR")
        return order_price * rate

    # New order - already in EUR
    return order_price


async def get_entity_balance(
    db: AsyncSession, entity_id: UUID, asset_type: AssetType
) -> Decimal:
    """Get entity's balance for a specific asset type"""
    result = await db.execute(
        select(EntityHolding).where(
            and_(
                EntityHolding.entity_id == entity_id,
                EntityHolding.asset_type == asset_type,
            )
        )
    )
    holding = result.scalar_one_or_none()
    return Decimal(str(holding.quantity)) if holding else Decimal("0")


async def update_entity_balance(
    db: AsyncSession,
    entity_id: UUID,
    asset_type: AssetType,
    amount: Decimal,
    transaction_type: TransactionType,
    created_by: UUID,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> Decimal:
    """
    Update entity balance and create audit trail.
    Returns the new balance.
    """
    # Get or create holding record
    result = await db.execute(
        select(EntityHolding).where(
            and_(
                EntityHolding.entity_id == entity_id,
                EntityHolding.asset_type == asset_type,
            )
        )
    )
    holding = result.scalar_one_or_none()

    balance_before = Decimal(str(holding.quantity)) if holding else Decimal("0")
    balance_after = balance_before + amount

    if holding:
        holding.quantity = balance_after
        holding.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        # Create new holding
        holding = EntityHolding(
            entity_id=entity_id, asset_type=asset_type, quantity=balance_after
        )
        db.add(holding)

    # Create audit trail
    transaction = AssetTransaction(
        entity_id=entity_id,
        asset_type=asset_type,
        transaction_type=transaction_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        reference=reference,
        notes=notes,
        created_by=created_by,
    )
    db.add(transaction)

    return balance_after


async def get_cea_sell_orders(
    db: AsyncSession, limit_price: Optional[Decimal] = None
) -> List[Order]:
    """
    Get available CEA sell orders sorted by price-time priority (FIFO).

    Includes orders from both legacy Sellers and Market Makers.

    Args:
        db: Database session
        limit_price: Optional maximum price (in CNY) to include

    Returns:
        List of Order objects sorted by price ASC, then created_at ASC
    """
    query = select(Order).where(
        and_(
            Order.certificate_type == CertificateType.CEA,
            Order.side == OrderSide.SELL,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            # Include orders from Sellers OR Market Makers
            or_(Order.seller_id.isnot(None), Order.market_maker_id.isnot(None)),
        )
    )

    if limit_price is not None:
        query = query.where(Order.price <= limit_price)

    query = query.order_by(Order.price.asc(), Order.created_at.asc())

    result = await db.execute(query)
    return result.scalars().all()


async def preview_buy_order(
    db: AsyncSession,
    entity_id: UUID,
    amount_eur: Optional[Decimal] = None,
    quantity: Optional[Decimal] = None,
    limit_price: Optional[Decimal] = None,
    order_type: str = "MARKET",
    all_or_none: bool = False,
) -> OrderPreviewResult:
    """
    Preview a buy order without executing it.

    Shows how much CEA can be bought with the given EUR amount,
    including fee calculations and price breakdown.

    Args:
        db: Database session
        entity_id: Buyer's entity ID
        amount_eur: EUR amount to spend (mutually exclusive with quantity)
        quantity: CEA quantity to buy (mutually exclusive with amount_eur)
        limit_price: Maximum price in EUR (for limit orders)
        order_type: "MARKET" or "LIMIT" - affects behavior when no liquidity
        all_or_none: If True, only return fills if entire order can be matched

    Returns:
        OrderPreviewResult with all fill and fee details
    """
    # Get dynamic fee rate for buyer (BID side)
    fee_rate = await get_effective_fee_rate(
        db, MarketType.CEA_CASH, "BID", entity_id
    )

    # Get available balance
    available_eur = await get_entity_eur_balance(db, entity_id)

    # Validate inputs
    if amount_eur is None and quantity is None:
        return OrderPreviewResult(
            fills=[],
            total_quantity=Decimal("0"),
            total_cost_gross=Decimal("0"),
            weighted_avg_price=Decimal("0"),
            best_price=None,
            worst_price=None,
            platform_fee_amount=Decimal("0"),
            total_cost_net=Decimal("0"),
            net_price_per_unit=Decimal("0"),
            can_execute=False,
            execution_message="Must specify either amount_eur or quantity",
            partial_fill=False,
        )

    # Get sell orders
    sell_orders = await get_cea_sell_orders(db, limit_price)

    if not sell_orders:
        # For LIMIT orders without immediate liquidity, allow placement in order book
        if order_type == "LIMIT" and limit_price is not None:
            # Calculate estimated quantity based on limit price and amount
            estimated_quantity = Decimal("0")
            if amount_eur is not None:
                # Estimate: quantity = amount / (price * (1 + fee))
                estimated_quantity = amount_eur / (limit_price * (Decimal("1") + fee_rate))

            return OrderPreviewResult(
                fills=[],
                total_quantity=estimated_quantity,
                total_cost_gross=amount_eur if amount_eur else Decimal("0"),
                weighted_avg_price=limit_price,
                best_price=None,
                worst_price=None,
                platform_fee_amount=(amount_eur * fee_rate) if amount_eur else Decimal("0"),
                total_cost_net=amount_eur * (Decimal("1") + fee_rate) if amount_eur else Decimal("0"),
                net_price_per_unit=limit_price * (Decimal("1") + fee_rate),
                can_execute=True,  # Can place in book
                execution_message=f"Order will be placed in order book at €{limit_price:.2f}",
                partial_fill=False,
                will_be_placed_in_book=True,
            )

        # MARKET orders without liquidity cannot execute
        return OrderPreviewResult(
            fills=[],
            total_quantity=Decimal("0"),
            total_cost_gross=Decimal("0"),
            weighted_avg_price=Decimal("0"),
            best_price=None,
            worst_price=None,
            platform_fee_amount=Decimal("0"),
            total_cost_net=Decimal("0"),
            net_price_per_unit=Decimal("0"),
            can_execute=False,
            execution_message="No CEA sellers available",
            partial_fill=False,
        )

    # Calculate max gross we can spend (accounting for fees)
    # total_net = total_gross + fee = total_gross * (1 + fee_rate)
    # So: max_gross = available_eur / (1 + fee_rate)
    if amount_eur is not None:
        # Use minimum of requested amount and available balance
        spending_limit_net = min(amount_eur, available_eur)
        max_gross = spending_limit_net / (Decimal("1") + fee_rate)
    else:
        # For quantity-based, we'll calculate as we go
        max_gross = available_eur / (Decimal("1") + fee_rate)

    # Simulate FIFO matching
    fills: List[OrderFillResult] = []
    remaining_budget = max_gross if amount_eur is not None else None
    remaining_qty = quantity
    total_cost_gross = Decimal("0")
    total_quantity = Decimal("0")

    for order in sell_orders:
        if amount_eur is not None and remaining_budget <= Decimal("0"):
            break
        if quantity is not None and remaining_qty <= Decimal("0"):
            break

        # Normalize order price to EUR (handles both legacy CNY and new EUR orders)
        order_price_eur = await normalize_order_price_to_eur(order)
        order_price_cny = Decimal(str(order.price))  # Keep for display/audit
        remaining_order_qty = Decimal(str(order.quantity)) - Decimal(
            str(order.filled_quantity)
        )

        if remaining_order_qty <= Decimal("0"):
            continue

        # Calculate how much we can buy from this order
        if amount_eur is not None:
            # Budget-based: calculate max quantity we can afford
            max_qty_by_funds = remaining_budget / order_price_eur
            qty_to_buy = min(max_qty_by_funds, remaining_order_qty)
        else:
            # Quantity-based: buy up to the requested quantity
            qty_to_buy = min(remaining_qty, remaining_order_qty)
            # But also check if we have enough funds
            cost_for_qty = qty_to_buy * order_price_eur
            fee_for_cost = cost_for_qty * fee_rate
            total_needed = cost_for_qty + fee_for_cost
            if total_needed > available_eur - total_cost_gross - (
                total_cost_gross * fee_rate
            ):
                # Adjust quantity to what we can afford
                max_gross_remaining = (
                    available_eur
                    - total_cost_gross * (Decimal("1") + fee_rate)
                ) / (Decimal("1") + fee_rate)
                qty_to_buy = min(qty_to_buy, max_gross_remaining / order_price_eur)

        if qty_to_buy <= Decimal("0"):
            continue

        cost_eur = qty_to_buy * order_price_eur

        # Get seller/MM code for display (fetch lazily only when needed)
        # For now, use order ID - callers can fetch seller/MM info separately
        seller_code = (
            str(order.seller_id) if order.seller_id else str(order.market_maker_id)
        )

        fills.append(
            OrderFillResult(
                order_id=order.id,
                seller_code=seller_code,
                price=order_price_cny,
                price_eur=order_price_eur,
                quantity=qty_to_buy,
                cost_eur=cost_eur,
            )
        )

        total_cost_gross += cost_eur
        total_quantity += qty_to_buy

        if amount_eur is not None:
            remaining_budget -= cost_eur
        if quantity is not None:
            remaining_qty -= qty_to_buy

    # Calculate summary
    platform_fee_amount = total_cost_gross * fee_rate
    total_cost_net = total_cost_gross + platform_fee_amount
    weighted_avg_price = (
        (total_cost_gross / total_quantity)
        if total_quantity > Decimal("0")
        else Decimal("0")
    )
    net_price_per_unit = (
        (total_cost_net / total_quantity)
        if total_quantity > Decimal("0")
        else Decimal("0")
    )

    # Best and worst prices
    best_price = fills[0].price_eur if fills else None
    worst_price = fills[-1].price_eur if fills else None

    # Check all-or-none condition
    partial_fill = False
    if quantity is not None and total_quantity < quantity:
        partial_fill = True
        if all_or_none:
            return OrderPreviewResult(
                fills=fills,
                total_quantity=total_quantity,
                total_cost_gross=total_cost_gross,
                weighted_avg_price=weighted_avg_price,
                best_price=best_price,
                worst_price=worst_price,
                platform_fee_amount=platform_fee_amount,
                total_cost_net=total_cost_net,
                net_price_per_unit=net_price_per_unit,
                can_execute=False,
                execution_message=(
                    f"All-or-none: Only {total_quantity:.2f} of "
                    f"{quantity:.2f} CEA available"
                ),
                partial_fill=True,
            )

    # Check if we can actually execute
    can_execute = total_quantity > Decimal("0") and total_cost_net <= available_eur
    execution_message = (
        "Ready to execute"
        if can_execute
        else "Insufficient balance or no matching orders"
    )

    if total_cost_net > available_eur:
        execution_message = (
            f"Insufficient balance: need {total_cost_net:.2f} EUR, "
            f"have {available_eur:.2f} EUR"
        )
        can_execute = False

    return OrderPreviewResult(
        fills=fills,
        total_quantity=total_quantity,
        total_cost_gross=total_cost_gross,
        weighted_avg_price=weighted_avg_price,
        best_price=best_price,
        worst_price=worst_price,
        platform_fee_amount=platform_fee_amount,
        total_cost_net=total_cost_net,
        net_price_per_unit=net_price_per_unit,
        can_execute=can_execute,
        execution_message=execution_message,
        partial_fill=partial_fill,
    )


@dataclass
class OrderExecutionResult:
    """Result of order execution"""

    success: bool
    order_id: Optional[UUID]
    message: str
    fills: List[OrderFillResult]
    total_quantity: Decimal
    total_cost_gross: Decimal
    platform_fee: Decimal
    total_cost_net: Decimal
    weighted_avg_price: Decimal
    eur_balance: Decimal
    certificate_balance: Decimal


async def execute_market_buy_order(
    db: AsyncSession,
    entity_id: UUID,
    user_id: UUID,
    amount_eur: Optional[Decimal] = None,
    quantity: Optional[Decimal] = None,
    all_or_none: bool = False,
) -> OrderExecutionResult:
    """
    Execute a market buy order for CEA.

    This is an atomic operation that:
    1. Finds matching sell orders using FIFO
    2. Creates trade records
    3. Updates seller statistics
    4. Updates buyer's balance

    Args:
        db: Database session
        entity_id: Buyer's entity ID
        user_id: User making the trade (for audit)
        amount_eur: EUR amount to spend
        quantity: CEA quantity to buy
        all_or_none: Reject partial fills

    Returns:
        OrderExecutionResult with trade details
    """
    # First preview the order
    preview = await preview_buy_order(
        db=db,
        entity_id=entity_id,
        amount_eur=amount_eur,
        quantity=quantity,
        limit_price=None,  # Market order - no limit
        all_or_none=all_or_none,
    )

    if not preview.can_execute:
        return OrderExecutionResult(
            success=False,
            order_id=None,
            message=preview.execution_message,
            fills=[],
            total_quantity=Decimal("0"),
            total_cost_gross=Decimal("0"),
            platform_fee=Decimal("0"),
            total_cost_net=Decimal("0"),
            weighted_avg_price=Decimal("0"),
            eur_balance=await get_entity_eur_balance(db, entity_id),
            certificate_balance=await get_entity_balance(db, entity_id, AssetType.CEA),
        )

    # Create buy order record (NEW ORDERS STORED IN EUR)
    buy_order = Order(
        market=MarketType.CEA_CASH,
        entity_id=entity_id,
        certificate_type=CertificateType.CEA,
        side=OrderSide.BUY,
        price=Decimal(str(preview.weighted_avg_price)),  # Store in EUR
        quantity=preview.total_quantity,
        filled_quantity=preview.total_quantity,
        status=OrderStatus.FILLED,
    )
    db.add(buy_order)
    await db.flush()  # Get the order ID

    # Execute trades
    for fill in preview.fills:
        # Get the sell order
        result = await db.execute(select(Order).where(Order.id == fill.order_id))
        sell_order = result.scalar_one()

        # Create trade record
        trade = CashMarketTrade(
            buy_order_id=buy_order.id,
            sell_order_id=sell_order.id,
            certificate_type=CertificateType.CEA,
            price=fill.price,
            quantity=fill.quantity,
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(trade)
        await db.flush()  # Populate trade.id before commission tracking

        # Persist trade price in price_history for chart data
        db.add(PriceHistory(
            certificate_type=CertificateType.CEA,
            price=fill.price,
            currency="EUR",
            source="trade_execution",
            recorded_at=trade.executed_at,
        ))

        # Commission tracking — lazy import to avoid circular deps
        from .commission_service import maybe_create_commission
        await maybe_create_commission(db, trade, entity_id)

        logger.info(
            f"Trade executed: buyer_order={buy_order.id}, seller_order={sell_order.id}, "
            f"qty={fill.quantity}, price={fill.price} EUR, cost={fill.cost_eur} EUR"
        )

        # Update sell order
        sell_order.filled_quantity = (
            Decimal(str(sell_order.filled_quantity)) + fill.quantity
        )
        if sell_order.filled_quantity >= sell_order.quantity:
            sell_order.status = OrderStatus.FILLED
        else:
            sell_order.status = OrderStatus.PARTIALLY_FILLED
        sell_order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # Update seller stats (only for legacy sellers, not Market Makers)
        if sell_order.seller_id:
            seller_result = await db.execute(
                select(Seller).where(Seller.id == sell_order.seller_id)
            )
            seller = seller_result.scalar_one_or_none()
            if seller:
                seller.cea_sold = Decimal(str(seller.cea_sold or 0)) + fill.quantity
                seller.total_transactions = (seller.total_transactions or 0) + 1

    # Update buyer balances
    # Deduct EUR (total cost + fees)
    new_eur_balance = await update_entity_balance(
        db=db,
        entity_id=entity_id,
        asset_type=AssetType.EUR,
        amount=-preview.total_cost_net,
        transaction_type=TransactionType.TRADE_BUY,
        created_by=user_id,
        reference=str(buy_order.id),
        notes=(
            f"Market buy {preview.total_quantity:.2f} CEA @ avg "
            f"{preview.weighted_avg_price:.4f} EUR/CEA"
        ),
    )

    # Role transition: CEA → CEA_SETTLE when entity EUR balance reaches 0
    from .role_transitions import transition_cea_to_cea_settle_if_eur_zero
    await transition_cea_to_cea_settle_if_eur_zero(db, entity_id, new_eur_balance)

    # Create settlement batch for CEA delivery (T+3)
    # CEA will be credited when settlement is finalized, not immediately
    settlement = await SettlementService.create_cea_purchase_settlement(
        db=db,
        entity_id=entity_id,
        order_id=buy_order.id,
        trade_id=None,  # Multiple trades in this order
        quantity=int(preview.total_quantity),  # Floor to integer — fractional CEA stays with NIHA
        price=preview.weighted_avg_price,
        seller_id=None,  # Multiple sellers possible
        created_by=user_id,
    )

    # Get current CEA balance (won't change until settlement completes)
    new_cea_balance = await get_entity_balance(db, entity_id, AssetType.CEA)

    await db.commit()

    return OrderExecutionResult(
        success=True,
        order_id=buy_order.id,
        message=(
            f"Successfully purchased {preview.total_quantity:.2f} CEA from "
            f"{len(preview.fills)} sellers. Settlement "
            f"{settlement.batch_reference} created - CEA will be delivered "
            f"on {settlement.expected_settlement_date.strftime('%Y-%m-%d')} "
            f"(T+3)"
        ),
        fills=preview.fills,
        total_quantity=preview.total_quantity,
        total_cost_gross=preview.total_cost_gross,
        platform_fee=preview.platform_fee_amount,
        total_cost_net=preview.total_cost_net,
        weighted_avg_price=preview.weighted_avg_price,
        eur_balance=new_eur_balance,
        certificate_balance=new_cea_balance,
    )


async def get_real_orderbook(db: AsyncSession, certificate_type: str) -> dict:
    """
    Get the real order book for a certificate type from the database.

    Returns both bids (buy orders from entities) and asks (sell orders from sellers).
    """
    cert_enum = (
        CertificateType.CEA if certificate_type == "CEA" else CertificateType.EUA
    )

    # Get sell orders (asks) - from Sellers
    sell_result = await db.execute(
        select(Order, Seller)
        .join(Seller, Order.seller_id == Seller.id, isouter=True)
        .where(
            and_(
                Order.certificate_type == cert_enum,
                Order.side == OrderSide.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        .order_by(Order.price.asc(), Order.created_at.asc())
    )
    sell_orders = sell_result.all()

    # Get buy orders (bids) - from Entities
    buy_result = await db.execute(
        select(Order, Entity)
        .join(Entity, Order.entity_id == Entity.id, isouter=True)
        .where(
            and_(
                Order.certificate_type == cert_enum,
                Order.side == OrderSide.BUY,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        .order_by(Order.price.desc(), Order.created_at.asc())  # Best bid first
    )
    buy_orders = buy_result.all()

    # Aggregate asks by price level
    ask_levels = {}
    for order, _seller in sell_orders:
        remaining = float(order.quantity) - float(order.filled_quantity)
        if remaining <= 0:
            continue
        price_key = float(order.price)
        if price_key not in ask_levels:
            ask_levels[price_key] = {
                "price": price_key,
                "quantity": 0,
                "order_count": 0,
            }
        ask_levels[price_key]["quantity"] += remaining
        ask_levels[price_key]["order_count"] += 1

    # Aggregate bids by price level
    bid_levels = {}
    for order, _entity in buy_orders:
        remaining = float(order.quantity) - float(order.filled_quantity)
        if remaining <= 0:
            continue
        price_key = float(order.price)
        if price_key not in bid_levels:
            bid_levels[price_key] = {
                "price": price_key,
                "quantity": 0,
                "order_count": 0,
            }
        bid_levels[price_key]["quantity"] += remaining
        bid_levels[price_key]["order_count"] += 1

    # Convert to sorted lists
    asks = sorted(ask_levels.values(), key=lambda x: x["price"])
    bids = sorted(bid_levels.values(), key=lambda x: x["price"], reverse=True)

    # Calculate cumulative quantities (CEA/EUA: integers only)
    ask_cumulative = 0
    for ask in asks:
        ask_cumulative += ask["quantity"]
        ask["cumulative_quantity"] = int(round(ask_cumulative))
        ask["quantity"] = int(round(ask["quantity"]))

    bid_cumulative = 0
    for bid in bids:
        bid_cumulative += bid["quantity"]
        bid["cumulative_quantity"] = int(round(bid_cumulative))
        bid["quantity"] = int(round(bid["quantity"]))

    # Market stats
    best_ask = asks[0]["price"] if asks else None
    best_bid = bids[0]["price"] if bids else None
    spread = round(best_ask - best_bid, 4) if best_ask and best_bid else None
    last_price = best_ask or best_bid or (63.0 if certificate_type == "CEA" else 81.0)

    # Get 24h trade stats
    time_24h_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    trades_result = await db.execute(
        select(CashMarketTrade)
        .where(
            and_(
                CashMarketTrade.certificate_type == cert_enum,
                CashMarketTrade.executed_at >= time_24h_ago,
            )
        )
        .order_by(CashMarketTrade.executed_at.desc())
    )
    trades_24h = trades_result.scalars().all()

    # Calculate 24h stats from actual trades
    if trades_24h:
        trade_prices = [float(t.price) for t in trades_24h]
        trade_volumes = [float(t.quantity) for t in trades_24h]
        high_24h = max(trade_prices)
        low_24h = min(trade_prices)
        volume_24h = sum(trade_volumes)
        # Change: compare most recent to oldest in 24h period
        change_24h = round(((trade_prices[0] - trade_prices[-1]) / trade_prices[-1]) * 100, 2) if len(trade_prices) > 1 else 0.0
        # Use most recent trade price as last_price if available
        last_price = trade_prices[0]
    else:
        # No trades in 24h - use current best prices as fallback
        high_24h = last_price
        low_24h = last_price
        volume_24h = 0
        change_24h = 0.0

    volume_24h = int(round(volume_24h)) if trades_24h else 0

    return {
        "certificate_type": certificate_type,
        "bids": bids,
        "asks": asks,
        "spread": spread,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "last_price": last_price,
        "volume_24h": volume_24h,
        "change_24h": change_24h,
        "high_24h": high_24h,
        "low_24h": low_24h,
    }
