import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useOfflineQueue } from '../hooks/useOfflineQueue';
import { useTheme } from '../context/ThemeContext';
import { useLang, LANG_LABELS, LANG_FULL_NAMES, type Lang } from '../context/LangContext';

interface HeaderProps {
  title?: string;
  showBack?: boolean;
}

export default function Header({ title, showBack }: HeaderProps) {
  const { rep, logout } = useAuth();
  const navigate = useNavigate();
  const { pendingCount, syncing, sync } = useOfflineQueue();
  const { theme, toggle: toggleTheme } = useTheme();
  const { lang, setLang, t } = useLang();
  const [menuOpen, setMenuOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const langRef = useRef<HTMLDivElement>(null);
  const isManager = rep?.role === 'manager' || rep?.role === 'admin';

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
      if (langRef.current && !langRef.current.contains(e.target as Node)) {
        setLangOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="bg-white dark:bg-forest-950 border-b border-forest-100 dark:border-forest-800 sticky top-0 z-40">
      <div className="max-w-2xl mx-auto px-4">
        <div className="flex items-center h-14 gap-3">
          {showBack ? (
            <button
              onClick={() => navigate(-1)}
              className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-forest-50 dark:hover:bg-forest-800 text-forest-600 dark:text-forest-300 transition-colors"
              aria-label="Go back"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          ) : (
            <Link to={isManager ? '/manager' : '/today'} className="flex items-center gap-2 shrink-0">
              <div className="w-7 h-7 bg-forest-700 rounded-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
                </svg>
              </div>
              <span className="text-sm font-bold text-forest-900 dark:text-white hidden sm:block font-display">FFI</span>
            </Link>
          )}

          <div className="flex-1 min-w-0">
            {title ? (
              <h1 className="text-sm font-semibold text-forest-900 dark:text-white truncate">{title}</h1>
            ) : (
              <nav className="flex gap-1">
                {isManager ? (
                  <>
                    <Link to="/manager" className="btn-ghost text-xs py-1.5 px-3 dark:text-forest-300">{t('nav.overview')}</Link>
                    <Link to="/manager/reps" className="btn-ghost text-xs py-1.5 px-3 dark:text-forest-300">{t('nav.reps')}</Link>
                    <Link to="/manager/weights" className="btn-ghost text-xs py-1.5 px-3 dark:text-forest-300">Learning Trail</Link>
                  </>
                ) : (
                  <>
                    <Link to="/today" className="btn-ghost text-xs py-1.5 px-3 dark:text-forest-300">{t('nav.priorities')}</Link>
                    <Link to="/anomalies" className="btn-ghost text-xs py-1.5 px-3 dark:text-forest-300">{t('nav.alerts')}</Link>
                    <Link to="/devices" className="btn-ghost text-xs py-1.5 px-3 dark:text-forest-300">{t('nav.devices')}</Link>
                  </>
                )}
              </nav>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Offline sync badge */}
            {pendingCount > 0 && (
              <button
                onClick={sync}
                disabled={syncing}
                className="flex items-center gap-1.5 bg-harvest-100 text-harvest-700 rounded-lg px-2.5 py-1.5 text-xs font-semibold hover:bg-harvest-200 transition-colors disabled:opacity-60"
                title={t('sync.now')}
              >
                {syncing ? (
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <span className="w-2 h-2 rounded-full bg-harvest-500 animate-pulse" />
                )}
                {pendingCount} {t('sync.pending')}
              </button>
            )}

            {/* Language picker */}
            <div className="relative" ref={langRef}>
              <button
                onClick={() => setLangOpen((p) => !p)}
                className="h-8 px-2.5 rounded-lg flex items-center justify-center hover:bg-forest-50 dark:hover:bg-forest-800 text-forest-600 dark:text-forest-300 text-xs font-bold transition-colors border border-forest-200 dark:border-forest-700"
                aria-label={t('lang.label')}
                title={t('lang.label')}
              >
                {LANG_LABELS[lang]}
              </button>
              {langOpen && (
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
              )}
            </div>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-forest-50 dark:hover:bg-forest-800 text-forest-600 dark:text-forest-300 transition-colors"
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            >
              {theme === 'dark' ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>

            {/* User avatar / logout */}
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((p) => !p)}
                className="w-8 h-8 rounded-full bg-forest-700 text-white text-xs font-bold flex items-center justify-center"
              >
                {rep?.name?.charAt(0).toUpperCase() ?? 'U'}
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-full mt-1 bg-white dark:bg-forest-900 border border-forest-100 dark:border-forest-700 rounded-xl shadow-card-lg p-1 min-w-[140px] z-50">
                  <div className="px-3 py-2 border-b border-forest-50 dark:border-forest-800">
                    <div className="text-xs font-semibold text-forest-900 dark:text-white truncate">{rep?.name}</div>
                    <div className="text-xs text-sage-500 capitalize">{rep?.role}</div>
                  </div>
                  <button
                    onClick={() => { setMenuOpen(false); logout(); }}
                    className="w-full text-left px-3 py-2 text-xs text-clay-600 hover:bg-clay-50 dark:hover:bg-clay-900 rounded-lg transition-colors font-medium"
                  >
                    {t('nav.signout')}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}