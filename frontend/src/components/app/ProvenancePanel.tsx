import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }
const NODE_COLORS: Record<string, string> = {
  origin: '#22c55e',
  dataset: '#3b82f6',
  transformation: '#f59e0b',
  record: '#06b6d4',
  agent: '#8b5cf6',
  activity: '#9aadcb',
};

const SCENARIO_COLORS = ['#ef4444', '#22c55e', '#3b82f6'];

export default function ProvenancePanel({ caseId, isDark }: Props) {
  const qc = useQueryClient();
  const [nodeId, setNodeId]   = useState('');
  const [nodeType, setNodeType] = useState('origin');
  const [parents, setParents] = useState('');
  const [label, setLabel]     = useState('');
  const [msg, setMsg]         = useState('');
  const [demoTab, setDemoTab] = useState<'graph' | 'demo'>('demo');

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

  // Independence demo — always available, no case required
  const { data: demoData, isLoading: demoLoading } = useQuery({
    queryKey: ['prov-demo'],
    queryFn: () => api.get<any>('/demo/provenance-demo'),
    staleTime: 60_000,
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

  const origins = graph?.nodes?.filter((n: any) => n.node_type === 'origin') ?? [];

  return (
    <div className="max-w-5xl mx-auto space-y-5">

      {/* Tab switcher */}
      <div style={{ display:'flex', gap:0, background: isDark?'rgba(6,13,24,0.6)':'rgba(0,0,0,0.05)', borderRadius:10, padding:3, width:'fit-content' }}>
        {(['demo','graph'] as const).map(t => (
          <button key={t} onClick={() => setDemoTab(t)}
            style={{
              padding:'7px 18px', borderRadius:8, border:'none', cursor:'pointer',
              fontSize:12, fontWeight:600, textTransform:'uppercase', letterSpacing:'0.05em',
              background: demoTab===t ? (isDark?'rgba(59,130,246,0.2)':'rgba(59,130,246,0.12)') : 'transparent',
              color: demoTab===t ? '#60a5fa' : muted,
              transition:'all 0.15s',
            }}
          >
            {t === 'demo' ? '🔬 Independence Demo' : '🌐 Graph'}
          </button>
        ))}
      </div>

      {/* ── DEMO TAB ─────────────────────────────────────────────────────── */}
      {demoTab === 'demo' && (
        <div className="space-y-4">
          {/* Key insight banner */}
          <div style={{ borderRadius:12, padding:'14px 18px', background:'rgba(59,130,246,0.08)', border:'1px solid rgba(59,130,246,0.2)' }}>
            <div style={{ fontSize:13, fontWeight:700, color:'#60a5fa', marginBottom:4 }}>
              Source count ≠ Independent evidence count
            </div>
            <div style={{ fontSize:12, color:muted, lineHeight:1.6 }}>
              {demoData?.key_insight ?? 'Loading…'}
            </div>
          </div>

          {/* Origin DAG visual */}
          {demoData && (
            <div style={{ borderRadius:12, padding:16, background:bg, border:'1px solid '+border }}>
              <div style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.08em', color:muted, marginBottom:12 }}>
                Ward 42 — Provenance DAG
              </div>
              {/* Origins row */}
              <div style={{ display:'flex', gap:8, marginBottom:12, flexWrap:'wrap' }}>
                {demoData.graph_summary.origins.map((o: any, i: number) => (
                  <div key={o.node_id} style={{
                    flex:1, minWidth:120, borderRadius:8, padding:'8px 12px',
                    background:'rgba(34,197,94,0.1)', border:'1px solid rgba(34,197,94,0.3)',
                  }}>
                    <div style={{ fontSize:9, fontWeight:700, color:'#22c55e', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:2 }}>
                      ORIGIN {i+1}
                    </div>
                    <div style={{ fontSize:11, fontWeight:600, color:text }}>{o.node_id}</div>
                    <div style={{ fontSize:10, color:muted }}>{o.label}</div>
                  </div>
                ))}
              </div>
              {/* Datasets row */}
              <div style={{ display:'flex', gap:8, marginBottom:4, flexWrap:'wrap' }}>
                {demoData.graph_summary.datasets.map((d: any) => {
                  // Find which origin this dataset descends from
                  const originIdx = demoData.graph_summary.origins.findIndex(
                    (o: any) => d.parent_ids.includes(o.node_id)
                  );
                  const originColors = ['rgba(34,197,94,0.08)', 'rgba(251,191,36,0.08)', 'rgba(6,182,212,0.08)'];
                  const originBorders = ['rgba(34,197,94,0.25)', 'rgba(251,191,36,0.25)', 'rgba(6,182,212,0.25)'];
                  const tcl = ['#22c55e', '#fbbf24', '#06b6d4'];
                  return (
                    <div key={d.node_id} style={{
                      flex:1, minWidth:100, borderRadius:8, padding:'6px 10px',
                      background: originColors[originIdx] ?? 'rgba(59,130,246,0.08)',
                      border:'1px solid '+(originBorders[originIdx] ?? 'rgba(59,130,246,0.3)'),
                    }}>
                      <div style={{ fontSize:9, color: tcl[originIdx] ?? '#3b82f6', fontWeight:700, marginBottom:1 }}>
                        ↑ {d.parent_ids[0]}
                      </div>
                      <div style={{ fontSize:10, color:text, fontWeight:600 }}>{d.node_id}</div>
                      <div style={{ fontSize:9, color:muted }}>{d.label}</div>
                    </div>
                  );
                })}
              </div>
              <div style={{ fontSize:10, color:muted, textAlign:'center', marginTop:8 }}>
                ↑ Both Cadastral and Revenue/RoR descend from the same 1999 survey
              </div>
            </div>
          )}

          {/* Scenario cards */}
          {demoLoading && (
            <div style={{ textAlign:'center', padding:24, color:muted, fontSize:13 }}>Loading demo…</div>
          )}
          {demoData?.scenarios?.map((s: any, i: number) => {
            const isCorrelated = !s.is_independent && s.independent_lineages === 1;
            const accentColor = isCorrelated ? '#ef4444' : i === 1 ? '#22c55e' : '#3b82f6';
            const bgColor = isCorrelated ? 'rgba(239,68,68,0.07)' : i === 1 ? 'rgba(34,197,94,0.07)' : 'rgba(59,130,246,0.07)';
            const borderColor = isCorrelated ? 'rgba(239,68,68,0.25)' : i === 1 ? 'rgba(34,197,94,0.25)' : 'rgba(59,130,246,0.25)';

            return (
              <motion.div key={i} initial={{ opacity:0, y:6 }} animate={{ opacity:1, y:0 }} transition={{ delay: i * 0.08 }}
                style={{ borderRadius:12, padding:16, background:bgColor, border:'1px solid '+borderColor }}>
                <div style={{ display:'flex', alignItems:'flex-start', gap:12, marginBottom:10 }}>
                  <div style={{ flexShrink:0 }}>
                    <div style={{ fontSize:22 }}>{isCorrelated ? '⚠️' : i === 1 ? '✅' : '🔵'}</div>
                  </div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:13, fontWeight:700, color:accentColor, marginBottom:2 }}>{s.label}</div>
                    <div style={{ fontSize:11, color:muted, lineHeight:1.5 }}>{s.description}</div>
                  </div>
                </div>

                {/* Metrics */}
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8, marginBottom:10 }}>
                  <div style={{ borderRadius:8, padding:'8px 10px', background:isDark?'rgba(0,0,0,0.3)':'rgba(255,255,255,0.6)' }}>
                    <div style={{ fontSize:9, color:muted, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:3 }}>Source files</div>
                    <div style={{ fontSize:18, fontWeight:800, color:text }}>{s.record_ids.length}</div>
                  </div>
                  <div style={{ borderRadius:8, padding:'8px 10px', background:isDark?'rgba(0,0,0,0.3)':'rgba(255,255,255,0.6)' }}>
                    <div style={{ fontSize:9, color:muted, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:3 }}>Independent origins</div>
                    <div style={{ fontSize:18, fontWeight:800, color:accentColor }}>{s.independent_lineages}</div>
                  </div>
                  <div style={{ borderRadius:8, padding:'8px 10px', background:isDark?'rgba(0,0,0,0.3)':'rgba(255,255,255,0.6)' }}>
                    <div style={{ fontSize:9, color:muted, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:3 }}>Provenance score</div>
                    <div style={{ fontSize:18, fontWeight:800, color:accentColor }}>{Math.round(s.provenance_score * 100)}%</div>
                  </div>
                </div>

                {/* Bar */}
                <div style={{ marginBottom:8 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:muted, marginBottom:3 }}>
                    <span>Provenance signal contribution</span>
                    <span style={{ color:accentColor, fontWeight:700 }}>{Math.round(s.provenance_score * 100)}%</span>
                  </div>
                  <div style={{ height:6, borderRadius:999, background:isDark?'#0c1118':'#e8edf5', overflow:'hidden' }}>
                    <motion.div
                      initial={{ width:0 }} animate={{ width: Math.round(s.provenance_score * 100)+'%' }}
                      transition={{ duration:0.8, delay: i * 0.1 }}
                      style={{ height:'100%', background:accentColor, borderRadius:999 }}
                    />
                  </div>
                </div>

                {/* Interpretation badge */}
                <div style={{ fontSize:11, fontWeight:600, color:accentColor }}>
                  {s.interpretation}
                </div>

                {/* Origin breakdown */}
                {s.origins?.length > 0 && (
                  <div style={{ marginTop:8, fontSize:10, color:muted }}>
                    Origins: {s.origins.join(' · ')}
                  </div>
                )}
              </motion.div>
            );
          })}

          {/* Scoring rule footnote */}
          {demoData?.scoring_rule && (
            <div style={{ borderRadius:10, padding:'12px 14px', background:isDark?'rgba(0,0,0,0.3)':'rgba(0,0,0,0.04)', border:'1px solid '+border }}>
              <div style={{ fontSize:10, fontWeight:700, color:muted, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:6 }}>
                How provenance affects confidence
              </div>
              {Object.entries(demoData.scoring_rule).map(([k, v]: [string, any]) => (
                <div key={k} style={{ display:'flex', gap:8, marginBottom:3 }}>
                  <span style={{ fontSize:9, fontFamily:'monospace', color:'#60a5fa', flexShrink:0,
                    background:'rgba(59,130,246,0.1)', padding:'1px 5px', borderRadius:3 }}>{k}</span>
                  <span style={{ fontSize:10, color:muted }}>{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── GRAPH TAB ────────────────────────────────────────────────────── */}
      {demoTab === 'graph' && (
        <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="space-y-4">
            <h2 className="text-base font-bold" style={{ color: text }}>Provenance Graph</h2>

            {!caseId && (
              <div style={{ borderRadius:10, padding:12, background:'rgba(245,158,11,0.08)', border:'1px solid rgba(245,158,11,0.2)', fontSize:12, color:'#f59e0b' }}>
                Select a case to view its provenance graph.
              </div>
            )}

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
              {!graph?.nodes?.length && caseId && (
                <div className="p-10 text-center text-sm" style={{ color: muted }}>No provenance nodes yet</div>
              )}
            </div>
          </div>

          {/* Add node */}
          <div className="space-y-4">
            <h2 className="text-base font-bold" style={{ color: text }}>Add Provenance Node</h2>
            <div className="rounded-2xl p-5 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
              {!caseId && (
                <div style={{ fontSize:12, color:'#f59e0b' }}>Select a case first.</div>
              )}
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
              <button disabled={!nodeId.trim() || !caseId || mut.isPending} onClick={() => mut.mutate()}
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
      )}
    </div>
  );
}
