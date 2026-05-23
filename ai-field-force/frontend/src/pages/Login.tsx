import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { loginWithPassword, sendOtp, verifyOtp, loginWithGoogle } from '../api/auth';
import { getErrorMessage } from '../api/client';

type LoginMode = 'password' | 'otp-phone' | 'otp-code';

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

  const [mode, setMode] = useState<LoginMode>('password');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [devOtp, setDevOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Redirect if already logged in
  useEffect(() => {
    if (rep) {
      navigate(rep.role === 'rep' ? '/today' : '/manager', { replace: true });
    }
  }, [rep, navigate]);

  // Initialize Google Sign-In
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
      login(res.access_token, res.rep);
      navigate(res.rep.role === 'rep' ? '/today' : '/manager', { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleSendOtp(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await sendOtp(phone);
      if (res.dev_otp) {
        setDevOtp(res.dev_otp);
        setOtp(res.dev_otp); // auto-fill in dev mode
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
    <div className="min-h-screen bg-forest-50 flex flex-col items-center justify-center px-4 py-10">
      {/* Logo / brand */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-forest-700 rounded-2xl mb-4 shadow-card-lg">
          <svg className="w-8 h-8 text-white" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
          </svg>
        </div>
        <h1 className="font-display text-2xl font-bold text-forest-900">Field Force Intelligence</h1>
        <p className="text-sm text-sage-500 mt-1">Syngenta Field Force Intelligence</p>
      </div>

      <div className="w-full max-w-sm">
        {/* Mode tabs */}
        <div className="flex rounded-xl bg-white border border-forest-100 p-1 mb-6 shadow-card">
          <button
            onClick={() => { setMode('password'); setError(''); }}
            className={`flex-1 rounded-lg py-2 text-xs font-semibold transition-colors ${
              mode === 'password' ? 'bg-forest-700 text-white' : 'text-sage-500 hover:text-forest-700'
            }`}
          >
            Email / Password
          </button>
          <button
            onClick={() => { setMode('otp-phone'); setError(''); }}
            className={`flex-1 rounded-lg py-2 text-xs font-semibold transition-colors ${
              mode === 'otp-phone' || mode === 'otp-code' ? 'bg-forest-700 text-white' : 'text-sage-500 hover:text-forest-700'
            }`}
          >
            Phone OTP
          </button>
        </div>

        <div className="card p-6 space-y-4 shadow-card-lg">
          {/* Password login */}
          {mode === 'password' && (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              <div>
                <label className="label">Email or Phone</label>
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
                <label className="label">Password</label>
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
              {error && <p className="text-xs text-clay-600 font-medium bg-clay-50 rounded-xl px-4 py-3">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          )}

          {/* OTP — phone entry */}
          {mode === 'otp-phone' && (
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <label className="label">Phone Number</label>
                <input
                  type="tel"
                  className="input-field"
                  placeholder="9999999999"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
                <p className="text-xs text-sage-400 mt-1">Enter 10-digit mobile number</p>
              </div>
              {error && <p className="text-xs text-clay-600 font-medium bg-clay-50 rounded-xl px-4 py-3">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Sending OTP...' : 'Send OTP'}
              </button>
            </form>
          )}

          {/* OTP — code entry */}
          {mode === 'otp-code' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="bg-forest-50 rounded-xl px-4 py-3 flex items-center gap-3">
                <svg className="w-4 h-4 text-forest-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <div>
                  <p className="text-xs font-medium text-forest-800">OTP sent to {phone}</p>
                  <button type="button" onClick={() => setMode('otp-phone')} className="text-xs text-forest-600 underline">
                    Change number
                  </button>
                </div>
              </div>
              <div>
                <label className="label">Enter OTP</label>
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
                  <p className="text-xs text-harvest-600 font-medium mt-1 bg-harvest-50 rounded-lg px-3 py-2">
                    DEV MODE — OTP auto-filled: {devOtp}
                  </p>
                )}
              </div>
              {error && <p className="text-xs text-clay-600 font-medium bg-clay-50 rounded-xl px-4 py-3">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Verifying...' : 'Verify OTP'}
              </button>
            </form>
          )}

          {/* Divider */}
          <div className="flex items-center gap-3 py-1">
            <div className="flex-1 h-px bg-forest-100" />
            <span className="text-xs text-sage-400 font-medium">or</span>
            <div className="flex-1 h-px bg-forest-100" />
          </div>

          {/* Google Sign-In */}
          <div id="google-btn" className="w-full flex justify-center" />

          {/* Register link */}
          <p className="text-center text-xs text-sage-500 pt-2">
            New account?{' '}
            <Link to="/register" className="text-forest-700 font-semibold hover:underline">
              Register with password
            </Link>
          </p>
        </div>

        {/* Demo credentials */}
        <div className="mt-4 card p-4 border-parchment-300 bg-parchment-50">
          <p className="text-xs font-semibold text-forest-800 mb-2">Demo credentials</p>
          <div className="space-y-1">
            <p className="text-xs text-sage-600"><span className="font-medium text-forest-700">Rep:</span> rep@syngenta.com / syngenta123</p>
            <p className="text-xs text-sage-600"><span className="font-medium text-forest-700">Manager:</span> manager@syngenta.com / manager123</p>
            <p className="text-xs text-sage-600"><span className="font-medium text-forest-700">OTP phone:</span> 9999999999</p>
          </div>
        </div>
      </div>
    </div>
  );
}
