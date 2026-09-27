import React from 'react';
import { Parcel } from '../api/client';

interface Props {
  parcel: Parcel;
}

/**
 * "Git diff for parcels" — shows exactly what the harmonization proposal
 * changes vs. the source state.
 *
 * This is the answer to: "What exactly would change?"
 * A judge who doesn't know GIS can still read this screen.
 */
export default function HarmonizationDiff({ parcel }: Props) {
  const proposal = parcel.proposal;
  const conflicts = parcel.conflicts ?? [];
  const ripple = proposal?.ripple_check;

  if (!proposal) {
    return (
      <div className="notice notice-amber">
        No harmonization proposal available. Run harmonization first.
      </div>
    );
  }

  const isAutoApproved = proposal.decision === 'AUTO_APPROVED';
  const isReview = proposal.decision === 'REVIEW_REQUIRED';
  const isBlocked = proposal.decision === 'BLOCKED';

  return (
    <div className="flex-col gap-3">

      {/* Decision banner — most important thing */}
      <div className={`notice ${isAutoApproved ? 'notice-green' : isBlocked ? 'notice-red' : 'notice-amber'}`}
        style={{ fontSize: 13, fontWeight: 700 }}>
        {isAutoApproved && '✓ AUTO-APPROVABLE'}
        {isReview && '⚠ REVIEW REQUIRED'}
        {isBlocked && '✕ BLOCKED'}
        {!isAutoApproved && proposal.decision_reason && (
          <div style={{ fontWeight: 400, fontSize: 12, marginTop: 4 }}>
            {proposal.decision_reason}
          </div>
        )}
      </div>

      {/* Geometry diff */}
      <div className="card">
        <div className="card-header">📐 Geometry Changes</div>
        <div className="card-body">
          <div className="kv">
            <span className="kv-k">Max boundary offset</span>
            <span className="kv-v" style={{
              color: (proposal.confidence_components as any)?.max_boundary_offset_m > 2
                ? 'var(--red)' : 'var(--text)'
            }}>
              {(proposal.confidence_components as any)?.max_boundary_offset_m?.toFixed(2) ?? '—'} m
            </span>

            <span className="kv-k">Area change</span>
            <span className="kv-v">
              {((proposal.confidence_components as any)?.area_change_pct_approx ?? 0).toFixed(1)}%
            </span>

            <span className="kv-k">Source count</span>
            <span className="kv-v">{parcel.source_count}</span>

            <span className="kv-k">Independent lineages</span>
            <span className="kv-v" style={{
              color: (parcel.independent_lineages ?? 0) >= 2 ? 'var(--green)' : 'var(--amber)'
            }}>
              {parcel.independent_lineages}
              {(parcel.independent_lineages ?? 0) < 2 && ' ⚠ insufficient for auto-approve'}
            </span>
          </div>

          {/* Change summary */}
          {(proposal.change_summary?.length ?? 0) > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text3)', marginBottom: 6 }}>
                What Changed
              </div>
              {proposal.change_summary!.map((s, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 3, paddingLeft: 8, borderLeft: '2px solid var(--border)' }}>
                  {s}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Attribute diff */}
      {conflicts.filter(c => ['OWNER_REFERENCE_MISMATCH', 'LAND_USE_MISMATCH', 'AREA_ATTRIBUTE_MISMATCH'].includes(c.type)).length > 0 && (
        <div className="card">
          <div className="card-header">🏷 Attribute Changes</div>
          <div className="card-body flex-col gap-2">
            {conflicts
              .filter(c => ['OWNER_REFERENCE_MISMATCH', 'LAND_USE_MISMATCH', 'AREA_ATTRIBUTE_MISMATCH'].includes(c.type))
              .map(c => (
                <div key={c.conflict_id} style={{ fontSize: 12 }}>
                  <span className={`badge ${c.severity === 'HIGH' ? 'badge-warn' : 'badge-neutral'}`} style={{ marginRight: 8 }}>
                    {c.type.replace(/_/g, ' ')}
                  </span>
                  <span style={{ color: 'var(--text2)' }}>{c.description}</span>
                  {c.measure !== undefined && (
                    <span style={{ marginLeft: 8, color: 'var(--text3)', fontSize: 11 }}>
                      {c.measure}{c.measure_unit ? ` ${c.measure_unit}` : ''}
                    </span>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Topology / Ripple diff */}
      <div className="card">
        <div className="card-header">🌐 Topology Impact</div>
        <div className="card-body">
          {ripple ? (
            <>
              <div className={`notice ${ripple.safe_to_auto_approve ? 'notice-green' : 'notice-amber'} mb-2`}>
                {ripple.safe_to_auto_approve
                  ? `✓ Safe — ${ripple.checked_neighbors ?? 0} neighbors, ${ripple.checked_buildings ?? 0} buildings checked`
                  : `⚠ ${ripple.total_issues} issue(s) detected`}
              </div>
              {(ripple.issues ?? []).length > 0 && (
                <div className="flex-col gap-2">
                  {ripple.issues!.map(issue => (
                    <div key={issue.issue_id} style={{
                      fontSize: 11, color: 'var(--text2)',
                      padding: '6px 8px',
                      background: 'var(--surface2)',
                      borderRadius: 4,
                      borderLeft: `3px solid ${issue.severity === 'CRITICAL' ? 'var(--red)' : 'var(--amber)'}`,
                    }}>
                      <strong>{issue.issue_type.replace(/_/g, ' ')}</strong>
                      {' — '}{issue.feature_type} <code style={{ fontFamily: 'var(--mono)' }}>{issue.feature_id}</code>
                      {issue.measure !== undefined && (
                        <span style={{ color: 'var(--text3)' }}> ({issue.measure} {issue.measure_unit})</span>
                      )}
                      <div style={{ marginTop: 3, color: 'var(--text3)' }}>{issue.description}</div>
                    </div>
                  ))}
                </div>
              )}
              {(ripple.issues ?? []).length === 0 && ripple.safe_to_auto_approve && (
                <div style={{ fontSize: 11, color: 'var(--text3)' }}>
                  No downstream topology issues. Proposal does not introduce new overlaps, gaps, or conflicts with neighboring features.
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text3)' }}>
              No ripple check data. Re-run harmonization with neighbor/building/utility layers to check topology impact.
            </div>
          )}
        </div>
      </div>

      {/* Why not auto-approved */}
      {!isAutoApproved && proposal.decision_reason && (
        <div className="card">
          <div className="card-header" style={{ color: isBlocked ? 'var(--red)' : 'var(--amber)' }}>
            {isBlocked ? '✕ Why This Was Blocked' : '⚠ Why This Needs Review'}
          </div>
          <div className="card-body flex-col gap-2">
            <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>
              {proposal.decision_reason.split(';').map((reason, i) => (
                <div key={i} style={{ marginBottom: 6, paddingLeft: 8, borderLeft: '3px solid var(--amber)' }}>
                  {reason.trim()}
                </div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
              The system does not auto-apply changes when evidence quality,
              topology safety, or provenance criteria are not fully satisfied.
              A human officer must review and approve this proposal.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
