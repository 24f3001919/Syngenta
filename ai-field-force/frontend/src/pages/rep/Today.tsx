import { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import PriorityCard from '../../components/PriorityCard';
import { getTodayPriorities } from '../../api/visits';
import type { PriorityGrower } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { useLang } from '../../context/LangContext';

export default function Today() {
  const { rep } = useAuth();
  const { t, lang } = useLang();
  const [growers, setGrowers] = useState<PriorityGrower[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    getTodayPriorities()
      .then(setGrowers)
      .catch(() => setError('Failed to load priorities. Check your connection.'))
      .finally(() => setLoading(false));
  }, [lang]);

  const localeMap: Record<string, string> = { en: 'en-IN', hi: 'hi-IN', gu: 'gu-IN', bn: 'bn-IN' };
  const todayStr = new Date().toLocaleDateString(localeMap[lang] ?? 'en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });

  return (
    <Layout>
      <div className="mb-5 md:mb-8">
        <p className="text-xs font-semibold text-sage-500 uppercase tracking-widest mb-1">{todayStr}</p>
        <h1 className="page-header md:text-3xl">{t('today.greeting')}, {rep?.name?.split(' ')[0]}.</h1>
        <p className="text-sm text-sage-500 mt-1">
          {growers.length > 0
            ? `${growers.length} ${t('today.growers_ranked')}`
            : loading
            ? t('today.loading')
            : t('today.none')}
        </p>
      </div>

      {!loading && growers.length > 0 && (
        <div className="flex gap-3 md:gap-4 mb-5 md:mb-8">
          <div className="flex-1 card px-4 py-3 md:py-5 bg-clay-50 border-clay-100">
            <p className="text-xs text-clay-600 font-semibold uppercase tracking-wide">{t('today.high_priority')}</p>
            <p className="text-xl md:text-3xl font-bold font-display text-clay-700">
              {growers.filter((g) => g.vps_score >= 80).length}
            </p>
          </div>
          <div className="flex-1 card px-4 py-3 md:py-5 bg-harvest-50 border-harvest-100">
            <p className="text-xs text-harvest-600 font-semibold uppercase tracking-wide">{t('today.alerts')}</p>
            <p className="text-xl md:text-3xl font-bold font-display text-harvest-700">
              {growers.reduce((s, g) => s + g.anomaly_count, 0)}
            </p>
          </div>
          <div className="flex-1 card px-4 py-3 md:py-5 bg-forest-50 border-forest-100">
            <p className="text-xs text-forest-600 font-semibold uppercase tracking-wide">{t('today.total')}</p>
            <p className="text-xl md:text-3xl font-bold font-display text-forest-700">{growers.length}</p>
          </div>
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-xl bg-sage-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-sage-100 rounded-md w-1/2" />
                  <div className="h-3 bg-sage-100 rounded-md w-1/3" />
                  <div className="flex gap-2">
                    <div className="h-5 bg-sage-100 rounded-full w-20" />
                    <div className="h-5 bg-sage-100 rounded-full w-16" />
                  </div>
                </div>
                <div className="w-14 h-14 rounded-xl bg-sage-100" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && !loading && (
        <div className="card p-6 text-center border-clay-100 bg-clay-50">
          <svg className="w-8 h-8 text-clay-400 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <p className="text-sm font-medium text-clay-700">{error}</p>
          <button
            onClick={() => { setError(''); setLoading(true); getTodayPriorities().then(setGrowers).catch(() => setError('Failed to load priorities.')).finally(() => setLoading(false)); }}
            className="mt-3 btn-secondary text-xs"
          >
            {t('today.retry')}
          </button>
        </div>
      )}

      {!loading && !error && growers.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
          {growers.map((grower) => (
            <PriorityCard key={grower.entity_id} grower={grower} />
          ))}
        </div>
      )}

      {!loading && !error && growers.length === 0 && (
        <div className="card p-8 text-center">
          <svg className="w-10 h-10 text-sage-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm font-semibold text-forest-900">{t('today.all_done')}</p>
          <p className="text-xs text-sage-500 mt-1">{t('today.no_growers')}</p>
        </div>
      )}
    </Layout>
  );
}