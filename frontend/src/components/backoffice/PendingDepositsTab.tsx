/**
 * Pending Deposits Tab Component
 * 
 * Displays and manages pending deposit requests with confirmation/rejection functionality.
 * Includes a modal for confirming deposits with actual received amounts.
 * 
 * @component
 * @example
 * ```tsx
 * <PendingDepositsTab
 *   pendingDeposits={deposits}
 *   loading={false}
 *   onConfirm={handleConfirm}
 *   onReject={handleReject}
 *   actionLoading={null}
 * />
 * ```
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Banknote, Clock, CheckCircle, XCircle, DollarSign, X, AlertCircle, Shield, Timer } from 'lucide-react';
import { Button, Card, ClientStatusBadge, NumberInput, ConfirmationModal } from '../common';
import { formatCurrency, formatRelativeTime, cn } from '../../utils';
import type { PendingDeposit } from '../../types/backoffice';
import type { Deposit } from '../../types';

interface PendingDepositsTabProps {
  pendingDeposits: PendingDeposit[];
  onHoldDeposits?: Deposit[];
  loading: boolean;
  onConfirm: (depositId: string, amount: number, currency: string, notes?: string) => Promise<void>;
  onReject: (depositId: string) => Promise<void>;
  onClear?: (depositId: string, forceClear?: boolean, notes?: string) => Promise<void>;
  actionLoading: string | null;
}

export function PendingDepositsTab({
  pendingDeposits,
  onHoldDeposits = [],
  loading,
  onConfirm,
  onReject,
  onClear,
  actionLoading,
}: PendingDepositsTabProps) {
  const [confirmDepositModal, setConfirmDepositModal] = useState<PendingDeposit | null>(null);
  const [clearDepositModal, setClearDepositModal] = useState<Deposit | null>(null);
  const [confirmAmount, setConfirmAmount] = useState('');
  const [confirmCurrency, setConfirmCurrency] = useState('EUR');
  const [confirmNotes, setConfirmNotes] = useState('');
  const [clearNotes, setClearNotes] = useState('');
  const [forceClear, setForceClear] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchRejectConfirm, setBatchRejectConfirm] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);

  const allDepositIds = pendingDeposits.map(d => d.id);
  const allSelected = allDepositIds.length > 0 && allDepositIds.every(id => selectedIds.has(id));
  const someSelected = selectedIds.size > 0;

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(allDepositIds));
  };

  const handleBatchReject = async () => {
    setBatchLoading(true);
    const ids = Array.from(selectedIds);
    for (const id of ids) {
      await onReject(id).catch(() => {});
    }
    setSelectedIds(new Set());
    setBatchLoading(false);
    setBatchRejectConfirm(false);
  };

  const getHoldTimeRemaining = (expiresAt: string | undefined): string => {
    if (!expiresAt) return 'Unknown';
    const expires = new Date(expiresAt);
    const now = new Date();
    const diff = expires.getTime() - now.getTime();

    if (diff <= 0) return 'Expired';

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h remaining`;
    return `${hours}h remaining`;
  };

  const isHoldExpired = (expiresAt: string | undefined): boolean => {
    if (!expiresAt) return false;
    return new Date(expiresAt) <= new Date();
  };

  const handleClearDeposit = async () => {
    if (!clearDepositModal || !onClear) return;
    try {
      await onClear(clearDepositModal.id, forceClear, clearNotes || undefined);
      setClearDepositModal(null);
      setClearNotes('');
      setForceClear(false);
    } catch (error) {
      setValidationError('Failed to clear deposit. Please try again.');
    }
  };

  const handleOpenConfirmDeposit = (deposit: PendingDeposit) => {
    setConfirmDepositModal(deposit);
    // Pre-fill with reported values if available
    setConfirmAmount(deposit.reportedAmount?.toString() || '');
    setConfirmCurrency(deposit.reportedCurrency || 'EUR');
    setConfirmNotes('');
    setValidationError(null);
  };

  const handleConfirmDeposit = async () => {
    if (!confirmDepositModal) return;

    const amount = parseFloat(confirmAmount);
    if (isNaN(amount) || amount <= 0) {
      setValidationError('Please enter a valid amount greater than 0');
      return;
    }

    setValidationError(null);
    try {
      await onConfirm(confirmDepositModal.id, amount, confirmCurrency, confirmNotes || undefined);
      setConfirmDepositModal(null);
      setConfirmAmount('');
      setConfirmNotes('');
    } catch (error) {
      // Error handling is done in parent component, but we can show a message here too
      setValidationError('Failed to confirm deposit. Please try again.');
    }
  };

  return (
    <>
      {/* AML On Hold Section */}
      {onHoldDeposits.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <Card>
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-500" />
              AML Hold - Awaiting Approval
              <span className="ml-2 px-2 py-0.5 bg-blue-900/30 text-blue-400 text-sm rounded-full">
                {onHoldDeposits.length}
              </span>
            </h2>

            <div className="space-y-4">
              {onHoldDeposits.map((deposit) => {
                const confirmedAtValue = deposit.confirmedAt;
                const holdExpiresAtValue = deposit.holdExpiresAt;

                const daysPassed = confirmedAtValue
                  ? Math.floor((Date.now() - new Date(confirmedAtValue).getTime()) / (1000 * 60 * 60 * 24))
                  : 0;
                const confirmedDate = confirmedAtValue
                  ? new Date(confirmedAtValue).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
                  : 'N/A';
                const expired = isHoldExpired(holdExpiresAtValue);

                return (
                  <div
                    key={deposit.id}
                    className={cn(
                      "p-4 rounded-xl border",
                      expired
                        ? "bg-emerald-900/20 border-emerald-800"
                        : "bg-blue-900/20 border-blue-800"
                    )}
                  >
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-white">
                            {deposit.entityName}
                          </h3>
                          <ClientStatusBadge role={deposit.userRole} />
                          {expired && (
                            <span className="px-2 py-0.5 bg-emerald-900/50 text-emerald-400 text-xs rounded-full">
                              Ready to Clear
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="text-navy-400">Amount:</span>
                            <span className="ml-2 text-navy-200 font-semibold">
                              {deposit.amount ? formatCurrency(Number(deposit.amount)) : 'N/A'} {deposit.currency || 'EUR'}
                            </span>
                          </div>
                          <div>
                            <span className="text-navy-400">User:</span>
                            <span className="ml-2 text-navy-200">{deposit.userEmail}</span>
                          </div>
                          <div>
                            <span className="text-navy-400">Confirmed:</span>
                            <span className="ml-2 text-navy-200">{confirmedDate}</span>
                          </div>
                          <div>
                            <span className="text-navy-400">Hold Status:</span>
                            <span className={cn(
                              "ml-2 font-medium",
                              expired ? "text-emerald-400" : "text-blue-400"
                            )}>
                              {getHoldTimeRemaining(holdExpiresAtValue)}
                            </span>
                          </div>
                        </div>
                        {/* Progress bar */}
                        <div className="flex items-center gap-2 mt-3">
                          <Timer className="w-4 h-4 text-navy-400" />
                          <div className="flex gap-0.5">
                            {Array.from({ length: Math.max(daysPassed, 1) }).map((_, i) => (
                              <div
                                key={i}
                                className={cn(
                                  "w-2 h-3 rounded-sm",
                                  expired ? "bg-emerald-500" : "bg-blue-500"
                                )}
                              />
                            ))}
                          </div>
                          <span className="text-xs text-navy-500">{daysPassed} days in hold</span>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            setClearDepositModal(deposit);
                            setForceClear(!expired);
                            setClearNotes('');
                          }}
                          className={expired ? "bg-emerald-500 hover:bg-emerald-600" : ""}
                        >
                          <CheckCircle className="w-4 h-4" />
                          {expired ? 'Clear Deposit' : 'Force Clear'}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Pending Deposits Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card>
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <Banknote className="w-5 h-5 text-navy-400" />
            Pending Deposits
          </h2>

          {/* Batch action toolbar */}
          {!loading && pendingDeposits.length > 0 && (
            <div className="flex items-center gap-3 mb-4 pb-4 border-b border-navy-700">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={el => {
                    if (el) el.indeterminate = someSelected && !allSelected;
                  }}
                  onChange={toggleSelectAll}
                  className="w-4 h-4 rounded border-navy-600 bg-navy-800 accent-emerald-500 cursor-pointer"
                  aria-label="Select all deposits"
                />
                <span className="text-xs text-navy-400">
                  {someSelected ? `${selectedIds.size} selected` : 'Select all'}
                </span>
              </label>
              {someSelected && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="ml-auto text-red-400 hover:bg-red-500/10 border-red-500/30"
                  onClick={() => setBatchRejectConfirm(true)}
                  disabled={batchLoading}
                >
                  <XCircle className="w-3.5 h-3.5 mr-1" />
                  Reject {selectedIds.size}
                </Button>
              )}
            </div>
          )}
          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse p-4 bg-navy-700/50 rounded-xl">
                  <div className="h-5 bg-navy-600 rounded w-1/3 mb-3" />
                  <div className="h-4 bg-navy-600 rounded w-1/2" />
                </div>
              ))}
            </div>
          ) : pendingDeposits.length > 0 ? (
            <div className="space-y-3">
              {pendingDeposits.map((deposit) => (
                <div
                  key={deposit.id}
                  className={`p-3 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                    selectedIds.has(deposit.id) ? 'bg-emerald-500/5 border border-emerald-500/20' : 'bg-navy-700/50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(deposit.id)}
                    onChange={() => toggleSelect(deposit.id)}
                    className="w-4 h-4 rounded border-navy-600 bg-navy-800 accent-emerald-500 cursor-pointer flex-shrink-0 self-start mt-1 sm:self-center sm:mt-0"
                    aria-label={`Select deposit from ${deposit.entityName}`}
                  />
                  <div className="flex-1 min-w-0">
                    {/* Primary: Entity + Amount highlighted */}
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-1">
                      <h3 className="font-semibold text-white">
                        {deposit.entityName}
                      </h3>
                      <ClientStatusBadge role={deposit.userRole} />
                      <span className="text-lg font-bold text-emerald-400 tabular-nums">
                        {deposit.reportedAmount ? formatCurrency(deposit.reportedAmount) : 'N/A'} {deposit.reportedCurrency || 'EUR'}
                      </span>
                    </div>
                    {/* Secondary: User, refs - compact */}
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5 text-xs text-navy-400">
                      <span className="truncate">{deposit.userEmail}</span>
                      <span className="font-mono text-navy-300">{deposit.bankReference}</span>
                      {deposit.wireReference && (
                        <span className="font-mono text-navy-400">Wire: {deposit.wireReference}</span>
                      )}
                      <span className="flex items-center gap-1 text-navy-500">
                        <Clock className="w-3 h-3 flex-shrink-0" />
                        {deposit.reportedAt ? formatRelativeTime(deposit.reportedAt) : formatRelativeTime(deposit.createdAt)}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onReject(deposit.id)}
                      loading={actionLoading === `reject-${deposit.id}`}
                      className="text-red-500 hover:bg-red-900/20"
                    >
                      <XCircle className="w-4 h-4" />
                      Reject
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenConfirmDeposit(deposit)}
                      loading={actionLoading === `confirm-${deposit.id}`}
                    >
                      <DollarSign className="w-4 h-4" />
                      Confirm
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <CheckCircle className="w-12 h-12 text-navy-400 mx-auto mb-4" />
              <p className="text-navy-400">No pending deposits</p>
              <p className="text-xs text-navy-400 mt-1">All deposits have been processed</p>
            </div>
          )}
        </Card>
      </motion.div>

      {/* Deposit Confirmation Modal */}
      {confirmDepositModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-navy-800 rounded-2xl border border-navy-700 shadow-xl w-full max-w-md"
          >
            <div className="flex items-center justify-between p-4 border-b border-navy-700">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-navy-400" />
                Confirm Deposit
              </h3>
              <button
                onClick={() => {
                  setConfirmDepositModal(null);
                  setConfirmAmount('');
                  setConfirmNotes('');
                }}
                className="text-navy-400 hover:text-navy-200"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" aria-hidden="true" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {/* Entity/User Info */}
              <div className="p-3 bg-navy-700/50 rounded-lg">
                <p className="text-sm text-navy-400">Entity</p>
                <p className="font-semibold text-white">{confirmDepositModal.entityName}</p>
                <p className="text-xs text-navy-400 mt-1">{confirmDepositModal.userEmail}</p>
              </div>

              {/* Reported Amount (for reference) */}
              <div className="p-3 bg-amber-900/20 border border-amber-800 rounded-lg">
                <p className="text-sm text-amber-400">Reported by User</p>
                <p className="font-semibold text-amber-200">
                  {confirmDepositModal.reportedAmount ? formatCurrency(confirmDepositModal.reportedAmount) : 'N/A'} {confirmDepositModal.reportedCurrency || ''}
                </p>
                {confirmDepositModal.wireReference && (
                  <p className="text-xs text-amber-500 mt-1 font-mono">
                    Wire Ref: {confirmDepositModal.wireReference}
                  </p>
                )}
              </div>

              {/* Validation Error Display */}
              {validationError && (
                <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-400 flex-1">{validationError}</p>
                  <button
                    onClick={() => setValidationError(null)}
                    className="text-red-400 hover:text-red-300"
                    aria-label="Dismiss error"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Actual Amount Input */}
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">
                  Actual Amount Received *
                </label>
                <NumberInput
                  value={confirmAmount}
                  onChange={(v) => {
                    setConfirmAmount(v);
                    setValidationError(null); // Clear error on change
                  }}
                  placeholder="Enter actual amount"
                  decimals={2}
                  aria-invalid={validationError ? 'true' : 'false'}
                  aria-describedby={validationError ? 'amount-error' : undefined}
                  className={cn(
                    validationError
                      ? "border-red-700 focus:ring-red-500"
                      : ""
                  )}
                  required
                />
                {validationError && (
                  <p id="amount-error" className="mt-1 text-xs text-red-400" role="alert">
                    {validationError}
                  </p>
                )}
              </div>

              {/* Currency Select */}
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">
                  Currency *
                </label>
                <select
                  value={confirmCurrency}
                  onChange={(e) => setConfirmCurrency(e.target.value)}
                  className="w-full form-select"
                >
                  <option value="EUR">EUR</option>
                  <option value="USD">USD</option>
                  <option value="CNY">CNY</option>
                  <option value="HKD">HKD</option>
                </select>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">
                  Notes (optional)
                </label>
                <textarea
                  value={confirmNotes}
                  onChange={(e) => setConfirmNotes(e.target.value)}
                  placeholder="Add any notes..."
                  rows={2}
                  className="w-full px-4 py-2 rounded-lg border border-navy-600 bg-navy-900 text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                />
              </div>

              {/* Info about what happens */}
              <div className="p-3 bg-navy-900/20 border border-navy-800 rounded-lg text-sm">
                <p className="text-navy-300">
                  Confirming this deposit will:
                </p>
                <ul className="text-navy-400 text-xs mt-1 list-disc list-inside">
                  <li>Update the entity balance</li>
                  <li>Upgrade the user to FUNDED status</li>
                  <li>Grant Cash Market access</li>
                </ul>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="ghost"
                  className="flex-1"
                  onClick={() => {
                    setConfirmDepositModal(null);
                    setConfirmAmount('');
                    setConfirmNotes('');
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  className="flex-1"
                  onClick={handleConfirmDeposit}
                  loading={actionLoading === `confirm-${confirmDepositModal.id}`}
                >
                  <CheckCircle className="w-4 h-4" />
                  Confirm Deposit
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Clear Deposit Modal */}
      {clearDepositModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-navy-800 rounded-2xl border border-navy-700 shadow-xl w-full max-w-md"
          >
            <div className="flex items-center justify-between p-4 border-b border-navy-700">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-emerald-500" />
                Clear AML Hold
              </h3>
              <button
                onClick={() => {
                  setClearDepositModal(null);
                  setClearNotes('');
                  setForceClear(false);
                }}
                className="text-navy-400 hover:text-navy-200"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" aria-hidden="true" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {/* Entity/User Info */}
              <div className="p-3 bg-navy-700/50 rounded-lg">
                <p className="text-sm text-navy-400">Entity</p>
                <p className="font-semibold text-white">{clearDepositModal.entityName}</p>
                <p className="text-xs text-navy-400 mt-1">{clearDepositModal.userEmail}</p>
              </div>

              {/* Amount */}
              <div className="p-3 bg-emerald-900/20 border border-emerald-800 rounded-lg">
                <p className="text-sm text-emerald-400">Amount to Clear</p>
                <p className="font-semibold text-emerald-200 text-xl">
                  {clearDepositModal.amount ? formatCurrency(Number(clearDepositModal.amount)) : 'N/A'} {clearDepositModal.currency || 'EUR'}
                </p>
              </div>

              {/* Force clear warning */}
              {forceClear && !isHoldExpired(clearDepositModal.holdExpiresAt) && (
                <div className="p-3 bg-amber-900/20 border border-amber-800 rounded-lg">
                  <p className="text-sm text-amber-400 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    Hold period has not expired yet
                  </p>
                  <p className="text-xs text-amber-500 mt-1">
                    {getHoldTimeRemaining(clearDepositModal.holdExpiresAt)}
                  </p>
                </div>
              )}

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">
                  Admin Notes (optional)
                </label>
                <textarea
                  value={clearNotes}
                  onChange={(e) => setClearNotes(e.target.value)}
                  placeholder="Add any notes..."
                  rows={2}
                  className="w-full px-4 py-2 rounded-lg border border-navy-600 bg-navy-900 text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                />
              </div>

              {/* Info about what happens */}
              <div className="p-3 bg-emerald-900/20 border border-emerald-800 rounded-lg text-sm">
                <p className="text-emerald-300">
                  Clearing this deposit will:
                </p>
                <ul className="text-emerald-400 text-xs mt-1 list-disc list-inside">
                  <li>Credit funds to entity balance</li>
                  <li>Upgrade users from AML to CEA status</li>
                  <li>Grant full trading access</li>
                </ul>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="ghost"
                  className="flex-1"
                  onClick={() => {
                    setClearDepositModal(null);
                    setClearNotes('');
                    setForceClear(false);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  className="flex-1 bg-emerald-500 hover:bg-emerald-600"
                  onClick={handleClearDeposit}
                  loading={actionLoading === `clear-${clearDepositModal.id}`}
                >
                  <CheckCircle className="w-4 h-4" />
                  Clear Deposit
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}

      {/* Batch Reject Confirmation */}
      <ConfirmationModal
        isOpen={batchRejectConfirm}
        onClose={() => setBatchRejectConfirm(false)}
        onConfirm={handleBatchReject}
        title={`Reject ${selectedIds.size} Deposit${selectedIds.size !== 1 ? 's' : ''}`}
        message={`This will reject ${selectedIds.size} selected deposit${selectedIds.size !== 1 ? 's' : ''}. This action cannot be undone.`}
        confirmText={`Reject ${selectedIds.size} Deposits`}
        cancelText="Cancel"
        variant="danger"
        details={[{ label: 'Selected', value: `${selectedIds.size} deposit${selectedIds.size !== 1 ? 's' : ''}` }]}
        loading={batchLoading}
      />
    </>
  );
}
