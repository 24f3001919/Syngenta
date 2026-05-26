// frontend/src/api/adapters.ts
//
// Translation layer: converts the real backend response shapes into the
// TypeScript types the frontend components were built against.
//
// Rule of thumb: leave the screens alone, leave the backend alone, do all
// the reconciliation here. Each adapter is a pure function.

import type {
  PriorityGrower,
  GrowerBrief,
  Anomaly,
  Device,
  ManagerOverview,
  RepMetrics,
  RepDetails,
  TopPriority,
  Rep,
  AuthResponse,
  RepOutcome,
  PerformanceLabel,
  OutcomeType,
} from '../types';

// ─── Auth ──────────────────────────────────────────────────────────────────

interface BackendIdentity {
  provider: string;
  identifier: string;
  verified_at: string | null;
}

interface BackendRep {
  id: string;
  rep_id: string | null;
  name: string;
  primary_email: string | null;
  role: 'rep' | 'manager' | 'admin';
  managed_rep_ids?: string[];
  is_active: boolean;
  created_at: string;
  identities?: BackendIdentity[];
  email_verified_at?: string | null;
}

interface BackendAuthResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  rep: BackendRep;
}

export function adaptRep(b: BackendRep): Rep {
  // Find a phone identity to populate the optional phone field
  const phoneIdent = b.identities?.find((i) => i.provider === 'whatsapp_otp');
  return {
    id: b.id,
    name: b.name,
    email: b.primary_email ?? '',
    phone: phoneIdent?.identifier,
    role: b.role,
    email_verified_at: b.email_verified_at ?? null,
  };
}

export function adaptAuthResponse(b: BackendAuthResponse): AuthResponse {
  return {
    access_token: b.access_token,
    token_type: b.token_type,
    rep: adaptRep(b.rep),
  };
}

// ─── Visits / Priority ─────────────────────────────────────────────────────

interface BackendAnomalyInline {
  type: string;
  severity: 'high' | 'medium' | 'low';
  message: string;
}

interface BackendPriorityGrower {
  entity_id: string;
  name: string;
  region: string;
  vps: number;
  reasons: string[];
  confidence_label: string;
  anomalies: BackendAnomalyInline[];
  rank: number;
  visit_sequence_position: number;
}

export function adaptPriorityGrower(b: BackendPriorityGrower): PriorityGrower {
  return {
    entity_id: b.entity_id,
    name: b.name,
    region: b.region,
    vps_score: b.vps,
    rank: b.rank,
    reasons: b.reasons ?? [],
    anomaly_count: b.anomalies?.length ?? 0,
  };
}

interface BackendGrowerBrief {
  entity_id: string;
  name: string;
  briefing: string;
  nba_actions: unknown[]; // backend may emit strings or objects, depending on chain
}

export function adaptGrowerBrief(b: BackendGrowerBrief): GrowerBrief {
  // nba_actions might be strings OR objects like {action, rationale, priority}
  // Normalize to strings so the screen's `.map(a => a)` works either way.
  const actions: string[] = (b.nba_actions ?? []).map((a) => {
    if (typeof a === 'string') return a;
    if (a && typeof a === 'object' && 'action' in a) return String((a as { action: unknown }).action);
    return JSON.stringify(a);
  });

  return {
    entity_id: b.entity_id,
    name: b.name,
    briefing: b.briefing,
    nba_actions: actions,
    // The backend doesn't return region/phone/village/crop on the brief itself.
    // Leaving them undefined — the screen renders them conditionally.
  };
}

// ─── Anomalies ─────────────────────────────────────────────────────────────

interface BackendAnomaliesResponse {
  rep_id: string;
  total_flagged: number;
  results: Array<{
    entity_id: string;
    name: string;
    region: string;
    anomalies: BackendAnomalyInline[];
  }>;
}

export function adaptAnomalies(b: BackendAnomaliesResponse): Anomaly[] {
  // Flatten nested {entity, [anomalies]} into a flat list of Anomaly rows
  const out: Anomaly[] = [];
  const now = new Date().toISOString();

  for (const row of b.results ?? []) {
    for (const a of row.anomalies ?? []) {
      out.push({
        entity_id: row.entity_id,
        name: row.name,
        region: row.region,
        anomaly_type: formatAnomalyType(a.type),
        description: a.message,
        severity: a.severity,
        // Backend doesn't track per-anomaly detection time today; use "now" as a
        // reasonable placeholder. Frontend sorts/filters on it but doesn't depend
        // on accuracy.
        detected_at: now,
      });
    }
  }

  // Sort: high severity first, then medium, then low
  const sevOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
  out.sort((x, y) => (sevOrder[x.severity] ?? 99) - (sevOrder[y.severity] ?? 99));
  return out;
}

