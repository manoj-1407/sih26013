import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { GitBranch, Plus, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

const NODE_COLORS: Record<string, string> = {
  origin: '#22c55e', dataset: '#3b82f6', transformation: '#f59e0b',
  record: '#06b6d4', agent: '#8b5cf6', activity: '#9aadcb',
};

export default function ProvenancePanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [nodeId, setNodeId] = useState('');
  const [nodeType, setNodeType] = useState('origin');
  const [parents, setParents] = useState('');
  const [label, setLabel] = useState('');
  const [msg, setMsg] = useState('');

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
      setMsg(`✓ Node ${nodeId} added`);
      setNodeId(''); setLabel(''); setParents('');
    },
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
      <GitBranch size={40} className="opacity-20" />
      <p className="text-sm">Select a case first</p>
    </div>
  );

  const origins = graph?.nodes?.filter(n => n.node_type === 'origin') ?? [];
  const independentCount = origins.length;

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Graph */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white">Provenance Graph</h2>
          <div className="text-xs text-gray-600">{graph?.nodes?.length ?? 0} nodes · {graph?.edges?.length ?? 0} edges</div>
        </div>

        {independentCount > 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass rounded-xl p-4 border-green-500/20"
          >
            <div className="text-lg font-black text-green-400 mb-1">{independentCount} independent origin{independentCount > 1 ? 's' : ''}</div>
            <div className="text-xs text-gray-500">
              The engine traces lineage to count origins, not source files.
              Multiple datasets from one origin = 1 independent observation.
            </div>
          </motion.div>
        )}

        <div className="glass rounded-2xl overflow-hidden">
          {(['origin', 'dataset', 'transformation', 'record'] as const).map(type => {
            const nodes = graph?.nodes?.filter(n => n.node_type === type) ?? [];
            if (!nodes.length) return null;
            const color = NODE_COLORS[type];
            return (
              <div key={type} className="border-b border-dark-200/30 last:border-0">
                <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-widest" style={{ color }}>
                  {type} nodes ({nodes.length})
                </div>
                {nodes.map((n, i) => {
                  const parentEdges = graph?.edges?.filter(e => e.from === n.node_id) ?? [];
                  return (
                    <motion.div key={n.node_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }}
                      className="px-4 py-2.5 hover:bg-dark-300/20 transition-colors">
                      <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className="text-xs font-mono" style={{ color }}>{n.node_id}</span>
                      </div>
                      {n.label && <div className="text-[11px] text-gray-500 mt-0.5 ml-3.5">{n.label}</div>}
                      {parentEdges.length > 0 && (
                        <div className="text-[10px] text-gray-700 mt-1 ml-3.5">
                          derives from: {parentEdges.map(e => e.to).join(', ')}
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            );
          })}
          {!graph?.nodes?.length && (
            <div className="p-8 text-center text-gray-600 text-sm">No provenance nodes yet</div>
          )}
        </div>
      </div>

      {/* Add node form */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-white">Add Provenance Node</h2>
        <div className="glass rounded-2xl p-5 space-y-4">
          <div>
            <label className="section-title">Node ID *</label>
            <input className="input-field font-mono" value={nodeId} onChange={e => setNodeId(e.target.value)} placeholder="e.g. ORIG-SURVEY-1999" />
          </div>
          <div>
            <label className="section-title">Node Type</label>
            <select className="select-field" value={nodeType} onChange={e => setNodeType(e.target.value)}>
              {['origin', 'dataset', 'transformation', 'record', 'agent', 'activity'].map(t => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="section-title">Parent IDs (comma-separated)</label>
            <input className="input-field font-mono text-xs" value={parents} onChange={e => setParents(e.target.value)} placeholder="e.g. ORIG-1999, ORIG-2022" />
          </div>
          <div>
            <label className="section-title">Label</label>
            <input className="input-field" value={label} onChange={e => setLabel(e.target.value)} placeholder="Human-readable description" />
          </div>
          {msg && <div className="text-xs text-green-400">{msg}</div>}
          {mut.error && <div className="text-xs text-red-400">{(mut.error as any).message}</div>}
          <button className="btn-primary" disabled={!nodeId || mut.isPending} onClick={() => mut.mutate()}>
            {mut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Add Node
          </button>
        </div>

        <div className="glass rounded-xl p-4 text-xs text-gray-500 space-y-2">
          <div className="font-medium text-gray-400">Node Types:</div>
          {Object.entries(NODE_COLORS).map(([t, c]) => (
            <div key={t} className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: c }} />
              <span style={{ color: c }} className="font-mono">{t}</span>
              <span>— {t === 'origin' ? 'independent data source' : t === 'dataset' ? 'derived from origin' : t === 'transformation' ? 'processing step' : t === 'record' ? 'individual feature' : t === 'agent' ? 'organization/person' : 'workflow activity'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
