import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../../api/client';

interface Props { isDark: boolean; }

type VerifyResult = { valid: boolean; reason: string };
type DemoStep = 'idle' | 'loaded' | 'tampered' | 'verified';

export default function EvidencePanel({ isDark }: Props) {
  // Manual verify tab
  const [raw, setRaw]           = useState('');
  const [manualResult, setManualResult] = useState<VerifyResult | null>(null);
  const [manualLoading, setManualLoading] = useState(false);
  const [manualError, setManualError]     = useState('');

  // Tamper demo tab
  const [demoStep, setDemoStep]           = useState<DemoStep>('idle');
  const [demoLoading, setDemoLoading]     = useState(false);
  const [demoError, setDemoError]         = useState('');
  const [originalEnvelope, setOriginalEnvelope] = useState<any>(null);
  const [tamperedEnvelope, setTamperedEnvelope] = useState<any>(null);
  const [validResult, setValidResult]     = useState<VerifyResult | null>(null);
  const [invalidResult, setInvalidResult] = useState<VerifyResult | null>(null);
  const [tamperedField, setTamperedField] = useState<{ key: string; before: string; after: string } | null>(null);

  const [tab, setTab] = useState<'demo' | 'manual'>('demo');

  const bg      = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border  = isDark ? '#1e2d42' : '#e2e8f0';
  const text    = isDark ? '#e8edf5' : '#1a202c';
  const muted   = isDark ? '#6b7280' : '#94a3b8';
  const inputBg = isDark ? '#060d18' : '#f8fafc';

  // ── Manual verify ─────────────────────────────────────────────────────────
  async function manualVerify() {
    if (!raw.trim()) { setManualError('Paste an evidence envelope'); return; }
    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch { setManualError('Invalid JSON'); return; }
    setManualLoading(true); setManualError(''); setManualResult(null);
    try {
      const r = await api.post<VerifyResult>('/verify', { envelope: parsed });
      setManualResult(r);
    } catch (e: any) {
      setManualError(e.message);
    } finally {
      setManualLoading(false);
    }
  }

  // ── Tamper demo steps ──────────────────────────────────────────────────────

  // Step 1 — fetch a real signed envelope from the backend
  async function loadEnvelope() {
    setDemoLoading(true); setDemoError('');
    setOriginalEnvelope(null); setTamperedEnvelope(null);
    setValidResult(null); setInvalidResult(null); setTamperedField(null);
    try {
      const r = await api.get<{ envelope: any; tamper_hint: string }>('/demo/signed-envelope');
      setOriginalEnvelope(r.envelope);
      setDemoStep('loaded');
    } catch (e: any) {
      setDemoError(e.message);
    } finally {
      setDemoLoading(false);
    }
  }

  // Step 2 — mutate one field to simulate tampering, verify both
  async function tamperAndVerify() {
    if (!originalEnvelope) return;
    setDemoLoading(true); setDemoError('');

    // Clone and tamper: flip the decision to make it look more favourable
    const tampered = JSON.parse(JSON.stringify(originalEnvelope));
    const originalDecision: string = tampered.decision ?? 'REVIEW_REQUIRED';
    const newDecision = 'AUTO_APPROVED';
    tampered.decision = newDecision;
    setTamperedField({ key: 'decision', before: originalDecision, after: newDecision });
    setTamperedEnvelope(tampered);

    try {
      // Verify both in parallel
      const [validR, invalidR] = await Promise.all([
        api.post<VerifyResult>('/verify', { envelope: originalEnvelope }),
        api.post<VerifyResult>('/verify', { envelope: tampered }),
      ]);
      setValidResult(validR);
      setInvalidResult(invalidR);
      setDemoStep('verified');
    } catch (e: any) {
      setDemoError(e.message);
    } finally {
      setDemoLoading(false);
    }
  }

  function resetDemo() {
    setDemoStep('idle');
    setOriginalEnvelope(null); setTamperedEnvelope(null);
    setValidResult(null); setInvalidResult(null);
    setTamperedField(null); setDemoError('');
  }

  // ── Renderers ──────────────────────────────────────────────────────────────

  const VerifyBadge = ({ result, label }: { result: VerifyResult; label: string }) => (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
      style={{
        flex: 1, borderRadius: 12, padding: 16,
        background: result.valid ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
        border: `1px solid ${result.valid ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
      }}
    >
      <div style={{ fontSize: 28, marginBottom: 8 }}>{result.valid ? '✅' : '❌'}</div>
      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: muted, marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 14, fontWeight: 800, color: result.valid ? '#22c55e' : '#ef4444', marginBottom: 6 }}>
        {result.valid ? 'VERIFIED' : 'TAMPER DETECTED'}
      </div>
      <div style={{ fontSize: 11, color: muted, lineHeight: 1.5 }}>{result.reason}</div>
    </motion.div>
  );

  const StepDot = ({ n, active, done }: { n: number; active: boolean; done: boolean }) => (
    <div style={{
      width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 12, fontWeight: 700,
      background: done ? '#22c55e' : active ? '#3b82f6' : (isDark ? '#1e2d42' : '#e2e8f0'),
      color: done || active ? '#fff' : muted,
      transition: 'all 0.3s',
    }}>
      {done ? '✓' : n}
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto space-y-5">

      {/* Tab switcher */}
      <div style={{ display:'flex', gap:0, background: isDark?'rgba(6,13,24,0.6)':'rgba(0,0,0,0.05)', borderRadius:10, padding:3, width:'fit-content' }}>
        {(['demo','manual'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              padding:'7px 18px', borderRadius:8, border:'none', cursor:'pointer',
              fontSize:12, fontWeight:600, textTransform:'uppercase', letterSpacing:'0.05em',
              background: tab===t ? (isDark?'rgba(59,130,246,0.2)':'rgba(59,130,246,0.12)') : 'transparent',
              color: tab===t ? '#60a5fa' : muted,
              transition:'all 0.15s',
            }}
          >
            {t === 'demo' ? '🔐 Tamper Demo' : '📋 Manual Verify'}
          </button>
        ))}
      </div>

      {/* ── TAMPER DEMO TAB ────────────────────────────────────────────────── */}
      {tab === 'demo' && (
        <div className="space-y-5">

          {/* Concept callout */}
          <div style={{ borderRadius:12, padding:'14px 18px', background:'rgba(59,130,246,0.08)', border:'1px solid rgba(59,130,246,0.2)' }}>
            <div style={{ fontSize:13, fontWeight:700, color:'#60a5fa', marginBottom:4 }}>
              Every decision is a cryptographic proof
            </div>
            <div style={{ fontSize:12, color:muted, lineHeight:1.6 }}>
              GeoSamanvay signs every harmonization decision with Ed25519. The signature is computed over a
              canonical hash of the entire evidence payload — change a single field and verification fails.
              No database access needed to verify. A field officer can check any 2026 decision in 2035.
            </div>
          </div>

          {/* Step tracker */}
          <div style={{ borderRadius:12, padding:16, background:bg, border:'1px solid '+border }}>
            <div style={{ fontSize:11, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.08em', color:muted, marginBottom:14 }}>
              Demo steps
            </div>
            <div style={{ display:'flex', gap:0, alignItems:'flex-start' }}>
              {[
                { n:1, label:'Load signed envelope', done: demoStep !== 'idle' },
                { n:2, label:'Tamper with decision field', done: demoStep === 'verified' },
                { n:3, label:'Verify both — see tamper detected', done: demoStep === 'verified' },
              ].map((step, i, arr) => (
                <React.Fragment key={step.n}>
                  <div style={{ flex:1, textAlign:'center' }}>
                    <div style={{ display:'flex', justifyContent:'center', marginBottom:6 }}>
                      <StepDot n={step.n} active={
                        (step.n === 1 && demoStep === 'idle') ||
                        (step.n === 2 && demoStep === 'loaded') ||
                        (step.n === 3 && demoStep === 'tampered')
                      } done={step.done} />
                    </div>
                    <div style={{ fontSize:10, color:muted, lineHeight:1.4 }}>{step.label}</div>
                  </div>
                  {i < arr.length - 1 && (
                    <div style={{ flexShrink:0, width:24, marginTop:12, height:2, background: step.done ? '#22c55e' : (isDark?'#1e2d42':'#e2e8f0'), transition:'all 0.3s' }} />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Error */}
          {demoError && (
            <div style={{ fontSize:12, color:'#ef4444', background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.2)', borderRadius:8, padding:'10px 14px' }}>
              ✗ {demoError}
            </div>
          )}

          {/* Step 1: idle → load */}
          {demoStep === 'idle' && (
            <div style={{ borderRadius:12, padding:20, background:bg, border:'1px solid '+border, textAlign:'center' }}>
              <div style={{ fontSize:36, marginBottom:10 }}>🔐</div>
              <div style={{ fontSize:14, fontWeight:700, color:text, marginBottom:6 }}>
                Step 1 — Load a signed evidence envelope
              </div>
              <div style={{ fontSize:12, color:muted, marginBottom:20, lineHeight:1.5 }}>
                Fetches a real signed envelope from the Ward 42 demo case
                (or generates a synthetic one if the demo hasn't been loaded yet).
              </div>
              <button
                onClick={loadEnvelope}
                disabled={demoLoading}
                style={{
                  background:'#2563eb', color:'#fff', border:'none', borderRadius:8,
                  padding:'10px 28px', fontSize:13, fontWeight:700, cursor:'pointer',
                  opacity: demoLoading ? 0.6 : 1, transition:'all 0.15s',
                }}
              >
                {demoLoading ? '⏳ Loading…' : '📥 Load Signed Envelope'}
              </button>
            </div>
          )}

          {/* Step 2: loaded → show envelope, offer tamper */}
          {demoStep === 'loaded' && originalEnvelope && (
            <motion.div initial={{ opacity:0, y:6 }} animate={{ opacity:1, y:0 }}
              style={{ borderRadius:12, padding:20, background:bg, border:'1px solid '+border }}
            >
              <div style={{ fontSize:12, fontWeight:700, color:'#22c55e', marginBottom:4 }}>
                ✓ Envelope loaded — signature valid
              </div>
              <div style={{ fontSize:11, color:muted, marginBottom:12 }}>
                Decision: <span style={{ color:text, fontWeight:600 }}>{originalEnvelope.decision}</span>
                {' · '}
                Algorithm: <span style={{ color:text }}>{originalEnvelope.signing?.algorithm}</span>
                {' · '}
                Key: <span style={{ color:'#06b6d4', fontFamily:'monospace', fontSize:10 }}>{originalEnvelope.signing?.key_id?.slice(0,12)}…</span>
              </div>

              {/* Hash preview */}
              <div style={{ borderRadius:8, padding:'8px 12px', background:isDark?'#060d18':'#f0f4f8', border:'1px solid '+border, marginBottom:16 }}>
                <div style={{ fontSize:9, color:muted, fontWeight:700, textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:3 }}>SHA-256 evidence hash</div>
                <div style={{ fontSize:10, fontFamily:'monospace', color:'#06b6d4', wordBreak:'break-all' }}>
                  {originalEnvelope.evidence_hash}
                </div>
              </div>

              <div style={{ fontSize:12, color:text, marginBottom:4, fontWeight:600 }}>
                Step 2 — Tamper with the decision field
              </div>
              <div style={{ fontSize:11, color:muted, marginBottom:16, lineHeight:1.5 }}>
                We'll change <code style={{ color:'#f59e0b', fontSize:10 }}>decision</code> from{' '}
                <strong style={{ color:'#ef4444' }}>{originalEnvelope.decision}</strong> to{' '}
                <strong style={{ color:'#ef4444' }}>AUTO_APPROVED</strong>.
                The hash and signature won't match — tamper detection fires.
              </div>
              <div style={{ display:'flex', gap:10 }}>
                <button onClick={tamperAndVerify} disabled={demoLoading}
                  style={{
                    flex:1, background:'rgba(239,68,68,0.9)', color:'#fff', border:'none', borderRadius:8,
                    padding:'10px', fontSize:13, fontWeight:700, cursor:'pointer',
                    opacity: demoLoading ? 0.6 : 1, transition:'all 0.15s',
                  }}
                >
                  {demoLoading ? '⏳ Verifying…' : '✎ Tamper + Verify'}
                </button>
                <button onClick={resetDemo}
                  style={{ padding:'10px 16px', borderRadius:8, border:'1px solid '+border, background:'transparent', color:muted, fontSize:12, cursor:'pointer' }}>
                  ↺ Reset
                </button>
              </div>
            </motion.div>
          )}

          {/* Step 3: results — side by side */}
          {demoStep === 'verified' && validResult && invalidResult && (
            <motion.div initial={{ opacity:0, y:6 }} animate={{ opacity:1, y:0 }} className="space-y-4">
              {/* Tamper callout */}
              {tamperedField && (
                <div style={{ borderRadius:10, padding:'10px 14px', background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.2)' }}>
                  <span style={{ fontSize:11, color:muted }}>Field tampered: </span>
                  <code style={{ fontSize:11, color:'#f59e0b' }}>{tamperedField.key}</code>
                  <span style={{ fontSize:11, color:muted }}> changed from </span>
                  <strong style={{ color:'#22c55e', fontSize:11 }}>{tamperedField.before}</strong>
                  <span style={{ fontSize:11, color:muted }}> → </span>
                  <strong style={{ color:'#ef4444', fontSize:11 }}>{tamperedField.after}</strong>
                </div>
              )}

              {/* Side-by-side results */}
              <div style={{ display:'flex', gap:12 }}>
                <VerifyBadge result={validResult}   label="Original envelope" />
                <VerifyBadge result={invalidResult} label="Tampered envelope" />
              </div>

              {/* Key point callout */}
              <div style={{ borderRadius:10, padding:'12px 16px', background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)' }}>
                <div style={{ fontSize:12, fontWeight:700, color:'#22c55e', marginBottom:4 }}>Why this matters</div>
                <div style={{ fontSize:11, color:muted, lineHeight:1.6 }}>
                  The verifier holds <strong style={{color:text}}>no write access and no database connection</strong>.
                  It reconstructs the canonical hash from the payload and checks it against the stored hash and signature.
                  A single changed byte — including changing REVIEW_REQUIRED to AUTO_APPROVED — breaks both checks simultaneously.
                  This makes every approved land record decision independently auditable in perpetuity.
                </div>
              </div>

              <button onClick={resetDemo}
                style={{ padding:'10px 20px', borderRadius:8, border:'1px solid '+border, background:'transparent', color:muted, fontSize:12, cursor:'pointer' }}>
                ↺ Run again
              </button>
            </motion.div>
          )}

          {/* How it works */}
          {demoStep !== 'verified' && (
            <div className="rounded-2xl p-6 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
              <div style={{ fontSize:12, fontWeight:700, color:text }}>How the signing works</div>
              {[
                ['01', 'Decision payload is canonically serialised (sorted keys, no whitespace)'],
                ['02', 'SHA-256 hash computed over the canonical bytes → stored as evidence_hash'],
                ['03', 'Ed25519 private key signs the canonical bytes → stored as signature'],
                ['04', 'Verification: reconstruct payload → recompute hash → check hash matches → verify signature via trust registry'],
                ['05', 'Change any field → hash mismatch → verification fails before the signature check even runs'],
              ].map(([step, desc]) => (
                <div key={step} style={{ display:'flex', alignItems:'flex-start', gap:10 }}>
                  <span style={{ fontSize:10, fontFamily:'monospace', color:'#3b82f6', background:'rgba(59,130,246,0.1)', padding:'2px 6px', borderRadius:3, flexShrink:0 }}>{step}</span>
                  <span style={{ fontSize:11, color:muted, lineHeight:1.5 }}>{desc}</span>
                </div>
              ))}
              <div style={{ borderRadius:8, padding:'10px 12px', background:'rgba(245,158,11,0.08)', border:'1px solid rgba(245,158,11,0.2)', fontSize:11, color:muted }}>
                <span style={{ color:'#f59e0b', fontWeight:600 }}>Original source data is never overwritten. </span>
                Every harmonization decision is an independently verifiable proof of what changed, why, and who approved it.
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── MANUAL VERIFY TAB ──────────────────────────────────────────────── */}
      {tab === 'manual' && (
        <div className="space-y-5">
          <h2 style={{ fontSize:15, fontWeight:700, color:text }}>Verify Signed Evidence Envelope</h2>

          <div className="rounded-2xl p-6 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
            <div style={{ display:'flex', alignItems:'flex-start', gap:12 }}>
              <span style={{ fontSize:20 }}>🔐</span>
              <div>
                <div style={{ fontSize:13, fontWeight:600, color:text, marginBottom:4 }}>Paste any signed decision</div>
                <div style={{ fontSize:11, color:muted, lineHeight:1.5 }}>
                  Ed25519 signature and SHA-256 hash verified independently — no database access needed.
                </div>
              </div>
            </div>

            <textarea
              value={raw} onChange={e => setRaw(e.target.value)}
              placeholder={'{\n  "schema_version": "gs-evidence-v1",\n  ...\n  "evidence_hash": "...",\n  "signature": "...",\n  "signing": { "algorithm": "Ed25519", "key_id": "..." }\n}'}
              style={{ width:'100%', borderRadius:8, padding:'12px 14px', fontSize:11, fontFamily:'monospace', border:'1px solid '+border, background:inputBg, color:text, height:200, resize:'none', outline:'none', boxSizing:'border-box' }}
            />

            {manualError && (
              <div style={{ fontSize:11, color:'#ef4444', background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.2)', borderRadius:8, padding:'8px 12px' }}>✗ {manualError}</div>
            )}

            {manualResult && (
              <motion.div initial={{ opacity:0, y:4 }} animate={{ opacity:1, y:0 }}
                style={{ display:'flex', alignItems:'flex-start', gap:12, padding:14, borderRadius:10,
                  background: manualResult.valid ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                  border: `1px solid ${manualResult.valid ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}` }}>
                <span style={{ fontSize:20 }}>{manualResult.valid ? '✅' : '❌'}</span>
                <div>
                  <div style={{ fontSize:13, fontWeight:700, color: manualResult.valid ? '#22c55e' : '#ef4444', marginBottom:3 }}>
                    {manualResult.valid ? 'VERIFIED ✓' : 'INVALID ✗'}
                  </div>
                  <div style={{ fontSize:11, color:muted }}>{manualResult.reason}</div>
                </div>
              </motion.div>
            )}

            <button onClick={manualVerify} disabled={manualLoading}
              style={{ display:'flex', alignItems:'center', gap:8, background:'#2563eb', color:'#fff', border:'none', borderRadius:8, padding:'10px 20px', fontSize:13, fontWeight:700, cursor:'pointer', opacity: manualLoading ? 0.6 : 1 }}>
              {manualLoading ? '⏳ Verifying…' : '🔐 Verify Signature'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
