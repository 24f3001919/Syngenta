import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../../components/Layout';
import OutcomeForm from '../../components/OutcomeForm';
import { getGrowerBrief } from '../../api/visits';
import { getNdviDetail, getPestDetail, type NdviDetail, type PestDetail } from '../../api/signals';
import { useOfflineQueue } from '../../hooks/useOfflineQueue';
import { useLang } from '../../context/LangContext';
import type { GrowerBrief, OutcomeType } from '../../types';

export default function GrowerDetail() {
  const { entity_id } = useParams<{ entity_id: string }>();
  const navigate = useNavigate();
  const { enqueue, sync } = useOfflineQueue();
  const { t, lang } = useLang();

  const [brief, setBrief] = useState<GrowerBrief | null>(null);
  const [ndvi, setNdvi] = useState<NdviDetail | null>(null);
  const [pest, setPest] = useState<PestDetail | null>(null);
  const [signalsLoading, setSignalsLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!entity_id) return;
    setLoading(true);
    getGrowerBrief(entity_id)
      .then(setBrief)
      .catch(() => setError('Failed to load grower brief.'))
      .finally(() => setLoading(false));
  }, [entity_id, lang]);

  useEffect(() => {
    if (!entity_id) return;
    setSignalsLoading(true);
    Promise.all([getNdviDetail(entity_id), getPestDetail(entity_id)])
      .then(([n, p]) => { setNdvi(n); setPest(p); })
      .finally(() => setSignalsLoading(false));
  }, [entity_id, lang]);

  async function handleOutcomeSubmit(values: {
    rating: number;
    outcome_type: OutcomeType;
    actions_taken: string[];
    notes: string;
  }) {
    if (!entity_id) return;
    const outcome = {
      client_outcome_id: crypto.randomUUID(),
      entity_id,
      ...values,
      visited_at: new Date().toISOString(),
    };

    enqueue(outcome, brief?.name);

    try {
      await sync();
    } catch {
      // Will sync later
    }

    setShowForm(false);
    setSubmitted(true);
  }

  if (loading) {
    return (
      <Layout title={t('grower.ai_brief')} showBack>
        <div className="space-y-4 animate-pulse">
          <div className="card p-5 space-y-3">
            <div className="h-5 bg-sage-100 rounded w-2/3" />
            <div className="h-3 bg-sage-100 rounded w-1/3" />
          </div>
          <div className="card p-5 space-y-2">
            {[...Array(4)].map((_, i) => <div key={i} className="h-3 bg-sage-100 rounded" />)}
          </div>
        </div>
      </Layout>
    );
  }

  if (error || !brief) {
    return (
      <Layout title={t('grower.ai_brief')} showBack>
        <div className="card p-6 text-center border-clay-100 bg-clay-50">
          <p className="text-sm font-medium text-clay-700">{error || 'Grower not found.'}</p>
          <button onClick={() => navigate(-1)} className="mt-3 btn-secondary text-xs">{t('grower.go_back')}</button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title={brief.name} showBack>
      <div className="card p-5 mb-4">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-2xl bg-forest-100 flex items-center justify-center shrink-0">
            <span className="text-forest-700 font-bold text-lg font-display">{brief.name.charAt(0)}</span>
          </div>
          <div>
            <h2 className="font-display text-xl font-bold text-forest-900">{brief.name}</h2>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
              {brief.region && (
                <span className="text-xs text-sage-500 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  </svg>
                  {brief.region}
                </span>
              )}
              {brief.phone && (
                <span className="text-xs text-sage-500 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                  </svg>
                  {brief.phone}
                </span>
              )}
              {brief.crop && (
                <span className="text-xs text-sage-500 flex items-center gap-1">
                  <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" />
                  </svg>
                  {brief.crop}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="card p-5 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-5 h-5 rounded bg-forest-700 flex items-center justify-center shrink-0">
            <svg className="w-3 h-3 text-white" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
          </div>
          <h3 className="text-xs font-bold text-forest-800 uppercase tracking-wider">{t('grower.ai_brief')}</h3>
        </div>
        <p className="text-sm text-forest-800 leading-relaxed">{brief.briefing}</p>
      </div>

      {/* Satellite NDVI widget */}
      <div className="card p-5 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-5 h-5 rounded bg-forest-700 flex items-center justify-center shrink-0">
            <span className="text-white text-[10px]">🛰</span>
          </div>
          <h3 className="text-xs font-bold text-forest-800 uppercase tracking-wider">{t('widget.satellite_title')}</h3>
        </div>
        {signalsLoading ? (
          <p className="text-xs text-sage-500">{t('widget.loading')}</p>
        ) : ndvi ? (
          <div className="space-y-2 text-xs">
            {ndvi.stress_score !== null && (
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-sage-600">{t('widget.stress_score')}</span>
                  <span className="font-semibold text-forest-900">{(ndvi.stress_score * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 bg-sage-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      ndvi.stress_score >= 0.6 ? 'bg-clay-500' : ndvi.stress_score >= 0.4 ? 'bg-harvest-500' : 'bg-forest-500'
                    }`}
                    style={{ width: `${Math.min(100, ndvi.stress_score * 100)}%` }}
                  />
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 pt-1">
              {ndvi.scene_date && (
                <div>
                  <p className="text-[10px] uppercase text-sage-400 font-semibold tracking-wide">{t('widget.scene_date')}</p>
                  <p className="text-forest-800">{ndvi.scene_date}</p>
                </div>
              )}
              {ndvi.cloud_cover_pct !== null && (
                <div>
                  <p className="text-[10px] uppercase text-sage-400 font-semibold tracking-wide">{t('widget.cloud_cover')}</p>
                  <p className="text-forest-800">{(ndvi.cloud_cover_pct * 100).toFixed(1)}%</p>
                </div>
              )}
            </div>
            <p className="text-[10px] text-sage-400 pt-1 border-t border-forest-50">{ndvi.source}</p>
          </div>
        ) : (
          <p className="text-xs text-sage-500">{t('widget.unavailable')}</p>
        )}
      </div>

      {/* Regional pest advisory widget */}
      <div className="card p-5 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-5 h-5 rounded bg-clay-600 flex items-center justify-center shrink-0">
            <span className="text-white text-[10px]">🐛</span>
          </div>
          <h3 className="text-xs font-bold text-forest-800 uppercase tracking-wider">{t('widget.pest_title')}</h3>
        </div>
        {signalsLoading ? (
          <p className="text-xs text-sage-500">{t('widget.loading')}</p>
        ) : pest ? (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-sage-600">{t('widget.severity')}</span>
              <span className={`badge-${
                pest.severity === 'high' ? 'red' : pest.severity === 'medium' ? 'yellow' : 'green'
              } capitalize`}>
                {pest.severity}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div>
                <p className="text-[10px] uppercase text-sage-400 font-semibold tracking-wide">{t('widget.district')}</p>
                <p className="text-forest-800 capitalize">{pest.district}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-sage-400 font-semibold tracking-wide">{t('widget.source')}</p>
                <p className="text-forest-800 text-[11px]">
                  {pest.is_live ? `🟢 ${t('widget.live')}` : `🔵 ${t('widget.baseline')}`}
                </p>
              </div>
            </div>
            <p className="text-[10px] text-sage-400 pt-1 border-t border-forest-50">{pest.source}</p>
          </div>
        ) : (
          <p className="text-xs text-sage-500">{t('widget.unavailable')}</p>
        )}
      </div>

      {brief.nba_actions.length > 0 && (
        <div className="card p-5 mb-4">
          <h3 className="text-xs font-bold text-forest-800 uppercase tracking-wider mb-3">
            {t('grower.actions')}
          </h3>
          <div className="space-y-2">
            {brief.nba_actions.map((action, i) => {
              const code = typeof action === 'string' ? action : (action as { action?: string }).action ?? '';
              const label = t('nba.' + code);
              const display = label === 'nba.' + code
                ? code.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                : label;
              return (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-5 h-5 rounded-full bg-forest-100 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[10px] font-bold text-forest-700">{i + 1}</span>
                  </div>
                  <p className="text-sm text-forest-800">{display}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {submitted && (
        <div className="card p-4 mb-4 bg-forest-50 border-forest-200">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-forest-100 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-forest-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-forest-800">{t('grower.logged')}</p>
              <p className="text-xs text-forest-600">{t('grower.will_sync')}</p>
            </div>
          </div>
        </div>
      )}

      {showForm ? (
        <div className="card p-5">
          <h3 className="section-title mb-4">{t('grower.log_outcome')}</h3>
          <OutcomeForm
            entityName={brief.name}
            onSubmit={handleOutcomeSubmit}
            onCancel={() => setShowForm(false)}
          />
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="btn-primary w-full"
        >
          {submitted ? t('grower.log_another') : t('grower.log_outcome')}
        </button>
      )}
    </Layout>
  );
}