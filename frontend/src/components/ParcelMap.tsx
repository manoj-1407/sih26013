import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, Parcel } from '../api/client';
import ConfidenceExplainer from './ConfidenceExplainer';
import BeforeAfterMap from './BeforeAfterMap';
import ULPINPanel from './ULPINPanel';
import HarmonizationDiff from './HarmonizationDiff';

declare const maplibregl: any;

// ── Moved outside export default to avoid build error ────────────────────────
function BeforeAfterSourceMap({
  caseId,
  parcelId,
  proposedGeometry,
}: {
  caseId: string | null;
  parcelId: string;
  proposedGeometry?: GeoJSON.Geometry;
}) {
  const { data: sourcesData } = useQuery({
    queryKey: ['parcel-sources', caseId, parcelId],
    queryFn: () =>
      api.get<{ type: string; features: any[] }>(
        `/cases/${caseId}/parcels/${parcelId}/sources`
      ),
    enabled: !!caseId,
  });

  const beforeFeatures = sourcesData
    ? { type: 'FeatureCollection' as const, features: sourcesData.features }
    : undefined;

  const afterFeatures = proposedGeometry
    ? {
        type: 'FeatureCollection' as const,
        features: [
          {
            type: 'Feature' as const,
            geometry: proposedGeometry,
            properties: { label: 'Harmonization Proposal', color: '#22c55e' },
          },
        ],
      }
    : undefined;

  return (
    <BeforeAfterMap
      caseId={caseId}
      parcelId={parcelId}
      beforeFeatures={beforeFeatures}
      afterFeatures={afterFeatures}
    />
  );
}
// ─────────────────────────────────────────────────────────────────────────────

