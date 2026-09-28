import React, { Component, useEffect, useRef } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';

// ── Error boundary: catch any React crash and show a helpful screen ─────────
class ErrorBoundary extends Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          background: '#0a0f1a', color: '#e8edf5', padding: 32, fontFamily: 'monospace',
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: '#ef4444' }}>
            Something went wrong
          </div>
          <div style={{ fontSize: 12, color: '#6b7280', maxWidth: 600, textAlign: 'center', marginBottom: 24 }}>
            {this.state.error.message}
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={() => { this.setState({ error: null }); window.location.hash = '#/'; }}
              style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
            >
              Go to Landing
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{ background: '#1e2d42', color: '#e8edf5', border: '1px solid #243045', padding: '10px 20px', borderRadius: 8, cursor: 'pointer' }}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Minimal particle canvas ─────────────────────────────────────────────────
function Particles() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let W = canvas.width = window.innerWidth;
    let H = canvas.height = window.innerHeight;
    let animId: number;
    const pts = Array.from({ length: 50 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r: Math.random() * 1.2 + 0.4,
      a: Math.random() * 0.35 + 0.08,
    }));
    const onResize = () => { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; };
    window.addEventListener('resize', onResize);
    function draw() {
      ctx!.clearRect(0, 0, W, H);
      pts.forEach(p => {
        p.x = (p.x + p.vx + W) % W;
        p.y = (p.y + p.vy + H) % H;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(59,130,246,${p.a})`;
        ctx!.fill();
      });
      pts.forEach((a, i) => pts.slice(i + 1).forEach(b => {
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 110) {
          ctx!.beginPath();
          ctx!.moveTo(a.x, a.y);
          ctx!.lineTo(b.x, b.y);
          ctx!.strokeStyle = `rgba(59,130,246,${0.06 * (1 - d / 110)})`;
          ctx!.lineWidth = 0.5;
          ctx!.stroke();
        }
      }));
      animId = requestAnimationFrame(draw);
    }
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', onResize); };
  }, []);
  return (
    <canvas ref={ref} style={{
      position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
      width: '100vw', height: '100vh',
    }} />
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <Particles />
        <div style={{ position: 'relative', zIndex: 1 }}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/app/*" element={<Dashboard />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </ErrorBoundary>
    </ThemeProvider>
  );
}
