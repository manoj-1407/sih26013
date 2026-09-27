import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Zap, Loader2, ChevronRight, Database, GitBranch, AlertTriangle } from 'lucide-react';
import { api, Case } from '../../api/client';

export default function CasesPanel({ activeCaseId, onSelectCase }: {
  activeCaseId: string | null;
  onSelectCase: (id: string) => void;
}) {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [title, setTitle] = useState('');
  const [caseId, setCaseId] = useState('');
  const [demoMsg, setDemoMsg] = useState('');
  const [demoLoading, setDemoLoading] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['cases'],
    queryFn: () => api.get<{ cases: Case[] }>('/cases'),
    refetchInterval: 5_000,
  });

  const createMut = useMutation({
    mutationFn: (body: { case_id?: string; title: string }) => api.post<Case>('/cases', body),
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
        ? '✓ Ward 42 demo already loaded — switching to it'
        : `✓ Loaded ${r.parcels_matched} parcels · ${r.review_required} for review`);
    } catch (e: any) {
      setDemoMsg(`Error: ${e.message}`);
    } finally {
      setDemoLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Demo loader */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass rounded-2xl p-5 border-brand-500/20 relative overflow-hidden"
      >
        <div className="absolute inset-0 opacity-5" style={{ background: 'radial-gradient(600px at 0% 0%, #3b82f6, transparent)' }} />
        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex-1">
            <div className="text-sm font-bold text-white flex items-center gap-2 mb-1">
              <Zap size={14} className="text-brand-400" />
              Ward 42 Demo — One Click
            </div>
            <div className="text-xs text-gray-500">
              Loads 4 source datasets with known boundary conflicts on Parcel P-1042.
              Full pipeline: match → conflict → propose → ripple check.
            </div>
            {demoMsg && (
              <div className={`mt-2 text-xs font-medium ${demoMsg.startsWith('✓') ? 'text-green-400' : 'text-red-400'}`}>
                {demoMsg}
              </div>
            )}
          </div>
          <button onClick={loadDemo} disabled={demoLoading} className="btn-primary flex-shrink-0">
            {demoLoading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            {demoLoading ? 'Loading…' : 'Load Ward 42'}
          </button>
        </div>
      </motion.div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold text-white">Harmonization Cases</h2>
        <button onClick={() => setShowNew(v => !v)} className="btn-ghost text-xs">
          <Plus size={13} />{showNew ? 'Cancel' : 'New Case'}
        </button>
      </div>

      {/* New case form */}
      <AnimPresence>
        {showNew && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass rounded-2xl p-5 space-y-3"
          >
            <div className="text-sm font-semibold text-white">Create New Case</div>
            <input className="input-field" placeholder="Title *" value={title} onChange={e => setTitle(e.target.value)} />
            <input className="input-field font-mono" placeholder="Case ID (auto-generated if blank)" value={caseId} onChange={e => setCaseId(e.target.value)} />
            {createMut.error && <p className="text-xs text-red-400">{(createMut.error as any).message}</p>}
            <button
              className="btn-primary"
              disabled={!title || createMut.isPending}
              onClick={() => createMut.mutate({ title, case_id: caseId || undefined })}
            >
              {createMut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
              Create Case
            </button>
          </motion.div>
        )}
      </AnimPresence>

      {/* Cases list */}
      {isLoading && (
        <div className="flex items-center gap-2 text-gray-600 text-sm py-8 justify-center">
          <Loader2 size={16} className="animate-spin" /> Loading cases…
        </div>
      )}
      <div className="space-y-2">
        {data?.cases?.map((c, i) => (
          <motion.div
            key={c.case_id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            onClick={() => onSelectCase(c.case_id)}
            className={`glass rounded-xl p-4 cursor-pointer transition-all duration-150 group
              ${activeCaseId === c.case_id ? 'border-brand-500/40 bg-brand-500/5' : 'glass-hover'}`}
          >
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-mono text-cyan-400 truncate">{c.case_id}</span>
                  <span className={c.status === 'ACTIVE' ? 'badge-ok' : 'badge-info'}>{c.status}</span>
                </div>
                <div className="text-sm text-white font-medium truncate">{c.title}</div>
                {c.stats && (
                  <div className="flex items-center gap-4 mt-2 text-[11px] text-gray-600">
                    <span className="flex items-center gap-1"><Database size={10} />{c.stats.datasets} datasets</span>
                    <span className="flex items-center gap-1"><GitBranch size={10} />{c.stats.canonical_parcels} parcels</span>
                    {c.stats.conflicts > 0 && (
                      <span className="flex items-center gap-1 text-amber-600">
                        <AlertTriangle size={10} />{c.stats.conflicts} conflicts
                      </span>
                    )}
                  </div>
                )}
              </div>
              <ChevronRight size={16} className="text-gray-700 group-hover:text-gray-400 transition-colors flex-shrink-0" />
            </div>
          </motion.div>
        ))}
        {!isLoading && !data?.cases?.length && (
          <div className="text-center py-12 text-gray-600">
            <Database size={32} className="mx-auto mb-3 opacity-30" />
            <div className="text-sm">No cases yet. Load the demo or create one.</div>
          </div>
        )}
      </div>
    </div>
  );
}

// Mini AnimatePresence alias to avoid import clutter
function AnimPresence({ children }: { children: React.ReactNode }) {
  const { AnimatePresence } = require('framer-motion');
  return <AnimatePresence>{children}</AnimatePresence>;
}
