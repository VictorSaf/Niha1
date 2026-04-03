import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, LayoutDashboard, BarChart3, ArrowRightLeft, CreditCard,
  Users, Settings, Briefcase, User, FileText, Palette, Bot,
  Sliders, Activity, Keyboard, Command,
} from 'lucide-react';
import { useAuthStore } from '../../stores/useStore';
import { getEffectiveRole } from '../../utils/effectiveRole';

interface PaletteItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  action: () => void;
  group: string;
  keywords?: string[];
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { isAuthenticated, user, simulatedRole } = useAuthStore();
  const role = getEffectiveRole(user, simulatedRole) ?? user?.role ?? null;
  const isAdmin = role === 'ADMIN';
  const isRealAdmin = user?.role === 'ADMIN';

  const go = useCallback((path: string) => {
    setOpen(false);
    navigate(path);
  }, [navigate]);

  // Build items based on role
  const items: PaletteItem[] = useMemo(() => {
    if (!isAuthenticated) return [];
    const list: PaletteItem[] = [];

    // Navigation
    const nav = (id: string, label: string, desc: string, icon: React.ReactNode, path: string, keywords?: string[]) =>
      list.push({ id, label, description: desc, icon, action: () => go(path), group: 'Navigation', keywords });

    const canDashboard = isAdmin || ['AML', 'CEA', 'CEA_SETTLE', 'SWAP', 'EUA_SETTLE', 'EUA', 'MM'].includes(role!);
    const canFunding = isAdmin || ['APPROVED', 'FUNDING', 'MM'].includes(role!);
    const canCashMarket = isAdmin || ['CEA', 'MM'].includes(role!);
    const canSwap = isAdmin || ['CEA', 'CEA_SETTLE', 'SWAP', 'MM'].includes(role!);
    const canOnboarding = isAdmin || ['NDA', 'KYC'].includes(role!);
    const isIntroducer = role === 'INTRODUCER';
    const isPreintroducer = role === 'PREINTRODUCER';

    if (canDashboard) nav('dashboard', 'Dashboard', 'Portfolio overview', <LayoutDashboard className="w-4 h-4" />, '/dashboard', ['home', 'portfolio']);
    if (canFunding) nav('funding', 'Funding', 'Deposit & manage funds', <CreditCard className="w-4 h-4" />, '/funding', ['deposit', 'money']);
    if (canCashMarket) nav('cash-market', 'CEA Cash Market', 'Trade CEA certificates', <BarChart3 className="w-4 h-4" />, '/cash-market', ['trade', 'buy', 'order']);
    if (canSwap) nav('swap', 'Swap Market', 'CEA to EUA exchange', <ArrowRightLeft className="w-4 h-4" />, '/swap', ['exchange', 'convert']);
    if (canOnboarding) nav('onboarding', 'Onboarding', 'Continue setup', <FileText className="w-4 h-4" />, '/onboarding');
    if (isIntroducer) nav('introducer', 'Introducer Portal', 'Referral dashboard', <Briefcase className="w-4 h-4" />, '/introducer/dashboard', ['referral']);
    if (isPreintroducer) nav('preintroducer', 'Referral Code', 'View your referral code', <Keyboard className="w-4 h-4" />, '/preintroducer');

    nav('profile', 'Profile', 'Your account settings', <User className="w-4 h-4" />, '/profile', ['account']);

    // Admin tools
    if (isRealAdmin) {
      list.push({ id: 'backoffice', label: 'Backoffice', description: 'Admin panel', icon: <Briefcase className="w-4 h-4" />, action: () => go('/backoffice'), group: 'Admin', keywords: ['admin'] });
      list.push({ id: 'users', label: 'Users', description: 'Manage users', icon: <Users className="w-4 h-4" />, action: () => go('/users'), group: 'Admin', keywords: ['manage'] });
      list.push({ id: 'settings', label: 'Settings', description: 'Scraping & system config', icon: <Settings className="w-4 h-4" />, action: () => go('/settings'), group: 'Admin', keywords: ['config', 'scraping'] });
      list.push({ id: 'fees', label: 'Fee Settings', description: 'Platform fee configuration', icon: <Sliders className="w-4 h-4" />, action: () => go('/fee-settings'), group: 'Admin', keywords: ['commission'] });
      list.push({ id: 'market-makers', label: 'Market Makers', description: 'MM management', icon: <Activity className="w-4 h-4" />, action: () => go('/market-makers'), group: 'Admin', keywords: ['mm'] });
      list.push({ id: 'auto-trade', label: 'Auto Trade', description: 'Automated trading rules', icon: <Bot className="w-4 h-4" />, action: () => go('/backoffice/auto-trade'), group: 'Admin', keywords: ['bot', 'automation'] });
      list.push({ id: 'theme', label: 'Theme', description: 'Visual customization', icon: <Palette className="w-4 h-4" />, action: () => go('/theme'), group: 'Admin' });
      list.push({ id: 'logging', label: 'Logs', description: 'System logs', icon: <FileText className="w-4 h-4" />, action: () => go('/logging'), group: 'Admin' });
    }

    return list;
  }, [isAuthenticated, role, isAdmin, isRealAdmin, go]);

  // Fuzzy filter
  const filtered = useMemo(() => {
    if (!query.trim()) return items;
    const q = query.toLowerCase();
    return items.filter(item => {
      const searchable = [item.label, item.description ?? '', ...(item.keywords ?? [])].join(' ').toLowerCase();
      return q.split('').every(char => searchable.includes(char)) && searchable.includes(q.charAt(0));
    });
  }, [items, query]);

  // Group results
  const grouped = useMemo(() => {
    const groups: Record<string, PaletteItem[]> = {};
    for (const item of filtered) {
      (groups[item.group] ??= []).push(item);
    }
    return groups;
  }, [filtered]);

  const flatFiltered = useMemo(() => filtered, [filtered]);

  // Reset selection when filter changes
  useEffect(() => { setSelectedIndex(0); }, [query]);

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
        setQuery('');
        setSelectedIndex(0);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(i => Math.min(i + 1, flatFiltered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      flatFiltered[selectedIndex]?.action();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
    }
  };

  if (!isAuthenticated) return null;

  let flatIdx = -1;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          className="fixed inset-0 z-[110] flex items-start justify-center pt-[15vh] bg-black/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ duration: 0.12 }}
            className="bg-navy-800 border border-navy-600 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-navy-700">
              <Search className="w-4 h-4 text-navy-400 shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a command or search..."
                className="flex-1 bg-transparent text-sm text-white placeholder-navy-500 outline-none"
              />
              <kbd className="px-1.5 py-0.5 rounded bg-navy-700 border border-navy-600 text-[10px] font-mono text-navy-400">Esc</kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[50vh] overflow-y-auto py-2">
              {flatFiltered.length === 0 ? (
                <div className="px-4 py-6 text-center text-sm text-navy-500">No results found</div>
              ) : (
                Object.entries(grouped).map(([group, groupItems]) => (
                  <div key={group}>
                    <div className="px-4 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-navy-500">{group}</div>
                    {groupItems.map(item => {
                      flatIdx++;
                      const idx = flatIdx;
                      const isSelected = idx === selectedIndex;
                      return (
                        <button
                          key={item.id}
                          data-index={idx}
                          onClick={() => item.action()}
                          onMouseEnter={() => setSelectedIndex(idx)}
                          className={`w-full flex items-center gap-3 px-4 py-2 text-left transition-colors ${
                            isSelected ? 'bg-emerald-500/10 text-white' : 'text-navy-300 hover:bg-navy-700/50'
                          }`}
                        >
                          <span className={isSelected ? 'text-emerald-400' : 'text-navy-500'}>{item.icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">{item.label}</div>
                            {item.description && <div className="text-[11px] text-navy-500 truncate">{item.description}</div>}
                          </div>
                          {isSelected && <span className="text-[10px] text-navy-500">↵</span>}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-2 border-t border-navy-700 text-[10px] text-navy-500">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded bg-navy-700 border border-navy-600 font-mono">↑↓</kbd> navigate</span>
                <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded bg-navy-700 border border-navy-600 font-mono">↵</kbd> select</span>
              </div>
              <span className="flex items-center gap-1"><Command className="w-3 h-3" />K to toggle</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
