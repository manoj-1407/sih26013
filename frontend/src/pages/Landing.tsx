import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { api } from '../api/client';
import { useTheme } from '../context/ThemeContext';

function Counter({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);
  useEffect(() => {
    const el = ref.current; if (!el || started.current) return;
    const obs = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      started.current = true; obs.disconnect();
      const start = Date.now(); const dur = 1800;
      const tick = () => {
        const p = Math.min(1, (Date.now() - start) / dur);
        const e3 = 1 - Math.pow(1 - p, 3);
        setVal(Math.floor(e3 * target));
        if (p < 1) requestAnimationFrame(tick); else setVal(target);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    obs.observe(el); return () => obs.disconnect();
  }, [target]);
  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>;
}

function Globe() {
  return (
    <div className="relative flex items-center justify-center" style={{ width: 280, height: 280 }}>
      <div className="absolute inset-0 rounded-full"
        style={{ background: 'radial-gradient(ellipse,rgba(59,130,246,0.12),transparent 70%)', animation: 'pulseGlow 3s ease-in-out infinite' }} />
      <div className="absolute rounded-full border border-blue-500/20"
        style={{ width: 200, height: 200, background: 'radial-gradient(ellipse at 35% 35%,rgba(59,130,246,0.15),rgba(10,15,26,0.9))', animation: 'spinSlow 20s linear infinite' }}>
        <svg className="absolute inset-0 w-full h-full opacity-25" viewBox="0 0 100 100">
          {[20, 35, 50, 65, 80].map(y => (
            <ellipse key={y} cx="50" cy={y} rx={Math.sqrt(Math.max(0, 2500 - Math.pow(y - 50, 2)))} ry="3" fill="none" stroke="#3b82f6" strokeWidth="0.4" />
          ))}
          {[0, 36, 72, 108, 144].map(a => (
            <ellipse key={a} cx="50" cy="50" rx="49" ry="14" fill="none" stroke="#3b82f6" strokeWidth="0.3" transform={'rotate(' + a + ' 50 50)'} />
          ))}
        </svg>
      </div>
      <div className="absolute rounded-full border border-cyan-500/20"
        style={{ width: 240, height: 240, animation: 'spinReverse 12s linear infinite', transform: 'rotateX(72deg)' }} />
      {([
        { angle: 0,   color: '#3b82f6', delay: 0 },
        { angle: 72,  color: '#22c55e', delay: 0.6 },
        { angle: 144, color: '#f59e0b', delay: 1.2 },
        { angle: 216, color: '#ef4444', delay: 1.8 },
        { angle: 288, color: '#8b5cf6', delay: 2.4 },
      ] as const).map(({ angle, color, delay }) => {
        const r = 110;
        const x = 140 + r * Math.cos((angle * Math.PI) / 180);
        const y = 140 + r * Math.sin((angle * Math.PI) / 180);
        return (
          <div key={angle} className="absolute rounded-full"
            style={{ width: 10, height: 10, left: x - 5, top: y - 5, background: color,
              boxShadow: '0 0 8px ' + color, animation: 'dotPulse 2s ease-in-out ' + delay + 's infinite' }} />
        );
      })}
    </div>
  );
}

const FEATURES = [
  { icon: '🔗', title: 'Provenance Independence', color: '#3b82f6',
    desc: '4 datasets ≠ 4 independent observations. Our DAG traces lineages — Cadastral and Revenue from the same survey = 1 observation, not 2.' },
  { icon: '🤖', title: 'ML-Assisted Matching', color: '#22c55e',
    desc: 'LightGBM binary classifier on 11 geospatial signals. Graceful fallback to deterministic weighted scoring when model unavailable.' },
  { icon: '🌊', title: 'Ripple Validation', color: '#f59e0b',
    desc: '93% confidence cannot override topology. Every neighbor parcel, building, utility line, and road ROW checked before auto-approval.' },
  { icon: '🔐', title: 'Signed Evidence Chain', color: '#8b5cf6',
    desc: 'Ed25519-signed decisions with SHA-256 manifests. Any auditor can verify offline — no server call required.' },
  { icon: '🗺️', title: 'Multi-Format Ingestion', color: '#06b6d4',
    desc: 'GeoJSON · Shapefile · GeoPackage · GeoParquet · CSV · GeoTIFF. 60+ schema aliases map Khasra_No to canonical model.' },
  { icon: '👮', title: 'Human-in-the-Loop', color: '#ef4444',
    desc: 'AI proposes. Rules constrain. Humans decide. Priority-scored review queue with field verification requests.' },
];

const PIPELINE = [
  ['INGEST', '#3b82f6'], ['PROFILE', '#06b6d4'], ['MATCH', '#22c55e'],
  ['CONFLICT', '#f59e0b'], ['PROPOSE', '#8b5cf6'], ['RIPPLE', '#ef4444'],
  ['REVIEW', '#22c55e'], ['SIGN', '#06b6d4'],
];

const PROBLEM_ROWS = [
  { src: '📐 Cadastral', area: '1,245 m²', tag: 'SHARED ORIGIN', tc: '#f59e0b', sc: '#3b82f6' },
  { src: '📋 Revenue/RoR', area: '1,238 m²', tag: 'SHARED ORIGIN', tc: '#f59e0b', sc: '#22c55e' },
  { src: '🏙 Municipal', area: '1,219 m²', tag: 'INDEPENDENT', tc: '#22c55e', sc: '#f59e0b' },
  { src: '🚁 Drone 2024', area: '1,231 m²', tag: 'INDEPENDENT', tc: '#22c55e', sc: '#06b6d4' },
];

const STATS = [
  { n: 186, s: '', l: 'Tests Passing', c: '#22c55e' },
  { n: 463000, s: '×', l: 'Candidate Reduction', c: '#3b82f6' },
  { n: 16, s: '', l: 'Conflict Types', c: '#f59e0b' },
  { n: 8, s: '', l: 'Pipeline Layers', c: '#8b5cf6' },
];

export default function Landing() {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; version: string }>('/health'),
    refetchInterval: 15_000,
    retry: false,
  });
  const isLive = health?.status === 'OPERATIONAL';

  const bg     = isDark ? 'transparent'               : 'rgba(240,244,248,0.97)';
  const cardBg = isDark ? 'rgba(20,28,39,0.8)'        : 'rgba(255,255,255,0.95)';
  const bd     = isDark ? '#1e2d42'                   : '#e2e8f0';
  const tx     = isDark ? '#e8edf5'                   : '#1a202c';
  const mt     = isDark ? '#6b7280'                   : '#94a3b8';
  const gridc  = isDark ? 'rgba(59,130,246,0.04)'     : 'rgba(59,130,246,0.08)';

  return (
    <div style={{ minHeight: '100vh', color: tx, background: bg }}>
      <style>{`
        @keyframes spinSlow    { from{transform:rotateY(0deg)}to{transform:rotateY(360deg)} }
        @keyframes spinReverse { from{transform:rotateX(72deg) rotateZ(360deg)}to{transform:rotateX(72deg) rotateZ(0deg)} }
        @keyframes dotPulse    { 0%,100%{opacity:.5;transform:scale(1)}50%{opacity:1;transform:scale(1.5)} }
        @keyframes pulseGlow   { 0%,100%{opacity:.4}50%{opacity:1} }
        @keyframes floatUp     { 0%,100%{transform:translateY(0)}50%{transform:translateY(-18px)} }
      `}</style>

      {/* Nav */}
      <nav style={{ position:'fixed',top:0,left:0,right:0,zIndex:50,background:isDark?'rgba(10,15,26,0.9)':'rgba(255,255,255,0.9)',backdropFilter:'blur(12px)',borderBottom:'1px solid '+bd }}>
        <div style={{ maxWidth:1280,margin:'0 auto',padding:'0 24px',height:64,display:'flex',alignItems:'center',justifyContent:'space-between' }}>
          <div style={{ display:'flex',alignItems:'center',gap:12 }}>
            <div style={{ width:32,height:32,borderRadius:8,background:'#2563eb',display:'flex',alignItems:'center',justifyContent:'center',color:'#fff',fontWeight:700,fontSize:14 }}>G</div>
            <span style={{ fontWeight:700,color:tx }}>GeoSamanvay</span>
            <span style={{ fontSize:12,opacity:0.4,color:tx }}>SIH26013</span>
          </div>
          <div style={{ display:'flex',alignItems:'center',gap:12 }}>
            <div style={{ display:'flex',alignItems:'center',gap:6,fontSize:12,color:isLive?'#4ade80':'#6b7280' }}>
              <div style={{ width:6,height:6,borderRadius:'50%',background:isLive?'#4ade80':'#6b7280',animation:isLive?'pulseGlow 2s infinite':undefined }} />
              <span>{isLive ? ('v'+health?.version+' Online') : 'Connecting…'}</span>
            </div>
            <button onClick={toggleTheme}
              style={{ width:32,height:32,borderRadius:8,border:'1px solid '+bd,background:'transparent',cursor:'pointer',fontSize:16 }}>
              {isDark ? '☀️' : '🌙'}
            </button>
            <button onClick={() => navigate('/app')}
              style={{ background:'#2563eb',color:'#fff',border:'none',padding:'8px 18px',borderRadius:8,fontWeight:600,fontSize:14,cursor:'pointer' }}>
              Open App →
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section style={{ minHeight:'100vh',display:'flex',alignItems:'center',paddingTop:64,position:'relative',overflow:'hidden' }}>
        <div style={{ position:'absolute',inset:0,backgroundImage:'linear-gradient('+gridc+' 1px,transparent 1px),linear-gradient(90deg,'+gridc+' 1px,transparent 1px)',backgroundSize:'40px 40px',opacity:0.8 }} />
        <div style={{ maxWidth:1200,margin:'0 auto',padding:'80px 24px',display:'flex',flexWrap:'wrap',alignItems:'center',gap:48,position:'relative',zIndex:1 }}>

          {/* Text */}
          <div style={{ flex:'1 1 400px' }}>
            <motion.div initial={{ opacity:0,y:20 }} animate={{ opacity:1,y:0 }} transition={{ duration:0.5 }}>
              <div style={{ display:'inline-flex',alignItems:'center',gap:8,fontSize:12,fontWeight:600,padding:'6px 14px',borderRadius:999,marginBottom:24,background:'rgba(59,130,246,0.1)',border:'1px solid rgba(59,130,246,0.2)',color:'#60a5fa' }}>
                <span style={{ width:6,height:6,borderRadius:'50%',background:'#4ade80',display:'inline-block',animation:'pulseGlow 2s infinite' }} />
                Smart India Hackathon 2026 · PS26013 · Team Aikta
              </div>
            </motion.div>

            <motion.h1 initial={{ opacity:0,y:25 }} animate={{ opacity:1,y:0 }} transition={{ duration:0.6,delay:0.1 }}
              style={{ fontSize:56,fontWeight:900,marginBottom:16,lineHeight:1.1 }}>
              <span className="gradient-text">GeoSamanvay</span>
            </motion.h1>

            <motion.p initial={{ opacity:0,y:20 }} animate={{ opacity:1,y:0 }} transition={{ duration:0.5,delay:0.2 }}
              style={{ fontSize:20,fontWeight:600,marginBottom:12,opacity:0.8,color:tx }}>
              Evidence-Aware Land Record Harmonization
            </motion.p>

            <motion.p initial={{ opacity:0,y:20 }} animate={{ opacity:1,y:0 }} transition={{ duration:0.5,delay:0.3 }}
              style={{ fontSize:15,opacity:0.6,maxWidth:480,marginBottom:32,lineHeight:1.7,color:tx }}>
              When government datasets disagree about the same parcel — GeoSamanvay reconciles the evidence,
              explains every conflict, and proposes the minimum safe change without overwriting source data.
            </motion.p>

            {/* Problem card */}
            <motion.div initial={{ opacity:0,y:15 }} animate={{ opacity:1,y:0 }} transition={{ duration:0.5,delay:0.4 }}
              style={{ borderRadius:16,padding:16,marginBottom:32,maxWidth:480,background:cardBg,border:'1px solid '+bd }}>
              <div style={{ fontSize:11,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.1em',opacity:0.5,marginBottom:12,color:tx }}>
                One Parcel · Four Records · No Agreement
              </div>
              {PROBLEM_ROWS.map(({ src, area, tag, tc, sc }) => (
                <div key={src} style={{ display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8 }}>
                  <span style={{ fontSize:12,fontWeight:500,color:sc }}>{src}</span>
                  <div style={{ display:'flex',alignItems:'center',gap:8 }}>
                    <span style={{ fontSize:12,fontFamily:'monospace',fontWeight:700,color:tx }}>{area}</span>
                    <span style={{ fontSize:9,fontWeight:700,padding:'2px 6px',borderRadius:4,color:tc,background:tc+'18',border:'1px solid '+tc+'35' }}>{tag}</span>
                  </div>
                </div>
              ))}
            </motion.div>

            <motion.div initial={{ opacity:0,y:15 }} animate={{ opacity:1,y:0 }} transition={{ duration:0.5,delay:0.5 }}
              style={{ display:'flex',gap:12,flexWrap:'wrap' }}>
              <button onClick={() => navigate('/app')} className="animated-border"
                style={{ background:'#2563eb',color:'#fff',border:'none',padding:'14px 32px',borderRadius:12,fontWeight:700,fontSize:16,cursor:'pointer' }}>
                Launch Application
              </button>
              <a href="/docs" target="_blank"
                style={{ display:'inline-flex',alignItems:'center',padding:'14px 24px',borderRadius:12,fontWeight:600,fontSize:16,textDecoration:'none',color:tx,background:isDark?'rgba(255,255,255,0.06)':'rgba(0,0,0,0.06)',border:'1px solid '+bd }}>
                API Docs →
              </a>
            </motion.div>
          </div>

          {/* Globe */}
          <motion.div initial={{ opacity:0,scale:0.85 }} animate={{ opacity:1,scale:1 }} transition={{ duration:0.8,delay:0.3 }}
            style={{ flexShrink:0,animation:'floatUp 6s ease-in-out infinite' }}>
            <Globe />
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section style={{ padding:'64px 0' }}>
        <div style={{ maxWidth:960,margin:'0 auto',padding:'0 24px',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:16 }}>
          {STATS.map(({ n, s, l, c }) => (
            <motion.div key={l} initial={{ opacity:0,scale:0.9 }} whileInView={{ opacity:1,scale:1 }} viewport={{ once:true }}
              style={{ borderRadius:16,padding:20,textAlign:'center',background:cardBg,border:'1px solid '+bd }}>
              <div style={{ fontSize:32,fontWeight:900,marginBottom:4,color:c }}><Counter target={n} suffix={s} /></div>
              <div style={{ fontSize:10,textTransform:'uppercase',letterSpacing:'0.08em',opacity:0.5,color:tx }}>{l}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section style={{ padding:'64px 0' }}>
        <div style={{ maxWidth:1200,margin:'0 auto',padding:'0 24px' }}>
          <motion.div initial={{ opacity:0,y:20 }} whileInView={{ opacity:1,y:0 }} viewport={{ once:true }}
            style={{ textAlign:'center',marginBottom:48 }}>
            <div style={{ fontSize:11,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.12em',color:'#60a5fa',marginBottom:12 }}>Why GeoSamanvay</div>
            <h2 style={{ fontSize:32,fontWeight:900,color:tx,marginBottom:12 }}>Not just conflict detection.</h2>
            <p style={{ opacity:0.6,color:tx }}>Evidence-aware reconciliation with a complete audit chain.</p>
          </motion.div>
          <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(280px,1fr))',gap:16 }}>
            {FEATURES.map(({ icon, title, color, desc }, i) => (
              <motion.div key={title} initial={{ opacity:0,y:30 }} whileInView={{ opacity:1,y:0 }} viewport={{ once:true }} transition={{ delay:i*0.08 }}
                whileHover={{ y:-4 }}
                style={{ borderRadius:16,padding:24,background:cardBg,border:'1px solid '+bd,cursor:'default' }}>
                <div style={{ fontSize:28,marginBottom:16 }}>{icon}</div>
                <h3 style={{ fontSize:14,fontWeight:700,marginBottom:8,color }}>{title}</h3>
                <p style={{ fontSize:12,opacity:0.6,lineHeight:1.7,color:tx }}>{desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pipeline */}
      <section style={{ padding:'64px 0' }}>
        <div style={{ maxWidth:960,margin:'0 auto',padding:'0 24px' }}>
          <motion.div initial={{ opacity:0,y:20 }} whileInView={{ opacity:1,y:0 }} viewport={{ once:true }}
            style={{ textAlign:'center',marginBottom:32 }}>
            <h2 style={{ fontSize:24,fontWeight:900,color:tx }}>The Reconciliation Pipeline</h2>
          </motion.div>
          <div style={{ display:'flex',flexWrap:'wrap',gap:8,justifyContent:'center',alignItems:'center' }}>
            {PIPELINE.map(([label, color], i) => (
              <React.Fragment key={label}>
                <motion.div initial={{ opacity:0,scale:0.8 }} whileInView={{ opacity:1,scale:1 }} viewport={{ once:true }} transition={{ delay:i*0.07 }}
                  style={{ padding:'7px 14px',borderRadius:8,fontSize:11,fontWeight:700,textTransform:'uppercase',letterSpacing:'0.05em',background:cardBg,border:'1px solid '+color+'30',color }}>
                  {label}
                </motion.div>
                {i < PIPELINE.length - 1 && <span style={{ opacity:0.3,fontSize:18,color:tx }}>›</span>}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding:'80px 0' }}>
        <div style={{ maxWidth:700,margin:'0 auto',padding:'0 24px',textAlign:'center' }}>
          <motion.div initial={{ opacity:0,y:30 }} whileInView={{ opacity:1,y:0 }} viewport={{ once:true }}
            style={{ borderRadius:24,padding:'48px 48px',position:'relative',overflow:'hidden',background:cardBg,border:'1px solid '+bd }}>
            <div style={{ position:'absolute',inset:0,background:'radial-gradient(ellipse,rgba(59,130,246,0.12),transparent 70%)',opacity:0.5 }} />
            <div style={{ position:'relative',zIndex:1 }}>
              <h2 style={{ fontSize:28,fontWeight:900,color:tx,marginBottom:16 }}>
                Most systems store land data.<br />
                <span className="gradient-text">GeoSamanvay reconciles it.</span>
              </h2>
              <p style={{ opacity:0.6,marginBottom:32,color:tx,fontSize:15 }}>
                Load the Ward 42 demo, watch the system explain four conflicting records,
                and see why 93% confidence still gets blocked by the ripple check.
              </p>
              <button onClick={() => navigate('/app')} className="animated-border"
                style={{ background:'#2563eb',color:'#fff',border:'none',padding:'16px 40px',borderRadius:14,fontWeight:700,fontSize:18,cursor:'pointer',display:'inline-block' }}>
                Open GeoSamanvay →
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop:'1px solid '+bd,padding:'32px 24px' }}>
        <div style={{ maxWidth:1200,margin:'0 auto',display:'flex',flexWrap:'wrap',alignItems:'center',justifyContent:'space-between',gap:16 }}>
          <div style={{ fontSize:14,opacity:0.4,color:tx }}>GeoSamanvay · Team Aikta · SIH26013 · MIT</div>
          <div style={{ display:'flex',gap:24,fontSize:12,opacity:0.4,color:tx }}>
            <a href="/docs" style={{ color:tx,textDecoration:'none' }}>API Docs</a>
            <a href="https://github.com/manoj-1407/sih26013" target="_blank" style={{ color:tx,textDecoration:'none' }}>GitHub</a>
            <span>{health?.version ?? '1.0.0'}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
