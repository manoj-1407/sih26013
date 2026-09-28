import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }
const NODE_COLORS: Record<string, string> = { origin: '#22c55e', dataset: '#3b82f6', transformation: '#f59e0b', record: '#06b6d4', agent: '#8b5cf6', activity: '#9aadcb' };

export default function ProvenancePanel({ caseId, isDark }: Props) {
  const qc = useQueryClient();
  const [nodeId, setNodeId] = useState('');
  const [nodeType, setNodeType] = useState('origin');
  const [parents, setParents] = useState('');
  const [label, setLabel] = useState('');
  const [msg, setMsg] = useState('');

  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';
  const inputBg = isDark ? '#060d18' : '#f8fafc';

  const { data: graph } = useQuery({
    queryKey: ['provenance', caseId],
    queryFn: () => api.get<{ nodes: any[]; edges: any[] }>(`/cases/${caseId}/provenance`),
    enabled: !!caseId,
  });

  const mut = useMutation({
    mutationFn: () => api.post(`/cases/${caseId}/provenance/nodes`, {
      node_id: nodeId, node_type: nodeType,
      parent_ids: parents.split(',').map(s => s.trim()).filter(Boolean),
      label,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['provenance', caseId] });
      setMsg(`✓ Node "${nodeId}" added`);
      setNodeId(''); setLabel(''); setParents('');
    },
    onError: (e: any) => setMsg(`✗ ${e.message}`),
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">🌐</div>
      <div className="text-sm">Select a case first</div>
    </div>
  );

  const origins = graph?.nodes?.filter(n => n.node_type === 'origin') ?? [];

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Graph */}
      <div className="space-y-4">
        <h2 className="text-base font-bold" style={{ color: text }}>Provenance Graph</h2>

        {origins.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="rounded-xl p-4 border border-green-500/20"
            style={{ background: isDark ? 'rgba(34,197,94,0.06)' : 'rgba(34,197,94,0.04)' }}>
            <div className="text-2xl font-black text-green-400 mb-1">{origins.length} independent origin{origins.length > 1 ? 's' : ''}</div>
            <div className="text-xs" style={{ color: muted }}>
              The engine traces lineage to count origins, not files.
              Multiple datasets from the same origin = 1 independent observation.
            </div>
          </motion.div>
        )}

        <div className="rounded-2xl overflow-hidden" style={{ background: bg, border: `1px solid ${border}` }}>
          {(['origin', 'dataset', 'transformation', 'record'] as const).map(type => {
            const nodes = graph?.nodes?.filter((n: any) => n.node_type === type) ?? [];
            if (!nodes.length) return null;
            const color = NODE_COLORS[type];
            return (
              <div key={type} style={{ borderBottom: `1px solid ${border}` }}>
                <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest" style={{ color }}>
                  {type} ({nodes.length})
                </div>
                {nodes.map((n: any, i: number) => {
                  const parentEdges = graph?.edges?.filter((e: any) => e.from === n.node_id) ?? [];
                  return (
                    <motion.div key={n.node_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}
                      className="px-4 py-2.5" style={{ borderBottom: `1px solid ${border}40` }}>
                      <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className="text-xs font-mono" style={{ color }}>{n.node_id}</span>
                      </div>
                      {n.label && <div className="text-[11px] mt-0.5 ml-3.5" style={{ color: muted }}>{n.label}</div>}
                      {parentEdges.length > 0 && (
                        <div className="text-[10px] mt-0.5 ml-3.5" style={{ color: `${muted}80` }}>
                          ← {parentEdges.map((e: any) => e.to).join(', ')}
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            );
          })}
          {!graph?.nodes?.length && (
            <div className="p-10 text-center text-sm" style={{ color: muted }}>No provenance nodes yet</div>
          )}
        </div>
      </div>

      {/* Add node */}
      <div className="space-y-4">
        <h2 className="text-base font-bold" style={{ color: text }}>Add Provenance Node</h2>
        <div className="rounded-2xl p-5 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: muted }}>Node ID *</label>
            <input value={nodeId} onChange={e => setNodeId(e.target.value)} placeholder="e.g. ORIG-SURVEY-1999"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none font-mono"
              style={{ background: inputBg, borderColor: border, color: text }} />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: muted }}>Node Type</label>
            <select value={nodeType} onChange={e => setNodeType(e.target.value)}
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
              style={{ background: inputBg, borderColor: border, color: text }}>
              {['origin', 'dataset', 'transformation', 'record', 'agent', 'activity'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: muted }}>Parent IDs (comma-separated)</label>
            <input value={parents} onChange={e => setParents(e.target.value)} placeholder="e.g. ORIG-1999, ORIG-2022"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none font-mono"
              style={{ background: inputBg, borderColor: border, color: text, fontSize: 11 }} />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: muted }}>Label</label>
            <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Human-readable description"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
              style={{ background: inputBg, borderColor: border, color: text }} />
          </div>
          {msg && <div className={`text-xs ${msg.startsWith('✓') ? 'text-green-400' : 'text-red-400'}`}>{msg}</div>}
          <button disabled={!nodeId.trim() || mut.isPending} onClick={() => mut.mutate()}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm px-5 py-2.5 rounded-lg transition-all">
            {mut.isPending ? '⏳ Adding…' : '+ Add Node'}
          </button>
        </div>

        {/* Legend */}
        <div className="rounded-xl p-4 space-y-2" style={{ background: bg, border: `1px solid ${border}` }}>
          <div className="text-xs font-semibold mb-3" style={{ color: text }}>Node Types</div>
          {Object.entries(NODE_COLORS).map(([t, c]) => (
            <div key={t} className="flex items-center gap-2.5 text-xs" style={{ color: muted }}>
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: c }} />
              <span className="font-mono" style={{ color: c }}>{t}</span>
              <span>— {t === 'origin' ? 'independent data source (root)' : t === 'dataset' ? 'derived from origin' : t === 'transformation' ? 'processing step' : t === 'record' ? 'individual feature record' : t === 'agent' ? 'organization/person' : 'workflow activity'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
