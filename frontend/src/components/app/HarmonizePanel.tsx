import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Zap, ChevronDown, ChevronUp, CheckCircle2, AlertTriangle, XCircle, Loader2, ArrowRight } from 'lucide-react';
import { api, HarmonizeResult } from '../../api/client';

function ConfidenceBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span className="text-[11px] text-gray-500 w-24 truncate">{label}</span>
      <div className="flex-1 bg-dark-600 rounded-full h-1.5 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(value * 100)}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      <span className="text-[11px] font-mono font-bold w-8 text-right" style={{ color }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

function ParcelCard({ p }: { p: HarmonizeResult['parcels'][0] }) {
  const [open, setOpen] = useState(false);
  const dec = p.proposal.decision;
  const decColor = dec === 'AUTO_APPROVED' ? '#22c55e' : dec === 'REVIEW_REQUIRED' ? '#f59e0b' : dec === 'BLOCKED' ? '#ef4444' : '#6b7280';
  const conf = p.proposal as any;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl overflow-hidden"
    >
      <button
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-dark-300/30 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <span className="text-xs font-mono text-cyan-400 flex-1 truncate">{p.parcel_id}</span>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] font-bold" style={{ color: decColor }}>{dec?.replace('_', ' ')}</span>
          <span className="text-xs text-gray-600">{Math.round(p.match_confidence * 100)}%</span>
          <span className="text-xs text-gray-600">{p.source_count} src</span>
          {p.conflicts.critical > 0 && <span className="badge-err">{p.conflicts.critical} critical</span>}
          {open ? <ChevronUp size={13} className="text-gray-600" /> : <ChevronDown size={13} className="text-gray-600" />}
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
            <div className="p-4 space-y-4">
              {/* Confidence */}
              <div>
                <div className="section-title">Match Evidence</div>
                {conf?.confidence_components && Object.entries(conf.confidence_components).map(([k, v]) =>
                  typeof v === 'number' && v > 0 && v <= 1
                    ? <ConfidenceBar key={k} label={k} value={v as number} color={v > 0.8 ? '#22c55e' : v > 0.6 ? '#f59e0b' : '#ef4444'} />
                    : null
                )}
              </div>
              {/* Conflicts */}
              <div>
                <div className="section-title">Conflicts</div>
                <div className="grid grid-cols-4 gap-2">
                  {[['CRITICAL', p.conflicts.critical, '#ef4444'], ['HIGH', p.conflicts.high, '#f59e0b'], ['MEDIUM', p.conflicts.medium, '#8b5cf6'], ['LOW', p.conflicts.low, '#6b7280']].map(([label, count, color]) => (
                    <div key={label as string} className="bg-dark-600 rounded-lg p-2 text-center">
                      <div className="text-lg font-black" style={{ color: color as string }}>{count as number}</div>
                      <div className="text-[9px] text-gray-600 uppercase">{label as string}</div>
                    </div>
                  ))}
                </div>
              </div>
              {/* Proposal */}
              <div className={`rounded-lg p-3 text-xs ${dec === 'AUTO_APPROVED' ? 'bg-green-500/10 text-green-400' : dec === 'REVIEW_REQUIRED' ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'}`}>
                <div className="font-bold mb-1">{dec?.replace('_', ' ')}</div>
                <div className="text-current opacity-80">{p.proposal.decision_reason}</div>
              </div>
              {/* Ripple */}
              <div className={`rounded-lg p-3 text-xs ${p.ripple.safe_to_auto_approve ? 'bg-green-500/10 text-green-400' : 'bg-amber-500/10 text-amber-400'}`}>
                <span className="font-bold">Ripple: </span>{p.ripple.summary}
              </div>
              {/* Changes */}
              {p.proposal.change_summary?.length > 0 && (
                <div className="space-y-1">
                  {p.proposal.change_summary.map((s, i) => (
                    <div key={i} className="text-xs text-gray-500 flex items-start gap-1.5">
                      <ArrowRight size={10} className="mt-0.5 flex-shrink-0 text-gray-700" />{s}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function HarmonizePanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [result, setResult] = useState<HarmonizeResult | null>(null);

  const mut = useMutation({
    mutationFn: () => api.post<HarmonizeResult>(`/cases/${caseId}/harmonize`, {}),
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: ['parcels', caseId] });
      qc.invalidateQueries({ queryKey: ['review', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
      <Zap size={40} className="opacity-20" />
      <p className="text-sm">Select a case first</p>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="glass rounded-2xl p-6">
        <h2 className="text-base font-bold text-white mb-2">Run Harmonization Pipeline</h2>
        <p className="text-sm text-gray-500 mb-5">
          Match → Conflict Detect → Evidence-Weighted Proposal → Ripple Check → Queue
        </p>
        <button className="btn-primary" disabled={mut.isPending} onClick={() => mut.mutate()}>
          {mut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
          {mut.isPending ? 'Running pipeline…' : 'Run Harmonization'}
        </button>
        {mut.error && (
          <div className="mt-3 text-xs text-red-400 flex items-center gap-2">
            <XCircle size={13} /> {(mut.error as any).message}
          </div>
        )}
      </div>

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Records', value: result.total_records, color: 'text-brand-400' },
              { label: 'Parcels', value: result.matched_groups, color: 'text-cyan-400' },
              { label: 'For Review', value: result.review_queue_count, color: 'text-amber-400' },
              { label: 'Auto-Approved', value: result.parcels.filter(p => p.proposal.decision === 'AUTO_APPROVED').length, color: 'text-green-400' },
            ].map(({ label, value, color }) => (
              <div key={label} className="glass rounded-xl p-4 text-center">
                <div className={`text-3xl font-black mb-1 ${color}`}>{value}</div>
                <div className="text-[10px] text-gray-600 uppercase tracking-wider">{label}</div>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {result.parcels.map(p => <ParcelCard key={p.parcel_id} p={p} />)}
          </div>
        </>
      )}
    </div>
  );
}
