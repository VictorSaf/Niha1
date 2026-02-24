"""Ticket generation and audit logging service"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RedisManager
from app.models.models import TicketLog, TicketStatus

logger = logging.getLogger(__name__)

# Type for async broadcast callback: (event_type: str, data: dict) -> None
BroadcastCallback = Callable[[str, dict], Coroutine[Any, Any, None]]


class TicketService:
    """Service for generating ticket IDs and managing audit logs"""

    # Registered broadcast callback for pushing new tickets via WebSocket
    _broadcast_callback: Optional[BroadcastCallback] = None

    @classmethod
    def register_broadcast(cls, callback: BroadcastCallback) -> None:
        """Register a callback to broadcast new tickets (e.g., to backoffice WS)"""
        cls._broadcast_callback = callback

    @staticmethod
    async def generate_ticket_id() -> str:
        """
        Generate unique ticket ID: TKT-YYYY-NNNNNN
        Uses Redis counter for atomic increment
        """
        year = datetime.now(timezone.utc).year
        redis = await RedisManager.get_redis()

        # Atomic increment counter for this year
        counter_key = f"ticket_counter:{year}"
        counter = await redis.incr(counter_key)

        # Set expiry on first creation (end of next year)
        if counter == 1:
            await redis.expire(counter_key, 60 * 60 * 24 * 400)  # ~13 months

        ticket_id = f"TKT-{year}-{counter:06d}"
        return ticket_id

    @staticmethod
    def _is_ticket_id_collision(exc: IntegrityError) -> bool:
        """Check if IntegrityError is duplicate ticket_id (Redis counter behind DB)."""
        err_msg = str(exc.orig) if hasattr(exc, "orig") and exc.orig else str(exc)
        return "ix_ticket_logs_ticket_id" in err_msg or "UniqueViolation" in err_msg

    @staticmethod
    async def create_ticket(
        db: AsyncSession,
        action_type: str,
        entity_type: str,
        entity_id: Optional[uuid.UUID],
        status: TicketStatus,
        user_id: Optional[uuid.UUID] = None,
        market_maker_id: Optional[uuid.UUID] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        related_ticket_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> TicketLog:
        """Create audit ticket. Retries on ticket_id collision (Redis counter behind DB)."""
        max_retries = 3

        for attempt in range(max_retries):
            ticket_id = await TicketService.generate_ticket_id()
            ticket = TicketLog(
                ticket_id=ticket_id,
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                user_id=user_id,
                market_maker_id=market_maker_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                status=status,
                request_payload=request_payload,
                response_data=response_data,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                before_state=before_state,
                after_state=after_state,
                related_ticket_ids=related_ticket_ids or [],
                tags=tags or [],
            )
            db.add(ticket)

            try:
                async with db.begin_nested():
                    await db.flush()
                    await db.refresh(ticket)
            except IntegrityError as e:
                if TicketService._is_ticket_id_collision(e) and attempt < max_retries - 1:
                    logger.warning(
                        "Ticket ID collision %s (attempt %d/%d), retrying with new ID",
                        ticket_id,
                        attempt + 1,
                        max_retries,
                    )
                    continue
                raise

            logger.info(f"Created ticket {ticket_id} for {action_type} on {entity_type}")
            break

        # Broadcast to backoffice WebSocket (fire-and-forget)
        if TicketService._broadcast_callback:
            try:
                asyncio.create_task(TicketService._broadcast_callback(
                    "new_ticket",
                    {
                        "ticket_id": ticket_id,
                        "action_type": action_type,
                        "entity_type": entity_type,
                        "entity_id": str(entity_id) if entity_id else None,
                        "status": status.value,
                        "user_id": str(user_id) if user_id else None,
                        "market_maker_id": str(market_maker_id) if market_maker_id else None,
                        "tags": tags or [],
                        "timestamp": ticket.timestamp.isoformat(),
                    },
                ))
            except Exception:
                pass  # Never let broadcast failure affect ticket creation

        return ticket

    @staticmethod
    async def get_entity_state(
        db: AsyncSession, entity_type: str, entity_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """Get current state of entity for before/after tracking"""
        # Import here to avoid circular imports
        from app.models.models import AssetTransaction, MarketMakerClient, Order, User

        model_map = {
            "Order": Order,
            "User": User,
            "MarketMaker": MarketMakerClient,
            "AssetTransaction": AssetTransaction,
        }

        model = model_map.get(entity_type)
        if not model:
            return None

        result = await db.execute(select(model).where(model.id == entity_id))
        entity = result.scalar_one_or_none()

        if not entity:
            return None

        # Convert to dict, excluding relationships
        from decimal import Decimal

        state = {}
        for column in model.__table__.columns:
            value = getattr(entity, column.name)
            # Convert non-serializable types
            if isinstance(value, uuid.UUID):
                state[column.name] = str(value)
            elif isinstance(value, datetime):
                state[column.name] = value.isoformat()
            elif isinstance(value, Decimal):
                state[column.name] = float(value)
            elif isinstance(value, bytes):
                state[column.name] = None  # Don't serialize binary blobs
            elif hasattr(value, 'value'):  # Enum
                state[column.name] = value.value
            else:
                state[column.name] = value

        return state
