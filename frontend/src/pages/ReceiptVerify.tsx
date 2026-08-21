import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { publicKey as fetchPublicKey, verifyReceipt } from '../api/client';
import { ApiError, type PublicKeyResponse, type ReceiptVerifyResponse, type VerificationReceipt } from '../api/types';
import { HashChip } from '../components/Copyable';
import { ErrorBanner } from '../components/Feedback';
import { Pill } from '../components/StatusBadge';
import { CheckIcon, XIcon } from '../components/icons';

function tryParseReceipt(text: string): { ok: true; value: VerificationReceipt } | { ok: false; error: string } {
  try {
    const value = JSON.parse(text);
    if (!value || typeof value !== 'object' || !value.receipt_hash || !value.receipt_id) {
      return { ok: false, error: 'Not a recognizable receipt — missing receipt_id / receipt_hash.' };
    }
    return { ok: true, value };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Invalid JSON' };
  }
}

export function ReceiptVerify() {
  const location = useLocation();
  const stateReceipt = (location.state as { receipt?: VerificationReceipt } | null)?.receipt;

  const [text, setText] = useState(stateReceipt ? JSON.stringify(stateReceipt, null, 2) : '');
  const [pubKey, setPubKey] = useState<PublicKeyResponse | 'unavailable' | null>(null);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<ReceiptVerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPublicKey()
      .then(setPubKey)
      .catch(() => setPubKey('unavailable'));
  }, []);

  const parsed = tryParseReceipt(text);

  const onVerify = async () => {
    if (!parsed.ok) return;
    setChecking(true);
    setError(null);
    setResult(null);
    try {
      const r = await verifyReceipt(parsed.value);
      setResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not reach the Verified backend.');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 760 }}>
        <h1 className="page-title">Verify a receipt</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
          Independently check a receipt's Ed25519 signature and hash integrity — no private key needed, and this
          doesn't have to be a receipt Verified just issued to you.
        </p>

        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="section-title">Public verification key</div>
          {pubKey === null && <span className="skeleton" style={{ display: 'block', height: 20, width: 240 }} />}
          {pubKey === 'unavailable' && <Pill tone="pending">Receipt signing not configured on this backend</Pill>}
          {pubKey && pubKey !== 'unavailable' && (
            <div className="kv-grid">
              <div className="kv">
                <span className="kv-label">Algorithm</span>
                <span className="kv-value mono">{pubKey.algorithm}</span>
              </div>
              <div className="kv">
                <span className="kv-label">Key ID</span>
                <span className="kv-value mono">{pubKey.key_id}</span>
              </div>
              <div className="kv">
                <span className="kv-label">Public key</span>
                <HashChip value={pubKey.public_key} head={14} tail={10} />
              </div>
            </div>
          )}
        </div>

        <div className="card card-pad">
          <div className="field">
            <label className="field-label" htmlFor="receipt">Receipt JSON</label>
            <textarea
              id="receipt"
              className="input"
              style={{ minHeight: 260 }}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setResult(null);
              }}
              placeholder="Paste a VerificationReceipt JSON object here…"
              spellCheck={false}
            />
            {!parsed.ok && text.trim() && <div className="field-error">{parsed.error}</div>}
          </div>

          <button
            type="button"
            className="btn btn-accent"
            onClick={onVerify}
            disabled={!parsed.ok || checking}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {checking && <span className="spinner" />}
            {checking ? 'Verifying…' : 'Verify receipt'}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: 16 }}>
            <ErrorBanner title="Verification failed" message={error} />
          </div>
        )}

        {result && (
          <div
            className="card card-pad"
            style={{
              marginTop: 20,
              borderColor: result.valid ? 'var(--success-border)' : 'var(--danger-border)',
              background: result.valid ? 'var(--success-bg)' : 'var(--danger-bg)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              {result.valid ? <CheckIcon color="var(--success)" width={22} height={22} /> : <XIcon color="var(--danger)" width={22} height={22} />}
              <h3 style={{ fontSize: 18, color: result.valid ? 'var(--success)' : 'var(--danger)' }}>
                {result.valid ? 'Receipt is authentic' : 'Receipt is invalid'}
              </h3>
            </div>
            <div className="kv-grid" style={{ marginBottom: 12 }}>
              <div className="kv">
                <span className="kv-label">Signature</span>
                <span className="kv-value">{result.signature_valid ? 'Valid' : 'Invalid'}</span>
              </div>
              <div className="kv">
                <span className="kv-label">Receipt integrity</span>
                <span className="kv-value">{result.receipt_integrity_valid ? 'Valid' : 'Invalid'}</span>
              </div>
              <div className="kv">
                <span className="kv-label">Algorithm</span>
                <span className="kv-value mono">{result.algorithm}</span>
              </div>
            </div>
            <p style={{ fontSize: 13.5 }}>{result.details}</p>
          </div>
        )}
      </div>
    </div>
  );
}
