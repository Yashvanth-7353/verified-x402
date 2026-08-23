import { Fragment, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Guilloche, VerificationSeal } from '../components/VerificationSeal';
import { Reveal } from '../components/Reveal';
import { Typewriter } from '../components/Typewriter';
import { useParallax } from '../lib/useReveal';
import { useTilt } from '../lib/useTilt';
import { loadSessionLog } from '../lib/session';
import { relativeTime } from '../lib/format';
import {
  BoltIcon, PackageIcon, LinkIcon, PlugIcon, ClipboardIcon,
  ScanCheckIcon, WrenchIcon, RefreshIcon, StampIcon, AnchorGlyphIcon,
} from '../components/icons';

const STEPS = [
  {
    title: 'Validate',
    body: 'Schema, type, syntax, SQL-safety and privacy checks run locally — nothing leaves the device yet.',
    icon: ScanCheckIcon,
    tone: 'accent',
  },
  {
    title: 'Repair',
    body: 'Fixable issues are corrected by bounded, rule-based repair, or escalated to paid semantic repair if not.',
    icon: WrenchIcon,
    tone: 'seal',
  },
  {
    title: 'Re-validate',
    body: 'Every repair — deterministic or semantic — is run back through the same pipeline. Nothing is trusted blindly.',
    icon: RefreshIcon,
    tone: 'accent',
  },
  {
    title: 'Prove',
    body: 'A cryptographically bound, Ed25519-signed receipt is issued for every outcome — pass, repair, or reject.',
    icon: StampIcon,
    tone: 'accent-strong',
  },
  {
    title: 'Anchor',
    body: 'Receipts are batched into a Merkle tree; only the root is committed to Algorand — never the raw payload.',
    icon: AnchorGlyphIcon,
    tone: 'success',
  },
] as const;

const PIPE_TONE_VAR: Record<string, string> = {
  accent: 'var(--accent)',
  'accent-strong': 'var(--accent-strong)',
  seal: 'var(--seal)',
  success: 'var(--success)',
};

/** Animated connector between pipeline stages — a traveling signal pulse. */
function PipeLink({ color }: { color: string }) {
  return (
    <div className="pipe-link" aria-hidden="true">
      <svg width="48" height="24" viewBox="0 0 48 24" fill="none">
        <line x1="2" y1="12" x2="46" y2="12" stroke={color} strokeWidth="1.5" strokeDasharray="1 5.5" strokeLinecap="round" opacity="0.55" />
        <circle r="2.6" fill={color}>
          <animateMotion dur="1.6s" repeatCount="indefinite" path="M2,12 L46,12" />
          <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.85;1" dur="1.6s" repeatCount="indefinite" />
        </circle>
      </svg>
    </div>
  );
}

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
    body: "Semantic repair is never invoked without a settled x402 payment on Algorand, verified through the GoPlausible facilitator. The user signs the payment from their own Algorand wallet — no private key ever reaches the browser.",
    visual: 'ledger',
  },
  {
    eyebrow: 'Invariant 06',
    title: 'Proof outlives the request',
    body: 'Every receipt is Ed25519-signed and hash-bound. Batches are Merkle-anchored to Algorand, so tampering after the fact is provable, not just discouraged.',
    visual: 'chain',
  },
];

const USE_CASES = [
  { icon: BoltIcon, title: 'AI Financial Agent', body: 'Validates payment instructions before execution.', tone: 'accent' },
  { icon: PackageIcon, title: 'Procurement Agent', body: 'Verifies purchase orders for structural completeness.', tone: 'seal' },
  { icon: LinkIcon, title: 'Multi-Agent Systems', body: 'Provides a trust boundary between agents.', tone: 'success' },
  { icon: PlugIcon, title: 'AI API Execution', body: 'Validates API requests before they are sent.', tone: 'accent-strong' },
  { icon: ClipboardIcon, title: 'Auditable AI', body: 'Generates signed, timestamped receipts for decisions.', tone: 'warning' },
] as const;

const USE_CASE_TONE_VAR: Record<string, string> = {
  accent: 'var(--accent)',
  'accent-strong': 'var(--accent-strong)',
  seal: 'var(--seal)',
  success: 'var(--success)',
  warning: 'var(--warning)',
};

