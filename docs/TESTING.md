# TESTING.md — Verified

## 1. Purpose

This document defines the testing strategy and concrete test scenarios for Verified, covering local validation, deterministic repair, semantic repair, the x402 payment flow, re-validation, receipts, hashing, audit anchoring, privacy filtering, failure handling, and execution gating. No test code is included — this is scenario- and strategy-level, intended to guide whatever test implementation the hackathon team builds.

## 2. Testing Strategy Overview

| Layer | Strategy |
|---|---|
| Individual validation stages (schema, type, syntax, SQL safety, privacy) | Isolated unit-style tests against known-good and known-bad fixtures per stage |
| Deterministic repair | Isolated tests confirming pure, reproducible behavior; explicit tests confirming out-of-scope cases are *not* repaired |
| Escalation decision logic | Tests over the classification of findings into deterministic/semantic/not-repairable |
| x402 payment flow | Integration tests against the GoPlausible AVM facilitator (or its testnet equivalent), covering success and failure paths |
| Semantic-repair integration | Integration tests treating the semantic-repair API as an external dependency; failure/timeout simulation required |
| Re-validation | Tests confirming repaired output is never trusted without a second full pipeline pass |
| Receipts & hashing | Tests confirming receipt fields are correctly bound/hashed and that tampering is detectable |
| Merkle anchoring | Tests confirming Merkle tree construction, on-chain root submission, and proof reconstruction |
| Failure handling | Fault-injection tests for every external dependency (facilitator, semantic-repair API, Algorand network) |
| Execution gating | Tests against the downstream execution stand-in (TASKS.md Milestone 8) confirming it refuses to act without a valid, matching receipt |
| Privacy | Tests confirming sensitive content never appears in any artifact that crosses the local trust boundary |

Given the hackathon timeline, prioritize integration/end-to-end coverage of the full demo scenario (PRD.md §14) over exhaustive unit coverage of every stage; the scenarios below are ordered with that priority in mind.

## 3. Validation Stage Test Scenarios

- **Schema validation**
  - Valid output against its schema → no schema-stage findings.
  - Output missing a required field → blocking finding, `stage = schema`.
  - Output with an extra/unexpected field (per whatever the chosen schema formalism defines as strict/lenient — Milestone 0 decision) → finding severity consistent with that policy choice.
- **Type checking**
  - Field value matching declared type → no finding.
  - Field value of wrong type where lossless coercion is possible per policy → finding marked `repairable: deterministic`.
  - Field value of wrong type where coercion is not well-defined → finding marked `repairable: semantic` or `not_repairable`, per the classification rules decided in Milestone 0.
- **Syntax checking**
  - Syntactically valid SQL / function-call arguments → no finding.
  - Syntactically invalid SQL (e.g., malformed statement) → blocking finding, `stage = syntax`.
- **SQL safety checking**
  - Safe, well-scoped query → no finding.
  - Query matching an unsafe class (per the ruleset decided in Milestone 0) → blocking finding, `repairable: not_repairable` or `semantic` per the "never silently rewritten" rule (ARCHITECTURE.md §4.2) — test explicitly that such findings are **never** marked `repairable: deterministic`.
- **Privacy filtering**
  - Payload with no sensitive content → no redaction, unaffected pipeline flow.
  - Payload with content matching a sensitive category → confirm it is filtered/redacted **before** any escalation decision is evaluated, and confirm the unfiltered version never appears in any log or outbound call made in the test.

## 4. Deterministic Repair Test Scenarios

- Applying a defined deterministic rule to an eligible finding produces the expected, reproducible fixed output (same input → same output across repeated runs).
- A finding outside the enumerated deterministic rule set is **not** touched by deterministic repair, even if a "plausible" fix might exist — confirms rule-set discipline (ARCHITECTURE.md §4.2).
- Deterministic repair never triggers a network call (verifiable via network-call assertion/mocking in the test harness).
- Post-repair payload is passed to re-validation and confirmed to pass (for the intended success scenario) or still fail appropriately (for a deliberately unresolvable fixture).

## 5. Escalation Decision Test Scenarios

- All findings resolved by deterministic repair → no escalation triggered, receipt issued directly.
- At least one remaining `blocking` finding marked `repairable: semantic` → escalation triggered, HTTP 402 challenge issued.
- At least one remaining `blocking` finding marked `not_repairable` (e.g., unsafe SQL under the chosen policy) → rejection, no escalation attempted, `rejection_reasons` populated.

## 6. x402 Payment Flow Test Scenarios

