import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Search, RefreshCw, ChevronLeft, ChevronRight, Filter, Shield, Link2, AlertTriangle, WifiOff } from 'lucide-react';
import { DataTable, type Column } from '../common/DataTable';
import { AlertBanner } from '../common';
import { getTickets, backofficeRealtimeApi } from '../../services/api';
import { TicketDetailModal } from './TicketDetailModal';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface TicketLog {
  [key: string]: unknown;
  id: string;
  ticketId: string;
  timestamp: string;
  userId?: string;
  marketMakerId?: string;
  actionType: string;
  entityType: string;
  entityId?: string;
  status: 'SUCCESS' | 'FAILED';
  requestPayload?: Record<string, unknown>;
  responseData?: Record<string, unknown>;
  ipAddress?: string;
  userAgent?: string;
  beforeState?: Record<string, unknown>;
  afterState?: Record<string, unknown>;
  relatedTicketIds: string[];
  tags: string[];
  // Enriched fields from backend
  userEmail?: string;
  userRole?: string;
  userCompany?: string;
  userFullName?: string;
  mmName?: string;
  // Client-side metadata
  _groupId?: string;
  _isGroupStart?: boolean;
  _isGroupEnd?: boolean;
  _isGroupMiddle?: boolean;
  _isNew?: boolean; // just arrived via WS
}

// ---------------------------------------------------------------------------
// Action label mapping
// ---------------------------------------------------------------------------
type ActionCategory = 'auth' | 'trading' | 'deposit' | 'withdrawal' | 'kyc' | 'mm' | 'auto_trade' | 'admin' | 'swap' | 'system';

interface ActionMeta { label: string; category: ActionCategory }

const ACTION_MAP: Record<string, ActionMeta> = {
  USER_LOGIN:                { label: 'Login',              category: 'auth' },
  USER_LOGIN_MAGIC_LINK:     { label: 'Magic Link Login',   category: 'auth' },
  ORDER_PLACED:              { label: 'Place Order',        category: 'trading' },
  ORDER_CANCELLED:           { label: 'Cancel Order',       category: 'trading' },
  ORDER_MODIFIED:            { label: 'Modify Order',       category: 'trading' },
  ASSET_TRADE_DEBIT:         { label: 'Trade Debit',        category: 'trading' },
  AUTO_TRADE_ORDER_PLACED:   { label: 'Auto Trade',         category: 'auto_trade' },
  ENTITY_ASSET_DEPOSIT:      { label: 'Asset Deposit',      category: 'deposit' },
  ENTITY_ASSET_WITHDRAWAL:   { label: 'Asset Withdrawal',   category: 'withdrawal' },
  DEPOSIT_ANNOUNCED:         { label: 'Announce Deposit',   category: 'deposit' },
  DEPOSIT_CONFIRMED:         { label: 'Confirm Deposit',    category: 'admin' },
  DEPOSIT_CLEARED:           { label: 'Clear Deposit',      category: 'admin' },
  KYC_DOCUMENT_UPLOADED:     { label: 'KYC Upload',         category: 'kyc' },
  KYC_SUBMITTED:             { label: 'KYC Submit',         category: 'kyc' },
  MM_CREATED:                { label: 'Create MM',         category: 'mm' },
  MM_UPDATED:                { label: 'Update MM',         category: 'mm' },
  MM_DELETED:                { label: 'Delete MM',         category: 'mm' },
  MM_RESET_ALL:              { label: 'Reset All MM',       category: 'mm' },
  MM_EUR_DEPOSIT:            { label: 'MM Deposit',         category: 'mm' },
  MM_EUR_WITHDRAWAL:         { label: 'MM Withdrawal',      category: 'mm' },
  SWAP_CREATED:              { label: 'Swap Request',       category: 'swap' },
  SWAP_EXECUTED:             { label: 'Swap Executed',      category: 'swap' },
  TRADE_EXECUTED:            { label: 'Trade',              category: 'trading' },
  WITHDRAWAL_REQUESTED:      { label: 'Withdrawal Request', category: 'withdrawal' },
  WITHDRAWAL_APPROVED:       { label: 'Withdrawal Approved', category: 'admin' },
  WITHDRAWAL_COMPLETED:      { label: 'Withdrawal Completed', category: 'admin' },
  WITHDRAWAL_REJECTED:       { label: 'Withdrawal Rejected', category: 'admin' },
};

