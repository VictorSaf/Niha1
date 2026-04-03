import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import {
  Bot,
  Database,
  Globe,
  RefreshCw,
  Play,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Plus,
  Trash2,
  Mail,
  Save,
  DollarSign,
  Send,
  ExternalLink,
  Pencil,
  MoreHorizontal,
  TrendingUp,
  FileText,
} from 'lucide-react';
import { Button, Card, Badge, AlertBanner, NumberInput, PageLoadingState } from '../components/common';
import { BackofficeLayout } from '../components/layout';
import { AIAgentTab } from '../components/settings/AIAgentTab';
import { DocumentsTab } from '../components/settings/DocumentsTab';
import { adminApi, exchangeRatesApi } from '../services/api';
import { getApiErrorMessage } from '../utils/errors';
import { TREND_COLORS } from '../constants/chartColors';
import type { ChartPoint, ScrapingSource, ScrapeLibrary, ExchangeRateSource, MailSettings, MailSettingsUpdate } from '../types';

interface ActionItem {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  loading?: boolean;
  danger?: boolean;
  separator?: boolean;
}

function ActionsDropdown({ actions }: { actions: ActionItem[] }) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0, openAbove: true });

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  const handleOpen = () => {
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      const menuHeight = actions.length * 30 + 8; // approximate: 30px per item + padding
      const spaceAbove = rect.top;
      const spaceBelow = window.innerHeight - rect.bottom;
      const openAbove = spaceAbove > menuHeight || spaceAbove > spaceBelow;
      setPos({
        top: openAbove ? rect.top - 4 : rect.bottom + 4,
        left: Math.min(rect.right - 144, window.innerWidth - 152), // 144 = w-36, 8px margin
        openAbove,
      });
    }
    setOpen(o => !o);
  };

  const menu = open && createPortal(
    <>
      <div className="fixed inset-0 z-[9998] backdrop-blur-sm bg-black/10" onClick={() => setOpen(false)} />
      <div
        ref={menuRef}
        className="fixed w-36 bg-navy-800 border border-navy-600 rounded-lg shadow-xl z-[9999] py-1"
        style={{
          top: pos.top,
          left: pos.left,
          transform: pos.openAbove ? 'translateY(-100%)' : undefined,
        }}
      >
        {actions.map((a, i) => (
          <div key={i}>
            {a.separator && <div className="border-t border-navy-600 my-1" />}
            <button
              onClick={() => { a.onClick(); setOpen(false); }}
              disabled={a.loading}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs transition-colors
                ${a.danger
                  ? 'text-red-400 hover:bg-red-900/30 hover:text-red-300'
                  : 'text-navy-200 hover:bg-navy-700 hover:text-white'}
                ${a.loading ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              {a.loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : a.icon}
              {a.label}
            </button>
          </div>
        ))}
      </div>
    </>,
    document.body
  );

  return (
    <>
      <button
        ref={btnRef}
        onClick={handleOpen}
        className="p-1.5 rounded hover:bg-navy-700 transition-colors text-navy-400 hover:text-white"
        aria-label="Actions"
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>
      {menu}
    </>
  );
}

// ============================================================================
// Price History Chart (SVG)
// ============================================================================

