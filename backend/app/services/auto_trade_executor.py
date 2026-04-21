"""
Auto Trade Executor Service

Thin scheduler that delegates order generation to market_making_service.tick().
Retains bootstrap, scheduling, price helpers, and volume calculation used by
other modules (admin endpoints, order_service, fill_spread_with_orders).
"""

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import func

from app.models.models import (
    AutoTradeMarketSettings,
    AutoTradePriceMode,
    AutoTradeQuantityMode,
    AutoTradeRule,
    AutoTradeSettings,
    CashMarketTrade,
    CertificateType,
    MarketMakerClient,
    MarketMakerType,
    MarketType,
    Order,
    OrderSide,
    OrderStatus,
    PriceHistory,
    TicketStatus,
    TransactionType,
)
from app.services.market_maker_service import MarketMakerService
from app.services.price_scraper import price_scraper
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


class AutoTradeExecutor:
    """
    Thin scheduler for market-making rules.

    Delegates all order generation and price discovery to
    market_making_service.tick().  Retains scheduling, bootstrap,
    and helper methods used by other modules.
    """

    # Market key -> (MM types, order side, rule name prefix)
    MARKET_KEY_MAP = {
        "CEA_BID": ([MarketMakerType.CEA_BUYER], OrderSide.BUY, "Liquidity Engine BID"),
        "CEA_ASK": ([MarketMakerType.CEA_SELLER], OrderSide.SELL, "Liquidity Engine ASK"),
        "EUA_SWAP": ([MarketMakerType.EUA_OFFER], OrderSide.SELL, "Liquidity Engine SWAP"),
    }

    # Default market settings based on OTC carbon market research
    DEFAULT_MARKET_SETTINGS = {
        "CEA_BID": {
            "target_liquidity": Decimal("500000"),
            "price_deviation_pct": Decimal("3.0"),
            "avg_order_count": 10,
            "min_order_volume_eur": Decimal("5000"),
            "max_order_volume_eur": Decimal("250000"),
            "volume_variety": 7,
            "max_orders_per_price_level": 4,
            "interval_seconds": 60,
            "internal_trade_interval": 120,
            "internal_trade_volume_min": Decimal("10000"),
            "internal_trade_volume_max": Decimal("100000"),
            "avg_spread": Decimal("0.20"),
            "tick_size": Decimal("0.10"),
        },
        "CEA_ASK": {
            "target_liquidity": Decimal("500000"),
            "price_deviation_pct": Decimal("3.0"),
            "avg_order_count": 10,
            "min_order_volume_eur": Decimal("5000"),
            "max_order_volume_eur": Decimal("250000"),
            "volume_variety": 7,
            "max_orders_per_price_level": 4,
            "interval_seconds": 60,
            "internal_trade_interval": 120,
            "internal_trade_volume_min": Decimal("10000"),
            "internal_trade_volume_max": Decimal("100000"),
            "avg_spread": Decimal("0.20"),
            "tick_size": Decimal("0.10"),
        },
        "EUA_SWAP": {
            "target_liquidity": Decimal("1000000"),
            "price_deviation_pct": Decimal("2.0"),
            "avg_order_count": 8,
            "min_order_volume_eur": Decimal("10000"),
            "max_order_volume_eur": Decimal("500000"),
            "volume_variety": 5,
            "max_orders_per_price_level": 3,
            "interval_seconds": 90,
            "internal_trade_interval": 300,
            "internal_trade_volume_min": Decimal("25000"),
            "internal_trade_volume_max": Decimal("200000"),
            "avg_spread": Decimal("0.0050"),
            "tick_size": Decimal("0.0010"),
        },
    }

    @staticmethod
    async def bootstrap_rules(db: AsyncSession) -> int:
        """
        Bootstrap AutoTradeMarketSettings and AutoTradeRule records.

        Called once at executor startup so that settings and rules exist even if the admin
        has never saved market settings via PUT endpoint.

        Returns the number of rules created.
        """
        created = 0

        for market_key, (mm_types, side, prefix) in AutoTradeExecutor.MARKET_KEY_MAP.items():
            # Ensure market settings exist (create with defaults if missing)
            settings_result = await db.execute(
                select(AutoTradeMarketSettings).where(
                    AutoTradeMarketSettings.market_key == market_key
                )
            )
            settings = settings_result.scalar_one_or_none()
            if not settings:
                defaults = AutoTradeExecutor.DEFAULT_MARKET_SETTINGS.get(market_key, {})
                settings = AutoTradeMarketSettings(
                    market_key=market_key,
                    enabled=True,
                    **defaults,
                )
                db.add(settings)
                await db.flush()
                logger.info(f"Bootstrapped AutoTradeMarketSettings for {market_key}")

            # Get active market makers of matching types
            mm_result = await db.execute(
                select(MarketMakerClient).where(
                    MarketMakerClient.mm_type.in_(mm_types),
                    MarketMakerClient.is_active.is_(True),
                )
            )
            market_makers = list(mm_result.scalars().all())

            for mm in market_makers:
                # Check if rule already exists
                existing = await db.execute(
                    select(AutoTradeRule).where(
                        AutoTradeRule.market_maker_id == mm.id,
                        AutoTradeRule.side == side,
                        AutoTradeRule.name.like("Liquidity Engine%"),
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                # Calculate min quantity from settings
                min_quantity = Decimal("1")
                if settings.target_liquidity and settings.avg_order_count:
                    avg_order_value = settings.target_liquidity / Decimal(str(settings.avg_order_count))
                    min_quantity = max(Decimal("1"), avg_order_value / Decimal("70"))

                # Spread: CEA cash uses avg_spread (target e.g. 0.1 EUR); SWAP uses price_deviation_pct
                if market_key in ("CEA_BID", "CEA_ASK"):
                    target_spread = settings.avg_spread if settings.avg_spread is not None else Decimal("0.1")
                    spread_min = target_spread
                    spread_max = target_spread * Decimal("1.5")
                else:
                    spread_min = settings.price_deviation_pct or Decimal("0.01")
                    spread_max = (settings.price_deviation_pct or Decimal("0.01")) * Decimal("3")

                rule = AutoTradeRule(
                    market_maker_id=mm.id,
                    name=f"{prefix} - {mm.name}",
                    enabled=settings.enabled,
                    side=side,
                    order_type="LIMIT",
                    price_mode=AutoTradePriceMode.RANDOM_SPREAD,
                    spread_min=spread_min,
                    spread_max=spread_max,
                    max_price_deviation=settings.price_deviation_pct,
                    quantity_mode=AutoTradeQuantityMode.RANDOM_RANGE,
                    min_quantity=min_quantity,
                    max_quantity=min_quantity * Decimal(str(1 + (settings.volume_variety or 5) * 0.1)),
                    interval_mode="fixed",
                    interval_seconds=settings.interval_seconds,
                    next_execution_at=datetime.now(timezone.utc).replace(tzinfo=None) if settings.enabled else None,
                )
                db.add(rule)
                created += 1
                logger.info(f"Bootstrapped rule: {rule.name} ({market_key}, {side.value})")

        if created:
            await db.flush()
            logger.info(f"Bootstrapped {created} auto-trade rules")
        else:
            logger.info("No new auto-trade rules needed (all exist or no MMs)")

        return created

    @staticmethod
    async def get_rules_ready_for_execution(
        db: AsyncSession,
    ) -> List[AutoTradeRule]:
        """
        Get all enabled rules that are ready for execution.
        A rule is ready if:
        - It is enabled
        - Its market maker is active
        - Its next_execution_at is in the past or null (never executed)
        """
        # Naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        result = await db.execute(
            select(AutoTradeRule)
            .join(MarketMakerClient)
            .where(
                and_(
                    AutoTradeRule.enabled.is_(True),
                    MarketMakerClient.is_active.is_(True),
                    # Ready if never executed or scheduled time has passed
                    (AutoTradeRule.next_execution_at.is_(None)) |
                    (AutoTradeRule.next_execution_at <= now)
                )
            )
            .options(selectinload(AutoTradeRule.market_maker))
        )

        return list(result.scalars().all())

    @staticmethod
    def calculate_next_execution_time(
        rule: AutoTradeRule,
        interval_variation_pct: Optional[Decimal] = None,
        override_interval_factor: Optional[float] = None,
    ) -> datetime:
        """
        Calculate the next execution time based on interval mode.
        For random mode, picks a random interval between min and max.
        Prefers seconds-based intervals if set, otherwise falls back to minutes.

        If interval_variation_pct is provided (from market settings), applies
        +/-pct% random variation to the calculated interval.

        If override_interval_factor is provided (e.g. 0.25 for spread narrowing),
        multiplies the base interval by this factor for faster execution.
        """
        # Naive UTC for TIMESTAMP WITHOUT TIME ZONE (asyncpg)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if rule.interval_mode == "random":
            # Prefer seconds-based intervals
            if rule.interval_min_seconds is not None and rule.interval_max_seconds is not None:
                min_secs = rule.interval_min_seconds
                max_secs = rule.interval_max_seconds
                interval_secs = random.randint(min_secs, max_secs)
            else:
                # Fall back to minutes
                min_mins = rule.interval_min_minutes or 1
                max_mins = rule.interval_max_minutes or 30
                interval_secs = random.randint(min_mins, max_mins) * 60
        else:
            # Fixed mode - prefer seconds
            if rule.interval_seconds is not None:
                interval_secs = rule.interval_seconds
            else:
                interval_secs = (rule.interval_minutes or 5) * 60

        # Apply market-level interval variation if provided
        if interval_variation_pct is not None and interval_variation_pct > 0:
            pct = float(interval_variation_pct)
            factor = 1.0 + random.uniform(-pct / 100, pct / 100)
            interval_secs = max(1, int(interval_secs * factor))

        # Apply override for spread narrowing (shorter interval when spread >> target)
        if override_interval_factor is not None and 0 < override_interval_factor < 1:
            interval_secs = max(1, int(interval_secs * override_interval_factor))

        return now + timedelta(seconds=interval_secs)

    @staticmethod
    async def get_market_price(
        certificate_type: str,
    ) -> Optional[Decimal]:
        """
        Get the current scraped market price for a certificate type.
        Returns None if price unavailable.
        """
        try:
            prices = await price_scraper.get_current_prices()
            cert_key = certificate_type.lower()  # 'cea' or 'eua'

            if cert_key in prices and prices[cert_key].get("price"):
                return Decimal(str(prices[cert_key]["price"]))
            return None
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")
            return None

    @staticmethod
    async def get_swap_ratio() -> Optional[Decimal]:
        """
        Get the current CEA/EUA swap ratio.

        IMPORTANT: In the swap market, Order.price is the ratio CEA/EUA
        (how many EUA you get per 1 CEA), NOT a EUR price!

        Example: CEA=9.85 EUR, EUA=83.72 EUR
        Ratio = 9.85/83.72 = 0.1177 (1 CEA -> 0.1177 EUA)

        Returns: Decimal ratio or None if unavailable.
        """
        try:
            prices = await price_scraper.get_current_prices()
            cea_price = prices.get("cea", {}).get("price")
            eua_price = prices.get("eua", {}).get("price")

            if cea_price and eua_price and eua_price > 0:
                ratio = Decimal(str(cea_price)) / Decimal(str(eua_price))
                return ratio.quantize(Decimal("0.0001"))
            return None
        except Exception as e:
            logger.error(f"Failed to get swap ratio: {e}")
            return None

    @staticmethod
    async def get_best_prices(
        db: AsyncSession,
        certificate_type: CertificateType,
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Get best bid and ask prices from the order book.
        Returns: (best_bid, best_ask)
        """
        # Best bid = highest buy price (skip near-exhausted orders with remaining < 1)
        result = await db.execute(
            select(Order.price)
            .where(
                and_(
                    Order.certificate_type == certificate_type,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    (Order.quantity - Order.filled_quantity) >= 1,
                )
            )
            .order_by(Order.price.desc())
            .limit(1)
        )
        best_bid = result.scalar_one_or_none()

        # Best ask = lowest sell price (skip near-exhausted orders with remaining < 1)
        result = await db.execute(
            select(Order.price)
            .where(
                and_(
                    Order.certificate_type == certificate_type,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    (Order.quantity - Order.filled_quantity) >= 1,
                )
            )
            .order_by(Order.price.asc())
            .limit(1)
        )
        best_ask = result.scalar_one_or_none()

        return best_bid, best_ask

    @staticmethod
    async def count_active_orders(
        db: AsyncSession,
        market_maker_id: uuid.UUID,
        rule_id: Optional[uuid.UUID] = None,
    ) -> int:
        """Count active orders for a market maker (optionally filtered by rule)."""
        query = select(Order.id).where(
            and_(
                Order.market_maker_id == market_maker_id,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )

        result = await db.execute(query)
        return len(result.scalars().all())

    @staticmethod
    async def get_liquidity_settings(
        db: AsyncSession,
        certificate_type: CertificateType,
    ) -> Optional["AutoTradeSettings"]:
        """Get liquidity settings for a certificate type."""
        result = await db.execute(
            select(AutoTradeSettings).where(
                AutoTradeSettings.certificate_type == certificate_type.value
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def determine_market_key(market_maker: MarketMakerClient) -> str:
        """
        Determine market key for AutoTradeMarketSettings based on market maker type.

        Mapping:
        - CEA_BUYER -> CEA_BID (buying CEA)
        - CEA_SELLER -> CEA_ASK (selling CEA)
        - EUA_OFFER -> EUA_SWAP (swap market)
        """
        if market_maker.mm_type == MarketMakerType.CEA_BUYER:
            return "CEA_BID"
        elif market_maker.mm_type == MarketMakerType.CEA_SELLER:
            return "CEA_ASK"
        elif market_maker.mm_type == MarketMakerType.EUA_OFFER:
            return "EUA_SWAP"
        else:
            # Default fallback
            return "CEA_BID"

    @staticmethod
    async def get_market_settings(
        db: AsyncSession,
        market_key: str,
    ) -> Optional[AutoTradeMarketSettings]:
        """Get market settings for a specific market key."""
        result = await db.execute(
            select(AutoTradeMarketSettings).where(
                AutoTradeMarketSettings.market_key == market_key
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def calculate_order_volume_with_variety(
        min_volume_eur: Decimal,
        volume_variety: int,
        target_liquidity: Optional[Decimal],
        current_liquidity: Decimal,
        avg_order_count: int,
        variation_pct: Optional[Decimal] = None,
        max_volume_eur: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculate order volume using log-normal distribution for realistic market feel.

        volume_variety (1-10) maps to log-normal sigma:
          1 -> sigma=0.05 (orders cluster near midpoint, very uniform)
          5 -> sigma=0.35 (moderate spread)
          10 -> sigma=0.80 (very diverse -- some large, many small)

        Args:
            min_volume_eur: Minimum order volume in EUR
            volume_variety: 1-10 scale controlling distribution width
            target_liquidity: Target liquidity in EUR
            current_liquidity: Current liquidity in EUR
            avg_order_count: Target number of orders
            variation_pct: +/-% variation (legacy, ignored when variety is set)
            max_volume_eur: Maximum order volume in EUR (cap)

        Returns:
            Order volume in EUR
        """
        min_vol = float(min_volume_eur)
        max_vol = float(max_volume_eur) if max_volume_eur and max_volume_eur > 0 else min_vol * 10

        # Ensure sensible range
        if max_vol <= min_vol:
            max_vol = min_vol * 2

        # Map variety (1-10) to log-normal sigma
        sigma = 0.05 + (max(1, min(10, volume_variety)) - 1) * 0.083

        # Generate log-normal sample (median=1.0)
        raw = random.lognormvariate(0.0, sigma)

        # Scale: median maps to midpoint of [min_vol, max_vol]
        midpoint = (min_vol + max_vol) / 2.0
        volume = raw * midpoint

        # Clamp to [min_vol, max_vol]
        volume = max(min_vol, min(max_vol, volume))

        return Decimal(str(round(volume, 2)))

    # ------------------------------------------------------------------
    # Market type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def determine_certificate_type(
        market_maker: MarketMakerClient,
    ) -> CertificateType:
        """Determine certificate type based on market maker type."""
        if market_maker.mm_type in [MarketMakerType.CEA_BUYER, MarketMakerType.CEA_SELLER]:
            return CertificateType.CEA
        return CertificateType.EUA

    @staticmethod
    def determine_market_type(
        market_maker: MarketMakerClient,
    ) -> MarketType:
        """Determine market type based on market maker type."""
        if market_maker.mm_type in [MarketMakerType.CEA_BUYER, MarketMakerType.CEA_SELLER]:
            return MarketType.CEA_CASH
        return MarketType.SWAP

    # ------------------------------------------------------------------
    # Scheduler entry point
    # ------------------------------------------------------------------

    @staticmethod
    async def run_cycle(db: AsyncSession) -> dict:
        """
        Run one scheduler cycle: tick() for each enabled rule ready for execution.

        Replaces execute_rule(). No priority chains -- the pressure model in
        market_making_service handles all order generation and price discovery.

        Returns a summary dict for logging/status.
        """
        from app.services import market_making_service

        rules = await AutoTradeExecutor.get_rules_ready_for_execution(db)
        result = {"rules_processed": 0, "orders_placed": 0, "errors": 0}

        for rule in rules:
            market_maker = rule.market_maker
            if not market_maker:
                continue

            market_key = AutoTradeExecutor.determine_market_key(market_maker)
            market_settings = await AutoTradeExecutor.get_market_settings(db, market_key)

            if not market_settings:
                logger.warning(f"[Scheduler] No market settings for {market_key}, skipping {rule.name}")
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
                logger.exception(f"[Scheduler] Error in rule {rule.name}: {e}")
                result["errors"] += 1

        return result

    # ------------------------------------------------------------------
    # Legacy compatibility: execute_all_ready_rules wraps run_cycle
    # ------------------------------------------------------------------

    @staticmethod
    async def execute_all_ready_rules(
        db: AsyncSession,
        admin_user_id: uuid.UUID,
    ) -> List[Dict]:
        """
        Execute all rules that are ready for execution.

        Thin wrapper around run_cycle() that returns the legacy result format
        expected by main.py and market_maker.py callers.
        """
        try:
            cycle_result = await AutoTradeExecutor.run_cycle(db)
            logger.info(
                f"Scheduler cycle: {cycle_result['rules_processed']} rules, "
                f"{cycle_result['orders_placed']} orders, "
                f"{cycle_result['errors']} errors"
            )
            # Convert to legacy format (list of dicts with success/order_id/reason)
            results = []
            for _ in range(cycle_result["orders_placed"]):
                results.append({"success": True, "order_id": "via_tick"})
            for _ in range(cycle_result["rules_processed"] - cycle_result["orders_placed"]):
                results.append({"success": False, "reason": "tick_no_order"})
            for _ in range(cycle_result["errors"]):
                results.append({"success": False, "reason": "tick_error"})
            return results
        except Exception as e:
            logger.exception(f"Error in execute_all_ready_rules: {e}")
            return []


# Background task for running auto-trade execution
_executor_task: Optional[asyncio.Task] = None
_executor_running = False

# Module-level status tracking (read by GET /admin/auto-trade-status)
_executor_status: Dict = {
    "executor_running": False,
    "cycle_interval_seconds": 5,
    "last_cycle_at": None,
    "last_cycle_results": {
        "rules_checked": 0,
        "orders_placed": 0,
        "internal_trades": 0,
        "errors": 0,
    },
    "next_cycle_at": None,
}


def get_executor_status() -> Dict:
    """Return a snapshot of the executor status for the status endpoint."""
    return dict(_executor_status)


def update_executor_status(
    results: List[Dict],
    cycle_interval: int = 5,
) -> None:
    """Update module-level status after an executor cycle."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    orders_placed = sum(1 for r in results if r.get("success") and r.get("order_id"))
    internal = sum(1 for r in results if r.get("action") in ("internal_trade", "threshold_reduction"))
    errors = sum(1 for r in results if not r.get("success") and r.get("reason"))

    _executor_status["executor_running"] = True
    _executor_status["cycle_interval_seconds"] = cycle_interval
    _executor_status["last_cycle_at"] = now.isoformat()
    _executor_status["last_cycle_results"] = {
        "rules_checked": len(results),
        "orders_placed": orders_placed,
        "internal_trades": internal,
        "errors": errors,
    }
    _executor_status["next_cycle_at"] = (now + timedelta(seconds=cycle_interval)).isoformat()


async def start_auto_trade_executor(
    db_session_maker,
    admin_user_id: uuid.UUID,
    check_interval_seconds: int = 30,
):
    """
    Start the background auto-trade executor.

    Args:
        db_session_maker: Async session factory for database connections
        admin_user_id: Admin user ID for audit trail
        check_interval_seconds: How often to check for ready rules (default 30s)
    """
    global _executor_running
    _executor_running = True

    logger.info(f"Starting auto-trade executor (check interval: {check_interval_seconds}s)")

    while _executor_running:
        try:
            async with db_session_maker() as db:
                results = await AutoTradeExecutor.execute_all_ready_rules(db, admin_user_id)

                successes = sum(1 for r in results if r["success"])
                if results:
                    logger.info(f"Auto-trade cycle complete: {successes}/{len(results)} successful")

        except Exception as e:
            logger.exception(f"Error in auto-trade executor cycle: {e}")

        await asyncio.sleep(check_interval_seconds)


async def stop_auto_trade_executor():
    """Stop the background auto-trade executor."""
    global _executor_running, _executor_task
    _executor_running = False

    if _executor_task:
        _executor_task.cancel()
        try:
            await _executor_task
        except asyncio.CancelledError:
            pass
        _executor_task = None

    logger.info("Auto-trade executor stopped")


async def get_all_orderbook_prices(
    db: AsyncSession,
    certificate_type: CertificateType,
    side: OrderSide,
) -> List[Decimal]:
    """Get all active price levels for a given side of the order book."""
    result = await db.execute(
        select(Order.price)
        .where(
            and_(
                Order.certificate_type == certificate_type,
                Order.side == side,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        .distinct()
        .order_by(Order.price.desc() if side == OrderSide.BUY else Order.price.asc())
    )
    return [row[0] for row in result.fetchall()]


async def fill_spread_with_orders(
    db: AsyncSession,
    certificate_type: CertificateType,
    market_type: MarketType,
    admin_user_id: uuid.UUID,
    price_step: Decimal = Decimal("0.1"),
    quantity_per_level: Decimal = Decimal("100000"),
) -> Dict:
    """
    Fill the spread between best bid and best ask with orders at each price level.

    This creates market depth by:
    1. Placing BID orders from best_bid+0.1 up to best_ask-0.1 (to improve best bid)
    2. Filling any gaps in the ASK side (missing price levels like 10.0 when 9.9 and 10.1 exist)

    The goal is to ensure max spread = 0.1 EUR after execution.

    Args:
        db: Database session
        certificate_type: CEA or EUA
        market_type: CEA_CASH or SWAP
        admin_user_id: Admin user for audit trail
        price_step: Price increment (default 0.1 EUR)
        quantity_per_level: Quantity to place at each price level

    Returns:
        Dict with results including orders created, prices filled, etc.
    """
    result = {
        "success": False,
        "certificate_type": certificate_type.value,
        "orders_created": 0,
        "bid_orders": [],
        "ask_orders": [],
        "gaps_found": [],
        "message": "",
    }

    try:
        # Get best bid and ask
        best_bid, best_ask = await AutoTradeExecutor.get_best_prices(db, certificate_type)

        if not best_bid or not best_ask:
            result["message"] = f"Cannot fill spread: best_bid={best_bid}, best_ask={best_ask}"
            return result

        spread = best_ask - best_bid
        result["current_spread"] = str(spread)
        result["best_bid"] = str(best_bid)
        result["best_ask"] = str(best_ask)

        if spread <= price_step:
            result["message"] = f"Spread ({spread}) is already <= {price_step}, no filling needed"
            result["success"] = True
            return result

        # Get existing price levels
        existing_bids = set(await get_all_orderbook_prices(db, certificate_type, OrderSide.BUY))
        existing_asks = set(await get_all_orderbook_prices(db, certificate_type, OrderSide.SELL))

        # Get all market makers
        from app.models.models import MarketMakerClient

        # Get CEA_BUYER market makers for bid orders
        buyer_result = await db.execute(
            select(MarketMakerClient)
            .where(
                and_(
                    MarketMakerClient.is_active.is_(True),
                    MarketMakerClient.mm_type == MarketMakerType.CEA_BUYER,
                )
            )
        )
        buyers = list(buyer_result.scalars().all())

        # Get CEA_SELLER market makers for ask orders
        seller_result = await db.execute(
            select(MarketMakerClient)
            .where(
                and_(
                    MarketMakerClient.is_active.is_(True),
                    MarketMakerClient.mm_type == MarketMakerType.CEA_SELLER,
                )
            )
        )
        sellers = list(seller_result.scalars().all())

        if not buyers and not sellers:
            result["message"] = "No active market makers available"
            return result

        # Calculate BID prices to add (from best_bid+0.1 up to best_ask-0.1)
        # This will improve the best bid and narrow the spread
        bid_prices_to_add = []
        current_price = best_bid + price_step
        while current_price < best_ask:
            # Round to 0.1 EUR step
            current_price = (current_price / price_step).quantize(Decimal("1")) * price_step
            if current_price not in existing_bids:
                bid_prices_to_add.append(current_price)
            current_price += price_step

        # Calculate ASK gaps to fill (missing prices in the ask book)
        # Find gaps where consecutive asks differ by more than 0.1
        sorted_asks = sorted(existing_asks)
        ask_prices_to_add = []

        for i in range(len(sorted_asks) - 1):
            gap = sorted_asks[i + 1] - sorted_asks[i]
            if gap > price_step:
                # Fill the gap
                fill_price = sorted_asks[i] + price_step
                while fill_price < sorted_asks[i + 1]:
                    fill_price = (fill_price / price_step).quantize(Decimal("1")) * price_step
                    if fill_price not in existing_asks:
                        ask_prices_to_add.append(fill_price)
                        result["gaps_found"].append({
                            "between": [str(sorted_asks[i]), str(sorted_asks[i + 1])],
                            "filling": str(fill_price),
                        })
                    fill_price += price_step

        logger.info(f"Fill spread: bid_prices_to_add={bid_prices_to_add}, ask_prices_to_add={ask_prices_to_add}")

        # Place bid orders (using CEA_BUYER market makers)
        buyer_idx = 0
        for price in bid_prices_to_add:
            if not buyers:
                break

            mm = buyers[buyer_idx % len(buyers)]
            buyer_idx += 1

            # Create bid order (MMs have unlimited resources)
            order = Order(
                market=market_type,
                market_maker_id=mm.id,
                certificate_type=certificate_type,
                side=OrderSide.BUY,
                price=price,
                quantity=quantity_per_level,
                filled_quantity=Decimal("0"),
                status=OrderStatus.OPEN,
            )
            db.add(order)
            result["bid_orders"].append({"price": str(price), "mm": mm.name})
            result["orders_created"] += 1

        # Place ask orders (using CEA_SELLER market makers)
        seller_idx = 0
        for price in ask_prices_to_add:
            if not sellers:
                break

            mm = sellers[seller_idx % len(sellers)]
            seller_idx += 1

            # Create ask order (MMs have unlimited resources)
            order = Order(
                market=market_type,
                market_maker_id=mm.id,
                certificate_type=certificate_type,
                side=OrderSide.SELL,
                price=price,
                quantity=quantity_per_level,
                filled_quantity=Decimal("0"),
                status=OrderStatus.OPEN,
            )
            db.add(order)
            result["ask_orders"].append({"price": str(price), "mm": mm.name})
            result["orders_created"] += 1

        await db.commit()

        # Calculate new spread
        new_best_bid, new_best_ask = await AutoTradeExecutor.get_best_prices(db, certificate_type)
        if new_best_bid and new_best_ask:
            result["new_spread"] = str(new_best_ask - new_best_bid)
            result["new_best_bid"] = str(new_best_bid)
            result["new_best_ask"] = str(new_best_ask)

        result["success"] = True
        result["message"] = f"Created {result['orders_created']} orders to fill spread"

        logger.info(f"Fill spread complete: {result['orders_created']} orders created")

        return result

    except Exception as e:
        logger.exception(f"Error filling spread: {e}")
        await db.rollback()
        result["message"] = f"Error: {str(e)}"
        return result
