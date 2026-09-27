import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Shield, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

export default function EvidencePanel() {
  const [raw, setRaw] = useState('');
  const [result, setResult] = useState<{ valid: boolean; reason: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
      <h2 className="text-base font-bold text-white">Evidence Verification</h2>

      <div className="glass rounded-2xl p-6 space-y-4">
        <div className="flex items-start gap-3">
          <Shield size={18} className="text-brand-400 mt-0.5 flex-shrink-0" />
          <div>
            <div className="text-sm font-semibold text-white mb-1">Verify Signed Evidence Envelope</div>
            <div className="text-xs text-gray-500 leading-relaxed">
              Paste any signed decision envelope from an exported ZIP or API response.
              The Ed25519 signature and SHA-256 hash are verified independently — no database access needed.
            </div>
          </div>
        </div>

        <textarea
          className="input-field font-mono text-xs h-56 resize-none"
          value={raw}
          onChange={e => setRaw(e.target.value)}
          placeholder={'{\n  "schema_version": "gs-evidence-v1",\n  "comparison_id": "DEC-...",\n  "decision": "APPROVED",\n  ...\n  "evidence_hash": "...",\n  "signature": "...",\n  "signing": { "algorithm": "Ed25519", "key_id": "..." }\n}'}
        />

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 rounded-lg p-3">
            <XCircle size={13} /> {error}
          </div>
        )}

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex items-start gap-3 p-4 rounded-xl text-sm ${result.valid ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'}`}
          >
            {result.valid
              ? <CheckCircle2 size={18} className="text-green-400 mt-0.5 flex-shrink-0" />
              : <XCircle size={18} className="text-red-400 mt-0.5 flex-shrink-0" />}
            <div>
              <div className={`font-bold mb-1 ${result.valid ? 'text-green-400' : 'text-red-400'}`}>
                {result.valid ? 'VERIFIED ✓' : 'INVALID ✗'}
              </div>
              <div className="text-xs text-gray-400">{result.reason}</div>
            </div>
          </motion.div>
        )}

        <button className="btn-primary" onClick={verify} disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Shield size={14} />}
          {loading ? 'Verifying…' : 'Verify Signature'}
        </button>
      </div>

      <div className="glass rounded-2xl p-6 space-y-4">
        <div className="text-sm font-semibold text-white">How It Works</div>
        <div className="space-y-3">
          {[
            { step: '01', text: 'Decision payload is canonically serialized (sorted keys, no whitespace)' },
            { step: '02', text: 'SHA-256 hash computed and stored in evidence_hash field' },
            { step: '03', text: 'Ed25519 private key signs the canonical bytes — signature stored' },
            { step: '04', text: 'Verification reconstructs payload, recomputes hash, verifies signature via trust registry' },
          ].map(({ step, text }) => (
            <div key={step} className="flex items-start gap-3">
              <span className="text-[10px] font-mono text-brand-400 bg-brand-500/10 px-2 py-1 rounded flex-shrink-0">{step}</span>
              <span className="text-xs text-gray-400 leading-relaxed">{text}</span>
            </div>
          ))}
        </div>
        <div className="bg-dark-600 rounded-lg p-3 text-xs text-gray-500 border border-dark-200/50">
          <span className="text-amber-400 font-medium">Original data is never overwritten.</span>{' '}
          Every decision is an independently verifiable proof of what changed, why, and who approved it.
        </div>
      </div>
    </div>
  );
}
