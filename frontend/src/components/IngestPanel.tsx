import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, Dataset } from '../api/client';

const SOURCE_TYPES = [
  'CADASTRAL', 'REVENUE_ROR', 'MUNICIPAL_GIS', 'DRONE_ORI',
  'GNSS_SURVEY', 'BUILDING_FOOTPRINT', 'UTILITY_NETWORK',
  'ROAD_NETWORK', 'ADMINISTRATIVE', 'HISTORICAL',
];

export default function IngestPanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [sourceType, setSourceType] = useState('CADASTRAL');
  const [label, setLabel] = useState('');
  const [authority, setAuthority] = useState('');
  const [geojsonText, setGeojsonText] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const datasetsQuery = useQuery({
    queryKey: ['datasets', caseId],
    queryFn: () => api.get<{ datasets: Dataset[] }>(`/cases/${caseId}/datasets`),
    enabled: !!caseId,
  });

  async function ingest() {
    if (!caseId) { setError('Select a case first'); return; }
    if (!geojsonText.trim()) { setError('Paste GeoJSON data'); return; }
    let parsed: any;
    try {
      parsed = JSON.parse(geojsonText);
    } catch {
      setError('Invalid JSON'); return;
    }
    // Accept FeatureCollection or array of features
    const features = parsed.type === 'FeatureCollection'
      ? parsed.features
      : Array.isArray(parsed) ? parsed : [parsed];

    setLoading(true); setError(''); setResult(null);
    try {
      const res = await api.post(`/cases/${caseId}/datasets`, {
        source_type: sourceType,
        label, authority,
        features,
      });
      setResult(res);
      qc.invalidateQueries({ queryKey: ['datasets', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
      setGeojsonText('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (!caseId) {
    return <div className="empty-state"><div className="empty-icon">📥</div>Select a case first.</div>;
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, height: '100%' }}>
      {/* Left: ingest form */}
      <div className="flex-col gap-2">
        <div className="card mb-3">
          <div className="card-header">Ingest Source Dataset</div>
          <div className="card-body flex-col gap-2">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div className="form-group">
                <label className="form-label">Source Type *</label>
                <select className="form-select" value={sourceType} onChange={e => setSourceType(e.target.value)}>
                  {SOURCE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Label</label>
                <input className="form-input" value={label} onChange={e => setLabel(e.target.value)}
                  placeholder="e.g. Cadastral 2019" />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Authority / Organization</label>
              <input className="form-input" value={authority} onChange={e => setAuthority(e.target.value)}
                placeholder="e.g. Survey of India, ULB Nagpur" />
            </div>
            <div className="form-group">
              <label className="form-label">GeoJSON FeatureCollection *</label>
              <textarea
                className="form-textarea"
                style={{ minHeight: 200 }}
                value={geojsonText}
                onChange={e => setGeojsonText(e.target.value)}
                placeholder={'{\n  "type": "FeatureCollection",\n  "features": [...]\n}'}
              />
            </div>
            {error && <div className="notice notice-red">{error}</div>}
            {result && (
              <div className="notice notice-green">
                ✓ Dataset <strong>{result.dataset_id}</strong> ingested — {result.accepted} accepted
                {result.rejected?.length > 0 && `, ${result.rejected.length} rejected`}.
                {result.quality_profile && (
                  <span style={{ marginLeft: 8 }}>
                    Quality: <strong>{result.quality_profile.quality_level}</strong>
                    {' '}({result.quality_profile.quality_score?.toFixed(1)}%)
                  </span>
                )}
              </div>
            )}
            <button className="btn btn-primary" onClick={ingest} disabled={loading}>
              {loading ? '⏳ Ingesting…' : '📥 Ingest Dataset'}
            </button>
          </div>
        </div>
      </div>

      {/* Right: ingested datasets */}
      <div className="card">
        <div className="card-header">Ingested Datasets ({datasetsQuery.data?.datasets?.length ?? 0})</div>
        <div className="card-body">
          {datasetsQuery.data?.datasets?.length === 0 && (
            <div className="empty-state" style={{ padding: 20 }}>No datasets yet</div>
          )}
          {datasetsQuery.data?.datasets?.map(d => (
            <div key={d.dataset_id} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: '1px solid var(--border)' }}>
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text2)' }}>{d.dataset_id}</span>
                <span className={`badge ${d.quality_level === 'HIGH' ? 'badge-ok' : d.quality_level === 'MEDIUM' ? 'badge-warn' : 'badge-err'}`}>
                  {d.quality_level}
                </span>
              </div>
              <div style={{ fontWeight: 700, marginTop: 2 }}>{d.label || d.source_type}</div>
              <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                {d.valid_features}/{d.total_features} valid features
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
