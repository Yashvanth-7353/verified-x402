import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getRecord, getMerkleProof } from '../api/client';
import { ApiError, type MerkleProofResponse, type RecordSummary } from '../api/types';
import { HashChip } from '../components/Copyable';
import { EmptyState, ErrorBanner } from '../components/Feedback';
import { OutcomeBadge, Pill } from '../components/StatusBadge';
import { VerificationSeal } from '../components/VerificationSeal';
import { algorandExplorerUrl, formatDateTime } from '../lib/format';

type RecordDetail = RecordSummary & {
  schema_ref_and_version?: string | null;
  validator_version?: string | null;
  signing_key_id?: string | null;
  signature_algorithm?: string | null;
  agent_identifier?: string | null;
  repair_type?: string | null;
  payment_facilitator?: string | null;
  settlement_network?: string | null;
};

// Timeline steps are built dynamically from the actual backend record data.
// Only steps with real information are shown — no placeholder values.

export function RecordDetail() {
  const { recordId } = useParams<{ recordId: string }>();
  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [proof, setProof] = useState<MerkleProofResponse | null>(null);
  const [proofLoading, setProofLoading] = useState(false);
  const [proofError, setProofError] = useState<string | null>(null);

  useEffect(() => {
    if (!recordId) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await getRecord(recordId);
        if (!cancelled) setRecord(r as RecordDetail);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : 'Failed to load record.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [recordId]);

  // Generate proof when record is anchored (must be before any early returns)
  useEffect(() => {
    if (!record || record.anchoring_status !== 'anchored' || !recordId) return;
    let cancelled = false;
    const loadProof = async () => {
      setProofLoading(true);
      setProofError(null);
      try {
        const p = await getMerkleProof(recordId);
        if (!cancelled) setProof(p);
      } catch (e) {
        if (!cancelled) {
          setProofError(e instanceof ApiError ? e.message : 'Failed to load proof.');
        }
      } finally {
        if (!cancelled) setProofLoading(false);
      }
    };
    loadProof();
    return () => { cancelled = true; };
  }, [record, recordId]);

  if (!recordId) {
    return (
      <div className="page">
        <div className="container" style={{ maxWidth: 700 }}>
          <EmptyState title="No record ID" message="Navigate to a specific record to see its details." action={<Link to="/history" className="btn btn-accent">View history</Link>} />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page">
        <div className="container" style={{ maxWidth: 700 }}>
          <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="spinner spinner-dark" />
            <span style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>Loading record…</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !record) {
    return (
      <div className="page">
        <div className="container" style={{ maxWidth: 700 }}>
          {error && <ErrorBanner title="Could not load record" message={error} />}
          {!error && <EmptyState title="Record not found" message={`No record found with ID ${recordId.slice(0, 8)}…`} action={<Link to="/history" className="btn btn-accent">View history</Link>} />}
        </div>
      </div>
    );
  }

  const isAnchored = record.anchoring_status === 'anchored';

  // Build timeline from actual backend data — only show steps with real info
  const timelineSteps: Array<{ label: string; detail: string; active: boolean }> = [
    { label: 'Record created', detail: formatDateTime(record.created_at), active: true },
    { label: 'Verification outcome', detail: record.outcome, active: true },
  ];
  if (record.repair_type && record.repair_type !== 'none') {
    timelineSteps.push({ label: 'Repair type', detail: record.repair_type, active: true });
  }
  if (record.payment_status && record.payment_status !== 'none') {
    timelineSteps.push({ label: 'Payment status', detail: record.payment_status, active: record.payment_status === 'settled' });
  }
  timelineSteps.push({ label: 'Anchoring status', detail: record.anchoring_status, active: isAnchored });

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 700 }}>
        <Link to="/history" className="btn btn-ghost btn-sm" style={{ marginBottom: 20 }}>
          ← Back to history
        </Link>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 24, flexWrap: 'wrap' }}>
          <VerificationSeal outcome={record.outcome as 'verified' | 'verified_repaired' | 'rejected'} size={72} />
          <div>
            <OutcomeBadge outcome={record.outcome as 'verified' | 'verified_repaired' | 'rejected'} />
            <h1 style={{ fontSize: 'var(--fs-lg)', marginTop: 6 }}>Verification Record</h1>
            <p style={{ color: 'var(--text-faint)', fontSize: 13, marginTop: 4 }}>
              Created {formatDateTime(record.created_at)}
            </p>
          </div>
        </div>

        {/* Timeline */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="section-title">Record timeline</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0, position: 'relative', paddingLeft: 24 }}>
            <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: 'var(--border)' }} />
            {timelineSteps.map((step, i) => (
              <div key={step.label} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, paddingBottom: i < timelineSteps.length - 1 ? 16 : 0, position: 'relative' }}>
                <div style={{
                  position: 'absolute', left: -24, top: 4, width: 16, height: 16,
                  borderRadius: '50%',
                  background: step.active ? 'var(--success)' : 'var(--surface-sunken)',
                  border: `2px solid ${step.active ? 'var(--success)' : 'var(--border)'}`,
                  zIndex: 1,
                }} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: step.active ? 'var(--text)' : 'var(--text-faint)' }}>{step.label}</div>
                  <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 2 }}>{step.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Identifiers */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="section-title">Identifiers</div>
          <div className="kv-grid">
            <div className="kv">
              <span className="kv-label">Record ID</span>
              <HashChip value={record.record_id} />
            </div>
            <div className="kv">
              <span className="kv-label">Request ID</span>
              <HashChip value={record.request_id} />
            </div>
            <div className="kv">
              <span className="kv-label">Receipt ID</span>
              <HashChip value={record.receipt_id} />
            </div>
          </div>
        </div>

        {/* Hashes */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="section-title">Integrity</div>
          <div className="kv-grid">
            <div className="kv">
              <span className="kv-label">Receipt hash</span>
              <HashChip value={record.receipt_hash} head={16} tail={12} />
            </div>
            {record.output_hash && (
              <div className="kv">
                <span className="kv-label">Output hash</span>
                <HashChip value={record.output_hash} head={16} tail={12} />
              </div>
            )}
          </div>
        </div>

        {/* Technical details */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="section-title">Technical details</div>
          <div className="kv-grid">
            {record.schema_ref_and_version && (
              <div className="kv">
                <span className="kv-label">Schema</span>
                <span className="kv-value mono">{record.schema_ref_and_version}</span>
              </div>
            )}
            {record.validator_version && (
              <div className="kv">
                <span className="kv-label">Validator</span>
                <span className="kv-value mono">{record.validator_version}</span>
              </div>
            )}
            {record.agent_identifier && (
              <div className="kv">
                <span className="kv-label">Agent</span>
                <span className="kv-value mono">{record.agent_identifier}</span>
              </div>
            )}
            {record.signing_key_id && (
              <div className="kv">
                <span className="kv-label">Signing key</span>
                <span className="kv-value mono">{record.signature_algorithm || 'Ed25519'} · {record.signing_key_id}</span>
              </div>
            )}
            {record.payment_facilitator && (
              <div className="kv">
                <span className="kv-label">Facilitator</span>
                <span className="kv-value">{record.payment_facilitator}</span>
              </div>
            )}
            {record.settlement_network && (
              <div className="kv">
                <span className="kv-label">Network</span>
                <span className="kv-value">{record.settlement_network}</span>
              </div>
            )}
          </div>
        </div>

        {/* Anchoring */}
        <div className="card card-pad" style={{ marginBottom: 20 }}>
          <div className="section-title">Anchoring</div>
          <div className="kv-grid">
            <div className="kv">
              <span className="kv-label">Status</span>
              <Pill tone={isAnchored ? 'success' : 'pending'}>{record.anchoring_status}</Pill>
            </div>
            {record.merkle_root && (
              <div className="kv">
                <span className="kv-label">Merkle root</span>
                <HashChip value={record.merkle_root} head={14} tail={10} />
              </div>
            )}
            {record.anchor_tx_ref && (
              <div className="kv">
                <span className="kv-label">Anchor transaction</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <HashChip value={record.anchor_tx_ref} />
                  <a className="icon-btn" href={algorandExplorerUrl(record.anchor_tx_ref)} target="_blank" rel="noreferrer" aria-label="View on Algorand explorer">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6M10 14 21 3"/></svg>
                  </a>
                </div>
              </div>
            )}
          </div>

          {/* Merkle inclusion proof (auto-loaded for anchored records) */}
          {isAnchored && proofLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
              <span className="spinner spinner-dark" />
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Generating inclusion proof…</span>
            </div>
          )}

          {proofError && (
            <p style={{ fontSize: 12.5, color: 'var(--danger)', marginTop: 10 }}>
              {proofError}
            </p>
          )}

          {proof && (
            <div style={{
              marginTop: 14,
              padding: '12px 14px',
              background: proof.verification.valid ? 'var(--success-bg)' : 'var(--danger-bg)',
              border: `1px solid ${proof.verification.valid ? 'var(--success-border)' : 'var(--danger-border)'}`,
              borderRadius: 'var(--radius-sm)',
              fontSize: 12.5,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{ color: proof.verification.valid ? 'var(--success)' : 'var(--danger)', fontWeight: 700 }}>
                  {proof.verification.valid ? '✓' : '✕'}
                </span>
                <span style={{ fontWeight: 600 }}>
                  Merkle inclusion proof {proof.verification.valid ? 'valid' : 'INVALID'}
                </span>
                <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>
                  ({proof.proof.length} nodes, leaf {proof.leaf_index} of {proof.batch_size})
                </span>
              </div>
              <p style={{ color: 'var(--text-muted)', margin: 0 }}>
                {proof.verification.details}
              </p>
              <Link to="/anchoring" className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}>
                View full proof details
              </Link>
            </div>
          )}

          {!isAnchored && !proofLoading && !proof && (
            <p style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 10 }}>
              <Link to="/anchoring">Go to Anchoring</Link> to anchor this record.
            </p>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Link to="/verify-receipt" state={{ receipt: { receipt_id: record.receipt_id, request_id_ref: record.request_id, outcome: record.outcome, output_hash: record.output_hash || '', receipt_hash: record.receipt_hash } }} className="btn btn-ghost btn-sm">
            Verify receipt
          </Link>
          {!isAnchored && (
            <Link to="/anchoring" className="btn btn-ghost btn-sm">
              Anchor this record
            </Link>
          )}
          {isAnchored && record.anchor_tx_ref && (
            <a
              className="btn btn-ghost btn-sm"
              href={algorandExplorerUrl(record.anchor_tx_ref)}
              target="_blank"
              rel="noreferrer"
            >
              View on Algorand →
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
