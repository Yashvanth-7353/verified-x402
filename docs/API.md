# API.md — Verified Backend API Contract

**Base URL**: `http://localhost:8000`  
**API Prefix**: `/api/v1`  
**Content-Type**: `application/json`

---

## Endpoints Summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/api/v1/verify` | None | Local verification (free) |
| POST | `/api/v1/semantic-repair` | x402 payment | Semantic repair (paid) |
| POST | `/api/v1/anchor` | None | Trigger Merkle anchoring |
| POST | `/api/v1/receipt/verify` | None | Verify signed receipt |
| GET | `/api/v1/receipt/public-key` | None | Get public verification key |
| GET | `/api/v1/records` | None | List persisted verification records |
| GET | `/api/v1/records/{record_id}` | None | Get a specific verification record |
| GET | `/api/v1/anchor/proof/{record_id}` | None | Get Merkle inclusion proof |

---

## 1. GET /health

Health check endpoint.

**Response 200:**
```json
{
  "status": "ok",
  "service": "verified",
  "version": "0.1.0"
}
```

---

## 2. POST /api/v1/verify

Local verification — no payment required. Runs schema validation, type checking, deterministic repair, and revalidation.

**Request:**
```json
{
  "request": {
    "request_id": "uuid",
    "submitted_at": "ISO 8601 timestamp",
    "output_type": "json",
    "output_payload": { "key": "value" },
    "schema_ref": "string",
    "agent_identifier": "string"
  },
  "policy": {
    "schema_id": "uuid",
    "version": "1.0",
    "output_type": "json",
    "schema_definition": {
      "type": "object",
      "properties": {},
      "required": []
    },
    "privacy_policy_ref": "default"
  }
}
```

**Response 200:**
```json
{
  "result": {
    "result_id": "uuid",
    "request_ref": "uuid-string",
    "findings": [],
    "repair_info": null,
    "outcome": "verified",
    "rejection_reasons": null,
    "validator_version": "0.1.0",
    "completed_at": "ISO 8601"
  },
  "receipt": {
    "receipt_id": "uuid",
    "request_id_ref": "uuid-string",
    "outcome": "verified",
    "output_hash": "sha256-hex",
    "schema_ref_and_version": "schema_id@version",
    "repair_summary_hash": null,
    "validator_version": "0.1.0",
    "issued_at": "ISO 8601",
    "receipt_hash": "sha256-hex",
    "signature": "hex-ed25519" | null,
    "signature_algorithm": "Ed25519" | null,
    "signing_key_id": "hex-16" | null
  }
}
```

**Errors:**
- `400` — Malformed request / invalid schema
- `422` — Request validation error
- `500` — Internal verification error

---

## 3. POST /api/v1/semantic-repair

Semantic repair — requires valid x402 payment. Returns 402 if no payment provided.

**Headers (first call):** None  
**Headers (with payment):** `PAYMENT-SIGNATURE: <base64-encoded-x402-payment>`

**Request:** Same structure as `/api/v1/verify`

**Response 402 (payment required):**
```json
{
  "x402Version": 1,
  "accepts": [{
    "scheme": "exact",
    "network": "algorand:...",
    "maxAmountRequired": "1000000",
    "resource": "/api/v1/semantic-repair",
    "description": "Semantic repair of a structured agent output",
    "mimeType": "",
    "payTo": "GAVM...",
    "asset": "10458941",
    "extra": {}
  }],
  "payTo": "GAVM...",
  "maxAmountRequired": "1000000",
  "asset": "10458941",
  "network": "algorand:...",
  "description": "Semantic repair of a structured agent output",
  "mimeType": "",
  "resource": "/api/v1/semantic-repair",
  "timeout": 600
}
```

