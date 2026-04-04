/**
 * WithdrawalsTab - Admin interface for managing withdrawal requests
 *
 * Features:
 * - View pending/processing withdrawal requests
 * - Approve, complete, or reject withdrawals
 * - Statistics dashboard
 */

import React, { useState, useEffect } from 'react';
import {
  ArrowUpRight,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  DollarSign,
  Building2,
  User,
  Calendar,
} from 'lucide-react';
import { AlertBanner, LoadingState } from '../common';
import { withdrawalApi } from '../../services/api';
import { getApiErrorMessage } from '../../utils/errors';
import { parseUtcDate } from '../../utils';
import type {
  Withdrawal,
  WithdrawalStats,
  WithdrawalStatus,
  AssetType,
} from '../../types';

// Asset type colors (design system: navy/emerald/amber/blue/red)
const ASSET_COLORS: Record<AssetType, string> = {
  EUR: 'bg-emerald-500/20 text-emerald-400',
  CEA: 'bg-amber-500/20 text-amber-400',
  EUA: 'bg-blue-500/20 text-blue-400',
};

// Status colors (design system tokens)
const STATUS_COLORS: Record<WithdrawalStatus, string> = {
  PENDING: 'bg-amber-500/20 text-amber-400',
  PROCESSING: 'bg-blue-500/20 text-blue-400',
  COMPLETED: 'bg-emerald-500/20 text-emerald-400',
  REJECTED: 'bg-red-500/20 text-red-400',
};

