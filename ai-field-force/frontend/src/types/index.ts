// ─── Auth ────────────────────────────────────────────────────────────────────

export interface Rep {
  id: string;
  name: string;
  email: string;
  phone?: string;
  role: 'rep' | 'manager' | 'admin';
  email_verified_at?: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  rep: Rep;
}

export interface Login2FAResponse {
  requires_2fa: true;
  challenge_id: string;
  email_masked: string;
  expires_in_seconds: number;
  dev_otp?: string;  // only present in DEV_MODE
}

export function is2FAResponse(
  r: AuthResponse | Login2FAResponse,
): r is Login2FAResponse {
  return (r as Login2FAResponse).requires_2fa === true;
}
export interface OtpSendResponse {
  message: string;
  dev_otp?: string; // Only present in DEV_MODE
}

// ─── Visits / Priority ───────────────────────────────────────────────────────

export interface PriorityGrower {
  entity_id: string;
  name: string;
  region: string;
  vps_score: number;
  rank: number;
  reasons: string[];
  anomaly_count: number;
}

export interface GrowerBrief {
  entity_id: string;
  name: string;
  region?: string;
  phone?: string;
  village?: string;
  crop?: string;
  briefing: string;
  nba_actions: string[];
}

// ─── Outcomes ────────────────────────────────────────────────────────────────

export type OutcomeType = 'sale' | 'follow_up_needed' | 'no_interest' | 'complaint' | 'complaint_resolved';
export interface OutcomeRecord {
  client_outcome_id: string;
  entity_id: string;
  rating: number;
  outcome_type: OutcomeType;
  actions_taken: string[];
  notes: string;
  competitor_seen?: boolean;
  visited_at: string;
}

export interface PendingOutcome extends OutcomeRecord {
  synced: boolean;
  entity_name?: string;
}

export interface SyncResultItem {
  client_outcome_id: string;
  status: 'created' | 'duplicate' | 'failed';
  error?: string;
}

export interface SyncResponse {
  created_count: number;
  duplicate_count: number;
  failed_count: number;
  results: SyncResultItem[];
}

// ─── Signals / Anomalies ─────────────────────────────────────────────────────

export type AnomalySeverity = 'high' | 'medium' | 'low';

export interface Anomaly {
  entity_id: string;
  name: string;
  anomaly_type: string;
  description: string;
  severity: AnomalySeverity;
  detected_at: string;
  region?: string;
}

// ─── Devices ─────────────────────────────────────────────────────────────────

export interface Device {
  device_id: string;
  device_name: string;
  device_platform: string;
  last_seen: string;
  is_current?: boolean;
}

// ─── Manager ─────────────────────────────────────────────────────────────────

export interface ManagerOverview {
  territory_health_score: number;
  total_reps: number;
  total_growers: number;
  outcomes_last_30d: number;
  avg_rating: number;
  high_priority_count: number;
}

export type PerformanceLabel = 'excellent' | 'good' | 'needs_attention';

export interface RepMetrics {
  rep_id: string;
  name: string;
  email: string;
  total_growers: number;
  outcomes_last_30d: number;
  avg_rating: number;
  performance_label: PerformanceLabel;
}

export interface TopPriority {
  entity_id: string;
  name: string;
  region: string;
  vps_score: number;
  rank: number;
  assigned_rep?: string;
  reasons?: string[];
  anomaly_count?: number;
}

export interface RepOutcome {
  id: string;
  entity_name: string;
  outcome_type: OutcomeType;
  rating: number;
  visited_at: string;
  notes?: string;
}

export interface RepDetails {
  rep: RepMetrics;
  priorities: PriorityGrower[];
  recent_outcomes: RepOutcome[];
  anomalies: Anomaly[];
}

// ─── Misc ────────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
}
