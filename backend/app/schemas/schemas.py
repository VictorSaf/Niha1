from datetime import datetime
from decimal import Decimal
from enum import Enum
from html import escape
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def sanitize_string(value: Optional[str]) -> Optional[str]:
    """Strip and escape HTML from user input to prevent XSS"""
    if value is None:
        return None
    # Strip whitespace and escape HTML entities
    return escape(value.strip())


def _coerce_certificate_quantity(value: Any) -> int:
    """Coerce CEA/EUA quantity to integer (whole certificates only)."""
    if value is None:
        raise ValueError("Quantity is required")
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a number")
    if n != int(round(n)) or n <= 0:
        raise ValueError("CEA/EUA quantity must be a positive integer")
    return int(round(n))


def _coerce_certificate_quantity_optional(value: Any) -> Optional[int]:
    """Coerce optional CEA/EUA quantity to integer."""
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a number")
    if n != int(round(n)) or n <= 0:
        raise ValueError("CEA/EUA quantity must be a positive integer")
    return int(round(n))


# Enums
class Jurisdiction(str, Enum):
    EU = "EU"
    CN = "CN"
    HK = "HK"
    OTHER = "OTHER"


class UserRole(str, Enum):
    """Unified with ContactStatus; full onboarding flow NDA → EUA. MM = Market Maker (admin-created only). INTRODUCER = Introducer flow (no entity)."""
    ADMIN = "ADMIN"
    MM = "MM"  # Market Maker; created and managed only by admin, no contact requests
    INTRODUCER = "INTRODUCER"  # Introducer flow; no entity, simplified dashboard
    PREINTRODUCER = "PREINTRODUCER"  # Pre-introducer; registered via referral code
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


class CertificateType(str, Enum):
    EUA = "EUA"
    CEA = "CEA"


class CertificateStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"


class SwapStatus(str, Enum):
    OPEN = "open"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order execution type"""

    MARKET = "MARKET"  # Execute immediately at best available price
    LIMIT = "LIMIT"  # Place in order book at specified price


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class TradeStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DocumentType(str, Enum):
    REGISTRATION = "REGISTRATION"
    ID = "ID"
    PROOF_ADDRESS = "PROOF_ADDRESS"
    BANK_STATEMENT = "BANK_STATEMENT"
    ARTICLES = "ARTICLES"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ScrapeLibrary(str, Enum):
    HTTPX = "HTTPX"
    BEAUTIFULSOUP = "BEAUTIFULSOUP"
    SELENIUM = "SELENIUM"
    PLAYWRIGHT = "PLAYWRIGHT"


# Contact Request Schemas
class ContactRequestCreate(BaseModel):
    entity_name: str = Field(..., min_length=2, max_length=255, description="Legal name of the company")
    contact_email: EmailStr
    contact_name: Optional[str] = Field(None, max_length=255, description="Full name (deprecated, use first/last)")  # Deprecated
    contact_first_name: Optional[str] = Field(None, max_length=128, description="Contact person first name")
    contact_last_name: Optional[str] = Field(None, max_length=128, description="Contact person last name")
    position: Optional[str] = Field(None, max_length=100, description="Job title or position")

    @field_validator(
        "entity_name", "contact_name", "contact_first_name", "contact_last_name", "position",
        mode="before",
    )
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class ContactRequestResponse(BaseModel):
    """Contact request; client/request state is ONLY user_role (NDA, KYC, REJECTED). Do not use request_type."""

    id: UUID
    entity_name: str
    contact_email: str
    contact_name: Optional[str] = None  # Deprecated
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    position: Optional[str]
    nda_file_name: Optional[str]
    submitter_ip: Optional[str] = None
    user_role: str  # Sole source for request state; values NDA, KYC, REJECTED
    request_flow: str = "buyer"  # 'buyer' | 'introducer'
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# User Schemas (defined first for forward reference)
class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    position: Optional[str]
    phone: Optional[str]
    role: str
    entity_id: Optional[UUID]
    is_active: bool = True
    must_change_password: bool = False
    nda_signed: bool = True
    referral_code: Optional[str] = None
    last_login: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Extended user info for admin views"""

    entity_name: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User last name")
    password: Optional[str] = Field(
        None, min_length=8, description="Password; omit to send invitation email"
    )  # Optional - if not provided, send invitation
    role: UserRole = UserRole.NDA
    entity_id: Optional[UUID] = None
    position: Optional[str] = None

    @field_validator("first_name", "last_name", "position", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100, description="User first name")
    last_name: Optional[str] = Field(None, max_length=100, description="User last name")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    position: Optional[str] = Field(None, max_length=100, description="Job title or position")

    @field_validator("first_name", "last_name", "phone", "position", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current password for verification")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class UserRoleUpdate(BaseModel):
    role: UserRole


# Auth Schemas
class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkVerify(BaseModel):
    token: str


class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, description="User password")


class SetupPasswordRequest(BaseModel):
    """Request body for password setup from invitation link."""
    token: str
    password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    confirm_password: str = Field(..., min_length=8, description="Must match password field")


class ResetPasswordRequest(BaseModel):
    """Request body for admin reset operations requiring password confirmation."""
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    position: Optional[str] = None


# Entity Schemas
class EntityResponse(BaseModel):
    id: UUID
    name: str
    legal_name: Optional[str]
    jurisdiction: str
    verified: bool
    kyc_status: str

    class Config:
        from_attributes = True


# Certificate Schemas (CEA/EUA quantities are integers only)
class CertificateCreate(BaseModel):
    certificate_type: CertificateType
    quantity: int = Field(..., gt=0, description="Whole certificates only")
    unit_price: float = Field(..., gt=0, description="Price per certificate in EUR")
    vintage_year: Optional[int] = Field(None, ge=2020, le=2030, description="Certificate vintage year (2020-2030)")

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> int:
        return _coerce_certificate_quantity(v)


class CertificateResponse(BaseModel):
    id: UUID
    anonymous_code: str
    certificate_type: str
    quantity: int
    unit_price: float
    vintage_year: Optional[int]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MarketplaceListing(BaseModel):
    anonymous_code: str
    certificate_type: str
    quantity: int
    unit_price: float
    vintage_year: Optional[int]
    created_at: datetime


