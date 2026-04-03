import { useState } from 'react';
import { Search } from 'lucide-react';
import { Tabs } from '../common/Tabs';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { useSection } from './SectionRegistry';
import { AccordionItem } from './AccordionItem';
import { SECTION_IDS, FAQ_CATEGORIES, FAQ_ITEMS, depthAtLeast } from './constants';
import { MiniFlow, MiniCheckGrid, MiniBarChart, MiniScale, MiniTimeline } from './charts';
import { RichText } from './RichText';

function FAQAccordionContent({ id, answer }: { id: string; answer: string }) {
  switch (id) {
    case 'swap-works':
      return (
        <>
          <RichText text={answer} />
          <MiniFlow
            title="The 5-Step Swap Process"
            steps={[
              { label: 'EU client deposits EUR', detail: 'Segregated client account in HK' },
              { label: 'NIHA acquires Chinese credits', detail: 'Via pilot market through GBA access' },
              { label: 'Credits registered through NIHA', detail: 'Institutional market access' },
              { label: 'Swap execution', detail: 'Chinese credits → EUA' },
              { label: 'EUA delivered to client', detail: 'EU registry, T+3–T+5' },
            ]}
          />
        </>
      );
    case 'eu-cant-buy-cea':
      return (
        <>
          <RichText text={answer} />
          <MiniCheckGrid
            title="Access Barriers"
            headers={['National ETS', 'Pilot Markets']}
            rows={[
              {
                label: 'EU Entity',
                values: [
                  { text: 'Closed', status: 'no' },
                  { text: 'No precedent', status: 'no' },
                ],
              },
              {
                label: 'NIHA',
                values: [
                  { text: 'Closed', status: 'no' },
                  { text: 'Authorized', status: 'yes' },
                ],
              },
            ]}
          />
        </>
      );
    case 'replication-barrier':
      return (
        <>
          <RichText text={answer} />
          <MiniBarChart
            title="Barrier Strength (qualitative)"
            bars={[
              { label: 'Regulatory auth.', value: 95, color: 'var(--color-ask)' },
              { label: 'Bilateral relationships', value: 90, color: 'var(--color-ask)' },
              { label: 'Cross-border expertise', value: 80, color: 'var(--color-cea)' },
              { label: 'Execution infrastructure', value: 75, color: 'var(--color-cea)' },
              { label: 'Network effects', value: 85, color: 'var(--color-ask)' },
              { label: 'GBA jurisdiction', value: 95, color: 'var(--color-ask)' },
            ]}
            maxValue={100}
          />
        </>
      );
    case 'detailed-path-examples':
      return (
        <>
          <RichText text={answer} />
          <MiniBarChart
            title="Annual Savings by Path"
            bars={[
              { label: 'Path A (Steel)', value: 1620, displayValue: '€1.62M/yr', color: 'var(--color-success)' },
              { label: 'Path B (Power)', value: 500, displayValue: '¥3M + EUR', color: 'var(--color-cea)' },
              { label: 'Path C (Trader)', value: 200, displayValue: '~3-5% improvement', color: 'var(--color-eua)' },
            ]}
          />
        </>
      );
    case 'business-model':
      return (
        <>
          <RichText text={answer} />
          <MiniScale
            title="Price Comparison"
            left={{ label: 'Direct', value: '€81/t', numericValue: 81, color: 'var(--color-ask)' }}
            right={{ label: 'Via NIHA', value: '€71-74/t', numericValue: 72.5, color: 'var(--color-success)' }}
            ratio="8-12% savings"
          />
        </>
      );
    case 'competitive-moat':
      return (
        <>
          <RichText text={answer} />
          <MiniBarChart
            title="Five Moat Layers"
            bars={[
              { label: 'Geographic', value: 95, color: 'var(--color-success)' },
              { label: 'Regulatory', value: 90, color: 'var(--color-success)' },
              { label: 'Relationship', value: 85, color: 'var(--color-cea)' },
              { label: 'Network', value: 80, color: 'var(--color-cea)' },
              { label: 'First-mover', value: 75, color: 'var(--color-eua)' },
            ]}
            maxValue={100}
          />
        </>
      );
    case 'target-clients':
      return (
        <>
          <RichText text={answer} />
          <MiniBarChart
            title="Client Segments by Priority"
            bars={[
              { label: 'EU Compliance (EUA buyers)', value: 70, displayValue: 'Primary', color: 'var(--color-success)' },
              { label: 'CN Surplus (CEA sellers)', value: 50, displayValue: 'Secondary', color: 'var(--color-cea)' },
              { label: 'Non-EU Swaps (portfolio)', value: 30, displayValue: 'Tertiary', color: 'var(--color-eua)' },
            ]}
            maxValue={100}
          />
        </>
      );
    case 'custody-requirement':
      return (
        <>
          <RichText text={answer} />
          <MiniFlow
            title="Why Custody is Required"
            steps={[
              { label: 'Credits exist in CN registries', detail: 'Institutional access required' },
              { label: 'EU entity cannot open account', detail: 'No government-facilitated pathway available' },
              { label: 'NIHA registers as principal', detail: 'Exclusive GBA access arrangements' },
              { label: 'Beneficial ownership documented', detail: 'HK law bilateral contract' },
            ]}
          />
        </>
      );
    case 'legal-sound':
      return (
        <>
          <RichText text={answer} />
          <MiniCheckGrid
            title="Regulatory Status by Jurisdiction"
            headers={['Status', 'Basis']}
            rows={[
              { label: 'China (Pilot)', values: [{ text: 'Authorized', status: 'yes' as const }, { text: 'Government-facilitated access', status: 'yes' as const }] },
              { label: 'Hong Kong', values: [{ text: 'Not regulated', status: 'yes' as const }, { text: 'Carbon ≠ financial instrument', status: 'yes' as const }] },
              { label: 'EU', values: [{ text: 'Open access', status: 'yes' as const }, { text: 'Established regulatory framework', status: 'yes' as const }] },
            ]}
          />
        </>
      );
    case 'cbam-effect':
      return (
        <>
          <RichText text={answer} />
          <MiniTimeline
            title="CBAM Implementation"
            events={[
              { year: '2023', label: 'CBAM regulation adopted', detail: 'Reporting obligations begin' },
              { year: '2026', label: 'Full CBAM effect', detail: 'Certificates required for imports' },
              { year: '2034', label: 'Free allocation ends', detail: 'Full EUA cost for all installations' },
            ]}
          />
        </>
      );
    case 'why-not-direct':
      return (
        <>
          <RichText text={answer} />
          <MiniScale
            title="500,000 Tonne Order Comparison"
            left={{ label: 'Direct exchange', value: '€40.5M', numericValue: 40.5, color: 'var(--color-ask)' }}
            right={{ label: 'Via NIHA', value: '€36-37M', numericValue: 36.5, color: 'var(--color-success)' }}
            ratio="€4-5M saved"
          />
        </>
      );
    case 'chinese-sell-own':
      return (
        <>
          <RichText text={answer} />
          <MiniScale
            title="CEA Sale: Domestic vs NIHA"
            left={{ label: 'Domestic exchange', value: '¥97-99/t', numericValue: 98, color: 'var(--color-ask)' }}
            right={{ label: 'Via NIHA', value: '¥103-106/t', numericValue: 104, color: 'var(--color-success)' }}
            ratio="5-8% better + EUR"
          />
        </>
      );
    case 'settlement-terms':
      return (
        <>
          <RichText text={answer} />
          <MiniFlow
            title="Settlement Timeline"
            steps={[
              { label: 'Counterparties reserve certificates', detail: 'Pre-trade commitment' },
              { label: 'Trade agreement signed', detail: 'T (trade date)' },
              { label: 'CEA delivered to NIHA', detail: 'T+2 to T+3' },
              { label: 'EUA delivered to client', detail: 'T+3 to T+5' },
            ]}
          />
        </>
      );
    case 'hk-access-china':
      return (
        <>
          <RichText text={answer} />
          <MiniCheckGrid
            title="GBA Access Requirements"
            headers={['Pathway', 'NIHA Status']}
            rows={[
              { label: 'GBA-zone incorporation', values: [{ text: 'Required', status: 'partial' as const }, { text: 'Established', status: 'yes' as const }] },
              { label: 'Cross-border settlement', values: [{ text: 'Required', status: 'partial' as const }, { text: 'Established', status: 'yes' as const }] },
              { label: 'Institutional market access', values: [{ text: 'Required', status: 'partial' as const }, { text: 'Established', status: 'yes' as const }] },
              { label: 'Ongoing compliance', values: [{ text: 'Ongoing', status: 'partial' as const }, { text: 'Active', status: 'yes' as const }] },
            ]}
          />
        </>
      );
    case 'carbon-connect-threat':
      return (
        <>
          <RichText text={answer} />
          <MiniTimeline
            title="Carbon Connect Evolution"
            events={[
              { year: '2024', label: 'GBA Standard Contract', detail: 'Data compliance framework' },
              { year: 'Sep 2025', label: 'Quadripartite MoU', detail: 'HKEX + 3 exchanges' },
              { year: '2026+', label: 'Pilot coordination', detail: 'Cross-boundary settlements' },
              { year: 'Future', label: 'Potential EU access', detail: 'Years away at minimum' },
            ]}
          />
        </>
      );
    case 'eu-hold-cea':
      return (
        <>
          <RichText text={answer} />
          <MiniBarChart
            title="Barriers to EU Entity Holding CEA"
            bars={[
              { label: 'No registry access', value: 95, color: 'var(--color-ask)' },
              { label: 'Settlement requirement', value: 90, color: 'var(--color-ask)' },
              { label: 'MRV compliance burden', value: 70, color: 'var(--color-cea)' },
              { label: 'No precedent exists', value: 95, color: 'var(--color-ask)' },
            ]}
            maxValue={100}
          />
        </>
      );
    default:
      return <RichText text={answer} />;
  }
}

