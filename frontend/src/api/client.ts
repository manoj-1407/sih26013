// GeoSamanvay API client — all calls go through /api/v1/

const BASE = '/api/v1';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) }),
};

// ── Types ──────────────────────────────────────────────────────────────────

export interface Case {
  case_id: string;
  title: string;
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
  quality_level: string;
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

export interface Conflict {
  conflict_id: string;
  type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  description: string;
  measure?: number;
  measure_unit?: string;
  record_ids?: string[];
  evidence?: Record<string, unknown>;
}

export interface Proposal {
  proposal_id: string;
  decision: string;
  decision_reason: string;
  match_confidence: number;
  confidence_components?: Record<string, unknown>;
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
  issues?: RippleIssue[];
}

export interface RippleIssue {
  issue_id: string;
  issue_type: string;
  severity: string;
  feature_id: string;
  feature_type: string;
  measure?: number;
  measure_unit?: string;
  description: string;
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

export interface ProvenanceGraph {
  nodes: ProvenanceNode[];
  edges: ProvenanceEdge[];
}

export interface ProvenanceNode {
  node_id: string;
  node_type: string;
  parent_ids: string[];
  label: string;
}

export interface ProvenanceEdge {
  from: string;
  to: string;
}

export interface HarmonizeResult {
  case_id: string;
  total_records: number;
  matched_groups: number;
  parcels: ParcelResult[];
  review_queue_count: number;
}

export interface ParcelResult {
  parcel_id: string;
  source_count: number;
  source_types: string[];
  match_confidence: number;
  independent_lineages: number;
  conflicts: { total: number; critical: number; high: number; medium: number; low: number };
  proposal: {
    proposal_id: string;
    decision: string;
    decision_reason: string;
    can_auto_approve: boolean;
    max_boundary_offset_m: number;
    area_change_pct: number;
    change_summary: string[];
  };
  ripple: { safe_to_auto_approve: boolean; total_issues: number; summary: string };
  review_item_id?: string;
}
