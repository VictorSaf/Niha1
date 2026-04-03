import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_swap_user
from ...models.models import (
    AssetType,
    CertificateType,
    EntityHolding,
    MarketMakerClient,
    MarketMakerType,
    MarketType,
    Order,
    OrderSide,
    OrderStatus,
    SettlementBatch,
    SettlementStatus,
    SettlementStatusHistory,
    SettlementType,
    SwapRequest,
    SwapStatus,
    User,
)
from ...models.models import TicketStatus
from ...services.market_maker_service import MarketMakerService
from ...services.price_scraper import price_scraper
from ...services.settlement_service import SettlementService
from ...services.ticket_service import TicketService
from .client_ws import client_ws_manager
from .backoffice import backoffice_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/swaps", tags=["Swap"])

# NOTE: Swap market uses real data from database


class SwapDirection(str, Enum):
    CEA_TO_EUA = "cea_to_eua"
    ALL = "all"


class CreateSwapRequest(BaseModel):
    """Request model for creating a swap. CEA/EUA quantities are whole numbers only."""

    from_type: str = Field(..., description="Source certificate type (CEA or EUA)")
    to_type: str = Field(..., description="Target certificate type (CEA or EUA)")
    quantity: int = Field(..., gt=0, description="Quantity to swap (whole certificates only)")
    desired_rate: Optional[float] = Field(None, description="Desired exchange rate")


@router.get("/available")
async def get_available_swaps(
    direction: SwapDirection = SwapDirection.ALL,
    min_quantity: Optional[int] = None,
    max_quantity: Optional[int] = None,
    page: int = Query(1, ge=1),  # noqa: B008
    per_page: int = Query(20, ge=1, le=50),  # noqa: B008
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db=Depends(get_db),  # noqa: B008
):
    """
    Get available swap requests in the marketplace. SWAP+ or ADMIN only.

    TODO: Query real swap orders from database when swap order model is implemented.
    Currently returns empty list as swap market is not yet live.
    """
    # Real implementation will query SwapOrder table
    # For now, return empty as swap market is being developed
    swaps = []
    total = 0

    return {
        "data": swaps,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": 0,
        },
        "message": "Swap market coming soon. No active swap requests.",
    }


@router.get("/rate")
async def get_current_swap_rate(
    current_user: User = Depends(get_swap_user),  # noqa: B008
):
    """
    Get current swap rate for CEA → EUA swaps. SWAP+ or ADMIN only (0010 §8).
    Returns the CEA/EUA ratio (how many EUA you get for 1 CEA).
    """
    prices = await price_scraper.get_current_prices()

    eua_price = prices["eua"]["price"]
    cea_price = prices["cea"]["price"]

    # Calculate CEA/EUA ratio: How many EUA for 1 CEA
    if eua_price > 0:
        cea_to_eua_ratio = cea_price / eua_price
    else:
        # Fallback if EUA price is 0/invalid to avoid ZeroDivisionError
        cea_to_eua_ratio = 0.12

    return {
        "cea_to_eua": round(cea_to_eua_ratio, 4),
        "eua_price_eur": eua_price,
        "cea_price_eur": cea_price,
        "explanation": f"1 CEA = {cea_to_eua_ratio:.4f} EUA at current market rates",
        "platform_fee_pct": 0.5,  # 0.5% platform fee
        "effective_rate": round(cea_to_eua_ratio * 0.995, 4),
    }


