# DESIGN.md — Verified

## 1. Purpose

This document defines API and system-level design principles for Verified: request/response concepts, the validation and repair pipelines as designed contracts, receipt structure, error handling, idempotency, privacy boundaries, and the execution-gating model. No code or concrete API schema (e.g., OpenAPI) is included — this is conceptual/interface-level design, consistent with the entities in DATA_MODEL.md and the flows in ARCHITECTURE.md.

## 2. Design Principles

- **Single responsibility per stage**: each validation stage (schema, type, syntax, SQL safety, privacy) only ever produces `ValidationFinding` entries — it does not itself decide escalation or rejection. Decisioning is centralized in the Escalation Decision Logic (ARCHITECTURE.md §4.1).
- **Idempotent verification given identical inputs**: verifying the same `output_payload` against the same `schema_ref`/version with the same `validator_version` should be expected to produce the same findings — determinism is required for the local pipeline (repair excluded, since semantic repair by nature may not be perfectly reproducible; see §7).
- **Receipts are the only externally trusted artifact**: a downstream system should never need to inspect internal `ValidationFinding` detail to decide whether to execute — it should be able to check the `VerificationReceipt.outcome` and hash bindings alone (Architecture Principle 5).
- **Payload minimization outward**: any data that crosses the local trust boundary (to the semantic-repair API) is the minimum necessary, post-privacy-filtering. No component external to the local pipeline needs to know more than that.
- **Explicit over implicit failure**: every rejection carries reasons; there is no "silent" rejection path in the design (ARCHITECTURE.md §10 / THREAT_MODEL.md).

## 3. Request/Response Concepts

### 3.1 Verification Request (conceptual)

A verification request conceptually carries what's defined in `VerificationRequest` (DATA_MODEL.md §3.1): the output to verify, its type, a reference to the schema/policy to check against, and agent identification. The exact transport (REST/JSON, gRPC, etc.) is **TBD** — not assumed here, since no transport was specified in the project brief.

### 3.2 Verification Response (conceptual)

Two response shapes are possible depending on flow:

1. **Synchronous outcome** — for local-only paths (no escalation needed), the response conceptually returns the `VerificationReceipt` directly once the pipeline completes.
2. **Escalation required** — if semantic repair is needed, the initial response is an HTTP 402–style challenge (per x402) rather than a receipt. The receipt is only returned once the agent completes the payment flow and Verified completes re-validation (ARCHITECTURE.md §5.1).

This two-phase shape (challenge, then completed result) mirrors x402's design and should not be flattened into a single call — the design deliberately keeps "payment required" as a distinct response state from "verification complete."

### 3.3 Status Polling / Long-Running Consideration

Semantic-repair escalation involves an external network call (facilitator + repair API) that may not complete instantly. Whether Verified's API is fully synchronous (agent's request blocks until receipt or 402) or supports async polling for the escalated path is **TBD** — an implementation decision to be made based on demo requirements and the semantic-repair API's expected latency (not specified in the brief).

## 4. Validation Pipeline as a Contract

The validation pipeline (ARCHITECTURE.md §4) is designed as an ordered, composable sequence of stages, each with a narrow contract:

- **Input**: the current payload state (original or post-repair) + the applicable `SchemaPolicy`.
- **Output**: a list of `ValidationFinding` entries (possibly empty).
- **No side effects**: stages do not mutate the payload or make network calls (with the sole exception of the Semantic-Repair API interaction, which is explicitly outside the validation-stage contract and lives in the Escalation flow, ARCHITECTURE.md §5).

This contract is what makes re-validation (§6) safe to implement as "run the same pipeline again" rather than a bespoke second code path.

## 5. Repair Pipeline as a Contract

- **Deterministic repair**: input is the payload + the specific `blocking`/`repairable: deterministic` findings; output is a new payload + a `RepairInfo` record (`repair_type = deterministic`). Must be a pure function of (payload, findings, rule set) — no external calls, no randomness (ARCHITECTURE.md §4.2).
- **Semantic repair**: input is the privacy-filtered payload + the specific `repairable: semantic` findings; output is a candidate payload + provider metadata, returned from the external Semantic-Repair API. This output is explicitly **untrusted** until it passes back through the validation pipeline contract (§4).

## 6. Re-validation Design

Re-validation is not a separate implementation — it is defined as: *invoke the validation pipeline contract (§4) again, using the repaired payload as input*. This design choice directly enforces Architecture Principle 4 ("Verify after repair") at the design level rather than relying on a separate policy check. There is no code path in the design that allows a repaired payload to reach `VerificationResult.outcome = verified_repaired` without passing through this same contract.

## 7. Idempotency Considerations

