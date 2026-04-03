import { cn } from '../../utils';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { useSection } from './SectionRegistry';
import {
  SECTION_IDS,
  LEGAL_SUMMARY_CARDS,
  NIHA_AUTHORIZATION_CHAIN,
  LEGAL_ACCORDIONS,
  depthAtLeast,
} from './constants';
import { AccordionItem } from './AccordionItem';
import { MiniScale, MiniCheckGrid, MiniFlow, MiniTimeline, MiniBarChart } from './charts';
import { RichText } from './RichText';

function LegalAccordionContent({ id, content }: { id: string; content: string }) {
  switch (id) {
    case 'national-vs-pilot':
      return (
        <>
          <RichText text={content} />
          <MiniScale
            title="Market Access Comparison"
            left={{ label: 'National', value: 'Closed to all foreign', numericValue: 0, color: 'var(--color-ask)' }}
            right={{ label: 'Pilot', value: 'Authorized institutional investors', numericValue: 70, color: 'var(--color-cea)' }}
            ratio="Two different systems"
          />
        </>
      );
    case 'eu-barriers':
      return (
        <>
          <RichText text={content} />
          <MiniCheckGrid
            title="Access Feasibility"
            headers={['National ETS', 'Pilot Markets']}
            rows={[
              { label: 'EU Entity', values: [{ text: 'Closed by law', status: 'no' }, { text: 'No precedent', status: 'no' }] },
              { label: 'HK Entity', values: [{ text: 'Closed by law', status: 'no' }, { text: 'Months of setup', status: 'partial' }] },
              { label: 'NIHA (GBA)', values: [{ text: 'Closed by law', status: 'no' }, { text: 'Authorized', status: 'yes' }] },
            ]}
          />
        </>
      );
    case 'why-hk':
      return (
        <>
          <RichText text={content} />
          <MiniCheckGrid
            title="Jurisdiction Comparison"
            headers={['Hong Kong', 'Singapore', 'Dubai', 'London']}
            rows={[
              { label: 'GBA Zone', values: [{ text: 'Yes', status: 'yes' }, { text: 'No', status: 'no' }, { text: 'No', status: 'no' }, { text: 'No', status: 'no' }] },
              { label: 'Cross-border Settlement', values: [{ text: 'Established', status: 'yes' }, { text: 'Difficult', status: 'partial' }, { text: 'None', status: 'no' }, { text: 'CNH only', status: 'partial' }] },
              { label: 'Pilot Market Access', values: [{ text: 'Established', status: 'yes' }, { text: 'Possible', status: 'partial' }, { text: 'No linkage', status: 'no' }, { text: 'No GBA status', status: 'no' }] },
              { label: 'EU ETS Access', values: [{ text: 'Yes', status: 'yes' }, { text: 'Yes', status: 'yes' }, { text: 'Yes', status: 'yes' }, { text: 'Yes (post-Brexit separate)', status: 'partial' }] },
            ]}
          />
        </>
      );
    case 'niha-authorizations':
      return (
        <>
          <RichText text={content} />
          <MiniFlow
            title="Required Authorization Chain"
            steps={[
              { label: 'Cross-border Trading Authorization', detail: 'Government-facilitated carbon trading pathway', color: 'var(--color-success)' },
              { label: 'Institutional Pilot Market Access', detail: 'Authorized participant via GBA framework', color: 'var(--color-success)' },
              { label: 'Cross-border Settlement', detail: 'RMB/EUR bilateral clearing channels', color: 'var(--color-eua)' },
              { label: 'Data Governance Compliance', detail: 'GBA regulatory framework', color: 'var(--color-eua)' },
              { label: 'EUA Delivery Capability', detail: 'European carbon market access', color: 'var(--color-cea)' },
            ]}
          />
        </>
      );
    case 'transaction-architecture':
      return (
        <>
          <RichText text={content} />
          <MiniFlow
            title="5-Step Custody Flow"
            steps={[
              { label: 'Client deposits EUR', detail: 'Segregated client account, HK law', color: 'var(--color-eua)' },
              { label: 'NIHA acquires Chinese credits', detail: 'Via pilot market through GBA access', color: 'var(--color-cea)' },
              { label: 'Credits registered through NIHA', detail: 'Institutional access (principal)', color: 'var(--color-cea)' },
              { label: 'Swap execution', detail: 'Chinese credits → EUA conversion', color: 'var(--color-success)' },
              { label: 'EUA delivered to client', detail: 'EU registry, T+3–T+5', color: 'var(--color-success)' },
            ]}
          />
        </>
      );
    case 'carbon-connect':
      return (
        <>
          <RichText text={content} />
          <MiniTimeline
            title="Carbon Connect Evolution"
            events={[
              { year: '2024', label: 'GBA carbon cooperation announced', detail: 'Policy framework established' },
              { year: 'Sep 2025', label: 'Quadripartite MoU signed', detail: 'HKEX + 3 pilot exchanges', highlight: true },
              { year: '2025-26', label: 'Trial phase begins', detail: 'Voluntary credits & pilot coordination' },
              { year: '2027+', label: 'Potential expansion', detail: 'Direct access years away', color: 'var(--color-text-muted)' },
            ]}
          />
        </>
      );
    case 'jurisdictions':
      return (
        <>
          <RichText text={content} />
          <MiniCheckGrid
            title="Why Not Other Jurisdictions?"
            headers={['HK', 'Singapore', 'Dubai', 'London']}
            rows={[
              { label: 'GBA Access', values: [{ text: 'Yes', status: 'yes' }, { text: 'No', status: 'no' }, { text: 'No', status: 'no' }, { text: 'No', status: 'no' }] },
              { label: 'China Carbon', values: [{ text: 'Pilot markets', status: 'yes' }, { text: 'Ginga precedent', status: 'partial' }, { text: 'None', status: 'no' }, { text: 'Blocked', status: 'no' }] },
              { label: 'EUR Banking', values: [{ text: 'Yes', status: 'yes' }, { text: 'Yes', status: 'yes' }, { text: 'Limited', status: 'partial' }, { text: 'Yes', status: 'yes' }] },
              { label: 'Time Zone', values: [{ text: '+0h from SZ', status: 'yes' }, { text: '+0h', status: 'yes' }, { text: '+4h', status: 'partial' }, { text: '+7h', status: 'no' }] },
            ]}
          />
        </>
      );
    case 'why-principal':
      return (
        <>
          <RichText text={content} />
          <MiniCheckGrid
            title="Broker vs Principal Model"
            headers={['Broker Model', 'Principal Model (NIHA)']}
            rows={[
              { label: 'EU holds CEA?', values: [{ text: 'Cannot — no registry', status: 'no' }, { text: 'NIHA holds as principal', status: 'yes' }] },
              { label: 'CN delivers EUA?', values: [{ text: 'Cannot — no EU registry', status: 'no' }, { text: 'NIHA delivers', status: 'yes' }] },
              { label: 'Direct transaction?', values: [{ text: 'Impossible across regimes', status: 'no' }, { text: 'Two bilateral trades', status: 'yes' }] },
              { label: 'Legal certainty', values: [{ text: 'Undefined counterparty', status: 'no' }, { text: 'HK common law governs', status: 'yes' }] },
            ]}
          />
        </>
      );
    case 'custody-legal':
      return (
        <>
          <RichText text={content} />
          <MiniFlow
            title="Legal Basis per Step"
            steps={[
              { label: 'EUR Deposit → Segregated Account', detail: 'HK law client fund protection + bank segregation' },
              { label: 'Carbon Acquisition → Principal', detail: 'Government-facilitated GBA access framework' },
              { label: 'Custody → Registry', detail: 'Prime brokerage model — legal title with NIHA' },
              { label: 'Swap → Physical delivery', detail: 'Not derivative under MiFID II; not SFO Schedule 5' },
              { label: 'EUA Delivery → EU Registry', detail: 'European carbon market framework' },
            ]}
          />
        </>
      );
    case 'authorization-detail':
      return (
        <>
          <RichText text={content} />
          <MiniFlow
            title="Five Jurisdictions"
            steps={[
              { label: 'China — Trading Authorization', detail: 'Government-facilitated carbon access', color: 'var(--color-ask)' },
              { label: 'China — Institutional Access', detail: 'Authorized participant on pilot exchanges', color: 'var(--color-ask)' },
              { label: 'China — Settlement', detail: 'Cross-border clearing channels', color: 'var(--color-cea)' },
              { label: 'China — Data Governance', detail: 'GBA compliance framework', color: 'var(--color-cea)' },
              { label: 'EU — Carbon Market Access', detail: 'European allowance participation', color: 'var(--color-eua)' },
              { label: 'Hong Kong — Regulatory Position', detail: 'Carbon not classified as financial instrument', color: 'var(--color-success)' },
            ]}
          />
        </>
      );
    case 'citations':
      return (
        <>
          <RichText text={content} />
          <MiniBarChart
            title="Regulatory Citations by Jurisdiction"
            bars={[
              { label: 'China (National ETS)', value: 3, displayValue: '3 refs', color: 'var(--color-ask)' },
              { label: 'China (Pilot Markets)', value: 4, displayValue: '4 refs', color: 'var(--color-cea)' },
              { label: 'China (Banking/Data)', value: 3, displayValue: '3 refs', color: 'var(--color-cea)' },
              { label: 'EU ETS / CBAM', value: 4, displayValue: '4 refs', color: 'var(--color-eua)' },
              { label: 'GBA / HK', value: 3, displayValue: '3 refs', color: 'var(--color-success)' },
            ]}
          />
        </>
      );
    default:
      return <RichText text={content} />;
  }
}

