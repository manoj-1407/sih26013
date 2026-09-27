import React, { useState } from 'react';
import { Parcel } from '../api/client';

interface Props {
  parcel: Parcel;
}

const SIGNAL_DESCRIPTIONS: Record<string, string> = {
  geometry: 'Spatial overlap, boundary offset, area ratio between source polygons',
  identifier: 'Khasra/parcel ID, ULPIN, property number exact or normalized match',
  attribute: 'Owner name similarity, land-use agreement, ward/locality match',
  temporal: 'Gap between source observation dates — large gap may mean temporal evolution',
  provenance: 'How many independent data lineages (origins) confirm this match',
  overall: 'Weighted composite of all signals above',
  match_confidence: 'Overall match confidence (geometry + identifier + attribute + temporal + provenance)',
};

const CONFLICT_DESCRIPTIONS: Record<string, string> = {
  BOUNDARY_OFFSET: 'Polygon boundaries from different sources do not align — may indicate survey measurement difference or datum shift',
  AREA_MISMATCH: 'Stated area values disagree across sources — check unit conversions and survey methods',
  OVERLAP: 'Source geometries have unintended overlap — topology violation requiring resolution',
  GAP: 'Adjacent parcels have an unintended gap between them',
  SHAPE_DEFORMATION: 'Overall parcel shape differs significantly between sources',
  OWNER_REFERENCE_MISMATCH: 'Owner names do not match — possible transliteration variation, name change, or different person',
  LAND_USE_MISMATCH: 'Land-use classification differs — may reflect genuine change or classification inconsistency',
  AREA_ATTRIBUTE_MISMATCH: 'Recorded area values in attribute tables differ beyond acceptable tolerance',
  IDENTIFIER_MISMATCH: 'Parcel reference numbers conflict — check if these are actually the same parcel',
  SHARED_ORIGIN: 'Multiple datasets trace back to the same source — they count as ONE independent observation',
  UNKNOWN_LINEAGE: 'Provenance information insufficient to determine source independence',
  BUILDING_OUTSIDE_PARCEL: 'Building footprint extends beyond the proposed parcel boundary',
  UTILITY_CROSSING: 'Utility line crosses the proposed parcel boundary',
  ROAD_ROW_CONFLICT: 'Proposed boundary overlaps road right-of-way',
};

function Bar({ label, value, tooltip }: { label: string; value: number; tooltip?: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const color = pct >= 85 ? 'var(--green)' : pct >= 65 ? 'var(--amber)' : 'var(--red)';
  const [showTip, setShowTip] = useState(false);

  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setShowTip(true)}
      onMouseLeave={() => setShowTip(false)}
    >
      <div className="conf-bar-row" style={{ cursor: tooltip ? 'help' : 'default' }}>
        <span className="conf-bar-label" style={{ textTransform: 'capitalize' }}>
          {label.replace(/_/g, ' ')}
          {tooltip && <span style={{ color: 'var(--text3)', marginLeft: 4 }}>ⓘ</span>}
        </span>
        <div className="conf-bar-track">
          <div className="conf-bar-fill" style={{ width: `${pct}%`, background: color }} />
        </div>
        <span className="conf-bar-value" style={{ color }}>{pct}%</span>
      </div>
      {showTip && tooltip && (
        <div style={{
          position: 'absolute', left: 110, top: -2, zIndex: 100,
          background: 'var(--surface2)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '6px 10px', fontSize: 11,
          color: 'var(--text2)', maxWidth: 260, lineHeight: 1.5,
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {tooltip}
        </div>
      )}
    </div>
  );
}

function IndependenceIndicator({ count }: { count: number }) {
  return (
    <div style={{
      background: count >= 2 ? 'rgba(34,197,94,0.1)' : 'rgba(245,158,11,0.1)',
      border: `1px solid ${count >= 2 ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.3)'}`,
      borderRadius: 6, padding: '8px 12px', marginTop: 8,
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: count >= 2 ? 'var(--green)' : 'var(--amber)' }}>
        {count} independent source lineage{count !== 1 ? 's' : ''}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 3 }}>
        {count >= 3
          ? '3+ distinct observations confirm this match — high evidence quality.'
          : count === 2
          ? '2 independent observations — sufficient for confident matching.'
          : count === 1
          ? 'All sources share one origin — they count as a single observation, not multiple.'
          : 'Independence unknown — provenance information incomplete.'}
      </div>
      {count === 1 && (
        <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 4 }}>
          ⚠ Example: Cadastral → Municipal GIS export → Tax database are ONE lineage, not three.
        </div>
      )}
    </div>
  );
}

