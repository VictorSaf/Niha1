import { useState, useEffect, useCallback, useRef, useId } from 'react';
import {
  TrendingUp,
  TrendingDown,
  ArrowLeftRight,
  RefreshCw,
  Zap,
  ChevronDown,
  ChevronUp,
  Settings,
  Save,
  SlidersHorizontal,
  Info,
  AlertTriangle,
} from 'lucide-react';
import { Card, Button, formatNumberWithSeparators, AlertBanner } from '../components/common';
import { BackofficeLayout } from '../components/layout';
import { adminApi } from '../services/api';
import { useAutoOrdersStore } from '../stores/useAutoOrdersStore';
import { getApiErrorMessage } from '../utils/errors';
import type { AutoTradeMarketSettings, AutoTradeMarketSettingsUpdate } from '../types';

// ============================================================================
// CONFIGURATION
// ============================================================================

const REFRESH_INTERVAL_MS = 10_000;

interface MarketConfig {
  title: string;
  subtitle: string;
  color: 'emerald' | 'red' | 'blue';
  icon: typeof TrendingUp;
  accentBorder: string;
}

const MARKET_CONFIG: Record<string, MarketConfig> = {
  CEA_BID: {
    title: 'CEA Buyer',
    subtitle: 'Buy Orders · BID',
    color: 'emerald',
    icon: TrendingUp,
    accentBorder: 'border-l-emerald-500',
  },
  CEA_ASK: {
    title: 'CEA Seller',
    subtitle: 'Sell Orders · ASK',
    color: 'red',
    icon: TrendingDown,
    accentBorder: 'border-l-red-500',
  },
  EUA_SWAP: {
    title: 'Swap EUA',
    subtitle: 'CEA → EUA Swap',
    color: 'blue',
    icon: ArrowLeftRight,
    accentBorder: 'border-l-blue-500',
  },
};

const COLOR_MAP = {
  emerald: { text: 'text-emerald-400', bg: 'bg-emerald-500/20', bar: 'bg-emerald-500', toggle: 'bg-emerald-500' },
  red: { text: 'text-red-400', bg: 'bg-red-500/20', bar: 'bg-red-500', toggle: 'bg-red-500' },
  blue: { text: 'text-blue-400', bg: 'bg-blue-500/20', bar: 'bg-blue-500', toggle: 'bg-blue-500' },
};

// ============================================================================
// RECOMMENDED VALUES (research-based)
// ============================================================================

const RECOMMENDED: Record<string, Record<string, string>> = {
  CEA_CASH: {
    targetLiquidity: '500,000 EUR',
    avgSpread: '0.20 EUR',
    tickSize: '0.10 EUR',
    intervalSeconds: '60 sec',
    minOrderVolumeEur: '5,000 EUR',
    maxOrderVolumeEur: '250,000 EUR',
    volumeVariety: '7 / 10',
    priceDeviationPct: '3%',
    maxOrdersPerPriceLevel: '4',
    avgOrderCount: '10',
    maxLiquidityThreshold: '750,000 EUR',
    internalTradeInterval: '120 sec',
    internalTradeVolumeMin: '10,000 EUR',
    internalTradeVolumeMax: '100,000 EUR',
    avgOrderCountVariationPct: '20%',
    maxOrdersPerLevelVariationPct: '15%',
    minOrderValueVariationPct: '25%',
    orderIntervalVariationPct: '30%',
  },
  SWAP: {
    targetLiquidity: '1,000,000 EUR',
    avgSpread: '0.0050',
    tickSize: '0.0010',
    intervalSeconds: '90 sec',
    minOrderVolumeEur: '10,000 EUR',
    maxOrderVolumeEur: '500,000 EUR',
    volumeVariety: '5 / 10',
    priceDeviationPct: '2%',
    maxOrdersPerPriceLevel: '3',
    avgOrderCount: '8',
    maxLiquidityThreshold: '1,500,000 EUR',
    internalTradeInterval: '300 sec',
    internalTradeVolumeMin: '25,000 EUR',
    internalTradeVolumeMax: '200,000 EUR',
    avgOrderCountVariationPct: '15%',
    maxOrdersPerLevelVariationPct: '10%',
    minOrderValueVariationPct: '20%',
    orderIntervalVariationPct: '25%',
  },
};

// ============================================================================
// FIELD TOOLTIPS (hover explanations)
// ============================================================================

