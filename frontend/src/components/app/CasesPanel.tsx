import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { activeCaseId: string | null; onSelectCase: (id: string) => void; isDark: boolean; }

export default function CasesPanel({ activeCaseId, onSelectCase, isDark }: Props) {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [title, setTitle] = useState('');
  const [caseId, setCaseId] = useState('');
  const [demoMsg, setDemoMsg] = useState('');
  const [demoLoading, setDemoLoading] = useState(false);

  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';

  const { data, isLoading, error } = useQuery({
    queryKey: ['cases'],
    queryFn: () => api.get<{ cases: any[] }>('/cases'),
    refetchInterval: 5_000,
  });

  const createMut = useMutation({
    mutationFn: (body: { case_id?: string; title: string }) => api.post<any>('/cases', body),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ['cases'] });
      onSelectCase(c.case_id);
      setShowNew(false);
      setTitle(''); setCaseId('');
    },
  });

  async function loadDemo() {
    setDemoLoading(true); setDemoMsg('');
    try {
      const r = await api.post<any>('/demo/load-ward42?force_reload=false', {});
      qc.invalidateQueries({ queryKey: ['cases'] });
      onSelectCase('WARD42-DEMO');
      setDemoMsg(r.status === 'already_loaded'
        ? '✓ Ward 42 already loaded — switched to it'
        : `✓ Loaded: ${r.parcels_matched} parcels matched, ${r.review_required} for review`);
    } catch (e: any) { setDemoMsg(`✗ ${e.message}`); }
    finally { setDemoLoading(false); }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Demo loader — 3 cities */}
      <div style={{ borderRadius: 16, padding: 16, background: bg, border: '1px solid rgba(59,130,246,0.35)' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: text, marginBottom: 6 }}>⚡ Pre-built Demo Cases</div>
        <div style={{ fontSize: 12, color: muted, marginBottom: 14, lineHeight: 1.5 }}>
          Load real conflicting land datasets from Indian cities. Each case has 4 source datasets and a known boundary conflict.
        </div>
        {demoMsg && (
          <div style={{ marginBottom: 10, fontSize: 12, fontWeight: 600, color: demoMsg.startsWith('✓') ? '#22c55e' : '#ef4444' }}>{demoMsg}</div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
          {[
            { label: '📍 Ward 42, Pune', sub: '10 parcels · 1.42m offset', endpoint: '/demo/load-ward42' },
            { label: '📍 Sector 7, Nagpur', sub: '6 parcels · 1.1m conflict', endpoint: '/demo/load-nagpur' },
            { label: '📍 Layout 3, Bengaluru', sub: '5 parcels · 2.1m encroach', endpoint: '/demo/load-bengaluru' },
          ].map(({ label, sub, endpoint }) => (
            <button key={endpoint} disabled={demoLoading}
              onClick={async () => {
                setDemoLoading(true); setDemoMsg('');
                try {
                  const r = await api.post<any>(`${endpoint}?force_reload=false`, {});
                  qc.invalidateQueries({ queryKey: ['cases'] });
                  const cid = r.case_id ?? r.status;
                  if (r.case_id) onSelectCase(r.case_id);
                  setDemoMsg(r.status === 'already_loaded'
                    ? `✓ ${label.split(',')[1]?.trim() ?? 'Case'} already loaded`
                    : `✓ ${r.parcels_matched} parcels · ${r.review_required} for review`);
                } catch (e: any) { setDemoMsg(`✗ ${e.message}`); }
                finally { setDemoLoading(false); }
              }}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                padding: '10px 12px', borderRadius: 10, cursor: demoLoading ? 'not-allowed' : 'pointer',
                background: isDark ? 'rgba(59,130,246,0.08)' : 'rgba(59,130,246,0.05)',
                border: '1px solid rgba(59,130,246,0.2)', opacity: demoLoading ? 0.6 : 1,
                textAlign: 'left',
              }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: text, marginBottom: 3 }}>{demoLoading ? '⏳ Loading…' : label}</div>
              <div style={{ fontSize: 10, color: muted }}>{sub}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold" style={{ color: text }}>Harmonization Cases ({data?.cases?.length ?? 0})</h2>
        <button onClick={() => setShowNew(v => !v)}
          className="text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
          style={{ background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)', color: muted }}>
          {showNew ? '✕ Cancel' : '+ New Case'}
        </button>
      </div>

      {/* New case form */}
      <AnimatePresence>
        {showNew && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
            className="rounded-2xl p-5 space-y-3 overflow-hidden" style={{ background: bg, border: `1px solid ${border}` }}>
            <div className="text-sm font-semibold" style={{ color: text }}>Create New Case</div>
            <input
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none focus:ring-2 focus:ring-blue-500/30"
              style={{ background: isDark ? '#060d18' : '#f8fafc', borderColor: border, color: text }}
              placeholder="Title *" value={title} onChange={e => setTitle(e.target.value)}
            />
            <input
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none focus:ring-2 focus:ring-blue-500/30 font-mono"
              style={{ background: isDark ? '#060d18' : '#f8fafc', borderColor: border, color: text }}
              placeholder="Case ID (auto-generated if blank)" value={caseId} onChange={e => setCaseId(e.target.value)}
            />
            {createMut.error && <p className="text-xs text-red-400">{(createMut.error as any).message}</p>}
            <button
              disabled={!title.trim() || createMut.isPending}
              onClick={() => createMut.mutate({ title, case_id: caseId.trim() || undefined })}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm px-5 py-2.5 rounded-lg transition-all">
              {createMut.isPending ? '⏳ Creating…' : '+ Create Case'}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error state */}
      {error && (
        <div className="text-center py-8 text-red-400 text-sm">
          ✗ Failed to load cases — is the backend running?
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-12" style={{ color: muted }}>Loading cases…</div>
      )}

      {/* Cases list */}
      <div className="space-y-2">
        {data?.cases?.map((c, i) => (
          <motion.button key={c.case_id} initial={{ opacity: 0, x: -15 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
            onClick={() => onSelectCase(c.case_id)}
            className="w-full text-left rounded-xl p-4 transition-all"
            style={{
              background: activeCaseId === c.case_id ? (isDark ? 'rgba(59,130,246,0.1)' : 'rgba(59,130,246,0.06)') : bg,
              border: `1px solid ${activeCaseId === c.case_id ? '#3b82f650' : border}`,
            }}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-cyan-400 truncate flex-1">{c.case_id}</span>
              <span className="text-[9px] font-bold px-2 py-0.5 rounded text-green-400 bg-green-500/12 border border-green-500/25">{c.status}</span>
            </div>
            <div className="text-sm font-medium truncate mb-1.5" style={{ color: text }}>{c.title}</div>
            {c.stats && (
              <div className="flex items-center gap-4 text-[11px]" style={{ color: muted }}>
                <span>📦 {c.stats.datasets} datasets</span>
                <span>🗺️ {c.stats.canonical_parcels} parcels</span>
                {c.stats.conflicts > 0 && <span className="text-amber-500">⚠ {c.stats.conflicts} conflicts</span>}
                {c.stats.proposals > 0 && <span>📋 {c.stats.proposals} proposals</span>}
              </div>
            )}
          </motion.button>
        ))}

        {!isLoading && !error && !data?.cases?.length && (
          <div className="text-center py-16" style={{ color: muted }}>
            <div className="text-4xl mb-3">📁</div>
            <div className="text-sm font-medium mb-1">No cases yet</div>
            <div className="text-xs">Load the Ward 42 demo or create a new case to get started</div>
          </div>
        )}
      </div>
    </div>
  );
}
