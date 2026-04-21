"""Integration tests for OrderService.place_order — uses live DB."""
import pytest
import uuid
from decimal import Decimal

from sqlalchemy import func, select, desc

from app.core.database import AsyncSessionLocal
from app.models.models import (
    CashMarketTrade,
    CertificateType,
    MarketMakerClient,
    MarketMakerType,
    MarketType,
    Order,
    OrderSide,
    OrderStatus,
    User,
    UserRole,
)


async def _get_admin_user_id(db):
    """Get admin user ID from DB."""
    result = await db.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    user = result.scalars().first()
    if not user:
        pytest.skip("No admin user in DB")
    return user.id


async def _get_mm_ids(db):
    """Return (buyer_mm_id, seller_mm_id) or skip if not found."""
    result = await db.execute(select(MarketMakerClient))
    mms = list(result.scalars().all())
    buyer = next((m for m in mms if m.mm_type == MarketMakerType.CEA_BUYER), None)
    seller = next((m for m in mms if m.mm_type == MarketMakerType.CEA_SELLER), None)
    if not buyer or not seller:
        pytest.skip("CEA_BUYER or CEA_SELLER market maker not found")
    return buyer.id, seller.id


@pytest.mark.asyncio
async def test_place_order_creates_open_order():
    """place_order() creates an Order with OPEN (or FILLED) status."""
    from app.services.order_service import place_order

    async with AsyncSessionLocal() as db:
        admin_id = await _get_admin_user_id(db)
        buyer_id, _ = await _get_mm_ids(db)

        order = await place_order(
            db=db,
            market_maker_id=buyer_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.BUY,
            price=Decimal("1.00"),  # very low — won't cross anything
            quantity=Decimal("100"),
            rule=None,
            admin_user_id=admin_id,
        )
        assert order is not None
        assert order.status in (OrderStatus.OPEN, OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED)

        # Teardown
        if order.status == OrderStatus.OPEN:
            order.status = OrderStatus.CANCELLED
            await db.commit()


@pytest.mark.asyncio
async def test_crossing_orders_produce_trade():
    """A BUY at price > resting SELL price produces a CashMarketTrade."""
    from app.services.order_service import place_order

    async with AsyncSessionLocal() as db:
        admin_id = await _get_admin_user_id(db)
        buyer_id, seller_id = await _get_mm_ids(db)

        # Count trades before
        result_before = await db.execute(
            select(func.count()).select_from(CashMarketTrade).where(
                CashMarketTrade.certificate_type == CertificateType.CEA
            )
        )
        count_before = result_before.scalar()

        # Place SELL first — it rests in book
        sell_order = await place_order(
            db=db,
            market_maker_id=seller_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.SELL,
            price=Decimal("5.00"),   # low price so BUY will cross it
            quantity=Decimal("50"),
            rule=None,
            admin_user_id=admin_id,
        )
        assert sell_order is not None

        # Place BUY that crosses sell (price > 5.00)
        buy_order = await place_order(
            db=db,
            market_maker_id=buyer_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.BUY,
            price=Decimal("5.50"),   # crosses the 5.00 SELL
            quantity=Decimal("50"),
            rule=None,
            admin_user_id=admin_id,
        )
        assert buy_order is not None

        # Verify at least one new trade was created
        result_after = await db.execute(
            select(func.count()).select_from(CashMarketTrade).where(
                CashMarketTrade.certificate_type == CertificateType.CEA
            )
        )
        count_after = result_after.scalar()
        assert count_after > count_before, f"Expected new trade(s). Before: {count_before}, After: {count_after}"

        # Teardown: cancel remaining open orders
        for o in [sell_order, buy_order]:
            if o and o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                await db.refresh(o)
                o.status = OrderStatus.CANCELLED
        await db.commit()


@pytest.mark.asyncio
async def test_place_order_rejects_invalid_price():
    """place_order() returns None for price <= 0."""
    from app.services.order_service import place_order

    async with AsyncSessionLocal() as db:
        admin_id = await _get_admin_user_id(db)
        buyer_id, _ = await _get_mm_ids(db)

        result = await place_order(
            db=db,
            market_maker_id=buyer_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.BUY,
            price=Decimal("0"),
            quantity=Decimal("100"),
            rule=None,
            admin_user_id=admin_id,
        )
        assert result is None


@pytest.mark.asyncio
async def test_place_order_rejects_invalid_quantity():
    """place_order() returns None for quantity < 1."""
    from app.services.order_service import place_order

    async with AsyncSessionLocal() as db:
        admin_id = await _get_admin_user_id(db)
        buyer_id, _ = await _get_mm_ids(db)

        result = await place_order(
            db=db,
            market_maker_id=buyer_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.BUY,
            price=Decimal("10.00"),
            quantity=Decimal("0.5"),
            rule=None,
            admin_user_id=admin_id,
        )
        assert result is None
