import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from ..core.database import Base


class Jurisdiction(str, enum.Enum):
    EU = "EU"
    CN = "CN"
    HK = "HK"
    OTHER = "OTHER"


class KYCStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserRole(str, enum.Enum):
    """Unified with ContactStatus; full onboarding flow NDA → EUA. MM = Market Maker (admin-created only). INTRODUCER = Introducer flow (no entity)."""
    ADMIN = "ADMIN"
    MM = "MM"  # Market Maker; created and managed only by admin, no contact requests
    INTRODUCER = "INTRODUCER"  # Introducer flow; approved, NDA signed, full access
    PRE_NDA = "PRE_NDA"  # Pre-NDA buyer; registered without NDA, must upload signed NDA
    PREINTRODUCER = "PREINTRODUCER"  # Pre-introducer; registered via referral code, limited access
    NDA = "NDA"
    REJECTED = "REJECTED"
    KYC = "KYC"
    APPROVED = "APPROVED"
    FUNDING = "FUNDING"
    AML = "AML"
    CEA = "CEA"
    CEA_SETTLE = "CEA_SETTLE"
    SWAP = "SWAP"
    EUA_SETTLE = "EUA_SETTLE"
    EUA = "EUA"


class DocumentType(str, enum.Enum):
    # Company Documents
    REGISTRATION = "REGISTRATION"  # Business Registration Certificate
    TAX_CERTIFICATE = "TAX_CERTIFICATE"  # Tax Registration Certificate
    ARTICLES = "ARTICLES"  # Articles of Association
    FINANCIAL_STATEMENTS = "FINANCIAL_STATEMENTS"  # Latest Financial Statements
    GHG_PERMIT = "GHG_PERMIT"  # Greenhouse Gas Emissions Permit (optional)
    # Representative Documents
    ID = "ID"  # Government-Issued ID
    PROOF_AUTHORITY = "PROOF_AUTHORITY"  # Proof of Authority / Power of Attorney
    CONTACT_INFO = "CONTACT_INFO"  # Representative Contact Information


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ScrapeStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ScrapeLibrary(str, enum.Enum):
    HTTPX = "HTTPX"
    BEAUTIFULSOUP = "BEAUTIFULSOUP"
    SELENIUM = "SELENIUM"
    PLAYWRIGHT = "PLAYWRIGHT"


class ContactStatus(str, enum.Enum):
    """Same values as UserRole where applicable; PRE_NDA, NDA, REJECTED, KYC for contact requests."""
    PRE_NDA = "PRE_NDA"
    NDA = "NDA"
    REJECTED = "REJECTED"
    KYC = "KYC"


class CertificateType(str, enum.Enum):
    EUA = "EUA"
    CEA = "CEA"


class CertificateStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"


class TradeType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SwapStatus(str, enum.Enum):
    OPEN = "open"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AuthMethod(str, enum.Enum):
    PASSWORD = "password"
    MAGIC_LINK = "magic_link"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class DepositStatus(str, enum.Enum):
    PENDING = "PENDING"  # User announced wire transfer
    CONFIRMED = "CONFIRMED"  # Backoffice confirmed receipt, now ON_HOLD
    ON_HOLD = "ON_HOLD"  # AML hold period active
    CLEARED = "CLEARED"  # AML hold passed, funds available
    REJECTED = "REJECTED"  # Wire not received or AML rejected


class HoldType(str, enum.Enum):
    """Types of AML hold periods"""

    FIRST_DEPOSIT = "FIRST_DEPOSIT"  # First deposit from entity
    SUBSEQUENT = "SUBSEQUENT"  # Regular subsequent deposit
    LARGE_AMOUNT = "LARGE_AMOUNT"  # Large amount (>500K EUR)


class AMLStatus(str, enum.Enum):
    """AML review status for deposits"""

    PENDING = "PENDING"  # Awaiting wire confirmation
    ON_HOLD = "ON_HOLD"  # Hold period active
    CLEARED = "CLEARED"  # Approved and funds released
    REJECTED = "REJECTED"  # Rejected for AML reasons


class Currency(str, enum.Enum):
    EUR = "EUR"
    USD = "USD"
    CNY = "CNY"
    HKD = "HKD"


class MarketMakerType(str, enum.Enum):
    """Types of market maker clients"""

    CEA_BUYER = "CEA_BUYER"  # Buys CEA with EUR (places BID orders)
    CEA_SELLER = "CEA_SELLER"  # Sells CEA for EUR (places ASK orders)
    EUA_OFFER = "EUA_OFFER"  # Offers EUA for swap operations


class MarketType(str, enum.Enum):
    """Trading markets"""

    CEA_CASH = "CEA_CASH"  # CEA Cash: Trade CEA with EUR
    SWAP = "SWAP"  # Swap: Exchange CEA↔EUA


