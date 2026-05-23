import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../../components/Layout';
import { getAnomalies } from '../../api/signals';
import { useLang } from '../../context/LangContext';
import type { Anomaly, AnomalySeverity } from '../../types';

export default function Anomalies() {
  const { t, lang } = useLang();
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<AnomalySeverity | 'all'>('all');

  useEffect(() => {
    setLoading(true);
    getAnomalies()
      .then(setAnomalies)
      .catch(() => setError('Failed to load anomalies.'))
      .finally(() => setLoading(false));
  }, [lang]);

  function severityConfig(s: AnomalySeverity) {
    switch (s) {
      case 'high':   return { label: t('anomaly.high'),   dotColor: 'bg-clay-500',    badge: 'badge-red',    card: 'border-clay-100 bg-clay-50' };
      case 'medium': return { label: t('anomaly.medium'), dotColor: 'bg-harvest-500', badge: 'badge-yellow', card: 'border-harvest-100 bg-harvest-50' };
      case 'low':    return { label: t('anomaly.low'),    dotColor: 'bg-forest-400',  badge: 'badge-green',  card: 'border-forest-100 bg-forest-50' };
    }
  }

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const hours = Math.floor(diff / 3_600_000);
    const days = Math.floor(diff / 86_400_000);
    if (days > 0) return `${days}d ${t('time.ago')}`;
    if (hours > 0) return `${hours}h ${t('time.ago')}`;
    return t('time.just_now');
  }

  // Translate the anomaly message code; fall back to humanized if missing
  function translateMessage(raw: string): string {
    if (!raw) return '';
    if (raw.startsWith('anomaly.') || raw.startsWith('reason.') || raw.startsWith('override.') || raw.startsWith('nba.')) {
      const looked = t(raw);
      if (looked !== raw) return looked;
    }
    const asAnomaly = t('anomaly.' + raw);
    if (asAnomaly !== 'anomaly.' + raw) return asAnomaly;
    return raw;
  }

  const filtered = filter === 'all' ? anomalies : anomalies.filter((a) => a.severity === filter);
  const highCount = anomalies.filter((a) => a.severity === 'high').length;
  const midCount = anomalies.filter((a) => a.severity === 'medium').length;

  return (
    <Layout>
      <div className="mb-5">
        <h1 className="page-header">{t('anomaly.title')}</h1>
        <p className="text-sm text-sage-500 mt-1">
          {anomalies.length > 0
            ? `${anomalies.length} ${t('anomaly.detected')}`
            : loading
            ? t('anomaly.scanning')
            : t('anomaly.none')}
        </p>
      </div>

      {!loading && anomalies.length > 0 && (
        <div className="flex gap-2 mb-4 flex-wrap">
          {highCount > 0 && (
            <span className="badge-red">
              <span className="w-1.5 h-1.5 rounded-full bg-clay-500 mr-1" />
              {highCount} {t('anomaly.high')}
            </span>
          )}
          {midCount > 0 && (
            <span className="badge-yellow">
              <span className="w-1.5 h-1.5 rounded-full bg-harvest-500 mr-1" />
              {midCount} {t('anomaly.medium')}
            </span>
          )}
        </div>
      )}

      {!loading && anomalies.length > 0 && (
        <div className="flex gap-1 bg-white border border-forest-100 rounded-xl p-1 mb-5 shadow-card">
          {(['all', 'high', 'medium', 'low'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`flex-1 rounded-lg py-1.5 text-xs font-semibold capitalize transition-colors ${
                filter === f ? 'bg-forest-700 text-white' : 'text-sage-500 hover:text-forest-700'
              }`}
            >
              {f === 'all' ? `${t('anomaly.all')} (${anomalies.length})` : t('anomaly.' + f)}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="space-y-3 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-4">
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-lg bg-sage-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-sage-100 rounded w-1/2" />
                  <div className="h-3 bg-sage-100 rounded w-3/4" />
                  <div className="h-3 bg-sage-100 rounded w-1/2" />
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
          {filtered.map((anomaly, i) => {
            const sev = severityConfig(anomaly.severity);
            return (
              <Link
                key={`${anomaly.entity_id}-${i}`}
                to={`/grower/${anomaly.entity_id}`}
                className={`block card-hover p-4 border ${sev.card}`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-1">
                    <span className={`inline-block w-2.5 h-2.5 rounded-full ${sev.dotColor}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-semibold text-sm text-forest-900">{anomaly.name}</span>
                      <span className={sev.badge}>{sev.label}</span>
                    </div>
                    <p className="text-xs font-medium text-forest-700 mb-1">{anomaly.anomaly_type}</p>
                    <p className="text-xs text-sage-600 leading-relaxed">{translateMessage(anomaly.description)}</p>
                    <div className="flex items-center gap-3 mt-2">
                      {anomaly.region && (
                        <span className="text-[11px] text-sage-400">{anomaly.region}</span>
                      )}
                      <span className="text-[11px] text-sage-400">{timeAgo(anomaly.detected_at)}</span>
                    </div>
                  </div>
                  <svg className="w-4 h-4 text-sage-300 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            );
          })}

          {filtered.length === 0 && !loading && (
            <div className="card p-8 text-center">
              <p className="text-sm font-medium text-sage-500">{t('anomaly.no_filter')}</p>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}