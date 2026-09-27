import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { Map, X, ChevronRight, Download, AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { api, Parcel } from '../../api/client';

declare const maplibregl: any;

const DECISION_STYLES: Record<string, { bg: string; text: string; badge: string }> = {
  AUTO_APPROVED: { bg: 'bg-green-500/10', text: 'text-green-400', badge: 'badge-ok' },
  REVIEW_REQUIRED: { bg: 'bg-amber-500/10', text: 'text-amber-400', badge: 'badge-warn' },
  BLOCKED: { bg: 'bg-red-500/10', text: 'text-red-400', badge: 'badge-err' },
  PENDING: { bg: 'bg-gray-500/10', text: 'text-gray-400', badge: 'badge-info' },
};

function ConfBar({ label, val }: { label: string; val: number }) {
  const pct = Math.round(val * 100);
  const color = pct >= 85 ? '#22c55e' : pct >= 65 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span className="text-[10px] text-gray-600 w-20 truncate capitalize">{label.replace(/_/g, ' ')}</span>
      <div className="flex-1 bg-dark-600 rounded-full h-1 overflow-hidden">
        <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }}
          className="h-full rounded-full" style={{ background: color }} />
      </div>
      <span className="text-[10px] font-mono font-bold w-7 text-right" style={{ color }}>{pct}%</span>
    </div>
  );
}

