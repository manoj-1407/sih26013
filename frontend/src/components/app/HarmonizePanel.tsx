import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }

function Bar({ label, val, isDark }: { label: string; val: number; isDark: boolean }) {
  const pct = Math.min(100, Math.round(val * 100));
  const color = pct >= 85 ? '#22c55e' : pct >= 65 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span className="text-[10px] w-24 truncate capitalize" style={{ color: isDark ? '#6b7280' : '#94a3b8' }}>
        {label.replace(/_/g, ' ')}
      </span>
      <div className="flex-1 rounded-full overflow-hidden" style={{ background: isDark ? '#0c1118' : '#e8edf5', height: 5 }}>
        <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.7 }}
          className="h-full rounded-full" style={{ background: color }} />
      </div>
      <span className="text-[10px] font-mono w-7 text-right font-bold" style={{ color }}>{pct}%</span>
    </div>
  );
}

export default function HarmonizePanel({ caseId, isDark }: Props) {
  const qc = useQueryClient();
  const [result, setResult] = useState<any>(null);
  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';

  const mut = useMutation({
    mutationFn: () => api.post<any>(`/cases/${caseId}/harmonize`, {}),
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: ['parcels', caseId] });
      qc.invalidateQueries({ queryKey: ['review-count', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">⚡</div>
      <div className="text-sm">Select a case first</div>
    </div>
  );

  const decColor = (d: string) => d === 'AUTO_APPROVED' ? '#22c55e' : d === 'REVIEW_REQUIRED' ? '#f59e0b' : d === 'BLOCKED' ? '#ef4444' : '#6b7280';

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Run button */}
      <div className="rounded-2xl p-6" style={{ background: bg, border: `1px solid ${border}` }}>
        <h2 className="text-base font-bold mb-2" style={{ color: text }}>Run Harmonization Pipeline</h2>
        <p className="text-sm mb-5" style={{ color: muted }}>
          Match → Conflict Detect → Evidence-Weighted Proposal → Ripple Check → Review Queue
        </p>
        <button disabled={mut.isPending} onClick={() => mut.mutate()}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm px-6 py-2.5 rounded-lg transition-all">
          {mut.isPending ? '⏳ Running…' : '⚡ Run Harmonization'}
        </button>
        {mut.error && <div className="mt-3 text-xs text-red-400">✗ {(mut.error as any).message}</div>}
      </div>

      {result && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { l: 'Records', v: result.total_records, c: '#3b82f6' },
              { l: 'Parcels', v: result.matched_groups, c: '#06b6d4' },
              { l: 'For Review', v: result.review_queue_count, c: '#f59e0b' },
              { l: 'Auto-Approved', v: result.parcels?.filter((p: any) => p.proposal?.decision === 'AUTO_APPROVED').length ?? 0, c: '#22c55e' },
            ].map(({ l, v, c }) => (
              <div key={l} className="rounded-xl p-4 text-center" style={{ background: bg, border: `1px solid ${border}` }}>
                <div className="text-2xl font-black mb-1" style={{ color: c }}>{v}</div>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: muted }}>{l}</div>
              </div>
            ))}
          </div>

          {/* Parcel cards */}
          {result.parcels?.map((p: any, i: number) => {
            const [open, setOpen] = useState(false);
            const dec = p.proposal?.decision ?? 'PENDING';
            const ev = p.proposal as any;
            return (
              <motion.div key={p.parcel_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                className="rounded-xl overflow-hidden" style={{ background: bg, border: `1px solid ${border}` }}>
                <button className="w-full flex items-center gap-3 p-4 text-left" onClick={() => setOpen(v => !v)}>
                  <span className="text-xs font-mono text-cyan-400 flex-1 truncate">{p.parcel_id}</span>
                  <span className="text-[10px] font-bold" style={{ color: decColor(dec) }}>{dec.replace('_', ' ')}</span>
                  <span className="text-[11px]" style={{ color: muted }}>{Math.round(p.match_confidence * 100)}%</span>
                  <span className="text-[11px]" style={{ color: muted }}>{p.source_count} src</span>
                  {p.conflicts?.critical > 0 && <span className="text-[9px] text-red-400 font-bold">{p.conflicts.critical} crit</span>}
                  <span style={{ color: muted }}>{open ? '▲' : '▼'}</span>
                </button>
                <AnimatePresence>
                  {open && (
                    <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
                      className="overflow-hidden" style={{ borderTop: `1px solid ${border}` }}>
                      <div className="p-4 space-y-3">
                        {ev?.confidence_components && (
                          <div>
                            <div className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: muted }}>Evidence</div>
                            {Object.entries(ev.confidence_components).map(([k, v]) =>
                              typeof v === 'number' && v > 0 && v <= 1
                                ? <Bar key={k} label={k} val={v as number} isDark={isDark} />
                                : null
                            )}
                          </div>
                        )}
                        <div className="rounded-lg p-3 text-xs"
                          style={{ background: `${decColor(dec)}14`, border: `1px solid ${decColor(dec)}30`, color: decColor(dec) }}>
                          <div className="font-bold mb-0.5">{dec.replace('_', ' ')}</div>
                          <div className="opacity-80">{p.proposal?.decision_reason}</div>
                        </div>
                        {p.ripple && (
                          <div className="rounded-lg p-3 text-xs"
                            style={{ background: p.ripple.safe_to_auto_approve ? '#22c55e14' : '#f59e0b14', color: p.ripple.safe_to_auto_approve ? '#22c55e' : '#f59e0b', border: `1px solid ${p.ripple.safe_to_auto_approve ? '#22c55e30' : '#f59e0b30'}` }}>
                            🌊 {p.ripple.summary}
                          </div>
                        )}
                        {p.proposal?.change_summary?.map((s: string, si: number) => (
                          <div key={si} className="text-[11px] flex items-start gap-1.5" style={{ color: muted }}>
                            <span className="opacity-40">›</span>{s}
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </>
      )}
    </div>
  );
}
