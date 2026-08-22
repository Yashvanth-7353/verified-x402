import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getRecord } from '../api/client';
import { ApiError, type RecordSummary } from '../api/types';
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

const TIMELINE_STEPS = [
  { key: 'record', label: 'Record created' },
  { key: 'outcome', label: 'Verification outcome' },
  { key: 'repair', label: 'Repair type' },
  { key: 'payment', label: 'Payment status' },
  { key: 'anchor', label: 'Anchoring status' },
];

export function RecordDetail() {
  const { recordId } = useParams<{ recordId: string }>();
  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Determine which timeline steps are active
  const hasRepair = Boolean(record.repair_type && record.repair_type !== 'none');
  const hasPayment = Boolean(record.payment_status && record.payment_status !== 'none');
  const isAnchored = record.anchoring_status === 'anchored';

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
            {/* Timeline line */}
            <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: 'var(--border)' }} />

            {TIMELINE_STEPS.map((step, i) => {
              const stepInfo = (() => {
                switch (step.key) {
                  case 'repair': return { active: hasRepair, detail: record.repair_type || 'none' };
                  case 'payment': return { active: hasPayment, detail: record.payment_status || 'not applicable' };
                  case 'anchor': return { active: isAnchored, detail: record.anchoring_status };
                  case 'outcome': return { active: true, detail: record.outcome };
                  default: return { active: true, detail: formatDateTime(record.created_at) };
                }
              })();
              const { active, detail } = stepInfo;

              return (
                <div key={step.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, paddingBottom: i < TIMELINE_STEPS.length - 1 ? 16 : 0, position: 'relative' }}>
                  <div style={{
                    position: 'absolute',
                    left: -24,
                    top: 4,
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    background: active ? 'var(--success)' : 'var(--surface-sunken)',
                    border: `2px solid ${active ? 'var(--success)' : 'var(--border)'}`,
                    zIndex: 1,
                  }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: active ? 'var(--text)' : 'var(--text-faint)' }}>{step.label}</div>
                    <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 2 }}>{detail}</div>
                  </div>
                </div>
              );
            })}
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
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Link to="/verify-receipt" state={{ receipt: { receipt_id: record.receipt_id, request_id_ref: record.request_id, outcome: record.outcome, output_hash: record.output_hash || '', receipt_hash: record.receipt_hash } }} className="btn btn-ghost btn-sm">
            Verify receipt
          </Link>
          {isAnchored && record.record_id && (
            <Link to="/anchoring" className="btn btn-ghost btn-sm">
              View Merkle proof
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