# Trade Schemas (CEA/EUA quantities are integers only)
class TradeCreate(BaseModel):
    certificate_id: UUID
    quantity: int = Field(..., gt=0, description="Number of certificates to trade")

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> int:
        return _coerce_certificate_quantity(v)


class TradeResponse(BaseModel):
    id: UUID
    trade_type: str
    certificate_type: str
    quantity: int
    price_per_unit: float
    total_value: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# Swap Schemas (CEA/EUA quantities are integers only)
class SwapCreate(BaseModel):
    from_type: CertificateType
    to_type: CertificateType
    quantity: int = Field(..., gt=0, description="Number of certificates to swap")
    desired_rate: Optional[float] = Field(None, gt=0, description="Desired CEA/EUA exchange ratio")

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> int:
        return _coerce_certificate_quantity(v)


class SwapResponse(BaseModel):
    id: UUID
    anonymous_code: str
    from_type: str
    to_type: str
    quantity: int
    desired_rate: Optional[float]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# Price Schemas
class PriceData(BaseModel):
    certificate_type: str
    price: float
    currency: str
    change_24h: Optional[float] = None
    source: str
    updated_at: datetime


class PriceResponse(BaseModel):
    eua: PriceData
    cea: PriceData
    swap_rate: float  # CEA per EUA


class PriceHistoryItem(BaseModel):
    price: float
    recorded_at: datetime


class PriceHistoryResponse(BaseModel):
    certificate_type: str
    currency: str
    data: List[PriceHistoryItem]


# Dashboard Schemas (CEA/EUA volumes are integers only)
class PortfolioSummary(BaseModel):
    total_eua: int
    total_cea: int
    total_value_usd: float
    pending_swaps: int
    completed_trades: int


class DashboardStats(BaseModel):
    portfolio: PortfolioSummary
    recent_trades: List[TradeResponse]
    active_swaps: List[SwapResponse]
    market_prices: PriceResponse


# Admin Schemas
VALID_CONTACT_STATUS = frozenset({"NDA", "REJECTED", "KYC"})


class ContactRequestUpdate(BaseModel):
    user_role: Optional[str] = None
    notes: Optional[str] = None
    agent_id: Optional[UUID] = None

    @field_validator("user_role")
    @classmethod
    def validate_user_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_CONTACT_STATUS:
            raise ValueError(
                f"user_role must be one of {sorted(VALID_CONTACT_STATUS)}"
            )
        return v


class EntityKYCUpdate(BaseModel):
    kyc_status: str
    notes: Optional[str] = None

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


# Generic Response
class MessageResponse(BaseModel):
    message: str
    success: bool = True


# Activity Log Schemas
class ActivityLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    action: str
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityStatsResponse(BaseModel):
    total_users: int
    users_by_role: Dict[str, int]
    active_sessions: int
    logins_today: int
    avg_session_duration: float


# KYC Document Schemas
class KYCDocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    entity_id: Optional[UUID]
    document_type: str
    file_name: str
    status: str
    reviewed_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class KYCDocumentReview(BaseModel):
    status: DocumentStatus
    notes: Optional[str] = None


# Scraping Source Schemas
class ScrapingSourceResponse(BaseModel):
    id: UUID
    name: str
    url: str
    certificate_type: str
    scrape_library: Optional[str] = "HTTPX"
    is_active: bool
    is_primary: bool = False
    scrape_interval_minutes: int
    last_scrape_at: Optional[datetime]
    last_scrape_status: Optional[str]
    last_price: Optional[float]
    last_price_eur: Optional[float] = None
    last_exchange_rate: Optional[float] = None
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScrapingSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    scrape_library: Optional[ScrapeLibrary] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    scrape_interval_minutes: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class ScrapingSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the scraping source")
    url: str = Field(..., min_length=1, max_length=500, description="URL to scrape prices from")
    certificate_type: CertificateType
    scrape_library: ScrapeLibrary = ScrapeLibrary.HTTPX
    scrape_interval_minutes: int = Field(5, ge=1, le=60, description="Minutes between scrape attempts")
    is_primary: bool = False
    config: Optional[Dict[str, Any]] = None


# Exchange Rate Source Schemas
class ExchangeRateSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the rate source")
    from_currency: str = Field(..., min_length=3, max_length=3, description="Source currency code (e.g. CNY)")
    to_currency: str = Field(..., min_length=3, max_length=3, description="Target currency code (e.g. EUR)")
    url: str = Field(..., min_length=1, max_length=500, description="URL to scrape exchange rates from")
    scrape_library: ScrapeLibrary = ScrapeLibrary.HTTPX
    scrape_interval_minutes: int = Field(60, ge=1, le=1440, description="Minutes between scrape attempts")
    is_primary: bool = False
    config: Optional[Dict[str, Any]] = None


class ExchangeRateSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Display name for the rate source")
    url: Optional[str] = Field(None, min_length=1, max_length=500, description="URL to scrape exchange rates from")
    scrape_library: Optional[ScrapeLibrary] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    scrape_interval_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Minutes between scrape attempts")
    config: Optional[Dict[str, Any]] = None


# Mail config (admin Settings)
class MailProvider(str, Enum):
    RESEND = "resend"
    SMTP = "smtp"


