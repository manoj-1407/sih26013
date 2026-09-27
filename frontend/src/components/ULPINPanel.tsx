import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';

interface Props {
  caseId: string;
  parcelId: string;
  existingUlpin?: string;
}

export default function ULPINPanel({ caseId, parcelId, existingUlpin }: Props) {
  const qc = useQueryClient();
  const [stateCode, setStateCode] = useState('15');
  const [districtCode, setDistrictCode] = useState('42');
  const [talukaCode, setTalukaCode] = useState('001');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function generateULPIN() {
    setLoading(true); setError('');
    try {
      const res = await api.get<any>(
        `/cases/${caseId}/parcels/${parcelId}/ulpin?state_code=${stateCode}&district_code=${districtCode}&taluka_code=${talukaCode}`
      );
      setResult(res);
      qc.invalidateQueries({ queryKey: ['parcel-detail', caseId, parcelId] });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const ulpin = existingUlpin || result?.ulpin;

  return (
    <div className="card">
      <div className="card-header">🆔 ULPIN — Bhu-Aadhaar</div>
      <div className="card-body flex-col gap-2">
        {ulpin ? (
          <>
            <div style={{
              fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 800,
              letterSpacing: '0.12em', color: 'var(--cyan)', padding: '8px 0',
              textAlign: 'center',
            }}>
              {ulpin.match(/.{1,2}/g)?.join(' ') ?? ulpin}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text3)', textAlign: 'center' }}>
              14-digit Unique Land Parcel Identification Number (ULPIN / Bhu-Aadhaar)
            </div>
            {result && (
              <div className="kv" style={{ marginTop: 8 }}>
                <span className="kv-k">State</span>
                <span className="kv-v mono">{result.state_code}</span>
                <span className="kv-k">District</span>
                <span className="kv-v mono">{result.district_code}</span>
                <span className="kv-k">Taluka</span>
                <span className="kv-v mono">{result.taluka_code}</span>
                <span className="kv-k">Centroid</span>
                <span className="kv-v mono">
                  {result.centroid_lat?.toFixed(6)}°N, {result.centroid_lon?.toFixed(6)}°E
                </span>
                <span className="kv-k">Method</span>
                <span className="kv-v">{result.method}</span>
                <span className="kv-k">Status</span>
                <span className="kv-v">
                  <span className={`badge ${result.status === 'existing' ? 'badge-ok' : 'badge-info'}`}>
                    {result.status}
                  </span>
                </span>
              </div>
            )}
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
              "ULPIN identifies the parcel. GeoSamanvay reconciles the evidence describing that parcel."
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 8 }}>
              Generate a 14-digit ULPIN from this parcel's centroid coordinates
              per the DoLR Bhu-Aadhaar specification.
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <div className="form-group">
                <label className="form-label">State Code</label>
                <input className="form-input" value={stateCode} onChange={e => setStateCode(e.target.value)}
                  maxLength={2} style={{ fontFamily: 'var(--mono)' }} />
              </div>
              <div className="form-group">
                <label className="form-label">District</label>
                <input className="form-input" value={districtCode} onChange={e => setDistrictCode(e.target.value)}
                  maxLength={2} style={{ fontFamily: 'var(--mono)' }} />
              </div>
              <div className="form-group">
                <label className="form-label">Taluka</label>
                <input className="form-input" value={talukaCode} onChange={e => setTalukaCode(e.target.value)}
                  maxLength={3} style={{ fontFamily: 'var(--mono)' }} />
              </div>
            </div>
            {error && <div className="notice notice-red">{error}</div>}
            <button className="btn btn-primary btn-sm" onClick={generateULPIN} disabled={loading}>
              {loading ? 'Generating…' : '🆔 Generate ULPIN'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