- **Local validation**: given the same input payload, schema version, and validator version, the local pipeline should produce the same findings (deterministic by design, §2).
- **Deterministic repair**: same input → same output, by construction (pure function).
- **Semantic repair**: **not guaranteed idempotent** — a second call to the semantic-repair API for the same input is not guaranteed to return an identical candidate fix (it is an external, model-backed service). Design implication: Verified should treat each escalation as its own priced event (a second attempt after a failed re-validation is a new payment-gated request, not a free retry) unless a specific retry policy is defined — **TBD**, retry policy is an open design decision (see TASKS.md).
- **Request replay**: if an agent resubmits an identical `VerificationRequest` (same request_id or same content) after already receiving a receipt, the design should define whether this returns the cached prior receipt or reprocesses. **TBD** — recommended default direction (not yet a firm decision) is to return the existing receipt for an exact request_id match to avoid double-charging for semantic repair, but this needs to be finalized (see THREAT_MODEL.md, "replayed payments" for the related security angle).

## 8. Receipt Structure (Design-Level)

As defined in DATA_MODEL.md §3.7, the receipt is designed to be:
- **Self-contained for verification purposes**: a downstream consumer can check `outcome`, `output_hash`, `schema_ref_and_version`, and `receipt_hash` without needing access to Verified's internal record store.
- **Minimal**: no raw payload, no raw repair diff — only hashes and references, so receipts can be logged, shared, or included in a Merkle tree freely (DATA_MODEL.md §3.7 design note).
- **Versioned**: `validator_version` is always included, so a receipt's meaning is pinned to the exact validation logic that produced it (Architecture Principle 7).

## 9. Error Handling

Design categories of error, and their handling posture:

| Error Category | Example | Design Response |
|---|---|---|
| Client input error | Malformed request, unknown schema_ref | Reject immediately with explicit reason; no repair/escalation attempted |
| Local validation failure (repairable) | Blocking findings, deterministic-repairable | Attempt deterministic repair, then re-validate |
| Local validation failure (not repairable locally) | Blocking findings requiring semantic judgment | Escalate per §3.2, subject to eligibility rules (ARCHITECTURE.md §4.2/§4.3) |
| Payment failure | Facilitator rejects/settlement fails | Reject with reason `payment_failed`; no payload forwarded to semantic-repair API (ARCHITECTURE.md §10) |
| External service failure | Semantic-Repair API unreachable/error/timeout | Reject with reason `semantic_repair_unavailable`; fail closed |
| Re-validation failure | Semantic repair candidate still fails validation | Reject with reason `repair_failed_revalidation`; fail closed, no partial trust extended to the candidate |
| Anchoring failure | Algorand anchoring transaction fails/unreachable | Does **not** produce a rejection or affect the receipt already issued; retried asynchronously (ARCHITECTURE.md §10) |

All rejection paths populate `VerificationResult.rejection_reasons` (DATA_MODEL.md §3.6) — there is no design path that returns an ambiguous or reason-less rejection.

## 10. Privacy Boundaries (Design-Level)

- The Privacy Filter stage (ARCHITECTURE.md §4.4) runs **before** the escalation decision is even evaluated, not conditionally after — so payload content classification does not depend on, or get skipped by, the outcome of other validation stages.
- Design rule: **no component past the Escalation Decision Logic may access the un-filtered payload.** Only the filtered/minimized payload is available to the x402 Payment Handler and the Semantic-Repair API Client.
- Design rule: the Receipt Generator and Merkle Anchoring Service never receive the raw payload at all — only hashes computed earlier in the pipeline (DATA_MODEL.md §3.7 design note, Architecture Principle 6).

## 11. Execution-Gating Model

This is the concrete design realization of "No valid proof, no execution":

- Verified's own responsibility ends at issuing a `VerificationReceipt`. Verified does **not** execute the agent's downstream action.
- A downstream execution system (out of Verified's scope, but part of the overall demo) is expected to implement a simple, well-defined contract: **do not execute unless presented with a `VerificationReceipt` whose `outcome` is `verified` or `verified_repaired`, whose `output_hash` matches the output about to be executed, and (optionally, for stricter deployments) whose inclusion in an anchored Merkle root can be confirmed.**
- This gating contract is intentionally simple and payload-hash-based so that it can be implemented by any downstream consumer without needing to understand Verified's internal pipeline.
- Fail-closed is structural, not policy: there is no `outcome` value other than `verified` / `verified_repaired` / `rejected` (DATA_MODEL.md §3.6) — an execution system checking for the two "pass" values by construction cannot be tricked into accepting an ambiguous state, because no ambiguous state exists in the model.

## 12. Explicit Design TBDs

| Area | Decision Needed |
|---|---|
| Transport protocol for the verification API | REST/JSON vs. other |
| Sync vs. async handling of the escalated (paid) path | Blocking call vs. polling |
| Retry policy for failed semantic-repair attempts | Free retry vs. new priced event |
| Request replay / idempotency-key handling | Return cached receipt vs. reprocess |
| Receipt signing mechanism | Whether/how local receipts are signed |

These mirror and extend the TBDs listed in ARCHITECTURE.md §11 and DATA_MODEL.md §5, viewed from the design/interface angle.