class MailConfigResponse(BaseModel):
    id: UUID
    provider: str
    use_env_credentials: bool
    from_email: str
    resend_api_key: Optional[str] = None  # Masked in API if present
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_use_tls: bool
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # Never returned; use placeholder
    invitation_subject: Optional[str] = None
    invitation_body_html: Optional[str] = None
    invitation_link_base_url: Optional[str] = None
    invitation_token_expiry_days: int
    verification_method: Optional[str] = None
    auth_method: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MailConfigUpdate(BaseModel):
    provider: Optional[MailProvider] = None
    use_env_credentials: Optional[bool] = None
    from_email: Optional[str] = Field(None, max_length=255, description="Sender email address")
    resend_api_key: Optional[str] = Field(None, max_length=500, description="API key for Resend mail provider")
    smtp_host: Optional[str] = Field(None, max_length=255, description="SMTP server hostname")
    smtp_port: Optional[int] = Field(None, ge=1, le=65535, description="SMTP server port number")
    smtp_use_tls: Optional[bool] = None
    smtp_username: Optional[str] = Field(None, max_length=255, description="SMTP authentication username")
    smtp_password: Optional[str] = Field(None, max_length=500, description="SMTP authentication password")
    invitation_subject: Optional[str] = Field(None, max_length=255, description="Email subject for invitation emails")
    invitation_body_html: Optional[str] = None
    invitation_link_base_url: Optional[str] = Field(None, max_length=500, description="Base URL for invitation links (legacy; prefer app_base_url)")
    app_base_url: Optional[str] = Field(None, max_length=500, description="Application base URL used in all generated links (emails, QR codes, etc.)")
    invitation_token_expiry_days: Optional[int] = Field(None, ge=1, le=365, description="Days before invitation token expires")
    verification_method: Optional[str] = Field(None, max_length=50, description="Email verification method")
    auth_method: Optional[str] = Field(None, max_length=50, description="Email authentication method")

    @field_validator("invitation_link_base_url", "app_base_url")
    @classmethod
    def url_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        v = v.rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


# User Session Schemas
class UserSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    ip_address: Optional[str]
    user_agent: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


# Onboarding Schemas
class OnboardingStatusResponse(BaseModel):
    documents_uploaded: int
    documents_required: int
    documents: List[KYCDocumentResponse]
    can_submit: bool
    status: str  # pending, submitted, approved, rejected


# Backoffice Schemas
class UserApprovalRequest(BaseModel):
    reason: Optional[str] = None


class PendingUserResponse(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    entity_name: Optional[str]
    documents_count: int
    submitted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# Paginated Response
class PaginatedResponse(BaseModel):
    data: List[Any]
    pagination: Dict[str, int]


# CEA Cash Market Order Schemas (CEA quantities are integers only)
class OrderCreate(BaseModel):
    certificate_type: CertificateType
    side: OrderSide
    price: float = Field(..., gt=0, description="Order price in EUR per certificate")
    quantity: int = Field(..., gt=0, description="Whole CEA certificates only")

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> int:
        return _coerce_certificate_quantity(v)


class OrderResponse(BaseModel):
    id: UUID
    entity_id: UUID
    certificate_type: str
    side: str
    price: float
    quantity: int
    filled_quantity: int
    remaining_quantity: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class OrderBookLevel(BaseModel):
    price: float
    quantity: int
    order_count: int
    cumulative_quantity: int


# =============================================================================
# Order Preview and Execution Schemas
# =============================================================================


class OrderFill(BaseModel):
    """Single fill from the order book (CEA quantity is integer)"""

    seller_code: str
    price: float
    quantity: int
    cost: float


class OrderPreviewRequest(BaseModel):
    """Request to preview an order before execution"""

    certificate_type: CertificateType
    side: OrderSide
    amount_eur: Optional[float] = Field(
        None, gt=0, description="Amount in EUR to spend (for BUY)"
    )
    quantity: Optional[int] = Field(None, gt=0, description="Quantity to buy/sell (whole CEA only)")
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = Field(
        None, gt=0, description="Limit price (required for LIMIT orders)"
    )
    all_or_none: bool = Field(
        False, description="Only execute if entire order can be filled"
    )

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> Optional[int]:
        return _coerce_certificate_quantity_optional(v)


class OrderPreviewResponse(BaseModel):
    """Response with preview of order execution (CEA quantities are integers)"""

    certificate_type: str
    side: str
    order_type: str

    # Input parameters
    amount_eur: Optional[float] = None
    quantity_requested: Optional[int] = None
    limit_price: Optional[float] = None
    all_or_none: bool = False

    # Calculated fills
    fills: List[OrderFill] = []
    total_quantity: int
    total_cost_gross: float  # Before fees

    # Price analysis
    weighted_avg_price: float  # Average price per certificate
    best_price: Optional[float] = None  # Best price in order book
    worst_price: Optional[float] = None  # Worst price we'd pay

    # Fee breakdown (platform fee: 0.5%)
    platform_fee_rate: float = 0.005
    platform_fee_amount: float
    total_cost_net: float  # After fees (what user actually pays)
    net_price_per_unit: float  # Net price per certificate including fees

    # Balance info
    available_balance: float
    remaining_balance: float

    # Execution status
    can_execute: bool
    execution_message: str
    partial_fill: bool = False  # True if order would only partially fill
    will_be_placed_in_book: bool = False  # True for LIMIT orders that will wait in order book


class MarketOrderRequest(BaseModel):
    """Request to execute a market order"""

    certificate_type: CertificateType
    side: OrderSide
    amount_eur: Optional[float] = Field(
        None, gt=0, description="Amount in EUR to spend (for BUY)"
    )
    quantity: Optional[int] = Field(None, gt=0, description="Quantity to buy/sell (whole CEA only)")
    all_or_none: bool = Field(
        False, description="Only execute if entire order can be filled"
    )

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> Optional[int]:
        return _coerce_certificate_quantity_optional(v)


class LimitOrderRequest(BaseModel):
    """Request to place a limit order"""

    certificate_type: CertificateType
    side: OrderSide
    price: float = Field(..., gt=0, description="Limit price")
    quantity: int = Field(..., gt=0, description="Quantity to buy/sell (whole CEA only)")
    all_or_none: bool = Field(
        False, description="Only execute if entire order can be filled"
    )

    @field_validator("quantity", mode="before")
    @classmethod
    def quantity_int(cls, v: Any) -> int:
        return _coerce_certificate_quantity(v)


class OrderExecutionResponse(BaseModel):
    """Response after order execution (CEA quantities are integers)"""

    success: bool
    order_id: Optional[UUID] = None
    message: str

    # Execution details
    certificate_type: str
    side: str
    order_type: str

    # What was filled
    total_quantity: int
    total_cost_gross: float
    platform_fee: float
    total_cost_net: float
    weighted_avg_price: float

    # Trade breakdown
    trades: List[OrderFill] = []

    # Updated balances
    eur_balance: float
    certificate_balance: int


class OrderBookResponse(BaseModel):
    certificate_type: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    spread: Optional[float]
    best_bid: Optional[float]
    best_ask: Optional[float]
    last_price: Optional[float]
    volume_24h: int
    change_24h: float
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None


class MarketDepthPoint(BaseModel):
    price: float
    cumulative_quantity: int


class MarketDepthResponse(BaseModel):
    certificate_type: str
    bids: List[MarketDepthPoint]
    asks: List[MarketDepthPoint]


class CashMarketTradeResponse(BaseModel):
    id: UUID
    certificate_type: str
    price: float
    quantity: int
    side: str  # BUY if taker was buyer, SELL if taker was seller
    executed_at: datetime

    class Config:
        from_attributes = True


class OHLCCandle(BaseModel):
    time: int  # Unix seconds (bucket start)
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketStatsResponse(BaseModel):
    certificate_type: str
    last_price: float
    change_24h: float
    high_24h: float
    low_24h: float
    volume_24h: int
    total_bids: int
    total_asks: int


# Authentication History Schemas
class AuthMethod(str, Enum):
    PASSWORD = "password"
    MAGIC_LINK = "magic_link"


class AuthenticationAttemptResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    email: str
    success: bool
    method: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    failure_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Admin User Management Schemas
class AdminUserFullResponse(UserResponse):
    """Full user details for admin - includes auth history and stats"""

    entity_name: Optional[str] = None
    password_set: bool = (
        False  # Indicates if user has password (NOT the actual password)
    )
    login_count: int = 0
    last_login_ip: Optional[str] = None
    failed_login_count_24h: int = 0
    sessions: List[UserSessionResponse] = []
    auth_history: List[AuthenticationAttemptResponse] = []


class AdminUserUpdate(BaseModel):
    """Schema for admin to update any user field"""

    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100, description="User first name")
    last_name: Optional[str] = Field(None, max_length=100, description="User last name")
    position: Optional[str] = Field(None, max_length=100, description="Job title or position")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    entity_id: Optional[UUID] = None


