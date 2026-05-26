import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { verifyEmailToken } from '../api/auth';
import { useLang } from '../context/LangContext';

type VerifyState = 'loading' | 'success' | 'error';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const [state, setState] = useState<VerifyState>('loading');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setState('error');
      return;
    }

    verifyEmailToken(token)
      .then(() => {
        setState('success');
        setTimeout(() => navigate('/login', { replace: true }), 3000);
      })
      .catch(() => setState('error'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-forest-50 dark:bg-forest-950 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-forest-900 rounded-2xl shadow-card-lg p-8 max-w-sm w-full text-center">
        {/* Logo */}
        <div className="w-10 h-10 bg-forest-700 rounded-xl flex items-center justify-center mx-auto mb-6">
          <svg className="w-5 h-5 text-white" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
          </svg>
        </div>

        {state === 'loading' && (
          <>
            <div className="w-8 h-8 border-2 border-forest-700 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-forest-600 dark:text-forest-300">{t('auth.verify.loading')}</p>
          </>
        )}

        {state === 'success' && (
          <>
            <div className="w-12 h-12 bg-forest-100 dark:bg-forest-800 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-forest-600 dark:text-forest-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-lg font-bold text-forest-900 dark:text-white mb-2">{t('auth.verify.success')}</h1>
          </>
        )}

        {state === 'error' && (
          <>
            <div className="w-12 h-12 bg-clay-100 dark:bg-clay-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-clay-600 dark:text-clay-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-lg font-bold text-forest-900 dark:text-white mb-2">{t('auth.verify.error')}</h1>
            <Link
              to="/login"
              className="inline-block mt-4 text-sm font-semibold text-forest-700 dark:text-forest-300 underline hover:no-underline"
            >
              {t('auth.verify.return_to_login')}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}   