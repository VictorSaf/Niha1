// Chart Types

/** A data point for SVG price/rate line charts. */
export interface ChartPoint {
  price: number;
  recordedAt: string;
}

// Certificate Types
export type CertificateType = 'EUA' | 'CEA';

export interface Certificate {
  id: string;
  anonymousCode: string;
  certificateType: CertificateType;
  quantity: number;
  unitPrice: number;
  totalValue: number;
  vintageYear?: number;
  status: 'available' | 'reserved' | 'sold';
  createdAt: string;
  jurisdiction?: string;
  views?: number;
  inquiries?: number;
}

// Price Types
export interface PriceData {
  price: number;
  currency: string;
  priceUsd: number;
  priceEur?: number;  // EUR equivalent (for CEA)
  change24h: number;
}

export interface Prices {
  eua: PriceData;
  cea: PriceData;
  swapRate: number;
  updatedAt: string;
}

// Price History Types
export interface PriceHistoryPoint {
  timestamp: string;
  price: number;
  priceEur?: number;
  change24h: number;
}

export interface PriceHistory {
  eua: PriceHistoryPoint[];
  cea: PriceHistoryPoint[];
}

// Swap Types
export interface SwapRequest {
  id: string;
  anonymousCode: string;
  fromType: CertificateType;
  toType: CertificateType;
  quantity: number;
  desiredRate: number;
  equivalentQuantity: number;
  status: 'open' | 'matched' | 'completed' | 'cancelled';
  createdAt: string;
  expiresAt?: string;
}

export interface SwapCalculation {
  input: {
    type: CertificateType;
    quantity: number;
    valueEur: number;
  };
  output: {
    type: CertificateType;
    quantity: number;
    valueEur: number;
  };
  rate: number;
  feePct: number;
  feeEur: number;
}

// User Types
/** Full onboarding flow: NDA → KYC → … → EUA. MM = Market Maker (admin-created only). INTRODUCER = Introducer flow (no entity). */
export type UserRole =
  | 'ADMIN'
  | 'MM'
  | 'PREINTRODUCER'
  | 'PRE_NDA'
  | 'INTRODUCER'
  | 'NDA'
  | 'REJECTED'
  | 'KYC'
  | 'APPROVED'
  | 'FUNDING'
  | 'AML'
  | 'CEA'
  | 'CEA_SETTLE'
  | 'SWAP'
  | 'EUA_SETTLE'
  | 'EUA';

export interface User {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  position?: string;
  phone?: string;
  role: UserRole;
  entityId?: string;
  mustChangePassword?: boolean;
  lastLogin?: string;
  ndaSigned?: boolean;
  referralCode?: string;
}

// Activity Log
export interface ActivityLog {
  id: string;
  userId: string;
  action: string;
  details: Record<string, unknown>;
  ipAddress: string;
  userAgent?: string;
  createdAt: string;
}

// KYC Document
export type KYCDocumentType =
  | 'REGISTRATION'          // Business Registration Certificate
  | 'TAX_CERTIFICATE'       // Tax Registration Certificate
  | 'ARTICLES'              // Articles of Association
  | 'FINANCIAL_STATEMENTS'  // Latest Financial Statements
  | 'GHG_PERMIT'            // Greenhouse Gas Emissions Permit (optional)
  | 'ID'                    // Government-Issued ID
  | 'PROOF_AUTHORITY'       // Proof of Authority / Power of Attorney
  | 'CONTACT_INFO';         // Representative Contact Information

export interface KYCDocument {
  id: string;
  userId: string;
  entityId?: string;
  documentType: KYCDocumentType;
  fileName: string;
  /** Server path; not returned by API in responses for security */
  filePath?: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewedAt?: string;
  reviewedBy?: string;
  notes?: string;
  createdAt: string;
}

// Scraping Source
export type ScrapeLibrary = 'HTTPX' | 'BEAUTIFULSOUP' | 'SELENIUM' | 'PLAYWRIGHT';

