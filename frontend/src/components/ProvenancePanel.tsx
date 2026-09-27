import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ProvenanceGraph } from '../api/client';

const NODE_TYPE_COLOR: Record<string, string> = {
  origin: 'var(--green)',
  dataset: 'var(--accent)',
  transformation: 'var(--amber)',
  record: 'var(--cyan)',
  agent: 'var(--purple)',
  activity: '#9aadcb',
};

export default function ProvenancePanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [nodeId, setNodeId] = useState('');
  const [nodeType, setNodeType] = useState('origin');
  const [parentIds, setParentIds] = useState('');
  const [label, setLabel] = useState('');
  const [error, setError] = useState('');
  const [added, setAdded] = useState('');

  const graphQuery = useQuery({
    queryKey: ['provenance', caseId],
    queryFn: () => api.get<ProvenanceGraph>(`/cases/${caseId}/provenance`),
    enabled: !!caseId,
  });

  async function addNode() {
    if (!caseId) return;
    if (!nodeId.trim()) { setError('Node ID is required'); return; }
    setError(''); setAdded('');
    try {
      await api.post(`/cases/${caseId}/provenance/nodes`, {
        node_id: nodeId.trim(),
        node_type: nodeType,
        parent_ids: parentIds.split(',').map(s => s.trim()).filter(Boolean),
        label: label.trim(),
      });
      qc.invalidateQueries({ queryKey: ['provenance', caseId] });
      setAdded(`✓ Node ${nodeId} added`);
      setNodeId(''); setLabel(''); setParentIds('');
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (!caseId) {
    return <div className="empty-state"><div className="empty-icon">🌐</div>Select a case first.</div>;
  }

  const graph = graphQuery.data;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
      {/* Left: graph visualization */}
      <div className="card">
        <div className="card-header">
          Provenance Graph
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text3)' }}>
            {graph?.nodes?.length ?? 0} nodes · {graph?.edges?.length ?? 0} edges
          </span>
        </div>
        <div className="card-body">
          {!graph?.nodes?.length && (
            <div className="empty-state"><div className="empty-icon">🌐</div>No provenance nodes yet</div>
          )}
          {/* Group by type */}
          {(['origin', 'dataset', 'transformation', 'record', 'agent'] as const).map(type => {
            const nodes = graph?.nodes?.filter(n => n.node_type === type) ?? [];
            if (!nodes.length) return null;
            return (
              <div key={type} style={{ marginBottom: 16 }}>
                <div style={{
                  fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
                  color: NODE_TYPE_COLOR[type], marginBottom: 6,
                }}>
                  {type} nodes ({nodes.length})
                </div>
                {nodes.map(n => {
                  const parents = graph!.edges.filter(e => e.from === n.node_id).map(e => e.to);
                  return (
                    <div key={n.node_id} style={{
                      background: 'var(--surface2)', border: '1px solid var(--border)',
                      borderLeft: `3px solid ${NODE_TYPE_COLOR[type]}`,
                      borderRadius: 6, padding: '6px 10px', marginBottom: 6,
                    }}>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: NODE_TYPE_COLOR[type] }}>
                        {n.node_id}
                      </div>
                      {n.label && <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>{n.label}</div>}
                      {parents.length > 0 && (
                        <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
                          ← derives from: {parents.join(', ')}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}

          {/* Independence summary */}
          {(graph?.nodes?.filter(n => n.node_type === 'origin') ?? []).length > 0 && (
            <div className="notice notice-blue mt-2">
              <strong>{graph!.nodes.filter(n => n.node_type === 'origin').length} independent origins</strong> — 
              the engine uses lineage tracing, not source count, to determine evidence independence.
              Multiple datasets descending from the same origin count as <em>one</em> independent observation.
            </div>
          )}
        </div>
      </div>

      {/* Right: add node form */}
      <div className="card">
        <div className="card-header">Add Provenance Node</div>
        <div className="card-body flex-col gap-2">
          <div className="form-group">
            <label className="form-label">Node ID *</label>
            <input className="form-input" value={nodeId} onChange={e => setNodeId(e.target.value)}
              placeholder="e.g. ORIG-SURVEY-1999" style={{ fontFamily: 'var(--mono)' }} />
          </div>
          <div className="form-group">
            <label className="form-label">Node Type</label>
            <select className="form-select" value={nodeType} onChange={e => setNodeType(e.target.value)}>
              {['origin', 'dataset', 'transformation', 'record', 'agent', 'activity'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Parent IDs (comma-separated)</label>
            <input className="form-input" value={parentIds} onChange={e => setParentIds(e.target.value)}
              placeholder="e.g. ORIG-SURVEY-1999, ORIG-AERIAL-2022" style={{ fontFamily: 'var(--mono)', fontSize: 11 }} />
          </div>
          <div className="form-group">
            <label className="form-label">Label</label>
            <input className="form-input" value={label} onChange={e => setLabel(e.target.value)}
              placeholder="Human-readable description" />
          </div>
          {error && <div className="notice notice-red">{error}</div>}
          {added && <div className="notice notice-green">{added}</div>}
          <button className="btn btn-primary btn-sm" onClick={addNode}>
            + Add Node
          </button>

          <hr className="divider" />
          <div style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.6 }}>
            <strong style={{ color: 'var(--text2)' }}>Node types:</strong><br />
            <code style={{ fontFamily: 'var(--mono)' }}>origin</code> — independent data source<br />
            <code style={{ fontFamily: 'var(--mono)' }}>dataset</code> — derived from an origin<br />
            <code style={{ fontFamily: 'var(--mono)' }}>transformation</code> — processing step<br />
            <code style={{ fontFamily: 'var(--mono)' }}>record</code> — individual feature record
          </div>
        </div>
      </div>
    </div>
  );
}
