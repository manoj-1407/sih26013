import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Upload, CheckCircle2, XCircle, AlertTriangle, Database, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

const SOURCE_TYPES = [
  'CADASTRAL', 'REVENUE_ROR', 'MUNICIPAL_GIS', 'DRONE_ORI',
  'GNSS_SURVEY', 'BUILDING_FOOTPRINT', 'UTILITY_NETWORK', 'ROAD_NETWORK', 'HISTORICAL',
];
const QUALITY_COLOR: Record<string, string> = {
  HIGH: 'text-green-400', MEDIUM: 'text-amber-400', LOW: 'text-red-400', UNKNOWN: 'text-gray-500',
};

export default function IngestPanel({ caseId }: { caseId: string | null }) {
  const qc = useQueryClient();
  const [sourceType, setSourceType] = useState('CADASTRAL');
  const [label, setLabel] = useState('');
  const [geojson, setGeojson] = useState('');
  const [result, setResult] = useState<any>(null);

  const { data: datasets } = useQuery({
    queryKey: ['datasets', caseId],
    queryFn: () => api.get<{ datasets: any[] }>(`/cases/${caseId}/datasets`),
    enabled: !!caseId,
  });

  const ingestMut = useMutation({
    mutationFn: async () => {
      const parsed = JSON.parse(geojson);
      const features = parsed.type === 'FeatureCollection' ? parsed.features : [parsed];
      return api.post(`/cases/${caseId}/datasets`, { source_type: sourceType, label, features });
    },
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: ['datasets', caseId] });
      qc.invalidateQueries({ queryKey: ['cases'] });
    },
  });

  if (!caseId) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
        <Database size={40} className="opacity-20" />
        <p className="text-sm">Select a case first to ingest data</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Ingest form */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-white">Ingest Source Dataset</h2>

        <div className="glass rounded-2xl p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="section-title">Source Type</label>
              <select className="select-field" value={sourceType} onChange={e => setSourceType(e.target.value)}>
                {SOURCE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="section-title">Label</label>
              <input className="input-field" value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. Cadastral 2019" />
            </div>
          </div>

          <div>
            <label className="section-title">GeoJSON FeatureCollection</label>
            <textarea
              className="input-field font-mono text-xs h-52 resize-none"
              value={geojson}
              onChange={e => setGeojson(e.target.value)}
              placeholder={'{\n  "type": "FeatureCollection",\n  "features": [...]\n}'}
            />
          </div>

          {ingestMut.error && (
            <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 rounded-lg p-3">
              <XCircle size={14} /> {(ingestMut.error as any).message}
            </div>
          )}

          {result && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-xs">
              <div className="text-green-400 font-bold mb-1 flex items-center gap-2">
                <CheckCircle2 size={13} /> Ingested successfully
              </div>
              <div className="text-gray-400">
                <span className="text-white">{result.accepted}</span> accepted ·{' '}
                <span className={QUALITY_COLOR[result.quality_profile?.quality_level ?? 'UNKNOWN']}>
                  {result.quality_profile?.quality_level} quality
                </span>
                {result.rejected?.length > 0 && (
                  <span className="text-red-400"> · {result.rejected.length} rejected</span>
                )}
              </div>
              {result.quality_profile?.warnings?.map((w: string, i: number) => (
                <div key={i} className="text-amber-500 mt-1 flex items-start gap-1">
                  <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />{w}
                </div>
              ))}
            </div>
          )}

          <button
            className="btn-primary w-full justify-center"
            disabled={!geojson || ingestMut.isPending}
            onClick={() => ingestMut.mutate()}
          >
            {ingestMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            {ingestMut.isPending ? 'Ingesting…' : 'Ingest Dataset'}
          </button>
        </div>
      </div>

      {/* Dataset list */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-white">
          Ingested Datasets ({datasets?.datasets?.length ?? 0})
        </h2>
        {datasets?.datasets?.map((d, i) => (
          <motion.div
            key={d.dataset_id}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className="glass rounded-xl p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-gray-500 truncate">{d.dataset_id}</span>
              <span className={`text-xs font-bold ${QUALITY_COLOR[d.quality_level]}`}>{d.quality_level}</span>
            </div>
            <div className="text-sm font-medium text-white mb-2">{d.label || d.source_type}</div>
            <div className="flex items-center gap-3 text-xs text-gray-600">
              <span>{d.valid_features} / {d.total_features} valid</span>
              <div className="flex-1 bg-dark-600 rounded-full h-1 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${d.quality_level === 'HIGH' ? 'bg-green-500' : d.quality_level === 'MEDIUM' ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${(d.valid_features / Math.max(1, d.total_features)) * 100}%` }}
                />
              </div>
            </div>
          </motion.div>
        ))}
        {!datasets?.datasets?.length && (
          <div className="text-center py-10 text-gray-600 text-sm">No datasets ingested yet</div>
        )}
      </div>
    </div>
  );
}
