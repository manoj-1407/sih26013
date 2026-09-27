import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

interface DatasetReport {
  dataset_id: string;
  source_type: string;
  label: string;
  total_features: number;
  valid_features: number;
  quality_level: string;
  quality_score?: number;
  validity_rate?: number;
  issues: {
    invalid_geometries: number;
    repaired_geometries: number;
    duplicate_ids: number;
    missing_timestamps: number;
    crs_issues: number;
    area_outliers: number;
  };
  warnings: string[];
}

interface QualityReport {
  case_id: string;
  generated_at: string;
  summary: {
    datasets: number;
    total_records: number;
    total_valid: number;
    overall_validity_rate: number;
  };
  datasets: DatasetReport[];
  source_manifest_hash: string;
  note: string;
}

function QualityBadge({ level }: { level: string }) {
  const cls = level === 'HIGH' ? 'badge-ok' : level === 'MEDIUM' ? 'badge-warn' : level === 'LOW' ? 'badge-err' : 'badge-neutral';
  return <span className={`badge ${cls}`}>{level}</span>;
}

function MiniBar({ value, max = 100, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div style={{ flex: 1, height: 6, background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden', minWidth: 60 }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3 }} />
    </div>
  );
}

export default function QualityReportPanel({ caseId }: { caseId: string | null }) {
  const { data, isLoading, error, refetch } = useQuery<QualityReport>({
    queryKey: ['quality-report', caseId],
    queryFn: () => api.get<QualityReport>(`/cases/${caseId}/quality-report`),
    enabled: !!caseId,
    retry: false,
  });

  if (!caseId) {
    return <div className="empty-state"><div className="empty-icon">📊</div>Select a case first.</div>;
  }
  if (isLoading) return <div className="loading">Loading quality report…</div>;
  if (error) {
    return (
      <div className="flex-col gap-2">
        <div className="notice notice-amber">
          No quality report available yet. Ingest datasets first.
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => refetch()}>↺ Retry</button>
      </div>
    );
  }
  if (!data) return null;

  const { summary, datasets, source_manifest_hash } = data;
  const overallColor = summary.overall_validity_rate >= 90 ? 'var(--green)'
    : summary.overall_validity_rate >= 70 ? 'var(--amber)' : 'var(--red)';

  return (
    <div className="flex-col gap-3">
      {/* Summary */}
      <div className="card">
        <div className="card-header">📊 Data Quality Summary</div>
        <div className="card-body">
          <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 12 }}>
            <div className="stat-box">
              <div className="stat-num">{summary.datasets}</div>
              <div className="stat-label">Datasets</div>
            </div>
            <div className="stat-box">
              <div className="stat-num">{summary.total_records}</div>
              <div className="stat-label">Total Records</div>
            </div>
            <div className="stat-box">
              <div className="stat-num" style={{ color: overallColor }}>{summary.total_valid}</div>
              <div className="stat-label">Valid Records</div>
            </div>
            <div className="stat-box">
              <div className="stat-num" style={{ color: overallColor }}>
                {summary.overall_validity_rate.toFixed(1)}%
              </div>
              <div className="stat-label">Validity Rate</div>
            </div>
          </div>

          {/* Source manifest hash */}
          <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>
            Source Manifest SHA-256 (all ingested records):
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)', wordBreak: 'break-all', padding: '4px 8px', background: 'var(--surface2)', borderRadius: 4 }}>
            {source_manifest_hash}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 6 }}>
            {data.note}
          </div>
        </div>
      </div>

      {/* Per-dataset table */}
      <div className="card">
        <div className="card-header">Per-Dataset Quality Profiles</div>
        <div className="card-body" style={{ padding: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Label</th>
                <th>Records</th>
                <th>Validity</th>
                <th>Quality</th>
                <th>Issues</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map(d => {
                const totalIssues = Object.values(d.issues).reduce((a, b) => a + b, 0);
                const validity = d.validity_rate ?? (d.total_features > 0 ? (d.valid_features / d.total_features) * 100 : 0);
                return (
                  <tr key={d.dataset_id}>
                    <td>
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text3)' }}>
                        {d.source_type}
                      </span>
                    </td>
                    <td style={{ maxWidth: 140 }}>
                      <div className="truncate" style={{ fontSize: 12 }}>{d.label || d.source_type}</div>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <span style={{ fontWeight: 700 }}>{d.valid_features}</span>
                      <span style={{ color: 'var(--text3)', fontSize: 11 }}>/{d.total_features}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <MiniBar
                          value={validity}
                          color={validity >= 90 ? 'var(--green)' : validity >= 70 ? 'var(--amber)' : 'var(--red)'}
                        />
                        <span style={{ fontSize: 11, minWidth: 34, textAlign: 'right', fontFamily: 'var(--mono)' }}>
                          {validity.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td><QualityBadge level={d.quality_level} /></td>
                    <td>
                      {totalIssues > 0 ? (
                        <span style={{ fontSize: 11, color: 'var(--amber)' }}>
                          ⚠ {totalIssues} issue{totalIssues > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, color: 'var(--green)' }}>✓ Clean</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Warnings */}
      {datasets.some(d => d.warnings.length > 0) && (
        <div className="card">
          <div className="card-header" style={{ color: 'var(--amber)' }}>⚠ Data Quality Warnings</div>
          <div className="card-body flex-col gap-2">
            {datasets.filter(d => d.warnings.length > 0).map(d =>
              d.warnings.map((w, i) => (
                <div key={`${d.dataset_id}-${i}`} style={{
                  fontSize: 12, color: 'var(--text2)', padding: '5px 8px',
                  borderLeft: '3px solid var(--amber)', background: 'var(--surface2)', borderRadius: '0 4px 4px 0',
                }}>
                  <span style={{ color: 'var(--text3)', marginRight: 8, fontSize: 11 }}>{d.label}:</span>
                  {w}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