@router.get("/my")
async def get_my_swaps(
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get current user's swap requests. SWAP+ or ADMIN only (0010 §8).
    Returns all swaps associated with the user's entity.
    """
    # Query swap requests for this user's entity
    result = await db.execute(
        select(SwapRequest)
        .where(SwapRequest.entity_id == current_user.entity_id)
        .order_by(SwapRequest.created_at.desc())
    )
    swaps = result.scalars().all()

    # Convert to response format (CEA/EUA quantities as integers)
    return {
        "data": [
            {
                "id": str(swap.id),
                "anonymous_code": swap.anonymous_code,
                "from_type": swap.from_type.value,
                "to_type": swap.to_type.value,
                "quantity": int(round(float(swap.quantity))),
                "desired_rate": float(swap.desired_rate) if swap.desired_rate else None,
                "equivalent_quantity": int(round(float(swap.quantity * swap.desired_rate))) if swap.desired_rate else 0,
                "status": swap.status.value.lower(),
                "created_at": swap.created_at.isoformat() if swap.created_at else None,
            }
            for swap in swaps
        ]
    }

@router.get("/calculator")
async def calculate_swap(
    from_type: str,
    quantity: int = Query(..., gt=0),  # noqa: B008  whole certificates only
    current_user: User = Depends(get_swap_user),  # noqa: B008
):
    """
    Calculate swap output for a given input. SWAP+ or ADMIN only (0010 §8).
    """
    prices = await price_scraper.get_current_prices()

    eua_price = prices["eua"]["price"]
    cea_price = prices["cea"]["price"]

    if from_type.upper() == "EUA":
        base_rate = eua_price / cea_price
        output_quantity = quantity * base_rate * 0.995  # After 0.5% fee
        output_type = "CEA"
        input_value = quantity * eua_price
    else:
        base_rate = cea_price / eua_price
        output_quantity = quantity * base_rate * 0.995
        output_type = "EUA"
        input_value = quantity * cea_price

    return {
        "input": {
            "type": from_type.upper(),
            "quantity": quantity,
            "value_eur": round(input_value, 2),
        },
        "output": {
            "type": output_type,
            "quantity": int(round(output_quantity)),
            "value_eur": round(
                output_quantity * (eua_price if output_type == "EUA" else cea_price), 2
            ),
        },
        "rate": round(output_quantity / quantity, 4),
        "fee_pct": 0.5,
        "fee_eur": round(input_value * 0.005, 2),
    }


@router.get("/stats")
async def get_swap_stats(
    current_user: User = Depends(get_swap_user),  # noqa: B008
):
    """
    Get swap market statistics. SWAP+ or ADMIN only.

    TODO: Calculate real stats from SwapOrder table when implemented.
    """
    prices = await price_scraper.get_current_prices()

    # Real implementation will aggregate from SwapOrder table
    return {
        "open_swaps": 0,
        "matched_today": 0,
        "eua_to_cea_requests": 0,
        "cea_to_eua_requests": 0,
        "total_eua_volume": 0,
        "total_cea_volume": 0,
        "current_rate": prices["swap_rate"],
        "avg_requested_rate": 0.0,
        "message": "Swap market coming soon.",
    }


# ============================================================================
# SWAP OFFERS ENDPOINTS (Market Maker liquidity for swap market)
# ============================================================================


class CreateSwapOfferRequest(BaseModel):
    """Request model for creating a swap offer (market maker liquidity). EUA quantity is whole number only."""

    market_maker_id: UUID = Field(..., description="Market maker ID (must be EUA_OFFER type)")
    ratio: float = Field(..., gt=0, description="CEA/EUA ratio (e.g., 0.1182 means 1 CEA = 0.1182 EUA)")
    eua_quantity: int = Field(..., gt=0, description="Amount of EUA to offer (whole certificates only)")


class CreateSwapOfferBatchRequest(BaseModel):
    """Request model for creating multiple swap offers at once."""

    offers: list[CreateSwapOfferRequest] = Field(..., description="List of swap offers to create")


@router.get("/offers")
async def get_swap_offers(
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get available swap offers from EUA_OFFER market makers.

    Returns orders from the SWAP market that users can accept.
    Each offer represents EUA available at a specific ratio.
    """
    from sqlalchemy.orm import joinedload

    # Query SWAP market orders that are OPEN, grouped by market maker and ratio
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.market_maker))
        .where(
            Order.market == MarketType.SWAP,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.market_maker_id.isnot(None),
        )
        .order_by(Order.price.desc())  # price = ratio, best ratio first
    )
    orders = result.scalars().unique().all()

    # Group offers by market maker
    offers_by_mm: dict = {}
    for order in orders:
        mm_id = str(order.market_maker_id)
        if mm_id not in offers_by_mm:
            offers_by_mm[mm_id] = {
                "market_maker_id": mm_id,
                "market_maker_name": order.market_maker.name if order.market_maker else "Unknown",
                "direction": "CEA_TO_EUA",  # Users give CEA, get EUA
                "offers": [],
                "total_eua_available": 0.0,
            }

        remaining = float(order.quantity) - float(order.filled_quantity)
        if remaining > 0:
            remaining_int = int(round(remaining))
            offers_by_mm[mm_id]["offers"].append({
                "order_id": str(order.id),
                "ratio": float(order.price),  # price = CEA/EUA ratio
                "eua_available": remaining_int,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            })
            offers_by_mm[mm_id]["total_eua_available"] += remaining_int

    # Flatten to list and calculate best rate for each MM (eua_available as int)
    offers_list = []
    for mm_data in offers_by_mm.values():
        if mm_data["offers"]:
            best_ratio = max(o["ratio"] for o in mm_data["offers"])
            total_eua = int(mm_data["total_eua_available"])
            offers_list.append({
                "market_maker_id": mm_data["market_maker_id"],
                "market_maker_name": mm_data["market_maker_name"],
                "direction": mm_data["direction"],
                "ratio": best_ratio,
                "eua_available": total_eua,
                "rate": best_ratio,
                "offers_count": len(mm_data["offers"]),
            })

    return {
        "offers": offers_list,
        "count": len(offers_list),
        "total_eua_available": sum(o["eua_available"] for o in offers_list),
    }