**Response 200 (payment accepted, repair complete):**
```json
{
  "result": {
    "result_id": "uuid",
    "request_ref": "uuid-string",
    "findings": [],
    "repair_info": {
      "repair_id": "uuid",
      "repair_type": "semantic",
      "findings_addressed": ["finding-id-1"],
      "pre_repair_output_hash": "sha256-hex",
      "post_repair_output_hash": "sha256-hex",
      "semantic_repair_provider_ref": "MockSemanticProvider",
      "payment_ref": "uuid"
    },
    "outcome": "verified_repaired",
    "rejection_reasons": null,
    "validator_version": "0.1.0",
    "completed_at": "ISO 8601"
  },
  "receipt": { "...same as /verify receipt structure..." },
  "payment_metadata": {
    "payment_id": "uuid",
    "x402_challenge_ref": "uuid-string",
    "payment_status": "settled",
    "facilitator": "GoPlausible AVM Facilitator",
    "settlement_network": "Algorand",
    "algorand_tx_ref": "algorand-tx-id",
    "amount_and_asset": { "scheme": "exact", "asset": "10458941", "amount": "1000000" },
    "verified_at": "ISO 8601"
  }
}
```

**Errors:**
- `402` — Payment required or settlement failed
- `400` — Malformed request
- `422` — Request validation error
- `500` — Internal error (settlement context missing)

**Notes:**
- `payment_metadata` is only present when semantic repair was attempted with settled payment
- `outcome` can be `verified_repaired` (success) or `rejected` (repair failed revalidation)
- Payment success NEVER implies verification success

---

## 4. POST /api/v1/anchor

Trigger Merkle anchoring of unanchored records to Algorand TestNet.

**Request (optional):**
```json
{
  "batch_size": 10
}
```

**Response 200:**
```json
{
  "status": "anchored",
  "leaf_count": 10,
  "merkle_root": "sha256-hex-64",
  "transaction_id": "algorand-tx-id",
  "error": null
}
```

**Response 200 (no records):**
```json
{
  "status": "no_records_to_anchor",
  "leaf_count": 0,
  "merkle_root": null,
  "transaction_id": null,
  "error": null
}
```

**Errors:**
- `503` — Anchoring not configured (ANCHOR_PRIVATE_KEY not set)
- `500` — Internal anchoring error

---

## 5. POST /api/v1/receipt/verify

Independently verify a signed receipt. Does NOT require the signing private key.

**Request:**
```json
{
  "receipt": {
    "receipt_id": "uuid",
    "request_id_ref": "uuid",
    "outcome": "verified",
    "output_hash": "sha256-hex",
    "schema_ref_and_version": "schema@1.0",
    "repair_summary_hash": null,
    "validator_version": "0.1.0",
    "issued_at": "ISO 8601",
    "receipt_hash": "sha256-hex",
    "signature": "hex-ed25519",
    "signature_algorithm": "Ed25519",
    "signing_key_id": "hex-16"
  }
}
```

**Response 200:**
```json
{
  "valid": true,
  "signature_valid": true,
  "receipt_integrity_valid": true,
  "algorithm": "Ed25519",
  "signing_key_id": "hex-16",
  "details": "Receipt verified: hash valid, signature valid"
}
```

**Errors:**
- `503` — Verification not configured (RECEIPT_SIGNING_PUBLIC_KEY not set)
- `500` — Invalid verification key

---

## 6. GET /api/v1/receipt/public-key

Returns the public Ed25519 key for independent receipt verification.

**Response 200:**
```json
{
  "algorithm": "Ed25519",
  "key_id": "hex-16",
  "public_key": "base64-encoded-ed25519-public-key"
}
```

**Errors:**
- `503` — Receipt signing not configured

---

## 7. GET /api/v1/records

List persisted verification records from the local SQLite store.

**Query Parameters:**
- `offset` (int, default 0) — Number of records to skip
- `limit` (int, default 50, max 200) — Maximum records to return

