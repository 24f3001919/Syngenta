import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../../components/Layout';
import { getManagerReps } from '../../api/manager';
import { useLang } from '../../context/LangContext';
import type { RepMetrics, PerformanceLabel } from '../../types';

function RatingBar({ value }: { value: number }) {
  const pct = Math.min((value / 5) * 100, 100);
  const color = value >= 4 ? 'bg-forest-500' : value >= 3 ? 'bg-harvest-400' : 'bg-clay-400';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-sage-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-forest-800 w-6 text-right">{value.toFixed(1)}</span>
    </div>
  );
}

export default function Reps() {
  const { t } = useLang();
  const [reps, setReps] = useState<RepMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'outcomes' | 'rating'>('outcomes');

  function performanceConfig(label: PerformanceLabel) {
    switch (label) {
      case 'excellent':       return { badge: 'badge-green',  text: t('reps.perf_excellent') };
      case 'good':            return { badge: 'badge-yellow', text: t('reps.perf_good') };
      case 'needs_attention': return { badge: 'badge-red',    text: t('reps.perf_attention') };
    }
  }

  useEffect(() => {
    getManagerReps()
      .then(setReps)
      .catch(() => setError('Failed to load rep data.'))
      .finally(() => setLoading(false));
  }, []);

  const sorted = [...reps].sort((a, b) => {
    if (sortBy === 'name')     return a.name.localeCompare(b.name);
    if (sortBy === 'outcomes') return b.outcomes_last_30d - a.outcomes_last_30d;
    if (sortBy === 'rating')   return b.avg_rating - a.avg_rating;
    return 0;
  });

  const excellentCount = reps.filter((r) => r.performance_label === 'excellent').length;
  const atRiskCount    = reps.filter((r) => r.performance_label === 'needs_attention').length;

  return (
    <Layout>
      <div className="mb-5">
        <h1 className="page-header">{t('reps.title')}</h1>
        <p className="text-sm text-sage-500 mt-1">
          {reps.length > 0 ? `${reps.length} ${t('reps.in_territory')}` : loading ? t('today.loading') : t('reps.none')}
        </p>
      </div>

      {!loading && reps.length > 0 && (
        <div className="flex gap-3 mb-5">
          <div className="flex-1 card px-4 py-3 bg-forest-50 border-forest-100">
            <p className="text-xs text-forest-600 font-semibold uppercase tracking-wide">{t('reps.excellent')}</p>
            <p className="text-xl font-bold font-display text-forest-700">{excellentCount}</p>
          </div>
          <div className="flex-1 card px-4 py-3 bg-sage-50 border-sage-100">
            <p className="text-xs text-sage-600 font-semibold uppercase tracking-wide">{t('reps.total')}</p>
            <p className="text-xl font-bold font-display text-sage-700">{reps.length}</p>
          </div>
          {atRiskCount > 0 && (
            <div className="flex-1 card px-4 py-3 bg-clay-50 border-clay-100">
              <p className="text-xs text-clay-600 font-semibold uppercase tracking-wide">{t('reps.at_risk')}</p>
              <p className="text-xl font-bold font-display text-clay-700">{atRiskCount}</p>
            </div>
          )}
        </div>
      )}

      {!loading && reps.length > 0 && (
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs text-sage-500 font-medium shrink-0">{t('reps.sort_by')}</span>
          <div className="flex gap-1 bg-white border border-forest-100 rounded-xl p-1 shadow-card">
            {(['outcomes', 'rating', 'name'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`rounded-lg px-3 py-1 text-xs font-semibold capitalize transition-colors ${
                  sortBy === s ? 'bg-forest-700 text-white' : 'text-sage-500 hover:text-forest-700'
                }`}
              >
                {s === 'outcomes' ? t('reps.outcomes') : s === 'rating' ? t('reps.rating') : t('reps.name')}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="space-y-3 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-4">
              <div className="flex gap-3">
                <div className="w-10 h-10 rounded-full bg-sage-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-sage-100 rounded w-1/2" />
                  <div className="h-3 bg-sage-100 rounded w-1/3" />
                  <div className="h-2 bg-sage-100 rounded w-full" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="card p-6 text-center border-clay-100 bg-clay-50">
          <p className="text-sm font-medium text-clay-700">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-3">
          {sorted.map((rep) => {
            const perf = performanceConfig(rep.performance_label);
            return (
              <Link
                key={rep.rep_id}
                to={`/manager/reps/${rep.rep_id}`}
                className="block card-hover p-4 group"
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-forest-100 flex items-center justify-center shrink-0">
                    <span className="text-forest-700 font-bold text-sm">
                      {rep.name.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="font-semibold text-sm text-forest-900 truncate">{rep.name}</span>
                      <span className={perf.badge}>{perf.text}</span>
                    </div>
                    <p className="text-xs text-sage-500 truncate mb-2">{rep.email}</p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                      <div>
                        <p className="text-[10px] text-sage-400 font-semibold uppercase tracking-wide mb-0.5">
                          {t('reps.outcomes_30d')}
                        </p>
                        <p className="text-sm font-bold text-forest-800">{rep.outcomes_last_30d}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-sage-400 font-semibold uppercase tracking-wide mb-0.5">
                          {t('reps.growers')}
                        </p>
                        <p className="text-sm font-bold text-forest-800">{rep.total_growers}</p>
                      </div>
                    </div>
                    <div className="mt-2">
                      <p className="text-[10px] text-sage-400 font-semibold uppercase tracking-wide mb-1">
                        {t('reps.avg_rating')}
                      </p>
                      <RatingBar value={rep.avg_rating} />
                    </div>
                  </div>
                  <svg
                    className="w-4 h-4 text-sage-300 group-hover:text-forest-400 transition-colors shrink-0 mt-1"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            );
          })}

          {sorted.length === 0 && (
            <div className="card p-8 text-center">
              <p className="text-sm text-sage-500">{t('reps.none')}</p>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}