@router.get("/orderbook")
async def get_swap_orderbook(
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get the swap market order book with individual price levels.

    Returns asks (EUA offers) grouped by price level, sorted best price first.
    This is for displaying the order book on the swap page.
    """
    from sqlalchemy import and_
    from sqlalchemy.orm import selectinload

    # Get all active SWAP orders
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.market_maker))
        .where(
            and_(
                Order.market == MarketType.SWAP,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                Order.quantity > Order.filled_quantity,
            )
        )
        .order_by(Order.price.desc())  # Best ratio first (highest CEA/EUA = more EUA per CEA)
    )
    orders = result.scalars().unique().all()

    # Group by price level (ratio)
    price_levels: dict = {}
    for order in orders:
        ratio = round(float(order.price), 4)  # Round to 4 decimals for grouping
        remaining = float(order.quantity) - float(order.filled_quantity)

        if remaining <= 0:
            continue

        if ratio not in price_levels:
            price_levels[ratio] = {
                "ratio": ratio,
                "eua_quantity": 0,
                "orders_count": 0,
            }

        price_levels[ratio]["eua_quantity"] += int(round(remaining))
        price_levels[ratio]["orders_count"] += 1

    # Convert to sorted list (best ratio first = highest)
    asks = sorted(price_levels.values(), key=lambda x: x["ratio"], reverse=True)

    # Calculate totals (integers for CEA/EUA)
    total_eua = sum(level["eua_quantity"] for level in asks)

    # Add cumulative totals for depth visualization
    cumulative = 0
    for level in asks:
        cumulative += level["eua_quantity"]
        level["cumulative_eua"] = cumulative
        level["depth_pct"] = (cumulative / total_eua * 100) if total_eua > 0 else 0

    return {
        "asks": asks,
        "total_eua_available": total_eua,
        "levels_count": len(asks),
    }


@router.post("/offers")
async def create_swap_offer(
    request: CreateSwapOfferRequest,
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a single swap offer (admin/backoffice only).

    Creates an order in the SWAP market representing EUA available for swap.
    The ratio is stored in the price field (CEA/EUA ratio).
    """

    # Verify admin access
    if current_user.role.value not in ["ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create swap offers",
        )

    # Verify market maker exists and is EUA_OFFER type
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id == request.market_maker_id)
    )
    mm = result.scalar_one_or_none()

    if not mm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market maker not found",
        )

    if mm.mm_type != MarketMakerType.EUA_OFFER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Market maker must be EUA_OFFER type, got {mm.mm_type.value}",
        )

    # Check MM has enough EUA available (using MarketMakerService to get actual balances)
    balances = await MarketMakerService.get_balances(db, request.market_maker_id)
    eua_available = balances.get("EUA", {}).get("available", 0)

    if float(eua_available) < request.eua_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient EUA balance. Available: {eua_available}, requested: {request.eua_quantity}",
        )

    # Create the order
    order = Order(
        market=MarketType.SWAP,
        market_maker_id=request.market_maker_id,
        certificate_type=CertificateType.EUA,  # Offering EUA
        side=OrderSide.SELL,  # MM is selling EUA
        price=Decimal(str(request.ratio)),  # ratio = CEA/EUA
        quantity=Decimal(str(request.eua_quantity)),
        filled_quantity=Decimal("0"),
        status=OrderStatus.OPEN,
    )

    db.add(order)
    await db.commit()
    await db.refresh(order)

    return {
        "success": True,
        "order_id": str(order.id),
        "market_maker_id": str(request.market_maker_id),
        "market_maker_name": mm.name,
        "ratio": float(order.price),
        "eua_quantity": int(round(float(order.quantity))),
        "status": order.status.value,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


class ResetSwapLiquidityRequest(BaseModel):
    """Request model for resetting swap liquidity."""

    confirmation_code: str = Field(..., description="Confirmation code to authorize reset")


@router.delete("/offers/reset")
async def reset_swap_liquidity(
    request: ResetSwapLiquidityRequest,
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Delete all open swap offers from EUA_OFFER market makers.

    This is a destructive operation that requires confirmation code.
    Only available to admins.
    """
    from sqlalchemy import and_, update

    # Verify admin access
    if current_user.role.value not in ["ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reset swap liquidity",
        )

    # Verify confirmation code
    if request.confirmation_code != "Niha010!":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation code",
        )

    # Count orders to be deleted
    result = await db.execute(
        select(Order).where(
            and_(
                Order.market == MarketType.SWAP,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
    )
    orders_to_delete = result.scalars().all()
    count = len(orders_to_delete)

    if count == 0:
        return {
            "success": True,
            "message": "No swap offers to delete",
            "deleted_count": 0,
        }

    # Delete all SWAP market orders that are OPEN or PARTIALLY_FILLED
    # We use update to set status to CANCELLED instead of deleting
    await db.execute(
        update(Order)
        .where(
            and_(
                Order.market == MarketType.SWAP,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        .values(
            status=OrderStatus.CANCELLED,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )

    await db.commit()

    return {
        "success": True,
        "message": f"Successfully cancelled {count} swap offers",
        "deleted_count": count,
    }


@router.post("/offers/batch")
async def create_swap_offers_batch(
    request: CreateSwapOfferBatchRequest,
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create multiple swap offers at once (admin/backoffice only).

    Used by the liquidity generation tool to create many offers efficiently.
    """
    # Verify admin access
    if current_user.role.value not in ["ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create swap offers",
        )

    if not request.offers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No offers provided",
        )

    # Pre-fetch all market makers
    mm_ids = list(set(o.market_maker_id for o in request.offers))
    result = await db.execute(
        select(MarketMakerClient).where(MarketMakerClient.id.in_(mm_ids))
    )
    mms = {str(mm.id): mm for mm in result.scalars().all()}

    # Validate all MMs are EUA_OFFER type and have sufficient balance
    mm_required_balance: dict[str, float] = {}
    for offer in request.offers:
        mm_id = str(offer.market_maker_id)
        if mm_id not in mms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Market maker {mm_id} not found",
            )
        mm = mms[mm_id]
        if mm.mm_type != MarketMakerType.EUA_OFFER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Market maker {mm.name} must be EUA_OFFER type",
            )
        mm_required_balance[mm_id] = mm_required_balance.get(mm_id, 0) + offer.eua_quantity

    # Check balances using MarketMakerService
    for mm_id, required in mm_required_balance.items():
        mm = mms[mm_id]
        balances = await MarketMakerService.get_balances(db, UUID(mm_id))
        eua_available = balances.get("EUA", {}).get("available", 0)

        if float(eua_available) < required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MM {mm.name}: insufficient EUA. Available: {eua_available}, required: {required}",
            )

    # Create all orders
    created_orders = []
    for offer in request.offers:
        order = Order(
            market=MarketType.SWAP,
            market_maker_id=offer.market_maker_id,
            certificate_type=CertificateType.EUA,
            side=OrderSide.SELL,
            price=Decimal(str(offer.ratio)),
            quantity=Decimal(str(offer.eua_quantity)),
            filled_quantity=Decimal("0"),
            status=OrderStatus.OPEN,
        )
        db.add(order)
        created_orders.append({
            "market_maker_id": str(offer.market_maker_id),
            "market_maker_name": mms[str(offer.market_maker_id)].name,
            "ratio": offer.ratio,
            "eua_quantity": offer.eua_quantity,
        })

    await db.commit()

    return {
        "success": True,
        "created_count": len(created_orders),
        "offers": created_orders,
    }


