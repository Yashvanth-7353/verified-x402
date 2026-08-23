import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  triggerAnchor,
  getMerkleProof,
  listRecords,
} from '../api/client';
import {
  ApiError,
  type AnchorResponse,
  type MerkleProofResponse,
  type RecordSummary,
} from '../api/types';
import { HashChip, CopyButton } from '../components/Copyable';
import { ErrorBanner } from '../components/Feedback';
import { ExternalIcon } from '../components/icons';
import { Pill } from '../components/StatusBadge';
import { algorandExplorerUrl, formatDateTime, truncateMiddle } from '../lib/format';

// ─── Mini Merkle tree visualization ─────────────────────────────────────────
// Builds a simple binary tree from receipt hashes to show the structure.
// Only shows the first 8 leaves for readability; the root is real.

function MerkleTreeView({
  leaves,
  root,
}: {
  leaves: string[];
  root: string | null;
}) {
  if (!root || leaves.length === 0) return null;

  // For display, limit to 8 leaves
  const displayLeaves = leaves.slice(0, 8);
  const hasMore = leaves.length > 8;

  return (
    <div
      style={{
        background: 'var(--surface-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        padding: 20,
        fontFamily: 'var(--mono)',
        fontSize: 11,
        overflow: 'auto',
        marginBottom: 16,
      }}
    >
      {/* Root */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div
          style={{
            display: 'inline-block',
            padding: '6px 12px',
            background: 'var(--accent-bg)',
            border: '1px solid var(--accent-border)',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 600,
            color: 'var(--accent)',
            marginBottom: 8,
          }}
        >
          MERKLE ROOT
        </div>
        <div style={{ fontSize: 12, color: 'var(--text)', wordBreak: 'break-all' }}>
          {truncateMiddle(root, 20, 20)}
        </div>
      </div>

      {/* Leaves */}
      <div style={{ borderTop: '1px dashed var(--border)', paddingTop: 10 }}>
        <div
          style={{
            fontSize: 10,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--text-faint)',
            marginBottom: 8,
          }}
        >
          Receipt hashes (leaves)
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {displayLeaves.map((leaf, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '3px 8px',
                borderRadius: 4,
                background: 'var(--surface-sunken)',
              }}
            >
              <span style={{ color: 'var(--text-faint)', minWidth: 18 }}>#{i + 1}</span>
              <span style={{ color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                {truncateMiddle(leaf, 12, 8)}
              </span>
            </div>
          ))}
          {hasMore && (
            <div style={{ color: 'var(--text-faint)', fontSize: 11, paddingLeft: 8 }}>
              … and {leaves.length - 8} more
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main Anchoring Page ─────────────────────────────────────────────────────

export function Anchoring() {
  // Records state
  const [allRecords, setAllRecords] = useState<RecordSummary[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(true);
  const [recordsError, setRecordsError] = useState<string | null>(null);

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Anchor state
  const [anchorRunning, setAnchorRunning] = useState(false);
  const [anchorResult, setAnchorResult] = useState<AnchorResponse | null>(null);
  const [anchorError, setAnchorError] = useState<string | null>(null);
  const [notConfigured, setNotConfigured] = useState(false);

  // Merkle leaf hashes for visualization
  const [leafHashes, setLeafHashes] = useState<string[]>([]);

  // Proof state
  const [proofRecordId, setProofRecordId] = useState<string | null>(null);
  const [proofResult, setProofResult] = useState<MerkleProofResponse | null>(null);
  const [proofLoading, setProofLoading] = useState(false);
  const [proofError, setProofError] = useState<string | null>(null);

  // Anchored records for proof generation
  const [anchoredRecords, setAnchoredRecords] = useState<RecordSummary[]>([]);

  // Helper to refresh the records list (used after anchoring)
  const refreshRecords = useCallback(async () => {
    setRecordsLoading(true);
    setRecordsError(null);
    try {
      const res = await listRecords(0, 200);
      setAllRecords(res.records);
      setAnchoredRecords(res.records.filter((r) => r.anchoring_status === 'anchored'));
    } catch (e) {
      if (e instanceof ApiError) setRecordsError(e.message);
      else setRecordsError('Failed to load records.');
    } finally {
      setRecordsLoading(false);
    }
  }, []);

  // Load records on mount using async IIFE to avoid setState-in-effect lint
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setRecordsLoading(true);
      setRecordsError(null);
      try {
        const res = await listRecords(0, 200);
        if (!cancelled) {
          setAllRecords(res.records);
          setAnchoredRecords(res.records.filter((r) => r.anchoring_status === 'anchored'));
        }
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError) setRecordsError(e.message);
          else setRecordsError('Failed to load records.');
        }
      } finally {
        if (!cancelled) setRecordsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const unanchored = allRecords.filter((r) => r.anchoring_status === 'unanchored');
  const allSelected = unanchored.length > 0 && selectedIds.size === unanchored.length;

  // Selection handlers
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    setSelectedIds(new Set(unanchored.map((r) => r.record_id)));
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
  };

  const selectedCount = selectedIds.size;

  // Anchor handler
  const onAnchor = async () => {
    if (selectedCount === 0) return;
    setAnchorRunning(true);
    setAnchorError(null);
    setAnchorResult(null);
    setNotConfigured(false);
    setLeafHashes([]);

    // Gather leaf hashes from selected records
    const hashes = unanchored
      .filter((r) => selectedIds.has(r.record_id))
      .map((r) => r.receipt_hash)
      .sort();
    setLeafHashes(hashes);

    try {
      const result = await triggerAnchor(undefined, Array.from(selectedIds));
      setAnchorResult(result);
      // Refresh records after anchoring
      await refreshRecords();
      setSelectedIds(new Set());
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) {
        setNotConfigured(true);
      } else {
        setAnchorError(e instanceof ApiError ? e.message : 'Anchoring request failed.');
      }
    } finally {
      setAnchorRunning(false);
    }
  };

  // Proof handler
  const onGenerateProof = async (recordId: string) => {
    setProofRecordId(recordId);
    setProofLoading(true);
    setProofError(null);
    setProofResult(null);
    try {
      const proof = await getMerkleProof(recordId);
      setProofResult(proof);
    } catch (e) {
      setProofError(
        e instanceof ApiError ? e.message : 'Failed to generate Merkle proof.',
      );
    } finally {
      setProofLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 900 }}>
        <h1 className="page-title">Anchoring</h1>

        {/* Intro explanation */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <p style={{ color: 'var(--text-muted)', fontSize: 13.5, lineHeight: 1.6, margin: 0 }}>
            Verification records accumulate locally as <code className="mono">unanchored</code>.
            Anchoring batches them into a deterministic Merkle tree over their receipt hashes,
            then commits only the{' '}
            <strong style={{ color: 'var(--text)' }}>Merkle root</strong> to Algorand TestNet
            as a transaction note — never the receipts or payloads themselves.
          </p>
          <div
            style={{
              marginTop: 12,
              padding: '10px 14px',
              background: 'var(--surface-sunken)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 12.5,
              lineHeight: 1.6,
              color: 'var(--text-muted)',
            }}
          >
            <strong style={{ color: 'var(--text)' }}>What is a Merkle root?</strong>
            <br />
            A Merkle root is a single cryptographic fingerprint representing all receipts in this
            anchor batch. If even one receipt changes, the resulting root no longer matches the root
            stored on Algorand.
            <br />
            <strong style={{ color: 'var(--text)' }}>Why it matters:</strong> The complete receipts
            do not need to be stored on-chain. The Merkle root is enough to later prove, via an
            inclusion proof, that an individual receipt belonged to this anchored batch.
          </div>
        </div>

        {/* Pipeline overview */}
        <div className="bento stagger-children" style={{ marginBottom: 24 }}>
          {[
            { num: '1', label: 'Select records', desc: 'Choose unanchored verifications' },
            { num: '2', label: 'Build Merkle tree', desc: 'Root computed from receipt hashes' },
            { num: '3', label: 'Submit to Algorand', desc: 'Root committed on-chain' },
            { num: '4', label: 'Proof available', desc: 'Any record can be independently verified' },
          ].map((item) => (
            <div
              className="span-3 card card-pad"
              key={item.num}
              style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
            >
              <span className="mono" style={{ fontSize: 12, color: 'var(--text-faint)' }}>
                Step {item.num}
              </span>
              <span style={{ fontSize: 13.5, fontWeight: 600 }}>{item.label}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.desc}</span>
            </div>
          ))}
        </div>

        {/* ─── SECTION: Records ready for anchoring ─── */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="copy-row" style={{ marginBottom: 12 }}>
            <h2 style={{ fontSize: 18, margin: 0 }}>Records ready to anchor</h2>
            {unanchored.length > 0 && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={allSelected ? clearSelection : selectAll}
                >
                  {allSelected ? 'Clear selection' : 'Select all'}
                </button>
                <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>
                  {selectedCount} selected
                </span>
              </div>
            )}
          </div>

          {recordsLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '20px 0' }}>
              <span className="spinner spinner-dark" />
              <span style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>
                Loading records…
              </span>
            </div>
          )}

          {recordsError && (
            <ErrorBanner title="Could not load records" message={recordsError} />
          )}

          {!recordsLoading && !recordsError && unanchored.length === 0 && (
            <p style={{ color: 'var(--text-faint)', fontSize: 13.5 }}>
              All records are already anchored. Run a verification to create new unanchored records.
            </p>
          )}

          {!recordsLoading && !recordsError && unanchored.length > 0 && (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table
                  style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}
                >
                  <thead>
                    <tr
                      style={{
                        textAlign: 'left',
                        borderBottom: '1px solid var(--border)',
                      }}
                    >
                      <th
                        style={{
                          padding: '10px 8px',
                          width: 36,
                          fontSize: 12,
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                          color: 'var(--text-faint)',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={() => (allSelected ? clearSelection() : selectAll())}
                          aria-label="Select all"
                        />
                      </th>
                      {['Outcome', 'Repair', 'Receipt', 'Created'].map((h) => (
                        <th
                          key={h}
                          style={{
                            padding: '10px 16px',
                            fontSize: 12,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            color: 'var(--text-faint)',
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {unanchored.map((r) => (
                      <tr
                        key={r.record_id}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          cursor: 'pointer',
                          background: selectedIds.has(r.record_id)
                            ? 'var(--accent-bg)'
                            : undefined,
                        }}
                        onClick={() => toggleSelect(r.record_id)}
                      >
                        <td style={{ padding: '10px 8px' }}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(r.record_id)}
                            onChange={() => toggleSelect(r.record_id)}
                            onClick={(e) => e.stopPropagation()}
                            aria-label={`Select record ${r.record_id.slice(0, 8)}`}
                          />
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          <Pill
                            tone={
                              r.outcome === 'verified'
                                ? 'success'
                                : r.outcome === 'verified_repaired'
                                  ? 'accent'
                                  : r.outcome === 'rejected'
                                    ? 'danger'
                                    : 'pending'
                            }
                          >
                            {r.outcome}
                          </Pill>
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          {r.repair_type ? (
                            <span
                              className={`badge ${r.repair_type === 'semantic' ? 'badge-accent' : 'badge-pending'}`}
                            >
                              {r.repair_type}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          <HashChip value={r.receipt_hash} head={8} tail={4} />
                        </td>
                        <td style={{ padding: '10px 16px', fontSize: 12.5, color: 'var(--text-faint)' }}>
                          {formatDateTime(r.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Create anchor batch button */}
              <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
                <button
                  type="button"
                  className="btn btn-accent"
                  onClick={onAnchor}
                  disabled={anchorRunning || selectedCount === 0}
                >
                  {anchorRunning && <span className="spinner" />}
                  {anchorRunning
                    ? 'Building Merkle tree & submitting to Algorand…'
                    : `Create anchor batch (${selectedCount} records)`}
                </button>
              </div>
            </>
          )}
        </div>

        {/* ─── Error states ─── */}
        {notConfigured && (
          <div style={{ marginBottom: 16 }}>
            <ErrorBanner
              title="Anchoring not configured"
              message="This backend doesn't have an Algorand anchor account configured (ANCHOR_PRIVATE_KEY). Check the backend environment variables."
            />
          </div>
        )}

        {anchorError && (
          <div style={{ marginBottom: 16 }}>
            <ErrorBanner title="Anchoring failed" message={anchorError} />
          </div>
        )}

        {/* ─── Anchor result ─── */}
        {anchorResult && (
          <div className="card card-pad" style={{ marginBottom: 20 }}>
            {anchorResult.status === 'no_records_to_anchor' ? (
              <>
                <Pill tone="pending">No records to anchor</Pill>
                <p
                  style={{
                    fontSize: 13.5,
                    color: 'var(--text-muted)',
                    marginTop: 10,
                  }}
                >
                  Every local verification record is already anchored, or none exist yet.
                </p>
              </>
            ) : (
              <>
                <div className="copy-row" style={{ marginBottom: 14 }}>
                  <h3 style={{ fontSize: 18, margin: 0 }}>
                    ✓ Anchored on Algorand TestNet
                  </h3>
                  <Pill tone="success">confirmed</Pill>
                </div>

                <div className="kv-grid" style={{ marginBottom: 16 }}>
                  <div className="kv">
                    <span className="kv-label">Merkle root</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <HashChip value={anchorResult.merkle_root} head={16} tail={12} />
                      {anchorResult.merkle_root && (
                        <CopyButton value={anchorResult.merkle_root} label="Root" />
                      )}
                    </div>
                  </div>
                  {anchorResult.transaction_id && (
                    <div className="kv">
                      <span className="kv-label">Transaction ID</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <HashChip value={anchorResult.transaction_id} />
                        <a
                          className="icon-btn"
                          href={algorandExplorerUrl(anchorResult.transaction_id)}
                          target="_blank"
                          rel="noreferrer"
                          aria-label="View on Algorand explorer"
                        >
                          <ExternalIcon width={14} height={14} />
                        </a>
                      </div>
                    </div>
                  )}
                  <div className="kv">
                    <span className="kv-label">Records anchored</span>
                    <span className="kv-value mono">{anchorResult.leaf_count}</span>
                  </div>
                  <div className="kv">
                    <span className="kv-label">Network</span>
                    <span className="kv-value">Algorand TestNet</span>
                  </div>
                </div>

                <p
                  style={{
                    fontSize: 12.5,
                    color: 'var(--text-faint)',
                    marginBottom: 16,
                    lineHeight: 1.6,
                  }}
                >
                  This root is a cryptographic commitment to every receipt hash in the batch — proof
                  that each one existed, unaltered, at anchoring time. No raw verification data was
                  uploaded to Algorand.
                </p>

                {/* Merkle tree visualization */}
                {leafHashes.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="section-title" style={{ marginBottom: 8 }}>
                      Merkle tree
                    </div>
                    <MerkleTreeView leaves={leafHashes} root={anchorResult.merkle_root} />
                  </div>
                )}

                {/* Anchored records list */}
                {anchorResult.record_ids && anchorResult.record_ids.length > 0 && (
                  <div>
                    <div className="section-title" style={{ marginBottom: 8 }}>
                      Anchored records
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                      }}
                    >
                      {anchorResult.record_ids.map((rid) => (
                        <div
                          key={rid}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                            padding: '6px 10px',
                            background: 'var(--surface-sunken)',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: 12.5,
                          }}
                        >
                          <span
                            style={{
                              color: 'var(--success)',
                              fontWeight: 700,
                            }}
                          >
                            ✓
                          </span>
                          <HashChip value={rid} head={8} tail={4} />
                          <Link
                            to={`/record/${rid}`}
                            className="btn btn-ghost btn-sm"
                            style={{ marginLeft: 'auto' }}
                          >
                            View record
                          </Link>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ─── SECTION: Merkle Inclusion Proof ─── */}
        <div style={{ marginTop: 28 }}>
          <h2 style={{ fontSize: 'var(--fs-lg)', marginBottom: 8 }}>
            Merkle Inclusion Proof
          </h2>
          <p
            style={{
              fontSize: 13.5,
              color: 'var(--text-muted)',
              marginBottom: 16,
              maxWidth: 640,
            }}
          >
            Select an anchored record to generate its Merkle inclusion proof — cryptographic evidence
            that this receipt hash was part of the anchored batch. An independent verifier can
            reconstruct the root from the leaf + proof.
          </p>

          {anchoredRecords.length === 0 && !recordsLoading && (
            <div
              className="card card-pad"
              style={{ color: 'var(--text-faint)', fontSize: 13.5 }}
            >
              No anchored records found. Anchor a batch first.
            </div>
          )}

          {anchoredRecords.length > 0 && (
            <div className="card" style={{ overflowX: 'auto', marginBottom: 16 }}>
              <table
                style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}
              >
                <thead>
                  <tr
                    style={{
                      textAlign: 'left',
                      borderBottom: '1px solid var(--border)',
                    }}
                  >
                    {['Outcome', 'Receipt hash', 'Merkle root', 'Action'].map(
                      (h) => (
                        <th
                          key={h}
                          style={{
                            padding: '10px 16px',
                            fontSize: 12,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            color: 'var(--text-faint)',
                          }}
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {anchoredRecords.slice(0, 20).map((r) => (
                    <tr
                      key={r.record_id}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        background:
                          proofRecordId === r.record_id
                            ? 'var(--accent-bg)'
                            : undefined,
                      }}
                    >
                      <td style={{ padding: '10px 16px' }}>
                        <Pill
                          tone={
                            r.outcome === 'verified'
                              ? 'success'
                              : r.outcome === 'verified_repaired'
                                ? 'accent'
                                : 'danger'
                          }
                        >
                          {r.outcome}
                        </Pill>
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <HashChip value={r.receipt_hash} head={8} tail={4} />
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <HashChip value={r.merkle_root} head={8} tail={4} />
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => onGenerateProof(r.record_id)}
                          disabled={
                            proofLoading && proofRecordId === r.record_id
                          }
                        >
                          {proofLoading && proofRecordId === r.record_id
                            ? 'Generating…'
                            : 'Get proof'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Proof error */}
          {proofError && (
            <div style={{ marginBottom: 16 }}>
              <ErrorBanner title="Proof generation failed" message={proofError} />
            </div>
          )}

          {/* Proof result */}
          {proofResult && (
            <div className="card card-pad" style={{ marginTop: 16 }}>
              <div className="copy-row" style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 18, margin: 0 }}>Merkle Inclusion Proof</h3>
                <Pill tone={proofResult.verification.valid ? 'success' : 'danger'}>
                  {proofResult.verification.valid ? 'PROOF VALID' : 'PROOF INVALID'}
                </Pill>
              </div>

              {/* Verification flow diagram */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 16px',
                  background: proofResult.verification.valid
                    ? 'var(--success-bg)'
                    : 'var(--danger-bg)',
                  border: `1px solid ${proofResult.verification.valid ? 'var(--success-border)' : 'var(--danger-border)'}`,
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: 16,
                  fontSize: 13,
                  fontFamily: 'var(--mono)',
                  flexWrap: 'wrap',
                }}
              >
                <span
                  style={{
                    color: proofResult.verification.valid
                      ? 'var(--success)'
                      : 'var(--danger)',
                    fontWeight: 700,
                  }}
                >
                  Receipt Hash
                </span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: 'var(--text-muted)' }}>Merkle Leaf</span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: 'var(--text-muted)' }}>
                  {proofResult.proof.length} Proof Nodes
                </span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span style={{ color: 'var(--text-muted)' }}>Merkle Root</span>
                <span style={{ color: 'var(--text-faint)' }}>→</span>
                <span
                  style={{
                    color: proofResult.verification.valid
                      ? 'var(--success)'
                      : 'var(--danger)',
                    fontWeight: 700,
                  }}
                >
                  {proofResult.verification.valid ? 'VERIFIED' : 'FAILED'}
                </span>
              </div>

              {/* Proof details */}
              <div className="kv-grid" style={{ marginBottom: 14 }}>
                <div className="kv">
                  <span className="kv-label">Receipt hash (leaf)</span>
                  <HashChip value={proofResult.receipt_hash} head={16} tail={12} />
                </div>
                <div className="kv">
                  <span className="kv-label">Leaf index</span>
                  <span className="kv-value mono">
                    {proofResult.leaf_index} of {proofResult.batch_size}
                  </span>
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
                      <a
                        className="icon-btn"
                        href={algorandExplorerUrl(proofResult.anchor_tx_ref)}
                        target="_blank"
                        rel="noreferrer"
                        aria-label="View on Algorand explorer"
                      >
                        <ExternalIcon width={14} height={14} />
                      </a>
                    </div>
                  </div>
                )}
              </div>

              {/* Proof nodes */}
              <div style={{ marginBottom: 12 }}>
                <div className="section-title">
                  Proof nodes ({proofResult.proof.length})
                </div>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  {proofResult.proof.map((node, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        fontSize: 12.5,
                      }}
                    >
                      <span
                        className="mono"
                        style={{
                          color: 'var(--text-faint)',
                          minWidth: 20,
                        }}
                      >
                        #{i + 1}
                      </span>
                      <span
                        className={`badge ${node.position === 'left' ? 'badge-accent' : 'badge-warning'}`}
                        style={{ minWidth: 44, justifyContent: 'center' }}
                      >
                        {node.position}
                      </span>
                      <HashChip value={node.hash} head={12} tail={8} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Verification explanation */}
              <p
                style={{
                  fontSize: 12.5,
                  color: 'var(--text-faint)',
                  lineHeight: 1.5,
                }}
              >
                {proofResult.verification.details}
              </p>

              {/* Link to record detail */}
              <div style={{ marginTop: 12 }}>
                <Link
                  to={`/record/${proofResult.record_id}`}
                  className="btn btn-ghost btn-sm"
                >
                  View full record detail →
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
