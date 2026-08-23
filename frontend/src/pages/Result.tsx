import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useWallet } from '@txnlab/use-wallet-react';
import { semanticRepair as callSemanticRepair, verifyReceipt } from '../api/client';
import {
  ApiError,
  type PaymentRequiredChallenge,
  type SchemaPolicy,
  type SemanticRepairResponse,
  type VerificationRequest,
  type VerifyResponse,
} from '../api/types';
import { EmptyState, ErrorBanner } from '../components/Feedback';
import { FindingsList } from '../components/FindingsList';
import { JsonView } from '../components/JsonView';
import { PaymentSettledCard } from '../components/PaymentCard';
import { type Stage, PipelineStages } from '../components/PipelineStages';
import { ReceiptCard } from '../components/ReceiptCard';
import { RepairCompare } from '../components/RepairCompare';
import { OutcomeBadge, Pill } from '../components/StatusBadge';
import { VerificationSeal } from '../components/VerificationSeal';
import { formatDateTime, formatAtomicAmount, algorandExplorerUrl } from '../lib/format';
import { appendSessionEntry } from '../lib/session';
import { createWalletAvmSigner, createSignedPayment } from '../lib/x402Payment';
import type { PaymentRequired } from '@x402/core/types';

interface LocationState {
  request: VerificationRequest;
  policy: SchemaPolicy;
  response: VerifyResponse;
}

type PaymentState = 'idle' | 'signing' | 'submitting' | 'settling' | 'settled' | 'failed' | 'cancelled';

