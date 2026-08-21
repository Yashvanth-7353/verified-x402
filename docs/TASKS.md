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

## 8. Milestone 6 — Local Verification Record Store (MVP-critical) ✅ Phase 9 complete

Depends on: Milestone 5.

- [x] Implement persistence of `LocalVerificationRecord` (result + receipt + anchoring status) via SQLite.
- [x] Implement retrieval by `request_id`/`receipt_id` for later audit/demo purposes.
- [x] Confirm raw payload content is retained only locally and never included in any outward-facing artifact beyond what Milestone 4 already sends to the semantic-repair API.
- [x] SQLite backend with WAL mode, auto-initialization, configurable path.
- [x] Idempotent saves (same request_id + receipt_id is a no-op).
- [x] Integrity conflict detection (same request_id, different receipt_id → IntegrityError).
- [x] `list_unanchored_records()` with deterministic ordering for future Merkle batching.
- [x] `mark_anchored()` for Phase 10 consumption.
- [x] Privacy: no raw payloads, private keys, X-PAYMENT, or recovery phrases stored.
- [x] Records survive process/database restart.
- [x] 30 Phase 9 tests covering persistence, idempotency, anchoring, privacy, and restart.

## 9. Milestone 7 — Merkle Anchoring on Algorand (MVP-critical) ✅ Phase 10 complete

Depends on: Milestone 6.

- [x] Anchoring trigger: explicit manual invocation via `POST /api/v1/anchor` (MVP choice).
- [x] Deterministic binary Merkle tree over `receipt_hash` values (SHA-256, odd-node doubling).
- [x] Algorand TestNet anchoring via payment transaction with Merkle root in note field.
- [x] `mark_anchored()` updates `anchoring_status`, `merkle_root`, `anchor_tx_ref` on all batch records.
- [x] Retry handling: failed batches remain unanchored, can be retried safely.
- [x] Process-local lock prevents duplicate anchoring of same batch.
- [x] Merkle inclusion proof generation and verification implemented.
- [x] Configurable batch size via `MERKLE_BATCH_SIZE`.
- [x] Anchoring wallet key via `ANCHOR_PRIVATE_KEY` env var (never hardcoded).
- [x] 39 Phase 10 tests (18 Merkle + 21 service) covering tree, proofs, batching, failure, security.

## 10. Milestone 8 — Execution-Gating Demo Consumer (MVP-critical for demo credibility) ✅ Phase 11 complete

Depends on: Milestone 5.

- [x] Receipt verification built into demo script (independently recomputes receipt_hash).
- [x] Demo demonstrates consumer refusing on tampered receipt hash.
- [x] Failure path tests confirm rejected receipts are properly handled.

## 11. Milestone 9 — Demo Assembly & Rehearsal (MVP-critical) ✅ Phase 11 complete

Depends on: Milestones 1–8.

- [x] Full demo script (`scripts/demo_e2e.py`) covering complete lifecycle.
- [x] Offline demo mode (mocked payment, no network required).
- [x] Real TestNet demo mode (live Algorand payment + anchoring).
- [x] Human-readable output with timing measurements.
- [x] Environment check (validates config without exposing secrets).
- [x] Merkle inclusion proof generation and verification in demo.
- [x] Tamper detection demonstration.
- [x] Failure path tests (payment failure, repair failure, anchoring failure).
- [x] `docs/DEMO.md` setup and usage guide.

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
