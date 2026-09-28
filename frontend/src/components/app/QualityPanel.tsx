import React from 'react';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }
const QL: Record<string, string> = { HIGH: '#22c55e', MEDIUM: '#f59e0b', LOW: '#ef4444', UNKNOWN: '#6b7280' };

// Clean CSS arc gauge — no chart library needed, no broken overlap
function ArcGauge({ value, color }: { value: number; color: string }) {
  const pct = Math.min(100, Math.max(0, value));
  // SVG arc: 180° semicircle
  const r = 38;
  const cx = 50;
  const cy = 52;
  const startAngle = Math.PI;
  const endAngle = 0;
  const arcLength = Math.PI; // 180°
  const angle = Math.PI - (pct / 100) * arcLength;
  const ex = cx + r * Math.cos(angle);
  const ey = cy - r * Math.sin(angle);
  const largeArc = pct > 50 ? 1 : 0;

  return (
    <div style={{ position: 'relative', width: '100%', paddingBottom: '60%' }}>
      <svg viewBox="0 0 100 60" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        {/* Background track */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke="#1a2535" strokeWidth="8" strokeLinecap="round"
        />
        {/* Value arc */}
        {pct > 0 && (
          <path
            d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`}
            fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          />
        )}
        {/* Value text */}
        <text x="50" y="48" textAnchor="middle" fontSize="14" fontWeight="900"
          fill={color} fontFamily="JetBrains Mono, monospace">
          {pct.toFixed(1)}%
        </text>
      </svg>
    </div>
  );
}

export default function QualityPanel({ caseId, isDark }: Props) {
  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';
  const barBg  = isDark ? '#0c1118' : '#e8edf5';

  const { data, isLoading, error, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['quality', caseId],
    queryFn: () => api.get<any>(`/cases/${caseId}/quality-report`),
    enabled: !!caseId,
    retry: false,
    refetchInterval: 30_000,
  });

  if (!caseId) return (
    <div style={{ display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:256,color:muted }}>
      <div style={{ fontSize:48,marginBottom:12 }}>📊</div>
      <div style={{ fontSize:14 }}>Select a case first</div>
    </div>
  );
  if (isLoading) return <div style={{ textAlign:'center',padding:'80px 0',color:muted }}>Loading quality report…</div>;
  if (error || !data) return (
    <div style={{ display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:256,color:muted }}>
      <div style={{ fontSize:48,marginBottom:12 }}>📊</div>
      <div style={{ fontSize:14 }}>No datasets ingested yet</div>
      <button onClick={() => refetch()} style={{ marginTop:12,background:'#1e2d42',border:'1px solid #243045',color:muted,padding:'6px 14px',borderRadius:8,cursor:'pointer',fontSize:12 }}>
        ↺ Retry
      </button>
    </div>
  );

  const { summary, datasets, source_manifest_hash } = data;
  const gaugeColor = summary.overall_validity_rate >= 90 ? '#22c55e' : summary.overall_validity_rate >= 70 ? '#f59e0b' : '#ef4444';
  const lastUpdate = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '—';

  return (
    <div style={{ maxWidth:960,margin:'0 auto' }}>
      {/* Header with refresh */}
      <div style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20 }}>
        <h2 style={{ fontSize:16,fontWeight:700,color:text }}>Data Quality Report</h2>
        <div style={{ display:'flex',alignItems:'center',gap:12 }}>
          <span style={{ fontSize:11,color:muted }}>Updated {lastUpdate}</span>
          <button onClick={() => refetch()}
            style={{ background:'rgba(255,255,255,0.06)',border:'1px solid #1e2d42',color:muted,padding:'5px 12px',borderRadius:8,cursor:'pointer',fontSize:12 }}>
            ↺ Refresh
          </button>
        </div>
      </div>

      {/* Summary grid */}
      <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:14,marginBottom:20 }}>
        {[
          { l: 'Datasets', v: summary.datasets, c: '#3b82f6' },
          { l: 'Total Records', v: summary.total_records, c: text },
          { l: 'Valid Records', v: summary.total_valid, c: '#22c55e' },
        ].map(({ l, v, c }) => (
          <motion.div key={l} initial={{ opacity:0,scale:0.9 }} animate={{ opacity:1,scale:1 }}
            style={{ borderRadius:12,padding:20,textAlign:'center',background:bg,border:'1px solid '+border }}>
            <div style={{ fontSize:32,fontWeight:900,marginBottom:4,color:c }}>{v}</div>
            <div style={{ fontSize:10,textTransform:'uppercase',letterSpacing:'0.08em',color:muted }}>{l}</div>
          </motion.div>
        ))}
        <motion.div initial={{ opacity:0,scale:0.9 }} animate={{ opacity:1,scale:1 }}
          style={{ borderRadius:12,padding:16,background:bg,border:'1px solid '+border }}>
          <div style={{ fontSize:10,textTransform:'uppercase',letterSpacing:'0.08em',color:muted,marginBottom:8 }}>Overall Validity</div>
          <ArcGauge value={summary.overall_validity_rate} color={gaugeColor} />
        </motion.div>
      </div>

      {/* Per-dataset */}
      <div style={{ borderRadius:16,overflow:'hidden',background:bg,border:'1px solid '+border,marginBottom:16 }}>
        <div style={{ padding:'12px 20px',borderBottom:'1px solid '+border,fontSize:10,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.08em',color:muted }}>
          Per-Dataset Quality Profiles
        </div>
        {datasets?.map((d: any, i: number) => {
          const validity = d.validity_rate ?? (d.total_features > 0 ? (d.valid_features / d.total_features) * 100 : 0);
          const color = QL[d.quality_level] ?? '#6b7280';
          return (
            <motion.div key={d.dataset_id} initial={{ opacity:0,x:-8 }} animate={{ opacity:1,x:0 }} transition={{ delay:i*0.05 }}
              style={{ padding:'16px 20px',borderBottom:'1px solid '+border+'50' }}>
              <div style={{ display:'flex',alignItems:'flex-start',justifyContent:'space-between',marginBottom:10 }}>
                <div>
                  <div style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
                    <span style={{ fontSize:10,fontFamily:'monospace',padding:'2px 6px',borderRadius:4,background:isDark?'#0c1118':'#f0f4f8',color:muted }}>{d.source_type}</span>
                    <span style={{ fontSize:12,fontWeight:700,color }}>{d.quality_level}</span>
                    {d.quality_score !== undefined && <span style={{ fontSize:11,color:muted }}>{d.quality_score.toFixed(1)}%</span>}
                  </div>
                  <div style={{ fontSize:14,fontWeight:500,color:text }}>{d.label || d.source_type}</div>
                </div>
                <div style={{ textAlign:'right',fontSize:12,color:muted }}>
                  <span style={{ color:text,fontWeight:700,fontFamily:'monospace' }}>{d.valid_features}</span> / {d.total_features}
                </div>
              </div>
              <div style={{ display:'flex',alignItems:'center',gap:12 }}>
                <div style={{ flex:1,borderRadius:999,overflow:'hidden',background:barBg,height:6 }}>
                  <motion.div initial={{ width:0 }} animate={{ width:validity+'%' }} transition={{ duration:0.7,delay:i*0.05 }}
                    style={{ height:'100%',borderRadius:999,background:color }} />
                </div>
                <span style={{ fontSize:11,fontFamily:'monospace',width:36,textAlign:'right',color:muted }}>{validity.toFixed(0)}%</span>
              </div>
              {d.warnings?.map((w: string, wi: number) => (
                <div key={wi} style={{ marginTop:6,display:'flex',alignItems:'flex-start',gap:6,fontSize:11,color:'#f59e0b' }}>
                  <span style={{ flexShrink:0 }}>⚠</span>{w}
                </div>
              ))}
            </motion.div>
          );
        })}
      </div>

      {/* Manifest hash */}
      <div style={{ borderRadius:12,padding:16,background:bg,border:'1px solid '+border }}>
        <div style={{ fontSize:10,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.08em',color:muted,marginBottom:8 }}>
          Source Manifest SHA-256 (Tamper Detection)
        </div>
        <div style={{ fontFamily:'monospace',fontSize:11,borderRadius:8,padding:10,wordBreak:'break-all',color:muted,background:isDark?'#0c1118':'#f0f4f8' }}>
          {source_manifest_hash}
        </div>
        <div style={{ fontSize:10,color:muted,marginTop:8,opacity:0.6 }}>
          Changes if any source record is modified. Compare against your last known-good hash to detect tampering.
        </div>
      </div>
    </div>
  );
}
