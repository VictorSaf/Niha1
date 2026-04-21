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
    pressure_momentum: Decimal  # how much pressure carries over (0-1)
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
    buy_price: Decimal = field(default_factory=lambda: Decimal("0"))
    sell_price: Decimal = field(default_factory=lambda: Decimal("0"))

    def tick(self, scraped_price: Decimal, settings: PressureSettings) -> None:
        """
        Advance the pressure model by one tick.

        1. Random component:   delta_random = gauss(0, sigma)
        2. Mean reversion:     delta_revert = -alpha * (mid - scraped) / tick
        3. Update pressure:    pressure = clip(pressure * momentum + delta_random + delta_revert)
        4. Update mid_price:   mid = scraped + pressure * amplitude * tick
        5. Compute bid/ask:    buy = mid - half_spread, sell = mid + half_spread
        """
        tick = settings.tick_size
        sigma = float(settings.pressure_sigma)
        alpha = float(settings.reversion_alpha)
        momentum = float(settings.pressure_momentum)
        amplitude = settings.band_amplitude_ticks

        delta_random = random.gauss(0.0, sigma)
        delta_revert = -alpha * float(self.mid_price - scraped_price) / float(tick)

        new_pressure = momentum * self.pressure + delta_random + delta_revert
        self.pressure = max(-1.0, min(1.0, new_pressure))

        # Update mid price: scraped + pressure * amplitude * tick
        offset = Decimal(str(round(self.pressure * amplitude, 10))) * tick
        self.mid_price = scraped_price + offset

        # Round mid to tick
        self.mid_price = (self.mid_price / tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * tick

        # Compute buy/ask symmetric around mid
        half_spread = settings.avg_spread / 2
        self.buy_price = self.mid_price - half_spread
        self.sell_price = self.mid_price + half_spread


# ============================================================================
# MODULE-LEVEL STATE (survives component lifecycle)
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
