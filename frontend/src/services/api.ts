import axios from 'axios';
import type {
  Prices,
  PriceHistory,
  Certificate,
  SwapRequest,
  SwapCalculation,
  MarketStats,
  ContactRequest,
  ContactRequestResponse,
  ContactRequestUpdate,
  MessageResponse,
  PaginatedResponse,
  User,
  UserRole,
  ActivityLog,
  KYCDocument,
  ScrapingSource,
  ScrapeLibrary,
  ExchangeRateSource,
  MailSettings,
  MailSettingsUpdate,
  UserSession,
  CertificateType,
  OrderSide,
  Order,
  OrderBook,
  MarketDepth,
  CashMarketTrade,
  CashMarketStats,
  AdminUserFull,
  AdminUserUpdate,
  AdminPasswordReset,
  AuthenticationAttempt,
  Deposit,
  DepositCreate,
  AnnounceDepositRequest,
  ConfirmDepositRequest,
  ClearDepositRequest,
  RejectDepositRequest,
  WireInstructions,
  DepositListResponse,
  DepositStats,
  HoldCalculation,
  Entity,
  EntityBalance,
  EntityBalances,
  MarketMaker,
  MarketMakerType,
  MarketMakerQueryParams,
  MarketMakerTransaction,
  SettlementBatch,
  AdminSettlementBatch,
  Trade,
  TransactionType,
  Withdrawal,
  WithdrawalRequest,
  ApproveWithdrawalRequest,
  CompleteWithdrawalRequest,
  RejectWithdrawalRequest,
  WithdrawalStats,
  AllFeesResponse,
  TradingFeeConfig,
  TradingFeeConfigUpdate,
  EntityFeeOverride,
  EntityFeeOverrideCreate,
  EffectiveFeeResponse,
  AutoTradeSettings,
  LiquidityStatus,
  AutoTradeMarketSettings,
  AutoTradeMarketSettingsUpdate,
  AddAssetApiRequest,
  ExchangeRatePeriod,
  ExchangeRateHistoryResponse,
  ProcessorStatus,
  SettlementMetrics,
  SettlementAlert,
} from '../types';
import type { FundingInstructions } from '../types/funding';
import type { AdminDashboardStats } from '../types/admin';
import { MARKET_MAKER_TYPES } from '../types';
import { logger } from '../utils/logger';
import { transformKeysToCamelCase, transformKeysToSnakeCase } from '../utils/dataTransform';
import { TOKEN_KEY } from '../constants/auth';
import { useAuthStore } from '../stores/useStore';

// Flag to prevent multiple redirects during auth failures
let isRedirectingToLogin = false;

// Token storage utilities
// Note: Primary auth is via httpOnly cookies (set by backend on login)
// sessionStorage is kept as fallback during transition period

function getToken(): string | null {
  try {
    // Check sessionStorage for backwards compatibility during transition
    // New auth flow uses httpOnly cookies (sent automatically via withCredentials)
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function removeToken(): void {
  try {
    // Clear sessionStorage token (httpOnly cookie cleared by logout endpoint)
    sessionStorage.removeItem(TOKEN_KEY);
  } catch (error) {
    logger.error('Failed to remove token', error);
  }
}

// Dynamic API URL detection for LAN/remote access
const getApiBaseUrl = (): string => {
  // If VITE_API_URL is explicitly set, use it
  if (import.meta.env.VITE_API_URL) {
    logger.debug('Using VITE_API_URL', { url: import.meta.env.VITE_API_URL });
    return import.meta.env.VITE_API_URL;
  }

  const { protocol, hostname, port } = window.location;
  logger.debug('Detecting API URL', { protocol, hostname, port });

  // If running on Vite dev server (port 5173), use relative URLs
  // Vite proxy handles forwarding /api requests to the backend
  if (port === '5173') {
    logger.debug('Using relative URLs (Vite dev server proxy)');
    return '';
  }

  // Guard against empty hostname
  if (!hostname) {
    logger.warn('Empty hostname detected, falling back to relative URLs');
    return '';
  }

  // For production/other access, construct URL from current hostname
  // Assume backend runs on port 8000
  const apiUrl = `${protocol}//${hostname}:8000`;
  logger.debug('Constructed API URL', { url: apiUrl });
  return apiUrl;
};

const API_BASE = getApiBaseUrl();
logger.debug('API base URL initialized', { base: API_BASE });

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  // Enable credentials to send/receive httpOnly cookies
  withCredentials: true,
});

// Add auth token to requests, handle FormData, and transform request data
api.interceptors.request.use((config) => {
  const token = getToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Remove Content-Type for FormData to let browser set it with correct boundary
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  } else if (config.data && typeof config.data === 'object') {
    // Transform request data from camelCase to snake_case (backend expects snake_case)
    config.data = transformKeysToSnakeCase(config.data);
  }
  return config;
});

// Response interceptor: Transform response data and handle errors
api.interceptors.response.use(
  (response) => {
    // Transform response data from snake_case to camelCase (frontend expects camelCase)
    if (response.data && typeof response.data === 'object') {
      response.data = transformKeysToCamelCase(response.data);
    }
    return response;
  },
  async (error) => {
    // Standardize error response format (message always string; data.detail unchanged for modal)
    const data = error.response?.data;
    const d = data?.detail;
    let message: string;
    if (typeof d === 'string') {
      message = d;
    } else if (
      d &&
      typeof d === 'object' &&
      !Array.isArray(d) &&
      typeof (d as { error?: string }).error === 'string'
    ) {
      message = (d as { error: string }).error;
    } else if (typeof data?.message === 'string') {
      message = data.message;
    } else if (typeof data === 'string') {
      message = data;
    } else if (error.response?.status) {
      // Status-code-based fallback messages when backend sends no specific message
      const statusMessages: Record<number, string> = {
        400: 'Invalid request. Please check your input and try again.',
        403: 'You don\'t have permission for this action.',
        404: 'The requested resource was not found.',
        409: 'This action conflicts with existing data. Please refresh and try again.',
        422: 'Please check your input — some fields are invalid.',
        429: 'Too many requests. Please wait a moment and try again.',
        500: 'Something went wrong on our end. Please try again or contact support.',
        502: 'Service temporarily unavailable. Please try again in a moment.',
        503: 'Service temporarily unavailable. Please try again in a moment.',
      };
      message = statusMessages[error.response.status] || `Request failed (${error.response.status}). Please try again.`;
    } else if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      message = 'Unable to connect to the server. Please check your internet connection.';
    } else {
      message = error.message || 'An unexpected error occurred. Please try again.';
    }
    const standardizedError = {
      message,
      status: error.response?.status,
      data: error.response?.data,
      originalError: error,
    };

    // 401 = invalid/expired token
    if (error.response?.status === 401) {
      // Check if we're on the login page - don't redirect if already there
      if (window.location.pathname === '/login') {
        logger.debug('[API] 401 on login page, not redirecting');
        return Promise.reject(standardizedError);
      }
      
      // Prevent multiple redirects and logout the user properly
      if (!isRedirectingToLogin) {
        isRedirectingToLogin = true;
        logger.warn('[API] 401 Unauthorized - logging out and redirecting to login');
        
        // Clear token from storage
        removeToken();
        
        // Clear Zustand auth state - this is CRITICAL to prevent loops
        // The store's logout() also removes token, but we do both for safety
        useAuthStore.getState().logout();
        
        // Small delay to allow state to update before redirect
        setTimeout(() => {
          isRedirectingToLogin = false;
          window.location.href = '/login';
        }, 100);
      }
      return Promise.reject(standardizedError);
    }

    // 403 with "Not authenticated" = missing token (HTTPBearer)
    if (error.response?.status === 403) {
      let detail = error.response?.data?.detail;

      // Handle blob responses (e.g., file downloads)
      if (error.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text();
          const json = JSON.parse(text);
          detail = json.detail;
        } catch {
          // Not JSON, ignore
        }
      }

      if (detail === 'Not authenticated' && !isRedirectingToLogin) {
        isRedirectingToLogin = true;
        logger.warn('[API] 403 Not authenticated - logging out and redirecting to login');
        removeToken();
        useAuthStore.getState().logout();
        setTimeout(() => {
          isRedirectingToLogin = false;
          window.location.href = '/login';
        }, 100);
      }
    }

    // Log error for debugging
    logger.error('API request failed', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      message: standardizedError.message,
    });

    return Promise.reject(standardizedError);
  }
);

// Auth API
export const authApi = {
  requestMagicLink: async (email: string): Promise<MessageResponse> => {
    const { data } = await api.post('/auth/magic-link', { email });
    return data;
  },

  verifyMagicLink: async (token: string): Promise<{ access_token: string; user: User }> => {
    const { data } = await api.post('/auth/verify', { token });
    return data;
  },

  loginWithPassword: async (email: string, password: string): Promise<{ access_token: string; user: User }> => {
    const { data } = await api.post('/auth/login', { email, password });
    return data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
    removeToken();
  },

  // Validate invitation token
  validateInvitation: async (token: string): Promise<{
    valid: boolean;
    email: string;
    firstName: string;
    lastName: string;
  }> => {
    const { data } = await api.get(`/auth/validate-invitation/${token}`);
    return data;
  },

  // Setup password from invitation
  setupPassword: async (
    token: string,
    password: string,
    confirmPassword: string
  ): Promise<{ access_token?: string; accessToken?: string; user: User }> => {
    const { data } = await api.post('/auth/setup-password', {
      token,
      password,
      confirm_password: confirmPassword
    });
    return data;
  },
};

