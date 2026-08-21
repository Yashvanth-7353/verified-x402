import type { ReactNode } from 'react';
import type { Severity, VerificationOutcome } from '../api/types';
import { outcomeLabel } from '../lib/format';
import { CheckIcon, XIcon } from './icons';

export function OutcomeBadge({ outcome }: { outcome: VerificationOutcome }) {
  const cls = outcome === 'rejected' ? 'badge-danger' : 'badge-success';
  return (
    <span className={`badge ${cls}`}>
      {outcome === 'rejected' ? <XIcon width={12} height={12} /> : <CheckIcon width={12} height={12} />}
      {outcomeLabel(outcome)}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const cls = severity === 'blocking' ? 'severity-blocking' : severity === 'warning' ? 'severity-warning' : 'severity-info';
  return <span className={`badge ${cls}`}>{severity}</span>;
}

export function Pill({
  tone = 'pending',
  children,
}: {
  tone?: 'success' | 'warning' | 'danger' | 'pending' | 'accent';
  children: ReactNode;
}) {
  return (
    <span className={`badge badge-${tone}`}>
      <span className="badge-dot" />
      {children}
    </span>
  );
}