class AdminPasswordReset(BaseModel):
    """Admin can reset user password"""

    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    force_change: bool = True  # Force user to change on next login


# Deposit Schemas
class DepositStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ON_HOLD = "on_hold"
    CLEARED = "cleared"
    REJECTED = "rejected"


class HoldType(str, Enum):
    """Types of AML hold periods"""

    FIRST_DEPOSIT = "FIRST_DEPOSIT"
    SUBSEQUENT = "SUBSEQUENT"
    LARGE_AMOUNT = "LARGE_AMOUNT"


class AMLStatus(str, Enum):
    """AML review status"""

    PENDING = "PENDING"
    ON_HOLD = "ON_HOLD"
    CLEARED = "CLEARED"
    REJECTED = "REJECTED"


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    CNY = "CNY"
    HKD = "HKD"


class DepositCreate(BaseModel):
    """Backoffice creates deposit when confirming wire transfer"""

    entity_id: UUID
    amount: float = Field(..., gt=0, description="Deposit amount in specified currency")
    currency: Currency
    wire_reference: Optional[str] = Field(None, max_length=100, description="Bank wire reference number")
    notes: Optional[str] = None


class UserDepositReport(BaseModel):
    """User reports a wire transfer they've made (APPROVED users only)"""

    amount: float = Field(..., gt=0, description="Amount sent in wire transfer")
    currency: Currency = Field(..., description="Currency of wire transfer")
    wire_reference: Optional[str] = Field(
        None, max_length=100, description="Bank wire reference number"
    )


class DepositConfirm(BaseModel):
    """Backoffice confirms a pending deposit with actual received amount"""

    amount: float = Field(..., gt=0, description="Actual amount received")
    currency: Currency = Field(..., description="Actual currency received")
    notes: Optional[str] = Field(None, description="Admin notes")


class DepositResponse(BaseModel):
    id: UUID
    entity_id: UUID
    reported_amount: Optional[float] = None
    reported_currency: Optional[str] = None
    amount: Optional[float] = None  # Confirmed amount
    currency: Optional[str] = None  # Confirmed currency
    wire_reference: Optional[str] = None
    bank_reference: Optional[str] = None
    status: str
    reported_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EntityBalanceResponse(BaseModel):
    """Entity balance info for dashboard/backoffice"""

    entity_id: UUID
    entity_name: str
    balance_amount: float
    balance_currency: Optional[str]
    total_deposited: float
    deposit_count: int


class DepositWithEntityResponse(DepositResponse):
    """Deposit with entity details for backoffice list"""

    entity_name: Optional[str] = None
    user_email: Optional[str] = None


# =============================================================================
# Enhanced Deposit Schemas for AML Hold Management
# =============================================================================


