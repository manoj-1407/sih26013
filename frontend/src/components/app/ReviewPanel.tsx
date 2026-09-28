import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }

export default function ReviewPanel({ caseId, isDark }: Props) {
  const qc = useQueryClient();
  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';
  const inputBg = isDark ? '#060d18' : '#f8fafc';

  const { data, isLoading } = useQuery({
    queryKey: ['review', caseId],
    queryFn: () => api.get<{ pending_count: number; items: any[] }>(`/cases/${caseId}/review`),
    enabled: !!caseId,
    refetchInterval: 6_000,
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">✅</div>
      <div className="text-sm">Select a case first</div>
    </div>
  );

  const items = data?.items ?? [];

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold" style={{ color: text }}>Officer Review Queue</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${items.length > 0 ? 'bg-amber-400 animate-pulse' : 'bg-green-400'}`} />
          <span className="text-sm font-bold" style={{ color: items.length > 0 ? '#f59e0b' : '#22c55e' }}>
            {items.length} pending
          </span>
        </div>
      </div>

      {isLoading && <div className="text-center py-10" style={{ color: muted }}>Loading queue…</div>}

      {items.length === 0 && !isLoading && (
        <div className="text-center py-16">
          <div className="text-5xl mb-3">✅</div>
          <div className="text-sm font-medium text-green-500 mb-1">Queue is empty</div>
          <div className="text-xs" style={{ color: muted }}>All proposals have been processed</div>
        </div>
      )}

      <AnimatePresence>
        {items.map((item: any) => <ReviewCard key={item.item_id} item={item} caseId={caseId!} isDark={isDark} bg={bg} border={border} text={text} muted={muted} inputBg={inputBg} qc={qc} />)}
      </AnimatePresence>
    </div>
  );
}

function ReviewCard({ item, caseId, isDark, bg, border, text, muted, inputBg, qc }: any) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [actor, setActor] = useState('Officer');

  const mut = useMutation({
    mutationFn: (decision: string) =>
      api.post(`/cases/${caseId}/proposals/${item.proposal_id}/decide`, { decision, reason, actor }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['review', caseId] }); qc.invalidateQueries({ queryKey: ['parcels', caseId] }); },
  });

  const priorityPct = Math.min(100, (item.priority / 200) * 100);
  const priorityColor = priorityPct > 70 ? '#ef4444' : priorityPct > 40 ? '#f59e0b' : '#3b82f6';

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
      className="rounded-xl overflow-hidden" style={{ background: bg, border: `1px solid ${border}` }}>
      <button className="w-full p-4 text-left" onClick={() => setOpen(v => !v)}>
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-mono text-cyan-400 truncate">{item.parcel_id}</span>
              <span className="text-[9px] font-bold text-amber-400 bg-amber-500/12 border border-amber-500/25 px-1.5 py-0.5 rounded">REVIEW</span>
            </div>
            <div className="text-[11px] mb-2 truncate" style={{ color: muted }}>{item.reason}</div>
            <div className="flex items-center gap-2">
              <div className="flex-1 rounded-full overflow-hidden" style={{ background: isDark ? '#0c1118' : '#e8edf5', height: 4 }}>
                <div className="h-full rounded-full" style={{ width: `${priorityPct}%`, background: priorityColor }} />
              </div>
              <span className="text-[10px] font-mono" style={{ color: priorityColor }}>P{item.priority}</span>
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-[10px]" style={{ color: muted }}>{item.conflict_count} conflicts</div>
            <div className="text-[10px]" style={{ color: muted }}>{Math.round(item.match_confidence * 100)}% conf</div>
            <div style={{ color: muted, fontSize: 10, marginTop: 4 }}>{open ? '▲' : '▼'}</div>
          </div>
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            className="overflow-hidden" style={{ borderTop: `1px solid ${border}` }}>
            <div className="p-4 space-y-3">
              {item.conflict_types?.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {item.conflict_types.map((ct: string) => (
                    <span key={ct} className="text-[9px] font-bold text-amber-400 bg-amber-500/12 border border-amber-500/25 px-1.5 py-0.5 rounded">
                      {ct.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: muted }}>Decision Reason *</label>
                  <input value={reason} onChange={e => setReason(e.target.value)} placeholder="Justification"
                    className="w-full rounded-lg px-3 py-2 text-xs border outline-none"
                    style={{ background: inputBg, borderColor: border, color: text }} />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: muted }}>Officer ID</label>
                  <input value={actor} onChange={e => setActor(e.target.value)}
                    className="w-full rounded-lg px-3 py-2 text-xs border outline-none"
                    style={{ background: inputBg, borderColor: border, color: text }} />
                </div>
              </div>

              {mut.error && <div className="text-xs text-red-400">✗ {(mut.error as any).message}</div>}
              {mut.isSuccess && <div className="text-xs text-green-400">✓ Decision recorded</div>}

              <div className="flex gap-2">
                <button disabled={!reason.trim() || mut.isPending} onClick={() => mut.mutate('APPROVED')}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-semibold text-white bg-green-600 hover:bg-green-500 disabled:opacity-50 rounded-lg transition-colors">
                  ✓ Approve
                </button>
                <button disabled={!reason.trim() || mut.isPending} onClick={() => mut.mutate('REJECTED')}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg transition-colors">
                  ✕ Reject
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
