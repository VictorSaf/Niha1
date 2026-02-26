import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, DollarSign, Leaf, Wind, Plus, Minus } from 'lucide-react';
import { Button, AlertBanner, NumberInput } from '../common';
import { backofficeApi } from '../../services/api';
import { cn } from '../../utils';
import type { AssetType } from '../../types';

interface AddAssetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  entityId: string;
  entityName: string;
}

interface EntityAssets {
  eurBalance: number;
  ceaBalance: number;
  euaBalance: number;
}

const formatEUR = (v: number) => `€${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const formatQty = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 0 });

const ASSET_CONFIG = {
  EUR: {
    label: 'EUR Cash',
    icon: DollarSign,
    bgClass: 'bg-emerald-900/30',
    textClass: 'text-emerald-400',
    borderClass: 'border-emerald-500',
    ringClass: 'focus:ring-emerald-500',
    format: formatEUR,
  },
  CEA: {
    label: 'CEA Certificates',
    icon: Leaf,
    bgClass: 'bg-amber-900/30',
    textClass: 'text-amber-400',
    borderClass: 'border-amber-500',
    ringClass: 'focus:ring-amber-500',
    format: formatQty,
  },
  EUA: {
    label: 'EUA Certificates',
    icon: Wind,
    bgClass: 'bg-blue-900/30',
    textClass: 'text-blue-400',
    borderClass: 'border-blue-500',
    ringClass: 'focus:ring-blue-500',
    format: formatQty,
  },
} as const;

export function AddAssetModal({
  isOpen,
  onClose,
  onSuccess,
  entityId,
  entityName,
}: AddAssetModalProps) {
  const [selectedAsset, setSelectedAsset] = useState<AssetType>('EUR');
  const [amount, setAmount] = useState('');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingAssets, setLoadingAssets] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assets, setAssets] = useState<EntityAssets | null>(null);

  // Fetch current assets when modal opens
  useEffect(() => {
    if (isOpen && entityId) {
      fetchAssets();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, entityId]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedAsset('EUR');
      setAmount('');
      setReference('');
      setNotes('');
      setError(null);
    }
  }, [isOpen]);

  const fetchAssets = async () => {
    setLoadingAssets(true);
    try {
      const data = await backofficeApi.getEntityAssets(entityId);
      setAssets({
        eurBalance: data.eurBalance,
        ceaBalance: data.ceaBalance,
        euaBalance: data.euaBalance,
      });
    } catch (err) {
      console.error('Failed to fetch assets:', err);
      // If new entity, show zeros
      setAssets({ eurBalance: 0, ceaBalance: 0, euaBalance: 0 });
    } finally {
      setLoadingAssets(false);
    }
  };

  const handleSubmit = async (operation: 'deposit' | 'withdraw') => {
    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setError('Please enter a valid amount greater than 0');
      return;
    }
    if (operation === 'withdraw') {
      const current = getCurrentBalance();
      if (amountNum > current) {
        setError('Insufficient balance');
        return;
      }
    }

    setLoading(true);
    setError(null);

    try {
      // CEA/EUA: whole certificates only — send integer
      const amountToSend =
        selectedAsset === 'CEA' || selectedAsset === 'EUA'
          ? Math.round(amountNum)
          : amountNum;
      await backofficeApi.addAsset(entityId, {
        asset_type: selectedAsset,
        amount: amountToSend,
        operation,
        reference: reference || undefined,
        notes: notes || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const errResp = err as { response?: { data?: { detail?: string } } };
      const detail = errResp.response?.data?.detail;
      setError(
        detail && String(detail).toLowerCase().includes('insufficient')
          ? 'Insufficient balance'
          : detail || (operation === 'withdraw' ? 'Failed to withdraw asset' : 'Failed to add asset')
      );
    } finally {
      setLoading(false);
    }
  };

  const getCurrentBalance = (): number => {
    if (!assets) return 0;
    switch (selectedAsset) {
      case 'EUR': return assets.eurBalance;
      case 'CEA': return assets.ceaBalance;
      case 'EUA': return assets.euaBalance;
    }
  };

  const setMaxAmount = () => {
    const current = getCurrentBalance();
    setAmount(
      selectedAsset === 'EUR'
        ? current.toFixed(2)
        : String(Math.floor(current))
    );
  };

  const getNewBalance = (operation: 'deposit' | 'withdraw'): number => {
    const current = getCurrentBalance();
    const amountNum = parseFloat(amount) || 0;
    return operation === 'withdraw' ? current - amountNum : current + amountNum;
  };

  const amountNum = parseFloat(amount) || 0;
  const isValidAmount = amountNum > 0;
  const canWithdraw = isValidAmount && amountNum <= getCurrentBalance();

  const config = ASSET_CONFIG[selectedAsset];

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', duration: 0.3 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              className="bg-navy-800 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-navy-700">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Plus className="w-5 h-5 text-emerald-500" />
                    Add Asset
                  </h2>
                  <p className="text-sm text-navy-400 mt-1">
                    {entityName}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg text-navy-400 hover:text-navy-300 hover:bg-navy-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Asset Type Tabs */}
              <div className="p-6 pb-0">
                <div className="flex gap-2 p-1 bg-navy-800 rounded-xl">
                  {(['EUR', 'CEA', 'EUA'] as const).map((asset) => {
                    const cfg = ASSET_CONFIG[asset];
                    const Icon = cfg.icon;
                    const isSelected = selectedAsset === asset;
                    return (
                      <button
                        key={asset}
                        onClick={() => setSelectedAsset(asset)}
                        className={cn(
                          'flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-all',
                          isSelected
                            ? `bg-navy-700 shadow-sm ${cfg.textClass}`
                            : 'text-navy-500 hover:text-navy-300'
                        )}
                      >
                        <Icon className="w-4 h-4" />
                        {asset}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Content */}
              <div className="p-6 space-y-4">
                {/* Current Balance */}
                <div className={cn('p-4 rounded-xl', config.bgClass)}>
                  <div className="text-xs uppercase tracking-wider text-navy-400 mb-1">
                    Current {config.label} Balance
                  </div>
                  <div className={cn('text-2xl font-bold font-mono', config.textClass)}>
                    {loadingAssets ? '...' : config.format(getCurrentBalance())}
                  </div>
                </div>

                {/* Amount Input */}
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-2">
                    Amount *
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <NumberInput
                        value={amount}
                        onChange={(v) => setAmount(v)}
                        placeholder={selectedAsset === 'EUR' ? '0.00' : '0'}
                        decimals={selectedAsset === 'EUR' ? 2 : 0}
                        className={cn(
                          isValidAmount
                            ? `${config.borderClass} ${config.ringClass}`
                            : 'border-navy-700 focus:ring-emerald-500'
                        )}
                        autoFocus
                      />
                    </div>
                    <button
                      type="button"
                      onClick={setMaxAmount}
                      className="px-3 py-2 text-sm border border-navy-600 text-navy-300 rounded-xl hover:bg-navy-700 font-medium"
                    >
                      Max
                    </button>
                  </div>
                </div>

                {/* Reference (optional) */}
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-2">
                    Reference <span className="text-navy-400">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    placeholder="Wire reference, certificate ID..."
                    maxLength={100}
                    className="w-full px-4 py-2.5 rounded-xl border border-navy-700 bg-navy-800 text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                {/* Notes (optional) */}
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-2">
                    Admin Notes <span className="text-navy-400">(optional)</span>
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Internal notes..."
                    rows={2}
                    className="w-full px-4 py-2.5 rounded-xl border border-navy-700 bg-navy-800 text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                  />
                </div>

                {/* New Balance Preview */}
                {isValidAmount && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 bg-navy-800/50 rounded-xl border border-navy-700 space-y-2"
                  >
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-navy-400">
                        After deposit
                      </span>
                      <span className={cn('text-lg font-bold font-mono', config.textClass)}>
                        {config.format(getNewBalance('deposit'))}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-navy-400">
                        After withdraw
                      </span>
                      <span className={cn(
                        'text-lg font-bold font-mono',
                        getNewBalance('withdraw') < 0 ? 'text-red-400' : config.textClass
                      )}>
                        {config.format(getNewBalance('withdraw'))}
                      </span>
                    </div>
                    {getNewBalance('withdraw') < 0 && (
                      <p className="text-sm text-red-400">
                        Insufficient balance to withdraw this amount
                      </p>
                    )}
                  </motion.div>
                )}

                {/* Error Message */}
                {error && (
                  <AlertBanner variant="error" message={error} />
                )}
              </div>

              {/* Footer */}
              <div className="flex gap-3 p-6 pt-0">
                <Button
                  variant="outline"
                  onClick={onClose}
                  disabled={loading}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={() => handleSubmit('deposit')}
                  loading={loading}
                  disabled={!isValidAmount}
                  className="flex-1"
                >
                  <Plus className="w-4 h-4" />
                  Deposit
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => handleSubmit('withdraw')}
                  loading={loading}
                  disabled={!canWithdraw}
                  className="flex-1 text-red-400 hover:bg-red-500/10 border-red-800"
                >
                  <Minus className="w-4 h-4" />
                  Withdraw
                </Button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