class DepositAnnouncementRequest(BaseModel):
    """Client announces incoming wire transfer"""

    amount: float = Field(..., gt=0, description="Amount being sent")
    currency: Currency = Field(..., description="Currency of wire transfer")
    source_bank: str = Field(
        ..., min_length=2, max_length=255, description="Name of sending bank"
    )
    source_iban: Optional[str] = Field(
        None, max_length=50, description="IBAN of source account"
    )
    source_swift: Optional[str] = Field(
        None, max_length=20, description="SWIFT/BIC of source bank"
    )
    wire_reference: Optional[str] = Field(
        None, max_length=100, description="Wire transfer reference"
    )
    notes: Optional[str] = Field(None, description="Additional notes from client")

    @field_validator("source_bank", "source_iban", "source_swift", "wire_reference", "notes", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class WireInstructions(BaseModel):
    """Bank wire instructions for deposit"""

    bank_name: str = "Nihao Group Bank Partner"
    account_name: str = "Nihao Carbon Trading Ltd"
    iban: str = "DE89370400440532013000"
    swift: str = "COBADEFFXXX"
    reference_prefix: str
    instructions: str = "Please include the reference in your wire transfer"


class DepositAnnouncementResponse(BaseModel):
    """Response after client announces deposit"""

    deposit_id: UUID
    wire_instructions: WireInstructions
    expected_hold_type: HoldType
    expected_hold_days: int
    message: str


class DepositConfirmRequest(BaseModel):
    """Admin confirms wire receipt"""

    actual_amount: float = Field(..., gt=0, description="Actual amount received")
    actual_currency: Currency = Field(..., description="Actual currency received")
    received_at: Optional[datetime] = Field(
        None, description="When wire was received (defaults to now)"
    )
    admin_notes: Optional[str] = Field(None, description="Admin notes")

    @field_validator("admin_notes", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class DepositApproveRequest(BaseModel):
    """Admin approves deposit after AML hold"""

    admin_notes: Optional[str] = Field(None, description="Approval notes")

    @field_validator("admin_notes", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class RejectionReason(str, Enum):
    """Standard rejection reasons"""

    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    INCOMPLETE_KYC = "INCOMPLETE_KYC"
    AML_COMPLIANCE_CONCERN = "AML_COMPLIANCE_CONCERN"
    SOURCE_OF_FUNDS_UNCLEAR = "SOURCE_OF_FUNDS_UNCLEAR"
    WIRE_NOT_RECEIVED = "WIRE_NOT_RECEIVED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    OTHER = "OTHER"


class DepositRejectRequest(BaseModel):
    """Admin rejects deposit"""

    reason: RejectionReason = Field(..., description="Rejection reason category")
    reason_details: str = Field(..., min_length=10, description="Detailed explanation")
    admin_notes: Optional[str] = Field(None, description="Internal admin notes")

    @field_validator("reason_details", "admin_notes", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class DepositDetailResponse(BaseModel):
    """Full deposit details for review"""

    id: UUID
    entity_id: UUID
    entity_name: str
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None

    # Reported by client
    reported_amount: Optional[float] = None
    reported_currency: Optional[str] = None
    source_bank: Optional[str] = None
    source_iban: Optional[str] = None
    source_swift: Optional[str] = None
    wire_reference: Optional[str] = None
    client_notes: Optional[str] = None

    # Confirmed by admin
    amount: Optional[float] = None
    currency: Optional[str] = None
    bank_reference: Optional[str] = None

    # Status
    status: DepositStatus
    aml_status: Optional[AMLStatus] = None
    hold_type: Optional[HoldType] = None
    hold_days_required: Optional[int] = None
    hold_expires_at: Optional[datetime] = None

    # Timestamps
    reported_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None

    # Admin info
    confirmed_by: Optional[UUID] = None
    confirmed_by_name: Optional[str] = None
    cleared_by_admin_id: Optional[UUID] = None
    cleared_by_name: Optional[str] = None
    rejected_by_admin_id: Optional[UUID] = None
    rejected_by_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    admin_notes: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DepositListFilters(BaseModel):
    """Filters for admin deposit list"""

    status: Optional[DepositStatus] = None
    aml_status: Optional[AMLStatus] = None
    entity_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    search: Optional[str] = Field(
        None, description="Search by entity name, email, wire ref"
    )


class MyDepositResponse(BaseModel):
    """Deposit info for client view"""

    id: UUID
    reported_amount: float
    reported_currency: str
    status: DepositStatus
    aml_status: Optional[str] = None
    hold_type: Optional[str] = None
    hold_expires_at: Optional[datetime] = None
    reported_at: datetime
    confirmed_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class HoldCalculationResult(BaseModel):
    """Result of hold period calculation"""

    hold_type: HoldType
    hold_days: int
    reason: str


# =============================================================================
# Asset Management Schemas (EUR, CEA, EUA)
# =============================================================================


class AssetTypeEnum(str, Enum):
    """Types of assets that can be held by entities"""

    EUR = "EUR"
    CEA = "CEA"
    EUA = "EUA"


class MarketMakerTypeEnum(str, Enum):
    """Types of market makers"""

    CEA_BUYER = "CEA_BUYER"
    CEA_SELLER = "CEA_SELLER"
    EUA_OFFER = "EUA_OFFER"


class TransactionTypeEnum(str, Enum):
    """Types of asset transactions"""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    ADJUSTMENT = "adjustment"


class AddAssetRequest(BaseModel):
    """Request to deposit or withdraw assets for an entity. CEA/EUA amounts are whole numbers only."""

    asset_type: AssetTypeEnum
    amount: float = Field(..., gt=0, description="Amount (positive); sign determined by operation. Integer when asset_type is CEA or EUA.")
    operation: Literal["deposit", "withdraw"] = Field(
        default="deposit", description="Deposit adds to balance, withdraw subtracts"
    )
    reference: Optional[str] = Field(
        None, max_length=100, description="External reference"
    )
    notes: Optional[str] = Field(None, description="Admin notes")

    @model_validator(mode="after")
    def cea_eua_amount_integer(self) -> "AddAssetRequest":
        if self.asset_type in (AssetTypeEnum.CEA, AssetTypeEnum.EUA):
            if self.amount != int(round(self.amount)):
                raise ValueError("CEA and EUA amounts must be whole numbers (no fractional certificates)")
        return self


class EntityHoldingResponse(BaseModel):
    """Single asset holding for an entity. CEA/EUA quantity is integer."""

    entity_id: UUID
    asset_type: str
    quantity: float  # API passes int for CEA/EUA, float for EUR
    updated_at: datetime

    class Config:
        from_attributes = True


class AssetTransactionResponse(BaseModel):
    """Asset transaction record for audit trail. CEA/EUA amount and balances are integers."""

    id: UUID
    entity_id: UUID
    asset_type: str
    transaction_type: str
    amount: float  # API passes int for CEA/EUA
    balance_before: float
    balance_after: float
    reference: Optional[str]
    notes: Optional[str]
    created_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class EntityAssetsResponse(BaseModel):
    """Complete asset overview for an entity. CEA/EUA balances are integers."""

    entity_id: UUID
    entity_name: str
    eur_balance: float = 0
    cea_balance: float = 0  # Integer in API response
    eua_balance: float = 0  # Integer in API response
    recent_transactions: List[AssetTransactionResponse] = []


# =============================================================================
# Market Maker Schemas
# =============================================================================


class MarketMakerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Market maker display name")
    email: EmailStr
    description: Optional[str] = None
    mm_type: MarketMakerTypeEnum = MarketMakerTypeEnum.CEA_SELLER
    initial_balances: Optional[Dict[str, Decimal]] = None  # {CEA: 10000, EUA: 5000}
    initial_eur_balance: Optional[Decimal] = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class MarketMakerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Market maker display name")
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize text fields to prevent XSS attacks"""
        return sanitize_string(v)


class MarketMakerBalance(BaseModel):
    available: Decimal
    locked: Decimal
    total: Decimal


class MarketMakerResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    mm_type: MarketMakerTypeEnum
    is_active: bool
    current_balances: Dict[str, MarketMakerBalance]  # {CEA: {...}, EUA: {...}}
    eur_balance: Optional[Decimal] = None
    cea_balance: Optional[Decimal] = None  # Flattened; integer for CEA
    eua_balance: Optional[Decimal] = None  # Flattened; integer for EUA
    total_orders: int = 0
    total_trades: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Asset Transaction Schemas (CEA/EUA amount and balance_after are integers)
class AssetTransactionCreate(BaseModel):
    certificate_type: str  # CEA, EUA
    transaction_type: str  # DEPOSIT, WITHDRAWAL
    amount: Decimal = Field(..., gt=0, description="Amount (integer for CEA/EUA certificates)")
    notes: Optional[str] = None


class MarketMakerTransactionResponse(BaseModel):
    id: UUID
    ticket_id: str
    market_maker_id: UUID
    certificate_type: str
    transaction_type: str
    amount: Decimal  # Integer when certificate_type is CEA/EUA
    balance_after: Decimal  # Integer when certificate_type is CEA/EUA
    notes: Optional[str]
    created_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Auto Trade Rule Schemas
# =============================================================================


class AutoTradePriceMode(str, Enum):
    FIXED = "fixed"
    SPREAD_FROM_BEST = "spread_from_best"
    RANDOM_SPREAD = "random_spread"
    PERCENTAGE_FROM_MARKET = "percentage_from_market"


class AutoTradeQuantityMode(str, Enum):
    FIXED = "fixed"
    PERCENTAGE_OF_BALANCE = "percentage_of_balance"
    RANDOM_RANGE = "random_range"


class AutoTradeRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Rule display name")
    enabled: bool = False
    side: OrderSide
    order_type: str = Field(default="LIMIT", pattern="^(LIMIT|MARKET)$", description="Order type: LIMIT or MARKET")

    # Price settings
    price_mode: AutoTradePriceMode = AutoTradePriceMode.SPREAD_FROM_BEST
    fixed_price: Optional[Decimal] = Field(None, gt=0, description="Fixed price in EUR per certificate")
    spread_from_best: Optional[Decimal] = Field(None, ge=0, description="Spread from best price in EUR")
    spread_min: Optional[Decimal] = Field(None, ge=0, description="Min spread for random_spread mode")
    spread_max: Optional[Decimal] = Field(None, ge=0, description="Max spread for random_spread mode")
    percentage_from_market: Optional[Decimal] = Field(None, ge=0, description="Percentage offset from market price")
    max_price_deviation: Optional[Decimal] = Field(None, ge=0, le=50, description="Max % deviation from scraped price")

    # Quantity settings (CEA/EUA: whole numbers only)
    quantity_mode: AutoTradeQuantityMode = AutoTradeQuantityMode.FIXED
    fixed_quantity: Optional[Decimal] = Field(None, gt=0, description="Fixed quantity of certificates")
    percentage_of_balance: Optional[Decimal] = Field(None, gt=0, le=100, description="Percentage of available balance to use")
    min_quantity: Optional[Decimal] = Field(None, gt=0, description="Minimum certificates per order")
    max_quantity: Optional[Decimal] = Field(None, gt=0, description="Maximum certificates per order")

    @field_validator("fixed_quantity", "min_quantity", "max_quantity", mode="before")
    @classmethod
    def quantity_whole_number(cls, v: Any) -> Any:
        if v is None:
            return v
        d = Decimal(str(v)) if not isinstance(v, Decimal) else v
        if d != d.to_integral_value():
            raise ValueError("CEA/EUA quantity must be a whole number (no fractions)")
        return d

    # Timing
    interval_mode: str = Field(default="fixed", pattern="^(fixed|random)$", description="Interval mode: fixed or random")
    interval_minutes: int = Field(default=5, ge=1, le=1440, description="Fixed interval in minutes (legacy)")
    interval_min_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Min random interval in minutes (legacy)")
    interval_max_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Max random interval in minutes (legacy)")
    # Seconds-based intervals (preferred for high-frequency trading)
    interval_seconds: Optional[int] = Field(None, ge=5, le=86400, description="Fixed interval in seconds")
    interval_min_seconds: Optional[int] = Field(None, ge=5, le=86400, description="Min random interval in seconds")
    interval_max_seconds: Optional[int] = Field(None, ge=5, le=86400, description="Max random interval in seconds")

    # Conditions
    min_balance: Optional[Decimal] = Field(None, ge=0, description="Minimum balance required to execute")
    max_active_orders: Optional[int] = Field(None, ge=1, description="Max open orders before pausing")


class AutoTradeRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Rule display name")
    enabled: Optional[bool] = None
    side: Optional[OrderSide] = None
    order_type: Optional[str] = Field(None, pattern="^(LIMIT|MARKET)$", description="Order type: LIMIT or MARKET")

    # Price settings
    price_mode: Optional[AutoTradePriceMode] = None
    fixed_price: Optional[Decimal] = Field(None, gt=0, description="Fixed price in EUR per certificate")
    spread_from_best: Optional[Decimal] = Field(None, ge=0, description="Spread from best price in EUR")
    spread_min: Optional[Decimal] = Field(None, ge=0, description="Min spread for random_spread mode")
    spread_max: Optional[Decimal] = Field(None, ge=0, description="Max spread for random_spread mode")
    percentage_from_market: Optional[Decimal] = Field(None, ge=0, description="Percentage offset from market price")
    max_price_deviation: Optional[Decimal] = Field(None, ge=0, le=50, description="Max % deviation from scraped price")

    # Quantity settings (CEA/EUA: whole numbers only)
    quantity_mode: Optional[AutoTradeQuantityMode] = None
    fixed_quantity: Optional[Decimal] = Field(None, gt=0, description="Fixed quantity of certificates")
    percentage_of_balance: Optional[Decimal] = Field(None, gt=0, le=100, description="Percentage of available balance to use")
    min_quantity: Optional[Decimal] = Field(None, gt=0, description="Minimum certificates per order")
    max_quantity: Optional[Decimal] = Field(None, gt=0, description="Maximum certificates per order")

    @field_validator("fixed_quantity", "min_quantity", "max_quantity", mode="before")
    @classmethod
    def quantity_whole_number(cls, v: Any) -> Any:
        if v is None:
            return v
        d = Decimal(str(v)) if not isinstance(v, Decimal) else v
        if d != d.to_integral_value():
            raise ValueError("CEA/EUA quantity must be a whole number (no fractions)")
        return d

    # Timing
    interval_mode: Optional[str] = Field(None, pattern="^(fixed|random)$", description="Interval mode: fixed or random")
    interval_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Fixed interval in minutes (legacy)")
    interval_min_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Min random interval in minutes (legacy)")
    interval_max_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Max random interval in minutes (legacy)")
    # Seconds-based intervals (preferred for high-frequency trading)
    interval_seconds: Optional[int] = Field(None, ge=5, le=86400, description="Fixed interval in seconds")
    interval_min_seconds: Optional[int] = Field(None, ge=5, le=86400, description="Min random interval in seconds")
    interval_max_seconds: Optional[int] = Field(None, ge=5, le=86400, description="Max random interval in seconds")

    # Conditions
    min_balance: Optional[Decimal] = Field(None, ge=0, description="Minimum balance required to execute")
    max_active_orders: Optional[int] = Field(None, ge=1, description="Max open orders before pausing")


class AutoTradeRuleResponse(BaseModel):
    id: UUID
    market_maker_id: UUID
    name: str
    enabled: bool
    side: str
    order_type: str

    # Price settings
    price_mode: str
    fixed_price: Optional[Decimal]
    spread_from_best: Optional[Decimal]
    spread_min: Optional[Decimal]
    spread_max: Optional[Decimal]
    percentage_from_market: Optional[Decimal]
    max_price_deviation: Optional[Decimal]

    # Quantity settings
    quantity_mode: str
    fixed_quantity: Optional[Decimal]
    percentage_of_balance: Optional[Decimal]
    min_quantity: Optional[Decimal]
    max_quantity: Optional[Decimal]

    # Timing
    interval_mode: str
    interval_minutes: int
    interval_min_minutes: Optional[int]
    interval_max_minutes: Optional[int]
    # Seconds-based intervals
    interval_seconds: Optional[int]
    interval_min_seconds: Optional[int]
    interval_max_seconds: Optional[int]

    # Conditions
    min_balance: Optional[Decimal]
    max_active_orders: Optional[int]

    # Execution tracking
    last_executed_at: Optional[datetime]
    next_execution_at: Optional[datetime]
    execution_count: int

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutoTradeConfigResponse(BaseModel):
    """Response for market maker auto trade configuration"""
    enabled: bool
    rules: List[AutoTradeRuleResponse]


class AutoTradeConfigUpdate(BaseModel):
    """Update the global enabled state for auto trade"""
    enabled: bool


# Auto Trade Settings Schemas (Global Liquidity Targets)
class AutoTradeSettingsResponse(BaseModel):
    """Response for auto trade global settings"""
    id: UUID
    certificate_type: str
    target_ask_liquidity: Optional[Decimal] = None
    target_bid_liquidity: Optional[Decimal] = None
    liquidity_limit_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutoTradeSettingsUpdate(BaseModel):
    """Update auto trade global settings"""
    target_ask_liquidity: Optional[Decimal] = Field(None, ge=0, description="Target EUR value of sell-side liquidity")
    target_bid_liquidity: Optional[Decimal] = Field(None, ge=0, description="Target EUR value of buy-side liquidity")
    liquidity_limit_enabled: Optional[bool] = None


class LiquidityStatusResponse(BaseModel):
    """Current liquidity status for a certificate type"""
    certificate_type: str
    ask_liquidity: Decimal  # Current EUR value of SELL orders
    bid_liquidity: Decimal  # Current EUR value of BUY orders
    target_ask_liquidity: Optional[Decimal]  # Target level
    target_bid_liquidity: Optional[Decimal]  # Target level
    ask_percentage: Optional[Decimal]  # Current % of target (null if no target)
    bid_percentage: Optional[Decimal]  # Current % of target (null if no target)
    liquidity_limit_enabled: bool


# Auto Trade Market Settings Schemas (Per-market-side settings)
class MarketMakerSummary(BaseModel):
    """Summary of a market maker for display"""
    id: UUID
    name: str
    is_active: bool

    class Config:
        from_attributes = True


class AutoTradeMarketSettingsResponse(BaseModel):
    """Response for per-market-side auto trade settings"""
    id: UUID
    market_key: str  # 'CEA_BID', 'CEA_ASK', 'EUA_SWAP'
    enabled: bool
    target_liquidity: Optional[Decimal]
    price_deviation_pct: Decimal  # Percentage deviation from best price
    avg_order_count: int  # Average number of orders to maintain
    min_order_volume_eur: Decimal  # Minimum order volume in EUR
    volume_variety: int  # 1-10 scale for volume diversity (legacy)
    avg_order_count_variation_pct: Decimal = Decimal("10.0")
    max_orders_per_price_level: int = 3
    max_orders_per_level_variation_pct: Decimal = Decimal("10.0")
    min_order_value_variation_pct: Decimal = Decimal("10.0")
    interval_seconds: int = 60  # Order placement interval in seconds
    order_interval_variation_pct: Decimal = Decimal("10.0")
    max_order_volume_eur: Optional[Decimal] = None
    max_liquidity_threshold: Optional[Decimal] = None  # Trigger internal trades above this
    internal_trade_interval: Optional[int] = None  # Interval for internal trades when at target
    internal_trade_volume_min: Optional[Decimal] = None  # Min volume per internal trade (EUR)
    internal_trade_volume_max: Optional[Decimal] = None  # Max volume per internal trade (EUR)
    avg_spread: Optional[Decimal] = None  # Average spread (EUR for cash, ratio for swap)
    tick_size: Optional[Decimal] = None  # Tick size / price increment (EUR for cash, ratio for swap)
    created_at: datetime
    updated_at: datetime

    # Associated market makers
    market_makers: List[MarketMakerSummary] = []

    # Current liquidity status
    current_liquidity: Optional[Decimal] = None
    liquidity_percentage: Optional[Decimal] = None

    # Derived status
    is_online: bool = False  # Whether the auto-trader is actively running

    class Config:
        from_attributes = True


class AutoTradeMarketSettingsUpdate(BaseModel):
    """Update per-market-side auto trade settings"""
    enabled: Optional[bool] = None
    target_liquidity: Optional[Decimal] = Field(None, ge=0, description="Target liquidity in EUR")
    price_deviation_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Max % deviation from best price")
    avg_order_count: Optional[int] = Field(None, ge=1, le=1000, description="Average number of orders to maintain")
    min_order_volume_eur: Optional[Decimal] = Field(None, ge=0, description="Minimum order volume in EUR")
    volume_variety: Optional[int] = Field(None, ge=1, le=10, description="Volume diversity scale (1-10)")
    avg_order_count_variation_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Order count variation percentage")
    max_orders_per_price_level: Optional[int] = Field(None, ge=1, le=100, description="Max orders at same price level")
    max_orders_per_level_variation_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Per-level order count variation %")
    min_order_value_variation_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Min order value variation percentage")
    interval_seconds: Optional[int] = Field(None, ge=5, le=3600, description="Order placement interval in seconds")
    order_interval_variation_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Interval variation percentage")
    max_order_volume_eur: Optional[Decimal] = Field(None, ge=0, description="Maximum order volume in EUR")
    max_liquidity_threshold: Optional[Decimal] = Field(None, ge=0, description="Threshold to trigger internal trades")
    internal_trade_interval: Optional[int] = Field(None, ge=10, le=3600, description="Seconds between internal trades")
    internal_trade_volume_min: Optional[Decimal] = Field(None, ge=0, description="Min volume per internal trade in EUR")
    internal_trade_volume_max: Optional[Decimal] = Field(None, ge=0, description="Max volume per internal trade in EUR")
    avg_spread: Optional[Decimal] = Field(None, ge=0, description="Average spread (EUR for cash, ratio for swap)")
    tick_size: Optional[Decimal] = Field(None, gt=0, description="Price increment per tick")


# Market Order (Admin) Schemas
class MarketOrderCreate(BaseModel):
    market_maker_id: UUID
    certificate_type: str  # CEA, EUA
    side: str = Field(..., pattern="^(BID|ASK)$", description="Order side: BID (buy) or ASK (sell)")
    order_type: str = "LIMIT"
    price: Decimal = Field(..., gt=0, description="Price in EUR per certificate")
    quantity: Decimal = Field(..., gt=0, description="Number of certificates to order")


# Ticket Log Schemas
class TicketLogResponse(BaseModel):
    id: UUID
    ticket_id: str
    timestamp: datetime
    user_id: Optional[UUID]
    market_maker_id: Optional[UUID]
    action_type: str
    entity_type: str
    entity_id: Optional[UUID]
    status: str
    request_payload: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    related_ticket_ids: List[str]
    tags: List[str]

    class Config:
        from_attributes = True


class TicketLogStats(BaseModel):
    total_actions: int
    success_count: int
    failed_count: int
    by_action_type: Dict[str, int]
    by_user: List[Dict[str, Any]]
    actions_over_time: List[Dict[str, Any]]


class ProvisionAction(str, Enum):
    """Actions for provisioning market makers"""

    CREATE_NEW = "create_new"
    FUND_EXISTING = "fund_existing"


class ProvisionRequest(BaseModel):
    action: ProvisionAction
    mm_type: MarketMakerTypeEnum
    amount: Decimal = Field(..., gt=0, description="Amount to provision (EUR or certificates)")
    mm_ids: Optional[List[UUID]] = None
    count: Optional[int] = None


# =============================================================================
# Trading Fee Schemas
# =============================================================================


class MarketTypeEnum(str, Enum):
    """Trading markets"""

    CEA_CASH = "CEA_CASH"
    SWAP = "SWAP"


class TradingFeeConfigResponse(BaseModel):
    """Response for a single market's fee configuration"""

    id: UUID
    market: MarketTypeEnum
    bid_fee_rate: Decimal = Field(..., ge=0, le=1, description="Fee rate for buyers (0-1)")
    ask_fee_rate: Decimal = Field(..., ge=0, le=1, description="Fee rate for sellers (0-1)")
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradingFeeConfigUpdate(BaseModel):
    """Request to update a market's fee configuration"""

    bid_fee_rate: Decimal = Field(..., ge=0, le=1, description="Fee rate for buyers (0-1)")
    ask_fee_rate: Decimal = Field(..., ge=0, le=1, description="Fee rate for sellers (0-1)")


class EntityFeeOverrideResponse(BaseModel):
    """Response for an entity's custom fee override"""

    id: UUID
    entity_id: UUID
    entity_name: Optional[str] = None  # Populated from join
    market: MarketTypeEnum
    bid_fee_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Custom buyer fee rate (0-1)")
    ask_fee_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Custom seller fee rate (0-1)")
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EntityFeeOverrideCreate(BaseModel):
    """Request to create/update an entity's fee override"""

    entity_id: UUID
    market: MarketTypeEnum
    bid_fee_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Custom buyer fee (null = use default)")
    ask_fee_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Custom seller fee (null = use default)")


class AllFeesResponse(BaseModel):
    """Response containing all fee configurations"""

    market_fees: List[TradingFeeConfigResponse]
    entity_overrides: List[EntityFeeOverrideResponse]


class EffectiveFeeResponse(BaseModel):
    """Response containing the effective fee rate for a specific context"""

    market: MarketTypeEnum
    side: str  # "BID" or "ASK"
    fee_rate: Decimal
    is_override: bool  # True if using entity override, False if using default
    entity_id: Optional[UUID] = None
