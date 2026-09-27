import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  LayoutDashboard, Database, Zap, Map, ClipboardCheck,
  Shield, GitBranch, BarChart3, Search, Settings,
  ChevronLeft, ArrowLeft, Loader2, AlertTriangle,
  CheckCircle2, XCircle, Clock, Activity,
} from 'lucide-react';
import { api, Case, Parcel, ReviewItem, QualityReport, HarmonizeResult } from '../api/client';
import CasesPanel from '../components/app/CasesPanel';
import IngestPanel from '../components/app/IngestPanel';
import HarmonizePanel from '../components/app/HarmonizePanel';
import MapPanel from '../components/app/MapPanel';
import ReviewPanel from '../components/app/ReviewPanel';
import EvidencePanel from '../components/app/EvidencePanel';
import ProvenancePanel from '../components/app/ProvenancePanel';
import QualityPanel from '../components/app/QualityPanel';

type Tab = 'cases' | 'ingest' | 'harmonize' | 'map' | 'review' | 'evidence' | 'provenance' | 'quality';

const NAV_ITEMS: Array<{ id: Tab; icon: React.ReactNode; label: string; badge?: string }> = [
  { id: 'cases',      icon: <LayoutDashboard size={16} />, label: 'Cases' },
  { id: 'ingest',     icon: <Database size={16} />,        label: 'Ingest Data' },
  { id: 'harmonize',  icon: <Zap size={16} />,             label: 'Harmonize' },
  { id: 'map',        icon: <Map size={16} />,             label: 'Map & Conflicts' },
  { id: 'review',     icon: <ClipboardCheck size={16} />,  label: 'Review Queue' },
  { id: 'evidence',   icon: <Shield size={16} />,          label: 'Evidence' },
  { id: 'provenance', icon: <GitBranch size={16} />,       label: 'Provenance' },
  { id: 'quality',    icon: <BarChart3 size={16} />,       label: 'Data Quality' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('cases');
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; version: string; subsystems: Record<string, string> }>('/health'),
    refetchInterval: 15_000,
  });

  const { data: reviewData } = useQuery({
    queryKey: ['review', activeCaseId],
    queryFn: () => api.get<{ pending_count: number }>(`/cases/${activeCaseId}/review`),
    enabled: !!activeCaseId,
    refetchInterval: 8_000,
  });

  const reviewCount = reviewData?.pending_count ?? 0;
  const isOnline = health?.status === 'OPERATIONAL';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex h-screen bg-dark-700 relative z-10"
    >
      {/* Sidebar */}
      <motion.aside
        animate={{ width: sidebarOpen ? 220 : 60 }}
        transition={{ duration: 0.2 }}
        className="flex-shrink-0 bg-dark-600 border-r border-dark-200/50 flex flex-col overflow-hidden"
      >
        {/* Logo */}
        <div className="h-14 flex items-center px-4 border-b border-dark-200/30 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">G</div>
          <AnimatePresence>
            {sidebarOpen && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="ml-3 overflow-hidden"
              >
                <div className="text-sm font-bold text-white whitespace-nowrap">GeoSamanvay</div>
                <div className="text-[10px] text-gray-600 whitespace-nowrap">SIH26013</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Active case chip */}
        <AnimatePresence>
          {sidebarOpen && activeCaseId && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="px-3 py-2 border-b border-dark-200/30"
            >
              <div className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Active Case</div>
              <div className="text-xs font-mono text-cyan-400 truncate">{activeCaseId}</div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto py-2 scrollbar-thin">
          {NAV_ITEMS.map(item => {
            const isActive = activeTab === item.id;
            const count = item.id === 'review' ? reviewCount : 0;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150 relative
                  ${isActive ? 'text-white bg-brand-600/20' : 'text-gray-500 hover:text-gray-200 hover:bg-dark-500/50'}`}
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-indicator"
                    className="absolute left-0 top-0 bottom-0 w-0.5 bg-brand-500 rounded-r"
                  />
                )}
                <span className={isActive ? 'text-brand-400' : ''}>{item.icon}</span>
                <AnimatePresence>
                  {sidebarOpen && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="whitespace-nowrap font-medium"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {count > 0 && sidebarOpen && (
                  <span className="ml-auto bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                    {count}
                  </span>
                )}
                {count > 0 && !sidebarOpen && (
                  <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom status */}
        <div className="p-3 border-t border-dark-200/30 flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(v => !v)}
            className="w-full flex items-center justify-center p-1.5 rounded text-gray-600 hover:text-gray-400 transition-colors"
          >
            <ChevronLeft size={14} className={`transition-transform ${sidebarOpen ? '' : 'rotate-180'}`} />
          </button>
          {sidebarOpen && (
            <div className="mt-2 flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isOnline ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
              <span className="text-[10px] text-gray-600 truncate">{isOnline ? 'System Online' : 'Offline'}</span>
            </div>
          )}
        </div>
      </motion.aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <div className="h-14 flex items-center justify-between px-5 bg-dark-600/50 border-b border-dark-200/30 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/')} className="text-gray-600 hover:text-white transition-colors">
              <ArrowLeft size={16} />
            </button>
            <div className="text-sm font-semibold text-white">
              {NAV_ITEMS.find(n => n.id === activeTab)?.label}
            </div>
            {activeCaseId && (
              <>
                <span className="text-gray-700">·</span>
                <span className="text-xs font-mono text-cyan-400">{activeCaseId}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Activity size={12} />
            v{health?.version ?? '—'}
          </div>
        </div>

        {/* Panel content */}
        <div className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15 }}
              className="h-full overflow-y-auto p-5 scrollbar-thin"
            >
              {activeTab === 'cases'      && <CasesPanel activeCaseId={activeCaseId} onSelectCase={id => { setActiveCaseId(id); setActiveTab('map'); }} />}
              {activeTab === 'ingest'     && <IngestPanel caseId={activeCaseId} />}
              {activeTab === 'harmonize'  && <HarmonizePanel caseId={activeCaseId} />}
              {activeTab === 'map'        && <MapPanel caseId={activeCaseId} />}
              {activeTab === 'review'     && <ReviewPanel caseId={activeCaseId} />}
              {activeTab === 'evidence'   && <EvidencePanel />}
              {activeTab === 'provenance' && <ProvenancePanel caseId={activeCaseId} />}
              {activeTab === 'quality'    && <QualityPanel caseId={activeCaseId} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