export function FAQSection() {
  const ref = useSection(SECTION_IDS.FAQ);
  const { activeTabs, setActiveTab, contentDepth } = useIntroducerStore();
  const activeCategory = activeTabs['faq'] ?? 'getting-started';
  const [search, setSearch] = useState('');

  const tabs = FAQ_CATEGORIES.map((c) => ({ id: c.id, label: c.label }));

  const filteredItems = FAQ_ITEMS.filter((item) => {
    if (!depthAtLeast(contentDepth, item.depth)) return false;
    const matchesCategory = item.category === activeCategory;
    if (!search.trim()) return matchesCategory;
    const query = search.toLowerCase();
    return matchesCategory && (
      item.question.toLowerCase().includes(query) ||
      item.answer.toLowerCase().includes(query)
    );
  });

  return (
    <section ref={ref} id={SECTION_IDS.FAQ}>
      <h3 className="section-heading text-white mb-4">Frequently Asked Questions</h3>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-navy-500" />
        <input
          type="text"
          placeholder="Search confidential briefing..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-navy-900/50 border border-navy-700 rounded-lg pl-10 pr-3 py-2 text-sm text-white placeholder:text-navy-600 focus:border-emerald-500/50 focus:outline-none"
        />
      </div>

      {/* Category tabs */}
      <Tabs
        tabs={tabs}
        activeTab={activeCategory}
        onChange={(tabId) => setActiveTab('faq', tabId)}
        variant="pills"
        size="sm"
        className="mb-6"
      />

      {/* FAQ items */}
      <div className="space-y-2">
        {filteredItems.length > 0 ? (
          filteredItems.map((item) => (
            <AccordionItem
              key={item.id}
              sectionId="faq"
              itemId={item.id}
              title={item.question}
            >
              <FAQAccordionContent id={item.id} answer={item.answer} />
            </AccordionItem>
          ))
        ) : (
          <div className="text-center py-8 text-navy-500 text-sm">
            No questions match your search.
          </div>
        )}
      </div>
    </section>
  );
}
