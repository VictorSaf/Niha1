import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield,
  Leaf,
  Wallet,
  Globe,
  FileCheck,
  ChevronRight,
  ChevronLeft,
  CheckCircle,
  Loader2,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { onboardingApi } from '../../services/api';
import { getApiErrorMessage } from '../../utils/errors';
import type {
  KYCFormDataResponse,
  KYCFormDataUpdate,
  PEPDeclarationItem,
} from '../../types';

// ── Step definitions ──
const STEPS = [
  { id: 1, title: 'PEP & Compliance', icon: Shield, description: 'Politically Exposed Person declarations' },
  { id: 2, title: 'Carbon Experience', icon: Leaf, description: 'Market experience & investment profile' },
  { id: 3, title: 'Source of Funds', icon: Wallet, description: 'Funding sources & expected activity' },
  { id: 4, title: 'Tax Status', icon: Globe, description: 'Tax residency & reporting' },
  { id: 5, title: 'Declarations', icon: FileCheck, description: 'Legal declarations & acceptance' },
];

const DECLARATION_KEYS = [
  'info_true', 'no_sanctions', 'no_investigation', 'lawful_funds',
  'notify_changes', 'niha_principal', 'risk_disclosure', 'ongoing_dd', 'right_to_decline',
] as const;

const DECLARATIONS: Record<string, string> = {
  info_true: 'All information provided in this application is true, complete, and accurate in all material respects.',
  no_sanctions: 'The Applicant Entity is not subject to any sanctions imposed by the United Nations, the European Union, the United States, the United Kingdom, or Hong Kong SAR.',
  no_investigation: 'The Applicant Entity is not under investigation and has not been convicted of any offence relating to money laundering, terrorist financing, fraud, tax evasion, or any other financial crime.',
  lawful_funds: 'The funds to be used in connection with carbon credit transactions originate from lawful sources and do not represent the proceeds of any criminal activity.',
  notify_changes: 'The Applicant Entity shall promptly notify NIHA of any material change to the information provided in this application.',
  niha_principal: 'The Applicant Entity acknowledges that NIHA operates as a principal counterparty in carbon credit transactions and is not acting as broker, agent, trustee, or investment adviser.',
  risk_disclosure: 'The Applicant Entity acknowledges that it has received, read, and understood the Risk Disclosure Statement provided by NIHA.',
  ongoing_dd: 'The Applicant Entity consents to NIHA conducting ongoing due diligence, including enhanced checks on transactions and beneficial ownership structures.',
  right_to_decline: 'The Applicant Entity acknowledges that NIHA reserves the right to decline this application or terminate the business relationship at any time.',
};

interface KycFormWizardProps {
  onComplete: () => void;
  onStepChange?: (step: number, totalSteps: number) => void;
}

