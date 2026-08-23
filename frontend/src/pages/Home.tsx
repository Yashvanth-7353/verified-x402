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

const prefersReducedMotion =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function FeatureVisual({ kind }: { kind: string }) {
  const { nodeRef, onMouseMove, onMouseLeave } = useTilt<HTMLDivElement>(6);
  const loop = !prefersReducedMotion;

  if (kind === 'seal-reject') {
    return (
      <div
        ref={nodeRef}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        className="feature-visual glass tilt-card"
        style={{ background: 'linear-gradient(160deg, var(--danger-bg), transparent)' }}
      >
        <svg width="118" height="118" viewBox="0 0 130 130" style={{ position: 'absolute' }} aria-hidden="true">
          <defs>
            <linearGradient id="radarFade" x1="0" y1="1" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--danger)" stopOpacity="0.32" />
              <stop offset="100%" stopColor="var(--danger)" stopOpacity="0" />
            </linearGradient>
            <clipPath id="radarClip">
              <circle cx="65" cy="65" r="58" />
            </clipPath>
          </defs>
          <circle cx="65" cy="65" r="58" fill="none" stroke="var(--danger-border)" strokeWidth="1" opacity="0.5" />
          <g clipPath="url(#radarClip)">
            <path d="M65,65 L65,7 A58,58 0 0,1 113,42 Z" fill="url(#radarFade)">
              {loop && (
                <animateTransform attributeName="transform" type="rotate" from="0 65 65" to="360 65 65" dur="3.4s" repeatCount="indefinite" />
              )}
            </path>
          </g>
        </svg>
        <VerificationSeal outcome="rejected" size={88} />
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
        style={{ background: 'linear-gradient(160deg, var(--seal-bg), transparent)' }}
      >
        <svg width="92%" viewBox="0 0 200 74" fill="none">
          <text x="20" y="14" fontSize="7.5" fontFamily="var(--mono)" fill="var(--seal-strong)">Wallet</text>
          <text x="82" y="14" fontSize="7.5" fontFamily="var(--mono)" fill="var(--seal-strong)">GoPlausible</text>
          <text x="166" y="14" fontSize="7.5" fontFamily="var(--mono)" fill="var(--seal-strong)">Repair</text>
          <line x1="20" y1="28" x2="180" y2="28" stroke="var(--seal-border)" strokeWidth="1.4" strokeDasharray="1 5" />
          {[20, 100, 180].map((cx) => (
            <circle key={cx} cx={cx} cy={28} r={6} fill="var(--seal-bg)" stroke="var(--seal-strong)" strokeWidth="1.6" />
          ))}
          {loop && (
            <circle r="3.2" fill="var(--seal)">
              <animateMotion dur="2.4s" repeatCount="indefinite" path="M20,28 L180,28" />
              <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.08;0.9;1" dur="2.4s" repeatCount="indefinite" />
            </circle>
          )}
          <text x="100" y="58" textAnchor="middle" fontSize="8" fontFamily="var(--mono)" fill="var(--success)">
            {loop && (
              <animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.75;0.86;0.97;1" dur="2.4s" repeatCount="indefinite" />
            )}
            settled → repair authorized
          </text>
        </svg>
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
      <svg width="80%" viewBox="0 0 200 90" fill="none">
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <rect x={10 + i * 46} y={16} width={34} height={34} rx={6} stroke="var(--accent-strong)" strokeWidth="2" fill="var(--accent-bg)">
              {loop && (
                <animate attributeName="stroke-opacity" values="1;0.3;1" keyTimes="0;0.5;1" dur="2.8s" begin={`${i * 0.35}s`} repeatCount="indefinite" />
              )}
            </rect>
            {i < 3 && (
              <line x1={44 + i * 46} y1={33} x2={56 + i * 46} y2={33} stroke="var(--accent-strong)" strokeWidth="2" strokeDasharray="2 4">
                {loop && <animate attributeName="stroke-dashoffset" values="0;-12" dur="1s" repeatCount="indefinite" />}
              </line>
            )}
          </g>
        ))}
        <text x="100" y="76" textAnchor="middle" fontSize="9" fill="var(--accent-strong)" fontFamily="var(--mono)">
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
            <Typewriter
              as="h1"
              startDelay={200}
              speed={26}
              className="hero-title"
              segments={[
                { text: 'Verify what ' },
                { text: 'AI', className: 'hero-title-ai' },
                { text: ' produces.' },
              ]}
            />
            <p style={{ fontSize: 'var(--fs-md)', color: 'var(--text-muted)', maxWidth: 540, marginTop: 16 }}>
              A local-first verification layer that validates, repairs, re-validates, signs, persists, and anchors
              AI-generated outputs — so downstream systems never have to trust blindly.
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
              position: 'relative',
            }}
          >
            <div className="seal-glow" />
            <VerificationSeal outcome="verified" size={140} />
          </div>
        </div>
      </section>

      {/* ---------- Invariants: compact 3-up grid, no stacked scroll ---------- */}
      <section className="container" style={{ marginBottom: 56 }}>
        <Reveal>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Invariants</div>
        </Reveal>
        <div className="invariant-grid">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 80}>
              <div className="invariant-card">
                <FeatureVisual kind={f.visual} />
                <div className="invariant-number mono">{f.eyebrow}</div>
                <h2 style={{ fontSize: 'var(--fs-lg)', margin: '8px 0 8px' }}>{f.title}</h2>
                <p style={{ fontSize: 15, color: 'var(--text-muted)', lineHeight: 1.5 }}>{f.body}</p>
              </div>
            </Reveal>
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
                      <s.icon width={26} height={26} />
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
              <div className="card card-pad" style={{ minWidth: 150, textAlign: 'center' }} key={`${t.label}-${i}`}>
                <div style={{ fontSize: 17, fontWeight: 700, fontFamily: 'var(--grotesk)' }}>{t.label}</div>
                <div style={{ fontSize: 13.5, color: 'var(--text-faint)', marginTop: 3 }}>{t.desc}</div>
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
                <div className="card card-pad use-case-card" style={{ ['--uc-tone' as string]: color, alignItems: 'center' }}>
                  <div className="use-case-icon">
                    <span className="use-case-icon-ring" style={{ animationDelay: `${i * 0.4}s` }} />
                    <uc.icon width={22} height={22} />
                  </div>
                  <h3 style={{ fontSize: 16 }}>{uc.title}</h3>
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
