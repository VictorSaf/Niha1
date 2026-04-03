import { useState, useEffect, useRef, useCallback, FormEvent, ChangeEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Lock, Loader2, Building2, User, Briefcase, CheckCircle, Upload, FileText } from 'lucide-react';
import { authApi, contactApi } from '../services/api';
import { useAuthStore } from '../stores/useStore';
import { isValidEmail, sanitizeEmail, sanitizeString } from '../utils';
import { logger } from '../utils/logger';
import {
  DiffuseLogo,
  FloatingPrices,
  GrowingTree,
  NDASuccessAmbient,
  ParticleField,
} from './LoginPageAnimations';

/**
 * Login page: ENTER (password login) and NDA (request access) modes.
 * After NDA submit, shows "Request Submitted" then after 5s fades to ambient animation.
 * Preview: ?preview=nda-success shows that flow without submitting.
 */
export function LoginPage() {
  const [mode, setMode] = useState<'initial' | 'enter' | 'nda' | 'code-entry' | 'no-introducer' | 'introducer-form' | 'buyer-form'>('initial');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const isSubmittingRef = useRef(false);
  const [requestSent, setRequestSent] = useState(false);
  const [ndaAmbientActive, setNdaAmbientActive] = useState(false);
  const [verifying, setVerifying] = useState(false);

  // After 5s on NDA success, fade out content and show ambient animation
  useEffect(() => {
    if (!requestSent) {
      setNdaAmbientActive(false);
      return;
    }
    const t = setTimeout(() => setNdaAmbientActive(true), 5000);
    return () => clearTimeout(t);
  }, [requestSent]);

  // NDA form fields
  const [entity, setEntity] = useState('');
  const [contactFirstName, setContactFirstName] = useState('');
  const [contactLastName, setContactLastName] = useState('');
  const [position, setPosition] = useState('');
  const [ndaFile, setNdaFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [referralCode, setReferralCode] = useState('');
  const [codeType, setCodeType] = useState<'preintroducer' | 'introducer' | null>(null);
  const [codeError, setCodeError] = useState('');
  const [validatingCode, setValidatingCode] = useState(false);

  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  // Note: isAuthenticated, user, and _hasHydrated are now handled by AuthGuard in App.tsx
  const containerRef = useRef<HTMLDivElement>(null);
  const previewAppliedRef = useRef(false);

  // Memoize verifyToken to prevent recreation and ensure stable reference
  // This helps prevent race conditions and unnecessary re-renders
  const verifyToken = useCallback(async (token: string) => {
    setVerifying(true);
    try {
      logger.debug('[LoginPage] Verifying magic link token');
      const { access_token, user: loggedInUser } = await authApi.verifyMagicLink(token);
      logger.debug('[LoginPage] Magic link verified, setting auth for user:', {
        email: loggedInUser.email,
        role: loggedInUser.role,
        timestamp: new Date().toISOString()
      });
      setAuth(loggedInUser, access_token);
      logger.debug('[LoginPage] Auth set, navigation will be handled by LoginRoute guard');
      // Navigation will be handled by LoginRoute guard in App.tsx
    } catch (err) {
      logger.error('[LoginPage] Magic link verification failed:', err);
      setError('Invalid or expired link. Please request a new one.');
      setMode('enter');
    } finally {
      setVerifying(false);
    }
  }, [setAuth, setError, setMode]);

  // Check for magic link token in URL
  useEffect(() => {
    const token = searchParams.get('token');
    if (token) {
      verifyToken(token);
    }
  }, [searchParams, verifyToken]);

  // Pre-fill admin credentials when opening in Cursor browser (?cursor=1)
  useEffect(() => {
    if (searchParams.get('cursor') === '1') {
      setEmail('admin@nihaogroup.com');
      setPassword('Admin123!');
    }
  }, [searchParams]);

  // Preview NDA success flow: ?preview=nda-success shows Request Submitted then ambient after 5s (once per mount)
  useEffect(() => {
    if (searchParams.get('preview') === 'nda-success' && !previewAppliedRef.current) {
      previewAppliedRef.current = true;
      setRequestSent(true);
      setEmail('preview@example.com');
    }
    if (searchParams.get('preview') !== 'nda-success') {
      previewAppliedRef.current = false;
    }
  }, [searchParams]);

  // Note: Navigation for already-authenticated users is now handled by LoginRoute guard in App.tsx
  // This prevents refresh loops by having a single source of truth for redirects

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();

    // PREVENT MULTIPLE SUBMISSIONS
    if (isSubmittingRef.current || loading) {
      return;
    }

    setError('');

    // Sanitize inputs
    const sanitizedEmail = sanitizeEmail(email);
    if (!sanitizedEmail || !isValidEmail(sanitizedEmail)) {
      setError('Please enter a valid email');
      return;
    }

    if (!password.trim()) {
      setError('Password is required');
      return;
    }

    isSubmittingRef.current = true;
    setLoading(true);

    try {
      const response = await authApi.loginWithPassword(sanitizedEmail, password);
      // Backend returns accessToken (camelCase), not access_token (snake_case)
      const { accessToken, access_token, user: loggedInUser } = response as {
        accessToken?: string;
        access_token?: string;
        user: Parameters<typeof setAuth>[0];
      };
      const token = accessToken || access_token; // Support both formats
      setAuth(loggedInUser, token!);
      // AuthGuard in App.tsx will detect the auth change and redirect automatically
    } catch (err: unknown) {
      logger.error('[LoginPage] Login failed:', err);
      const error = err as { message?: string; response?: { data?: { detail?: string } } };
      setError(error.message || error.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
      isSubmittingRef.current = false;
    }
  };

  const handleNDA = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    // Sanitize all inputs
    const sanitizedEntity = sanitizeString(entity);
    const sanitizedEmail = sanitizeEmail(email);
    const sanitizedFirstName = sanitizeString(contactFirstName);
    const sanitizedLastName = sanitizeString(contactLastName);
    const sanitizedPosition = sanitizeString(position);

    if (!sanitizedEntity.trim()) {
      setError('Entity name is required');
      return;
    }

    if (!sanitizedEmail || !isValidEmail(sanitizedEmail)) {
      setError('Please enter a valid corporate email');
      return;
    }

    if (!sanitizedFirstName.trim()) {
      setError('First name is required');
      return;
    }

    if (!sanitizedLastName.trim()) {
      setError('Last name is required');
      return;
    }

    if (!sanitizedPosition.trim()) {
      setError('Position is required');
      return;
    }

    if (ndaFile && !ndaFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are allowed');
      return;
    }

    setLoading(true);
    try {
      await contactApi.submitNDARequest({
        entity_name: sanitizedEntity,
        contact_email: sanitizedEmail,
        contact_first_name: sanitizedFirstName,
        contact_last_name: sanitizedLastName,
        position: sanitizedPosition,
        nda_file: ndaFile || undefined,
        referral_code: codeType === 'introducer' ? referralCode.trim() : undefined,
      });
      setRequestSent(true);
    } catch {
      setError('Unable to process request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF files are allowed');
        return;
      }
      setNdaFile(file);
      setError('');
    }
  };

  const handleValidateCode = async () => {
    const code = referralCode.trim();
    if (!code) {
      setCodeError('Please enter a code');
      return;
    }
    if (code.length !== 8) {
      setCodeError('Code must be exactly 8 characters');
      return;
    }
    setValidatingCode(true);
    setCodeError('');
    try {
      const result = await contactApi.validateCode(code);
      if (!result.valid || !result.type) {
        setCodeError('This code is not valid');
        return;
      }
      setCodeType(result.type);
      if (result.type === 'preintroducer') {
        setMode('introducer-form');
      } else {
        setMode('buyer-form');
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) {
        setCodeError('Too many attempts. Please wait 10 minutes and try again.');
      } else {
        setCodeError('Unable to verify code. Please try again.');
      }
    } finally {
      setValidatingCode(false);
    }
  };

  const handleIntroducerSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    const sanitizedEmail = sanitizeEmail(email);
    const sanitizedFirstName = sanitizeString(contactFirstName);
    const sanitizedLastName = sanitizeString(contactLastName);

    if (!sanitizedEmail || !isValidEmail(sanitizedEmail)) {
      setError('Please enter a valid email');
      return;
    }
    if (!sanitizedFirstName.trim()) { setError('First name is required'); return; }
    if (!sanitizedLastName.trim()) { setError('Last name is required'); return; }

    // Validate NDA file if provided
    if (ndaFile && !ndaFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are allowed');
      return;
    }

    setLoading(true);
    try {
      await contactApi.submitIntroducerNDARequest({
        contact_email: sanitizedEmail,
        contact_first_name: sanitizedFirstName,
        contact_last_name: sanitizedLastName,
        entity_name: sanitizeString(entity) || '',
        position: '',
        referral_code: referralCode.trim(),
        nda_file: ndaFile || undefined,
      });
      setRequestSent(true);
    } catch (err: unknown) {
      const ax = err as { response?: { status?: number; data?: { detail?: string } } };
      const detail = ax.response?.status === 409 ? ax.response?.data?.detail : null;
      setError(detail || 'Unable to process request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <Loader2 className="w-8 h-8 animate-spin text-white/40 mx-auto" />
          <p className="text-white/30 mt-4 text-sm tracking-wide">Verifying...</p>
        </motion.div>
      </main>
    );
  }

  if (requestSent) {
    const resetNda = () => {
      setRequestSent(false);
      setNdaAmbientActive(false);
      setMode('initial');
      setEntity('');
      setEmail('');
      setContactFirstName('');
      setContactLastName('');
      setPosition('');
      setNdaFile(null);
      setReferralCode('');
      setCodeType(null);
      setCodeError('');
    };

    return (
      <main className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4 overflow-hidden">
        {ndaAmbientActive ? <NDASuccessAmbient /> : <ParticleField />}
        <AnimatePresence mode="wait">
          {!ndaAmbientActive ? (
            <motion.div
              key="nda-confirm"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.8, ease: 'easeInOut' } }}
              className="text-center z-10"
            >
              <motion.div
                className="w-20 h-20 rounded-full border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center mx-auto mb-8"
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <CheckCircle className="w-10 h-10 text-emerald-400/80" />
              </motion.div>
              <h2 className="text-2xl font-light text-white/90 mb-4 tracking-wide">Request Submitted</h2>
              <p className="text-white/40 max-w-sm mx-auto text-sm leading-relaxed mb-2">
                Thank you for your interest in Nihao Group.
              </p>
              <p className="text-white/40 max-w-sm mx-auto text-sm leading-relaxed">
                Our team will review your application and contact you at <span className="text-white/60">{email}</span>
              </p>
              <button
                type="button"
                onClick={resetNda}
                className="mt-8 text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
                aria-label="Submit another NDA request"
              >
                Submit another request
              </button>
            </motion.div>
          ) : (
            <motion.div
              key="nda-ambient-cta"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5, duration: 0.6 }}
              className="absolute bottom-12 left-0 right-0 text-center z-10"
            >
              <button
                type="button"
                onClick={resetNda}
                className="text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
                aria-label="Submit another NDA request"
              >
                Submit another request
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    );
  }

  return (
    <main
      ref={containerRef}
      className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4 overflow-x-hidden overflow-y-auto"
    >
      {/* Background Elements */}
      <DiffuseLogo />
      <ParticleField />
      <FloatingPrices />

      {/* Tree: wrapper needs explicit width so inner centering + crown aren’t clipped */}
      <div className="absolute bottom-0 left-[max(0.25rem,1.5vw)] z-[1] hidden w-[min(400px,44vw)] overflow-visible lg:block">
        <GrowingTree />
      </div>

      {/* Main Content */}
      <motion.div
        className="relative z-10 w-full max-w-md"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.5 }}
      >
        {/* Logo */}
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 1 }}
        >
          <h1 className="text-5xl font-light text-white/90 tracking-[0.3em] mb-2">NIHAO</h1>
          <div className="w-12 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent mx-auto" />
        </motion.div>

        <AnimatePresence mode="wait">
          {mode === 'initial' && (
            <motion.div
              key="initial"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-4"
            >
              <button
                onClick={() => setMode('enter')}
                className="w-full py-4 px-8 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/80 hover:text-white font-light tracking-[0.2em] transition-all duration-300"
              >
                ENTER
              </button>
              <button
                onClick={() => setMode('nda')}
                className="w-full py-4 px-8 rounded-lg bg-transparent hover:bg-white/5 border border-white/5 hover:border-white/10 text-white/40 hover:text-white/60 font-light tracking-[0.2em] transition-all duration-300"
              >
                NDA
              </button>
            </motion.div>
          )}

          {mode === 'enter' && (
            <motion.form
              key="enter"
              onSubmit={handleLogin}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-5"
            >
              <div className="space-y-4">
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="email"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full py-4 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
                  />
                </div>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full py-4 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
                  />
                </div>
              </div>

              {error && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-red-400/70 text-sm text-center"
                >
                  {error}
                </motion.p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 px-8 rounded-lg bg-white/10 hover:bg-white/15 border border-white/20 text-white/90 font-light tracking-[0.2em] transition-all duration-300 disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin mx-auto" />
                ) : (
                  'CONTINUE'
                )}
              </button>

              <button
                type="button"
                onClick={() => { setMode('initial'); setError(''); }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
              >
                Back
              </button>
            </motion.form>
          )}

          {mode === 'nda' && (
            <motion.div
              key="nda"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-4"
            >
              <p className="text-white/40 text-center text-sm font-light leading-relaxed mb-2">
                How would you like to request access?
              </p>
              <button
                onClick={() => setMode('code-entry')}
                className="w-full py-4 px-6 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-500/30 text-left transition-all duration-300"
              >
                <div className="text-white/80 font-light tracking-wide text-sm">I have an access code</div>
                <div className="text-white/30 text-xs mt-1">Enter the code from your introducer</div>
              </button>
              <button
                onClick={() => setMode('no-introducer')}
                className="w-full py-4 px-6 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-amber-500/30 text-left transition-all duration-300"
              >
                <div className="text-white/80 font-light tracking-wide text-sm">No access code</div>
                <div className="text-white/30 text-xs mt-1">Request access without a referral</div>
              </button>
              <button
                type="button"
                onClick={() => { setMode('initial'); setError(''); }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
              >
                Back
              </button>
            </motion.div>
          )}

          {mode === 'code-entry' && (
            <motion.div
              key="code-entry"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-5"
            >
              <p className="text-white/40 text-center text-sm font-light leading-relaxed">
                Enter the access code from your introducer
              </p>
              <input
                type="text"
                value={referralCode}
                onChange={(e) => { setReferralCode(e.target.value); setCodeError(''); }}
                placeholder="e.g. Nx7k$mP2"
                className="w-full py-4 px-4 bg-white/5 border border-white/10 rounded-lg text-white/90 text-center text-lg font-mono tracking-[0.15em] placeholder-white/20 focus:outline-none focus:border-white/20 transition-colors"
                maxLength={8}
              />
              {codeError && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-red-400/70 text-sm text-center">
                  {codeError}
                </motion.p>
              )}
              <button
                onClick={handleValidateCode}
                disabled={validatingCode}
                className="w-full py-4 px-8 rounded-lg bg-emerald-600/80 hover:bg-emerald-500/80 border border-emerald-500/30 text-white/90 font-light tracking-[0.2em] transition-all duration-300 disabled:opacity-50"
              >
                {validatingCode ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'VERIFY CODE'}
              </button>
              <button
                type="button"
                onClick={() => { setMode('nda'); setReferralCode(''); setCodeError(''); }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
              >
                Back
              </button>
            </motion.div>
          )}

          {mode === 'no-introducer' && (
            <motion.div
              key="no-introducer"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-5"
            >
              <div className="bg-white/5 border border-amber-500/20 rounded-lg p-5 text-white/50 text-xs leading-relaxed space-y-3">
                <p>NIHA provides an <span className="text-amber-400/80">exclusive market access service</span>, available only to referred business partners and qualified entities.</p>
                <p>Due to limited CEA market liquidity, we carefully manage our client capacity to ensure we can deliver on our commitments.</p>
                <p>You may request access without a referral — we will assess whether current market conditions allow us to serve your needs and <span className="text-white/70">respond within 48 hours</span>.</p>
                <p className="text-white/30">Thank you for your interest. If we are unable to accommodate your request at this time, we conduct systematic reviews and will be honored to invite you as a partner as soon as liquidity permits.</p>
              </div>
              <button
                onClick={() => setMode('buyer-form')}
                className="w-full py-4 px-8 rounded-lg bg-white/10 hover:bg-white/15 border border-white/20 text-white/90 font-light tracking-[0.2em] transition-all duration-300"
              >
                CONTINUE
              </button>
              <button
                type="button"
                onClick={() => setMode('nda')}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
              >
                Back
              </button>
            </motion.div>
          )}

          {mode === 'buyer-form' && (
            <motion.form
              key="buyer-form"
              onSubmit={handleNDA}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-5"
            >
              <p className="text-white/40 text-center text-sm font-light leading-relaxed mb-2">
                Submit your signed NDA to request access
              </p>
              <a
                href="/api/v1/contact/nda-template"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/60 hover:text-white/80 text-sm font-light tracking-wider transition-all duration-300"
              >
                <FileText className="w-4 h-4" />
                Download NDA
              </a>

              <div className="space-y-3">
                {/* Entity Name */}
                <div className="relative">
                  <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input type="text" placeholder="Entity Name" value={entity} onChange={(e) => setEntity(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                </div>
                {/* Email */}
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input type="email" placeholder="Corporate Email" value={email} onChange={(e) => setEmail(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                </div>
                {/* Names */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <input type="text" placeholder="First Name" value={contactFirstName} onChange={(e) => setContactFirstName(e.target.value)}
                      className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                  </div>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <input type="text" placeholder="Last Name" value={contactLastName} onChange={(e) => setContactLastName(e.target.value)}
                      className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                  </div>
                </div>
                {/* Position */}
                <div className="relative">
                  <Briefcase className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input type="text" placeholder="Position in Entity" value={position} onChange={(e) => setPosition(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                </div>
                {/* File Upload */}
                <input ref={fileInputRef} type="file" accept=".pdf" onChange={handleFileChange} className="hidden" />
                <div onClick={() => fileInputRef.current?.click()}
                  className={`w-full py-3.5 px-4 bg-white/5 border rounded-lg cursor-pointer transition-colors flex items-center gap-3 ${
                    ndaFile ? 'border-emerald-500/50' : 'border-white/10 hover:border-white/20'
                  }`}>
                  {ndaFile ? (
                    <><FileText className="w-4 h-4 text-emerald-400/70" /><span className="text-white/70 font-light text-sm truncate">{ndaFile.name}</span></>
                  ) : (
                    <><Upload className="w-4 h-4 text-white/30" /><span className="text-white/30 font-light">Upload Signed NDA (optional)</span></>
                  )}
                </div>
              </div>

              {error && (<motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-red-400/70 text-sm text-center">{error}</motion.p>)}

              <button type="submit" disabled={loading}
                className="w-full py-4 px-8 rounded-lg bg-white/10 hover:bg-white/15 border border-white/20 text-white/90 font-light tracking-[0.2em] transition-all duration-300 disabled:opacity-50">
                {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'SUBMIT'}
              </button>

              <button type="button" onClick={() => { setMode('nda'); setError(''); setNdaFile(null); }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors">
                Back
              </button>
            </motion.form>
          )}

          {mode === 'introducer-form' && (
            <motion.form
              key="introducer-form"
              onSubmit={handleIntroducerSubmit}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-5"
            >
              <p className="text-white/40 text-center text-sm font-light leading-relaxed mb-2">
                Apply as an Introducer
              </p>

              <div className="space-y-3">
                {/* Email */}
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                </div>
                {/* Names */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <input type="text" placeholder="First Name" value={contactFirstName} onChange={(e) => setContactFirstName(e.target.value)}
                      className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                  </div>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <input type="text" placeholder="Last Name" value={contactLastName} onChange={(e) => setContactLastName(e.target.value)}
                      className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                  </div>
                </div>
                {/* Entity (optional) */}
                <div className="relative">
                  <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input type="text" placeholder="Entity (optional)" value={entity} onChange={(e) => setEntity(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light" />
                </div>
                {/* NDA Upload (optional) */}
                <input ref={fileInputRef} type="file" accept=".pdf" onChange={handleFileChange} className="hidden" />
                <div onClick={() => fileInputRef.current?.click()}
                  className={`w-full py-3.5 px-4 bg-white/5 border rounded-lg cursor-pointer transition-colors flex items-center gap-3 ${
                    ndaFile ? 'border-emerald-500/50' : 'border-white/10 hover:border-white/20'
                  }`}>
                  {ndaFile ? (
                    <><FileText className="w-4 h-4 text-emerald-400/70" /><span className="text-white/70 font-light text-sm truncate">{ndaFile.name}</span></>
                  ) : (
                    <><Upload className="w-4 h-4 text-white/30" /><span className="text-white/30 font-light">Upload Signed NDA (optional)</span></>
                  )}
                </div>
              </div>

              {error && (<motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-red-400/70 text-sm text-center">{error}</motion.p>)}

              <button type="submit" disabled={loading}
                className="w-full py-4 px-8 rounded-lg bg-emerald-600/80 hover:bg-emerald-500/80 border border-emerald-500/30 text-white/90 font-light tracking-[0.2em] transition-all duration-300 disabled:opacity-50">
                {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'APPLY'}
              </button>

              <button type="button" onClick={() => { setMode('code-entry'); setError(''); setNdaFile(null); }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors">
                Back
              </button>
            </motion.form>
          )}
        </AnimatePresence>

        {/* Subtle footer */}
        <motion.div
          className="mt-12 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2, duration: 1 }}
        >
          <p className="text-white/10 text-[10px] tracking-[0.3em]">EXCLUSIVE ACCESS</p>
        </motion.div>
      </motion.div>
    </main>
  );
}