export function Result() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  const [response, setResponse] = useState<VerifyResponse | SemanticRepairResponse | undefined>(state?.response);
  const [escalating, setEscalating] = useState(false);
  const [escalationAttempted, setEscalationAttempted] = useState(false);
  const [challenge, setChallenge] = useState<PaymentRequiredChallenge | null>(null);
  const [escalationError, setEscalationError] = useState<string | null>(null);

  // Wallet payment state
  const { activeAddress, signTransactions } = useWallet();
  const [paymentState, setPaymentState] = useState<PaymentState>('idle');
  const [settlementTxId, setSettlementTxId] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const [tamperResult, setTamperResult] = useState<'idle' | 'checking' | { valid: boolean; details: string }>('idle');

  const paymentMeta = response && 'payment_metadata' in response ? response.payment_metadata : null;

  // Log to session only when the receipt ID actually changes (not on initial render).
  // This prevents logging the intermediate 'rejected' state before payment,
  // ensuring the session log shows only the final outcome.
  const initialReceiptIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!state || !response) return;
    const currentReceiptId = response.receipt.receipt_id;
    // Skip the first render — we don't want to log the initial (pre-payment) state
    if (initialReceiptIdRef.current === null) {
      initialReceiptIdRef.current = currentReceiptId;
      return;
    }
    // Only log when the receipt ID actually changes (e.g., after repair)
    if (initialReceiptIdRef.current !== currentReceiptId) {
      initialReceiptIdRef.current = currentReceiptId;
      appendSessionEntry({
        logged_at: new Date().toISOString(),
        request_id: state.request.request_id,
        agent_identifier: state.request.agent_identifier,
        outcome: response.result.outcome,
        receipt_id: currentReceiptId,
        receipt_hash: response.receipt.receipt_hash,
        had_payment: Boolean(paymentMeta),
        result: response.result,
        receipt: response.receipt,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response?.receipt.receipt_id]);

  const stages = useMemo<Stage[]>(() => {
    if (!response) return [];
    const hasRepair = Boolean(response.result.repair_info);
    const isSemanticRepair = response.result.repair_info?.repair_type === 'semantic';
    const isRejected = response.result.outcome === 'rejected';
    const isVerifiedRepaired = response.result.outcome === 'verified_repaired';
    const isPaid = paymentMeta?.payment_status === 'settled';
    const hasRepairedOutput = Boolean('repaired_output' in response && response.repaired_output);

    // Escalation: show when user requested semantic repair or it was attempted
    const showEscalation = escalationAttempted || escalating || isSemanticRepair || isPaid || (isRejected && challenge != null);
    const escalatedState: Stage['state'] = escalating ? 'active' : showEscalation ? 'done' : 'skipped';

    // Paid: show when semantic repair path was entered
    const paidState: Stage['state'] = isPaid ? 'done' : escalating ? 'active' : challenge ? 'pending' : 'skipped';

    // Repair stages depend on the three semantic repair outcomes:
    // A. Candidate accepted (repair_info + verified_repaired): Repaired ✓, Re-validated ✓
    // B. Candidate rejected (hasRepairedOutput + rejected): Repaired ✓, Re-validated ✗
    // C. No candidate (isPaid + rejected + no repair_info): Repaired ✗, Re-validated —
    let repairedState: Stage['state'] = 'skipped';
    let revalidatedState: Stage['state'] = 'skipped';

    if (isVerifiedRepaired && hasRepair) {
      // Case A: candidate accepted after re-validation
      repairedState = 'done';
      revalidatedState = 'done';
    } else if (isRejected && hasRepairedOutput && isPaid) {
      // Case B: candidate generated but re-validation failed
      repairedState = 'done';
      revalidatedState = 'failed';
    } else if (isRejected && !hasRepair && isPaid) {
      // Case C: payment made but no candidate generated (Groq failed)
      repairedState = 'failed';
      revalidatedState = 'skipped';
    } else if (hasRepair && !isSemanticRepair) {
      // Deterministic repair (no payment needed)
      repairedState = 'done';
      revalidatedState = 'done';
    }

    // Initial validation: done only if outcome is 'verified' (passed first time).
    // For rejected or verified_repaired, initial validation found issues.
    const validatedState: Stage['state'] =
      response.result.outcome === 'verified' ? 'done' : 'failed';

    return [
      { key: 'submitted', label: 'Submitted', state: 'done' },
      { key: 'validated', label: 'Validated', state: validatedState },
      { key: 'escalated', label: 'Escalated', state: escalatedState },
      { key: 'paid', label: 'Paid', state: paidState },
      { key: 'repaired', label: 'Repaired', state: repairedState },
      { key: 'revalidated', label: 'Re-validated', state: revalidatedState },
      { key: 'receipt', label: 'Receipt', state: 'done' },
    ];
  }, [response, challenge, escalating, escalationAttempted, paymentMeta]);

  if (!state || !response) {
    return (
      <div className="page">
        <div className="container" style={{ maxWidth: 640 }}>
          <EmptyState
            title="No verification to show"
            message="Start a new verification to see its result, findings, receipt and proof here."
            action={
              <Link to="/verify" className="btn btn-accent">
                Verify an output
              </Link>
            }
          />
        </div>
      </div>
    );
  }

  const { request, policy } = state;

  const onEscalate = async () => {
    setEscalating(true);
    setEscalationAttempted(true);
    setEscalationError(null);
    setChallenge(null);
    setPaymentState('idle');
    setSettlementTxId(null);
    setPaymentError(null);
    try {
      const paid = await callSemanticRepair({ request, policy });
      setResponse(paid);
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        setChallenge(e.challenge ?? null);
      } else {
        setEscalationError(e instanceof Error ? e.message : 'Semantic repair failed.');
      }
    } finally {
      setEscalating(false);
    }
  };

  const onPay = async () => {
    if (!challenge || !activeAddress || !signTransactions) return;

    setPaymentState('signing');
    setPaymentError(null);

    try {
      // 1. Parse payment requirements from the 402 challenge
      const paymentReq = challenge.accepts?.[0];
      if (!paymentReq) throw new Error('No payment requirements in 402 response');

      // 2. Build the full PaymentRequired structure for the x402 client.
      // Cast: our PaymentRequiredChallenge mirrors the live server's actual
      // (looser) shape, not the SDK's stricter CAIP-2-typed `network` field.
      const paymentRequired = {
        x402Version: challenge.x402Version,
        accepts: challenge.accepts,
        resource: challenge.resource,
        error: challenge.error,
      } as unknown as PaymentRequired;

      // 3. Create a ClientAvmSigner adapter from the wallet
      const walletSigner = createWalletAvmSigner(activeAddress, signTransactions);

      // 4. Use x402 to create the signed payment payload
      const paymentSignature = await createSignedPayment(paymentRequired, walletSigner);

      setPaymentState('submitting');

      // 5. Send the signed payment to the backend
      const paid = await callSemanticRepair({ request, policy }, paymentSignature);

      // 6. Extract settlement tx from payment metadata
      const meta = paid.payment_metadata;
      if (meta?.algorand_tx_ref) {
        setSettlementTxId(meta.algorand_tx_ref);
      }

      setPaymentState('settled');
      setResponse(paid);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Payment failed';

      // Distinguish wallet cancellation from other errors
      if (msg.includes('cancelled') || msg.includes('rejected') || msg.includes('User declined')) {
        setPaymentState('cancelled');
        setPaymentError('Payment cancelled by wallet.');
      } else {
        setPaymentState('failed');
        setPaymentError(msg);
      }
    }
  };

  const onTamperTest = async () => {
    setTamperResult('checking');
    const tampered = {
      ...response.receipt,
      outcome: response.receipt.outcome === 'rejected' ? ('verified' as const) : ('rejected' as const),
    };
    try {
      const r = await verifyReceipt(tampered);
      setTamperResult({ valid: r.valid, details: r.details });
    } catch (e) {
      setTamperResult({ valid: false, details: e instanceof Error ? e.message : 'Verification request failed.' });
    }
  };

  const canEscalate = response.result.outcome === 'rejected' && !challenge && !escalationAttempted;
  const showPaymentFlow = Boolean(challenge) && !paymentMeta;
  const wasPaidButFailed = paymentMeta?.payment_status === 'settled' && response.result.outcome === 'rejected' && !response.result.repair_info;
  const wasPaidCandidateRejected = paymentMeta?.payment_status === 'settled' && response.result.outcome === 'rejected' && Boolean('repaired_output' in response && response.repaired_output);

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 880 }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/verify')} style={{ marginBottom: 20 }}>
          ← New verification
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 8, flexWrap: 'wrap' }}>
          <VerificationSeal outcome={response.result.outcome} size={84} />
          <div>
            <div style={{ marginBottom: 6 }}>
              <OutcomeBadge outcome={response.result.outcome} />
            </div>
            <h1 style={{ fontSize: 'var(--fs-lg)' }}>Verification result</h1>
            <p style={{ color: 'var(--text-faint)', fontSize: 13, marginTop: 6 }}>
              {request.agent_identifier} · completed {formatDateTime(response.result.completed_at)}
            </p>
          </div>
        </div>

        <div className="card card-pad" style={{ margin: '24px 0' }}>
          <div className="section-title">Verification pipeline</div>
          <PipelineStages stages={stages} />
          {wasPaidButFailed && (
            <p style={{ fontSize: 12.5, color: 'var(--warning)', marginTop: 12 }}>
              Payment was settled on Algorand TestNet, but the semantic-repair provider could not produce a valid candidate. The output remains rejected.
            </p>
          )}
          {wasPaidCandidateRejected && (
            <p style={{ fontSize: 12.5, color: 'var(--warning)', marginTop: 12 }}>
              Payment was settled and a repair candidate was generated, but the candidate failed re-validation. The output remains rejected.
            </p>
          )}
        </div>

        <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="card card-pad">
            <div className="section-title">Findings</div>
            <FindingsList findings={response.result.findings} />
          </div>

          {response.result.repair_info && (
            <div className="card card-pad">
              <div className="section-title">Repair</div>
              <RepairCompare
                repairInfo={response.result.repair_info}
                before={request.output_payload}
                after={response.repaired_output}
                revalidated={response.result.outcome === 'verified_repaired' ? true : undefined}
              />
            </div>
          )}

          {/* Show failed candidate when re-validation rejected it */}
          {wasPaidCandidateRejected && response.result.repair_info && (
            <div className="card card-pad" style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-bg)' }}>
              <div className="section-title" style={{ color: 'var(--danger)' }}>Re-validation failed</div>
              <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 8 }}>
                The candidate generated by the semantic-repair provider did not satisfy the verification policy.
                Groq proposes a repair, but Verified never trusts it directly — the candidate is passed through the same verification pipeline again before acceptance.
              </p>
              <p style={{ fontSize: 13, color: 'var(--danger)', fontWeight: 600 }}>
                Cannot repair this output safely.
              </p>
            </div>
          )}

          {/* Escalation button */}
          {canEscalate && !showPaymentFlow && (
            <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ fontSize: 16, marginBottom: 4 }}>Local repair couldn't resolve this</h3>
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Escalate to semantic repair — this triggers a payment-gated endpoint. A settled x402
                  payment (0.01 USDC on Algorand TestNet) is required before any repair is attempted.
                </p>
              </div>
              <button type="button" className="btn btn-accent" onClick={onEscalate} disabled={escalating}>
                {escalating && <span className="spinner" />}
                {escalating ? 'Requesting…' : 'Request semantic repair'}
              </button>
            </div>
          )}

          {escalationError && <ErrorBanner title="Escalation failed" message={escalationError} />}

          {/* Wallet payment flow */}
          {showPaymentFlow && challenge && (
            <div className="card card-pad" style={{ borderColor: 'var(--seal-border)', background: 'var(--seal-bg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <h3 style={{ fontSize: 18 }}>Payment required</h3>
                <Pill tone="warning">HTTP 402</Pill>
              </div>
              <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 16 }}>
                Semantic repair requires a settled x402 payment on Algorand TestNet.
                Connect your Algorand wallet to sign and submit the payment.
              </p>

              {/* Payment details from 402 response */}
              {challenge.accepts?.[0] && (
                <div className="kv-grid" style={{ marginBottom: 16 }}>
                  <div className="kv">
                    <span className="kv-label">Amount</span>
                    <span className="kv-value">{formatAtomicAmount(challenge.accepts[0].amount, challenge.accepts[0].extra?.decimals ?? 6)} USDC</span>
                  </div>
                  <div className="kv">
                    <span className="kv-label">Network</span>
                    <span className="kv-value">{challenge.accepts[0].network}</span>
                  </div>
                  <div className="kv">
                    <span className="kv-label">Asset</span>
                    <span className="kv-value mono">{challenge.accepts[0].asset}</span>
                  </div>
                  <div className="kv">
                    <span className="kv-label">Recipient</span>
                    <span className="kv-value mono" style={{ fontSize: 12, wordBreak: 'break-all' }}>{challenge.accepts[0].payTo}</span>
                  </div>
                  <div className="kv">
                    <span className="kv-label">Facilitator</span>
                    <span className="kv-value">GoPlausible AVM</span>
                  </div>
                </div>
              )}

              {/* Payment states */}
              {paymentState === 'idle' && (
                <div>
                  {!activeAddress ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 8, fontSize: 13 }}>
                      <span style={{ color: 'var(--warning)', fontWeight: 600 }}>⚠</span>
                      <span>Connect your Algorand wallet to proceed with payment.</span>
                    </div>
                  ) : (
                    <button type="button" className="btn btn-accent" onClick={onPay} style={{ width: '100%', justifyContent: 'center' }}>
                      Pay {formatAtomicAmount(challenge.accepts?.[0]?.amount, challenge.accepts?.[0]?.extra?.decimals ?? 6)} USDC
                    </button>
                  )}
                </div>
              )}

              {paymentState === 'signing' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: 'var(--accent-bg)', border: '1px solid var(--accent-border)', borderRadius: 8, fontSize: 13 }}>
                  <span className="spinner spinner-dark" />
                  <span>Awaiting wallet approval…</span>
                </div>
              )}

              {paymentState === 'submitting' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: 'var(--accent-bg)', border: '1px solid var(--accent-border)', borderRadius: 8, fontSize: 13 }}>
                  <span className="spinner spinner-dark" />
                  <span>Payment submitted — waiting for settlement…</span>
                </div>
              )}

              {paymentState === 'settled' && settlementTxId && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 8, fontSize: 13 }}>
                  <span style={{ color: 'var(--success)', fontWeight: 700 }}>✓</span>
                  <span>Payment settled</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-faint)', marginLeft: 'auto' }}>
                    <a href={algorandExplorerUrl(settlementTxId)} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-strong)' }}>
                      View on Explorer →
                    </a>
                  </span>
                </div>
              )}

              {paymentState === 'cancelled' && (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 8, fontSize: 13 }}>
                    <span style={{ color: 'var(--warning)' }}>⚠</span>
                    <span>Payment cancelled</span>
                  </div>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPaymentState('idle')} style={{ marginTop: 8 }}>
                    Try Again
                  </button>
                </div>
              )}

              {paymentState === 'failed' && (
                <div>
                  <ErrorBanner title="Payment failed" message={paymentError ?? 'Unknown error'} />
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPaymentState('idle')} style={{ marginTop: 8 }}>
                    Try Again
                  </button>
                </div>
              )}

              {/* Technical details */}
              {challenge.accepts?.[0] && (
                <details className="tech" style={{ marginTop: 12 }}>
                  <summary>Technical details</summary>
                  <div className="kv-grid" style={{ marginTop: 8 }}>
                    <div className="kv">
                      <span className="kv-label">x402 Version</span>
                      <span className="kv-value mono">{challenge.x402Version}</span>
                    </div>
                    <div className="kv">
                      <span className="kv-label">Scheme</span>
                      <span className="kv-value mono">{challenge.accepts[0].scheme}</span>
                    </div>
                    <div className="kv">
                      <span className="kv-label">Asset ID</span>
                      <span className="kv-value mono">{challenge.accepts[0].asset}</span>
                    </div>
                    <div className="kv">
                      <span className="kv-label">Atomic Amount</span>
                      <span className="kv-value mono">{challenge.accepts[0].amount}</span>
                    </div>
                    {challenge.accepts[0].extra?.feePayer && (
                      <div className="kv">
                        <span className="kv-label">Fee Payer</span>
                        <span className="kv-value mono" style={{ fontSize: 11 }}>{challenge.accepts[0].extra.feePayer}</span>
                      </div>
                    )}
                    {challenge.accepts[0].maxTimeoutSeconds && (
                      <div className="kv">
                        <span className="kv-label">Timeout</span>
                        <span className="kv-value">{challenge.accepts[0].maxTimeoutSeconds}s</span>
                      </div>
                    )}
                  </div>
                </details>
              )}
            </div>
          )}

          {paymentMeta && <PaymentSettledCard payment={paymentMeta} />}

          <ReceiptCard receipt={response.receipt} />

          <div className="card card-pad">
            <div className="copy-row" style={{ marginBottom: 10 }}>
              <div>
                <h3 style={{ fontSize: 16 }}>Tamper detection</h3>
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Flip a signed field on a client-side copy of this receipt and re-verify it — the real stored receipt
                  is never touched.
                </p>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={onTamperTest} disabled={tamperResult === 'checking'}>
                {tamperResult === 'checking' ? 'Checking…' : 'Test tamper detection'}
              </button>
            </div>
            {typeof tamperResult === 'object' && (
              <div style={{ marginTop: 8 }}>
                <Pill tone={tamperResult.valid ? 'success' : 'danger'}>
                  {tamperResult.valid ? 'Still valid (unexpected)' : 'Signature invalid — tampering detected'}
                </Pill>
                <p style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 6 }}>{tamperResult.details}</p>
              </div>
            )}
          </div>

          <div className="card card-pad">
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              This receipt isn't anchored to Algorand yet — anchoring batches multiple receipts together on a
              schedule, it isn't triggered per-request.{' '}
              <Link to="/anchoring" style={{ color: 'var(--accent-strong)', fontWeight: 600 }}>
                Go to Anchoring →
              </Link>
            </p>
          </div>

          <JsonView data={{ request, policy }} title="Raw request + policy" collapsible />
        </div>
      </div>
    </div>
  );
}
