"""
Auto Trade Executor Service

Handles automatic order placement for market makers based on configured rules.
Validates balances before placing orders to ensure orders are always covered.
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
    Executes auto-trade rules for market makers.

    Key responsibilities:
    - Determine when rules should execute based on intervals
    - Calculate order prices based on price mode and scraped prices
    - Calculate order quantities based on quantity mode and available balance
    - Validate sufficient balance before placing orders
    - Place orders with proper audit trail
    """

    # Market key → (MM types, order side, rule name prefix)
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
        ±pct% random variation to the calculated interval.

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
        Ratio = 9.85/83.72 = 0.1177 (1 CEA → 0.1177 EUA)

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
          1 → sigma=0.05 (orders cluster near midpoint, very uniform)
          5 → sigma=0.35 (moderate spread)
          10 → sigma=0.80 (very diverse — some large, many small)

        Args:
            min_volume_eur: Minimum order volume in EUR
            volume_variety: 1-10 scale controlling distribution width
            target_liquidity: Target liquidity in EUR
            current_liquidity: Current liquidity in EUR
            avg_order_count: Target number of orders
            variation_pct: ±% variation (legacy, ignored when variety is set)
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

    @staticmethod
    def calculate_price_with_deviation(
        best_price: Decimal,
        price_deviation_pct: Decimal,
        side: OrderSide,
        is_swap_market: bool = False,
        tick_size: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculate order price with deviation from best price.

        For BUY orders: price is below best ask (or best bid if no asks)
        For SELL orders: price is above best bid (or best ask if no bids)

        The deviation is applied to create spread in the order book.
        Prices are rounded to the configured tick_size.
        """
        # Calculate deviation as percentage
        deviation = best_price * (price_deviation_pct / Decimal("100"))

        # Apply random factor within the deviation range
        random_deviation = Decimal(str(random.random())) * deviation

        if side == OrderSide.BUY:
            # BUY: place below reference price
            price = best_price - random_deviation
        else:
            # SELL: place above reference price
            price = best_price + random_deviation

        if is_swap_market:
            tick = tick_size or Decimal("0.0001")
            price = (price / tick).quantize(Decimal("1")) * tick
            return max(price, tick)
        else:
            tick = tick_size or Decimal("0.1")
            price = (price / tick).quantize(Decimal("1")) * tick
            return max(price, tick)

    # ------------------------------------------------------------------
    # Priority chain helpers (gap fill, price align, level rebalance)
    # ------------------------------------------------------------------

    @staticmethod
    async def find_price_gaps(
        db: AsyncSession,
        certificate_type: CertificateType,
        side: OrderSide,
        tick_size: Decimal = Decimal("0.1"),
    ) -> List[Tuple[Decimal, Decimal]]:
        """
        Priority 1: Find price gaps in the orderbook.

        A gap is any interval > tick_size between adjacent active order prices
        on the same side.  Returns list of (gap_start, gap_end) tuples.
        """
        result = await db.execute(
            select(Order.price)
            .where(
                and_(
                    Order.certificate_type == certificate_type,
                    Order.side == side,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),
                )
            )
            .distinct()
            .order_by(Order.price.asc())
        )
        prices = [row[0] for row in result.all()]

        gaps: List[Tuple[Decimal, Decimal]] = []
        for i in range(len(prices) - 1):
            if prices[i + 1] - prices[i] > tick_size + Decimal("0.001"):
                gaps.append((prices[i] + tick_size, prices[i + 1] - tick_size))
        return gaps

    @staticmethod
    def pick_gap_fill_price(
        gaps: List[Tuple[Decimal, Decimal]],
        tick_size: Decimal = Decimal("0.1"),
    ) -> Optional[Decimal]:
        """Pick a random price inside the first (closest-to-best) gap."""
        if not gaps:
            return None
        gap_start, gap_end = gaps[0]
        if gap_end < gap_start:
            return gap_start
        steps = int((gap_end - gap_start) / tick_size) + 1
        chosen_step = random.randint(0, max(0, steps - 1))
        return gap_start + tick_size * chosen_step

    @staticmethod
    def calculate_alignment_price(
        scraped_price: Optional[Decimal],
        best_price: Optional[Decimal],
        side: OrderSide,
        tick_size: Decimal = Decimal("0.1"),
        threshold: Decimal = Decimal("0.2"),
        market_settings: Optional["AutoTradeMarketSettings"] = None,
    ) -> Optional[Decimal]:
        """
        Priority 2: Price alignment toward scraped reference price.

        If best_bid/ask deviates more than `threshold` EUR from scraped price,
        return a price closer to scraped (applying 60 % mean-reversion).
        """
        if scraped_price is None or best_price is None:
            return None

        if side == OrderSide.BUY:
            # Best bid should be just below scraped; check deviation
            target_best = scraped_price - tick_size  # ideal best bid
            deviation = target_best - best_price
        else:
            target_best = scraped_price + tick_size  # ideal best ask
            deviation = best_price - target_best

        if abs(deviation) <= threshold:
            return None  # Close enough — no alignment needed

        # 60 % correction toward ideal
        correction = Decimal(str(market_settings.alignment_correction_factor)) if market_settings and market_settings.alignment_correction_factor else Decimal("0.60")
        adjustment = deviation * correction
        if side == OrderSide.SELL:
            new_price = best_price - adjustment
        else:
            new_price = best_price + adjustment

        # Round to tick
        new_price = (new_price / tick_size).quantize(Decimal("1")) * tick_size
        return max(new_price, tick_size)

    @staticmethod
    async def find_thin_levels_near_best(
        db: AsyncSession,
        certificate_type: CertificateType,
        side: OrderSide,
        best_price: Decimal,
        max_orders_per_level: int,
        depth_levels: int = 5,
        tick_size: Decimal = Decimal("0.1"),
    ) -> Optional[Decimal]:
        """
        Priority 3: Level rebalancing.

        Scan the first `depth_levels` price ticks from best and return the
        price level with the fewest orders (below max), or None.
        """
        thinnest_price: Optional[Decimal] = None
        thinnest_count = max_orders_per_level  # start high

        for i in range(depth_levels):
            if side == OrderSide.BUY:
                level_price = best_price - tick_size * i
            else:
                level_price = best_price + tick_size * i

            if level_price <= Decimal("0"):
                continue

            count_result = await db.execute(
                select(func.count()).select_from(Order).where(
                    and_(
                        Order.certificate_type == certificate_type,
                        Order.side == side,
                        Order.price == level_price,
                        Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    )
                )
            )
            count = count_result.scalar() or 0

            if count < thinnest_count:
                thinnest_count = count
                thinnest_price = level_price

        # Only return if there's actually room
        if thinnest_count < max_orders_per_level:
            return thinnest_price
        return None

    @staticmethod
    async def determine_priority_price(
        db: AsyncSession,
        certificate_type: CertificateType,
        side: OrderSide,
        market_settings: Optional[AutoTradeMarketSettings],
        scraped_price: Optional[Decimal],
        best_bid: Optional[Decimal],
        best_ask: Optional[Decimal],
        is_swap: bool = False,
    ) -> Tuple[Optional[Decimal], str]:
        """
        Run the 5-priority chain and return (price, reason).

        When MM introduces a new order, first priority is to achieve target spread (0.1 EUR for cash).

        Priority 0: Spread narrowing — if spread > target, place order to narrow it
        Priority 1: Gap filling
        Priority 2: Price alignment toward scraped price
        Priority 3: Level rebalancing near best
        Priority 4: Normal (returns None — caller uses default logic)
        """
        default_tick = Decimal("0.0001") if is_swap else Decimal("0.1")
        raw_tick = Decimal(str(market_settings.tick_size)) if (market_settings and market_settings.tick_size) else default_tick
        tick = max(raw_tick, Decimal("0.0001"))  # guard against zero/negative
        best_price = best_bid if side == OrderSide.BUY else best_ask
        max_per_level = (market_settings.max_orders_per_price_level if market_settings else 3) or 3

        # Target spread when settings.avg_spread is NULL: 0.1 EUR for cash, 0.0050 ratio for swap (matches EUA_SWAP typical avg_spread)
        default_target_spread = Decimal("0.0050") if is_swap else Decimal("0.1")
        target_spread = (
            Decimal(str(market_settings.avg_spread))
            if market_settings and market_settings.avg_spread is not None
            else default_target_spread
        )

        # Priority 0 — spread narrowing (first when MM introduces order)
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            if spread > target_spread:
                if side == OrderSide.BUY and best_bid + tick < best_ask:
                    return best_bid + tick, "priority0_spread_narrow"
                if side == OrderSide.SELL and best_ask - tick > best_bid:
                    return best_ask - tick, "priority0_spread_narrow"

        # Priority 1 — gap filling
        gaps = await AutoTradeExecutor.find_price_gaps(
            db, certificate_type, side, tick
        )
        if gaps:
            gap_price = AutoTradeExecutor.pick_gap_fill_price(gaps, tick)
            if gap_price is not None:
                return gap_price, "priority1_gap_fill"

        # Priority 2 — price alignment toward scraped
        if scraped_price and best_price:
            align_price = AutoTradeExecutor.calculate_alignment_price(
                scraped_price, best_price, side, tick,
                threshold=tick * (market_settings.alignment_threshold_ticks if market_settings and market_settings.alignment_threshold_ticks else 2),
                market_settings=market_settings,
            )
            if align_price is not None:
                # Guard: BUY must not cross above best_ask (would immediately execute at wrong price).
                # SELL is intentionally allowed to cross below best_bid — this causes the order to
                # execute immediately against old bids at their (better) price, consuming stale volume
                # and driving the book toward the real market price (convergence).
                if side == OrderSide.BUY and best_ask is not None and align_price >= best_ask:
                    align_price = best_ask - tick
                if align_price > Decimal("0"):
                    return align_price, "priority2_price_alignment"

        # Priority 3 — level rebalancing
        if best_price and market_settings:
            thin_price = await AutoTradeExecutor.find_thin_levels_near_best(
                db, certificate_type, side, best_price,
                max_per_level, depth_levels=(int(market_settings.level_rebalance_depth) if market_settings and market_settings.level_rebalance_depth else 5), tick_size=tick,
            )
            if thin_price is not None:
                return thin_price, "priority3_level_rebalance"

        # Priority 4 — normal (caller handles)
        return None, "priority4_normal"

    @staticmethod
    async def calculate_current_liquidity(
        db: AsyncSession,
        certificate_type: CertificateType,
        side: OrderSide,
        market_type: Optional[MarketType] = None,
    ) -> Decimal:
        """
        Calculate current liquidity (EUR value) for a side.

        For CEA_CASH market: Liquidity = SUM(price * remaining_quantity)
        For SWAP market: Liquidity = SUM(remaining_quantity * eua_eur_price)
            because Order.price is ratio (CEA/EUA), not EUR price!
        """
        if market_type == MarketType.SWAP:
            # For swap market, quantity is in EUA, price is ratio (not EUR)
            # Get total EUA available
            result = await db.execute(
                select(func.sum(Order.quantity - Order.filled_quantity))
                .where(
                    and_(
                        Order.certificate_type == certificate_type,
                        Order.market == MarketType.SWAP,
                        Order.side == side,
                        Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                        Order.market_maker_id.isnot(None),
                    )
                )
            )
            total_eua = Decimal(str(result.scalar() or 0))

            # Convert to EUR using current EUA price
            eua_eur_price = await AutoTradeExecutor.get_market_price("EUA")
            if eua_eur_price and eua_eur_price > 0:
                return total_eua * eua_eur_price
            return Decimal("0")
        else:
            # For CEA cash market, price is in EUR
            result = await db.execute(
                select(func.sum(Order.price * (Order.quantity - Order.filled_quantity)))
                .where(
                    and_(
                        Order.certificate_type == certificate_type,
                        Order.side == side,
                        Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                        Order.market_maker_id.isnot(None),  # Only MM orders
                    )
                )
            )
            return Decimal(str(result.scalar() or 0))

    @staticmethod
    async def get_liquidity_status(
        db: AsyncSession,
        certificate_type: CertificateType,
        side: OrderSide,
        market_type: Optional[MarketType] = None,
    ) -> Tuple[str, Optional[Decimal], Optional[Decimal]]:
        """
        Check liquidity status relative to target.
        Returns: (status, current_liquidity, target_liquidity)

        Status can be:
        - "below_target": need to place new orders
        - "at_target": within 5% tolerance, do nothing
        - "above_target": need to consume orders via internal trades
        - "no_target": no target set, do nothing
        """
        settings = await AutoTradeExecutor.get_liquidity_settings(db, certificate_type)

        if not settings or not settings.liquidity_limit_enabled:
            return "no_target", None, None

        current = await AutoTradeExecutor.calculate_current_liquidity(
            db, certificate_type, side, market_type
        )

        if side == OrderSide.SELL:
            target = settings.target_ask_liquidity
        else:
            target = settings.target_bid_liquidity

        if target is None or target <= 0:
            return "no_target", current, None

        # 5% tolerance band around target
        tolerance = target * Decimal("0.05")

        if current < target - tolerance:
            return "below_target", current, target
        elif current > target + tolerance:
            return "above_target", current, target
        else:
            return "at_target", current, target

    @staticmethod
    async def get_liquidity_status_v2(
        db: AsyncSession,
        market_key: str,
        certificate_type: CertificateType,
        side: OrderSide,
        market_type: Optional[MarketType] = None,
    ) -> Tuple[str, Optional[Decimal], Optional[Decimal], Optional[AutoTradeMarketSettings]]:
        """
        Check liquidity status using the new AutoTradeMarketSettings.
        Returns: (status, current_liquidity, target_liquidity, market_settings)

        Status can be:
        - "exceeds_max_threshold": URGENT - exceeds max_liquidity_threshold, trigger aggressive internal trades
        - "below_target": need to place new orders
        - "at_target": within 5% tolerance, do nothing
        - "above_target": need to consume orders via internal trades
        - "no_target": no target set or market disabled
        """
        market_settings = await AutoTradeExecutor.get_market_settings(db, market_key)

        if not market_settings or not market_settings.enabled:
            return "no_target", None, None, market_settings

        current = await AutoTradeExecutor.calculate_current_liquidity(
            db, certificate_type, side, market_type
        )

        target = market_settings.target_liquidity

        # Check max threshold first (takes priority)
        max_threshold = market_settings.max_liquidity_threshold
        if max_threshold and max_threshold > 0 and current and current > max_threshold:
            return "exceeds_max_threshold", current, target, market_settings

        if target is None or target <= 0:
            return "no_target", current, None, market_settings

        # 5% tolerance band around target
        tolerance = target * Decimal("0.05")

        if current < target - tolerance:
            return "below_target", current, target, market_settings
        elif current > target + tolerance:
            return "above_target", current, target, market_settings
        else:
            return "at_target", current, target, market_settings

    @staticmethod
    async def execute_internal_trade(
        db: AsyncSession,
        certificate_type: CertificateType,
        admin_user_id: uuid.UUID,
        market_settings: Optional[AutoTradeMarketSettings] = None,
        market_key: Optional[str] = None,
    ) -> Dict:
        """
        Execute an internal trade between market makers.
        Used when liquidity limit is reached - consumes existing orders.

        1. Check internal_trade_interval cooldown (if market_settings provided)
        2. Find best bid and best ask
        3. Find matching BUY and SELL orders
        4. Set trade price to midpoint of matched order prices (deterministic, no random spread)
        5. Match quantity, applying volume limits
        6. Create trade record

        Volume limits: if market_settings has internal_trade_volume_min/max,
        the match quantity is capped using log-normal distribution between
        those bounds. Otherwise, matches the full remaining qty.

        Returns: dict with trade details or error
        """
        result = {
            "success": False,
            "trade_id": None,
            "price": None,
            "quantity": None,
            "reason": None,
        }

        try:
            # Check internal trade interval cooldown
            if market_key and market_settings and market_settings.internal_trade_interval:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                last_at = _last_internal_trade_at.get(market_key)
                if last_at:
                    elapsed = (now - last_at).total_seconds()
                    if elapsed < market_settings.internal_trade_interval:
                        result["reason"] = (
                            f"internal_trade_cooldown ({int(elapsed)}s / "
                            f"{market_settings.internal_trade_interval}s)"
                        )
                        return result

            # Get best prices
            best_bid, best_ask = await AutoTradeExecutor.get_best_prices(
                db, certificate_type
            )

            if not best_bid or not best_ask:
                result["reason"] = "no_spread_available"
                return result

            if best_bid >= best_ask:
                result["reason"] = "no_spread_to_trade_in"
                return result

            # Find a SELL order to consume (best ask = lowest price first, oldest first)
            # Filter out near-exhausted orders (remaining < 1) to avoid match_qty rounding to 0
            sell_result = await db.execute(
                select(Order)
                .where(
                    and_(
                        Order.certificate_type == certificate_type,
                        Order.side == OrderSide.SELL,
                        Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                        Order.market_maker_id.isnot(None),
                        (Order.quantity - Order.filled_quantity) >= 1,
                    )
                )
                .order_by(Order.price.asc(), Order.created_at.asc())
                .limit(1)
            )
            sell_order = sell_result.scalar_one_or_none()

            # Find a BUY order to consume (best bid = highest price first, oldest first)
            buy_result = await db.execute(
                select(Order)
                .where(
                    and_(
                        Order.certificate_type == certificate_type,
                        Order.side == OrderSide.BUY,
                        Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                        Order.market_maker_id.isnot(None),
                        (Order.quantity - Order.filled_quantity) >= 1,
                    )
                )
                .order_by(Order.price.desc(), Order.created_at.asc())
                .limit(1)
            )
            buy_order = buy_result.scalar_one_or_none()

            if not sell_order or not buy_order:
                result["reason"] = "no_matching_orders_found"
                return result

            # Don't match same market maker
            if sell_order.market_maker_id == buy_order.market_maker_id:
                result["reason"] = "only_same_mm_orders_available"
                return result

            # Trade price = midpoint of the two matched orders' actual prices, rounded to tick.
            # This ensures every recorded trade price is directly derived from real order prices
            # in the book (no random spread sampling that produces phantom prices).
            _tick = max(
                Decimal(str(market_settings.tick_size)) if market_settings and market_settings.tick_size else Decimal("0.1"),
                Decimal("0.0001"),
            )
            trade_price = (buy_order.price + sell_order.price) / 2
            trade_price = (trade_price / _tick).quantize(Decimal("1")) * _tick

            # Calculate match quantity (smaller of remaining quantities)
            sell_remaining = sell_order.quantity - sell_order.filled_quantity
            buy_remaining = buy_order.quantity - buy_order.filled_quantity
            max_available_qty = min(sell_remaining, buy_remaining)

            # Apply internal trade volume limits from market_settings
            if (
                market_settings
                and market_settings.internal_trade_volume_min is not None
                and market_settings.internal_trade_volume_max is not None
            ):
                vol_min = float(market_settings.internal_trade_volume_min)
                vol_max = float(market_settings.internal_trade_volume_max)
                if vol_max <= vol_min:
                    vol_max = vol_min * 2
                variety = market_settings.volume_variety or 5
                sigma = 0.05 + (max(1, min(10, variety)) - 1) * 0.083
                raw = random.lognormvariate(0.0, sigma)
                midpoint = (vol_min + vol_max) / 2.0
                volume_eur = max(vol_min, min(vol_max, raw * midpoint))
                # Convert EUR volume to quantity using trade price
                target_qty = Decimal(str(round(volume_eur, 2))) / trade_price
                match_qty = min(max_available_qty, target_qty)
            else:
                match_qty = max_available_qty

            # Round to integer
            match_qty = match_qty.quantize(Decimal("1"), rounding=ROUND_DOWN)

            if match_qty <= 0:
                result["reason"] = "no_quantity_to_match"
                return result

            # Create trade
            trade = CashMarketTrade(
                buy_order_id=buy_order.id,
                sell_order_id=sell_order.id,
                market_maker_id=buy_order.market_maker_id,
                certificate_type=certificate_type,
                price=trade_price,
                quantity=match_qty,
                executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            db.add(trade)
            await db.flush()

            # Persist trade price in price_history for chart data
            db.add(PriceHistory(
                certificate_type=certificate_type,
                price=trade_price,
                currency="EUR",
                source="auto_trade",
                recorded_at=trade.executed_at,
            ))

            # Create audit ticket for internal trade
            buy_ticket_id = getattr(buy_order, 'ticket_id', None)
            sell_ticket_id = getattr(sell_order, 'ticket_id', None)
            related = [tid for tid in [buy_ticket_id, sell_ticket_id] if tid]

            trade_ticket = await TicketService.create_ticket(
                db=db,
                action_type="TRADE_EXECUTED",
                entity_type="Trade",
                entity_id=trade.id,
                status=TicketStatus.SUCCESS,
                user_id=admin_user_id,
                market_maker_id=buy_order.market_maker_id,
                request_payload={
                    "match_type": "internal_trade",
                    "buy_order_id": str(buy_order.id),
                    "sell_order_id": str(sell_order.id),
                },
                response_data={
                    "trade_id": str(trade.id),
                    "buy_order_id": str(buy_order.id),
                    "sell_order_id": str(sell_order.id),
                    "buyer_mm_id": str(buy_order.market_maker_id) if buy_order.market_maker_id else None,
                    "seller_mm_id": str(sell_order.market_maker_id) if sell_order.market_maker_id else None,
                    "certificate_type": certificate_type.value,
                    "price": str(trade_price),
                    "quantity": str(match_qty),
                },
                related_ticket_ids=related,
                tags=["trade", "internal_trade", certificate_type.value.lower()],
            )
            trade.ticket_id = trade_ticket.ticket_id

            # Update buy order
            buy_order.filled_quantity = buy_order.filled_quantity + match_qty
            if buy_order.filled_quantity >= buy_order.quantity:
                buy_order.status = OrderStatus.FILLED
            else:
                buy_order.status = OrderStatus.PARTIALLY_FILLED
            buy_order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            # Update sell order
            sell_order.filled_quantity = sell_order.filled_quantity + match_qty
            if sell_order.filled_quantity >= sell_order.quantity:
                sell_order.status = OrderStatus.FILLED
            else:
                sell_order.status = OrderStatus.PARTIALLY_FILLED
            sell_order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            await db.commit()

            logger.info(
                f"Internal trade executed: {match_qty} {certificate_type.value} @ {trade_price} "
                f"(BUY {buy_order.id} <-> SELL {sell_order.id})"
            )

            # Broadcast trade to all clients so chart + activity update in real-time
            try:
                from app.api.v1.client_ws import client_ws_manager
                asyncio.create_task(client_ws_manager.broadcast_to_all({
                    "type": "trade_executed",
                    "data": {
                        "id": str(trade.id),
                        "certificate_type": certificate_type.value,
                        "price": float(trade_price),
                        "quantity": int(round(float(match_qty))),
                        "side": "BUY",
                        "executed_at": trade.executed_at.isoformat() if trade.executed_at else datetime.now(timezone.utc).isoformat(),
                    },
                }))
            except Exception as ws_err:
                logger.debug(f"WS broadcast failed for internal trade: {ws_err}")

            result["success"] = True
            result["trade_id"] = str(trade.id) if hasattr(trade, 'id') else None
            result["price"] = str(trade_price)
            result["quantity"] = str(match_qty)
            result["buy_order_id"] = str(buy_order.id)
            result["sell_order_id"] = str(sell_order.id)

            # Update interval tracker
            if market_key:
                _last_internal_trade_at[market_key] = datetime.now(timezone.utc).replace(tzinfo=None)

            return result

        except Exception as e:
            logger.exception(f"Error executing internal trade: {e}")
            await db.rollback()
            result["reason"] = f"exception: {str(e)}"
            return result

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

    @staticmethod
    async def calculate_order_price(
        db: AsyncSession,
        rule: AutoTradeRule,
        certificate_type: CertificateType,
        market_price: Optional[Decimal],
    ) -> Tuple[Optional[Decimal], str]:
        """
        Calculate order price based on rule's price mode.

        Returns: (price, reason) where reason explains the calculation or failure.
        """
        if rule.order_type == "MARKET":
            # Market orders don't need a price
            return None, "market_order"

        if rule.price_mode == AutoTradePriceMode.FIXED:
            if rule.fixed_price:
                return rule.fixed_price, "fixed_price"
            return None, "fixed_price_not_set"

        elif rule.price_mode == AutoTradePriceMode.SPREAD_FROM_BEST:
            best_bid, best_ask = await AutoTradeExecutor.get_best_prices(
                db, certificate_type
            )

            spread = rule.spread_from_best or Decimal("0")

            if rule.side == OrderSide.BUY:
                # For BUY: place below best ask (or below best bid if no asks)
                if best_ask:
                    price = best_ask - spread
                elif best_bid:
                    price = best_bid - spread
                elif market_price:
                    price = market_price - spread
                else:
                    return None, "no_reference_price"
            else:
                # For SELL: place above best bid (or above best ask if no bids)
                if best_bid:
                    price = best_bid + spread
                elif best_ask:
                    price = best_ask + spread
                elif market_price:
                    price = market_price + spread
                else:
                    return None, "no_reference_price"

            # Round to 0.1 EUR step
            price = (price / Decimal("0.1")).quantize(Decimal("1")) * Decimal("0.1")
            return max(price, Decimal("0.10")), "spread_from_best"

        elif rule.price_mode == AutoTradePriceMode.PERCENTAGE_FROM_MARKET:
            if not market_price:
                return None, "market_price_unavailable"

            pct = rule.percentage_from_market or Decimal("0")

            if rule.side == OrderSide.BUY:
                # BUY: below market price
                price = market_price * (Decimal("1") - pct / Decimal("100"))
            else:
                # SELL: above market price
                price = market_price * (Decimal("1") + pct / Decimal("100"))

            # Round to 0.1 EUR step
            price = (price / Decimal("0.1")).quantize(Decimal("1")) * Decimal("0.1")
            return max(price, Decimal("0.10")), "percentage_from_market"

        elif rule.price_mode == AutoTradePriceMode.RANDOM_SPREAD:
            # Random spread between min and max, respecting 0.1 EUR step
            best_bid, best_ask = await AutoTradeExecutor.get_best_prices(
                db, certificate_type
            )

            spread_min = rule.spread_min or Decimal("0.1")
            spread_max = rule.spread_max or Decimal("1.0")

            # Ensure min <= max
            if spread_min > spread_max:
                spread_min, spread_max = spread_max, spread_min

            # Calculate number of 0.1 EUR steps in the range
            steps_min = int(spread_min / Decimal("0.1"))
            steps_max = int(spread_max / Decimal("0.1"))

            # Pick a random step count
            random_steps = random.randint(steps_min, steps_max)
            spread = Decimal(str(random_steps)) * Decimal("0.1")

            if rule.side == OrderSide.BUY:
                # For BUY: place below best ask (or use best bid/market price as reference)
                if best_ask:
                    price = best_ask - spread
                elif best_bid:
                    # If no asks, place slightly below best bid
                    price = best_bid - spread
                elif market_price:
                    price = market_price - spread
                else:
                    return None, "no_reference_price"
            else:
                # For SELL: place above best bid (or use best ask/market price as reference)
                if best_bid:
                    price = best_bid + spread
                elif best_ask:
                    # If no bids, place slightly above best ask
                    price = best_ask + spread
                elif market_price:
                    price = market_price + spread
                else:
                    return None, "no_reference_price"

            # Round to 0.1 EUR step (should already be, but ensure)
            price = (price / Decimal("0.1")).quantize(Decimal("1")) * Decimal("0.1")
            return max(price, Decimal("0.10")), f"random_spread ({spread} EUR)"

        return None, "unknown_price_mode"

    @staticmethod
    async def calculate_order_quantity(
        db: AsyncSession,
        rule: AutoTradeRule,
        balances: Dict[str, Dict[str, Decimal]],
        certificate_type: CertificateType,
        price: Optional[Decimal],
    ) -> Tuple[Optional[Decimal], str]:
        """
        Calculate order quantity based on rule's quantity mode.

        Returns: (quantity, reason) where reason explains the calculation or failure.
        """
        if rule.quantity_mode == AutoTradeQuantityMode.FIXED:
            if rule.fixed_quantity:
                return rule.fixed_quantity, "fixed_quantity"
            return None, "fixed_quantity_not_set"

        elif rule.quantity_mode == AutoTradeQuantityMode.PERCENTAGE_OF_BALANCE:
            pct = rule.percentage_of_balance or Decimal("0")

            if rule.side == OrderSide.BUY:
                # For BUY: percentage of available EUR
                available_eur = balances.get("EUR", {}).get("available", Decimal("0"))
                if price and price > 0:
                    max_qty = available_eur / price
                    qty = max_qty * pct / Decimal("100")
                else:
                    return None, "cannot_calculate_without_price"
            else:
                # For SELL: percentage of available certificates
                available_certs = balances.get(certificate_type.value, {}).get("available", Decimal("0"))
                qty = available_certs * pct / Decimal("100")

            if qty <= 0:
                return None, "insufficient_balance_for_percentage"

            # Round to integer - no fractional certificates
            return qty.quantize(Decimal("1"), rounding=ROUND_DOWN), "percentage_of_balance"

        elif rule.quantity_mode == AutoTradeQuantityMode.RANDOM_RANGE:
            min_qty = rule.min_quantity or Decimal("1")
            max_qty = rule.max_quantity or Decimal("100")

            # Generate random quantity
            range_size = max_qty - min_qty
            random_offset = Decimal(str(random.random())) * range_size
            qty = min_qty + random_offset

            # Round to integer - no fractional certificates
            return qty.quantize(Decimal("1"), rounding=ROUND_DOWN), "random_range"

        return None, "unknown_quantity_mode"

    @staticmethod
    async def validate_order(
        db: AsyncSession,
        rule: AutoTradeRule,
        market_maker: MarketMakerClient,
        price: Optional[Decimal],
        quantity: Decimal,
        market_price: Optional[Decimal],
        balances: Dict[str, Dict[str, Decimal]],
        certificate_type: CertificateType,
        best_bid: Optional[Decimal] = None,
        best_ask: Optional[Decimal] = None,
        price_reason: str = "",
    ) -> Tuple[bool, str]:
        """
        Validate that an order can be placed.

        Checks:
        1. Max active orders limit
        2. Min balance requirement
        3. Sufficient balance for the order
        4. Price deviation — checked against scraped price OR market mid-price.
           If the market has moved significantly (e.g. after a large buy), the
           scraped price can lag behind. Accepting the order when it is within
           deviation% of the current mid-price prevents autotrade from freezing
           until the scraper catches up.

        Returns: (is_valid, reason)
        """
        # Check max active orders
        if rule.max_active_orders:
            active_count = await AutoTradeExecutor.count_active_orders(
                db, market_maker.id
            )
            if active_count >= rule.max_active_orders:
                return False, f"max_active_orders_reached ({active_count}/{rule.max_active_orders})"

        # Market makers have unlimited resources — skip balance checks

        # Alignment orders are intentionally placed toward the scraped price, potentially crossing
        # the spread to consume stale volume. Bypassing deviation check for them is correct —
        # they ARE moving toward the real price, not away from it.
        if price_reason == "priority2_price_alignment":
            return True, "ok_alignment"

        # Check price deviation.
        # Primary reference: scraped market price.
        # Fallback: current order-book mid-price (avoids freeze when scraper lags after large moves).
        if rule.max_price_deviation and price:
            if market_price:
                scraped_dev = abs(price - market_price) / market_price * Decimal("100")
                if scraped_dev <= rule.max_price_deviation:
                    return True, "ok"
                # Scraped price check failed — try mid-price fallback
                if best_bid and best_ask and best_bid > 0 and best_ask > 0:
                    mid_price = (best_bid + best_ask) / Decimal("2")
                    mid_dev = abs(price - mid_price) / mid_price * Decimal("100")
                    if mid_dev <= rule.max_price_deviation:
                        logger.info(
                            f"validate_order: scraped deviation {scraped_dev:.1f}% > limit, "
                            f"but mid-price deviation {mid_dev:.1f}% OK — allowing order"
                        )
                        return True, "ok"
                return False, f"price_deviation_exceeded ({scraped_dev:.2f}% vs scraped, mid fallback unavailable or also exceeded)"

        return True, "ok"

    @staticmethod
    async def place_order(
        db: AsyncSession,
        rule: AutoTradeRule,
        market_maker: MarketMakerClient,
        certificate_type: CertificateType,
        market_type: MarketType,
        price: Optional[Decimal],
        quantity: Decimal,
        admin_user_id: uuid.UUID,
        interval_variation_pct: Optional[Decimal] = None,
        override_interval_factor: Optional[float] = None,
    ) -> Tuple[Optional[Order], str]:
        """
        Place an order for the market maker.

        For SELL orders: locks certificates via TRADE_DEBIT transaction.
        For BUY orders: locks EUR (handled by order matching).

        Returns: (Order, ticket_id) or (None, error_reason)
        """
        try:
            # For SELL orders: lock certificates
            if rule.side == OrderSide.SELL:
                transaction, ticket_id = await MarketMakerService.create_transaction(
                    db=db,
                    market_maker_id=market_maker.id,
                    certificate_type=certificate_type,
                    transaction_type=TransactionType.TRADE_DEBIT,
                    amount=-quantity,  # Negative to lock
                    notes=f"Auto-trade rule '{rule.name}' - lock for sell order",
                    created_by_id=admin_user_id,
                )
            else:
                ticket_id = None

            # Create the order
            order = Order(
                market=market_type,
                market_maker_id=market_maker.id,
                certificate_type=certificate_type,
                side=rule.side,
                price=price or Decimal("0"),  # Market orders may not have price
                quantity=quantity,
                filled_quantity=Decimal("0"),
                status=OrderStatus.OPEN,
            )
            db.add(order)
            await db.flush()

            # Create audit ticket for the order
            order_ticket = await TicketService.create_ticket(
                db=db,
                action_type="AUTO_TRADE_ORDER_PLACED",
                entity_type="Order",
                entity_id=order.id,
                status=TicketStatus.SUCCESS,
                user_id=admin_user_id,
                market_maker_id=market_maker.id,
                request_payload={
                    "rule_id": str(rule.id),
                    "rule_name": rule.name,
                    "side": rule.side.value,
                    "order_type": rule.order_type,
                    "price_mode": rule.price_mode.value if rule.price_mode else None,
                    "quantity_mode": rule.quantity_mode.value if rule.quantity_mode else None,
                },
                response_data={
                    "order_id": str(order.id),
                    "price": str(price) if price else None,
                    "quantity": str(quantity),
                    "certificate_type": certificate_type.value,
                },
                related_ticket_ids=[ticket_id] if ticket_id else [],
                tags=["auto_trade", "order", rule.side.value.lower()],
            )

            # Update order with ticket ID
            order.ticket_id = order_ticket.ticket_id

            # Update rule execution tracking (naive UTC for asyncpg)
            rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(
                rule,
                interval_variation_pct=interval_variation_pct,
                override_interval_factor=override_interval_factor,
            )
            rule.execution_count = (rule.execution_count or 0) + 1

            await db.commit()
            await db.refresh(order)

            logger.info(
                f"Auto-trade order placed: {order.id} for MM {market_maker.name} "
                f"({rule.side.value} {quantity} {certificate_type.value} @ {price})"
            )

            return order, order_ticket.ticket_id

        except Exception as e:
            logger.error(f"Failed to place auto-trade order: {e}")
            await db.rollback()
            return None, str(e)

    @staticmethod
    async def try_match_orders(
        db: AsyncSession,
        certificate_type: CertificateType,
        admin_user_id: uuid.UUID,
    ) -> int:
        """
        Try to match crossing limit orders between market makers.

        Looks for BUY orders with price >= lowest SELL order price
        and creates trades between them.

        Returns: number of trades created
        """
        trades_created = 0

        # Get crossing orders: buy orders that can match with sell orders
        # BUY orders sorted by price DESC (highest first)
        buy_result = await db.execute(
            select(Order)
            .where(
                and_(
                    Order.certificate_type == certificate_type,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),  # Only MM orders
                )
            )
            .order_by(Order.price.desc(), Order.created_at.asc())
        )
        buy_orders = list(buy_result.scalars().all())

        # SELL orders sorted by price ASC (lowest first)
        sell_result = await db.execute(
            select(Order)
            .where(
                and_(
                    Order.certificate_type == certificate_type,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.market_maker_id.isnot(None),  # Only MM orders
                )
            )
            .order_by(Order.price.asc(), Order.created_at.asc())
        )
        sell_orders = list(sell_result.scalars().all())

        if not buy_orders or not sell_orders:
            return 0

        # Try to match
        for buy_order in buy_orders:
            buy_remaining = buy_order.quantity - buy_order.filled_quantity
            if buy_remaining <= 0:
                continue

            for sell_order in sell_orders:
                # Check if orders can match (buy price >= sell price)
                if buy_order.price < sell_order.price:
                    # No more matches possible for this buy order
                    break

                # Don't match orders from the same market maker
                if buy_order.market_maker_id == sell_order.market_maker_id:
                    continue

                sell_remaining = sell_order.quantity - sell_order.filled_quantity
                if sell_remaining <= 0:
                    continue

                # Calculate match quantity (must be integer)
                match_qty = min(buy_remaining, sell_remaining)
                # Round to integer - no fractional certificates
                match_qty = match_qty.quantize(Decimal("1"), rounding=ROUND_DOWN)
                if match_qty <= 0:
                    continue

                # Trade executes at the MAKER's price (price-time priority).
                # The maker is whoever placed their order first (earlier created_at).
                # When an alignment SELL at €10.70 crosses a resting BUY at €11.50,
                # the BUY is the maker → trade executes at €11.50 (correct).
                buy_created = getattr(buy_order, 'created_at', None)
                sell_created = getattr(sell_order, 'created_at', None)
                if buy_created and sell_created and buy_created <= sell_created:
                    # Buy order was in book first — use buy (maker) price
                    trade_price = buy_order.price if buy_order.price and buy_order.price > 0 else sell_order.price
                else:
                    # Sell order was in book first — use sell (maker) price
                    trade_price = sell_order.price if sell_order.price and sell_order.price > 0 else buy_order.price
                # Round to 0.1 EUR step
                trade_price = (trade_price / Decimal("0.1")).quantize(Decimal("1")) * Decimal("0.1")

                # Create trade
                trade = CashMarketTrade(
                    buy_order_id=buy_order.id,
                    sell_order_id=sell_order.id,
                    market_maker_id=buy_order.market_maker_id,  # Buyer's MM
                    certificate_type=certificate_type,
                    price=trade_price,
                    quantity=match_qty,
                    executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                db.add(trade)
                await db.flush()

                # Persist trade price in price_history for chart data
                db.add(PriceHistory(
                    certificate_type=certificate_type,
                    price=trade_price,
                    currency="EUR",
                    source="auto_trade",
                    recorded_at=trade.executed_at,
                ))

                # Create audit ticket for trade execution
                buy_ticket_id = getattr(buy_order, 'ticket_id', None)
                sell_ticket_id = getattr(sell_order, 'ticket_id', None)
                related = [tid for tid in [buy_ticket_id, sell_ticket_id] if tid]

                trade_ticket = await TicketService.create_ticket(
                    db=db,
                    action_type="TRADE_EXECUTED",
                    entity_type="Trade",
                    entity_id=trade.id,
                    status=TicketStatus.SUCCESS,
                    user_id=admin_user_id,
                    market_maker_id=buy_order.market_maker_id,
                    request_payload={
                        "match_type": "auto_trade",
                        "aggressor_side": "BUY",
                        "buy_order_id": str(buy_order.id),
                        "sell_order_id": str(sell_order.id),
                    },
                    response_data={
                        "trade_id": str(trade.id),
                        "buy_order_id": str(buy_order.id),
                        "sell_order_id": str(sell_order.id),
                        "buyer_mm_id": str(buy_order.market_maker_id) if buy_order.market_maker_id else None,
                        "seller_mm_id": str(sell_order.market_maker_id) if sell_order.market_maker_id else None,
                        "certificate_type": certificate_type.value,
                        "price": str(trade_price),
                        "quantity": str(match_qty),
                    },
                    related_ticket_ids=related,
                    tags=["trade", "auto_trade", certificate_type.value.lower()],
                )
                trade.ticket_id = trade_ticket.ticket_id

                # Update buy order
                buy_order.filled_quantity = buy_order.filled_quantity + match_qty
                if buy_order.filled_quantity >= buy_order.quantity:
                    buy_order.status = OrderStatus.FILLED
                else:
                    buy_order.status = OrderStatus.PARTIALLY_FILLED
                buy_order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                # Update sell order
                sell_order.filled_quantity = sell_order.filled_quantity + match_qty
                if sell_order.filled_quantity >= sell_order.quantity:
                    sell_order.status = OrderStatus.FILLED
                else:
                    sell_order.status = OrderStatus.PARTIALLY_FILLED
                sell_order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

                trades_created += 1
                buy_remaining -= match_qty

                logger.info(
                    f"Auto-trade match: {match_qty} {certificate_type.value} @ {trade_price} "
                    f"(BUY order {buy_order.id} <-> SELL order {sell_order.id})"
                )

                if buy_remaining <= 0:
                    break

        if trades_created > 0:
            await db.commit()
            logger.info(f"Created {trades_created} auto-trade matches for {certificate_type.value}")

            # Broadcast orderbook_updated so activity feed refreshes
            try:
                from app.api.v1.client_ws import client_ws_manager
                asyncio.create_task(client_ws_manager.broadcast_to_all(
                    {"type": "orderbook_updated", "data": {"certificate_type": certificate_type.value}},
                ))
            except Exception:
                pass

        return trades_created

    @staticmethod
    async def execute_rule(
        db: AsyncSession,
        rule: AutoTradeRule,
        admin_user_id: uuid.UUID,
    ) -> Dict:
        """
        Execute a single auto-trade rule with target-based liquidity management.

        Behavior based on liquidity status:
        - below_target: Place new orders to refill liquidity
        - at_target: Skip execution (maintain current level), unless spread > target
        - above_target: Execute internal trades to consume excess, unless spread > target
        - no_target: Place orders normally (no liquidity management)

        Priority 0 (spread narrowing) overrides at_target and above_target: if spread > avg_spread,
        the executor places a spread-narrowing order even when liquidity is at or above target.

        Returns a dict with execution result details.
        """
        result = {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "market_maker_id": str(rule.market_maker_id),
            "success": False,
            "order_id": None,
            "reason": None,
        }

        try:
            market_maker = rule.market_maker
            if not market_maker or not market_maker.is_active:
                result["reason"] = "market_maker_inactive"
                return result

            # Determine certificate and market types
            certificate_type = AutoTradeExecutor.determine_certificate_type(market_maker)
            market_type = AutoTradeExecutor.determine_market_type(market_maker)
            market_key = AutoTradeExecutor.determine_market_key(market_maker)

            # Check liquidity status using new v2 method (AutoTradeMarketSettings)
            status, current_liq, target_liq, market_settings = await AutoTradeExecutor.get_liquidity_status_v2(
                db, market_key, certificate_type, rule.side, market_type
            )

            result["liquidity_status"] = {
                "status": status,
                "current": str(current_liq) if current_liq else None,
                "target": str(target_liq) if target_liq else None,
                "market_key": market_key,
            }

            # Extract interval variation for scheduling (used throughout execute_rule)
            _interval_var = market_settings.order_interval_variation_pct if market_settings else None

            # Include market settings params in result for debugging
            if market_settings:
                result["market_settings"] = {
                    "price_deviation_pct": str(market_settings.price_deviation_pct),
                    "avg_order_count": market_settings.avg_order_count,
                    "min_order_volume_eur": str(market_settings.min_order_volume_eur),
                    "volume_variety": market_settings.volume_variety,
                }

            # Handle based on liquidity status
            if status == "exceeds_max_threshold":
                # URGENT: Liquidity exceeds max threshold - aggressively reduce via internal trades
                max_threshold = market_settings.max_liquidity_threshold if market_settings else None
                logger.warning(
                    f"Rule {rule.name}: Liquidity EXCEEDS MAX THRESHOLD ({current_liq}/{max_threshold} EUR) - "
                    f"executing internal trades to reduce"
                )

                # Execute multiple internal trades to bring liquidity below threshold
                trades_executed = 0
                max_trades = 5  # Limit to avoid infinite loops

                while trades_executed < max_trades:
                    internal_result = await AutoTradeExecutor.execute_internal_trade(
                        db, certificate_type, admin_user_id,
                        market_settings=market_settings,
                        market_key=market_key,
                    )

                    if not internal_result["success"]:
                        break

                    trades_executed += 1
                    logger.info(
                        f"Rule {rule.name} threshold reduction trade #{trades_executed}: "
                        f"{internal_result['quantity']} @ {internal_result['price']}"
                    )

                    # Re-check liquidity
                    new_current = await AutoTradeExecutor.calculate_current_liquidity(
                        db, certificate_type, rule.side, market_type
                    )
                    if new_current and max_threshold and new_current <= max_threshold:
                        logger.info(f"Rule {rule.name}: Liquidity now {new_current} EUR, below threshold")
                        break

                # Update rule execution tracking
                rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(rule, _interval_var)
                rule.execution_count = (rule.execution_count or 0) + 1
                await db.commit()

                result["success"] = trades_executed > 0
                result["action"] = "threshold_reduction"
                result["trades_executed"] = trades_executed
                result["reason"] = f"executed {trades_executed} internal trades to reduce excess liquidity"
                return result

            if status == "at_target":
                # Priority 0: spread narrowing can exceed liquidity level — check first
                best_bid, best_ask = await AutoTradeExecutor.get_best_prices(db, certificate_type)
                target_spread = (
                    Decimal(str(market_settings.avg_spread))
                    if market_settings and market_settings.avg_spread is not None
                    else (Decimal("0.0050") if market_type == MarketType.SWAP else Decimal("0.1"))
                )
                spread_needs_narrowing = (
                    best_bid is not None
                    and best_ask is not None
                    and (best_ask - best_bid) > target_spread
                )
                if spread_needs_narrowing:
                    # Fall through to order placement — priority 0 overrides at_target
                    status = "below_target"  # treat as place-order path
                    result["action"] = "place_order_spread_priority"
                    logger.info(
                        f"Rule {rule.name}: At target but spread > {target_spread} — "
                        "placing spread-narrowing order (priority 0 exceeds liquidity level)"
                    )
                else:
                    # Priority 2: price alignment override — if book price deviates from scraped
                    # price by more than threshold, place an alignment order even when at target.
                    # This is the primary mechanism for converging the platform price toward
                    # the real market price. Only applies to cash markets (not SWAP).
                    if market_type != MarketType.SWAP:
                        _at_scraped = await AutoTradeExecutor.get_market_price(certificate_type.value)
                        _at_best_price = best_ask if rule.side == OrderSide.SELL else best_bid
                        _at_tick = max(
                            Decimal(str(market_settings.tick_size)) if market_settings and market_settings.tick_size else Decimal("0.1"),
                            Decimal("0.0001"),
                        )
                        if _at_scraped and _at_best_price:
                            _at_align_price = AutoTradeExecutor.calculate_alignment_price(
                                _at_scraped, _at_best_price, rule.side, _at_tick,
                                threshold=_at_tick * (market_settings.alignment_threshold_ticks if market_settings and market_settings.alignment_threshold_ticks else 2),
                                market_settings=market_settings,
                            )
                            if _at_align_price is not None:
                                status = "below_target"  # fall through to order placement
                                result["action"] = "place_order_alignment_priority"
                                logger.info(
                                    f"Rule {rule.name}: At target but price misaligned "
                                    f"({_at_best_price} vs scraped {_at_scraped}) — "
                                    "placing alignment order (priority 2 overrides at_target)"
                                )

                if status == "at_target":
                    # Spread OK, price aligned — try periodic internal trade if interval allows
                    if (
                        market_settings
                        and market_settings.internal_trade_interval
                        and market_settings.internal_trade_volume_min is not None
                    ):
                        internal_result = await AutoTradeExecutor.execute_internal_trade(
                            db, certificate_type, admin_user_id,
                            market_settings=market_settings,
                            market_key=market_key,
                        )
                        if internal_result["success"]:
                            logger.info(
                                f"Rule {rule.name}: At-target periodic internal trade: "
                                f"{internal_result['quantity']} @ {internal_result['price']}"
                            )
                            result["success"] = True
                            result["action"] = "internal_trade_periodic"
                            result["internal_trade"] = internal_result
                        else:
                            result["reason"] = f"at_target_internal_skipped: {internal_result['reason']}"
                            result["action"] = "skipped"
                    else:
                        result["reason"] = "liquidity_at_target"
                        result["action"] = "skipped"

                    rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(rule, _interval_var)
                    rule.execution_count = (rule.execution_count or 0) + 1
                    await db.commit()
                    return result

            if status == "above_target":
                # Priority 0: spread narrowing can exceed liquidity — if spread > target, place order instead
                best_bid_at, best_ask_at = await AutoTradeExecutor.get_best_prices(db, certificate_type)
                target_spread_at = (
                    Decimal(str(market_settings.avg_spread))
                    if market_settings and market_settings.avg_spread is not None
                    else (Decimal("0.0050") if market_type == MarketType.SWAP else Decimal("0.1"))
                )
                spread_needs_narrowing_at = (
                    best_bid_at is not None
                    and best_ask_at is not None
                    and (best_ask_at - best_bid_at) > target_spread_at
                )
                if spread_needs_narrowing_at:
                    status = "below_target"
                    result["action"] = "place_order_spread_priority"
                    logger.info(
                        f"Rule {rule.name}: Above target but spread > {target_spread_at} — "
                        "placing spread-narrowing order (priority 0 exceeds liquidity level)"
                    )
                else:
                    # Priority 2: price alignment — place alignment order even when above target
                    if market_type != MarketType.SWAP:
                        _ab_scraped = await AutoTradeExecutor.get_market_price(certificate_type.value)
                        _ab_best_price = best_ask_at if rule.side == OrderSide.SELL else best_bid_at
                        _ab_tick = max(
                            Decimal(str(market_settings.tick_size)) if market_settings and market_settings.tick_size else Decimal("0.1"),
                            Decimal("0.0001"),
                        )
                        if _ab_scraped and _ab_best_price:
                            _ab_align_price = AutoTradeExecutor.calculate_alignment_price(
                                _ab_scraped, _ab_best_price, rule.side, _ab_tick,
                                threshold=_ab_tick * (market_settings.alignment_threshold_ticks if market_settings and market_settings.alignment_threshold_ticks else 2),
                                market_settings=market_settings,
                            )
                            if _ab_align_price is not None:
                                status = "below_target"  # fall through to order placement
                                result["action"] = "place_order_alignment_priority"
                                logger.info(
                                    f"Rule {rule.name}: Above target but price misaligned "
                                    f"({_ab_best_price} vs scraped {_ab_scraped}) — "
                                    "placing alignment order (priority 2 overrides above_target)"
                                )

                if status == "above_target":
                    # Spread OK, price aligned — consume excess via internal trade
                    logger.info(
                        f"Rule {rule.name}: Liquidity above target ({current_liq}/{target_liq} EUR) - "
                        f"executing internal trade to consume excess"
                    )

                    internal_result = await AutoTradeExecutor.execute_internal_trade(
                        db, certificate_type, admin_user_id,
                        market_settings=market_settings,
                        market_key=market_key,
                    )

                    rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(rule, _interval_var)
                    rule.execution_count = (rule.execution_count or 0) + 1
                    await db.commit()

                    result["success"] = internal_result["success"]
                    result["action"] = "internal_trade"
                    result["internal_trade"] = internal_result

                    if internal_result["success"]:
                        logger.info(
                            f"Rule {rule.name} executed internal trade: "
                            f"{internal_result['quantity']} @ {internal_result['price']}"
                        )
                    else:
                        result["reason"] = f"internal_trade_failed: {internal_result['reason']}"
                        logger.warning(f"Rule {rule.name} internal trade failed: {internal_result['reason']}")

                    return result

            # status == "below_target" or "no_target" - place new orders
            if status == "below_target":
                logger.info(
                    f"Rule {rule.name}: Liquidity below target ({current_liq}/{target_liq} EUR) - "
                    f"placing order to refill"
                )
                result["action"] = "place_order_refill"
            else:
                result["action"] = "place_order_normal"

            # Get market price (or swap ratio for SWAP market)
            # IMPORTANT: For SWAP market, Order.price is the ratio CEA/EUA, NOT EUR price!
            if market_type == MarketType.SWAP:
                # For swap market, use the CEA/EUA ratio as the "market price"
                market_price = await AutoTradeExecutor.get_swap_ratio()
                logger.info(f"Swap market: using ratio {market_price} as reference price")
            else:
                market_price = await AutoTradeExecutor.get_market_price(certificate_type.value)

            # MMs have unlimited resources — skip balance fetch
            balances: Dict[str, Dict[str, Decimal]] = {}

            # Get best prices for price calculation
            best_bid, best_ask = await AutoTradeExecutor.get_best_prices(db, certificate_type)

            # Detect spread-priority large-spread: use smaller volume to look natural
            target_spread_placement = (
                Decimal(str(market_settings.avg_spread))
                if market_settings and market_settings.avg_spread is not None
                else (Decimal("0.0050") if market_type == MarketType.SWAP else Decimal("0.1"))
            )
            current_spread = (best_ask - best_bid) if (best_bid and best_ask) else Decimal("0")
            spread_priority_large_spread = (
                result["action"] == "place_order_spread_priority"
                and current_spread > target_spread_placement * Decimal("2")
            )

            # --- 5-PRIORITY ORDER PLACEMENT CHAIN ---
            # Try priorities 0-3 before falling back to normal (priority 4)
            priority_price, priority_reason = await AutoTradeExecutor.determine_priority_price(
                db, certificate_type, rule.side, market_settings,
                scraped_price=market_price,
                best_bid=best_bid, best_ask=best_ask,
                is_swap=(market_type == MarketType.SWAP),
            )

            if priority_price is not None:
                # Priorities 0-3 provided a price — use it directly
                price = priority_price
                price_reason = priority_reason
                logger.info(f"Rule {rule.name}: {priority_reason} → price={price}")
            # Priority 4: normal price calculation (existing logic)
            elif market_settings and best_bid and rule.order_type == "LIMIT":
                # Use new price deviation setting
                # For BUY: use best_ask as reference (we want to buy below it)
                # For SELL: use best_bid as reference (we want to sell above it)
                if rule.side == OrderSide.BUY:
                    reference_price = best_ask if best_ask else (best_bid if best_bid else market_price)
                else:
                    reference_price = best_bid if best_bid else (best_ask if best_ask else market_price)

                if reference_price:
                    price = AutoTradeExecutor.calculate_price_with_deviation(
                        reference_price,
                        market_settings.price_deviation_pct,
                        rule.side,
                        is_swap_market=(market_type == MarketType.SWAP),
                        tick_size=market_settings.tick_size,
                    )
                    price_reason = f"market_settings_deviation ({market_settings.price_deviation_pct}%)"
                else:
                    # Fall back to rule-based calculation
                    price, price_reason = await AutoTradeExecutor.calculate_order_price(
                        db, rule, certificate_type, market_price
                    )
            else:
                # Use rule-based calculation
                price, price_reason = await AutoTradeExecutor.calculate_order_price(
                    db, rule, certificate_type, market_price
                )

            if price is None and rule.order_type == "LIMIT":
                result["reason"] = f"price_calculation_failed: {price_reason}"
                # Schedule next execution anyway
                rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(
                    rule,
                    interval_variation_pct=_interval_var,
                    override_interval_factor=None,
                )
                await db.commit()
                return result

            # Max orders per price level enforcement
            if market_settings and price and market_settings.max_orders_per_price_level:
                from sqlalchemy import and_ as sql_and, func as sql_func
                max_per_level = market_settings.max_orders_per_price_level
                # Apply variation to the max
                if market_settings.max_orders_per_level_variation_pct and market_settings.max_orders_per_level_variation_pct > 0:
                    pct = float(market_settings.max_orders_per_level_variation_pct)
                    factor = 1.0 + random.uniform(-pct / 100, pct / 100)
                    max_per_level = max(1, round(max_per_level * factor))

                # Count existing orders at this price level
                count_result = await db.execute(
                    select(sql_func.count()).select_from(Order).where(
                        sql_and(
                            Order.certificate_type == certificate_type,
                            Order.side == rule.side,
                            Order.price == price,
                            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                        )
                    )
                )
                orders_at_price = count_result.scalar() or 0

                # If at capacity, shift to next available price level
                if orders_at_price >= max_per_level:
                    # Use tick_size from market settings instead of hardcoded step
                    if market_settings and market_settings.tick_size:
                        step = Decimal(str(market_settings.tick_size))
                    else:
                        step = Decimal("0.1") if market_type != MarketType.SWAP else Decimal("0.0001")

                    # Dynamic range: cover full price_deviation_pct range
                    if market_settings and market_settings.price_deviation_pct and price and step > 0:
                        max_deviation = price * Decimal(str(market_settings.price_deviation_pct)) / Decimal("100")
                        max_shifts = max(20, int(max_deviation / step) + 1)
                    else:
                        max_shifts = 50

                    shifted = False
                    for shift in range(1, max_shifts):
                        if rule.side == OrderSide.BUY:
                            candidate = price - step * shift
                            if candidate <= Decimal("0"):
                                break
                        else:
                            candidate = price + step * shift

                        count_result = await db.execute(
                            select(sql_func.count()).select_from(Order).where(
                                sql_and(
                                    Order.certificate_type == certificate_type,
                                    Order.side == rule.side,
                                    Order.price == candidate,
                                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                                )
                            )
                        )
                        if (count_result.scalar() or 0) < max_per_level:
                            price = candidate
                            shifted = True
                            break

                    if not shifted:
                        # Fallback: execute internal trade to free capacity
                        if market_settings and market_settings.internal_trade_volume_min is not None:
                            logger.info(
                                f"Rule {rule.name}: All price levels at max capacity — "
                                f"executing internal trade to free capacity"
                            )
                            internal_result = await AutoTradeExecutor.execute_internal_trade(
                                db, certificate_type, admin_user_id,
                                market_settings=market_settings,
                                market_key=market_key,
                            )
                            rule.last_executed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                            rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(
                                rule,
                                interval_variation_pct=_interval_var,
                                override_interval_factor=None,
                            )
                            rule.execution_count = (rule.execution_count or 0) + 1
                            await db.commit()

                            if internal_result["success"]:
                                result["success"] = True
                                result["action"] = "internal_trade_capacity_relief"
                                result["internal_trade"] = internal_result
                                result["reason"] = "capacity_full_executed_internal_trade"
                                logger.info(
                                    f"Rule {rule.name}: Capacity relief trade: "
                                    f"{internal_result['quantity']} @ {internal_result['price']}"
                                )
                            else:
                                result["reason"] = f"all_price_levels_at_max_capacity_internal_failed: {internal_result['reason']}"
                            return result

                        result["reason"] = "all_price_levels_at_max_capacity"
                        rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(
                            rule,
                            interval_variation_pct=_interval_var,
                            override_interval_factor=None,
                        )
                        await db.commit()
                        return result

            # Calculate quantity - use market settings for volume variety if available
            if market_settings and price and price > 0:
                # Calculate volume in EUR with variety
                volume_eur = AutoTradeExecutor.calculate_order_volume_with_variety(
                    market_settings.min_order_volume_eur,
                    market_settings.volume_variety,
                    target_liq,
                    current_liq or Decimal("0"),
                    market_settings.avg_order_count,
                    variation_pct=market_settings.min_order_value_variation_pct,
                    max_volume_eur=market_settings.max_order_volume_eur,
                )
                # When spread >> target, use smaller volume to avoid exceeding target liquidity
                if spread_priority_large_spread:
                    volume_eur = (volume_eur * Decimal("0.4")).quantize(Decimal("0.01"))
                    volume_eur = max(volume_eur, market_settings.min_order_volume_eur or Decimal("1"))
                # Convert EUR volume to quantity (certificates)
                # IMPORTANT: For SWAP market, price is ratio (CEA/EUA), not EUR price!
                # We need to use the actual EUA EUR price to calculate quantity
                if market_type == MarketType.SWAP:
                    # For swap: quantity is in EUA, so divide by EUA EUR price
                    eua_eur_price = await AutoTradeExecutor.get_market_price("EUA")
                    if eua_eur_price and eua_eur_price > 0:
                        quantity = (volume_eur / eua_eur_price).quantize(Decimal("1"), rounding=ROUND_DOWN)
                        qty_reason = f"swap_volume (vol={volume_eur:.0f} EUR / {eua_eur_price} EUR/EUA = {quantity} EUA)"
                    else:
                        quantity = Decimal("0")
                        qty_reason = "eua_price_unavailable"
                else:
                    quantity = (volume_eur / price).quantize(Decimal("1"), rounding=ROUND_DOWN)
                    qty_reason = f"market_settings_variety (vol={volume_eur:.0f} EUR, variety={market_settings.volume_variety})"
            else:
                # Use rule-based calculation
                quantity, qty_reason = await AutoTradeExecutor.calculate_order_quantity(
                    db, rule, balances, certificate_type, price
                )

            if quantity is None or quantity <= 0:
                result["reason"] = f"quantity_calculation_failed: {qty_reason}"
                rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(
                    rule,
                    interval_variation_pct=_interval_var,
                    override_interval_factor=None,
                )
                await db.commit()
                return result

            # Validate order
            is_valid, validation_reason = await AutoTradeExecutor.validate_order(
                db, rule, market_maker, price, quantity, market_price,
                balances, certificate_type,
                best_bid=best_bid, best_ask=best_ask,
                price_reason=price_reason,
            )

            if not is_valid:
                result["reason"] = f"validation_failed: {validation_reason}"
                rule.next_execution_at = AutoTradeExecutor.calculate_next_execution_time(
                    rule,
                    interval_variation_pct=_interval_var,
                    override_interval_factor=None,
                )
                await db.commit()
                return result

            # Place the order
            order, ticket_id = await AutoTradeExecutor.place_order(
                db, rule, market_maker, certificate_type, market_type,
                price, quantity, admin_user_id,
                interval_variation_pct=_interval_var,
                override_interval_factor=None,
            )

            if order:
                result["success"] = True
                result["order_id"] = str(order.id)
                result["ticket_id"] = ticket_id
                result["price"] = str(price) if price else None
                result["quantity"] = str(quantity)
                result["price_reason"] = price_reason

                # Try to match crossing orders after placement
                trades_matched = await AutoTradeExecutor.try_match_orders(
                    db, certificate_type, admin_user_id
                )
                result["trades_matched"] = trades_matched
            else:
                result["reason"] = f"order_placement_failed: {ticket_id}"

            return result

        except Exception as e:
            logger.exception(f"Error executing rule {rule.id}: {e}")
            result["reason"] = f"exception: {str(e)}"
            return result

    @staticmethod
    async def execute_all_ready_rules(
        db: AsyncSession,
        admin_user_id: uuid.UUID,
    ) -> List[Dict]:
        """
        Execute all rules that are ready for execution.

        This is the main entry point for the background scheduler.
        Returns list of execution results.
        """
        results = []

        try:
            rules = await AutoTradeExecutor.get_rules_ready_for_execution(db)
            logger.info(f"Found {len(rules)} rules ready for execution")

            for rule in rules:
                result = await AutoTradeExecutor.execute_rule(db, rule, admin_user_id)
                results.append(result)

                if result["success"]:
                    logger.info(f"Rule {rule.name} executed successfully: order {result['order_id']}")
                else:
                    logger.warning(f"Rule {rule.name} execution failed: {result['reason']}")

            return results

        except Exception as e:
            logger.exception(f"Error in execute_all_ready_rules: {e}")
            return results


# Background task for running auto-trade execution
_executor_task: Optional[asyncio.Task] = None
_executor_running = False

# Module-level internal trade interval tracking (per market_key)
_last_internal_trade_at: Dict[str, datetime] = {}

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
