import { cn } from '../../utils';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { AccordionItem } from './AccordionItem';
import { MiniScale, MiniBarChart, MiniFlow, MiniTimeline, MiniCheckGrid } from './charts';
import { RichText } from './RichText';
import {
  TIMING_CATALYSTS,
  CONVERGENCE_TABLE,
  RISK_MITIGATIONS,
  depthAtLeast,
} from './constants';

function ConvergenceChart() {
  const data = [
    { year: '2024', eua: 67, cea: 12 },
    { year: '2025', eua: 74, cea: 10 },
    { year: '2026', eua: 81, cea: 11 },
    { year: '2027', eua: 90, cea: 14 },
    { year: '2028', eua: 100, cea: 17 },
    { year: '2029', eua: 113, cea: 21 },
    { year: '2030', eua: 126, cea: 25 },
  ];
  const maxY = 140;
  const w = 280, h = 100, padL = 30, padR = 10, padT = 10, padB = 20;
  const chartW = w - padL - padR;
  const chartH = h - padT - padB;

  const toX = (i: number) => padL + (i / (data.length - 1)) * chartW;
  const toY = (val: number) => padT + chartH - (val / maxY) * chartH;

  const euaLine = data.map((d, i) => `${toX(i)},${toY(d.eua)}`).join(' ');
  const ceaLine = data.map((d, i) => `${toX(i)},${toY(d.cea)}`).join(' ');
  // Fill area between the two lines
  const areaPoints = [
    ...data.map((d, i) => `${toX(i)},${toY(d.eua)}`),
    ...data.map((_d, i) => `${toX(data.length - 1 - i)},${toY(data[data.length - 1 - i].cea)}`),
  ].join(' ');

  return (
    <div className="mb-4">
      <div className="text-[10px] uppercase tracking-wider text-navy-500 mb-2">Price Convergence Forecast (€/tonne)</div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxHeight: 160 }}>
        {/* Grid lines */}
        {[0, 50, 100].map((v) => (
          <g key={v}>
            <line x1={padL} y1={toY(v)} x2={w - padR} y2={toY(v)} stroke="var(--color-border)" strokeWidth={0.5} strokeDasharray="2,2" />
            <text x={padL - 4} y={toY(v) + 3} textAnchor="end" className="text-[7px] fill-navy-600">€{v}</text>
          </g>
        ))}
        {/* Area between lines */}
        <polygon points={areaPoints} fill="var(--color-success)" opacity={0.08} />
        {/* EUA line */}
        <polyline points={euaLine} fill="none" stroke="var(--color-eua)" strokeWidth={1.5} />
        {/* CEA line */}
        <polyline points={ceaLine} fill="none" stroke="var(--color-cea)" strokeWidth={1.5} />
        {/* Data points + year labels */}
        {data.map((d, i) => (
          <g key={d.year}>
            <circle cx={toX(i)} cy={toY(d.eua)} r={2} fill="var(--color-eua)" />
            <circle cx={toX(i)} cy={toY(d.cea)} r={2} fill="var(--color-cea)" />
            <text x={toX(i)} y={h - 4} textAnchor="middle" className="text-[7px] fill-navy-500">{d.year}</text>
          </g>
        ))}
        {/* Peak marker at 2026 */}
        <text x={toX(2)} y={toY(81) - 6} textAnchor="middle" className="text-[7px] fill-emerald-400 font-semibold">★ Peak</text>
      </svg>
      <div className="flex items-center gap-4 mt-1">
        <div className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-400 inline-block" /><span className="text-[9px] text-navy-500">EUA</span></div>
        <div className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block" /><span className="text-[9px] text-navy-500">CEA</span></div>
        <div className="flex items-center gap-1"><span className="w-3 h-1.5 bg-emerald-400/20 inline-block rounded-sm" /><span className="text-[9px] text-navy-500">NIHA opportunity zone</span></div>
      </div>
    </div>
  );
}

