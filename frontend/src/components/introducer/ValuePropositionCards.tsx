import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { VALUE_PROPOSITIONS, depthAtLeast } from './constants';
import { MiniScale, MiniBarChart } from './charts';

const iconBgMap = {
  emerald: 'bg-emerald-500/20',
  amber: 'bg-amber-500/20',
  blue: 'bg-blue-500/20',
} as const;

const iconTextMap = {
  emerald: 'text-emerald-400',
  amber: 'text-amber-400',
  blue: 'text-blue-400',
} as const;

export function ValuePropositionCards() {
  const { contentDepth } = useIntroducerStore();
  const visibleProps = VALUE_PROPOSITIONS.filter((p) => depthAtLeast(contentDepth, p.depth));
  const showExtended = depthAtLeast(contentDepth, 'advanced');

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {visibleProps.map((prop) => (
        <div
          key={prop.title}
          className="bg-navy-800/50 border border-navy-700 rounded-xl p-6 flex items-start gap-4"
        >
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${iconBgMap[prop.color]}`}>
            <span className={`text-lg font-bold ${iconTextMap[prop.color]}`}>
              {prop.title.charAt(0)}
            </span>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">{prop.title}</div>
            <div className="text-xs text-navy-400 mt-1 leading-relaxed">
              {prop.description}
            </div>
            {showExtended && prop.extendedDescription && (
              <div className="text-xs text-navy-500 mt-2 leading-relaxed border-t border-navy-700 pt-2">
                {prop.extendedDescription}
              </div>
            )}
            {showExtended && prop.title === '8–12% Cost Savings' && (
              <MiniScale
                left={{ label: 'Direct', value: '€81/t', numericValue: 81, color: 'var(--color-ask)' }}
                right={{ label: 'NIHA', value: '€71-74/t', numericValue: 72.5, color: 'var(--color-success)' }}
              />
            )}
            {showExtended && prop.title === 'Zero Market Impact' && (
              <MiniBarChart
                title="Order Visibility"
                bars={[
                  { label: 'Exchange', value: 100, displayValue: 'Visible on orderbook', color: 'var(--color-ask)' },
                  { label: 'NIHA OTC', value: 0, displayValue: 'Zero visibility', color: 'var(--color-success)' },
                ]}
                maxValue={100}
              />
            )}
            {showExtended && prop.title === 'Faster Settlement' && (
              <MiniScale
                left={{ label: 'Multi-leg exchange', value: '5-10 days', numericValue: 10, color: 'var(--color-ask)' }}
                right={{ label: 'NIHA bilateral', value: 'T+2–T+5', numericValue: 3.5, color: 'var(--color-success)' }}
              />
            )}
            {showExtended && prop.title === 'Regulatory Moat' && (
              <MiniBarChart
                title="Barrier Layers"
                bars={[
                  { label: 'Regulatory', value: 95, color: 'var(--color-success)' },
                  { label: 'Geographic', value: 90, color: 'var(--color-success)' },
                  { label: 'Network', value: 80, color: 'var(--color-cea)' },
                  { label: 'First-mover', value: 75, color: 'var(--color-eua)' },
                ]}
                maxValue={100}
              />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
