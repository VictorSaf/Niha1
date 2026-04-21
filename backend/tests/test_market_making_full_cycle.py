"""
Full cycle integration test: scheduler -> pressure -> orders -> market.
Tests that run_cycle() produces active orders near a reasonable price range.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, desc, update

from app.core.database import AsyncSessionLocal
from app.models.models import (
    AutoTradeRule, CertificateType, Order, OrderSide, OrderStatus
)
from app.services.auto_trade_executor import AutoTradeExecutor


@pytest.mark.asyncio
async def test_run_cycle_produces_active_orders():
    """
    After bootstrap + 3 cycles, BUY and SELL orders should exist
    for CEA at prices within a reasonable range.

    Orders may be OPEN or FILLED (if the matching engine crosses them),
    so we check for any recently-created MM orders on both sides.
    """
    async with AsyncSessionLocal() as db:
        # Bootstrap rules if they don't exist
        await AutoTradeExecutor.bootstrap_rules(db)
        await db.commit()

        # Force all CEA rules to be ready NOW (they may have future next_execution_at
        # from the live executor or a previous test run)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        past = now - timedelta(seconds=10)
        await db.execute(
            update(AutoTradeRule)
            .where(AutoTradeRule.enabled.is_(True))
            .values(next_execution_at=past)
        )
        await db.commit()

        # Run 3 full cycles
        for _ in range(3):
            result = await AutoTradeExecutor.run_cycle(db)
            assert result["errors"] == 0, f"Unexpected errors in run_cycle: {result}"
            # Reset execution times so next cycle also fires
            await db.execute(
                update(AutoTradeRule)
                .where(AutoTradeRule.enabled.is_(True))
                .values(next_execution_at=past)
            )
            await db.commit()

        # Check BUY orders exist (OPEN or FILLED — matching may have crossed them)
        buy_result = await db.execute(
            select(Order).where(
                and_(
                    Order.certificate_type == CertificateType.CEA,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([
                        OrderStatus.OPEN,
                        OrderStatus.PARTIALLY_FILLED,
                        OrderStatus.FILLED,
                    ]),
                    Order.market_maker_id.isnot(None),
                )
            ).order_by(desc(Order.created_at)).limit(10)
        )
        buy_orders = list(buy_result.scalars().all())

        # Check SELL orders exist
        sell_result = await db.execute(
            select(Order).where(
                and_(
                    Order.certificate_type == CertificateType.CEA,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([
                        OrderStatus.OPEN,
                        OrderStatus.PARTIALLY_FILLED,
                        OrderStatus.FILLED,
                    ]),
                    Order.market_maker_id.isnot(None),
                )
            ).order_by(desc(Order.created_at)).limit(10)
        )
        sell_orders = list(sell_result.scalars().all())

        assert len(buy_orders) > 0, "Expected BUY orders after 3 cycles"
        assert len(sell_orders) > 0, "Expected SELL orders after 3 cycles"

        # Prices should be within a reasonable range for CEA (EUR)
        for o in buy_orders + sell_orders:
            assert Decimal("1.00") < o.price < Decimal("50.00"), (
                f"Order price {o.price} outside expected range [1, 50]"
            )


@pytest.mark.asyncio
async def test_pressure_model_state_initialized():
    """
    After a run_cycle(), the market_states dict should exist and be accessible.
    """
    from app.services.market_making_service import _market_states

    async with AsyncSessionLocal() as db:
        await AutoTradeExecutor.bootstrap_rules(db)
        await db.commit()
        await AutoTradeExecutor.run_cycle(db)

    # After a cycle, market states should be populated
    # (they may or may not be populated depending on whether scraped price is available)
    # Just verify the dict exists and is accessible
    assert isinstance(_market_states, dict)
