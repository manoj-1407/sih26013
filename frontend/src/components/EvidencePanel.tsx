import React, { useState } from 'react';
import { api } from '../api/client';

export default function EvidencePanel({ caseId }: { caseId: string | null }) {
  const [envelope, setEnvelope] = useState('');
  const [result, setResult] = useState<{ valid: boolean; reason: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function verify() {
    if (!envelope.trim()) { setError('Paste an evidence envelope'); return; }
    let parsed: unknown;
    try { parsed = JSON.parse(envelope); } catch { setError('Invalid JSON'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await api.post<{ valid: boolean; reason: string }>('/verify', { envelope: parsed });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Evidence Verification</h2>

      <div className="card mb-3">
        <div className="card-header">🔏 Verify Evidence Envelope</div>
        <div className="card-body flex-col gap-2">
          <p style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>
            Paste a signed evidence envelope (from an exported ZIP or API response)
            to cryptographically verify it hasn't been tampered with.
          </p>
          <div className="form-group">
            <label className="form-label">Evidence Envelope JSON</label>
            <textarea
              className="form-textarea"
              style={{ minHeight: 200 }}
              value={envelope}
              onChange={e => setEnvelope(e.target.value)}
              placeholder={'{\n  "schema_version": "gs-evidence-v1",\n  "comparison_id": "DEC-...",\n  ...\n  "evidence_hash": "...",\n  "signature": "...",\n  "signing": { "algorithm": "Ed25519", "key_id": "..." }\n}'}
            />
          </div>
          {error && <div className="notice notice-red">{error}</div>}
          {result && (
            <div className={`notice ${result.valid ? 'notice-green' : 'notice-red'}`}>
              {result.valid ? '✓ VERIFIED — ' : '✕ INVALID — '}{result.reason}
            </div>
          )}
          <button className="btn btn-primary btn-sm" onClick={verify} disabled={loading}>
            {loading ? 'Verifying…' : '🔏 Verify Signature'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">How Evidence Works</div>
        <div className="card-body flex-col gap-2" style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>
          <p>Every harmonization decision produces a signed evidence package:</p>
          <ol style={{ paddingLeft: 16 }}>
            <li>The decision payload is <strong>canonically serialized</strong> (sorted keys, no whitespace)</li>
            <li>A <strong>SHA-256 hash</strong> is computed and stored in <code style={{ fontFamily: 'var(--mono)' }}>evidence_hash</code></li>
            <li>An <strong>Ed25519 signature</strong> is computed over the canonical bytes and stored in <code style={{ fontFamily: 'var(--mono)' }}>signature</code></li>
            <li>Verification reconstructs the payload, recomputes the hash, and verifies the signature against the trust registry</li>
          </ol>
          <p style={{ marginTop: 8 }}>
            Original source data is <strong>never overwritten</strong> — the evidence package records why
            a specific harmonization was proposed and who approved it.
          </p>
        </div>
      </div>
    </div>
  );
}