class TradingFeeConfig(Base):
    """Platform-wide trading fee configuration per market.

    Defines default fees for each market, separate for buyers (BID) and sellers (ASK).
    Fees are stored as decimal rates (e.g., 0.005 = 0.5%).
    """
    __tablename__ = "trading_fee_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market = Column(SQLEnum(MarketType), nullable=False, unique=True)
    bid_fee_rate = Column(Numeric(8, 6), nullable=False, default=0.005)  # Fee for buyers (BID)
    ask_fee_rate = Column(Numeric(8, 6), nullable=False, default=0.005)  # Fee for sellers (ASK)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class EntityFeeOverride(Base):
    """Per-entity fee override for custom client rates.

    When an entity has an override for a market, their fee rate takes precedence
    over the default market rate. NULL values mean "use default".
    """
    __tablename__ = "entity_fee_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    market = Column(SQLEnum(MarketType), nullable=False)
    bid_fee_rate = Column(Numeric(8, 6), nullable=True)  # NULL = use default
    ask_fee_rate = Column(Numeric(8, 6), nullable=True)  # NULL = use default
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    entity = relationship("Entity", backref="fee_overrides")

    # Unique constraint: one override per entity per market
    __table_args__ = (UniqueConstraint('entity_id', 'market', name='uq_entity_market_fee'),)


class Entity(Base):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    jurisdiction = Column(SQLEnum(Jurisdiction), nullable=False)
    registration_number = Column(String(100))
    verified = Column(Boolean, default=False)
    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.PENDING)
    kyc_submitted_at = Column(DateTime, nullable=True)
    kyc_approved_at = Column(DateTime, nullable=True)
    kyc_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    # Balance fields - set by backoffice when confirming deposits
    balance_amount = Column(Numeric(18, 2), default=0)
    balance_currency = Column(SQLEnum(Currency), nullable=True)
    total_deposited = Column(Numeric(18, 2), default=0)  # Lifetime total deposits
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    users = relationship("User", back_populates="entity", foreign_keys="User.entity_id")
    certificates = relationship("Certificate", back_populates="entity")
    buy_trades = relationship(
        "Trade", foreign_keys="Trade.buyer_entity_id", back_populates="buyer"
    )
    sell_trades = relationship(
        "Trade", foreign_keys="Trade.seller_entity_id", back_populates="seller"
    )
    swap_requests = relationship("SwapRequest", back_populates="entity")
    kyc_documents = relationship("KYCDocument", back_populates="entity")
    deposits = relationship("Deposit", back_populates="entity")
    holdings = relationship("EntityHolding", back_populates="entity")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Optional for magic link users
    first_name = Column(String(100))
    last_name = Column(String(100))
    position = Column(String(100))
    phone = Column(String(50), nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.NDA)
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=True)
    invitation_token = Column(String(100), nullable=True)
    invitation_sent_at = Column(DateTime, nullable=True)
    invitation_expires_at = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    creation_method = Column(String(20), nullable=True)  # 'manual' or 'invitation'
    referral_code = Column(String(16), unique=True, nullable=True, index=True)
    # Per-introducer commission rate (NULL = use platform default 1%)
    commission_rate = Column(Numeric(8, 6), nullable=True)
    nda_signed = Column(Boolean, default=True, server_default="true")
    nda_file_data = Column(LargeBinary, nullable=True)
    nda_file_name = Column(String(255), nullable=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    entity = relationship("Entity", back_populates="users", foreign_keys=[entity_id])
    activity_logs = relationship("ActivityLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    kyc_documents = relationship(
        "KYCDocument", back_populates="user", foreign_keys="KYCDocument.user_id"
    )
    auth_attempts = relationship("AuthenticationAttempt", back_populates="user")
    market_maker_client = relationship(
        "MarketMakerClient",
        foreign_keys="MarketMakerClient.user_id",
        back_populates="user",
        uselist=False,
    )
    created_market_maker_clients = relationship(
        "MarketMakerClient",
        foreign_keys="MarketMakerClient.created_by",
        back_populates="creator",
    )


class MarketMakerClient(Base):
    """Market Maker client managed by admin"""

    __tablename__ = "market_maker_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)  # Display name like "MM-Alpha"
    client_code = Column(
        String(20), unique=True, nullable=False, index=True
    )  # e.g., "MM-001", "MM-002"
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    mm_type = Column(
        SQLEnum(MarketMakerType),
        default=MarketMakerType.CEA_SELLER,
        nullable=False,
    )
    eur_balance = Column(
        Numeric(18, 2), default=0, nullable=False
    )  # For Liquidity Providers
    eua_balance = Column(
        Numeric(18, 2), default=0, nullable=False
    )  # EUA balance for EUA_OFFER market makers

    @property
    def market(self) -> MarketType:
        """
        Determine which market this Market Maker operates in.

        Returns:
            MarketType.CEA_CASH for CEA_BUYER and CEA_SELLER
            MarketType.SWAP for EUA_OFFER
        """
        if self.mm_type in (
            MarketMakerType.CEA_BUYER,
            MarketMakerType.CEA_SELLER,
        ):
            return MarketType.CEA_CASH
        elif self.mm_type == MarketMakerType.EUA_OFFER:
            return MarketType.SWAP
        else:
            # Should never happen with proper enum validation
            raise ValueError(f"Unknown market maker type: {self.mm_type}")

    # Relationships
    user = relationship(
        "User", foreign_keys=[user_id], back_populates="market_maker_client"
    )
    creator = relationship(
        "User", foreign_keys=[created_by], back_populates="created_market_maker_clients"
    )
    transactions = relationship("AssetTransaction", back_populates="market_maker")
    orders = relationship("Order", back_populates="market_maker")
    auto_trade_rules = relationship("AutoTradeRule", back_populates="market_maker", cascade="all, delete-orphan")


class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=True)  # Deprecated — use first/last
    contact_first_name = Column(String(128), nullable=True)
    contact_last_name = Column(String(128), nullable=True)
    position = Column(String(100))
    nda_file_path = Column(
        String(500), nullable=True
    )  # Deprecated - kept for migration
    nda_file_name = Column(String(255), nullable=True)
    nda_file_data = Column(LargeBinary, nullable=True)  # Store PDF binary in database
    nda_file_mime_type = Column(String(100), nullable=True, default="application/pdf")
    submitter_ip = Column(String(45), nullable=True)  # IPv6 max length
    user_role = Column(SQLEnum(ContactStatus), default=ContactStatus.NDA)
    request_flow = Column(String(32), default="buyer", nullable=False)  # 'buyer' | 'introducer'
    notes = Column(Text)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    referred_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    referral_code_used = Column(String(16), nullable=True)
    nda_accepted = Column(Boolean, default=False)
    nda_accepted_at = Column(DateTime, nullable=True)
    nda_accepted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


