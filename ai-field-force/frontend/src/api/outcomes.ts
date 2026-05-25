import { client } from './client';
import type { OutcomeRecord, SyncResponse } from '../types';

const QUEUE_KEY = 'pending_outcomes';

// ─── Shape adapter (frontend ↔ backend) ────────────────────────────────────

interface BackendOutcomeItem {
  client_outcome_id: string;
  entity_id: string;
  outcome_rating: number;
  outcome_type: string;
  actions_taken: string[];
  actions_accepted?: string[];
  notes?: string;
  competitor_seen?: boolean;
  recorded_at: string;
}

function toBackendOutcomeItem(o: OutcomeRecord): BackendOutcomeItem {
  return {
    client_outcome_id: o.client_outcome_id,
    entity_id: o.entity_id,
    outcome_rating: o.rating,
    outcome_type: o.outcome_type,
    actions_taken: o.actions_taken,
    actions_accepted: [],
    notes: o.notes,
    competitor_seen: o.competitor_seen ?? false,
    recorded_at: o.visited_at,
  };
}

// ─── Online single record ──────────────────────────────────────────────────

export async function recordOutcome(outcome: OutcomeRecord): Promise<void> {
  await client.post('/outcomes/record', toBackendOutcomeItem(outcome));
}

// ─── Bulk sync ─────────────────────────────────────────────────────────────

export async function syncOutcomes(
  device_id: string,
  device_name: string,
  device_platform: string,
  outcomes: OutcomeRecord[]
): Promise<SyncResponse> {
  const { data } = await client.post<{
    synced_at: string;
    device_id: string;
    total: number;
    created_count: number;
    duplicate_count: number;
    failed_count: number;
    results: Array<{
      client_outcome_id: string;
      server_outcome_id: number | null;
      status: 'created' | 'duplicate' | 'failed';
      error: string | null;
    }>;
  }>('/outcomes/sync', {
    device_id,
    device_name,
    device_platform,
    outcomes: outcomes.map(toBackendOutcomeItem),
  });
  return {
    created_count: data.created_count,
    duplicate_count: data.duplicate_count,
    failed_count: data.failed_count,
    results: data.results.map((r) => ({
      client_outcome_id: r.client_outcome_id,
      status: r.status,
      error: r.error ?? undefined,
    })),
  };
}

// ─── Local queue helpers (unchanged — local-only logic) ────────────────────

export interface QueuedOutcome extends OutcomeRecord {
  synced: boolean;
  entity_name?: string;
  failed?: boolean;
}

export function getQueue(): QueuedOutcome[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as QueuedOutcome[];
  } catch {
    return [];
  }
}

export function saveQueue(queue: QueuedOutcome[]): void {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

export function addToQueue(outcome: OutcomeRecord, entity_name?: string): void {
  const queue = getQueue();
  queue.push({ ...outcome, synced: false, entity_name });
  saveQueue(queue);
}

export function getPendingCount(): number {
  return getQueue().filter((o) => !o.synced).length;
}

export function markSynced(client_outcome_ids: string[]): void {
  const queue = getQueue().map((o) =>
    client_outcome_ids.includes(o.client_outcome_id) ? { ...o, synced: true } : o
  );
  saveQueue(queue);
}

export function markFailed(client_outcome_ids: string[]): void {
  const queue = getQueue().map((o) =>
    client_outcome_ids.includes(o.client_outcome_id) ? { ...o, failed: true } : o
  );
  saveQueue(queue);
}

export function clearSynced(): void {
  const queue = getQueue().filter((o) => !o.synced);
  saveQueue(queue);
}