export const WithdrawalsTab: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pending' | 'processing'>('pending');
  const [pendingWithdrawals, setPendingWithdrawals] = useState<Withdrawal[]>([]);
  const [processingWithdrawals, setProcessingWithdrawals] = useState<Withdrawal[]>([]);
  const [stats, setStats] = useState<WithdrawalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [selectedWithdrawal, setSelectedWithdrawal] = useState<Withdrawal | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Form states
  const [adminNotes, setAdminNotes] = useState('');
  const [wireReference, setWireReference] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pending, processing, statsData] = await Promise.all([
        withdrawalApi.getPendingWithdrawals(),
        withdrawalApi.getProcessingWithdrawals(),
        withdrawalApi.getWithdrawalStats(),
      ]);
      setPendingWithdrawals(pending);
      setProcessingWithdrawals(processing);
      setStats(statsData);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleApprove = async () => {
    if (!selectedWithdrawal) return;
    setActionLoading(true);
    try {
      const result = await withdrawalApi.approveWithdrawal(selectedWithdrawal.id, {
        adminNotes: adminNotes || undefined,
      });
      if (result.success) {
        await fetchData();
        closeModals();
      } else {
        setError(result.error || 'Failed to approve withdrawal');
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    if (!selectedWithdrawal) return;
    setActionLoading(true);
    try {
      const result = await withdrawalApi.completeWithdrawal(selectedWithdrawal.id, {
        wireReference: wireReference || undefined,
        adminNotes: adminNotes || undefined,
      });
      if (result.success) {
        await fetchData();
        closeModals();
      } else {
        setError(result.error || 'Failed to complete withdrawal');
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedWithdrawal || !rejectionReason) return;
    setActionLoading(true);
    try {
      const result = await withdrawalApi.rejectWithdrawal(selectedWithdrawal.id, {
        rejectionReason: rejectionReason,
        adminNotes: adminNotes || undefined,
      });
      if (result.success) {
        await fetchData();
        closeModals();
      } else {
        setError(result.error || 'Failed to reject withdrawal');
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const closeModals = () => {
    setShowApproveModal(false);
    setShowCompleteModal(false);
    setShowRejectModal(false);
    setSelectedWithdrawal(null);
    setAdminNotes('');
    setWireReference('');
    setRejectionReason('');
  };

  const openApproveModal = (withdrawal: Withdrawal) => {
    setSelectedWithdrawal(withdrawal);
    setShowApproveModal(true);
  };

  const openCompleteModal = (withdrawal: Withdrawal) => {
    setSelectedWithdrawal(withdrawal);
    setShowCompleteModal(true);
  };

  const openRejectModal = (withdrawal: Withdrawal) => {
    setSelectedWithdrawal(withdrawal);
    setShowRejectModal(true);
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return parseUtcDate(dateStr)?.toLocaleString() ?? '—';
  };

  const formatAmount = (amount: number, assetType: AssetType) => {
    if (assetType === 'EUR') {
      return `€${amount.toLocaleString()}`;
    }
    return `${amount.toLocaleString()} ${assetType}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingState variant="spinner" size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-navy-400">Pending</p>
                <p className="text-2xl font-semibold text-amber-500">{stats.pending}</p>
              </div>
              <Clock className="h-8 w-8 text-amber-400" />
            </div>
          </div>
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-navy-400">Processing</p>
                <p className="text-2xl font-semibold text-blue-500">{stats.processing}</p>
              </div>
              <ArrowUpRight className="h-8 w-8 text-blue-400" />
            </div>
          </div>
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-navy-400">Completed</p>
                <p className="text-2xl font-semibold text-emerald-500">{stats.completed}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-emerald-400" />
            </div>
          </div>
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-navy-400">Rejected</p>
                <p className="text-2xl font-semibold text-red-500">{stats.rejected}</p>
              </div>
              <XCircle className="h-8 w-8 text-red-400" />
            </div>
          </div>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <AlertBanner variant="error" message={error} onDismiss={() => setError(null)} />
      )}

      {/* Tabs */}
      <div className="bg-navy-800 rounded-2xl border border-navy-700">
        <div className="border-b border-navy-700">
          <div className="flex">
            <button
              onClick={() => setActiveTab('pending')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors rounded-t-xl ${
                activeTab === 'pending'
                  ? 'border-emerald-500 text-white'
                  : 'border-transparent text-navy-400 hover:text-navy-300'
              }`}
            >
              Pending ({pendingWithdrawals.length})
            </button>
            <button
              onClick={() => setActiveTab('processing')}
              className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'processing'
                  ? 'border-emerald-500 text-white'
                  : 'border-transparent text-navy-400 hover:text-navy-300'
              }`}
            >
              Processing ({processingWithdrawals.length})
            </button>
            <button
              onClick={fetchData}
              className="ml-auto px-4 py-2 rounded-xl text-navy-400 hover:text-navy-300 hover:bg-navy-700"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Withdrawal List */}
        <div className="divide-y divide-navy-700">
          {(activeTab === 'pending' ? pendingWithdrawals : processingWithdrawals).length === 0 ? (
            <div className="p-8 text-center text-navy-400">
              No {activeTab} withdrawals
            </div>
          ) : (
            (activeTab === 'pending' ? pendingWithdrawals : processingWithdrawals).map((withdrawal) => (
              <div key={withdrawal.id} className="p-4 hover:bg-navy-700/30">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${ASSET_COLORS[withdrawal.assetType]}`}>
                        {withdrawal.assetType}
                      </span>
                      <span className="text-lg font-semibold">
                        {formatAmount(withdrawal.amount, withdrawal.assetType)}
                      </span>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_COLORS[withdrawal.status]}`}>
                        {withdrawal.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm text-navy-400">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4" />
                        <span>{withdrawal.entityName || 'Unknown Entity'}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        <span>{withdrawal.userEmail || '-'}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        <span>Requested: {formatDate(withdrawal.requestedAt)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <DollarSign className="h-4 w-4" />
                        <span>Ref: {withdrawal.internalReference || '-'}</span>
                      </div>
                    </div>

                    {/* Destination info */}
                    <div className="mt-3 p-3 bg-navy-700/50 rounded-xl text-sm">
                      {withdrawal.assetType === 'EUR' ? (
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-navy-400">Bank:</span>{' '}
                            {withdrawal.destinationBank || '-'}
                          </div>
                          <div>
                            <span className="text-navy-400">IBAN:</span>{' '}
                            <span className="font-mono">{withdrawal.destinationIban || '-'}</span>
                          </div>
                          <div>
                            <span className="text-navy-400">SWIFT:</span>{' '}
                            {withdrawal.destinationSwift || '-'}
                          </div>
                          <div>
                            <span className="text-navy-400">Holder:</span>{' '}
                            {withdrawal.destinationAccountHolder || '-'}
                          </div>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="text-navy-400">Registry:</span>{' '}
                            {withdrawal.destinationRegistry || '-'}
                          </div>
                          <div>
                            <span className="text-navy-400">Account ID:</span>{' '}
                            <span className="font-mono">{withdrawal.destinationAccountId || '-'}</span>
                          </div>
                        </div>
                      )}
                      {withdrawal.clientNotes && (
                        <div className="mt-2 pt-2 border-t border-navy-700">
                          <span className="text-navy-400">Client Notes:</span>{' '}
                          {withdrawal.clientNotes}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex flex-col gap-2 ml-4">
                    {activeTab === 'pending' && (
                      <>
                        <button
                          onClick={() => openApproveModal(withdrawal)}
                          className="px-4 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 text-sm font-medium"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => openRejectModal(withdrawal)}
                          className="px-4 py-2 bg-red-500/20 text-red-400 rounded-xl hover:bg-red-500/30 text-sm font-medium"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {activeTab === 'processing' && (
                      <>
                        <button
                          onClick={() => openCompleteModal(withdrawal)}
                          className="px-4 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 text-sm font-medium"
                        >
                          Complete
                        </button>
                        <button
                          onClick={() => openRejectModal(withdrawal)}
                          className="px-4 py-2 bg-red-500/20 text-red-400 rounded-xl hover:bg-red-500/30 text-sm font-medium"
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Approve Modal */}
      {showApproveModal && selectedWithdrawal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-6 w-full max-w-md shadow-xl">
            <h3 className="text-lg font-semibold text-white mb-4">Approve Withdrawal</h3>
            <div className="mb-4 p-3 bg-blue-500/20 rounded-xl border border-blue-500/30">
              <p className="text-sm text-navy-200">
                <strong>Amount:</strong> {formatAmount(selectedWithdrawal.amount, selectedWithdrawal.assetType)}
              </p>
              <p className="text-sm text-navy-200">
                <strong>Entity:</strong> {selectedWithdrawal.entityName}
              </p>
              <p className="text-sm text-navy-200">
                <strong>Reference:</strong> {selectedWithdrawal.internalReference}
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-navy-300 mb-1">
                Admin Notes (optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                className="w-full border border-navy-600 rounded-xl bg-navy-900 text-white p-3 text-sm placeholder-navy-500 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                rows={3}
                placeholder="Add any notes..."
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={closeModals}
                className="flex-1 px-4 py-2 border border-navy-600 rounded-xl text-navy-300 hover:bg-navy-700 font-medium"
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                className="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 flex items-center justify-center font-medium"
                disabled={actionLoading}
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Approve'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Complete Modal */}
      {showCompleteModal && selectedWithdrawal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-6 w-full max-w-md shadow-xl">
            <h3 className="text-lg font-semibold text-white mb-4">Complete Withdrawal</h3>
            <div className="mb-4 p-3 bg-emerald-500/20 rounded-xl border border-emerald-500/30">
              <p className="text-sm text-navy-200">
                <strong>Amount:</strong> {formatAmount(selectedWithdrawal.amount, selectedWithdrawal.assetType)}
              </p>
              <p className="text-sm text-navy-200">
                <strong>Entity:</strong> {selectedWithdrawal.entityName}
              </p>
              <p className="text-sm text-navy-200">
                <strong>Reference:</strong> {selectedWithdrawal.internalReference}
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-navy-300 mb-1">
                Wire/Transfer Reference
              </label>
              <input
                type="text"
                value={wireReference}
                onChange={(e) => setWireReference(e.target.value)}
                className="w-full border border-navy-600 rounded-xl bg-navy-900 text-white p-3 text-sm placeholder-navy-500 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="Enter wire reference..."
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-navy-300 mb-1">
                Admin Notes (optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                className="w-full border border-navy-600 rounded-xl bg-navy-900 text-white p-3 text-sm placeholder-navy-500 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                rows={3}
                placeholder="Add any notes..."
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={closeModals}
                className="flex-1 px-4 py-2 border border-navy-600 rounded-xl text-navy-300 hover:bg-navy-700 font-medium"
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                onClick={handleComplete}
                className="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 flex items-center justify-center font-medium"
                disabled={actionLoading}
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Complete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && selectedWithdrawal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl border border-navy-700 p-6 w-full max-w-md shadow-xl">
            <h3 className="text-lg font-semibold text-white mb-4">Reject Withdrawal</h3>
            <div className="mb-4 p-3 bg-red-500/20 rounded-xl border border-red-500/30">
              <p className="text-sm text-navy-200">
                <strong>Amount:</strong> {formatAmount(selectedWithdrawal.amount, selectedWithdrawal.assetType)}
              </p>
              <p className="text-sm text-navy-200">
                <strong>Entity:</strong> {selectedWithdrawal.entityName}
              </p>
              <p className="text-sm text-red-400 font-medium mt-2">
                Funds will be refunded to the entity&apos;s balance.
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-navy-300 mb-1">
                Rejection Reason *
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                className="w-full border border-navy-600 rounded-xl bg-navy-900 text-white p-3 text-sm placeholder-navy-500 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                rows={3}
                placeholder="Enter reason for rejection..."
                required
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-navy-300 mb-1">
                Admin Notes (optional)
              </label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                className="w-full border border-navy-600 rounded-xl bg-navy-900 text-white p-3 text-sm placeholder-navy-500 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                rows={2}
                placeholder="Additional notes..."
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={closeModals}
                className="flex-1 px-4 py-2 border border-navy-600 rounded-xl text-navy-300 hover:bg-navy-700 font-medium"
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-xl hover:bg-red-700 flex items-center justify-center font-medium"
                disabled={actionLoading || !rejectionReason.trim()}
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Reject & Refund'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