const FIELD_TIPS: Record<string, string> = {
  targetLiquidity: 'Total EUR value of open orders to maintain on this market side. The engine places/cancels orders to stay near this target.',
  avgSpread: 'Average bid-ask spread. For CEA Cash this is in EUR (e.g. 0.20 = 20 cents). For Swap this is in ratio units. Used by the algorithm to space orders around the mid price.',
  tickSize: 'Minimum price increment. All order prices are rounded to this step. CEA Cash: EUR steps (0.01 = 1 cent). Swap: ratio steps (0.0010).',
  intervalSeconds: 'How often (in seconds) the engine checks and places new orders. Lower = more active market, higher = calmer.',
  avgOrderCount: 'Target number of open orders to maintain. The engine distributes the target liquidity across this many orders.',
  minOrderVolumeEur: 'Minimum EUR value for a single order. Orders below this threshold are skipped.',
  maxOrderVolumeEur: 'Maximum EUR value for a single order. Large orders are capped at this amount.',
  volumeVariety: 'Controls order size distribution. 1 = all orders similar size (uniform). 10 = wide range of sizes (log-normal). Higher values create more realistic order books.',
  priceDeviationPct: 'Maximum price depth as % from best price. Orders are spread from the best price down to this % away. Larger = deeper order book.',
  maxOrdersPerPriceLevel: 'Maximum number of orders allowed at the same price level. Prevents unrealistic order stacking.',
  maxLiquidityThreshold: 'When total liquidity exceeds this EUR value, the engine triggers internal trades to reduce it back toward the target.',
  internalTradeInterval: 'Cooldown (seconds) between internal trades. Prevents excessive self-matching when liquidity is at target.',
  internalTradeVolumeMin: 'Minimum EUR volume for each internal (self-matching) trade.',
  internalTradeVolumeMax: 'Maximum EUR volume for each internal trade. Actual volume follows a log-normal distribution between min and max.',
  avgOrderCountVariationPct: 'Random ± variation applied to Avg Order Count each cycle. E.g. 20% means the count varies ±20% around the configured average.',
  maxOrdersPerLevelVariationPct: 'Random ± variation on Max Orders/Level each cycle. Adds natural randomness to order book depth.',
  minOrderValueVariationPct: 'Random ± variation on Min Order Value each cycle. Prevents predictable minimum order sizes.',
  orderIntervalVariationPct: 'Random ± variation on Order Interval each cycle. Makes timing less predictable and more realistic.',
};

// ============================================================================
// HELPERS
// ============================================================================

function formatEuro(value: number | null | undefined): string {
  if (value === null || value === undefined) return '€0';
  return `€${formatNumberWithSeparators(value, 'en-US', 0)}`;
}

/** Format a number for display in inputs (thousands separators, optional decimals) */
function fmtInput(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined) return '';
  return formatNumberWithSeparators(value, 'en-US', decimals);
}

// ============================================================================
// SMALL COMPONENTS
// ============================================================================

function ToggleSwitch({ checked, onChange, disabled, color = 'emerald' }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  color?: 'emerald' | 'red' | 'blue';
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors
        ${checked ? COLOR_MAP[color].toggle : 'bg-navy-600'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform
        ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  );
}