const STATUS_COLORS = {
  red: { bg: 'border-red-500/30', text: 'text-red-400' },
  amber: { bg: 'border-amber-500/30', text: 'text-amber-400' },
  emerald: { bg: 'border-emerald-500/30', text: 'text-emerald-400' },
} as const;

export function LegalSection() {
  const ref = useSection(SECTION_IDS.LEGAL);
  const { contentDepth } = useIntroducerStore();
  const visibleAccordions = LEGAL_ACCORDIONS.filter((a) => depthAtLeast(contentDepth, a.depth));

  return (
    <section ref={ref} id={SECTION_IDS.LEGAL}>
      <h3 className="section-heading text-white mb-4">Legal & Regulatory Framework</h3>

      {/* Three-lock summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        {LEGAL_SUMMARY_CARDS.map((card) => {
          const colors = STATUS_COLORS[card.statusColor];
          return (
            <div
              key={card.label}
              className={cn(
                'bg-navy-800/50 border rounded-lg p-4',
                colors.bg,
              )}
            >
              <div className={cn('text-lg font-semibold mb-1', colors.text)}>
                {card.status}
              </div>
              <div className="text-xs font-medium text-navy-300 mb-1">{card.label}</div>
              <div className="text-xs text-navy-500 leading-relaxed">{card.description}</div>
            </div>
          );
        })}
      </div>

      {/* Authorization chain */}
      <div className="bg-navy-800/30 border border-navy-700 rounded-xl p-4 mb-6">
        <div className="text-xs uppercase tracking-wider text-navy-400 mb-3">
          NIHA Authorization Chain — Required Approvals
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {NIHA_AUTHORIZATION_CHAIN.map((item, i) => (
            <div key={item.step} className="flex items-center gap-2">
              <div className="bg-navy-700/80 border border-navy-600 rounded-lg px-3 py-1.5 text-center min-w-[90px]">
                <div className="text-xs font-mono font-semibold text-emerald-400">{item.step}</div>
                <div className="text-[10px] text-navy-400 leading-tight mt-0.5">{item.label}</div>
              </div>
              {i < NIHA_AUTHORIZATION_CHAIN.length - 1 && (
                <span className="text-navy-600 text-xs">→</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Accordion items */}
      <div className="space-y-2">
        {visibleAccordions.map((item) => (
          <AccordionItem key={item.id} sectionId="legal" itemId={item.id} title={item.title}>
            <LegalAccordionContent id={item.id} content={item.content} />
          </AccordionItem>
        ))}
      </div>
    </section>
  );
}