export interface ScrapingSource {
  id: string;
  name: string;
  url: string;
  certificateType: CertificateType;
  scrapeLibrary?: ScrapeLibrary;
  isActive: boolean;
  isPrimary: boolean;
  scrapeIntervalMinutes: number;
  lastScrapeAt?: string;
  lastScrapeStatus?: 'success' | 'failed' | 'timeout';
  lastPrice?: number;
  lastPriceEur?: number;  // EUR-converted price (for CEA)
  lastExchangeRate?: number;  // EUR/CNY rate used for conversion
  config?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

// Exchange Rate Source
export interface ExchangeRateSource {
  id: string;
  name: string;
  fromCurrency: string;
  toCurrency: string;
  url: string;
  scrapeLibrary?: ScrapeLibrary;
  isActive: boolean;
  isPrimary: boolean;
  scrapeIntervalMinutes: number;
  lastRate?: number;
  lastScrapedAt?: string;
  lastScrapeStatus?: 'success' | 'failed' | 'timeout';
  config?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

// Exchange Rate History (public API)
export type ExchangeRatePeriod = '24h' | '7d' | '30d' | '90d' | '1y';

export interface ExchangeRateHistoryPoint {
  rate: number;
  recordedAt: string;
}

export interface ExchangeRateHistoryResponse {
  pair: string;
  period: ExchangeRatePeriod;
  currentRate: number | null;
  points: ExchangeRateHistoryPoint[];
}

// Mail & Auth Settings (admin Settings page)
export type MailProvider = 'resend' | 'smtp';

export interface MailSettings {
  id: string | null;
  provider: MailProvider;
  useEnvCredentials: boolean;
  fromEmail: string;
  resendApiKey: string | null;
  smtpHost: string | null;
  smtpPort: number | null;
  smtpUseTls: boolean;
  smtpUsername: string | null;
  smtpPassword: string | null;
  invitationSubject: string | null;
  invitationBodyHtml: string | null;
  invitationLinkBaseUrl: string | null;
  appBaseUrl: string | null;
  invitationTokenExpiryDays: number;
  verificationMethod: string | null;
  authMethod: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface MailSettingsUpdate {
  provider?: MailProvider;
  useEnvCredentials?: boolean;
  fromEmail?: string;
  resendApiKey?: string;
  smtpHost?: string;
  smtpPort?: number;
  smtpUseTls?: boolean;
  smtpUsername?: string;
  smtpPassword?: string;
  invitationSubject?: string;
  invitationBodyHtml?: string;
  invitationLinkBaseUrl?: string;
  appBaseUrl?: string;
  invitationTokenExpiryDays?: number;
  verificationMethod?: string;
  authMethod?: string;
}

/** Platform document entry from Settings → Documents (repo documents/). API returns snake_case; response interceptor yields camelCase. */
export interface SettingsDocumentEntry {
  path: string;
  name: string;
  type: 'pdf' | 'docx';
  used: boolean;
  emailTemplates: string[];
  /** From DOCUMENT_CATALOG when filename matches */
  title?: string;
  titleRo?: string;
  phase?: string;
  phaseName?: string;
  category?: string;
  minRole?: string;
}

// User Session
export interface UserSession {
  id: string;
  userId: string;
  ipAddress: string;
  userAgent?: string;
  startedAt: string;
  endedAt?: string;
  durationSeconds?: number;
  isActive?: boolean;
}

export interface Entity {
  id: string;
  name: string;
  legalName?: string;
  jurisdiction: 'EU' | 'CN' | 'HK' | 'OTHER';
  verified: boolean;
  kycStatus: 'pending' | 'approved' | 'rejected';
}

// Contact Request
export interface ContactRequest {
  entityName: string;
  contactEmail: string;
  contactName?: string;
  position?: string;
}

// NDA Request (for file upload)
export interface NDARequest {
  entityName: string;
  contactEmail: string;
  contactFirstName: string;
  contactLastName: string;
  position: string;
  ndaFile: File;
}

// Contact Request Response (from admin API). Client state: ONLY userRole (NDA, KYC, REJECTED).
export interface ContactRequestResponse {
  id: string;
  entityName: string;
  contactEmail: string;
  contactName?: string;  // Deprecated — use contactFirstName/contactLastName
  contactFirstName?: string;
  contactLastName?: string;
  position?: string;
  ndaFileName?: string;
  submitterIp?: string;
  /** Sole source for request state; values NDA, KYC, REJECTED. */
  userRole: string;
  /** Request flow: 'buyer' (default) or 'introducer'. */
  requestFlow?: string;
  notes?: string;
  createdAt: string;
  referredByUserId?: string;
  referralCodeUsed?: string;
}

// Contact Request update payload (admin API)
export interface ContactRequestUpdate {
  userRole?: string;
  notes?: string;
}

// KYC form (onboarding wizard) – persisted per user when backend supports GET/PUT /onboarding/form
export interface PEPDeclarationItem {
  name: string;
  role: string;
  is_pep: boolean;
}

export interface KYCFormDataResponse {
  current_step?: number;
  /** Current wizard step (1-based); may be returned as current_step by API. */
  currentStep?: number;
  pepDeclarations?: PEPDeclarationItem[];
  hasCarbonExperience?: boolean | null;
  carbonExperienceYears?: string;
  carbonCreditsTraded?: string[];
  investmentObjectives?: string[];
  riskAppetite?: string;
  sourceOfFunds?: string[];
  expectedAnnualVolume?: string;
  intendedUseDescription?: string;
  taxResidencyCountry?: string;
  subjectToCrs?: boolean | null;
  declarationsAccepted?: string[];
}

export interface KYCFormDataUpdate {
  current_step?: number;
  pep_declarations?: PEPDeclarationItem[];
  has_carbon_experience?: boolean;
  carbon_experience_years?: string;
  carbon_credits_traded?: string[];
  investment_objectives?: string[];
  risk_appetite?: string;
  source_of_funds?: string[];
  expected_annual_volume?: string;
  intended_use_description?: string;
  tax_residency_country?: string;
  subject_to_crs?: boolean;
  declarations_accepted?: string[];
}

// IP Lookup Result
export interface IPLookupResult {
  ip: string;
  country: string;
  countryCode: string;
  region: string;
  city: string;
  zip: string;
  lat: number;
  lon: number;
  timezone: string;
  isp: string;
  org: string;
  as: string;
}

// Market Stats
export interface MarketStats {
  ceaListings: number;
  euaListings: number;
  activeSwaps: number;
  totalCeaVolume: number;
  totalEuaVolume: number;
  totalMarketValueUsd: number;
  avgCeaPrice: number;
  avgEuaPrice: number;
  jurisdictionsServed: string[];
  trades24h: number;
  volume24hUsd: number;
}

// API Response Types
export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    perPage: number;
    total: number;
    totalPages: number;
  };
}

export interface MessageResponse {
  message: string;
  success: boolean;
}

// Trade Types
export interface Trade {
  id: string;
  tradeType: 'buy' | 'sell' | 'swap';
  certificateType: CertificateType;
  quantity: number;
  pricePerUnit: number;
  totalValue: number;
  status: 'pending' | 'confirmed' | 'completed' | 'cancelled';
  createdAt: string;
}

// Portfolio Summary
export interface PortfolioSummary {
  totalEua: number;
  totalCea: number;
  totalValueUsd: number;
  pendingSwaps: number;
  completedTrades: number;
}

// Cash Market Types
export type OrderSide = 'BUY' | 'SELL';
export type OrderStatus = 'OPEN' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED';

export interface Order {
  id: string;
  entityId: string;
  certificateType: CertificateType;
  side: OrderSide;
  price: number;
  quantity: number;
  filledQuantity: number;
  remainingQuantity: number;
  status: OrderStatus;
  market?: MarketType;  // Which market this order is on (CEA_CASH or SWAP)
  createdAt: string;
  updatedAt?: string;
}

export interface OrderBookLevel {
  price: number;
  quantity: number;
  orderCount: number;
  cumulativeQuantity: number;
}

export interface OrderBook {
  certificateType: CertificateType;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  spread: number | null;
  bestBid: number | null;
  bestAsk: number | null;
  lastPrice: number | null;
  volume24h: number;
  change24h: number;
  high24h: number | null;
  low24h: number | null;
}

export interface MarketDepthPoint {
  price: number;
  cumulativeQuantity: number;
}

export interface MarketDepth {
  certificateType: CertificateType;
  bids: MarketDepthPoint[];
  asks: MarketDepthPoint[];
}

export interface CashMarketTrade {
  id: string;
  certificateType: CertificateType;
  price: number;
  quantity: number;
  side: OrderSide;
  executedAt: string;
}

export interface CashMarketStats {
  certificateType: CertificateType;
  lastPrice: number;
  change24h: number;
  high24h: number;
  low24h: number;
  volume24h: number;
  totalBids: number;
  totalAsks: number;
}

// Authentication History Types
export type AuthMethod = 'password' | 'magic_link';

export interface AuthenticationAttempt {
  id: string;
  userId?: string;
  email: string;
  success: boolean;
  method: AuthMethod;
  ipAddress?: string;
  userAgent?: string;
  failureReason?: string;
  createdAt: string;
}

// Admin User Management Types
export interface AdminUserFull extends User {
  entityName?: string;
  passwordSet: boolean;
  loginCount: number;
  lastLoginIp?: string;
  failedLoginCount24h: number;
  sessions: UserSession[];
  authHistory: AuthenticationAttempt[];
  isActive: boolean;
  createdAt?: string;
}

export interface AdminUserUpdate {
  email?: string;
  firstName?: string;
  lastName?: string;
  position?: string;
  phone?: string;
  role?: UserRole;
  isActive?: boolean;
  entityId?: string;
}

export interface AdminPasswordReset {
  newPassword: string;
  forceChange?: boolean;
}

// Deposit Types
export type DepositStatus = 'pending' | 'confirmed' | 'on_hold' | 'cleared' | 'rejected';
export type Currency = 'EUR' | 'USD' | 'CNY' | 'HKD';
export type HoldType = 'FIRST_DEPOSIT' | 'SUBSEQUENT' | 'LARGE_AMOUNT';
export type AMLStatus = 'PENDING' | 'ON_HOLD' | 'CLEARED' | 'REJECTED';
export type RejectionReason =
  | 'WIRE_NOT_RECEIVED'
  | 'AMOUNT_MISMATCH'
  | 'SOURCE_VERIFICATION_FAILED'
  | 'AML_FLAG'
  | 'SANCTIONS_HIT'
  | 'SUSPICIOUS_ACTIVITY'
  | 'OTHER';

export interface Deposit {
  id: string;
  entityId: string;
  entityName?: string;
  userId?: string;
  userEmail?: string;

