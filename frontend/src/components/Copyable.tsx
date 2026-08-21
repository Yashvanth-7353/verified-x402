import { useState } from 'react';
import { copyText, truncateMiddle } from '../lib/format';
import { useToast } from '../lib/useToast';
import { CheckIcon, CopyIcon } from './icons';

export function HashChip({ value, head = 10, tail = 8 }: { value: string | null | undefined; head?: number; tail?: number }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  if (!value) return <span className="kv-value">—</span>;

  const onCopy = async () => {
    const ok = await copyText(value);
    if (ok) {
      setCopied(true);
      toast.show('Copied to clipboard', 'success');
      setTimeout(() => setCopied(false), 1400);
    }
  };

  return (
    <span className="hash-chip">
      <span title={value}>{truncateMiddle(value, head, tail)}</span>
      <button type="button" className={`icon-btn ${copied ? 'pulse-once' : ''}`} onClick={onCopy} aria-label="Copy value">
        {copied ? <CheckIcon width={13} height={13} /> : <CopyIcon width={13} height={13} />}
      </button>
    </span>
  );
}

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  const onCopy = async () => {
    const ok = await copyText(value);
    if (ok) {
      setCopied(true);
      toast.show('Copied to clipboard', 'success');
      setTimeout(() => setCopied(false), 1400);
    }
  };
  return (
    <button type="button" className={`btn btn-ghost btn-sm ${copied ? 'pulse-once' : ''}`} onClick={onCopy}>
      {copied ? <CheckIcon width={13} height={13} /> : <CopyIcon width={13} height={13} />}
      {copied ? 'Copied' : label}
    </button>
  );
}
