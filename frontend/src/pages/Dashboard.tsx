import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from '../context/ThemeContext';
import { api } from '../api/client';
import StatusBar from '../components/ui/StatusBar';
import CasesPanel from '../components/app/CasesPanel';
import IngestPanel from '../components/app/IngestPanel';
import HarmonizePanel from '../components/app/HarmonizePanel';
import MapPanel from '../components/app/MapPanel';
import ReviewPanel from '../components/app/ReviewPanel';
import EvidencePanel from '../components/app/EvidencePanel';
import ProvenancePanel from '../components/app/ProvenancePanel';
import QualityPanel from '../components/app/QualityPanel';
import DemoTab from '../components/app/DemoTab';

type Tab = 'demo' | 'cases' | 'ingest' | 'harmonize' | 'map' | 'review' | 'evidence' | 'provenance' | 'quality';

const TABS: Array<{ id: Tab; emoji: string; label: string }> = [
  { id: 'demo',       emoji: '▶',  label: 'Demo' },
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
  const navigate   = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const [tab, setTab]           = useState<Tab>('demo');
  const [caseId, setCaseId]     = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false); // mobile: closed by default
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);

  // Detect mobile
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);

  // Close mobile sidebar when tab changes
  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [tab, isMobile]);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; version: string }>('/health'),
    refetchInterval: 5_000,
    retry: false,
  });

  const { data: reviewData } = useQuery({
    queryKey: ['review-count', caseId],
    queryFn: () => api.get<{ pending_count: number }>(`/cases/${caseId}/review`),
    enabled: !!caseId,
    refetchInterval: 8_000,
  });

  const reviewCount = reviewData?.pending_count ?? 0;

  // Colors
  const bg      = isDark ? '#0c1118'              : '#f0f4f8';
  const sidebar  = isDark ? '#0a0f1a'             : '#ffffff';
  const border   = isDark ? '#1e2d42'             : '#e2e8f0';
  const text     = isDark ? '#e8edf5'             : '#1a202c';
  const muted    = isDark ? '#6b7280'             : '#94a3b8';

  // Sidebar width
  const sidebarW = isMobile ? 220 : (desktopCollapsed ? 52 : 200);

  const NavItem = ({ t }: { t: typeof TABS[0] }) => {
    const isActive = tab === t.id;
    const cnt = t.id === 'review' ? reviewCount : 0;
    return (
      <button
        onClick={() => { setTab(t.id); }}
        style={{
          width: '100%', display: 'flex', alignItems: 'center',
          gap: 10, padding: '11px 14px',
          background: isActive ? (isDark ? 'rgba(59,130,246,0.12)' : 'rgba(59,130,246,0.08)') : 'transparent',
          border: 'none', cursor: 'pointer',
          color: isActive ? '#60a5fa' : muted,
          fontSize: 13, fontWeight: isActive ? 600 : 400,
          borderLeft: `2px solid ${isActive ? '#3b82f6' : 'transparent'}`,
          transition: 'all 0.15s', textAlign: 'left',
          position: 'relative',
        }}
      >
        <span style={{ fontSize: 16, flexShrink: 0 }}>{t.emoji}</span>
        {(!desktopCollapsed || isMobile) && (
          <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {t.label}
          </span>
        )}
        {cnt > 0 && (!desktopCollapsed || isMobile) && (
          <span style={{ fontSize: 10, fontWeight: 700, color: '#fff', background: '#ef4444', padding: '1px 5px', borderRadius: 9999 }}>
            {cnt}
          </span>
        )}
        {cnt > 0 && desktopCollapsed && !isMobile && (
          <span style={{ position: 'absolute', top: 6, right: 6, width: 7, height: 7, background: '#ef4444', borderRadius: '50%' }} />
        )}
      </button>
    );
  };

  return (
    <div style={{ display: 'flex', height: '100dvh', overflow: 'hidden', background: bg, color: text, position: 'relative' }}>

      {/* Mobile overlay backdrop */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 40 }}
        />
      )}

      {/* Sidebar */}
      <aside style={{
        position: isMobile ? 'fixed' : 'relative',
        top: 0, bottom: 0, left: 0,
        zIndex: isMobile ? 50 : 1,
        width: sidebarW,
        background: sidebar,
        borderRight: '1px solid ' + border,
        display: 'flex', flexDirection: 'column',
        flexShrink: 0,
        transform: isMobile ? (sidebarOpen ? 'translateX(0)' : 'translateX(-100%)') : 'none',
        transition: 'transform 0.25s ease, width 0.2s ease',
        boxShadow: isMobile && sidebarOpen ? '4px 0 24px rgba(0,0,0,0.4)' : 'none',
      }}>
        {/* Logo */}
        <div style={{ height: 56, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 10, borderBottom: '1px solid ' + border, flexShrink: 0 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: 13, flexShrink: 0 }}>G</div>
          {(!desktopCollapsed || isMobile) && (
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: text, whiteSpace: 'nowrap' }}>GeoSamanvay</div>
              <div style={{ fontSize: 10, color: muted, whiteSpace: 'nowrap' }}>SIH26013</div>
            </div>
          )}
          {isMobile && (
            <button onClick={() => setSidebarOpen(false)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: muted, cursor: 'pointer', fontSize: 18, padding: 4 }}>✕</button>
          )}
        </div>

        {/* Active case */}
        {caseId && (!desktopCollapsed || isMobile) && (
          <div style={{ padding: '8px 14px', borderBottom: '1px solid ' + border, flexShrink: 0 }}>
            <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: muted, marginBottom: 3 }}>Active Case</div>
            <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#22d3ee', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{caseId}</div>
          </div>
        )}

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
          {TABS.map(t => <NavItem key={t.id} t={t} />)}
        </nav>

        {/* Bottom */}
        <div style={{ padding: '8px', borderTop: '1px solid ' + border, flexShrink: 0 }}>
          <button onClick={toggleTheme} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '7px', borderRadius: 8, border: '1px solid ' + border, background: 'transparent', cursor: 'pointer', color: muted, fontSize: 14 }}>
            {isDark ? '☀️' : '🌙'}
            {(!desktopCollapsed || isMobile) && <span style={{ marginLeft: 6, fontSize: 11 }}>{isDark ? 'Light mode' : 'Dark mode'}</span>}
          </button>
          {!isMobile && (
            <button onClick={() => setDesktopCollapsed(v => !v)} style={{ width: '100%', marginTop: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '5px', border: 'none', background: 'transparent', cursor: 'pointer', color: muted, fontSize: 11 }}>
              {desktopCollapsed ? '▶' : '◀ Collapse'}
            </button>
          )}
        </div>
      </aside>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        {/* Topbar */}
        <div style={{
          height: 52, display: 'flex', alignItems: 'center',
          padding: '0 16px', flexShrink: 0,
          background: isDark ? 'rgba(10,15,26,0.95)' : 'rgba(255,255,255,0.95)',
          borderBottom: '1px solid ' + border,
          gap: 10,
        }}>
          {/* Hamburger (mobile) or home button */}
          {isMobile ? (
            <button onClick={() => setSidebarOpen(v => !v)} style={{ background: 'none', border: 'none', color: text, cursor: 'pointer', fontSize: 20, padding: '2px 4px', flexShrink: 0 }}>☰</button>
          ) : (
            <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', color: muted, cursor: 'pointer', fontSize: 13, padding: '2px 4px', flexShrink: 0, whiteSpace: 'nowrap' }}>← Home</button>
          )}

          <div style={{ color: border, flexShrink: 0 }}>|</div>

          <span style={{ fontSize: 13, fontWeight: 600, color: text, flexShrink: 0 }}>
            {TABS.find(t => t.id === tab)?.emoji} {isMobile ? '' : TABS.find(t => t.id === tab)?.label}
          </span>

          {caseId && (
            <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#22d3ee', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: isMobile ? 100 : 200 }}>
              · {caseId}
            </span>
          )}

          <div style={{ marginLeft: 'auto' }}>
            <StatusBar isDark={isDark} version={health?.version} caseId={caseId} refreshInterval={8} />
          </div>
        </div>

        {/* Mobile bottom nav bar */}
        {isMobile && (
          <div style={{
            position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 30,
            background: sidebar, borderTop: '1px solid ' + border,
            display: 'flex', height: 60, overflowX: 'auto',
          }}>
            {TABS.map(t => {
              const isActive = tab === t.id;
              const cnt = t.id === 'review' ? reviewCount : 0;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  style={{
                    flex: '0 0 auto', minWidth: 56,
                    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    gap: 2, border: 'none', background: 'transparent', cursor: 'pointer',
                    color: isActive ? '#3b82f6' : muted,
                    borderTop: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                    padding: '6px 8px', position: 'relative',
                  }}
                >
                  <span style={{ fontSize: 18 }}>{t.emoji}</span>
                  <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{t.label}</span>
                  {cnt > 0 && <span style={{ position: 'absolute', top: 4, right: 6, width: 7, height: 7, background: '#ef4444', borderRadius: '50%' }} />}
                </button>
              );
            })}
          </div>
        )}

        {/* Content */}
        <div style={{
          flex: 1, overflowY: 'auto', overflowX: 'hidden',
          padding: isMobile ? '12px 12px 72px' : '20px',
          WebkitOverflowScrolling: 'touch',
        }}>
          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}>
              {tab === 'demo'      && <DemoTab        isDark={isDark} onSelectCase={id => { setCaseId(id); }} />}
              {tab === 'cases'      && <CasesPanel      activeCaseId={caseId} onSelectCase={id => { setCaseId(id); setTab('map'); }} isDark={isDark} />}
              {tab === 'ingest'     && <IngestPanel      caseId={caseId} isDark={isDark} />}
              {tab === 'harmonize'  && <HarmonizePanel   caseId={caseId} isDark={isDark} />}
              {tab === 'map'        && <MapPanel          caseId={caseId} isDark={isDark} />}
              {tab === 'review'     && <ReviewPanel       caseId={caseId} isDark={isDark} />}
              {tab === 'evidence'   && <EvidencePanel     isDark={isDark} />}
              {tab === 'provenance' && <ProvenancePanel   caseId={caseId} isDark={isDark} />}
              {tab === 'quality'    && <QualityPanel      caseId={caseId} isDark={isDark} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
