import { useSection } from './SectionRegistry';
import { SECTION_IDS } from './constants';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { ToggleGroup } from '../common/ToggleGroup';
import { AnimatedCounter } from '../common/AnimatedCounter';

const DISCOUNT_PRESETS = [
  { value: '8', label: 'Conservative (8%)' },
  { value: '10', label: 'Expected (10%)' },
  { value: '12', label: 'Optimistic (12%)' },
];

function formatEUR(value: number): string {
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value);
}

export function ROICalculator() {
  const ref = useSection(SECTION_IDS.CALCULATOR);
  const { calcInputs, setCalcInput } = useIntroducerStore();

  const directCost = calcInputs.euaVolume * calcInputs.currentEuaPrice;
  const nihaCost = calcInputs.euaVolume * calcInputs.currentEuaPrice * (1 - calcInputs.nihaDiscount / 100);
  const totalSavings = directCost - nihaCost;
  const savingsPerTonne = calcInputs.currentEuaPrice * (calcInputs.nihaDiscount / 100);
  const nihaBarWidth = directCost > 0 ? (nihaCost / directCost) * 100 : 0;

  return (
    <section ref={ref} id={SECTION_IDS.CALCULATOR}>
      <h3 className="section-heading text-white mb-6">ROI Calculator — Estimate Your Savings</h3>

      <div className="bg-navy-800/30 border border-navy-700 rounded-xl p-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* LEFT: Inputs */}
          <div className="space-y-6">
            {/* Volume */}
            <div>
              <label className="text-xs uppercase tracking-wider text-navy-400 block mb-2">
                EUA Volume Needed (tonnes)
              </label>
              <input
                type="range"
                min={1000}
                max={1000000}
                step={1000}
                value={calcInputs.euaVolume}
                onChange={(e) => setCalcInput('euaVolume', Number(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <div className="text-lg font-mono text-white mt-1">
                {calcInputs.euaVolume.toLocaleString('de-DE')} tonnes
              </div>
            </div>

            {/* Price */}
            <div>
              <label className="text-xs uppercase tracking-wider text-navy-400 block mb-2">
                Current EUA Spot Price (€/tonne)
              </label>
              <input
                type="number"
                min={1}
                max={500}
                value={calcInputs.currentEuaPrice}
                onChange={(e) => setCalcInput('currentEuaPrice', Number(e.target.value))}
                className="bg-navy-900/50 border border-navy-700 rounded-lg px-3 py-2 text-white font-mono w-full focus:border-emerald-500/50 focus:outline-none"
              />
            </div>

            {/* Discount */}
            <div>
              <label className="text-xs uppercase tracking-wider text-navy-400 block mb-2">
                Estimated NIHA Discount ({calcInputs.nihaDiscount}%)
              </label>
              <input
                type="range"
                min={5}
                max={15}
                step={0.5}
                value={calcInputs.nihaDiscount}
                onChange={(e) => setCalcInput('nihaDiscount', Number(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <div className="mt-2">
                <ToggleGroup
                  options={DISCOUNT_PRESETS}
                  value={String(calcInputs.nihaDiscount)}
                  onChange={(v) => setCalcInput('nihaDiscount', Number(v))}
                  size="sm"
                  fullWidth
                />
              </div>
            </div>
          </div>

          {/* RIGHT: Results */}
          <div className="space-y-6">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-navy-400">Direct EUA Purchase</span>
                <span className="text-lg text-navy-300 font-mono">{formatEUR(directCost)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-navy-400">Via NIHA</span>
                <span className="text-lg text-navy-300 font-mono">{formatEUR(nihaCost)}</span>
              </div>
              <div className="border-t border-navy-700 pt-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-semibold text-white">Your Total Savings</span>
                  <AnimatedCounter
                    value={totalSavings}
                    prefix="€"
                    className="text-3xl font-bold text-emerald-400"
                  />
                </div>
                <div className="flex justify-between items-center mt-1">
                  <span className="text-xs text-navy-500">Savings Per Tonne</span>
                  <span className="text-lg text-emerald-400 font-mono">€{savingsPerTonne.toFixed(2)}/t</span>
                </div>
              </div>
            </div>

            {/* Visual bar comparison */}
            <div className="space-y-2">
              <div className="relative w-full bg-navy-700 h-10 rounded-lg overflow-hidden">
                <div className="absolute inset-0 flex items-center px-3">
                  <span className="text-xs text-navy-300">Direct Purchase — {formatEUR(directCost)}</span>
                </div>
              </div>
              <div
                className="relative h-10 rounded-lg overflow-hidden border border-emerald-500/30 bg-gradient-to-r from-emerald-500/15 to-emerald-500/30"
                style={{ width: `${Math.max(nihaBarWidth, 20)}%` }}
              >
                <div className="absolute inset-0 flex items-center px-3">
                  <span className="text-xs text-emerald-300 whitespace-nowrap">Via NIHA — {formatEUR(nihaCost)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
