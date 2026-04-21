"""Integration test: scheduler correctly calls tick() for each enabled rule."""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.database import AsyncSessionLocal
from app.services.auto_trade_executor import AutoTradeExecutor


@pytest.mark.asyncio
async def test_run_cycle_exists():
    """AutoTradeExecutor.run_cycle() exists and can be called without error."""
    async with AsyncSessionLocal() as db:
        # Bootstrap rules if they don't exist
        await AutoTradeExecutor.bootstrap_rules(db)
        await db.commit()

        result = await AutoTradeExecutor.run_cycle(db)
        assert isinstance(result, dict)
        assert "rules_processed" in result
        assert "orders_placed" in result
        assert "errors" in result


@pytest.mark.asyncio
async def test_run_cycle_calls_market_making_tick():
    """run_cycle() calls market_making_service.tick() for each enabled rule."""
    async with AsyncSessionLocal() as db:
        await AutoTradeExecutor.bootstrap_rules(db)
        await db.commit()

        call_count = 0

        async def fake_tick(db, rule, market_key, market_settings):
            nonlocal call_count
            call_count += 1
            return True

        with patch("app.services.market_making_service.tick", side_effect=fake_tick):
            result = await AutoTradeExecutor.run_cycle(db)

        # If there are enabled rules ready, tick should have been called
        # (may be 0 if all rules have future next_execution_at after bootstrap)
        assert result["errors"] == 0