export default function MapPanel({ caseId }: { caseId: string | null }) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInst = useRef<any>(null);
  const [mapReady, setMapReady] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'info' | 'evidence' | 'ripple'>('info');

  const { data: parcelsData } = useQuery({
    queryKey: ['parcels', caseId],
    queryFn: () => api.get<{ parcels: Parcel[] }>(`/cases/${caseId}/parcels`),
    enabled: !!caseId,
    refetchInterval: 15_000,
  });

  const { data: detail } = useQuery({
    queryKey: ['parcel-detail', caseId, selected],
    queryFn: () => api.get<Parcel>(`/cases/${caseId}/parcels/${selected}`),
    enabled: !!caseId && !!selected,
  });

  // Init map
  useEffect(() => {
    if (!mapRef.current || typeof maplibregl === 'undefined' || mapInst.current) return;
    const map = new maplibregl.Map({
      container: mapRef.current,
      style: {
        version: 8,
        glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
        sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256 } },
        layers: [{ id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-brightness-min': 0, 'raster-brightness-max': 0.3, 'raster-saturation': -0.9, 'raster-contrast': 0.3 } }],
      },
      center: [78.9629, 20.5937], zoom: 4,
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.on('load', () => { mapInst.current = map; setMapReady(true); });
    return () => { map.remove(); mapInst.current = null; };
  }, []);

  // Add parcel features
  useEffect(() => {
    const map = mapInst.current;
    if (!map || !mapReady || !parcelsData?.parcels?.length) return;

    ['gs-fill', 'gs-line', 'gs-fill-hover'].forEach(id => { if (map.getLayer(id)) map.removeLayer(id); });
    if (map.getSource('gs')) map.removeSource('gs');

    const features = parcelsData.parcels.filter(p => p.geometry).map(p => ({
      type: 'Feature' as const, id: p.canonical_id,
      geometry: p.geometry!,
      properties: { id: p.canonical_id, conflicts: p.conflict_count, confidence: p.match_confidence, decision: p.proposal_id ? 'HAS_PROPOSAL' : 'PENDING' },
    }));
    if (!features.length) return;

    map.addSource('gs', { type: 'geojson', data: { type: 'FeatureCollection', features } });
    map.addLayer({
      id: 'gs-fill', type: 'fill', source: 'gs',
      paint: {
        'fill-color': ['case', ['>', ['get', 'conflicts'], 2], '#ef444430', ['>', ['get', 'conflicts'], 0], '#f59e0b28', '#3b82f618'],
        'fill-opacity': ['case', ['==', ['get', 'id'], selected ?? ''], 0.8, 0.5],
      },
    });
    map.addLayer({
      id: 'gs-line', type: 'line', source: 'gs',
      paint: {
        'line-color': ['case', ['==', ['get', 'id'], selected ?? ''], '#3b82f6', ['>', ['get', 'conflicts'], 2], '#ef4444', ['>', ['get', 'conflicts'], 0], '#f59e0b', '#3b82f640'],
        'line-width': ['case', ['==', ['get', 'id'], selected ?? ''], 2.5, 1.5],
      },
    });
    map.on('click', 'gs-fill', (e: any) => {
      const id = e.features?.[0]?.properties?.id;
      if (id) setSelected(id);
    });
    map.on('mouseenter', 'gs-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'gs-fill', () => { map.getCanvas().style.cursor = ''; });

    const all = features.flatMap(f => f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] as [number,number][] : []);
    if (all.length) {
      const lons = all.map(c => c[0]), lats = all.map(c => c[1]);
      map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 60, duration: 1000 });
    }
  }, [mapReady, parcelsData, selected]);

  const parcel = detail;
  const propDecision = parcel?.proposal?.decision ?? 'PENDING';
  const style = DECISION_STYLES[propDecision] ?? DECISION_STYLES.PENDING;

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
      <Map size={40} className="opacity-20" />
      <p className="text-sm">Select a case first</p>
    </div>
  );

  return (
    <div style={{ height: 'calc(100vh - 100px)' }} className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Map */}
      <div className="lg:col-span-2 glass rounded-2xl overflow-hidden relative">
        <div className="absolute top-3 left-3 z-10 glass rounded-lg px-3 py-1.5 text-xs text-gray-400">
          {parcelsData?.parcels?.length ?? 0} parcels · click to inspect
        </div>
        {typeof maplibregl === 'undefined' && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm">
            MapLibre not available
          </div>
        )}
        <div ref={mapRef} className="w-full h-full" />
      </div>

      {/* Side panel */}
      <div className="overflow-y-auto scrollbar-thin space-y-3">
        {/* Parcel list */}
        {!selected && (
          <div className="glass rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-dark-200/30 text-xs font-bold text-gray-400 uppercase tracking-wider">
              Parcels ({parcelsData?.parcels?.length ?? 0})
            </div>
            <div className="divide-y divide-dark-200/30 max-h-96 overflow-y-auto scrollbar-thin">
              {parcelsData?.parcels?.map(p => (
                <button key={p.canonical_id} onClick={() => setSelected(p.canonical_id)}
                  className="w-full flex items-center gap-2 px-4 py-3 hover:bg-dark-300/30 transition-colors text-left">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-mono text-cyan-400 truncate">{p.canonical_id}</div>
                    <div className="text-[11px] text-gray-600 mt-0.5">
                      {Math.round(p.match_confidence * 100)}% · {p.source_count} src · {p.independent_lineages} lin
                    </div>
                  </div>
                  {p.conflict_count > 0 && <span className="badge-warn text-[9px]">{p.conflict_count}</span>}
                  <ChevronRight size={12} className="text-gray-700 flex-shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Detail panel */}
        <AnimatePresence>
          {selected && parcel && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
              {/* Header */}
              <div className="glass rounded-2xl overflow-hidden mb-3">
                <div className="flex items-center gap-2 p-4 border-b border-dark-200/30">
                  <span className="text-xs font-mono text-cyan-400 flex-1 truncate">{selected}</span>
                  <span className={`text-[10px] font-bold ${style.text}`}>{propDecision.replace('_', ' ')}</span>
                  <button onClick={() => setSelected(null)} className="text-gray-600 hover:text-white ml-1">
                    <X size={13} />
                  </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-dark-200/30">
                  {(['info', 'evidence', 'ripple'] as const).map(t => (
                    <button key={t} onClick={() => setActiveTab(t)}
                      className={`flex-1 py-2 text-[11px] font-semibold uppercase tracking-wider transition-colors
                        ${activeTab === t ? 'text-brand-400 border-b-2 border-brand-500' : 'text-gray-600 hover:text-gray-400'}`}>
                      {t}
                    </button>
                  ))}
                </div>

                <div className="p-4">
                  {activeTab === 'info' && (
                    <div className="space-y-1">
                      <div className="data-row"><span className="data-key">Confidence</span><span className="data-val font-bold">{Math.round(parcel.match_confidence * 100)}%</span></div>
                      <div className="data-row"><span className="data-key">Lineages</span><span className="data-val">{parcel.independent_lineages}</span></div>
                      <div className="data-row"><span className="data-key">Sources</span><span className="data-val">{parcel.source_count}</span></div>
                      {parcel.area_sqm && <div className="data-row"><span className="data-key">Area</span><span className="data-val font-mono">{Math.round(parcel.area_sqm)} m²</span></div>}
                      {parcel.land_use && <div className="data-row"><span className="data-key">Land Use</span><span className="data-val">{parcel.land_use}</span></div>}
                      {parcel.ulpin && <div className="data-row"><span className="data-key">ULPIN</span><span className="data-val font-mono text-[10px]">{parcel.ulpin}</span></div>}
                    </div>
                  )}

                  {activeTab === 'evidence' && parcel.proposal?.confidence_components && (
                    <div className="pt-1">
                      {Object.entries(parcel.proposal.confidence_components).map(([k, v]) =>
                        typeof v === 'number' && v > 0 && v <= 1
                          ? <ConfBar key={k} label={k} val={v} />
                          : null
                      )}
                      <div className="mt-3 text-[10px] text-gray-600">
                        {parcel.independent_lineages} independent lineage{parcel.independent_lineages !== 1 ? 's' : ''}
                        {parcel.independent_lineages < 2 && <span className="text-amber-500 ml-1">⚠ below threshold</span>}
                      </div>
                    </div>
                  )}

                  {activeTab === 'ripple' && parcel.proposal?.ripple_check && (
                    <div className="space-y-2">
                      <div className={`rounded-lg p-3 text-xs ${parcel.proposal.ripple_check.safe_to_auto_approve ? 'bg-green-500/10 text-green-400' : 'bg-amber-500/10 text-amber-400'}`}>
                        {parcel.proposal.ripple_check.summary}
                      </div>
                      {parcel.proposal.ripple_check.issues?.map(issue => (
                        <div key={issue.issue_id} className="bg-dark-600 rounded-lg p-3 text-xs space-y-1">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold severity-${issue.severity}`}>{issue.severity}</span>
                            <span className="text-gray-400">{issue.issue_type.replace(/_/g, ' ')}</span>
                          </div>
                          <div className="text-gray-500">{issue.description}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Conflicts */}
              {(parcel.conflicts ?? []).length > 0 && (
                <div className="glass rounded-2xl overflow-hidden mb-3">
                  <div className="px-4 py-3 border-b border-dark-200/30 text-xs font-bold text-gray-400 uppercase tracking-wider">
                    Conflicts ({parcel.conflicts!.length})
                  </div>
                  <div className="divide-y divide-dark-200/30">
                    {parcel.conflicts!.map(c => (
                      <div key={c.conflict_id} className="px-4 py-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`severity-${c.severity} text-[10px] font-bold`}>●</span>
                          <span className="text-xs text-white">{c.type.replace(/_/g, ' ')}</span>
                          <span className={`ml-auto text-[9px] font-bold ${c.severity === 'CRITICAL' ? 'text-red-400' : c.severity === 'HIGH' ? 'text-amber-400' : 'text-gray-500'}`}>{c.severity}</span>
                        </div>
                        <div className="text-[11px] text-gray-500 leading-relaxed">{c.description}</div>
                        {c.measure !== undefined && (
                          <div className="text-[10px] text-gray-600 mt-1 font-mono">{c.measure} {c.measure_unit}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <a href={`/api/v1/cases/${caseId}/parcels/${selected}/export`} download
                  className="btn-ghost flex-1 justify-center text-xs py-2">
                  <Download size={12} /> Evidence ZIP
                </a>
                <a href={`/api/v1/cases/${caseId}/export/geopackage`} download
                  className="btn-ghost flex-1 justify-center text-xs py-2">
                  <Download size={12} /> GeoPackage
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
