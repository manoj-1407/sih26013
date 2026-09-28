import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

declare const maplibregl: any;
interface Props { caseId: string | null; isDark: boolean; }

export default function MapPanel({ caseId, isDark }: Props) {
  const mapRef  = useRef<HTMLDivElement>(null);
  const mapInst = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [sTab, setSTab] = useState<'info' | 'evidence' | 'ripple'>('info');

  const bg     = isDark ? 'rgba(20,28,39,0.9)' : 'rgba(255,255,255,0.96)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';

  const { data: parcelsData, refetch } = useQuery({
    queryKey: ['parcels', caseId],
    queryFn: () => api.get<{ parcels: any[] }>(`/cases/${caseId}/parcels`),
    enabled: !!caseId,
    refetchInterval: 20_000,
  });

  const { data: detail } = useQuery({
    queryKey: ['parcel-detail', caseId, selected],
    queryFn: () => api.get<any>(`/cases/${caseId}/parcels/${selected}`),
    enabled: !!caseId && !!selected,
  });

  useEffect(() => {
    if (!mapRef.current || typeof maplibregl === 'undefined' || mapInst.current) return;
    const map = new maplibregl.Map({
      container: mapRef.current,
      style: {
        version: 8,
        sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap' } },
        layers: [{ id: 'osm', type: 'raster', source: 'osm',
          paint: isDark ? { 'raster-brightness-min': 0, 'raster-brightness-max': 0.25, 'raster-saturation': -0.9, 'raster-contrast': 0.4 } : {} }],
      },
      center: [78.9629, 20.5937], zoom: 4,
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.on('load', () => { mapInst.current = map; setReady(true); });
    return () => { if (mapInst.current) { mapInst.current.remove(); mapInst.current = null; } };
  }, []);

  useEffect(() => {
    const map = mapInst.current;
    if (!map || !ready || !parcelsData?.parcels?.length) return;
    ['gs-fill','gs-line'].forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
    if (map.getSource('gs')) map.removeSource('gs');

    const features = parcelsData.parcels.filter(p => p.geometry).map(p => ({
      type: 'Feature' as const, id: p.canonical_id,
      geometry: p.geometry!,
      properties: { id: p.canonical_id, cf: p.conflict_count, sel: p.canonical_id === selected ? 1 : 0 },
    }));
    if (!features.length) return;

    map.addSource('gs', { type: 'geojson', data: { type: 'FeatureCollection', features } });
    map.addLayer({ id: 'gs-fill', type: 'fill', source: 'gs', paint: {
      'fill-color': ['case',['>', ['get','cf'], 2],'#ef444428',['>', ['get','cf'], 0],'#f59e0b22','#3b82f618'],
      'fill-opacity': ['case', ['==', ['get','sel'], 1], 0.85, 0.5],
    }});
    map.addLayer({ id: 'gs-line', type: 'line', source: 'gs', paint: {
      'line-color': ['case',['==',['get','sel'],1],'#3b82f6',['>', ['get','cf'], 2],'#ef4444',['>', ['get','cf'], 0],'#f59e0b','#3b82f640'],
      'line-width': ['case', ['==', ['get','sel'], 1], 2.5, 1.5],
    }});
    map.on('click', 'gs-fill', (e: any) => { const id = e.features?.[0]?.properties?.id; if (id) setSelected(id); });
    map.on('mouseenter', 'gs-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'gs-fill', () => { map.getCanvas().style.cursor = ''; });

    const all = features.flatMap(f => f.geometry?.type === 'Polygon' ? f.geometry.coordinates[0] as number[][] : []);
    if (all.length) {
      const lons = all.map(c => c[0]), lats = all.map(c => c[1]);
      try { map.fitBounds([[Math.min(...lons),Math.min(...lats)],[Math.max(...lons),Math.max(...lats)]], { padding: 60, duration: 800 }); } catch {}
    }
  }, [ready, parcelsData, selected]);

  const decBg = (d?: string) => d === 'AUTO_APPROVED' ? '#22c55e12' : d === 'REVIEW_REQUIRED' ? '#f59e0b12' : '#6b728012';
  const decColor = (d?: string) => d === 'AUTO_APPROVED' ? '#22c55e' : d === 'REVIEW_REQUIRED' ? '#f59e0b' : '#6b7280';

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">🗺️</div>
      <div className="text-sm">Select a case first</div>
    </div>
  );

  return (
    <div style={{ height: 'calc(100vh - 108px)', display: 'grid', gridTemplateColumns: '1fr 320px', gap: 12 }}>
      {/* Map */}
      <div className="rounded-2xl overflow-hidden relative" style={{ background: bg, border: `1px solid ${border}` }}>
        <div className="absolute top-3 left-3 z-10 text-xs px-3 py-1.5 rounded-lg"
          style={{ background: 'rgba(10,15,26,0.85)', color: muted, border: `1px solid ${border}` }}>
          {parcelsData?.parcels?.length ?? 0} parcels · click to inspect
        </div>
        <button onClick={() => refetch()} className="absolute top-3 right-14 z-10 text-xs px-2.5 py-1.5 rounded-lg transition-colors"
          style={{ background: 'rgba(10,15,26,0.85)', color: muted, border: `1px solid ${border}` }}>
          ↺ Refresh
        </button>
        {typeof maplibregl === 'undefined' && (
          <div className="absolute inset-0 flex items-center justify-center text-sm" style={{ color: muted }}>
            MapLibre loading…
          </div>
        )}
        <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
      </div>

      {/* Side panel */}
      <div className="overflow-y-auto space-y-3 pr-1" style={{ scrollbarWidth: 'thin' }}>
        {!selected ? (
          <div className="rounded-2xl overflow-hidden" style={{ background: bg, border: `1px solid ${border}` }}>
            <div className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest" style={{ borderBottom: `1px solid ${border}`, color: muted }}>
              Parcels ({parcelsData?.parcels?.length ?? 0})
            </div>
            <div className="divide-y max-h-96 overflow-y-auto" style={{ borderColor: border }}>
              {parcelsData?.parcels?.map((p: any) => (
                <button key={p.canonical_id} onClick={() => setSelected(p.canonical_id)}
                  className="w-full flex items-center gap-2 px-4 py-3 text-left transition-colors"
                  style={{ color: text }}
                  onMouseEnter={e => (e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-mono text-cyan-400 truncate">{p.canonical_id}</div>
                    <div className="text-[10px] mt-0.5" style={{ color: muted }}>
                      {Math.round(p.match_confidence * 100)}% · {p.source_count} src · {p.independent_lineages} lin
                    </div>
                  </div>
                  {p.conflict_count > 0 && (
                    <span className="text-[9px] font-bold text-amber-400 bg-amber-500/12 border border-amber-500/25 px-1.5 py-0.5 rounded flex-shrink-0">
                      {p.conflict_count}
                    </span>
                  )}
                  <span style={{ color: muted, fontSize: 10 }}>›</span>
                </button>
              ))}
              {!parcelsData?.parcels?.length && (
                <div className="p-8 text-center text-sm" style={{ color: muted }}>
                  Run harmonization to see parcels
                </div>
              )}
            </div>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div key={selected} initial={{ opacity: 0, x: 15 }} animate={{ opacity: 1, x: 0 }}>
              {/* Header */}
              <div className="rounded-2xl overflow-hidden mb-3" style={{ background: bg, border: `1px solid ${border}` }}>
                <div className="flex items-center gap-2 p-4" style={{ borderBottom: `1px solid ${border}` }}>
                  <span className="text-[11px] font-mono text-cyan-400 flex-1 truncate">{selected}</span>
                  {detail?.proposal?.decision && (
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded"
                      style={{ color: decColor(detail.proposal.decision), background: decBg(detail.proposal.decision), border: `1px solid ${decColor(detail.proposal.decision)}30` }}>
                      {detail.proposal.decision.replace('_', ' ')}
                    </span>
                  )}
                  <button onClick={() => setSelected(null)} style={{ color: muted, fontSize: 13 }}>✕</button>
                </div>

                {/* Tabs */}
                <div className="flex" style={{ borderBottom: `1px solid ${border}` }}>
                  {(['info', 'evidence', 'ripple'] as const).map(t => (
                    <button key={t} onClick={() => setSTab(t)}
                      className="flex-1 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors"
                      style={{ color: sTab === t ? '#60a5fa' : muted, borderBottom: sTab === t ? '2px solid #3b82f6' : '2px solid transparent' }}>
                      {t}
                    </button>
                  ))}
                </div>

                <div className="p-4">
                  {sTab === 'info' && detail && (
                    <div className="space-y-0">
                      {[
                        ['Confidence', `${Math.round(detail.match_confidence * 100)}%`],
                        ['Lineages', `${detail.independent_lineages}`],
                        ['Sources', `${detail.source_count}`],
                        detail.area_sqm ? ['Area', `${Math.round(detail.area_sqm)} m²`] : null,
                        detail.land_use ? ['Land Use', detail.land_use] : null,
                        detail.ulpin ? ['ULPIN', detail.ulpin] : null,
                      ].filter(Boolean).map(([k, v]) => (
                        <div key={k as string} className="flex items-center justify-between py-1.5" style={{ borderBottom: `1px solid ${border}50` }}>
                          <span className="text-xs" style={{ color: muted }}>{k}</span>
                          <span className="text-xs font-medium" style={{ color: text }}>{v}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {sTab === 'evidence' && detail?.proposal?.confidence_components && (
                    <div>
                      {Object.entries(detail.proposal.confidence_components).map(([k, v]) => {
                        if (typeof v !== 'number' || v <= 0 || v > 1) return null;
                        const pct = Math.round(v * 100);
                        const c = pct >= 85 ? '#22c55e' : pct >= 65 ? '#f59e0b' : '#ef4444';
                        return (
                          <div key={k} className="flex items-center gap-2 mb-1.5">
                            <span className="text-[10px] w-24 truncate capitalize" style={{ color: muted }}>{k.replace(/_/g, ' ')}</span>
                            <div className="flex-1 rounded-full overflow-hidden" style={{ background: isDark ? '#0c1118' : '#e8edf5', height: 5 }}>
                              <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }} className="h-full rounded-full" style={{ background: c }} />
                            </div>
                            <span className="text-[10px] font-mono w-7 text-right font-bold" style={{ color: c }}>{pct}%</span>
                          </div>
                        );
                      })}
                      <div className="mt-2 text-[10px]" style={{ color: muted }}>
                        {detail.independent_lineages} independent lineage{detail.independent_lineages !== 1 ? 's' : ''}
                        {detail.independent_lineages < 2 && <span className="text-amber-400 ml-1">⚠ below threshold</span>}
                      </div>
                    </div>
                  )}

                  {sTab === 'ripple' && detail?.proposal?.ripple_check && (
                    <div className="space-y-2">
                      <div className="rounded-lg p-2.5 text-xs"
                        style={{ background: detail.proposal.ripple_check.safe_to_auto_approve ? '#22c55e12' : '#f59e0b12', color: detail.proposal.ripple_check.safe_to_auto_approve ? '#22c55e' : '#f59e0b', border: `1px solid ${detail.proposal.ripple_check.safe_to_auto_approve ? '#22c55e30' : '#f59e0b30'}` }}>
                        {detail.proposal.ripple_check.summary}
                      </div>
                      {detail.proposal.ripple_check.issues?.map((issue: any) => (
                        <div key={issue.issue_id} className="rounded-lg p-2.5 text-xs space-y-0.5" style={{ background: isDark ? '#0c1118' : '#f0f4f8', border: `1px solid ${border}` }}>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-[10px]" style={{ color: issue.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b' }}>{issue.severity}</span>
                            <span style={{ color: muted }}>{issue.issue_type.replace(/_/g, ' ')}</span>
                          </div>
                          <div style={{ color: muted }}>{issue.description}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Conflicts */}
              {detail?.conflicts?.length > 0 && (
                <div className="rounded-2xl overflow-hidden mb-3" style={{ background: bg, border: `1px solid ${border}` }}>
                  <div className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest" style={{ borderBottom: `1px solid ${border}`, color: muted }}>
                    Conflicts ({detail.conflicts.length})
                  </div>
                  {detail.conflicts.map((c: any) => (
                    <div key={c.conflict_id} className="px-4 py-3" style={{ borderBottom: `1px solid ${border}50` }}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-bold" style={{ color: c.severity === 'CRITICAL' ? '#ef4444' : c.severity === 'HIGH' ? '#f59e0b' : c.severity === 'MEDIUM' ? '#a78bfa' : '#6b7280' }}>● {c.severity}</span>
                        <span className="text-xs" style={{ color: text }}>{c.type.replace(/_/g, ' ')}</span>
                        {c.measure !== undefined && <span className="ml-auto text-[10px] font-mono" style={{ color: muted }}>{c.measure} {c.measure_unit}</span>}
                      </div>
                      <div className="text-[11px] leading-relaxed" style={{ color: muted }}>{c.description}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <a href={`/api/v1/cases/${caseId}/parcels/${selected}/export`} download
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-lg transition-colors"
                  style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: muted, border: `1px solid ${border}` }}>
                  📦 ZIP
                </a>
                <a href={`/api/v1/cases/${caseId}/export/geopackage`} download
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-lg transition-colors"
                  style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: muted, border: `1px solid ${border}` }}>
                  🗄 GPKG
                </a>
              </div>
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