# ─── Referral Invitation Status ───────────────────────────
class InvitationStatus(str, enum.Enum):
    PENDING = "pending"       # Sent, not yet acted on
    CLICKED = "clicked"       # Link clicked but not registered
    REGISTERED = "registered" # Recipient created an account
    EXPIRED = "expired"       # Token expired without action


class CommissionStatus(str, enum.Enum):
    PENDING = "pending"       # Accrued, not yet confirmed
    CONFIRMED = "confirmed"   # Admin confirmed, ready to pay
    PAID = "paid"             # Paid out to introducer
    REVERSED = "reversed"     # Trade reversed/cancelled


class ReferralInvitation(Base):
    """Tracks invitations sent by INTRODUCER users to potential clients."""
    __tablename__ = "referral_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    introducer_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    invited_email = Column(String(255), nullable=False, index=True)
    invited_first_name = Column(String(100), nullable=True)
    personal_note = Column(String(200), nullable=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    status = Column(
        SQLEnum(InvitationStatus),
        default=InvitationStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Outcome tracking
    clicked_at = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, nullable=True)
    registered_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    # Relationships
    introducer = relationship("User", foreign_keys=[introducer_user_id])

    __table_args__ = (
        UniqueConstraint(
            "introducer_user_id", "invited_email",
            name="uq_introducer_invite_email",
        ),
    )


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class CommissionLedger(Base):
    """Immutable commission events for introducer earnings.

    One row per qualifying CEA buy trade. Append-only: corrections
    use a REVERSED row + new corrected row, never UPDATE.
    """
    __tablename__ = "commission_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who earns the commission
    introducer_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Which referred client generated this
    referred_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    referred_entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )

    # The trade that triggered this commission
    cash_market_trade_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cash_market_trades.id"),
        nullable=False,
        unique=True,  # One commission per trade
        index=True,
    )

    # Financial snapshot at time of trade (never recalculate)
    trade_eur_value = Column(Numeric(18, 2), nullable=False)
    commission_rate = Column(Numeric(8, 6), nullable=False)  # e.g. 0.010000 = 1%
    commission_eur = Column(Numeric(18, 2), nullable=False)

    status = Column(
        SQLEnum(CommissionStatus),
        default=CommissionStatus.PENDING,
        nullable=False,
        index=True,
    )

    trade_executed_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
        index=True,
    )
    confirmed_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    notes = Column(Text, nullable=True)

    # Relationships
    introducer = relationship("User", foreign_keys=[introducer_user_id])
    referred_user = relationship("User", foreign_keys=[referred_user_id])
    trade = relationship("CashMarketTrade")


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False)
    quantity = Column(Numeric(18, 2), nullable=False)
    unit_price = Column(Numeric(18, 4), nullable=False)
    vintage_year = Column(Integer)
    status = Column(SQLEnum(CertificateStatus), default=CertificateStatus.AVAILABLE)
    anonymous_code = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    entity = relationship("Entity", back_populates="certificates")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_type = Column(SQLEnum(TradeType), nullable=False)
    buyer_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    seller_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    certificate_id = Column(UUID(as_uuid=True), ForeignKey("certificates.id"))
    certificate_type = Column(SQLEnum(CertificateType), nullable=False)
    quantity = Column(Numeric(18, 2), nullable=False)
    price_per_unit = Column(Numeric(18, 4), nullable=False)
    total_value = Column(Numeric(18, 4), nullable=False)
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.PENDING)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = Column(DateTime)

    buyer = relationship(
        "Entity", foreign_keys=[buyer_entity_id], back_populates="buy_trades"
    )
    seller = relationship(
        "Entity", foreign_keys=[seller_entity_id], back_populates="sell_trades"
    )


class SwapRequest(Base):
    __tablename__ = "swap_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    from_type = Column(SQLEnum(CertificateType), nullable=False)
    to_type = Column(SQLEnum(CertificateType), nullable=False)
    quantity = Column(Numeric(18, 2), nullable=False)
    desired_rate = Column(Numeric(10, 6))
    status = Column(SQLEnum(SwapStatus), default=SwapStatus.OPEN)
    matched_with = Column(
        UUID(as_uuid=True), ForeignKey("swap_requests.id"), nullable=True
    )
    anonymous_code = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    entity = relationship("Entity", back_populates="swap_requests")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(3), nullable=False)
    source = Column(String(100))
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)


class ActivityLog(Base):
    """Track user activity for audit and analytics"""

    __tablename__ = "activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    action = Column(
        String(100), nullable=False
    )  # login, logout, view_page, trade, etc.
    details = Column(JSON, nullable=True)  # {page: "marketplace", ip: "x.x.x.x", ...}
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    user = relationship("User", back_populates="activity_logs")


