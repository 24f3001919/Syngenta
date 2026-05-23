import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../../components/Layout';
import { getRepDetails } from '../../api/manager';
import { useLang } from '../../context/LangContext';
import type { RepDetails, OutcomeType, AnomalySeverity } from '../../types';

function severityDot(s: AnomalySeverity) {
  switch (s) {
    case 'high':   return 'bg-clay-500';
    case 'medium': return 'bg-harvest-400';
    case 'low':    return 'bg-forest-400';
  }
}

function Stars({ value }: { value: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <svg
          key={s}
          className={`w-3 h-3 ${s <= value ? 'text-harvest-400' : 'text-sage-200'}`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </div>
  );
}

type Tab = 'priorities' | 'outcomes' | 'anomalies';

export default function RepDetail() {
  const { rep_id } = useParams<{ rep_id: string }>();
  const navigate = useNavigate();
  const { t, lang } = useLang();
  const [details, setDetails] = useState<RepDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('priorities');

  const OUTCOME_LABELS: Record<OutcomeType, { label: string; style: string }> = {
    sale:               { label: t('outcome.sale'),         style: 'badge-green' },
    follow_up_needed:   { label: t('outcome.follow_up'),    style: 'badge-yellow' },
    no_interest:        { label: t('outcome.no_interest'),  style: 'badge-gray' },
    complaint:          { label: t('outcome.complaint'),    style: 'badge-red' },
    complaint_resolved: { label: t('outcome.complaint') + ' ✓', style: 'badge-green' }
  };

  function translateReason(raw: string): string {
    if (!raw) return '';
    if (raw.startsWith('reason.') || raw.startsWith('anomaly.') || raw.startsWith('nba.') || raw.startsWith('override.')) {
      const looked = t(raw);
      if (looked !== raw) return looked;
    }
    const asReason = t('reason.' + raw);
    if (asReason !== 'reason.' + raw) return asReason;
    const asAnomaly = t('anomaly.' + raw);
    if (asAnomaly !== 'anomaly.' + raw) return asAnomaly;
    const asOverride = t('override.' + raw);
    if (asOverride !== 'override.' + raw) return asOverride;
    return raw;
  }

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / 86_400_000);
    const hours = Math.floor(diff / 3_600_000);
    if (days > 0) return `${days}d ${t('time.ago')}`;
    if (hours > 0) return `${hours}h ${t('time.ago')}`;
    return t('time.just_now');
  }

  useEffect(() => {
    if (!rep_id) return;
    setLoading(true);
    getRepDetails(rep_id)
      .then(setDetails)
      .catch(() => setError('Failed to load rep details.'))
      .finally(() => setLoading(false));
  }, [rep_id, lang]);

  const tabLabels: Record<Tab, string> = {
    priorities: t('rep.priorities'),
    outcomes:   t('rep.outcomes'),
    anomalies:  t('rep.anomalies'),
  };

  if (loading) {
    return (
      <Layout title={t('reps.title')} showBack>
        <div className="space-y-4 animate-pulse">
          <div className="card p-5 h-24" />
          <div className="card p-5 h-10" />
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => <div key={i} className="card h-16" />)}
          </div>
        </div>
      </Layout>
    );
  }

  if (error || !details) {
    return (
      <Layout title={t('reps.title')} showBack>
        <div className="card p-6 text-center border-clay-100 bg-clay-50">
          <p className="text-sm font-medium text-clay-700">{error || 'Rep not found.'}</p>
          <button onClick={() => navigate(-1)} className="mt-3 btn-secondary text-xs">{t('grower.go_back')}</button>
        </div>
      </Layout>
    );
  }

  const { rep, priorities, recent_outcomes, anomalies } = details;

  return (
    <Layout title={rep.name} showBack>
      <div className="card p-5 mb-4">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-forest-100 flex items-center justify-center shrink-0">
            <span className="text-forest-700 font-bold text-2xl font-display">
              {rep.name.charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <h2 className="font-display text-xl font-bold text-forest-900">{rep.name}</h2>
            <p className="text-xs text-sage-500 mt-0.5">{rep.email}</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-forest-50">
          <div className="text-center">
            <p className="text-xl font-bold font-display text-forest-800">{rep.outcomes_last_30d}</p>
            <p className="text-[10px] text-sage-400 font-semibold uppercase tracking-wide mt-0.5">{t('reps.outcomes')}</p>
          </div>
          <div className="text-center border-x border-forest-50">
            <p className="text-xl font-bold font-display text-forest-800">{rep.avg_rating.toFixed(1)}</p>
            <p className="text-[10px] text-sage-400 font-semibold uppercase tracking-wide mt-0.5">{t('reps.avg_rating')}</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-bold font-display text-forest-800">{rep.total_growers}</p>
            <p className="text-[10px] text-sage-400 font-semibold uppercase tracking-wide mt-0.5">{t('reps.growers')}</p>
          </div>
        </div>
      </div>

      <div className="flex gap-1 bg-white border border-forest-100 rounded-xl p-1 mb-5 shadow-card">
        {(['priorities', 'outcomes', 'anomalies'] as Tab[]).map((tk) => {
          const counts: Record<Tab, number> = {
            priorities: priorities.length,
            outcomes: recent_outcomes.length,
            anomalies: anomalies.length,
          };
          return (
            <button
              key={tk}
              onClick={() => setTab(tk)}
              className={`flex-1 rounded-lg py-2 text-xs font-semibold capitalize transition-colors ${
                tab === tk ? 'bg-forest-700 text-white' : 'text-sage-500 hover:text-forest-700'
              }`}
            >
              {tabLabels[tk]}
              {counts[tk] > 0 && (
                <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                  tab === tk ? 'bg-forest-600 text-white' : 'bg-sage-100 text-sage-500'
                }`}>
                  {counts[tk]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === 'priorities' && (
        <div className="space-y-3">
          {priorities.length === 0 && (
            <div className="card p-8 text-center">
              <p className="text-sm text-sage-500">{t('rep.no_priorities')}</p>
            </div>
          )}
          {priorities.map((g) => (
            <div key={g.entity_id} className="card p-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-forest-50 border border-forest-100 flex items-center justify-center shrink-0">
                  <span className="text-xs font-bold text-forest-600">#{g.rank}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm text-forest-900 truncate">{g.name}</p>
                  <p className="text-xs text-sage-500">{g.region}</p>
                  {g.reasons.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {g.reasons.slice(0, 2).map((r, i) => (
                        <span key={i} className="badge-gray text-xs">{translateReason(r)}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <p className={`text-lg font-bold font-display ${
                    g.vps_score >= 80 ? 'text-clay-600' : g.vps_score >= 60 ? 'text-harvest-600' : 'text-forest-600'
                  }`}>
                    {Math.round(g.vps_score)}
                  </p>
                  <p className="text-[10px] text-sage-400 font-semibold uppercase">VPS</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'outcomes' && (
        <div className="space-y-3">
          {recent_outcomes.length === 0 && (
            <div className="card p-8 text-center">
              <p className="text-sm text-sage-500">{t('rep.no_outcomes')}</p>
            </div>
          )}
          {recent_outcomes.map((o) => {
            const otype = OUTCOME_LABELS[o.outcome_type];
            return (
              <div key={o.id} className="card p-4">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="font-semibold text-sm text-forest-900 truncate">{o.entity_name}</span>
                      <span className={otype.style}>{otype.label}</span>
                    </div>
                    <Stars value={o.rating} />
                    {o.notes && (
                      <p className="text-xs text-sage-500 mt-1.5 line-clamp-2">{o.notes}</p>
                    )}
                  </div>
                  <span className="text-xs text-sage-400 shrink-0 mt-0.5">{timeAgo(o.visited_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === 'anomalies' && (
        <div className="space-y-3">
          {anomalies.length === 0 && (
            <div className="card p-8 text-center">
              <svg className="w-8 h-8 text-sage-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-sage-500">{t('rep.no_anomalies')}</p>
            </div>
          )}
          {anomalies.map((a, i) => (
            <div key={`${a.entity_id}-${i}`} className="card p-4">
              <div className="flex items-start gap-3">
                <span className={`mt-1.5 inline-block w-2.5 h-2.5 rounded-full shrink-0 ${severityDot(a.severity)}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="font-semibold text-sm text-forest-900">{a.name}</span>
                    <span className="text-xs font-medium text-sage-500 capitalize">{t('anomaly.' + a.severity)}</span>
                  </div>
                  <p className="text-xs font-medium text-forest-700 mb-0.5">{a.anomaly_type}</p>
                  <p className="text-xs text-sage-500 leading-relaxed">{translateReason(a.description)}</p>
                  <p className="text-[11px] text-sage-400 mt-1">{timeAgo(a.detected_at)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}