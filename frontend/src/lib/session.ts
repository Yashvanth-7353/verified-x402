import type { VerificationOutcome, VerificationReceipt, VerificationResult } from '../api/types';

/**
 * The backend does not currently expose a GET history/list endpoint (see
 * docs/API.md — only /verify, /semantic-repair, /anchor, /receipt/verify,
 * /receipt/public-key exist). So "History" here is an honest, clearly-labeled
 * local log of verifications this browser has performed, not a claim about
 * server-side records. Nothing here is sent anywhere; it only powers the UI.
 */

export interface SessionEntry {
  logged_at: string;
  request_id: string;
  agent_identifier: string;
  outcome: VerificationOutcome;
  receipt_id: string;
  receipt_hash: string;
  had_payment: boolean;
  result: VerificationResult;
  receipt: VerificationReceipt;
}

const KEY = 'verified.session_log.v1';
const MAX_ENTRIES = 200;

export function loadSessionLog(): SessionEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function appendSessionEntry(entry: SessionEntry): SessionEntry[] {
  const current = loadSessionLog();
  const next = [entry, ...current].slice(0, MAX_ENTRIES);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage unavailable (private mode, quota) — degrade silently, UI still works this render
  }
  return next;
}

export function clearSessionLog(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
