import { Link } from 'react-router-dom';
import type { VerificationReceipt } from '../api/types';
import { formatDateTime } from '../lib/format';
import { HashChip } from './Copyable';
import { JsonView } from './JsonView';
import { OutcomeBadge, Pill } from './StatusBadge';

export function ReceiptCard({ receipt }: { receipt: VerificationReceipt }) {
  const signed = Boolean(receipt.signature);
  return (
    <div className="card card-pad">
      <div className="copy-row" style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: 18 }}>Verification receipt</h3>
        <OutcomeBadge outcome={receipt.outcome} />
      </div>

      <div className="kv-grid">
        <div className="kv">
          <span className="kv-label">Receipt ID</span>
          <HashChip value={receipt.receipt_id} />
        </div>
        <div className="kv">
          <span className="kv-label">Request</span>
          <HashChip value={receipt.request_id_ref} />
        </div>
        <div className="kv">
          <span className="kv-label">Output hash</span>
          <HashChip value={receipt.output_hash} />
        </div>
        <div className="kv">
          <span className="kv-label">Receipt hash</span>
          <HashChip value={receipt.receipt_hash} />
        </div>
        {receipt.repair_summary_hash && (
          <div className="kv">
            <span className="kv-label">Repair summary hash</span>
            <HashChip value={receipt.repair_summary_hash} />
          </div>
        )}
        <div className="kv">
          <span className="kv-label">Schema</span>
          <span className="kv-value mono">{receipt.schema_ref_and_version}</span>
        </div>
        <div className="kv">
          <span className="kv-label">Validator</span>
          <span className="kv-value mono">{receipt.validator_version}</span>
        </div>
        <div className="kv">
          <span className="kv-label">Issued</span>
          <span className="kv-value">{formatDateTime(receipt.issued_at)}</span>
        </div>
      </div>

      <div className="divider" />

      <div className="copy-row">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {signed ? (
            <Pill tone="success">{receipt.signature_algorithm ?? 'Ed25519'} signature valid</Pill>
          ) : (
            <Pill tone="pending">Unsigned receipt</Pill>
          )}
          {receipt.signing_key_id && (
            <span style={{ fontSize: 12, color: 'var(--text-faint)' }} className="mono">
              key {receipt.signing_key_id}
            </span>
          )}
        </div>
        <Link
          to="/verify-receipt"
          state={{ receipt }}
          className="btn btn-ghost btn-sm"
        >
          Verify independently
        </Link>
      </div>

      <JsonView data={receipt} title="Raw receipt" collapsible />
    </div>
  );
}