  // Reported by client
  reportedAmount?: number;
  reportedCurrency?: Currency;
  sourceBank?: string;
  sourceIban?: string;
  sourceSwift?: string;
  clientNotes?: string;

  // Confirmed by admin
  amount?: number;
  currency?: Currency;
  wireReference?: string;
  bankReference?: string;

  // Status
  status: DepositStatus;
  /** Reporting user's role (client status); FUNDING when announced. */
  userRole?: string;
  amlStatus?: AMLStatus;
  holdType?: HoldType;
  holdDaysRequired?: number;
  holdExpiresAt?: string;

  // Timestamps
  reportedAt?: string;
  confirmedAt?: string;
  clearedAt?: string;
  rejectedAt?: string;

  // Audit trail
  confirmedBy?: string;
  clearedBy?: string;
  rejectedBy?: string;
  rejectionReason?: string;
  adminNotes?: string;
  notes?: string;
  ticketId?: string;
  createdAt: string;
}

/** Unified item for Deposit History: wire deposit or add-asset transaction (deposit/withdrawal). */
export type DepositHistoryItem =
  | { type: 'wire_deposit'; id: string; amount?: number; currency?: Currency; status: DepositStatus; createdAt: string; wireReference?: string; notes?: string }
  | { type: 'asset_tx'; id: string; transactionType: 'DEPOSIT' | 'WITHDRAWAL'; amount: number; assetType: string; createdAt: string; notes?: string };

export interface DepositCreate {
  entityId: string;
  amount: number;
  currency: Currency;
  wireReference?: string;
  notes?: string;
}

// AML Deposit Request/Response Types
export interface AnnounceDepositRequest {
  amount: number;
  currency: Currency;
  sourceBank?: string;
  sourceIban?: string;
  sourceSwift?: string;
  clientNotes?: string;
}

export interface ConfirmDepositRequest {
  actualAmount: number;
  actualCurrency: Currency;
  wireReference?: string;
  bankReference?: string;
  adminNotes?: string;
}

export interface ClearDepositRequest {
  adminNotes?: string;
  forceClear?: boolean;
}

export interface RejectDepositRequest {
  reason: RejectionReason;
  adminNotes?: string;
}

export interface WireInstructions {
  bankName: string;
  iban: string;
  swiftBic: string;
  beneficiary: string;
  referenceFormat: string;
  importantNotes: string[];
}

export interface DepositListResponse {
  deposits: Deposit[];
  total: number;
  hasMore: boolean;
}

export interface DepositStats {
  pendingCount: number;
  onHoldCount: number;
  onHoldTotal: number;
  clearedCount: number;
  clearedTotal: number;
  rejectedCount: number;
  expiredHoldsCount: number;
}

export interface HoldCalculation {
  holdType: HoldType;
  holdDays: number;
  estimatedReleaseDate: string;
  reason: string;
}

export interface EntityBalance {
  entityId: string;
  entityName: string;
  balanceAmount: number;
  balanceCurrency?: Currency;
  totalDeposited: number;
  depositCount: number;
}

/**
 * Entity balances for all asset types (admin testing tools)
 */
export interface EntityBalances {
  eur: number;
  cea: number;
  eua: number;
}

// =============================================================================
// Asset Management Types
// =============================================================================

export type AssetType = 'EUR' | 'CEA' | 'EUA';

export type TransactionType = 'deposit' | 'withdrawal' | 'trade_buy' | 'trade_sell' | 'adjustment';

export interface EntityHolding {
  entityId: string;
  assetType: AssetType;
  quantity: number;
  updatedAt: string;
}

export interface AssetTransaction {
  id: string;
  entityId: string;
  assetType: AssetType;
  transactionType: TransactionType;
  amount: number;
  balanceBefore: number;
  balanceAfter: number;
  reference?: string;
  notes?: string;
  createdBy: string;
  createdAt: string;
}

// Market Maker Transaction (extends AssetTransaction with MM-specific fields)
export interface MarketMakerTransaction extends AssetTransaction {
  marketMakerId: string;
  marketMakerName?: string;
  certificateType?: CertificateType;
}

// Market Maker Query Parameters
// Note: Uses snake_case because these are sent directly to the backend API
export interface MarketMakerQueryParams {
  mm_type?: MarketMakerType;
  market?: MarketType;
  is_active?: boolean;
  page?: number;
  per_page?: number;
}

export interface EntityAssets {
  entityId: string;
  entityName: string;
  eurBalance: number;
  ceaBalance: number;
  euaBalance: number;
  recentTransactions: AssetTransaction[];
}

/** Request shape for add-asset API (snake_case). Use this for backofficeApi.addAsset. */
export interface AddAssetApiRequest {
  asset_type: AssetType;
  amount: number;
  operation?: 'deposit' | 'withdraw';
  reference?: string;
  notes?: string;
}

/** @deprecated Prefer AddAssetApiRequest for API payloads. Kept for backwards compatibility. */
export interface AddAssetRequest {
  assetType: AssetType;
  amount: number;
  operation?: 'deposit' | 'withdraw';
  reference?: string;
  notes?: string;
}

// =============================================================================
// Market Types
// =============================================================================

export type MarketType = 'CEA_CASH' | 'SWAP';

export interface Market {
  type: MarketType;
  name: string;
  description: string;
}

export const MARKETS: Record<MarketType, Market> = {
  CEA_CASH: {
    type: 'CEA_CASH',
    name: 'CEA Cash',
    description: 'Trade CEA certificates with EUR'
  },
  SWAP: {
    type: 'SWAP',
    name: 'Swap',
    description: 'Exchange CEA certificates for EUA certificates'
  }
};

// =============================================================================
// Market Maker Types
// =============================================================================

export type MarketMakerType = 'CEA_BUYER' | 'CEA_SELLER' | 'EUA_OFFER';

export interface MarketMaker {
  id: string;
  name: string;
  email?: string;  // Optional email field for MM contact
  description?: string;
  mmType: MarketMakerType;
  market: MarketType;  // Which market this MM operates in
  isActive: boolean;
  eurBalance: number;
  ceaBalance: number;
  euaBalance: number;
  totalOrders: number;
  createdAt: string;
  ticketId?: string;
  [key: string]: unknown;  // Index signature for DataTable compatibility
}

export interface MarketMakerTypeInfo {
  value: MarketMakerType;
  market: MarketType;
  name: string;
  description: string;
  balanceLabel: string;
  color: string;
}

export const MARKET_MAKER_TYPES: Record<MarketMakerType, MarketMakerTypeInfo> = {
  CEA_BUYER: {
    value: 'CEA_BUYER',
    market: 'CEA_CASH',
    name: 'CEA Buyer',
    description: 'Buys CEA certificates with EUR',
    balanceLabel: 'EUR Balance',
    color: 'emerald'
  },
  CEA_SELLER: {
    value: 'CEA_SELLER',
    market: 'CEA_CASH',
    name: 'CEA Seller',
    description: 'Sells CEA certificates for EUR',
    balanceLabel: 'CEA Balance',
    color: 'amber'
  },
  EUA_OFFER: {
    value: 'EUA_OFFER',
    market: 'SWAP',
    name: 'EUA Offer',
    description: 'Offers EUA for swap operations',
    balanceLabel: 'EUA Balance',
    color: 'blue'
  }
};

// Settlement
export type SettlementStatus =
  | 'PENDING'
  | 'TRANSFER_INITIATED'
  | 'IN_TRANSIT'
  | 'AT_CUSTODY'
  | 'SETTLED'
  | 'FAILED';

export type SettlementType = 'CEA_PURCHASE' | 'SWAP_CEA_TO_EUA';

export interface SettlementBatch {
  id: string;
  batchReference: string;
  settlementType: SettlementType;
  status: SettlementStatus;
  assetType: 'CEA' | 'EUA';
  quantity: number;
  price: number;
  totalValueEur: number;
  expectedSettlementDate: string;
  actualSettlementDate: string | null;
  progressPercent?: number;
  registryReference?: string;
  notes?: string;
  timeline?: SettlementStatusHistory[];
  createdAt: string;
  updatedAt: string;
}

export interface SettlementStatusHistory {
  id: string;
  settlementBatchId: string;
  status: SettlementStatus;
  notes?: string;
  createdAt: string;
}

export interface AdminSettlementBatch extends SettlementBatch {
  entityName: string;
  userEmail: string | null;
  userRole: string | null;
}

// =============================================================================
// Withdrawal Types
// =============================================================================

export type WithdrawalStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'REJECTED';

export interface Withdrawal {
  id: string;
  entityId: string;
  entityName?: string;
  userId?: string;
  userEmail?: string;

