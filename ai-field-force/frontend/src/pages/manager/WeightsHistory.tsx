import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Header from '../../components/Header';
import { useLang } from '../../context/LangContext';
import { getWeightsHistory, type WeightsSnapshot } from '../../api/manager';

function fmt(val: number) {
  return (val * 100).toFixed(1) + '%';
}

function DeltaBadge({ value }: { value: number }) {
  const positive = value > 0;
  const label = (positive ? '+' : '') + (value * 100).toFixed(1) + '%';
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-md ${
        positive
          ? 'bg-forest-50 text-forest-700'
          : 'bg-clay-50 text-clay-600'
      }`}
    >
      {positive ? '▲' : '▼'} {label}
    </span>
  );
}

function SnapshotCard({ snap, index }: { snap: WeightsSnapshot; index: number }) {
  const { t, lang } = useLang();
  const [expanded, setExpanded] = useState(index === 0);

  const SIGNAL_LABELS: Record<string, string> = {
    pest_alert_severity:       t('signal.pest_alert'),
    inventory_shortage_level:  t('signal.inventory_shortage'),
    days_since_last_visit:     t('signal.days_since_visit'),
    weather_risk_score:        t('signal.weather_risk'),
    complaint_open:            t('signal.complaint_open'),
    crop_stage_sensitivity:    t('signal.crop_stage'),
    revenue_potential:         t('signal.revenue_potential'),
    competitor_activity:       t('signal.competitor_activity'),
  };

  const localeMap: Record<string, string> = { en: 'en-IN', hi: 'hi-IN', gu: 'gu-IN', bn: 'bn-IN' };
  const date = new Date(snap.created_at).toLocaleString(localeMap[lang] ?? 'en-IN', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
  const hasDelta = snap.delta && Object.keys(snap.delta).length > 0;
  const isManual = snap.trigger === 'manual_recalibration';

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-forest-50 transition-colors"
      >
        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
          isManual ? 'bg-harvest-100 text-harvest-700' : 'bg-forest-100 text-forest-700'
        }`}>
          #{snap.id}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-forest-900">
              {isManual
                ? t('trail.manual_recalibration')
                : `${t('trail.outcome_label')} #${snap.outcome_id} ${t('trail.logged_suffix')}`}
            </span>
            {hasDelta && (
              <span className="text-xs text-sage-500">
                {Object.keys(snap.delta!).length} {t('trail.signals_shifted')}
              </span>
            )}
          </div>
          <p className="text-xs text-sage-500 mt-0.5">{date}</p>
        </div>
        <svg
          className={`w-4 h-4 text-sage-400 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-forest-50 px-4 py-3 space-y-3">
          {hasDelta && (
            <div>
              <p className="text-xs font-semibold text-sage-500 uppercase tracking-wide mb-2">{t('trail.what_changed')}</p>
              <div className="space-y-1.5">
                {Object.entries(snap.delta!).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-xs text-forest-800">{SIGNAL_LABELS[key] ?? key}</span>
                    <DeltaBadge value={val} />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-xs font-semibold text-sage-500 uppercase tracking-wide mb-2">{t('trail.all_weights')}</p>
            <div className="space-y-2">
              {Object.entries(snap.weights)
                .sort(([, a], [, b]) => b - a)
                .map(([key, val]) => {
                  const deltaVal = snap.delta?.[key];
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-xs text-forest-700">{SIGNAL_LABELS[key] ?? key}</span>
                        <div className="flex items-center gap-2">
                          {deltaVal !== undefined && <DeltaBadge value={deltaVal} />}
                          <span className="text-xs font-semibold text-forest-900">{fmt(val)}</span>
                        </div>
                      </div>
                      <div className="h-1.5 bg-sage-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-forest-600 rounded-full transition-all"
                          style={{ width: `${(val * 100).toFixed(1)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function WeightsHistory() {
  const { t } = useLang();
  const [snapshots, setSnapshots] = useState<WeightsSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getWeightsHistory(20)
      .then(setSnapshots)
      .catch(() => setError('Failed to load weights history.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-forest-50 dark:bg-forest-950">
      <Header title={t('trail.title')} showBack />
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
        <div className="card px-4 py-3">
          <p className="text-sm text-forest-800 dark:text-forest-200 font-semibold">{t('trail.how_learns')}</p>
          <p className="text-xs text-sage-500 mt-0.5">{t('trail.intro')}</p>
        </div>

        <div className="flex justify-end">
          <Link to="/manager" className="text-xs text-forest-600 dark:text-forest-300 font-semibold hover:underline">
            {t('trail.back_to_overview')}
          </Link>
        </div>

        {loading && (
          <div className="space-y-3 animate-pulse">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="card p-4 h-16" />
            ))}
          </div>
        )}

        {error && (
          <div className="card p-6 text-center border-clay-100 bg-clay-50">
            <p className="text-sm font-medium text-clay-700">{error}</p>
          </div>
        )}

        {!loading && !error && snapshots.length === 0 && (
          <div className="card p-8 text-center">
            <p className="text-sm text-sage-500">{t('trail.empty')}</p>
          </div>
        )}

        {!loading && !error && snapshots.map((snap, i) => (
          <SnapshotCard key={snap.id} snap={snap} index={i} />
        ))}
      </div>
    </div>
  );
}