import { Link } from 'react-router-dom';
import { useLang } from '../context/LangContext';
import type { PriorityGrower } from '../types';

interface Props {
  grower: PriorityGrower;
}

function vpsColor(score: number): string {
  if (score >= 80) return 'text-clay-600';
  if (score >= 60) return 'text-harvest-600';
  return 'text-forest-600';
}

function vpsBg(score: number): string {
  if (score >= 80) return 'bg-clay-50 border-clay-100';
  if (score >= 60) return 'bg-harvest-50 border-harvest-100';
  return 'bg-forest-50 border-forest-100';
}

export default function PriorityCard({ grower }: Props) {
  const { t } = useLang();

  /** Translate a reason. Accepts both new codes (reason.x) and legacy English. */
  const translateReason = (raw: string): string => {
    if (!raw) return '';
    // Already a translation key
    if (raw.startsWith('reason.') || raw.startsWith('anomaly.') || raw.startsWith('nba.') || raw.startsWith('override.')) {      const looked = t(raw);
      return looked === raw ? humanize(raw) : looked;
    }
    // Bare code from backend (no namespace) — try reason.<code>
    const asReason = t('reason.' + raw);
    if (asReason !== 'reason.' + raw) return asReason;
    const asAnomaly = t('anomaly.' + raw);
    if (asAnomaly !== 'anomaly.' + raw) return asAnomaly;
    const asOverride = t('override.' + raw);
    if (asOverride !== 'override.' + raw) return asOverride;
    // Fall back to original (could be legacy English string)
    return raw;
  };

  const humanize = (key: string): string =>
    key.replace(/^[a-z]+\./, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  const alertLabel = grower.anomaly_count === 1
    ? t('priority.alert_one')
    : t('priority.alert_many');

  return (
    <Link
      to={`/grower/${grower.entity_id}`}
      className="block card-hover p-4 group"
    >
      <div className="flex items-start gap-4">
        <div className="shrink-0 w-10 h-10 rounded-xl bg-forest-50 border border-forest-100 flex items-center justify-center">
          <span className="text-xs font-bold text-forest-600">#{grower.rank}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-forest-900 text-sm truncate">{grower.name}</h3>
            {grower.anomaly_count > 0 && (
              <span className="flex items-center gap-1 badge-red">
                <span className="w-1.5 h-1.5 rounded-full bg-clay-500" />
                {grower.anomaly_count} {alertLabel}
              </span>
            )}
          </div>
          <p className="text-xs text-sage-500 mb-2 flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {grower.region}
          </p>
          {grower.reasons.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {grower.reasons.slice(0, 3).map((reason, i) => (
                <span key={i} className="badge-gray text-forest-600">
                  {translateReason(reason)}
                </span>
              ))}
              {grower.reasons.length > 3 && (
                <span className="badge-gray">+{grower.reasons.length - 3}</span>
              )}
            </div>
          )}
        </div>
        <div className={`shrink-0 text-center rounded-xl border px-3 py-2 min-w-[56px] ${vpsBg(grower.vps_score)}`}>
          <div className={`text-xl font-bold font-display leading-none ${vpsColor(grower.vps_score)}`}>
            {Math.round(grower.vps_score)}
          </div>
          <div className="text-[10px] font-semibold text-sage-400 mt-0.5 uppercase tracking-wide">VPS</div>
        </div>
      </div>
      <div className="flex justify-end mt-2">
        <svg
          className="w-4 h-4 text-sage-300 group-hover:text-forest-400 transition-colors"
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
}