function LiquidityBar({ current, target, color }: {
  current: number | null;
  target: number | null;
  color: 'emerald' | 'red' | 'blue';
}) {
  const pct = target && target > 0 ? ((current || 0) / target) * 100 : 0;
  const clamped = Math.min(pct, 150);
  const w = (clamped / 150) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-navy-400">Liquidity</span>
        <span className="text-white font-medium">
          {formatEuro(current)} <span className="text-navy-500">/ {formatEuro(target)}</span>
        </span>
      </div>
      <div className="w-full h-2 bg-navy-800 rounded-full overflow-hidden">
        <div
          className={`h-full ${COLOR_MAP[color].bar} rounded-full transition-all duration-500`}
          style={{ width: `${w}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-navy-600">
        <span>0%</span>
        <span>{pct > 0 ? `${pct.toFixed(0)}%` : '-'}</span>
        <span>150%</span>
      </div>
    </div>
  );
}

// ============================================================================
// TOOLTIP + SETTINGS INPUT WITH FORMATTING + RECOMMENDED HINT
// ============================================================================

function FieldLabel({ label, tipKey, htmlFor }: { label: string; tipKey?: string; htmlFor?: string }) {
  const [show, setShow] = useState(false);
  const tip = tipKey ? FIELD_TIPS[tipKey] : undefined;

  if (!tip) return <label htmlFor={htmlFor} className="text-[11px] text-navy-400 font-medium">{label}</label>;

  return (
    <div className="relative inline-flex items-center gap-1 group">
      <label
        htmlFor={htmlFor}
        className="text-[11px] text-navy-400 font-medium cursor-help"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {label}
      </label>
      <Info
        className="w-3 h-3 text-navy-600 opacity-0 group-hover:opacity-100 transition-opacity cursor-help"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <div className="absolute left-0 bottom-full mb-1.5 z-50 w-64 px-3 py-2 text-[11px] leading-relaxed
                        text-navy-200 bg-navy-800 border border-navy-700 rounded-lg shadow-xl
                        pointer-events-none animate-in fade-in duration-150">
          {tip}
        </div>
      )}
    </div>
  );
}

function SettingsInput({ label, value, onChange, suffix, min, max, step, decimals, hint, tipKey }: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  suffix?: string;
  min?: number;
  max?: number;
  step?: number;
  decimals?: number;
  hint?: string;
  tipKey?: string;
}) {
  const id = useId();
  const dec = decimals ?? (step && step < 1 ? Math.max(0, -Math.floor(Math.log10(step))) : 0);
  const [focused, setFocused] = useState(false);
  const [rawText, setRawText] = useState('');

  const displayValue = focused
    ? rawText
    : fmtInput(value, dec);

  return (
    <div className="space-y-0.5">
      <FieldLabel label={label} tipKey={tipKey} htmlFor={id} />
      <div className="flex items-center gap-1.5">
        <input
          id={id}
          type="text"
          inputMode="decimal"
          value={displayValue}
          onFocus={() => {
            setFocused(true);
            setRawText(value !== null && value !== undefined ? String(value) : '');
          }}
          onBlur={() => {
            setFocused(false);
            if (rawText === '') {
              onChange(null);
            } else {
              const n = parseFloat(rawText);
              if (!isNaN(n)) onChange(n);
            }
          }}
          onChange={e => {
            const v = e.target.value;
            if (/^-?\d*\.?\d*$/.test(v) || v === '') {
              setRawText(v);
            }
          }}
          min={min}
          max={max}
          step={step ?? 1}
          className="w-full bg-navy-900 border border-navy-700 rounded-lg px-2.5 py-1.5 text-sm text-white
                     focus:outline-none focus:border-emerald-500/50 transition-colors tabular-nums"
        />
        {suffix && <span className="text-[11px] text-navy-500 whitespace-nowrap">{suffix}</span>}
      </div>
      {hint && (
        <button
          type="button"
          onClick={() => {
            const num = parseFloat(hint.replace(/[^0-9.\-]/g, '').replace(/^\./, '0.'));  // eslint-disable-line no-useless-escape
            if (!isNaN(num)) onChange(num);
          }}
          className="text-[10px] text-navy-600 italic hover:text-emerald-400 cursor-pointer transition-colors"
          title="Click to use recommended value"
        >
          Rec: {hint}
        </button>
      )}
    </div>
  );
}

function VarietySlider({ value, onChange, hint }: {
  value: number;
  onChange: (v: number) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <FieldLabel label="Volume Variety" tipKey="volumeVariety" />
        <span className="text-xs text-white font-medium">{value}/10</span>
      </div>
      <input
        type="range"
        min={1}
        max={10}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 bg-navy-700 rounded-full appearance-none cursor-pointer
                   [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4
                   [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full
                   [&::-webkit-slider-thumb]:bg-emerald-400 [&::-webkit-slider-thumb]:cursor-pointer"
      />
      <div className="flex justify-between text-[10px] text-navy-600">
        <span>Uniform</span>
        <span>Log-normal</span>
        <span>Very Diverse</span>
      </div>
      {hint && (
        <button
          type="button"
          onClick={() => {
            const match = hint.match(/\d+/);
            if (match) onChange(Number(match[0]));
          }}
          className="text-[10px] text-navy-600 italic hover:text-emerald-400 cursor-pointer transition-colors"
          title="Click to use recommended value"
        >
          Rec: {hint}
        </button>
      )}
    </div>
  );
}

// ============================================================================
// FULL SETTINGS FORM (ALL FIELDS + ADVANCED EXPAND)
// ============================================================================

interface AllSideSettings {
  targetLiquidity: number | null;
  avgSpread: number | null;
  tickSize: number | null;
  intervalSeconds: number;
  minOrderVolumeEur: number;
  maxOrderVolumeEur: number | null;
  volumeVariety: number;
  priceDeviationPct: number;
  maxOrdersPerPriceLevel: number;
  avgOrderCount: number;
  maxLiquidityThreshold: number | null;
  internalTradeInterval: number | null;
  internalTradeVolumeMin: number | null;
  internalTradeVolumeMax: number | null;
  // Advanced variation % fields
  avgOrderCountVariationPct: number;
  maxOrdersPerLevelVariationPct: number;
  minOrderValueVariationPct: number;
  orderIntervalVariationPct: number;
  // Executor algorithm params
  alignmentCorrectionFactor: number;
  alignmentThresholdTicks: number;
  levelRebalanceDepth: number;
}

function extractAllSettings(s: AutoTradeMarketSettings): AllSideSettings {
  return {
    targetLiquidity: s.targetLiquidity,
    avgSpread: s.avgSpread,
    tickSize: s.tickSize,
    intervalSeconds: s.intervalSeconds,
    minOrderVolumeEur: s.minOrderVolumeEur,
    maxOrderVolumeEur: s.maxOrderVolumeEur,
    volumeVariety: s.volumeVariety,
    priceDeviationPct: s.priceDeviationPct,
    maxOrdersPerPriceLevel: s.maxOrdersPerPriceLevel,
    avgOrderCount: s.avgOrderCount,
    maxLiquidityThreshold: s.maxLiquidityThreshold,
    internalTradeInterval: s.internalTradeInterval,
    internalTradeVolumeMin: s.internalTradeVolumeMin,
    internalTradeVolumeMax: s.internalTradeVolumeMax,
    avgOrderCountVariationPct: s.avgOrderCountVariationPct,
    maxOrdersPerLevelVariationPct: s.maxOrdersPerLevelVariationPct,
    minOrderValueVariationPct: s.minOrderValueVariationPct,
    orderIntervalVariationPct: s.orderIntervalVariationPct,
    alignmentCorrectionFactor: s.alignmentCorrectionFactor,
    alignmentThresholdTicks: s.alignmentThresholdTicks,
    levelRebalanceDepth: s.levelRebalanceDepth,
  };
}

function SideSettingsForm({
  label,
  color,
  settings,
  onChange,
  rec,
  showBidAsk,
  bidTarget,
  askTarget,
  onBidTargetChange,
  onAskTargetChange,
}: {
  label: string;
  color: string;
  settings: AllSideSettings;
  onChange: (s: AllSideSettings) => void;
  rec: Record<string, string>;
  showBidAsk?: boolean;
  bidTarget?: number | null;
  askTarget?: number | null;
  onBidTargetChange?: (v: number | null) => void;
  onAskTargetChange?: (v: number | null) => void;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [expertOpen, setExpertOpen] = useState(false);
  const update = (patch: Partial<AllSideSettings>) => onChange({ ...settings, ...patch });
  const isSwap = label.toLowerCase().includes('swap');

  return (
    <div className="space-y-4">
      <h4 className={`text-sm font-semibold ${color} flex items-center gap-2`}>
        <Settings className="w-4 h-4" />
        {label}
      </h4>

      {/* ═══ MAIN FIELDS (always visible) ═══ */}

      {/* Liquidity targets */}
      {showBidAsk ? (
        <div className="grid grid-cols-2 gap-3">
          <SettingsInput
            label="BID Liquidity Target"
            value={bidTarget ?? null}
            onChange={v => onBidTargetChange?.(v)}
            suffix="EUR"
            min={0}
            hint={rec.targetLiquidity}
            tipKey="targetLiquidity"
          />
          <SettingsInput
            label="ASK Liquidity Target"
            value={askTarget ?? null}
            onChange={v => onAskTargetChange?.(v)}
            suffix="EUR"
            min={0}
            hint={rec.targetLiquidity}
            tipKey="targetLiquidity"
          />
        </div>
      ) : (
        <SettingsInput
          label="Liquidity Target"
          value={settings.targetLiquidity}
          onChange={v => update({ targetLiquidity: v })}
          suffix="EUR"
          min={0}
          hint={rec.targetLiquidity}
          tipKey="targetLiquidity"
        />
      )}

      {/* Spread & Tick Size */}
      <div className="grid grid-cols-2 gap-3">
        <SettingsInput
          label="Avg Spread"
          value={settings.avgSpread}
          onChange={v => update({ avgSpread: v })}
          suffix={isSwap ? 'ratio' : 'EUR'}
          min={0}
          step={isSwap ? 0.0001 : 0.01}
          decimals={isSwap ? 4 : 2}
          hint={rec.avgSpread}
          tipKey="avgSpread"
        />
        <SettingsInput
          label="Tick Size"
          value={settings.tickSize}
          onChange={v => update({ tickSize: v })}
          suffix={isSwap ? 'ratio' : 'EUR'}
          min={0}
          step={isSwap ? 0.0001 : 0.01}
          decimals={isSwap ? 4 : 2}
          hint={rec.tickSize}
          tipKey="tickSize"
        />
      </div>

      {/* Interval & Avg Order Count */}
      <div className="grid grid-cols-2 gap-3">
        <SettingsInput
          label="Order Interval"
          value={settings.intervalSeconds}
          onChange={v => update({ intervalSeconds: v ?? 60 })}
          suffix="sec"
          min={5}
          hint={rec.intervalSeconds}
          tipKey="intervalSeconds"
        />
        <SettingsInput
          label="Avg Order Count"
          value={settings.avgOrderCount}
          onChange={v => update({ avgOrderCount: v ?? 5 })}
          min={1}
          max={50}
          hint={rec.avgOrderCount}
          tipKey="avgOrderCount"
        />
      </div>

      {/* Volume range */}
      <div className="grid grid-cols-2 gap-3">
        <SettingsInput
          label="Min Volume"
          value={settings.minOrderVolumeEur}
          onChange={v => update({ minOrderVolumeEur: v ?? 0 })}
          suffix="EUR"
          min={0}
          hint={rec.minOrderVolumeEur}
          tipKey="minOrderVolumeEur"
        />
        <SettingsInput
          label="Max Volume"
          value={settings.maxOrderVolumeEur}
          onChange={v => update({ maxOrderVolumeEur: v })}
          suffix="EUR"
          min={0}
          hint={rec.maxOrderVolumeEur}
          tipKey="maxOrderVolumeEur"
        />
      </div>

      {/* ═══ ADVANCED (amber expandable) ═══ */}
      <div className="border-t border-navy-700/30 pt-2 mt-2">
        <button
          type="button"
          aria-expanded={advancedOpen}
          onClick={() => setAdvancedOpen(!advancedOpen)}
          className="flex items-center gap-1.5 text-[11px] hover:text-amber-300 transition-colors w-full"
        >
          <SlidersHorizontal className="w-3 h-3 text-amber-500/70" />
          <span className="font-medium text-amber-500/70">Advanced</span>
          {advancedOpen
            ? <ChevronUp className="w-3 h-3 ml-auto text-amber-500/50" />
            : <ChevronDown className="w-3 h-3 ml-auto text-amber-500/50" />
          }
        </button>
        {advancedOpen && (
          <div className="mt-3 space-y-4 pl-2 border-l-2 border-amber-500/20">
            {/* Volume variety slider */}
            <VarietySlider
              value={settings.volumeVariety}
              onChange={v => update({ volumeVariety: v })}
              hint={rec.volumeVariety}
            />

            {/* Price depth + max orders per level */}
            <div className="grid grid-cols-2 gap-3">
              <SettingsInput
                label="Max Price Depth"
                value={settings.priceDeviationPct}
                onChange={v => update({ priceDeviationPct: v ?? 0.5 })}
                suffix="%"
                min={0.1}
                max={50}
                step={0.1}
                decimals={1}
                hint={rec.priceDeviationPct}
                tipKey="priceDeviationPct"
              />
              <SettingsInput
                label="Max Orders/Level"
                value={settings.maxOrdersPerPriceLevel}
                onChange={v => update({ maxOrdersPerPriceLevel: v ?? 3 })}
                min={1}
                max={20}
                hint={rec.maxOrdersPerPriceLevel}
                tipKey="maxOrdersPerPriceLevel"
              />
            </div>

            {/* Max Liquidity Threshold */}
            <SettingsInput
              label="Max Liquidity Threshold"
              value={settings.maxLiquidityThreshold}
              onChange={v => update({ maxLiquidityThreshold: v })}
              suffix="EUR"
              min={0}
              hint={rec.maxLiquidityThreshold}
              tipKey="maxLiquidityThreshold"
            />

            {/* Internal trades section */}
            <div className="border-t border-navy-700/20 pt-3 mt-3">
              <p className="text-[11px] text-navy-500 mb-2 font-medium">Internal Trades (at target)</p>
              <div className="grid grid-cols-3 gap-3">
                <SettingsInput
                  label="Interval"
                  value={settings.internalTradeInterval}
                  onChange={v => update({ internalTradeInterval: v })}
                  suffix="sec"
                  min={10}
                  hint={rec.internalTradeInterval}
                  tipKey="internalTradeInterval"
                />
                <SettingsInput
                  label="Vol Min"
                  value={settings.internalTradeVolumeMin}
                  onChange={v => update({ internalTradeVolumeMin: v })}
                  suffix="EUR"
                  min={0}
                  hint={rec.internalTradeVolumeMin}
                  tipKey="internalTradeVolumeMin"
                />
                <SettingsInput
                  label="Vol Max"
                  value={settings.internalTradeVolumeMax}
                  onChange={v => update({ internalTradeVolumeMax: v })}
                  suffix="EUR"
                  min={0}
                  hint={rec.internalTradeVolumeMax}
                  tipKey="internalTradeVolumeMax"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ═══ EXPERT (red expandable) ═══ */}
      <div className="border-t border-navy-700/30 pt-2 mt-1">
        <button
          type="button"
          aria-expanded={expertOpen}
          onClick={() => setExpertOpen(!expertOpen)}
          className="flex items-center gap-1.5 text-[11px] hover:text-red-300 transition-colors w-full"
        >
          <AlertTriangle className="w-3 h-3 text-red-500/60" />
          <span className="font-medium text-red-500/60">Expert</span>
          {expertOpen
            ? <ChevronUp className="w-3 h-3 ml-auto text-red-500/40" />
            : <ChevronDown className="w-3 h-3 ml-auto text-red-500/40" />
          }
        </button>
        {expertOpen && (
          <div className="mt-3 space-y-3 pl-2 border-l-2 border-red-500/20">
            <p className="text-[10px] text-navy-600">
              Variation percentages add randomness (±%) to each parameter per cycle.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <SettingsInput
                label="Order Count ±"
                value={settings.avgOrderCountVariationPct}
                onChange={v => update({ avgOrderCountVariationPct: v ?? 0 })}
                suffix="%"
                min={0}
                max={100}
                hint={rec.avgOrderCountVariationPct}
                tipKey="avgOrderCountVariationPct"
              />
              <SettingsInput
                label="Orders/Level ±"
                value={settings.maxOrdersPerLevelVariationPct}
                onChange={v => update({ maxOrdersPerLevelVariationPct: v ?? 0 })}
                suffix="%"
                min={0}
                max={100}
                hint={rec.maxOrdersPerLevelVariationPct}
                tipKey="maxOrdersPerLevelVariationPct"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <SettingsInput
                label="Min Order Value ±"
                value={settings.minOrderValueVariationPct}
                onChange={v => update({ minOrderValueVariationPct: v ?? 0 })}
                suffix="%"
                min={0}
                max={100}
                hint={rec.minOrderValueVariationPct}
                tipKey="minOrderValueVariationPct"
              />
              <SettingsInput
                label="Order Interval ±"
                value={settings.orderIntervalVariationPct}
                onChange={v => update({ orderIntervalVariationPct: v ?? 0 })}
                suffix="%"
                min={0}
                max={100}
                hint={rec.orderIntervalVariationPct}
                tipKey="orderIntervalVariationPct"
              />
            </div>
            <div className="border-t border-navy-700/20 pt-3 mt-3">
              <p className="text-[11px] text-navy-500 mb-2 font-medium">Priority Engine Params</p>
              <div className="grid grid-cols-3 gap-3">
                <SettingsInput
                  label="Correction Factor"
                  value={settings.alignmentCorrectionFactor}
                  onChange={v => update({ alignmentCorrectionFactor: v ?? 0.60 })}
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  decimals={2}
                  hint="0.60"
                  tipKey="alignmentCorrectionFactor"
                />
                <SettingsInput
                  label="Align Threshold"
                  value={settings.alignmentThresholdTicks}
                  onChange={v => update({ alignmentThresholdTicks: v ?? 2 })}
                  suffix="ticks"
                  min={1}
                  max={20}
                  hint="2"
                  tipKey="alignmentThresholdTicks"
                />
                <SettingsInput
                  label="Rebalance Depth"
                  value={settings.levelRebalanceDepth}
                  onChange={v => update({ levelRebalanceDepth: v ?? 5 })}
                  suffix="lvls"
                  min={1}
                  max={20}
                  hint="5"
                  tipKey="levelRebalanceDepth"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// LIQUIDITY SETTINGS PANEL (main expandable)
// ============================================================================

function LiquiditySettingsPanel({
  markets,
  onSave,
  saving,
}: {
  markets: AutoTradeMarketSettings[];
  onSave: (updates: { marketKey: string; data: AutoTradeMarketSettingsUpdate }[]) => Promise<void>;
  saving: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const bidMarket = markets.find(m => m.marketKey === 'CEA_BID');
  const askMarket = markets.find(m => m.marketKey === 'CEA_ASK');
  const swapMarket = markets.find(m => m.marketKey === 'EUA_SWAP');

  // Local form state
  const [bidSettings, setBidSettings] = useState<AllSideSettings | null>(null);
  const [askSettings, setAskSettings] = useState<AllSideSettings | null>(null);
  const [swapSettings, setSwapSettings] = useState<AllSideSettings | null>(null);

  // Initialize form state when markets load
  useEffect(() => {
    if (bidMarket && !bidSettings) setBidSettings(extractAllSettings(bidMarket));
    if (askMarket && !askSettings) setAskSettings(extractAllSettings(askMarket));
    if (swapMarket && !swapSettings) setSwapSettings(extractAllSettings(swapMarket));
  }, [bidMarket, askMarket, swapMarket, bidSettings, askSettings, swapSettings]);

  const handleSave = async () => {
    const updates: { marketKey: string; data: AutoTradeMarketSettingsUpdate }[] = [];
    if (bidSettings) updates.push({ marketKey: 'CEA_BID', data: bidSettings });
    if (askSettings) updates.push({ marketKey: 'CEA_ASK', data: askSettings });
    if (swapSettings) updates.push({ marketKey: 'EUA_SWAP', data: swapSettings });
    await onSave(updates);
  };

  if (!bidMarket || !askMarket || !swapMarket) return null;

  return (
    <Card className="border-l-4 border-l-amber-500 bg-navy-800/60 border-navy-700/30 overflow-hidden mb-5">
      {/* Collapsible header */}
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-4 flex items-center justify-between hover:bg-navy-700/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-500/20">
            <Zap className="w-5 h-5 text-amber-400" />
          </div>
          <div className="text-left">
            <h3 className="text-base font-semibold text-white">Liquidity & Auto Trade</h3>
            <p className="text-[11px] text-navy-400">Market simulation parameters for CEA Cash & Swap</p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-navy-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-navy-400" />
        )}
      </button>

      {/* Expandable content */}
      {expanded && (
        <div className="px-5 pb-5 border-t border-navy-700/30">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4">
            {/* CEA Cash Market section */}
            {bidSettings && askSettings && (
              <div className="bg-navy-900/40 rounded-lg p-4 border border-navy-700/20">
                <SideSettingsForm
                  label="CEA Cash Market"
                  color="text-emerald-400"
                  settings={bidSettings}
                  rec={RECOMMENDED.CEA_CASH}
                  onChange={s => {
                    setBidSettings(s);
                    // Sync shared fields to ASK (everything except targetLiquidity)
                    setAskSettings(prev => prev ? {
                      ...prev,
                      avgSpread: s.avgSpread,
                      tickSize: s.tickSize,
                      intervalSeconds: s.intervalSeconds,
                      minOrderVolumeEur: s.minOrderVolumeEur,
                      maxOrderVolumeEur: s.maxOrderVolumeEur,
                      volumeVariety: s.volumeVariety,
                      priceDeviationPct: s.priceDeviationPct,
                      maxOrdersPerPriceLevel: s.maxOrdersPerPriceLevel,
                      avgOrderCount: s.avgOrderCount,
                      maxLiquidityThreshold: s.maxLiquidityThreshold,
                      internalTradeInterval: s.internalTradeInterval,
                      internalTradeVolumeMin: s.internalTradeVolumeMin,
                      internalTradeVolumeMax: s.internalTradeVolumeMax,
                      avgOrderCountVariationPct: s.avgOrderCountVariationPct,
                      maxOrdersPerLevelVariationPct: s.maxOrdersPerLevelVariationPct,
                      minOrderValueVariationPct: s.minOrderValueVariationPct,
                      orderIntervalVariationPct: s.orderIntervalVariationPct,
                      alignmentCorrectionFactor: s.alignmentCorrectionFactor,
                      alignmentThresholdTicks: s.alignmentThresholdTicks,
                      levelRebalanceDepth: s.levelRebalanceDepth,
                    } : prev);
                  }}
                  showBidAsk
                  bidTarget={bidSettings.targetLiquidity}
                  askTarget={askSettings.targetLiquidity}
                  onBidTargetChange={v => setBidSettings(prev => prev ? { ...prev, targetLiquidity: v } : prev)}
                  onAskTargetChange={v => setAskSettings(prev => prev ? { ...prev, targetLiquidity: v } : prev)}
                />
              </div>
            )}

            {/* Swap Market section */}
            {swapSettings && (
              <div className="bg-navy-900/40 rounded-lg p-4 border border-navy-700/20">
                <SideSettingsForm
                  label="Swap Market"
                  color="text-blue-400"
                  settings={swapSettings}
                  rec={RECOMMENDED.SWAP}
                  onChange={setSwapSettings}
                />
              </div>
            )}
          </div>

          {/* Save button */}
          <div className="flex justify-end mt-4">
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={saving}
              icon={<Save className="w-4 h-4" />}
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// MARKET SECTION COMPONENT
// ============================================================================

function MarketSection({ settings, onToggle, isToggling }: {
  settings: AutoTradeMarketSettings;
  onToggle: (enabled: boolean) => void;
  isToggling: boolean;
}) {
  const cfg = MARKET_CONFIG[settings.marketKey];
  const clr = COLOR_MAP[cfg.color];
  const Icon = cfg.icon;

  return (
    <Card className={`border-l-4 ${cfg.accentBorder} bg-navy-800/60 border-navy-700/30 overflow-hidden`}>
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-navy-700/30">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${clr.bg}`}>
            <Icon className={`w-5 h-5 ${clr.text}`} />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">{cfg.title}</h3>
            <p className="text-[11px] text-navy-400">{cfg.subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {settings.enabled ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> ON
            </span>
          ) : (
            <span className="text-xs text-navy-500 font-medium">OFF</span>
          )}
          <ToggleSwitch
            checked={settings.enabled}
            onChange={onToggle}
            disabled={isToggling}
            color={cfg.color}
          />
        </div>
      </div>

      {/* Liquidity Bar */}
      <div className="px-5 py-3 border-b border-navy-700/20">
        <LiquidityBar
          current={settings.currentLiquidity}
          target={settings.targetLiquidity}
          color={cfg.color}
        />
      </div>

      {/* MM Info footer */}
      <div className="px-5 py-3 bg-navy-900/30 flex items-center gap-1.5 text-[11px] text-navy-500">
        <Zap className="w-3 h-3 flex-shrink-0" />
        <span className="truncate">{settings.marketMakers.map(mm => mm.name).join(', ') || 'No MMs'}</span>
      </div>
    </Card>
  );
}