**Response 200:**
```json
{
  "records": [
    {
      "record_id": "uuid",
      "request_id": "uuid",
      "receipt_id": "uuid",
      "outcome": "verified_repaired",
      "receipt_hash": "sha256-hex",
      "output_hash": "sha256-hex",
      "payment_status": "settled",
      "anchoring_status": "anchored",
      "merkle_root": "sha256-hex" | null,
      "anchor_tx_ref": "algorand-tx-id" | null,
      "created_at": "ISO 8601"
    }
  ],
  "total": 42,
  "offset": 0,
  "limit": 50
}
```

**Errors:**
- `500` — Failed to retrieve records

---

## 8. GET /api/v1/records/{record_id}

Get a specific verification record by ID.

**Response 200:**
```json
{
  "record_id": "uuid",
  "request_id": "uuid",
  "receipt_id": "uuid",
  "outcome": "verified_repaired",
  "receipt_hash": "sha256-hex",
  "output_hash": "sha256-hex",
  "payment_status": "settled",
  "anchoring_status": "anchored",
  "merkle_root": "sha256-hex",
  "anchor_tx_ref": "algorand-tx-id",
  "created_at": "ISO 8601",
  "schema_ref_and_version": "schema@1.0",
  "validator_version": "0.1.0",
  "signing_key_id": "hex-16",
  "signature_algorithm": "Ed25519",
  "repair_type": "semantic",
  "payment_facilitator": "GoPlausible AVM Facilitator",
  "settlement_network": "Algorand"
}
```

**Errors:**
- `404` — Record not found
- `500` — Failed to retrieve record

---

## 9. GET /api/v1/anchor/proof/{record_id}

Generate a Merkle inclusion proof for an anchored verification record.

**Response 200:**
```json
{
  "record_id": "uuid",
  "receipt_hash": "sha256-hex",
  "merkle_root": "sha256-hex",
  "leaf_index": 3,
  "batch_size": 10,
  "proof": [
    { "hash": "sha256-hex", "position": "left" },
    { "hash": "sha256-hex", "position": "right" },
    { "hash": "sha256-hex", "position": "left" }
  ],
  "anchor_tx_ref": "algorand-tx-id",
  "verification": {
    "valid": true,
    "details": "Proof verified: leaf 3 of 10 in batch with root a1b2c3..."
  }
}
```

**Errors:**
- `404` — Record not found
- `400` — Record is not anchored
- `500` — Failed to generate proof

---

## 10. Error Response Structure

All errors follow a consistent pattern:

```json
{
  "detail": "Human-readable error message"
}
```

For verification errors (400):
```json
{
  "error": "verification_failed",
  "message": "Description of failure",
  "reasons": ["reason-1", "reason-2"]
}
```

---

## 8. Key Concepts

### Outcome Values
- `verified` — Output passed all validation checks
- `verified_repaired` — Output required semantic repair, passed re-validation after payment
- `rejected` — Output failed validation, could not be repaired

### Payment Flow
1. Client calls `/api/v1/semantic-repair` without payment → gets 402
2. Client constructs x402 payment using the 402 response
3. Client resubmits with `PAYMENT-SIGNATURE` header
4. Server verifies payment via GoPlausible facilitator
5. Server settles payment on Algorand TestNet
6. Server performs semantic repair + re-validation
7. Returns result with receipt and payment metadata

### Receipt Integrity
- `receipt_hash` = SHA-256 of all receipt fields (excluding receipt_hash, signature, signature_algorithm, signing_key_id)
- `signature` = Ed25519 signature over canonical JSON of content fields (same fields as receipt_hash)
- `receipt_hash` is used as Merkle leaf for Algorand anchoring
- Signature proves authenticity; Merkle root proves batch inclusion

### Anchoring
- Records start as `unanchored` in SQLite
- `POST /api/v1/anchor` batches unanchored records into a Merkle tree
- Merkle root is submitted as an Algorand TestNet transaction note
- After confirmation, records are marked `anchored`
- Failed anchoring can be retried (records remain unanchored)