function RiskAccordionContent({ id, mitigation }: { id: string; mitigation: string }) {
  switch (id) {
    case 'reg-risk':
      return (
        <>
          <RichText text={mitigation} />
          <MiniCheckGrid
            title="Pathway Legitimacy"
            headers={['Status']}
            rows={[
              { label: 'Cross-border Authorization', values: [{ text: 'Government-facilitated', status: 'yes' as const }] },
              { label: 'Institutional Market Access', values: [{ text: 'Established via GBA', status: 'yes' as const }] },
              { label: 'Settlement Capability', values: [{ text: 'Bilateral clearing active', status: 'yes' as const }] },
              { label: 'Grey-area exploitation', values: [{ text: 'None — legal pathways only', status: 'yes' as const }] },
            ]}
          />
        </>
      );
    case 'cpty-risk':
      return (
        <>
          <RichText text={mitigation} />
          <MiniFlow
            title="Risk Mitigation Chain"
            steps={[
              { label: 'Client Fund Protection', detail: 'Segregated from operations' },
              { label: 'Staged Settlement', detail: 'Partial deliveries reduce exposure' },
              { label: 'Institutional Custody', detail: 'Government-facilitated registry access' },
            ]}
          />
        </>
      );
    case 'fx-risk':
      return (
        <>
          <RichText text={mitigation} />
          <MiniScale
            title="FX Exposure Window"
            left={{ label: 'Exchange T+2', value: '48h exposed', numericValue: 48, color: 'var(--color-ask)' }}
            right={{ label: 'NIHA bilateral', value: 'Price locked T+0', numericValue: 1, color: 'var(--color-success)' }}
          />
        </>
      );
    case 'convergence-risk':
      return (
        <>
          <RichText text={mitigation} />
          <MiniBarChart
            title="Price Gap Compression"
            horizontal={false}
            bars={[
              { label: '2026', value: 10, displayValue: '7-10×', color: 'var(--color-cea)' },
              { label: '2028', value: 6, displayValue: '~6×', color: 'var(--color-cea)' },
              { label: '2030', value: 5, displayValue: '~5×', color: 'var(--color-text-muted)' },
            ]}
            annotation="Savings remain material in EUR terms even as ratio compresses"
          />
        </>
      );
    case 'carbon-connect-risk':
      return (
        <>
          <RichText text={mitigation} />
          <MiniTimeline
            title="Carbon Connect Timeline"
            events={[
              { year: '2025', label: 'MoU signed', detail: 'Pilot phase begins' },
              { year: '2026-27', label: 'Trial period', detail: 'Voluntary credits only' },
              { year: '2028+', label: 'Potential expansion', detail: 'Direct access years away', color: 'var(--color-text-muted)' },
            ]}
          />
        </>
      );
    case 'liquidity-risk':
      return (
        <>
          <RichText text={mitigation} />
          <MiniBarChart
            title="Supply Pool Growth"
            bars={[
              { label: 'Power 2021', value: 2200, color: 'var(--color-eua)' },
              { label: '+Steel/Cement 2024', value: 800, color: 'var(--color-cea)' },
              { label: '+Aluminium 2025', value: 500, color: 'var(--color-success)' },
            ]}
            annotation="Growing entity count = growing CEA supply"
          />
        </>
      );
    default:
      return (
        <>
          <span className="text-emerald-400/80">Mitigation:</span> {mitigation}
        </>
      );
  }
}

export function TimingSection() {
  const { contentDepth } = useIntroducerStore();
  const showAdvanced = depthAtLeast(contentDepth, 'advanced');
  const visibleRisks = RISK_MITIGATIONS.filter((r) => depthAtLeast(contentDepth, r.depth));

  return (
    <div>
      <h4 className="text-sm font-semibold text-navy-300 mb-4">Why 2026 Is the Optimal Entry Point</h4>

      {/* Catalyst cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {TIMING_CATALYSTS.map((catalyst) => (
          <div key={catalyst.title} className="bg-navy-800/50 border border-navy-700 rounded-lg p-4">
            <div className="text-xs text-emerald-400 font-semibold mb-1">{catalyst.year}</div>
            <div className="text-sm font-medium text-white mb-1">{catalyst.title}</div>
            <div className="text-xs text-navy-500">{catalyst.description}</div>
            {showAdvanced && catalyst.extendedContent && (
              <div className="text-xs text-navy-500 mt-2 border-t border-navy-700 pt-2 leading-relaxed">
                {catalyst.extendedContent}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Convergence table */}
      <div className="bg-navy-800/30 border border-navy-700 rounded-xl p-4 mb-6">
        <ConvergenceChart />
        <h5 className="text-xs uppercase tracking-wider text-navy-400 mb-3">Price Convergence Forecast</h5>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-navy-500">
                <th className="pb-2 pr-3 font-medium">Year</th>
                <th className="pb-2 px-3 font-medium">EUA (€/t)</th>
                <th className="pb-2 px-3 font-medium">CEA (€ equiv.)</th>
                <th className="pb-2 px-3 font-medium">Ratio</th>
                <th className="pb-2 pl-3 font-medium">Opportunity</th>
              </tr>
            </thead>
            <tbody>
              {CONVERGENCE_TABLE.map((row) => (
                <tr
                  key={row.year}
                  className={cn(
                    'border-t border-navy-800',
                    row.opportunity.includes('★') && 'bg-emerald-500/5'
                  )}
                >
                  <td className="py-2 pr-3 text-sm text-navy-300 font-medium">{row.year}</td>
                  <td className="py-2 px-3 text-sm text-navy-400 font-mono">{row.eua}</td>
                  <td className="py-2 px-3 text-sm text-navy-400 font-mono">{row.cea}</td>
                  <td className="py-2 px-3 text-sm text-amber-400 font-mono">{row.ratio}</td>
                  <td className={cn(
                    'py-2 pl-3 text-sm font-medium',
                    row.opportunity.includes('★') ? 'text-emerald-400' : 'text-navy-500'
                  )}>
                    {row.opportunity}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Risks & Mitigations */}
      <h5 className="text-xs uppercase tracking-wider text-navy-400 mb-3">Risks & Mitigations</h5>
      <div className="space-y-2">
        {visibleRisks.map((item) => (
          <AccordionItem key={item.id} sectionId="timing" itemId={item.id} title={`${item.risk}: ${item.description}`}>
            <RiskAccordionContent id={item.id} mitigation={item.mitigation} />
          </AccordionItem>
        ))}
      </div>
    </div>
  );
}