class KYCDocument(Base):
    """KYC documents uploaded by users/entities"""

    __tablename__ = "kyc_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True, index=True
    )
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", back_populates="kyc_documents", foreign_keys=[user_id])
    entity = relationship("Entity", back_populates="kyc_documents")


class ScrapingSource(Base):
    """Configuration for price scraping sources"""

    __tablename__ = "scraping_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False)
    scrape_library = Column(SQLEnum(ScrapeLibrary), default=ScrapeLibrary.HTTPX)
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)
    scrape_interval_minutes = Column(Integer, default=5)
    last_scrape_at = Column(DateTime, nullable=True)
    last_scrape_status = Column(SQLEnum(ScrapeStatus), nullable=True)
    last_price = Column(Numeric(18, 4), nullable=True)  # Raw price in source currency
    last_price_eur = Column(Numeric(18, 4), nullable=True)  # Converted EUR price (for CEA)
    last_exchange_rate = Column(Numeric(18, 8), nullable=True)  # Rate used for conversion
    config = Column(
        JSON, nullable=True
    )  # Additional scraper configuration (CSS selectors, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class ExchangeRateHistory(Base):
    """Historical exchange rate data points for charting"""

    __tablename__ = "exchange_rate_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    source = Column(String(100))
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)


class ExchangeRateSource(Base):
    """Configuration for exchange rate scraping sources"""

    __tablename__ = "exchange_rate_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    from_currency = Column(String(3), nullable=False)  # e.g., "EUR"
    to_currency = Column(String(3), nullable=False)  # e.g., "CNY"
    url = Column(String(500), nullable=False)
    scrape_library = Column(SQLEnum(ScrapeLibrary), default=ScrapeLibrary.HTTPX)
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)  # Primary source for this pair
    scrape_interval_minutes = Column(Integer, default=60)
    last_rate = Column(Numeric(18, 8), nullable=True)
    last_scraped_at = Column(DateTime, nullable=True)
    last_scrape_status = Column(SQLEnum(ScrapeStatus), nullable=True)
    config = Column(
        JSON, nullable=True
    )  # Additional scraper configuration (CSS selectors, XPath, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class UserSession(Base):
    """Track user sessions for security and analytics"""

    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    device_info = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")


class Order(Base):
    """CEA Cash market orders for trading"""

    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market = Column(SQLEnum(MarketType), nullable=False)  # NEW: Which market
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True, index=True
    )  # Buyer entity (for BUY orders)
    seller_id = Column(
        UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=True, index=True
    )  # Seller (for SELL orders)
    market_maker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("market_maker_clients.id"),
        nullable=True,
        index=True,
    )  # Market maker (for MM orders)
    ticket_id = Column(String(30), nullable=True, index=True)  # Link to audit log
    certificate_type = Column(
        SQLEnum(CertificateType), nullable=False
    )  # Still needed for SWAP
    side = Column(SQLEnum(OrderSide), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Numeric(18, 2), nullable=False)
    filled_quantity = Column(Numeric(18, 2), default=0)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.OPEN)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    entity = relationship("Entity")
    seller = relationship("Seller", back_populates="orders")
    market_maker = relationship("MarketMakerClient", back_populates="orders")
    buy_trades = relationship(
        "CashMarketTrade",
        foreign_keys="CashMarketTrade.buy_order_id",
        back_populates="buy_order",
    )
    sell_trades = relationship(
        "CashMarketTrade",
        foreign_keys="CashMarketTrade.sell_order_id",
        back_populates="sell_order",
    )


class CashMarketTrade(Base):
    """Executed trades from the CEA Cash market matching engine"""

    __tablename__ = "cash_market_trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buy_order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    sell_order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    market_maker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("market_maker_clients.id"),
        nullable=True,
        index=True,
    )
    ticket_id = Column(String(30), nullable=True, index=True)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Numeric(18, 2), nullable=False)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    buy_order = relationship(
        "Order", foreign_keys=[buy_order_id], back_populates="buy_trades"
    )
    sell_order = relationship(
        "Order", foreign_keys=[sell_order_id], back_populates="sell_trades"
    )
    market_maker = relationship("MarketMakerClient")


class AuthenticationAttempt(Base):
    """Track all authentication attempts for security and audit"""

    __tablename__ = "authentication_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    email = Column(
        String(255), nullable=False, index=True
    )  # Store email even if user doesn't exist
    success = Column(Boolean, nullable=False)
    method = Column(SQLEnum(AuthMethod), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    failure_reason = Column(
        String(255), nullable=True
    )  # 'invalid_password', 'user_not_found', 'account_disabled', etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)

    user = relationship("User", back_populates="auth_attempts")


class Seller(Base):
    """CEA sellers with unique client codes for the CEA Cash market"""

    __tablename__ = "sellers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_code = Column(
        String(20), unique=True, nullable=False, index=True
    )  # e.g., "CEA-001", "CEA-002"
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    jurisdiction = Column(SQLEnum(Jurisdiction), default=Jurisdiction.CN)
    cea_balance = Column(Numeric(18, 2), default=0)  # Available CEA for sale
    cea_sold = Column(Numeric(18, 2), default=0)  # Total CEA sold
    total_transactions = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationship to orders
    orders = relationship("Order", back_populates="seller")


