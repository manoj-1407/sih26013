import { useState, useEffect, useCallback } from 'react';

export interface PingResult {
  latency: number | null;    // ms, null if offline
  status: 'online' | 'offline' | 'checking';
  lastChecked: Date | null;
}

export function usePing(intervalMs = 5000): PingResult {
  const [result, setResult] = useState<PingResult>({
    latency: null,
    status: 'checking',
    lastChecked: null,
  });

  const ping = useCallback(async () => {
    const start = performance.now();
    try {
      const res = await fetch('/api/v1/health', {
        method: 'GET',
        cache: 'no-store',
        signal: AbortSignal.timeout(4000),
      });
      const end = performance.now();
      if (res.ok) {
        setResult({ latency: Math.round(end - start), status: 'online', lastChecked: new Date() });
      } else {
        setResult({ latency: null, status: 'offline', lastChecked: new Date() });
      }
    } catch {
      setResult({ latency: null, status: 'offline', lastChecked: new Date() });
    }
  }, []);

  useEffect(() => {
    ping();
    const id = setInterval(ping, intervalMs);
    return () => clearInterval(id);
  }, [ping, intervalMs]);

  return result;
}
