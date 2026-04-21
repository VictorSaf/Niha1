"""
Order Service

Validates, persists, and initiates matching for market maker orders.
Wraps LimitOrderMatcher.match_incoming_order() — the single source of
truth for all order matching on this platform.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AutoTradeRule,
    CertificateType,
    MarketType,
    Order,
    OrderSide,
    OrderStatus,
    TicketStatus,
)
from app.services.limit_order_matching import LimitOrderMatcher
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


async def place_order(
    db: AsyncSession,
    market_maker_id: uuid.UUID,
    certificate_type: CertificateType,
    market_type: MarketType,
    side: OrderSide,
    price: Decimal,
    quantity: Decimal,
    rule: Optional[AutoTradeRule],
    admin_user_id: uuid.UUID,
) -> Optional[Order]:
    """
    Validate, persist, and match a market maker order.

    Steps:
    1. Validate inputs (price > 0, quantity >= 1)
    2. Persist Order with OPEN status
    3. Create audit ticket
    4. Update rule execution tracking (if rule provided)
    5. Call LimitOrderMatcher.match_incoming_order() for crossing
    6. Commit
    7. Broadcast orderbook_updated WS event

    Returns the Order on success, None on failure.
    """
    try:
        if price <= Decimal("0"):
            logger.warning(f"[OrderService] Rejected order: price={price} <= 0")
            return None
        if quantity < Decimal("1"):
            logger.warning(f"[OrderService] Rejected order: quantity={quantity} < 1")
            return None

        order = Order(
            market=market_type,
            market_maker_id=market_maker_id,
            certificate_type=certificate_type,
            side=side,
            price=price,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            status=OrderStatus.OPEN,
        )
        db.add(order)
        await db.flush()

        await TicketService.create_ticket(
            db=db,
            action_type="AUTO_TRADE_ORDER_PLACED",
            entity_type="Order",
            entity_id=order.id,
            status=TicketStatus.SUCCESS,
            user_id=admin_user_id,
            market_maker_id=market_maker_id,
            request_payload={
                "rule_id": str(rule.id) if rule else None,
                "rule_name": rule.name if rule else "pressure_model",
                "side": side.value,
                "price": str(price),
                "quantity": str(quantity),
            },
            response_data={
                "order_id": str(order.id),
                "certificate_type": certificate_type.value,
            },
            tags=["auto_trade", "order", side.value.lower()],
        )

        if rule is not None:
            from app.services.auto_trade_executor import AutoTradeExecutor
            rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(rule)
            rule.execution_count = (rule.execution_count or 0) + 1

        # Match against existing orders — this is where trades happen
        await LimitOrderMatcher.match_incoming_order(db, order, user_id=admin_user_id)

        await db.commit()
        await db.refresh(order)

        # Broadcast orderbook update (fire-and-forget)
        try:
            from app.api.v1.client_ws import client_ws_manager
            asyncio.create_task(client_ws_manager.broadcast_to_all({
                "type": "orderbook_updated",
                "data": {"certificate_type": certificate_type.value},
            }))
        except Exception:
            pass

        return order

    except Exception as e:
        logger.exception(f"[OrderService] place_order failed: {e}")
        await db.rollback()
        return None