// ============================================================================
// MAIN PAGE
// ============================================================================

export function AutoTradePage() {
  const [markets, setMarkets] = useState<AutoTradeMarketSettings[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingSwap, setRefreshingSwap] = useState(false);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-orders — global background service (runs even when not on this page)
  const { isRunning: autoOrdering, nextOrderIn, orderCount } = useAutoOrdersStore();

  const loadMarkets = useCallback(async (silent = false) => {
    try {
      const data = await adminApi.getMarketSettings();
      const order = ['CEA_BID', 'CEA_ASK', 'EUA_SWAP'];
      data.sort((a, b) => order.indexOf(a.marketKey) - order.indexOf(b.marketKey));
      setMarkets(data);
      if (!silent) setError(null);
    } catch (err) {
      if (!silent) setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + auto-refresh
  useEffect(() => {
    loadMarkets();
    refreshTimerRef.current = setInterval(() => loadMarkets(true), REFRESH_INTERVAL_MS);
    return () => { if (refreshTimerRef.current) clearInterval(refreshTimerRef.current); };
  }, [loadMarkets]);

  // Toggle handler
  const handleToggle = useCallback(async (marketKey: string, enabled: boolean) => {
    setToggling(marketKey);
    try {
      const updated = await adminApi.updateMarketSettings(marketKey, { enabled });
      setMarkets(prev => prev.map(m => m.marketKey === marketKey ? updated : m));
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setToggling(null);
    }
  }, []);

  // Refresh CEA Market handler
  const handleRefreshCea = useCallback(async () => {
    setRefreshing(true);
    setRefreshResult(null);
    try {
      const result = await adminApi.refreshCeaMarket();
      const dev = result.price_deviation_pct ? ` (${Number(result.price_deviation_pct) > 0 ? '+' : ''}${result.price_deviation_pct}%)` : '';
      setRefreshResult(
        `CEA scraped: €${result.cea_price_eur} → mid: €${result.mid_price_eur}${dev}. ` +
        `${result.bid_orders_created} bids + ${result.ask_orders_created} asks.`
      );
      await loadMarkets(true);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setRefreshing(false);
    }
  }, [loadMarkets]);

  // Refresh Swap Market handler
  const handleRefreshSwap = useCallback(async () => {
    setRefreshingSwap(true);
    setRefreshResult(null);
    try {
      const result = await adminApi.refreshSwapMarket();
      const dev = result.midRatio ? ` (mid ratio: ${result.midRatio})` : '';
      setRefreshResult(
        `Swap: base ratio ${result.baseRatio}${dev}. ` +
        `${result.ordersCreated} orders → €${Number(result.liquidityEur).toLocaleString('en-US', { maximumFractionDigits: 0 })} / €${Number(result.targetLiquidityEur).toLocaleString('en-US', { maximumFractionDigits: 0 })}.`
      );
      await loadMarkets(true);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setRefreshingSwap(false);
    }
  }, [loadMarkets]);

  // Save settings handler for LiquiditySettingsPanel
  const handleSaveSettings = useCallback(async (
    updates: { marketKey: string; data: AutoTradeMarketSettingsUpdate }[]
  ) => {
    setSavingSettings(true);
    try {
      await Promise.all(updates.map(({ marketKey, data }) =>
        adminApi.updateMarketSettings(marketKey, data)
      ));
      setRefreshResult('Settings saved successfully.');
      await loadMarkets(true);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSavingSettings(false);
    }
  }, [loadMarkets]);

  // Clear refresh result after 8s
  useEffect(() => {
    if (refreshResult) {
      const t = setTimeout(() => setRefreshResult(null), 8000);
      return () => clearTimeout(t);
    }
  }, [refreshResult]);

  // Auto-refresh market data when an order is placed in the background
  const prevOrderCount = useRef(orderCount);
  useEffect(() => {
    if (orderCount > prevOrderCount.current) {
      loadMarkets(true);
    }
    prevOrderCount.current = orderCount;
  }, [orderCount, loadMarkets]);

  const subSubHeader = (
    <div className="flex items-center gap-3">
      {/* Read-only executor status indicator */}
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-navy-800/80 border border-navy-700/40 text-xs">
        {autoOrdering ? (
          <>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-emerald-400 font-medium">Executor ON</span>
            {nextOrderIn !== null && (
              <span className="text-navy-400 ml-1">next: {nextOrderIn}s</span>
            )}
            {orderCount > 0 && (
              <span className="text-navy-500 ml-1">({orderCount} orders/cycle)</span>
            )}
          </>
        ) : (
          <>
            <span className="w-2 h-2 rounded-full bg-navy-600" />
            <span className="text-navy-500 font-medium">Executor OFF</span>
          </>
        )}
      </div>
      <Button
        variant="secondary"
        size="sm"
        onClick={handleRefreshCea}
        disabled={refreshing}
        icon={<RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />}
      >
        Refresh CEA
      </Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={handleRefreshSwap}
        disabled={refreshingSwap}
        icon={<ArrowLeftRight className={`w-4 h-4 ${refreshingSwap ? 'animate-spin' : ''}`} />}
      >
        Refresh Swap
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => loadMarkets()}
        disabled={loading}
        icon={<RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />}
        title="Refresh data"
        aria-label="Refresh data"
      />
    </div>
  );

  return (
    <BackofficeLayout subSubHeader={subSubHeader}>
      {error && (
            <AlertBanner
              variant="error"
              message={error}
              onDismiss={() => setError(null)}
              className="mb-4"
            />
          )}
          {refreshResult && (
            <AlertBanner
              variant="success"
              message={refreshResult}
              onDismiss={() => setRefreshResult(null)}
              className="mb-4"
            />
          )}

          {loading && markets.length === 0 ? (
            <div className="flex items-center justify-center py-20">
              <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
            </div>
          ) : (
            <>
              {/* Expandable Liquidity & Auto Trade settings panel */}
              {markets.length > 0 && (
                <LiquiditySettingsPanel
                  markets={markets}
                  onSave={handleSaveSettings}
                  saving={savingSettings}
                />
              )}

              <div className="space-y-6">
                {markets.map(market => (
                  <MarketSection
                    key={market.marketKey}
                    settings={market}
                    onToggle={(enabled) => handleToggle(market.marketKey, enabled)}
                    isToggling={toggling === market.marketKey}
                  />
                ))}
              </div>
            </>
          )}
    </BackofficeLayout>
  );
}

export default AutoTradePage;
