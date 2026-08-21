import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { health } from '../api/client';
import { Guilloche, VerificationSeal } from '../components/VerificationSeal';
import { Pill } from '../components/StatusBadge';
import { Reveal } from '../components/Reveal';
import { Typewriter } from '../components/Typewriter';
import { useParallax } from '../lib/useReveal';
import { useCountUp } from '../lib/useCountUp';
import { useTilt } from '../lib/useTilt';
import { loadSessionLog } from '../lib/session';
import { relativeTime } from '../lib/format';

const STEPS = [
  { title: 'Validate', body: 'Schema, type, syntax, SQL-safety and privacy checks run locally — nothing leaves the device yet.' },
  { title: 'Repair', body: 'Fixable issues are corrected by bounded, rule-based repair, or escalated to paid semantic repair if not.' },
  { title: 'Re-validate', body: 'Every repair — deterministic or semantic — is run back through the same pipeline. Nothing is trusted blindly.' },
  { title: 'Prove', body: 'A cryptographically bound, Ed25519-signed receipt is issued for every outcome — pass, repair, or reject.' },
  { title: 'Anchor', body: 'Receipts are batched into a Merkle tree; only the root is committed to Algorand — never the raw payload.' },
];

const FEATURES = [
  {
    eyebrow: 'Invariant 01',
    title: 'Fails closed, always',
    body: 'Uncertainty, timeout, or an unresolved finding resolves to rejected — never a default "verified". There is no code path that trusts an output by accident.',
    visual: 'seal-reject',
  },
  {
    eyebrow: 'Invariant 03',
    title: 'Escalation costs something real',
    body: "Semantic repair is never invoked without a settled x402 payment on Algorand, verified through the GoPlausible facilitator. Payment success never implies verification success.",
    visual: 'ledger',
  },
  {
    eyebrow: 'Invariant 06',
    title: 'Proof outlives the request',
    body: 'Every receipt is Ed25519-signed and hash-bound. Batches are Merkle-anchored to Algorand, so tampering after the fact is provable, not just discouraged.',
    visual: 'chain',
  },
];

const TICKER = [
  'FAIL-CLOSED', 'ED25519-SIGNED', 'PAYMENT-GATED', 'MERKLE-ANCHORED',
  'LOCAL-FIRST', 'RE-VALIDATED', 'TAMPER-EVIDENT', 'ALGORAND TESTNET',
];

function FeatureVisual({ kind }: { kind: string }) {
  const { nodeRef, onMouseMove, onMouseLeave } = useTilt<HTMLDivElement>(6);

  if (kind === 'seal-reject') {
    return (
      <div
        ref={nodeRef}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        className="feature-visual glass tilt-card"
        style={{ background: 'linear-gradient(160deg, var(--danger-bg), transparent)' }}
      >
        <VerificationSeal outcome="rejected" size={104} />
      </div>
    );
  }
  if (kind === 'ledger') {
    return (
      <div
        ref={nodeRef}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        className="feature-visual glass tilt-card"
        style={{ background: 'linear-gradient(160deg, var(--seal-bg), transparent)', padding: 20 }}
      >
        <div style={{ width: '100%', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--seal-strong)', lineHeight: 2 }}>
          <div>HTTP 402 · Payment Required</div>
          <div>scheme: exact · asset: USDC</div>
          <div className="mono" style={{ opacity: 0.6 }}>network: algorand:testnet…</div>
          <div style={{ color: 'var(--success)' }}>✓ settled → semantic repair authorized</div>
        </div>
      </div>
    );
  }
  return (
    <div
      ref={nodeRef}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className="feature-visual glass tilt-card"
      style={{ background: 'linear-gradient(160deg, var(--accent-bg), transparent)' }}
    >
      <svg width="70%" viewBox="0 0 200 120" fill="none">
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <rect x={10 + i * 46} y={40} width={34} height={34} rx={6} stroke="var(--accent-strong)" strokeWidth="2" />
            {i < 3 && <line x1={44 + i * 46} y1={57} x2={56 + i * 46} y2={57} stroke="var(--accent-strong)" strokeWidth="2" />}
          </g>
        ))}
        <text x="100" y="100" textAnchor="middle" fontSize="9" fill="var(--accent-strong)" fontFamily="var(--mono)">
          receipt hashes → Merkle root
        </text>
      </svg>
    </div>
  );
}

