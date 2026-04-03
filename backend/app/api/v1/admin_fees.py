"""
Admin Fee Configuration API

Endpoints for managing trading fees per market and per entity.
ADMIN access required for all endpoints.
"""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_admin_user
from ...models.models import Entity, EntityFeeOverride, MarketType, TradingFeeConfig, User
from ...schemas.schemas import (
    AllFeesResponse,
    EffectiveFeeResponse,
    EntityFeeOverrideCreate,
    EntityFeeOverrideResponse,
    MarketTypeEnum,
    TradingFeeConfigResponse,
    TradingFeeConfigUpdate,
)

router = APIRouter(prefix="/fees", tags=["Fee Configuration"])


# =============================================================================
# Market Fee Configuration
# =============================================================================


@router.get("", response_model=AllFeesResponse)
async def get_all_fees(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """
    Get all fee configurations including market defaults and entity overrides.
    ADMIN only.
    """
    # Get market fee configs
    market_result = await db.execute(
        select(TradingFeeConfig).order_by(TradingFeeConfig.market)
    )
    market_fees = market_result.scalars().all()

    # Get entity overrides with entity names
    override_result = await db.execute(
        select(EntityFeeOverride, Entity.name)
        .join(Entity, EntityFeeOverride.entity_id == Entity.id)
        .where(EntityFeeOverride.is_active.is_(True))
        .order_by(Entity.name)
    )
    overrides_with_names = override_result.all()

    entity_overrides = []
    for override, entity_name in overrides_with_names:
        override_dict = {
            "id": override.id,
            "entity_id": override.entity_id,
            "entity_name": entity_name,
            "market": override.market.value,
            "bid_fee_rate": override.bid_fee_rate,
            "ask_fee_rate": override.ask_fee_rate,
            "is_active": override.is_active,
            "created_at": override.created_at,
        }
        entity_overrides.append(EntityFeeOverrideResponse(**override_dict))

    return AllFeesResponse(
        market_fees=[TradingFeeConfigResponse.model_validate(f) for f in market_fees],
        entity_overrides=entity_overrides,
    )


@router.put("/{market}", response_model=TradingFeeConfigResponse)
async def update_market_fees(
    market: MarketTypeEnum,
    data: TradingFeeConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Update fee configuration for a specific market.
    ADMIN only.
    """
    # Get or create fee config for this market
    result = await db.execute(
        select(TradingFeeConfig).where(TradingFeeConfig.market == MarketType(market.value))
    )
    fee_config = result.scalar_one_or_none()

    if not fee_config:
        # Create new config
        fee_config = TradingFeeConfig(
            market=MarketType(market.value),
            bid_fee_rate=data.bid_fee_rate,
            ask_fee_rate=data.ask_fee_rate,
            updated_by=admin.id,
        )
        db.add(fee_config)
    else:
        # Update existing
        fee_config.bid_fee_rate = data.bid_fee_rate
        fee_config.ask_fee_rate = data.ask_fee_rate
        fee_config.updated_by = admin.id

    await db.commit()
    await db.refresh(fee_config)

    return TradingFeeConfigResponse.model_validate(fee_config)


# =============================================================================
# Entity Fee Overrides
# =============================================================================


@router.get("/entities", response_model=List[EntityFeeOverrideResponse])
async def get_entity_overrides(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """
    Get all entity fee overrides.
    ADMIN only.
    """
    result = await db.execute(
        select(EntityFeeOverride, Entity.name)
        .join(Entity, EntityFeeOverride.entity_id == Entity.id)
        .where(EntityFeeOverride.is_active.is_(True))
        .order_by(Entity.name)
    )
    overrides_with_names = result.all()

    return [
        EntityFeeOverrideResponse(
            id=override.id,
            entity_id=override.entity_id,
            entity_name=entity_name,
            market=override.market.value,
            bid_fee_rate=override.bid_fee_rate,
            ask_fee_rate=override.ask_fee_rate,
            is_active=override.is_active,
            created_at=override.created_at,
        )
        for override, entity_name in overrides_with_names
    ]


@router.get("/entities/{entity_id}", response_model=List[EntityFeeOverrideResponse])
async def get_entity_override(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """
    Get fee overrides for a specific entity.
    ADMIN only.
    """
    result = await db.execute(
        select(EntityFeeOverride, Entity.name)
        .join(Entity, EntityFeeOverride.entity_id == Entity.id)
        .where(EntityFeeOverride.entity_id == entity_id)
        .where(EntityFeeOverride.is_active.is_(True))
    )
    overrides_with_names = result.all()

    return [
        EntityFeeOverrideResponse(
            id=override.id,
            entity_id=override.entity_id,
            entity_name=entity_name,
            market=override.market.value,
            bid_fee_rate=override.bid_fee_rate,
            ask_fee_rate=override.ask_fee_rate,
            is_active=override.is_active,
            created_at=override.created_at,
        )
        for override, entity_name in overrides_with_names
    ]


@router.put("/entities/{entity_id}", response_model=EntityFeeOverrideResponse)
async def upsert_entity_override(
    entity_id: UUID,
    data: EntityFeeOverrideCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Create or update fee override for an entity.
    ADMIN only.
    """
    # Verify entity exists
    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_id} not found",
        )

    # Check for existing override
    result = await db.execute(
        select(EntityFeeOverride)
        .where(EntityFeeOverride.entity_id == entity_id)
        .where(EntityFeeOverride.market == MarketType(data.market.value))
    )
    override = result.scalar_one_or_none()

    if not override:
        # Create new override
        override = EntityFeeOverride(
            entity_id=entity_id,
            market=MarketType(data.market.value),
            bid_fee_rate=data.bid_fee_rate,
            ask_fee_rate=data.ask_fee_rate,
            updated_by=admin.id,
        )
        db.add(override)
    else:
        # Update existing
        override.bid_fee_rate = data.bid_fee_rate
        override.ask_fee_rate = data.ask_fee_rate
        override.updated_by = admin.id
        override.is_active = True

    await db.commit()
    await db.refresh(override)

    return EntityFeeOverrideResponse(
        id=override.id,
        entity_id=override.entity_id,
        entity_name=entity.name,
        market=override.market.value,
        bid_fee_rate=override.bid_fee_rate,
        ask_fee_rate=override.ask_fee_rate,
        is_active=override.is_active,
        created_at=override.created_at,
    )


