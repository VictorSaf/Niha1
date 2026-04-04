import { useState, useEffect, useCallback } from 'react';
import { Send, DollarSign, Clock, CheckCircle2, Copy, Check } from 'lucide-react';
import { Badge } from '../common';
import { introducerApi } from '../../services/api';
import { useAuthStore } from '../../stores/useStore';
import { parseUtcDate } from '../../utils';

// ─── Types ───────────────────────────────────────────────────
interface Invitation {
  id: string;
  invitedEmail: string;
  invitedFirstName?: string;
  status: string;
  createdAt: string;
  clickedAt?: string;
  registeredAt?: string;
}

interface CommissionSummary {
  lifetimeEur: number;
  commissionRate: number;
  pending: { total: number; count: number };
  confirmed: { total: number; count: number };
  paid: { total: number; count: number };
}

interface CommissionEntry {
  id: string;
  tradeEurValue: number;
  commissionRate: number;
  commissionEur: number;
  status: string;
  tradeExecutedAt: string;
  createdAt: string;
}

// ─── Helpers ─────────────────────────────────────────────────
function formatEur(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(iso: string): string {
  return (parseUtcDate(iso) ?? new Date(iso)).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatPct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

// ─── Status Badge ────────────────────────────────────────────
function InvitationStatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, 'default' | 'warning' | 'success' | 'danger'> = {
    pending: 'default',
    clicked: 'warning',
    registered: 'success',
    expired: 'danger',
  };
  return <Badge variant={variantMap[status] || 'default'}>{status}</Badge>;
}

function CommissionStatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, 'default' | 'warning' | 'success' | 'info'> = {
    pending: 'warning',
    confirmed: 'success',
    paid: 'info',
  };
  return <Badge variant={variantMap[status] || 'default'}>{status}</Badge>;
}

// ─── Skeleton ────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-6">
        <div className="h-5 w-40 bg-navy-700 rounded mb-4" />
        <div className="space-y-3">
          <div className="h-10 bg-navy-700 rounded" />
          <div className="h-10 bg-navy-700 rounded" />
          <div className="h-10 bg-navy-700 rounded w-1/2" />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-navy-900/50 rounded-lg p-4 border border-navy-700">
            <div className="h-4 w-24 bg-navy-700 rounded mb-2" />
            <div className="h-6 w-16 bg-navy-700 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────
