import { ArrowRight } from 'lucide-react';
import { cn } from '../../utils';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { CLIENT_PATHS, depthAtLeast } from './constants';
import { MiniScale } from './charts';

const PATH_SCALES: Record<string, { left: { label: string; value: string; numericValue: number; color: string }; right: { label: string; value: string; numericValue: number; color: string }; ratio: string }> = {
  'path-a': {
    left: { label: 'Direct', value: '€81/t', numericValue: 81, color: 'var(--color-ask)' },
    right: { label: 'Via NIHA', value: '€71-74/t', numericValue: 72.5, color: 'var(--color-success)' },
    ratio: '8-12% savings',
  },
  'path-b': {
    left: { label: 'Domestic', value: '¥97-99/t', numericValue: 98, color: 'var(--color-ask)' },
    right: { label: 'Via NIHA', value: '¥103-106/t', numericValue: 104, color: 'var(--color-success)' },
    ratio: '5-8% better',
  },
  'path-c': {
    left: { label: 'Exchanges', value: '2-4% cost', numericValue: 3, color: 'var(--color-ask)' },
    right: { label: 'Via NIHA', value: '~1% cost', numericValue: 1, color: 'var(--color-success)' },
    ratio: 'Single bilateral swap',
  },
};

const borderColorMap = {
  emerald: 'border-t-emerald-500',
  amber: 'border-t-amber-500',
  blue: 'border-t-blue-500',
} as const;

const badgeColorMap = {
  emerald: 'bg-emerald-500/20 text-emerald-400',
  amber: 'bg-amber-500/20 text-amber-400',
  blue: 'bg-blue-500/20 text-blue-400',
} as const;

export function ClientPathsSection() {
  const { contentDepth } = useIntroducerStore();
  const showAdvanced = depthAtLeast(contentDepth, 'advanced');
  const showExpert = depthAtLeast(contentDepth, 'expert');

  return (
    <div>
      <h4 className="text-sm font-semibold text-navy-300 mb-4">Client Transaction Paths</h4>
      <div className="space-y-4">
        {CLIENT_PATHS.map((path) => (
          <div
            key={path.id}
            className={cn(
              'bg-navy-800/50 border border-navy-700 border-t-2 rounded-xl p-6',
              borderColorMap[path.color]
            )}
          >
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <span className={cn('px-2 py-0.5 rounded text-xs font-semibold', badgeColorMap[path.color])}>
                {path.label}
              </span>
              <span className="text-sm font-medium text-white">{path.title}</span>
            </div>

            {/* Key point */}
            <p className="text-xs text-navy-400 mb-4 italic">{path.keyPoint}</p>

            {/* Mini flow */}
            <div className="flex flex-wrap items-center gap-2 mb-4">
              {path.steps.map((step, i) => (
                <div key={step} className="contents">
                  <span className="text-xs bg-navy-900/50 border border-navy-700 rounded-md px-2 py-1 text-navy-300">
                    {step}
                  </span>
                  {i < path.steps.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-navy-600 flex-shrink-0" />
                  )}
                </div>
              ))}
            </div>

            {/* Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              <div className="bg-navy-900/30 rounded-md p-2 text-navy-500">
                {path.comparison.via}
              </div>
              <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-md p-2 text-emerald-400">
                {path.comparison.niha}
              </div>
            </div>

            {/* Inline scale chart */}
            {PATH_SCALES[path.id] && (
              <MiniScale {...PATH_SCALES[path.id]} />
            )}

            {/* Extended example (advanced) */}
            {showAdvanced && path.extendedExample && (
              <div className="mt-4 bg-navy-900/30 border border-navy-700 rounded-lg p-4">
                <h5 className="text-xs font-semibold text-amber-400 mb-2">{path.extendedExample.title}</h5>
                <ul className="space-y-1">
                  {path.extendedExample.lines.map((line, i) => (
                    <li key={i} className="text-xs text-navy-400 font-mono flex items-start gap-2">
                      <span className="text-navy-600 mt-0.5">-</span>
                      {line}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Detailed comparison (expert) */}
            {showExpert && path.detailedComparison && (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-navy-500">
                      <th className="pb-1 pr-3 font-medium"></th>
                      <th className="pb-1 px-3 font-medium">Via Exchange</th>
                      <th className="pb-1 pl-3 font-medium text-emerald-400">Via NIHA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {path.detailedComparison.rows.map((row) => (
                      <tr key={row.label} className="border-t border-navy-800">
                        <td className="py-1.5 pr-3 text-xs text-navy-400 font-medium">{row.label}</td>
                        <td className="py-1.5 px-3 text-xs text-navy-500 font-mono">{row.exchange}</td>
                        <td className="py-1.5 pl-3 text-xs text-emerald-400 font-mono">{row.niha}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
