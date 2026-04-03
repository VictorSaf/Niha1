import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import (
    admin,
    admin_fees,
    admin_logging,
    ai_agent,
    assets,
    auth,
    backoffice,
    cash_market,
    client_ws,
    contact,
    deposits,
    documents,
    exchange_rates,
    introducer,
    market_maker,
    market_news,
    marketplace,
    onboarding,
    prices,
    settlement,
    swaps,
    system_health,
    users,
    withdrawals,
)
from .core.config import settings
from .core.database import AsyncSessionLocal, init_db
from .core.security import RedisManager
from .services import deposit_service
from .services.auto_trade_executor import AutoTradeExecutor, update_executor_status
from .services.settlement_monitoring import SettlementMonitoring
from .services.news_scraper import news_scraper
from .services.settlement_processor import SettlementProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global task reference
_background_tasks = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Nihao Carbon Trading Platform API...")
    await init_db()
    logger.info("Database initialized")

    from .services.processor_registry import register_processor, report_run

    # Register background processors
    register_processor("settlement_processor", 3600)
    register_processor("settlement_monitoring", 3600)
    register_processor("price_scraper", 60)
    register_processor("exchange_rate_scraper", 60)
    register_processor("auto_trade_executor", 5)
    register_processor("deposit_hold_processor", 3600)

    # Start settlement processor background task
    async def settlement_processor_loop():
        """Run settlement processor every hour"""
        while True:
            try:
                await SettlementProcessor.process_pending_settlements()
                await SettlementProcessor.check_overdue_settlements()
                report_run("settlement_processor")
            except Exception as e:
                logger.error(f"Settlement processor error: {e}", exc_info=True)
                report_run("settlement_processor", success=False, error=str(e))

            # Wait 1 hour
            await asyncio.sleep(3600)

    # Start settlement monitoring background task
    async def settlement_monitoring_loop():
        """Run settlement monitoring every hour"""
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    result = await SettlementMonitoring.run_monitoring_cycle(db)
                    if result.get("success"):
                        logger.info(
                            f"Settlement monitoring cycle completed: "
                            f"{result.get('alert_count', 0)} alerts detected"
                        )
                        # Broadcast health update to backoffice admins
                        from .api.v1.backoffice import backoffice_ws_manager as _bo_ws
                        from .services.processor_registry import get_all_statuses as _get_statuses

                        asyncio.create_task(
                            _bo_ws.broadcast(
                                "system_health_update",
                                {
                                    "alert_count": result.get("alert_count", 0),
                                    "critical_alerts": result.get("critical_alerts", 0),
                                    "processors": _get_statuses(),
                                },
                            )
                        )
                    else:
                        logger.error(
                            f"Settlement monitoring cycle failed: {result.get('error')}"
                        )
                report_run("settlement_monitoring")
            except Exception as e:
                logger.error(f"Settlement monitoring error: {e}", exc_info=True)
                report_run("settlement_monitoring", success=False, error=str(e))

            # Wait 1 hour
            await asyncio.sleep(3600)

    # Deposit hold expiration processor
    async def deposit_hold_processor_loop():
        """Process expired deposit holds every hour"""
        # Get system admin ID for audit trail (first admin user)
        from sqlalchemy import select

        from .models.models import User, UserRole

        while True:
            try:
                async with AsyncSessionLocal() as db:
                    # Get a system admin for audit trail
                    result = await db.execute(
                        select(User).where(User.role == UserRole.ADMIN).limit(1)
                    )
                    admin = result.scalar_one_or_none()

                    if admin:
                        cleared = await deposit_service.process_expired_holds(
                            db=db, system_admin_id=admin.id
                        )
                        await db.commit()
                        if cleared > 0:
                            logger.info(
                                f"Auto-cleared {cleared} deposit(s) with expired holds"
                            )
                report_run("deposit_hold_processor")
            except Exception as e:
                logger.error(f"Deposit hold processor error: {e}", exc_info=True)
                report_run("deposit_hold_processor", success=False, error=str(e))

            # Wait 1 hour
            await asyncio.sleep(3600)

    def _is_due(source, now):
        """Check if a scraping source is due for a refresh based on its interval."""
        last = getattr(source, "last_scrape_at", None) or getattr(source, "last_scraped_at", None)
        if last is None:
            return True
        return (now - last).total_seconds() / 60 >= source.scrape_interval_minutes

    # Price scraping scheduler
    async def price_scraping_scheduler_loop():
        """Run price scraping based on each source's configured interval.
        Failover: if primary source fails, try other active sources of the same type."""
        from datetime import datetime, timezone

        from sqlalchemy import select

        from .models.models import CertificateType, ScrapingSource
        from .services.price_scraper import price_scraper

        # Wait 30 seconds on startup before first check
        await asyncio.sleep(30)

        while True:
            try:
                async with AsyncSessionLocal() as db:
                    # Get all active scraping sources
                    result = await db.execute(
                        select(ScrapingSource).where(
                            ScrapingSource.is_active.is_(True)
                        )
                    )
                    sources = result.scalars().all()

                    now = datetime.now(timezone.utc).replace(tzinfo=None)

                    from .services.price_scraper import is_carboncredits_url

                    # Partition: carboncredits.com uses one shared fetch per cycle (0026)
                    carboncredits_sources = [
                        s for s in sources
                        if s.url and is_carboncredits_url(s.url)
                    ]
                    other_sources = [
                        s for s in sources
                        if not s.url or not is_carboncredits_url(s.url)
                    ]

                    # Track which cert types got a successful scrape this cycle
                    scraped_cert_types: set = set()

                    # --- Carboncredits group (shared fetch) ---
                    if carboncredits_sources:
                        any_due = any(_is_due(s, now) for s in carboncredits_sources)
                        if any_due:
                            try:
                                await price_scraper.refresh_carboncredits_sources(
                                    db, carboncredits_sources
                                )
                                for s in carboncredits_sources:
                                    if s.last_price is not None:
                                        scraped_cert_types.add(s.certificate_type)
                                        logger.info(
                                            "Auto-scraped %s: %s",
                                            s.name,
                                            s.last_price,
                                        )
                            except Exception as e:
                                logger.warning(
                                    "Auto-scrape failed for carboncredits.com: %s",
                                    e,
                                )

                    # --- Non-carboncredits sources: primary first, then fallbacks ---
                    for cert_type in (CertificateType.EUA, CertificateType.CEA):
                        type_sources = [s for s in other_sources if s.certificate_type == cert_type]
                        if not type_sources:
                            continue

                        # Sort: primary first, then by created_at
                        type_sources.sort(key=lambda s: (not s.is_primary, s.created_at))

                        primary = type_sources[0] if type_sources[0].is_primary else None
                        fallbacks = type_sources[1:] if primary else type_sources

                        # Try primary first
                        if primary and _is_due(primary, now):
                            try:
                                await price_scraper.refresh_source(primary, db)
                                scraped_cert_types.add(cert_type)
                                logger.info(
                                    "Auto-scraped %s (primary): %s",
                                    primary.name,
                                    primary.last_price,
                                )
                                continue  # Primary succeeded, skip fallbacks
                            except Exception as e:
                                logger.warning(
                                    "Primary %s source %s failed: %s — trying fallbacks",
                                    cert_type.value,
                                    primary.name,
                                    e,
                                )
                        elif primary and not _is_due(primary, now):
                            # Primary not due yet and had a previous success
                            if primary.last_scrape_status and primary.last_scrape_status.value == "SUCCESS":
                                continue  # Not due, skip

                        # Failover: try fallback sources in order
                        for fallback in fallbacks:
                            if not _is_due(fallback, now) and cert_type in scraped_cert_types:
                                continue
                            try:
                                await price_scraper.refresh_source(fallback, db)
                                scraped_cert_types.add(cert_type)
                                logger.info(
                                    "Auto-scraped %s (fallback): %s",
                                    fallback.name,
                                    fallback.last_price,
                                )
                                break  # One successful fallback is enough
                            except Exception as e:
                                logger.warning(
                                    "Fallback %s source %s also failed: %s",
                                    cert_type.value,
                                    fallback.name,
                                    e,
                                )

                    # Warm Redis cache after scrape cycle so header reflects latest prices
                    try:
                        eua_eur = None
                        cea_eur = None
                        all_sources = carboncredits_sources + other_sources
                        for s in all_sources:
                            if s.certificate_type == CertificateType.EUA and s.is_primary and s.last_price is not None:
                                eua_eur = float(s.last_price)
                            elif s.certificate_type == CertificateType.CEA and s.is_primary and getattr(s, "last_price_eur", None) is not None:
                                cea_eur = float(s.last_price_eur)
                        if eua_eur is not None and cea_eur is not None:
                            from .core.security import RedisManager

                            await RedisManager.cache_prices(
                                {
                                    "eua_eur": str(eua_eur),
                                    "cea_eur": str(cea_eur),
                                    "eua_change": "0",
                                    "cea_change": "0",
                                    "updated_at": now.isoformat(),
                                }
                            )
                            logger.info("Cache warmed: EUA=%.2f EUR, CEA=%.2f EUR", eua_eur, cea_eur)
                    except Exception as e:
                        logger.warning("Failed to warm price cache: %s", e)

                    # Check price alerts after each scrape cycle
                    try:
                        from .services.price_scraper import check_price_alerts

                        prices = await price_scraper.get_current_prices()
                        await check_price_alerts(db, prices)
                    except Exception as e:
                        logger.warning("Price alert check failed: %s", e)

                report_run("price_scraper")
            except Exception as e:
                logger.error(f"Price scraping scheduler error: {e}", exc_info=True)
                report_run("price_scraper", success=False, error=str(e))

            # Check every 60 seconds
            await asyncio.sleep(60)

    # Exchange rate scraping scheduler
    async def exchange_rate_scraping_scheduler_loop():
        """Run exchange rate scraping based on each source's configured interval.
        Failover: if primary source fails, try other active sources."""
        from datetime import datetime, timezone

        from sqlalchemy import select

        from .models.models import ExchangeRateSource
        from .services.price_scraper import price_scraper

        # Wait 45 seconds on startup before first check (stagger from price scraper)
        await asyncio.sleep(45)

        while True:
            try:
                async with AsyncSessionLocal() as db:
                    # Get all active exchange rate sources
                    result = await db.execute(
                        select(ExchangeRateSource).where(
                            ExchangeRateSource.is_active.is_(True)
                        )
                    )
                    sources = list(result.scalars().all())

                    now = datetime.now(timezone.utc).replace(tzinfo=None)

                    # Sort: primary first, then by created_at
                    sources.sort(key=lambda s: (not s.is_primary, s.created_at))

                    primary = sources[0] if sources and sources[0].is_primary else None
                    fallbacks = sources[1:] if primary else sources

                    scraped = False

                    # Try primary first
                    if primary and _is_due(primary, now):
                        try:
                            await price_scraper.refresh_exchange_rate_source(
                                primary, db
                            )
                            scraped = True
                            logger.info(
                                "Auto-scraped exchange rate %s (primary): %s",
                                primary.name,
                                primary.last_rate,
                            )
                        except Exception as e:
                            logger.warning(
                                "Primary exchange rate source %s failed: %s — trying fallbacks",
                                primary.name,
                                e,
                            )
                    elif primary and not _is_due(primary, now):
                        if primary.last_scrape_status and primary.last_scrape_status.value == "SUCCESS":
                            scraped = True  # Not due, already have good data

                    # Failover: try fallback sources if primary failed
                    if not scraped:
                        for fallback in fallbacks:
                            if not _is_due(fallback, now):
                                continue
                            try:
                                await price_scraper.refresh_exchange_rate_source(
                                    fallback, db
                                )
                                logger.info(
                                    "Auto-scraped exchange rate %s (fallback): %s",
                                    fallback.name,
                                    fallback.last_rate,
                                )
                                break  # One success is enough
                            except Exception as e:
                                logger.warning(
                                    "Fallback exchange rate source %s also failed: %s",
                                    fallback.name,
                                    e,
                                )
                report_run("exchange_rate_scraper")
            except Exception as e:
                logger.error(
                    f"Exchange rate scraping scheduler error: {e}", exc_info=True
                )
                report_run("exchange_rate_scraper", success=False, error=str(e))

            # Check every 60 seconds
            await asyncio.sleep(60)

    # Auto-trade executor scheduler
    async def auto_trade_executor_loop():
        """Execute auto-trade rules based on their configured intervals"""
        from sqlalchemy import select

        from .models.models import User, UserRole

        # Wait 10 seconds on startup before first check
        await asyncio.sleep(10)

        # Bootstrap: ensure rules exist for all active market makers
        try:
            async with AsyncSessionLocal() as db:
                created = await AutoTradeExecutor.bootstrap_rules(db)
                await db.commit()
                if created:
                    logger.info(f"Auto-trade bootstrap: created {created} rules")
        except Exception as e:
            logger.error(f"Auto-trade bootstrap error: {e}", exc_info=True)

        while True:
            try:
                async with AsyncSessionLocal() as db:
                    # Get a system admin for audit trail
                    result = await db.execute(
                        select(User).where(User.role == UserRole.ADMIN).limit(1)
                    )
                    admin = result.scalar_one_or_none()

                    if admin:
                        results = await AutoTradeExecutor.execute_all_ready_rules(
                            db=db, admin_user_id=admin.id
                        )
                        update_executor_status(results, cycle_interval=5)
                        successes = sum(1 for r in results if r.get("success"))
                        if results:
                            logger.info(
                                f"Auto-trade cycle: {successes}/{len(results)} orders placed"
                            )
                report_run("auto_trade_executor")
            except Exception as e:
                logger.error(f"Auto-trade executor error: {e}", exc_info=True)
                report_run("auto_trade_executor", success=False, error=str(e))

            # Check every 5 seconds for rules ready to execute (supports 10-20 sec intervals)
            await asyncio.sleep(5)

    # Exchange rate history retention loop (compact granular data older than 30 days)
    async def exchange_rate_retention_loop():
        """Once per day, aggregate granular exchange rate rows older than 30 days
        into daily averages (source='daily_avg'), then delete the granular rows."""
        import uuid as _uuid
        from datetime import datetime, timedelta, timezone
        from decimal import Decimal

        from sqlalchemy import select, delete as sa_delete, func

        from .models.models import ExchangeRateHistory

        # Wait 120 seconds on startup before first run
        await asyncio.sleep(120)

        while True:
            try:
                async with AsyncSessionLocal() as db:
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    cutoff = now - timedelta(days=30)

                    # Find distinct currency pairs that have old granular rows
                    pairs_q = (
                        select(
                            ExchangeRateHistory.from_currency,
                            ExchangeRateHistory.to_currency,
                        )
                        .where(
                            ExchangeRateHistory.recorded_at < cutoff,
                            ExchangeRateHistory.source != "daily_avg",
                        )
                        .distinct()
                    )
                    pairs_result = await db.execute(pairs_q)
                    pairs = pairs_result.all()

                    total_created = 0

                    for from_cur, to_cur in pairs:
                        # Compute daily averages for old granular rows
                        day_col = func.date_trunc("day", ExchangeRateHistory.recorded_at).label("day")
                        avg_q = (
                            select(
                                day_col,
                                func.avg(ExchangeRateHistory.rate).label("avg_rate"),
                            )
                            .where(
                                ExchangeRateHistory.from_currency == from_cur,
                                ExchangeRateHistory.to_currency == to_cur,
                                ExchangeRateHistory.recorded_at < cutoff,
                                ExchangeRateHistory.source != "daily_avg",
                            )
                            .group_by(day_col)
                        )
                        avg_result = await db.execute(avg_q)
                        daily_avgs = avg_result.all()

                        for day_ts, avg_rate in daily_avgs:
                            # Skip if a daily_avg row already exists for this day+pair
                            exists_q = select(ExchangeRateHistory.id).where(
                                ExchangeRateHistory.from_currency == from_cur,
                                ExchangeRateHistory.to_currency == to_cur,
                                ExchangeRateHistory.source == "daily_avg",
                                ExchangeRateHistory.recorded_at == day_ts,
                            )
                            exists_result = await db.execute(exists_q)
                            if exists_result.scalar_one_or_none() is not None:
                                continue

                            # Insert daily average row
                            avg_row = ExchangeRateHistory(
                                id=_uuid.uuid4(),
                                from_currency=from_cur,
                                to_currency=to_cur,
                                rate=Decimal(str(round(float(avg_rate), 8))),
                                source="daily_avg",
                                recorded_at=day_ts,
                            )
                            db.add(avg_row)
                            total_created += 1

                        # Delete old granular rows for this pair
                        del_stmt = sa_delete(ExchangeRateHistory).where(
                            ExchangeRateHistory.from_currency == from_cur,
                            ExchangeRateHistory.to_currency == to_cur,
                            ExchangeRateHistory.recorded_at < cutoff,
                            ExchangeRateHistory.source != "daily_avg",
                        )
                        await db.execute(del_stmt)

                    await db.commit()

                    if total_created > 0 or pairs:
                        logger.info(
                            "Exchange rate retention: created %d daily averages, "
                            "compacted %d currency pair(s)",
                            total_created,
                            len(pairs),
                        )

            except Exception as e:
                logger.error(f"Exchange rate retention loop error: {e}", exc_info=True)

            # Run once per day
            await asyncio.sleep(86400)

    # Seed default scraping sources if none exist
    try:
        from .services.price_scraper import (
            seed_default_exchange_rate_sources,
            seed_default_sources,
        )

        async with AsyncSessionLocal() as db:
            await seed_default_sources(db)
            await seed_default_exchange_rate_sources(db)
        logger.info("Scraping source seed check complete")
    except Exception as e:
        logger.error(f"Failed to seed scraping sources: {e}", exc_info=True)

    # Start background tasks
    processor_task = asyncio.create_task(settlement_processor_loop())
    monitoring_task = asyncio.create_task(settlement_monitoring_loop())
    deposit_task = asyncio.create_task(deposit_hold_processor_loop())
    scraping_task = asyncio.create_task(price_scraping_scheduler_loop())
    exchange_rate_task = asyncio.create_task(exchange_rate_scraping_scheduler_loop())
    auto_trade_task = asyncio.create_task(auto_trade_executor_loop())
    retention_task = asyncio.create_task(exchange_rate_retention_loop())

    async def news_scraper_loop():
        await asyncio.sleep(20)  # short startup delay
        while True:
            try:
                await news_scraper.refresh()
            except Exception as exc:
                logger.error(f"News scraper loop error: {exc}", exc_info=True)
            await asyncio.sleep(1200)  # refresh every 20 minutes

    news_task = asyncio.create_task(news_scraper_loop())
    _background_tasks.extend(
        [processor_task, monitoring_task, deposit_task, scraping_task, exchange_rate_task, auto_trade_task, retention_task, news_task]
    )
    logger.info(
        "Settlement processor, monitoring, deposit hold processor, price scraping, "
        "exchange rate scraping, auto-trade, retention schedulers, and news scraper started"
    )

    # Register ticket broadcast to backoffice WebSocket
    from app.api.v1.backoffice import backoffice_ws_manager
    from app.services.ticket_service import TicketService
    TicketService.register_broadcast(backoffice_ws_manager.broadcast)
    logger.info("Ticket broadcast registered to backoffice WebSocket")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Cancel background tasks
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    logger.info("Background tasks cancelled")

    await RedisManager.close()


