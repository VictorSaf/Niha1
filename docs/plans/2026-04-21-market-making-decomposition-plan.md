# Market Making Decomposition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the monolithic `auto_trade_executor.py` with focused services where bid/ask volatility around the scraped price emerges naturally from a pressure model.

**Architecture:** `AutoTradeScheduler` (thin cron) → `MarketMakingService` (pressure model, order gen) → `OrderService` (persist + match) → `LimitOrderMatcher` (unchanged) → WS broadcast.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, Python dataclasses.

---

## Context

Read the design doc first: `docs/plans/2026-04-21-market-making-decomposition-design.md`

Key existing files:
- `backend/app/services/auto_trade_executor.py` — monolith we're decomposing (~2000 lines)
- `backend/app/services/limit_order_matching.py` — clean matcher, DO NOT TOUCH
- `backend/app/models/models.py` — SQLAlchemy models, `AutoTradeMarketSettings` at line ~1448
- `backend/alembic/versions/` — migrations, current head: `2026_04_04_autotrade_ssot`

Run commands inside Docker: `docker compose exec backend <cmd>`

---

## Task 1: DB Migration — Pressure Model Columns

**Files:**
- Create: `backend/alembic/versions/2026_04_21_mm_pressure_params.py`
- Modify: `backend/app/models/models.py` (add 4 columns to `AutoTradeMarketSettings`)

### Step 1: Add columns to SQLAlchemy model

In `backend/app/models/models.py`, find `AutoTradeMarketSettings` (around line 1448).
After the `level_rebalance_depth` column (around line 1519), add:

```python
    # Pressure model parameters (bid/ask volatility around scraped price)
    pressure_momentum = Column(Numeric(4, 2), nullable=False, server_default="0.70")
    pressure_sigma = Column(Numeric(4, 2), nullable=False, server_default="0.25")
    reversion_alpha = Column(Numeric(4, 2), nullable=False, server_default="0.20")
    band_amplitude_ticks = Column(Integer, nullable=False, server_default="3")
```

### Step 2: Create the migration file

Create `backend/alembic/versions/2026_04_21_mm_pressure_params.py`:

```python
"""mm_pressure_params — add pressure model columns to auto_trade_market_settings

Revision ID: 2026_04_21_mm_pressure_params
Revises: 2026_04_04_autotrade_ssot
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision: str = "2026_04_21_mm_pressure_params"
down_revision: str = "2026_04_04_autotrade_ssot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("pressure_momentum", sa.Numeric(4, 2), nullable=False, server_default="0.70"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("pressure_sigma", sa.Numeric(4, 2), nullable=False, server_default="0.25"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("reversion_alpha", sa.Numeric(4, 2), nullable=False, server_default="0.20"),
    )
    op.add_column(
        "auto_trade_market_settings",
        sa.Column("band_amplitude_ticks", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("auto_trade_market_settings", "band_amplitude_ticks")
    op.drop_column("auto_trade_market_settings", "reversion_alpha")
    op.drop_column("auto_trade_market_settings", "pressure_sigma")
    op.drop_column("auto_trade_market_settings", "pressure_momentum")
```

### Step 3: Run migration

```bash
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 2026_04_04_autotrade_ssot -> 2026_04_21_mm_pressure_params`

### Step 4: Verify

```bash
docker compose exec db psql -U niha_user -d niha_carbon -c \
  "SELECT market_key, pressure_momentum, pressure_sigma, reversion_alpha, band_amplitude_ticks FROM auto_trade_market_settings;"
```

Expected: 3 rows (CEA_BID, CEA_ASK, EUA_SWAP) with default values 0.70 / 0.25 / 0.20 / 3.

### Step 5: Commit

```bash
git add backend/alembic/versions/2026_04_21_mm_pressure_params.py backend/app/models/models.py
git commit -m "feat(autotrade): add pressure model columns to auto_trade_market_settings"
```

---

## Task 2: MarketState + Pressure Model (Pure Functions, TDD)

