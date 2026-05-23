import { client, MOCK_MODE, mockDelay } from './client';
import { MOCK_ANOMALIES } from './mockData';
import { adaptAnomalies } from './adapters';
import type { Anomaly } from '../types';

// ─── Anomalies ────────────────────────────────────────────────────────────────

export async function getAnomalies(): Promise<Anomaly[]> {
  if (MOCK_MODE) return mockDelay(MOCK_ANOMALIES);
  try {
    const { data } = await client.get('/signals/anomalies');
    return adaptAnomalies(data);
  } catch (err: unknown) {
    // 403 for not-linked accounts → empty list, friendly UI
    if (err && typeof err === 'object' && 'response' in err) {
      const r = (err as { response?: { status?: number } }).response;
      if (r?.status === 403) return [];
    }
    throw err;
  }
}

// ─── NDVI (Sentinel-2 satellite crop health) ──────────────────────────────────

export interface NdviDetail {
  entity_id: string;
  name: string;
  ndvi_raw: number | null;
  stress_score: number | null;
  scene_date: string | null;
  cloud_cover_pct: number | null;
  scene_id: string | null;
  source: string;
  location?: { lat: number; lon: number };
}

export async function getNdviDetail(entity_id: string): Promise<NdviDetail | null> {
  try {
    const { data } = await client.get<NdviDetail>(`/signals/ndvi/${entity_id}`);
    return data;
  } catch {
    return null;
  }
}

// ─── Pest advisory (ICAR + IMD + baseline fallback) ───────────────────────────

export interface PestDetail {
  entity_id: string;
  name: string;
  region: string;
  severity: string;
  district: string;
  source: string;
  is_live: boolean;
  fetched_at: string;
  note?: string;
}

export async function getPestDetail(entity_id: string): Promise<PestDetail | null> {
  try {
    const { data } = await client.get<PestDetail>(`/signals/pest/${entity_id}`);
    return data;
  } catch {
    return null;
  }
}