import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Check, X, Loader2, XCircle, Eye, EyeOff, Lock, Upload, FileText, CheckCircle2 } from 'lucide-react';
import { authApi, contactApi } from '../services/api';
import { useAuthStore } from '../stores/useStore';
import { getPostLoginRedirect } from '../utils/redirect';
import { logger } from '../utils/logger';
import { getApiErrorMessage } from '../utils/errors';

export function SetupPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(true);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [userInfo, setUserInfo] = useState<{
    email: string;
    firstName: string;
    lastName: string;
  } | null>(null);
  const [error, setError] = useState('');

  // NDA upload step state
  const [step, setStep] = useState<'password' | 'nda' | 'done'>('password');
  const [ndaFile, setNdaFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const ndaRef = useRef<HTMLInputElement>(null);

  // Password validation
  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasSpecialChar = /[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/.test(password);
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0;
  const isValidPassword = hasMinLength && hasUppercase && hasSpecialChar && passwordsMatch;

  // Validate token on mount
  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const validateToken = async () => {
      try {
        const data = await authApi.validateInvitation(token);
        setTokenValid(true);
        setUserInfo(data);
      } catch (err: unknown) {
        setTokenValid(false);
        const error = err as { response?: { status?: number } };
        if (error.response?.status === 410) {
          setError('This invitation link has expired. Please contact the administrator for a new invitation.');
        } else {
          setError('This invitation link is invalid. Please contact the administrator.');
        }
      } finally {
        setValidating(false);
      }
    };

    validateToken();
  }, [token, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValidPassword || !token) return;

    setLoading(true);
    setError('');

    try {
      logger.debug('[SetupPasswordPage] Setting up password for token');
      const { access_token, user } = await authApi.setupPassword(
        token,
        password,
        confirmPassword
      );

      logger.debug('[SetupPasswordPage] Password setup successful, setting auth for user:', {
        email: user.email,
        role: user.role,
        timestamp: new Date().toISOString()
      });

      // Store auth (user is now logged in)
      setAuth(user, access_token);

      // TRODUCER or form-submitted PREINTRODUCER (nda_signed=false) → show NDA upload step
      if (user.role === 'TRODUCER' || (user.role === 'PREINTRODUCER' && !user.ndaSigned)) {
        setStep('nda');
        return;
      }

      // All other roles: navigate normally
      const target = getPostLoginRedirect(user);
      logger.debug('[SetupPasswordPage] Auth set, redirecting to', target);
      navigate(target, { replace: true });
    } catch (err: unknown) {
      logger.error('[SetupPasswordPage] Password setup failed:', err);
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to set password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleNdaUpload = async () => {
    if (!ndaFile) return;
    setUploading(true);
    setError('');
    try {
      await contactApi.uploadIntroducerNDA(ndaFile);
      // Clear auth state — TRODUCER cannot login until admin approves
      useAuthStore.getState().logout();
      setStep('done');
    } catch (err: unknown) {
      setError(getApiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type === 'application/pdf') {
      setNdaFile(file);
      setError('');
    } else if (file) {
      setError('Please upload a PDF file.');
    }
  };

  // Loading state
  if (validating) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-emerald-500 animate-spin mx-auto mb-4" />
          <p className="text-navy-300">Validating invitation...</p>
        </div>
      </div>
    );
  }

  // Invalid/expired token
  if (tokenValid === false) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-navy-800 rounded-2xl shadow-xl p-8 max-w-md w-full text-center"
        >
          <div className="w-16 h-16 bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">
            Invalid Invitation
          </h1>
          <p className="text-navy-400 mb-6">
            {error}
          </p>
          <button
            onClick={() => navigate('/login')}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors"
          >
            Go to Login
          </button>
        </motion.div>
      </div>
    );
  }

  // Step: NDA Upload
  if (step === 'nda') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-navy-800 rounded-2xl shadow-xl p-8 max-w-md w-full"
        >
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-emerald-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <Upload className="w-8 h-8 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">
              Upload Signed NDA
            </h1>
            <p className="text-navy-400 mt-2">
              Upload the NDA document signed by you to complete your account setup
            </p>
          </div>

          {/* Step indicator */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-emerald-600 flex items-center justify-center">
                <Check className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="text-sm text-emerald-400">Password</span>
            </div>
            <div className="flex-1 h-px bg-emerald-600" />
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-emerald-600 flex items-center justify-center">
                <span className="text-xs font-bold text-white">2</span>
              </div>
              <span className="text-sm text-emerald-400 font-medium">Upload NDA</span>
            </div>
          </div>

          {/* File upload area */}
          <div
            onClick={() => ndaRef.current?.click()}
            className="border-2 border-dashed border-navy-600 hover:border-emerald-500/50 rounded-xl p-8 text-center cursor-pointer transition-colors"
          >
            <input
              ref={ndaRef}
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="hidden"
            />
            {ndaFile ? (
              <div className="flex items-center justify-center gap-3">
                <FileText className="w-8 h-8 text-emerald-400" />
                <div className="text-left">
                  <p className="text-white font-medium">{ndaFile.name}</p>
                  <p className="text-navy-400 text-sm">{(ndaFile.size / 1024).toFixed(0)} KB</p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="w-10 h-10 text-navy-500 mx-auto mb-3" />
                <p className="text-navy-300 font-medium">Click to upload signed NDA</p>
                <p className="text-navy-500 text-sm mt-1">PDF files only</p>
              </>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-red-900/20 border border-red-800 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Submit */}
          <button
            type="button"
            onClick={handleNdaUpload}
            disabled={!ndaFile || uploading}
            className="w-full mt-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading...
              </>
            ) : (
              'Upload NDA & Complete Setup'
            )}
          </button>
        </motion.div>
      </div>
    );
  }

  // Step: Done (NDA uploaded, awaiting approval — no login until admin approves)
  if (step === 'done') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-navy-800 rounded-2xl shadow-xl p-8 max-w-md w-full text-center"
        >
          <div className="w-16 h-16 bg-emerald-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-8 h-8 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">
            NDA Uploaded Successfully
          </h1>
          <p className="text-navy-400">
            Your signed NDA has been submitted for review. You will receive
            a confirmation email once it&apos;s approved and your Introducer
            Dashboard will be activated.
          </p>
          <p className="text-navy-500 text-sm mt-4">
            You may close this page. No further action is required.
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-navy-800 rounded-2xl shadow-xl p-8 max-w-md w-full"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-emerald-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">
            Welcome, {userInfo?.firstName}!
          </h1>
          <p className="text-navy-400 mt-2">
            Set up your password to activate your account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email (readonly) */}
          <div>
            <label className="block text-sm font-medium text-navy-300 mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={userInfo?.email || ''}
              disabled
              className="w-full px-4 py-2.5 rounded-lg border border-navy-700 bg-navy-900 text-navy-400"
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-navy-300 mb-1.5">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a strong password"
                className="w-full px-4 py-2.5 pr-10 rounded-lg border border-navy-700 bg-navy-900 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-navy-400 hover:text-navy-600"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {/* Password Requirements */}
            <div className="mt-3 space-y-1.5">
              <div className={`flex items-center gap-2 text-sm ${
                hasMinLength ? 'text-emerald-400' : 'text-navy-400'
              }`}>
                {hasMinLength ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <X className="w-4 h-4" />
                )}
                At least 8 characters
              </div>
              <div className={`flex items-center gap-2 text-sm ${
                hasUppercase ? 'text-emerald-400' : 'text-navy-400'
              }`}>
                {hasUppercase ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <X className="w-4 h-4" />
                )}
                At least 1 uppercase letter
              </div>
              <div className={`flex items-center gap-2 text-sm ${
                hasSpecialChar ? 'text-emerald-400' : 'text-navy-400'
              }`}>
                {hasSpecialChar ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <X className="w-4 h-4" />
                )}
                At least 1 special character (!@#$%^&*)
              </div>
            </div>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="block text-sm font-medium text-navy-300 mb-1.5">
              Confirm Password
            </label>
            <input
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
              className="w-full px-4 py-2.5 rounded-lg border border-navy-700 bg-navy-900 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
            />
            {confirmPassword && !passwordsMatch && (
              <p className="mt-1.5 text-sm text-red-500 flex items-center gap-1">
                <X className="w-4 h-4" />
                Passwords do not match
              </p>
            )}
            {passwordsMatch && (
              <p className="mt-1.5 text-sm text-emerald-400 flex items-center gap-1">
                <Check className="w-4 h-4" />
                Passwords match
              </p>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={!isValidPassword || loading}
            className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Setting up account...
              </>
            ) : (
              'Set Password & Continue'
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
