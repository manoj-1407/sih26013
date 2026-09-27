import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ReviewItem } from '../api/client';

export default function ReviewPanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [actor, setActor] = useState('Officer');
  const [processing, setProcessing] = useState(false);
  const [msg, setMsg] = useState('');

  const queueQuery = useQuery({
    queryKey: ['review', caseId],
    queryFn: () => api.get<{ pending_count: number; items: ReviewItem[] }>(`/cases/${caseId}/review`),
    enabled: !!caseId,
    refetchInterval: 5_000,
  });

  async function decide(proposalId: string, decision: 'APPROVED' | 'REJECTED') {
    if (!caseId) return;
    if (!reason.trim()) { setMsg('Enter a reason'); return; }
    setProcessing(true); setMsg('');
    try {
      await api.post(`/cases/${caseId}/proposals/${proposalId}/decide`, {
        decision, reason, actor,
      });
      setDecidingId(null);
      setReason('');
      setMsg(`✓ Proposal ${decision.toLowerCase()}`);
      qc.invalidateQueries({ queryKey: ['review', caseId] });
      qc.invalidateQueries({ queryKey: ['parcels', caseId] });
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setProcessing(false);
    }
  }

  if (!caseId) {
    return <div className="empty-state"><div className="empty-icon">🔍</div>Select a case first.</div>;
  }

  const items = queueQuery.data?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 style={{ fontSize: 14, fontWeight: 700 }}>Officer Review Queue</h2>
        <span className={`badge ${items.length > 0 ? 'badge-warn' : 'badge-ok'}`}>
          {items.length} pending
        </span>
      </div>

      {msg && (
        <div className={`notice ${msg.startsWith('✓') ? 'notice-green' : 'notice-red'} mb-3`}>
          {msg}
        </div>
      )}

      {items.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">✅</div>
          <div>Review queue is empty — all proposals processed</div>
        </div>
      )}

      {items.map(item => (
        <div key={item.item_id} className="card mb-2">
          <div className="card-header">
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)' }}>{item.parcel_id}</span>
            <span className={`badge ${item.priority > 100 ? 'badge-err' : item.priority > 50 ? 'badge-warn' : 'badge-info'}`}>
              Priority {item.priority}
            </span>
            <span className="ml-auto" style={{ fontSize: 11, color: 'var(--text3)' }}>
              {item.conflict_count} conflicts · {item.ripple_issues} ripple issues
            </span>
          </div>
          <div className="card-body">
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>{item.reason}</div>
            <div className="flex gap-2 items-center mb-2">
              {item.conflict_types.map(ct => (
                <span key={ct} className="badge badge-warn" style={{ fontSize: 10 }}>{ct.replace(/_/g, ' ')}</span>
              ))}
              <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 'auto' }}>
                Confidence: {Math.round(item.match_confidence * 100)}%
              </span>
            </div>

            {decidingId === item.item_id ? (
              <div className="flex-col gap-2">
                <div className="form-group">
                  <label className="form-label">Decision Reason *</label>
                  <input className="form-input" value={reason} onChange={e => setReason(e.target.value)}
                    placeholder="Enter justification for the decision" />
                </div>
                <div className="form-group">
                  <label className="form-label">Officer ID</label>
                  <input className="form-input" value={actor} onChange={e => setActor(e.target.value)} />
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-green btn-sm" disabled={processing}
                    onClick={() => decide(item.proposal_id, 'APPROVED')}>
                    ✓ Approve
                  </button>
                  <button className="btn btn-red btn-sm" disabled={processing}
                    onClick={() => decide(item.proposal_id, 'REJECTED')}>
                    ✕ Reject
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setDecidingId(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button className="btn btn-primary btn-sm" onClick={() => { setDecidingId(item.item_id); setMsg(''); }}>
                Review → Decide
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
