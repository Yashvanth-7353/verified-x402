import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { semanticRepair, verifyReceipt } from '../api/client';
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
import { PaymentRequiredCard, PaymentSettledCard } from '../components/PaymentCard';
import { type Stage, PipelineStages } from '../components/PipelineStages';
import { ReceiptCard } from '../components/ReceiptCard';
import { RepairCompare } from '../components/RepairCompare';
import { OutcomeBadge, Pill } from '../components/StatusBadge';
import { VerificationSeal } from '../components/VerificationSeal';
import { formatDateTime } from '../lib/format';
import { appendSessionEntry } from '../lib/session';

interface LocationState {
  request: VerificationRequest;
  policy: SchemaPolicy;
  response: VerifyResponse;
}

export function Result() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  const [response, setResponse] = useState<VerifyResponse | SemanticRepairResponse | undefined>(state?.response);
  const [escalating, setEscalating] = useState(false);
  const [escalated, setEscalated] = useState(false);
  const [challenge, setChallenge] = useState<PaymentRequiredChallenge | null>(null);
  const [escalationError, setEscalationError] = useState<string | null>(null);

  const [tamperResult, setTamperResult] = useState<'idle' | 'checking' | { valid: boolean; details: string }>('idle');

  const paymentMeta = response && 'payment_metadata' in response ? response.payment_metadata : null;

  useEffect(() => {
    if (!state || !response) return;
    appendSessionEntry({
      logged_at: new Date().toISOString(),
      request_id: state.request.request_id,
      agent_identifier: state.request.agent_identifier,
      outcome: response.result.outcome,
      receipt_id: response.receipt.receipt_id,
      receipt_hash: response.receipt.receipt_hash,
      had_payment: Boolean(paymentMeta),
      result: response.result,
      receipt: response.receipt,
    });
    // Log once per response identity, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response?.receipt.receipt_id]);

  const stages = useMemo<Stage[]>(() => {
    if (!response) return [];
    const hasRepair = Boolean(response.result.repair_info);
    const isSemanticRepair = response.result.repair_info?.repair_type === 'semantic';
    return [
      { key: 'submitted', label: 'Submitted', state: 'done' },
      { key: 'validated', label: 'Validated', state: 'done' },
      {
        key: 'escalated',
        label: 'Escalated',
        state: !isSemanticRepair && !challenge && !escalating ? 'skipped' : escalating ? 'active' : 'done',
      },
      {
        key: 'paid',
        label: 'Paid',
        state:
          !isSemanticRepair && !challenge
            ? 'skipped'
            : paymentMeta?.payment_status === 'settled'
              ? 'done'
              : challenge
                ? 'pending'
                : escalating
                  ? 'active'
                  : 'skipped',
      },
      { key: 'repaired', label: 'Repaired', state: hasRepair ? 'done' : 'skipped' },
      { key: 'revalidated', label: 'Re-validated', state: hasRepair ? 'done' : 'skipped' },
      { key: 'receipt', label: 'Receipt', state: response.result.outcome === 'rejected' ? 'failed' : 'done' },
    ];
  }, [response, challenge, escalating, paymentMeta]);

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
    setEscalationError(null);
    setChallenge(null);
    try {
      const paid = await semanticRepair({ request, policy });
      setResponse(paid);
      setEscalated(true);
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        setChallenge(e.challenge ?? null);
        setEscalated(true);
      } else {
        setEscalationError(e instanceof Error ? e.message : 'Semantic repair failed.');
      }
    } finally {
      setEscalating(false);
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

  const canEscalate = response.result.outcome === 'rejected' && !escalated;

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
        </div>

        <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="card card-pad">
            <div className="section-title">Findings</div>
            <FindingsList findings={response.result.findings} />
          </div>

          {response.result.repair_info && (
            <div className="card card-pad">
              <div className="section-title">Repair</div>
              <RepairCompare repairInfo={response.result.repair_info} before={request.output_payload} />
            </div>
          )}

          {canEscalate && (
            <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
              <div>
                <h3 style={{ fontSize: 16, marginBottom: 4 }}>Local repair couldn't resolve this</h3>
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Escalate to semantic repair — this calls the payment-gated endpoint and will require a settled x402
                  payment before any repair is attempted.
                </p>
              </div>
              <button type="button" className="btn btn-accent" onClick={onEscalate} disabled={escalating}>
                {escalating && <span className="spinner" />}
                {escalating ? 'Requesting…' : 'Request semantic repair'}
              </button>
            </div>
          )}

          {escalationError && <ErrorBanner title="Escalation failed" message={escalationError} />}

          {challenge && !paymentMeta && (
            <div>
              <PaymentRequiredCard challenge={challenge} />
              <p style={{ fontSize: 12.5, color: 'var(--text-faint)', marginTop: 10 }}>
                Browser-side wallet signing isn't part of the current API contract — Verified's backend never receives
                or handles a private key from this UI. Settlement for this demo is completed via the backend's x402
                client (see <code className="mono">backend/scripts/e2e_client.py</code>); once settled, refreshing this
                escalation will show the paid, repaired result below.
              </p>
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
