import { Link } from 'react-router-dom';
import { Guilloche, VerificationSeal } from '../components/VerificationSeal';
import { Reveal } from '../components/Reveal';
import { Typewriter } from '../components/Typewriter';

const PRINCIPLES = [
  { title: 'Local-first', body: 'Validation, schema/type checks, and deterministic repair run entirely on-device before anything is sent anywhere.' },
  { title: 'Fail-closed', body: 'Any uncertainty, failure, or unresolved issue resolves to rejected — never a default "verified".' },
  { title: 'Payment-gated escalation', body: 'Semantic repair is never invoked without a settled x402 payment via the GoPlausible AVM facilitator on Algorand TestNet.' },
  { title: 'Verify after repair', body: 'A repaired candidate — deterministic or semantic — is never accepted until it passes the same validation pipeline again.' },
  { title: 'Cryptographic receipts', body: 'Every request produces exactly one Ed25519-signed, hash-bound receipt, regardless of outcome.' },
  { title: 'Tamper-evident anchoring', body: 'Only Merkle roots over batches of receipt hashes are committed to Algorand — never raw payloads.' },
];

const TECH_STACK = [
  {
    category: 'Frontend',
    items: [
      'React 19 + TypeScript',
      'Vite 8',
      'react-router-dom',
      'Pure CSS design system',
    ],
  },
  {
    category: 'Backend',
    items: [
      'FastAPI (Python)',
      'Pydantic validation',
      'SQLite persistence',
      'SHA-256 hashing',
    ],
  },
  {
    category: 'Verification',
    items: [
      'Deterministic validation engine',
      '4-stage validation pipeline',
      'Rule-based deterministic repair',
      'Groq semantic repair (openai/gpt-oss-20b)',
      'Mandatory re-validation after repair',
    ],
  },
  {
    category: 'Payment',
    items: [
      'x402 v2 protocol',
      'GoPlausible AVM Facilitator',
      'Algorand TestNet',
      'USDC (ASA 10458941)',
    ],
  },
  {
    category: 'Cryptography',
    items: [
      'Ed25519 receipt signing (PyNaCl)',
      'SHA-256 receipt hashing',
      'Independent public-key verification',
    ],
  },
  {
    category: 'Integrity',
    items: [
      'Binary Merkle tree',
      'Algorand TestNet anchoring',
      'Merkle inclusion proofs',
      'Tamper detection',
    ],
  },
];

const USE_CASES = [
  {
    title: 'AI Financial Agent',
    description: 'An AI agent generates a payment instruction. Verified validates the structure and semantics before execution, producing a signed receipt for auditability.',
  },
  {
    title: 'Procurement Agent',
    description: 'An AI creates a purchase order with required fields. Verified ensures structural completeness and semantic correctness before forwarding to procurement systems.',
  },
  {
    title: 'Multi-Agent Systems',
    description: 'One AI agent produces an output consumed by another. Verified provides a trust boundary — the consuming agent verifies before acting.',
  },
  {
    title: 'AI API Execution',
    description: 'An AI generates an API request. Verified validates the request structure against a schema before it is sent to external systems.',
  },
  {
    title: 'Auditable AI Decisions',
    description: 'When AI makes an important decision, Verified generates a signed, timestamped receipt that can later be independently verified — even years later.',
  },
];

const DISTINCTIONS = [
  {
    left: 'Validation',
    right: 'Semantic Repair',
    explanation: 'Validation checks structure and rules. Semantic repair uses an LLM to infer missing or incorrect values when rules alone cannot fix the output.',
  },
  {
    left: 'Groq (LLM)',
    right: 'Verification Engine',
    explanation: 'Groq generates a candidate repair. The verification engine independently re-validates that candidate. The LLM is never the final authority.',
  },
  {
    left: 'x402 Payment',
    right: 'Blockchain Anchoring',
    explanation: 'Payment settles a fee for semantic repair on Algorand TestNet. Anchoring commits receipt hashes to a Merkle tree rooted on Algorand. These are separate operations.',
  },
  {
    left: 'Receipt Signature',
    right: 'Merkle Proof',
    explanation: 'The Ed25519 signature proves a specific receipt is authentic and unmodified. The Merkle proof proves that receipt hash was included in an anchored batch.',
  },
  {
    left: 'SQLite Persistence',
    right: 'Algorand Anchoring',
    explanation: 'SQLite stores full records locally. Algorand stores only a Merkle root — a cryptographic commitment, not the data itself.',
  },
];