export default function ConfidenceExplainer({ parcel }: Props) {
  const evidence = parcel.match_evidence || {};
  const components = parcel.proposal?.confidence_components || {};
  const conflicts = parcel.conflicts || [];
  const proposal = parcel.proposal;

  const signalScores: Record<string, number> = {};
  for (const [k, v] of Object.entries({ ...evidence, ...components })) {
    if (typeof v === 'number' && v >= 0 && v <= 1) {
      signalScores[k] = v;
    }
  }

  return (
    <div className="flex-col gap-3">
      {/* Confidence signals */}
      <div className="card">
        <div className="card-header">📊 Match Evidence Breakdown</div>
        <div className="card-body">
          <div className="conf-bar-container" style={{ gap: 8 }}>
            {Object.entries(signalScores).map(([k, v]) => (
              <Bar key={k} label={k} value={v} tooltip={SIGNAL_DESCRIPTIONS[k]} />
            ))}
            {Object.keys(signalScores).length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>
                Run harmonization to see match evidence breakdown.
              </div>
            )}
          </div>
          <IndependenceIndicator count={parcel.independent_lineages ?? 0} />
          <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 8 }}>
            Confidence is a weighted composite signal — not a calibrated probability.
            It reflects agreement across geometry, identifiers, attributes, temporal context and source independence.
          </div>
        </div>
      </div>

      {/* Conflict explanations */}
      {conflicts.length > 0 && (
        <div className="card">
          <div className="card-header">⚡ Conflict Explanations</div>
          <div className="card-body flex-col gap-2">
            {conflicts.map(c => (
              <div key={c.conflict_id} style={{
                borderLeft: `3px solid ${
                  c.severity === 'CRITICAL' ? 'var(--red)'
                  : c.severity === 'HIGH' ? 'var(--amber)'
                  : c.severity === 'MEDIUM' ? '#a78bfa' : 'var(--text3)'
                }`,
                paddingLeft: 10, paddingBottom: 6,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <span className={`badge ${
                    c.severity === 'CRITICAL' ? 'badge-err'
                    : c.severity === 'HIGH' ? 'badge-warn'
                    : 'badge-neutral'
                  }`}>{c.severity}</span>
                  <span style={{ fontSize: 11, fontWeight: 700 }}>
                    {c.type.replace(/_/g, ' ')}
                  </span>
                  {c.measure !== undefined && (
                    <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 'auto' }}>
                      {c.measure} {c.measure_unit}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.4 }}>
                  {c.description}
                </div>
                {CONFLICT_DESCRIPTIONS[c.type] && (
                  <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 3, fontStyle: 'italic' }}>
                    {CONFLICT_DESCRIPTIONS[c.type]}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proposal reasoning */}
      {proposal && (
        <div className="card">
          <div className="card-header">🔄 Harmonization Reasoning</div>
          <div className="card-body flex-col gap-2">
            <div className={`notice ${
              proposal.decision === 'AUTO_APPROVED' ? 'notice-green'
              : proposal.decision === 'REVIEW_REQUIRED' ? 'notice-amber'
              : 'notice-red'
            }`}>
              <strong>{proposal.decision?.replace('_', ' ')}</strong>
              {proposal.decision_reason && `: ${proposal.decision_reason}`}
            </div>
            {proposal.change_summary && proposal.change_summary.length > 0 && (
              <div>
                <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text3)', marginBottom: 4 }}>
                  Change Summary
                </div>
                {proposal.change_summary.map((s, i) => (
                  <div key={i} style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 3 }}>
                    • {s}
                  </div>
                ))}
              </div>
            )}
            {proposal.ripple_check && (
              <div className={`notice ${proposal.ripple_check.safe_to_auto_approve ? 'notice-green' : 'notice-amber'}`}>
                <strong>Ripple Check:</strong> {proposal.ripple_check.summary}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
