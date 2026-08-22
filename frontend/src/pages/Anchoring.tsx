import { useEffect, useState } from 'react';
import { triggerAnchor, getMerkleProof, listRecords } from '../api/client';
import { ApiError, type AnchorResponse, type MerkleProofResponse, type RecordSummary } from '../api/types';
import { HashChip } from '../components/Copyable';
import { ErrorBanner } from '../components/Feedback';
import { ExternalIcon } from '../components/icons';
import { Pill } from '../components/StatusBadge';
import { algorandExplorerUrl, formatDateTime } from '../lib/format';

export function Anchoring() {
  const [batchSize, setBatchSize] = useState('10');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AnchorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  // Server records for proof generation
  const [anchoredRecords, setAnchoredRecords] = useState<RecordSummary[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<string | null>(null);
  const [proofResult, setProofResult] = useState<MerkleProofResponse | null>(null);
  const [proofLoading, setProofLoading] = useState(false);
  const [proofError, setProofError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setRecordsLoading(true);
      try {
        const res = await listRecords(0, 200);
        if (!cancelled) {
          setAnchoredRecords(res.records.filter((r) => r.anchoring_status === 'anchored'));
        }
      } catch {
        // Non-critical — proof UI just won't show
      } finally {
        if (!cancelled) setRecordsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  const onAnchor = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    setNotConfigured(false);
    try {
      const size = Number(batchSize);
      const r = await triggerAnchor(Number.isFinite(size) && size > 0 ? size : undefined);
      setResult(r);
      // Refresh anchored records after anchoring
      try {
        const res = await listRecords(0, 200);
        setAnchoredRecords(res.records.filter((r) => r.anchoring_status === 'anchored'));
      } catch { /* non-critical */ }
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

  const onGenerateProof = async (recordId: string) => {
    setSelectedRecord(recordId);
    setProofLoading(true);
    setProofError(null);
    setProofResult(null);
    try {
      const proof = await getMerkleProof(recordId);
      setProofResult(proof);
    } catch (e) {
      setProofError(e instanceof ApiError ? e.message : 'Failed to generate Merkle proof.');
    } finally {
      setProofLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 860 }}>
        <h1 className="page-title">Anchoring</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 24, maxWidth: 620 }}>
          Verification records accumulate locally as <code className="mono">unanchored</code>. Anchoring batches
          them, builds a Merkle tree over their receipt hashes, and commits only the Merkle root to Algorand TestNet
          as a transaction note — never the receipts or payloads themselves.
        </p>

        {/* Pipeline overview */}
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

        {/* Anchoring trigger */}
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
              message="This backend doesn't have an Algorand anchor account configured, so it can't submit anchor transactions. This is a backend deployment setting — check that the ANCHOR_PRIVATE_KEY environment variable is set."
            />
          </div>
        )}

        {error && (
          <div style={{ marginTop: 16 }}>
            <ErrorBanner title="Anchoring failed" message={error} />
          </div>
        )}

        {/* Anchoring result */}
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

        {/* Merkle inclusion proof section */}
        <div style={{ marginTop: 28 }}>
          <h2 style={{ fontSize: 'var(--fs-lg)', marginBottom: 8 }}>Merkle Inclusion Proof</h2>
          <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 16 }}>
            Select an anchored record to generate its Merkle inclusion proof — cryptographic evidence that
            this receipt hash was part of the anchored batch.
          </p>

          {recordsLoading && (
            <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span className="spinner spinner-dark" />
              <span style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>Loading anchored records…</span>
            </div>
          )}

          {!recordsLoading && anchoredRecords.length === 0 && (
            <div className="card card-pad" style={{ color: 'var(--text-faint)', fontSize: 13.5 }}>
              No anchored records found. Anchor a batch first.
            </div>
          )}

          {!recordsLoading && anchoredRecords.length > 0 && (
            <div className="card" style={{ overflowX: 'auto', marginBottom: 16 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    {['Receipt', 'Outcome', 'Anchored', 'Action'].map((h) => (
                      <th key={h} style={{ padding: '10px 16px', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-faint)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {anchoredRecords.slice(0, 20).map((r) => (
                    <tr
                      key={r.record_id}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        background: selectedRecord === r.record_id ? 'var(--accent-bg)' : undefined,
                      }}
                    >
                      <td style={{ padding: '10px 16px' }}>
                        <HashChip value={r.receipt_hash} head={8} tail={4} />
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 13 }}>{r.outcome}</td>
                      <td style={{ padding: '10px 16px', fontSize: 12.5, color: 'var(--text-faint)' }}>
                        {formatDateTime(r.created_at)}
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => onGenerateProof(r.record_id)}
                          disabled={proofLoading && selectedRecord === r.record_id}
                        >
                          {proofLoading && selectedRecord === r.record_id ? 'Generating…' : 'Get proof'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {proofError && (
            <div style={{ marginBottom: 16 }}>
              <ErrorBanner title="Proof generation failed" message={proofError} />
            </div>
          )}

          {proofResult && (
            <div className="card card-pad" style={{ marginTop: 16 }}>
              <div className="copy-row" style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 18 }}>Merkle Inclusion Proof</h3>
                <Pill tone={proofResult.verification.valid ? 'success' : 'danger'}>
                  {proofResult.verification.valid ? 'PROOF VALID' : 'PROOF INVALID'}
                </Pill>
              </div>

              {/* Verification flow diagram */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '12px 16px',
                background: proofResult.verification.valid ? 'var(--success-bg)' : 'var(--danger-bg)',
                border: `1px solid ${proofResult.verification.valid ? 'var(--success-border)' : 'var(--danger-border)'}`,
                borderRadius: 'var(--radius-sm)',
                marginBottom: 16,
                fontSize: 13,
                fontFamily: 'var(--mono)',
                flexWrap: 'wrap',
              }}>
                <span style={{ color: proofResult.verification.valid ? 'var(--success)' : 'var(--danger)', fontWeight: 700 }}>
                  Receipt Hash
                </span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: 'var(--text-muted)' }}>Merkle Leaf</span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: 'var(--text-muted)' }}>{proofResult.proof.length} Proof Nodes</span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: 'var(--text-muted)' }}>Merkle Root</span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: proofResult.verification.valid ? 'var(--success)' : 'var(--danger)', fontWeight: 700 }}>
                  {proofResult.verification.valid ? 'VERIFIED' : 'FAILED'}
                </span>
              </div>

              <div className="kv-grid" style={{ marginBottom: 14 }}>
                <div className="kv">
                  <span className="kv-label">Receipt hash (leaf)</span>
                  <HashChip value={proofResult.receipt_hash} head={16} tail={12} />
                </div>
                <div className="kv">
                  <span className="kv-label">Leaf index</span>
                  <span className="kv-value mono">{proofResult.leaf_index} of {proofResult.batch_size}</span>
                </div>
                <div className="kv">
                  <span className="kv-label">Merkle root</span>
                  <HashChip value={proofResult.merkle_root} head={14} tail={10} />
                </div>
                {proofResult.anchor_tx_ref && (
                  <div className="kv">
                    <span className="kv-label">Anchor transaction</span>
                    <div className="copy-row" style={{ gap: 8 }}>
                      <HashChip value={proofResult.anchor_tx_ref} />
                      <a className="icon-btn" href={algorandExplorerUrl(proofResult.anchor_tx_ref)} target="_blank" rel="noreferrer" aria-label="View on Algorand explorer">
                        <ExternalIcon width={14} height={14} />
                      </a>
                    </div>
                  </div>
                )}
              </div>

              <div style={{ marginBottom: 12 }}>
                <div className="section-title">Proof nodes ({proofResult.proof.length})</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {proofResult.proof.map((node, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5 }}>
                      <span className="mono" style={{ color: 'var(--text-faint)', minWidth: 20 }}>#{i + 1}</span>
                      <span className={`badge ${node.position === 'left' ? 'badge-accent' : 'badge-warning'}`} style={{ minWidth: 44, justifyContent: 'center' }}>
                        {node.position}
                      </span>
                      <HashChip value={node.hash} head={12} tail={8} />
                    </div>
                  ))}
                </div>
              </div>

              <p style={{ fontSize: 12.5, color: 'var(--text-faint)' }}>
                {proofResult.verification.details}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
