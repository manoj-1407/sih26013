import React from 'react';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, Loader2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { RadialBarChart, RadialBar, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { api, QualityReport } from '../../api/client';

const Q_COLORS: Record<string, string> = { HIGH: '#22c55e', MEDIUM: '#f59e0b', LOW: '#ef4444', UNKNOWN: '#6b7280' };

export default function QualityPanel({ caseId }: { caseId: string | null }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['quality', caseId],
    queryFn: () => api.get<QualityReport>(`/cases/${caseId}/quality-report`),
    enabled: !!caseId,
    retry: false,
  });

  if (!caseId) return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
      <BarChart3 size={40} className="opacity-20" />
      <p className="text-sm">Select a case first</p>
    </div>
  );

  if (isLoading) return (
    <div className="flex items-center justify-center gap-2 py-20 text-gray-600">
      <Loader2 size={16} className="animate-spin" /> Loading quality report…
    </div>
  );

  if (error || !data) return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-600 gap-3">
      <BarChart3 size={40} className="opacity-20" />
      <p className="text-sm">No datasets ingested yet for this case</p>
    </div>
  );

  const gaugeData = [{ value: data.summary.overall_validity_rate, fill: data.summary.overall_validity_rate >= 90 ? '#22c55e' : data.summary.overall_validity_rate >= 70 ? '#f59e0b' : '#ef4444' }];

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <h2 className="text-base font-bold text-white">Data Quality Report</h2>

      {/* Summary row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="glass rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-brand-400 mb-1">{data.summary.datasets}</div>
          <div className="text-[10px] text-gray-600 uppercase tracking-wider">Datasets</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 }} className="glass rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-white mb-1">{data.summary.total_records}</div>
          <div className="text-[10px] text-gray-600 uppercase tracking-wider">Total Records</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }} className="glass rounded-xl p-4 text-center">
          <div className="text-3xl font-black text-green-400 mb-1">{data.summary.total_valid}</div>
          <div className="text-[10px] text-gray-600 uppercase tracking-wider">Valid Records</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3 }} className="glass rounded-xl p-5">
          <div className="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Overall Validity</div>
          <div className="h-20">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart cx="50%" cy="100%" innerRadius="60%" outerRadius="90%" startAngle={180} endAngle={0} data={gaugeData}>
                <RadialBar dataKey="value" cornerRadius={4} background={{ fill: '#1a2535' }}>
                  {gaugeData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </RadialBar>
              </RadialBarChart>
            </ResponsiveContainer>
          </div>
          <div className="text-center -mt-6">
            <span className="text-xl font-black" style={{ color: gaugeData[0].fill }}>
              {data.summary.overall_validity_rate.toFixed(1)}%
            </span>
          </div>
        </motion.div>
      </div>

      {/* Per-dataset */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3 border-b border-dark-200/30 section-title mt-0">Per-Dataset Quality</div>
        <div className="divide-y divide-dark-200/30">
          {data.datasets.map((d, i) => {
            const validity = d.validity_rate ?? (d.total_features > 0 ? (d.valid_features / d.total_features) * 100 : 0);
            const color = Q_COLORS[d.quality_level];
            return (
              <motion.div key={d.dataset_id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono text-gray-600 bg-dark-600 px-2 py-0.5 rounded">{d.source_type}</span>
                      <span className="text-xs font-bold" style={{ color }}>{d.quality_level}</span>
                      {d.quality_score !== undefined && (
                        <span className="text-[11px] text-gray-600">{d.quality_score.toFixed(1)}%</span>
                      )}
                    </div>
                    <div className="text-sm text-white font-medium">{d.label || d.source_type}</div>
                  </div>
                  <div className="text-right text-xs text-gray-600">
                    <span className="text-white font-mono">{d.valid_features}</span> / {d.total_features}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-dark-600 rounded-full h-2 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${validity}%` }}
                      transition={{ duration: 0.8, delay: i * 0.05 }}
                      className="h-full rounded-full"
                      style={{ background: color }}
                    />
                  </div>
                  <span className="text-[11px] font-mono text-gray-500 w-10 text-right">{validity.toFixed(0)}%</span>
                </div>
                {d.warnings?.map((w, wi) => (
                  <div key={wi} className="mt-2 flex items-start gap-1.5 text-[11px] text-amber-500/80">
                    <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />{w}
                  </div>
                ))}
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Source hash */}
      <div className="glass rounded-xl p-4">
        <div className="section-title">Source Manifest SHA-256</div>
        <div className="font-mono text-xs text-gray-400 break-all bg-dark-600 rounded-lg p-3">
          {data.source_manifest_hash}
        </div>
        <div className="text-[10px] text-gray-600 mt-2">
          Hash of all ingested source records — changes if any source data changes.
        </div>
      </div>
    </div>
  );
}
