import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Play,
  Pause,
  Clock,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Settings,
  Zap,
} from 'lucide-react';
import { Button, LoadingState } from '../common';
import {
  getAutoTradeRules,
  updateAutoTradeRule,
  type AutoTradeRule,
} from '../../services/api';
import { getApiErrorMessage } from '../../utils/errors';
import type { MarketMaker } from '../../types';

interface MarketMakerAutoTradeTabProps {
  marketMaker: MarketMaker;
}


export function MarketMakerAutoTradeTab({ marketMaker }: MarketMakerAutoTradeTabProps) {
  const [rules, setRules] = useState<AutoTradeRule[]>([]);
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load rules from API
  const loadRules = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getAutoTradeRules(marketMaker.id);
      setRules(data);
    } catch (err: unknown) {
      console.error('Failed to load auto trade rules:', err);
      setError(getApiErrorMessage(err));
      setRules([]);
    } finally {
      setIsLoading(false);
    }
  }, [marketMaker.id]);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const selectedRule = rules.find(r => r.id === selectedRuleId);

  const handleToggleRule = async (ruleId: string) => {
    const rule = rules.find(r => r.id === ruleId);
    if (!rule) return;
    try {
      await updateAutoTradeRule(marketMaker.id, ruleId, { enabled: !rule.enabled });
      setRules(prev => prev.map(r => r.id === ruleId ? { ...r, enabled: !rule.enabled } : r));
    } catch (err: unknown) {
      console.error('Failed to toggle rule:', err);
      setError(getApiErrorMessage(err));
    }
  };

  const activeRulesCount = rules.filter(r => r.enabled).length;

  // Helper to format interval display
  const formatInterval = (rule: AutoTradeRule) => {
    if (rule.intervalMode === 'random') {
      if (rule.intervalMinSeconds && rule.intervalMaxSeconds) {
        return `${rule.intervalMinSeconds}-${rule.intervalMaxSeconds}s`;
      }
      return `${rule.intervalMinMinutes || 1}-${rule.intervalMaxMinutes || 5}m`;
    }
    if (rule.intervalSeconds) return `${rule.intervalSeconds}s`;
    return `${rule.intervalMinutes || 1}m`;
  };


  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingState variant="spinner" size="lg" />
      </div>
    );
  }

  if (error && rules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <p className="text-red-400 mb-4">{error}</p>
        <Button onClick={loadRules}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with stats */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/10">
            <Zap className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <h3 className="font-semibold text-white">Auto Trade Rules</h3>
            <p className="text-sm text-navy-400">
              {activeRulesCount} active rule{activeRulesCount !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Rules List */}
        <div className="space-y-2">
          {rules.length === 0 ? (
            <div className="p-6 rounded-xl border-2 border-dashed border-navy-600 text-center">
              <p className="text-navy-400 text-sm">
                No rules configured.
              </p>
            </div>
          ) : (
            rules.map(rule => (
              <motion.button
                key={rule.id}
                onClick={() => setSelectedRuleId(rule.id)}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`w-full p-3 rounded-xl border-2 text-left transition-all ${
                  selectedRuleId === rule.id
                    ? 'border-emerald-500 bg-emerald-900/20 shadow-lg shadow-emerald-500/10'
                    : rule.enabled
                      ? 'border-emerald-400/40 bg-emerald-900/10 hover:border-emerald-400'
                      : 'border-navy-700 hover:border-navy-600 opacity-70'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white text-sm truncate max-w-[120px]">
                      {rule.name}
                    </span>
                    {rule.enabled && (
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-500 text-white text-[10px] font-bold">
                        <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                        LIVE
                      </span>
                    )}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleRule(rule.id);
                    }}
                    className={`p-1.5 rounded-lg transition-colors ${
                      rule.enabled
                        ? 'text-white bg-emerald-500 hover:bg-emerald-600'
                        : 'text-navy-400 bg-navy-800 hover:bg-navy-200'
                    }`}
                  >
                    {rule.enabled ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                  </button>
                </div>
                <div className="flex items-center gap-2 text-xs text-navy-400">
                  {rule.side === 'BUY' ? (
                    <TrendingUp className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-red-500" />
                  )}
                  <span className="font-medium">{rule.side}</span>
                  <span>•</span>
                  <Clock className="w-3 h-3" />
                  <span>{formatInterval(rule)}</span>
                </div>
                {rule.executionCount > 0 && (
                  <div className="mt-2 pt-2 border-t border-navy-700">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-navy-400">
                        {rule.executionCount} orders
                      </span>
                      {rule.enabled && rule.nextExecutionAt && (
                        <span className="text-emerald-400 font-medium">
                          Next: {Math.max(0, Math.round((new Date(rule.nextExecutionAt).getTime() - Date.now()) / 1000))}s
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </motion.button>
            ))
          )}
        </div>

        {/* Rule Status (read-only) */}
        <div className="col-span-2">
          {selectedRule ? (
            <div className="rounded-lg border border-navy-700/50 bg-navy-800/30 p-4 space-y-3">
              <p className="text-[11px] text-navy-500 font-medium uppercase tracking-wide">Rule Status</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[10px] text-navy-600 mb-0.5">Name</p>
                  <p className="text-sm text-white/80 font-mono">{selectedRule.name}</p>
                </div>
                <div>
                  <p className="text-[10px] text-navy-600 mb-0.5">Side</p>
                  <p className="text-sm text-white/80 font-mono">{selectedRule.side}</p>
                </div>
                <div>
                  <p className="text-[10px] text-navy-600 mb-0.5">Status</p>
                  <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-medium ${selectedRule.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-navy-700/50 text-navy-500'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${selectedRule.enabled ? 'bg-emerald-400' : 'bg-navy-500'}`} />
                    {selectedRule.enabled ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div>
                  <p className="text-[10px] text-navy-600 mb-0.5">Orders Placed</p>
                  <p className="text-sm text-white/80 font-mono">{selectedRule.executionCount}</p>
                </div>
                {selectedRule.lastExecutedAt && (
                  <div className="col-span-2">
                    <p className="text-[10px] text-navy-600 mb-0.5">Last Execution</p>
                    <p className="text-[11px] text-white/60 font-mono">
                      {new Date(selectedRule.lastExecutedAt).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>
              <p className="text-[10px] text-navy-600 pt-2 border-t border-navy-700/30">
                Configure auto-trade parameters in the <span className="text-amber-500/70">Auto Trade</span> page.
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full py-12 text-center rounded-xl bg-navy-800/30 border-2 border-dashed border-navy-600">
              <Settings className="w-12 h-12 text-navy-600 mb-4" />
              <p className="text-navy-400 mb-2">
                Select a rule to view its status
              </p>
              <p className="text-sm text-navy-500">
                or create a new one with the button above
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
