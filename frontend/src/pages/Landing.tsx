import React, { useEffect, useRef, useState } from 'react';
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, HealthResponse } from '../api/client';

// ── Animated counter ──────────────────────────────────────────────────────────
function Counter({ target, suffix = '', duration = 2000 }: { target: number; suffix?: string; duration?: number }) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();
      const start = Date.now();
      const tick = () => {
        const p = Math.min(1, (Date.now() - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        setValue(Math.floor(eased * target));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.5 });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target, duration]);
  return <span ref={ref}>{value.toLocaleString()}{suffix}</span>;
}

// ── Rotating globe ────────────────────────────────────────────────────────────
function Globe() {
  return (
    <div className="relative w-80 h-80 flex items-center justify-center">
      {/* Outer glow */}
      <div className="absolute inset-0 rounded-full bg-brand-500/5 blur-3xl animate-pulse-glow" />

      {/* Main sphere */}
      <motion.div
        animate={{ rotateY: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        className="relative w-60 h-60"
      >
        <div className="absolute inset-0 rounded-full border border-brand-500/20 bg-gradient-to-br from-dark-400 to-dark-600">
          {/* Grid lines */}
          <svg className="absolute inset-0 w-full h-full opacity-20" viewBox="0 0 100 100">
            <defs>
              <radialGradient id="sphereGrad" cx="40%" cy="35%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#0c1118" stopOpacity="0" />
              </radialGradient>
            </defs>
            <circle cx="50" cy="50" r="49" fill="url(#sphereGrad)" />
            {[20, 35, 50, 65, 80].map(y => (
              <ellipse key={y} cx="50" cy={y} rx={Math.sqrt(2500 - Math.pow(y - 50, 2))} ry="3"
                fill="none" stroke="#3b82f6" strokeWidth="0.3" />
            ))}
            {[0, 30, 60, 90, 120, 150].map(a => (
              <ellipse key={a} cx="50" cy="50" rx="49" ry="15"
                fill="none" stroke="#3b82f6" strokeWidth="0.3"
                transform={`rotate(${a} 50 50)`} />
            ))}
          </svg>
        </div>
      </motion.div>

      {/* Orbiting rings */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
        className="absolute inset-0 rounded-full"
        style={{ border: '1px solid rgba(59,130,246,0.2)', transform: 'rotateX(75deg)' }}
      />
      <motion.div
        animate={{ rotate: -360 }}
        transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
        className="absolute rounded-full"
        style={{ width: '260px', height: '260px', border: '1px solid rgba(6,182,212,0.15)', transform: 'rotateX(70deg) rotateZ(45deg)' }}
      />

      {/* Floating parcel dots */}
      {[
        { angle: 0, color: '#3b82f6', delay: 0 },
        { angle: 72, color: '#22c55e', delay: 0.5 },
        { angle: 144, color: '#f59e0b', delay: 1 },
        { angle: 216, color: '#ef4444', delay: 1.5 },
        { angle: 288, color: '#8b5cf6', delay: 2 },
      ].map(({ angle, color, delay }) => {
        const r = 120;
        const x = 160 + r * Math.cos((angle * Math.PI) / 180);
        const y = 160 + r * Math.sin((angle * Math.PI) / 180);
        return (
          <motion.div
            key={angle}
            className="absolute w-3 h-3 rounded-full"
            style={{ left: x - 6, top: y - 6, backgroundColor: color, boxShadow: `0 0 8px ${color}` }}
            animate={{ scale: [1, 1.5, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 2, repeat: Infinity, delay }}
          />
        );
      })}
    </div>
  );
}

// ── Feature card ──────────────────────────────────────────────────────────────
function FeatureCard({ icon, title, description, color, delay }: {
  icon: string; title: string; description: string; color: string; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.6, delay }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="glass rounded-2xl p-6 card-glow group cursor-default relative overflow-hidden"
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{ background: `radial-gradient(600px at 50% 0%, ${color}10, transparent 60%)` }} />
      <div className="text-3xl mb-4">{icon}</div>
      <h3 className="text-base font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-gray-400 leading-relaxed">{description}</p>
      <div className="absolute bottom-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />
    </motion.div>
  );
}

// ── Main landing ──────────────────────────────────────────────────────────────
export default function Landing() {
  const navigate = useNavigate();
  const { scrollYProgress } = useScroll();
  const heroY = useTransform(scrollYProgress, [0, 0.3], [0, -80]);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthResponse>('/health'),
    refetchInterval: 10_000,
  });

  const isLive = health?.status === 'OPERATIONAL';

  const features = [
    { icon: '🔍', title: 'Provenance Intelligence', color: '#3b82f6', delay: 0,
      description: '4 datasets ≠ 4 independent observations. Our DAG engine traces lineages — Cadastral + Revenue sharing one origin counts as one observation, not two.' },
    { icon: '⚡', title: 'ML-Assisted Matching', color: '#22c55e', delay: 0.1,
      description: 'LightGBM reranker on 11 geospatial signals blended with deterministic scoring. Graceful fallback ensures it always works.' },
    { icon: '🌊', title: 'Ripple Validation', color: '#f59e0b', delay: 0.2,
      description: '93% confidence cannot override topology. We check every neighbor parcel, building, utility, and road ROW before any auto-approval.' },
    { icon: '🔐', title: 'Signed Evidence Chain', color: '#8b5cf6', delay: 0.3,
      description: 'Ed25519-signed decisions with SHA-256 manifests. Any government auditor can verify offline — no server call required.' },
    { icon: '🗺️', title: 'Multi-Format Ingestion', color: '#06b6d4', delay: 0.4,
      description: 'GeoJSON · Shapefile · GeoPackage · GeoParquet · CSV · GeoTIFF. 60+ schema aliases map Khasra_No, Property_ID, Parcel_ID → one canonical model.' },
    { icon: '⚖️', title: 'Human-in-the-Loop', color: '#ef4444', delay: 0.5,
      description: 'AI proposes. Spatial rules constrain. Humans decide ambiguous cases. Priority-scored review queue with field verification requests.' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen relative z-10"
    >
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-dark-200/30">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm">G</div>
            <span className="font-bold text-white">GeoSamanvay</span>
            <span className="text-gray-600 text-xs hidden sm:block">SIH26013</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 text-xs ${isLive ? 'text-green-400' : 'text-gray-500'}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
              {isLive ? 'System Online' : 'Checking…'}
            </div>
            <button onClick={() => navigate('/app')} className="btn-primary text-sm py-2 px-4">
              Open App →
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="min-h-screen flex flex-col items-center justify-center relative pt-16 overflow-hidden">
        {/* Background grid */}
        <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-100" />
        <div className="absolute inset-0 bg-radial-glow" />

        {/* Animated background circles */}
        <motion.div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl opacity-10 bg-brand-500"
          animate={{ scale: [1, 1.2, 1], x: [0, 20, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div className="absolute bottom-1/4 right-1/4 w-64 h-64 rounded-full blur-3xl opacity-10 bg-cyan-500"
          animate={{ scale: [1, 1.3, 1], x: [0, -20, 0] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        />

        <motion.div style={{ y: heroY }} className="relative z-10 max-w-6xl mx-auto px-6 flex flex-col lg:flex-row items-center gap-16">
          {/* Text */}
          <div className="flex-1 text-center lg:text-left">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-2 bg-brand-500/10 border border-brand-500/20 rounded-full px-4 py-1.5 text-xs text-brand-400 font-medium mb-6"
            >
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              Smart India Hackathon 2026 · PS26013 · Team Aikta
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 }}
              className="text-5xl lg:text-7xl font-black text-white mb-4 leading-tight"
            >
              <span className="gradient-text">GeoSamanvay</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-xl lg:text-2xl text-gray-300 font-medium mb-4"
            >
              Evidence-Aware Land Record Harmonization
            </motion.p>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="text-base text-gray-500 max-w-lg mb-8 leading-relaxed"
            >
              When government datasets disagree about the same parcel —
              GeoSamanvay reconciles the evidence, explains every conflict,
              and proposes the minimum safe change.
            </motion.p>

            {/* Problem preview */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="glass rounded-2xl p-4 mb-8 text-left max-w-lg"
            >
              <div className="text-xs text-gray-500 mb-3 font-medium uppercase tracking-wider">One parcel · Four records · No agreement</div>
              <div className="space-y-1.5">
                {[
                  { src: 'Cadastral 2019', area: '1,245 m²', badge: 'shared-origin', col: 'text-brand-400' },
                  { src: 'Revenue / RoR', area: '1,238 m²', badge: 'shared-origin', col: 'text-green-400' },
                  { src: 'Municipal GIS', area: '1,219 m²', badge: 'independent', col: 'text-amber-400' },
                  { src: 'Drone ORI 2024', area: '1,231 m²', badge: 'independent', col: 'text-cyan-400' },
                ].map(({ src, area, badge, col }) => (
                  <div key={src} className="flex items-center justify-between">
                    <span className={`text-xs font-medium ${col}`}>{src}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-white">{area}</span>
                      <span className={badge === 'independent' ? 'badge-ok' : 'badge-warn'}>{badge}</span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="flex flex-col sm:flex-row gap-3"
            >
              <button onClick={() => navigate('/app')} className="btn-primary text-base py-3 px-8 justify-center animated-border">
                Launch Application
              </button>
              <a href="/docs" target="_blank" className="btn-ghost text-base py-3 px-6 justify-center">
                API Docs →
              </a>
            </motion.div>
          </div>

          {/* Globe */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.3 }}
            className="animate-float"
          >
            <Globe />
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-gray-600"
        >
          <span className="text-xs tracking-widest uppercase">Scroll</span>
          <div className="w-px h-8 bg-gradient-to-b from-gray-600 to-transparent" />
        </motion.div>
      </section>

      {/* Stats */}
      <section className="py-20 relative z-10">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { value: 186, suffix: '', label: 'Tests Passing', color: '#22c55e' },
              { value: 463000, suffix: '×', label: 'Candidate Reduction', color: '#3b82f6' },
              { value: 16, suffix: '', label: 'Conflict Types', color: '#f59e0b' },
              { value: 8, suffix: '', label: 'Architecture Layers', color: '#8b5cf6' },
            ].map(({ value, suffix, label, color }) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                className="glass rounded-2xl p-6 text-center"
              >
                <div className="text-4xl font-black mb-1" style={{ color }}>
                  <Counter target={value} suffix={suffix} />
                </div>
                <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 relative z-10">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <div className="text-xs text-brand-400 font-bold uppercase tracking-widest mb-3">Why GeoSamanvay</div>
            <h2 className="text-3xl lg:text-4xl font-black text-white">Not just conflict detection.</h2>
            <p className="text-gray-400 mt-3 text-lg">Evidence-aware reconciliation with a full audit chain.</p>
          </motion.div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map(f => <FeatureCard key={f.title} {...f} />)}
          </div>
        </div>
      </section>

      {/* Pipeline diagram */}
      <section className="py-20 relative z-10">
        <div className="max-w-4xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-10"
          >
            <h2 className="text-2xl font-black text-white">The Reconciliation Pipeline</h2>
          </motion.div>
          <div className="flex flex-wrap justify-center gap-3 items-center">
            {[
              { label: 'INGEST', color: '#3b82f6' },
              { label: 'PROFILE', color: '#06b6d4' },
              { label: 'MATCH', color: '#22c55e' },
              { label: 'CONFLICT', color: '#f59e0b' },
              { label: 'PROPOSE', color: '#8b5cf6' },
              { label: 'RIPPLE', color: '#ef4444' },
              { label: 'REVIEW', color: '#22c55e' },
              { label: 'SIGN', color: '#06b6d4' },
            ].map(({ label, color }, i) => (
              <React.Fragment key={label}>
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.08 }}
                  className="glass rounded-lg px-4 py-2 text-xs font-bold uppercase tracking-widest"
                  style={{ color, borderColor: `${color}30` }}
                >
                  {label}
                </motion.div>
                {i < 7 && <span className="text-gray-700 text-lg">›</span>}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 relative z-10">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="glass rounded-3xl p-12 relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-radial-glow opacity-50" />
            <div className="relative z-10">
              <h2 className="text-3xl font-black text-white mb-4">
                Most systems store land data.<br />
                <span className="gradient-text">GeoSamanvay reconciles it.</span>
              </h2>
              <p className="text-gray-400 mb-8">
                Open the application, load the Ward 42 demo, and watch the system
                explain exactly why four records disagree — and what to do about it.
              </p>
              <button onClick={() => navigate('/app')} className="btn-primary text-lg py-4 px-10 mx-auto animated-border">
                Open GeoSamanvay →
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-dark-200/30 py-8 relative z-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-sm text-gray-600">GeoSamanvay · Team Aikta · SIH26013 · MIT License</div>
          <div className="flex items-center gap-6 text-xs text-gray-600">
            <a href="/docs" className="hover:text-brand-400 transition-colors">API Docs</a>
            <a href="https://github.com/manoj-1407/sih26013" target="_blank" className="hover:text-brand-400 transition-colors">GitHub</a>
            <span>v1.0.0</span>
          </div>
        </div>
      </footer>
    </motion.div>
  );
}
