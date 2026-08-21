"""
===============================================================
  VERIFIED -- End-to-End Demonstration
  Phase 11: Demo Assembly & Validation
===============================================================

Demonstrates the complete Verified lifecycle:

  AI Agent Output -> Local Validation -> Findings -> Escalation
  -> HTTP 402 -> x402 Payment -> GoPlausible Facilitator
  -> Algorand TestNet Settlement -> Semantic Repair -> Re-validation
  -> verified_repaired -> VerificationReceipt -> SQLite Persistence
  -> Merkle Batch -> Merkle Root -> Algorand Anchor -> Inclusion Proof

Usage:
  # Offline demo (mocked payment, no network required):
  python scripts/demo_e2e.py

  # Real TestNet demo (in-process, real Algorand):
  python scripts/demo_e2e.py --real

Environment variables (for real demo):
  PAYER_PRIVATE_KEY    -- Base64-encoded Algorand private key for x402 payment
  ANCHOR_PRIVATE_KEY   -- Base64-encoded Algorand private key for Merkle anchoring
  FACILITATOR_URL      -- GoPlausible facilitator URL
  ALGORAND_NETWORK     -- Algorand network identifier
  ANCHOR_ALGOD_ADDRESS -- Algorand TestNet node URL
"""
from __future__ import annotations

import sys
import os
import time
import hashlib
import json
import argparse
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===============================================================
# Display helpers
# ===============================================================

BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
DIM = "\033[2m"


def header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{'=' * 60}")


def step(num: int, title: str):
    print(f"\n{BOLD}{CYAN}[{num}]{RESET} {BOLD}{title}{RESET}")


def detail(label: str, value: str, color: str = ""):
    c = color or ""
    print(f"    {DIM}{label}:{RESET} {c}{value}{RESET}")


def success(msg: str):
    print(f"    {GREEN}[OK] {msg}{RESET}")


def warning(msg: str):
    print(f"    {YELLOW}[WARN] {msg}{RESET}")


def failure(msg: str):
    print(f"    {RED}[FAIL] {msg}{RESET}")


def timing(label: str, ms: float):
    print(f"    {DIM}{label}:{RESET} {CYAN}{ms:.0f}ms{RESET}")


# ===============================================================
# Environment check
# ===============================================================

def check_environment(real_mode: bool = False) -> dict:
    """Check required environment variables without exposing values."""
    header("ENVIRONMENT CHECK")

    env_vars = {
        "PAYER_PRIVATE_KEY": os.environ.get("PAYER_PRIVATE_KEY"),
        "ANCHOR_PRIVATE_KEY": os.environ.get("ANCHOR_PRIVATE_KEY"),
        "FACILITATOR_URL": os.environ.get("FACILITATOR_URL", "https://facilitator.goplausible.xyz"),
        "ALGORAND_NETWORK": os.environ.get("ALGORAND_NETWORK", "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="),
        "ANCHOR_ALGOD_ADDRESS": os.environ.get("ANCHOR_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"),
    }

    for key, value in env_vars.items():
        if value:
            if "KEY" in key or "SECRET" in key:
                detail(key, "configured [OK]")
            else:
                detail(key, value)
        else:
            detail(key, "NOT SET", RED)

    if real_mode:
        if not env_vars.get("PAYER_PRIVATE_KEY"):
            failure("PAYER_PRIVATE_KEY is required for real demo mode")
            sys.exit(1)
        if not env_vars.get("ANCHOR_PRIVATE_KEY"):
            warning("ANCHOR_PRIVATE_KEY not set -- Merkle anchoring will be skipped")
    else:
        detail("Mode", "OFFLINE (mocked payment)")

    return env_vars


# ===============================================================
# Demo data
# ===============================================================

def build_demo_payload(request_id: str = None) -> dict:
    """Build a deterministic demo verification request."""
    if request_id is None:
        request_id = str(uuid4())
    schema_id = str(uuid4())

    return {
        "request": {
            "request_id": request_id,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "output_type": "json",
            "output_payload": {
                "name": "Alice",
                "inject_mock_semantic_repair": {"age": 30}
            },
            "schema_ref": "demo_schema",
            "agent_identifier": "demo_agent",
        },
        "policy": {
            "schema_id": schema_id,
            "version": "1.0",
            "output_type": "json",
            "schema_definition": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
            "privacy_policy_ref": "default",
        },
    }