class Deposit(Base):
    """Track wire transfer deposits from entities with AML hold management"""

    __tablename__ = "deposits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # User-reported deposit details (what user says they sent)
    reported_amount = Column(Numeric(18, 2), nullable=True)
    reported_currency = Column(SQLEnum(Currency), nullable=True)

    # Confirmed deposit details (what backoffice actually received)
    amount = Column(Numeric(18, 2), nullable=True)  # Actual confirmed amount
    currency = Column(SQLEnum(Currency), nullable=True)  # Actual confirmed currency
    wire_reference = Column(String(100), nullable=True)  # Bank wire reference
    bank_reference = Column(String(100), nullable=True)  # Our internal reference

    # Source bank details (provided by client)
    source_bank = Column(String(255), nullable=True)
    source_iban = Column(String(50), nullable=True)
    source_swift = Column(String(20), nullable=True)

    # Status tracking
    status = Column(SQLEnum(DepositStatus), default=DepositStatus.PENDING)

    # AML Hold fields
    hold_type = Column(
        String(50), nullable=True
    )  # FIRST_DEPOSIT, SUBSEQUENT, LARGE_AMOUNT
    hold_days_required = Column(Integer, nullable=True)
    hold_expires_at = Column(DateTime, nullable=True)
    aml_status = Column(
        String(50), nullable=True, default="PENDING"
    )  # PENDING, ON_HOLD, CLEARED, REJECTED

    # Timestamps
    reported_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )  # When user announced the wire
    confirmed_at = Column(DateTime, nullable=True)  # When backoffice confirmed receipt

    # Approval/Rejection tracking
    cleared_at = Column(DateTime, nullable=True)
    cleared_by_admin_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejected_at = Column(DateTime, nullable=True)
    rejected_by_admin_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    rejection_reason = Column(Text, nullable=True)

    # Backoffice tracking
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)  # Legacy admin notes
    admin_notes = Column(Text, nullable=True)  # Detailed admin notes
    client_notes = Column(Text, nullable=True)  # Notes from client

    # Ticket tracking
    ticket_id = Column(String(50), nullable=True)  # Ticket ID for the deposit announcement

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    entity = relationship("Entity", back_populates="deposits")
    user = relationship("User", foreign_keys=[user_id])
    confirmed_by_user = relationship("User", foreign_keys=[confirmed_by])
    cleared_by_admin = relationship("User", foreign_keys=[cleared_by_admin_id])
    rejected_by_admin = relationship("User", foreign_keys=[rejected_by_admin_id])


class AssetType(str, enum.Enum):
    """Types of assets that can be held by entities"""

    EUR = "EUR"  # Cash in EUR
    CEA = "CEA"  # China Emission Allowances
    EUA = "EUA"  # EU Allowances


class TransactionType(str, enum.Enum):
    """Types of asset transactions for audit trail"""

    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRADE_DEBIT = "TRADE_DEBIT"  # Locks assets when order placed
    TRADE_CREDIT = "TRADE_CREDIT"  # Releases assets when order cancelled/filled
    TRADE_BUY = "TRADE_BUY"  # Asset purchase transaction
    TRADE_SELL = "TRADE_SELL"  # Asset sale transaction
    ADJUSTMENT = "ADJUSTMENT"  # Admin balance adjustment


class TicketStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class EntityHolding(Base):
    """Track entity holdings of various asset types (EUR, CEA, EUA)"""

    __tablename__ = "entity_holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    asset_type = Column(SQLEnum(AssetType), nullable=False)
    quantity = Column(Numeric(18, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    entity = relationship("Entity", back_populates="holdings")

    __table_args__ = (
        # One record per entity per asset type
        {"sqlite_autoincrement": True},
    )


class AssetTransaction(Base):
    """Audit trail for all asset movements"""

    __tablename__ = "asset_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Existing fields (for backward compatibility with Entity-based transactions)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True, index=True
    )
    asset_type = Column(
        SQLEnum(AssetType), nullable=True
    )  # EUR, CEA, EUA (for Entity transactions)
    balance_before = Column(Numeric(18, 2), nullable=True)
    reference = Column(String(255), nullable=True)

    # New fields (for Market Makers system)
    ticket_id = Column(String(30), nullable=True, index=True)  # Links to TicketLog
    market_maker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("market_maker_clients.id"),
        nullable=True,
        index=True,
    )
    certificate_type = Column(SQLEnum(CertificateType), nullable=True)

    # Common fields (used by both Entity and Market Maker transactions)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(
        Numeric(18, 2), nullable=False
    )  # Positive for deposits/credits, negative for debits/withdrawals
    balance_after = Column(Numeric(18, 2), nullable=False)  # Running balance
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)

    # Relationships
    entity = relationship("Entity", foreign_keys=[entity_id])
    market_maker = relationship("MarketMakerClient", back_populates="transactions")
    creator = relationship("User", foreign_keys=[created_by])


