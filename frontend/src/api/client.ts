import {
  ApiError,
  type AnchorResponse,
  type HealthResponse,
  type PaymentRequiredChallenge,
  type PublicKeyResponse,
  type ReceiptVerifyResponse,
  type SchemaPolicy,
  type SemanticRepairResponse,
  type VerificationReceipt,
  type VerificationRequest,
  type VerifyResponse,
} from './types';

/**
 * The x402 challenge is NOT in the 402 response body (that's `{}`) — it's
 * base64-encoded JSON in the `payment-required` response header. Confirmed
 * against the live backend; this is the real contract, not what docs/API.md
 * shows as an illustrative example.
 */
function decodeChallenge(res: Response): PaymentRequiredChallenge | undefined {
  const header = res.headers.get('payment-required');
  if (!header) return undefined;
  try {
    return JSON.parse(atob(header)) as PaymentRequiredChallenge;
  } catch {
    return undefined;
  }
}

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractDetail(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const obj = body as Record<string, unknown>;
    if (typeof obj.detail === 'string') return obj.detail;
    if (typeof obj.message === 'string') return obj.message;
  }
  return `Request failed (${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, `Cannot reach Verified backend at ${API_BASE}. Is it running?`);
  }

  if (res.status === 402) {
    const challenge = decodeChallenge(res);
    const body = await parseJson(res);
    throw new ApiError(402, 'Payment required for semantic repair', body, challenge);
  }

  if (!res.ok) {
    const body = await parseJson(res);
    throw new ApiError(res.status, extractDetail(body, res.status), body);
  }

  return (await parseJson(res)) as T;
}

export function health(): Promise<HealthResponse> {
  return request('/health');
}

export function verify(payload: { request: VerificationRequest; policy: SchemaPolicy }): Promise<VerifyResponse> {
  return request('/api/v1/verify', { method: 'POST', body: JSON.stringify(payload) });
}

/**
 * Calls /api/v1/semantic-repair. On first call (no payment) the backend
 * returns HTTP 402 with a challenge — this throws ApiError(402, ..., challenge).
 * Pass `paymentSignature` to retry with a signed x402 payment header.
 */
export function semanticRepair(
  payload: { request: VerificationRequest; policy: SchemaPolicy },
  paymentSignature?: string,
): Promise<SemanticRepairResponse> {
  return request('/api/v1/semantic-repair', {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: paymentSignature ? { 'PAYMENT-SIGNATURE': paymentSignature } : undefined,
  });
}

export function triggerAnchor(batchSize?: number): Promise<AnchorResponse> {
  return request('/api/v1/anchor', {
    method: 'POST',
    body: JSON.stringify(batchSize ? { batch_size: batchSize } : {}),
  });
}

export function verifyReceipt(receipt: VerificationReceipt): Promise<ReceiptVerifyResponse> {
  return request('/api/v1/receipt/verify', {
    method: 'POST',
    body: JSON.stringify({ receipt }),
  });
}

export function publicKey(): Promise<PublicKeyResponse> {
  return request('/api/v1/receipt/public-key');
}
