import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }

function Bar({ label, val, isDark }: { label: string; val: number; isDark: boolean }) {
  const pct = Math.min(100, Math.round(val * 100));
  const color = pct >= 85 ? '#22c55e' : pct >= 65 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
      <span style={{ fontSize: 10, color: isDark ? '#6b7280' : '#94a3b8', width: 96, flexShrink: 0, textTransform: 'capitalize' }}>
        {label.replace(/_/g, ' ')}
      </span>
      <div style={{ flex: 1, height: 5, borderRadius: 999, background: isDark ? '#0c1118' : '#e8edf5', overflow: 'hidden' }}>
        <motion.div initial={{ width: 0 }} animate={{ width: pct + '%' }} transition={{ duration: 0.7 }}
          style={{ height: '100%', borderRadius: 999, background: color }} />
      </div>
      <span style={{ fontSize: 10, fontFamily: 'monospace', color, width: 28, textAlign: 'right', fontWeight: 700 }}>{pct}%</span>
    </div>
  );
}

// ── EXTRACTED to avoid hooks-in-map violation (React error #310) ─────────────
function ParcelCard({ p, isDark, bg, border, text, muted }: {
  p: any; isDark: boolean; bg: string; border: string; text: string; muted: string;
}) {
  const [open, setOpen] = useState(false);

  const dec = p.proposal?.decision ?? 'PENDING';
  const decColor = dec === 'AUTO_APPROVED' ? '#22c55e' : dec === 'REVIEW_REQUIRED' ? '#f59e0b' : dec === 'BLOCKED' ? '#ef4444' : '#6b7280';
  const ev = p.proposal as any;

  return (
    <div style={{ borderRadius: 12, overflow: 'hidden', background: bg, border: '1px solid ' + border }}>
      <button onClick={() => setOpen(v => !v)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}>
        <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#22d3ee', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.parcel_id}</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: decColor, flexShrink: 0 }}>{dec.replace('_', ' ')}</span>
        <span style={{ fontSize: 11, color: muted, flexShrink: 0 }}>{Math.round(p.match_confidence * 100)}%</span>
        <span style={{ fontSize: 11, color: muted, flexShrink: 0 }}>{p.source_count}src</span>
        {p.conflicts?.critical > 0 && <span style={{ fontSize: 9, color: '#ef4444', fontWeight: 700, flexShrink: 0 }}>{p.conflicts.critical}crit</span>}
        <span style={{ color: muted, fontSize: 12, flexShrink: 0 }}>{open ? '▲' : '▼'}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            style={{ overflow: 'hidden', borderTop: '1px solid ' + border }}>
            <div style={{ padding: 14 }}>
              {/* Confidence */}
              {ev?.confidence_components && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: muted, marginBottom: 8 }}>Evidence</div>
                  {Object.entries(ev.confidence_components).map(([k, v]) =>
                    typeof v === 'number' && v > 0 && v <= 1
                      ? <Bar key={k} label={k} val={v as number} isDark={isDark} />
                      : null
                  )}
                </div>
              )}
              {/* Decision */}
              <div style={{ borderRadius: 8, padding: 10, fontSize: 12, marginBottom: 10, background: decColor + '14', border: '1px solid ' + decColor + '30', color: decColor }}>
                <div style={{ fontWeight: 700, marginBottom: 3 }}>{dec.replace('_', ' ')}</div>
                <div style={{ opacity: 0.85, fontSize: 11 }}>{p.proposal?.decision_reason}</div>
              </div>
              {/* Ripple */}
              {p.ripple && (
                <div style={{ borderRadius: 8, padding: 10, fontSize: 11, marginBottom: 10, background: p.ripple.safe_to_auto_approve ? '#22c55e14' : '#f59e0b14', color: p.ripple.safe_to_auto_approve ? '#22c55e' : '#f59e0b', border: '1px solid ' + (p.ripple.safe_to_auto_approve ? '#22c55e30' : '#f59e0b30') }}>
                  🌊 {p.ripple.summary}
                </div>
              )}
              {/* Changes */}
              {p.proposal?.change_summary?.map((s: string, si: number) => (
                <div key={si} style={{ fontSize: 11, display: 'flex', gap: 6, color: muted, marginBottom: 4 }}>
                  <span style={{ opacity: 0.4 }}>›</span>{s}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function HarmonizePanel({ caseId, isDark }: Props) {
  const qc = useQueryClient();
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';

  const mut = useMutation({
    mutationFn: () => api.post<any>(`/cases/${caseId}/harmonize`, {}),
    onSuccess: (r) => {
      setResult(r);
      setError('');
      qc.invalidateQueries({ queryKey: ['parcels', caseId] });
      qc.invalidateQueries({ queryKey: ['review-count', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
    onError: (e: any) => setError(e.message),
  });

  if (!caseId) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 256, color: muted }}>
      <div style={{ fontSize: 48, marginBottom: 12 }}>⚡</div>
      <div style={{ fontSize: 14 }}>Select a case first</div>
    </div>
  );

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      {/* Run button */}
      <div style={{ borderRadius: 16, padding: 24, marginBottom: 16, background: bg, border: '1px solid ' + border }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: text, marginBottom: 8 }}>Run Harmonization Pipeline</h2>
        <p style={{ fontSize: 13, color: muted, marginBottom: 20, lineHeight: 1.6 }}>
          Match → Conflict Detect → Evidence-Weighted Proposal → Ripple Check → Review Queue
        </p>
        <button disabled={mut.isPending} onClick={() => mut.mutate()}
          style={{ display: 'flex', alignItems: 'center', gap: 8, background: mut.isPending ? '#1d4ed8' : '#2563eb', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: 10, fontWeight: 600, fontSize: 14, cursor: mut.isPending ? 'not-allowed' : 'pointer', opacity: mut.isPending ? 0.7 : 1 }}>
          {mut.isPending ? '⏳ Running…' : '⚡ Run Harmonization'}
        </button>
        {error && <div style={{ marginTop: 10, fontSize: 12, color: '#ef4444' }}>✗ {error}</div>}
      </div>

      {/* Results */}
      {result && (
        <div>
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 16 }}>
            {[
              { l: 'Records', v: result.total_records, c: '#3b82f6' },
              { l: 'Parcels', v: result.matched_groups, c: '#06b6d4' },
              { l: 'For Review', v: result.review_queue_count, c: '#f59e0b' },
              { l: 'Auto-Approved', v: result.parcels?.filter((p: any) => p.proposal?.decision === 'AUTO_APPROVED').length ?? 0, c: '#22c55e' },
            ].map(({ l, v, c }) => (
              <div key={l} style={{ borderRadius: 12, padding: 16, textAlign: 'center', background: bg, border: '1px solid ' + border }}>
                <div style={{ fontSize: 28, fontWeight: 900, marginBottom: 4, color: c }}>{v}</div>
                <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: muted }}>{l}</div>
              </div>
            ))}
          </div>

          {/* Parcel cards — each is its own component so useState is valid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {result.parcels?.map((p: any) => (
              <ParcelCard key={p.parcel_id} p={p} isDark={isDark} bg={bg} border={border} text={text} muted={muted} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
