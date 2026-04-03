import type { ReactNode } from 'react';

interface Bar {
  label: string;
  value: number;
  color?: string;
  displayValue?: string;
}

interface Props {
  bars: Bar[];
  maxValue?: number;
  unit?: string;
  title?: string;
  horizontal?: boolean;
  annotation?: ReactNode;
}

const DEFAULT_COLOR = 'var(--color-success)';

export function MiniBarChart({
  bars,
  maxValue: maxOverride,
  unit = '',
  title,
  horizontal = true,
  annotation,
}: Props) {
  const max = maxOverride ?? Math.max(...bars.map((b) => b.value), 1);

  if (horizontal) {
    return (
      <div className="my-3">
        {title && <div className="text-[10px] uppercase tracking-wider text-navy-500 mb-2">{title}</div>}
        <div className="space-y-1.5">
          {bars.map((bar) => {
            const pct = Math.max((bar.value / max) * 100, 3);
            const display = bar.displayValue ?? `${bar.value}${unit}`;
            return (
              <div key={bar.label} className="flex items-center gap-2">
                <span className="text-[10px] text-navy-400 w-24 text-right flex-shrink-0 truncate">{bar.label}</span>
                <div className="flex-1 bg-navy-900/50 rounded-full h-4 overflow-hidden">
                  <div
                    className="h-full rounded-full flex items-center justify-end pr-2"
                    style={{ width: `${pct}%`, background: bar.color ?? DEFAULT_COLOR, opacity: 0.45 }}
                  />
                </div>
                <span className="text-[10px] text-navy-300 font-mono w-16 flex-shrink-0">{display}</span>
              </div>
            );
          })}
        </div>
        {annotation && <div className="text-[10px] text-navy-600 mt-1.5 italic">{annotation}</div>}
      </div>
    );
  }

  // Vertical bars
  return (
    <div className="my-3">
      {title && <div className="text-[10px] uppercase tracking-wider text-navy-500 mb-2">{title}</div>}
      <div className="flex items-end gap-1 h-24">
        {bars.map((bar) => {
          const pct = Math.max((bar.value / max) * 100, 2);
          const display = bar.displayValue ?? `${bar.value}${unit}`;
          return (
            <div key={bar.label} className="flex-1 flex flex-col items-center gap-0.5 min-w-0">
              <span className="text-[8px] text-navy-300 font-mono truncate max-w-full">{display}</span>
              <div className="w-full flex justify-center" style={{ height: '72px' }}>
                <div className="flex items-end w-full max-w-[36px]">
                  <div
                    className="w-full rounded-t-sm"
                    style={{
                      height: `${pct}%`,
                      background: bar.color ?? DEFAULT_COLOR,
                      opacity: 0.5,
                    }}
                  />
                </div>
              </div>
              <span className="text-[8px] text-navy-500 truncate max-w-full text-center">{bar.label}</span>
            </div>
          );
        })}
      </div>
      {annotation && <div className="text-[10px] text-navy-600 mt-1.5 italic">{annotation}</div>}
    </div>
  );
}
