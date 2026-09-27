import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, HarmonizeResult, ParcelResult } from '../api/client';

function ConfBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 85 ? 'var(--green)' : pct >= 65 ? 'var(--amber)' : 'var(--red)';
  return (
    <div className="conf-bar-row">
      <span className="conf-bar-label">{label}</span>
      <div className="conf-bar-track">
        <div className="conf-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="conf-bar-value">{pct}%</span>
    </div>
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const cls = decision === 'AUTO_APPROVED' ? 'badge-ok'
    : decision === 'REVIEW_REQUIRED' ? 'badge-warn'
    : decision === 'BLOCKED' ? 'badge-err'
    : 'badge-neutral';
  return <span className={`badge ${cls}`}>{decision.replace('_', ' ')}</span>;
}

function ParcelCard({ p }: { p: ParcelResult }) {
  const [open, setOpen] = useState(false);
  const ev = p.proposal;
  const conf = ev?.match_confidence ?? p.match_confidence;

  return (
    <div className="card mb-2">
      <div
        className="card-header"
        style={{ cursor: 'pointer' }}
        onClick={() => setOpen(v => !v)}
      >
        <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>{p.parcel_id}</span>
        <span style={{ color: 'var(--text3)', fontSize: 11 }}>
          {p.source_count} sources · {p.independent_lineages} indep. lineages
        </span>
        <span className="ml-auto flex gap-2 items-center">
          <DecisionBadge decision={ev?.decision ?? 'PENDING'} />
          <span style={{ fontSize: 11, color: 'var(--text3)' }}>{open ? '▲' : '▼'}</span>
        </span>
      </div>

      {open && (
        <div className="card-body flex-col gap-3">
          {/* Confidence */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Match Confidence
            </div>
            <div className="conf-bar-container">
              {ev?.confidence_components && Object.entries(ev.confidence_components).map(([k, v]) =>
                typeof v === 'number' && v > 0 && v <= 1
                  ? <ConfBar key={k} label={k} value={v as number} />
                  : null
              )}
              <ConfBar label="Overall" value={conf} />
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text3)' }}>
              {p.independent_lineages} independent source lineage{p.independent_lineages !== 1 ? 's' : ''}
            </div>
          </div>

          <hr className="divider" />

          {/* Conflicts */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Conflicts Detected
            </div>
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
              {[
                { label: 'Critical', value: p.conflicts.critical, color: 'var(--red)' },
                { label: 'High', value: p.conflicts.high, color: 'var(--amber)' },
                { label: 'Medium', value: p.conflicts.medium, color: '#a78bfa' },
                { label: 'Low', value: p.conflicts.low, color: 'var(--text3)' },
              ].map(({ label, value, color }) => (
                <div key={label} className="stat-box">
                  <div className="stat-num" style={{ color, fontSize: 18 }}>{value}</div>
                  <div className="stat-label">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Proposal */}
          {ev && (
            <>
              <hr className="divider" />
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Harmonization Proposal
                </div>
                <div className="kv">
                  <span className="kv-k">Boundary offset</span>
                  <span className="kv-v">{ev.max_boundary_offset_m?.toFixed(2)}m max</span>
                  <span className="kv-k">Area change</span>
                  <span className="kv-v">{ev.area_change_pct?.toFixed(1)}%</span>
                  <span className="kv-k">Decision</span>
                  <span className="kv-v"><DecisionBadge decision={ev.decision} /></span>
                </div>
                {ev.change_summary && ev.change_summary.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {ev.change_summary.map((s, i) => (
                      <div key={i} style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 3 }}>
                        • {s}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Ripple */}
          <hr className="divider" />
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Ripple / Topology Check
            </div>
            <div className={`notice ${p.ripple.safe_to_auto_approve ? 'notice-green' : 'notice-amber'}`}>
              {p.ripple.safe_to_auto_approve ? '✓ ' : '⚠ '}
              {p.ripple.summary}
            </div>
          </div>

          {/* Decision reason */}
          {ev?.decision_reason && (
            <div className={`notice ${ev.decision === 'AUTO_APPROVED' ? 'notice-green' : 'notice-amber'}`}
              style={{ fontSize: 11 }}>
              {ev.decision_reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function HarmonizePanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HarmonizeResult | null>(null);
  const [error, setError] = useState('');

  async function runHarmonization() {
    if (!caseId) { setError('Select a case first'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await api.post<HarmonizeResult>(`/cases/${caseId}/harmonize`, {});
      setResult(res);
      qc.invalidateQueries({ queryKey: ['cases'] });
      qc.invalidateQueries({ queryKey: ['parcels', caseId] });
      qc.invalidateQueries({ queryKey: ['review', caseId] });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (!caseId) {
    return <div className="empty-state"><div className="empty-icon">⚡</div>Select a case first.</div>;
  }

  return (
    <div>
      <div className="card mb-3">
        <div className="card-header">Run Harmonization Pipeline</div>
        <div className="card-body">
          <p style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 12 }}>
            Runs the full pipeline: <strong>Ingest → Match → Conflict Detect → Propose → Ripple Check → Queue</strong>
          </p>
          <button className="btn btn-primary" onClick={runHarmonization} disabled={loading}>
            {loading ? '⏳ Running pipeline…' : '⚡ Run Harmonization'}
          </button>
          {error && <div className="notice notice-red mt-2">{error}</div>}
        </div>
      </div>

      {result && (
        <>
          <div className="stat-grid mb-3">
            <div className="stat-box">
              <div className="stat-num">{result.total_records}</div>
              <div className="stat-label">Records</div>
            </div>
            <div className="stat-box">
              <div className="stat-num">{result.matched_groups}</div>
              <div className="stat-label">Parcels</div>
            </div>
            <div className="stat-box">
              <div className="stat-num" style={{ color: 'var(--amber)' }}>{result.review_queue_count}</div>
              <div className="stat-label">For Review</div>
            </div>
            <div className="stat-box">
              <div className="stat-num" style={{ color: 'var(--green)' }}>
                {result.parcels.filter(p => p.proposal.decision === 'AUTO_APPROVED').length}
              </div>
              <div className="stat-label">Auto-Approved</div>
            </div>
          </div>

          <div>
            {result.parcels.map(p => <ParcelCard key={p.parcel_id} p={p} />)}
          </div>
        </>
      )}
    </div>
  );
}
