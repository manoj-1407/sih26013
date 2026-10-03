/**
 * DemoTab — the 60-second judge path for GeoSamanvay SIH26013
 *
 * Three moments, in sequence:
 *  1. One parcel, four sources, one conflict — ripple blocks auto-approval
 *  2. Source independence — 4 files ≠ 4 independent observations
 *  3. Cryptographic tamper detection — change one field, verification fails
 *
 * Each moment is self-contained and triggered by a single button.
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../../api/client';

interface Props { isDark: boolean; onSelectCase: (id: string) => void; }

type Phase = 'intro' | 'moment1' | 'moment2' | 'moment3' | 'done';

// ── Helpers ───────────────────────────────────────────────────────────────────

function Step({ n, label, active, done, isDark }: {
  n: number; label: string; active: boolean; done: boolean; isDark: boolean;
}) {
  const bg = done ? '#22c55e' : active ? '#3b82f6' : (isDark ? '#1e2d42' : '#e2e8f0');
  const fg = done || active ? '#fff' : (isDark ? '#6b7280' : '#94a3b8');
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, opacity: done || active ? 1 : 0.45 }}>
      <div style={{ width: 28, height: 28, borderRadius: '50%', background: bg, color: fg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0, transition: 'all 0.3s' }}>
        {done ? '✓' : n}
      </div>
      <span style={{ fontSize: 12, color: done ? '#22c55e' : active ? '#60a5fa' : (isDark ? '#6b7280' : '#94a3b8'), fontWeight: done || active ? 600 : 400 }}>
        {label}
      </span>
    </div>
  );
}

function SectionCard({ children, accent = '#3b82f6', isDark }: {
  children: React.ReactNode; accent?: string; isDark: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      style={{
        borderRadius: 14, padding: 20,
        background: isDark ? 'rgba(20,28,39,0.85)' : 'rgba(255,255,255,0.95)',
        border: `1px solid ${accent}40`,
        boxShadow: `0 0 0 1px ${accent}18`,
      }}
    >
      {children}
    </motion.div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string | number; accent: string }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '10px 8px', borderRadius: 8, background: accent + '10', border: '1px solid ' + accent + '25' }}>
      <div style={{ fontSize: 22, fontWeight: 900, color: accent }}>{value}</div>
      <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.09em', color: accent, opacity: 0.75, marginTop: 2 }}>{label}</div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function DemoTab({ isDark, onSelectCase }: Props) {
  const [phase, setPhase]       = useState<Phase>('intro');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  // Moment 1 data
  const [m1Data, setM1Data] = useState<any>(null);
  // Moment 2 data
  const [m2Data, setM2Data] = useState<any>(null);
  // Moment 3 data
  const [m3Original, setM3Original] = useState<any>(null);
  const [m3Valid, setM3Valid]       = useState<{ valid: boolean; reason: string } | null>(null);
  const [m3Invalid, setM3Invalid]   = useState<{ valid: boolean; reason: string } | null>(null);

  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';

  function reset() {
    setPhase('intro'); setError('');
    setM1Data(null); setM2Data(null);
    setM3Original(null); setM3Valid(null); setM3Invalid(null);
  }

  // ── Moment 1: load Ward42, find a blocked parcel ──────────────────────────
  async function runMoment1() {
    setLoading(true); setError('');
    try {
      // Load (or reload) the Ward42 demo case
      const loaded = await api.post<any>('/demo/load-ward42', null);
      const caseId = loaded.case_id as string;

      // Get full parcel list to find the most interesting one
      const parcelsResp = await api.get<{ parcels: any[] }>(`/cases/${caseId}/parcels`);
      const parcels = parcelsResp.parcels ?? [];

      // Find the parcel with most conflicts + REVIEW_REQUIRED decision
      const focal = [...parcels].sort((a, b) => {
        const aScore = (a.conflict_count ?? 0) * 10 + (a.proposal?.decision === 'REVIEW_REQUIRED' ? 5 : 0);
        const bScore = (b.conflict_count ?? 0) * 10 + (b.proposal?.decision === 'REVIEW_REQUIRED' ? 5 : 0);
        return bScore - aScore;
      })[0];

      // Get full detail (ripple check etc.)
      const detail = focal
        ? await api.get<any>(`/cases/${caseId}/parcels/${focal.canonical_id}`)
        : null;

      setM1Data({
        caseId,
        summary: {
          parcels: loaded.parcels_matched ?? parcels.length,
          review: loaded.review_required ?? 0,
          auto: loaded.auto_approved ?? 0,
          datasets: loaded.datasets_ingested?.length ?? 4,
        },
        focal: detail,
        allParcels: parcels,
      });
      onSelectCase(caseId);
      setPhase('moment1');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Moment 2: provenance independence ─────────────────────────────────────
  async function runMoment2() {
    setLoading(true); setError('');
    try {
      const data = await api.get<any>('/demo/provenance-demo');
      setM2Data(data);
      setPhase('moment2');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Moment 3: tamper demo ──────────────────────────────────────────────────
  async function runMoment3() {
    setLoading(true); setError('');
    try {
      const envResp = await api.get<{ envelope: any }>('/demo/signed-envelope');
      const original = envResp.envelope;

      // Tamper: change decision to AUTO_APPROVED
      const tampered = JSON.parse(JSON.stringify(original));
      tampered.decision = 'AUTO_APPROVED';

      const [validR, invalidR] = await Promise.all([
        api.post<{ valid: boolean; reason: string }>('/verify', { envelope: original }),
        api.post<{ valid: boolean; reason: string }>('/verify', { envelope: tampered }),
      ]);

      setM3Original(original);
      setM3Valid(validR);
      setM3Invalid(invalidR);
      setPhase('moment3');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const ripple   = m1Data?.focal?.proposal?.ripple_check;
  const decision = m1Data?.focal?.proposal?.decision;
  const decColor = decision === 'AUTO_APPROVED' ? '#22c55e' : decision === 'REVIEW_REQUIRED' ? '#f59e0b' : '#ef4444';
  const conflicts: any[] = m1Data?.focal?.conflicts ?? [];

  // Scenario A (shared origin) from moment 2
  const scenA = m2Data?.scenarios?.[0];
  const scenB = m2Data?.scenarios?.[1];
  const scenC = m2Data?.scenarios?.[2];

  return (
    <div style={{ maxWidth: 780, margin: '0 auto', paddingBottom: 40 }}>

      {/* Progress sidebar + content layout */}
      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

        {/* Left: step tracker (sticky) */}
        <div style={{
          width: 200, flexShrink: 0, position: 'sticky', top: 16,
          borderRadius: 14, padding: '16px 14px',
          background: isDark ? 'rgba(10,15,26,0.9)' : 'rgba(255,255,255,0.9)',
          border: '1px solid ' + border,
          display: 'flex', flexDirection: 'column', gap: 14,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.09em', color: muted, marginBottom: 2 }}>
            Judge Demo Path
          </div>
          <Step n={1} label="Parcel conflict & ripple"  active={phase==='intro'||phase==='moment1'} done={['moment2','moment3','done'].includes(phase)} isDark={isDark} />
          <Step n={2} label="Source independence"        active={phase==='moment2'}                 done={['moment3','done'].includes(phase)}             isDark={isDark} />
          <Step n={3} label="Cryptographic proof"        active={phase==='moment3'}                 done={phase==='done'}                                  isDark={isDark} />

          {phase !== 'intro' && (
            <button onClick={reset}
              style={{ marginTop: 4, padding: '7px 0', borderRadius: 8, border: '1px solid ' + border, background: 'transparent', color: muted, fontSize: 11, cursor: 'pointer' }}>
              ↺ Reset demo
            </button>
          )}
        </div>

        {/* Right: content */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── INTRO ────────────────────────────────────────────────────── */}
          {phase === 'intro' && (
            <SectionCard isDark={isDark}>
              <div style={{ fontSize: 22, marginBottom: 10 }}>🗺️</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: text, marginBottom: 6 }}>
                GeoSamanvay — 60-second demo
              </div>
              <div style={{ fontSize: 12, color: muted, lineHeight: 1.7, marginBottom: 20 }}>
                Three moments that show why GeoSamanvay is different from a GIS tool or an auto-fix system.
                Each moment is a live proof — no mock data, no pre-recorded screenshots.
              </div>
              {[
                ['1', '#f59e0b', 'One parcel, four conflicting sources. The system blocks auto-approval and explains exactly why.'],
                ['2', '#3b82f6', '4 source files ≠ 4 independent observations. The provenance graph counts origins, not file names.'],
                ['3', '#22c55e', 'Change a single field in a signed decision. Tamper detection fires instantly.'],
              ].map(([n, c, desc]) => (
                <div key={n} style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
                  <div style={{ width: 26, height: 26, borderRadius: '50%', background: c + '20', border: '1px solid ' + c + '40', color: c, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>{n}</div>
                  <div style={{ fontSize: 12, color: muted, lineHeight: 1.5, paddingTop: 3 }}>{desc}</div>
                </div>
              ))}

              {error && (
                <div style={{ fontSize: 11, color: '#ef4444', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '8px 12px', marginBottom: 14 }}>
                  ✗ {error}
                </div>
              )}

              <button onClick={runMoment1} disabled={loading}
                style={{ background: '#2563eb', color: '#fff', border: 'none', borderRadius: 10, padding: '11px 28px', fontSize: 13, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.65 : 1, transition: 'all 0.15s' }}>
                {loading ? '⏳ Loading Ward 42…' : '▶ Start Demo'}
              </button>
            </SectionCard>
          )}

          {/* ── MOMENT 1: conflict + ripple ──────────────────────────────── */}
          {(phase === 'moment1' || phase === 'moment2' || phase === 'moment3' || phase === 'done') && m1Data && (
            <SectionCard accent="#f59e0b" isDark={isDark}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div style={{ width: 26, height: 26, borderRadius: '50%', background: '#f59e0b20', border: '1px solid #f59e0b40', color: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>1</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: text }}>Parcel conflict and ripple validation</div>
                <div style={{ marginLeft: 'auto', fontSize: 9, fontWeight: 700, color: '#22c55e', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)', padding: '2px 7px', borderRadius: 4 }}>WARD42-DEMO</div>
              </div>

              {/* Summary metrics */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                <Metric label="Parcels" value={m1Data.summary.parcels} accent="#3b82f6" />
                <Metric label="Datasets" value={m1Data.summary.datasets} accent="#06b6d4" />
                <Metric label="For Review" value={m1Data.summary.review} accent="#f59e0b" />
                <Metric label="Auto-Approved" value={m1Data.summary.auto} accent="#22c55e" />
              </div>

              {/* Focal parcel */}
              {m1Data.focal && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: muted, marginBottom: 8 }}>
                    Focal parcel — most conflicts
                  </div>

                  {/* Decision badge */}
                  <div style={{ borderRadius: 10, padding: '10px 14px', marginBottom: 10, background: decColor + '12', border: '1px solid ' + decColor + '30' }}>
                    <div style={{ fontSize: 13, fontWeight: 800, color: decColor, marginBottom: 3 }}>
                      {decision?.replace(/_/g, ' ') ?? 'PENDING'}
                    </div>
                    <div style={{ fontSize: 11, color: muted }}>{m1Data.focal.proposal?.decision_reason}</div>
                  </div>

                  {/* Conflict list */}
                  {conflicts.length > 0 && (
                    <div style={{ marginBottom: 10 }}>
                      {conflicts.slice(0, 3).map((c: any) => {
                        const sc = c.severity === 'CRITICAL' ? '#ef4444' : c.severity === 'HIGH' ? '#f59e0b' : '#a78bfa';
                        return (
                          <div key={c.conflict_id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '6px 0', borderBottom: '1px solid ' + border + '30' }}>
                            <span style={{ fontSize: 9, fontWeight: 700, color: sc, background: sc + '15', border: '1px solid ' + sc + '30', padding: '2px 5px', borderRadius: 3, flexShrink: 0, marginTop: 1 }}>
                              {c.severity}
                            </span>
                            <span style={{ fontSize: 11, color: muted, lineHeight: 1.4 }}>{c.description}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Ripple check */}
                  {ripple && (
                    <div style={{ borderRadius: 10, padding: '10px 14px', background: ripple.safe_to_auto_approve ? 'rgba(34,197,94,0.08)' : 'rgba(245,158,11,0.08)', border: '1px solid ' + (ripple.safe_to_auto_approve ? 'rgba(34,197,94,0.25)' : 'rgba(245,158,11,0.25)'), marginBottom: 6 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: ripple.safe_to_auto_approve ? '#22c55e' : '#f59e0b', marginBottom: 4 }}>
                        🌊 Ripple check — {ripple.safe_to_auto_approve ? 'safe' : 'BLOCKED'}
                      </div>
                      <div style={{ fontSize: 11, color: muted }}>{ripple.summary}</div>
                      {ripple.issues?.slice(0, 2).map((issue: any) => (
                        <div key={issue.issue_id} style={{ fontSize: 10, color: muted, marginTop: 4 }}>
                          · {issue.issue_type.replace(/_/g, ' ')}: {issue.description}
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ fontSize: 10, color: muted, marginTop: 6 }}>
                    The system does not decide which source is correct.
                    It explains why this parcel <strong style={{ color: text }}>cannot safely be auto-finalized</strong> and sends it to an authorized officer.
                  </div>
                </div>
              )}

              {/* Advance button */}
              {phase === 'moment1' && (
                <div style={{ marginTop: 16 }}>
                  {error && <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>✗ {error}</div>}
                  <button onClick={runMoment2} disabled={loading}
                    style={{ background: '#2563eb', color: '#fff', border: 'none', borderRadius: 9, padding: '10px 24px', fontSize: 12, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.65 : 1 }}>
                    {loading ? '⏳ Loading…' : 'Next → Source independence'}
                  </button>
                </div>
              )}
            </SectionCard>
          )}

          {/* ── MOMENT 2: provenance independence ────────────────────────── */}
          {(phase === 'moment2' || phase === 'moment3' || phase === 'done') && m2Data && (
            <SectionCard accent="#3b82f6" isDark={isDark}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div style={{ width: 26, height: 26, borderRadius: '50%', background: '#3b82f620', border: '1px solid #3b82f640', color: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>2</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: text }}>Source independence — provenance tracing</div>
              </div>

              {/* Key insight */}
              <div style={{ borderRadius: 10, padding: '10px 14px', background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', marginBottom: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#60a5fa', marginBottom: 3 }}>The core insight</div>
                <div style={{ fontSize: 11, color: muted, lineHeight: 1.6 }}>{m2Data.key_insight}</div>
              </div>

              {/* Three scenarios side by side */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
                {[scenA, scenB, scenC].map((s: any, i: number) => {
                  if (!s) return null;
                  const isCorr = s.independent_lineages === 1;
                  const ac = isCorr ? '#ef4444' : i === 1 ? '#22c55e' : '#3b82f6';
                  return (
                    <motion.div key={i}
                      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                      style={{ borderRadius: 10, padding: '10px 12px', background: ac + '0e', border: '1px solid ' + ac + '30' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: ac, marginBottom: 6 }}>{s.label}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 9, color: muted }}>Files</span>
                        <span style={{ fontSize: 14, fontWeight: 900, color: text }}>{s.record_ids.length}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 9, color: muted }}>Origins</span>
                        <span style={{ fontSize: 14, fontWeight: 900, color: ac }}>{s.independent_lineages}</span>
                      </div>
                      {/* Mini bar */}
                      <div style={{ height: 4, borderRadius: 999, background: isDark ? '#0c1118' : '#e8edf5', overflow: 'hidden' }}>
                        <motion.div
                          initial={{ width: 0 }} animate={{ width: Math.round(s.provenance_score * 100) + '%' }}
                          transition={{ duration: 0.8, delay: 0.2 + i * 0.1 }}
                          style={{ height: '100%', background: ac, borderRadius: 999 }}
                        />
                      </div>
                      <div style={{ fontSize: 9, color: ac, marginTop: 4, fontWeight: 600 }}>
                        {Math.round(s.provenance_score * 100)}% signal
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* DAG origin summary */}
              <div style={{ borderRadius: 10, padding: '10px 14px', background: isDark ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.03)', border: '1px solid ' + border, marginBottom: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Ward 42 provenance origins</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {m2Data.graph_summary?.origins?.map((o: any, i: number) => {
                    const oc = ['#22c55e', '#f59e0b', '#06b6d4'][i] ?? '#3b82f6';
                    return (
                      <div key={o.node_id} style={{ borderRadius: 6, padding: '4px 9px', background: oc + '14', border: '1px solid ' + oc + '30' }}>
                        <div style={{ fontSize: 9, color: oc, fontWeight: 700 }}>{o.node_id}</div>
                        <div style={{ fontSize: 9, color: muted }}>{o.label}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={{ fontSize: 10, color: muted, marginTop: 6 }}>
                Cadastral and Revenue/RoR both descend from the 1999 survey.
                They <strong style={{ color: text }}>agree on area</strong> but that agreement is <strong style={{ color: text }}>one observation, not two</strong>.
              </div>

              {/* Advance */}
              {phase === 'moment2' && (
                <div style={{ marginTop: 16 }}>
                  {error && <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>✗ {error}</div>}
                  <button onClick={runMoment3} disabled={loading}
                    style={{ background: '#2563eb', color: '#fff', border: 'none', borderRadius: 9, padding: '10px 24px', fontSize: 12, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.65 : 1 }}>
                    {loading ? '⏳ Loading…' : 'Next → Cryptographic proof'}
                  </button>
                </div>
              )}
            </SectionCard>
          )}

          {/* ── MOMENT 3: tamper detection ────────────────────────────────── */}
          {(phase === 'moment3' || phase === 'done') && m3Valid && m3Invalid && m3Original && (
            <SectionCard accent="#22c55e" isDark={isDark}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div style={{ width: 26, height: 26, borderRadius: '50%', background: '#22c55e20', border: '1px solid #22c55e40', color: '#22c55e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>3</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: text }}>Cryptographic tamper detection</div>
              </div>

              <div style={{ fontSize: 11, color: muted, marginBottom: 14, lineHeight: 1.6 }}>
                We loaded a real signed envelope and changed{' '}
                <code style={{ color: '#f59e0b', fontSize: 10 }}>decision</code>
                {' '}from{' '}
                <strong style={{ color: '#ef4444' }}>{m3Original.decision === 'AUTO_APPROVED' ? 'REVIEW_REQUIRED' : m3Original.decision}</strong>
                {' '}to{' '}
                <strong style={{ color: '#ef4444' }}>AUTO_APPROVED</strong>.
                Both are verified below.
              </div>

              {/* Side by side */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                {[
                  { r: m3Valid,   label: 'Original', icon: '✅', accent: '#22c55e' },
                  { r: m3Invalid, label: 'Tampered',  icon: '❌', accent: '#ef4444' },
                ].map(({ r, label, icon, accent }) => (
                  <motion.div key={label}
                    initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
                    style={{ borderRadius: 10, padding: 14, background: accent + '0a', border: '1px solid ' + accent + '30' }}>
                    <div style={{ fontSize: 24, marginBottom: 8 }}>{icon}</div>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: muted, marginBottom: 4 }}>{label}</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: accent, marginBottom: 6 }}>
                      {r.valid ? 'VERIFIED' : 'TAMPER DETECTED'}
                    </div>
                    <div style={{ fontSize: 10, color: muted, lineHeight: 1.5 }}>{r.reason}</div>
                  </motion.div>
                ))}
              </div>

              {/* Hash preview */}
              <div style={{ borderRadius: 8, padding: '8px 12px', background: isDark ? '#060d18' : '#f0f4f8', border: '1px solid ' + border, marginBottom: 10 }}>
                <div style={{ fontSize: 9, color: muted, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>
                  SHA-256 evidence hash (would change if any field changes)
                </div>
                <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#06b6d4', wordBreak: 'break-all' }}>
                  {m3Original.evidence_hash}
                </div>
              </div>

              <div style={{ fontSize: 10, color: muted, lineHeight: 1.6 }}>
                The verifier holds <strong style={{ color: text }}>no write access</strong>.
                Verification works offline from a downloaded evidence package.
                A field officer can verify any 2026 decision in 2035 without connecting to the server.
              </div>

              {/* Done */}
              {phase === 'moment3' && (
                <div style={{ marginTop: 16 }}>
                  <button onClick={() => setPhase('done')}
                    style={{ background: '#22c55e', color: '#fff', border: 'none', borderRadius: 9, padding: '10px 24px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                    ✓ Demo complete
                  </button>
                </div>
              )}
            </SectionCard>
          )}

          {/* ── DONE ─────────────────────────────────────────────────────── */}
          {phase === 'done' && (
            <SectionCard accent="#22c55e" isDark={isDark}>
              <div style={{ textAlign: 'center', padding: '10px 0' }}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>✅</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: text, marginBottom: 8 }}>
                  Three moments, three differentiators
                </div>
                <div style={{ fontSize: 12, color: muted, lineHeight: 1.7, marginBottom: 20, textAlign: 'left' }}>
                  {[
                    ['🌊 Ripple governance', 'Boundary changes are never reviewed in isolation. Every proposed change is checked against neighbours, buildings, utilities and roads before auto-approval is permitted.'],
                    ['🔗 Source independence', 'GeoSamanvay traces every record to its root origin. 4 files from 1 origin count as 1 independent observation, not 4.'],
                    ['🔐 Cryptographic evidence', 'Every approved decision is signed with Ed25519. Tamper with a single field — the signature fails. No database access required to verify.'],
                  ].map(([title, desc]) => (
                    <div key={title as string} style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                      <div style={{ fontSize: 16, flexShrink: 0 }}>{(title as string).split(' ')[0]}</div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: text, marginBottom: 2 }}>{(title as string).slice(3)}</div>
                        <div style={{ fontSize: 11, color: muted }}>{desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
                <button onClick={reset}
                  style={{ padding: '9px 22px', borderRadius: 9, border: '1px solid ' + border, background: 'transparent', color: muted, fontSize: 12, cursor: 'pointer' }}>
                  ↺ Run again
                </button>
              </div>
            </SectionCard>
          )}

        </div>
      </div>
    </div>
  );
}