**Files:**
- Create: `backend/app/services/market_making_service.py`
- Create: `backend/tests/test_market_making_pressure.py`

### Step 1: Write the failing tests

Create `backend/tests/test_market_making_pressure.py`:

```python
"""Unit tests for MarketState pressure model — pure functions, no DB needed."""
import pytest
from decimal import Decimal
from app.services.market_making_service import MarketState, PressureSettings


DEFAULT_SETTINGS = PressureSettings(
    tick_size=Decimal("0.10"),
    avg_spread=Decimal("0.20"),
    pressure_momentum=Decimal("0.70"),
    pressure_sigma=Decimal("0.25"),
    reversion_alpha=Decimal("0.20"),
    band_amplitude_ticks=3,
)
SCRAPED = Decimal("12.09")


def test_pressure_stays_in_band():
    """After 100 ticks, mid_price stays within ±3 ticks of scraped price."""
    state = MarketState(mid_price=SCRAPED, pressure=0.0)
    for _ in range(100):
        state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    band = DEFAULT_SETTINGS.tick_size * DEFAULT_SETTINGS.band_amplitude_ticks
    assert abs(state.mid_price - SCRAPED) <= band


def test_pressure_mean_reverts():
    """A price far from scraped must drift back within 20 ticks."""
    state = MarketState(mid_price=Decimal("12.50"), pressure=1.0)
    for _ in range(20):
        state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    assert state.mid_price < Decimal("12.30")


def test_bid_ask_prices_computed():
    """buy_price and sell_price are symmetric around mid_price."""
    state = MarketState(mid_price=SCRAPED, pressure=0.0)
    state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    half = DEFAULT_SETTINGS.avg_spread / 2
    assert state.buy_price == state.mid_price - half
    assert state.sell_price == state.mid_price + half


def test_pressure_clipped():
    """Pressure is always in [-1.0, +1.0] regardless of noise."""
    state = MarketState(mid_price=SCRAPED, pressure=0.99)
    for _ in range(50):
        state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    assert -1.0 <= state.pressure <= 1.0
```

### Step 2: Run tests to confirm they fail

