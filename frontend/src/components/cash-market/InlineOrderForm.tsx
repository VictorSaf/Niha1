/* eslint-disable react-refresh/only-export-components -- exports helper functions alongside component */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  Loader2,
  AlertCircle,
  ShoppingCart,
} from 'lucide-react';
import { cashMarketApi } from '../../services/api';
import type { CertificateType, OrderBookLevel } from '../../types';
import { TradeConfirmationModal } from './TradeConfirmationModal';

// ─────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────

interface OrderPreview {
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
  totalQuantity?: number;
  totalCostGross?: number;
  weightedAvgPrice?: number;
  bestPrice: number | null;
  worstPrice: number | null;
  platformFeeRate?: number;
  platformFeeAmount?: number;
  totalCostNet?: number;
  netPricePerUnit?: number;
  availableBalance?: number;
  remainingBalance?: number;
  canExecute: boolean;
  executionMessage: string;
  partialFill: boolean;
  willBePlacedInBook?: boolean;
}

interface InlineOrderFormProps {
  certificateType: CertificateType;
  availableBalance: number;
  bestBid: number | null;
  bestAsk: number | null;
  spread: number | null;
  asks: OrderBookLevel[];
  onOrderSubmit: (order: { orderType: 'MARKET'; amountEur: number }) => Promise<void>;
  onRefresh: () => Promise<void>;
  onExpandChange?: (expanded: boolean) => void;
}

// ─────────────────────────────────────────────────
// Local orderbook-based calculation
// ─────────────────────────────────────────────────

export interface MarketCalc {
  totalQty: number;
  totalCost: number;
  avgPrice: number;
  levelsUsed: number;
}

export function calcMarketBuy(asks: OrderBookLevel[], budgetEur: number): MarketCalc | null {
  if (!asks.length || budgetEur <= 0) return null;

  let remaining = budgetEur;
  let totalQty = 0;
  let totalCost = 0;
  let levelsUsed = 0;

  for (const level of asks) {
    if (remaining <= 0) break;
    const costForLevel = level.price * level.quantity;

    if (remaining >= costForLevel) {
      totalQty += level.quantity;
      totalCost += costForLevel;
      remaining -= costForLevel;
      levelsUsed++;
    } else {
      const units = Math.floor(remaining / level.price);
      if (units > 0) {
        totalQty += units;
        totalCost += units * level.price;
        remaining -= units * level.price;
        levelsUsed++;
      }
    }
  }

  if (totalQty <= 0) return null;
  return { totalQty, totalCost, avgPrice: totalCost / totalQty, levelsUsed };
}

// ─────────────────────────────────────────────────
// Component — always-open vertical layout
// ─────────────────────────────────────────────────