class TicketLog(Base):
    """Comprehensive audit trail for all system actions"""

    __tablename__ = "ticket_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        String(30), unique=True, nullable=False, index=True
    )  # TKT-2026-001234
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    market_maker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("market_maker_clients.id"),
        nullable=True,
        index=True,
    )
    action_type = Column(
        String(100), nullable=False, index=True
    )  # ORDER_PLACED, MM_CREATED, etc.
    entity_type = Column(
        String(50), nullable=False, index=True
    )  # Order, MarketMaker, User, etc.
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    status = Column(SQLEnum(TicketStatus), nullable=False, index=True)
    request_payload = Column(JSONB, nullable=True)
    response_data = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("user_sessions.id"), nullable=True
    )
    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    related_ticket_ids = Column(ARRAY(String(30)), nullable=True)
    tags = Column(ARRAY(String(50)), nullable=True, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    market_maker = relationship("MarketMakerClient", foreign_keys=[market_maker_id])
    session = relationship("UserSession", foreign_keys=[session_id])


class LiquidityOperation(Base):
    """Audit trail for liquidity creation operations

    market_makers_used JSONB schema:
    [
        {
            "mm_id": "uuid-string",
            "mm_type": "CEA_BUYER" | "CEA_SELLER" | "EUA_OFFER",
            "amount": "decimal-as-string"
        },
        ...
    ]
    """

    __tablename__ = "liquidity_operations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(String(30), nullable=False, unique=True, index=True)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False, index=True)

    # Targets
    target_bid_liquidity_eur = Column(Numeric(18, 2), nullable=False)
    target_ask_liquidity_eur = Column(Numeric(18, 2), nullable=False)

    # Actuals
    actual_bid_liquidity_eur = Column(Numeric(18, 2), nullable=False)
    actual_ask_liquidity_eur = Column(Numeric(18, 2), nullable=False)

    # Execution details
    market_makers_used = Column(
        JSONB, nullable=False
    )  # [{mm_id, mm_type, amount}, ...]
    orders_created = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    reference_price = Column(Numeric(18, 4), nullable=False)

    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    notes = Column(Text, nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])


class WithdrawalStatus(str, enum.Enum):
    """Status for withdrawal requests"""

    PENDING = "PENDING"  # User requested withdrawal, awaiting admin
    PROCESSING = "PROCESSING"  # Admin approved, processing transfer
    COMPLETED = "COMPLETED"  # Withdrawal completed
    REJECTED = "REJECTED"  # Withdrawal rejected


class SettlementStatus(str, enum.Enum):
    """Settlement status progression for T+N external settlements"""

    PENDING = "PENDING"  # T+0: Order confirmed, awaiting T+1
    TRANSFER_INITIATED = "TRANSFER_INITIATED"  # T+1: Transfer started to registry
    IN_TRANSIT = "IN_TRANSIT"  # T+2: In registry processing
    AT_CUSTODY = "AT_CUSTODY"  # T+3: Arrived at Nihao custody
    SETTLED = "SETTLED"  # Final settlement completed
    FAILED = "FAILED"  # Settlement failed, requires intervention


class SettlementType(str, enum.Enum):
    """Types of settlement operations"""

    CEA_PURCHASE = "CEA_PURCHASE"  # CEA purchase from seller (T+3)
    SWAP_CEA_TO_EUA = "SWAP_CEA_TO_EUA"  # Swap CEA→EUA (CEA T+2, EUA T+5)


class SettlementBatch(Base):
    """
    Settlement batch tracking for external T+N settlements.

    Manages the complete lifecycle of certificate transfers through
    external registries with proper status tracking and audit trail.

    Timeline:
    - CEA Purchase: T+1 to T+3 business days
    - Swap CEA→EUA: CEA T+1 to T+2, EUA T+1 to T+5
    """

    __tablename__ = "settlement_batches"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_reference = Column(String(50), unique=True, nullable=False, index=True)
    # Example: "SET-2026-001234-CEA", "SET-2026-001235-EUA"

    # Ownership and linkage
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, index=True
    )
    trade_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cash_market_trades.id"),
        nullable=True,
        index=True,
    )
    counterparty_id = Column(
        UUID(as_uuid=True), nullable=True
    )  # Seller or Market Maker ID

    # Settlement details
    settlement_type = Column(SQLEnum(SettlementType), nullable=False, index=True)
    status = Column(
        SQLEnum(SettlementStatus),
        default=SettlementStatus.PENDING,
        nullable=False,
        index=True,
    )
    asset_type = Column(SQLEnum(CertificateType), nullable=False)  # CEA or EUA

    # Financial details
    quantity = Column(Numeric(18, 2), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    total_value_eur = Column(Numeric(18, 2), nullable=False)

    # Timeline tracking
    expected_settlement_date = Column(
        DateTime, nullable=False, index=True
    )  # T+1, T+3, or T+5
    actual_settlement_date = Column(DateTime, nullable=True)

    # External registry tracking
    registry_reference = Column(
        String(100), nullable=True
    )  # Reference from external registry

    # Additional info
    notes = Column(Text, nullable=True)

    # Audit timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    # Relationships
    entity = relationship("Entity", foreign_keys=[entity_id])
    order = relationship("Order", foreign_keys=[order_id])
    trade = relationship("CashMarketTrade", foreign_keys=[trade_id])
    status_history = relationship(
        "SettlementStatusHistory",
        back_populates="settlement_batch",
        cascade="all, delete-orphan",
    )


class SettlementStatusHistory(Base):
    """
    Audit trail for all settlement status changes.

    Tracks every status transition with timestamp, notes, and responsible user.
    Provides complete audit trail for regulatory compliance.
    """

    __tablename__ = "settlement_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("settlement_batches.id"),
        nullable=False,
        index=True,
    )
    status = Column(SQLEnum(SettlementStatus), nullable=False)
    notes = Column(Text, nullable=True)  # Reason for status change, admin comments
    updated_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )  # Admin who made the change
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)

    # Relationships
    settlement_batch = relationship("SettlementBatch", back_populates="status_history")
    updater = relationship("User", foreign_keys=[updated_by])