export function ReferralsSection() {
  const user = useAuthStore((s) => s.user);
  const referralCode = user?.referralCode || '';

  // Data state
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [commissionSummary, setCommissionSummary] = useState<CommissionSummary | null>(null);
  const [commissions, setCommissions] = useState<CommissionEntry[]>([]);

  // Loading / error
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [personalNote, setPersonalNote] = useState('');
  const [sending, setSending] = useState(false);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  // Copy state for referral code
  const [copied, setCopied] = useState(false);

  // ── Data loading ────────────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [invRes, summaryRes, commRes] = await Promise.all([
        introducerApi.getInvitations(),
        introducerApi.getCommissionSummary(),
        introducerApi.getCommissions(),
      ]);
      setInvitations(Array.isArray(invRes) ? invRes : []);
      setCommissionSummary(summaryRes);
      setCommissions(Array.isArray(commRes) ? commRes : []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load referral data';
      setError(typeof (err as { message?: string })?.message === 'string' ? (err as { message: string }).message : msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Send invitation ─────────────────────────────────────────
  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setSending(true);
    setSendSuccess(null);
    setSendError(null);

    try {
      await introducerApi.sendInvitation({
        email: email.trim(),
        first_name: firstName.trim() || undefined,
        personal_note: personalNote.trim() || undefined,
      });
      setSendSuccess(`Invitation sent to ${email}`);
      setEmail('');
      setFirstName('');
      setPersonalNote('');
      // Refresh invitations list
      const invRes = await introducerApi.getInvitations();
      setInvitations(Array.isArray(invRes) ? invRes : []);
    } catch (err: unknown) {
      const msg = typeof (err as { message?: string })?.message === 'string'
        ? (err as { message: string }).message
        : 'Failed to send invitation';
      setSendError(msg);
    } finally {
      setSending(false);
    }
  };

  // ── Copy referral code ──────────────────────────────────────
  const handleCopy = async () => {
    if (!referralCode) return;
    try {
      await navigator.clipboard.writeText(referralCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: do nothing
    }
  };

  if (loading) return <LoadingSkeleton />;

  return (
    <div className="space-y-8">
      {/* ── Error Banner ──────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* ── Referral Code ─────────────────────────────────────── */}
      {referralCode && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-6">
          <h3 className="text-lg font-semibold text-white mb-3">Your Referral Code</h3>
          <div className="flex items-center gap-3">
            <code className="bg-navy-900 border border-navy-600 rounded-lg px-4 py-2 text-lg font-mono text-emerald-400 tracking-widest select-all">
              {referralCode}
            </code>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-navy-700 hover:bg-navy-600 text-navy-200 text-sm transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
          <p className="text-xs text-navy-400 mt-2">
            Share this code with potential clients. They can use it when signing up.
          </p>
        </div>
      )}

      {/* ── Send Invitation Form ──────────────────────────────── */}
      <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Send className="w-5 h-5 text-emerald-400" />
          Send Invitation
        </h3>

        <form onSubmit={handleSend} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-navy-400 mb-1">Email *</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="client@company.com"
                className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-navy-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-navy-400 mb-1">First Name (optional)</label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="John"
                className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-navy-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-navy-400 mb-1">
              Personal Note (optional, max 200 chars)
            </label>
            <textarea
              value={personalNote}
              onChange={(e) => setPersonalNote(e.target.value.slice(0, 200))}
              placeholder="Hi, I'd like to introduce you to NIHA's carbon trading platform..."
              rows={3}
              maxLength={200}
              className="w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-navy-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none resize-none"
            />
            <span className="text-xs text-navy-500">{personalNote.length}/200</span>
          </div>

          <div className="flex items-center gap-4">
            <button
              type="submit"
              disabled={sending || !email.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              <Send className="w-4 h-4" />
              {sending ? 'Sending...' : 'Send Invitation'}
            </button>

            {sendSuccess && (
              <span className="flex items-center gap-1.5 text-sm text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                {sendSuccess}
              </span>
            )}
            {sendError && (
              <span className="text-sm text-red-400">{sendError}</span>
            )}
          </div>
        </form>
      </div>

      {/* ── Invitations Table ─────────────────────────────────── */}
      <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          Sent Invitations
          {invitations.length > 0 && (
            <span className="ml-2 text-sm font-normal text-navy-400">({invitations.length})</span>
          )}
        </h3>

        {invitations.length === 0 ? (
          <p className="text-sm text-navy-400 py-4 text-center">
            No invitations sent yet. Use the form above to invite potential clients.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-navy-700">
                  <th className="text-left text-xs text-navy-400 font-medium pb-3 pr-4">Email</th>
                  <th className="text-left text-xs text-navy-400 font-medium pb-3 pr-4">Name</th>
                  <th className="text-left text-xs text-navy-400 font-medium pb-3 pr-4">Status</th>
                  <th className="text-left text-xs text-navy-400 font-medium pb-3">Sent</th>
                </tr>
              </thead>
              <tbody>
                {invitations.map((inv) => (
                  <tr key={inv.id} className="border-b border-navy-700/50 last:border-b-0">
                    <td className="py-3 pr-4 text-sm text-navy-200">{inv.invitedEmail}</td>
                    <td className="py-3 pr-4 text-sm text-navy-300">{inv.invitedFirstName || '-'}</td>
                    <td className="py-3 pr-4">
                      <InvitationStatusBadge status={inv.status} />
                    </td>
                    <td className="py-3 text-sm text-navy-300">{formatDate(inv.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Commission Summary Cards ──────────────────────────── */}
      {commissionSummary && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            Commissions
            <span className="ml-2 text-sm font-normal text-navy-400">
              Rate: {formatPct(commissionSummary.commissionRate)}
            </span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {/* Lifetime Earnings */}
            <div className="bg-navy-900/50 rounded-lg p-4 border border-navy-700">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-navy-400">Lifetime Earnings</span>
              </div>
              <p className="text-xl font-semibold text-white">{formatEur(commissionSummary.lifetimeEur)}</p>
            </div>

            {/* Pending */}
            <div className="bg-navy-900/50 rounded-lg p-4 border border-navy-700">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-4 h-4 text-amber-400" />
                <span className="text-xs text-navy-400">Pending</span>
              </div>
              <p className="text-xl font-semibold text-white">{formatEur(commissionSummary.pending.total)}</p>
              <p className="text-xs text-navy-500 mt-0.5">{commissionSummary.pending.count} trade{commissionSummary.pending.count !== 1 ? 's' : ''}</p>
            </div>

            {/* Confirmed */}
            <div className="bg-navy-900/50 rounded-lg p-4 border border-navy-700">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-navy-400">Confirmed</span>
              </div>
              <p className="text-xl font-semibold text-white">{formatEur(commissionSummary.confirmed.total)}</p>
              <p className="text-xs text-navy-500 mt-0.5">{commissionSummary.confirmed.count} trade{commissionSummary.confirmed.count !== 1 ? 's' : ''}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Commission History Table ──────────────────────────── */}
      {commissions.length > 0 && (
        <div className="rounded-xl border border-navy-700 bg-navy-800/50 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Commission History</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-navy-700">
                  <th className="text-left text-xs text-navy-400 font-medium pb-3 pr-4">Date</th>
                  <th className="text-right text-xs text-navy-400 font-medium pb-3 pr-4">Trade Value</th>
                  <th className="text-right text-xs text-navy-400 font-medium pb-3 pr-4">Rate</th>
                  <th className="text-right text-xs text-navy-400 font-medium pb-3 pr-4">Commission</th>
                  <th className="text-left text-xs text-navy-400 font-medium pb-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {commissions.map((c) => (
                  <tr key={c.id} className="border-b border-navy-700/50 last:border-b-0">
                    <td className="py-3 pr-4 text-sm text-navy-300">{formatDate(c.tradeExecutedAt)}</td>
                    <td className="py-3 pr-4 text-sm text-navy-200 text-right">{formatEur(c.tradeEurValue)}</td>
                    <td className="py-3 pr-4 text-sm text-navy-300 text-right">{formatPct(c.commissionRate)}</td>
                    <td className="py-3 pr-4 text-sm text-emerald-400 text-right font-medium">{formatEur(c.commissionEur)}</td>
                    <td className="py-3">
                      <CommissionStatusBadge status={c.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
