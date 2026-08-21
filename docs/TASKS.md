# TASKS.md — Verified

## 1. Purpose

A practical, dependency-ordered implementation roadmap for a hackathon team building Verified. Tasks are grouped into milestones. Each task notes whether it is **MVP-critical** or **optional/future**. This roadmap assumes the architecture in ARCHITECTURE.md, data model in DATA_MODEL.md, and design in DESIGN.md as the reference; several tasks below exist specifically to resolve the TBDs flagged in those documents.

## 2. Milestone 0 — Foundational Decisions (blocks nearly everything)

*MVP-critical.* These resolve the TBDs that everything downstream depends on.

- [ ] Decide the schema/typing formalism used for `SchemaPolicy.schema_definition` (ARCHITECTURE.md §4.2, DATA_MODEL.md §3.2).
- [ ] Decide the SQL dialect(s) supported and the SQL safety rule classification approach (ARCHITECTURE.md §4.3).
- [ ] Decide the privacy filter taxonomy and detection mechanism (ARCHITECTURE.md §4.4).
- [ ] Decide the cryptographic hash algorithm(s) used for output hashing, repair hashing, and receipt hashing (DATA_MODEL.md §3.7).
- [ ] Decide the enumerated deterministic repair rule set for the MVP demo (ARCHITECTURE.md §4.2).
- [ ] Decide the transport protocol for the verification API (DESIGN.md §12).
- [ ] Decide wallet/key custody model for the agent side of the x402 flow (PRD.md §4, AGENTS.md §3).
- [ ] Confirm exact x402 payment terms conventions to adopt (price representation, asset, expiry) in coordination with GoPlausible AVM facilitator requirements (ARCHITECTURE.md §5.1).