export function About() {
  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 860 }}>
        {/* Hero card */}
        <section className="card" style={{ position: 'relative', overflow: 'hidden', padding: '44px 32px', marginBottom: 32, display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
          <Guilloche />
          <VerificationSeal outcome="verified" size={96} />
          <div style={{ position: 'relative', maxWidth: 560 }}>
            <Typewriter as="h1" className="page-title" speed={26} startDelay={100} segments={[{ text: 'How Verified works' }]} />
            <p style={{ fontSize: 14.5, color: 'var(--text-muted)' }}>
              Verified is a verification layer for AI-agent structured output — JSON, SQL, or function-call
              arguments — that sits between an agent and whatever executes what it produced. It doesn't trust the
              agent, and it doesn't trust its own repairs either, until they're proven.
            </p>
          </div>
        </section>

        {/* Core principles */}
        <Reveal>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Core principles</div>
        </Reveal>
        <div className="bento" style={{ marginBottom: 40 }}>
          {PRINCIPLES.map((p, i) => (
            <Reveal key={p.title} delay={i * 60}>
              <div className="span-6 card card-pad">
                <h3 style={{ fontSize: 16, marginBottom: 6 }}>{p.title}</h3>
                <p style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* Architecture */}
        <Reveal>
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <div className="section-title">Architecture</div>
            <pre className="json-block" style={{ fontFamily: 'var(--mono)', lineHeight: 1.7, overflow: 'auto' }}>
{`Agent Output
    |
    v
Local Validation  (schema · type · syntax · SQL-safety · privacy)
    |
    +-- deterministic fix? --> Deterministic Repair --> Re-validate
    |
    +-- still blocked, eligible for escalation?
              |
              v
        x402 Payment Required  (HTTP 402)
              |
              v
        GoPlausible Facilitator  -->  Algorand TestNet (settle 1 USDC)
              |
              v
        Groq Semantic Repair  (openai/gpt-oss-20b)
              |
              v
        Re-validation  (same engine — LLM output is never trusted directly)
              |
              v
        Verification Receipt  (Ed25519-signed, SHA-256 hash-bound)
              |
              v
        SQLite Persistence  --batch-->  Merkle Tree  --root-->  Algorand Anchor
              |
              v
        Independent Verification  (public key only — no backend required)`}
            </pre>
          </div>
        </Reveal>

        {/* Important distinctions */}
        <Reveal>
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <div className="section-title">Important distinctions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {DISTINCTIONS.map((d) => (
                <div key={d.left} style={{ display: 'flex', gap: 14, flexDirection: 'column' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13.5 }}>
                    <span className="badge badge-accent">{d.left}</span>
                    <span style={{ color: 'var(--text-faint)' }}>≠</span>
                    <span className="badge badge-pending">{d.right}</span>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', marginLeft: 2 }}>{d.explanation}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        {/* Technology stack */}
        <Reveal>
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <div className="section-title">Technology stack</div>
            <div className="bento" style={{ gap: 14 }}>
              {TECH_STACK.map((section) => (
                <div key={section.category} className="span-4">
                  <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 6, color: 'var(--text-muted)' }}>{section.category}</h4>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {section.items.map((item) => (
                      <li key={item} style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
                        <span style={{ color: 'var(--accent-strong)', marginRight: 4 }}>•</span>{item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        {/* Semantic repair provider */}
        <Reveal>
          <div className="card card-pad" style={{ marginBottom: 24 }}>
            <div className="section-title">Semantic repair provider</div>
            <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 12 }}>
              For outputs that cannot be fixed by deterministic rules, Verified escalates to a semantic repair provider.
              The provider generates a <em>candidate</em> repair — this candidate is never trusted directly.
            </p>
            <div className="bento" style={{ gap: 12 }}>
              <div className="span-6 card" style={{ padding: '14px 16px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent-strong)', marginBottom: 4 }}>Production</div>
                <div style={{ fontSize: 13.5, fontWeight: 600 }}>GroqSemanticProvider</div>
                <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 2 }}>Model: openai/gpt-oss-20b · JSON structured output · Prompt-injection defenses</div>
              </div>
              <div className="span-6 card" style={{ padding: '14px 16px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-faint)', marginBottom: 4 }}>Tests & Offline Demo</div>
                <div style={{ fontSize: 13.5, fontWeight: 600 }}>MockSemanticProvider</div>
                <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 2 }}>Deterministic · No API key required · Used for unit tests and offline demo only</div>
              </div>
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 12 }}>
              In both cases, the candidate output passes through the same validation engine before acceptance.
              Payment success never implies verification success.
            </p>
          </div>
        </Reveal>

        {/* Use cases */}
        <Reveal>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Use cases</div>
        </Reveal>
        <div className="bento" style={{ marginBottom: 40 }}>
          {USE_CASES.map((uc, i) => (
            <Reveal key={uc.title} delay={i * 60}>
              <div className="span-6 card card-pad">
                <h3 style={{ fontSize: 15, marginBottom: 6 }}>{uc.title}</h3>
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{uc.description}</p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* CTA */}
        <Reveal>
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <Link to="/verify" className="btn btn-accent" style={{ padding: '14px 28px', fontSize: 15 }}>
              Try it now →
            </Link>
          </div>
        </Reveal>
      </div>
    </div>
  );
}
