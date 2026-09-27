import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, Case } from '../api/client';

interface Props {
  activeCaseId: string | null;
  onSelectCase: (id: string) => void;
}

export default function CasesPanel({ activeCaseId, onSelectCase }: Props) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState('');
  const [caseId, setCaseId] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [demoMsg, setDemoMsg] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['cases'],
    queryFn: () => api.get<{ cases: Case[] }>('/cases'),
    refetchInterval: 5_000,
  });

  async function loadWard42Demo() {
    setLoadingDemo(true); setDemoMsg('');
    try {
      const res = await api.post<any>('/demo/load-ward42?force_reload=false', {});
      qc.invalidateQueries({ queryKey: ['cases'] });
      onSelectCase('WARD42-DEMO');
      setDemoMsg(
        res.status === 'already_loaded'
          ? '✓ Ward 42 demo already loaded'
          : `✓ Loaded: ${res.parcels_matched} parcels, ${res.review_required} for review`
      );
    } catch (e: any) {
      setDemoMsg(`Error: ${e.message}`);
    } finally {
      setLoadingDemo(false);
    }
  }

  async function createCase() {
    if (!title.trim()) { setError('Title is required'); return; }
    setCreating(true);
    setError('');
    try {
      const res = await api.post<{ case_id: string }>('/cases', {
        case_id: caseId.trim() || undefined,
        title: title.trim(),
      });
      qc.invalidateQueries({ queryKey: ['cases'] });
      onSelectCase(res.case_id);
      setShowForm(false);
      setTitle('');
      setCaseId('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      {/* Demo quick-load */}
      <div className="card mb-3" style={{ borderColor: 'var(--accent)', background: 'rgba(59,130,246,0.05)' }}>
        <div className="card-header" style={{ color: 'var(--accent)' }}>🚀 Ward 42 Demo</div>
        <div className="card-body">
          <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>
            One-click load: 4 source datasets for Ward 42 with known conflicts on Parcel P-1042.
            Demonstrates matching, conflict detection, minimum-change proposal, and ripple check.
          </div>
          {demoMsg && (
            <div className={`notice ${demoMsg.startsWith('✓') ? 'notice-green' : 'notice-red'} mb-2`}>
              {demoMsg}
            </div>
          )}
          <button className="btn btn-primary btn-sm" onClick={loadWard42Demo} disabled={loadingDemo}>
            {loadingDemo ? '⏳ Loading Ward 42…' : '⚡ Load Ward 42 Demo'}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 style={{ fontSize: 14, fontWeight: 700 }}>Harmonization Cases</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(v => !v)}>
          {showForm ? '✕ Cancel' : '+ New Case'}
        </button>
      </div>

      {showForm && (
        <div className="card mb-3">
          <div className="card-header">Create new case</div>
          <div className="card-body flex-col gap-2">
            <div className="form-group">
              <label className="form-label">Title *</label>
              <input className="form-input" value={title} onChange={e => setTitle(e.target.value)}
                placeholder="e.g. Ward 42 Harmonization 2024" />
            </div>
            <div className="form-group">
              <label className="form-label">Case ID (optional)</label>
              <input className="form-input" value={caseId} onChange={e => setCaseId(e.target.value)}
                placeholder="Auto-generated if blank" style={{ fontFamily: 'var(--mono)' }} />
            </div>
            {error && <div className="notice notice-red">{error}</div>}
            <button className="btn btn-primary btn-sm" onClick={createCase} disabled={creating}>
              {creating ? 'Creating…' : '✓ Create Case'}
            </button>
          </div>
        </div>
      )}

      {isLoading && <div className="loading">Loading cases…</div>}

      {data?.cases?.length === 0 && !isLoading && (
        <div className="empty-state">
          <div className="empty-icon">📁</div>
          <div>No cases yet. Create one to begin.</div>
        </div>
      )}

      {data?.cases?.map(c => (
        <div
          key={c.case_id}
          onClick={() => onSelectCase(c.case_id)}
          style={{
            background: activeCaseId === c.case_id ? 'rgba(59,130,246,0.08)' : 'var(--surface)',
            border: `1px solid ${activeCaseId === c.case_id ? 'var(--accent)' : 'var(--border)'}`,
            borderRadius: 8, padding: '10px 14px', marginBottom: 8, cursor: 'pointer',
          }}
        >
          <div className="flex items-center justify-between">
            <span style={{ fontWeight: 700, fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--cyan)' }}>
              {c.case_id}
            </span>
            <span className={`badge ${c.status === 'ACTIVE' ? 'badge-ok' : 'badge-neutral'}`}>
              {c.status}
            </span>
          </div>
          <div style={{ color: 'var(--text)', marginTop: 3 }}>{c.title}</div>
          {c.stats && (
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 5 }}>
              {c.stats.datasets} datasets · {c.stats.canonical_parcels} parcels ·
              {' '}{c.stats.conflicts} conflicts · {c.stats.proposals} proposals
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
