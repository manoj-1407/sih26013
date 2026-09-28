import React from 'react';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { RadialBarChart, RadialBar, Cell, ResponsiveContainer } from 'recharts';
import { api } from '../../api/client';

interface Props { caseId: string | null; isDark: boolean; }
const QL: Record<string, string> = { HIGH: '#22c55e', MEDIUM: '#f59e0b', LOW: '#ef4444', UNKNOWN: '#6b7280' };

export default function QualityPanel({ caseId, isDark }: Props) {
  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';
  const barBg  = isDark ? '#0c1118' : '#e8edf5';

  const { data, isLoading, error } = useQuery({
    queryKey: ['quality', caseId],
    queryFn: () => api.get<any>(`/cases/${caseId}/quality-report`),
    enabled: !!caseId,
    retry: false,
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">📊</div>
      <div className="text-sm">Select a case first</div>
    </div>
  );
  if (isLoading) return <div className="text-center py-20" style={{ color: muted }}>Loading quality report…</div>;
  if (error || !data) return (
    <div className="flex flex-col items-center justify-center h-64" style={{ color: muted }}>
      <div className="text-5xl mb-3">📊</div>
      <div className="text-sm">No datasets ingested yet for this case</div>
    </div>
  );

  const { summary, datasets, source_manifest_hash } = data;
  const gaugeColor = summary.overall_validity_rate >= 90 ? '#22c55e' : summary.overall_validity_rate >= 70 ? '#f59e0b' : '#ef4444';

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <h2 className="text-base font-bold" style={{ color: text }}>Data Quality Report</h2>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { l: 'Datasets', v: summary.datasets, c: '#3b82f6' },
          { l: 'Total Records', v: summary.total_records, c: text },
          { l: 'Valid Records', v: summary.total_valid, c: '#22c55e' },
        ].map(({ l, v, c }) => (
          <motion.div key={l} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
            className="rounded-xl p-5 text-center" style={{ background: bg, border: `1px solid ${border}` }}>
            <div className="text-3xl font-black mb-1" style={{ color: c }}>{v}</div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: muted }}>{l}</div>
          </motion.div>
        ))}
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl p-4" style={{ background: bg, border: `1px solid ${border}` }}>
          <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: muted }}>Overall Validity</div>
          <div style={{ height: 80 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart cx="50%" cy="100%" innerRadius="55%" outerRadius="90%" startAngle={180} endAngle={0}
                data={[{ value: summary.overall_validity_rate }]}>
                <RadialBar dataKey="value" cornerRadius={4} background={{ fill: barBg }}>
                  <Cell fill={gaugeColor} />
                </RadialBar>
              </RadialBarChart>
            </ResponsiveContainer>
          </div>
          <div className="text-center -mt-4">
            <span className="text-xl font-black" style={{ color: gaugeColor }}>{summary.overall_validity_rate.toFixed(1)}%</span>
          </div>
        </motion.div>
      </div>

      {/* Datasets */}
      <div className="rounded-2xl overflow-hidden" style={{ background: bg, border: `1px solid ${border}` }}>
        <div className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest" style={{ borderBottom: `1px solid ${border}`, color: muted }}>
          Per-Dataset Quality
        </div>
        <div>
          {datasets?.map((d: any, i: number) => {
            const validity = d.validity_rate ?? (d.total_features > 0 ? (d.valid_features / d.total_features) * 100 : 0);
            const color = QL[d.quality_level] ?? '#6b7280';
            return (
              <motion.div key={d.dataset_id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                className="px-5 py-4" style={{ borderBottom: `1px solid ${border}50` }}>
                <div className="flex items-start justify-between mb-2.5">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: isDark ? '#0c1118' : '#f0f4f8', color: muted }}>{d.source_type}</span>
                      <span className="text-xs font-bold" style={{ color }}>{d.quality_level}</span>
                      {d.quality_score !== undefined && <span className="text-[11px]" style={{ color: muted }}>{d.quality_score.toFixed(1)}%</span>}
                    </div>
                    <div className="text-sm font-medium" style={{ color: text }}>{d.label || d.source_type}</div>
                  </div>
                  <div className="text-right text-xs" style={{ color: muted }}>
                    <span style={{ color: text, fontWeight: 700 }}>{d.valid_features}</span> / {d.total_features}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 rounded-full overflow-hidden" style={{ background: barBg, height: 6 }}>
                    <motion.div initial={{ width: 0 }} animate={{ width: `${validity}%` }} transition={{ duration: 0.7, delay: i * 0.05 }}
                      className="h-full rounded-full" style={{ background: color }} />
                  </div>
                  <span className="text-[11px] font-mono w-10 text-right" style={{ color: muted }}>{validity.toFixed(0)}%</span>
                </div>
                {d.warnings?.map((w: string, wi: number) => (
                  <div key={wi} className="mt-1.5 flex items-start gap-1.5 text-[11px] text-amber-400">
                    <span className="flex-shrink-0">⚠</span>{w}
                  </div>
                ))}
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Manifest hash */}
      <div className="rounded-xl p-4" style={{ background: bg, border: `1px solid ${border}` }}>
        <div className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: muted }}>Source Manifest SHA-256</div>
        <div className="font-mono text-xs rounded-lg p-3 break-all" style={{ background: isDark ? '#0c1118' : '#f0f4f8', color: muted }}>
          {source_manifest_hash}
        </div>
        <div className="text-[10px] mt-2" style={{ color: `${muted}80` }}>
          Hash of all ingested source records — changes if any source data changes.
        </div>
      </div>
    </div>
  );
}