class Withdrawal(Base):
    """Track withdrawal requests from entities"""

    __tablename__ = "withdrawals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )

    # Asset details
    asset_type = Column(SQLEnum(AssetType), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)

    # Status
    status = Column(
        SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False
    )

    # Destination details (for EUR withdrawals)
    destination_bank = Column(String(255), nullable=True)
    destination_iban = Column(String(50), nullable=True)
    destination_swift = Column(String(20), nullable=True)
    destination_account_holder = Column(String(255), nullable=True)

    # Destination details (for CEA/EUA transfers)
    destination_registry = Column(String(100), nullable=True)
    destination_account_id = Column(String(100), nullable=True)

    # Reference numbers
    wire_reference = Column(String(100), nullable=True)
    internal_reference = Column(String(100), unique=True, nullable=True)

    # Rejection details
    rejection_reason = Column(Text, nullable=True)

    # Notes
    client_notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)

    # Timestamps
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)

    # Admin tracking
    processed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rejected_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Standard audit columns
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    entity = relationship("Entity", foreign_keys=[entity_id])
    user = relationship("User", foreign_keys=[user_id])
    processed_by_user = relationship("User", foreign_keys=[processed_by])
    completed_by_user = relationship("User", foreign_keys=[completed_by])
    rejected_by_user = relationship("User", foreign_keys=[rejected_by])


class AutoTradePriceMode(str, enum.Enum):
    """Price strategy for auto trade rules"""
    FIXED = "fixed"
    SPREAD_FROM_BEST = "spread_from_best"
    PERCENTAGE_FROM_MARKET = "percentage_from_market"
    RANDOM_SPREAD = "random_spread"  # Random spread between min and max, respecting 0.1 step


class AutoTradeQuantityMode(str, enum.Enum):
    """Quantity strategy for auto trade rules"""
    FIXED = "fixed"
    PERCENTAGE_OF_BALANCE = "percentage_of_balance"
    RANDOM_RANGE = "random_range"


class AutoTradeRule(Base):
    """Auto trade rules for market makers to automatically place orders"""

    __tablename__ = "auto_trade_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_maker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("market_maker_clients.id"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)

    # Order settings
    side = Column(SQLEnum(OrderSide), nullable=False)
    order_type = Column(String(20), nullable=False, default="LIMIT")  # LIMIT or MARKET

    # Price settings
    price_mode = Column(SQLEnum(AutoTradePriceMode), nullable=False, default=AutoTradePriceMode.SPREAD_FROM_BEST)
    fixed_price = Column(Numeric(18, 4), nullable=True)
    spread_from_best = Column(Numeric(18, 4), nullable=True)  # EUR spread from best bid/ask
    spread_min = Column(Numeric(18, 4), nullable=True)  # Min spread for RANDOM_SPREAD mode (in EUR)
    spread_max = Column(Numeric(18, 4), nullable=True)  # Max spread for RANDOM_SPREAD mode (in EUR)
    percentage_from_market = Column(Numeric(8, 4), nullable=True)  # Percentage offset
    max_price_deviation = Column(Numeric(8, 4), nullable=True)  # Max % deviation from scraped price allowed

    # Quantity settings
    quantity_mode = Column(SQLEnum(AutoTradeQuantityMode), nullable=False, default=AutoTradeQuantityMode.FIXED)
    fixed_quantity = Column(Numeric(18, 2), nullable=True)
    percentage_of_balance = Column(Numeric(8, 4), nullable=True)
    min_quantity = Column(Numeric(18, 2), nullable=True)  # For random range
    max_quantity = Column(Numeric(18, 2), nullable=True)  # For random range

    # Timing (supports both minutes and seconds - seconds take precedence if set)
    interval_mode = Column(String(20), nullable=False, default="fixed")  # 'fixed' or 'random'
    interval_minutes = Column(Integer, nullable=False, default=5)  # Used when interval_mode='fixed' (legacy)
    interval_min_minutes = Column(Integer, nullable=True)  # Min interval when mode='random' (legacy)
    interval_max_minutes = Column(Integer, nullable=True)  # Max interval when mode='random' (legacy)
    # Seconds-based intervals (preferred for high-frequency trading)
    interval_seconds = Column(Integer, nullable=True, default=60)  # Used when interval_mode='fixed'
    interval_min_seconds = Column(Integer, nullable=True)  # Min interval when mode='random'
    interval_max_seconds = Column(Integer, nullable=True)  # Max interval when mode='random'

    # Conditions
    min_balance = Column(Numeric(18, 2), nullable=True)  # Min balance required to place order
    max_active_orders = Column(Integer, nullable=True)  # Max concurrent orders for this rule

    # Execution tracking
    last_executed_at = Column(DateTime, nullable=True)  # When this rule last placed an order
    next_execution_at = Column(DateTime, nullable=True)  # When this rule should next execute
    execution_count = Column(Integer, default=0, nullable=False)  # Total orders placed by this rule

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    # Relationships
    market_maker = relationship("MarketMakerClient", back_populates="auto_trade_rules")