export function InlineOrderForm({
  certificateType,
  availableBalance,
  bestAsk,
  asks,
  onOrderSubmit,
  onRefresh,
  onExpandChange,
}: InlineOrderFormProps) {
  const [preview, setPreview] = useState<OrderPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  // Notify parent that form is always expanded
  useEffect(() => { onExpandChange?.(true); }, [onExpandChange]);

  const calc = useMemo(
    () => calcMarketBuy(asks, availableBalance),
    [asks, availableBalance],
  );

  const fetchPreview = useCallback(async () => {
    if (availableBalance <= 0) {
      setPreview(null);
      setPreviewError(null);
      return;
    }

    setIsLoadingPreview(true);
    setPreviewError(null);

    try {
      const previewData = await cashMarketApi.previewOrder({
        certificate_type: certificateType,
        side: 'BUY',
        amount_eur: availableBalance,
        order_type: 'MARKET',
      });
      setPreview(previewData);
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      setPreviewError(err.response?.data?.detail || 'Failed to preview order.');
      setPreview(null);
    } finally {
      setIsLoadingPreview(false);
    }
  }, [certificateType, availableBalance]);

  useEffect(() => {
    fetchPreview();
  }, [fetchPreview]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!preview?.canExecute || availableBalance <= 0) return;
    setShowConfirmation(true);
  };

  const handleConfirmExecute = async () => {
    setIsSubmitting(true);
    try {
      await onOrderSubmit({ orderType: 'MARKET', amountEur: availableBalance });
      setShowConfirmation(false);
      setPreview(null);
      setSubmitSuccess(true);
      setTimeout(() => setSubmitSuccess(false), 3000);
      await onRefresh();
    } catch (error) {
      console.error('Order submission error:', error);
      throw error;
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit =
    !isSubmitting &&
    !isLoadingPreview &&
    preview?.canExecute &&
    availableBalance > 0;

  const formatNumber = (num: number | null | undefined, decimals = 2) => {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  return (
    <div className="rounded-lg border border-navy-700/50 overflow-hidden flex flex-col flex-1 min-h-0 bg-navy-800/30 widget-accent-emerald">
      {/* Header */}
      <div className="px-3 py-1 border-b border-navy-700/50 flex items-center gap-1.5 shrink-0">
        <ShoppingCart className="w-3 h-3 text-emerald-400" />
        <span className="text-xs font-semibold text-navy-300 uppercase tracking-wider">Buy {certificateType}</span>
      </div>

      {/* Form content — vertical stack */}
      <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-y-auto px-3 py-2 gap-1.5">
        {/* Ask price */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-navy-500 uppercase">Market Ask</span>
          <span className="text-sm font-mono font-bold text-red-400 tabular-nums">
            €{formatNumber(bestAsk)}
          </span>
        </div>

        {/* Balance */}
        <div>
          <label className="text-xs text-navy-500 uppercase block">Amount (EUR)</label>
          <div className="h-7 px-2.5 rounded-lg border border-navy-700 bg-navy-900/50 text-xs font-mono text-white flex items-center justify-between">
            <span className="tabular-nums">€{formatNumber(availableBalance)}</span>
            <span className="text-[10px] text-navy-600">full balance</span>
          </div>
        </div>

        {/* Est. Quantity */}
        <div>
          <label className="text-xs text-navy-500 uppercase block">Est. Quantity</label>
          <div className="h-7 px-2.5 rounded-lg border border-navy-700 bg-navy-900/50 text-xs font-mono text-white flex items-center justify-between">
            {calc ? (
              <span className="tabular-nums">{formatNumber(calc.totalQty, 0)}</span>
            ) : (
              <span className="text-navy-500">—</span>
            )}
            <span className="text-[10px] text-navy-600">{certificateType}</span>
          </div>
        </div>

        {/* Preview details */}
        {calc && (
          <div className="rounded-lg bg-navy-900/50 border border-navy-700/50 px-2.5 py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs">
              <span className="text-navy-500">Avg Price</span>
              <span className="font-mono text-amber-400 tabular-nums">€{formatNumber(calc.avgPrice)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-navy-500">Total Cost</span>
              <span className="font-mono text-white tabular-nums">€{formatNumber(calc.totalCost)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-navy-500">Levels</span>
              <span className="font-mono text-navy-300 tabular-nums">{calc.levelsUsed}</span>
            </div>
            {preview?.platformFeeAmount != null && preview.platformFeeAmount > 0 && (
              <div className="flex justify-between text-xs">
                <span className="text-navy-500">Fee</span>
                <span className="font-mono text-navy-300 tabular-nums">
                  €{formatNumber(preview.platformFeeAmount)}
                  {preview.platformFeeRate != null && (
                    <span className="text-navy-600 ml-0.5">({(preview.platformFeeRate * 100).toFixed(1)}%)</span>
                  )}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Loading / Error states */}
        {isLoadingPreview && !calc && (
          <div className="flex items-center justify-center py-2 rounded-lg bg-navy-900/50 border border-navy-700/50">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-500 mr-1.5" />
            <span className="text-xs text-navy-400">Calculating...</span>
          </div>
        )}

        {previewError && (
          <div className="flex items-start gap-1.5 p-2 rounded-lg bg-red-900/15 border border-red-800/30">
            <AlertCircle className="w-3 h-3 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-300">{previewError}</p>
          </div>
        )}

        {/* Status — only show when NOT executable (error/warning) */}
        {!preview?.canExecute && preview && (
          <div className="flex items-start gap-1.5 px-2 py-1 rounded bg-red-900/20 border border-red-800/30">
            <AlertCircle className="w-3 h-3 text-red-400 shrink-0 mt-0.5" />
            <span className="text-xs text-red-300">{preview.executionMessage}</span>
          </div>
        )}

        {/* Submit — mt-auto pushes to bottom when space allows without clipping on short screens */}
        <motion.button
          whileHover={canSubmit ? { scale: 1.01 } : {}}
          whileTap={canSubmit ? { scale: 0.99 } : {}}
          type="submit"
          disabled={!canSubmit}
          className={`w-full py-2 rounded-lg font-semibold text-xs text-white transition-all duration-200 flex items-center justify-center gap-1.5 shrink-0 mt-auto ${
            canSubmit
              ? 'bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 shadow-lg shadow-emerald-500/20'
              : 'bg-navy-700 text-navy-500 cursor-not-allowed'
          }`}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Executing...</span>
            </>
          ) : (
            <>
              <ShoppingCart className="w-3.5 h-3.5" />
              <span>Buy {certificateType} at Market</span>
            </>
          )}
        </motion.button>

        {/* Success feedback */}
        <AnimatePresence>
          {submitSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="flex items-center justify-center gap-1 py-1.5 rounded-lg bg-emerald-900/20 border border-emerald-800/30 shrink-0"
            >
              <TrendingUp className="w-3 h-3 text-emerald-400" />
              <span className="text-xs font-medium text-emerald-400">Order placed</span>
            </motion.div>
          )}
        </AnimatePresence>
      </form>

      {/* Trade Confirmation Modal */}
      <TradeConfirmationModal
        isOpen={showConfirmation}
        onClose={() => setShowConfirmation(false)}
        onConfirm={handleConfirmExecute}
        trade={
          calc && preview
            ? {
                certificateType,
                side: 'BUY',
                amountEur: availableBalance,
                estimatedQuantity: calc.totalQty,
                avgPrice: calc.avgPrice,
                levelsUsed: calc.levelsUsed,
                bestPrice: preview.bestPrice,
                worstPrice: preview.worstPrice,
                platformFeeRate: preview.platformFeeRate ?? null,
                platformFeeAmount: preview.platformFeeAmount ?? null,
                totalCostGross: preview.totalCostGross ?? null,
                totalCostNet: preview.totalCostNet ?? null,
                remainingBalance: preview.remainingBalance ?? null,
                partialFill: preview.partialFill,
              }
            : null
        }
      />
    </div>
  );
}