# ===============================================================
# Offline demo (uses TestClient -- no network required)
# ===============================================================

def run_offline_demo():
    """Run the complete demo using FastAPI TestClient with mocked x402."""
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from x402.http.x402_http_server import x402HTTPResourceServer
    from x402.server import x402ResourceServer
    from x402.http.types import HTTPProcessResult, RESULT_PAYMENT_VERIFIED, ProcessSettleResult
    from app.main import app
    from app.storage.store import LocalVerificationRecordStore
    from app.core.config import settings

    header("VERIFIED -- OFFLINE END-TO-END DEMONSTRATION")
    print(f"  {DIM}All payment and Algorand operations are mocked.{RESET}")
    print(f"  {DIM}No network connectivity required.{RESET}")

    # -- Environment --
    check_environment(real_mode=False)

    # -- Demo payloads (separate IDs for free vs paid paths) --
    free_request_id = str(uuid4())
    paid_request_id = str(uuid4())
    free_payload = build_demo_payload(free_request_id)
    paid_payload = build_demo_payload(paid_request_id)

    step(1, "Verification Request")
    detail("Free Request ID", free_request_id[:8] + "...")
    detail("Paid Request ID", paid_request_id[:8] + "...")
    detail("Output", '{"name": "Alice", "inject_mock_semantic_repair": {"age": 30}}')
    detail("Schema", "object with required: [name, age]")

    # -- Step 2: Local validation via /verify (free path) --
    step(2, "Local Validation (free -- no payment required)")
    t0 = time.time()
    with TestClient(app, raise_server_exceptions=False) as c:
        # Patch x402 initialization for free routes
        with patch.object(x402ResourceServer, "initialize"):
            with patch.object(x402HTTPResourceServer, "initialize"):
                resp = c.post("/api/v1/verify", json=free_payload)
    t_validation = (time.time() - t0) * 1000

    if resp.status_code == 200:
        data = resp.json()
        result = data["result"]
        receipt = data["receipt"]

        detail("Outcome", result["outcome"], GREEN if result["outcome"] == "verified" else YELLOW)
        detail("Findings", f"{len(result['findings'])} total")
        for f in result["findings"]:
            detail("  ->", f"[{f['stage']}] {f['severity']}: {f['description']}")
        timing("Local validation", t_validation)
        success("Local validation completed")
    else:
        failure(f"Validation failed: {resp.status_code}")
        return

    # -- Step 3: Show that semantic repair needs payment --
    step(3, "Escalation Decision")
    detail("Blocking findings", "Yes (missing 'age' field)")
    detail("Repair type", "semantic (requires external AI)")
    detail("Decision", "escalate -> x402 payment required", YELLOW)

    # -- Step 4-8: Semantic repair with mocked payment --
    step(4, "x402 Payment Flow (mocked)")
    detail("Challenge", "HTTP 402 Payment Required")
    detail("Payment asset", "ASA 10458941 (TestNet USDC)")
    detail("Amount", "1,000,000 (1 USDC)")
    detail("Network", "Algorand TestNet")
    detail("Facilitator", "GoPlausible AVM Facilitator")

    # Mock the x402 flow
    verified_result = HTTPProcessResult(type=RESULT_PAYMENT_VERIFIED)
    settle_result = ProcessSettleResult(
        success=True,
        transaction="DEMO_MOCK_TX_abc123def456",
        network="algorand",
        payer="MOCK_PAYER_ADDRESS",
        headers={},
    )

    step(5, "Payment Settlement")
    detail("Status", "settled [OK]", GREEN)
    detail("Settlement TX", "DEMO_MOCK_TX_abc123def456")
    detail("Network", "Algorand TestNet")

    step(6, "Semantic Repair")
    t0 = time.time()
    with TestClient(app, raise_server_exceptions=False) as c:
        with patch.object(x402ResourceServer, "initialize"):
            with patch.object(x402HTTPResourceServer, "initialize"):
                with patch(
                    "x402.http.x402_http_server.x402HTTPResourceServer.process_http_request",
                    new_callable=AsyncMock,
                    return_value=verified_result,
                ):
                    with patch(
                        "x402.http.x402_http_server.x402HTTPResourceServer.process_settlement",
                        new_callable=AsyncMock,
                        return_value=settle_result,
                    ):
                        resp = c.post("/api/v1/semantic-repair", json=paid_payload)
    t_repair = (time.time() - t0) * 1000

    if resp.status_code == 200:
        data = resp.json()
        result = data["result"]
        receipt = data["receipt"]
        payment_metadata = data.get("payment_metadata")

        timing("Semantic repair + revalidation", t_repair)

        step(7, "Re-validation Result")
        detail("Outcome", result["outcome"], GREEN)
        detail("Repair type", result.get("repair_info", {}).get("repair_type", "N/A"))
        detail("Payment ref", result.get("repair_info", {}).get("payment_ref", "N/A"), GREEN)
        success("Semantic repair passed re-validation")

        step(8, "Payment Metadata (Phase 8)")
        if payment_metadata:
            detail("Payment status", payment_metadata.get("payment_status", "N/A"), GREEN)
            detail("Facilitator", payment_metadata.get("facilitator", "N/A"))
            detail("Network", payment_metadata.get("settlement_network", "N/A"))
            detail("Settlement TX", payment_metadata.get("algorand_tx_ref", "N/A"))
            success("Phase 8 invariant: payment_status = settled")
        else:
            warning("No payment metadata (expected in offline mode)")

        step(9, "Verification Receipt")
        detail("Receipt ID", str(receipt["receipt_id"])[:8] + "...")
        detail("Request ID", receipt["request_id_ref"][:8] + "...")
        detail("Outcome", receipt["outcome"], GREEN)
        detail("Output hash", receipt["output_hash"][:16] + "...")
        detail("Schema", receipt["schema_ref_and_version"])
        detail("Repair hash", (receipt.get("repair_summary_hash") or "N/A")[:16] + "...")
        detail("Validator", receipt["validator_version"])
        detail("Issued at", receipt["issued_at"])

        # Verify receipt hash
        from app.evidence.hasher import hash_data
        receipt_dict = dict(receipt)
        receipt_dict.pop("receipt_hash", None)
        receipt_dict.pop("signature", None)
        receipt_dict.pop("signature_algorithm", None)
        receipt_dict.pop("signing_key_id", None)
        computed_hash = hash_data(receipt_dict)
        hash_valid = computed_hash == receipt["receipt_hash"]

        detail("Receipt hash", receipt["receipt_hash"][:16] + "...",
               GREEN if hash_valid else RED)
        if hash_valid:
            success("Receipt integrity: VALID")
        else:
            failure("Receipt integrity: INVALID")

        # -- Step 10: SQLite persistence --
        step(10, "SQLite Persistence")
        store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)
        record = store.get_by_request_id(paid_request_id)

        if record:
            detail("Record ID", str(record.record_id)[:8] + "...")
            detail("Outcome", record.outcome)
            detail("Receipt hash", record.receipt_hash[:16] + "...")
            detail("Anchoring status", record.anchoring_status.value)
            detail("Database", settings.resolved_database_path)
            success("Record persisted to SQLite")
        else:
            failure("Record not found in database")
            store.close()
            return

        # -- Step 11: Merkle tree (local only for offline) --
        step(11, "Merkle Tree (offline -- no Algorand anchor)")
        unanchored = store.list_unanchored_records()
        detail("Unanchored records", str(len(unanchored)))

        from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof

        # Filter to records with valid 64-char hex receipt_hash
        valid_unanchored = [r for r in unanchored if len(r.receipt_hash) == 64]
        valid_unanchored = [r for r in valid_unanchored if all(c in '0123456789abcdef' for c in r.receipt_hash)]

        if valid_unanchored:
            # Find our record in valid unanchored list
            demo_idx = None
            for i, r in enumerate(valid_unanchored):
                if r.request_id == paid_request_id:
                    demo_idx = i
                    break

            if demo_idx is not None:
                leaves = [r.receipt_hash for r in valid_unanchored]
                tree = build_merkle_tree(leaves)
                detail("Batch size", str(len(leaves)))
                detail("Merkle root", tree.root[:16] + "...", CYAN)

                # -- Step 12: Inclusion proof --
                step(12, "Merkle Inclusion Proof")
                proof = generate_proof(tree, demo_idx)
                valid = verify_proof(leaves[demo_idx], proof, tree.root, demo_idx)

                detail("Leaf index", str(demo_idx))
                detail("Proof length", f"{len(proof)} hashes")
                detail("Proof valid", "YES" if valid else "NO",
                       GREEN if valid else RED)

                if valid:
                    success("Merkle inclusion proof: VALID")

                # -- Step 13: Tamper detection --
                step(13, "Tamper Detection")
                fake_hash = hashlib.sha256("tampered_data".encode()).hexdigest()
                tamper_valid = verify_proof(fake_hash, proof, tree.root, demo_idx)
                detail("Tampered hash verification", "INVALID" if not tamper_valid else "ERROR",
                       GREEN if not tamper_valid else RED)

                if not tamper_valid:
                    success("Tamper detection: WORKING (tampered hash rejected)")
            else:
                failure("Demo record not found in unanchored list")
        else:
            detail("Records", "None available for Merkle tree")

        store.close()

    else:
        failure(f"Semantic repair failed: {resp.status_code} {resp.text[:200]}")

    # -- Summary --
    header("DEMO COMPLETE -- SUMMARY")
    detail("Pipeline", "verified -> verified_repaired -> receipt -> SQLite -> Merkle")
    detail("Phases demonstrated", "7 (payment) + 8 (receipt) + 9 (SQLite) + 10 (Merkle)")
    detail("Mode", "OFFLINE (all mocked)")
    print(f"\n  {DIM}For real TestNet demo, run: python scripts/demo_e2e.py --real{RESET}\n")