class AutoTradeSettings(Base):
    """
    Global auto-trade settings per certificate type (legacy).
    Controls target liquidity levels - auto-trade maintains liquidity at target.
    Below target: places new orders to refill.
    Above target: executes internal trades to consume excess.
    """

    __tablename__ = "auto_trade_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False, unique=True)

    # Target liquidity in EUR (total value = price * quantity for all open orders)
    target_ask_liquidity = Column(Numeric(18, 2), nullable=True)  # Target EUR value on SELL side
    target_bid_liquidity = Column(Numeric(18, 2), nullable=True)  # Target EUR value on BUY side

    # Enable/disable liquidity management
    liquidity_limit_enabled = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class AutoTradeMarketSettings(Base):
    """
    Per-market-side auto-trade settings.
    Markets: CEA_BID (buyers), CEA_ASK (sellers), EUA_SWAP (swappers)

    Controls:
    - Target liquidity level
    - Price deviation from best price
    - Average number of orders
    - Min order volume
    - Volume variety (1-10 scale)
    """

    __tablename__ = "auto_trade_market_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_key = Column(String(20), nullable=False, unique=True)  # 'CEA_BID', 'CEA_ASK', 'EUA_SWAP'

    # Enable/disable this market's auto-trade
    enabled = Column(Boolean, default=True, nullable=False)

    # Target liquidity in EUR
    target_liquidity = Column(Numeric(18, 2), nullable=True)

    # Price deviation from best price (percentage, e.g., 0.5 = 0.5%)
    price_deviation_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("0.5"))

    # Average number of orders to maintain in the book
    avg_order_count = Column(Integer, nullable=False, default=10)

    # Minimum volume per order in EUR
    min_order_volume_eur = Column(Numeric(18, 2), nullable=False, default=Decimal("1000"))

    # Volume variety indicator (1-10)
    # 1 = orders close to min volume (uniform)
    # 10 = very diverse order sizes
    volume_variety = Column(Integer, nullable=False, default=5)

    # Avg order count variation (percentage ±)
    avg_order_count_variation_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("10.0"))

    # Max orders per price level
    max_orders_per_price_level = Column(Integer, nullable=False, default=3)

    # Max orders per price level variation (percentage ±)
    max_orders_per_level_variation_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("10.0"))

    # Min order value variation (percentage ±)
    min_order_value_variation_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("10.0"))

    # Order placement interval in seconds
    interval_seconds = Column(Integer, nullable=False, default=60)

    # Order interval variation (percentage ±)
    order_interval_variation_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("10.0"))

    # Max order volume in EUR (single order cap)
    max_order_volume_eur = Column(Numeric(18, 2), nullable=True)

    # Max liquidity threshold in EUR - if exceeded, execute internal trades to reduce
    max_liquidity_threshold = Column(Numeric(18, 2), nullable=True)

    # Average spread (EUR for cash, ratio for swap) — used by algorithm for order placement
    avg_spread = Column(Numeric(10, 4), nullable=True)
    # Tick size / minimum price increment (EUR for cash, ratio for swap) — used for price rounding
    tick_size = Column(Numeric(10, 4), nullable=True)
    # Price alignment (P2) — correction toward scraped price
    alignment_correction_factor = Column(Numeric(5, 2), nullable=False, default=Decimal("0.60"))
    # Ticks away from ideal before P2 alignment triggers
    alignment_threshold_ticks = Column(Integer, nullable=False, default=2)
    # Depth levels scanned for P3 level rebalancing
    level_rebalance_depth = Column(Integer, nullable=False, default=5)

    # Internal trade settings (when liquidity is at target)
    # Interval in seconds for internal trades
    internal_trade_interval = Column(Integer, nullable=True)
    # Min volume per internal trade in EUR
    internal_trade_volume_min = Column(Numeric(18, 2), nullable=True)
    # Max volume per internal trade in EUR
    internal_trade_volume_max = Column(Numeric(18, 2), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class MailProvider(str, enum.Enum):
    RESEND = "resend"
    SMTP = "smtp"


class MailConfig(Base):
    """
    Admin-configurable mail and invitation settings (single row).
    When present, email_service uses this instead of env; otherwise env fallback.
    """

    __tablename__ = "mail_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(
        SQLEnum(MailProvider), nullable=False, default=MailProvider.RESEND
    )
    # Use RESEND_API_KEY / SMTP from env
    use_env_credentials = Column(Boolean, default=True)
    from_email = Column(String(255), nullable=False)
    # Used when use_env_credentials=False
    resend_api_key = Column(String(500), nullable=True)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_use_tls = Column(Boolean, default=True)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(String(500), nullable=True)
    invitation_subject = Column(String(255), nullable=True)
    invitation_body_html = Column(Text, nullable=True)
    invitation_link_base_url = Column(String(500), nullable=True)
    app_base_url = Column(String(500), nullable=True)
    invitation_token_expiry_days = Column(Integer, default=7)
    # Placeholder: magic_link, password_only
    verification_method = Column(String(50), nullable=True)
    # Placeholder for auth options
    auth_method = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AlertDirection(str, enum.Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"


class PriceAlert(Base):
    """User-configured price alert: fires when price crosses target in given direction."""

    __tablename__ = "price_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    certificate_type = Column(SQLEnum(CertificateType), nullable=False)
    direction = Column(SQLEnum(AlertDirection), nullable=False)
    target_price = Column(Numeric(18, 4), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    user = relationship("User", foreign_keys=[user_id])