function getActionMeta(actionType: string, tags: string[]): ActionMeta {
  const mapped = ACTION_MAP[actionType];
  if (mapped) return mapped;
  const label = actionType.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  let category: ActionCategory = 'system';
  if (tags.includes('admin')) category = 'admin';
  else if (tags.includes('order') || tags.includes('cash_market')) category = 'trading';
  else if (tags.includes('deposit') || tags.includes('funding')) category = 'deposit';
  else if (tags.includes('withdrawal')) category = 'withdrawal';
  else if (tags.includes('market_maker')) category = 'mm';
  else if (tags.includes('kyc')) category = 'kyc';
  else if (tags.includes('auto_trade')) category = 'auto_trade';
  else if (tags.includes('auth')) category = 'auth';
  return { label, category };
}

// ---------------------------------------------------------------------------
// Category pill colors — dark-mode only, minimal & muted
// ---------------------------------------------------------------------------
const PILL_STYLE: Record<ActionCategory, string> = {
  auth:       'bg-navy-700/60 text-navy-300',
  trading:    'bg-emerald-900/30 text-emerald-400',
  deposit:    'bg-blue-900/30 text-blue-400',
  withdrawal: 'bg-amber-900/30 text-amber-400',
  kyc:        'bg-navy-700/50 text-navy-300',
  mm:         'bg-orange-900/25 text-orange-400',
  auto_trade: 'bg-cyan-900/25 text-cyan-400',
  admin:      'bg-violet-900/25 text-violet-400',
  swap:       'bg-indigo-900/25 text-indigo-400',
  system:     'bg-navy-700/40 text-navy-400',
};

// ---------------------------------------------------------------------------
// Extraction helpers
// ---------------------------------------------------------------------------
function getActorDisplay(ticket: TicketLog): { name: string; adminBadge: boolean; tradeSide?: 'BUY' | 'SELL' } {
  const isAdmin = ticket.userRole === 'ADMIN';
  const at = ticket.actionType;
  const req = ticket.requestPayload;
  const res = ticket.responseData;

  let tradeSide: 'BUY' | 'SELL' | undefined;
  if (at === 'ORDER_PLACED' && req) {
    const s = String(req.side || '').toUpperCase();
    if (s === 'BUY' || s === 'SELL') tradeSide = s;
  } else if (at === 'AUTO_TRADE_ORDER_PLACED') {
    if ((ticket.tags || []).includes('buy')) tradeSide = 'BUY';
    else if ((ticket.tags || []).includes('sell')) tradeSide = 'SELL';
    else if (req) { const s = String(req.side || '').toUpperCase(); if (s === 'BUY' || s === 'SELL') tradeSide = s; }
  } else if (at === 'ASSET_TRADE_DEBIT') {
    tradeSide = 'SELL';
  } else if (at === 'TRADE_EXECUTED') {
    tradeSide = undefined;
  } else if (at === 'ORDER_CANCELLED' || at === 'ORDER_MODIFIED') {
    if ((ticket.tags || []).includes('buy')) tradeSide = 'BUY';
    else if ((ticket.tags || []).includes('sell')) tradeSide = 'SELL';
    else if (res) { const s = String(res.side || '').toUpperCase(); if (s === 'BUY' || s === 'SELL') tradeSide = s; }
  }

  if (ticket.mmName) return { name: ticket.mmName, adminBadge: isAdmin, tradeSide };
  if (isAdmin) return { name: ticket.userCompany || 'Nihao Group', adminBadge: false, tradeSide };
  return { name: ticket.userCompany || ticket.userFullName || ticket.userEmail || 'Unknown', adminBadge: false, tradeSide };
}

/** Determine trade direction for TRADE_EXECUTED row tinting */
function getTradeDirection(ticket: TicketLog): 'bid' | 'ask' | null {
  if (ticket.actionType !== 'TRADE_EXECUTED') return null;
  const req = ticket.requestPayload;
  const aggressorSide = String(req?.aggressor_side || req?.aggressorSide || '').toUpperCase();
  // BUY aggressor = buyer lifted the ask → traded at ask (green tint)
  // SELL aggressor = seller hit the bid → traded at bid (red tint)
  if (aggressorSide === 'BUY') return 'ask';
  if (aggressorSide === 'SELL') return 'bid';
  // Internal trades — neutral
  return null;
}

