import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }

const SOURCE_TYPES = ['CADASTRAL','REVENUE_ROR','MUNICIPAL_GIS','DRONE_ORI','GNSS_SURVEY','BUILDING_FOOTPRINT','UTILITY_NETWORK','ROAD_NETWORK','HISTORICAL'];
const QL_COLOR: Record<string, string> = { HIGH: '#22c55e', MEDIUM: '#f59e0b', LOW: '#ef4444', UNKNOWN: '#6b7280' };

export default function IngestPanel({ caseId, isDark }: Props) {
  const qc = useQueryClient();
  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';
  const inputBg = isDark ? '#060d18' : '#f8fafc';

  const [sourceType, setSourceType] = useState('CADASTRAL');
  const [label, setLabel] = useState('');
  const [geojsonText, setGeojsonText] = useState('');
  const [result, setResult] = useState<any>(null);
  const [parseErr, setParseErr] = useState('');

  const { data: datasets } = useQuery({
    queryKey: ['datasets', caseId],
    queryFn: () => api.get<{ datasets: any[] }>(`/cases/${caseId}/datasets`),
    enabled: !!caseId,
  });

  const mut = useMutation({
    mutationFn: async () => {
      let parsed: any;
      try { parsed = JSON.parse(geojsonText); } catch { throw new Error('Invalid JSON — paste a valid GeoJSON FeatureCollection'); }
      const features = parsed.type === 'FeatureCollection' ? parsed.features : Array.isArray(parsed) ? parsed : [parsed];
      return api.post(`/cases/${caseId}/datasets`, { source_type: sourceType, label, features });
    },
    onSuccess: (r: any) => {
      setResult(r);
      setParseErr('');
      qc.invalidateQueries({ queryKey: ['datasets', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
    onError: (e: any) => setParseErr(e.message),
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">📥</div>
      <div className="text-sm">Select a case first to ingest data</div>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Form */}
      <div className="space-y-4">
        <h2 className="text-base font-bold" style={{ color: text }}>Ingest Source Dataset</h2>
        <div className="rounded-2xl p-5 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: muted }}>Source Type</label>
              <select value={sourceType} onChange={e => setSourceType(e.target.value)}
                className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
                style={{ background: inputBg, borderColor: border, color: text }}>
                {SOURCE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: muted }}>Label</label>
              <input value={label} onChange={e => setLabel(e.target.value)}
                placeholder="e.g. Cadastral 2024"
                className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
                style={{ background: inputBg, borderColor: border, color: text }} />
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: muted }}>GeoJSON FeatureCollection</label>
            <textarea
              value={geojsonText} onChange={e => setGeojsonText(e.target.value)}
              placeholder={'{\n  "type": "FeatureCollection",\n  "features": [...]\n}'}
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none resize-none font-mono"
              style={{ background: inputBg, borderColor: border, color: text, height: 180, fontSize: 11 }}
            />
          </div>

          {(parseErr || mut.error) && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              ✗ {parseErr || (mut.error as any)?.message}
            </div>
          )}

          {result && (
            <div className="text-xs bg-green-500/10 border border-green-500/20 rounded-lg p-3 space-y-1">
              <div className="text-green-400 font-bold">✓ Ingested: {result.accepted} accepted</div>
              {result.quality_profile && (
                <div style={{ color: QL_COLOR[result.quality_profile.quality_level] ?? '#6b7280' }}>
                  Quality: {result.quality_profile.quality_level} ({result.quality_profile.quality_score?.toFixed(1)}%)
                </div>
              )}
              {result.rejected?.length > 0 && <div className="text-red-400">{result.rejected.length} records rejected</div>}
              {result.quality_profile?.warnings?.map((w: string, i: number) => (
                <div key={i} className="text-amber-400">⚠ {w}</div>
              ))}
            </div>
          )}

          <button disabled={!geojsonText.trim() || mut.isPending} onClick={() => mut.mutate()}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-all">
            {mut.isPending ? '⏳ Ingesting…' : '📥 Ingest Dataset'}
          </button>
        </div>
      </div>

      {/* Dataset list */}
      <div className="space-y-4">
        <h2 className="text-base font-bold" style={{ color: text }}>Ingested Datasets ({datasets?.datasets?.length ?? 0})</h2>
        {datasets?.datasets?.map((d: any, i: number) => {
          const validity = d.validity_rate ?? (d.total_features > 0 ? (d.valid_features / d.total_features) * 100 : 0);
          return (
            <motion.div key={d.dataset_id} initial={{ opacity: 0, x: 15 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
              className="rounded-xl p-4" style={{ background: bg, border: `1px solid ${border}` }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono truncate max-w-[55%]" style={{ color: muted }}>{d.dataset_id}</span>
                <span className="text-xs font-bold" style={{ color: QL_COLOR[d.quality_level] }}>{d.quality_level}</span>
              </div>
              <div className="text-sm font-medium mb-2.5 truncate" style={{ color: text }}>{d.label || d.source_type}</div>
              <div className="flex items-center gap-2.5">
                <div className="flex-1 rounded-full overflow-hidden" style={{ background: isDark ? '#0c1118' : '#e8edf5', height: 6 }}>
                  <motion.div initial={{ width: 0 }} animate={{ width: `${validity}%` }} transition={{ duration: 0.7 }}
                    className="h-full rounded-full" style={{ background: QL_COLOR[d.quality_level] }} />
                </div>
                <span className="text-[11px] font-mono w-10 text-right" style={{ color: muted }}>{validity.toFixed(0)}%</span>
                <span className="text-[11px]" style={{ color: muted }}>{d.valid_features}/{d.total_features}</span>
              </div>
            </motion.div>
          );
        })}
        {!datasets?.datasets?.length && (
          <div className="text-center py-10 text-sm" style={{ color: muted }}>No datasets ingested yet</div>
        )}
      </div>
    </div>
  );
}