function StatCard({ label, value, hint, tone }: { label: string; value: number; hint: string; tone?: 'success' }) {
  const [ref, count] = useCountUp(value);
  return (
    <div ref={ref as never} className="card glass stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value poster-figure" style={{ fontSize: 32, color: tone === 'success' ? 'var(--success)' : undefined }}>
        {count}
      </span>
      <span className="field-hint">{hint}</span>
    </div>
  );
}

export function Home() {
  const [backendUp, setBackendUp] = useState<'checking' | 'up' | 'down'>('checking');
  const log = useMemo(() => loadSessionLog(), []);
  const [sealRef, sealOffset] = useParallax<HTMLDivElement>(0.06);
  const [guillocheRef, guillocheOffset] = useParallax<HTMLDivElement>(0.02);

  useEffect(() => {
    health()
      .then(() => setBackendUp('up'))
      .catch(() => setBackendUp('down'));
  }, []);

  const counts = useMemo(() => {
    const c = { total: log.length, verified: 0, repaired: 0, rejected: 0 };
    for (const e of log) {
      if (e.outcome === 'verified') c.verified++;
      else if (e.outcome === 'verified_repaired') c.repaired++;
      else c.rejected++;
    }
    return c;
  }, [log]);

  return (
    <div className="page-anim">
      {/* ---------- Hero ---------- */}
      <section
        style={{
          position: 'relative',
          overflow: 'hidden',
          padding: '148px 0 72px',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <div ref={guillocheRef} className="parallax" style={{ position: 'absolute', inset: 0, transform: `translateY(${guillocheOffset}px)` }}>
          <Guilloche />
        </div>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 40, flexWrap: 'wrap', position: 'relative' }}>
          <div style={{ maxWidth: 640 }}>
            <span className="eyebrow glass-pill glass" style={{ marginBottom: 18, display: 'inline-flex' }}>
              <Typewriter
                segments={[{ text: 'Local-first · fail-closed · on Algorand' }]}
                speed={22}
                startDelay={100}
              />
            </span>
            <Typewriter
              as="h1"
              startDelay={900}
              speed={26}
              className="hero-title"
              segments={[
                { text: 'A ' },
                { text: 'notary', className: 'display-italic' },
                { text: ' for what your agent just said it did.' },
              ]}
            />
            <p style={{ fontSize: 'var(--fs-md)', color: 'var(--text-muted)', maxWidth: 540, marginTop: 16 }}>
              Verified sits between an AI agent's structured output and whatever executes it. It validates, repairs,
              re-validates, and issues a signed, tamper-evident receipt — anchored to Algorand — before anything
              downstream is allowed to trust the result.
            </p>
            <div style={{ display: 'flex', gap: 12, marginTop: 30, flexWrap: 'wrap' }}>
              <Link to="/verify" className="btn btn-accent">
                Verify an output →
              </Link>
              <Link to="/about" className="btn btn-ghost glass">
                How it works
              </Link>
            </div>
          </div>
          <div
            ref={sealRef}
            className="parallax glass"
            style={{
              flexShrink: 0,
              borderRadius: '50%',
              padding: 28,
              transform: `translateY(${sealOffset}px)`,
            }}
          >
            <VerificationSeal outcome="verified" size={140} />
          </div>
        </div>
      </section>

      {/* ---------- Marquee ticker ---------- */}
      <div className="marquee">
        <div className="marquee-track">
          {[...TICKER, ...TICKER].map((item, i) => (
            <span className="marquee-item" key={i}>
              <span className="marquee-dot" />
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* ---------- Stat strip ---------- */}
      <section className="container" style={{ marginTop: 40, marginBottom: 8 }}>
        <div className="bento">
          <Reveal delay={0} className="span-4">
            <div className="card glass stat-card">
              <span className="stat-label">Backend</span>
              <span className="stat-value" style={{ fontSize: 20 }}>
                {backendUp === 'checking' ? 'Checking…' : backendUp === 'up' ? 'Reachable' : 'Unreachable'}
              </span>
              {backendUp !== 'checking' && (
                <Pill tone={backendUp === 'up' ? 'success' : 'danger'}>{backendUp === 'up' ? 'online' : 'offline'}</Pill>
              )}
              <span className="field-hint">Live check against GET /health</span>
            </div>
          </Reveal>
          <Reveal delay={80} className="span-4">
            <StatCard label="This session" value={counts.total} hint="Verifications submitted from this browser" />
          </Reveal>
          <Reveal delay={160} className="span-4">
            <StatCard label="Passed" value={counts.verified + counts.repaired} hint={`${counts.rejected} rejected, this session`} tone="success" />
          </Reveal>
        </div>
      </section>

      {/* ---------- Feature rows (varied, alternating layout) ---------- */}
      <section className="container">
        {FEATURES.map((f, i) => (
          <div className={`feature-row ${i % 2 ? 'reverse' : ''}`} key={f.title}>
            <Reveal variant={i % 2 ? 'right' : 'left'}>
              <span className="eyebrow">{f.eyebrow}</span>
              <h2 style={{ fontSize: 'var(--fs-xl)', margin: '10px 0 12px' }}>{f.title}</h2>
              <p style={{ fontSize: 'var(--fs-base)', color: 'var(--text-muted)', maxWidth: 460 }}>{f.body}</p>
            </Reveal>
            <Reveal variant="scale" delay={100}>
              <FeatureVisual kind={f.visual} />
            </Reveal>
          </div>
        ))}
      </section>

      {/* ---------- Pipeline: horizontal scroll-snap ---------- */}
      <section className="container" style={{ marginTop: 24, marginBottom: 56 }}>
        <Reveal>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            The pipeline
          </div>
        </Reveal>
        <div className="snap-strip">
          {STEPS.map((s, i) => (
            <Reveal key={s.title} delay={i * 70}>
              <div className="card glass card-pad" style={{ width: 260, height: '100%' }}>
                <span className="poster-figure" style={{ fontSize: 34, color: 'var(--accent-strong)' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <h3 style={{ fontSize: 'var(--fs-lg)', margin: '10px 0 8px' }}>{s.title}</h3>
                <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>{s.body}</p>
              </div>
            </Reveal>
          ))}
          <Reveal delay={STEPS.length * 70}>
            <div
              className="card card-pad"
              style={{
                width: 260,
                height: '100%',
                background: 'linear-gradient(160deg, var(--accent), var(--accent-strong))',
                color: '#fff',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
              }}
            >
              <p className="editorial-quote" style={{ color: '#fff', fontSize: 20, marginBottom: 8 }}>
                "No valid proof, no execution."
              </p>
              <p style={{ fontSize: 12.5, opacity: 0.85 }}>
                A downstream system checks the signature and output hash before it acts — every time.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {log.length > 0 && (
        <section className="container" style={{ marginBottom: 56 }}>
          <Reveal>
            <div className="copy-row" style={{ marginBottom: 12 }}>
              <div className="eyebrow" style={{ marginBottom: 0 }}>
                Recent, this session
              </div>
              <Link to="/history" className="btn btn-ghost btn-sm">
                View history
              </Link>
            </div>
          </Reveal>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {log.slice(0, 3).map((e, i) => (
              <Reveal key={e.receipt_id} delay={i * 60}>
                <Link
                  to="/history"
                  className="card glass"
                  style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', textDecoration: 'none', color: 'inherit' }}
                >
                  <span className="mono" style={{ fontSize: 13 }}>
                    {e.agent_identifier} · {e.request_id.slice(0, 8)}
                  </span>
                  <span style={{ fontSize: 12.5, color: 'var(--text-faint)' }}>{relativeTime(e.logged_at)}</span>
                </Link>
              </Reveal>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
