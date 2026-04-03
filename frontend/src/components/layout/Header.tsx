import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Menu, X, LogOut, User, UserPlus, Settings, Briefcase, ChevronDown, Palette } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Logo, Button, PriceTicker } from '../common';
import { useAuthStore, useUIStore } from '../../stores/useStore';
import { useIntroducerStore } from '../../stores/useIntroducerStore';
import { usePrices } from '../../hooks/usePrices';
import { getEffectiveRole } from '../../utils/effectiveRole';
import { cn } from '../../utils';
import type { User as UserType } from '../../types';

// Helper to get user initials
const getInitials = (user: UserType | null): string => {
  if (!user) return '??';
  if (user.firstName && user.lastName) {
    return `${user.firstName[0]}${user.lastName[0]}`.toUpperCase();
  }
  return user.email.substring(0, 2).toUpperCase();
};

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { isAuthenticated, user, simulatedRole, logout } = useAuthStore();
  const { prices } = usePrices();
  const { theme } = useUIStore();
  const setDashboardTab = useIntroducerStore((s) => s.setDashboardTab);
  const location = useLocation();
  const navigate = useNavigate();

  const isLandingPage = location.pathname === '/';
  const isDark = theme === 'dark';
  const role = getEffectiveRole(user, simulatedRole) ?? user?.role ?? null;
  const isAdmin = role === 'ADMIN';
  const isRealAdmin = user?.role === 'ADMIN';

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setUserDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMenuItemClick = (path: string) => {
    setUserDropdownOpen(false);
    navigate(path);
  };

  const handleLogout = () => {
    setUserDropdownOpen(false);
    logout();
    navigate('/');
  };

  // Build navigation links based on user role (0010 flow)
  // ADMIN sees ALL navigation options (superuser access)
  const navLinks = useMemo(() => {
    if (!isAuthenticated) {
      return [{ href: '/contact', label: 'Contact', icon: null }];
    }
    if (!role) return [];

    const links: { href: string; label: string; icon: LucideIcon | null; highlight?: boolean }[] = [];

    // ADMIN superuser: show ALL navigation options
    if (isAdmin) {
      links.push({ href: '/dashboard', label: 'Dashboard', icon: null });
      links.push({ href: '/funding', label: 'Funding', icon: null });
      links.push({ href: '/cash-market', label: 'CEA Cash', icon: null });
      links.push({ href: '/swap', label: 'Swap', icon: null });
      links.push({ href: '/onboarding', label: 'Onboarding', icon: null });
      links.push({ href: '/introducer/dashboard', label: 'Introducer', icon: null });
    } else if (role === 'PREINTRODUCER') {
      links.push({ href: '/preintroducer', label: 'Referral Code', icon: null });
    } else if (role === 'INTRODUCER') {
      links.push({ href: '/introducer/dashboard', label: 'Introducer Portal', icon: null });
      links.push({ href: '/introducer/dashboard', label: 'Referrals', icon: UserPlus, highlight: true });
    } else {

      // Regular users: show only their allowed sections
      const canCashMarket = ['CEA', 'MM'].includes(role);
      const canSwap = ['CEA', 'CEA_SETTLE', 'SWAP', 'MM'].includes(role);
      const canDashboard = ['AML', 'CEA', 'CEA_SETTLE', 'SWAP', 'EUA_SETTLE', 'EUA', 'MM'].includes(role);
      const canFunding = ['APPROVED', 'FUNDING', 'MM'].includes(role);
      const canOnboarding = ['NDA', 'KYC'].includes(role);

      if (canDashboard) links.push({ href: '/dashboard', label: 'Dashboard', icon: null });
      if (canFunding) links.push({ href: '/funding', label: 'Funding', icon: null });
      if (canCashMarket) links.push({ href: '/cash-market', label: 'CEA Cash', icon: null });
      if (canSwap) links.push({ href: '/swap', label: 'Swap', icon: null });
      if (canOnboarding) links.push({ href: '/onboarding', label: 'Onboarding', icon: null });
    }

    return links;
  }, [isAuthenticated, role, isAdmin, location.pathname]);

  return (
    <header
      className={cn(
        'fixed top-0 left-0 right-0 z-50 transition-all duration-300',
        isLandingPage
          ? 'bg-transparent'
          : isDark
            ? 'bg-navy-900/80 backdrop-blur-lg border-b border-navy-700'
            : 'bg-white/80 backdrop-blur-lg border-b border-navy-100'
      )}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 md:h-20">
          {/* Logo */}
          <Link to="/" className="flex-shrink-0">
            <Logo variant={isLandingPage || isDark ? 'light' : 'dark'} />
          </Link>

          {/* Price Ticker (Desktop) — admin only */}
          {!isLandingPage && isRealAdmin && (
            <div className="hidden lg:block">
              <PriceTicker prices={prices} variant="compact" />
            </div>
          )}

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => {
              const Icon = link.icon;

              if (link.highlight) {
                return (
                  <Link
                    key={`${link.href}-${link.label}`}
                    to={link.href}
                    onClick={() => setDashboardTab('referrals')}
                    className="text-sm font-medium transition-all flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 hover:text-emerald-300"
                  >
                    {Icon && <Icon className="w-4 h-4" />}
                    {link.label}
                  </Link>
                );
              }

              return (
                <Link
                  key={link.href}
                  to={link.href}
                  className={cn(
                    'text-sm font-medium transition-colors flex items-center gap-1.5',
                    isLandingPage || isDark
                      ? 'text-white/80 hover:text-white'
                      : 'text-navy-600 hover:text-navy-900',
                    location.pathname === link.href &&
                      (isLandingPage || isDark ? 'text-white' : 'text-emerald-600')
                  )}
                >
                  {Icon && <Icon className="w-4 h-4" />}
                  {link.label}
                </Link>
              );
            })}

            {isAuthenticated ? (
              <div className="relative" ref={dropdownRef}>
                {/* Avatar Button */}
                <button
                  onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                  className={cn(
                    'flex items-center gap-2 p-1 rounded-full transition-all duration-200',
                    userDropdownOpen && 'ring-2 ring-emerald-500 ring-offset-2',
                    isDark ? 'ring-offset-navy-900' : 'ring-offset-white'
                  )}
                >
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center text-white font-bold text-sm shadow-lg">
                    {getInitials(user)}
                  </div>
                  <ChevronDown className={cn(
                    'w-4 h-4 transition-transform duration-200',
                    userDropdownOpen && 'rotate-180',
                    isLandingPage || isDark ? 'text-white' : 'text-navy-600'
                  )} />
                </button>

                {/* Dropdown Menu */}
                <AnimatePresence>
                  {userDropdownOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 10, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 10, scale: 0.95 }}
                      transition={{ duration: 0.15 }}
                      className={cn(
                        'absolute right-0 mt-2 w-56 rounded-xl shadow-xl border overflow-hidden z-50',
                        isDark
                          ? 'bg-navy-800 border-navy-700'
                          : 'bg-white border-navy-100'
                      )}
                    >
                      {/* User Info Header */}
                      <div className={cn(
                        'px-4 py-3 border-b',
                        isDark ? 'border-navy-700 bg-navy-900/50' : 'border-navy-100 bg-navy-50'
                      )}>
                        <p className={cn(
                          'text-sm font-semibold truncate',
                          isDark ? 'text-white' : 'text-navy-900'
                        )}>
                          {user?.firstName && user?.lastName
                            ? `${user.firstName} ${user.lastName}`
                            : user?.email}
                        </p>
                        <p className={cn(
                          'text-xs truncate',
                          isDark ? 'text-navy-400' : 'text-navy-500'
                        )}>
                          {user?.firstName && user?.lastName
                            ? user?.email
                            : user?.role === 'ADMIN' && simulatedRole
                              ? `ADMIN (simulând: ${simulatedRole})`
                              : (role ?? 'User')}
                        </p>
                      </div>

                      {/* Menu Items */}
                      <div className="py-2">
                        <button
                          onClick={() => handleMenuItemClick('/profile')}
                          className={cn(
                            'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                            isDark
                              ? 'text-navy-200 hover:bg-navy-700'
                              : 'text-navy-700 hover:bg-navy-50'
                          )}
                        >
                          <User className="w-4 h-4" />
                          Profile
                        </button>

                        {isRealAdmin && (
                          <>
                            <button
                              onClick={() => handleMenuItemClick('/settings')}
                              className={cn(
                                'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                                isDark
                                  ? 'text-navy-200 hover:bg-navy-700'
                                  : 'text-navy-700 hover:bg-navy-50'
                              )}
                            >
                              <Settings className="w-4 h-4" />
                              Settings
                            </button>
                            <button
                              onClick={() => handleMenuItemClick('/theme')}
                              className={cn(
                                'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                                isDark
                                  ? 'text-navy-200 hover:bg-navy-700'
                                  : 'text-navy-700 hover:bg-navy-50'
                              )}
                            >
                              <Palette className="w-4 h-4" />
                              Theme
                            </button>
                            <button
                              onClick={() => handleMenuItemClick('/backoffice')}
                              className={cn(
                                'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                                isDark
                                  ? 'text-navy-200 hover:bg-navy-700'
                                  : 'text-navy-700 hover:bg-navy-50'
                              )}
                            >
                              <Briefcase className="w-4 h-4" />
                              Backoffice
                            </button>
                          </>
                        )}
                      </div>

                      {/* Divider & Logout */}
                      <div className={cn(
                        'border-t py-2',
                        isDark ? 'border-navy-700' : 'border-navy-100'
                      )}>
                        <button
                          onClick={handleLogout}
                          className={cn(
                            'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
                            'text-red-500 hover:bg-red-900/20'
                          )}
                        >
                          <LogOut className="w-4 h-4" />
                          Logout
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : (
              <Link to="/login">
                <Button variant={isLandingPage ? 'secondary' : 'primary'} size="sm">
                  Enter Platform
                </Button>
              </Link>
            )}
          </nav>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center gap-2">
            <button
              className="p-2"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? (
                <X className={cn('w-6 h-6', isLandingPage || isDark ? 'text-white' : 'text-navy-900')} />
              ) : (
                <Menu className={cn('w-6 h-6', isLandingPage || isDark ? 'text-white' : 'text-navy-900')} />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div className={cn(
            'md:hidden py-4 border-t',
            isDark ? 'border-navy-700' : 'border-white/10'
          )}>
            <nav className="flex flex-col gap-4">
              {navLinks.map((link) => {
                const Icon = link.icon;

                if (link.highlight) {
                  return (
                    <Link
                      key={`${link.href}-${link.label}`}
                      to={link.href}
                      onClick={() => { setMobileMenuOpen(false); setDashboardTab('referrals'); }}
                      className="text-lg font-medium flex items-center gap-2 px-3 py-1.5 rounded-full w-fit bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                    >
                      {Icon && <Icon className="w-5 h-5" />}
                      {link.label}
                    </Link>
                  );
                }

                return (
                  <Link
                    key={link.href}
                    to={link.href}
                    className={cn(
                      'text-lg font-medium flex items-center gap-2',
                      isLandingPage || isDark ? 'text-white' : 'text-navy-900'
                    )}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {Icon && <Icon className="w-5 h-5" />}
                    {link.label}
                  </Link>
                );
              })}
              {isAuthenticated ? (
                <>
                  <div className={cn('border-t pt-4 mt-2', isDark ? 'border-navy-700' : 'border-navy-200')}>
                    <Link to="/profile" className={cn('text-lg font-medium flex items-center gap-2', isDark ? 'text-navy-200' : 'text-navy-700')} onClick={() => setMobileMenuOpen(false)}>
                      <User className="w-5 h-5" /> Profile
                    </Link>
                  </div>
                  {isRealAdmin && (
                    <>
                      <Link to="/settings" className={cn('text-lg font-medium flex items-center gap-2', isDark ? 'text-navy-200' : 'text-navy-700')} onClick={() => setMobileMenuOpen(false)}>
                        <Settings className="w-5 h-5" /> Settings
                      </Link>
                      <Link to="/backoffice" className={cn('text-lg font-medium flex items-center gap-2', isDark ? 'text-navy-200' : 'text-navy-700')} onClick={() => setMobileMenuOpen(false)}>
                        <Briefcase className="w-5 h-5" /> Backoffice
                      </Link>
                    </>
                  )}
                  <button
                    onClick={() => { setMobileMenuOpen(false); handleLogout(); }}
                    className="text-lg font-medium flex items-center gap-2 text-red-500"
                  >
                    <LogOut className="w-5 h-5" /> Logout
                  </button>
                </>
              ) : (
                <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="primary" className="w-full">
                    Enter Platform
                  </Button>
                </Link>
              )}
            </nav>
          </div>
        )}
      </div>
    </header>
  );
}
