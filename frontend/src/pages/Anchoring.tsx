import { useState } from 'react';
import { triggerAnchor } from '../api/client';
import { ApiError, type AnchorResponse } from '../api/types';
import { HashChip } from '../components/Copyable';
import { ErrorBanner } from '../components/Feedback';
import { ExternalIcon } from '../components/icons';
import { Pill } from '../components/StatusBadge';
import { algorandExplorerUrl } from '../lib/format';

export function Anchoring() {
  const [batchSize, setBatchSize] = useState('10');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnchorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  const onAnchor = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    setNotConfigured(false);
    try {
      const size = Number(batchSize);
      const r = await triggerAnchor(Number.isFinite(size) && size > 0 ? size : undefined);
      setResult(r);
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) {
        setNotConfigured(true);
      } else {
        setError(e instanceof ApiError ? e.message : 'Anchoring request failed.');
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 760 }}>
        <h1 className="page-title">Anchoring</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 24, maxWidth: 620 }}>
          Verification records accumulate locally as <code className="mono">unanchored</code>. Anchoring batches
          them, builds a Merkle tree over their receipt hashes, and commits only the Merkle root to Algorand TestNet
          as a transaction note — never the receipts or payloads themselves.
        </p>

        <div className="bento stagger-children" style={{ marginBottom: 24 }}>
          {['Pending records', 'Merkle batch', 'Merkle root', 'Algorand transaction'].map((label, i, arr) => (
            <div className="span-3 card card-pad" key={label} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span className="mono" style={{ fontSize: 12, color: 'var(--text-faint)' }}>
                {i + 1}/{arr.length}
              </span>
              <span style={{ fontSize: 13.5, fontWeight: 600 }}>{label}</span>
            </div>
          ))}
        </div>

        <div className="card card-pad">
          <div className="field" style={{ maxWidth: 220 }}>
            <label className="field-label" htmlFor="batch">Batch size</label>
            <input id="batch" className="input" type="number" min={1} value={batchSize} onChange={(e) => setBatchSize(e.target.value)} />
            <div className="field-hint">Maximum unanchored records to include in this batch.</div>
          </div>

          <button type="button" className="btn btn-accent" onClick={onAnchor} disabled={running}>
            {running && <span className="spinner" />}
            {running ? 'Anchoring…' : 'Anchor pending records'}
          </button>
        </div>

        {notConfigured && (
          <div style={{ marginTop: 16 }}>
            <ErrorBanner
              title="Anchoring not configured"
              message="This backend doesn't have ANCHOR_PRIVATE_KEY set, so it can't submit Algorand transactions. This is a backend deployment setting, not something the frontend can fix."
            />
          </div>
        )}

        {error && (
          <div style={{ marginTop: 16 }}>
            <ErrorBanner title="Anchoring failed" message={error} />
          </div>
        )}

        {result && (
          <div className="card card-pad" style={{ marginTop: 20 }}>
            {result.status === 'no_records_to_anchor' ? (
              <>
                <Pill tone="pending">No records to anchor</Pill>
                <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginTop: 10 }}>
                  Every local verification record is already anchored, or none exist yet. Run a verification first.
                </p>
              </>
            ) : (
              <>
                <div className="copy-row" style={{ marginBottom: 14 }}>
                  <h3 style={{ fontSize: 18 }}>Batch anchored</h3>
                  <Pill tone="success">{result.status}</Pill>
                </div>
                <div className="kv-grid">
                  <div className="kv">
                    <span className="kv-label">Records in batch</span>
                    <span className="kv-value">{result.leaf_count}</span>
                  </div>
                  <div className="kv">
                    <span className="kv-label">Merkle root</span>
                    <HashChip value={result.merkle_root} head={14} tail={10} />
                  </div>
                  {result.transaction_id && (
                    <div className="kv">
                      <span className="kv-label">Algorand transaction</span>
                      <div className="copy-row" style={{ gap: 8 }}>
                        <HashChip value={result.transaction_id} />
                        <a className="icon-btn" href={algorandExplorerUrl(result.transaction_id)} target="_blank" rel="noreferrer" aria-label="View on Algorand explorer">
                          <ExternalIcon width={14} height={14} />
                        </a>
                      </div>
                    </div>
                  )}
                </div>
                <p style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 14 }}>
                  This root is a cryptographic commitment to every receipt hash in the batch — proof that each one
                  existed, unaltered, at anchoring time. No raw verification data was uploaded to Algorand.
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
