import React, { useState, useEffect } from 'react';
import { usePing } from '../../hooks/usePing';

function PingDot({ latency, status }: { latency: number | null; status: string }) {
  const color =
    status === 'offline'  ? '#ef4444' :
    status === 'checking' ? '#6b7280' :
    latency !== null && latency < 100 ? '#22c55e' :
    latency !== null && latency < 300 ? '#f59e0b' : '#f59e0b';

  return (
    <div style={{ display:'flex', alignItems:'center', gap:6 }}>
      <div style={{
        width:8, height:8, borderRadius:'50%', background:color,
        boxShadow: status === 'online' ? ('0 0 6px ' + color) : 'none',
        animation: status === 'online' ? 'pulseGlow 2s ease-in-out infinite' : undefined,
        flexShrink: 0,
      }} />
      <span style={{ fontSize:11, fontWeight:600, color }}>
        {status === 'checking' ? 'Connecting…' : status === 'offline' ? 'Offline' : 'Online'}
      </span>
      {status === 'online' && latency !== null && (
        <span style={{
          fontSize:10, fontFamily:'monospace',
          color: latency < 100 ? '#22c55e' : '#f59e0b',
          background:'rgba(255,255,255,0.05)',
          border:'1px solid rgba(255,255,255,0.1)',
          padding:'1px 6px', borderRadius:4,
        }}>
          {latency}ms
        </span>
      )}
    </div>
  );
}

function AutoRefreshRing({ intervalSec = 5 }: { intervalSec?: number }) {
  const [remaining, setRemaining] = useState(intervalSec);
  useEffect(() => {
    setRemaining(intervalSec);
    const id = setInterval(() => setRemaining(r => r <= 1 ? intervalSec : r - 1), 1000);
    return () => clearInterval(id);
  }, [intervalSec]);

  const circ = 2 * Math.PI * 5.5;
  const pct  = (intervalSec - remaining) / intervalSec;
  const dash = circ * pct;

  return (
    <div style={{ display:'flex', alignItems:'center', gap:5 }} title={'Auto-refreshes in ' + remaining + 's'}>
      <svg width={14} height={14} viewBox="0 0 14 14">
        <circle cx={7} cy={7} r={5.5} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={1.5} />
        <circle cx={7} cy={7} r={5.5} fill="none" stroke="#3b82f6" strokeWidth={1.5}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ - dash}
          transform="rotate(-90 7 7)"
          style={{ transition:'stroke-dashoffset 1s linear' }}
        />
      </svg>
      <span style={{ fontSize:10, color:'rgba(255,255,255,0.2)' }}>↺{remaining}s</span>
    </div>
  );
}

interface Props {
  isDark: boolean;
  version?: string;
  caseId?: string | null;
  refreshInterval?: number;
}

export default function StatusBar({ isDark, version, caseId, refreshInterval = 5 }: Props) {
  const ping = usePing(refreshInterval * 1000);
  const mt   = isDark ? '#6b7280' : '#94a3b8';
  const bd   = isDark ? 'rgba(30,45,66,0.5)' : 'rgba(0,0,0,0.06)';

  return (
    <div style={{ display:'flex', alignItems:'center', gap:14, height:'100%', paddingRight:4 }}>
      <PingDot latency={ping.latency} status={ping.status} />
      {ping.lastChecked && (
        <span style={{ fontSize:10, color:mt }}>{ping.lastChecked.toLocaleTimeString()}</span>
      )}
      <div style={{ width:1, height:12, background:bd }} />
      {caseId && <AutoRefreshRing intervalSec={refreshInterval} />}
      {caseId && <div style={{ width:1, height:12, background:bd }} />}
      <span style={{ fontSize:10, color:mt }}>v{version ?? '1.0.0'}</span>
    </div>
  );
}
