import { useState } from 'react';
import { useLang } from '../context/LangContext';
import type { OutcomeType } from '../types';

// Action chips: value goes to backend (stays English for data consistency),
// key is used to look up the translated label.
const ACTIONS: Array<{ value: string; key: string }> = [
  { value: 'Demonstrated product',   key: 'action.demonstrated_product' },
  { value: 'Shared brochure',        key: 'action.shared_brochure' },
  { value: 'Collected soil sample',  key: 'action.collected_soil_sample' },
  { value: 'Discussed crop plan',    key: 'action.discussed_crop_plan' },
  { value: 'Resolved complaint',     key: 'action.resolved_complaint' },
  { value: 'Offered trial pack',     key: 'action.offered_trial_pack' },
  { value: 'Scheduled follow-up',    key: 'action.scheduled_follow_up' },
  { value: 'Processed order',        key: 'action.processed_order' },
];
interface FormValues {
  rating: number;
  outcome_type: OutcomeType;
  actions_taken: string[];
  notes: string;
}

interface Props {
  entityName?: string;
  onSubmit: (values: FormValues) => Promise<void>;
  onCancel?: () => void;
}

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hovered, setHovered] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          className="p-0.5"
        >
          <svg
            className={`w-8 h-8 transition-colors ${
              star <= (hovered || value)
                ? 'text-harvest-400'
                : 'text-sage-200'
            }`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        </button>
      ))}
    </div>
  );
}

export default function OutcomeForm({ entityName, onSubmit, onCancel }: Props) {
  const { t } = useLang();
  const [rating, setRating] = useState(0);
  const [outcomeType, setOutcomeType] = useState<OutcomeType>('follow_up_needed');
  const [actionsTaken, setActionsTaken] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const OUTCOME_LABELS: Record<OutcomeType, string> = {
    sale: t('outcome.sale'),
    follow_up_needed: t('outcome.follow_up'),
    no_interest: t('outcome.no_interest'),
    complaint: t('outcome.complaint'),
    complaint_resolved: t('outcome.complaint') + ' ✓',
  };

  function toggleAction(action: string) {
    setActionsTaken((prev) =>
      prev.includes(action) ? prev.filter((a) => a !== action) : [...prev, action]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (rating === 0) { setError(t('outcome.rating_err')); return; }
    setError('');
    setLoading(true);
    try {
      await onSubmit({ rating, outcome_type: outcomeType, actions_taken: actionsTaken, notes });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {entityName && (
        <div className="card px-4 py-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-forest-100 flex items-center justify-center text-forest-700 font-bold text-sm shrink-0">
            {entityName.charAt(0)}
          </div>
          <div>
            <p className="text-xs text-sage-500 font-medium">{t('outcome.logging_for')}</p>
            <p className="text-sm font-semibold text-forest-900">{entityName}</p>
          </div>
        </div>
      )}

      <div>
        <label className="label">{t('outcome.rating')}</label>
        <StarRating value={rating} onChange={setRating} />
        {rating > 0 && (
          <p className="text-xs text-sage-500 mt-1">
            {['', t('outcome.rate_1'), t('outcome.rate_2'), t('outcome.rate_3'), t('outcome.rate_4'), t('outcome.rate_5')][rating]}
          </p>
        )}
      </div>

      <div>
        <label className="label">{t('outcome.outcome')}</label>
        <div className="grid grid-cols-2 gap-2">
          {(Object.entries(OUTCOME_LABELS) as [OutcomeType, string][]).map(([type, label]) => (
            <button
              key={type}
              type="button"
              onClick={() => setOutcomeType(type)}
              className={`rounded-xl border px-3 py-2.5 text-xs font-semibold text-left transition-colors ${
                outcomeType === type
                  ? type === 'sale'
                    ? 'bg-forest-700 border-forest-700 text-white'
                    : type === 'complaint_resolved'
                    ? 'bg-clay-600 border-clay-600 text-white'
                    : 'bg-forest-50 border-forest-400 text-forest-800'
                  : 'bg-white border-sage-200 text-sage-600 hover:bg-sage-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="label">{t('outcome.actions')}</label>
        <div className="flex flex-wrap gap-2">
          {ACTIONS.map((action) => (
            <button
              key={action.value}
              type="button"
              onClick={() => toggleAction(action.value)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                actionsTaken.includes(action.value)
                  ? 'bg-forest-700 border-forest-700 text-white'
                  : 'bg-white border-sage-200 text-sage-600 hover:bg-forest-50 hover:border-forest-300'
              }`}
            >
              {t(action.key)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label htmlFor="notes" className="label">{t('outcome.notes')}</label>
        <textarea
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={t('outcome.notes_ph')}
          rows={3}
          className="input-field resize-none"
        />
      </div>

      {error && (
        <p className="text-xs text-clay-600 font-medium bg-clay-50 rounded-xl px-4 py-3">{error}</p>
      )}

      <div className="flex gap-3">
        {onCancel && (
          <button type="button" onClick={onCancel} className="btn-secondary flex-1">
            {t('outcome.cancel')}
          </button>
        )}
        <button type="submit" disabled={loading} className="btn-primary flex-1">
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {t('outcome.saving')}
            </span>
          ) : (
            t('outcome.save')
          )}
        </button>
      </div>
    </form>
  );
}