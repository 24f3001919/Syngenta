import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../../components/Layout';
import HealthScoreCard from '../../components/HealthScoreCard';
import MetricCard from '../../components/MetricCard';
import { getManagerOverview, getTopPriorities } from '../../api/manager';
import { useLang } from '../../context/LangContext';
import type { ManagerOverview, TopPriority } from '../../types';

function vpsColor(score: number): string {
  if (score >= 80) return 'text-clay-600';
  if (score >= 60) return 'text-harvest-600';
  return 'text-forest-600';
}

export default function Overview() {
  const { t, lang } = useLang();
  const [overview, setOverview] = useState<ManagerOverview | null>(null);
  const [priorities, setPriorities] = useState<TopPriority[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([getManagerOverview(), getTopPriorities(5)])
      .then(([ov, prio]) => { setOverview(ov); setPriorities(prio); })
      .catch(() => setError('Failed to load overview.'))
      .finally(() => setLoading(false));
  }, [lang]);

  const localeMap: Record<string, string> = { en: 'en-IN', hi: 'hi-IN', gu: 'gu-IN', bn: 'bn-IN' };
  const todayStr = new Date().toLocaleDateString(localeMap[lang] ?? 'en-IN', {
    weekday: 'long', day: 'numeric', month: 'long',
  });

  if (loading) {
    return (
      <Layout>
        <div className="mb-5">
          <p className="text-xs text-sage-500 uppercase tracking-wider font-semibold">{todayStr}</p>
          <div className="h-8 bg-sage-100 rounded-xl w-48 mt-2 animate-pulse" />
        </div>
        <div className="space-y-4 animate-pulse">
          <div className="card p-6 h-32" />
          <div className="grid grid-cols-2 gap-3">
            {[...Array(4)].map((_, i) => <div key={i} className="card h-20" />)}
          </div>
        </div>
      </Layout>
    );
  }

  if (error || !overview) {
    return (
      <Layout>
        <div className="card p-6 text-center border-clay-100 bg-clay-50">
          <p className="text-sm font-medium text-clay-700">{error || 'Failed to load.'}</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mb-5">
        <p className="text-xs font-semibold text-sage-500 uppercase tracking-widest mb-1">{todayStr}</p>
        <h1 className="page-header">{t('manager.overview')}</h1>
      </div>

      <div className="mb-4">
        <HealthScoreCard score={overview.territory_health_score} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6">
        <MetricCard
          label={t('manager.total_reps')}
          value={overview.total_reps}
          accent="green"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          }
        />
        <MetricCard
          label={t('manager.growers')}
          value={overview.total_growers}
          accent="sage"
          icon={
            <svg className="w-6 h-6" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
            </svg>
          }
        />
        <MetricCard
          label={t('manager.outcomes_30d')}
          value={overview.outcomes_last_30d}
          accent="harvest"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          }
        />
        <MetricCard
          label={t('manager.avg_rating')}
          value={overview.avg_rating.toFixed(1)}
          sub="/ 5.0"
          accent="green"
          icon={
            <svg className="w-6 h-6" viewBox="0 0 20 20" fill="currentColor">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          }
        />
        {overview.high_priority_count > 0 && (
          <MetricCard
            label={t('manager.high_priority')}
            value={overview.high_priority_count}
            accent="clay"
          />
        )}
      </div>

      {priorities.length > 0 && (
        <div className="card overflow-hidden mb-4">
          <div className="px-4 py-3 border-b border-forest-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-forest-900">{t('manager.top_priorities')}</h2>
            <Link to="/manager/reps" className="text-xs text-forest-600 font-semibold hover:underline">
              {t('manager.view_all')}
            </Link>
          </div>
          <div className="divide-y divide-forest-50">
            {priorities.map((p, idx) => (
              <div key={p.entity_id} className="px-4 py-3 flex items-center gap-3">
                <span className="text-xs font-bold text-sage-400 w-6">#{idx + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-forest-900 truncate">{p.name}</p>
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-sage-500">{p.region}</p>
                    {p.assigned_rep && (
                      <span className="text-xs text-sage-400">· {p.assigned_rep}</span>
                    )}
                  </div>
                </div>
                <span className={`text-base font-bold font-display ${vpsColor(p.vps_score)}`}>
                  {Math.round(p.vps_score)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Layout>
  );
}