// Contact API
export const contactApi = {
  submitRequest: async (request: ContactRequest): Promise<MessageResponse> => {
    const { data } = await api.post('/contact/request', request);
    return data;
  },

  submitNDARequest: async (request: {
    entity_name?: string;
    contact_email: string;
    contact_first_name: string;
    contact_last_name: string;
    position?: string;
    nda_file?: File;
    referral_code?: string;
  }): Promise<MessageResponse> => {
    const formData = new FormData();
    if (request.entity_name) formData.append('entity_name', request.entity_name);
    formData.append('contact_email', request.contact_email);
    formData.append('contact_first_name', request.contact_first_name);
    formData.append('contact_last_name', request.contact_last_name);
    if (request.position) formData.append('position', request.position);
    if (request.nda_file) formData.append('file', request.nda_file);
    if (request.referral_code) formData.append('referral_code', request.referral_code);

    const { data } = await api.post('/contact/nda-request', formData);
    return data;
  },

  submitIntroducerNDARequest: async (request: {
    entity_name: string;
    contact_email: string;
    contact_first_name: string;
    contact_last_name: string;
    position: string;
    nda_file?: File;
    referral_code?: string;
    invite_token?: string;
    request_flow?: string;
  }): Promise<ContactRequestResponse> => {
    const formData = new FormData();
    formData.append('entity_name', request.entity_name);
    formData.append('contact_email', request.contact_email);
    formData.append('contact_first_name', request.contact_first_name);
    formData.append('contact_last_name', request.contact_last_name);
    formData.append('position', request.position);
    if (request.nda_file) formData.append('file', request.nda_file);
    if (request.referral_code) formData.append('referral_code', request.referral_code);
    if (request.invite_token) formData.append('invite_token', request.invite_token);
    if (request.request_flow) formData.append('request_flow', request.request_flow);

    const { data } = await api.post('/contact/introducer-nda-request', formData);
    return data;
  },

  getInvitationInfo: async (token: string): Promise<{
    invitedEmail: string;
    invitedFirstName: string | null;
    introducerName: string;
  }> => {
    const { data } = await api.get(`/contact/invitation/${token}`);
    return data;
  },

  validateCode: async (code: string): Promise<{ valid: boolean; type?: 'preintroducer' | 'introducer' }> => {
    const formData = new FormData();
    formData.append('code', code);
    const { data } = await api.post('/contact/validate-code', formData);
    return data;
  },

  submitIntroducerRequest: async (payload: {
    contact_email: string;
    contact_first_name: string;
    contact_last_name: string;
    entity_name?: string;
    referral_code: string;
    file?: File;
  }): Promise<ContactRequestResponse> => {
    const formData = new FormData();
    formData.append('contact_email', payload.contact_email);
    formData.append('contact_first_name', payload.contact_first_name);
    formData.append('contact_last_name', payload.contact_last_name);
    formData.append('entity_name', payload.entity_name || '');
    formData.append('referral_code', payload.referral_code);
    if (payload.file) formData.append('file', payload.file);
    const { data } = await api.post('/contact/introducer-request', formData);
    return data;
  },

  uploadIntroducerNDA: async (file: File): Promise<MessageResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/contact/introducer/upload-nda', formData);
    return data;
  },
};

// ─── Introducer Portal API ────────────────────────────────
export const introducerApi = {
  /** Send a referral invitation to a potential client */
  sendInvitation: async (data: {
    email: string;
    first_name?: string;
    personal_note?: string;
  }) => {
    const { data: result } = await api.post('/introducer/invitations', data);
    return result;
  },

  /** List all invitations sent by the current introducer */
  getInvitations: async () => {
    const { data } = await api.get('/introducer/invitations');
    return data;
  },

  /** Get commission earnings summary */
  getCommissionSummary: async () => {
    const { data } = await api.get('/introducer/commissions/summary');
    return data;
  },

  /** List individual commission entries */
  getCommissions: async (params?: { limit?: number; offset?: number }) => {
    const { data } = await api.get('/introducer/commissions', { params });
    return data;
  },
};

// Prices API
export const pricesApi = {
  getCurrent: async (): Promise<Prices> => {
    const { data } = await api.get('/prices/current');
    return data;
  },

  getHistory: async (hours: number = 24): Promise<PriceHistory> => {
    const { data } = await api.get(`/prices/history?hours=${hours}`);
    return data;
  },

  // WebSocket connection for live prices
  connectWebSocket: (onMessage: (prices: Prices) => void): WebSocket => {
    const getWsUrl = (): string => {
      // If VITE_WS_URL is explicitly set, use it
      if (import.meta.env.VITE_WS_URL) {
        logger.debug('Using VITE_WS_URL for WebSocket', { url: import.meta.env.VITE_WS_URL });
        return `${import.meta.env.VITE_WS_URL}/api/v1/prices/ws`;
      }

      const { protocol, hostname, port } = window.location;
      logger.debug('Detecting WebSocket URL', { protocol, hostname, port });

      // If running on Vite dev server (port 5173), use relative WebSocket URL
      // Vite proxy handles forwarding /api requests (including WebSocket) to the backend
      if (port === '5173') {
        const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${hostname}:${port}/api/v1/prices/ws`;
        logger.debug('Using Vite proxy WebSocket URL', { url: wsUrl });
        return wsUrl;
      }

      // For production/other access, construct URL from current hostname
      // Assume backend runs on port 8000
      const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${hostname}:8000/api/v1/prices/ws`;
      logger.debug('Using direct WebSocket URL', { url: wsUrl });
      return wsUrl;
    };

    const wsUrl = getWsUrl();
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Transform data from snake_case to camelCase
        const transformedData = transformKeysToCamelCase<Prices>(data);
        onMessage(transformedData);
      } catch (error) {
        logger.error('Failed to parse WebSocket message', error);
      }
    };

    ws.onerror = (error) => {
      logger.error('WebSocket error', error);
    };

    return ws;
  },
};

// Price Alerts API
export interface PriceAlertItem {
  id: string;
  certificateType: 'EUA' | 'CEA';
  direction: 'ABOVE' | 'BELOW';
  targetPrice: number;
  isActive: boolean;
  triggeredAt: string | null;
  createdAt: string | null;
}

export const priceAlertsApi = {
  list: async (): Promise<PriceAlertItem[]> => {
    const { data } = await api.get('/prices/alerts');
    return data;
  },
  create: async (body: { certificate_type: string; direction: string; target_price: number }): Promise<PriceAlertItem> => {
    const { data } = await api.post('/prices/alerts', body);
    return data;
  },
  remove: async (id: string): Promise<void> => {
    await api.delete(`/prices/alerts/${id}`);
  },
};

// Client Realtime Types (role_updated e.g. AML→CEA after clear deposit)
export interface ClientWebSocketMessage {
  type: 'connected' | 'heartbeat' | 'role_updated' | 'balance_updated'
    | 'deposit_status_updated' | 'kyc_status_updated' | 'swap_updated'
    | 'settlement_updated' | 'user_deactivated' | 'notification'
    | 'orderbook_updated' | 'trade_executed';
  data?: {
    role?: string; oldRole?: string; entityId?: string;
    eurBalance?: number; ceaBalance?: number; source?: string;
    depositId?: string; status?: string;
    swapId?: string; batchId?: string; batchReference?: string;
    documentId?: string;
    message?: string; level?: string;
    certificateType?: string;
    /** New trade from trade_executed (id, certificateType, price, quantity, side, executedAt) */
    id?: string;
    price?: number;
    quantity?: number;
    side?: 'BUY' | 'SELL';
    executedAt?: string;
  };
  message?: string;
  timestamp: string;
}

// Backoffice Realtime Types
export interface BackofficeWebSocketMessage {
  type: 'connected' | 'heartbeat' | 'new_request' | 'request_updated' | 'request_removed' | 'kyc_document_uploaded' | 'kyc_document_reviewed' | 'kyc_document_deleted' | 'new_ticket' | 'newTicket' | 'system_health_update' | 'new_settlement' | 'settlement_status_changed' | 'settlement_settled';
  data?: Record<string, unknown>;
  message?: string;
  timestamp: string;
}

// Client Realtime API (authenticated WS for role updates etc.)
export const clientRealtimeApi = {
  connectWebSocket: (
    token: string,
    onMessage: (message: ClientWebSocketMessage) => void,
    onOpen?: () => void,
    onClose?: () => void,
    onError?: (error: Event) => void
  ): WebSocket => {
    const getWsUrl = (): string => {
      if (import.meta.env.VITE_WS_URL) {
        return `${import.meta.env.VITE_WS_URL}/api/v1/client/ws?token=${encodeURIComponent(token)}`;
      }
      const { protocol, hostname, port } = window.location;
      const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
      if (port === '5173') {
        return `${wsProtocol}//${hostname}:${port}/api/v1/client/ws?token=${encodeURIComponent(token)}`;
      }
      return `${wsProtocol}//${hostname}:8000/api/v1/client/ws?token=${encodeURIComponent(token)}`;
    };
    const wsUrl = getWsUrl();
    logger.debug('Connecting to client WebSocket');
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      logger.debug('Client WebSocket connected');
      onOpen?.();
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ClientWebSocketMessage;
        const transformed = transformKeysToCamelCase<ClientWebSocketMessage>(data);
        logger.debug('Client WebSocket message', { type: transformed.type });
        onMessage(transformed);
      } catch (err) {
        logger.error('Failed to parse client WebSocket message', err);
      }
    };
    ws.onclose = () => {
      logger.debug('Client WebSocket disconnected');
      onClose?.();
    };
    ws.onerror = (error) => {
      logger.error('Client WebSocket error', error);
      onError?.(error);
    };
    return ws;
  },
};

// Backoffice Realtime API
export const backofficeRealtimeApi = {
  connectWebSocket: (
    onMessage: (message: BackofficeWebSocketMessage) => void,
    onOpen?: () => void,
    onClose?: () => void,
    onError?: (error: Event) => void
  ): WebSocket => {
    const getWsUrl = (): string => {
      // If VITE_WS_URL is explicitly set, use it
      if (import.meta.env.VITE_WS_URL) {
        return `${import.meta.env.VITE_WS_URL}/api/v1/backoffice/ws`;
      }

      const { protocol, hostname, port } = window.location;
      const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
      // WebSocket is served by backend (port 8000), not by Vite (port 5173)
      const wsPort = port === '5173' ? '8000' : port || '8000';
      return `${wsProtocol}//${hostname}:${wsPort}/api/v1/backoffice/ws`;
    };

    const wsUrl = getWsUrl();
    // Append auth token for backoffice WS authentication
    const token = getToken();
    const authedUrl = token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl;
    logger.debug('Connecting to backoffice WebSocket', { url: wsUrl });
    const ws = new WebSocket(authedUrl);

    ws.onopen = () => {
      logger.debug('Backoffice WebSocket connected');
      onOpen?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as BackofficeWebSocketMessage;
        // Transform data from snake_case to camelCase
        const transformedData = transformKeysToCamelCase<BackofficeWebSocketMessage>(data);
        logger.debug('Backoffice WebSocket message received', { type: transformedData.type });
        onMessage(transformedData);
      } catch (err) {
        logger.error('Failed to parse backoffice WebSocket message', err);
      }
    };

    ws.onclose = () => {
      logger.debug('Backoffice WebSocket disconnected');
      onClose?.();
    };

    ws.onerror = (error) => {
      logger.error('Backoffice WebSocket error', error);
      onError?.(error);
    };

    return ws;
  },
};