- Escalation-eligible request → confirm HTTP 402 challenge is issued with well-formed payment terms.
- Valid `X-PAYMENT` resubmission → confirm facilitator verification/settlement is invoked and, on success, the flow proceeds to semantic-repair forwarding.
- Invalid/malformed `X-PAYMENT` → confirm rejection with `payment_failed` reason, and confirm no payload is forwarded to the semantic-repair API.
- Facilitator unreachable (simulated network failure) → confirm fail-closed rejection, no hang/timeout left unresolved.
- Facilitator reports settlement failure (e.g., insufficient funds, per whatever Algorand testnet failure mode is used in testing) → confirm rejection, no semantic-repair call made.
- Confirm `PaymentMetadata.payment_status` transitions are recorded accurately for each of the above (`pending` → `verified`/`settled`/`failed`).

### Phase 8 payment metadata tests (implemented)

- Settlement failure → 402 rejection, no handler invoked.
- Settlement failure never invokes SemanticRepairEngine.
- Successful settlement creates `PaymentMetadata` with `payment_status=settled`.
- `PaymentMetadata.facilitator` = "GoPlausible AVM Facilitator".
- `PaymentMetadata.settlement_network` = "Algorand".
- `PaymentMetadata.algorand_tx_ref` reflects actual settlement transaction.
- `PaymentMetadata.x402_challenge_ref` matches the request_id.
- `RepairInfo.payment_ref` references `PaymentMetadata.payment_id`.
- `verified_repaired` requires non-null `payment_ref` (Phase 8 invariant).
- `verified_repaired` with semantic repair cannot occur without settled payment.
- Failed payment cannot produce `verified_repaired`.
- Deterministic repair (free path) has `payment_ref=None`.

## 7. Semantic-Repair Integration Test Scenarios

- Successful escalation with a valid candidate fix returned → confirm the candidate is re-validated, not trusted directly.
- Candidate fix that still fails re-validation → confirm outcome is `rejected`, not `verified_repaired` — this is the core "verify after repair" test (Architecture Principle 4).
- Semantic-Repair API unreachable/timeout → confirm fail-closed rejection.
- Semantic-Repair API returns a malformed/unparseable response → confirm this is treated as a validation failure on re-validation (i.e., garbage output does not bypass the pipeline), not as a special-cased pass.
- Confirm the payload sent to the semantic-repair API in this test is the **filtered** payload, not the raw original (cross-check against the privacy filtering test in §3).

## 8. Re-validation Test Scenarios

- Deterministic-repair path: confirm re-validation runs and confirm a payload that still has issues after deterministic repair is not incorrectly marked `verified`.
- Semantic-repair path: same, using the semantic-repair candidate as input.
- Confirm re-validation is literally the same pipeline invocation as initial validation (e.g., by confirming identical stage ordering/behavior in test assertions), not a divergent implementation — this test protects against future code drift breaking Architecture Principle 4.

## 9. Receipt & Hashing Test Scenarios

- Every processed request (regardless of outcome) produces exactly one `VerificationReceipt` — including rejections.
- `output_hash` in the receipt matches a hash computed over the actual final output (post-repair, where applicable) — not the pre-repair output.
- Changing any bound field (output, schema ref/version, repair summary, validator version) changes `receipt_hash` — confirms tamper-evidence at the hashing level (Architecture Principle 7).
- A receipt for a `verified_repaired` outcome has a non-null `repair_summary_hash` and a `payment_ref` with `payment_status = settled`; a receipt for a `verified` (non-repaired) outcome does not require a payment ref — confirms the DATA_MODEL.md §4 invariant.
- Attempted tampering with a stored receipt (e.g., manually altering `outcome` in test fixtures) is detectable by recomputing and comparing `receipt_hash`.
- `receipt_hash` determinism: the same logical receipt always produces the same hash.
- `repair_summary_hash` is deterministic: the same `RepairInfo` always produces the same hash; a change to `RepairInfo` changes `repair_summary_hash`.

### Phase 8 receipt tests (implemented)

- Tamper outcome → hash changes.
- Tamper output_hash → hash changes.
- Tamper schema_ref_and_version → hash changes.
- Tamper validator_version → hash changes.
- output_hash matches FINAL payload (not pre-repair).
- repair_summary_hash present for repaired, absent for verified.
- No raw payload content in receipt.

## 10. Local Verification Record Store Test Scenarios (Phase 9 — implemented)

- Save a finalized record and retrieve by request_id — receipt_id, outcome, receipt_hash match.
- Save a finalized record and retrieve by receipt_id — request_id, receipt_hash match.
- receipt_hash is preserved exactly (not recalculated).
- output_hash is preserved exactly.
- All three outcomes (verified, verified_repaired, rejected) are persistable.
- Semantic repaired record preserves payment_ref, payment_status=settled, algorand_tx_ref.
- Duplicate save with same request_id + receipt_id is idempotent (no duplicate).
- Duplicate save with same request_id but different receipt_id raises IntegrityError.
- New records start as unanchored.
- list_unanchored_records() returns new records with deterministic ordering.
- mark_anchored() updates status and excludes from unanchored query.
- Records survive database close/reopen (restart persistence).
- Private keys, X-PAYMENT, recovery phrases, and raw payloads are never stored.
- Nonexistent record queries return None.
- Empty database returns empty list from list_unanchored_records().
- Receipt and Result roundtrip correctly through serialization.
- Multiple distinct records can be stored and retrieved.

