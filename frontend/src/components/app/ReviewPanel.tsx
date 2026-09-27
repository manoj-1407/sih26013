import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ClipboardCheck, CheckCircle2, XCircle, Loader2, AlertTriangle, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { api, ReviewItem } from '../../api/client';

function PriorityBar({ priority }: { priority: number }) {
  const max = 200;
  const pct = Math.min(100, (priority / max) * 100);
  const color = pct > 70 ? '#ef4444' : pct > 40 ? '#f59e0b' : '#3b82f6';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-dark-600 rounded-full h-1.5 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[10px] font-mono" style={{ color }}>{priority}</span>
    </div>
  );
}

function ReviewCard({ item, caseId }: { item: ReviewItem; caseId: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [actor, setActor] = useState('Officer');

  const mut = useMutation({
    mutationFn: (decision: 'APPROVED' | 'REJECTED') =>
      api.post(`/cases/${caseId}/proposals/${item.proposal_id}/decide`, { decision, reason, actor }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review', caseId] });
      qc.invalidateQueries({ queryKey: ['parcels', caseId] });
    },
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass rounded-xl overflow-hidden"
    >
      <button
        className="w-full p-4 text-left hover:bg-dark-300/30 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-cyan-400 truncate">{item.parcel_id}</span>
              <span className="badge-warn text-[9px]">REVIEW</span>
            </div>
            <div className="text-[11px] text-gray-500 truncate mb-2">{item.reason}</div>
            <PriorityBar priority={item.priority} />
          </div>
          <div className="flex flex-col items-end gap-1 flex-shrink-0">
            <span className="text-[10px] text-gray-600">{item.conflict_count} conflicts · {item.ripple_issues} ripple</span>
            <span className="text-[10px] font-mono text-gray-600">{Math.round(item.match_confidence * 100)}% conf</span>
            {open ? <ChevronUp size={12} className="text-gray-600" /> : <ChevronDown size={12} className="text-gray-600" />}
          </div>
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="overflow-hidden border-t border-dark-200/30"
          >
            <div className="p-4 space-y-3">
              {item.conflict_types.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {item.conflict_types.map(ct => (
                    <span key={ct} className="badge-warn text-[9px]">{ct.replace(/_/g, ' ')}</span>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="section-title">Decision Reason *</label>
                  <input className="input-field text-xs" value={reason} onChange={e => setReason(e.target.value)}
                    placeholder="Justification for decision" />
                </div>
                <div>
                  <label className="section-title">Officer ID</label>
                  <input className="input-field text-xs" value={actor} onChange={e => setActor(e.target.value)} />
                </div>
              </div>

              {mut.error && (
                <div className="text-xs text-red-400 flex items-center gap-1">
                  <XCircle size={12} /> {(mut.error as any).message}
                </div>
              )}

              {mut.isSuccess && (
                <div className="text-xs text-green-400 flex items-center gap-1">
                  <CheckCircle2 size={12} /> Decision recorded
                </div>
              )}

              <div className="flex gap-2">
                <button
                  className="btn-primary flex-1 justify-center py-2 text-xs bg-green-600 hover:bg-green-500 shadow-green-900/50"
                  disabled={!reason || mut.isPending}
                  onClick={() => mut.mutate('APPROVED')}
                >
                  {mut.isPending ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                  Approve
                </button>
                <button
                  className="btn-danger flex-1 justify-center py-2 text-xs"
                  disabled={!reason || mut.isPending}
                  onClick={() => mut.mutate('REJECTED')}
                >
                  <XCircle size={12} /> Reject
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ReviewPanel({ caseId }: { caseId: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ['review', caseId],
    queryFn: () => api.get<{ pending_count: number; items: ReviewItem[] }>(`/cases/${caseId}/review`),
    enabled: !!caseId,
    refetchInterval: 5_000,
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
      <ClipboardCheck size={40} className="opacity-20" />
      <p className="text-sm">Select a case first</p>
    </div>
  );

  const items = data?.items ?? [];

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-white">Officer Review Queue</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${items.length > 0 ? 'bg-amber-400 animate-pulse' : 'bg-green-400'}`} />
          <span className={`text-sm font-bold ${items.length > 0 ? 'text-amber-400' : 'text-green-400'}`}>
            {items.length} pending
          </span>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-12 text-gray-600">
          <Loader2 size={16} className="animate-spin" /> Loading queue…
        </div>
      )}

      {items.length === 0 && !isLoading && (
        <div className="text-center py-16 text-gray-600">
          <CheckCircle2 size={40} className="mx-auto mb-3 text-green-600 opacity-40" />
          <div className="text-sm font-medium text-green-500">Review queue is empty</div>
          <div className="text-xs text-gray-600 mt-1">All proposals have been processed</div>
        </div>
      )}

      <AnimatePresence>
        {items.map(item => (
          <ReviewCard key={item.item_id} item={item} caseId={caseId} />
        ))}
      </AnimatePresence>
    </div>
  );
}