```bash
docker compose exec backend pytest tests/test_market_making_pressure.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` (file doesn't exist yet).

### Step 3: Implement MarketState

Create `backend/app/services/market_making_service.py`:

```python
"""
Market Making Service

Implements the bid/ask pressure model for organic price volatility
around the scraped reference price.

MarketState is in-memory only. On restart, mid_price re-initializes
from scraped price and pressure starts at 0. Market stabilizes in 2-3 ticks.
"""
import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AutoTradeMarketSettings,
    AutoTradeRule,
    CertificateType,
    MarketMakerClient,
    MarketMakerType,
    MarketType,
    Order,
    OrderSide,
    OrderStatus,
)
from app.services.price_scraper import price_scraper

logger = logging.getLogger(__name__)


# ============================================================================
# PRESSURE MODEL — pure dataclasses, no DB dependency
# ============================================================================


@dataclass
class PressureSettings:
    """Parameters controlling the bid/ask pressure model."""
    tick_size: Decimal
    avg_spread: Decimal
    pressure_momentum: Decimal  # how much pressure carries over (0–1)
    pressure_sigma: Decimal     # random noise per tick
    reversion_alpha: Decimal    # pull strength toward scraped price
    band_amplitude_ticks: int   # max deviation = amplitude * tick_size


@dataclass
class MarketState:
    """
    Per-market in-memory state for the pressure model.

    mid_price: current simulated mid, initialized from scraped price
    pressure:  [-1.0, +1.0] net directional bias, starts at 0
    buy_price: last computed BUY MM order price (mid - half_spread)
    sell_price: last computed SELL MM order price (mid + half_spread)
    """
    mid_price: Decimal
    pressure: float = 0.0
    buy_price: Decimal = Decimal("0")
    sell_price: Decimal = Decimal("0")

    def tick(self, scraped_price: Decimal, settings: PressureSettings) -> None:
        """
        Advance the pressure model by one tick.

        1. Random component:   δ_random = gauss(0, σ)
        2. Mean reversion:     δ_revert = -α * (mid - scraped) / tick
        3. Update pressure:    pressure = clip(pressure * momentum + δ_random + δ_revert)
        4. Update mid_price:   mid = scraped + pressure * amplitude * tick
        5. Compute bid/ask:    buy = mid - half_spread, sell = mid + half_spread
        """
        tick = settings.tick_size
        sigma = float(settings.pressure_sigma)
        alpha = float(settings.reversion_alpha)
        momentum = float(settings.pressure_momentum)
        amplitude = settings.band_amplitude_ticks

        delta_random = random.gauss(0.0, sigma)
        delta_revert = -alpha * float(mid_deviation := (self.mid_price - scraped_price)) / float(tick)

        new_pressure = momentum * self.pressure + delta_random + delta_revert
        self.pressure = max(-1.0, min(1.0, new_pressure))

        # Update mid price
        offset = Decimal(str(self.pressure * amplitude)) * tick
        self.mid_price = scraped_price + offset

        # Round mid to tick
        self.mid_price = (self.mid_price / tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * tick

        # Compute buy/ask symmetric around mid
        half_spread = settings.avg_spread / 2
        self.buy_price = self.mid_price - half_spread
        self.sell_price = self.mid_price + half_spread


# ============================================================================
# MODULE-LEVEL STATE (survives React component lifecycle)
# ============================================================================

# Keyed by market_key: "CEA_BID" / "CEA_ASK"
_market_states: dict[str, MarketState] = {}


def get_or_create_state(market_key: str, initial_mid: Decimal) -> MarketState:
    """Get existing MarketState or create with given mid price."""
    if market_key not in _market_states:
        _market_states[market_key] = MarketState(mid_price=initial_mid)
        logger.info(f"[MarketMaking] Initialized state for {market_key} at mid={initial_mid}")
    return _market_states[market_key]


# ============================================================================
# TICK — called by scheduler per rule per cycle
# ============================================================================


async def tick(
    db: AsyncSession,
    rule: AutoTradeRule,
    market_key: str,
    market_settings: AutoTradeMarketSettings,
) -> bool:
    """
    Advance one market making tick for the given rule.

    1. Load scraped price
    2. Build PressureSettings from market_settings
    3. Update pressure + mid_price via MarketState.tick()
    4. Cancel all resting orders for this MM + side
    5. Place new order at computed price via order_service

    Returns True if an order was placed, False otherwise.
    """
    from app.services.order_service import place_order

    try:
        market_maker = rule.market_maker
        if not market_maker or not market_maker.is_active:
            logger.debug(f"[MarketMaking] Skipping {rule.name}: MM inactive")
            return False

        # Determine certificate type and side
        if market_maker.mm_type in (MarketMakerType.CEA_BUYER, MarketMakerType.CEA_SELLER):
            certificate_type = CertificateType.CEA
            market_type = MarketType.CEA_CASH
        else:
            # Swap market — not handled by pressure model yet, skip
            return False

        # Load scraped price
        scraped_price = await _get_scraped_price(certificate_type)
        if scraped_price is None:
            logger.warning(f"[MarketMaking] {rule.name}: scraped price unavailable, skipping tick")
            return False

        # Build pressure settings from DB settings
        tick_size = Decimal(str(market_settings.tick_size or "0.10"))
        avg_spread = Decimal(str(market_settings.avg_spread or "0.20"))
        settings = PressureSettings(
            tick_size=tick_size,
            avg_spread=avg_spread,
            pressure_momentum=Decimal(str(market_settings.pressure_momentum or "0.70")),
            pressure_sigma=Decimal(str(market_settings.pressure_sigma or "0.25")),
            reversion_alpha=Decimal(str(market_settings.reversion_alpha or "0.20")),
            band_amplitude_ticks=int(market_settings.band_amplitude_ticks or 3),
        )

        # Get or create state, initializing mid from scraped price
        state = get_or_create_state(market_key, scraped_price)

        # Advance the pressure model
        state.tick(scraped_price=scraped_price, settings=settings)

        # Determine target order price based on side
        if rule.side == OrderSide.BUY:
            order_price = state.buy_price
        else:
            order_price = state.sell_price

        # Ensure positive price
        order_price = max(order_price, tick_size)

        # Cancel all resting orders for this MM + side
        await _cancel_resting_orders(db, market_maker.id, certificate_type, rule.side)

        # Calculate quantity (use existing random range from rule)
        min_qty = rule.min_quantity or Decimal("100")
        max_qty = rule.max_quantity or Decimal("1000")
        qty_range = max_qty - min_qty
        quantity = min_qty + Decimal(str(random.random())) * qty_range
        from decimal import ROUND_DOWN
        quantity = max(Decimal("1"), quantity.quantize(Decimal("1"), rounding=ROUND_DOWN))

        # Get admin user ID (first admin entity)
        admin_user_id = await _get_admin_user_id(db)
        if admin_user_id is None:
            logger.error("[MarketMaking] No admin user found — cannot place order")
            return False

        # Place order via OrderService
        order = await place_order(
            db=db,
            market_maker_id=market_maker.id,
            certificate_type=certificate_type,
            market_type=market_type,
            side=rule.side,
            price=order_price,
            quantity=quantity,
            rule=rule,
            admin_user_id=admin_user_id,
        )

        if order:
            logger.info(
                f"[MarketMaking] {rule.name}: placed {rule.side.value} "
                f"{quantity} {certificate_type.value} @ {order_price} "
                f"(pressure={state.pressure:.2f}, mid={state.mid_price})"
            )
            return True

        return False

    except Exception as e:
        logger.exception(f"[MarketMaking] tick() failed for {rule.name}: {e}")
        await db.rollback()
        return False


# ============================================================================
# HELPERS
# ============================================================================


async def _get_scraped_price(certificate_type: CertificateType) -> Optional[Decimal]:
    try:
        prices = await price_scraper.get_current_prices()
        cert_key = certificate_type.value.lower()
        if cert_key in prices and prices[cert_key].get("price"):
            return Decimal(str(prices[cert_key]["price"]))
    except Exception as e:
        logger.error(f"[MarketMaking] Failed to get scraped price: {e}")
    return None


async def _cancel_resting_orders(
    db: AsyncSession,
    market_maker_id: uuid.UUID,
    certificate_type: CertificateType,
    side: OrderSide,
) -> int:
    """Cancel all resting orders for this MM + side. Returns count cancelled."""
    result = await db.execute(
        select(Order).where(
            and_(
                Order.market_maker_id == market_maker_id,
                Order.certificate_type == certificate_type,
                Order.side == side,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
    )
    orders = list(result.scalars().all())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for o in orders:
        o.status = OrderStatus.CANCELLED
        o.updated_at = now
    if orders:
        await db.flush()
        logger.debug(f"[MarketMaking] Cancelled {len(orders)} resting orders for MM {market_maker_id} {side.value}")
    return len(orders)


async def _get_admin_user_id(db: AsyncSession) -> Optional[uuid.UUID]:
    """Return the ID of any active admin user (for audit trail)."""
    from app.models.models import User, UserRole
    result = await db.execute(
        select(User.id).where(User.role == UserRole.ADMIN).limit(1)
    )
    return result.scalar_one_or_none()
```

### Step 4: Run tests

```bash
docker compose exec backend pytest tests/test_market_making_pressure.py -v
```

Expected: 4 tests PASS. If `test_pressure_stays_in_band` occasionally fails (stochastic), run 3 times — it should pass consistently with the chosen parameters.

### Step 5: Commit

```bash
git add backend/app/services/market_making_service.py backend/tests/test_market_making_pressure.py
git commit -m "feat(autotrade): MarketState pressure model with TDD"
```

---

## Task 3: OrderService — Place Order

**Files:**
- Create: `backend/app/services/order_service.py`
- Create: `backend/tests/test_order_service.py`

### Step 1: Write the failing tests

Create `backend/tests/test_order_service.py`:

```python
"""Integration tests for OrderService.place_order — uses live DB."""
import pytest
import uuid
from decimal import Decimal
from sqlalchemy import select, and_

from app.core.database import get_db
from app.models.models import (
    CertificateType, CashMarketTrade, MarketType, Order, OrderSide, OrderStatus
)
from app.services.order_service import place_order


@pytest.fixture
def any_admin_id(client):
    """Get any admin user ID from the live DB via the test client."""
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@nihaogroup.com",
        "password": "admin123"
    })
    assert resp.status_code == 200
    return resp.json()["user"]["id"]


@pytest.fixture
def any_mm_buyer_id(client):
    """Get the CEA Buyer market maker ID."""
    # This relies on MMs existing in the dev DB after bootstrap
    resp = client.get("/api/v1/admin/market-makers", headers={"Authorization": f"Bearer {_get_token(client)}"})
    mms = resp.json()
    for mm in mms:
        if mm.get("mm_type") == "CEA_BUYER":
            return mm["id"]
    pytest.skip("No CEA_BUYER market maker found")


@pytest.fixture
def any_mm_seller_id(client):
    resp = client.get("/api/v1/admin/market-makers", headers={"Authorization": f"Bearer {_get_token(client)}"})
    mms = resp.json()
    for mm in mms:
        if mm.get("mm_type") == "CEA_SELLER":
            return mm["id"]
    pytest.skip("No CEA_SELLER market maker found")


def _get_token(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@nihaogroup.com", "password": "admin123"})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_place_order_creates_order(any_mm_buyer_id, any_admin_id):
    """place_order() creates an Order with OPEN status."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        order = await place_order(
            db=db,
            market_maker_id=uuid.UUID(any_mm_buyer_id),
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.BUY,
            price=Decimal("10.00"),  # well below market — won't cross anything
            quantity=Decimal("100"),
            rule=None,
            admin_user_id=uuid.UUID(any_admin_id),
        )
        assert order is not None
        assert order.status in (OrderStatus.OPEN, OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED)

        # Teardown: cancel the order
        if order.status == OrderStatus.OPEN:
            order.status = OrderStatus.CANCELLED
            await db.commit()


@pytest.mark.asyncio
async def test_crossing_orders_produce_trade(any_mm_buyer_id, any_mm_seller_id, any_admin_id):
    """A BUY at price > SELL price produces a CashMarketTrade."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        buy_id = uuid.UUID(any_mm_buyer_id)
        sell_id = uuid.UUID(any_mm_seller_id)
        admin_id = uuid.UUID(any_admin_id)

        # Count trades before
        count_before_result = await db.execute(
            select(CashMarketTrade).where(CashMarketTrade.certificate_type == CertificateType.CEA)
        )
        count_before = len(list(count_before_result.scalars().all()))

        # Place SELL first (will rest in book)
        sell_order = await place_order(
            db=db,
            market_maker_id=sell_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.SELL,
            price=Decimal("11.00"),
            quantity=Decimal("50"),
            rule=None,
            admin_user_id=admin_id,
        )

        # Place BUY that crosses (price > sell price)
        buy_order = await place_order(
            db=db,
            market_maker_id=buy_id,
            certificate_type=CertificateType.CEA,
            market_type=MarketType.CEA_CASH,
            side=OrderSide.BUY,
            price=Decimal("11.50"),  # crosses the 11.00 SELL
            quantity=Decimal("50"),
            rule=None,
            admin_user_id=admin_id,
        )

        # Verify trade was created
        count_after_result = await db.execute(
            select(CashMarketTrade).where(CashMarketTrade.certificate_type == CertificateType.CEA)
        )
        count_after = len(list(count_after_result.scalars().all()))
        assert count_after > count_before, "Expected at least one new trade"

        # Teardown: cancel any remaining open orders we created
        for o in [sell_order, buy_order]:
            if o and o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                o.status = OrderStatus.CANCELLED
        await db.commit()
```

### Step 2: Run tests to verify they fail

```bash
docker compose exec backend pytest tests/test_order_service.py -v
```

Expected: `ImportError` (file doesn't exist yet).

### Step 3: Implement OrderService

Create `backend/app/services/order_service.py`:

```python
"""
Order Service

Validates, persists, and initiates matching for market maker orders.
This is the entry point for all MM order placement — wraps
LimitOrderMatcher.match_incoming_order() for cross-matching.
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
    TransactionType,
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
    1. Validate inputs
    2. Persist Order with OPEN status
    3. Create audit ticket
    4. Update rule execution tracking (if rule provided)
    5. Call LimitOrderMatcher.match_incoming_order() for crossing
    6. Broadcast orderbook_updated WS event
    7. Commit

    Returns the Order on success, None on failure.
    """
    try:
        # Basic validation
        if price <= Decimal("0"):
            logger.warning(f"[OrderService] Rejected order: price={price} <= 0")
            return None
        if quantity < Decimal("1"):
            logger.warning(f"[OrderService] Rejected order: quantity={quantity} < 1")
            return None

        # Create order
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

        # Audit ticket
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

        # Update rule execution tracking
        if rule is not None:
            from app.services.auto_trade_executor import AutoTradeExecutor
            rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(rule)
            rule.execution_count = (rule.execution_count or 0) + 1

        # Match against existing orders
        await LimitOrderMatcher.match_incoming_order(db, order, user_id=admin_user_id)

        # Commit all changes (order + any trades from matching)
        await db.commit()
        await db.refresh(order)

        # Broadcast orderbook update
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
```

### Step 4: Run tests

```bash
docker compose exec backend pytest tests/test_order_service.py -v
```

Expected: 2 tests PASS.

### Step 5: Commit

```bash
git add backend/app/services/order_service.py backend/tests/test_order_service.py
git commit -m "feat(autotrade): OrderService — place_order with LimitOrderMatcher integration"
```

---

## Task 4: Gut AutoTradeExecutor to Thin Scheduler

**Files:**
- Modify: `backend/app/services/auto_trade_executor.py`

This is the main surgery. We replace `execute_rule()` with a thin call to `market_making_service.tick()`.
Everything else (priority chain, try_match_orders, cancel_excess_orders, find_price_gaps, etc.) gets removed.

**What we KEEP from the executor:**
- `bootstrap_rules()` — still needed to create rules on startup
- `get_rules_ready_for_execution()` — still needed by scheduler
- `calculate_next_execution_time()` — still needed by order_service.py
- `get_market_settings()` — still needed by tick()
- `determine_market_key()` — still needed by tick()

**What we REMOVE:**
- `execute_rule()` — replaced by `market_making_service.tick()`
- `try_match_orders()` — replaced by LimitOrderMatcher in OrderService
- `cancel_excess_orders()` — no longer needed (pressure model self-regulates)
- `determine_priority_price()` — priority chain deleted
- `find_price_gaps()`, `pick_gap_fill_price()` — P1 dead code
- `find_thin_levels_near_best()` — P3 dead code
- `calculate_alignment_price()` — P2 dead code
- `calculate_order_price()`, `calculate_order_quantity()` — replaced by pressure model
- `validate_order()` — now in order_service.py
- `get_liquidity_status()`, `get_liquidity_status_v2()` — no longer used
- `calculate_current_liquidity()` — no longer used
- `calculate_order_volume_with_variety()` — no longer used (kept in market_making_service)
- `place_order()` — now in order_service.py

### Step 1: Write test to verify scheduler calls tick

Create `backend/tests/test_autotrade_scheduler.py`:

```python
"""Integration test: scheduler correctly calls tick() for each enabled rule."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_run_cycle_calls_tick_for_enabled_rules():
    """
    Verifies that AutoTradeExecutor.run_cycle() calls market_making_service.tick()
    for each enabled rule that is ready for execution.
    """
    from app.core.database import AsyncSessionLocal
    from app.services.auto_trade_executor import AutoTradeExecutor

    async with AsyncSessionLocal() as db:
        # Bootstrap rules if they don't exist
        await AutoTradeExecutor.bootstrap_rules(db)
        await db.commit()

        rules = await AutoTradeExecutor.get_rules_ready_for_execution(db)
        if not rules:
            pytest.skip("No enabled rules ready — run bootstrap_rules first")

        call_count = 0

        async def fake_tick(db, rule, market_key, market_settings):
            nonlocal call_count
            call_count += 1
            return True

        with patch("app.services.auto_trade_executor.tick", fake_tick):
            await AutoTradeExecutor.run_cycle(db)

        assert call_count > 0, "Expected at least one tick() call"
```

### Step 2: Run test to confirm it fails

```bash
docker compose exec backend pytest tests/test_autotrade_scheduler.py -v
```

Expected: `AttributeError: type object 'AutoTradeExecutor' has no attribute 'run_cycle'`

### Step 3: Replace execute_rule with run_cycle in auto_trade_executor.py

Find the `execute_rule` method (around line 1553) and replace it — and remove all dead code above it.

The new `auto_trade_executor.py` should look like this after surgery. **Replace everything from line ~534 (the priority chain helpers section) to end-of-file** with:

```python
    @staticmethod
    async def run_cycle(db: AsyncSession) -> dict:
        """
        Run one scheduler cycle: tick() for each enabled rule ready for execution.

        This replaces execute_rule(). No priority chains, no liquidity management —
        the pressure model in market_making_service handles all of that.

        Returns a summary dict for logging/status.
        """
        from app.services import market_making_service

        rules = await AutoTradeExecutor.get_rules_ready_for_execution(db)
        result = {"rules_processed": 0, "orders_placed": 0, "errors": 0}

        for rule in rules:
            market_key = AutoTradeExecutor.determine_market_key(rule.market_maker)
            market_settings = await AutoTradeExecutor.get_market_settings(db, market_key)

            if not market_settings:
                logger.warning(f"No market settings for {market_key}, skipping rule {rule.name}")
                continue

            try:
                placed = await market_making_service.tick(
                    db=db,
                    rule=rule,
                    market_key=market_key,
                    market_settings=market_settings,
                )
                result["rules_processed"] += 1
                if placed:
                    result["orders_placed"] += 1
            except Exception as e:
                logger.exception(f"run_cycle: error in rule {rule.name}: {e}")
                result["errors"] += 1

        return result
```

Also remove the following static methods (they are now dead code):
- `find_price_gaps`
- `pick_gap_fill_price`
- `calculate_alignment_price`
- `find_thin_levels_near_best`
- `determine_priority_price`
- `calculate_order_volume_with_variety`
- `calculate_price_with_deviation`
- `calculate_order_price`
- `calculate_order_quantity`
- `validate_order`
- `place_order`
- `try_match_orders`
- `execute_rule`
- `get_liquidity_status`
- `get_liquidity_status_v2`
- `calculate_current_liquidity`
- `cancel_excess_orders`

**Keep these:**
- `MARKET_KEY_MAP`
- `DEFAULT_MARKET_SETTINGS`
- `bootstrap_rules`
- `get_rules_ready_for_execution`
- `calculate_next_execution_time`
- `get_market_price`
- `get_swap_ratio`
- `get_best_prices`
- `count_active_orders`
- `get_liquidity_settings`
- `determine_market_key`
- `get_market_settings`
- `determine_certificate_type`
- `determine_market_type`
- `run_cycle` (new)

### Step 4: Find where execute_rule is called and update it

```bash
grep -rn "execute_rule\|try_match_orders\|cancel_excess_orders" \
  /Users/victorsafta/work/Niha/backend/app/ --include="*.py"
```

For each call site to `execute_rule`, replace with `run_cycle`. Likely in `app/api/v1/market_maker.py` and `app/main.py` or a background task runner.

### Step 5: Run scheduler test

```bash
docker compose exec backend pytest tests/test_autotrade_scheduler.py -v
```

Expected: PASS.

### Step 6: Run full backend test suite

```bash
docker compose exec backend pytest --tb=short -q
```

Expected: All existing tests pass.

### Step 7: Commit

```bash
git add backend/app/services/auto_trade_executor.py backend/tests/test_autotrade_scheduler.py
git commit -m "refactor(autotrade): gut executor to thin scheduler, route to market_making_service.tick()"
```

---

## Task 5: Full Cycle Integration Test + Smoke Check

**Files:**
- Create: `backend/tests/test_market_making_full_cycle.py`

### Step 1: Write the integration test

```python
"""
Full cycle integration test: scheduler → pressure → orders → match → trade.
Tests that the pressure model produces organic price movement and real trades.
"""
import asyncio
import pytest
from decimal import Decimal
from sqlalchemy import select, and_, desc

from app.core.database import AsyncSessionLocal
from app.models.models import (
    AutoTradeRule, CashMarketTrade, CertificateType, Order, OrderSide, OrderStatus
)
from app.services.auto_trade_executor import AutoTradeExecutor
from app.services import market_making_service


@pytest.mark.asyncio
async def test_multiple_ticks_produce_orders_near_scraped_price():
    """
    After 5 ticks, BUY and SELL orders should exist in the book
    at prices within ±3 ticks (±€0.30) of a reference price.
    """
    from app.services.auto_trade_executor import AutoTradeExecutor

    async with AsyncSessionLocal() as db:
        # Bootstrap if needed
        await AutoTradeExecutor.bootstrap_rules(db)
        await db.commit()

        # Run 5 full cycles
        for _ in range(5):
            await AutoTradeExecutor.run_cycle(db)

        # Check that we have active BUY and SELL orders
        buy_result = await db.execute(
            select(Order).where(
                and_(
                    Order.certificate_type == CertificateType.CEA,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),
                )
            ).order_by(desc(Order.created_at)).limit(5)
        )
        buy_orders = list(buy_result.scalars().all())

        sell_result = await db.execute(
            select(Order).where(
                and_(
                    Order.certificate_type == CertificateType.CEA,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),
                )
            ).order_by(desc(Order.created_at)).limit(5)
        )
        sell_orders = list(sell_result.scalars().all())

        assert len(buy_orders) > 0, "Expected active BUY orders after 5 cycles"
        assert len(sell_orders) > 0, "Expected active SELL orders after 5 cycles"

        # Prices should be reasonable (within ±€1.00 of some mid)
        for o in buy_orders + sell_orders:
            assert o.price > Decimal("5.00"), f"Price {o.price} too low"
            assert o.price < Decimal("25.00"), f"Price {o.price} too high"
```

### Step 2: Run the test

```bash
docker compose exec backend pytest tests/test_market_making_full_cycle.py -v
```

Expected: PASS.

### Step 3: Run the full test suite one final time

```bash
docker compose exec backend pytest --tb=short -q
```

Expected: All tests pass.

### Step 4: Rebuild containers and verify live

```bash
docker compose build backend && docker compose up -d
```

Wait 30 seconds, then check logs:

```bash
docker compose logs backend --tail=50 | grep -E "MarketMaking|pressure|AutoTrade"
```

Expected: Lines like `[MarketMaking] Liquidity Engine BID: placed BUY 450 CEA @ 12.10 (pressure=0.23, mid=12.20)`

### Step 5: Commit

```bash
git add backend/tests/test_market_making_full_cycle.py
git commit -m "test(autotrade): full cycle integration test — scheduler → pressure → orders → match"
```

---

## Post-Implementation Verification

```bash
# TypeScript build (frontend unchanged, should still pass)
cd frontend && npx tsc --noEmit

# All backend tests
docker compose exec backend pytest --tb=short -q

# No hardcoded colors in new files
grep -n "slate-\|gray-\|#[0-9a-fA-F]" \
  backend/app/services/market_making_service.py \
  backend/app/services/order_service.py || echo "Clean"
```

Check `app_truth.md` — no new API routes or roles were added, so no update needed.
