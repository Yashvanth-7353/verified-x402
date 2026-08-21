import type { PaymentMetadata, PaymentRequiredChallenge } from '../api/types';
import { algorandExplorerUrl, formatAtomicAmount, formatDateTime } from '../lib/format';
import { HashChip } from './Copyable';
import { ExternalIcon } from './icons';
import { Pill } from './StatusBadge';

export function PaymentRequiredCard({ challenge }: { challenge: PaymentRequiredChallenge }) {
  const accept = challenge.accepts?.[0];
  const decimals = accept?.extra?.decimals ?? 6;
  return (
    <div className="card card-pad" style={{ borderColor: 'var(--seal-border)', background: 'var(--seal-bg)' }}>
      <div className="copy-row" style={{ marginBottom: 12 }}>
        <h3 style={{ fontSize: 18 }}>Payment required</h3>
        <Pill tone="warning">HTTP 402</Pill>
      </div>
      <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 16 }}>
        This output can't be repaired by deterministic rules. Semantic repair is a paid escalation, gated by an{' '}
        <strong>x402</strong> payment settled on Algorand — Verified will never call the repair provider before payment
        settles.
      </p>
      <div className="kv-grid">
        <div className="kv">
          <span className="kv-label">Price</span>
          <span className="kv-value">{formatAtomicAmount(accept?.amount, decimals)} USDC</span>
        </div>
        <div className="kv">
          <span className="kv-label">Network</span>
          <span className="kv-value">{accept?.network}</span>
        </div>
        <div className="kv">
          <span className="kv-label">Facilitator</span>
          <span className="kv-value">GoPlausible AVM</span>
        </div>
        <div className="kv">
          <span className="kv-label">Pay to</span>
          <HashChip value={accept?.payTo} />
        </div>
      </div>
    </div>
  );
}

export function PaymentSettledCard({ payment }: { payment: PaymentMetadata }) {
  const asset = payment.amount_and_asset as { amount?: string; asset?: string } | undefined;
  return (
    <div className="card card-pad">
      <div className="copy-row" style={{ marginBottom: 14 }}>
        <h3 style={{ fontSize: 18 }}>Payment</h3>
        <Pill tone={payment.payment_status === 'settled' ? 'success' : 'warning'}>{payment.payment_status}</Pill>
      </div>
      <div className="kv-grid">
        <div className="kv">
          <span className="kv-label">Protocol</span>
          <span className="kv-value">x402</span>
        </div>
        <div className="kv">
          <span className="kv-label">Amount</span>
          <span className="kv-value">{formatAtomicAmount(asset?.amount)} USDC</span>
        </div>
        <div className="kv">
          <span className="kv-label">Network</span>
          <span className="kv-value">{payment.settlement_network}</span>
        </div>
        <div className="kv">
          <span className="kv-label">Facilitator</span>
          <span className="kv-value">{payment.facilitator}</span>
        </div>
        <div className="kv">
          <span className="kv-label">Verified at</span>
          <span className="kv-value">{formatDateTime(payment.verified_at)}</span>
        </div>
        {payment.algorand_tx_ref && (
          <div className="kv">
            <span className="kv-label">Transaction</span>
            <div className="copy-row" style={{ gap: 8 }}>
              <HashChip value={payment.algorand_tx_ref} />
              <a
                className="icon-btn"
                href={algorandExplorerUrl(payment.algorand_tx_ref)}
                target="_blank"
                rel="noreferrer"
                aria-label="View transaction on Algorand explorer"
              >
                <ExternalIcon width={14} height={14} />
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
