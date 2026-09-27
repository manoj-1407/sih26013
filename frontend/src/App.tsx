import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api/client';
import CasesPanel from './components/CasesPanel';
import IngestPanel from './components/IngestPanel';
import HarmonizePanel from './components/HarmonizePanel';
import ParcelMap from './components/ParcelMap';
import ReviewPanel from './components/ReviewPanel';
import EvidencePanel from './components/EvidencePanel';
import ProvenancePanel from './components/ProvenancePanel';
import QualityReportPanel from './components/QualityReportPanel';

type Tab = 'cases' | 'ingest' | 'harmonize' | 'map' | 'review' | 'evidence' | 'provenance' | 'quality';

const TAB_LABELS: Record<Tab, string> = {
  cases: 'Cases',
  ingest: 'Ingest Data',
  harmonize: 'Harmonize',
  map: 'Map & Conflicts',
  review: 'Review Queue',
  evidence: 'Evidence',
  provenance: 'Provenance',
  quality: 'Data Quality',
};

const TAB_ICONS: Record<Tab, string> = {
  cases: '📁',
  ingest: '📥',
  harmonize: '⚡',
  map: '🗺',
  review: '🔍',
  evidence: '🔏',
  provenance: '🌐',
  quality: '📊',
};

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('cases');
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; version: string }>('/health'),
    refetchInterval: 30_000,
  });

  const reviewQuery = useQuery({
    queryKey: ['review', activeCaseId],
    queryFn: () => activeCaseId
      ? api.get<{ pending_count: number }>(`/cases/${activeCaseId}/review`)
      : Promise.resolve({ pending_count: 0 }),
    enabled: !!activeCaseId,
    refetchInterval: 10_000,
  });

  const reviewCount = reviewQuery.data?.pending_count ?? 0;

  return (
    <div className="shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          GeoSamanvay
          <span>Evidence-Aware Harmonization</span>
        </div>

        {activeCaseId && (
          <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active Case</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--cyan)', marginTop: 2, fontFamily: 'var(--mono)' }}>
              {activeCaseId}
            </div>
          </div>
        )}

        <div className="sidebar-section">
          <div className="sidebar-section-label">Workflow</div>
          {(['cases', 'ingest', 'harmonize', 'map'] as Tab[]).map(tab => (
            <button
              key={tab}
              className={`nav-item ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              <span className="icon">{TAB_ICONS[tab]}</span>
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Analysis</div>
          {(['review', 'evidence', 'provenance', 'quality'] as Tab[]).map(tab => (
            <button
              key={tab}
              className={`nav-item ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              <span className="icon">{TAB_ICONS[tab]}</span>
              {TAB_LABELS[tab]}
              {tab === 'review' && reviewCount > 0 && (
                <span className="nav-badge">{reviewCount}</span>
              )}
            </button>
          ))}
        </div>

        <div style={{ marginTop: 'auto', padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 10, color: 'var(--text3)' }}>
            {health?.status === 'OPERATIONAL'
              ? <span style={{ color: 'var(--green)' }}>● System Operational</span>
              : <span style={{ color: 'var(--red)' }}>● Backend Offline</span>
            }
          </div>
          <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
            v{health?.version ?? '—'} · SIH26013
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="main-area">
        <div className="topbar">
          <span className="topbar-title">{TAB_LABELS[activeTab]}</span>
          {activeCaseId && (
            <>
              <span className="topbar-sep">|</span>
              <span>Case: <strong style={{ color: 'var(--cyan)', fontFamily: 'var(--mono)' }}>{activeCaseId}</strong></span>
            </>
          )}
        </div>

        <div className="content-area">
          {activeTab === 'cases' && (
            <CasesPanel activeCaseId={activeCaseId} onSelectCase={setActiveCaseId} />
          )}
          {activeTab === 'ingest' && (
            <IngestPanel caseId={activeCaseId} />
          )}
          {activeTab === 'harmonize' && (
            <HarmonizePanel caseId={activeCaseId} />
          )}
          {activeTab === 'map' && (
            <ParcelMap caseId={activeCaseId} />
          )}
          {activeTab === 'review' && (
            <ReviewPanel caseId={activeCaseId} />
          )}
          {activeTab === 'evidence' && (
            <EvidencePanel caseId={activeCaseId} />
          )}
          {activeTab === 'provenance' && (
            <ProvenancePanel caseId={activeCaseId} />
          )}
          {activeTab === 'quality' && (
            <QualityReportPanel caseId={activeCaseId} />
          )}
        </div>
      </div>
    </div>
  );
}