@router.delete("/entities/{entity_id}/{market}")
async def delete_entity_override(
    entity_id: UUID,
    market: MarketTypeEnum,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """
    Delete (soft-delete) fee override for an entity.
    The entity will revert to using default market fees.
    ADMIN only.
    """
    result = await db.execute(
        select(EntityFeeOverride)
        .where(EntityFeeOverride.entity_id == entity_id)
        .where(EntityFeeOverride.market == MarketType(market.value))
    )
    override = result.scalar_one_or_none()

    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No fee override found for entity {entity_id} in market {market}",
        )

    override.is_active = False
    await db.commit()

    return {"status": "deleted", "entity_id": str(entity_id), "market": market.value}


# =============================================================================
# Introducer Commission Defaults & Overrides
# =============================================================================


@router.get("/introducer-defaults")
async def get_introducer_defaults(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Get the platform default introducer commission rate."""
    from ...services.commission_service import get_default_commission_rate

    rate = await get_default_commission_rate(db)
    return {"commission_rate": str(rate)}


@router.put("/introducer-defaults")
async def update_introducer_defaults(
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Update the platform default introducer commission rate."""
    from ...models.models import PlatformSetting

    rate_str = body.get("commission_rate")
    if rate_str is None:
        raise HTTPException(status_code=400, detail="Missing 'commission_rate' in body")

    try:
        rate = Decimal(rate_str)
        if rate < 0 or rate > Decimal("1"):
            raise ValueError("Rate must be between 0 and 1")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid rate. Must be a number between 0 and 1.") from e

    result = await db.execute(
        select(PlatformSetting).where(PlatformSetting.key == "introducer_commission_rate")
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = str(rate)
        setting.updated_by = admin.id
    else:
        db.add(
            PlatformSetting(
                key="introducer_commission_rate", value=str(rate), updated_by=admin.id
            )
        )

    await db.commit()
    return {"commission_rate": str(rate)}


@router.get("/introducer-overrides")
async def get_introducer_overrides(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """List introducers with custom commission rates (different from default)."""
    from ...models.models import UserRole
    from ...services.commission_service import get_default_commission_rate

    result = await db.execute(
        select(User)
        .where(User.role.in_([UserRole.INTRODUCER, UserRole.PREINTRODUCER]))
        .where(User.commission_rate.isnot(None))
        .where(User.is_active.is_(True))
        .order_by(User.email)
    )
    users = result.scalars().all()
    default_rate = await get_default_commission_rate(db)

    return [
        {
            "user_id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "commission_rate": str(u.commission_rate),
        }
        for u in users
        if u.commission_rate != default_rate
    ]


@router.get("/search-clients")
async def search_clients(
    q: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """Search entities and introducer users by name/email."""
    from ...models.models import UserRole

    if not q or len(q.strip()) < 2:
        return {"entities": [], "introducers": []}

    term = f"%{q.strip()}%"

    # Search entities by name
    entity_result = await db.execute(select(Entity).where(Entity.name.ilike(term)).limit(10))
    entities = entity_result.scalars().all()

    # Search introducer users by email or name
    user_result = await db.execute(
        select(User)
        .where(User.role.in_([UserRole.INTRODUCER, UserRole.PREINTRODUCER]))
        .where(User.is_active.is_(True))
        .where(
            (User.email.ilike(term))
            | (User.first_name.ilike(term))
            | (User.last_name.ilike(term))
        )
        .limit(10)
    )
    users = user_result.scalars().all()

    return {
        "entities": [{"id": str(e.id), "name": e.name, "type": "entity"} for e in entities],
        "introducers": [
            {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "type": "introducer",
                "commission_rate": str(u.commission_rate) if u.commission_rate else None,
            }
            for u in users
        ],
    }


# =============================================================================
# Fee Calculation Helper
# =============================================================================


@router.get("/effective/{market}/{side}", response_model=EffectiveFeeResponse)
async def get_effective_fee(
    market: MarketTypeEnum,
    side: str,
    entity_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """
    Get the effective fee rate for a specific market, side, and optionally entity.
    Useful for preview calculations.
    ADMIN only.
    """
    if side.upper() not in ("BID", "ASK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Side must be 'BID' or 'ASK'",
        )

    side_upper = side.upper()
    fee_rate: Decimal
    is_override = False

    # Check for entity override first
    if entity_id:
        result = await db.execute(
            select(EntityFeeOverride)
            .where(EntityFeeOverride.entity_id == entity_id)
            .where(EntityFeeOverride.market == MarketType(market.value))
            .where(EntityFeeOverride.is_active.is_(True))
        )
        override = result.scalar_one_or_none()

        if override:
            override_rate = override.bid_fee_rate if side_upper == "BID" else override.ask_fee_rate
            if override_rate is not None:
                fee_rate = override_rate
                is_override = True

    # Fall back to market default
    if not is_override:
        result = await db.execute(
            select(TradingFeeConfig).where(TradingFeeConfig.market == MarketType(market.value))
        )
        config = result.scalar_one_or_none()

        if not config:
            # Default fallback if no config exists
            fee_rate = Decimal("0.005")
        else:
            fee_rate = config.bid_fee_rate if side_upper == "BID" else config.ask_fee_rate

    return EffectiveFeeResponse(
        market=market,
        side=side_upper,
        fee_rate=fee_rate,
        is_override=is_override,
        entity_id=entity_id,
    )
