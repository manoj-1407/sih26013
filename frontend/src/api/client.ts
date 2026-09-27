const BASE = '/api/v1';

class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get:    <T>(path: string)              => apiFetch<T>(path),
  post:   <T>(path: string, body: unknown) => apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  delete: <T>(path: string)              => apiFetch<T>(path, { method: 'DELETE' }),
};

// ── Types ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp_utc: string;
  subsystems: Record<string, string>;
  ml_reranker: { available: boolean; metrics?: Record<string, number> };
}

export interface Case {
  case_id: string;
  title: string;
  description?: string;
  status: string;
  created_at: string;
  stats?: { datasets: number; canonical_parcels: number; conflicts: number; proposals: number };
}

export interface Dataset {
  dataset_id: string;
  source_type: string;
  label: string;
  total_features: number;
  valid_features: number;
  quality_level: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
}

export interface Conflict {
  conflict_id: string;
  type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  description: string;
  measure?: number;
  measure_unit?: string;
  record_ids?: string[];
}

export interface Proposal {
  proposal_id: string;
  decision: string;
  decision_reason: string;
  match_confidence: number;
  confidence_components?: Record<string, number | string | string[]>;
  change_summary?: string[];
  proposed_geometry?: GeoJSON.Geometry;
  ripple_check?: RippleCheck;
  independent_lineages?: number;
}

export interface RippleCheck {
  safe_to_auto_approve: boolean;
  total_issues: number;
  critical_issues: number;
  summary: string;
  issues?: Array<{
    issue_id: string; issue_type: string; severity: string;
    feature_id: string; feature_type: string;
    measure?: number; measure_unit?: string; description: string;
  }>;
}

export interface Parcel {
  canonical_id: string;
  ulpin?: string;
  match_confidence: number;
  independent_lineages: number;
  source_count: number;
  conflict_count: number;
  proposal_id?: string;
  status: string;
  geometry?: GeoJSON.Geometry;
  area_sqm?: number;
  land_use?: string;
  owner_reference?: string;
  match_evidence?: Record<string, unknown>;
  conflicts?: Conflict[];
  proposal?: Proposal;
  source_record_ids?: string[];
}

export interface ReviewItem {
  item_id: string;
  proposal_id: string;
  parcel_id: string;
  priority: number;
  reason: string;
  conflict_types: string[];
  conflict_count: number;
  ripple_issues: number;
  match_confidence: number;
  created_at: string;
  status: string;
}

export interface ProvenanceNode {
  node_id: string;
  node_type: string;
  parent_ids: string[];
  label: string;
}

export interface QualityReport {
  case_id: string;
  summary: { datasets: number; total_records: number; total_valid: number; overall_validity_rate: number };
  datasets: Array<{
    dataset_id: string; source_type: string; label: string;
    total_features: number; valid_features: number;
    quality_level: string; quality_score?: number; validity_rate?: number;
    warnings: string[];
  }>;
  source_manifest_hash: string;
}

export interface HarmonizeResult {
  case_id: string;
  total_records: number;
  matched_groups: number;
  review_queue_count: number;
  parcels: Array<{
    parcel_id: string; source_count: number; source_types: string[];
    match_confidence: number; independent_lineages: number;
    conflicts: { total: number; critical: number; high: number; medium: number; low: number };
    proposal: { proposal_id: string; decision: string; decision_reason: string; max_boundary_offset_m: number; change_summary: string[] };
    ripple: { safe_to_auto_approve: boolean; total_issues: number; summary: string };
  }>;
}

export interface CaseStats {
  case_id: string;
  datasets: number;
  total_records: number;
  canonical_parcels: number;
  conflicts_total: number;
  conflicts_by_severity: Record<string, number>;
  proposals: number;
  auto_approved: number;
  review_required: number;
  blocked: number;
  pending: number;
}
