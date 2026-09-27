import React, { useEffect, useRef, useState } from 'react';

declare const maplibregl: any;

interface Props {
  caseId: string | null;
  parcelId: string | null;
  beforeFeatures?: GeoJSON.FeatureCollection;
  afterFeatures?: GeoJSON.FeatureCollection;
}

/**
 * Before/After slider map comparison.
 * LEFT = source records (original, immutable).
 * RIGHT = harmonization proposal (minimum-change reconciliation).
 *
 * Dragging the divider reveals how much the proposed change moves boundaries.
 * This directly answers "what changed and by how much?" — a key evaluation moment.
 */
export default function BeforeAfterMap({ caseId, parcelId, beforeFeatures, afterFeatures }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const beforeMapRef = useRef<HTMLDivElement>(null);
  const afterMapRef = useRef<HTMLDivElement>(null);
  const sliderRef = useRef<HTMLDivElement>(null);
  const beforeMap = useRef<any>(null);
  const afterMap = useRef<any>(null);
  const isDragging = useRef(false);
  const [sliderPct, setSliderPct] = useState(50);
  const [ready, setReady] = useState(false);
  const [noMapLib, setNoMapLib] = useState(false);

  const SOURCE_COLORS: Record<string, string> = {
    CADASTRAL: '#3b82f6',
    REVENUE_ROR: '#10b981',
    MUNICIPAL_GIS: '#f59e0b',
    DRONE_ORI: '#06b6d4',
    BUILDING_FOOTPRINT: '#ef4444',
    DEFAULT: '#8b5cf6',
  };

  useEffect(() => {
    if (typeof maplibregl === 'undefined') {
      setNoMapLib(true);
      return;
    }
    if (!beforeMapRef.current || !afterMapRef.current) return;
    if (beforeMap.current) return;

    const styleSpec = {
      version: 8 as const,
      sources: {
        osm: { type: 'raster' as const, tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256 },
      },
      layers: [{ id: 'osm', type: 'raster' as const, source: 'osm' }],
    };

    const center: [number, number] = [78.9629, 20.5937];
    const zoom = 4;

    const bMap = new maplibregl.Map({
      container: beforeMapRef.current,
      style: styleSpec,
      center,
      zoom,
      interactive: true,
    });
    const aMap = new maplibregl.Map({
      container: afterMapRef.current,
      style: styleSpec,
      center,
      zoom,
      interactive: false, // synced to before
    });

    // Sync after to before
    bMap.on('move', () => {
      if (!aMap) return;
      aMap.setCenter(bMap.getCenter());
      aMap.setZoom(bMap.getZoom());
      aMap.setBearing(bMap.getBearing());
      aMap.setPitch(bMap.getPitch());
    });

    bMap.addControl(new maplibregl.NavigationControl(), 'top-left');

    bMap.on('load', () => {
      beforeMap.current = bMap;
      setReady(true);
    });
    aMap.on('load', () => {
      afterMap.current = aMap;
    });
  }, []);

  // Add features to maps
  useEffect(() => {
    const bMap = beforeMap.current;
    const aMap = afterMap.current;
    if (!ready || !bMap) return;

    // Clean up old layers
    ['gs-before-fill', 'gs-before-line'].forEach(id => {
      if (bMap.getLayer(id)) bMap.removeLayer(id);
    });
    if (bMap.getSource('gs-before')) bMap.removeSource('gs-before');

    ['gs-after-fill', 'gs-after-line'].forEach(id => {
      if (aMap?.getLayer(id)) aMap.removeLayer(id);
    });
    if (aMap?.getSource('gs-after')) aMap.removeSource('gs-after');

    if (beforeFeatures?.features?.length) {
      bMap.addSource('gs-before', { type: 'geojson', data: beforeFeatures });
      bMap.addLayer({ id: 'gs-before-fill', type: 'fill', source: 'gs-before',
        paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.25 } });
      bMap.addLayer({ id: 'gs-before-line', type: 'line', source: 'gs-before',
        paint: { 'line-color': '#3b82f6', 'line-width': 2 } });

      // Fit bounds
      const coords = beforeFeatures.features.flatMap(f => {
        if (f.geometry?.type === 'Polygon') return f.geometry.coordinates[0] as [number,number][];
        return [];
      });
      if (coords.length) {
        const lons = coords.map(c => c[0]);
        const lats = coords.map(c => c[1]);
        bMap.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 60 });
      }
    }

    if (afterFeatures?.features?.length && aMap) {
      aMap.addSource('gs-after', { type: 'geojson', data: afterFeatures });
      aMap.addLayer({ id: 'gs-after-fill', type: 'fill', source: 'gs-after',
        paint: { 'fill-color': '#22c55e', 'fill-opacity': 0.25 } });
      aMap.addLayer({ id: 'gs-after-line', type: 'line', source: 'gs-after',
        paint: { 'line-color': '#22c55e', 'line-width': 2.5 } });
    }
  }, [ready, beforeFeatures, afterFeatures]);

  // Slider drag
  const onMouseDown = (e: React.MouseEvent) => {
    isDragging.current = true;
    e.preventDefault();
  };
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = Math.min(95, Math.max(5, ((e.clientX - rect.left) / rect.width) * 100));
      setSliderPct(pct);
    };
    const onUp = () => { isDragging.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  if (noMapLib) {
    return (
      <div className="notice notice-amber">
        MapLibre GL JS not loaded. Add CDN script to index.html for map visualization.
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', userSelect: 'none' }}>
      {/* Labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span className="badge badge-info">◀ BEFORE — Source Records</span>
        <span className="badge badge-ok">AFTER — Harmonization Proposal ▶</span>
      </div>

      <div
        ref={containerRef}
        style={{ position: 'relative', height: 380, borderRadius: 8, overflow: 'hidden',
                 border: '1px solid var(--border)' }}
      >
        {/* Before map (full width, clipped by slider) */}
        <div
          ref={beforeMapRef}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
        />

        {/* After map (right side, revealed by slider) */}
        <div
          style={{
            position: 'absolute', top: 0, bottom: 0,
            left: `${sliderPct}%`, right: 0,
            overflow: 'hidden',
          }}
        >
          <div
            ref={afterMapRef}
            style={{
              position: 'absolute', top: 0, bottom: 0,
              right: 0,
              width: containerRef.current?.offsetWidth ?? 600,
              marginLeft: `${-sliderPct}%`,
            }}
          />
        </div>

        {/* Slider divider */}
        <div
          ref={sliderRef}
          onMouseDown={onMouseDown}
          style={{
            position: 'absolute', top: 0, bottom: 0,
            left: `calc(${sliderPct}% - 2px)`,
            width: 4,
            background: 'white',
            cursor: 'ew-resize',
            zIndex: 10,
            boxShadow: '0 0 0 1px rgba(0,0,0,0.3)',
          }}
        >
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 28, height: 28, borderRadius: '50%',
            background: 'white', border: '2px solid var(--accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, color: 'var(--accent)', fontWeight: 700,
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          }}>⟺</div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6, textAlign: 'center' }}>
        Drag the slider to compare original source geometries with the harmonization proposal.
        Original data is never overwritten.
      </div>
    </div>
  );
}
