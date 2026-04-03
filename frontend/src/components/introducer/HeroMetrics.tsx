import { motion, useReducedMotion } from 'framer-motion';
import { useAuthStore } from '../../stores/useStore';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { useSection } from './SectionRegistry';
import { SECTION_IDS, HERO_METRICS, OVERVIEW_NARRATIVES, depthAtLeast } from './constants';
import { MiniScale, MiniBarChart } from './charts';

const colorMap = {
  emerald: 'text-emerald-400',
  amber: 'text-amber-400',
  blue: 'text-blue-400',
} as const;

function NarrativeContent({ id, content }: { id: string; content: string }) {
  switch (id) {
    case 'core-thesis':
      return (
        <>
          <p className="text-sm text-navy-300 leading-relaxed">{content}</p>
          <MiniScale
            title="The Price Gap"
            left={{ label: 'EU EUA', value: '€81/t', numericValue: 81, color: 'var(--color-eua)' }}
            right={{ label: 'China CEA', value: '~€11/t', numericValue: 11, color: 'var(--color-cea)' }}
            ratio="7-10× gap"
          />
        </>
      );
    case 'what-this-means':
      return (
        <>
          <p className="text-sm text-navy-300 leading-relaxed">{content}</p>
          <MiniBarChart
            title="OTC as % of EU ETS Volume"
            bars={[
              { label: 'Exchange-traded', value: 75, displayValue: '75-85%', color: 'var(--color-eua)' },
              { label: 'OTC / broker', value: 25, displayValue: '15-25%', color: 'var(--color-success)' },
            ]}
            annotation="OTC segment = NIHA's primary target market"
          />
        </>
      );
    case 'otc-opportunity':
      return (
        <>
          <p className="text-sm text-navy-300 leading-relaxed">{content}</p>
          <MiniScale
            title="Daily Volume Comparison"
            left={{ label: 'EU ETS', value: '€3B+', numericValue: 3000, color: 'var(--color-eua)' }}
            right={{ label: 'China ETS', value: '€9.5M', numericValue: 9.5, color: 'var(--color-cea)' }}
            ratio="316× difference"
          />
        </>
      );
    default:
      return <p className="text-sm text-navy-300 leading-relaxed">{content}</p>;
  }
}

export function HeroMetrics() {
  const ref = useSection(SECTION_IDS.OVERVIEW);
  const { user } = useAuthStore();
  const { contentDepth } = useIntroducerStore();
  const name = user?.firstName ?? user?.email ?? 'User';
  const prefersReduced = useReducedMotion();

  const visibleMetrics = HERO_METRICS.filter((m) => depthAtLeast(contentDepth, m.depth));
  const visibleNarratives = OVERVIEW_NARRATIVES.filter((n) => depthAtLeast(contentDepth, n.depth));

  return (
    <section ref={ref} id={SECTION_IDS.OVERVIEW}>
      <div className="mb-8">
        <h2 className="text-2xl font-light text-white tracking-wide">
          Welcome back, {name}
        </h2>
        <p className="text-navy-400 text-sm mt-1">
          Your gateway to carbon market opportunities
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {visibleMetrics.map((metric, i) => (
          <motion.div
            key={metric.label}
            initial={prefersReduced ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05, ease: 'easeOut' }}
            className="bg-navy-800/50 border border-navy-700 rounded-xl p-6"
          >
            <div className={`text-3xl font-bold font-mono ${colorMap[metric.color]}`}>
              {metric.value}
            </div>
            <div className="text-xs uppercase tracking-wider text-navy-400 mt-2">
              {metric.label}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Narrative sections */}
      {visibleNarratives.length > 0 && (
        <div className="mt-6 space-y-4">
          {visibleNarratives.map((narrative) => (
            <div
              key={narrative.id}
              className="bg-navy-800/30 border border-navy-700 rounded-xl p-5"
            >
              <h4 className="text-sm font-semibold text-emerald-400 mb-2">{narrative.title}</h4>
              <NarrativeContent id={narrative.id} content={narrative.content} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