tags_metadata = [
    {
        "name": "Authentication",
        "description": "Login, magic links, token refresh, and password management",
    },
    {
        "name": "Users",
        "description": "User profile, settings, and account management",
    },
    {
        "name": "Admin",
        "description": "Admin-only endpoints: contact requests, user creation, entity/KYC, settings, market controls",
    },
    {
        "name": "Fee Configuration",
        "description": "Fee configuration: global defaults, entity overrides, introducer commission rates",
    },
    {
        "name": "Logging & Audit",
        "description": "Audit log viewer for admin actions",
    },
    {
        "name": "Backoffice",
        "description": "Backoffice operations: user approval, KYC review, deposit management, asset adjustments",
    },
    {
        "name": "Contact",
        "description": "Public contact request and NDA submission endpoints",
    },
    {
        "name": "Onboarding",
        "description": "User onboarding flow: KYC document upload and status checks",
    },
    {
        "name": "CEA Cash",
        "description": "CEA cash market: order book, market depth, OHLC data, order placement and management",
    },
    {
        "name": "Deposits",
        "description": "Deposit lifecycle: announce, hold period, confirm, clear, and admin management",
    },
    {
        "name": "withdrawals",
        "description": "Withdrawal requests and admin approval workflow",
    },
    {
        "name": "Swap",
        "description": "CEA/EUA swap operations: rates, previews, execution, and history",
    },
    {
        "name": "Market Makers",
        "description": "Market maker management: orders, inventory, auto-trade rules, and market settings",
    },
    {
        "name": "Assets",
        "description": "Asset holdings and transaction history",
    },
    {
        "name": "Marketplace",
        "description": "Public marketplace listings (anonymous)",
    },
    {
        "name": "Prices",
        "description": "Carbon credit price data: current prices, historical, and scraping sources",
    },
    {
        "name": "exchange-rates",
        "description": "EUR/CNY exchange rate sources and current rates",
    },
    {
        "name": "Settlement",
        "description": "T+3 settlement system: metrics, alerts, and management",
    },
    {
        "name": "System Health",
        "description": "Background processor status and system health monitoring",
    },
    {
        "name": "introducer",
        "description": "Introducer portal: referrals, invitations, commissions, and chat",
    },
    {
        "name": "ai-agent",
        "description": "AI chat assistant configuration: knowledge sources, API keys, and conversation management",
    },
    {
        "name": "Client Realtime",
        "description": "WebSocket endpoints for real-time client notifications and price updates",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Nihao Group Carbon Trading Platform API

    A professional OTC carbon credit trading platform enabling swap trading
    between EU ETS (EUA) and China ETS (CEA) emission certificates.

    ### Features
    - **Marketplace**: Browse anonymous CEA and EUA listings
    - **Swap Center**: Exchange certificates between jurisdictions
    - **Real-time Prices**: Live carbon credit pricing via WebSocket
    - **Magic Link Auth**: Passwordless authentication

    ### Market Context
    - EUA (EU Allowances): ~€75-80/tCO2e
    - CEA (China Allowances): ~¥100/tCO2e (~€13)
    - Swap Rate: ~5.8 CEA per 1 EUA

    Built by Nihao Group Ltd - Hong Kong | Italy
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
)

# CORS: restrict origins in production, allow all in development
_cors_origins = (
    settings.cors_origins_list if settings.ENVIRONMENT == "production" else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Log unhandled exceptions and return useful error for 500s."""
    import traceback

    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    logger.error(
        "Unhandled exception: %s\n%s",
        exc,
        traceback.format_exc(),
        extra={"path": request.url.path, "method": request.method},
    )
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(contact.router, prefix="/api/v1")
app.include_router(prices.router, prefix="/api/v1")
app.include_router(marketplace.router, prefix="/api/v1")
app.include_router(swaps.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(client_ws.router, prefix="/api/v1")
app.include_router(backoffice.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(cash_market.router, prefix="/api/v1")
app.include_router(settlement.router, prefix="/api/v1")
app.include_router(market_maker.router, prefix="/api/v1/admin")
app.include_router(admin_logging.router, prefix="/api/v1/admin")
app.include_router(admin_fees.router, prefix="/api/v1/admin")
app.include_router(deposits.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(withdrawals.router, prefix="/api/v1")
app.include_router(introducer.router, prefix="/api/v1")
app.include_router(ai_agent.router, prefix="/api/v1")
app.include_router(exchange_rates.router, prefix="/api/v1")
app.include_router(market_news.router, prefix="/api/v1")
app.include_router(system_health.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "prices": "/api/v1/prices/current",
            "marketplace": "/api/v1/marketplace/cea",
            "swaps": "/api/v1/swaps/available",
            "contact": "/api/v1/contact/request",
            "users": "/api/v1/users/me",
            "onboarding": "/api/v1/onboarding/status",
            "backoffice": "/api/v1/backoffice/pending-users",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}
