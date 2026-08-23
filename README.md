# Verified

**A verifiable trust layer for AI-agent structured output.**

Verified sits between an autonomous AI agent and whatever system executes what it produced. It validates structured output locally, repairs what can be repaired deterministically, escalates to paid, on-chain-settled semantic repair only when required, and issues a cryptographically signed, blockchain-anchored receipt for every outcome — pass, repair, or reject. No output is ever trusted by default, including its own repairs.

---

## The Problem

Autonomous AI agents increasingly write to production databases, call payment APIs, generate SQL, and issue function-call arguments consumed directly by downstream systems — without a human in the loop and without any independent record of what was actually produced or why it was trusted.

Consider two agents in a pipeline: Agent A generates structured data; Agent B consumes it and writes it to a production system. Agent B has no mechanism to know whether Agent A's output was ever validated. A single malformed or hallucinated field propagates silently, and by the time it causes a downstream failure, there is no evidence of which agent produced what, when, or under what conditions it was accepted.

Verified closes that gap by acting as a mandatory, independently verifiable checkpoint between generation and execution.

---

## Design Principles

| Principle | Guarantee |
|---|---|
| **Local-first** | Schema, type, syntax, SQL-safety, and privacy checks run entirely on-device before any data leaves the machine. |
| **Fail-closed** | Any uncertainty, timeout, or unresolved finding resolves to `rejected`. There is no code path that defaults to `verified`. |
| **Payment-gated escalation** | Semantic repair is never invoked without a settled x402 payment. An LLM call cannot execute without prior on-chain settlement. |
| **Verify after repair** | A repaired candidate — deterministic or semantic — is never accepted until it passes the same validation pipeline it originally failed. |
| **Cryptographic receipts** | Every request produces exactly one Ed25519-signed, SHA-256 hash-bound receipt, regardless of outcome. |
| **Tamper-evident anchoring** | Only Merkle roots over batches of receipt hashes are committed on-chain — never raw payloads. |
| **Independent verifiability** | Any receipt can be verified with a public key and a Merkle proof alone. No access to Verified's backend or database is required. |

---

## How It Works

```
Agent Output
    │
    ▼
Local Validation            schema · type · syntax · SQL-safety · privacy
    │
    ├─ deterministic fix available ──► Deterministic Repair ──► Re-validate
    │
    └─ requires reasoning, eligible for escalation
              │
              ▼
        HTTP 402 Payment Required          (x402 protocol)
              │
              ▼
        GoPlausible Facilitator  ──►  Algorand TestNet   (USDC settlement)
              │
              ▼
        Semantic Repair                    Groq · openai/gpt-oss-20b
              │
              ▼
        Re-validation                      same engine — LLM output is never trusted directly
              │
              ▼
        Verification Receipt               Ed25519 signature · SHA-256 hash binding
              │
              ▼
        Local Persistence  ──batch──►  Merkle Tree  ──root──►  Algorand Anchor
              │
              ▼
        Independent Verification           public key + Merkle proof only, no backend required
```

A full architecture diagram is available at [`architecture.png`](./architecture.png).

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, react-router-dom |
| Backend | FastAPI (Python), Pydantic |
| Verification engine | Deterministic multi-stage validation pipeline, rule-based repair |
| Semantic repair | Groq (`openai/gpt-oss-20b`) |
| Payments | x402 protocol v2, GoPlausible AVM Facilitator, Algorand TestNet, USDC |
| Wallet integration | Pera Wallet via `@txnlab/use-wallet-react` |
| Cryptography | Ed25519 receipt signing (PyNaCl), SHA-256 hashing |
| Integrity / anchoring | Binary Merkle tree, Algorand TestNet on-chain anchoring, Merkle inclusion proofs |
| Persistence | SQLite (local), optional Postgres via `DATABASE_URL` |

---

## API Reference