const fmtNum = (n: number | string, decimals = 2) => {
  const num = typeof n === 'string' ? parseFloat(n) : n;
  if (isNaN(num)) return '0';
  return Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

function extractAmount(ticket: TicketLog): { text: string; isLarge?: boolean } | null {
  const req = ticket.requestPayload;
  const res = ticket.responseData;
  const at = ticket.actionType;

  if (at === 'ORDER_PLACED' && req) {
    const qty = fmtNum(req.quantity as number, 0);
    const price = fmtNum(req.price as number);
    const cert = String(req.certificate_type || req.certificateType || 'CEA');
    const side = String(req.side || '').toUpperCase();
    return { text: `${side} ${qty} ${cert} @ \u20AC${price}` };
  }
  if (at === 'AUTO_TRADE_ORDER_PLACED' && res) {
    const qty = fmtNum(res.quantity as number, 0);
    const price = fmtNum(res.price as number);
    const cert = String(res.certificate_type || res.certificateType || 'CEA');
    const side = (ticket.tags.includes('buy') ? 'BUY' : ticket.tags.includes('sell') ? 'SELL' : '');
    return { text: `${side} ${qty} ${cert} @ \u20AC${price}` };
  }
  if (at === 'TRADE_EXECUTED' && res) {
    const qty = fmtNum(res.quantity as number, 0);
    const price = fmtNum(res.price as number);
    const cert = String(res.certificate_type || res.certificateType || 'CEA');
    return { text: `${qty} ${cert} @ \u20AC${price}` };
  }
  if (at === 'ASSET_TRADE_DEBIT' && req) {
    return { text: `${fmtNum(req.amount as number, 0)} ${String(req.certificate_type || req.certificateType || '')}` };
  }
  if (at === 'DEPOSIT_ANNOUNCED' && req) {
    const amt = fmtNum(req.amount as number);
    const isLarge = parseFloat(String(req.amount || 0)) >= 50000;
    return { text: `\u20AC${amt}`, isLarge };
  }
  if (at === 'DEPOSIT_CONFIRMED' && req) return { text: `\u20AC${fmtNum((req.actual_amount || req.actualAmount || 0) as number)}` };
  if (at === 'DEPOSIT_CLEARED' && res) return { text: `\u20AC${fmtNum(res.amount as number)}` };
  if ((at === 'MM_EUR_DEPOSIT' || at === 'MM_EUR_WITHDRAWAL') && req) return { text: `\u20AC${fmtNum(req.amount as number)}` };
  if ((at === 'ENTITY_ASSET_DEPOSIT' || at === 'ENTITY_ASSET_WITHDRAWAL')) {
    const src = ticket.afterState || req;
    if (src) return { text: `${fmtNum(src.amount as number, 0)} ${String(src.asset_type || src.assetType || src.certificate_type || src.certificateType || '')}` };
  }
  if (at === 'MM_CREATED' && req && req.initial_eur_balance) return { text: `\u20AC${fmtNum(req.initial_eur_balance as number)}` };
  if (at === 'ORDER_MODIFIED' && res) return { text: `\u20AC${fmtNum(res.old_price as number)} \u2192 \u20AC${fmtNum(res.new_price as number)}` };
  if (at === 'KYC_DOCUMENT_UPLOADED' && req && req.file_name) return { text: String(req.file_name) };
  if (at === 'WITHDRAWAL_REQUESTED' || at === 'WITHDRAWAL_APPROVED' || at === 'WITHDRAWAL_COMPLETED' || at === 'WITHDRAWAL_REJECTED') {
    const src = req || ticket.responseData;
    if (src?.amount != null && src?.asset_type != null) return { text: `${fmtNum(src.amount as number)} ${String(src.asset_type)}` };
    if (src?.amount != null) return { text: `${fmtNum(src.amount as number)}` };
  }
  if (at === 'SWAP_CREATED' && req) {
    const qty = fmtNum(req.quantity as number, 0);
    const from = String(req.from_type || 'CEA');
    const to = String(req.to_type || 'EUA');
    return { text: `${qty} ${from} \u2192 ${to}` };
  }
  if (at === 'SWAP_EXECUTED' && req) {
    const cea = fmtNum(req.cea_quantity as number, 0);
    const eua = fmtNum(req.eua_output as number, 0);
    return { text: `${cea} CEA \u2192 ${eua} EUA` };
  }
  return null;
}

function extractResult(ticket: TicketLog): { text: string; variant: 'success' | 'info' | 'warning' | 'muted' } | null {
  const res = ticket.responseData;
  const at = ticket.actionType;
  if (ticket.status === 'FAILED') return { text: 'Failed', variant: 'warning' };
  if (at === 'ORDER_PLACED' && res) return { text: String(res.status || 'OPEN'), variant: 'success' };
  if (at === 'ORDER_CANCELLED') return { text: 'Cancelled', variant: 'muted' };
  if (at === 'ORDER_MODIFIED') return { text: 'Modified', variant: 'info' };
  if (at === 'DEPOSIT_CONFIRMED' && res) return { text: String(res.hold_type || res.holdType || 'ON_HOLD').replace(/_/g, ' '), variant: 'info' };
  if (at === 'DEPOSIT_CLEARED' && res) { const u = Number(res.upgraded_users || res.upgradedUsers || 0); return { text: u > 0 ? `Cleared +${u}` : 'Cleared', variant: 'success' }; }
  if (at === 'AUTO_TRADE_ORDER_PLACED') return { text: 'Placed', variant: 'success' };
  if (at === 'MM_CREATED') return { text: 'Created', variant: 'success' };
  if (at === 'MM_DELETED') return { text: 'Deleted', variant: 'warning' };
  if (at === 'MM_UPDATED') return { text: 'Updated', variant: 'info' };
  if (at === 'MM_RESET_ALL') return { text: 'All Reset', variant: 'warning' };
  if (at === 'USER_LOGIN' || at === 'USER_LOGIN_MAGIC_LINK') return { text: 'OK', variant: 'muted' };
  if (at === 'KYC_SUBMITTED') return { text: 'Submitted', variant: 'info' };
  if (at === 'KYC_DOCUMENT_UPLOADED') return { text: 'Uploaded', variant: 'muted' };
  if (at === 'TRADE_EXECUTED') return { text: 'Filled', variant: 'success' };
  if (at === 'ASSET_TRADE_DEBIT') return { text: 'Debited', variant: 'muted' };
  if (at === 'DEPOSIT_ANNOUNCED') return { text: 'Announced', variant: 'info' };
  if (at === 'MM_EUR_DEPOSIT') return { text: 'Credited', variant: 'success' };
  if (at === 'MM_EUR_WITHDRAWAL') return { text: 'Withdrawn', variant: 'muted' };
  if (at === 'ENTITY_ASSET_DEPOSIT') return { text: 'Deposited', variant: 'success' };
  if (at === 'ENTITY_ASSET_WITHDRAWAL') return { text: 'Withdrawn', variant: 'muted' };
  if (at === 'WITHDRAWAL_REQUESTED') return { text: 'Requested', variant: 'info' };
  if (at === 'WITHDRAWAL_APPROVED') return { text: 'Approved', variant: 'success' };
  if (at === 'WITHDRAWAL_COMPLETED') return { text: 'Completed', variant: 'success' };
  if (at === 'WITHDRAWAL_REJECTED') return { text: 'Rejected', variant: 'warning' };
  if (at === 'SWAP_CREATED') return { text: 'Created', variant: 'info' };
  if (at === 'SWAP_EXECUTED') return { text: 'Executed', variant: 'success' };
  return null;
}

const RESULT_CLS: Record<string, string> = {
  success: 'text-emerald-400',
  info:    'text-blue-400',
  warning: 'text-red-400 font-semibold',
  muted:   'text-navy-500',
};

// ---------------------------------------------------------------------------
// Time formatting
// ---------------------------------------------------------------------------
function formatTime(iso: string): { short: string; full: string; relative: string } {
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const now = new Date();
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
  const isToday = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const short = isToday ? time : `${d.toLocaleDateString([], { day: '2-digit', month: '2-digit' })} ${time}`;
  const full = d.toLocaleString();
  let relative: string;
  if (diffMin < 1) relative = 'just now';
  else if (diffMin < 60) relative = `${diffMin}m ago`;
  else if (diffMin < 1440) relative = `${Math.floor(diffMin / 60)}h ago`;
  else relative = `${Math.floor(diffMin / 1440)}d ago`;
  return { short, full, relative };
}

// ---------------------------------------------------------------------------
// Visual grouping
// ---------------------------------------------------------------------------
function annotateGroups(tickets: TicketLog[]): TicketLog[] {
  const idxMap = new Map<string, number>();
  tickets.forEach((t, i) => idxMap.set(t.ticketId, i));
  const visited = new Set<number>();
  const groups: number[][] = [];
  for (let i = 0; i < tickets.length; i++) {
    if (visited.has(i)) continue;
    const related = (tickets[i].relatedTicketIds || [])
      .map((rid) => idxMap.get(rid))
      .filter((idx): idx is number => idx !== undefined && !visited.has(idx));
    if (related.length === 0) continue;
    const group = [i, ...related].sort((a, b) => a - b);
    if (group[group.length - 1] - group[0] > group.length + 1) continue;
    groups.push(group);
    group.forEach((idx) => visited.add(idx));
  }
  const result = tickets.map((t) => ({ ...t }));
  for (const group of groups) {
    const gid = result[group[0]].ticketId;
    for (let gi = 0; gi < group.length; gi++) {
      const idx = group[gi];
      result[idx]._groupId = gid;
      result[idx]._isGroupStart = gi === 0;
      result[idx]._isGroupEnd = gi === group.length - 1;
      result[idx]._isGroupMiddle = gi > 0 && gi < group.length - 1;
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------
const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Actions' },
  { value: 'auth', label: 'Authentication' },
  { value: 'trading', label: 'Trading' },
  { value: 'deposit', label: 'Deposits' },
  { value: 'withdrawal', label: 'Withdrawals' },
  { value: 'kyc', label: 'KYC' },
  { value: 'mm', label: 'Market Makers' },
  { value: 'auto_trade', label: 'Auto Trade' },
  { value: 'admin', label: 'Admin Actions' },
];

const CATEGORY_TO_TAGS: Record<string, string> = {
  auth: 'auth', trading: 'order,cash_market', deposit: 'deposit', withdrawal: 'withdrawal',
  kyc: 'kyc', mm: 'market_maker', auto_trade: 'auto_trade', admin: 'admin',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function AllTicketsTab() {
  const [tickets, setTickets] = useState<TicketLog[]>([]);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [initialLoading, setInitialLoading] = useState(true); // only for first load
  const [refreshing, setRefreshing] = useState(false); // for manual refresh (spinner only, no skeleton)
  const [error, setError] = useState<string | null>(null);
  const [selectedTicket, setSelectedTicket] = useState<TicketLog | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [pendingCount, setPendingCount] = useState(0); // new tickets arrived while on page > 1

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const perPage = 50;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const pageRef = useRef(page);
  pageRef.current = page;
  const hasFilters = !!(searchQuery || statusFilter || categoryFilter);
  const hasFiltersRef = useRef(hasFilters);
  hasFiltersRef.current = hasFilters;

  // ── Data fetching (full reload from API) ──
  const fetchTickets = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) {
      // First load → skeleton; subsequent → just spinner icon
      if (tickets.length === 0) setInitialLoading(true);
      else setRefreshing(true);
    }
    setError(null);
    try {
      const params: Record<string, unknown> = { page, per_page: perPage };
      if (searchQuery) params.search = searchQuery;
      if (statusFilter) params.status = statusFilter;
      if (categoryFilter && categoryFilter in CATEGORY_TO_TAGS) params.tags = CATEGORY_TO_TAGS[categoryFilter];
      const { data } = await getTickets(params);
      setTickets(data.tickets || []);
      setTotal(data.total || 0);
      setTotalPages(data.totalPages || data.total_pages || 0);
      setPendingCount(0);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to fetch tickets');
    } finally {
      setInitialLoading(false);
      setRefreshing(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, searchQuery, statusFilter, categoryFilter]);

  // Stable ref so WS handler never triggers reconnections
  const fetchTicketsRef = useRef(fetchTickets);
  fetchTicketsRef.current = fetchTickets;

  useEffect(() => { fetchTickets(); }, [fetchTickets]);

  // Clear pending count when navigating to page 1
  useEffect(() => { if (page === 1) setPendingCount(0); }, [page]);

  // ── WebSocket: live streaming ──
  useEffect(() => {
    mountedRef.current = true;
    const RECONNECT_DELAY = 3000;

    const connect = () => {
      if (!mountedRef.current) return;
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      wsRef.current = backofficeRealtimeApi.connectWebSocket(
        (message) => {
          if (!mountedRef.current) return;
          if (message.type !== 'newTicket' && message.type !== 'new_ticket') return;

          // If user has active filters, just silently re-fetch to respect filters
          if (hasFiltersRef.current) {
            if (pageRef.current === 1) fetchTicketsRef.current({ silent: true });
            else setPendingCount((c) => c + 1);
            return;
          }

          if (pageRef.current === 1) {
            // Silently re-fetch (no flicker — no loading state change)
            fetchTicketsRef.current({ silent: true });
          } else {
            // Not on page 1 → show badge
            setPendingCount((c) => c + 1);
          }
        },
        () => { if (mountedRef.current) { setWsConnected(true); if (reconnectTimeoutRef.current) { clearTimeout(reconnectTimeoutRef.current); reconnectTimeoutRef.current = null; } } },
        () => { if (mountedRef.current) { setWsConnected(false); reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY); } },
        () => { if (mountedRef.current) setWsConnected(false); },
      );
    };
    connect();
    return () => {
      mountedRef.current = false;
      if (wsRef.current) {
        wsRef.current.onerror = null; wsRef.current.onclose = null; wsRef.current.onmessage = null;
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) { clearTimeout(reconnectTimeoutRef.current); reconnectTimeoutRef.current = null; }
    };
  }, []);

  const annotatedTickets = useMemo(() => annotateGroups(tickets), [tickets]);

  const handleRowClick = (ticket: TicketLog) => { setSelectedTicket(ticket); setIsModalOpen(true); };

  // ---------------------------------------------------------------------------
  // Columns — 6 compact columns, dark-only styling
  // ---------------------------------------------------------------------------
  const columns: Column<TicketLog>[] = [
    // 1. TIME
    {
      key: 'timestamp',
      header: 'Time',
      width: '100px',
      render: (_value, row) => {
        const { short, full, relative } = formatTime(row.timestamp);
        const isFailed = row.status === 'FAILED';
        const isGrouped = !!row._groupId;
        return (
          <div className="flex items-center gap-2" title={full}>
            <div className="relative flex-shrink-0">
              {isGrouped && !row._isGroupStart && <span className="absolute -top-3 left-[3px] w-px h-3 bg-navy-600/40" />}
              {isGrouped && !row._isGroupEnd && <span className="absolute -bottom-3 left-[3px] w-px h-3 bg-navy-600/40" />}
              <span className={`block w-1.5 h-1.5 rounded-full ${isFailed ? 'bg-red-500' : 'bg-emerald-500/70'}`} />
            </div>
            <div className="flex flex-col leading-none">
              <span className="text-[11px] text-navy-200 tabular-nums">{short}</span>
              <span className="text-[10px] text-navy-500 mt-0.5">{relative}</span>
            </div>
          </div>
        );
      },
    },
    // 2. ACTOR
    {
      key: 'userEmail',
      header: 'Actor',
      width: '200px',
      render: (_value, row) => {
        // TRADE_EXECUTED → împerechere clară Cumpărător / Vânzător (două rânduri)
        if (row.actionType === 'TRADE_EXECUTED') {
          const req = row.requestPayload;
          const res = row.responseData;
          const aggressorSide = String(req?.aggressor_side || req?.aggressorSide || '').toUpperCase();
          const buyerName = (row as Record<string, unknown>).buyerMmName ?? (row as Record<string, unknown>).buyer_mm_name ?? (row as Record<string, unknown>).buyerEntityName ?? (row as Record<string, unknown>).buyer_entity_name ?? res?.buyer_mm_id ?? '—';
          const sellerName = (row as Record<string, unknown>).sellerMmName ?? (row as Record<string, unknown>).seller_mm_name ?? (row as Record<string, unknown>).sellerEntityName ?? (row as Record<string, unknown>).seller_entity_name ?? res?.seller_mm_id ?? '—';
          const matchType = String(req?.match_type || req?.matchType || '');
          const isInternal = matchType === 'internal_trade';
          const dir = getTradeDirection(row);
          const buyerLabel = String(buyerName).replace(/^Market Maker\s+/i, '');
          const sellerLabel = String(sellerName).replace(/^Market Maker\s+/i, '');

          return (
            <div className="flex flex-col gap-0.5 min-w-0 rounded-lg border border-navy-700/60 bg-navy-800/40 px-2 py-1.5" title={aggressorSide ? `Aggressor: ${aggressorSide}` : undefined}>
              <span className={`flex-shrink-0 self-start px-1 py-px rounded text-[9px] font-semibold ${
                isInternal ? 'bg-violet-900/30 text-violet-400' :
                dir === 'ask' ? 'bg-emerald-900/30 text-emerald-400' :
                dir === 'bid' ? 'bg-red-900/30 text-red-400' :
                'bg-amber-900/30 text-amber-400'
              }`}>
                {isInternal ? 'Internal' : 'Trade'}
              </span>
              <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-[10px]">
                <span className="text-navy-500 font-medium uppercase tracking-wider">Buyer</span>
                <span className="text-emerald-400/90 font-medium truncate" title={String(buyerLabel)}>{buyerLabel}</span>
                <span className="text-navy-500 font-medium uppercase tracking-wider">Seller</span>
                <span className="text-amber-400/90 font-medium truncate" title={String(sellerLabel)}>{sellerLabel}</span>
              </div>
              {aggressorSide && (
                <span className="text-[9px] text-navy-500 mt-0.5">Aggressor: {aggressorSide}</span>
              )}
            </div>
          );
        }

        const { name, adminBadge, tradeSide } = getActorDisplay(row);
        const isMM = !!row.mmName || row.userRole === 'MM';

        return (
          <div className="flex items-center gap-1.5 min-w-0">
            {tradeSide && (
              <span className={`flex-shrink-0 px-1 py-px rounded text-[9px] font-semibold leading-tight tracking-wide ${
                tradeSide === 'BUY' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'
              }`}>
                {tradeSide}
              </span>
            )}
            {adminBadge && (
              <span title="Admin" className="flex items-center justify-center w-3.5 h-3.5 rounded flex-shrink-0 bg-violet-900/30">
                <Shield className="w-2.5 h-2.5 text-violet-400" />
              </span>
            )}
            {isMM && !tradeSide && (
              <span className="flex-shrink-0 px-1 py-px rounded text-[9px] font-semibold bg-orange-900/25 text-orange-400 leading-tight tracking-wide">
                MM
              </span>
            )}
            <span className={`text-[11px] font-medium truncate ${isMM ? 'text-orange-300/80' : 'text-navy-200'}`}>
              {name}
            </span>
          </div>
        );
      },
    },
    // 3. ACTION — category pill
    {
      key: 'actionType',
      header: 'Action',
      width: '120px',
      render: (_value, row) => {
        const meta = getActionMeta(row.actionType, row.tags || []);
        const isAdminAction = (row.tags || []).includes('admin');
        const style = PILL_STYLE[isAdminAction ? 'admin' : meta.category];
        const isGroupChild = row._groupId && !row._isGroupStart;
        return (
          <div className="flex items-center gap-1.5">
            {isGroupChild && <Link2 className="w-2.5 h-2.5 flex-shrink-0 text-navy-600" />}
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${style}`}>
              {meta.label}
            </span>
          </div>
        );
      },
    },
    // 4. DETAILS
    {
      key: 'requestPayload',
      header: 'Details',
      width: '220px',
      render: (_value, row) => {
        const amount = extractAmount(row);
        if (!amount) return <span className="text-[10px] text-navy-600">&mdash;</span>;
        return (
          <span className={`text-[11px] font-mono tabular-nums ${amount.isLarge ? 'text-amber-400 font-semibold' : 'text-navy-300'}`}>
            {amount.text}
          </span>
        );
      },
    },
    // 5. RESULT
    {
      key: 'status',
      header: 'Result',
      width: '90px',
      align: 'center',
      render: (_value, row) => {
        const result = extractResult(row);
        if (!result) return <span className="text-[10px] text-navy-600">&mdash;</span>;
        return (
          <span className={`text-[10px] font-medium ${RESULT_CLS[result.variant]}`}>
            {result.variant === 'warning' && <AlertTriangle className="inline w-2.5 h-2.5 mr-0.5 -mt-px" />}
            {result.text}
          </span>
        );
      },
    },
    // 6. TICKET REF
    {
      key: 'ticketId',
      header: 'Ref',
      width: '70px',
      align: 'right',
      render: (value) => (
        <span className="text-[10px] font-mono text-navy-600" title={String(value)}>
          {String(value).replace('TKT-2026-', '#')}
        </span>
      ),
    },
  ];

  // ── Row styling: minimal, with trade direction tints ──
  const getRowClassName = (row: TicketLog) => {
    const classes: string[] = [];
    const isFailed = row.status === 'FAILED';

    if (isFailed) {
      classes.push('!bg-red-950/20 border-l-2 !border-l-red-500/60');
    }

    // Trade direction tint for TRADE_EXECUTED — 30% opacity
    const dir = getTradeDirection(row);
    if (dir === 'ask') {
      // Bought at ask → green tint
      classes.push('!bg-emerald-900/30');
    } else if (dir === 'bid') {
      // Sold at bid → red tint
      classes.push('!bg-red-900/30');
    }

    // Grouped rows
    if (row._groupId && !isFailed) {
      classes.push('border-l-2 !border-l-navy-600/30');
    }

    return classes.join(' ');
  };

  return (
    <div className="space-y-2">
      {/* ── Filters Bar ── */}
      <div className="flex flex-wrap items-center gap-2 px-1">
        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-navy-500" />
          <input
            type="text"
            placeholder="Search ticket, action, entity..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
            className="w-full pl-8 pr-3 py-1.5 border border-navy-700 rounded-md bg-navy-800/50 text-navy-200 text-xs placeholder-navy-500 focus:ring-1 focus:ring-emerald-500/30 focus:border-emerald-500/30 transition-colors"
          />
        </div>

        {/* Category Filter */}
        <div className="flex items-center gap-1">
          <Filter className="w-3 h-3 text-navy-500" />
          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
            className="bg-navy-800/50 border border-navy-700 text-navy-300 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-emerald-500/30"
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="bg-navy-800/50 border border-navy-700 text-navy-300 text-xs rounded-md px-2 py-1.5 focus:ring-1 focus:ring-emerald-500/30"
        >
          <option value="">All Status</option>
          <option value="SUCCESS">Success</option>
          <option value="FAILED">Failed</option>
        </select>

        {/* Live indicator + Refresh */}
        <div className="flex items-center gap-2 ml-auto">
          {wsConnected ? (
            <span className="flex items-center gap-1 text-[10px] text-emerald-500/80 select-none" title="Live streaming">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
              </span>
              LIVE
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[10px] text-navy-500" title="Disconnected — reconnecting...">
              <WifiOff className="w-3 h-3" />
            </span>
          )}
          {pendingCount > 0 && (
            <button
              onClick={() => { setPage(1); setPendingCount(0); }}
              className="text-[10px] text-emerald-400 bg-emerald-900/20 px-1.5 py-0.5 rounded hover:bg-emerald-900/30 transition-colors"
            >
              {pendingCount} new
            </button>
          )}
          <button
            onClick={() => fetchTickets()}
            className="flex items-center gap-1 px-2 py-1 rounded-md border border-navy-700 hover:bg-navy-700/50 transition-colors text-navy-400 hover:text-navy-200"
            title="Refresh"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="text-[10px] tabular-nums">{total.toLocaleString()}</span>
          </button>
        </div>
      </div>

      {/* ── Error ── */}
      {error && <AlertBanner variant="error" message={error} />}

      {/* ── Table ── */}
      <div className="rounded-lg border border-navy-700/50 overflow-hidden">
        <DataTable
          columns={columns}
          data={annotatedTickets}
          loading={initialLoading}
          onRowClick={handleRowClick}
          rowKey="id"
          emptyMessage="No tickets found"
          variant="compact"
          className="bg-navy-800"
          getRowClassName={getRowClassName}
        />
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1">
          <span className="text-[10px] text-navy-500">
            Page {page} of {totalPages} &middot; {total.toLocaleString()} tickets
          </span>
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-1 rounded border border-navy-700/50 disabled:opacity-20 hover:bg-navy-700/40 transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5 text-navy-400" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) pageNum = i + 1;
              else if (page <= 3) pageNum = i + 1;
              else if (page >= totalPages - 2) pageNum = totalPages - 4 + i;
              else pageNum = page - 2 + i;
              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`w-6 h-6 rounded text-[10px] font-medium transition-colors ${
                    pageNum === page
                      ? 'bg-emerald-600/80 text-white'
                      : 'text-navy-400 hover:bg-navy-700/40'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-1 rounded border border-navy-700/50 disabled:opacity-20 hover:bg-navy-700/40 transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5 text-navy-400" />
            </button>
          </div>
        </div>
      )}

      {/* ── Detail Modal ── */}
      <TicketDetailModal
        ticket={selectedTicket}
        isOpen={isModalOpen}
        onClose={() => { setIsModalOpen(false); setSelectedTicket(null); }}
      />
    </div>
  );
}
