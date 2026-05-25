import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLang, LANG_LABELS, LANG_FULL_NAMES, type Lang } from '../context/LangContext';
import { useTheme } from '../context/ThemeContext';
import { loginWithPassword, verify2fa, sendOtp, verifyOtp, loginWithGoogle } from '../api/auth';
import { is2FAResponse } from '../types';
import { getErrorMessage } from '../api/client';

type LoginMode = 'password' | 'password-2fa' | 'otp-phone' | 'otp-code';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (element: HTMLElement, options: object) => void;
        };
      };
    };
  }
}

export default function Login() {
  const { login, rep } = useAuth();
  const navigate = useNavigate();
  const { lang, setLang, t } = useLang();
  const { theme, toggle: toggleTheme } = useTheme();

  const [mode, setMode] = useState<LoginMode>('password');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [devOtp, setDevOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef<HTMLDivElement>(null);
  // 2FA challenge state (after password verified, before OTP entered)
  const [twoFaChallengeId, setTwoFaChallengeId] = useState('');
  const [twoFaEmailMasked, setTwoFaEmailMasked] = useState('');
  const [twoFaCode, setTwoFaCode] = useState('');
  const [twoFaDevOtp, setTwoFaDevOtp] = useState('');

  useEffect(() => {
    if (rep) {
      navigate(rep.role === 'rep' ? '/today' : '/manager', { replace: true });
    }
  }, [rep, navigate]);

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    if (!clientId || !window.google) return;
    const el = document.getElementById('google-btn');
    if (!el) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async ({ credential }) => {
        setLoading(true);
        setError('');
        try {
          const res = await loginWithGoogle(credential);
          login(res.access_token, res.rep);
          navigate(res.rep.role === 'rep' ? '/today' : '/manager', { replace: true });
        } catch (err) {
          setError(getErrorMessage(err));
        } finally {
          setLoading(false);
        }
      },
    });
    window.google.accounts.id.renderButton(el, {
      theme: 'outline',
      size: 'large',
      width: el.offsetWidth || 320,
      text: 'continue_with',
    });
  }, [login, navigate]);

  async function handlePasswordLogin(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await loginWithPassword(identifier, password);
      if (is2FAResponse(res)) {
        // Password validated; need OTP next
        setTwoFaChallengeId(res.challenge_id);
        setTwoFaEmailMasked(res.email_masked);
        setTwoFaDevOtp(res.dev_otp ?? '');
        setTwoFaCode(res.dev_otp ?? '');  // pre-fill in dev mode for convenience
        setMode('password-2fa');
      } else {
        // No 2FA required — straight to dashboard
        login(res.access_token, res.rep);
        navigate(res.rep.role === 'rep' ? '/today' : '/manager', { replace: true });
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handle2faVerify(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await verify2fa(twoFaChallengeId, twoFaCode);
      login(res.access_token, res.rep);
      navigate(res.rep.role === 'rep' ? '/today' : '/manager', { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function cancel2fa() {
    setTwoFaChallengeId('');
    setTwoFaEmailMasked('');
    setTwoFaCode('');
    setTwoFaDevOtp('');
    setError('');
    setMode('password');
  }

  async function handleSendOtp(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await sendOtp(phone);
      if (res.dev_otp) {
        setDevOtp(res.dev_otp);
        setOtp(res.dev_otp);
      }
      setMode('otp-code');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await verifyOtp(phone, otp);
      login(res.access_token, res.rep);
      navigate(res.rep.role === 'rep' ? '/today' : '/manager', { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-forest-50 dark:bg-dm-bg flex flex-col items-center justify-center px-4 py-10 relative">

      {/* ── Top-right controls: theme toggle + language picker ── */}
      <div className="absolute top-4 right-4 z-30 flex items-center gap-2">

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="h-9 w-9 rounded-lg flex items-center justify-center
                     bg-white/80 dark:bg-forest-900/80 backdrop-blur
                     border border-forest-200 dark:border-forest-700
                     text-forest-600 dark:text-forest-300
                     hover:bg-white dark:hover:bg-forest-800
                     transition-colors"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? (
            /* Sun — currently dark, click to go light */
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            /* Moon — currently light, click to go dark */
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>

        {/* Language picker */}
        <div className="relative" ref={langRef}>
          <button
            onClick={() => setLangOpen((p) => !p)}
            className="h-9 px-3 rounded-lg flex items-center justify-center
                       bg-white/80 dark:bg-forest-900/80 backdrop-blur
                       border border-forest-200 dark:border-forest-700
                       text-forest-700 dark:text-forest-300
                       hover:bg-white dark:hover:bg-forest-800
                       text-xs font-bold transition-colors"
            aria-label={t('lang.label')}
          >
            {LANG_LABELS[lang]}
          </button>
          {langOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setLangOpen(false)} />
              <div className="absolute right-0 top-full mt-1 bg-white dark:bg-forest-900 border border-forest-100 dark:border-forest-700 rounded-xl shadow-card-lg p-1 min-w-[120px] z-50">
                {(['en', 'hi', 'gu', 'bn'] as Lang[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => { setLang(l); setLangOpen(false); }}
                    className={`w-full text-left px-3 py-2 text-xs rounded-lg transition-colors font-medium ${
                      l === lang
                        ? 'bg-forest-100 dark:bg-forest-800 text-forest-900 dark:text-white'
                        : 'text-forest-700 dark:text-forest-300 hover:bg-forest-50 dark:hover:bg-forest-800'
                    }`}
                  >
                    {LANG_FULL_NAMES[l]}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Brand ── */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-forest-700 rounded-2xl mb-4 shadow-card-lg">
          <svg className="w-8 h-8 text-white" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
          </svg>
        </div>
        <h1 className="font-display text-2xl font-bold text-forest-900 dark:text-white">
          {t('auth.title')}
        </h1>
        <p className="text-sm text-sage-500 mt-1">{t('auth.subtitle')}</p>
      </div>

      <div className="w-full max-w-sm">

        {/* ── Mode tabs ── */}
        <div className="flex rounded-xl bg-white dark:bg-forest-900 border border-forest-100 dark:border-forest-800 p-1 mb-6 shadow-card">
          <button
            onClick={() => { setMode('password'); setError(''); }}
            className={`flex-1 rounded-lg py-2 text-xs font-semibold transition-colors ${
              mode === 'password'
                ? 'bg-forest-700 text-white'
                : 'text-sage-500 hover:text-forest-700 dark:hover:text-forest-300'
            }`}
          >
            {t('auth.tab.password')}
          </button>
          <button
            onClick={() => { setMode('otp-phone'); setError(''); }}
            className={`flex-1 rounded-lg py-2 text-xs font-semibold transition-colors ${
              mode === 'otp-phone' || mode === 'otp-code'
                ? 'bg-forest-700 text-white'
                : 'text-sage-500 hover:text-forest-700 dark:hover:text-forest-300'
            }`}
          >
            {t('auth.tab.otp')}
          </button>
        </div>

        <div className="card p-6 space-y-4 shadow-card-lg">

          {/* Password login */}
          {mode === 'password' && (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              <div>
                <label className="label">{t('auth.email')}</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="rep@syngenta.com"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="label">{t('auth.password')}</label>
                <input
                  type="password"
                  className="input-field"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </div>
              {error && (
                <p className="text-xs text-clay-600 font-medium bg-clay-50 dark:bg-clay-900/30 rounded-xl px-4 py-3">
                  {error}
                </p>
              )}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? t('auth.signing_in') : t('auth.signin')}
              </button>
            </form>
          )}
          {/* Password + 2FA — OTP entry */}
          {mode === 'password-2fa' && (
            <form onSubmit={handle2faVerify} className="space-y-4">
              <div className="bg-forest-50 dark:bg-forest-900 rounded-xl px-4 py-3 flex items-center gap-3">
                <svg className="w-4 h-4 text-forest-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 12a4 4 0 10-8 0v4a4 4 0 008 0V12zm-4-9C5.373 3 0 8.373 0 15s5.373 12 12 12 12-5.373 12-12S18.627 3 12 3z" />
                </svg>
                <div>
                  <p className="text-xs font-medium text-forest-800 dark:text-forest-200">
                    {t('auth.2fa.sent_to')} {twoFaEmailMasked}
                  </p>
                  <button type="button" onClick={cancel2fa} className="text-xs text-forest-600 underline">
                    {t('auth.2fa.use_different')}
                  </button>
                </div>
              </div>
              <div>
                <label className="label">{t('auth.2fa.enter_code')}</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  className="input-field text-center text-lg tracking-[0.4em] font-bold"
                  placeholder="------"
                  value={twoFaCode}
                  onChange={(e) => setTwoFaCode(e.target.value.replace(/\D/g, ''))}
                  required
                  autoFocus
                />
                {twoFaDevOtp && (
                  <p className="text-xs text-harvest-600 font-medium mt-1 bg-harvest-50 rounded-lg px-3 py-2">
                    {t('auth.2fa.dev_hint')} {twoFaDevOtp}
                  </p>
                )}
              </div>
              {error && <p className="text-xs text-clay-600 font-medium bg-clay-50 rounded-xl px-4 py-3">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? t('auth.2fa.verifying') : t('auth.2fa.verify')}
              </button>
            </form>
          )}

          {/* OTP — phone entry */}
          {mode === 'otp-phone' && (
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <label className="label">{t('auth.phone')}</label>
                <input
                  type="tel"
                  className="input-field"
                  placeholder="9999999999"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
              </div>
              {error && (
                <p className="text-xs text-clay-600 font-medium bg-clay-50 dark:bg-clay-900/30 rounded-xl px-4 py-3">
                  {error}
                </p>
              )}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? t('auth.sending_otp') : t('auth.send_otp')}
              </button>
            </form>
          )}

          {/* OTP — code entry */}
          {mode === 'otp-code' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="bg-forest-50 dark:bg-dm-raised rounded-xl px-4 py-3 flex items-center gap-3">
                <svg className="w-4 h-4 text-forest-600 dark:text-forest-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <div>
                  <p className="text-xs font-medium text-forest-800 dark:text-forest-200">OTP → {phone}</p>
                  <button type="button" onClick={() => setMode('otp-phone')} className="text-xs text-forest-600 dark:text-forest-400 underline">
                    {t('auth.phone')}
                  </button>
                </div>
              </div>
              <div>
                <label className="label">{t('auth.enter_otp')}</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  className="input-field text-center text-lg tracking-[0.4em] font-bold"
                  placeholder="------"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  required
                />
                {devOtp && (
                  <p className="text-xs text-harvest-600 font-medium mt-1 bg-harvest-50 dark:bg-dm-raised rounded-lg px-3 py-2">
                    DEV MODE — OTP: {devOtp}
                  </p>
                )}
              </div>
              {error && (
                <p className="text-xs text-clay-600 font-medium bg-clay-50 dark:bg-clay-900/30 rounded-xl px-4 py-3">
                  {error}
                </p>
              )}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? t('auth.verifying') : t('auth.verify_otp')}
              </button>
            </form>
          )}

          {/* Divider */}
          <div className="flex items-center gap-3 py-1">
            <div className="flex-1 h-px bg-forest-100 dark:bg-dm-border" />
            <span className="text-xs text-sage-400 font-medium">or</span>
            <div className="flex-1 h-px bg-forest-100 dark:bg-dm-border" />
          </div>

          {/* Google Sign-In */}
          <div id="google-btn" className="w-full flex justify-center" />

          {/* Register link */}
          <p className="text-center text-xs text-sage-500 pt-2">
            {t('auth.new_account')}{' '}
            <Link to="/register" className="text-forest-700 dark:text-forest-300 font-semibold hover:underline">
              {t('auth.register')}
            </Link>
          </p>
        </div>

        {/* Demo credentials */}
        <div className="mt-4 card p-4 border-parchment-300 bg-parchment-50 dark:bg-dm-surface dark:border-dm-border">
          <p className="text-xs font-semibold text-forest-800 dark:text-forest-300 mb-2">
            {t('auth.demo')}
          </p>
          <div className="space-y-1">
            <p className="text-xs text-sage-600 dark:text-dm-subtle">
              <span className="font-medium text-forest-700 dark:text-forest-400">Rep:</span> rep@syngenta.com / syngenta123
            </p>
            <p className="text-xs text-sage-600 dark:text-dm-subtle">
              <span className="font-medium text-forest-700 dark:text-forest-400">Manager:</span> manager@syngenta.com / manager123
            </p>
            <p className="text-xs text-sage-600 dark:text-dm-subtle">
              <span className="font-medium text-forest-700 dark:text-forest-400">OTP:</span> 9999999999
            </p>
          </div>
        </div>

      </div>
    </div>
  );
}