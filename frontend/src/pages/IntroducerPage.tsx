import { useState, useEffect, useRef, FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Lock, Building2, User, Briefcase, CheckCircle, Loader2, Download, Upload } from 'lucide-react';
import { authApi, contactApi } from '../services/api';
import { useAuthStore } from '../stores/useStore';
import { isValidEmail, sanitizeEmail, sanitizeString } from '../utils';
import { logger } from '../utils/logger';
import {
  DiffuseLogo,
  FloatingPrices,
  NDASuccessAmbient,
  ParticleField,
} from './LoginPageAnimations';

/**
 * Introducer page: ENTER (password login) and NDA (request access) modes.
 * Same pattern as LoginPage but for Introducer flow; NDA submits to introducer-nda-request.
 * After login, INTRODUCER is redirected to /introducer/dashboard via getPostLoginRedirect.
 */
export function IntroducerPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth, user, _hasHydrated } = useAuthStore();

  const inviteToken = searchParams.get('invite');
  const refCode = searchParams.get('ref');

  const [mode, setMode] = useState<'initial' | 'enter' | 'nda'>('initial');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const isSubmittingRef = useRef(false);
  const [requestSent, setRequestSent] = useState(false);
  const [ndaAmbientActive, setNdaAmbientActive] = useState(false);
  const [invitationInfo, setInvitationInfo] = useState<{
    invitedEmail: string;
    invitedFirstName: string | null;
    introducerName: string;
  } | null>(null);
  const [referralCode, setReferralCode] = useState('');
  const [codeType, setCodeType] = useState<'introducer' | 'troducer' | 'buyer' | null>(null);

  // Fetch invitation info when landing with invite token
  useEffect(() => {
    if (inviteToken) {
      contactApi.getInvitationInfo(inviteToken)
        .then(res => {
          setInvitationInfo(res);
          // Pre-fill form fields from invitation data
          if (res.invitedEmail) setEmail(res.invitedEmail);
          if (res.invitedFirstName) setContactFirstName(res.invitedFirstName);
          // Auto-switch to NDA mode so the form is visible
          setMode('nda');
        })
        .catch(() => {
          // Invalid/expired invitation — don't block the form
        });
    }
    if (refCode) {
      setReferralCode(refCode);
      // Detect referral code type to determine if invitee is a buyer
      contactApi.validateCode(refCode)
        .then(res => {
          if (res.valid && res.type === 'introducer') {
            // Code belongs to an introducer → the invitee is a buyer
            setCodeType('buyer');
          }
          // 'preintroducer' and 'troducer' codes → introducer registration flow (default)
        })
        .catch(() => {
          // Validation failed — default to introducer flow
        });
    }
  }, [inviteToken, refCode]);

  useEffect(() => {
    if (!_hasHydrated || !user) return;
    if (user.role === 'TRODUCER') {
      navigate('/introducer/sign-nda', { replace: true });
    } else if (user.role === 'PREINTRODUCER' && !user.ndaSigned) {
      navigate('/introducer/sign-nda', { replace: true });
    } else if (user.role === 'INTRODUCER') {
      navigate('/introducer/dashboard', { replace: true });
    }
  }, [_hasHydrated, user, navigate]);

  useEffect(() => {
    if (!requestSent) {
      setNdaAmbientActive(false);
      return;
    }
    const t = setTimeout(() => setNdaAmbientActive(true), 5000);
    return () => clearTimeout(t);
  }, [requestSent]);

  const [entity, setEntity] = useState('');
  const [contactFirstName, setContactFirstName] = useState('');
  const [contactLastName, setContactLastName] = useState('');
  const [position, setPosition] = useState('');
  const [ndaFile, setNdaFile] = useState<File | null>(null);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    if (isSubmittingRef.current || loading) return;

    setError('');
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
      const { accessToken, access_token, user: loggedInUser } = response as {
        accessToken?: string;
        access_token?: string;
        user: Parameters<typeof setAuth>[0];
      };
      const token = accessToken || access_token;
      setAuth(loggedInUser, token!);
    } catch (err: unknown) {
      logger.error('[IntroducerPage] Login failed:', err);
      const errorObj = err as { message?: string; response?: { data?: { detail?: string } } };
      setError(errorObj.message || errorObj.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
      isSubmittingRef.current = false;
    }
  };

  const handleNDA = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    const sanitizedEntity = sanitizeString(entity);
    const sanitizedEmail = sanitizeEmail(email);
    const sanitizedFirstName = sanitizeString(contactFirstName);
    const sanitizedLastName = sanitizeString(contactLastName);
    const sanitizedPosition = sanitizeString(position);

    if (!sanitizedEmail || !isValidEmail(sanitizedEmail)) {
      setError('Please enter a valid email');
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
    if (sanitizedEntity.trim() && !sanitizedPosition.trim()) {
      setError('Position is required when entity name is provided');
      return;
    }

    setLoading(true);
    try {
      await contactApi.submitIntroducerNDARequest({
        entity_name: sanitizedEntity,
        contact_email: sanitizedEmail,
        contact_first_name: sanitizedFirstName,
        contact_last_name: sanitizedLastName,
        position: sanitizedPosition,
        nda_file: ndaFile || undefined,
        referral_code: referralCode || undefined,
        invite_token: inviteToken || undefined,
        request_flow: codeType === 'buyer' ? 'buyer' : undefined,
      });
      setRequestSent(true);
    } catch {
      setError('Unable to process request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

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
                Our team will review your application and contact you at{' '}
                <span className="text-white/60">{email}</span>
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
    <main className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4 overflow-hidden">
      <DiffuseLogo />
      <ParticleField />
      <FloatingPrices />

      <motion.div
        className="relative z-10 w-full max-w-md"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.5 }}
      >
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
                onClick={() => {
                  setMode('initial');
                  setError('');
                }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
              >
                Back
              </button>
            </motion.form>
          )}

          {mode === 'nda' && (
            <motion.form
              key="nda"
              onSubmit={handleNDA}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="space-y-5"
            >
              <p className="text-white/40 text-center text-sm font-light leading-relaxed mb-2">
                {codeType === 'buyer' ? 'Submit your signed NDA to request access' : 'Request introducer access'}
              </p>
              {codeType === 'buyer' ? (
                <>
                  <a
                    href="/api/v1/contact/nda-template"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/60 hover:text-white/80 text-sm font-light tracking-wider transition-all duration-300"
                  >
                    <Download className="w-4 h-4" />
                    Download NDA
                  </a>
                  <label className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/60 hover:text-white/80 text-sm font-light tracking-wider transition-all duration-300 cursor-pointer">
                    <Upload className="w-4 h-4" />
                    {ndaFile ? ndaFile.name : 'Upload Signed NDA (optional)'}
                    <input
                      type="file"
                      accept=".pdf"
                      className="hidden"
                      onChange={(e) => setNdaFile(e.target.files?.[0] || null)}
                    />
                  </label>
                </>
              ) : (
                <div className="w-full py-3 px-4 rounded-lg bg-white/5 border border-white/10 text-white/50 text-sm font-light leading-relaxed text-center">
                  After submitting this form, you will receive an email with the NDA document attached.
                  Please sign it and use the link in the email to upload your signed copy.
                </div>
              )}
              {invitationInfo && (
                <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-lg p-4 mb-2">
                  <p className="text-emerald-400 text-sm font-medium">
                    You were invited by {invitationInfo.introducerName}
                  </p>
                </div>
              )}
              <div className="space-y-3">
                <div className="relative">
                  <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="text"
                    placeholder="Entity Name (optional)"
                    value={entity}
                    onChange={(e) => setEntity(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
                  />
                </div>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="email"
                    placeholder={codeType === 'troducer' ? 'Email' : 'Corporate Email'}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <input
                      type="text"
                      placeholder="First Name"
                      value={contactFirstName}
                      onChange={(e) => setContactFirstName(e.target.value)}
                      className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
                    />
                  </div>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <input
                      type="text"
                      placeholder="Last Name"
                      value={contactLastName}
                      onChange={(e) => setContactLastName(e.target.value)}
                      className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
                    />
                  </div>
                </div>
                <div className="relative">
                  <Briefcase className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="text"
                    placeholder={entity.trim() ? 'Position in Entity *' : 'Position in Entity (optional)'}
                    value={position}
                    onChange={(e) => setPosition(e.target.value)}
                    className="w-full py-3.5 pl-12 pr-4 bg-white/5 border border-white/10 rounded-lg text-white/90 placeholder-white/30 focus:outline-none focus:border-white/20 transition-colors font-light"
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
                  'SUBMIT'
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setMode('initial');
                  setError('');
                }}
                className="w-full text-white/30 hover:text-white/50 text-xs tracking-wider transition-colors"
              >
                Back
              </button>
            </motion.form>
          )}
        </AnimatePresence>

        <motion.div
          className="mt-12 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2, duration: 1 }}
        >
          <p className="text-white/10 text-[10px] tracking-[0.3em]">INTRODUCER ACCESS</p>
        </motion.div>
      </motion.div>
    </main>
  );
}
