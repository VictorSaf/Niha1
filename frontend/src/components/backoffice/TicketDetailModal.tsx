import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  CheckCircle,
  AlertCircle,
  Shield,
  Bot,
  ArrowRight,
  Clock,
  Tag,
  Link2,
  Globe,
  User,
  Banknote,
  FileText,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { Button } from '../common';

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
  // Enriched
  userEmail?: string;
  userRole?: string;
  userCompany?: string;
  userFullName?: string;
  mmName?: string;
}

interface TicketDetailModalProps {
  ticket: TicketLog | null;
  isOpen: boolean;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const fmtNum = (n: number | string | null | undefined, decimals = 2): string => {
  if (n == null) return '—';
  const num = typeof n === 'string' ? parseFloat(n) : n;
  if (isNaN(num)) return '—';
  return num.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

const fmtDate = (iso: string): string => {
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const fmtRelative = (iso: string): string => {
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
};

// ---------------------------------------------------------------------------
// Action display metadata
// ---------------------------------------------------------------------------
const ACTION_LABELS: Record<string, string> = {
  USER_LOGIN: 'User Login',
  USER_LOGIN_MAGIC_LINK: 'Magic Link Login',
  ORDER_PLACED: 'Order Placed',
  ORDER_CANCELLED: 'Order Cancelled',
  ORDER_MODIFIED: 'Order Modified',
  ASSET_TRADE_DEBIT: 'Trade Debit',
  AUTO_TRADE_ORDER_PLACED: 'Auto Trade Order',
  ENTITY_ASSET_DEPOSIT: 'Asset Deposit',
  ENTITY_ASSET_WITHDRAWAL: 'Asset Withdrawal',
  DEPOSIT_ANNOUNCED: 'Deposit Announced',
  DEPOSIT_CONFIRMED: 'Deposit Confirmed',
  DEPOSIT_CLEARED: 'Deposit Cleared',
  KYC_DOCUMENT_UPLOADED: 'KYC Document Upload',
  KYC_SUBMITTED: 'KYC Submitted',
  MM_CREATED: 'Market Maker Created',
  MM_UPDATED: 'Market Maker Updated',
  MM_DELETED: 'Market Maker Deleted',
  MM_RESET_ALL: 'All Market Makers Reset',
  MM_EUR_DEPOSIT: 'MM EUR Deposit',
  MM_EUR_WITHDRAWAL: 'MM EUR Withdrawal',
  SWAP_CREATED: 'Swap Request',
  SWAP_EXECUTED: 'Swap Executed',
  WITHDRAWAL_REQUESTED: 'Withdrawal Request',
  WITHDRAWAL_APPROVED: 'Withdrawal Approved',
  WITHDRAWAL_COMPLETED: 'Withdrawal Completed',
  WITHDRAWAL_REJECTED: 'Withdrawal Rejected',
  TRADE_EXECUTED: 'Trade Executed',
};

function getActionLabel(at: string): string {
  return ACTION_LABELS[at] || at.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Extract structured detail rows from ticket data
// ---------------------------------------------------------------------------
interface DetailRow {
  label: string;
  value: string;
  icon?: 'up' | 'down' | 'money' | 'arrow';
  highlight?: boolean;
  mono?: boolean;
}

function extractDetails(t: TicketLog): DetailRow[] {
  const rows: DetailRow[] = [];
  const req = t.requestPayload;
  const res = t.responseData;
  const at = t.actionType;

  // ---- Trading orders ----
  if (at === 'ORDER_PLACED' && req) {
    const side = String(req.side || '').toUpperCase();
    rows.push({ label: 'Side', value: side, icon: side === 'BUY' ? 'up' : 'down', highlight: true });
    rows.push({ label: 'Certificate', value: String(req.certificate_type || req.certificateType || 'CEA') });
    rows.push({ label: 'Quantity', value: fmtNum(req.quantity as number, 0), mono: true });
    rows.push({ label: 'Price', value: `€${fmtNum(req.price as number)}`, mono: true, highlight: true });
    if (res?.status) rows.push({ label: 'Order Status', value: String(res.status) });
    if (res?.orderId || res?.order_id)
      rows.push({ label: 'Order ID', value: String(res.orderId || res.order_id).slice(0, 12) + '...', mono: true });
  }

  // ---- Auto trade ----
  if (at === 'AUTO_TRADE_ORDER_PLACED') {
    const side = t.tags.includes('buy') ? 'BUY' : t.tags.includes('sell') ? 'SELL' : '';
    if (side) rows.push({ label: 'Side', value: side, icon: side === 'BUY' ? 'up' : 'down', highlight: true });
    if (res) {
      rows.push({ label: 'Certificate', value: String(res.certificate_type || res.certificateType || 'CEA') });
      rows.push({ label: 'Quantity', value: fmtNum(res.quantity as number, 0), mono: true });
      rows.push({ label: 'Price', value: `€${fmtNum(res.price as number)}`, mono: true, highlight: true });
      if (res.orderId || res.order_id)
        rows.push({ label: 'Order ID', value: String(res.orderId || res.order_id).slice(0, 12) + '...', mono: true });
    }
    if (req) {
      if (req.ruleName || req.rule_name)
        rows.push({ label: 'Rule', value: String(req.ruleName || req.rule_name) });
      if (req.priceMode || req.price_mode)
        rows.push({ label: 'Price Mode', value: String(req.priceMode || req.price_mode).replace(/_/g, ' ') });
      if (req.quantityMode || req.quantity_mode)
        rows.push({ label: 'Quantity Mode', value: String(req.quantityMode || req.quantity_mode).replace(/_/g, ' ') });
    }
  }

  // ---- Trade debit ----
  if (at === 'ASSET_TRADE_DEBIT' && req) {
    const cert = String(req.certificate_type || req.certificateType || '');
    rows.push({ label: 'Asset', value: cert });
    rows.push({ label: 'Amount Debited', value: `${fmtNum(req.amount as number, 0)} ${cert}`, icon: 'down', mono: true, highlight: true });
  }

  // ---- Order cancelled ----
  if (at === 'ORDER_CANCELLED') {
    if (req?.order_id || req?.orderId)
      rows.push({ label: 'Order ID', value: String(req?.order_id || req?.orderId).slice(0, 12) + '...', mono: true });
    if (res?.side || res?.order_side) {
      const side = String(res.side || res.order_side).toUpperCase();
      rows.push({ label: 'Side', value: side, icon: side === 'BUY' ? 'up' : 'down' });
    }
    if (res?.quantity) rows.push({ label: 'Quantity', value: fmtNum(res.quantity as number, 0), mono: true });
    if (res?.price) rows.push({ label: 'Price', value: `€${fmtNum(res.price as number)}`, mono: true });
  }

  // ---- Order modified ----
  if (at === 'ORDER_MODIFIED') {
    if (res) {
      if (res.old_price != null && res.new_price != null) {
        rows.push({
          label: 'Price Change',
          value: `€${fmtNum(res.old_price as number)} → €${fmtNum(res.new_price as number)}`,
          icon: 'arrow',
          highlight: true,
          mono: true,
        });
      }
      if (res.orderId || res.order_id)
        rows.push({ label: 'Order ID', value: String(res.orderId || res.order_id).slice(0, 12) + '...', mono: true });
    }
  }

  // ---- Deposit announced ----
  if (at === 'DEPOSIT_ANNOUNCED' && req) {
    rows.push({ label: 'Amount', value: `€${fmtNum(req.amount as number)}`, icon: 'money', mono: true, highlight: true });
    if (req.currency) rows.push({ label: 'Currency', value: String(req.currency) });
    if (req.reference) rows.push({ label: 'Reference', value: String(req.reference), mono: true });
  }

  // ---- Deposit confirmed ----
  if (at === 'DEPOSIT_CONFIRMED') {
    if (req) {
      const amt = req.actual_amount || req.actualAmount;
      if (amt != null) rows.push({ label: 'Confirmed Amount', value: `€${fmtNum(amt as number)}`, icon: 'money', mono: true, highlight: true });
    }
    if (res) {
      if (res.hold_type || res.holdType)
        rows.push({ label: 'Hold Type', value: String(res.hold_type || res.holdType).replace(/_/g, ' ') });
    }
  }

  // ---- Deposit cleared ----
  if (at === 'DEPOSIT_CLEARED' && res) {
    if (res.amount != null) rows.push({ label: 'Amount Cleared', value: `€${fmtNum(res.amount as number)}`, icon: 'money', mono: true, highlight: true });
    const upgraded = Number(res.upgraded_users || res.upgradedUsers || 0);
    if (upgraded > 0) rows.push({ label: 'Users Upgraded', value: String(upgraded), highlight: true });
  }

  // ---- Asset deposit/withdrawal ----
  if (at === 'ENTITY_ASSET_DEPOSIT' || at === 'ENTITY_ASSET_WITHDRAWAL') {
    const src = t.afterState || req;
    if (src) {
      const cert = String(src.asset_type || src.assetType || src.certificate_type || src.certificateType || '');
      const isDeposit = at === 'ENTITY_ASSET_DEPOSIT';
      rows.push({
        label: isDeposit ? 'Deposited' : 'Withdrawn',
        value: `${fmtNum(src.amount as number, 0)} ${cert}`,
        icon: isDeposit ? 'up' : 'down',
        mono: true,
        highlight: true,
      });
      if (src.balance_before != null || src.balanceBefore != null) {
        const before = src.balance_before ?? src.balanceBefore;
        const after = src.balance_after ?? src.balanceAfter;
        rows.push({
          label: 'Balance Change',
          value: `${fmtNum(before as number, 0)} → ${fmtNum(after as number, 0)} ${cert}`,
          icon: 'arrow',
          mono: true,
        });
      }
    }
  }

  // ---- MM EUR deposit/withdrawal ----
  if ((at === 'MM_EUR_DEPOSIT' || at === 'MM_EUR_WITHDRAWAL') && req) {
    const isDeposit = at === 'MM_EUR_DEPOSIT';
    rows.push({
      label: isDeposit ? 'EUR Credited' : 'EUR Withdrawn',
      value: `€${fmtNum(req.amount as number)}`,
      icon: isDeposit ? 'up' : 'down',
      mono: true,
      highlight: true,
    });
  }

  // ---- MM Created ----
  if (at === 'MM_CREATED' && req) {
    if (req.name) rows.push({ label: 'MM Name', value: String(req.name) });
    if (req.initial_eur_balance || req.initialEurBalance)
      rows.push({ label: 'Initial Balance', value: `€${fmtNum((req.initial_eur_balance || req.initialEurBalance) as number)}`, icon: 'money', mono: true });
    if (req.side) rows.push({ label: 'Side', value: String(req.side).toUpperCase() });
    if (req.certificate_type || req.certificateType)
      rows.push({ label: 'Certificate', value: String(req.certificate_type || req.certificateType) });
  }

  // ---- MM Updated ----
  if (at === 'MM_UPDATED' && req) {
    // Show what was updated - iterate over request keys
    for (const [k, v] of Object.entries(req)) {
      if (v != null && k !== 'market_maker_id' && k !== 'marketMakerId') {
        const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        rows.push({ label, value: String(v) });
      }
    }
  }

  // ---- KYC ----
  if (at === 'KYC_DOCUMENT_UPLOADED' && req) {
    if (req.file_name || req.fileName) rows.push({ label: 'File', value: String(req.file_name || req.fileName) });
    if (req.document_type || req.documentType) rows.push({ label: 'Document Type', value: String(req.document_type || req.documentType) });
  }

  // ---- Login ----
  if ((at === 'USER_LOGIN' || at === 'USER_LOGIN_MAGIC_LINK') && t.ipAddress) {
    rows.push({ label: 'IP Address', value: t.ipAddress, mono: true });
  }

  // ---- Swap ----
  if (at === 'SWAP_CREATED' && req) {
    if (req.from_type || req.fromType) rows.push({ label: 'From', value: String(req.from_type || req.fromType) });
    if (req.to_type || req.toType) rows.push({ label: 'To', value: String(req.to_type || req.toType) });
    if (req.quantity != null) rows.push({ label: 'Quantity', value: fmtNum(req.quantity as number, 0), mono: true, highlight: true });
    if (req.desired_rate != null || req.desiredRate != null) rows.push({ label: 'Desired rate', value: fmtNum((req.desired_rate ?? req.desiredRate) as number, 4), mono: true });
    if (req.anonymous_code || req.anonymousCode) rows.push({ label: 'Code', value: String(req.anonymous_code || req.anonymousCode), mono: true });
  }
  if (at === 'SWAP_EXECUTED' && req) {
    if (req.cea_quantity != null || req.ceaQuantity != null) rows.push({ label: 'CEA', value: fmtNum((req.cea_quantity ?? req.ceaQuantity) as number, 0), mono: true, highlight: true });
    if (req.eua_output != null || req.euaOutput != null) rows.push({ label: 'EUA', value: fmtNum((req.eua_output ?? req.euaOutput) as number, 0), mono: true, highlight: true });
    if (req.weighted_avg_ratio != null || req.weightedAvgRatio != null) rows.push({ label: 'Avg ratio', value: fmtNum((req.weighted_avg_ratio ?? req.weightedAvgRatio) as number, 4), mono: true });
    if (req.matched_orders_count != null || req.matchedOrdersCount != null) rows.push({ label: 'Matched orders', value: String(req.matched_orders_count ?? req.matchedOrdersCount) });
  }

  // ---- Withdrawal ----
  if ((at === 'WITHDRAWAL_REQUESTED' || at === 'WITHDRAWAL_APPROVED' || at === 'WITHDRAWAL_COMPLETED' || at === 'WITHDRAWAL_REJECTED') && (req || res)) {
    const src = req || res;
    if (src?.amount != null && src?.asset_type != null) rows.push({ label: 'Amount', value: `${fmtNum(src.amount as number)} ${String(src.asset_type)}`, icon: 'money', mono: true, highlight: true });
    if (src?.internal_reference || src?.internalReference) rows.push({ label: 'Reference', value: String(src.internal_reference ?? src.internalReference), mono: true });
    if (at === 'WITHDRAWAL_REJECTED' && req?.rejection_reason) rows.push({ label: 'Reason', value: String(req.rejection_reason), highlight: true });
  }

  // ---- Trade executed (counterparties in dedicated section below) ----
  if (at === 'TRADE_EXECUTED' && res) {
    rows.push({ label: 'Certificate', value: String(res.certificate_type || res.certificateType || 'CEA') });
    rows.push({ label: 'Quantity', value: fmtNum(res.quantity as number, 0), mono: true, highlight: true });
    rows.push({ label: 'Price', value: `€${fmtNum(res.price as number)}`, mono: true });
  }

  return rows;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function TicketDetailModal({ ticket, isOpen, onClose }: TicketDetailModalProps) {
  if (!isOpen || !ticket) return null;

  const actionLabel = getActionLabel(ticket.actionType);
  const isSuccess = ticket.status === 'SUCCESS';
  const isMM = !!ticket.mmName || ticket.userRole === 'MM';
  const isAdmin = ticket.userRole === 'ADMIN';
  const actorName = ticket.mmName
    || ticket.userCompany
    || ticket.userFullName
    || ticket.userEmail
    || 'Unknown';
  const adminInitiated = isAdmin && !!ticket.mmName;
  const details = extractDetails(ticket);
  const hasStateChange = ticket.beforeState && ticket.afterState;

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
        onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.15 }}
          className="bg-navy-800 rounded-xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-hidden flex flex-col"
        >
          {/* ── Header ── */}
          <div className="flex items-start justify-between p-5 pb-4 border-b border-navy-700">
            <div className="flex items-start gap-3 min-w-0">
              <div className={`p-2 rounded-lg flex-shrink-0 ${
                isSuccess
                  ? 'bg-emerald-900/20'
                  : 'bg-red-900/20'
              }`}>
                {isSuccess
                  ? <CheckCircle className="w-5 h-5 text-emerald-400" />
                  : <AlertCircle className="w-5 h-5 text-red-400" />
                }
              </div>
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-white truncate">
                  {actionLabel}
                </h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-navy-400 font-mono">
                    #{ticket.ticketId.replace('TKT-2026-', '')}
                  </span>
                  <span className="text-navy-600">·</span>
                  <span className={`text-xs font-medium ${
                    isSuccess
                      ? 'text-emerald-400'
                      : 'text-red-400'
                  }`}>
                    {isSuccess ? 'Success' : 'Failed'}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-navy-700 rounded-lg transition-colors flex-shrink-0"
            >
              <X className="w-4 h-4 text-navy-400" />
            </button>
          </div>

          {/* ── Scrollable Body ── */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">

            {/* ── Actor Card ── */}
            <div className="rounded-lg bg-navy-900/40 border border-navy-700 p-3">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-navy-500 mb-2">
                Actor
              </div>
              <div className="flex items-center gap-2">
                {adminInitiated && (
                  <span title="Admin initiated" className="flex items-center justify-center w-5 h-5 rounded bg-violet-900/40 flex-shrink-0">
                    <Shield className="w-3 h-3 text-violet-400" />
                  </span>
                )}
                {isMM && (
                  <span className="flex items-center justify-center w-5 h-5 rounded bg-orange-900/40 flex-shrink-0">
                    <Bot className="w-3 h-3 text-orange-400" />
                  </span>
                )}
                {!isMM && !adminInitiated && (
                  <span className="flex items-center justify-center w-5 h-5 rounded bg-navy-700 flex-shrink-0">
                    <User className="w-3 h-3 text-navy-400" />
                  </span>
                )}
                <span className={`text-sm font-medium ${
                  isMM
                    ? 'text-orange-400'
                    : 'text-white'
                }`}>
                  {actorName}
                </span>
              </div>
              {adminInitiated && (
                <div className="mt-1.5 pl-7 text-[11px] text-violet-400">
                  Initiated by Admin ({ticket.userCompany || 'Nihao Group'})
                </div>
              )}
              {!adminInitiated && isAdmin && (
                <div className="mt-1.5 pl-7 text-[11px] text-navy-500">
                  Admin account
                </div>
              )}
            </div>

            {/* ── Counterparties (trades only) ── */}
            {ticket.actionType === 'TRADE_EXECUTED' && (
              <div className="rounded-xl border-2 border-navy-600 bg-navy-900/50 p-4">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-navy-400 mb-3">
                  Counterparties
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-lg bg-emerald-900/20 border border-emerald-700/40 p-3">
                    <div className="text-[10px] font-medium uppercase tracking-wider text-emerald-500/90 mb-1">Buyer</div>
                    <div className="text-sm font-semibold text-emerald-400 truncate" title={String((ticket as Record<string, unknown>).buyerMmName ?? (ticket as Record<string, unknown>).buyer_mm_name ?? (ticket as Record<string, unknown>).buyerEntityName ?? (ticket as Record<string, unknown>).buyer_entity_name ?? ticket.responseData?.buyer_mm_id ?? '—')}>
                      {String((ticket as Record<string, unknown>).buyerMmName ?? (ticket as Record<string, unknown>).buyer_mm_name ?? (ticket as Record<string, unknown>).buyerEntityName ?? (ticket as Record<string, unknown>).buyer_entity_name ?? '—').replace(/^Market Maker\s+/i, '')}
                    </div>
                  </div>
                  <div className="rounded-lg bg-amber-900/20 border border-amber-700/40 p-3">
                    <div className="text-[10px] font-medium uppercase tracking-wider text-amber-500/90 mb-1">Seller</div>
                    <div className="text-sm font-semibold text-amber-400 truncate" title={String((ticket as Record<string, unknown>).sellerMmName ?? (ticket as Record<string, unknown>).seller_mm_name ?? (ticket as Record<string, unknown>).sellerEntityName ?? (ticket as Record<string, unknown>).seller_entity_name ?? ticket.responseData?.seller_mm_id ?? '—')}>
                      {String((ticket as Record<string, unknown>).sellerMmName ?? (ticket as Record<string, unknown>).seller_mm_name ?? (ticket as Record<string, unknown>).sellerEntityName ?? (ticket as Record<string, unknown>).seller_entity_name ?? '—').replace(/^Market Maker\s+/i, '')}
                    </div>
                  </div>
                </div>
                {Boolean(ticket.requestPayload?.aggressor_side || ticket.requestPayload?.aggressorSide) && (
                  <div className="mt-2 text-[10px] text-navy-500">
                    Aggressor: <span className="font-medium text-navy-400">
                      {String(ticket.requestPayload?.aggressor_side ?? ticket.requestPayload?.aggressorSide ?? '').toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* ── Action Details ── */}
            {details.length > 0 && (
              <div className="rounded-lg bg-navy-900/40 border border-navy-700 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-navy-500 mb-2">
                  Details
                </div>
                <div className="space-y-1.5">
                  {details.map((row, i) => (
                    <div key={i} className="flex items-center justify-between gap-3">
                      <span className="text-xs text-navy-400 flex items-center gap-1.5 flex-shrink-0">
                        <DetailIcon type={row.icon} />
                        {row.label}
                      </span>
                      <span className={`text-xs text-right truncate ${
                        row.highlight
                          ? 'font-semibold text-white'
                          : 'text-navy-300'
                      } ${row.mono ? 'font-mono tabular-nums' : ''}`}>
                        {row.value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── State Change (before → after) ── */}
            {hasStateChange && (
              <div className="rounded-lg bg-navy-900/40 border border-navy-700 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-navy-500 mb-2">
                  State Change
                </div>
                <StateChangeDiff before={ticket.beforeState!} after={ticket.afterState!} />
              </div>
            )}

            {/* ── Related Tickets ── */}
            {ticket.relatedTicketIds && ticket.relatedTicketIds.length > 0 && (
              <div className="rounded-lg bg-navy-900/40 border border-navy-700 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-navy-500 mb-2">
                  Related Tickets
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {ticket.relatedTicketIds.map((ref, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded bg-blue-900/30 text-blue-400 border border-blue-800"
                    >
                      <Link2 className="w-2.5 h-2.5" />
                      #{ref.replace('TKT-2026-', '')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* ── Tags ── */}
            {ticket.tags && ticket.tags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <Tag className="w-3 h-3 text-navy-500" />
                {ticket.tags.map((tag, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-navy-700 text-navy-400"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {/* ── Metadata footer ── */}
            <div className="pt-2 border-t border-navy-700/50 space-y-1">
              <div className="flex items-center gap-1.5 text-[11px] text-navy-500">
                <Clock className="w-3 h-3" />
                {fmtDate(ticket.timestamp)}
                <span className="text-navy-600">·</span>
                {fmtRelative(ticket.timestamp)}
              </div>
              {ticket.ipAddress && (
                <div className="flex items-center gap-1.5 text-[11px] text-navy-500">
                  <Globe className="w-3 h-3" />
                  {ticket.ipAddress}
                </div>
              )}
              <div className="flex items-center gap-1.5 text-[11px] text-navy-500 font-mono">
                <FileText className="w-3 h-3" />
                {ticket.ticketId}
              </div>
            </div>
          </div>

          {/* ── Footer ── */}
          <div className="flex items-center justify-end p-4 border-t border-navy-700">
            <Button onClick={onClose} variant="secondary" size="sm">
              Close
            </Button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DetailIcon({ type }: { type?: 'up' | 'down' | 'money' | 'arrow' }) {
  if (!type) return null;
  const cls = 'w-3 h-3';
  switch (type) {
    case 'up': return <ArrowUpRight className={`${cls} text-emerald-500`} />;
    case 'down': return <ArrowDownRight className={`${cls} text-red-500`} />;
    case 'money': return <Banknote className={`${cls} text-blue-500`} />;
    case 'arrow': return <ArrowRight className={`${cls} text-navy-400`} />;
    default: return null;
  }
}

function StateChangeDiff({ before, after }: { before: Record<string, unknown>; after: Record<string, unknown> }) {
  // Merge all keys from both states
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  const changes: { key: string; from: string; to: string }[] = [];

  for (const key of keys) {
    const bv = before[key];
    const av = after[key];
    const bStr = bv != null ? String(bv) : '—';
    const aStr = av != null ? String(av) : '—';
    if (bStr !== aStr) {
      const label = key
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/\b\w/g, c => c.toUpperCase());
      changes.push({ key: label, from: bStr, to: aStr });
    }
  }

  if (changes.length === 0) {
    return <div className="text-xs text-navy-500 italic">No visible changes</div>;
  }

  return (
    <div className="space-y-1.5">
      {changes.map((c, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="text-navy-400 w-24 flex-shrink-0 truncate">{c.key}</span>
          <span className="font-mono text-red-400/60 line-through tabular-nums truncate max-w-[100px]">
            {c.from}
          </span>
          <ArrowRight className="w-3 h-3 text-navy-500 flex-shrink-0" />
          <span className="font-mono text-emerald-400 font-medium tabular-nums truncate max-w-[100px]">
            {c.to}
          </span>
        </div>
      ))}
    </div>
  );
}
