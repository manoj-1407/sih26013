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
  const [showDetail, setShowDetail] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);

  const bg     = isDark ? 'rgba(20,28,39,0.9)' : 'rgba(255,255,255,0.96)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';

  const { data: parcelsData, refetch } = useQuery({
    queryKey: ['parcels', caseId],
    queryFn: () => api.get<{ parcels: any[] }>(`/cases/${caseId}/parcels`),
    enabled: !!caseId,
    refetchInterval: 30_000,
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
          paint: isDark ? { 'raster-brightness-min': 0, 'raster-brightness-max': 0.25, 'raster-saturation': -0.9 } : {} }],
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
      properties: { id: p.canonical_id, cf: p.conflict_count },
    }));
    if (!features.length) return;
    map.addSource('gs', { type: 'geojson', data: { type: 'FeatureCollection', features } });
    map.addLayer({ id: 'gs-fill', type: 'fill', source: 'gs', paint: {
      'fill-color': ['case', ['>', ['get','cf'], 2], '#ef444428', ['>', ['get','cf'], 0], '#f59e0b22', '#3b82f618'],
      'fill-opacity': 0.7,
    }});
    map.addLayer({ id: 'gs-line', type: 'line', source: 'gs', paint: {
      'line-color': ['case', ['==',['get','id'],selected??''], '#3b82f6', ['>', ['get','cf'], 2], '#ef4444', ['>', ['get','cf'], 0], '#f59e0b', '#3b82f640'],
      'line-width': ['case', ['==',['get','id'],selected??''], 2.5, 1.5],
    }});
    map.on('click', 'gs-fill', (e: any) => {
      const id = e.features?.[0]?.properties?.id;
      if (id) { setSelected(id); setShowDetail(true); setSTab('info'); }
    });
    map.on('mouseenter', 'gs-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'gs-fill', () => { map.getCanvas().style.cursor = ''; });
    const all = features.flatMap(f => f.geometry?.type === 'Polygon' ? f.geometry.coordinates[0] as number[][] : []);
    if (all.length) {
      const lons = all.map(c => c[0]), lats = all.map(c => c[1]);
      try { map.fitBounds([[Math.min(...lons),Math.min(...lats)],[Math.max(...lons),Math.max(...lats)]], { padding: isMobile ? 20 : 60, duration: 800 }); } catch {}
    }
  }, [ready, parcelsData, selected]);

  const decColor = (d?: string) => d === 'AUTO_APPROVED' ? '#22c55e' : d === 'REVIEW_REQUIRED' ? '#f59e0b' : '#6b7280';

  if (!caseId) return (
    <div style={{ display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:300,color:muted }}>
      <div style={{ fontSize:48,marginBottom:12 }}>🗺️</div>
      <div style={{ fontSize:14 }}>Select a case first</div>
    </div>
  );

  // Map height: mobile = 280px, desktop = 100% of container
  const mapH = isMobile ? 280 : 'calc(100vh - 160px)';

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Map */}
      <div style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', border: '1px solid ' + border, marginBottom: 12, height: mapH, minHeight: 220 }}>
        <div style={{ position:'absolute',top:10,left:10,zIndex:10,background:'rgba(10,15,26,0.85)',color:muted,border:'1px solid '+border,borderRadius:8,padding:'5px 10px',fontSize:11 }}>
          {parcelsData?.parcels?.length ?? 0} parcels · tap to inspect
        </div>
        <button onClick={() => refetch()} style={{ position:'absolute',top:10,right:46,zIndex:10,background:'rgba(10,15,26,0.85)',color:muted,border:'1px solid '+border,borderRadius:8,padding:'5px 10px',fontSize:11,cursor:'pointer' }}>↺</button>
        {typeof maplibregl === 'undefined' && (
          <div style={{ position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center',color:muted,fontSize:13 }}>Map loading…</div>
        )}
        <div ref={mapRef} style={{ width:'100%',height:'100%' }} />
      </div>

      {/* Parcel list (when nothing selected on mobile, show compact list) */}
      {!showDetail && (
        <div style={{ borderRadius:12,overflow:'hidden',background:bg,border:'1px solid '+border }}>
          <div style={{ padding:'10px 16px',borderBottom:'1px solid '+border,fontSize:10,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.08em',color:muted }}>
            Parcels ({parcelsData?.parcels?.length ?? 0})
          </div>
          <div style={{ maxHeight: isMobile ? 220 : 300, overflowY:'auto' }}>
            {parcelsData?.parcels?.map((p: any) => (
              <button key={p.canonical_id} onClick={() => { setSelected(p.canonical_id); setShowDetail(true); setSTab('info'); }}
                style={{ width:'100%',display:'flex',alignItems:'center',gap:10,padding:'10px 16px',borderBottom:'1px solid '+border+'40',background:'transparent',border:'none',cursor:'pointer',textAlign:'left' }}>
                <div style={{ flex:1,minWidth:0 }}>
                  <div style={{ fontSize:11,fontFamily:'monospace',color:'#22d3ee',marginBottom:2,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap' }}>{p.canonical_id}</div>
                  <div style={{ fontSize:10,color:muted }}>{Math.round(p.match_confidence*100)}% · {p.source_count} sources · {p.independent_lineages} lineages</div>
                </div>
                {p.conflict_count > 0 && <span style={{ fontSize:9,fontWeight:700,color:'#fbbf24',background:'rgba(245,158,11,0.12)',border:'1px solid rgba(245,158,11,0.3)',padding:'1px 6px',borderRadius:4,flexShrink:0 }}>{p.conflict_count}</span>}
                <span style={{ color:muted,fontSize:12,flexShrink:0 }}>›</span>
              </button>
            ))}
            {!parcelsData?.parcels?.length && (
              <div style={{ padding:24,textAlign:'center',fontSize:13,color:muted }}>Run harmonization to see parcels</div>
            )}
          </div>
        </div>
      )}

      {/* Detail panel */}
      <AnimatePresence>
        {showDetail && selected && (
          <motion.div initial={{ opacity:0,y:10 }} animate={{ opacity:1,y:0 }} exit={{ opacity:0 }}>
            <div style={{ borderRadius:12,overflow:'hidden',background:bg,border:'1px solid '+border,marginBottom:12 }}>
              {/* Header */}
              <div style={{ display:'flex',alignItems:'center',gap:8,padding:'12px 16px',borderBottom:'1px solid '+border }}>
                <button onClick={() => setShowDetail(false)} style={{ background:'none',border:'none',color:muted,cursor:'pointer',fontSize:16,padding:'2px 6px' }}>←</button>
                <span style={{ fontSize:11,fontFamily:'monospace',color:'#22d3ee',flex:1,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap' }}>{selected}</span>
                {detail?.proposal?.decision && (
                  <span style={{ fontSize:9,fontWeight:700,color:decColor(detail.proposal.decision),background:decColor(detail.proposal.decision)+'18',border:'1px solid '+decColor(detail.proposal.decision)+'35',padding:'2px 7px',borderRadius:4,flexShrink:0 }}>
                    {detail.proposal.decision.replace('_',' ')}
                  </span>
                )}
              </div>
              {/* Tabs */}
              <div style={{ display:'flex',borderBottom:'1px solid '+border }}>
                {(['info','evidence','ripple'] as const).map(t => (
                  <button key={t} onClick={() => setSTab(t)} style={{ flex:1,padding:'9px 4px',fontSize:11,fontWeight:600,textTransform:'uppercase',letterSpacing:'0.05em',border:'none',background:'transparent',cursor:'pointer',color:sTab===t?'#60a5fa':muted,borderBottom:sTab===t?'2px solid #3b82f6':'2px solid transparent' }}>{t}</button>
                ))}
              </div>
              <div style={{ padding:16 }}>
                {sTab === 'info' && detail && (
                  <div>
                    {[['Confidence',`${Math.round(detail.match_confidence*100)}%`],['Lineages',`${detail.independent_lineages}`],['Sources',`${detail.source_count}`],detail.area_sqm?['Area',`${Math.round(detail.area_sqm)} m²`]:null,detail.land_use?['Land Use',detail.land_use]:null].filter(Boolean).map(([k,v]) => (
                      <div key={k as string} style={{ display:'flex',justifyContent:'space-between',padding:'7px 0',borderBottom:'1px solid '+border+'40' }}>
                        <span style={{ fontSize:12,color:muted }}>{k}</span>
                        <span style={{ fontSize:12,fontWeight:500,color:text }}>{v}</span>
                      </div>
                    ))}
                    {detail?.proposal && (
                      <div style={{ marginTop:10,padding:10,borderRadius:8,fontSize:12,background:decColor(detail.proposal.decision)+'12',color:decColor(detail.proposal.decision),border:'1px solid '+decColor(detail.proposal.decision)+'30' }}>
                        <div style={{ fontWeight:700,marginBottom:3 }}>{detail.proposal.decision?.replace('_',' ')}</div>
                        <div style={{ opacity:0.8,fontSize:11 }}>{detail.proposal.decision_reason}</div>
                      </div>
                    )}
                  </div>
                )}
                {sTab === 'evidence' && detail?.proposal?.confidence_components && (
                  <div>
                    {Object.entries(detail.proposal.confidence_components).map(([k,v]) => {
                      if (typeof v !== 'number' || v <= 0 || v > 1) return null;
                      const pct = Math.round(v*100);
                      const c = pct>=85?'#22c55e':pct>=65?'#f59e0b':'#ef4444';
                      return (
                        <div key={k} style={{ display:'flex',alignItems:'center',gap:8,marginBottom:8 }}>
                          <span style={{ fontSize:10,color:muted,width:90,flexShrink:0,textTransform:'capitalize' }}>{k.replace(/_/g,' ')}</span>
                          <div style={{ flex:1,height:5,borderRadius:999,background:isDark?'#0c1118':'#e8edf5',overflow:'hidden' }}>
                            <motion.div initial={{ width:0 }} animate={{ width:pct+'%' }} transition={{ duration:0.6 }} style={{ height:'100%',background:c,borderRadius:999 }} />
                          </div>
                          <span style={{ fontSize:10,fontFamily:'monospace',color:c,width:28,textAlign:'right',fontWeight:700 }}>{pct}%</span>
                        </div>
                      );
                    })}
                    <div style={{ fontSize:11,color:muted,marginTop:8 }}>{detail.independent_lineages} independent lineage{detail.independent_lineages!==1?'s':''}</div>
                  </div>
                )}
                {sTab === 'ripple' && detail?.proposal?.ripple_check && (
                  <div>
                    <div style={{ borderRadius:8,padding:10,fontSize:12,marginBottom:10,background:detail.proposal.ripple_check.safe_to_auto_approve?'rgba(34,197,94,0.1)':'rgba(245,158,11,0.1)',color:detail.proposal.ripple_check.safe_to_auto_approve?'#22c55e':'#f59e0b',border:'1px solid '+(detail.proposal.ripple_check.safe_to_auto_approve?'rgba(34,197,94,0.3)':'rgba(245,158,11,0.3)') }}>
                      {detail.proposal.ripple_check.summary}
                    </div>
                    {detail.proposal.ripple_check.issues?.map((issue: any) => (
                      <div key={issue.issue_id} style={{ borderRadius:8,padding:10,marginBottom:6,fontSize:11,background:isDark?'#0c1118':'#f0f4f8',border:'1px solid '+border }}>
                        <div style={{ display:'flex',gap:6,marginBottom:3 }}>
                          <span style={{ fontWeight:700,color:issue.severity==='CRITICAL'?'#ef4444':'#f59e0b',fontSize:10 }}>{issue.severity}</span>
                          <span style={{ color:muted }}>{issue.issue_type.replace(/_/g,' ')}</span>
                        </div>
                        <div style={{ color:muted }}>{issue.description}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Conflicts */}
            {detail?.conflicts?.length > 0 && (
              <div style={{ borderRadius:12,overflow:'hidden',background:bg,border:'1px solid '+border,marginBottom:12 }}>
                <div style={{ padding:'10px 16px',borderBottom:'1px solid '+border,fontSize:10,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.08em',color:muted }}>
                  Conflicts ({detail.conflicts.length})
                </div>
                {detail.conflicts.map((c: any) => (
                  <div key={c.conflict_id} style={{ padding:'10px 16px',borderBottom:'1px solid '+border+'40' }}>
                    <div style={{ display:'flex',alignItems:'center',gap:6,marginBottom:3 }}>
                      <span style={{ fontSize:10,fontWeight:700,color:c.severity==='CRITICAL'?'#ef4444':c.severity==='HIGH'?'#f59e0b':'#a78bfa' }}>● {c.severity}</span>
                      <span style={{ fontSize:12,color:text }}>{c.type.replace(/_/g,' ')}</span>
                      {c.measure!==undefined && <span style={{ marginLeft:'auto',fontSize:10,fontFamily:'monospace',color:muted }}>{c.measure} {c.measure_unit}</span>}
                    </div>
                    <div style={{ fontSize:11,color:muted,lineHeight:1.4 }}>{c.description}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div style={{ display:'flex',gap:8 }}>
              <a href={`/api/v1/cases/${caseId}/parcels/${selected}/export`} download
                style={{ flex:1,display:'flex',alignItems:'center',justifyContent:'center',gap:6,padding:'10px',borderRadius:10,fontSize:12,fontWeight:500,textDecoration:'none',color:muted,background:isDark?'rgba(255,255,255,0.05)':'rgba(0,0,0,0.05)',border:'1px solid '+border }}>
                📦 Evidence ZIP
              </a>
              <a href={`/api/v1/cases/${caseId}/export/geopackage`} download
                style={{ flex:1,display:'flex',alignItems:'center',justifyContent:'center',gap:6,padding:'10px',borderRadius:10,fontSize:12,fontWeight:500,textDecoration:'none',color:muted,background:isDark?'rgba(255,255,255,0.05)':'rgba(0,0,0,0.05)',border:'1px solid '+border }}>
                🗄 GeoPackage
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