## 11. Audit / Merkle Anchoring Test Scenarios

- Batch of N local records → confirm Merkle root is computed correctly and deterministically over their `receipt_hash` values.
- Confirm the anchoring transaction submitted to Algorand contains only the Merkle root (and necessary transaction metadata) — explicitly assert no raw payload or unhashed receipt content appears in the transaction payload.
- After anchoring, confirm a Merkle proof can be reconstructed for a specific included receipt and independently validated against the on-chain root (this is the demo's core audit-integrity proof, PRD.md §13).
- Simulate anchoring failure (network/Algorand unavailability) → confirm receipts already issued are unaffected, and confirm the record is retried/re-attempted rather than lost (ARCHITECTURE.md §10).
- Confirm records not yet anchored are still correctly retrievable and their receipts remain valid/usable for execution gating even while `anchoring_status = unanchored` (DATA_MODEL.md §4 invariant).

### Phase 10 Merkle anchoring tests (implemented)

**Merkle tree (18 tests):**
- Empty tree returns None root.
- Single leaf: root = leaf.
- Two leaves: root = SHA256(A || B).
- Three leaves: odd node doubled, root matches manual computation.
- Four leaves: balanced tree.
- Same inputs → same root (determinism).
- Changed leaf → different root.
- Changed order → different root.
- Proof generation + verification for each leaf.
- Proof fails with wrong root, wrong leaf, or wrong index.
- Single leaf and odd-count tree proofs.

**Anchoring service (21 tests):**
- Empty batch → no_records_to_anchor, no Algorand call.
- Batch selection: fewer/equal/more than batch size.
- Only unanchored records selected.
- Merkle root computed from batch.
- Transaction ID stored from Algorand.
- Merkle root sent to Algorand.
- Submission failure → records remain unanchored.
- Failed batch can be retried.
- Successful batch not selected again.
- No fake tx_ref on failure.
- All records marked anchored after success.
- Same merkle_root for entire batch.
- Same anchor_tx_ref for entire batch.
- Anchored records disappear from unanchored query.
- Private key never in logs.
- Raw payload never submitted.
- X-PAYMENT never submitted.
- Deterministic ordering → deterministic root.

## 12. Privacy Test Scenarios

- End-to-end trace of a full escalated request confirming that no unfiltered sensitive content appears in: the HTTP request sent to the semantic-repair API, any log output, the receipt, the local record's externally-shareable fields, or any Algorand transaction.
- Negative test: a payload engineered to contain content matching a sensitive category is confirmed filtered even when it appears in a non-obvious location within the structured payload (e.g., nested field), to the extent the chosen filtering mechanism (Milestone 0 decision) claims to support.

## 12. Failure Handling Test Scenarios (Consolidated Fault Injection)

For each of: facilitator unreachable, Algorand network unreachable, semantic-repair API unreachable, semantic-repair API slow/timeout, Algorand anchoring submission failure —
- Confirm the system fails closed (no `verified`/`verified_repaired` outcome is produced under uncertainty).
- Confirm the failure is surfaced with an explicit reason where applicable (payment/repair failures) or handled via retry without blocking receipt issuance (anchoring failures only, per ARCHITECTURE.md §10).
- Confirm no partial/inconsistent state is left in the local record store (e.g., no record stuck indefinitely in `pending` payment status without an eventual failure resolution in the test's time bound).

## 13. Execution-Gating Test Scenarios

- Downstream execution stand-in (TASKS.md Milestone 8) presented with a `verified` receipt and matching output → proceeds.
- Presented with a `rejected` receipt → refuses, regardless of how "close" the output looks to valid.
- Presented with a `verified` receipt but a *different* output than the one the receipt's `output_hash` covers → refuses (mismatch detection).
- Presented with a malformed/tampered receipt (hash does not recompute correctly) → refuses.

## 14. Out of Scope for MVP Testing

Per PRD.md's MVP scope, the following are **not** required test coverage for the hackathon MVP (candidates for future scope):
- Load/performance/throughput testing (no performance targets are defined in this document set — PRD.md §9).
- Multi-tenant isolation testing.
- Exhaustive SQL dialect coverage testing beyond the dialect(s) chosen in Milestone 0.
- Formal security audit / penetration testing (see THREAT_MODEL.md for the threat-level analysis that substitutes for this at hackathon scale).
