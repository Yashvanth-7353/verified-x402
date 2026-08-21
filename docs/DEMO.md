# DEMO.md — Verified End-to-End Demonstration

## 1. Project Overview

Verified is a local-first verification layer for AI agent structured output. It validates, repairs, and cryptographically attests to the correctness of JSON/SQL/function-call outputs before allowing downstream execution.

**Core invariant:** No valid proof, no execution.

## 2. Architecture

```
AI Agent Output
    ↓
Local Validation (schema, type, syntax, SQL safety)
    ↓
Deterministic Repair (if applicable)
    ↓
Escalation Decision
    ↓
x402 Payment (if semantic repair needed)
    ↓
GoPlausible AVM Facilitator → Algorand TestNet
    ↓
Semantic Repair (external AI)
    ↓
Full Re-validation
    ↓
VerificationReceipt (cryptographically bound)
    ↓
SQLite Local Record Store
    ↓
Merkle Tree → Algorand Anchor
    ↓
Inclusion Proof
```

## 3. Prerequisites

- **Python 3.11+**
- **Node.js** (for x402 dependency, if installing from scratch)
- **Algorand TestNet account** (for real demo only)
- **USDC opt-in** on TestNet (ASA 10458941)

## 4. Quick Start (Offline Demo)

No network, no keys, no money required:

```bash
cd backend
python -m pytest tests/ -q    # Run all 171 tests
python scripts/demo_e2e.py    # Run offline demo (mocked, no network)
python scripts/demo_e2e.py --real  # Run real TestNet demo (in-process)
```

## 5. Environment Variables

### Required for all modes:
```bash
# Server configuration (backend/.env)
FACILITATOR_URL=https://facilitator.goplausible.xyz
ALGORAND_NETWORK=algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=
SEMANTIC_REPAIR_PRICE=1000000
```

### Required for real TestNet demo:
```bash
# Client wallet (backend/.env.client)
PAYER_PRIVATE_KEY=<base64-encoded-algorand-private-key>

# Anchoring wallet (backend/.env)
ANCHOR_PRIVATE_KEY=<base64-encoded-algorand-private-key>
ANCHOR_ALGOD_ADDRESS=https://testnet-api.algonode.cloud
```

**⚠️ NEVER commit private keys to source control.**

## 6. Wallet Requirements

The demo uses TWO separate wallets:

| Wallet | Purpose | Environment Variable |
|--------|---------|---------------------|
| Payer wallet | x402 payment for semantic repair | `PAYER_PRIVATE_KEY` |
| Anchoring wallet | Merkle root anchoring on Algorand | `ANCHOR_PRIVATE_KEY` |

Do not reuse the same wallet unless you explicitly intend to.

## 7. TestNet Funding

1. Go to https://bank.testnet.algorand.network/
2. Enter your payer wallet address
3. Request testnet ALGO (for transaction fees)
4. Ensure you have USDC (ASA 10458941) opted in

## 8. USDC Opt-in

```bash
cd backend
PAYER_PRIVATE_KEY=<your-key> python scripts/opt_in_usdc.py
```

## 9. Running the Server

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 10. Running the Demo

### Offline (mocked — no network):
```bash
python scripts/demo_e2e.py
```

### Real TestNet (in-process — no server needed):
```bash
# Set environment variables
export PAYER_PRIVATE_KEY=<base64-key>
export ANCHOR_PRIVATE_KEY=<base64-key>

# Run the real demo (in-process TestClient + real Algorand)
python scripts/demo_e2e.py --real
```

The real demo runs entirely in-process using FastAPI's TestClient.
All external calls are real:
- x402 payment verification via GoPlausible facilitator
- Algorand TestNet settlement
- Merkle anchoring to Algorand TestNet
- On-chain transaction readback verification

## 11. API Endpoints

| Endpoint | Method | Purpose | Payment |
|----------|--------|---------|---------|
| `/health` | GET | Health check | Free |
| `/api/v1/verify` | POST | Local verification | Free |
| `/api/v1/semantic-repair` | POST | Paid semantic repair | x402 |
| `/api/v1/anchor` | POST | Merkle anchoring | Free |

### POST /api/v1/verify
Local validation + deterministic repair. No payment required.
Returns: `VerificationResult` + `VerificationReceipt`

### POST /api/v1/semantic-repair
Requires x402 payment. Performs semantic repair + re-validation.
Returns: `VerificationResult` + `VerificationReceipt` + `PaymentMetadata`

### POST /api/v1/anchor
Triggers Merkle anchoring of unanchored records to Algorand TestNet.
Requires: `ANCHOR_PRIVATE_KEY` configured.

## 12. Verifying Algorand Transactions

After a successful demo, verify transactions on TestNet explorer:

1. Payment TX: Check the settlement transaction ID in the response
2. Anchor TX: Check the anchoring transaction ID from POST /api/v1/anchor

TestNet explorer: https://testnet.explorer.perawallet.app/

## 13. Verifying Merkle Proofs

The demo script automatically verifies inclusion proofs. To verify manually:

```python
from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof

leaves = [record.receipt_hash for record in records]
tree = build_merkle_tree(leaves)
proof = generate_proof(tree, leaf_index)
valid = verify_proof(leaves[leaf_index], proof, tree.root, leaf_index)
```

## 14. Troubleshooting

| Issue | Solution |
|-------|----------|
| `PAYER_PRIVATE_KEY not set` | Add key to `.env.client` |
| `ANCHOR_PRIVATE_KEY not set` | Add key to `.env` |
| `Server not reachable` | Start server with `uvicorn app.main:app` |
| `402 but no settlement` | Check facilitator URL and wallet balance |
| `Merkle anchoring 503` | Set `ANCHOR_PRIVATE_KEY` in `.env` |
| `Receipt hash mismatch` | Database corruption — delete `data/verified.db` |

## 15. Test Suite

```bash
# Run all tests (no network required)
cd backend
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/anchoring/ -v   # Phase 10 Merkle tests
python -m pytest tests/storage/ -v     # Phase 9 SQLite tests
python -m pytest tests/api/ -v         # API endpoint tests
python -m pytest tests/demo/ -v        # Phase 11 failure path tests
```

All 166+ tests pass offline without real Algorand credentials.