// Marketplace API
export const marketplaceApi = {
  getCEAListings: async (params?: {
    sort_by?: string;
    min_quantity?: number;
    max_quantity?: number;
    min_price?: number;
    max_price?: number;
    vintage_year?: number;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<Certificate>> => {
    const { data } = await api.get('/marketplace/cea', { params });
    return data;
  },

  getEUAListings: async (params?: {
    sort_by?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<Certificate>> => {
    const { data } = await api.get('/marketplace/eua', { params });
    return data;
  },

  getStats: async (): Promise<MarketStats & { current_prices: Prices }> => {
    const { data } = await api.get('/marketplace/stats');
    return data;
  },

  getListing: async (code: string): Promise<Certificate> => {
    const { data } = await api.get(`/marketplace/listing/${code}`);
    return data;
  },
};

// Swaps API
export const swapsApi = {
  getAvailable: async (params?: {
    direction?: 'eua_to_cea' | 'cea_to_eua' | 'all';
    min_quantity?: number;
    max_quantity?: number;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<SwapRequest>> => {
    const { data } = await api.get('/swaps/available', { params });
    return data;
  },

  getRate: async (): Promise<{
    eua_to_cea: number;
    cea_to_eua: number;
    eua_price_eur: number;
    cea_price_eur: number;
    explanation: string;
    platform_fee_pct: number;
    effective_rate: number;
    rate_change_24h?: number;
    eua_change_24h?: number;
    cea_change_24h?: number;
  }> => {
    const { data } = await api.get('/swaps/rate');
    return data;
  },

  calculate: async (from_type: string, quantity: number): Promise<SwapCalculation> => {
    const { data } = await api.get('/swaps/calculator', {
      params: { from_type, quantity },
    });
    return data;
  },

  getStats: async (): Promise<{
    open_swaps: number;
    matched_today: number;
    eua_to_cea_requests: number;
    cea_to_eua_requests: number;
    total_eua_volume: number;
    total_cea_volume: number;
    current_rate: number;
    avg_requested_rate: number;
  }> => {
    const { data } = await api.get('/swaps/stats');
    return data;
  },

  createSwapRequest: async (request: {
    from_type: 'CEA' | 'EUA';
    to_type: 'CEA' | 'EUA';
    quantity: number;
    desired_rate?: number;
  }): Promise<SwapRequest> => {
    const { data } = await api.post('/swaps', request);
    return data;
  },

  executeSwap: async (swapId: string): Promise<{
    success: boolean;
    message: string;
    swap_id: string;
    swap_reference: string;
    from_quantity: number;
    to_quantity: number;
    rate: number;
    from_balance_after: number;
    to_balance_after: number;
  }> => {
    const { data } = await api.post(`/swaps/${swapId}/execute`);
    return data;
  },

  getMySwaps: async (status?: string): Promise<{ data: SwapRequest[] }> => {
    const { data } = await api.get('/swaps/my', {
      params: status ? { status } : undefined,
    });
    return data;
  },

  getSwapOffers: async (): Promise<{
    offers: Array<{
      market_maker_id: string;
      market_maker_name: string;
      direction: 'CEA_TO_EUA' | 'EUA_TO_CEA';
      ratio: number;
      eua_available?: number;
      cea_available?: number;
      rate: number;
    }>;
    count: number;
  }> => {
    const { data } = await api.get('/swaps/offers');
    return data;
  },

  getOrderbook: async (): Promise<{
    asks: Array<{
      ratio: number;
      euaQuantity: number;
      ordersCount: number;
      cumulativeEua: number;
      depthPct: number;
    }>;
    totalEuaAvailable: number;
    levelsCount: number;
  }> => {
    const { data } = await api.get('/swaps/orderbook');
    // Data is already transformed by axios interceptor, just return it
    return data;
  },

  createSwapOffer: async (offer: {
    market_maker_id: string;
    ratio: number;
    eua_quantity: number;
  }): Promise<{
    success: boolean;
    orderId: string;  // Transformed by axios interceptor from order_id
    marketMakerId: string;
    marketMakerName: string;
    ratio: number;
    euaQuantity: number;
    status: string;
    createdAt: string;
  }> => {
    const { data } = await api.post('/swaps/offers', offer);
    return data;
  },

  createSwapOffersBatch: async (offers: Array<{
    market_maker_id: string;
    ratio: number;
    eua_quantity: number;
  }>): Promise<{
    success: boolean;
    created_count: number;
    offers: Array<{
      market_maker_id: string;
      market_maker_name: string;
      ratio: number;
      eua_quantity: number;
    }>;
  }> => {
    const { data } = await api.post('/swaps/offers/batch', { offers });
    return data;
  },

  resetSwapLiquidity: async (confirmationCode: string): Promise<{
    success: boolean;
    message: string;
    deleted_count: number;
  }> => {
    const { data } = await api.delete('/swaps/offers/reset', {
      data: { confirmation_code: confirmationCode },
    });
    return data;
  },
};

// Users API (Profile management)
export const usersApi = {
  getProfile: async (): Promise<User> => {
    const { data } = await api.get('/users/me');
    return data;
  },

  updateProfile: async (update: Partial<User>): Promise<User> => {
    const { data } = await api.put('/users/me', update);
    return data;
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<MessageResponse> => {
    const { data } = await api.put('/users/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return data;
  },

  getActivity: async (params?: {
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<ActivityLog>> => {
    const { data } = await api.get('/users/me/activity', { params });
    return data;
  },

  getSessions: async (): Promise<UserSession[]> => {
    const { data } = await api.get('/users/me/sessions');
    return data;
  },

  // Deposit reporting (APPROVED users)
  reportDeposit: async (amount: number, currency: string, wire_reference?: string): Promise<MessageResponse> => {
    const { data } = await api.post('/users/me/deposits/report', {
      amount,
      currency,
      wire_reference,
    });
    return data;
  },

  getMyDeposits: async (): Promise<Deposit[]> => {
    const { data } = await api.get('/users/me/deposits');
    return data;
  },

  getMyEntity: async (): Promise<Entity | null> => {
    const { data } = await api.get('/users/me/entity');
    return data || null;
  },

  getMyEntityBalance: async (): Promise<EntityBalance> => {
    const { data } = await api.get('/users/me/entity/balance');
    return data;
  },

  getFundingInstructions: async (): Promise<FundingInstructions> => {
    const { data } = await api.get('/users/me/funding-instructions');
    return data;
  },
};

// Admin API
export const adminApi = {
  // Contact Requests
  getContactRequests: async (params?: {
    user_role?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<ContactRequestResponse>> => {
    const { data } = await api.get('/admin/contact-requests', { params });
    return data;
  },

  updateContactRequest: async (id: string, update: ContactRequestUpdate): Promise<MessageResponse> => {
    const { data } = await api.put(`/admin/contact-requests/${id}`, update);
    return data;
  },

  // Delete contact request
  deleteContactRequest: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/admin/contact-requests/${id}`);
    return data;
  },

  /** Remove introducer contact requests with no PREINTRODUCER/INTRODUCER user for that email. */
  reconcileIntroducerOrphanContactRequests: async (): Promise<{ deleted: number }> => {
    const { data } = await api.post('/admin/contact-requests/reconcile-introducer-orphans');
    return data;
  },

  // Create user from contact request (approve & create user)
  createUserFromRequest: async (
    requestId: string,
    userData: {
      email: string;
      first_name: string;
      last_name: string;
      mode: 'manual' | 'invitation';
      password?: string;
      position?: string;
      /** Target role: 'KYC' (buyer flow, creates Entity) or 'INTRODUCER' (no Entity). */
      target_role?: 'KYC' | 'INTRODUCER';
    }
  ): Promise<{
    message: string;
    success: boolean;
    user: {
      id: string;
      email: string;
      first_name: string;
      last_name: string;
      role: string;
      entity_id: string;
      creation_method: string;
    };
  }> => {
    const params: Record<string, string> = {
      request_id: requestId,
      email: userData.email,
      first_name: userData.first_name,
      last_name: userData.last_name,
      mode: userData.mode,
    };
    if (userData.password != null && userData.password !== '') {
      params.password = userData.password;
    }
    if (userData.position != null && userData.position !== '') {
      params.position = userData.position;
    }
    if (userData.target_role) {
      params.target_role = userData.target_role;
    }
    const { data } = await api.post('/admin/users/create-from-request', null, {
      params,
    });
    return data;
  },

  /**
   * Open NDA PDF in a new browser tab. Fetches the file with auth, creates a blob URL, opens it with noopener, revokes the URL after 5s.
   * @param requestId - Contact request UUID
   * @param _fileName - Unused; kept for API compatibility
   * @throws Error with message 'POPUP_BLOCKED' if the browser blocks window.open (caller should show "Allow pop-ups for this site and try again.")
   */
  openNDAInBrowser: async (requestId: string, _fileName: string): Promise<void> => {
    const response = await api.get(`/admin/contact-requests/${requestId}/nda`, {
      responseType: 'blob'
    });

    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const win = window.open(url, '_blank', 'noopener');
    if (!win) {
      window.URL.revokeObjectURL(url);
      throw new Error('POPUP_BLOCKED');
    }
    setTimeout(() => window.URL.revokeObjectURL(url), 5000);
  },

  /**
   * Open User NDA PDF in a new browser tab. Fetches the file from the User model with auth,
   * creates a blob URL, and opens it with noopener.
   * @param userId - User UUID
   * @throws Error with message 'POPUP_BLOCKED' if the browser blocks window.open
   */
  openUserNDAInBrowser: async (userId: string): Promise<void> => {
    const response = await api.get(`/admin/users/${userId}/nda`, {
      responseType: 'blob'
    });

    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const win = window.open(url, '_blank', 'noopener');
    if (!win) {
      window.URL.revokeObjectURL(url);
      throw new Error('POPUP_BLOCKED');
    }
    setTimeout(() => window.URL.revokeObjectURL(url), 5000);
  },

  // IP WHOIS Lookup
  lookupIP: async (ipAddress: string): Promise<{
    ip: string;
    country: string;
    country_code: string;
    region: string;
    city: string;
    zip: string;
    lat: number;
    lon: number;
    timezone: string;
    isp: string;
    org: string;
    as: string;
  }> => {
    const { data } = await api.get(`/admin/ip-lookup/${ipAddress}`);
    return data;
  },

  getDashboard: async (): Promise<AdminDashboardStats> => {
    const { data } = await api.get('/admin/dashboard');
    return data;
  },

  // User Management
  getUsers: async (params?: {
    role?: UserRole | 'DISABLED';
    search?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<User>> => {
    const { data } = await api.get('/admin/users', { params });
    return data;
  },

  createUser: async (userData: {
    email: string;
    firstName: string;
    lastName: string;
    role: UserRole;
    password?: string;
    position?: string;
    entityId?: string;
  }): Promise<User> => {
    const { data } = await api.post('/admin/users', userData);
    return data;
  },

  getUser: async (id: string): Promise<User> => {
    const { data } = await api.get(`/admin/users/${id}`);
    return data;
  },

  updateUser: async (id: string, update: Partial<User>): Promise<User> => {
    const { data } = await api.put(`/admin/users/${id}`, update);
    return data;
  },

  deleteUser: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/admin/users/${id}`);
    return data;
  },

  changeUserRole: async (id: string, role: UserRole): Promise<MessageResponse> => {
    const { data } = await api.put(`/admin/users/${id}/role`, { role });
    return data;
  },

  bulkChangeRole: async (userIds: string[], role: UserRole): Promise<MessageResponse> => {
    const { data } = await api.post('/admin/users/bulk-role-change', { user_ids: userIds, role });
    return data;
  },

  bulkDeactivate: async (userIds: string[]): Promise<MessageResponse> => {
    const { data } = await api.post('/admin/users/bulk-deactivate', { user_ids: userIds, role: 'NDA' });
    return data;
  },

  // Full User Details (with auth history, sessions, stats)
  getUserFull: async (id: string): Promise<AdminUserFull> => {
    const { data } = await api.get(`/admin/users/${id}/full`);
    return data;
  },

  // Update any user field
  updateUserFull: async (id: string, update: AdminUserUpdate): Promise<User> => {
    const { data } = await api.put(`/admin/users/${id}`, update);
    return data;
  },

  // Reset user password
  resetUserPassword: async (id: string, reset: AdminPasswordReset): Promise<MessageResponse> => {
    const { data } = await api.post(`/admin/users/${id}/reset-password`, reset);
    return data;
  },

  // Create entity for user (for users created without entity who need to report deposits)
  createEntityForUser: async (id: string, entityName?: string): Promise<MessageResponse> => {
    const params = entityName ? { entity_name: entityName } : {};
    const { data } = await api.post(`/admin/users/${id}/create-entity`, null, { params });
    return data;
  },

  // Get user auth history
  getUserAuthHistory: async (
    id: string,
    params?: { page?: number; per_page?: number }
  ): Promise<PaginatedResponse<AuthenticationAttempt>> => {
    const { data } = await api.get(`/admin/users/${id}/auth-history`, { params });
    return data;
  },

  // Activity Logs
  getActivityLogs: async (params?: {
    user_id?: string;
    action?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<ActivityLog>> => {
    const { data } = await api.get('/admin/activity-logs', { params });
    return data;
  },

  // Scraping Sources
  getScrapingSources: async (): Promise<ScrapingSource[]> => {
    const { data } = await api.get('/admin/scraping-sources');
    return data;
  },

  updateScrapingSource: async (id: string, update: Partial<ScrapingSource>): Promise<ScrapingSource> => {
    const { data } = await api.put(`/admin/scraping-sources/${id}`, update);
    return data;
  },

  testScrapingSource: async (id: string): Promise<{ success: boolean; message: string; price?: number }> => {
    const { data } = await api.post(`/admin/scraping-sources/${id}/test`);
    return data;
  },

  refreshScrapingSource: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.post(`/admin/scraping-sources/${id}/refresh`);
    return data;
  },

  deleteScrapingSource: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/admin/scraping-sources/${id}`);
    return data;
  },

  createScrapingSource: async (source: {
    name: string;
    url: string;
    certificate_type: 'EUA' | 'CEA';
    scrape_library?: ScrapeLibrary;
    scrape_interval_minutes: number;
    config?: Record<string, unknown>;
  }): Promise<ScrapingSource> => {
    const { data } = await api.post('/admin/scraping-sources', source);
    return data;
  },

  getScrapingSourceHistory: async (id: string, hours = 24): Promise<{
    sourceId: string;
    sourceName: string;
    certificateType: string;
    currency: string;
    points: Array<{ price: number; recordedAt: string }>;
  }> => {
    const { data } = await api.get(`/admin/scraping-sources/${id}/history?hours=${hours}`);
    return data;
  },

  resetScrapingSourceHistory: async (id: string): Promise<{ message: string; success: boolean }> => {
    const { data } = await api.delete(`/admin/scraping-sources/${id}/history`);
    return data;
  },

  // Referral / Introducer Management
  createPreintroducer: async (payload: {
    email: string; first_name: string; last_name: string;
    position?: string;
  }): Promise<{
    message: string;
    success: boolean;
    user: { id: string; email: string; role: string; referral_code: string };
    contact_request_id?: string;
  }> => {
    const params = new URLSearchParams();
    Object.entries(payload).forEach(([k, v]) => { if (v) params.set(k, v); });
    const { data } = await api.post(`/admin/users/create-preintroducer?${params}`);
    return data;
  },

  sendIntroducerNDA: async (requestId: string): Promise<MessageResponse> => {
    const { data } = await api.post(`/admin/introducer/${requestId}/send-nda`);
    return data;
  },

  approveIntroducerNDA: async (userId: string): Promise<MessageResponse> => {
    const { data } = await api.put(`/admin/introducer/${userId}/approve-nda`);
    return data;
  },

  sendBuyerNDA: async (requestId: string): Promise<MessageResponse> => {
    const { data } = await api.post(`/admin/buyer/${requestId}/send-nda`);
    return data;
  },

  acceptNDA: async (requestId: string): Promise<MessageResponse> => {
    const { data } = await api.put(`/admin/contact-requests/${requestId}/accept-nda`);
    return data;
  },

  // Exchange Rate Sources
  getExchangeRateSources: async (): Promise<ExchangeRateSource[]> => {
    const { data } = await api.get('/admin/exchange-rate-sources');
    return data;
  },

  createExchangeRateSource: async (source: {
    name: string;
    from_currency: string;
    to_currency: string;
    url: string;
    scrape_library?: ScrapeLibrary;
    scrape_interval_minutes: number;
    is_primary?: boolean;
    config?: Record<string, unknown>;
  }): Promise<ExchangeRateSource> => {
    const { data } = await api.post('/admin/exchange-rate-sources', source);
    return data;
  },

  updateExchangeRateSource: async (
    id: string,
    update: {
      name?: string;
      url?: string;
      scrape_library?: ScrapeLibrary;
      is_active?: boolean;
      is_primary?: boolean;
      scrape_interval_minutes?: number;
      config?: Record<string, unknown>;
    }
  ): Promise<MessageResponse> => {
    const { data } = await api.put(`/admin/exchange-rate-sources/${id}`, update);
    return data;
  },

  testExchangeRateSource: async (
    id: string
  ): Promise<{ success: boolean; message: string; rate?: number }> => {
    const { data } = await api.post(`/admin/exchange-rate-sources/${id}/test`);
    return data;
  },

  refreshExchangeRateSource: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.post(`/admin/exchange-rate-sources/${id}/refresh`);
    return data;
  },

  deleteExchangeRateSource: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/admin/exchange-rate-sources/${id}`);
    return data;
  },

  getExchangeRateHistory: async (id: string, hours = 24): Promise<{
    sourceId: string;
    sourceName: string;
    pair: string;
    points: Array<{ rate: number; recordedAt: string }>;
  }> => {
    const { data } = await api.get(`/admin/exchange-rate-sources/${id}/history?hours=${hours}`);
    return data;
  },

  resetExchangeRateHistory: async (id: string): Promise<{ message: string; success: boolean }> => {
    const { data } = await api.delete(`/admin/exchange-rate-sources/${id}/history`);
    return data;
  },

  // Mail & Auth Settings
  getMailSettings: async (): Promise<MailSettings> => {
    const { data } = await api.get('/admin/settings/mail');
    return data;
  },

  updateMailSettings: async (payload: MailSettingsUpdate): Promise<{ message: string; success: boolean }> => {
    const { data } = await api.put('/admin/settings/mail', payload);
    return data;
  },

  sendTestEmail: async (testEmail: string): Promise<{ success: boolean; message: string }> => {
    const { data } = await api.post('/admin/settings/mail/test-email', { test_email: testEmail });
    return data;
  },

  getEmailTemplates: async (): Promise<{ name: string; used: boolean }[]> => {
    const { data } = await api.get('/admin/settings/mail/templates');
    return data.templates;
  },

  getEmailTemplatePreview: async (templateName: string): Promise<string> => {
    const { data } = await api.get(`/admin/settings/mail/preview/${templateName}`, {
      responseType: 'text',
      transformResponse: [(data: string) => data],
    });
    return data;
  },

  getDocumentsList: async (): Promise<import('../types').SettingsDocumentEntry[]> => {
    const { data } = await api.get('/admin/settings/documents/list');
    return data;
  },

  getDocumentPreview: async (path: string): Promise<Blob> => {
    const response = await api.get('/admin/settings/documents/preview', {
      params: { path },
      responseType: 'blob',
    });
    return response.data;
  },

  // Get all entities for admin purposes (for fee override dropdown)
  getEntities: async (): Promise<Entity[]> => {
    const { data } = await api.get('/admin/entities');
    return data.data;  // API returns { data: [...] }
  },

  // Auto Trade Settings (Liquidity Limits)
  getAutoTradeSettings: async (): Promise<AutoTradeSettings[]> => {
    const { data } = await api.get('/admin/auto-trade-settings');
    return data;
  },

  getAutoTradeSettingsByType: async (certificateType: string): Promise<AutoTradeSettings> => {
    const { data } = await api.get(`/admin/auto-trade-settings/${certificateType}`);
    return data;
  },

  updateAutoTradeSettings: async (
    certificateType: string,
    payload: {
      target_ask_liquidity?: number | null;
      target_bid_liquidity?: number | null;
      liquidity_limit_enabled?: boolean;
    }
  ): Promise<AutoTradeSettings> => {
    const { data } = await api.put(`/admin/auto-trade-settings/${certificateType}`, payload);
    return data;
  },

  getLiquidityStatus: async (certificateType: string): Promise<LiquidityStatus> => {
    const { data } = await api.get(`/admin/auto-trade-settings/${certificateType}/liquidity`);
    return data;
  },

  getAutoTradeStatus: async (): Promise<import('../types').AutoTradeStatus> => {
    const { data } = await api.get('/admin/auto-trade-status');
    return data;
  },

  // Per-market-side auto trade settings
  getMarketSettings: async (): Promise<AutoTradeMarketSettings[]> => {
    const { data } = await api.get('/admin/auto-trade-market-settings');
    return data;
  },

  getMarketSettingsByKey: async (marketKey: string): Promise<AutoTradeMarketSettings> => {
    const { data } = await api.get(`/admin/auto-trade-market-settings/${marketKey}`);
    return data;
  },

  updateMarketSettings: async (
    marketKey: string,
    payload: AutoTradeMarketSettingsUpdate
  ): Promise<AutoTradeMarketSettings> => {
    const { data } = await api.put(`/admin/auto-trade-market-settings/${marketKey}`, payload);
    return data;
  },

  refreshCeaMarket: async (): Promise<{
    success: boolean;
    orders_cancelled: number;
    cea_price_eur: string;
    mid_price_eur: string;
    price_deviation_pct: string;
    new_best_bid: string;
    new_best_ask: string;
    bid_orders_created: number;
    ask_orders_created: number;
  }> => {
    const { data } = await api.post('/admin/auto-trade-market-settings/refresh-cea');
    return data;
  },

  placeRandomOrder: async (): Promise<{
    success: boolean;
    side: string;
    price: string;
    quantity: string;
    volume_eur: string;
    is_market_like: boolean;
    trades_matched: number;
    market_maker: string;
    status: string;
  }> => {
    const { data } = await api.post('/admin/auto-trade-market-settings/place-random-order');
    return data;
  },

  placeRandomSwapOrder: async (): Promise<{
    success?: boolean;
    skipped?: boolean;
    action?: string;
    ratio?: string;
    euaQuantity?: string;
    volumeEur?: string;
    deficitEur?: string;
    currentLiquidityPct?: string;
    marketMaker?: string;
    reason?: string;
  }> => {
    const { data } = await api.post('/admin/auto-trade-market-settings/place-random-swap-order');
    return data;
  },

  refreshSwapMarket: async (): Promise<{
    success: boolean;
    ordersCancelled: number;
    ordersCreated: number;
    baseRatio: string;
    midRatio: string;
    liquidityEur: string;
    targetLiquidityEur: string;
  }> => {
    const { data } = await api.post('/admin/auto-trade-market-settings/refresh-swap');
    return data;
  },

  getMmActivity: async (limit = 50): Promise<Array<{
    side: 'SELL' | 'BUY';
    totalQuantity: number;
    vwap: number;
    totalEur: number;
    fillCount: number;
    timestamp: string;
  }>> => {
    const { data } = await api.get(`/admin/auto-trade-market-settings/mm-activity?limit=${limit}`);
    return data;
  },

  // ==================== Admin Testing Tools ====================

  /**
   * Update admin's own role for testing purposes
   */
  updateMyRole: async (role: string): Promise<User> => {
    const { data } = await api.put('/admin/me/role', { role });
    return data;
  },

  /**
   * Credit assets to admin's own entity for testing
   */
  creditMyEntity: async (assetType: string, amount: number): Promise<EntityBalances> => {
    const { data } = await api.post('/admin/me/credit', {
      asset_type: assetType,
      amount,
    });
    return data;
  },

  /**
   * Get admin's entity balances
   */
  getMyBalances: async (): Promise<EntityBalances> => {
    const { data } = await api.get('/admin/me/balances');
    return data;
  },

  // ==================== Settlement Management ====================

  /**
   * Get all pending settlement batches across all entities
   */
  getAdminPendingSettlements: async (): Promise<{ data: AdminSettlementBatch[]; count: number }> => {
    const { data } = await api.get('/admin/settlements/pending');
    return data;
  },

  /**
   * Instantly settle a single settlement batch
   */
  settleSettlementBatch: async (batchId: string): Promise<{ message: string; batchReference: string }> => {
    const { data } = await api.post(`/admin/settlements/${batchId}/settle`);
    return data;
  },
};

// Backoffice API (KYC review, user approvals)
export const backofficeApi = {
  // Pending Users/Access Requests
  getPendingUsers: async (): Promise<User[]> => {
    const { data } = await api.get('/backoffice/pending-users');
    return data;
  },

  approveUser: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.put(`/backoffice/users/${id}/approve`);
    return data;
  },

  rejectUser: async (id: string, reason: string): Promise<MessageResponse> => {
    const { data } = await api.put(`/backoffice/users/${id}/reject`, { reason });
    return data;
  },

  // KYC Documents
  getKYCDocuments: async (userId?: string): Promise<KYCDocument[]> => {
    const { data } = await api.get('/backoffice/kyc-documents', {
      params: userId ? { user_id: userId } : undefined,
    });
    return data;
  },

  reviewDocument: async (
    id: string,
    status: 'approved' | 'rejected',
    notes?: string
  ): Promise<MessageResponse> => {
    const { data } = await api.put(`/backoffice/kyc-documents/${id}/review`, {
      status,
      notes,
    });
    return data;
  },

  // Get document content as blob for preview
  getDocumentContent: async (documentId: string): Promise<Blob> => {
    const response = await api.get(`/backoffice/kyc-documents/${documentId}/content`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // User Details
  getUserSessions: async (userId: string): Promise<UserSession[]> => {
    const { data } = await api.get(`/backoffice/users/${userId}/sessions`);
    return data;
  },

  getUserTrades: async (userId: string): Promise<Trade[]> => {
    const { data } = await api.get(`/backoffice/users/${userId}/trades`);
    return data;
  },

  getUserDeposits: async (userId: string): Promise<Deposit[]> => {
    const { data } = await api.get(`/backoffice/users/${userId}/deposits`);
    return data;
  },

  // Deposit Management
  getDeposits: async (params?: {
    status?: string;
    entity_id?: string;
  }): Promise<Deposit[]> => {
    const { data } = await api.get('/backoffice/deposits', { params });
    return data;
  },

  createDeposit: async (deposit: DepositCreate): Promise<MessageResponse> => {
    const { data } = await api.post('/backoffice/deposits', deposit);
    return data;
  },

  getDeposit: async (depositId: string): Promise<Deposit> => {
    const { data } = await api.get(`/backoffice/deposits/${depositId}`);
    return data;
  },

  getEntityBalance: async (entityId: string): Promise<EntityBalance> => {
    const { data } = await api.get(`/backoffice/entities/${entityId}/balance`);
    return data;
  },

  // Sync entity.balance_amount to EntityHolding (fix for legacy deposits)
  syncEntityBalance: async (entityId: string): Promise<MessageResponse> => {
    const { data } = await api.post(`/backoffice/entities/${entityId}/sync-balance`);
    return data;
  },

  // Confirm pending deposit with actual received amount
  confirmDeposit: async (
    depositId: string,
    amount: number,
    currency: string,
    notes?: string
  ): Promise<MessageResponse> => {
    const { data } = await api.put(`/backoffice/deposits/${depositId}/confirm`, {
      amount,
      currency,
      notes,
    });
    return data;
  },

  // Reject pending deposit
  rejectDeposit: async (depositId: string): Promise<MessageResponse> => {
    const { data } = await api.put(`/backoffice/deposits/${depositId}/reject`);
    return data;
  },

  // Get all pending deposits (legacy - use new AML endpoints)
  getPendingDeposits: async (): Promise<Deposit[]> => {
    const { data } = await api.get('/backoffice/deposits', {
      params: { status: 'PENDING' },
    });
    return data;
  },

  // ============== NEW AML Deposit Endpoints ==============

  // Client endpoints
  getWireInstructions: async (): Promise<WireInstructions> => {
    const { data } = await api.get('/deposits/wire-instructions');
    return data;
  },

  announceDeposit: async (request: AnnounceDepositRequest): Promise<Deposit> => {
    const { data } = await api.post('/deposits/announce', request);
    return data;
  },

  getMyDepositsAML: async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<DepositListResponse> => {
    const { data } = await api.get('/deposits/my-deposits', { params });
    return data;
  },

  previewHoldPeriod: async (amount: number): Promise<HoldCalculation> => {
    const { data } = await api.get('/deposits/preview-hold', {
      params: { amount },
    });
    return data;
  },

  // Admin AML endpoints
  getPendingDepositsAML: async (params?: {
    limit?: number;
    offset?: number;
  }): Promise<DepositListResponse> => {
    const { data } = await api.get('/deposits/pending', { params });
    return data;
  },

  getOnHoldDeposits: async (params?: {
    include_expired?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<DepositListResponse> => {
    const { data } = await api.get('/deposits/on-hold', { params });
    return data;
  },

  getDepositStats: async (entityId?: string): Promise<DepositStats> => {
    const { data } = await api.get('/deposits/stats', {
      params: entityId ? { entity_id: entityId } : undefined,
    });
    return data;
  },

  getDepositAML: async (depositId: string): Promise<Deposit> => {
    const { data } = await api.get(`/deposits/${depositId}`);
    return data;
  },

  confirmDepositAML: async (
    depositId: string,
    request: ConfirmDepositRequest
  ): Promise<Deposit> => {
    const { data } = await api.post(`/deposits/${depositId}/confirm`, request);
    return data;
  },

  clearDeposit: async (
    depositId: string,
    request: ClearDepositRequest
  ): Promise<Deposit> => {
    const { data } = await api.post(`/deposits/${depositId}/clear`, request);
    return data;
  },

  rejectDepositAML: async (
    depositId: string,
    request: RejectDepositRequest
  ): Promise<Deposit> => {
    const { data } = await api.post(`/deposits/${depositId}/reject`, request);
    return data;
  },

  processExpiredHolds: async (): Promise<MessageResponse> => {
    const { data } = await api.post('/deposits/process-expired-holds');
    return data;
  },

  // Asset Management
  addAsset: async (entityId: string, request: AddAssetApiRequest): Promise<MessageResponse> => {
    const { data } = await api.post(`/backoffice/entities/${entityId}/add-asset`, request);
    return data;
  },

  getEntityAssets: async (entityId: string): Promise<{
    entityId: string;
    entityName: string;
    eurBalance: number;
    ceaBalance: number;
    euaBalance: number;
    recentTransactions: Array<{
      id: string;
      entityId: string;
      assetType: string;
      transactionType: string;
      amount: number;
      balanceBefore: number;
      balanceAfter: number;
      reference?: string;
      notes?: string;
      createdBy: string;
      createdAt: string;
    }>;
  }> => {
    const { data } = await api.get(`/backoffice/entities/${entityId}/assets`);
    return data;
  },

  getEntityTransactions: async (entityId: string, assetType?: 'EUR' | 'CEA' | 'EUA'): Promise<Array<{
    id: string;
    entity_id: string;
    asset_type: string;
    transaction_type: string;
    amount: number;
    balance_before: number;
    balance_after: number;
    reference?: string;
    notes?: string;
    created_by: string;
    created_at: string;
  }>> => {
    const { data } = await api.get(`/backoffice/entities/${entityId}/transactions`, {
      params: assetType ? { asset_type: assetType } : undefined,
    });
    return data;
  },

  // Update asset balance (admin edit)
  updateAssetBalance: async (entityId: string, assetType: 'EUR' | 'CEA' | 'EUA', request: {
    new_balance: number;
    notes?: string;
    reference?: string;
  }): Promise<MessageResponse> => {
    const { data } = await api.put(`/backoffice/entities/${entityId}/assets/${assetType}`, request);
    return data;
  },

  // Get entity orders (admin)
  getEntityOrders: async (entityId: string, params?: {
    status?: string;
    certificate_type?: string;
    limit?: number;
  }): Promise<Order[]> => {
    const { data } = await api.get(`/backoffice/entities/${entityId}/orders`, { params });
    return data;
  },

  // Admin cancel order
  adminCancelOrder: async (orderId: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/backoffice/orders/${orderId}`);
    return data;
  },

  // Admin update order
  adminUpdateOrder: async (orderId: string, update: {
    price?: number;
    quantity?: number;
  }): Promise<Order & { message: string }> => {
    const { data } = await api.put(`/backoffice/orders/${orderId}`, update);
    return data;
  },
};

// Onboarding API (KYC document upload for pending users)
export const onboardingApi = {
  getStatus: async (): Promise<{
    documents_uploaded: number;
    documents_required: number;
    documents: KYCDocument[];
    can_submit: boolean;
    status: 'pending' | 'submitted' | 'approved' | 'rejected';
  }> => {
    const { data } = await api.get('/onboarding/status');
    return data;
  },

  uploadDocument: async (
    type: string,
    file: File
  ): Promise<KYCDocument> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', type);

    // Don't set Content-Type manually - axios will set it with correct boundary for FormData
    const { data } = await api.post('/onboarding/documents', formData);
    return data;
  },

  getDocuments: async (): Promise<KYCDocument[]> => {
    const { data } = await api.get('/onboarding/documents');
    return data;
  },

  deleteDocument: async (id: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/onboarding/documents/${id}`);
    return data;
  },

  submit: async (): Promise<MessageResponse> => {
    const { data } = await api.post('/onboarding/submit');
    return data;
  },

  /** KYC form data – stub until backend exposes GET/PUT /onboarding/form. Returns empty so wizard loads; save is no-op. */
  getFormData: async (): Promise<import('../types').KYCFormDataResponse> => {
    try {
      const { data } = await api.get('/onboarding/form');
      return data ?? {};
    } catch {
      return {};
    }
  },

  /** KYC form data – stub until backend exposes PUT /onboarding/form. No-op so wizard can advance. */
  saveFormData: async (_update: import('../types').KYCFormDataUpdate): Promise<void> => {
    try {
      await api.put('/onboarding/form', _update);
    } catch {
      // No backend endpoint yet; allow wizard to proceed
    }
  },
};

// Cash Market API
export const cashMarketApi = {
  getOrderBook: async (certificateType: CertificateType): Promise<OrderBook> => {
    const { data } = await api.get(`/cash-market/orderbook/${certificateType}`);
    return data;
  },

  getMarketDepth: async (certificateType: CertificateType): Promise<MarketDepth> => {
    const { data } = await api.get(`/cash-market/depth/${certificateType}`);
    return data;
  },

  getRecentTrades: async (
    certificateType: CertificateType,
    limit: number = 50
  ): Promise<CashMarketTrade[]> => {
    const { data } = await api.get(`/cash-market/trades/${certificateType}`, {
      params: { limit },
    });
    return data;
  },

  getMarketStats: async (certificateType: CertificateType): Promise<CashMarketStats> => {
    const { data } = await api.get(`/cash-market/stats/${certificateType}`);
    return data;
  },

  getOHLC: async (
    certificateType: CertificateType,
    interval: number = 900
  ): Promise<{ time: number; open: number; high: number; low: number; close: number; volume: number }[]> => {
    const { data } = await api.get(`/cash-market/ohlc/${certificateType}`, {
      params: { interval },
    });
    return data;
  },

  // CEA/EUA: quantity and volume fields are whole numbers only (no fractional certificates).
  placeOrder: async (order: {
    certificate_type: CertificateType;
    side: OrderSide;
    price: number;
    quantity: number; // integer for CEA
  }): Promise<MessageResponse> => {
    const { data } = await api.post('/cash-market/orders', order);
    return data;
  },

  getMyOrders: async (params?: {
    status?: string;
    certificate_type?: CertificateType;
  }): Promise<Order[]> => {
    const { data } = await api.get('/cash-market/orders/my', { params });
    return data || [];
  },

  cancelOrder: async (orderId: string): Promise<MessageResponse> => {
    const { data } = await api.delete(`/cash-market/orders/${orderId}`);
    return data;
  },

  modifyOrder: async (orderId: string, update: { price: number }): Promise<unknown> => {
    const { data } = await api.put(`/cash-market/orders/${orderId}/price`, {
      new_price: update.price,
    });
    return data;
  },

  // NEW REAL TRADING ENDPOINTS

  getUserBalances: async (): Promise<{
    entityId: string | null;
    eurBalance: number;
    ceaBalance: number;
    euaBalance: number;
  }> => {
    const { data } = await api.get('/cash-market/user/balances');
    return {
      entityId: data.entityId ?? null,
      eurBalance: data.eurBalance ?? 0,
      ceaBalance: data.ceaBalance ?? 0,
      euaBalance: data.euaBalance ?? 0,
    };
  },

  getRealOrderBook: async (certificateType: CertificateType): Promise<OrderBook> => {
    const { data } = await api.get(`/cash-market/real/orderbook/${certificateType}`);
    return data;
  },

  previewOrder: async (request: {
    certificate_type: CertificateType;
    side: OrderSide;
    amount_eur?: number;
    quantity?: number;
    order_type?: 'MARKET' | 'LIMIT';
    limit_price?: number;
    all_or_none?: boolean;
  }): Promise<{
    certificateType: string;
    side: string;
    orderType: string;
    amountEur: number | null;
    quantityRequested: number | null;
    limitPrice: number | null;
    allOrNone: boolean;
    fills: Array<{
      sellerCode: string;
      price: number;
      quantity: number;
      cost: number;
    }>;
    totalQuantity: number;
    totalCostGross: number;
    weightedAvgPrice: number;
    bestPrice: number | null;
    worstPrice: number | null;
    platformFeeRate: number;
    platformFeeAmount: number;
    totalCostNet: number;
    netPricePerUnit: number;
    availableBalance: number;
    remainingBalance: number;
    canExecute: boolean;
    executionMessage: string;
    partialFill: boolean;
  }> => {
    const { data } = await api.post('/cash-market/order/preview', request);
    return data;
  },

  executeMarketOrder: async (request: {
    certificate_type: CertificateType;
    side: OrderSide;
    amount_eur?: number;
    quantity?: number;
    all_or_none?: boolean;
  }): Promise<{
    success: boolean;
    order_id: string | null;
    message: string;
    certificate_type: string;
    side: string;
    order_type: string;
    total_quantity: number;
    total_cost_gross: number;
    platform_fee: number;
    total_cost_net: number;
    weighted_avg_price: number;
    trades: Array<{
      seller_code: string;
      price: number;
      quantity: number;
      cost: number;
    }>;
    eur_balance: number;
    certificate_balance: number;
  }> => {
    const { data } = await api.post('/cash-market/order/market', request);
    return data;
  },
};

// Market Makers API
export const getMarketMakers = async (params?: MarketMakerQueryParams): Promise<MarketMaker[]> => {
  const { data } = await api.get('/admin/market-makers', { params });
  // Data is already transformed by axios interceptor to camelCase
  // Handle legacy nested balances format if present
  return data.map((mm: MarketMaker & { currentBalances?: { CEA?: { total: string | number }; EUA?: { total: string | number } } }) => ({
    ...mm,
    eurBalance: Number(mm.eurBalance) || 0,
    ceaBalance: Number(mm.ceaBalance) || Number(mm.currentBalances?.CEA?.total) || 0,
    euaBalance: Number(mm.euaBalance) || Number(mm.currentBalances?.EUA?.total) || 0,
    market: MARKET_MAKER_TYPES[mm.mmType as MarketMakerType]?.market || 'CEA_CASH',
  }));
};

export interface CreateMarketMakerRequest {
  name: string;
  email: string;
  description?: string;
  mm_type?: MarketMakerType;
  initial_eur_balance?: number;
  cea_balance?: number;
  eua_balance?: number;
}

export const createMarketMaker = async (data: CreateMarketMakerRequest): Promise<MarketMaker> => {
  // Transform frontend format to backend expected format
  // Backend expects: name, email, mm_type, initial_eur_balance, initial_balances: {CEA: number, EUA: number}
  // Frontend sends: name, email, mm_type, initial_eur_balance, cea_balance, eua_balance
  const payload: {
    name: string;
    email: string;
    description?: string;
    mm_type: MarketMakerType;
    initial_eur_balance?: number;
    initial_balances?: { CEA?: number; EUA?: number };
  } = {
    name: data.name,
    email: data.email,
    description: data.description,
    mm_type: data.mm_type || 'CEA_SELLER',
  };

  // Add EUR balance for CEA_BUYER
  if (data.initial_eur_balance !== undefined) {
    payload.initial_eur_balance = data.initial_eur_balance;
  }

  // Build initial_balances dict if any balance provided for CEA_SELLER or EUA_OFFER
  // Use !== undefined to properly handle zero values
  if (data.cea_balance !== undefined || data.eua_balance !== undefined) {
    payload.initial_balances = {};
    if (data.cea_balance !== undefined) payload.initial_balances.CEA = data.cea_balance;
    if (data.eua_balance !== undefined) payload.initial_balances.EUA = data.eua_balance;
  }

  const { data: response } = await api.post('/admin/market-makers', payload);
  return response;
};

export const updateMarketMaker = async (id: string, data: {
  name?: string;
  description?: string;
  is_active?: boolean;
}): Promise<MarketMaker> => {
  const { data: response } = await api.put(`/admin/market-makers/${id}`, data);
  return response;
};

export const deleteMarketMaker = async (id: string): Promise<MessageResponse> => {
  const { data } = await api.delete(`/admin/market-makers/${id}`);
  return data;
};

export const resetAllMarketMakers = async (password: string): Promise<{
  message: string;
  reset_count: number;
  orders_deleted: number;
  ticket_id: string;
}> => {
  const { data } = await api.post('/admin/market-makers/reset-all', { password });
  return data;
};

export interface CreateTransactionRequest {
  certificate_type: 'CEA' | 'EUA';
  transaction_type: 'DEPOSIT' | 'WITHDRAWAL';
  amount: number;
  notes?: string;
}

export const createMarketMakerTransaction = async (
  marketMakerId: string,
  data: CreateTransactionRequest
): Promise<{
  transaction_id: string;
  ticket_id: string;
  balance_after: number;
  message: string;
}> => {
  const { data: response } = await api.post(`/admin/market-makers/${marketMakerId}/transactions`, data);
  return response;
};

export const depositEurToMarketMaker = async (
  marketMakerId: string,
  amount: number,
  notes?: string
): Promise<{
  balance_before: number;
  balance_after: number;
  ticket_id: string;
  message: string;
}> => {
  const params = new URLSearchParams({ amount: String(amount) });
  if (notes) params.append('notes', notes);
  const { data: response } = await api.post(`/admin/market-makers/${marketMakerId}/eur-deposit?${params.toString()}`);
  return response;
};

export const withdrawEurFromMarketMaker = async (
  marketMakerId: string,
  amount: number,
  notes?: string
): Promise<{
  balance_before: number;
  balance_after: number;
  ticket_id: string;
  message: string;
}> => {
  const params = new URLSearchParams({ amount: String(amount) });
  if (notes) params.append('notes', notes);
  const { data: response } = await api.post(`/admin/market-makers/${marketMakerId}/eur-withdrawal?${params.toString()}`);
  return response;
};

export interface MarketMakerTransactionQueryParams {
  page?: number;
  per_page?: number;
  asset_type?: 'EUR' | 'CEA' | 'EUA';
  transaction_type?: string;
}

export const getMarketMakerTransactions = async (
  id: string,
  params?: MarketMakerTransactionQueryParams
): Promise<MarketMakerTransaction[]> => {
  const { data } = await api.get(`/admin/market-makers/${id}/transactions`, { params });
  // Data transformed by axios interceptor; add marketMakerId and normalize transaction_type
  return data.map((transaction: MarketMakerTransaction) => ({
    ...transaction,
    marketMakerId: id,
    transactionType: (transaction.transactionType?.toLowerCase() || 'deposit') as TransactionType,
    amount: Math.abs(transaction.amount),
  }));
};

export const createTransaction = async (id: string, data: {
  certificate_type: CertificateType;
  transaction_type: 'deposit' | 'withdrawal';
  amount: number;
  notes?: string;
}): Promise<MarketMakerTransaction> => {
  // Transform to backend format (uppercase transaction_type)
  const backendPayload = {
    ...data,
    transaction_type: data.transaction_type.toUpperCase(),
  };

  const { data: response } = await api.post(`/admin/market-makers/${id}/transactions`, backendPayload);
  return response;
};

export const getMarketMakerBalances = async (id: string): Promise<{
  ceaBalance: number;
  euaBalance: number;
  eurBalance: number;
  ceaAvailable: number;
  euaAvailable: number;
  eurAvailable: number;
  ceaLocked: number;
  euaLocked: number;
  eurLocked: number;
}> => {
  const { data } = await api.get(`/admin/market-makers/${id}/balances`);
  // Backend returns nested structure: {CEA: {available, locked, total}, ...}
  return {
    ceaBalance: data.CEA?.total ?? 0,
    euaBalance: data.EUA?.total ?? 0,
    eurBalance: data.EUR?.total ?? 0,
    ceaAvailable: data.CEA?.available ?? 0,
    euaAvailable: data.EUA?.available ?? 0,
    eurAvailable: data.EUR?.available ?? 0,
    ceaLocked: data.CEA?.locked ?? 0,
    euaLocked: data.EUA?.locked ?? 0,
    eurLocked: data.EUR?.locked ?? 0,
  };
};

// Auto Trade Rules API
export interface AutoTradeRule {
  id: string;
  marketMakerId: string;
  name: string;
  enabled: boolean;
  side: 'BUY' | 'SELL';
  orderType: 'LIMIT' | 'MARKET';
  priceMode: 'fixed' | 'spread_from_best' | 'random_spread' | 'percentage_from_market';
  fixedPrice?: number;
  spreadFromBest?: number;
  spreadMin?: number;
  spreadMax?: number;
  percentageFromMarket?: number;
  maxPriceDeviation?: number;
  quantityMode: 'fixed' | 'percentage_of_balance' | 'random_range';
  fixedQuantity?: number;
  percentageOfBalance?: number;
  minQuantity?: number;
  maxQuantity?: number;
  intervalMode: 'fixed' | 'random';
  intervalMinutes: number;
  intervalMinMinutes?: number;
  intervalMaxMinutes?: number;
  intervalSeconds?: number | null;
  intervalMinSeconds?: number | null;
  intervalMaxSeconds?: number | null;
  minBalance?: number;
  maxActiveOrders?: number;
  lastExecutedAt?: string;
  nextExecutionAt?: string;
  executionCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface AutoTradeRuleCreate {
  name: string;
  enabled?: boolean;
  side: 'BUY' | 'SELL';
  order_type?: 'LIMIT' | 'MARKET';
  price_mode?: 'fixed' | 'spread_from_best' | 'random_spread' | 'percentage_from_market';
  fixed_price?: number;
  spread_from_best?: number;
  spread_min?: number;
  spread_max?: number;
  percentage_from_market?: number;
  max_price_deviation?: number;
  quantity_mode?: 'fixed' | 'percentage_of_balance' | 'random_range';
  fixed_quantity?: number;
  percentage_of_balance?: number;
  min_quantity?: number;
  max_quantity?: number;
  interval_mode?: 'fixed' | 'random';
  interval_minutes?: number;
  interval_min_minutes?: number;
  interval_max_minutes?: number;
  interval_seconds?: number | null;
  interval_min_seconds?: number | null;
  interval_max_seconds?: number | null;
  min_balance?: number;
  max_active_orders?: number;
}

export interface AutoTradeRuleUpdate {
  name?: string;
  enabled?: boolean;
  side?: 'BUY' | 'SELL';
  order_type?: 'LIMIT' | 'MARKET';
  price_mode?: 'fixed' | 'spread_from_best' | 'random_spread' | 'percentage_from_market';
  fixed_price?: number | null;
  spread_from_best?: number | null;
  spread_min?: number | null;
  spread_max?: number | null;
  percentage_from_market?: number | null;
  max_price_deviation?: number | null;
  quantity_mode?: 'fixed' | 'percentage_of_balance' | 'random_range';
  fixed_quantity?: number | null;
  percentage_of_balance?: number | null;
  min_quantity?: number | null;
  max_quantity?: number | null;
  interval_mode?: 'fixed' | 'random';
  interval_minutes?: number;
  interval_min_minutes?: number | null;
  interval_max_minutes?: number | null;
  interval_seconds?: number | null;
  interval_min_seconds?: number | null;
  interval_max_seconds?: number | null;
  min_balance?: number | null;
  max_active_orders?: number | null;
}

export const getAutoTradeRules = async (marketMakerId: string): Promise<AutoTradeRule[]> => {
  const { data } = await api.get(`/admin/market-makers/${marketMakerId}/auto-trade-rules`);
  return data;
};

export const createAutoTradeRule = async (
  marketMakerId: string,
  ruleData: AutoTradeRuleCreate
): Promise<{ id: string; message: string }> => {
  const { data } = await api.post(`/admin/market-makers/${marketMakerId}/auto-trade-rules`, ruleData);
  return data;
};

export const updateAutoTradeRule = async (
  marketMakerId: string,
  ruleId: string,
  ruleData: AutoTradeRuleUpdate
): Promise<{ id: string; message: string }> => {
  const { data } = await api.put(
    `/admin/market-makers/${marketMakerId}/auto-trade-rules/${ruleId}`,
    ruleData
  );
  return data;
};

export const deleteAutoTradeRule = async (
  marketMakerId: string,
  ruleId: string
): Promise<{ message: string }> => {
  const { data } = await api.delete(
    `/admin/market-makers/${marketMakerId}/auto-trade-rules/${ruleId}`
  );
  return data;
};

// Auto Trade Monitor
export interface AutoTradeRuleStatus {
  id: string;
  name: string;
  market_maker_id: string;
  market_maker_name: string;
  enabled: boolean;
  side: string | null;
  health: 'healthy' | 'disabled' | 'inactive' | 'overdue' | 'delayed';
  health_reason: string | null;
  last_executed_at: string | null;
  next_execution_at: string | null;
  time_until_next_seconds: number | null;
  execution_count: number;
  interval_seconds: number;
}

export interface AutoTradeMonitorResponse {
  summary: {
    total_rules: number;
    enabled: number;
    disabled: number;
    healthy: number;
    overdue: number;
  };
  rules: AutoTradeRuleStatus[];
  timestamp: string;
}

export const getAutoTradeMonitor = async (): Promise<AutoTradeMonitorResponse> => {
  const { data } = await api.get('/admin/market-makers/auto-trade-rules/monitor');
  return data;
};

// Logging/Audit API
export const getTickets = (params?: {
  start_date?: string;
  end_date?: string;
  action_type?: string;
  user_id?: string;
  market_maker_id?: string;
  status?: string;
  entity_type?: string;
  entity_id?: string;
  search?: string;
  tags?: string;
  page?: number;
  per_page?: number;
}) => api.get('/admin/logging/tickets', { params });

export const getLoggingStats = (params?: {
  date_from?: string;
  date_to?: string;
}) => api.get('/admin/logging/stats', { params });

export const getMarketMakerActions = (params?: {
  limit?: number;
  offset?: number;
}) => api.get('/admin/logging/market-maker-actions', { params });

export const getFailedActions = (params?: {
  limit?: number;
  offset?: number;
}) => api.get('/admin/logging/failed-actions', { params });

export const settlementApi = {
  getPendingSettlements: async (): Promise<{ data: SettlementBatch[]; count: number }> => {
    const { data } = await api.get<{ data: SettlementBatch[]; count: number }>('/settlement/pending');
    const list = data?.data;
    return {
      data: Array.isArray(list) ? list : [],
      count: typeof data?.count === 'number' ? data.count : 0,
    };
  },

  getSettlementDetails: async (settlementId: string): Promise<SettlementBatch> => {
    const { data } = await api.get<SettlementBatch>(`/settlement/${settlementId}`);
    return data;
  },
};

// =============================================================================
// Withdrawals API
// =============================================================================

export const withdrawalApi = {
  // Client endpoints
  requestWithdrawal: async (request: WithdrawalRequest): Promise<{
    success: boolean;
    withdrawal_id?: string;
    internal_reference?: string;
    error?: string;
  }> => {
    const { data } = await api.post('/withdrawals/request', request);
    return data;
  },

  getMyWithdrawals: async (): Promise<Withdrawal[]> => {
    const { data } = await api.get('/withdrawals/my-withdrawals');
    return data;
  },

  // Admin endpoints
  getPendingWithdrawals: async (): Promise<Withdrawal[]> => {
    const { data } = await api.get('/withdrawals/pending');
    return data;
  },

  getProcessingWithdrawals: async (): Promise<Withdrawal[]> => {
    const { data } = await api.get('/withdrawals/processing');
    return data;
  },

  getWithdrawalStats: async (): Promise<WithdrawalStats> => {
    const { data } = await api.get('/withdrawals/stats');
    return data;
  },

  approveWithdrawal: async (
    withdrawalId: string,
    request: ApproveWithdrawalRequest
  ): Promise<{ success: boolean; error?: string }> => {
    const { data } = await api.post(`/withdrawals/${withdrawalId}/approve`, request);
    return data;
  },

  completeWithdrawal: async (
    withdrawalId: string,
    request: CompleteWithdrawalRequest
  ): Promise<{ success: boolean; error?: string }> => {
    const { data } = await api.post(`/withdrawals/${withdrawalId}/complete`, request);
    return data;
  },

  rejectWithdrawal: async (
    withdrawalId: string,
    request: RejectWithdrawalRequest
  ): Promise<{ success: boolean; error?: string }> => {
    const { data } = await api.post(`/withdrawals/${withdrawalId}/reject`, request);
    return data;
  },
};

// =============================================================================
// Trading Fee Configuration API
// =============================================================================

export const feesApi = {
  getAllFees: async (): Promise<AllFeesResponse> => {
    const { data } = await api.get('/admin/fees');
    return data;
  },

  updateMarketFees: async (
    market: 'CEA_CASH' | 'SWAP',
    feeData: TradingFeeConfigUpdate
  ): Promise<TradingFeeConfig> => {
    const { data } = await api.put(`/admin/fees/${market}`, feeData);
    return data;
  },

  getEntityOverrides: async (): Promise<EntityFeeOverride[]> => {
    const { data } = await api.get('/admin/fees/entities');
    return data;
  },

  getEntityOverride: async (entityId: string): Promise<EntityFeeOverride[]> => {
    const { data } = await api.get(`/admin/fees/entities/${entityId}`);
    return data;
  },

  upsertEntityOverride: async (
    entityId: string,
    overrideData: EntityFeeOverrideCreate
  ): Promise<EntityFeeOverride> => {
    const { data } = await api.put(`/admin/fees/entities/${entityId}`, overrideData);
    return data;
  },

  deleteEntityOverride: async (
    entityId: string,
    market: 'CEA_CASH' | 'SWAP'
  ): Promise<{ status: string; entity_id: string; market: string }> => {
    const { data } = await api.delete(`/admin/fees/entities/${entityId}/${market}`);
    return data;
  },

  getEffectiveFee: async (
    market: 'CEA_CASH' | 'SWAP',
    side: 'BID' | 'ASK',
    entityId?: string
  ): Promise<EffectiveFeeResponse> => {
    const params = entityId ? `?entity_id=${entityId}` : '';
    const { data } = await api.get(`/admin/fees/effective/${market}/${side}${params}`);
    return data;
  },

  getIntroducerDefaults: async (): Promise<{ commissionRate: string }> => {
    const { data } = await api.get('/admin/fees/introducer-defaults');
    return data;
  },

  updateIntroducerDefaults: async (commissionRate: string): Promise<{ commissionRate: string }> => {
    const { data } = await api.put('/admin/fees/introducer-defaults', { commission_rate: commissionRate });
    return data;
  },

  getIntroducerOverrides: async (): Promise<Array<{
    userId: string; email: string; firstName: string; lastName: string; commissionRate: string;
  }>> => {
    const { data } = await api.get('/admin/fees/introducer-overrides');
    return data;
  },

  searchClients: async (q: string): Promise<{
    entities: Array<{ id: string; name: string; type: 'entity' }>;
    introducers: Array<{ id: string; email: string; firstName: string; lastName: string; type: 'introducer'; commissionRate: string | null }>;
  }> => {
    const { data } = await api.get(`/admin/fees/search-clients?q=${encodeURIComponent(q)}`);
    return data;
  },

  setUserCommissionRate: async (userId: string, rate: string): Promise<void> => {
    await api.put(`/admin/users/${userId}/commission-rate`, { rate });
  },

  deleteUserCommissionRate: async (userId: string): Promise<void> => {
    await api.put(`/admin/users/${userId}/commission-rate`, { rate: null });
  },
};

// AI Agent API (admin only)
export const aiAgentApi = {
  // Configs
  getConfigs: async () => {
    const { data } = await api.get('/admin/ai-agent/configs');
    return data;
  },

  updateConfig: async (role: string, update: {
    model?: string;
    system_prompt?: string;
    temperature?: number;
    max_tokens?: number;
    allow_internet?: boolean;
    allow_off_knowledge?: boolean;
    enabled?: boolean;
  }) => {
    const { data } = await api.put(`/admin/ai-agent/configs/${role}`, update);
    return data;
  },

  // Knowledge
  getKnowledgeSources: async () => {
    const { data } = await api.get('/admin/ai-agent/knowledge');
    return data;
  },

  uploadKnowledgeFile: async (name: string, file: File) => {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('file', file);
    const { data } = await api.post('/admin/ai-agent/knowledge/upload', formData);
    return data;
  },

  addKnowledgeURL: async (name: string, url: string) => {
    const { data } = await api.post('/admin/ai-agent/knowledge/add-url', { name, url });
    return data;
  },

  deleteKnowledgeSource: async (id: string) => {
    const { data } = await api.delete(`/admin/ai-agent/knowledge/${id}`);
    return data;
  },

  reindexSource: async (id: string) => {
    const { data } = await api.post(`/admin/ai-agent/knowledge/${id}/reindex`);
    return data;
  },

  getSourceChunks: async (id: string) => {
    const { data } = await api.get(`/admin/ai-agent/knowledge/${id}/chunks`);
    return data;
  },

  // API Keys
  getApiKeys: async () => {
    const { data } = await api.get('/admin/ai-agent/api-keys');
    return data;
  },

  updateApiKeys: async (update: {
    anthropic_api_key?: string;
    openai_api_key?: string;
  }) => {
    const { data } = await api.put('/admin/ai-agent/api-keys', update);
    return data;
  },

  // Test Chat
  testChat: async (messages: Array<{ role: string; content: string }>, role: string) => {
    const { data } = await api.post('/admin/ai-agent/test-chat', { messages, role });
    return data;
  },

  dualChat: async (messages: Array<{ role: string; content: string }>) => {
    const { data } = await api.post('/admin/ai-agent/dual-chat', { messages });
    return data;
  },
};

// ─── Exchange Rates (public, any authenticated user) ────────────────────────
export const exchangeRatesApi = {
  getHistory: async (params?: {
    fromCurrency?: string;
    toCurrency?: string;
    period?: ExchangeRatePeriod;
  }): Promise<ExchangeRateHistoryResponse> => {
    const { data } = await api.get('/exchange-rates/history', {
      params: {
        from_currency: params?.fromCurrency,
        to_currency: params?.toCurrency,
        period: params?.period,
      },
    });
    return data;
  },
};

// =============================================================================
// System Health API
// =============================================================================

export const systemHealthApi = {
  getProcessors: async (): Promise<{ processors: ProcessorStatus[] }> => {
    const { data } = await api.get('/admin/system-health/processors');
    return data;
  },

  getSettlementMetrics: async (): Promise<SettlementMetrics> => {
    const { data } = await api.get('/settlement/monitoring/metrics');
    return data;
  },

  getSettlementAlerts: async (): Promise<{
    alerts: SettlementAlert[];
    count: number;
    criticalCount: number;
    errorCount: number;
    warningCount: number;
  }> => {
    const { data } = await api.get('/settlement/monitoring/alerts');
    return data;
  },
};

// =============================================================================
// Document Library API
// =============================================================================

export const documentLibraryApi = {
  getLibrary: async (params?: { phase?: string; category?: string }) => {
    const { data } = await api.get('/documents/library', { params });
    return data;
  },

  downloadDocument: async (documentId: string): Promise<{ blob: Blob; filename: string }> => {
    const response = await api.get(`/documents/download/${documentId}`, {
      responseType: 'blob',
    });
    const disposition = response.headers['content-disposition'] ?? '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `${documentId}.pdf`;
    return { blob: response.data as Blob, filename };
  },
};

export default api;
