import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '../../api/client';

interface Props { isDark: boolean; }

export default function EvidencePanel({ isDark }: Props) {
  const [raw, setRaw] = useState('');
  const [result, setResult] = useState<{ valid: boolean; reason: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const bg     = isDark ? 'rgba(20,28,39,0.8)' : 'rgba(255,255,255,0.95)';
  const border = isDark ? '#1e2d42' : '#e2e8f0';
  const text   = isDark ? '#e8edf5' : '#1a202c';
  const muted  = isDark ? '#6b7280' : '#94a3b8';
  const inputBg = isDark ? '#060d18' : '#f8fafc';

  async function verify() {
    if (!raw.trim()) { setError('Paste an evidence envelope'); return; }
    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch { setError('Invalid JSON'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const r = await api.post<{ valid: boolean; reason: string }>('/verify', { envelope: parsed });
      setResult(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <h2 className="text-base font-bold" style={{ color: text }}>Evidence Verification</h2>

      <div className="rounded-2xl p-6 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
        <div className="flex items-start gap-3">
          <span className="text-xl">🔐</span>
          <div>
            <div className="text-sm font-semibold mb-1" style={{ color: text }}>Verify Signed Evidence Envelope</div>
            <div className="text-xs leading-relaxed" style={{ color: muted }}>
              Paste any signed decision from an exported ZIP or API response.
              Ed25519 signature and SHA-256 hash verified independently — no database access needed.
            </div>
          </div>
        </div>

        <textarea
          value={raw} onChange={e => setRaw(e.target.value)}
          placeholder={'{\n  "schema_version": "gs-evidence-v1",\n  ...\n  "evidence_hash": "...",\n  "signature": "...",\n  "signing": { "algorithm": "Ed25519", "key_id": "..." }\n}'}
          className="w-full rounded-lg px-4 py-3 text-xs font-mono border outline-none resize-none"
          style={{ background: inputBg, borderColor: border, color: text, height: 200 }}
        />

        {error && (
          <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">✗ {error}</div>
        )}

        {result && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
            className="flex items-start gap-3 p-4 rounded-xl text-sm"
            style={{ background: result.valid ? '#22c55e14' : '#ef444414', border: `1px solid ${result.valid ? '#22c55e30' : '#ef444430'}` }}>
            <span className="text-xl">{result.valid ? '✅' : '❌'}</span>
            <div>
              <div className="font-bold mb-1" style={{ color: result.valid ? '#22c55e' : '#ef4444' }}>
                {result.valid ? 'VERIFIED ✓' : 'INVALID ✗'}
              </div>
              <div className="text-xs" style={{ color: muted }}>{result.reason}</div>
            </div>
          </motion.div>
        )}

        <button onClick={verify} disabled={loading}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm px-5 py-2.5 rounded-lg transition-all">
          {loading ? '⏳ Verifying…' : '🔐 Verify Signature'}
        </button>
      </div>

      <div className="rounded-2xl p-6 space-y-4" style={{ background: bg, border: `1px solid ${border}` }}>
        <div className="text-sm font-semibold" style={{ color: text }}>How Evidence Signing Works</div>
        {[
          ['01', 'Decision payload is canonically serialized (sorted keys, no whitespace)'],
          ['02', 'SHA-256 hash computed and stored in evidence_hash field'],
          ['03', 'Ed25519 private key signs the canonical bytes — stored in signature field'],
          ['04', 'Verification: reconstruct payload, recompute hash, verify signature via trust registry'],
        ].map(([step, desc]) => (
          <div key={step} className="flex items-start gap-3">
            <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded flex-shrink-0">{step}</span>
            <span className="text-xs leading-relaxed" style={{ color: muted }}>{desc}</span>
          </div>
        ))}
        <div className="bg-amber-500/8 border border-amber-500/20 rounded-lg p-3 text-xs" style={{ color: muted }}>
          <span className="text-amber-400 font-medium">Original source data is never overwritten.</span>{' '}
          Every harmonization decision is an independently verifiable proof of what changed, why, and who approved it.
        </div>
      </div>
    </div>
  );
}
