# BACKEND_COMPLETE.md — Verified Backend Documentation

**Version:** 0.1.0  
**Status:** Backend complete through Phase 14  
**Last updated:** August 21, 2026  

---

## Table of Contents

1. [Document Purpose](#1-document-purpose)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Complete Phase History](#4-complete-phase-history)
5. [Phases 1–6 — Foundational Development](#5-phases-1-6-foundational-development)
6. [Phase 7 — x402 Payment Integration](#6-phase-7-x402-payment-integration)
7. [Phase 8 — Receipts, Integrity, Payment Metadata](#7-phase-8-receipts-integrity-payment-metadata)
8. [Phase 9 — SQLite Persistence](#8-phase-9-sqlite-persistence)
9. [Phase 10 — Merkle Anchoring](#9-phase-10-merkle-anchoring)
10. [Phase 11 — Real E2E Demo](#10-phase-11-real-e2e-demo)
11. [Phase 12 — Ed25519 Receipt Signing](#11-phase-12-ed25519-receipt-signing)
12. [Phase 13 — Independent Verification](#12-phase-13-independent-verification)
13. [Phase 14 — Backend Hardening](#13-phase-14-backend-hardening)
14. [Complete API Reference](#14-complete-api-reference)
15. [Complete Data Model](#15-complete-data-model)
16. [Payment Configuration](#16-payment-configuration)
17. [Environment Configuration](#17-environment-configuration)
18. [Setup From Zero](#18-setup-from-zero)
19. [Wallet / Algorand Setup](#19-wallet-algorand-setup)
20. [How to Run the Backend](#20-how-to-run-the-backend)
21. [How to Run the Test Suite](#21-how-to-run-the-test-suite)
22. [How to Run the Offline Demo](#22-how-to-run-the-offline-demo)
23. [How to Run the Real Demo](#23-how-to-run-the-real-demo)
24. [Complete Feature Demonstration Checklist](#24-complete-feature-demonstration-checklist)
25. [Complete Real E2E Walkthrough](#25-complete-real-e2e-walkthrough)
26. [Troubleshooting History](#26-troubleshooting-history)
27. [Security Model](#27-security-model)
28. [What is Real vs. Mocked](#28-what-is-real-vs-mocked)
29. [Testing Matrix](#29-testing-matrix)
30. [Real TestNet Evidence](#30-real-testnet-evidence)
31. [Frontend Handoff](#31-frontend-handoff)
32. [Current Backend Status](#32-current-backend-status)

---

## 1. Document Purpose

### What Verified Is

Verified is a **local-first verification layer for AI agent structured output**. It validates, repairs, and cryptographically attests to the correctness of JSON, SQL, and function-call outputs before allowing downstream execution.

The core invariant is: **No valid proof, no execution.**

### What Problem It Solves

AI agents produce structured outputs that downstream systems must trust. Verified provides:

1. **Local validation** — deterministic checks against declared schemas
2. **Repair** — fixing outputs that can be corrected automatically
3. **Cryptographic receipts** — tamper-evident proof of what was verified
4. **Payment gating** — semantic repair requires payment, preventing abuse
5. **On-chain anchoring** — Merkle roots committed to Algorand for external auditability
6. **Independent verification** — any third party can verify a receipt without trusting the backend

### What the Backend Does

The backend processes verification requests through a multi-stage pipeline:

- **Free path**: Local validation + deterministic repair → receipt
- **Paid path**: x402 payment → semantic repair → re-validation → receipt
- **Audit path**: Receipt → SQLite → Merkle tree → Algorand anchor → proof

### The Complete Lifecycle

```
AI Agent Output
    ↓
Verification Request
    ↓
Local Validation (schema, type, syntax, SQL safety, privacy)
    ↓
Findings
    ↓
Escalation Decision
    ↓
├── [Free path] No repair needed → Receipt → Done
│
├── [Deterministic repair] Rule-based fix → Re-validation → Receipt → Done
│
└── [Semantic repair required]
        ↓
    HTTP 402 Payment Required
        ↓
    x402 Payment (USDC on Algorand)
        ↓
    GoPlausible Facilitator → Algorand Settlement
        ↓
    Semantic Repair Provider
        ↓
    Re-validation (same pipeline)
        ↓
    Verification Receipt (signed, hashed)
        ↓
    SQLite Persistence
        ↓
    Merkle Tree → Algorand Anchor
        ↓
    Independent Verification / Tamper Detection
```

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENT                                  │
│                    (Agent / Frontend)                             │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/JSON
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI                                   │
│                                                                 │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────────────────┐   │
│  │  /verify     │ │ /semantic-   │ │ /anchor                │   │
│  │  (free)      │ │  repair      │ │ (Merkle anchoring)     │   │
│  │              │ │  (x402 paid) │ │                        │   │
│  └──────┬───────┘ └──────┬───────┘ └──────────┬─────────────┘   │
│         │                │                     │                 │
│  ┌──────┴───────┐ ┌──────┴───────┐ ┌──────────┴─────────────┐   │
│  │ /receipt/    │ │ /receipt/    │ │ /health                │   │
│  │  verify      │ │  public-key  │ │                        │   │
│  └──────────────┘ └──────────────┘ └────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 x402 Payment Middleware                    │   │
│  │    verify payment → settle → store on request.state       │   │
│  └──────────────────┬──────────────────┬────────────────────┘   │
│                     │                  │                         │
└─────────────────────┼──────────────────┼─────────────────────────┘
                      │                  │
          ┌───────────▼──┐    ┌──────────▼──────────┐
          │ GoPlausible  │    │  Algorand TestNet    │
          │ Facilitator  │───▶│  (USDC settlement)   │
          └──────────────┘    └─────────────────────┘
                      │                  │
                      ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  VERIFICATION PIPELINE                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ Schema Stage │  │ Repair Engine │  │ Receipt Service  │      │
│  │ Type Stage   │  │ (deterministic│  │ (hash + sign)    │      │
│  │ SQL Safety   │  │  + semantic)  │  │                  │      │
│  │ Privacy      │  └──────────────┘  └────────┬─────────┘      │
│  └──────────────┘                             │                  │
│                                               ▼                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              SQLite Local Record Store                     │   │
│  │   (request_id, receipt_hash, outcome, anchoring_status)   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │              Merkle Anchoring Service                      │   │
│  │   Merkle tree → Algorand anchor → mark anchored            │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  INDEPENDENT VERIFICATION                        │
│                                                                 │
│  ReceiptVerifier(receipt, public_key)                           │
│      → VALID / INVALID                                          │
│                                                                 │
│  CLI: verify_receipt.py                                         │
│  API: POST /api/v1/receipt/verify                               │
└─────────────────────────────────────────────────────────────────┘
```

### Component Explanations

| Component | File(s) | Purpose |
|-----------|---------|---------|
| **x402 Middleware** | `main.py` | Intercepts requests to `/semantic-repair`, verifies USDC payment via GoPlausible, settles on Algorand, stores settlement info on `request.state` BEFORE calling the handler |
| **Verification Engine** | `validation/engine.py` | Runs schema, type, syntax, SQL safety, and privacy validation stages in sequence |
| **Deterministic Repair** | `repair/deterministic.py` | Applies rule-based fixes (e.g., filling defaults) |
| **Semantic Repair** | `repair/semantic.py` | Sends privacy-filtered payload to `GroqSemanticProvider` (or `MockSemanticProvider` in tests) for AI-based repair |
| **Receipt Service** | `evidence/receipt.py` | Generates signed `VerificationReceipt` with deterministic `receipt_hash` |
| **Ed25519 Signing** | `crypto/signing.py` | Signs receipts using dedicated key pair |
| **Receipt Verifier** | `crypto/verify.py` | Verifies receipts independently (public-key-only) |
| **SQLite Store** | `storage/store.py` | Persists `LocalVerificationRecord` with receipt, result, payment metadata, anchoring status |
| **Merkle Tree** | `anchoring/merkle.py` | Deterministic SHA-256 binary Merkle tree with proof generation |
| **Anchoring Service** | `anchoring/service.py` | Batches unanchored records, builds Merkle tree, submits root to Algorand TestNet |
| **Orchestrator** | `services/orchestrator.py` | Coordinates the free verification path (no payment) |

---

## 3. Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Runtime |
| **FastAPI** | ≥0.110.0 | REST API framework |
| **Pydantic** | ≥2.7.0 | Data validation and models |
| **pydantic-settings** | ≥2.2.1 | Environment-based configuration |
| **SQLite** | 3.x (stdlib) | Local record persistence (WAL mode) |
| **PyNaCl** | (via x402) | Ed25519 signing/verification |
| **py-algorand-sdk** | (via x402) | Algorand TestNet interaction |
| **x402** | (latest) | x402 payment protocol, AVM Exact scheme, GoPlausible facilitator |
| **SHA-256** | (stdlib hashlib) | Receipt hashing, Merkle tree leaves/roots |
| **pytest** | ≥8.1.0 | Test framework |
| **httpx** | ≥0.27.0 | HTTP client for facilitator and TestClient |

### What Each Technology Does

- **FastAPI**: Serves the REST API, handles request validation via Pydantic, provides automatic OpenAPI docs
- **Pydantic**: Defines all data models (VerificationRequest, VerificationReceipt, PaymentMetadata, etc.) with strict validation
- **SQLite**: Zero-dependency local database for persisting verification records; WAL mode for concurrent reads
- **PyNaCl**: Ed25519 digital signatures for receipt signing (128-bit security, fast, Algorand-compatible)
- **x402**: Payment protocol library — constructs x402 challenges, verifies payment payloads, settles via GoPlausible AVM facilitator on Algorand
- **SHA-256**: Used for receipt_hash, output_hash, repair_summary_hash, and Merkle tree construction
- **GoPlausible**: AVM facilitator that verifies and settles x402 payments on Algorand TestNet

---

## 4. Complete Phase History

| Phase | Name | Status | Tests Added |
|-------|------|--------|-------------|
| 7 | x402 Payment Integration | ✅ Complete | — |
| 8 | Receipt Hardening & Payment Metadata | ✅ Complete | 28 new |
| 9 | SQLite Local Record Store | ✅ Complete | 30 new |
| 10 | Merkle Anchoring | ✅ Complete | 39 new |
| 11 | Real E2E Demo | ✅ Complete | 5 new |
| 12 | Ed25519 Receipt Signing | ✅ Complete | 25 new |
| 13 | Independent Verification | ✅ Complete | 38 new |
| 14 | Backend Hardening | ✅ Complete | 0 new (hardening) |

**Total**: 234 tests, 0 failures

---

## 5. Phases 1–6 — Foundational Development

> **Historical-source note:** The original Phase 1–6 execution reports were created outside the current ChatGPT workspace and are not present in the uploaded `BACKEND_COMPLETE.md`. The repository's surviving planning/design artifacts do preserve the foundational implementation contracts, architecture, and milestone definitions.  
>
> Therefore, the six sections below document the **grounded foundational work recoverable from the surviving project artifacts**. They are intentionally not presented as an exact reconstruction of the original Phase 1–6 challenge logs. Exact historical problems/commits/tests from those phases should only be added when the original Phase 1–6 reports are available.

### Phase 1 — Foundational Decisions and Cryptographic Primitives

#### Objective

Establish the core rules that every later backend component depends on:

- deterministic serialization
- cryptographic hashing
- request/result/receipt identity
- fail-closed behavior
- privacy boundaries
- stable validation/repair contracts

#### Implementation established

- SHA-256 was selected for output, repair-summary, and receipt hashing.
- Canonical JSON serialization uses sorted keys and compact separators.
- A custom canonical encoder handles project data types such as UUIDs, datetimes, enums, and Pydantic models.
- The system treats hashes as bindings rather than as encryption.
- Verification is designed to be deterministic for identical inputs and policy/version combinations.
- Repaired outputs are never trusted automatically; they must return through the same validation contract.

The later Phase 8 implementation explicitly records SHA-256 and the compact sorted-key canonicalization as decisions established in the original foundation work.

#### Important architectural decisions

- Validation stages produce findings; centralized decision logic determines whether the request passes, is repaired, escalated, or rejected.
- Deterministic repair must be pure and reproducible.
- Semantic-repair output is untrusted until re-validation.
- Raw payload content must not cross the local trust boundary unnecessarily.
- The downstream execution boundary is responsible for requiring a valid receipt before acting.

---

### Phase 2 — Local Validation Pipeline

#### Objective

Build the local verification engine that can inspect structured AI output without requiring a network call.

#### Pipeline

```text
Verification Request
        ↓
Ingestion / normalization
        ↓
Privacy pre-check
        ↓
Schema validation
        ↓
Type checking
        ↓
Syntax checking
        ↓
SQL safety checking
        ↓
ValidationFinding aggregation
```

#### Implemented responsibilities

The architecture defines the local pipeline as:

1. **Ingestion** — normalize the incoming verification request.
2. **Privacy Filter** — run before escalation decisions so sensitive content is not accidentally forwarded.
3. **Schema Validator** — validate the output against the referenced schema/policy.
4. **Type Checker** — validate field-level types.
5. **Syntax Checker** — validate code-like outputs such as SQL/function-call arguments.
6. **SQL Safety Checker** — identify unsafe statement classes.
7. **Finding aggregation** — collect findings from the independent stages.

Each validation stage has a narrow responsibility and does not itself decide the final outcome.

#### Important behavior

- A valid payload can pass locally without payment.
- Missing/invalid structure creates findings rather than being silently accepted.
- Unsafe SQL is never silently rewritten into a different query.
- Privacy filtering runs before any external escalation.
- The same validation pipeline is reused for re-validation after repair.

---

### Phase 3 — Deterministic Repair and Escalation Decision

#### Objective

Introduce safe local repair while preventing the system from making semantic guesses.

#### Deterministic repair principles

Deterministic repair is limited to changes that are:

- unambiguous
- rule-derived from schema/policy
- reproducible
- local
- free of external model inference

The architecture permits categories such as:

- lossless type coercion when explicitly safe
- structural/format normalization
- filling explicitly declared schema defaults

The architecture explicitly excludes:

- guessing user intent
- ambiguous value selection
- silently rewriting unsafe SQL
- any repair requiring semantic judgment

#### Escalation decision

After validation and deterministic repair, unresolved blocking findings are classified into:

```text
deterministic
semantic
not_repairable
```

The decision logic determines the next stage.

```text
No blocking findings
        ↓
      PASS

Blocking finding
        ↓
Deterministic repair possible?
   ┌───────────────┐
   │ YES           │
   ↓               │
Repair → Revalidate│
                   │
   NO              ↓
        Semantic repair eligible?
             ┌───────────────┐
             │ YES           │ NO
             ↓               ↓
          Escalate        Reject
```

#### Key invariant

A repaired payload is never considered valid merely because a repair function returned it. It must pass the validation pipeline again.

---

### Phase 4 — Semantic-Repair Escalation Pipeline

#### Objective

Add the external semantic-repair path for issues that cannot be resolved safely using deterministic rules.

#### Flow

```text
Local validation
      ↓
Deterministic repair attempt
      ↓
Unresolved semantic finding
      ↓
Privacy-filtered payload
      ↓
Semantic Repair Provider
      ↓
Candidate repaired output
      ↓
FULL LOCAL RE-VALIDATION
      ↓
verified_repaired / rejected
```

#### Important implementation rules

- Only the minimum privacy-filtered payload is eligible to leave the local boundary.
- Semantic repair is not trusted by default.
- A candidate repair must pass the same validation pipeline used for the original output.
- Successful re-validation produces `verified_repaired`.
- Failed re-validation produces `rejected`.
- Provider/network failure is fail-closed.
- Semantic repair does not bypass SQL safety or other local validation rules.

#### MVP provider

The production system uses `GroqSemanticProvider` (Groq API, `openai/gpt-oss-20b`). `MockSemanticProvider` is used for tests and offline demo only.

This is an intentional application-level architecture decision. It is not a mock of:

- x402 payment
- GoPlausible
- Algorand settlement
- Algorand anchoring

Those infrastructure components are real in the real E2E path.

---

### Phase 5 — Verification Receipts, Hashing, and Outcome Model

#### Objective

Create a stable cryptographic artifact representing the result of verification.

#### Outcome model

The backend distinguishes:

| Outcome | Meaning |
|---|---|
| `verified` | Original output passed validation without semantic repair |
| `verified_repaired` | Output was repaired and then passed full re-validation |
| `rejected` | Output remained unsafe/invalid or the flow failed closed |

#### Receipt responsibilities

The receipt binds the verification event to:

- request identity
- verification outcome
- final output hash
- schema reference/version
- validator version
- repair information where applicable
- issuance time
- receipt hash

#### Hashing

The foundation established:

```text
Python object
    ↓
Canonical JSON
    ↓
SHA-256
    ↓
Deterministic hash
```

The later receipt implementation verifies that:

- identical receipt content produces the same hash
- changing a bound field changes the hash
- `output_hash` refers to the FINAL validated output
- `repair_summary_hash` exists when repair occurred

This receipt layer became the dependency for later SQLite persistence and Merkle anchoring.

---

### Phase 6 — Backend Integration Baseline Before Payment Hardening

#### Objective

Bring the foundational validation, repair, receipt, and API layers together into a working backend baseline before the x402-specific hardening work documented in Phase 7.

#### Integrated flow

```text
HTTP Request
    ↓
FastAPI API
    ↓
VerificationRequest / Policy
    ↓
Local validation
    ↓
Deterministic repair if eligible
    ↓
Re-validation
    ↓
Semantic escalation when required
    ↓
VerificationResult
    ↓
VerificationReceipt
```

#### Established backend contracts

The surviving project design defines the following as stable contracts:

- `VerificationRequest`
- `VerificationResult`
- `ValidationFinding`
- `RepairInfo`
- `VerificationReceipt`
- `PaymentMetadata`
- schema/policy references
- receipt/output hashes
- fail-closed rejection behavior

#### Privacy boundary

The backend was designed so that:

- local validation happens before external calls
- privacy filtering happens before escalation
- raw payloads are not placed on-chain
- external infrastructure receives only what its role requires
- receipts use cryptographic bindings rather than exposing unnecessary internal data

#### Execution-gating model

The project establishes:

> **No valid proof, no execution.**

The receipt is the trusted artifact used by the downstream execution boundary. A rejected receipt must never authorize execution, and a receipt for a different output must fail the `output_hash` binding check.

#### Transition into Phase 7

At the end of the foundational implementation, the remaining major integration challenge was the paid semantic-repair path.

Phase 7 therefore introduced the real x402 payment gate, GoPlausible facilitator integration, and Algorand TestNet settlement.

---

### Historical Challenges: What Can and Cannot Be Claimed

The surviving artifacts support the following foundational challenges/design constraints:

- choosing a deterministic hashing/canonicalization scheme
- separating validation-stage findings from centralized escalation decisions
- preventing deterministic repair from becoming semantic guessing
- enforcing re-validation after every repair
- maintaining a privacy boundary before escalation
- keeping unsafe SQL from being silently rewritten
- making receipts the externally trusted artifact
- enforcing fail-closed behavior

However, the **exact Phase 1–6 debugging chronology, individual errors, commit-level file changes, and original per-phase test counts are not recoverable from the current documentation set**. They should not be fabricated in this master document.

---

## 6. Phase 7 — x402 Payment Integration

### Objective
Integrate real x402 payment gating with GoPlausible AVM facilitator on Algorand TestNet.

### Implementation
- Custom x402 middleware that settles payment BEFORE calling the semantic-repair handler
- Real USDC (ASA 10458941) payments via Algorand TestNet
- GoPlausible facilitator integration for payment verification and settlement

### Files Changed
- `backend/app/main.py` — Custom `_verified_payment_middleware`
- `backend/scripts/e2e_client.py` — x402 client with `PrivateKeySigner`
- `backend/scripts/opt_in_usdc.py` — USDC opt-in script
- `backend/scripts/derive_pera_account.py` — Account derivation

### Problems Encountered

**Problem 1: HTTP 500 instead of HTTP 402**
- Root cause: x402 middleware initialization timing — `http_server.initialize()` was called at module load, before the facilitator URL was available
- Solution: Lazy initialization on first protected request, plus `sync_facilitator_on_start=True` flag

**Problem 2: Client expected payment challenge in JSON body**
- Root cause: x402 v2 sends payment requirements in the `Payment-Required` header as base64-encoded JSON, not in the response body
- Solution: Client must decode `base64.b64decode(response.headers["PAYMENT-REQUIRED"])` to get payment requirements

**Problem 3: AssetTransferTxn IndexError with native ALGO**
- Root cause: Initial test used `asset=0` (native ALGO), but the Exact AVM client scheme expected ASA transfer (`AssetTransferTxn`). The algosdk raises an `IndexError` when constructing a native-ALGO payment as an asset transfer
- Solution: Moved to USDC ASA (10458941), which is an actual asset transfer

**Problem 4: Payer not opted into USDC**
- Root cause: Algorand requires accounts to opt-in to ASA assets before holding them
- Solution: Created `opt_in_usdc.py` script; payer account opted into ASA 10458941

**Problem 5: Receiver (payTo) not opted into USDC**
- Root cause: The `payTo` address in the x402 payment requirements (`GAVMWAOT52HYGQOPZAVYXA2NZHZX7DXRJYZQ5YVG4NXPQ3UUWLCHUBWVW4`) was not opted into USDC
- Solution: Identified the receiver address from the facilitator's payment requirements and opted it into ASA 10458941

### Final Payment Configuration
- **Asset**: USDC ASA 10458941 (6 decimal places)
- **Amount**: 1,000,000 atomic units = 1 USDC
- **Network**: Algorand TestNet
- **Facilitator**: `https://facilitator.goplausible.xyz`
- **payTo**: `GAVMWAOT52HYGQOPZAVYXA2NZHZX7DXRJYZQ5YVG4NXPQ3UUWLCHUBWVW4`

---

## 7. Phase 8 — Receipts, Integrity, Payment Metadata

### Objective
Harden VerificationReceipt so every request produces a correct, cryptographically bound receipt, and semantic repair receipts correctly reference the settled x402 payment.

### Implementation
- **ReceiptService**: Generates `VerificationReceipt` with deterministic `receipt_hash`
- **PaymentMetadata**: Created from actual GoPlausible settlement result (not mocked)
- **Invariant enforcement**: `verified_repaired` with semantic repair requires non-null `payment_ref` with `payment_status=settled`
- **Custom middleware**: Settles payment BEFORE calling handler, making settlement info available via `request.state`

### Files Changed
- `backend/app/main.py` — Custom settlement-before-handler middleware
- `backend/app/api/semantic.py` — Creates `PaymentMetadata` from settlement info
- `backend/app/models/api.py` — Added `payment_metadata` to `SemanticRepairResponse`
- `backend/app/evidence/receipt.py` — Invariant enforcement for `verified_repaired`

### Key Invariants
- `receipt_hash` is computed from canonical JSON of all bound fields (excluding `receipt_hash` and `signature`)
- `output_hash` always represents the FINAL validated output (post-repair)
- `repair_summary_hash` is present when any repair occurred
- `verified_repaired` with semantic repair requires `payment_ref != null` and `payment_status = settled`

---

## 8. Phase 9 — SQLite Persistence

### Objective
Persist finalized verification records locally for audit trail and Merkle anchoring.

### SQLite Schema

```sql
CREATE TABLE local_verification_records (
    record_id       TEXT PRIMARY KEY,
    request_id      TEXT NOT NULL UNIQUE,
    receipt_id      TEXT NOT NULL UNIQUE,
    outcome         TEXT NOT NULL,           -- verified | verified_repaired | rejected
    receipt_hash    TEXT NOT NULL,           -- Merkle leaf value
    output_hash     TEXT NOT NULL,
    receipt_json    TEXT NOT NULL,           -- Serialized VerificationReceipt
    result_json     TEXT NOT NULL,           -- Serialized VerificationResult
    payment_metadata_json TEXT,              -- Serialized PaymentMetadata (if any)
    anchoring_status TEXT NOT NULL DEFAULT 'unanchored',
    merkle_inclusion_ref TEXT,
    anchor_tx_ref   TEXT,
    merkle_root     TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX idx_lvr_receipt_id ON local_verification_records(receipt_id);
CREATE INDEX idx_lvr_anchoring_status ON local_verification_records(anchoring_status);
CREATE INDEX idx_lvr_created_at ON local_verification_records(created_at);
```

### Key Behaviors
- **Idempotency**: Saving the same `request_id` + `receipt_id` twice is a no-op
- **Conflict detection**: Saving the same `request_id` with a different `receipt_id` raises `IntegrityError`
- **WAL mode**: Enables concurrent reads during writes
- **Thread safety**: Thread-local SQLite connections with `threading.Lock`

### Privacy — What Is NOT Stored
- Private keys (payer, anchor, receipt signing)
- Mnemonic phrases / recovery seeds
- `X-PAYMENT` / `PAYMENT-SIGNATURE` headers
- Authorization headers
- Raw signed payment payloads
- Raw agent output payloads (only hashes)

### Configuration
- `DATABASE_PATH` env var — defaults to `backend/data/verified.db`
- Auto-creates database and schema on first startup

---

## 9. Phase 10 — Merkle Anchoring

### Merkle Algorithm

- **Hash function**: SHA-256 (32-byte digests)
- **Leaf**: `receipt_hash` (64-char hex) → decoded to 32 raw bytes
- **Parent**: `SHA-256(left_32_bytes || right_32_bytes)` — raw byte concatenation, then SHA-256
- **Root**: 64-char lowercase hex string
- **Odd node**: Last node is duplicated (paired with itself)
- **Ordering**: `ORDER BY created_at ASC, record_id ASC` (deterministic, stable)

### Algorand Anchor Transaction

- **Type**: Payment transaction (0 microAlgos to self)
- **Note field**: `verified-merkle-v1:<merkle_root_hex>` (UTF-8 encoded)
- **Confirmation**: Waits for 4 rounds before marking anchored
- **Failure handling**: Records remain unanchored on failure; can be retried

### What Is On-Chain
- Only the Merkle root (64-char hex) in the transaction note field
- No raw payload, no receipt content, no user data

### What Is NOT On-Chain
- Individual receipt hashes
- Raw verification payloads
- Payment data
- Private keys

### Configuration
- `ANCHOR_PRIVATE_KEY` — Base64-encoded Ed25519 private key for anchoring
- `ANCHOR_ALGOD_ADDRESS` — Algod node URL (default: `https://testnet-api.algonode.cloud`)
- `MERKLE_BATCH_SIZE` — Max records per anchor batch (default: 10)

---

## 10. Phase 11 — Real E2E Demo

### Two Demo Modes

**Offline demo** (`python scripts/demo_e2e.py`):
- Uses FastAPI TestClient (no server needed)
- Mocked x402 payment (no real Algorand)
- Real local validation, receipt generation, Merkle tree, SQLite
- No network required

**Real demo** (`python scripts/demo_e2e.py --real`):
- In-process TestClient with real x402 payment
- Real GoPlausible facilitator verification
- Real Algorand TestNet USDC settlement
- Real semantic repair (GroqSemanticProvider via Groq API)
- Real receipt signing
- Real SQLite persistence
- Real Merkle anchoring to Algorand TestNet
- Real on-chain verification readback

### Semantic Repair Provider (Phase 15)

The production semantic repair provider is `GroqSemanticProvider`, which calls the Groq API (`openai/gpt-oss-20b`) with structured JSON output. The LLM candidate is always re-validated by `VerificationEngine` — never trusted directly.

`MockSemanticProvider` is retained for unit tests and offline demo mode only. Tests use `MockSemanticProvider` enforced via `tests/conftest.py` autouse fixture.

The x402 payment, GoPlausible facilitator, Algorand settlement, and Merkle anchoring are all REAL.

### 13-Step Demo Flow

1. Verification Request — Submit output to verify
2. Local Validation — Free path, no payment
3. Escalation Decision — Blocking findings detected
4. x402 Payment — Real HTTP 402 → real payment construction
5. Settlement — Real GoPlausible facilitator → Algorand USDC transfer
6. Semantic Repair — Provider fixes the output
7. Re-validation — Same pipeline re-validates repaired output
8. Payment Metadata — Shows settled payment with real Algorand tx
9. Receipt — Signed verification receipt generated
10. SQLite Persistence — Record stored in local database
11. Merkle Anchoring — Real Algorand TestNet anchor transaction
12. Inclusion Proof — Merkle proof verifies receipt is in the tree
13. Tamper Detection — Modified receipt hash fails verification

---

## 11. Phase 12 — Ed25519 Receipt Signing

### Why Signing Was Needed
Third parties need to verify that a receipt was actually produced by Verified and hasn't been modified. Ed25519 provides fast, Algorand-compatible digital signatures.

### Configuration
- `RECEIPT_SIGNING_PRIVATE_KEY` — Base64-encoded 32-byte Ed25519 private key
- `RECEIPT_SIGNING_PUBLIC_KEY` — Base64-encoded 32-byte Ed25519 public key
- Key generation: `python scripts/generate_receipt_signing_key.py`

### Key Design Decision
The signing key is **separate** from:
- The payer wallet (`PAYER_PRIVATE_KEY`) — used for x402 payment
- The anchor wallet (`ANCHOR_PRIVATE_KEY`) — used for Merkle anchoring

### Signed Fields (Protected by Signature)
- `receipt_id`
- `request_id_ref`
- `outcome`
- `output_hash`
- `schema_ref_and_version`
- `repair_summary_hash`
- `validator_version`
- `issued_at`

### Excluded from Signature (By Design)
| Field | Why Excluded |
|-------|-------------|
| `receipt_hash` | Computed from content; Merkle-tree layer, not signature layer |
| `signature` | Self-referential (can't sign the signature) |
| `signature_algorithm` | Metadata about the signature, not content |
| `signing_key_id` | Metadata about the key, not content |

### Merkle Compatibility
`receipt_hash` excludes signature fields. The Merkle tree uses `receipt_hash` as the leaf. Therefore, signing does not change the Merkle leaf or root. Existing Phase 10 anchoring remains compatible.

---

## 12. Phase 13 — Independent Verification

### Three Verification Paths

**1. API (server required)**
```bash
POST /api/v1/receipt/verify
{"receipt": {<signed receipt JSON>}}
```

**2. CLI (no server, no backend)**
```bash
python scripts/verify_receipt.py receipt.json --public-key <base64-key>
```

**3. Library (Python import only)**
```python
from app.crypto.verify import ReceiptVerifier
verifier = ReceiptVerifier(public_key_b64="abc123...")
result = verifier.verify(receipt_dict)
```

### What Independent Verification Does NOT Require
- ❌ Private signing key
- ❌ Backend server
- ❌ SQLite database
- ❌ Algorand access
- ❌ GoPlausible facilitator
- ❌ PAYER_PRIVATE_KEY
- ❌ ANCHOR_PRIVATE_KEY

### What It DOES Require
- ✅ Signed receipt (JSON dict)
- ✅ Public Ed25519 verification key (Base64-encoded 32 bytes)

### Verification Process
```
Signed Receipt + Public Key
        ↓
Canonicalize signable fields (exclude receipt_hash, signature, metadata)
        ↓
Decode Ed25519 signature (hex → 64 bytes)
        ↓
Ed25519 verify(public_key, signature, canonical_bytes)
        ↓
VerificationResult { valid, signature_valid, receipt_integrity_valid }
```

### Public Key Distribution
```bash
GET /api/v1/receipt/public-key
# Returns: {"algorithm": "Ed25519", "key_id": "...", "public_key": "..."}
```

---

## 13. Phase 14 — Backend Hardening

### Issues Found and Fixed

| Problem | Risk | Fix | Final Behavior |
|---------|------|-----|----------------|
| No CORS middleware | Frontend can't access API | Added `CORSMiddleware` with configurable origins | `CORS_ORIGINS` env var, defaults to `localhost:3000,localhost:5173` |
| No request size limits | DoS via unbounded payloads | Added `MAX_REQUEST_BYTES` | 1 MB default |
| No batch_size validation | Accept negative/absurd values | Added validation (1-1000) with safety clamp | Rejects invalid, clamps extreme values |
| `payment_failure.log` disk writes | Disk fill, file permissions | Removed file I/O, use `logger.warning()` only | Logging only, no disk writes |
| None values in payment metadata | Messy JSON serialization | Filter None values before serialization | Clean JSON |
| No API documentation | Frontend can't integrate | Created `docs/API.md` | Stable contract documented |

### Configuration Added
- `CORS_ORIGINS` — Comma-separated allowed origins
- `MAX_REQUEST_BYTES` — Maximum request body size (1 MB default)

---

## 14. Complete API Reference

### GET /health

Health check.

**Response 200:**
```json
{"status": "ok", "service": "verified", "version": "0.1.0"}
```

---

### POST /api/v1/verify

Local verification — no payment required.

**Request:**
```json
{
  "request": {
    "request_id": "uuid",
    "submitted_at": "2026-01-01T00:00:00Z",
    "output_type": "json",
    "output_payload": {"key": "value"},
    "schema_ref": "string",
    "agent_identifier": "string"
  },
  "policy": {
    "schema_id": "uuid",
    "version": "1.0",
    "output_type": "json",
    "schema_definition": {"type": "object", "properties": {}, "required": []},
    "privacy_policy_ref": "default"
  }
}
```

**Response 200:** `VerifyPayloadResponse` with `result` and `receipt`

**Errors:** 400, 422, 500

---

### POST /api/v1/semantic-repair

Semantic repair — requires x402 payment. First call returns 402 with payment requirements.

**First call (no payment):** Returns HTTP 402 with `Payment-Required` header containing base64-encoded payment requirements.

**Second call (with payment):**
- Header: `PAYMENT-SIGNATURE: <base64-encoded-x402-payment>`
- Returns 200 with `result`, `receipt`, and `payment_metadata`

**Response 200:** `SemanticRepairResponse` with `result`, `receipt`, and `payment_metadata`

**Errors:** 402, 400, 422, 500

---

### POST /api/v1/anchor

Trigger Merkle anchoring of unanchored records.

**Request (optional):**
```json
{"batch_size": 10}
```

**Response 200:**
```json
{"status": "anchored", "leaf_count": 10, "merkle_root": "...", "transaction_id": "...", "error": null}
```

**Errors:** 503 (not configured), 500

---

### POST /api/v1/receipt/verify

Independently verify a signed receipt.

**Request:**
```json
{"receipt": {<signed receipt JSON>}}
```

**Response 200:**
```json
{"valid": true, "signature_valid": true, "receipt_integrity_valid": true, "algorithm": "Ed25519", "signing_key_id": "...", "details": "..."}
```

**Errors:** 503 (not configured), 500

---

### GET /api/v1/receipt/public-key

Get the public verification key.

**Response 200:**
```json
{"algorithm": "Ed25519", "key_id": "hex-16", "public_key": "base64-encoded-key"}
```

**Errors:** 503 (not configured)

---

## 15. Complete Data Model

### Entity Relationships

```
VerificationRequest ──1:1──▶ VerificationResult ──1:1──▶ VerificationReceipt
       │                          │                           │
       │                          ├──▶ ValidationFinding[]     ├──▶ signature
       │                          │                           ├──▶ receipt_hash
       │                          └──▶ RepairInfo (optional)   └──▶ output_hash
       │                                    │
       │                                    └──▶ PaymentMetadata (if semantic)
       │
SchemaPolicy ◀── validated against

VerificationReceipt ──receipt_hash──▶ Merkle Tree ──root──▶ Algorand Transaction

LocalVerificationRecord (SQLite) = Result + Receipt + AnchoringStatus
```

### Key Identifiers
- `request_id` (UUID) — Unique per verification request
- `receipt_id` (UUID) — Unique per receipt
- `payment_id` (UUID) — Unique per payment
- `record_id` (UUID) — Unique per SQLite record
- `signing_key_id` (hex-16) — Truncated SHA-256 of public key

---

## 16. Payment Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| `FACILITATOR_URL` | `https://facilitator.goplausible.xyz` | GoPlausible AVM Facilitator |
| `ALGORAND_NETWORK` | `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=` | CAIP-2 network identifier |
| `AVM_ADDRESS` | `GAVMWAOT52HYGQOPZAVYXA2NZHZX7DXRJYZQ5YVG4NXPQ3UUWLCHUBWVW4` | Payment receiver |
| `SEMANTIC_REPAIR_PRICE` | `10000` | 0.01 USDC (6 decimal places) |
| ASA ID | `10458941` | USDC on Algorand TestNet |
| Decimals | `6` | 1 USDC = 1,000,000 atomic units |

**Important:** `ALGORAND_NETWORK` is a CAIP-2/x402 network identifier, NOT an Algod URL. The Algod URL is `ANCHOR_ALGOD_ADDRESS`.

---

## 17. Environment Configuration

### Public Configuration

| Variable | Purpose | Default | Secret? |
|----------|---------|---------|---------|
| `ENVIRONMENT` | Environment name | `development` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `API_V1_STR` | API prefix | `/api/v1` | No |
| `FACILITATOR_URL` | GoPlausible URL | `https://facilitator.goplausible.xyz` | No |
| `ALGORAND_NETWORK` | CAIP-2 network identifier | `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=` | No |
| `SEMANTIC_REPAIR_PRICE` | Payment amount (atomic units) | `10000` | No |
| `AVM_ADDRESS` | Payment receiver address | `GAVMWAOT52HYGQOPZAVYXA2NZHZX7DXRJYZQ5YVG4NXPQ3UUWLCHUBWVW4` | No |
| `DATABASE_PATH` | SQLite path | `backend/data/verified.db` | No |
| `ANCHOR_ALGOD_ADDRESS` | Algorand node URL | `https://testnet-api.algonode.cloud` | No |
| `ANCHOR_ALGOD_TOKEN` | Algod API token | `""` (empty) | No |
| `MERKLE_BATCH_SIZE` | Max records per anchor | `10` | No |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://localhost:5173` | No |
| `MAX_REQUEST_BYTES` | Max request body | `1048576` (1 MB) | No |

### Sensitive Configuration

| Variable | Purpose | Secret? |
|----------|---------|---------|
| `PAYER_PRIVATE_KEY` | x402 USDC payment signing | ⚠️ YES — never commit |
| `ANCHOR_PRIVATE_KEY` | Algorand Merkle anchor signing | ⚠️ YES — never commit |
| `RECEIPT_SIGNING_PRIVATE_KEY` | Ed25519 receipt signing | ⚠️ YES — never commit |
| `RECEIPT_SIGNING_PUBLIC_KEY` | Ed25519 public key (safe to share) | No |

---

## 18. Setup From Zero

### Prerequisites
- Python 3.11+
- Git
- Algorand TestNet accounts (payer + anchor)

### Steps

```powershell
# 1. Clone repository
git clone https://github.com/Yashvanth-7353/verified-x402.git
cd verified-x402

# 2. Create virtual environment
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create environment files
# backend/.env (server config)
@"
ENVIRONMENT=development
LOG_LEVEL=INFO
FACILITATOR_URL=https://facilitator.goplausible.xyz
ALGORAND_NETWORK=algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=
SEMANTIC_REPAIR_PRICE=10000
AVM_ADDRESS=GAVMWAOT52HYGQOPZAVYXA2NZHZX7DXRJYZQ5YVG4NXPQ3UUWLCHUBWVW4
ANCHOR_ALGOD_ADDRESS=https://testnet-api.algonode.cloud
ANCHOR_ALGOD_TOKEN=
ANCHOR_PRIVATE_KEY=<your-anchor-private-key-base64>
RECEIPT_SIGNING_PRIVATE_KEY=<your-signing-private-key-base64>
RECEIPT_SIGNING_PUBLIC_KEY=<your-signing-public-key-base64>
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
"@ | Out-File -Encoding utf8 .env

# backend/.env.client (client wallet)
@"
PAYER_PRIVATE_KEY=<your-payer-private-key-base64>
"@ | Out-File -Encoding utf8 .env.client

# 5. Generate receipt signing key (if not already done)
python scripts/generate_receipt_signing_key.py
# Copy the output keys into .env

# 6. Verify configuration
python -c "
from dotenv import load_dotenv
import os
load_dotenv('.env')
load_dotenv('.env.client')
for k in ['PAYER_PRIVATE_KEY','ANCHOR_PRIVATE_KEY','RECEIPT_SIGNING_PRIVATE_KEY','RECEIPT_SIGNING_PUBLIC_KEY']:
    v = os.environ.get(k, '')
    print(f'{k}: {\"configured\" if v else \"NOT SET\"} (len={len(v)})')
"
```

---

## 19. Wallet / Algorand Setup

### Three Separate Identities

| Identity | Purpose | Environment Variable | Used For |
|----------|---------|---------------------|----------|
| **Payer** | x402 USDC payment | `PAYER_PRIVATE_KEY` | Signing USDC transfers to GoPlausible |
| **Anchor** | Merkle root anchoring | `ANCHOR_PRIVATE_KEY` | Submitting anchor transactions to Algorand |
| **Receipt signer** | Ed25519 receipt signing | `RECEIPT_SIGNING_PRIVATE_KEY` | Cryptographically signing verification receipts |

These are intentionally separate. Do not reuse the same key for multiple purposes.

### Safe Commands

```powershell
# Check payer USDC balance (DO NOT print private key)
python -c "
from algosdk.v2client import algod
from dotenv import load_dotenv; load_dotenv('.env.client')
import os, base64
from algosdk import encoding
sk = base64.b64decode(os.environ['PAYER_PRIVATE_KEY'])
addr = encoding.encode_address(sk[32:])
client = algod.AlgodClient('', 'https://testnet-api.algonode.cloud')
info = client.account_info(addr)
print(f'Address: {addr}')
print(f'ALGO: {info[\"amount\"]/1e6}')
for a in info.get('assets', []):
    if a['asset-id'] == 10458941:
        print(f'USDC: {a[\"amount\"]/1e6}')
"

# Check anchor ALGO balance (DO NOT print private key)
python -c "
from algosdk.v2client import algod
from dotenv import load_dotenv; load_dotenv('.env')
import os, base64
from algosdk import encoding
sk = base64.b64decode(os.environ['ANCHOR_PRIVATE_KEY'])
addr = encoding.encode_address(sk[32:])
client = algod.AlgodClient('', 'https://testnet-api.algonode.cloud')
info = client.account_info(addr)
print(f'Anchor: {addr}')
print(f'ALGO: {info[\"amount\"]/1e6}')
"
```

---

## 20. How to Run the Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Start API server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Expected startup:
```
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     CORS allowed origins: ['http://localhost:3000', 'http://localhost:5173']
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","service":"verified","version":"0.1.0"}`

---

## 21. How to Run the Test Suite

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test suite
pytest tests/crypto/ -v      # Receipt signing + verification
pytest tests/anchoring/ -v   # Merkle tree + anchoring
pytest tests/storage/ -v     # SQLite persistence
pytest tests/api/ -v         # API endpoint tests
```

**Current baseline: 234 passed, 0 failures**

### Test Categories

| Directory | Tests | Purpose |
|-----------|-------|---------|
| `tests/validation/` | 9 | Schema, type, engine tests |
| `tests/repair/` | 7 | Deterministic + semantic repair |
| `tests/evidence/` | 8 | Canonical, hasher, receipt |
| `tests/models/` | 9 | Pydantic model validation |
| `tests/crypto/` | 63 | Signing + independent verification |
| `tests/api/` | 52 | API endpoint tests |
| `tests/storage/` | 34 | SQLite persistence |
| `tests/anchoring/` | 39 | Merkle tree + anchoring service |
| `tests/demo/` | 5 | Failure path tests |
| `tests/api/` | 1 | Health check |

---

## 22. How to Run the Offline Demo

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/demo_e2e.py
```

- **No network required**
- All x402 payments are mocked
- Local validation, receipt generation, Merkle tree, and SQLite are real
- Expected output: 13 steps with green [OK] indicators

---

## 23. How to Run the Real Demo

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts/demo_e2e.py --real
```

### Prerequisites
- `PAYER_PRIVATE_KEY` configured with funded TestNet account
- Payer opted into ASA 10458941 (USDC)
- Payer has >0 USDC balance
- `ANCHOR_PRIVATE_KEY` configured with TestNet account
- Anchor has >0 ALGO balance
- `RECEIPT_SIGNING_PRIVATE_KEY` + `RECEIPT_SIGNING_PUBLIC_KEY` configured
- Facilitator reachable at `https://facilitator.goplausible.xyz`
- Algorand TestNet reachable

### Expected Output
13 steps with real Algorand transaction IDs, real Merkle root, real inclusion proof.

---

## 24. Complete Feature Demonstration Checklist

| # | Feature | Trigger | Verification |
|---|---------|---------|-------------|
| 1 | Free verification | `POST /api/v1/verify` | Outcome in response |
| 2 | HTTP 402 challenge | `POST /api/v1/semantic-repair` (no payment) | 402 status + `Payment-Required` header |
| 3 | Payment requirements | Decode base64 `Payment-Required` header | Valid x402 payment terms |
| 4 | Real USDC payment | Construct x402 payment with real key | `x402 version: 2` |
| 5 | GoPlausible settlement | Middleware settles before handler | `payment_status: settled` in response |
| 6 | Semantic repair | Provider fixes output | `outcome: verified_repaired` |
| 7 | Re-validation | Same pipeline re-validates | No blocking findings in re-validation |
| 8 | Payment metadata | Check `payment_metadata` in response | `algorand_tx_ref` present and valid |
| 9 | Receipt generation | Check `receipt` in response | `receipt_hash` present |
| 10 | Receipt integrity | Recompute hash from receipt fields | Computed hash matches `receipt_hash` |
| 11 | Receipt signing | Check `signature` field | `signature_algorithm: Ed25519`, `signing_key_id` present |
| 12 | Public key retrieval | `GET /api/v1/receipt/public-key` | Returns algorithm, key_id, public_key |
| 13 | Independent verification | `POST /api/v1/receipt/verify` | `valid: true` |
| 14 | Tamper detection | Modify receipt field, re-verify | `valid: false` |
| 15 | SQLite persistence | Query database | Record exists with correct outcome |
| 16 | Restart persistence | Restart server, query database | Record still exists |
| 17 | Unanchored records | `list_unanchored_records()` | Records available for anchoring |
| 18 | Merkle root | `POST /api/v1/anchor` | 64-char hex root returned |
| 19 | Real Algorand anchor | Anchor on TestNet | Transaction ID confirmed |
| 20 | Merkle inclusion proof | `generate_proof()` + `verify_proof()` | `True` |
| 21 | Anchor failure/retry | Records remain unanchored on failure | Can retry safely |
| 22 | Invalid payment | Send malformed payment | 402 rejection |
| 23 | Invalid receipt | Modify receipt, verify | `valid: false` |

---

## 25. Complete Real E2E Walkthrough

### Step 1: Start Backend
```powershell
cd backend
uvicorn app.main:app --port 8000
```

### Step 2: Free Verification
```powershell
curl -X POST http://localhost:8000/api/v1/verify -H "Content-Type: application/json" -d '{...}'
```
→ 200 with `outcome: verified` or `outcome: verified_repaired`

### Step 3: Paid Path — Get 402
```powershell
curl -X POST http://localhost:8000/api/v1/semantic-repair -H "Content-Type: application/json" -d '{...}'
```
→ 402 with `Payment-Required` header

### Step 4: Decode Payment Requirements
```python
import base64, json
pr = json.loads(base64.b64decode(response.headers["PAYMENT-REQUIRED"]))
```

### Step 5: Construct x402 Payment
```python
from x402.client import x402Client
from x402.mechanisms.avm.exact import ExactAvmClientScheme
client = x402Client()
client.register(network, ExactAvmClientScheme(signer=signer))
payment = await client.create_payment_payload(PaymentRequired(**pr))
```

### Step 6: Submit Payment
```python
encoded = base64.b64encode(payment.model_dump_json(...).encode()).decode()
resp = await client.post("/api/v1/semantic-repair", json=payload, headers={"PAYMENT-SIGNATURE": encoded})
```
→ 200 with receipt + payment_metadata

### Step 7: Verify Receipt Signature
```python
from app.crypto.verify import ReceiptVerifier
result = ReceiptVerifier(public_key_b64).verify(receipt_dict)
# result.valid == True
```

### Step 8: Check SQLite
```python
from app.storage.store import LocalVerificationRecordStore
store = LocalVerificationRecordStore()
record = store.get_by_request_id(request_id)
# record.outcome == "verified_repaired"
# record.receipt_hash == receipt.receipt_hash
```

### Step 9: Anchor Records
```python
POST /api/v1/anchor {"batch_size": 10}
# → {"status": "anchored", "merkle_root": "...", "transaction_id": "..."}
```

### Step 10: Verify On-Chain
```python
from algosdk.v2client import algod
client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
tx_info = client.pending_transaction_info(tx_id)
# tx_info["confirmed-round"] → confirmed
# note field → "verified-merkle-v1:<root>"
```

### Step 11: Generate & Verify Merkle Proof
```python
from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof
tree = build_merkle_tree(leaves)
proof = generate_proof(tree, leaf_index)
valid = verify_proof(leaves[leaf_index], proof, tree.root, leaf_index)
# valid == True
```

### Step 12: Tamper Detection
```python
tampered = dict(receipt)
tampered["outcome"] = "rejected"
result = ReceiptVerifier(pub).verify(tampered)
# result.valid == False, result.signature_valid == False
```

---

## 26. Troubleshooting History

### Problem: HTTP 500 instead of HTTP 402
- **Root cause**: x402 middleware initialization at module load time
- **Solution**: Lazy initialization on first protected request

### Problem: Client expected payment challenge in JSON body
- **Root cause**: x402 v2 uses `Payment-Required` header with base64-encoded JSON
- **Solution**: `base64.b64decode(response.headers["PAYMENT-REQUIRED"])`

### Problem: AssetTransferTxn IndexError
- **Root cause**: `asset=0` (native ALGO) but Exact AVM expects ASA transfer
- **Solution**: Move to USDC ASA 10458941

### Problem: Payer not opted into USDC
- **Root cause**: Algorand requires opt-in before holding ASA assets
- **Solution**: `opt_in_usdc.py` script

### Problem: Receiver not opted into USDC
- **Root cause**: `payTo` address not opted into ASA 10458941
- **Solution**: Identify receiver from facilitator response, opt in

### Problem: PAYER_PRIVATE_KEY not loaded
- **Root cause**: PowerShell environment loading; `.env.client` path issues
- **Solution**: Use `python-dotenv` to load `.env.client` explicitly

### Problem: ALGORAND_NETWORK confusion
- **Root cause**: `ALGORAND_NETWORK` is a CAIP-2 identifier, not an Algod URL
- **Solution**: `ANCHOR_ALGOD_ADDRESS` is the Algod URL

### Problem: Phase 9 request_id conflicts
- **Root cause**: Free path and paid path using same request_id
- **Solution**: Use separate request_ids for each path in demo

### Problem: Real demo not anchoring
- **Root cause**: `run_real_demo()` built Merkle tree locally but never called `MerkleAnchoringService`
- **Solution**: Rewrote to call real `MerkleAnchoringService` with `TestNetAlgorandClient`

### Problem: Phase 14 missing CORS
- **Root cause**: No CORS middleware configured
- **Solution**: Added `CORSMiddleware` with configurable `CORS_ORIGINS`

### Problem: Flaky `test_same_records_same_root`
- **Root cause**: Random UUID4 for `record_id` caused non-deterministic ordering
- **Solution**: Use deterministic `uuid5` for test record IDs

---

## 27. Security Model

### Secret Separation

| Secret | Purpose | Never In |
|--------|---------|----------|
| `PAYER_PRIVATE_KEY` | x402 USDC payment | Receipts, logs, SQLite, frontend, source code |
| `ANCHOR_PRIVATE_KEY` | Algorand anchoring | Receipts, logs, SQLite, frontend, source code |
| `RECEIPT_SIGNING_PRIVATE_KEY` | Receipt signing | Receipts, logs, SQLite, frontend, source code |

### Public Information (Safe to Share)
- `RECEIPT_SIGNING_PUBLIC_KEY` — for independent verification
- Wallet addresses (payer, anchor) — visible on blockchain
- Algorand transaction IDs — public on TestNet
- Merkle roots — public on Algorand
- Receipt content (with signature) — designed for sharing

### Privacy Guarantees
- Raw agent payloads never stored in SQLite (only hashes)
- Raw payloads never sent to Algorand
- Raw payloads never included in receipts
- Payment credentials never logged
- Private keys never in API responses

### "Never Do This" Rules
- ❌ Never commit `.env` or `.env.client` files
- ❌ Never log `X-PAYMENT` or `PAYMENT-SIGNATURE` contents
- ❌ Never store private keys in SQLite
- ❌ Never put private keys in frontend code
- ❌ Never put payer private key in frontend
- ❌ Never put anchor private key in frontend
- ❌ Never put receipt signing private key in frontend
- ❌ Never print private keys in logs or error messages

---

## 28. What is Real vs. Mocked

| Component | Real in Demo | Mocked In | Why Mocked |
|-----------|-------------|-----------|------------|
| **x402 payment construction** | ✅ Real | Offline demo only | No network in offline mode |
| **GoPlausible facilitator** | ✅ Real | Unit tests only | External dependency |
| **Algorand USDC settlement** | ✅ Real | Unit tests only | External dependency |
| **Merkle tree** | ✅ Real | Never mocked | Pure local computation |
| **Algorand anchoring** | ✅ Real | Unit tests only | External dependency |
| **Receipt signing (Ed25519)** | ✅ Real | Never mocked | Pure local cryptography |
| **Receipt verification** | ✅ Real | Never mocked | Pure local cryptography |
| **SQLite persistence** | ✅ Real | Test DBs in tests | Local database |
| **Semantic repair** | ✅ Real (GroqSemanticProvider) | MockSemanticProvider in tests/offline | Groq API with re-validation |
| **Local validation** | ✅ Real | Never mocked | Core local pipeline |

**Important**: Production uses `GroqSemanticProvider` (Groq API). `MockSemanticProvider` is used only in unit tests (enforced by conftest.py) and offline demo. The x402 payment, GoPlausible facilitator, Algorand settlement, and Merkle anchoring are all real.

---

## 29. Testing Matrix

### Phase-Specific Test Counts

| Phase | New Tests | Focus |
|-------|-----------|-------|
| 8 | 28 | Payment metadata, receipt integrity, tamper detection |
| 9 | 30 | SQLite persistence, idempotency, anchoring status |
| 10 | 39 | Merkle tree, anchoring service, proof generation |
| 11 | 5 | Failure path tests |
| 12 | 25 | Ed25519 signing, receipt integrity |
| 13 | 38 | Independent verification, no-private-key, no-SQLite |
| 14 | 0 | Hardening phase (no new features) |

### Current Baseline

```
234 passed, 0 failed, 1 warning (Starlette deprecation)
```

---

## 30. Real TestNet Evidence

### Run: August 21, 2026 (Phase 14 final validation)

| Transaction | ID | Round |
|------------|-----|-------|
| **x402 USDC payment** | `WME53DKSCMU3YVIWIXOPPBS4YU2OUG5FRCKSG7FIG5AWFNLJI7UA` | GoPlausible settlement |
| **Algorand anchor** | `IWLST7OPC3HFOGCENDD74PRIWMQJYI32VWFRPK37PVB4NJ6VAV4Q` | 66525032 |
| **Merkle root** | `9fe8d959073c9e8a...` | On-chain note verified |

### Run: August 21, 2026 (Phase 13 validation)

| Transaction | ID | Round |
|------------|-----|-------|
| **x402 USDC payment** | `WPHOJSLVOFHCAQQKGHBNONMG37MI5JTLLBCXBYNDB2CA5QKIVLQA` | GoPlausible settlement |
| **Algorand anchor** | `2F53RYDOF4TBC66FYB3TWD6JK3EVJNDVAWMRPBUYRB35FRJJQ7ZA` | 66524572 |
| **Merkle root** | `5bed8958785b1a07...` | On-chain note verified |

---

## 31. Frontend Handoff

### The backend is complete through Phase 14.

The frontend should consume the stable API contract documented in `docs/API.md`.

### Frontend Should NOT:
- Implement payment signing using backend secrets
- Access `PAYER_PRIVATE_KEY`
- Access `ANCHOR_PRIVATE_KEY`
- Access `RECEIPT_SIGNING_PRIVATE_KEY`
- Directly modify SQLite
- Directly modify backend data
- Reproduce backend verification logic unnecessarily

### Frontend SHOULD Display:
- Verification request submission
- Validation findings
- Verification status (verified / verified_repaired / rejected)
- Escalation decision
- Payment status and settlement details
- Repair status and before/after output
- Receipt details (receipt_id, outcome, hashes)
- Signature status and public key
- Merkle root and anchor transaction
- Inclusion proof verification
- Tamper verification

### Backend-Only Operations
These remain server-controlled:
- x402 payment verification (middleware)
- GoPlausible facilitator interaction
- Algorand settlement
- Receipt generation and signing
- SQLite persistence
- Merkle tree construction
- Algorand anchoring

---

## 32. Current Backend Status

```
Backend:              COMPLETE THROUGH PHASE 14
Tests:                234 passed, 0 failures
Real E2E:             WORKING
Real x402:            WORKING
Real Algorand settlement: WORKING
Real Algorand anchoring:  WORKING
Receipt signing:      WORKING
Independent verification: WORKING
Merkle proof:         WORKING
Tamper detection:     WORKING
CORS:                 CONFIGURED
API documentation:    COMPLETE (docs/API.md)

Frontend:             NOT STARTED
Next phase:           PHASE 15 — FRONTEND
```
