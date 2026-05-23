import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LangContext';
import { registerWithPassword } from '../api/auth';
import { getErrorMessage } from '../api/client';

export default function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { t } = useLang();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    setLoading(true);
    try {
      const res = await registerWithPassword(name, email, phone, password);
      login(res.access_token, res.rep);
      navigate(res.rep.role === 'rep' ? '/today' : '/manager', { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-forest-50 dark:bg-forest-950 flex flex-col items-center justify-center px-4 py-10">
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-forest-700 rounded-2xl mb-4 shadow-card-lg">
          <svg className="w-8 h-8 text-white" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
          </svg>
        </div>
        <h1 className="font-display text-2xl font-bold text-forest-900 dark:text-white">{t('register.title')}</h1>
        <p className="text-sm text-sage-500 mt-1">{t('auth.title')}</p>
      </div>

      <div className="w-full max-w-sm card p-6 shadow-card-lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">{t('register.name')}</label>
            <input
              type="text"
              className="input-field"
              placeholder="Ramesh Kumar"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">{t('register.email')}</label>
            <input
              type="email"
              className="input-field"
              placeholder="you@syngenta.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div>
            <label className="label">{t('register.phone')}</label>
            <input
              type="tel"
              className="input-field"
              placeholder="9876543210"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div>
            <label className="label">{t('register.password')}</label>
            <input
              type="password"
              className="input-field"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="label">{t('register.confirm')}</label>
            <input
              type="password"
              className="input-field"
              placeholder="••••••••"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>

          {error && <p className="text-xs text-clay-600 font-medium bg-clay-50 rounded-xl px-4 py-3">{error}</p>}

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? t('register.creating') : t('register.submit')}
          </button>

          <p className="text-center text-xs text-sage-500">
            {t('register.have_account')}{' '}
            <Link to="/login" className="text-forest-700 dark:text-forest-300 font-semibold hover:underline">
              {t('register.login')}
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}