export default function ParcelMap({ caseId }: { caseId: string | null }) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);
  const [selectedParcel, setSelectedParcel] = useState<Parcel | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [activeTab, setActiveTab] = useState<'map' | 'evidence' | 'diff' | 'compare' | 'ulpin'>('map');

  const parcelsQuery = useQuery({
    queryKey: ['parcels', caseId],
    queryFn: () => api.get<{ parcels: Parcel[] }>(`/cases/${caseId}/parcels`),
    enabled: !!caseId,
  });

  const parcelDetailQuery = useQuery({
    queryKey: ['parcel-detail', caseId, selectedParcel?.canonical_id],
    queryFn: () =>
      api.get<Parcel>(`/cases/${caseId}/parcels/${selectedParcel!.canonical_id}`),
    enabled: !!caseId && !!selectedParcel,
  });

  useEffect(() => {
    if (!mapRef.current || typeof maplibregl === 'undefined') return;
    if (mapInstance.current) return;
    const map = new maplibregl.Map({
      container: mapRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: [78.9629, 20.5937],
      zoom: 4,
    });
    map.addControl(new maplibregl.NavigationControl());
    map.on('load', () => {
      mapInstance.current = map;
      setMapReady(true);
    });
  }, []);

  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !mapReady || !parcelsQuery.data?.parcels) return;
    ['gs-parcels-fill', 'gs-parcels-outline'].forEach(id => {
      if (map.getLayer(id)) map.removeLayer(id);
    });
    if (map.getSource('gs-parcels')) map.removeSource('gs-parcels');

    const features = parcelsQuery.data.parcels
      .filter(p => p.geometry)
      .map(p => ({
        type: 'Feature' as const,
        id: p.canonical_id,
        geometry: p.geometry!,
        properties: {
          canonical_id: p.canonical_id,
          conflict_count: p.conflict_count,
          match_confidence: p.match_confidence,
        },
      }));
    if (!features.length) return;

    map.addSource('gs-parcels', { type: 'geojson', data: { type: 'FeatureCollection', features } });
    map.addLayer({
      id: 'gs-parcels-fill', type: 'fill', source: 'gs-parcels',
      paint: {
        'fill-color': ['case',
          ['>', ['get', 'conflict_count'], 2], '#ef444440',
          ['>', ['get', 'conflict_count'], 0], '#f59e0b30',
          '#3b82f620'],
        'fill-opacity': 0.6,
      },
    });
    map.addLayer({
      id: 'gs-parcels-outline', type: 'line', source: 'gs-parcels',
      paint: {
        'line-color': ['case',
          ['>', ['get', 'conflict_count'], 2], '#ef4444',
          ['>', ['get', 'conflict_count'], 0], '#f59e0b',
          '#3b82f6'],
        'line-width': 2,
      },
    });
    map.on('click', 'gs-parcels-fill', (e: any) => {
      const props = e.features?.[0]?.properties;
      if (props?.canonical_id) {
        const parcel = parcelsQuery.data!.parcels.find(p => p.canonical_id === props.canonical_id);
        if (parcel) setSelectedParcel(parcel);
      }
    });
    map.on('mouseenter', 'gs-parcels-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'gs-parcels-fill', () => { map.getCanvas().style.cursor = ''; });

    const coords = features.flatMap(f => {
      if (f.geometry.type === 'Polygon') return f.geometry.coordinates[0] as [number, number][];
      return [];
    });
    if (coords.length) {
      const lons = coords.map(c => c[0]);
      const lats = coords.map(c => c[1]);
      map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 40 });
    }
  }, [mapReady, parcelsQuery.data]);

  const detail = parcelDetailQuery.data;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 12, height: 'calc(100vh - 80px)' }}>
      {/* Map */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="card-header">
          🗺 Parcel Map
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text3)' }}>Click a parcel</span>
        </div>
        <div style={{ height: 'calc(100% - 38px)', position: 'relative' }}>
          {typeof maplibregl === 'undefined' && (
            <div className="notice notice-amber" style={{ margin: 12 }}>
              MapLibre GL not loaded — add CDN script to index.html
            </div>
          )}
          <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
        </div>
      </div>

      {/* Side panel */}
      <div className="flex-col gap-2" style={{ overflow: 'auto' }}>
        {!selectedParcel && (
          <div className="card">
            <div className="card-header">Parcels ({parcelsQuery.data?.parcels?.length ?? 0})</div>
            <div className="card-body">
              {parcelsQuery.data?.parcels?.map(p => (
                <div key={p.canonical_id} onClick={() => setSelectedParcel(p)}
                  style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--cyan)', flex: 1 }}>{p.canonical_id}</span>
                  {p.conflict_count > 0 && <span className="badge badge-err">{p.conflict_count}</span>}
                  <span style={{ fontSize: 11, color: 'var(--text3)' }}>{Math.round(p.match_confidence * 100)}%</span>
                </div>
              ))}
              {!parcelsQuery.data?.parcels?.length && (
                <div className="empty-state" style={{ padding: 20 }}>Run harmonization first</div>
              )}
            </div>
          </div>
        )}

        {selectedParcel && (
          <div className="card">
            <div className="card-header">
              <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontSize: 11 }}>{selectedParcel.canonical_id}</span>
              <button className="btn btn-ghost btn-sm ml-auto" onClick={() => setSelectedParcel(null)}>✕</button>
            </div>
            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 14px' }}>
              {(['map', 'evidence', 'diff', 'compare', 'ulpin'] as const).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '6px 8px',
                  fontSize: 10, fontWeight: 600,
                  color: activeTab === tab ? 'var(--accent)' : 'var(--text3)',
                  borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
                  textTransform: 'uppercase', letterSpacing: '0.04em',
                }}>
                  {tab === 'map' ? '📍' : tab === 'evidence' ? '📊' : tab === 'diff' ? '📋' : tab === 'compare' ? '🔄' : '🆔'}
                  {' '}{tab}
                </button>
              ))}
            </div>
            <div className="card-body" style={{ overflow: 'auto', maxHeight: 'calc(100vh - 250px)' }}>
              {activeTab === 'map' && (
                <div className="flex-col gap-2">
                  <div className="kv">
                    <span className="kv-k">Confidence</span>
                    <span className="kv-v" style={{ fontWeight: 700 }}>{Math.round(selectedParcel.match_confidence * 100)}%</span>
                    <span className="kv-k">Lineages</span>
                    <span className="kv-v">{selectedParcel.independent_lineages}</span>
                    <span className="kv-k">Sources</span>
                    <span className="kv-v">{selectedParcel.source_count}</span>
                    {detail?.area_sqm && <><span className="kv-k">Area</span><span className="kv-v">{Math.round(detail.area_sqm)} m²</span></>}
                    {detail?.ulpin && <><span className="kv-k">ULPIN</span><span className="kv-v mono" style={{ fontSize: 10 }}>{detail.ulpin}</span></>}
                  </div>
                  {(detail?.conflicts ?? []).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {detail!.conflicts!.map(c => (
                        <div key={c.conflict_id} className="conflict-card">
                          <div className="conflict-title flex items-center gap-2">
                            <span className={`severity-${c.severity}`}>●</span>
                            <span style={{ fontSize: 11 }}>{c.type.replace(/_/g, ' ')}</span>
                            <span className="ml-auto" style={{ fontSize: 10, color: 'var(--text3)' }}>{c.severity}</span>
                          </div>
                          <div className="conflict-desc">{c.description}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {detail?.proposal && (
                    <div className={`notice ${detail.proposal.decision === 'AUTO_APPROVED' ? 'notice-green' : 'notice-amber'}`} style={{ fontSize: 11, marginTop: 8 }}>
                      {detail.proposal.decision?.replace('_', ' ')}: {detail.proposal.decision_reason}
                    </div>
                  )}
                  <div className="flex gap-2 mt-2">
                    <a href={`/api/v1/cases/${caseId}/parcels/${selectedParcel.canonical_id}/export`} download className="btn btn-ghost btn-sm" style={{ display: 'inline-flex' }}>📦 ZIP</a>
                    <a href={`/api/v1/cases/${caseId}/export/geopackage`} download className="btn btn-ghost btn-sm" style={{ display: 'inline-flex' }}>🗄 GPKG</a>
                  </div>
                </div>
              )}
              {activeTab === 'evidence' && detail && <ConfidenceExplainer parcel={detail} />}
              {activeTab === 'diff' && detail && <HarmonizationDiff parcel={detail} />}
              {activeTab === 'compare' && (
                <BeforeAfterSourceMap
                  caseId={caseId}
                  parcelId={selectedParcel.canonical_id}
                  proposedGeometry={detail?.proposal?.proposed_geometry}
                />
              )}
              {activeTab === 'ulpin' && (
                <ULPINPanel caseId={caseId!} parcelId={selectedParcel.canonical_id} existingUlpin={detail?.ulpin} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