const TECH = [
  { label: 'FastAPI', desc: 'Backend API' },
  { label: 'SQLite', desc: 'Local persistence' },
  { label: 'Groq', desc: 'Semantic repair' },
  { label: 'x402', desc: 'Payment protocol' },
  { label: 'GoPlausible', desc: 'Payment facilitator' },
  { label: 'Ed25519', desc: 'Receipt signing' },
  { label: 'SHA-256', desc: 'Hashing' },
  { label: 'Merkle Tree', desc: 'Batch commitment' },
  { label: 'Algorand', desc: 'TestNet anchor' },
  { label: 'Pera Wallet', desc: 'Browser signing' },
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
          <div className="mono" style={{ opacity: 0.6 }}>wallet signs → GoPlausible settles</div>
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

export function Home() {
  const log = useMemo(() => loadSessionLog(), []);
  const [sealRef, sealOffset] = useParallax<HTMLDivElement>(0.06);
  const [guillocheRef, guillocheOffset] = useParallax<HTMLDivElement>(0.02);

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
        <div className="hero-particles">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="hero-particle"
              style={{
                width: 4 + (i % 4) * 2,
                height: 4 + (i % 4) * 2,
                top: `${10 + (i * 13) % 80}%`,
                left: `${5 + (i * 17) % 90}%`,
                animationDelay: `${-(i * 1.5)}s`,
              }}
            />
          ))}
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
                { text: 'Verify what AI produces.' },
              ]}
            />
            <p style={{ fontSize: 'var(--fs-md)', color: 'var(--text-muted)', maxWidth: 540, marginTop: 16 }}>
              A local-first verification layer that validates, repairs, re-validates, signs, persists, and anchors
              AI-generated outputs — so downstream systems never have to trust blindly.
            </p>
            <div style={{ marginTop: 12, minHeight: 24, fontSize: 'var(--fs-sm)', color: 'var(--text-faint)' }}>
              <Typewriter
                segments={[{ text: 'Cryptographically bound. Merkle anchored. Fails closed.' }]}
                speed={20}
                startDelay={2400}
              />
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 30, flexWrap: 'wrap' }}>
              <Link to="/verify" className="btn btn-accent">
                Verify an output →
              </Link>
              <Link to="/about" className="btn btn-ghost glass">
                How it works
              </Link>
            </div>
            <div className="trust-badges">
              <span className="trust-badge">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                Ed25519 Signed
              </span>
              <span className="trust-badge">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
                Algorand Anchored
              </span>
              <span className="trust-badge">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
                Fails Closed
              </span>
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
              position: 'relative',
            }}
          >
            <div className="seal-glow" />
            <VerificationSeal outcome="verified" size={140} />
          </div>
        </div>
      </section>

      {/* ---------- Feature rows ---------- */}
      <section className="container">
        <div className="feature-timeline">
          {FEATURES.map((f, i) => (
            <div className={`feature-row ${i % 2 ? 'reverse' : ''}`} key={f.title} style={{ position: 'relative' }}>
              <Reveal variant={i % 2 ? 'right' : 'left'}>
                <div style={{ position: 'relative' }}>
                  <div className="feature-number">0{i + 1}</div>
                  <span className="eyebrow">{f.eyebrow}</span>
                  <h2 style={{ fontSize: 'var(--fs-xl)', margin: '10px 0 12px' }}>{f.title}</h2>
                  <p style={{ fontSize: 'var(--fs-base)', color: 'var(--text-muted)', maxWidth: 460 }}>{f.body}</p>
                </div>
              </Reveal>
              <Reveal variant="scale" delay={100}>
                <FeatureVisual kind={f.visual} />
              </Reveal>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- Pipeline: no-scroll node diagram, live loop per stage ---------- */}
      <section className="container" style={{ marginTop: 24, marginBottom: 56 }}>
        <Reveal>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            The pipeline
          </div>
        </Reveal>
        <div className="pipeline-rail">
          {STEPS.map((s, i) => {
            const color = PIPE_TONE_VAR[s.tone];
            return (
              <Fragment key={s.title}>
                <Reveal delay={i * 70}>
                  <div className="pipe-node" style={{ ['--pipe-tone' as string]: color }}>
                    <div className="pipe-node-circle">
                      <span className="pipe-node-ring" style={{ animationDelay: `${i * 0.35}s` }} />
                      <s.icon width={22} height={22} />
                      <span className="pipe-node-index mono">{i + 1}</span>
                    </div>
                    <h3 className="pipe-node-title">{s.title}</h3>
                    <p className="pipe-node-body">{s.body}</p>
                  </div>
                </Reveal>
                {i < STEPS.length - 1 && <PipeLink color={color} />}
              </Fragment>
            );
          })}
        </div>
        <Reveal delay={STEPS.length * 70}>
          <div className="pipeline-quote">
            <p className="editorial-quote">"No valid proof, no execution."</p>
            <p className="pipeline-quote-sub">
              A downstream system checks the signature and output hash before it acts — every time.
            </p>
          </div>
        </Reveal>
      </section>

      {/* ---------- Technology stack: auto-scrolling marquee ---------- */}
      <section style={{ marginBottom: 56 }}>
        <Reveal>
          <div className="eyebrow container" style={{ marginBottom: 10 }}>Built with</div>
        </Reveal>
        <div className="marquee">
          <div className="marquee-track">
            {[...TECH, ...TECH].map((t, i) => (
              <div className="card card-pad" style={{ minWidth: 140, textAlign: 'center' }} key={`${t.label}-${i}`}>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'var(--grotesk)' }}>{t.label}</div>
                <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 2 }}>{t.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Use cases ---------- */}
      <section className="container" style={{ marginBottom: 56 }}>
        <Reveal>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Use cases</div>
        </Reveal>
        <div className="use-case-grid">
          {USE_CASES.map((uc, i) => {
            const color = USE_CASE_TONE_VAR[uc.tone];
            return (
              <Reveal key={uc.title} delay={i * 60}>
                <div className="card card-pad use-case-card" style={{ ['--uc-tone' as string]: color }}>
                  <div className="use-case-icon">
                    <span className="use-case-icon-ring" style={{ animationDelay: `${i * 0.4}s` }} />
                    <uc.icon width={19} height={19} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 14.5, marginBottom: 3 }}>{uc.title}</h3>
                    <p style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.4 }}>{uc.body}</p>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section className="container">
        <Reveal>
          <div className="cta-section">
            <div className="cta-guilloche" />
            <h2 style={{ fontSize: 'var(--fs-2xl)', marginBottom: 16 }}>Ready to verify your first output?</h2>
            <p style={{ fontSize: 'var(--fs-md)', color: 'var(--text-muted)', maxWidth: 500, margin: '0 auto 32px' }}>
              Drop in a schema, write a prompt, and see how Verified handles uncertain AI generations with cryptographically backed certainty.
            </p>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link to="/verify" className="btn btn-accent" style={{ padding: '14px 28px', fontSize: 16 }}>
                Start Verification
              </Link>
              <Link to="/about" className="btn btn-ghost" style={{ padding: '14px 28px', fontSize: 16, background: 'var(--glass-bg)' }}>
                Read the Docs
              </Link>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ---------- Session log ---------- */}
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