*Dependency note:* Milestones 1–4 below can begin in parallel once their relevant subset of Milestone 0 decisions are made (e.g., local pipeline work doesn't need the payment-terms decision).

## 3. Milestone 1 — Local Validation Pipeline (MVP-critical)

Depends on: Milestone 0 (schema formalism, SQL dialect/rules, privacy taxonomy, hash algorithm).

- [ ] Implement Ingestion / Request Handler accepting a `VerificationRequest`-shaped input.
- [ ] Implement Privacy Filter pre-check stage (runs first, unconditionally).
- [ ] Implement Schema Validator stage.
- [ ] Implement Type Checker stage.
- [ ] Implement Syntax Checker stage (for `sql` and `function_call_args` output types).
- [ ] Implement SQL Safety Checker stage.
- [ ] Implement `ValidationFinding` aggregation across stages.
- [ ] Unit-verify each stage in isolation against known-good and known-bad fixtures (see TESTING.md §3).

## 4. Milestone 2 — Deterministic Repair & Escalation Decision (MVP-critical)

Depends on: Milestone 1.

- [ ] Implement the enumerated deterministic repair rule set decided in Milestone 0.
- [ ] Implement Escalation Decision Logic: classify unresolved `blocking` findings as `deterministic` / `semantic` / `not_repairable`.
- [ ] Implement the "unsafe SQL is never silently rewritten" rule as a hard constraint in the decision logic (ARCHITECTURE.md §4.2, §5).
- [ ] Wire re-validation: after deterministic repair, re-run the Milestone 1 pipeline on the repaired payload (DESIGN.md §6).
- [ ] Verify local-only pass and local-only reject paths end-to-end without any network calls.

## 5. Milestone 3 — x402 Payment Flow (MVP-critical) ✅ Phase 8 hardened

Depends on: Milestone 0 (payment terms convention), Milestone 2 (escalation decision producing the trigger).

- [x] Implement HTTP 402 challenge issuance when escalation is required.
- [x] Implement `X-PAYMENT` header acceptance and parsing on resubmission.
- [x] Integrate with GoPlausible AVM facilitator client for payment verification/settlement on Algorand.
- [x] Implement `PaymentMetadata` record creation and status tracking (`pending` → `verified`/`settled`/`failed`).
- [x] Implement fail-closed behavior on facilitator/network failure (reject, no payload forwarded — ARCHITECTURE.md §10).
- [x] End-to-end test: trigger escalation, complete a real (or testnet) payment, confirm settlement is observed correctly.
- [x] Phase 8: Custom middleware settles payment BEFORE calling handler, making `ProcessSettleResult` available via `request.state`.
- [x] Phase 8: `PaymentMetadata` created from actual settlement result with `payment_status=settled`, `algorand_tx_ref` from real settlement.
- [x] Phase 8: `RepairInfo.payment_ref` set to `PaymentMetadata.payment_id` for semantic repair outcomes.

## 6. Milestone 4 — Semantic-Repair Escalation (MVP-critical)

Depends on: Milestone 3 (payment must be settled before this triggers, per DATA_MODEL.md §4 invariant).

- [ ] Implement Semantic-Repair API client (forwarding only the privacy-filtered payload).
- [ ] Implement candidate-fix intake and re-validation via the Milestone 1 pipeline (no direct trust extended to the candidate).
- [ ] Implement outcome resolution: `verified_repaired` on re-validation pass, `rejected` on re-validation fail.
- [ ] Implement fail-closed behavior on semantic-repair API failure/timeout.
- [ ] End-to-end test: full escalation → payment → semantic repair → re-validation → receipt loop.

## 7. Milestone 5 — Receipts (MVP-critical) ✅ Phase 8 hardened

Depends on: Milestones 1–4 (needs outcomes from all paths).

- [x] Implement `VerificationReceipt` generation for all three outcomes (`verified`, `verified_repaired`, `rejected`).
- [x] Implement receipt hashing (binding output hash, schema ref+version, repair summary hash, validator version — ARCHITECTURE.md §7).
- [ ] Decide and, if in scope, implement receipt signing (DESIGN.md §12 TBD) — otherwise explicitly deferred to future scope with a note in the demo narrative.
- [x] Verify receipts are produced for **every** request, including all rejection paths (no reason-less/receiptless outcome — DESIGN.md §9).
- [x] Phase 8: Receipt invariant enforcement — `verified_repaired` with semantic repair requires non-null `repair_info.payment_ref`.
- [x] Phase 8: `output_hash` always reflects the FINAL validated output (post-repair), never pre-repair.
- [x] Phase 8: `repair_summary_hash` is present when repair occurred, absent otherwise.
- [x] Phase 8: `receipt_hash` is deterministic (same data → same hash) and tamper-evident (any field change → different hash).

## 8. Milestone 6 — Local Verification Record Store (MVP-critical)

Depends on: Milestone 5.

- [ ] Implement persistence of `LocalVerificationRecord` (result + receipt + anchoring status).
- [ ] Implement retrieval by `request_id`/`receipt_id` for later audit/demo purposes.
- [ ] Confirm raw payload content is retained only locally and never included in any outward-facing artifact beyond what Milestone 4 already sends to the semantic-repair API.

## 9. Milestone 7 — Merkle Anchoring on Algorand (MVP-critical)

Depends on: Milestone 6.

- [ ] Decide the anchoring trigger condition for the demo (time-based, count-based, or manual — ARCHITECTURE.md §11).
- [ ] Implement Merkle tree construction over a batch of `receipt_hash` values.
- [ ] Implement Algorand anchoring transaction submission carrying only the Merkle root.
- [ ] Implement `MerkleInclusion` and `AnchorTransaction` record creation/linking back to `LocalVerificationRecord`.
- [ ] Implement retry handling for anchoring failures (does not block receipt issuance — ARCHITECTURE.md §10).
- [ ] End-to-end test: anchor a batch, then independently reconstruct a Merkle proof for a specific receipt and confirm it validates against the on-chain root.

## 10. Milestone 8 — Execution-Gating Demo Consumer (MVP-critical for demo credibility)

Depends on: Milestone 5.

- [ ] Build a minimal downstream "execution" stand-in that only proceeds given a `VerificationReceipt` with a passing outcome and matching `output_hash` (DESIGN.md §11).
- [ ] Demonstrate this consumer refusing to execute on a `rejected` receipt or a mismatched output/receipt pair.

## 11. Milestone 9 — Demo Assembly & Rehearsal (MVP-critical)

Depends on: Milestones 1–8.

- [ ] Script the full demo scenario from PRD.md §14 (local pass, unsafe-SQL local reject, escalated semantic repair with real x402/Algorand flow, receipt issuance, Merkle anchoring + proof).
- [ ] Prepare visibility into the x402 HTTP 402 → `X-PAYMENT` → facilitator sequence (e.g., logs or a simple trace view) for judges (PRD.md §13).
- [ ] Prepare an Algorand explorer view showing the anchored Merkle root transaction, and a walkthrough proving a specific receipt's inclusion without exposing raw payload data.
- [ ] Rehearse failure-path fallback in case of live network issues during judging (e.g., recorded trace as backup).

## 12. Optional / Future Scope Tasks (Explicitly Not MVP)

- [ ] Multi-agent/multi-tenant policy isolation (PRD.md §11).
- [ ] Semantic-repair provider marketplace / multiple providers (PRD.md §11).
- [ ] On-chain receipt-verification smart contract beyond simple Merkle anchoring (PRD.md §11).
- [ ] Formal policy authoring language/UI (PRD.md §11).
- [ ] Broader SQL dialect/query-safety coverage beyond demo scope (PRD.md §10, §11).
- [ ] Performance/latency/cost benchmarking against defined SLAs (PRD.md §9, §11).
- [ ] Local dashboard for recent verification outcomes (PRD.md §12).
- [ ] Configurable repair-confidence thresholds (PRD.md §12).
- [ ] Batch/offline verification API (PRD.md §12).
- [ ] Request idempotency-key/replay-caching implementation (DESIGN.md §7) — recommended to at least stub for MVP if time allows, since it touches payment-safety (avoiding double charge on resubmission), but not a hard MVP blocker if the demo script avoids resubmission scenarios.

## 13. Suggested Team Split (Hackathon-Practical)

- **Local pipeline track**: Milestone 1, 2 — validation stages, deterministic repair, escalation decision.
- **Payments/chain track**: Milestone 3, 7 — x402 flow, GoPlausible facilitator integration, Merkle anchoring.
- **Escalation/repair track**: Milestone 4 — semantic-repair API integration, re-validation wiring.
- **Receipts/records/demo track**: Milestone 5, 6, 8, 9 — receipt generation, record store, execution-gating stand-in, demo assembly.

Milestone 0 should be a short, whole-team session before tracks split, since its decisions gate every track.
