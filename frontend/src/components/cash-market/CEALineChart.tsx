import { useState, useCallback, useEffect, useRef } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { TrendingUp, Clock, ChevronDown } from 'lucide-react';
import { cashMarketApi } from '../../services/api';
import type { CashMarketTrade } from '../../types';

// ─── Time intervals ───────────────────────────────────────────────────────────

const TIME_INTERVALS = [
  { label: '1m',  seconds: 60 },
  { label: '5m',  seconds: 300 },
  { label: '15m', seconds: 900 },
  { label: '1h',  seconds: 3600 },
  { label: '6h',  seconds: 21600 },
  { label: '1D',  seconds: 86400 },
];

const DEFAULT_INTERVAL = TIME_INTERVALS[2]; // 15m

// ─── Types ────────────────────────────────────────────────────────────────────

interface ChartPoint {
  time: number;   // unix seconds
  value: number;  // close price
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatAxisTime(unixSec: number, intervalSec: number): string {
  const d = new Date(unixSec * 1000);
  if (intervalSec >= 86400) {
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
  }
  if (intervalSec >= 3600) {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function formatTooltipTime(unixSec: number): string {
  return new Date(unixSec * 1000).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

// ─── Custom tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { value: number; payload: ChartPoint }[] }) {
  if (!active || !payload?.length) return null;
  const { time, value } = payload[0].payload;
  return (
    <div className="bg-navy-800 border border-navy-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-navy-400 mb-0.5">{formatTooltipTime(time)}</p>
      <p className="font-mono font-semibold text-emerald-400">€{value.toFixed(2)}</p>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function CEALineChart() {
  const [interval, setInterval] = useState(DEFAULT_INTERVAL);
  const [data, setData] = useState<ChartPoint[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const intervalRef = useRef(DEFAULT_INTERVAL);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node))
        setDropdownOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [dropdownOpen]);

  const fetchData = useCallback(async () => {
    try {
      const raw = await cashMarketApi.getOHLC('CEA', intervalRef.current.seconds);
      setData(raw.map(c => ({ time: c.time as number, value: c.close })));
    } catch (err) {
      console.error('CEALineChart fetch error:', err);
    }
  }, []);

  // Re-fetch on interval change
  useEffect(() => {
    intervalRef.current = interval;
    fetchData();
  }, [interval, fetchData]);

  // Initial fetch + polling + live trade updates
  useEffect(() => {
    let mounted = true;
    fetchData();
    const poll = window.setInterval(() => { if (mounted) fetchData(); }, 30_000);

    const handler = (e: Event) => {
      const { trade } = (e as CustomEvent<{ trade: CashMarketTrade }>).detail ?? {};
      if (!trade || !mounted || trade.certificateType !== 'CEA') return;

      const price = trade.price;
      let ts = Date.now() / 1000;
      if (trade.executedAt) {
        try {
          const utc = trade.executedAt.endsWith('Z') ? trade.executedAt : trade.executedAt + 'Z';
          const d = new Date(utc);
          if (!isNaN(d.getTime())) ts = d.getTime() / 1000;
        } catch { /* fallback */ }
      }

      const bucket = Math.floor(ts / intervalRef.current.seconds) * intervalRef.current.seconds;
      setData(prev => {
        const last = prev[prev.length - 1];
        if (last && last.time === bucket) {
          return [...prev.slice(0, -1), { time: bucket, value: price }];
        }
        return [...prev, { time: bucket, value: price }];
      });
    };
    window.addEventListener('nihao:tradeExecuted', handler);

    return () => {
      mounted = false;
      clearInterval(poll);
      window.removeEventListener('nihao:tradeExecuted', handler);
    };
  }, [fetchData]);

  // Y-axis domain with small padding
  const yDomain = (() => {
    if (data.length === 0) return ['auto', 'auto'] as const;
    const values = data.map(d => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.15 || 0.1;
    return [
      parseFloat((min - pad).toFixed(2)),
      parseFloat((max + pad).toFixed(2)),
    ] as const;
  })();

  return (
    <div className="rounded-xl border border-navy-700/50 bg-navy-800/30 overflow-hidden widget-accent-emerald">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-navy-700/50 flex items-center gap-2 bg-navy-800/50">
        <TrendingUp className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
        <span className="text-[11px] font-semibold text-navy-300 uppercase tracking-wider">CEA Price</span>
        <div className="live-dot bg-emerald-400 ml-1" title="Live" />

        {/* Interval selector */}
        <div className="relative ml-auto" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(p => !p)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium
              text-navy-300 hover:text-white hover:bg-navy-700/50 transition-colors"
          >
            <Clock className="w-3 h-3" />
            <span>{interval.label}</span>
            <ChevronDown className={`w-3 h-3 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 bg-navy-800 border border-navy-700
              rounded-lg shadow-xl py-1 min-w-[80px]">
              {TIME_INTERVALS.map(ti => (
                <button
                  key={ti.label}
                  onClick={() => { setInterval(ti); setDropdownOpen(false); }}
                  className={`w-full text-left px-3 py-1.5 text-[11px] font-mono transition-colors
                    ${ti.label === interval.label
                      ? 'text-emerald-400 bg-emerald-500/10'
                      : 'text-navy-300 hover:text-white hover:bg-navy-700/50'
                    }`}
                >
                  {ti.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="h-52 px-1 pt-3 pb-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ceaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#34d399" stopOpacity={0.20} />
                <stop offset="100%" stopColor="#34d399" stopOpacity={0.00} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(51,65,85,0.35)"
              vertical={false}
            />

            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tickFormatter={v => formatAxisTime(v, interval.seconds)}
              tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(51,65,85,0.4)' }}
              minTickGap={50}
            />

            <YAxis
              domain={yDomain}
              tickFormatter={v => `€${Number(v).toFixed(2)}`}
              tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'ui-monospace, monospace' }}
              tickLine={false}
              axisLine={false}
              width={52}
            />

            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: '#64748b', strokeWidth: 1, strokeDasharray: '4 4' }}
            />

            <Area
              type="monotone"
              dataKey="value"
              stroke="#34d399"
              strokeWidth={2}
              fill="url(#ceaGradient)"
              dot={false}
              activeDot={{ r: 4, fill: '#34d399', stroke: '#1e293b', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
