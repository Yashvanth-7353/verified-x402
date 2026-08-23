import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { verify } from '../api/client';
import { ApiError } from '../api/types';
import { ErrorBanner } from '../components/Feedback';
import { Reveal } from '../components/Reveal';
import { Typewriter } from '../components/Typewriter';
import { EXAMPLES } from '../lib/examples';

function tryParse(text: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  try {
    const value = JSON.parse(text);
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      return { ok: false, error: 'Must be a JSON object' };
    }
    return { ok: true, value };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Invalid JSON' };
  }
}

export function Verify() {
  const navigate = useNavigate();
  const [agentIdentifier, setAgentIdentifier] = useState('demo-agent');
  const [outputType, setOutputType] = useState<'json' | 'sql' | 'function_call_args'>('json');
  const [schemaRef, setSchemaRef] = useState('invoice.v1');
  const [schemaVersion, setSchemaVersion] = useState('1.0');
  const [privacyPolicyRef, setPrivacyPolicyRef] = useState('default');
  const [payloadText, setPayloadText] = useState(() => JSON.stringify(EXAMPLES[0].payload, null, 2));
  const [schemaText, setSchemaText] = useState(() => JSON.stringify(EXAMPLES[0].schemaDefinition, null, 2));
  const [showPolicy, setShowPolicy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedExample, setSelectedExample] = useState<string | null>(EXAMPLES[0].id);

  const applyExample = (id: string) => {
    const ex = EXAMPLES.find((e) => e.id === id);
    if (!ex) return;
    setSelectedExample(id);
    setOutputType(ex.outputType);
    setSchemaRef(ex.schemaRef);
    setSchemaVersion(ex.schemaVersion);
    setPayloadText(JSON.stringify(ex.payload, null, 2));
    setSchemaText(JSON.stringify(ex.schemaDefinition, null, 2));
    setError(null);
  };

  const payloadParsed = tryParse(payloadText);
  const schemaParsed = tryParse(schemaText);

  const onSubmit = async () => {
    if (!payloadParsed.ok) {
      setError(`Output payload: ${payloadParsed.error}`);
      return;
    }
    if (!schemaParsed.ok) {
      setError(`Schema definition: ${schemaParsed.error}`);
      return;
    }
    setError(null);
    setSubmitting(true);

    const request = {
      request_id: crypto.randomUUID(),
      submitted_at: new Date().toISOString(),
      output_type: outputType,
      output_payload: payloadParsed.value,
      schema_ref: schemaRef,
      agent_identifier: agentIdentifier,
    };
    const activeExample = EXAMPLES.find((e) => e.id === selectedExample);
    const policy = {
      schema_id: crypto.randomUUID(),
      version: schemaVersion,
      output_type: outputType,
      schema_definition: schemaParsed.value,
      privacy_policy_ref: privacyPolicyRef,
      ...(activeExample?.businessRules ? { business_rules: activeExample.businessRules } : {}),
    };

    try {
      const response = await verify({ request, policy });
      navigate('/result', { state: { request, policy, response } });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Could not reach the Verified backend.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 780 }}>
        <Typewriter as="h1" className="page-title" speed={30} startDelay={80} segments={[{ text: 'Verify an output' }]} />
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
          Submit a structured output and the schema it's meant to satisfy. Verified runs it through local validation
          immediately — no payment required for this step.
        </p>

        <div className="section-title">Try a real scenario</div>
        <p style={{ color: 'var(--text-faint)', fontSize: 13, marginBottom: 14 }}>
          See how Verified handles correct outputs, deterministic fixes,
          and repairs that require semantic reasoning.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12, marginBottom: 28 }}>
          {EXAMPLES.map((ex) => {
            const isActive = selectedExample === ex.id;
            const indicatorColor = ex.indicator === 'pass' ? 'var(--success)' : ex.indicator === 'warn' ? 'var(--warning)' : 'var(--danger)';
            const categoryBg = ex.category === 'VALID'
              ? 'rgba(34,197,94,0.12)' : ex.category === 'DETERMINISTIC'
                ? 'rgba(251,191,36,0.12)' : 'rgba(168,85,247,0.12)';
            const categoryColor = ex.category === 'VALID'
              ? 'var(--success)' : ex.category === 'DETERMINISTIC'
                ? 'var(--warning)' : 'rgba(168,85,247,1)';
            return (
              <button
                key={ex.id}
                type="button"
                onClick={() => applyExample(ex.id)}
                className="glass"
                style={{
                  textAlign: 'left', padding: '14px 16px', borderRadius: 12,
                  border: `1.5px solid ${isActive ? indicatorColor : 'rgba(255,255,255,0.10)'}`,
                  background: isActive ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.03)',
                  cursor: 'pointer', transition: 'border-color 200ms, background 200ms',
                  display: 'flex', flexDirection: 'column', gap: 8,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ fontSize: 13.5, fontWeight: 700, fontFamily: 'var(--grotesk)', color: 'var(--text)' }}>{ex.label}</span>
                  <span style={{
                    fontSize: 10.5, fontWeight: 700, fontFamily: 'var(--grotesk)',
                    color: categoryColor, background: categoryBg,
                    padding: '2px 8px', borderRadius: 6, letterSpacing: '0.04em',
                    whiteSpace: 'nowrap',
                  }}>{ex.category}</span>
                </div>
                <div style={{ fontSize: 12.5, color: 'var(--text-faint)', lineHeight: 1.45 }}>{ex.description}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontStyle: 'italic', marginTop: 'auto' }}>{ex.hint}</div>
              </button>
            );
          })}
        </div>

        <Reveal variant="scale" className="card card-pad">
          <div className="field">
            <label className="field-label" htmlFor="agent">Agent identifier</label>
            <input id="agent" className="input" value={agentIdentifier} onChange={(e) => setAgentIdentifier(e.target.value)} />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="type">Output type</label>
            <select
              id="type"
              className="input"
              value={outputType}
              onChange={(e) => setOutputType(e.target.value as typeof outputType)}
            >
              <option value="json">json</option>
              <option value="sql">sql</option>
              <option value="function_call_args">function_call_args</option>
            </select>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="payload">Output payload</label>
            <textarea
              id="payload"
              className="input"
              value={payloadText}
              onChange={(e) => setPayloadText(e.target.value)}
              spellCheck={false}
            />
            {!payloadParsed.ok && <div className="field-error">{payloadParsed.error}</div>}
          </div>

          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowPolicy((v) => !v)}
            style={{ marginBottom: showPolicy ? 16 : 0 }}
          >
            {showPolicy ? 'Hide' : 'Show'} validation policy
          </button>

          {showPolicy && (
            <>
              <div className="field">
                <label className="field-label" htmlFor="schemaRef">Schema ref</label>
                <input id="schemaRef" className="input" value={schemaRef} onChange={(e) => setSchemaRef(e.target.value)} />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="schemaVersion">Version</label>
                <input id="schemaVersion" className="input" value={schemaVersion} onChange={(e) => setSchemaVersion(e.target.value)} />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="privacy">Privacy policy ref</label>
                <input id="privacy" className="input" value={privacyPolicyRef} onChange={(e) => setPrivacyPolicyRef(e.target.value)} />
              </div>
              <div className="field">
                <label className="field-label" htmlFor="schemaDef">Schema definition (JSON Schema)</label>
                <textarea
                  id="schemaDef"
                  className="input"
                  value={schemaText}
                  onChange={(e) => setSchemaText(e.target.value)}
                  spellCheck={false}
                />
                {!schemaParsed.ok && <div className="field-error">{schemaParsed.error}</div>}
              </div>
            </>
          )}

          {error && (
            <div style={{ marginBottom: 16 }}>
              <ErrorBanner title="Couldn't verify" message={error} />
            </div>
          )}

          <button type="button" className="btn btn-accent" onClick={onSubmit} disabled={submitting} style={{ width: '100%', justifyContent: 'center' }}>
            {submitting && <span className="spinner" />}
            {submitting ? 'Validating…' : 'Verify output'}
          </button>
        </Reveal>
      </div>
    </div>
  );
}