export default function KycFormWizard({ onComplete, onStepChange }: KycFormWizardProps) {
  const [, setFormData] = useState<KYCFormDataResponse | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local form state
  const [pepDeclarations, setPepDeclarations] = useState<PEPDeclarationItem[]>([
    { name: '', role: 'director', is_pep: false },
  ]);
  const [hasCarbonExperience, setHasCarbonExperience] = useState<boolean | null>(null);
  const [carbonExperienceYears, setCarbonExperienceYears] = useState('');
  const [carbonCreditsTraded, setCarbonCreditsTraded] = useState<string[]>([]);
  const [investmentObjectives, setInvestmentObjectives] = useState<string[]>([]);
  const [riskAppetite, setRiskAppetite] = useState('');
  const [sourceOfFunds, setSourceOfFunds] = useState<string[]>([]);
  const [expectedAnnualVolume, setExpectedAnnualVolume] = useState('');
  const [intendedUseDescription, setIntendedUseDescription] = useState('');
  const [taxResidencyCountry, setTaxResidencyCountry] = useState('');
  const [subjectToCrs, setSubjectToCrs] = useState<boolean | null>(null);
  const [declarationsAccepted, setDeclarationsAccepted] = useState<string[]>([]);

  // Load existing form data
  useEffect(() => {
    loadFormData();
  }, []);

  useEffect(() => {
    onStepChange?.(currentStep, STEPS.length);
  }, [currentStep, onStepChange]);

  const loadFormData = async () => {
    setLoading(true);
    try {
      const data = await onboardingApi.getFormData();
      setFormData(data);
      // Populate local state from saved data
      if (data.pepDeclarations?.length) setPepDeclarations(data.pepDeclarations);
      if (data.hasCarbonExperience !== undefined && data.hasCarbonExperience !== null) setHasCarbonExperience(data.hasCarbonExperience);
      if (data.carbonExperienceYears) setCarbonExperienceYears(data.carbonExperienceYears);
      if (data.carbonCreditsTraded?.length) setCarbonCreditsTraded(data.carbonCreditsTraded);
      if (data.investmentObjectives?.length) setInvestmentObjectives(data.investmentObjectives);
      if (data.riskAppetite) setRiskAppetite(data.riskAppetite);
      if (data.sourceOfFunds?.length) setSourceOfFunds(data.sourceOfFunds);
      if (data.expectedAnnualVolume) setExpectedAnnualVolume(data.expectedAnnualVolume);
      if (data.intendedUseDescription) setIntendedUseDescription(data.intendedUseDescription);
      if (data.taxResidencyCountry) setTaxResidencyCountry(data.taxResidencyCountry);
      if (data.subjectToCrs !== undefined && data.subjectToCrs !== null) setSubjectToCrs(data.subjectToCrs);
      if (data.declarationsAccepted?.length) setDeclarationsAccepted(data.declarationsAccepted as string[]);
      const step = data.currentStep ?? data.current_step;
      if (step != null && step > 1) setCurrentStep(step);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const saveCurrentStep = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      const update: KYCFormDataUpdate = { current_step: currentStep };

      if (currentStep === 1) {
        update.pep_declarations = pepDeclarations.filter(p => p.name.trim() !== '');
      } else if (currentStep === 2) {
        update.has_carbon_experience = hasCarbonExperience ?? false;
        update.carbon_experience_years = carbonExperienceYears || undefined;
        update.carbon_credits_traded = carbonCreditsTraded;
        update.investment_objectives = investmentObjectives;
        update.risk_appetite = riskAppetite || undefined;
      } else if (currentStep === 3) {
        update.source_of_funds = sourceOfFunds;
        update.expected_annual_volume = expectedAnnualVolume || undefined;
        update.intended_use_description = intendedUseDescription || undefined;
      } else if (currentStep === 4) {
        update.tax_residency_country = taxResidencyCountry || undefined;
        update.subject_to_crs = subjectToCrs ?? undefined;
      } else if (currentStep === 5) {
        update.declarations_accepted = declarationsAccepted;
      }

      await onboardingApi.saveFormData(update);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [currentStep, pepDeclarations, hasCarbonExperience, carbonExperienceYears, carbonCreditsTraded, investmentObjectives, riskAppetite, sourceOfFunds, expectedAnnualVolume, intendedUseDescription, taxResidencyCountry, subjectToCrs, declarationsAccepted]);

  const handleNext = async () => {
    await saveCurrentStep();
    if (currentStep < STEPS.length) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(prev => prev - 1);
  };

  const handleFinish = async () => {
    await saveCurrentStep();
    onComplete();
  };

  // ── Toggle helpers ──
  const toggleArrayItem = (arr: string[], item: string, setter: (v: string[]) => void) => {
    setter(arr.includes(item) ? arr.filter(i => i !== item) : [...arr, item]);
  };

  const addPepPerson = () => {
    setPepDeclarations(prev => [...prev, { name: '', role: 'director', is_pep: false }]);
  };

  const updatePepPerson = (index: number, field: keyof PEPDeclarationItem, value: string | boolean) => {
    setPepDeclarations(prev => prev.map((p, i) => i === index ? { ...p, [field]: value } : p));
  };

  const removePepPerson = (index: number) => {
    if (pepDeclarations.length > 1) {
      setPepDeclarations(prev => prev.filter((_, i) => i !== index));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Step indicator */}
      <div className="flex items-center justify-between mb-8 px-2">
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const isActive = currentStep === step.id;
          const isCompleted = currentStep > step.id;
          return (
            <div key={step.id} className="flex items-center">
              <button
                onClick={() => isCompleted && setCurrentStep(step.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-all ${
                  isActive
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : isCompleted
                    ? 'bg-emerald-900/20 text-emerald-500 cursor-pointer'
                    : 'text-navy-500'
                }`}
              >
                {isCompleted ? (
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                ) : (
                  <Icon className="w-5 h-5" />
                )}
                <span className="text-sm font-medium hidden lg:inline">{step.title}</span>
              </button>
              {i < STEPS.length - 1 && (
                <ChevronRight className={`w-4 h-4 mx-1 ${isCompleted ? 'text-emerald-600' : 'text-navy-600'}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded-lg flex items-center gap-2 bg-red-500/10 text-red-400 border border-red-500/20">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Step content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
          className="bg-navy-800 rounded-2xl border border-navy-700 p-6"
        >
          <h3 className="text-xl font-bold text-white mb-1">
            {STEPS[currentStep - 1].title}
          </h3>
          <p className="text-navy-400 text-sm mb-6">
            {STEPS[currentStep - 1].description}
          </p>

          {/* Step 1 — PEP Declarations */}
          {currentStep === 1 && (
            <div className="space-y-4">
              <p className="text-sm text-navy-300">
                Please declare whether any directors, officers, or ultimate beneficial owners
                of your entity are Politically Exposed Persons (PEPs).
              </p>
              {pepDeclarations.map((person, i) => (
                <div key={i} className="p-4 rounded-xl bg-navy-700/50 border border-navy-600 space-y-3">
                  <div className="flex items-center gap-3">
                    <input
                      type="text"
                      placeholder="Full name"
                      value={person.name}
                      onChange={e => updatePepPerson(i, 'name', e.target.value)}
                      className="flex-1 px-3 py-2 rounded-lg bg-navy-900 border border-navy-600 text-white text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                    />
                    <select
                      value={person.role}
                      onChange={e => updatePepPerson(i, 'role', e.target.value)}
                      className="select-arrow-spaced"
                    >
                      <option value="director">Director / Officer</option>
                      <option value="ubo">Beneficial Owner</option>
                    </select>
                    {pepDeclarations.length > 1 && (
                      <button
                        onClick={() => removePepPerson(i)}
                        className="p-2 rounded-lg hover:bg-navy-600 text-red-400"
                      >×</button>
                    )}
                  </div>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={person.is_pep}
                      onChange={e => updatePepPerson(i, 'is_pep', e.target.checked)}
                      className="w-4 h-4 rounded border-navy-500 text-emerald-500 focus:ring-emerald-500 bg-navy-900"
                    />
                    <span className="text-sm text-navy-200">
                      This person is a Politically Exposed Person (PEP)
                    </span>
                  </label>
                </div>
              ))}
              <button
                onClick={addPepPerson}
                className="w-full py-2 rounded-lg border-2 border-dashed border-navy-600 text-navy-400 hover:border-emerald-500 hover:text-emerald-400 transition-colors text-sm"
              >
                + Add another person
              </button>
            </div>
          )}

          {/* Step 2 — Carbon Market Experience */}
          {currentStep === 2 && (
            <div className="space-y-5">
              {/* Experience */}
              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">
                  Do you have prior carbon credit trading experience?
                </label>
                <div className="flex gap-3">
                  {[true, false].map(val => (
                    <button
                      key={String(val)}
                      onClick={() => setHasCarbonExperience(val)}
                      className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${
                        hasCarbonExperience === val
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500'
                          : 'bg-navy-700 text-navy-300 border border-navy-600 hover:border-navy-500'
                      }`}
                    >{val ? 'Yes' : 'No'}</button>
                  ))}
                </div>
              </div>

              {hasCarbonExperience && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-navy-200 mb-2">Years of experience</label>
                    <select
                      value={carbonExperienceYears}
                      onChange={e => setCarbonExperienceYears(e.target.value)}
                      className="w-full form-select"
                    >
                      <option value="">Select</option>
                      <option value="1-2">1–2 years</option>
                      <option value="3-5">3–5 years</option>
                      <option value="5-10">5–10 years</option>
                      <option value="10+">10+ years</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-navy-200 mb-2">Types of carbon credits traded</label>
                    <div className="flex flex-wrap gap-2">
                      {['EUA', 'CER', 'VER/VCU', 'CEA', 'Other'].map(type => (
                        <button
                          key={type}
                          onClick={() => toggleArrayItem(carbonCreditsTraded, type, setCarbonCreditsTraded)}
                          className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                            carbonCreditsTraded.includes(type)
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500'
                              : 'bg-navy-700 text-navy-300 border border-navy-600'
                          }`}
                        >{type}</button>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Investment Objectives */}
              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">Investment Objectives</label>
                <div className="space-y-2">
                  {[
                    { key: 'compliance', label: 'Compliance obligation fulfilment (EU ETS / China ETS)' },
                    { key: 'diversification', label: 'Portfolio diversification into carbon assets' },
                    { key: 'trading', label: 'Speculative trading / market-making' },
                    { key: 'offsetting', label: 'Voluntary carbon offsetting (ESG / CSR)' },
                    { key: 'arbitrage', label: 'Cross-border CEA–EUA conversion arbitrage' },
                    { key: 'accumulation', label: 'Long-term carbon credit accumulation' },
                  ].map(obj => (
                    <label key={obj.key} className="flex items-center gap-3 cursor-pointer p-2 rounded-lg hover:bg-navy-700/50">
                      <input
                        type="checkbox"
                        checked={investmentObjectives.includes(obj.key)}
                        onChange={() => toggleArrayItem(investmentObjectives, obj.key, setInvestmentObjectives)}
                        className="w-4 h-4 rounded border-navy-500 text-emerald-500 focus:ring-emerald-500 bg-navy-900"
                      />
                      <span className="text-sm text-navy-200">{obj.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Risk Appetite */}
              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">Risk Appetite</label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { key: 'conservative', label: 'Conservative', desc: 'Capital preservation priority' },
                    { key: 'moderate', label: 'Moderate', desc: 'Balanced risk/return' },
                    { key: 'aggressive', label: 'Aggressive', desc: 'High return priority' },
                  ].map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => setRiskAppetite(opt.key)}
                      className={`p-3 rounded-xl text-center transition-all border ${
                        riskAppetite === opt.key
                          ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400'
                          : 'bg-navy-700 border-navy-600 text-navy-300 hover:border-navy-500'
                      }`}
                    >
                      <div className="font-medium text-sm">{opt.label}</div>
                      <div className="text-xs mt-1 opacity-70">{opt.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 3 — Source of Funds */}
          {currentStep === 3 && (
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">Source of Funds</label>
                <p className="text-xs text-navy-400 mb-3">
                  Select all that apply to the funds intended for carbon credit transactions.
                </p>
                <div className="space-y-2">
                  {[
                    { key: 'operating_revenue', label: 'Operating revenue / Business profits' },
                    { key: 'investment_returns', label: 'Investment returns / Capital gains' },
                    { key: 'shareholder_capital', label: 'Shareholder capital contribution' },
                    { key: 'bank_loan', label: 'Bank loan / Credit facility' },
                    { key: 'government_grant', label: 'Government grant / Subsidy' },
                    { key: 'other', label: 'Other' },
                  ].map(src => (
                    <label key={src.key} className="flex items-center gap-3 cursor-pointer p-2 rounded-lg hover:bg-navy-700/50">
                      <input
                        type="checkbox"
                        checked={sourceOfFunds.includes(src.key)}
                        onChange={() => toggleArrayItem(sourceOfFunds, src.key, setSourceOfFunds)}
                        className="w-4 h-4 rounded border-navy-500 text-emerald-500 focus:ring-emerald-500 bg-navy-900"
                      />
                      <span className="text-sm text-navy-200">{src.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">
                  Expected Annual Transaction Volume
                </label>
                <select
                  value={expectedAnnualVolume}
                  onChange={e => setExpectedAnnualVolume(e.target.value)}
                  className="w-full form-select"
                >
                  <option value="">Select range</option>
                  <option value="<100K">Less than €100,000</option>
                  <option value="100K-500K">€100,000 – €500,000</option>
                  <option value="500K-1M">€500,000 – €1,000,000</option>
                  <option value="1M-5M">€1,000,000 – €5,000,000</option>
                  <option value=">5M">More than €5,000,000</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">
                  Intended Use of Carbon Credit Services
                </label>
                <p className="text-xs text-navy-400 mb-2">
                  Brief description of your company&apos;s intended use and commercial rationale.
                </p>
                <textarea
                  value={intendedUseDescription}
                  onChange={e => setIntendedUseDescription(e.target.value)}
                  placeholder="e.g., Our company intends to acquire EUA carbon credits for EU ETS compliance..."
                  className="w-full px-3 py-2 rounded-lg bg-navy-900 border border-navy-600 text-white text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  rows={3}
                />
              </div>
            </div>
          )}

          {/* Step 4 — Tax Status */}
          {currentStep === 4 && (
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">
                  Country of Tax Residency
                </label>
                <input
                  type="text"
                  value={taxResidencyCountry}
                  onChange={e => setTaxResidencyCountry(e.target.value)}
                  placeholder="e.g., Germany, United Kingdom, Hong Kong"
                  className="w-full px-3 py-2 rounded-lg bg-navy-900 border border-navy-600 text-white text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-navy-200 mb-2">
                  Is the entity subject to CRS/AEOI reporting?
                </label>
                <p className="text-xs text-navy-400 mb-3">
                  Common Reporting Standard / Automatic Exchange of Information
                </p>
                <div className="flex gap-3">
                  {[
                    { val: true, label: 'Yes' },
                    { val: false, label: 'No' },
                  ].map(opt => (
                    <button
                      key={String(opt.val)}
                      onClick={() => setSubjectToCrs(opt.val)}
                      className={`px-6 py-2 rounded-lg text-sm font-medium transition-all ${
                        subjectToCrs === opt.val
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500'
                          : 'bg-navy-700 text-navy-300 border border-navy-600 hover:border-navy-500'
                      }`}
                    >{opt.label}</button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 5 — Declarations */}
          {currentStep === 5 && (
            <div className="space-y-4">
              <p className="text-sm text-navy-300 mb-4">
                The undersigned, being duly authorised to act on behalf of the Applicant
                Entity, hereby declares and undertakes as follows:
              </p>
              {DECLARATION_KEYS.map((key, i) => (
                <label
                  key={key}
                  className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all border ${
                    declarationsAccepted.includes(key)
                      ? 'bg-emerald-900/20 border-emerald-800'
                      : 'bg-navy-700/50 border-navy-600 hover:border-navy-500'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={declarationsAccepted.includes(key)}
                    onChange={e => {
                      if (e.target.checked) {
                        setDeclarationsAccepted(prev => [...prev, key]);
                      } else {
                        setDeclarationsAccepted(prev => prev.filter(k => k !== key));
                      }
                    }}
                    className="w-4 h-4 mt-0.5 rounded border-navy-500 text-emerald-500 focus:ring-emerald-500 bg-navy-900 flex-shrink-0"
                  />
                  <span className="text-sm text-navy-200 leading-relaxed">
                    <span className="text-navy-400 font-medium mr-1">{i + 1}.</span>
                    {DECLARATIONS[key]}
                    {key === 'risk_disclosure' && (
                      <a
                        href="/api/v1/documents/download/risk_disclosure"
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="inline-flex items-center gap-1 ml-2 text-blue-400 hover:text-blue-300 underline underline-offset-2"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        View Document
                      </a>
                    )}
                  </span>
                </label>
              ))}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-6">
        <button
          onClick={handleBack}
          disabled={currentStep === 1}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            currentStep === 1
              ? 'text-navy-600 cursor-not-allowed'
              : 'text-navy-300 hover:bg-navy-700'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>

        <div className="flex items-center gap-3">
          {saving && <Loader2 className="w-4 h-4 animate-spin text-navy-400" />}
          {currentStep < STEPS.length ? (
            <button
              onClick={handleNext}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-br from-emerald-500 to-blue-600 hover:from-emerald-400 hover:to-blue-500 transition-all"
            >
              Save & Continue
              <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={saving || declarationsAccepted.length < DECLARATION_KEYS.length}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all ${
                declarationsAccepted.length >= DECLARATION_KEYS.length
                  ? 'bg-gradient-to-br from-emerald-500 to-blue-600 hover:from-emerald-400 hover:to-blue-500'
                  : 'bg-navy-600 cursor-not-allowed opacity-50'
              }`}
            >
              <CheckCircle className="w-4 h-4" />
              Complete KYC Form
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