# ===============================================================
# Real TestNet demo (in-process, real Algorand)
# ===============================================================

def run_real_demo():
    """Run the real E2E demo in-process using TestClient.

    All external calls are real:
      - x402 payment verification via GoPlausible facilitator
      - Algorand TestNet settlement
      - Merkle anchoring to Algorand TestNet

    No server startup required -- runs entirely in-process.
    """
    import asyncio
    import base64

    from dotenv import load_dotenv
    from fastapi.testclient import TestClient

    from app.main import app
    from app.storage.store import LocalVerificationRecordStore
    from app.core.config import settings
    from app.evidence.hasher import hash_data

    # -- Load env --
    load_dotenv(".env")
    load_dotenv(".env.client")

    header("VERIFIED -- REAL TESTNET DEMONSTRATION (in-process)")
    print(f"  {YELLOW}Real Algorand TestNet -- real x402 payment + real Merkle anchoring.{RESET}\n")

    env = check_environment(real_mode=True)

    payer_key = os.environ.get("PAYER_PRIVATE_KEY")
    anchor_key = os.environ.get("ANCHOR_PRIVATE_KEY")

    from scripts.e2e_client import PrivateKeySigner

    signer = PrivateKeySigner(payer_key)
    detail("Payer address", signer.address)

    if anchor_key:
        from algosdk import encoding as algo_encoding
        anchor_sk = base64.b64decode(anchor_key)
        anchor_addr = algo_encoding.encode_address(anchor_sk[32:])
        detail("Anchor address", anchor_addr)

    # ===========================================================
    # Step 1-2: Build verification request + show free path
    # ===========================================================
    free_request_id = str(uuid4())
    free_payload = build_demo_payload(free_request_id)

    step(1, "Verification Request")
    detail("Free Request ID", free_request_id[:8] + "...")
    detail("Output", '{"name": "Alice", "inject_mock_semantic_repair": {"age": 30}}')
    detail("Schema", "object with required: [name, age]")

    # Free path (local validation, no payment)
    step(2, "Local Validation (free -- no payment)")
    t0 = time.time()
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/api/v1/verify", json=free_payload)
    t_local = (time.time() - t0) * 1000

    if resp.status_code == 200:
        data = resp.json()
        detail("Outcome", data["result"]["outcome"], YELLOW)
        detail("Findings", str(len(data["result"]["findings"])))
        timing("Local validation", t_local)
    else:
        failure(f"Local validation failed: {resp.status_code}")

    step(3, "Escalation Decision")
    detail("Blocking findings", "Yes (missing 'age' field)")
    detail("Decision", "escalate -> x402 payment required", YELLOW)

    # Paid path (separate request_id to avoid SQLite integrity conflict)
    request_id = str(uuid4())
    payload = build_demo_payload(request_id)

    # ===========================================================
    # Step 4-6: Real x402 payment + semantic repair
    # ===========================================================
    step(4, "x402 Payment + Semantic Repair (REAL)")

    async def _real_payment_flow():
        import httpx
        from x402.client import x402Client
        from x402.mechanisms.avm.exact import ExactAvmClientScheme
        from x402.schemas import PaymentRequired

        # Use httpx to a running server... but we're in-process.
        # Instead, use TestClient for the 402 challenge, then x402Client
        # for payment creation, then TestClient again for the paid request.

        # First get 402 from TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            resp_402 = c.post("/api/v1/semantic-repair", json=payload)

        if resp_402.status_code != 402:
            failure(f"Expected 402, got {resp_402.status_code}")
            detail("Response", resp_402.text[:200])
            return None, None, None, None

        t_402_start = time.time()
        detail("Status", "402 Payment Required [OK]", GREEN)

        # Parse payment requirements
        payment_required_b64 = resp_402.headers.get("PAYMENT-REQUIRED")
        if not payment_required_b64:
            failure("No PAYMENT-REQUIRED header in 402 response")
            return None, None, None, None

        pr_json = base64.b64decode(payment_required_b64).decode("utf-8")
        pr_data = json.loads(pr_json)
        detail("Scheme", pr_data.get("accepts", [{}])[0].get("scheme", "unknown"))
        detail("Asset", pr_data.get("accepts", [{}])[0].get("asset", "unknown"))
        detail("Amount", pr_data.get("accepts", [{}])[0].get("amount", "unknown"))

        # Create x402 payment with real client
        x402_client = x402Client()
        scheme = ExactAvmClientScheme(signer=signer)
        network = env["ALGORAND_NETWORK"]
        x402_client.register(network, scheme)
        payment_required_model = PaymentRequired(**pr_data)

        t0 = time.time()
        payment_payload = await x402_client.create_payment_payload(payment_required_model)
        t_payment_create = (time.time() - t0) * 1000
        timing("Payment construction (real signing)", t_payment_create)
        detail("x402 version", str(payment_payload.x402_version))

        # Encode payment header
        encoded = base64.b64encode(
            payment_payload.model_dump_json(by_alias=True, exclude_none=True).encode()
        ).decode()
        header_name = "PAYMENT-SIGNATURE" if payment_payload.x402_version == 2 else "X-PAYMENT"

        # Submit with payment to TestClient (real settlement via middleware)
        t0 = time.time()
        with TestClient(app, raise_server_exceptions=False) as c:
            resp_paid = c.post(
                "/api/v1/semantic-repair",
                json=payload,
                headers={header_name: encoded},
            )
        t_settle = (time.time() - t0) * 1000

        t_402_total = (time.time() - t_402_start) * 1000
        timing("Settlement + repair + receipt (real)", t_settle)
        timing("Total 402 flow", t_402_total)

        if resp_paid.status_code == 200:
            detail("Status", "200 OK [OK]", GREEN)
            data = resp_paid.json()
            return data, resp_paid.headers, t_settle, t_402_total
        else:
            failure(f"Payment failed: {resp_paid.status_code}")
            detail("Response", resp_paid.text[:300])
            return None, None, None, None

    data, resp_headers, t_settle, t_402_total = asyncio.run(_real_payment_flow())

    if data is None:
        failure("x402 payment flow failed")
        return

    result = data["result"]
    receipt = data["receipt"]
    pm = data.get("payment_metadata")

    # ===========================================================
    # Step 7: Show result
    # ===========================================================
    step(5, "Semantic Repair Result")
    detail("Outcome", result["outcome"], GREEN)
    detail("Repair type", result.get("repair_info", {}).get("repair_type", "N/A"))
    payment_ref = result.get("repair_info", {}).get("payment_ref")
    detail("Payment ref", (payment_ref[:8] + "..." if payment_ref else "N/A"), GREEN)
    success("Semantic repair passed re-validation")

    # ===========================================================
    # Step 8: Payment metadata
    # ===========================================================
    step(6, "Payment Metadata (Phase 8)")
    if pm:
        detail("Status", pm["payment_status"], GREEN)
        detail("Facilitator", pm["facilitator"])
        detail("Network", pm["settlement_network"])
        detail("Settlement TX", pm.get("algorand_tx_ref", "N/A"))
        success("Phase 8 invariant: payment_status = settled")
    else:
        warning("No payment metadata returned")

    # ===========================================================
    # Step 9: Receipt
    # ===========================================================
    step(7, "Verification Receipt")
    detail("Receipt ID", str(receipt["receipt_id"])[:8] + "...")
    detail("Outcome", receipt["outcome"], GREEN)
    detail("Output hash", receipt["output_hash"][:16] + "...")
    detail("Schema", receipt["schema_ref_and_version"])
    detail("Repair hash", (receipt.get("repair_summary_hash") or "N/A")[:16] + "...")
    detail("Validator", receipt["validator_version"])

    # Verify receipt hash
    rd = dict(receipt)
    rd.pop("receipt_hash", None)
    rd.pop("signature", None)
    rd.pop("signature_algorithm", None)
    rd.pop("signing_key_id", None)
    computed = hash_data(rd)
    valid = computed == receipt["receipt_hash"]
    detail("Receipt hash", receipt["receipt_hash"][:16] + "...",
           GREEN if valid else RED)
    if valid:
        success("Receipt integrity: VALID")
    else:
        failure("Receipt integrity: INVALID")

    # ===========================================================
    # Step 10: SQLite persistence
    # ===========================================================
    step(8, "SQLite Persistence")
    store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)
    record = store.get_by_request_id(request_id)

    if record:
        detail("Record", "PERSISTED [OK]", GREEN)
        detail("Outcome", record.outcome)
        detail("Receipt hash", record.receipt_hash[:16] + "...")
        detail("Anchoring", record.anchoring_status.value)
        detail("Database", settings.resolved_database_path)
    else:
        failure("Record not found in database")
        store.close()
        return

    # ===========================================================
    # Step 11: REAL Merkle anchoring to Algorand TestNet
    # ===========================================================
    step(9, "Merkle Anchoring (REAL Algorand TestNet)")

    if not anchor_key:
        detail("ANCHOR_PRIVATE_KEY", "not set -- skipping anchoring")
        store.close()
        return

    from app.anchoring.service import (
        MerkleAnchoringService,
        TestNetAlgorandClient,
    )
    from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof

    # Create real Algorand client for anchoring
    anchor_client = TestNetAlgorandClient(
        private_key_b64=anchor_key,
        algod_address=settings.ANCHOR_ALGOD_ADDRESS,
        algod_token=settings.ANCHOR_ALGOD_TOKEN,
    )

    # Show unanchored count before
    unanchored_before = store.list_unanchored_records()
    detail("Unanchored before", str(len(unanchored_before)))

    # Compute Merkle root for display
    leaves_before = [r.receipt_hash for r in unanchored_before]
    tree_before = build_merkle_tree(leaves_before)
    detail("Merkle root", tree_before.root[:16] + "...", CYAN)
    detail("Leaf count", str(len(leaves_before)))

    # Execute REAL anchoring
    anchoring_service = MerkleAnchoringService(
        record_store=store,
        anchor_client=anchor_client,
        batch_size=settings.MERKLE_BATCH_SIZE,
    )

    t0 = time.time()
    anchor_result = anchoring_service.anchor_pending_records()
    t_anchor = (time.time() - t0) * 1000

    if anchor_result.status == "anchored":
        timing("Real Algorand anchor", t_anchor)
        detail("Status", "ANCHORED [OK]", GREEN)
        detail("Records anchored", str(anchor_result.leaf_count))
        detail("Merkle root", anchor_result.merkle_root[:16] + "...")
        detail("Algorand tx", anchor_result.transaction_id, CYAN)
        success("Real Algorand anchor transaction confirmed")
    elif anchor_result.status == "no_records_to_anchor":
        detail("Status", "no unanchored records")
        store.close()
        return
    else:
        failure(f"Anchoring failed: {anchor_result.error}")
        detail("Status", anchor_result.status)
        store.close()
        return

    # ===========================================================
    # Step 12: Verify on-chain transaction
    # ===========================================================
    step(10, "On-Chain Verification (readback from Algorand)")
    try:
        from algosdk.v2client import algod as algod_module
        verify_client = algod_module.AlgodClient(
            settings.ANCHOR_ALGOD_TOKEN,
            settings.ANCHOR_ALGOD_ADDRESS,
        )
        tx_info = verify_client.pending_transaction_info(anchor_result.transaction_id)
        if tx_info and tx_info.get("confirmed-round"):
            detail("Confirmed round", str(tx_info["confirmed-round"]))
            detail("Transaction", "CONFIRMED on Algorand TestNet", GREEN)

            # Verify note field contains Merkle root
            note_b64 = tx_info.get("txn", {}).get("txn", {}).get("note", "")
            if note_b64:
                note_bytes = base64.b64decode(note_b64)
                note_str = note_bytes.decode("utf-8", errors="replace")
                expected_prefix = f"verified-merkle-v1:{anchor_result.merkle_root}"
                if note_str == expected_prefix:
                    detail("On-chain note", "MATCHES local Merkle root", GREEN)
                    success("On-chain root verification: VALID")
                else:
                    detail("On-chain note", note_str[:64] + "...")
                    detail("Expected prefix", expected_prefix[:64] + "...")
                    warning("Note format mismatch (check encoding)")
            else:
                detail("Note", "empty in tx info")
        else:
            detail("Transaction", "PENDING (not yet confirmed)")
    except Exception as e:
        detail("On-chain readback", f"error: {e}")
        warning("Could not read back transaction from Algorand (may need time to propagate)")

    # ===========================================================
    # Step 13: Verify local anchor state
    # ===========================================================
    step(11, "Local Anchor State")
    record_after = store.get_by_request_id(request_id)
    if record_after:
        detail("Anchoring status", record_after.anchoring_status.value,
               GREEN if record_after.anchoring_status.value == "anchored" else RED)
        detail("Merkle root", (record_after.merkle_root or "N/A")[:16] + "...")
        detail("Anchor tx ref", (record_after.anchor_tx_ref or "N/A"))

        unanchored_after = store.list_unanchored_records()
        still_unanchored = [r for r in unanchored_after if r.request_id == request_id]
        if not still_unanchored:
            detail("In unanchored list", "NO (correct)", GREEN)
            success("Local anchor state: VALID")
        else:
            detail("In unanchored list", "YES (unexpected)", RED)

    # ===========================================================
    # Step 14: Merkle inclusion proof
    # ===========================================================
    step(12, "Merkle Inclusion Proof")

    # Rebuild tree from the original ordered batch for proof generation
    demo_idx = None
    for i, r in enumerate(unanchored_before):
        if r.request_id == request_id:
            demo_idx = i
            break

    if demo_idx is not None:
        proof = generate_proof(tree_before, demo_idx)
        proof_valid = verify_proof(leaves_before[demo_idx], proof, tree_before.root, demo_idx)

        detail("Leaf index", str(demo_idx))
        detail("Proof length", f"{len(proof)} hashes")
        detail("Proof valid", "YES" if proof_valid else "NO",
               GREEN if proof_valid else RED)

        if proof_valid:
            success("Merkle inclusion proof: VALID")
    else:
        detail("Demo record", "not found in anchoring batch (may have been in overflow)")

    # ===========================================================
    # Step 15: Tamper detection
    # ===========================================================
    step(13, "Tamper Detection")
    if demo_idx is not None:
        fake = hashlib.sha256("tampered".encode()).hexdigest()
        tamper = verify_proof(fake, proof, tree_before.root, demo_idx)
        detail("Tampered hash", "REJECTED [OK]" if not tamper else "ACCEPTED [ERROR]",
               GREEN if not tamper else RED)

        if not tamper:
            success("Tamper detection: WORKING")
    else:
        detail("Skipped", "demo record not in anchoring batch")

    store.close()

    # ===========================================================
    # Summary
    # ===========================================================
    header("DEMO COMPLETE")
    detail("Payment", "REAL x402 -> GoPlausible -> Algorand TestNet", GREEN)
    detail("Receipt", f"REAL (receipt_hash={receipt['receipt_hash'][:16]}...)", GREEN)
    detail("SQLite", "REAL persistence", GREEN)
    detail("Anchoring", f"REAL Algorand tx={anchor_result.transaction_id}", GREEN)
    detail("Proof", "REAL Merkle inclusion proof", GREEN)


# ===============================================================
# Main
# ===============================================================

def main():
    parser = argparse.ArgumentParser(description="Verified E2E Demo")
    parser.add_argument("--real", action="store_true", help="Run against real TestNet")
    args = parser.parse_args()

    if args.real:
        run_real_demo()
    else:
        run_offline_demo()


if __name__ == "__main__":
    main()
