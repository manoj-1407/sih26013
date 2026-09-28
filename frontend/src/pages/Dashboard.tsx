import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useNavigate, Routes, Route } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from '../context/ThemeContext';
import { api } from '../api/client';
import CasesPanel from '../components/app/CasesPanel';
import IngestPanel from '../components/app/IngestPanel';
import HarmonizePanel from '../components/app/HarmonizePanel';
import MapPanel from '../components/app/MapPanel';
import ReviewPanel from '../components/app/ReviewPanel';
import EvidencePanel from '../components/app/EvidencePanel';
import ProvenancePanel from '../components/app/ProvenancePanel';
import QualityPanel from '../components/app/QualityPanel';

type Tab = 'cases' | 'ingest' | 'harmonize' | 'map' | 'review' | 'evidence' | 'provenance' | 'quality';

const TABS: Array<{ id: Tab; emoji: string; label: string }> = [
  { id: 'cases',      emoji: '📁', label: 'Cases' },
  { id: 'ingest',     emoji: '📥', label: 'Ingest' },
  { id: 'harmonize',  emoji: '⚡', label: 'Harmonize' },
  { id: 'map',        emoji: '🗺️', label: 'Map' },
  { id: 'review',     emoji: '✅', label: 'Review' },
  { id: 'evidence',   emoji: '🔐', label: 'Evidence' },
  { id: 'provenance', emoji: '🌐', label: 'Provenance' },
  { id: 'quality',    emoji: '📊', label: 'Quality' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const [tab, setTab] = useState<Tab>('cases');
  const [caseId, setCaseId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; version: string; subsystems: Record<string, string> }>('/health'),
    refetchInterval: 20_000,
    retry: false,
  });

  const { data: reviewData } = useQuery({
    queryKey: ['review-count', caseId],
    queryFn: () => api.get<{ pending_count: number }>(`/cases/${caseId}/review`),
    enabled: !!caseId,
    refetchInterval: 8_000,
  });

  const reviewCount = reviewData?.pending_count ?? 0;
  const isOnline = health?.status === 'OPERATIONAL';

  // Theme-aware colors
  const bg     = isDark ? '#0c1118' : '#f0f4f8';
  const sidebar = isDark ? '#0a0f1a'   : '#ffffff';
  const border  = isDark ? '#1e2d42'   : '#e2e8f0';
  const text    = isDark ? '#e8edf5'   : '#1a202c';
  const muted   = isDark ? '#6b7280'   : '#94a3b8';
  const surface = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: bg, color: text }}>
      {/* Sidebar */}
      <aside
        className="flex flex-col flex-shrink-0 transition-all duration-200"
        style={{
          width: collapsed ? 56 : 200,
          background: sidebar,
          borderRight: `1px solid ${border}`,
        }}
      >
        {/* Logo */}
        <div className="h-14 flex items-center px-3 flex-shrink-0" style={{ borderBottom: `1px solid ${border}` }}>
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">G</div>
          {!collapsed && (
            <div className="ml-2.5 overflow-hidden">
              <div className="text-sm font-bold whitespace-nowrap" style={{ color: text }}>GeoSamanvay</div>
              <div className="text-[10px] whitespace-nowrap" style={{ color: muted }}>SIH26013</div>
            </div>
          )}
        </div>

        {/* Active case */}
        {!collapsed && caseId && (
          <div className="px-3 py-2 flex-shrink-0" style={{ borderBottom: `1px solid ${border}` }}>
            <div className="text-[9px] font-bold uppercase tracking-widest mb-1" style={{ color: muted }}>Active Case</div>
            <div className="text-[11px] font-mono text-cyan-400 truncate">{caseId}</div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-1.5">
          {TABS.map(t => {
            const isActive = tab === t.id;
            const cnt = t.id === 'review' ? reviewCount : 0;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm transition-all relative text-left"
                style={{
                  background: isActive ? (isDark ? 'rgba(59,130,246,0.12)' : 'rgba(59,130,246,0.08)') : 'transparent',
                  color: isActive ? '#60a5fa' : muted,
                }}
              >
                {isActive && (
                  <motion.div layoutId="sidebar-indicator"
                    className="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-500 rounded-r"
                  />
                )}
                <span className="flex-shrink-0 text-base">{t.emoji}</span>
                {!collapsed && (
                  <span className="font-medium whitespace-nowrap text-xs">{t.label}</span>
                )}
                {cnt > 0 && !collapsed && (
                  <span className="ml-auto text-[10px] font-bold text-white bg-red-500 px-1.5 py-0.5 rounded-full">{cnt}</span>
                )}
                {cnt > 0 && collapsed && (
                  <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="p-2 flex-shrink-0" style={{ borderTop: `1px solid ${border}` }}>
          <button onClick={toggleTheme}
            className="w-full flex items-center justify-center py-1.5 rounded-lg text-sm transition-colors"
            style={{ color: muted }}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
            {isDark ? '☀️' : '🌙'}
          </button>
          <button onClick={() => setCollapsed(v => !v)}
            className="w-full flex items-center justify-center py-1 text-xs transition-colors mt-1"
            style={{ color: muted }}>
            {collapsed ? '▶' : '◀'}
          </button>
          {!collapsed && (
            <div className="flex items-center gap-1.5 mt-2 px-1">
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isOnline ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
              <span className="text-[10px] truncate" style={{ color: muted }}>
                {isOnline ? `v${health?.version}` : 'Offline'}
              </span>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <div className="h-14 flex items-center justify-between px-5 flex-shrink-0"
          style={{ background: isDark ? 'rgba(10,15,26,0.8)' : 'rgba(255,255,255,0.95)', borderBottom: `1px solid ${border}` }}>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/')} className="opacity-50 hover:opacity-80 transition-opacity text-sm">
              ← Home
            </button>
            <span style={{ color: border }}>|</span>
            <span className="text-sm font-semibold" style={{ color: text }}>
              {TABS.find(t => t.id === tab)?.emoji} {TABS.find(t => t.id === tab)?.label}
            </span>
            {caseId && (
              <>
                <span style={{ color: muted }}>·</span>
                <span className="text-xs font-mono text-cyan-400">{caseId}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs" style={{ color: muted }}>
              {isOnline ? '● Online' : '● Offline'}
            </span>
            <a href="/docs" target="_blank" className="text-xs px-3 py-1.5 rounded-lg transition-colors"
              style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', color: muted }}>
              API Docs
            </a>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="p-5 min-h-full"
            >
              {tab === 'cases'      && <CasesPanel activeCaseId={caseId} onSelectCase={id => { setCaseId(id); setTab('map'); }} isDark={isDark} />}
              {tab === 'ingest'     && <IngestPanel caseId={caseId} isDark={isDark} />}
              {tab === 'harmonize'  && <HarmonizePanel caseId={caseId} isDark={isDark} />}
              {tab === 'map'        && <MapPanel caseId={caseId} isDark={isDark} />}
              {tab === 'review'     && <ReviewPanel caseId={caseId} isDark={isDark} />}
              {tab === 'evidence'   && <EvidencePanel isDark={isDark} />}
              {tab === 'provenance' && <ProvenancePanel caseId={caseId} isDark={isDark} />}
              {tab === 'quality'    && <QualityPanel caseId={caseId} isDark={isDark} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