function formatAnomalyType(type: string): string {
  // "visit_gap_exceeded" → "Visit Gap Exceeded"
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// ─── Devices ───────────────────────────────────────────────────────────────

interface BackendDevice {
  id: string;
  name: string | null;
  platform: string | null;
  is_revoked: boolean;
  first_seen_at: string;
  last_seen_at: string;
  last_sync_at: string | null;
  sync_count: string;
}

export function adaptDevice(b: BackendDevice, currentDeviceId?: string): Device {
  return {
    device_id: b.id,
    device_name: b.name ?? 'Unnamed device',
    device_platform: b.platform ?? 'unknown',
    last_seen: b.last_seen_at,
    is_current: currentDeviceId === b.id,
  };
}

// ─── Manager: overview ─────────────────────────────────────────────────────

interface BackendTerritoryHealth {
  score: number;
  label: 'healthy' | 'watch_list' | 'needs_attention';
  components: Record<string, unknown>;
  weights: Record<string, number>;
}

interface BackendManagerOverview {
  territory_health: BackendTerritoryHealth;
  total_reps: number;
  total_growers_under_management: number;
  total_outcomes_logged: number;
  outcomes_last_30d: number;
  average_outcome_rating: number | null;
  high_priority_growers_count: number;
  open_anomalies_count: number;
  last_activity_at: string | null;
}

export function adaptManagerOverview(b: BackendManagerOverview): ManagerOverview {
  return {
    territory_health_score: b.territory_health.score,
    total_reps: b.total_reps,
    total_growers: b.total_growers_under_management,
    outcomes_last_30d: b.outcomes_last_30d,
    avg_rating: b.average_outcome_rating ?? 0,
    high_priority_count: b.high_priority_growers_count,
  };
}

// ─── Manager: rep metrics ──────────────────────────────────────────────────

interface BackendRepMetrics {
  rep_id: string;
  name: string;
  territory_size: number;
  outcomes_total: number;
  outcomes_last_30d: number;
  average_rating: number | null;
  high_priority_count: number;
  anomalies_count: number;
  last_activity_at: string | null;
  performance_label: 'active' | 'low_activity' | 'needs_attention';
}

const PERFORMANCE_LABEL_MAP: Record<string, PerformanceLabel> = {
  active: 'excellent',
  low_activity: 'good',
  needs_attention: 'needs_attention',
};

export function adaptRepMetrics(b: BackendRepMetrics): RepMetrics {
  return {
    rep_id: b.rep_id,
    name: b.name,
    email: '', // backend doesn't return rep emails here; leave blank
    total_growers: b.territory_size,
    outcomes_last_30d: b.outcomes_last_30d,
    avg_rating: b.average_rating ?? 0,
    performance_label: PERFORMANCE_LABEL_MAP[b.performance_label] ?? 'good',
  };
}

// ─── Manager: rep details ──────────────────────────────────────────────────

interface BackendRepOutcome {
  id: number;
  entity_id: string;
  outcome_rating: number;
  outcome_type: string;
  actions_taken: string[];
  notes: string | null;
  recorded_at: string | null;
  synced_at: string | null;
}

interface BackendRepDetails {
  rep_id: string;
  name: string | null;
  priority_list: BackendPriorityGrower[];
  recent_outcomes: BackendRepOutcome[];
  anomalies: BackendAnomaliesResponse;
}

function adaptRepOutcome(b: BackendRepOutcome): RepOutcome {
  return {
    id: String(b.id),
    entity_name: b.entity_id, // backend doesn't denormalize the grower name onto outcomes
    outcome_type: (b.outcome_type as OutcomeType) ?? 'follow_up_needed',
    rating: b.outcome_rating,
    visited_at: b.recorded_at ?? b.synced_at ?? new Date().toISOString(),
    notes: b.notes ?? undefined,
  };
}

export function adaptRepDetails(
  b: BackendRepDetails,
  metricsLookup?: RepMetrics
): RepDetails {
  // The /manager/reps/{id}/details endpoint doesn't return the metrics block
  // alongside — managers see /manager/reps for that. We accept an optional
  // pre-fetched metrics object and synthesize a minimal one if absent.
  const rep: RepMetrics = metricsLookup ?? {
    rep_id: b.rep_id,
    name: b.name ?? `Rep ${b.rep_id}`,
    email: '',
    total_growers: b.priority_list?.length ?? 0,
    outcomes_last_30d: b.recent_outcomes?.length ?? 0,
    avg_rating: 0,
    performance_label: 'good',
  };

  return {
    rep,
    priorities: (b.priority_list ?? []).map(adaptPriorityGrower),
    recent_outcomes: (b.recent_outcomes ?? []).map(adaptRepOutcome),
    anomalies: adaptAnomalies(b.anomalies),
  };
}

// ─── Manager: top priorities ───────────────────────────────────────────────

interface BackendTopPriority {
  entity_id: string;
  name: string;
  region: string;
  rep_id: string;
  vps: number;
  rank_within_rep: number;
  reasons: string[];
  confidence_label: string;
}

export function adaptTopPriority(b: BackendTopPriority): TopPriority {
  return {
    entity_id: b.entity_id,
    name: b.name,
    region: b.region,
    vps_score: b.vps,
    rank: b.rank_within_rep,
    assigned_rep: b.rep_id, // we don't have the rep's display name here without an extra lookup
    reasons: b.reasons,
    anomaly_count: 0, // not provided on this endpoint
  };
}