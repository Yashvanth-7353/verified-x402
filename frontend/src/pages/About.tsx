import type { CSSProperties } from 'react';
import { Guilloche, VerificationSeal } from '../components/VerificationSeal';
import { Typewriter } from '../components/Typewriter';

const PRINCIPLES = [
  { title: 'Local-first', body: 'Validation, schema/type checks, and deterministic repair run entirely on-device before anything is sent anywhere.' },
  { title: 'Fail-closed', body: 'Any uncertainty, failure, or unresolved issue resolves to rejected — never a default "verified".' },
  { title: 'Payment-gated escalation', body: 'Semantic repair is never invoked without a settled x402 payment via the GoPlausible AVM facilitator on Algorand.' },
  { title: 'Verify after repair', body: 'A repaired candidate — deterministic or semantic — is never accepted until it passes the same validation pipeline again.' },
  { title: 'Cryptographic receipts', body: 'Every request produces exactly one Ed25519-signed, hash-bound receipt, regardless of outcome.' },
  { title: 'Tamper-evident anchoring', body: 'Only Merkle roots over batches of receipt hashes are committed to Algorand — never raw payloads.' },
];

export function About() {
  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 860 }}>
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

        <div className="bento" style={{ marginBottom: 40 }}>
          {PRINCIPLES.map((p, i) => (
            <div key={p.title} className="span-6 card card-pad reveal" style={{ '--rd': `${i * 60}ms` } as CSSProperties}>
              <h3 style={{ fontSize: 16, marginBottom: 6 }}>{p.title}</h3>
              <p style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>{p.body}</p>
            </div>
          ))}
        </div>

        <div className="card card-pad">
          <div className="section-title">Architecture</div>
          <pre className="json-block" style={{ fontFamily: 'var(--mono)', lineHeight: 1.7 }}>
{`Agent
  |
  v
Local Validation  (schema, type, syntax, SQL-safety, privacy)
  |
  +-- issues? --> Deterministic Repair --> Re-validate
  |
  +-- still blocked, eligible --> x402 402 Payment Required
                                    |
                                    v
                          GoPlausible Facilitator --> Algorand TestNet (settle)
                                    |
                                    v
                          Semantic Repair Provider --> Re-validate
  |
  v
Verification Receipt (Ed25519-signed, hash-bound)
  |
  v
Local record store (SQLite)  --batch-->  Merkle Tree  --root-->  Algorand anchor`}
          </pre>
        </div>

        <div className="card card-pad" style={{ marginTop: 20 }}>
          <div className="section-title">What's real vs. MVP-scoped</div>
          <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 10 }}>
            The x402 payment flow, GoPlausible facilitator integration, Algorand settlement, receipt signing, SQLite
            persistence, Merkle tree construction, and Algorand anchoring are all real, working integrations — not
            mocked for demo purposes.
          </p>
          <p style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>
            The one intentionally-scoped placeholder is the semantic-repair provider itself
            (<code className="mono">MockSemanticProvider</code>) — a deterministic stand-in for an external LLM-based
            repair service, swappable behind the same interface without touching payment, validation, or receipt
            logic.
          </p>
        </div>
      </div>
    </div>
  );
}