  // Asset details
  assetType: AssetType;
  amount: number;

  // Status
  status: WithdrawalStatus;

  // Destination (EUR)
  destinationBank?: string;
  destinationIban?: string;
  destinationSwift?: string;
  destinationAccountHolder?: string;

  // Destination (CEA/EUA)
  destinationRegistry?: string;
  destinationAccountId?: string;

  // References
  wireReference?: string;
  internalReference?: string;

  // Notes
  clientNotes?: string;
  adminNotes?: string;
  rejectionReason?: string;

  // Timestamps
  requestedAt?: string;
  processedAt?: string;
  completedAt?: string;
  rejectedAt?: string;

  // Audit
  processedBy?: string;
  completedBy?: string;
  rejectedBy?: string;

  createdAt: string;
}

export interface WithdrawalRequest {
  assetType: AssetType;
  amount: number;
  // EUR
  destinationBank?: string;
  destinationIban?: string;
  destinationSwift?: string;
  destinationAccountHolder?: string;
  // CEA/EUA
  destinationRegistry?: string;
  destinationAccountId?: string;
  clientNotes?: string;
}

export interface ApproveWithdrawalRequest {
  adminNotes?: string;
}

export interface CompleteWithdrawalRequest {
  wireReference?: string;
  adminNotes?: string;
}

export interface RejectWithdrawalRequest {
  rejectionReason: string;
  adminNotes?: string;
}

export interface WithdrawalStats {
  pending: number;
  processing: number;
  completed: number;
  rejected: number;
  total: number;
}

// Re-export backoffice types for convenience
// Note: ContactRequest and KYCDocument are defined locally above, so we only re-export the others
export type {
  PendingUserResponse,
  PendingDepositResponse,
  UserTradeResponse,
  KYCUser,
  PendingDeposit,
  UserTrade,
  DocumentViewerState,
  // Re-export these as aliases to avoid conflicts
  ContactRequest as BackofficeContactRequest,
  KYCDocument as BackofficeKYCDocument,
} from './backoffice';

// ============================================================
// Trading Fee Types
// ============================================================

export type MarketTypeEnum = 'CEA_CASH' | 'SWAP';

export interface TradingFeeConfig {
  id: string;
  market: MarketTypeEnum;
  bidFeeRate: number;
  askFeeRate: number;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface TradingFeeConfigUpdate {
  bidFeeRate: number;
  askFeeRate: number;
}

export interface EntityFeeOverride {
  id: string;
  entityId: string;
  entityName: string;
  market: MarketTypeEnum;
  bidFeeRate: number | null;
  askFeeRate: number | null;
  isActive: boolean;
  createdAt: string;
}

export interface EntityFeeOverrideCreate {
  market: MarketTypeEnum;
  bidFeeRate: number | null;
  askFeeRate: number | null;
}

export interface AllFeesResponse {
  marketFees: TradingFeeConfig[];
  entityOverrides: EntityFeeOverride[];
}

export interface EffectiveFeeResponse {
  market: MarketTypeEnum;
  side: string;
  feeRate: number;
  isOverride: boolean;
  entityId?: string;
}

// =============================================================================
// Market Maker Order Types (Individual Orders, not aggregated)
// =============================================================================

export interface MarketMakerOrder {
  id: string;
  marketMakerId: string;
  marketMakerName: string;
  certificateType: CertificateType;
  side: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  filledQuantity: number;
  remainingQuantity: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt?: string;
  ticketId?: string;
  [key: string]: unknown;  // Index signature for DataTable compatibility
}

export interface MarketMakerOrderUpdate {
  price?: number;
  quantity?: number;
}

// Auto Trade Settings Types
export interface AutoTradeSettings {
  id: string;
  certificateType: string;
  maxAskLiquidity: number | null;
  maxBidLiquidity: number | null;
  liquidityLimitEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AutoTradeSettingsUpdate {
  targetAskLiquidity?: number | null;
  targetBidLiquidity?: number | null;
  liquidityLimitEnabled?: boolean;
}

export interface LiquidityStatus {
  certificateType: string;
  askLiquidity: number;
  bidLiquidity: number;
  targetAskLiquidity: number | null;
  targetBidLiquidity: number | null;
  askPercentage: number | null;
  bidPercentage: number | null;
  liquidityLimitEnabled: boolean;
}

// Per-market-side auto trade settings
export interface MarketMakerSummary {
  id: string;
  name: string;
  isActive: boolean;
}

export interface AutoTradeMarketSettings {
  id: string;
  marketKey: string;  // 'CEA_BID', 'CEA_ASK', 'EUA_SWAP'
  enabled: boolean;
  targetLiquidity: number | null;
  priceDeviationPct: number;  // Percentage deviation from best price
  avgOrderCount: number;  // Average number of orders to maintain
  minOrderVolumeEur: number;  // Minimum order volume in EUR
  volumeVariety: number;  // 1-10 scale for volume diversity (legacy)
  avgOrderCountVariationPct: number;  // ±% variation on avg_order_count
  maxOrdersPerPriceLevel: number;  // Cap orders at one price level
  maxOrdersPerLevelVariationPct: number;  // ±% variation on max per level
  minOrderValueVariationPct: number;  // ±% variation on min order value
  intervalSeconds: number;  // Order placement interval in seconds
  orderIntervalVariationPct: number;  // ±% variation on interval
  maxOrderVolumeEur: number | null;  // Max EUR per single order
  maxLiquidityThreshold: number | null;  // Trigger internal trades above this EUR value
  internalTradeInterval: number | null;  // Interval for internal trades when at target (seconds)
  internalTradeVolumeMin: number | null;  // Min volume per internal trade (EUR)
  internalTradeVolumeMax: number | null;  // Max volume per internal trade (EUR)
  avgSpread: number | null;  // Average bid-ask spread
  tickSize: number | null;  // Minimum price increment
  createdAt: string;
  updatedAt: string;
  marketMakers: MarketMakerSummary[];
  currentLiquidity: number | null;
  liquidityPercentage: number | null;
  isOnline: boolean;  // Whether the auto-trader is actively running
}

export interface AutoTradeMarketSettingsUpdate {
  enabled?: boolean;
  targetLiquidity?: number | null;
  priceDeviationPct?: number;
  avgOrderCount?: number;
  minOrderVolumeEur?: number;
  volumeVariety?: number;
  avgOrderCountVariationPct?: number;
  maxOrdersPerPriceLevel?: number;
  maxOrdersPerLevelVariationPct?: number;
  minOrderValueVariationPct?: number;
  intervalSeconds?: number;
  orderIntervalVariationPct?: number;
  maxOrderVolumeEur?: number | null;
  maxLiquidityThreshold?: number | null;
  internalTradeInterval?: number | null;
  internalTradeVolumeMin?: number | null;
  internalTradeVolumeMax?: number | null;
  avgSpread?: number | null;
  tickSize?: number | null;
}

export interface AutoTradeStatus {
  executorRunning: boolean;
  cycleIntervalSeconds: number;
  lastCycleAt: string | null;
  lastCycleResults: {
    rulesChecked: number;
    ordersPlaced: number;
    internalTrades: number;
    errors: number;
  };
  nextCycleAt: string | null;
  rulesSummary: {
    total: number;
    enabled: number;
    readyToExecute: number;
  };
}

// =============================================================================
// System Health Types
// =============================================================================

export interface ProcessorStatus {
  name: string;
  cycleSeconds: number;
  status: 'idle' | 'error' | 'running';
  lastRunAt: string | null;
  errorCount: number;
  lastError: string | null;
  runCount: number;
}

export interface SettlementMetrics {
  totalPending: number;
  totalInProgress: number;
  totalSettledToday: number;
  totalFailed: number;
  totalOverdue: number;
  avgSettlementTimeHours: number | null;
  totalValuePendingEur: number;
  totalValueSettledTodayEur: number;
  oldestPendingDays: number | null;
}

export interface SettlementAlert {
  severity: 'CRITICAL' | 'ERROR' | 'WARNING';
  settlementId: string;
  batchReference: string;
  alertType: string;
  message: string;
  entityName: string;
  daysOverdue: number | null;
  totalValueEur: number | null;
}

// =============================================================================
// Document Library
// =============================================================================

export type DocumentCategory = 'legal' | 'compliance' | 'operational' | 'trading' | 'reporting' | 'internal';
export type DocumentPhase = 'F0' | 'F1' | 'F2' | 'F3' | 'F4' | 'F5' | 'F6' | 'F7';

export interface PlatformDocument {
  id: string;
  title: string;
  titleRo: string;
  filename: string;
  phase: DocumentPhase;
  phaseName: string;
  category: DocumentCategory;
  description: string;
  descriptionRo: string;
  adminOnly: boolean;
  trigger: string;
  audience: string;
  downloadUrl: string;
}

export interface DocumentPhaseInfo {
  code: DocumentPhase;
  name: string;
}

export interface DocumentLibraryResponse {
  documents: PlatformDocument[];
  totalCount: number;
  userRole: string;
  phases: DocumentPhaseInfo[];
}
