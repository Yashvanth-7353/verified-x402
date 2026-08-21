// Mirrors backend/docs/API.md exactly. Do not add fields the backend does not send.

export type OutputType = 'json' | 'sql' | 'function_call_args';
export type Severity = 'info' | 'warning' | 'blocking';
export type Repairability = 'deterministic' | 'semantic' | 'not_repairable';
export type RepairType = 'deterministic' | 'semantic' | 'none';
export type PaymentStatus = 'pending' | 'verified' | 'settled' | 'failed';
export type VerificationOutcome = 'verified' | 'verified_repaired' | 'rejected';

export interface VerificationRequest {
  request_id: string;
  submitted_at: string;
  output_type: OutputType;
  output_payload: Record<string, unknown>;
  schema_ref: string;
  agent_identifier: string;
  privacy_class_hint?: string | null;
}

export interface SchemaPolicy {
  schema_id: string;
  version: string;
  output_type: OutputType;
  schema_definition: Record<string, unknown>;
  deterministic_repair_rules_ref?: string | null;
  sql_safety_ruleset_ref?: string | null;
  privacy_policy_ref: string;
}

export interface ValidationFinding {
  finding_id: string;
  stage: string;
  severity: Severity;
  description: string;
  field_path?: string | null;
  repairable: Repairability;
}

export interface RepairInfo {
  repair_id: string;
  repair_type: RepairType;
  findings_addressed: string[];
  pre_repair_output_hash: string;
  post_repair_output_hash: string;
  deterministic_rule_refs?: string[] | null;
  semantic_repair_provider_ref?: string | null;
  payment_ref?: string | null;
}

export interface VerificationResult {
  result_id: string;
  request_ref: string;
  findings: ValidationFinding[];
  repair_info?: RepairInfo | null;
  outcome: VerificationOutcome;
  rejection_reasons?: string[] | null;
  validator_version: string;
  completed_at: string;
}

export interface VerificationReceipt {
  receipt_id: string;
  request_id_ref: string;
  outcome: VerificationOutcome;
  output_hash: string;
  schema_ref_and_version: string;
  repair_summary_hash?: string | null;
  validator_version: string;
  issued_at: string;
  receipt_hash: string;
  signature?: string | null;
  signature_algorithm?: string | null;
  signing_key_id?: string | null;
}

export interface PaymentMetadata {
  payment_id: string;
  x402_challenge_ref: string;
  payment_status: PaymentStatus;
  facilitator: string;
  settlement_network: string;
  algorand_tx_ref?: string | null;
  amount_and_asset: { scheme?: string; asset?: string; amount?: string } | unknown;
  verified_at?: string | null;
}

export interface VerifyResponse {
  result: VerificationResult;
  receipt: VerificationReceipt;
}

export interface SemanticRepairResponse extends VerifyResponse {
  payment_metadata?: PaymentMetadata | null;
}

/**
 * Actual shape observed from a live 402 response's `payment-required` header
 * (base64 JSON) — the x402 v2 protocol shape. This differs from the v1-style
 * example in docs/API.md (flat maxAmountRequired/payTo/asset); the live
 * server sends v2, so the frontend targets what it actually returns.
 */
export interface PaymentRequiredChallenge {
  x402Version: number;
  error?: string;
  resource: {
    url: string;
    description: string;
    mimeType: string;
  };
  accepts: Array<{
    scheme: string;
    network: string;
    asset: string;
    amount: string;
    payTo: string;
    maxTimeoutSeconds?: number;
    extra?: { decimals?: number; feePayer?: string; genesisHash?: string; genesisId?: string } & Record<string, unknown>;
  }>;
}

export interface AnchorResponse {
  status: 'anchored' | 'no_records_to_anchor' | string;
  leaf_count: number;
  merkle_root: string | null;
  transaction_id: string | null;
  error: string | null;
}

export interface ReceiptVerifyResponse {
  valid: boolean;
  signature_valid: boolean;
  receipt_integrity_valid: boolean;
  algorithm: string;
  signing_key_id: string | null;
  details: string;
}

export interface PublicKeyResponse {
  algorithm: string;
  key_id: string;
  public_key: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

/** Structured API failure — distinguishes HTTP status from message. */
export class ApiError extends Error {
  status: number;
  body: unknown;
  challenge?: PaymentRequiredChallenge;

  constructor(status: number, message: string, body?: unknown, challenge?: PaymentRequiredChallenge) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
    this.challenge = challenge;
  }
}

// ---- Phase 15: Server-side records ----

export interface RecordSummary {
  record_id: string;
  request_id: string;
  receipt_id: string;
  outcome: VerificationOutcome;
  receipt_hash: string;
  output_hash: string | null;
  payment_status: PaymentStatus | null;
  anchoring_status: string;
  merkle_root: string | null;
  anchor_tx_ref: string | null;
  created_at: string;
  schema_ref_and_version?: string | null;
  validator_version?: string | null;
  signing_key_id?: string | null;
  signature_algorithm?: string | null;
  repair_type?: string | null;
  payment_facilitator?: string | null;
  settlement_network?: string | null;
}

export interface RecordsListResponse {
  records: RecordSummary[];
  total: number;
  offset: number;
  limit: number;
}

// ---- Phase 15: Merkle inclusion proof ----

export interface ProofNode {
  hash: string;
  position: 'left' | 'right';
}

export interface MerkleProofResponse {
  record_id: string;
  receipt_hash: string;
  merkle_root: string;
  leaf_index: number;
  batch_size: number;
  proof: ProofNode[];
  anchor_tx_ref: string | null;
  verification: {
    valid: boolean;
    details: string;
  };
}