All endpoints are served under `settings.API_V1_STR` (default `/api/v1`).

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/verify` | Run local validation and deterministic repair on a structured output. |
| `POST` | `/semantic-repair` | Escalate to paid semantic repair, gated by an x402 payment. |
| `POST` | `/receipt/verify` | Independently verify a receipt's signature and hash binding. |
| `GET` | `/receipt/public-key` | Retrieve the Ed25519 public key used for receipt verification. |
| `POST` | `/anchor` | Batch a set of receipts, compute a Merkle root, and anchor it on Algorand. |
| `GET` | `/anchor/proof/{record_id}` | Retrieve a Merkle inclusion proof for a specific anchored record. |
| `GET` | `/records` | List verification records. |
| `GET` | `/records/unanchored` | List records eligible for anchoring. |
| `GET` | `/records/{record_id}` | Retrieve a single verification record. |
| `GET` | `/health` | Service health check. |

Full request/response schemas are documented in [`docs/API.md`](./docs/API.md).

---

## Project Structure

```
verified-x402/
├── backend/            FastAPI application, verification engine, x402 integration
│   ├── app/
│   │   ├── api/            HTTP route handlers
│   │   ├── validation/     Schema, type, SQL-safety, privacy checks
│   │   ├── repair/         Deterministic and semantic repair
│   │   ├── payments/       x402 protocol integration
│   │   ├── algorand/       Algorand transaction handling
│   │   ├── anchoring/      Merkle tree construction and on-chain anchoring
│   │   ├── crypto/         Ed25519 signing and verification
│   │   ├── receipts/       Receipt construction
│   │   └── storage/        Local persistence layer
│   ├── tests/          23 test modules covering validation, repair, payments, and anchoring
│   └── scripts/        End-to-end demo, key generation, wallet utilities
├── frontend/           React dashboard — verification console, history, anchoring, receipt lookup
├── docs/               Architecture, API, data model, threat model, and process documentation
├── architecture.png    Full system architecture diagram
└── render.yaml         Backend deployment configuration (Render)
```

---

## Local Development

### Backend

```
cd backend
pip install -r requirements.txt
cp .env.example .env        # populate AVM_ADDRESS and GROQ_API_KEY
python scripts/generate_receipt_signing_key.py   # populate RECEIPT_SIGNING_PRIVATE_KEY / _PUBLIC_KEY
uvicorn app.main:app --reload
```

The API is served at `http://localhost:8000`, with interactive documentation at `/docs`.

### Frontend

```
cd frontend
npm install
cp .env.example .env        # set VITE_API_BASE_URL to the backend origin
npm run dev
```

### Tests

```
cd backend
pytest
```

---

## Deployment

The backend deploys to Render as a Python web service (`render.yaml`), with health checks against `/health`. The frontend is a static Cloudflare Pages deployment, proxying `/api/*` and `/health` to the backend through Cloudflare Functions to avoid CORS and client-side ad-blocker interference.

---

## Security Model

Verified's threat model, key management approach, and failure-mode analysis are documented in [`docs/THREAT_MODEL.md`](./docs/THREAT_MODEL.md). At a high level:

- Private keys used for receipt signing and Algorand transactions never leave the backend environment.
- Payment authorization is signed client-side by the user's own wallet; no private key is ever transmitted to or handled by Verified.
- Anchored data is limited to Merkle roots — raw payloads are never committed on-chain.
- Every verification outcome, including rejections, is receipted and auditable.

---

## Use Cases

- **AI financial agents** — validating payment instructions before execution, with a signed audit trail.
- **Procurement agents** — enforcing structural and semantic correctness on purchase orders before they reach downstream systems.
- **Multi-agent pipelines** — establishing a trust boundary at the handoff between agents.
- **AI-driven API execution** — validating generated request payloads against a schema before dispatch.
- **Auditable AI decisions** — producing a cryptographically verifiable, timestamped record of AI-driven decisions for later independent review.

---

## Beyond This Submission

The architecture generalizes past this specific pipeline:

- **Payment-gated inference** — the x402-gated escalation pattern applies to any pay-per-verification or pay-per-inference API, not only semantic repair.
- **Chain-agnostic anchoring** — the Merkle-batch anchoring model is not tied to Algorand and ports to any settlement layer with low-cost, fast finality.
- **Enterprise trust layer** — a drop-in verification boundary for organizations deploying autonomous agents against production systems, where auditability is a compliance requirement rather than an optional feature.
