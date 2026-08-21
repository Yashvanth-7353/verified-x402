export function truncateMiddle(value: string | null | undefined, head = 10, tail = 8): string {
  if (!value) return '—';
  if (value.length <= head + tail + 3) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'medium',
    });
  } catch {
    return iso;
  }
}

export function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const s = Math.round(diffMs / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

export function formatAtomicAmount(amount: string | number | undefined, decimals = 6): string {
  if (amount === undefined || amount === null) return '—';
  const n = typeof amount === 'string' ? Number(amount) : amount;
  if (Number.isNaN(n)) return String(amount);
  return (n / 10 ** decimals).toLocaleString(undefined, { maximumFractionDigits: decimals });
}

export function outcomeLabel(outcome: string): string {
  switch (outcome) {
    case 'verified':
      return 'Verified';
    case 'verified_repaired':
      return 'Verified — Repaired';
    case 'rejected':
      return 'Rejected';
    default:
      return outcome;
  }
}

export function algorandExplorerUrl(txId: string): string {
  return `https://testnet.explorer.perawallet.app/tx/${txId}/`;
}