def _generate_anonymous_code() -> str:
    """Generate a random anonymous swap code."""
    import random
    import string

    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"SWAP-{suffix}"


@router.post("")
async def create_swap(
    request: CreateSwapRequest,
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Create a new swap request. SWAP+ or ADMIN only.

    Creates a swap request to exchange CEA for EUA (or vice versa).
    The user must have sufficient balance of the source certificate.
    """
    if not current_user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with an entity",
        )

    # Validate certificate types
    try:
        from_cert = CertificateType(request.from_type.upper())
        to_cert = CertificateType(request.to_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid certificate type. Must be 'CEA' or 'EUA'",
        )

    if from_cert == to_cert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target certificate types must be different",
        )

    # Check user's balance
    # Convert CertificateType to AssetType for EntityHolding lookup
    from_asset = AssetType.CEA if from_cert == CertificateType.CEA else AssetType.EUA

    result = await db.execute(
        select(EntityHolding).where(
            EntityHolding.entity_id == current_user.entity_id,
            EntityHolding.asset_type == from_asset,
        )
    )
    holding = result.scalar_one_or_none()

    # Compare as rounded integers — the balance API returns int(round(quantity))
    # so the frontend sends that rounded value. Raw decimal comparison would reject
    # a "full balance" swap when quantity has fractional certificates (e.g. 301982.51
    # rounded to 301983 by the API, but 301982.51 < 301983 fails the raw check).
    if not holding or int(round(float(holding.quantity))) < request.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient {from_cert.value} balance",
        )

    # Check available liquidity in SWAP market (CEA → EUA swaps)
    # Liquidity is based on EUA balance of the EUA_OFFER market maker
    if from_cert == CertificateType.CEA and to_cert == CertificateType.EUA:
        from sqlalchemy import and_

        # Find EUA_OFFER market maker
        result = await db.execute(
            select(MarketMakerClient)
            .where(MarketMakerClient.mm_type == MarketMakerType.EUA_OFFER)
            .where(MarketMakerClient.is_active.is_(True))
        )
        eua_mm = result.scalar_one_or_none()

        if not eua_mm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "no_liquidity",
                    "message": "No swap liquidity provider available. Please try again later.",
                },
            )

        # Use eua_balance from the market maker record (SSOT for swap EUA inventory).
        # MarketMakerService.get_balances() calculates from AssetTransaction which
        # isn't populated for the SWAP market maker's virtual EUA inventory.
        total_eua_available = float(eua_mm.eua_balance) if eua_mm.eua_balance else 0.0

        # Get best ratio from available SWAP orders to calculate EUA needed
        result = await db.execute(
            select(Order)
            .where(
                and_(
                    Order.market == MarketType.SWAP,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.quantity > Order.filled_quantity,
                )
            )
            .order_by(Order.price.desc())  # Best ratio first
        )
        available_orders = result.scalars().all()

        if not available_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "no_liquidity",
                    "message": "No swap offers available. Please try again later.",
                },
            )

        # Calculate EUA needed using best available ratio
        best_ratio = float(available_orders[0].price)
        eua_needed = request.quantity * best_ratio

        if total_eua_available < eua_needed:
            # Calculate max CEA that can be swapped with available EUA
            max_cea_possible = total_eua_available / best_ratio if best_ratio > 0 else 0
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "insufficient_liquidity",
                    "message": f"Insufficient EUA liquidity. Maximum {max_cea_possible:.2f} CEA can be swapped.",
                    "requested": request.quantity,
                    "available": round(max_cea_possible, 2),
                    "total_eua_available": round(total_eua_available, 2),
                    "eua_needed": round(eua_needed, 2),
                },
            )

    # Generate unique anonymous code
    code = _generate_anonymous_code()
    while True:
        result = await db.execute(
            select(SwapRequest).where(SwapRequest.anonymous_code == code)
        )
        if not result.scalar_one_or_none():
            break
        code = _generate_anonymous_code()

    # Create swap request
    swap = SwapRequest(
        entity_id=current_user.entity_id,
        from_type=from_cert,
        to_type=to_cert,
        quantity=Decimal(str(request.quantity)),
        desired_rate=Decimal(str(request.desired_rate)) if request.desired_rate else None,
        status=SwapStatus.OPEN,
        anonymous_code=code,
    )

    db.add(swap)
    await db.flush()

    await TicketService.create_ticket(
        db=db,
        action_type="SWAP_CREATED",
        entity_type="SwapRequest",
        entity_id=swap.id,
        status=TicketStatus.SUCCESS,
        user_id=current_user.id,
        request_payload={
            "from_type": from_cert.value,
            "to_type": to_cert.value,
            "quantity": request.quantity,
            "desired_rate": float(request.desired_rate) if request.desired_rate else None,
            "anonymous_code": code,
        },
        response_data={
            "swap_id": str(swap.id),
            "status": SwapStatus.OPEN.value,
        },
        tags=["swap", "client"],
    )
    await db.commit()
    await db.refresh(swap)

    return {
        "id": str(swap.id),
        "anonymous_code": swap.anonymous_code,
        "from_type": swap.from_type.value,
        "to_type": swap.to_type.value,
        "quantity": float(swap.quantity),
        "desired_rate": float(swap.desired_rate) if swap.desired_rate else None,
        "status": swap.status.value,
        "created_at": swap.created_at.isoformat(),
    }


@router.post("/{swap_id}/execute")
async def execute_swap(
    swap_id: UUID,
    current_user: User = Depends(get_swap_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Execute a swap request by matching against available SWAP market orders.

    This endpoint:
    1. Validates the swap belongs to the user
    2. Finds available SWAP orders (best ratio first)
    3. Matches and fills orders to satisfy the swap
    4. Deducts CEA from user's holdings
    5. Creates a settlement batch for EUA delivery (T+10-14)
    6. Updates user role from SWAP to EUA_SETTLE
    """
    from datetime import timedelta
    from sqlalchemy import and_

    if not current_user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with an entity",
        )

    # Get the swap request
    result = await db.execute(select(SwapRequest).where(SwapRequest.id == swap_id))
    swap = result.scalar_one_or_none()

    if not swap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Swap request not found"
        )

    if swap.entity_id != current_user.entity_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to execute this swap",
        )

    if swap.status != SwapStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Swap is already {swap.status.value}",
        )

    cea_quantity = float(swap.quantity)

    # Check user's CEA balance first
    result = await db.execute(
        select(EntityHolding).where(
            EntityHolding.entity_id == current_user.entity_id,
            EntityHolding.asset_type == AssetType.CEA,
        )
    )
    cea_holding = result.scalar_one_or_none()

    # Same rounding as balance API — see create_swap comment for rationale
    if not cea_holding or int(round(float(cea_holding.quantity))) < int(cea_quantity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient CEA balance",
        )

    # Find available SWAP orders sorted by best ratio (highest first = best for user)
    # price field stores the ratio (CEA/EUA)
    result = await db.execute(
        select(Order)
        .where(
            and_(
                Order.market == MarketType.SWAP,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                Order.quantity > Order.filled_quantity,  # Has remaining quantity
            )
        )
        .order_by(Order.price.desc())  # Best ratio first
    )
    available_orders = result.scalars().all()

    if not available_orders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No swap liquidity available. Please try again later.",
        )

    # Calculate how much EUA we need based on CEA quantity
    # Match against orders to get actual EUA output
    eua_needed = 0.0
    matched_orders = []
    remaining_cea = cea_quantity

    for order in available_orders:
        if remaining_cea <= 0:
            break

        ratio = float(order.price)  # CEA/EUA ratio
        available_eua = float(order.quantity) - float(order.filled_quantity)

        # How much CEA can this order handle?
        cea_for_this_order = available_eua / ratio if ratio > 0 else 0

        if cea_for_this_order >= remaining_cea:
            # This order can fully satisfy remaining CEA
            eua_from_order = remaining_cea * ratio
            matched_orders.append({
                "order": order,
                "eua_amount": eua_from_order,
                "cea_amount": remaining_cea,
                "ratio": ratio,
            })
            eua_needed += eua_from_order
            remaining_cea = 0
        else:
            # Partial fill - use all available from this order
            matched_orders.append({
                "order": order,
                "eua_amount": available_eua,
                "cea_amount": cea_for_this_order,
                "ratio": ratio,
            })
            eua_needed += available_eua
            remaining_cea -= cea_for_this_order

    if remaining_cea > 0.01:  # Allow small rounding errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient swap liquidity. Can only swap {cea_quantity - remaining_cea:.2f} CEA out of {cea_quantity:.2f} requested.",
        )

    # Apply platform fee (0.5%) and floor to integer — fractional EUA stays with NIHA
    platform_fee_pct = 0.005
    eua_output = int(eua_needed * (1 - platform_fee_pct))

    # Calculate weighted average ratio
    total_cea_matched = sum(m["cea_amount"] for m in matched_orders)
    weighted_avg_ratio = eua_needed / total_cea_matched if total_cea_matched > 0 else 0

    # Update matched orders - fill them
    for match in matched_orders:
        order = match["order"]
        eua_amount = Decimal(str(match["eua_amount"]))
        order.filled_quantity = order.filled_quantity + eua_amount

        # Update status if fully filled
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        order.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Deduct CEA from user's holdings.
    # When swapping the full balance, the integer-rounded quantity may exceed
    # the raw decimal (e.g. 301983 vs 301982.51). Clamp to zero to avoid
    # tiny negative balances from rounding.
    new_cea = float(cea_holding.quantity) - cea_quantity
    cea_holding.quantity = Decimal("0") if new_cea < 0 else Decimal(str(new_cea))

    # Get current EUA price for settlement value calculation
    prices = await price_scraper.get_current_prices()
    eua_price = prices["eua"]["price"]

    # Create settlement batch for EUA delivery (T+10-14 days)
    # Use naive datetime for DB compatibility (model uses TIMESTAMP WITHOUT TIME ZONE)
    expected_settlement = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    ) + timedelta(days=14)

    # Retry with savepoint to handle rare batch_reference collisions
    max_attempts = 3
    settlement = None
    for attempt in range(max_attempts):
        batch_reference = await SettlementService.generate_batch_reference(
            db, SettlementType.SWAP_CEA_TO_EUA, CertificateType.EUA
        )

        settlement = SettlementBatch(
            entity_id=current_user.entity_id,
            batch_reference=batch_reference,
            settlement_type=SettlementType.SWAP_CEA_TO_EUA,
            asset_type=CertificateType.EUA,
            quantity=Decimal(str(eua_output)),
            price=Decimal(str(eua_price)),
            total_value_eur=Decimal(str(eua_output * eua_price)),
            status=SettlementStatus.PENDING,
            expected_settlement_date=expected_settlement,
            notes=f"Swap {cea_quantity:.2f} CEA → {eua_output:.2f} EUA at avg rate {weighted_avg_ratio:.4f}. Matched {len(matched_orders)} orders.",
        )

        try:
            async with db.begin_nested():
                db.add(settlement)
                await db.flush()
            break  # Success
        except IntegrityError:
            if attempt < max_attempts - 1:
                logger.warning(
                    f"batch_reference collision on {batch_reference}, "
                    f"retrying (attempt {attempt + 1}/{max_attempts})"
                )
                continue
            raise

    # Add initial status history
    history_entry = SettlementStatusHistory(
        settlement_batch_id=settlement.id,
        status=SettlementStatus.PENDING,
        notes=f"Swap executed - matched {len(matched_orders)} liquidity orders",
        updated_by=current_user.id,
    )
    db.add(history_entry)

    # Update swap status
    swap.status = SwapStatus.COMPLETED
    swap.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update user role from SWAP to EUA_SETTLE
    # Note: current_user is loaded from a separate session (get_current_user) so it's
    # detached — we must query the user from this endpoint's db session to persist changes.
    from ...models.models import UserRole

    if current_user.role == UserRole.SWAP:
        user_result = await db.execute(
            select(User).where(User.id == current_user.id)
        )
        user_in_session = user_result.scalar_one_or_none()
        if user_in_session:
            user_in_session.role = UserRole.EUA_SETTLE

    await TicketService.create_ticket(
        db=db,
        action_type="SWAP_EXECUTED",
        entity_type="SwapRequest",
        entity_id=swap.id,
        status=TicketStatus.SUCCESS,
        user_id=current_user.id,
        request_payload={
            "from_type": swap.from_type.value,
            "to_type": swap.to_type.value,
            "cea_quantity": cea_quantity,
            "eua_output": eua_output,
            "weighted_avg_ratio": round(weighted_avg_ratio, 4),
            "matched_orders_count": len(matched_orders),
        },
        response_data={
            "swap_id": str(swap.id),
            "anonymous_code": swap.anonymous_code,
            "settlement_batch_id": str(settlement.id),
            "batch_reference": settlement.batch_reference,
            "status": SwapStatus.COMPLETED.value,
        },
        tags=["swap", "client"],
    )
    await db.commit()

    # Notify the user: swap completed + balance changed + role may have changed
    asyncio.create_task(client_ws_manager.broadcast_to_users(
        [current_user.id],
        {"type": "swap_updated", "data": {"swap_id": str(swap.id), "status": "COMPLETED"}},
    ))
    asyncio.create_task(client_ws_manager.broadcast_to_users(
        [current_user.id],
        {"type": "balance_updated", "data": {"source": "swap_executed"}},
    ))
    # Notify backoffice admins of new swap settlement
    asyncio.create_task(backoffice_ws_manager.broadcast(
        "new_settlement",
        {
            "batch_id": str(settlement.id),
            "batch_reference": settlement.batch_reference,
            "entity_id": str(current_user.entity_id),
            "settlement_type": SettlementType.SWAP_CEA_TO_EUA.value,
            "status": SettlementStatus.PENDING.value,
            "quantity": float(eua_output),
            "total_value_eur": float(eua_output * eua_price),
            "expected_settlement_date": expected_settlement.strftime("%Y-%m-%d"),
        },
    ))

    # Swap confirmation email (fire-and-forget)
    try:
        from ...services.email_service import email_service as _email_svc
        await _email_svc.send_swap_match_notification(
            to_email=current_user.email,
            from_type="CEA",
            to_type="EUA",
            quantity=cea_quantity,
            rate=round(weighted_avg_ratio, 4),
        )
    except Exception:
        logger.debug("Swap confirmation email failed for user %s", current_user.id)

    # Reactive auto-trade: schedule background replenishment with random 5-15s delays
    try:
        from app.api.v1.admin import _delayed_swap_replenishment

        asyncio.create_task(_delayed_swap_replenishment())
        logger.info("Swap auto-trade replenishment scheduled (background, 5-15s intervals)")
    except Exception as e:
        logger.warning(f"Failed to schedule swap replenishment: {e}")

    return {
        "success": True,
        "message": "Swap executed successfully",
        "swap_id": str(swap.id),
        "swap_reference": swap.anonymous_code,
        "from_quantity": cea_quantity,
        "to_quantity": round(eua_output, 2),
        "rate": round(weighted_avg_ratio, 4),
        "orders_matched": len(matched_orders),
        "settlement_batch_id": str(settlement.id),
        "expected_settlement_date": expected_settlement.isoformat(),
    }