function PriceHistoryChart({ sourceName, currency, points, onReset }: {
  sourceName: string; currency: string; points: ChartPoint[]; onReset?: () => void;
}) {
  const [hover, setHover] = useState<{ x: number; y: number; point: ChartPoint } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  if (points.length < 2) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2 text-xs text-navy-400">
          <TrendingUp className="w-3.5 h-3.5" />
          <span className="font-medium text-navy-200">{sourceName}</span>
          <span>— Not enough data points</span>
        </div>
      </Card>
    );
  }

  const W = 600, H = 140, PX = 40, PY = 16;
  const prices = points.map(p => p.price);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const range = maxP - minP || 1;

  const toX = (i: number) => PX + (i / (points.length - 1)) * (W - PX * 2);
  const toY = (p: number) => PY + (1 - (p - minP) / range) * (H - PY * 2);

  const pathD = points.map((pt, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(pt.price).toFixed(1)}`).join(' ');
  const areaD = pathD + ` L${toX(points.length - 1).toFixed(1)},${(H - PY).toFixed(1)} L${PX.toFixed(1)},${(H - PY).toFixed(1)} Z`;

  // Y-axis labels (3 ticks)
  const yTicks = [minP, minP + range / 2, maxP];

  // X-axis labels (first, mid, last)
  const xIndices = [0, Math.floor(points.length / 2), points.length - 1];
  const fmtTime = (iso: string) => {
    const d = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
    return d.toLocaleString('en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * W;
    const idx = Math.round(((mouseX - PX) / (W - PX * 2)) * (points.length - 1));
    if (idx >= 0 && idx < points.length) {
      setHover({ x: toX(idx), y: toY(points[idx].price), point: points[idx] });
    }
  };

  // Color: green if last >= first, red if down
  const trending = prices[prices.length - 1] >= prices[0];
  const lineColor = trending ? TREND_COLORS.up : TREND_COLORS.down;
  const fillColor = trending ? TREND_COLORS.upFill : TREND_COLORS.downFill;

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className={`w-3.5 h-3.5 ${trending ? 'text-emerald-400' : 'text-red-400'}`} />
        <span className="text-xs font-medium text-navy-200">{sourceName}</span>
        <span className="text-[10px] text-navy-500">{currency}</span>
        <span className="ml-auto text-[10px] text-navy-500">{points.length} pts</span>
        {onReset && (
          <button
            onClick={onReset}
            className="ml-2 px-2 py-0.5 rounded text-[10px] font-medium bg-navy-700 text-navy-300 hover:bg-red-500/20 hover:text-red-400 transition-colors"
            title="Reset chart — delete all history and start fresh from current price"
          >
            Reset
          </button>
        )}
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-36"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
      >
        {/* Grid lines */}
        {yTicks.map((t, i) => (
          <line key={i} x1={PX} x2={W - PX} y1={toY(t)} y2={toY(t)}
            stroke="currentColor" className="text-navy-700" strokeWidth="0.5" strokeDasharray="4 2" />
        ))}

        {/* Area fill */}
        <path d={areaD} fill={fillColor} />

        {/* Line */}
        <path d={pathD} fill="none" stroke={lineColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />

        {/* Y-axis labels */}
        {yTicks.map((t, i) => (
          <text key={i} x={PX - 4} y={toY(t) + 3} textAnchor="end" className="fill-navy-400" fontSize="9">{t.toFixed(2)}</text>
        ))}

        {/* X-axis labels */}
        {xIndices.map((idx) => (
          <text key={idx} x={toX(idx)} y={H - 2} textAnchor="middle" className="fill-navy-400" fontSize="8">{fmtTime(points[idx].recordedAt)}</text>
        ))}

        {/* Hover crosshair + tooltip */}
        {hover && (
          <>
            <line x1={hover.x} x2={hover.x} y1={PY} y2={H - PY} stroke={lineColor} strokeWidth="0.5" opacity="0.5" />
            <circle cx={hover.x} cy={hover.y} r="3" fill={lineColor} />
            <rect x={hover.x - 45} y={hover.y - 28} width="90" height="20" rx="4"
              className="fill-navy-700" opacity="0.9" />
            <text x={hover.x} y={hover.y - 15} textAnchor="middle" className="fill-white" fontSize="9" fontWeight="600">
              {hover.point.price.toFixed(4)} {currency}
            </text>
          </>
        )}
      </svg>
    </Card>
  );
}

const SCRAPE_LIBRARY_OPTIONS: { value: ScrapeLibrary; label: string }[] = [
  { value: 'HTTPX', label: 'HTTPX' },
  { value: 'BEAUTIFULSOUP', label: 'BS4' },
  { value: 'SELENIUM', label: 'Selenium' },
  { value: 'PLAYWRIGHT', label: 'Playwright' },
];
const SCRAPE_INTERVAL_OPTIONS: { value: number; label: string }[] = [
  { value: 5, label: '5m' },
  { value: 10, label: '10m' },
  { value: 15, label: '15m' },
  { value: 30, label: '30m' },
  { value: 60, label: '1h' },
];

/** Preset for Trading Economics EU Carbon Permits (feature 0041). Uses href-anchored XPath for robustness. */
const TRADING_ECONOMICS_EUA_PRESET = {
  name: 'Trading Economics EUA',
  url: 'https://tradingeconomics.com/commodity/carbon',
  certificate_type: 'EUA' as const,
  scrape_library: 'HTTPX' as ScrapeLibrary,
  scrape_interval_minutes: 5,
  xpath_selector:
    "//a[@href='/commodity/carbon']/ancestor::tr/td[@id='p']",
};

type SettingsTab = 'server' | 'scraping' | 'exchange' | 'mail' | 'documents' | 'ai-agent';
const SETTINGS_TABS: { key: SettingsTab; label: string; icon: typeof Database }[] = [
  { key: 'server', label: 'Server', icon: Globe },
  { key: 'scraping', label: 'Price Scraping', icon: Database },
  { key: 'exchange', label: 'Exchange Rate', icon: DollarSign },
  { key: 'mail', label: 'Mail Settings', icon: Mail },
  { key: 'documents', label: 'Documents', icon: FileText },
  { key: 'ai-agent', label: 'AI Agent', icon: Bot },
];

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('scraping');
  const [sources, setSources] = useState<ScrapingSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingSource, setTestingSource] = useState<string | null>(null);
  const [refreshingSource, setRefreshingSource] = useState<string | null>(null);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ sourceId: string; price?: number; success: boolean } | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newSource, setNewSource] = useState({
    name: '',
    url: '',
    certificate_type: 'EUA' as 'EUA' | 'CEA',
    scrape_library: 'HTTPX' as ScrapeLibrary,
    scrape_interval_minutes: 5,
    xpath_selector: '',
  });

  // Price Scraping edit state
  const [editingSource, setEditingSource] = useState<ScrapingSource | null>(null);
  const [editSourceForm, setEditSourceForm] = useState<{
    name: string; url: string; certificate_type: 'EUA' | 'CEA';
    scrape_library: ScrapeLibrary; scrape_interval_minutes: number;
    is_primary: boolean; is_active: boolean;
    xpath_selector: string;
  }>({ name: '', url: '', certificate_type: 'EUA', scrape_library: 'HTTPX', scrape_interval_minutes: 5, is_primary: false, is_active: true, xpath_selector: '' });

  // Price history charts
  const [priceHistories, setPriceHistories] = useState<Record<string, { points: Array<{ price: number; recordedAt: string }>; currency: string }>>({});
  const [historyHours, setHistoryHours] = useState(24);

  // Exchange Rate Sources state
  const [exchangeRateSources, setExchangeRateSources] = useState<ExchangeRateSource[]>([]);
  const [testingExchangeSource, setTestingExchangeSource] = useState<string | null>(null);
  const [refreshingExchangeSource, setRefreshingExchangeSource] = useState<string | null>(null);
  const [deletingExchangeSource, setDeletingExchangeSource] = useState<string | null>(null);
  const [exchangeTestResult, setExchangeTestResult] = useState<{ sourceId: string; rate?: number; success: boolean } | null>(null);
  const [showAddExchangeModal, setShowAddExchangeModal] = useState(false);
  const [editingExchangeSource, setEditingExchangeSource] = useState<ExchangeRateSource | null>(null);
  const [editExchangeForm, setEditExchangeForm] = useState<{
    name: string; url: string; scrape_library: ScrapeLibrary;
    scrape_interval_minutes: number; is_primary: boolean; is_active: boolean;
  }>({ name: '', url: '', scrape_library: 'HTTPX', scrape_interval_minutes: 60, is_primary: false, is_active: true });
  const [newExchangeSource, setNewExchangeSource] = useState({
    name: '',
    from_currency: 'EUR',
    to_currency: 'CNY',
    url: 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml',
    scrape_library: 'HTTPX' as ScrapeLibrary,
    scrape_interval_minutes: 60,
    is_primary: true,
  });

  // Exchange rate history charts
  const [exchangeRateHistories, setExchangeRateHistories] = useState<Record<string, { points: ChartPoint[]; pair: string }>>({});
  const [exchangeRateHistoryHours, setExchangeRateHistoryHours] = useState(24);
  // Aggregated history for long periods (30d/90d/1y) from public API
  const [aggregatedHistory, setAggregatedHistory] = useState<{ points: ChartPoint[]; pair: string } | null>(null);
  const [aggregatedPeriod, setAggregatedPeriod] = useState<string | null>(null);

  // Mail & Auth settings
  const [_mailSettings, setMailSettings] = useState<MailSettings | null>(null);
  const [mailSaving, setMailSaving] = useState(false);
  const [mailSavedSuccess, setMailSavedSuccess] = useState(false);
  const [mailForm, setMailForm] = useState<MailSettingsUpdate & { fromEmail: string }>({
    provider: 'resend',
    useEnvCredentials: true,
    fromEmail: '',
    appBaseUrl: '',
    invitationLinkBaseUrl: '',
    invitationTokenExpiryDays: 7,
  });

  // Test email
  const [testEmail, setTestEmail] = useState('');
  const [testEmailLoading, setTestEmailLoading] = useState(false);
  const [testEmailResult, setTestEmailResult] = useState<{ success: boolean; message: string } | null>(null);

  // Email template preview (used = sent from app code; NU = not used in any flow)
  const [emailTemplates, setEmailTemplates] = useState<{ name: string; used: boolean }[]>([]);
  const [emailTemplatesError, setEmailTemplatesError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [templatePreviewHtml, setTemplatePreviewHtml] = useState('');
  const [templatePreviewLoading, setTemplatePreviewLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- load once on mount

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      setEmailTemplatesError(null);
      const [sourcesData, mailData, exchangeData, templatesResult] = await Promise.all([
        adminApi.getScrapingSources(),
        adminApi.getMailSettings(),
        adminApi.getExchangeRateSources(),
        adminApi.getEmailTemplates()
          .then((data) => ({ data, error: null as string | null }))
          .catch((e) => ({ data: [] as { name: string; used: boolean }[], error: getApiErrorMessage(e) })),
      ]);
      setSources(sourcesData);
      setMailSettings(mailData);
      setExchangeRateSources(exchangeData);
      setEmailTemplates(templatesResult.data);
      if (templatesResult.error) setEmailTemplatesError(templatesResult.error);
      if (templatesResult.data.length > 0) {
        const names = new Set(templatesResult.data.map((t) => t.name));
        if (!selectedTemplate || !names.has(selectedTemplate)) {
          setSelectedTemplate(templatesResult.data[0].name);
        }
      }

      setMailForm({
        provider: mailData.provider,
        useEnvCredentials: mailData.useEnvCredentials,
        fromEmail: mailData.fromEmail ?? '',
        resendApiKey: mailData.resendApiKey ?? undefined,
        smtpHost: mailData.smtpHost ?? undefined,
        smtpPort: mailData.smtpPort ?? undefined,
        smtpUseTls: mailData.smtpUseTls,
        smtpUsername: mailData.smtpUsername ?? undefined,
        smtpPassword: mailData.smtpPassword ?? undefined,
        invitationSubject: mailData.invitationSubject ?? undefined,
        invitationBodyHtml: mailData.invitationBodyHtml ?? undefined,
        invitationLinkBaseUrl: mailData.invitationLinkBaseUrl ?? '',
        appBaseUrl: mailData.appBaseUrl ?? '',
        invitationTokenExpiryDays: mailData.invitationTokenExpiryDays ?? 7,
        verificationMethod: mailData.verificationMethod ?? undefined,
        authMethod: mailData.authMethod ?? undefined,
      });
    } catch (e) {
      console.error('Failed to load settings data:', e);
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const loadHistories = useCallback(async (srcs: ScrapingSource[], hours: number) => {
    const results: Record<string, { points: Array<{ price: number; recordedAt: string }>; currency: string }> = {};
    await Promise.all(
      srcs.map(async (s) => {
        try {
          const data = await adminApi.getScrapingSourceHistory(s.id, hours);
          results[s.id] = { points: data.points, currency: data.currency };
        } catch { /* silent */ }
      })
    );
    setPriceHistories(results);
  }, []);

  // Load price histories when sources load or hours change
  useEffect(() => {
    if (sources.length > 0) loadHistories(sources, historyHours);
  }, [sources, historyHours, loadHistories]);

  // Exchange rate history loader
  const loadExchangeRateHistories = useCallback(async (srcs: ExchangeRateSource[], hours: number) => {
    const results: Record<string, { points: ChartPoint[]; pair: string }> = {};
    await Promise.all(
      srcs.map(async (s) => {
        try {
          const data = await adminApi.getExchangeRateHistory(s.id, hours);
          results[s.id] = {
            points: data.points.map(p => ({ price: p.rate, recordedAt: p.recordedAt })),
            pair: data.pair,
          };
        } catch { /* silent */ }
      })
    );
    setExchangeRateHistories(results);
  }, []);

  useEffect(() => {
    if (exchangeRateSources.length > 0) loadExchangeRateHistories(exchangeRateSources, exchangeRateHistoryHours);
  }, [exchangeRateSources, exchangeRateHistoryHours, loadExchangeRateHistories]);

  const handleResetExchangeRateHistory = async (sourceId: string) => {
    if (!confirm('Reset chart? This deletes all history and starts fresh from the current rate.')) return;
    try {
      await adminApi.resetExchangeRateHistory(sourceId);
      await loadExchangeRateHistories(exchangeRateSources, exchangeRateHistoryHours);
    } catch (e) {
      console.error('Reset exchange rate history failed:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleTestSource = async (sourceId: string) => {
    setTestingSource(sourceId);
    setTestResult(null);
    setError(null);
    try {
      const result = await adminApi.testScrapingSource(sourceId);
      setTestResult({ sourceId, price: result.price, success: result.success });
      if (result.success) setError(null);
      else setError(result.message || 'Test failed.');
    } catch (e) {
      console.error('Test source failed:', e);
      setError(getApiErrorMessage(e));
      setTestResult({ sourceId, success: false });
    } finally {
      setTestingSource(null);
    }
  };

  const handleResetHistory = async (sourceId: string) => {
    if (!confirm('Reset chart? This deletes all history and starts fresh from the current price.')) return;
    try {
      await adminApi.resetScrapingSourceHistory(sourceId);
      await loadHistories(sources, historyHours);
    } catch (e) {
      console.error('Reset history failed:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleRefreshSource = async (sourceId: string) => {
    setRefreshingSource(sourceId);
    setError(null);
    try {
      await adminApi.refreshScrapingSource(sourceId);
      const sourcesData = await adminApi.getScrapingSources();
      setSources(sourcesData);
    } catch (e) {
      console.error('Failed to refresh source:', e);
      setError(getApiErrorMessage(e));
    } finally {
      setRefreshingSource(null);
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    if (!confirm('Are you sure you want to delete this scraping source?')) return;

    setDeletingSource(sourceId);
    setError(null);
    try {
      await adminApi.deleteScrapingSource(sourceId);
      setSources(sources.filter(s => s.id !== sourceId));
    } catch (e) {
      console.error('Failed to delete source:', e);
      setError(getApiErrorMessage(e));
    } finally {
      setDeletingSource(null);
    }
  };

  const handleIntervalChange = async (sourceId: string, interval: number) => {
    setError(null);
    try {
      await adminApi.updateScrapingSource(sourceId, { scrapeIntervalMinutes: interval });
      setSources(sources.map(s =>
        s.id === sourceId
          ? { ...s, scrapeIntervalMinutes: interval }
          : s
      ));
    } catch (e) {
      console.error('Failed to update interval:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleLibraryChange = async (sourceId: string, library: ScrapeLibrary) => {
    setError(null);
    try {
      await adminApi.updateScrapingSource(sourceId, { scrapeLibrary: library });
      setSources(sources.map(s =>
        s.id === sourceId
          ? { ...s, scrapeLibrary: library }
          : s
      ));
    } catch (e) {
      console.error('Failed to update library:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleAddSource = async () => {
    setError(null);
    try {
      const { xpath_selector, ...rest } = newSource;
      const config = xpath_selector?.trim()
        ? { xpath_selector: xpath_selector.trim() }
        : undefined;
      const created = await adminApi.createScrapingSource({ ...rest, config });
      setSources([...sources, created]);
      setShowAddModal(false);
      setNewSource({ name: '', url: '', certificate_type: 'EUA', scrape_library: 'HTTPX', scrape_interval_minutes: 5, xpath_selector: '' });
    } catch (e) {
      console.error('Failed to create source:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleOpenEditSource = (source: ScrapingSource) => {
    setEditingSource(source);
    const cfg = source.config as Record<string, unknown> | undefined;
    setEditSourceForm({
      name: source.name,
      url: source.url,
      certificate_type: source.certificateType as 'EUA' | 'CEA',
      scrape_library: source.scrapeLibrary || 'HTTPX',
      scrape_interval_minutes: source.scrapeIntervalMinutes,
      is_primary: source.isPrimary ?? false,
      is_active: source.isActive,
      xpath_selector: (cfg?.xpath_selector as string) ?? '',
    });
  };

  const handleToggleSourceEnabled = async (source: ScrapingSource) => {
    const newPrimary = !source.isPrimary;
    setError(null);
    try {
      await adminApi.updateScrapingSource(source.id, { isPrimary: newPrimary } as Partial<ScrapingSource>);
      setSources(prev => prev.map(s =>
        s.id === source.id
          ? { ...s, isPrimary: newPrimary }
          : newPrimary && s.certificateType === source.certificateType
            ? { ...s, isPrimary: false }
            : s
      ));
    } catch (e) {
      console.error('Failed to toggle source:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleSaveEditSource = async () => {
    if (!editingSource) return;
    setError(null);
    try {
      const config: Record<string, unknown> = { ...(editingSource.config as Record<string, unknown> || {}) };
      if (editSourceForm.xpath_selector.trim()) {
        config.xpath_selector = editSourceForm.xpath_selector.trim();
      } else {
        delete config.xpath_selector;
      }
      await adminApi.updateScrapingSource(editingSource.id, {
        name: editSourceForm.name,
        url: editSourceForm.url,
        scrapeLibrary: editSourceForm.scrape_library,
        scrapeIntervalMinutes: editSourceForm.scrape_interval_minutes,
        isPrimary: editSourceForm.is_primary,
        isActive: editSourceForm.is_active,
        config,
      } as Partial<ScrapingSource>);
      setSources(prev => prev.map(s =>
        s.id === editingSource.id
          ? {
              ...s,
              name: editSourceForm.name,
              url: editSourceForm.url,
              certificateType: editSourceForm.certificate_type as 'EUA' | 'CEA',
              scrapeLibrary: editSourceForm.scrape_library,
              scrapeIntervalMinutes: editSourceForm.scrape_interval_minutes,
              isPrimary: editSourceForm.is_primary,
              isActive: editSourceForm.is_active,
              config,
            }
          : editSourceForm.is_primary && s.certificateType === editSourceForm.certificate_type
            ? { ...s, isPrimary: false }
            : s
      ));
      setEditingSource(null);
    } catch (e) {
      console.error('Failed to update source:', e);
      setError(getApiErrorMessage(e));
    }
  };

  // Exchange Rate Source handlers
  const handleTestExchangeSource = async (sourceId: string) => {
    setTestingExchangeSource(sourceId);
    setExchangeTestResult(null);
    setError(null);
    try {
      const result = await adminApi.testExchangeRateSource(sourceId);
      setExchangeTestResult({ sourceId, rate: result.rate, success: result.success });
      if (!result.success) setError(result.message || 'Test failed.');
    } catch (e) {
      console.error('Failed to test exchange source:', e);
      setError(getApiErrorMessage(e));
      setExchangeTestResult({ sourceId, success: false });
    } finally {
      setTestingExchangeSource(null);
    }
  };

  const handleRefreshExchangeSource = async (sourceId: string) => {
    setRefreshingExchangeSource(sourceId);
    setError(null);
    try {
      await adminApi.refreshExchangeRateSource(sourceId);
      const exchangeData = await adminApi.getExchangeRateSources();
      setExchangeRateSources(exchangeData);
    } catch (e) {
      console.error('Failed to refresh exchange source:', e);
      setError(getApiErrorMessage(e));
    } finally {
      setRefreshingExchangeSource(null);
    }
  };

  const handleDeleteExchangeSource = async (sourceId: string) => {
    if (!confirm('Are you sure you want to delete this exchange rate source?')) return;

    setDeletingExchangeSource(sourceId);
    setError(null);
    try {
      await adminApi.deleteExchangeRateSource(sourceId);
      setExchangeRateSources(exchangeRateSources.filter(s => s.id !== sourceId));
    } catch (e) {
      console.error('Failed to delete exchange source:', e);
      setError(getApiErrorMessage(e));
    } finally {
      setDeletingExchangeSource(null);
    }
  };

  const handleAddExchangeSource = async () => {
    setError(null);
    try {
      const created = await adminApi.createExchangeRateSource(newExchangeSource);
      setExchangeRateSources([...exchangeRateSources, created]);
      setShowAddExchangeModal(false);
      setNewExchangeSource({
        name: '',
        from_currency: 'EUR',
        to_currency: 'CNY',
        url: 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml',
        scrape_library: 'HTTPX',
        scrape_interval_minutes: 60,
        is_primary: true,
      });
    } catch (e) {
      console.error('Failed to create exchange source:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleOpenEditExchange = (source: ExchangeRateSource) => {
    setEditingExchangeSource(source);
    setEditExchangeForm({
      name: source.name,
      url: source.url,
      scrape_library: source.scrapeLibrary || 'HTTPX',
      scrape_interval_minutes: source.scrapeIntervalMinutes,
      is_primary: source.isPrimary,
      is_active: source.isActive,
    });
  };

  const handleSaveEditExchange = async () => {
    if (!editingExchangeSource) return;
    setError(null);
    try {
      await adminApi.updateExchangeRateSource(editingExchangeSource.id, editExchangeForm);
      setExchangeRateSources(prev => prev.map(s =>
        s.id === editingExchangeSource.id
          ? { ...s, name: editExchangeForm.name, url: editExchangeForm.url, scrapeLibrary: editExchangeForm.scrape_library, scrapeIntervalMinutes: editExchangeForm.scrape_interval_minutes, isPrimary: editExchangeForm.is_primary, isActive: editExchangeForm.is_active }
          : editExchangeForm.is_primary && s.fromCurrency === editingExchangeSource.fromCurrency && s.toCurrency === editingExchangeSource.toCurrency
            ? { ...s, isPrimary: false }
            : s
      ));
      setEditingExchangeSource(null);
    } catch (e) {
      console.error('Failed to update exchange source:', e);
      setError(getApiErrorMessage(e));
    }
  };

  const handleSaveMailSettings = async () => {
    setError(null);
    setMailSaving(true);
    try {
      const payload: MailSettingsUpdate = {
        provider: mailForm.provider,
        useEnvCredentials: mailForm.useEnvCredentials,
        fromEmail: mailForm.fromEmail || undefined,
        resendApiKey: mailForm.resendApiKey && mailForm.resendApiKey !== '********' ? mailForm.resendApiKey : undefined,
        smtpHost: mailForm.smtpHost ?? undefined,
        smtpPort: mailForm.smtpPort ?? undefined,
        smtpUseTls: mailForm.smtpUseTls,
        smtpUsername: mailForm.smtpUsername ?? undefined,
        smtpPassword: mailForm.smtpPassword && mailForm.smtpPassword !== '********' ? mailForm.smtpPassword : undefined,
        invitationSubject: mailForm.invitationSubject ?? undefined,
        invitationBodyHtml: mailForm.invitationBodyHtml ?? undefined,
        invitationLinkBaseUrl: mailForm.invitationLinkBaseUrl || undefined,
        appBaseUrl: mailForm.appBaseUrl || undefined,
        invitationTokenExpiryDays: mailForm.invitationTokenExpiryDays ?? undefined,
        verificationMethod: mailForm.verificationMethod ?? undefined,
        authMethod: mailForm.authMethod ?? undefined,
      };
      await adminApi.updateMailSettings(payload);
      const mailData = await adminApi.getMailSettings();
      setMailSettings(mailData);
      setMailForm({
        provider: mailData.provider,
        useEnvCredentials: mailData.useEnvCredentials,
        fromEmail: mailData.fromEmail ?? '',
        resendApiKey: mailData.resendApiKey ?? undefined,
        smtpHost: mailData.smtpHost ?? undefined,
        smtpPort: mailData.smtpPort ?? undefined,
        smtpUseTls: mailData.smtpUseTls,
        smtpUsername: mailData.smtpUsername ?? undefined,
        smtpPassword: mailData.smtpPassword ?? undefined,
        invitationSubject: mailData.invitationSubject ?? undefined,
        invitationBodyHtml: mailData.invitationBodyHtml ?? undefined,
        invitationLinkBaseUrl: mailData.invitationLinkBaseUrl ?? '',
        appBaseUrl: mailData.appBaseUrl ?? '',
        invitationTokenExpiryDays: mailData.invitationTokenExpiryDays ?? 7,
        verificationMethod: mailData.verificationMethod ?? undefined,
        authMethod: mailData.authMethod ?? undefined,
      });
      setMailSavedSuccess(true);
      setTimeout(() => setMailSavedSuccess(false), 3000);
    } catch (e) {
      console.error('Failed to save mail settings:', e);
      setError(getApiErrorMessage(e));
    } finally {
      setMailSaving(false);
    }
  };

  const handleSendTestEmail = async () => {
    if (!testEmail.trim()) return;
    setTestEmailLoading(true);
    setTestEmailResult(null);
    try {
      const result = await adminApi.sendTestEmail(testEmail.trim());
      setTestEmailResult(result);
    } catch (e) {
      setTestEmailResult({ success: false, message: getApiErrorMessage(e) });
    } finally {
      setTestEmailLoading(false);
    }
  };

  const handlePreviewTemplate = async () => {
    if (!selectedTemplate) return;
    setTemplatePreviewLoading(true);
    setTemplatePreviewHtml('');
    try {
      const html = await adminApi.getEmailTemplatePreview(selectedTemplate);
      setTemplatePreviewHtml(html);
    } catch (e) {
      setTemplatePreviewHtml(`<html><body style="font-family:sans-serif;padding:2rem;color:#ef4444"><h2>Error loading template</h2><p>${getApiErrorMessage(e)}</p></body></html>`); // eslint-disable-line no-restricted-syntax -- HTML string
    } finally {
      setTemplatePreviewLoading(false);
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'timeout':
        return <AlertCircle className="w-4 h-4 text-amber-500" />;
      default:
        return <Clock className="w-4 h-4 text-navy-400" />;
    }
  };

  /** Display label for scrape status (correct spelling: Success, Failed, Timeout). */
  const getStatusLabel = (status?: string) => {
    if (!status) return 'Unknown';
    switch (status.toLowerCase()) {
      case 'success':
        return 'Success';
      case 'failed':
        return 'Failed';
      case 'timeout':
        return 'Timeout';
      default:
        return status;
    }
  };

  const formatTimeAgo = (timestamp?: string) => {
    if (!timestamp) return 'Never';
    // Normalize: append 'Z' if missing to treat naive timestamps as UTC
    const normalized = timestamp.endsWith('Z') || timestamp.includes('+')
      ? timestamp
      : timestamp + 'Z';
    const diff = Date.now() - new Date(normalized).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  if (loading) {
    return (
      <BackofficeLayout>
        <PageLoadingState text="Loading settings..." />
      </BackofficeLayout>
    );
  }

  return (
    <BackofficeLayout
      subSubHeaderLeft={
        <nav className="flex items-center gap-2" aria-label="Settings sections">
          {SETTINGS_TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`subsubheader-nav-btn ${
                activeTab === key
                  ? 'subsubheader-nav-btn-active'
                  : 'subsubheader-nav-btn-inactive'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="whitespace-nowrap">{label}</span>
            </button>
          ))}
        </nav>
      }
    >
      <div>

        {error && (
          <AlertBanner
            variant="error"
            message={error}
            onDismiss={() => setError(null)}
            className="mb-6"
          />
        )}

        <div className="space-y-6">
          {/* Server Settings */}
          {activeTab === 'server' && <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card
              data-testid="server-settings-card"
              className="bg-navy-800/50 border-navy-700"
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Globe className="w-5 h-5 text-emerald-500" />
                  Server URL
                </h2>
                <div className="flex items-center gap-3">
                  {mailSavedSuccess && (
                    <span className="text-sm font-medium text-emerald-400" role="status">
                      Saved
                    </span>
                  )}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSaveMailSettings}
                    loading={mailSaving}
                    icon={<Save className="w-4 h-4" />}
                  >
                    Save
                  </Button>
                </div>
              </div>
              <p className="text-sm text-navy-400 mb-6">
                The base URL where this application is accessible. Used in all generated links —
                invitation emails, NDA setup links, referral URLs, and any other absolute URL
                produced by the server. Change this when deploying to a new host or testing from
                other devices on the local network (e.g.{' '}
                <code className="text-emerald-400 bg-navy-900 px-1 rounded text-xs">http://192.168.10.74:5173</code>).
              </p>
              <div className="max-w-lg">
                <label className="block text-sm font-medium text-navy-300 mb-1">
                  Application URL
                </label>
                <input
                  type="url"
                  value={mailForm.appBaseUrl ?? ''}
                  onChange={(e) => setMailForm({ ...mailForm, appBaseUrl: e.target.value })}
                  className="w-full form-input font-mono"
                  placeholder="http://192.168.10.74:5173"
                  spellCheck={false}
                />
                <p className="mt-2 text-xs text-navy-500">
                  Include the protocol and port. No trailing slash.
                  If empty, falls back to <em>Invitation link base URL</em> in Mail Settings,
                  then to <code className="text-navy-400">http://localhost:5173</code>.
                </p>
              </div>
            </Card>
          </motion.div>}

          {/* Scraping Sources */}
          {activeTab === 'scraping' && <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card
              data-testid="price-scraping-sources-card"
              data-component="PriceScrapingSources"
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Database className="w-5 h-5 text-blue-500" />
                  Price Scraping Sources
                </h2>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setNewSource({ ...TRADING_ECONOMICS_EUA_PRESET });
                      setShowAddModal(true);
                    }}
                    icon={<TrendingUp className="w-4 h-4" />}
                    aria-label="Add Trading Economics EUA preset and open form"
                  >
                    Add Trading Economics EUA
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setNewSource({ name: '', url: '', certificate_type: 'EUA', scrape_library: 'HTTPX', scrape_interval_minutes: 5, xpath_selector: '' });
                      setShowAddModal(true);
                    }}
                    icon={<Plus className="w-4 h-4" />}
                  >
                    Add Source
                  </Button>
                </div>
              </div>

              <div className="w-full overflow-x-auto">
                <table className="w-full table-fixed min-w-[800px]">
                  <thead>
                    <tr className="border-b border-navy-700">
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[26%]">
                        Source
                      </th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[14%]">
                        Library
                      </th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[10%]">
                        Interval
                      </th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[9%]">
                        Last Scrape
                      </th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[17%]">
                        Last Price
                      </th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[8%]">
                        Status
                      </th>
                      <th className="text-center py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[6%]">
                        Enable
                      </th>
                      <th className="text-right py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[5%]">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-700">
                    {sources.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-navy-400">
                          No scraping sources configured. Click &quot;Add Source&quot; to create one.
                        </td>
                      </tr>
                    ) : (
                      sources.map((source) => (
                        <tr key={source.id} className="hover:bg-navy-800/50">
                          <td className="py-2 px-2 align-middle">
                            <div className="min-w-0">
                              <p className="font-medium text-sm text-white flex items-center gap-2.5 flex-wrap">
                                <span className="truncate">{source.name}</span>
                                <Badge variant={source.certificateType === 'EUA' ? 'info' : 'warning'} className="text-[10px] px-1.5 py-0.5 shrink-0">
                                  {source.certificateType}
                                </Badge>
                                {source.isPrimary && (
                                  <Badge variant="success" className="text-[10px] px-1.5 py-0.5">Primary</Badge>
                                )}
                              </p>
                              <p className="text-[10px] text-navy-400 truncate" title={source.url}>
                                {source.url}
                              </p>
                            </div>
                          </td>
                          <td className="py-2 px-2 align-middle">
                            <div className="min-w-0 w-full">
                              <select
                                value={
                                  (() => {
                                    const v = source.scrapeLibrary ?? 'HTTPX';
                                    return SCRAPE_LIBRARY_OPTIONS.some((o) => o.value === v) ? v : 'HTTPX';
                                  })()
                                }
                                onChange={(e) => handleLibraryChange(source.id, e.target.value as ScrapeLibrary)}
                                className="w-full min-w-[6.5rem] form-select text-xs text-white bg-navy-900 pl-2 pr-7"
                                aria-label={`Library for ${source.certificateType} source`}
                              >
                                {SCRAPE_LIBRARY_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </td>
                          <td className="py-2 px-2 align-middle">
                            <div className="min-w-0 w-full">
                              <select
                                value={String(
                                  SCRAPE_INTERVAL_OPTIONS.some((o) => o.value === (source.scrapeIntervalMinutes ?? 5))
                                    ? source.scrapeIntervalMinutes ?? 5
                                    : 5
                                )}
                                onChange={(e) => handleIntervalChange(source.id, parseInt(e.target.value, 10))}
                                className="w-full min-w-[4rem] form-select text-xs text-white bg-navy-900 pl-2 pr-7"
                                aria-label={`Interval for ${source.certificateType} source`}
                              >
                                {SCRAPE_INTERVAL_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={String(opt.value)}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </td>
                          <td className="py-2 px-2 align-middle">
                            <span className="text-xs text-navy-300 whitespace-nowrap">
                              {formatTimeAgo(source.lastScrapeAt)}
                            </span>
                          </td>
                          <td className="py-2 px-2 align-middle min-w-0">
                            {source.lastPrice ? (
                              <div className="flex flex-col">
                                <span className="text-xs font-medium text-emerald-400">
                                  {source.certificateType === 'EUA' ? '€' : '¥'}{source.lastPrice.toFixed(2)}
                                </span>
                                {source.certificateType === 'CEA' && source.lastPriceEur && (
                                  <span className="text-[10px] text-navy-400">
                                    ≈ €{source.lastPriceEur.toFixed(2)}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <span className="text-xs text-navy-400">-</span>
                            )}
                            {testResult?.sourceId === source.id && testResult.price && (
                              <div className="text-[10px] text-blue-500 mt-0.5">
                                Test: {source.certificateType === 'EUA' ? '€' : '¥'}{testResult.price.toFixed(2)}
                              </div>
                            )}
                          </td>
                          <td className="py-2 px-2 align-middle">
                            <div className="flex items-center gap-1 whitespace-nowrap">
                              {getStatusIcon(source.lastScrapeStatus)}
                              <span className="text-[10px] text-navy-300">
                                {getStatusLabel(source.lastScrapeStatus)}
                              </span>
                            </div>
                          </td>
                          <td className="py-2 px-2 align-middle text-center">
                            <input
                              type="checkbox"
                              checked={source.isPrimary}
                              onChange={() => handleToggleSourceEnabled(source)}
                              className="w-4 h-4 rounded border-navy-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                              title={source.isPrimary ? `Enabled for ${source.certificateType}` : `Click to enable for ${source.certificateType}`}
                            />
                          </td>
                          <td className="py-2 px-2 align-middle">
                            <div className="flex justify-end">
                              <ActionsDropdown actions={[
                                { label: 'Edit', icon: <Pencil className="w-3 h-3" />, onClick: () => handleOpenEditSource(source) },
                                { label: 'Test', icon: <Play className="w-3 h-3" />, onClick: () => handleTestSource(source.id), loading: testingSource === source.id },
                                { label: 'Refresh', icon: <RefreshCw className="w-3 h-3" />, onClick: () => handleRefreshSource(source.id), loading: refreshingSource === source.id },
                                { label: 'Delete', icon: <Trash2 className="w-3 h-3" />, onClick: () => handleDeleteSource(source.id), loading: deletingSource === source.id, danger: true, separator: true },
                              ]} />
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* Price History Charts */}
            {sources.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-navy-200 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-blue-500" />
                    Price History
                  </h3>
                  <div className="flex items-center gap-1.5">
                    {([
                      { label: '6h', hours: 6 },
                      { label: '12h', hours: 12 },
                      { label: '1d', hours: 24 },
                      { label: '2d', hours: 48 },
                      { label: '3d', hours: 72 },
                      { label: '7d', hours: 168 },
                      { label: '30d', hours: 720 },
                      { label: '90d', hours: 2160 },
                      { label: '1y', hours: 8760 },
                    ] as const).map(({ label, hours }) => (
                      <button
                        key={label}
                        onClick={() => setHistoryHours(hours)}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                          historyHours === hours
                            ? 'bg-blue-500 text-white'
                            : 'bg-navy-700 text-navy-300 hover:bg-navy-600'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-4">
                  {sources.map(s => (
                    <PriceHistoryChart
                      key={s.id}
                      sourceName={s.name}
                      currency={priceHistories[s.id]?.currency ?? (s.certificateType === 'EUA' ? 'EUR' : 'CNY')}
                      points={priceHistories[s.id]?.points ?? []}
                      onReset={() => handleResetHistory(s.id)}
                    />
                  ))}
                </div>
              </div>
            )}
          </motion.div>}

          {/* Exchange Rate Sources */}
          {activeTab === 'exchange' && <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card data-testid="exchange-rate-sources-card">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <DollarSign className="w-5 h-5 text-emerald-500" />
                  Exchange Rate Sources
                </h2>
                <Button variant="outline" size="sm" onClick={() => setShowAddExchangeModal(true)} icon={<Plus className="w-4 h-4" />}>
                  Add Source
                </Button>
              </div>

              <p className="text-sm text-navy-400 mb-4">
                Configure exchange rate sources for currency conversion. CEA prices are converted from CNY to EUR using scraped rates.
              </p>

              <div className="w-full">
                <table className="w-full table-fixed">
                  <thead>
                    <tr className="border-b border-navy-700">
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[22%]">Source</th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[8%]">Pair</th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[10%]">Method</th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[7%]">Interval</th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[10%]">Last Scrape</th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[8%]">Rate</th>
                      <th className="text-left py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[8%]">Status</th>
                      <th className="text-right py-2 px-2 text-[10px] font-medium text-navy-400 uppercase tracking-wider w-[6%]">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-700">
                    {exchangeRateSources.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-navy-400">
                          No exchange rate sources configured. Click &quot;Add Source&quot; to create one.
                        </td>
                      </tr>
                    ) : (
                      exchangeRateSources.map((source) => (
                        <tr key={source.id} className="hover:bg-navy-800/50">
                          <td className="py-2 px-2">
                            <div className="min-w-0">
                              <p className="font-medium text-sm text-white flex items-center gap-1.5 flex-wrap">
                                <span className="truncate">{source.name}</span>
                                {source.isPrimary && (
                                  <Badge variant="success" className="text-[10px] px-1.5 py-0.5">Primary</Badge>
                                )}
                              </p>
                              <p className="text-[10px] text-navy-400 truncate">{source.url}</p>
                            </div>
                          </td>
                          <td className="py-2 px-2">
                            <Badge variant="info" className="text-[10px] px-1.5 py-0.5">{source.fromCurrency}/{source.toCurrency}</Badge>
                          </td>
                          <td className="py-2 px-2">
                            <span className="text-[10px] font-mono text-navy-300">{source.scrapeLibrary || 'HTTPX'}</span>
                          </td>
                          <td className="py-2 px-2">
                            <span className="text-xs text-navy-300">{source.scrapeIntervalMinutes}m</span>
                          </td>
                          <td className="py-2 px-2">
                            <span className="text-xs text-navy-300">{formatTimeAgo(source.lastScrapedAt)}</span>
                          </td>
                          <td className="py-2 px-2">
                            <div className="flex flex-col">
                              {source.lastRate ? (
                                <span className="text-xs font-medium text-emerald-400">
                                  {source.lastRate.toFixed(4)}
                                </span>
                              ) : (
                                <span className="text-xs text-navy-400">-</span>
                              )}
                              {exchangeTestResult?.sourceId === source.id && exchangeTestResult.rate && (
                                <span className="text-[10px] text-blue-500">Test: {exchangeTestResult.rate.toFixed(4)}</span>
                              )}
                            </div>
                          </td>
                          <td className="py-2 px-2">
                            <div className="flex items-center gap-1">
                              {getStatusIcon(source.lastScrapeStatus)}
                              <span className="text-[10px] text-navy-300">
                                {source.lastScrapeStatus ? getStatusLabel(source.lastScrapeStatus) : 'Pending'}
                              </span>
                            </div>
                          </td>
                          <td className="py-2 px-2">
                            <div className="flex justify-end">
                              <ActionsDropdown actions={[
                                { label: 'Edit', icon: <Pencil className="w-3 h-3" />, onClick: () => handleOpenEditExchange(source) },
                                { label: 'Test', icon: <Play className="w-3 h-3" />, onClick: () => handleTestExchangeSource(source.id), loading: testingExchangeSource === source.id },
                                { label: 'Refresh', icon: <RefreshCw className="w-3 h-3" />, onClick: () => handleRefreshExchangeSource(source.id), loading: refreshingExchangeSource === source.id },
                                { label: 'Delete', icon: <Trash2 className="w-3 h-3" />, onClick: () => handleDeleteExchangeSource(source.id), loading: deletingExchangeSource === source.id, danger: true, separator: true },
                              ]} />
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Exchange Rate History Charts */}
              {exchangeRateSources.length > 0 && (
                <div className="mt-6 border-t border-navy-700 pt-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-navy-200 flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-emerald-500" />
                      Rate History
                    </h3>
                    <div className="flex gap-1">
                      {/* Short periods: per-source via admin API */}
                      {([
                        { label: '6h', hours: 6 },
                        { label: '12h', hours: 12 },
                        { label: '24h', hours: 24 },
                        { label: '48h', hours: 48 },
                        { label: '7d', hours: 168 },
                      ] as const).map(({ label, hours }) => (
                        <button key={label} onClick={() => { setExchangeRateHistoryHours(hours); setAggregatedPeriod(null); }}
                          className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                            exchangeRateHistoryHours === hours && !aggregatedPeriod
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-navy-700 text-navy-400 hover:text-navy-200'
                          }`}>
                          {label}
                        </button>
                      ))}
                      {/* Long periods: aggregated via public API */}
                      {(['30d', '90d', '1y'] as const).map(p => (
                        <button key={p} onClick={async () => {
                          setAggregatedPeriod(p);
                          try {
                            const data = await exchangeRatesApi.getHistory({ period: p });
                            setAggregatedHistory({
                              points: data.points.map(pt => ({ price: pt.rate, recordedAt: pt.recordedAt })),
                              pair: data.pair,
                            });
                          } catch { setAggregatedHistory(null); }
                        }}
                          className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                            aggregatedPeriod === p
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-navy-700 text-navy-400 hover:text-navy-200'
                          }`}>
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-4">
                    {aggregatedPeriod && aggregatedHistory ? (
                      <PriceHistoryChart
                        sourceName={`All sources (${aggregatedPeriod})`}
                        currency={aggregatedHistory.pair}
                        points={aggregatedHistory.points}
                      />
                    ) : (
                      exchangeRateSources.map(s => (
                        <PriceHistoryChart
                          key={s.id}
                          sourceName={s.name}
                          currency={exchangeRateHistories[s.id]?.pair ?? `${s.fromCurrency}/${s.toCurrency}`}
                          points={exchangeRateHistories[s.id]?.points ?? []}
                          onReset={() => handleResetExchangeRateHistory(s.id)}
                        />
                      ))
                    )}
                  </div>
                </div>
              )}
            </Card>
          </motion.div>}

          {/* Mail & Auth: admin-only config for invitation emails (provider, from, subject/body, link base URL, token expiry). GET/PUT /admin/settings/mail. */}
          {activeTab === 'mail' && <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card
              data-testid="mail-auth-settings-card"
              className="bg-navy-800/50 border-navy-700"
              aria-describedby="mail-auth-description"
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Mail className="w-5 h-5 text-amber-500" />
                  Mail & Authentication
                </h2>
                <div className="flex items-center gap-3">
                  {mailSavedSuccess && (
                    <span className="text-sm font-medium text-emerald-400" role="status">
                      Saved
                    </span>
                  )}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSaveMailSettings}
                    loading={mailSaving}
                    icon={<Save className="w-4 h-4" />}
                  >
                    Save
                  </Button>
                </div>
              </div>
              <p id="mail-auth-description" className="text-sm text-navy-400 mb-6">
                Configure mail server and invitation emails. When set, invitation emails use these settings; otherwise env (RESEND_API_KEY, FROM_EMAIL) is used.
              </p>
              {mailForm.provider === 'smtp' && (!mailForm.smtpHost || String(mailForm.smtpHost).trim() === '') && (
                <div className="mb-6 rounded-lg border border-amber-800 bg-amber-950/30 px-4 py-3 text-sm text-amber-200" role="alert">
                  SMTP host is not set. Invitation emails will not send until you configure host and port.
                </div>
              )}

              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-1">Provider</label>
                  <select
                    value={mailForm.provider ?? 'resend'}
                    onChange={(e) => setMailForm({ ...mailForm, provider: e.target.value as 'resend' | 'smtp' })}
                    className="w-full form-select"
                  >
                    <option value="resend">Resend</option>
                    <option value="smtp">SMTP</option>
                  </select>
                </div>
                <div className="flex items-center gap-2 pt-7">
                  <input
                    type="checkbox"
                    id="useEnvCredentials"
                    checked={mailForm.useEnvCredentials ?? true}
                    onChange={(e) => setMailForm({ ...mailForm, useEnvCredentials: e.target.checked })}
                    className="rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <label htmlFor="useEnvCredentials" className="text-sm text-navy-300">
                    Use credentials from environment
                  </label>
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-navy-300 mb-1">From email</label>
                  <input
                    type="email"
                    value={mailForm.fromEmail ?? ''}
                    onChange={(e) => setMailForm({ ...mailForm, fromEmail: e.target.value })}
                    className="w-full form-input"
                    placeholder="noreply@example.com"
                  />
                </div>
                {mailForm.provider === 'resend' && (
                  <div className="sm:col-span-2">
                    <label className="block text-sm font-medium text-navy-300 mb-1">Resend API key</label>
                    <input
                      type="password"
                      value={mailForm.resendApiKey === '********' ? '' : (mailForm.resendApiKey ?? '')}
                      onChange={(e) => setMailForm({ ...mailForm, resendApiKey: e.target.value })}
                      className="w-full form-input"
                      placeholder="Leave blank to use RESEND_API_KEY from env"
                      autoComplete="off"
                    />
                  </div>
                )}
                {mailForm.provider === 'smtp' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-navy-300 mb-1">SMTP host</label>
                      <input
                        type="text"
                        value={mailForm.smtpHost ?? ''}
                        onChange={(e) => setMailForm({ ...mailForm, smtpHost: e.target.value })}
                        className="w-full form-input"
                        placeholder="smtp.example.com"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-navy-300 mb-1">SMTP port</label>
                      <NumberInput
                        value={mailForm.smtpPort ?? ''}
                        onChange={(v) => setMailForm({ ...mailForm, smtpPort: v === '' ? undefined : parseInt(v, 10) })}
                        placeholder="587"
                        decimals={0}
                      />
                    </div>
                    <div className="flex items-center gap-2 pt-7">
                      <input
                        type="checkbox"
                        id="smtpUseTls"
                        checked={mailForm.smtpUseTls ?? true}
                        onChange={(e) => setMailForm({ ...mailForm, smtpUseTls: e.target.checked })}
                        className="rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      <label htmlFor="smtpUseTls" className="text-sm text-navy-300">Use TLS</label>
                    </div>
                    <div />
                    <div>
                      <label className="block text-sm font-medium text-navy-300 mb-1">SMTP username</label>
                      <input
                        type="text"
                        value={mailForm.smtpUsername ?? ''}
                        onChange={(e) => setMailForm({ ...mailForm, smtpUsername: e.target.value })}
                        className="w-full form-input"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-navy-300 mb-1">SMTP password</label>
                      <input
                        type="password"
                        value={mailForm.smtpPassword === '********' ? '' : (mailForm.smtpPassword ?? '')}
                        onChange={(e) => setMailForm({ ...mailForm, smtpPassword: e.target.value })}
                        className="w-full form-input"
                        placeholder="Leave blank to keep current"
                        autoComplete="off"
                      />
                    </div>
                  </>
                )}
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-navy-300 mb-1">Invitation link base URL</label>
                  <input
                    type="url"
                    value={mailForm.invitationLinkBaseUrl ?? ''}
                    onChange={(e) => setMailForm({ ...mailForm, invitationLinkBaseUrl: e.target.value })}
                    className="w-full form-input"
                    placeholder="https://app.example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-1">Invitation token expiry (days)</label>
                  <NumberInput
                    value={mailForm.invitationTokenExpiryDays ?? 7}
                    onChange={(v) => setMailForm({ ...mailForm, invitationTokenExpiryDays: parseInt(v, 10) || 7 })}
                    decimals={0}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-1">Verification method</label>
                  <select
                    value={mailForm.verificationMethod ?? ''}
                    onChange={(e) => setMailForm({ ...mailForm, verificationMethod: e.target.value || undefined })}
                    className="w-full form-select"
                  >
                    <option value="">—</option>
                    <option value="magic_link">Magic link</option>
                    <option value="password_only">Password only</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-1">Auth method</label>
                  <select
                    value={mailForm.authMethod ?? ''}
                    onChange={(e) => setMailForm({ ...mailForm, authMethod: e.target.value || undefined })}
                    className="w-full form-select"
                  >
                    <option value="">—</option>
                    <option value="password">Password</option>
                    <option value="magic_link">Magic link</option>
                  </select>
                </div>
              </div>
            </Card>

            {/* Test Email Delivery — second wrapper: settings verification */}
            <Card className="bg-navy-800/50 border-navy-700 mt-6" data-testid="mail-test-email-card">
              <h3 className="text-lg font-semibold text-white mb-2">Test Email Delivery</h3>
              <p className="text-sm text-navy-400 mb-4">
                Send a test email to verify your mail configuration is working.
              </p>
              <div className="flex gap-3 items-start">
                <input
                  type="email"
                  value={testEmail}
                  onChange={(e) => { setTestEmail(e.target.value); setTestEmailResult(null); }}
                  placeholder="recipient@example.com"
                  className="flex-1 form-input"
                />
                <Button
                  onClick={handleSendTestEmail}
                  loading={testEmailLoading}
                  disabled={!testEmail.trim() || testEmailLoading}
                  variant="secondary"
                  size="sm"
                >
                  <Send className="w-4 h-4 mr-1" />
                  Send Test Email
                </Button>
              </div>
              {testEmailResult && (
                <div className={`mt-3 flex items-center gap-2 text-sm ${testEmailResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                  {testEmailResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {testEmailResult.message}
                </div>
              )}
            </Card>

            {/* Email Templates — separate wrapper; show when list has items or when load failed */}
            {(emailTemplates.length > 0 || emailTemplatesError) && (
              <Card className="bg-navy-800/50 border-navy-700 mt-6" data-testid="mail-templates-card">
                <h3 className="text-lg font-semibold text-white mb-2">Email Templates</h3>
                {emailTemplatesError && (
                  <p className="text-sm text-amber-400 mb-3" role="alert">
                    {emailTemplatesError}
                  </p>
                )}
                <p className="text-sm text-navy-400 mb-3">
                  Preview email templates with sample data
                </p>
                {emailTemplates.length > 0 && (
                  <div className="flex items-center gap-3">
                    <select
                      value={selectedTemplate}
                      onChange={(e) => {
                        setSelectedTemplate(e.target.value);
                        setTemplatePreviewHtml('');
                      }}
                      className="flex-1 form-select"
                    >
                      {emailTemplates.map((t) => (
                        <option key={t.name} value={t.name}>
                          {t.name.replace(/_/g, ' ').replace('.html', '')}{t.used ? '' : ' (NU)'}
                        </option>
                      ))}
                    </select>
                    <Button
                      onClick={handlePreviewTemplate}
                      loading={templatePreviewLoading}
                      disabled={!selectedTemplate || templatePreviewLoading}
                      variant="secondary"
                      size="sm"
                    >
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Preview
                    </Button>
                  </div>
                )}
                {templatePreviewHtml && (
                  <div className="mt-4 border border-navy-600 rounded-lg overflow-hidden">
                    <iframe
                      srcDoc={templatePreviewHtml}
                      title="Email Template Preview"
                      className="w-full bg-white"
                      style={{ height: '600px', border: 'none' }}
                      sandbox="allow-same-origin"
                    />
                  </div>
                )}
              </Card>
            )}
          </motion.div>}

          {activeTab === 'documents' && <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <DocumentsTab />
          </motion.div>}

          {activeTab === 'ai-agent' && <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <AIAgentTab />
          </motion.div>}

        </div>
      </div>

      {/* Edit Scraping Source Modal */}
      {editingSource && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl p-6 border border-navy-700 w-full max-w-md mx-4">
            <h3 className="text-lg font-bold text-white mb-4">Edit Scraping Source</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Name</label>
                <input
                  type="text"
                  value={editSourceForm.name}
                  onChange={(e) => setEditSourceForm({ ...editSourceForm, name: e.target.value })}
                  className="w-full form-input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">URL</label>
                <input
                  type="url"
                  value={editSourceForm.url}
                  onChange={(e) => setEditSourceForm({ ...editSourceForm, url: e.target.value })}
                  className="w-full form-input"
                />
              </div>
              <div>
                <label htmlFor="edit_source_xpath" className="block text-sm font-medium text-navy-300 mb-1">XPath selector (optional)</label>
                <input
                  id="edit_source_xpath"
                  type="text"
                  value={editSourceForm.xpath_selector}
                  onChange={(e) => setEditSourceForm({ ...editSourceForm, xpath_selector: e.target.value })}
                  className="w-full form-input font-mono text-xs"
                  placeholder="e.g. //table/tbody/tr[4]/td[2]"
                  aria-describedby="edit_source_xpath_hint"
                />
                <p id="edit_source_xpath_hint" className="text-[10px] text-navy-400 mt-0.5">
                  Use Chrome DevTools: right-click element → Copy → Copy XPath.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scraping Library</label>
                <select
                  value={editSourceForm.scrape_library}
                  onChange={(e) => setEditSourceForm({ ...editSourceForm, scrape_library: e.target.value as ScrapeLibrary })}
                  className="w-full form-select"
                >
                  <option value="HTTPX">HTTPX (Fast, async HTTP)</option>
                  <option value="BEAUTIFULSOUP">BeautifulSoup (HTML parsing)</option>
                  <option value="SELENIUM">Selenium (Browser automation)</option>
                  <option value="PLAYWRIGHT">Playwright (Modern browser automation)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scrape Interval</label>
                <select
                  value={editSourceForm.scrape_interval_minutes}
                  onChange={(e) => setEditSourceForm({ ...editSourceForm, scrape_interval_minutes: parseInt(e.target.value) })}
                  className="w-full form-select"
                >
                  <option value={5}>5 minutes</option>
                  <option value={10}>10 minutes</option>
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={60}>1 hour</option>
                </select>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_source_is_primary"
                    checked={editSourceForm.is_primary}
                    onChange={(e) => setEditSourceForm({ ...editSourceForm, is_primary: e.target.checked })}
                    className="w-4 h-4 rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <label htmlFor="edit_source_is_primary" className="text-sm text-navy-300">Primary</label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_source_is_active"
                    checked={editSourceForm.is_active}
                    onChange={(e) => setEditSourceForm({ ...editSourceForm, is_active: e.target.checked })}
                    className="w-4 h-4 rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <label htmlFor="edit_source_is_active" className="text-sm text-navy-300">Active</label>
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={() => setEditingSource(null)} className="flex-1">
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveEditSource} className="flex-1">
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add Source Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl p-6 border border-navy-700 w-full max-w-md mx-4">
            <h3 className="text-lg font-bold text-white mb-4">Add Scraping Source</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Name</label>
                <input
                  type="text"
                  value={newSource.name}
                  onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
                  className="w-full form-input"
                  placeholder="e.g., ICE Exchange"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">URL</label>
                <input
                  type="url"
                  value={newSource.url}
                  onChange={(e) => setNewSource({ ...newSource, url: e.target.value })}
                  className="w-full form-input"
                  placeholder="https://example.com/prices"
                />
              </div>
              <div>
                <label htmlFor="add_source_xpath" className="block text-sm font-medium text-navy-300 mb-1">XPath selector (optional)</label>
                <input
                  id="add_source_xpath"
                  type="text"
                  value={newSource.xpath_selector}
                  onChange={(e) => setNewSource({ ...newSource, xpath_selector: e.target.value })}
                  className="w-full form-input font-mono text-xs"
                  placeholder="e.g. //table/tbody/tr[4]/td[2]"
                  aria-describedby="add_source_xpath_hint"
                />
                <p id="add_source_xpath_hint" className="text-[10px] text-navy-400 mt-0.5">
                  Chrome DevTools → right-click element → Copy → Copy XPath.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Certificate Type</label>
                <select
                  value={newSource.certificate_type}
                  onChange={(e) => setNewSource({ ...newSource, certificate_type: e.target.value as 'EUA' | 'CEA' })}
                  className="w-full form-select"
                >
                  <option value="EUA">EUA</option>
                  <option value="CEA">CEA</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scraping Library</label>
                <select
                  value={newSource.scrape_library}
                  onChange={(e) => setNewSource({ ...newSource, scrape_library: e.target.value as ScrapeLibrary })}
                  className="w-full form-select"
                >
                  <option value="HTTPX">HTTPX (Fast, async HTTP)</option>
                  <option value="BEAUTIFULSOUP">BeautifulSoup (HTML parsing)</option>
                  <option value="SELENIUM">Selenium (Browser automation)</option>
                  <option value="PLAYWRIGHT">Playwright (Modern browser automation)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scrape Interval</label>
                <select
                  value={newSource.scrape_interval_minutes}
                  onChange={(e) => setNewSource({ ...newSource, scrape_interval_minutes: parseInt(e.target.value) })}
                  className="w-full form-select"
                >
                  <option value={5}>5 minutes</option>
                  <option value={10}>10 minutes</option>
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={60}>1 hour</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowAddModal(false)} className="flex-1">
                Cancel
              </Button>
              <Button variant="primary" onClick={handleAddSource} className="flex-1">
                Add Source
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Exchange Rate Source Modal */}
      {editingExchangeSource && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl p-6 border border-navy-700 w-full max-w-md mx-4">
            <h3 className="text-lg font-bold text-white mb-4">Edit Exchange Rate Source</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Name</label>
                <input
                  type="text"
                  value={editExchangeForm.name}
                  onChange={(e) => setEditExchangeForm({ ...editExchangeForm, name: e.target.value })}
                  className="w-full form-input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">URL</label>
                <input
                  type="url"
                  value={editExchangeForm.url}
                  onChange={(e) => setEditExchangeForm({ ...editExchangeForm, url: e.target.value })}
                  className="w-full form-input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scraping Library</label>
                <select
                  value={editExchangeForm.scrape_library}
                  onChange={(e) => setEditExchangeForm({ ...editExchangeForm, scrape_library: e.target.value as ScrapeLibrary })}
                  className="w-full form-select"
                >
                  <option value="HTTPX">HTTPX (Fast, async HTTP)</option>
                  <option value="BEAUTIFULSOUP">BeautifulSoup (HTML parsing)</option>
                  <option value="SELENIUM">Selenium (Browser automation)</option>
                  <option value="PLAYWRIGHT">Playwright (Modern browser automation)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scrape Interval</label>
                <select
                  value={editExchangeForm.scrape_interval_minutes}
                  onChange={(e) => setEditExchangeForm({ ...editExchangeForm, scrape_interval_minutes: parseInt(e.target.value) })}
                  className="w-full form-select"
                >
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={60}>1 hour</option>
                  <option value={120}>2 hours</option>
                  <option value={360}>6 hours</option>
                  <option value={720}>12 hours</option>
                  <option value={1440}>24 hours</option>
                </select>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_is_primary"
                    checked={editExchangeForm.is_primary}
                    onChange={(e) => setEditExchangeForm({ ...editExchangeForm, is_primary: e.target.checked })}
                    className="w-4 h-4 rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <label htmlFor="edit_is_primary" className="text-sm text-navy-300">Primary</label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_is_active"
                    checked={editExchangeForm.is_active}
                    onChange={(e) => setEditExchangeForm({ ...editExchangeForm, is_active: e.target.checked })}
                    className="w-4 h-4 rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                  />
                  <label htmlFor="edit_is_active" className="text-sm text-navy-300">Active</label>
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={() => setEditingExchangeSource(null)} className="flex-1">
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveEditExchange} className="flex-1">
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add Exchange Rate Source Modal */}
      {showAddExchangeModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-navy-800 rounded-2xl p-6 border border-navy-700 w-full max-w-md mx-4">
            <h3 className="text-lg font-bold text-white mb-4">Add Exchange Rate Source</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Name</label>
                <input
                  type="text"
                  value={newExchangeSource.name}
                  onChange={(e) => setNewExchangeSource({ ...newExchangeSource, name: e.target.value })}
                  className="w-full form-input"
                  placeholder="e.g., ECB Daily Rates"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-1">From Currency</label>
                  <input
                    type="text"
                    value={newExchangeSource.from_currency}
                    onChange={(e) => setNewExchangeSource({ ...newExchangeSource, from_currency: e.target.value.toUpperCase() })}
                    className="w-full form-input"
                    placeholder="EUR"
                    maxLength={3}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-navy-300 mb-1">To Currency</label>
                  <input
                    type="text"
                    value={newExchangeSource.to_currency}
                    onChange={(e) => setNewExchangeSource({ ...newExchangeSource, to_currency: e.target.value.toUpperCase() })}
                    className="w-full form-input"
                    placeholder="CNY"
                    maxLength={3}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">URL</label>
                <input
                  type="url"
                  value={newExchangeSource.url}
                  onChange={(e) => setNewExchangeSource({ ...newExchangeSource, url: e.target.value })}
                  className="w-full form-input"
                  placeholder="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scraping Library</label>
                <select
                  value={newExchangeSource.scrape_library}
                  onChange={(e) => setNewExchangeSource({ ...newExchangeSource, scrape_library: e.target.value as ScrapeLibrary })}
                  className="w-full form-select"
                >
                  <option value="HTTPX">HTTPX (Fast, async HTTP)</option>
                  <option value="BEAUTIFULSOUP">BeautifulSoup (HTML parsing)</option>
                  <option value="SELENIUM">Selenium (Browser automation)</option>
                  <option value="PLAYWRIGHT">Playwright (Modern browser automation)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-300 mb-1">Scrape Interval</label>
                <select
                  value={newExchangeSource.scrape_interval_minutes}
                  onChange={(e) => setNewExchangeSource({ ...newExchangeSource, scrape_interval_minutes: parseInt(e.target.value) })}
                  className="w-full form-select"
                >
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={60}>1 hour</option>
                  <option value={120}>2 hours</option>
                  <option value={360}>6 hours</option>
                  <option value={720}>12 hours</option>
                  <option value={1440}>24 hours</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_primary"
                  checked={newExchangeSource.is_primary}
                  onChange={(e) => setNewExchangeSource({ ...newExchangeSource, is_primary: e.target.checked })}
                  className="w-4 h-4 rounded border-navy-300 text-emerald-600 focus:ring-emerald-500"
                />
                <label htmlFor="is_primary" className="text-sm text-navy-300">
                  Set as primary source for this currency pair
                </label>
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button variant="outline" onClick={() => setShowAddExchangeModal(false)} className="flex-1">
                Cancel
              </Button>
              <Button variant="primary" onClick={handleAddExchangeSource} className="flex-1">
                Add Source
              </Button>
            </div>
          </div>
        </div>
      )}
    </BackofficeLayout>
  );
}
