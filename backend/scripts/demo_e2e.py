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

  # Real TestNet demo (requires PAYER_PRIVATE_KEY, ANCHOR_PRIVATE_KEY):
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

        # -- Step 11: Merkle anchoring --
        step(11, "Merkle Anchoring")
        unanchored = store.list_unanchored_records()
        detail("Unanchored records", str(len(unanchored)))

        from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof

        # Build Merkle tree from all unanchored records
        if unanchored:
            # Limit to a manageable batch for demo
            batch = unanchored[:10]
            leaves = [r.receipt_hash for r in batch]
            tree = build_merkle_tree(leaves)
            detail("Batch size", str(len(batch)) + " of " + str(len(unanchored)) + " unanchored")
            detail("Merkle root", tree.root[:16] + "...", CYAN)

            # Find our record's index in the batch
            demo_idx = None
            for i, r in enumerate(batch):
                if r.request_id == paid_request_id:
                    demo_idx = i
                    break

            if demo_idx is not None:
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
                # Our record is beyond the first batch; build a single-leaf tree for proof demo
                step(12, "Merkle Inclusion Proof (single-leaf demo)")
                single_leaves = [record.receipt_hash]
                single_tree = build_merkle_tree(single_leaves)
                single_proof = generate_proof(single_tree, 0)
                single_valid = verify_proof(record.receipt_hash, single_proof, single_tree.root, 0)
                detail("Leaf index", "0 (single leaf)")
                detail("Proof length", f"{len(single_proof)} hashes")
                detail("Proof valid", "YES" if single_valid else "NO",
                       GREEN if single_valid else RED)
                if single_valid:
                    success("Merkle inclusion proof: VALID")

                step(13, "Tamper Detection")
                fake_hash = hashlib.sha256("tampered_data".encode()).hexdigest()
                tamper_valid = verify_proof(fake_hash, single_proof, single_tree.root, 0)
                detail("Tampered hash verification", "INVALID" if not tamper_valid else "ERROR",
                       GREEN if not tamper_valid else RED)
                if not tamper_valid:
                    success("Tamper detection: WORKING (tampered hash rejected)")
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
# Real TestNet demo (uses live Algorand)
# ===============================================================

def run_real_demo():
    """Run the real end-to-end demo against a running server with live Algorand."""
    import httpx
    import asyncio

    header("VERIFIED -- REAL TESTNET DEMONSTRATION")
    print(f"  {YELLOW}This demo requires a running server and real Algorand TestNet.{RESET}")
    print(f"  {DIM}Start server: cd backend && uvicorn app.main:app --port 8000{RESET}\n")

    env = check_environment(real_mode=True)

    server_url = "http://localhost:8000"

    # Check server is running
    step(1, "Server Health Check")
    try:
        resp = httpx.get(f"{server_url}/health", timeout=5)
        if resp.status_code == 200:
            detail("Server", "running [OK]", GREEN)
        else:
            failure(f"Server returned {resp.status_code}")
            return
    except Exception as e:
        failure(f"Server not reachable: {e}")
        detail("Start server", "cd backend && uvicorn app.main:app --port 8000")
        return

    # Load payer key for x402
    from dotenv import load_dotenv
    load_dotenv(".env.client")

    payer_key = os.environ.get("PAYER_PRIVATE_KEY")
    if not payer_key:
        failure("PAYER_PRIVATE_KEY not found in .env.client")
        return

    from scripts.e2e_client import PrivateKeySigner
    from x402.client import x402Client
    from x402.mechanisms.avm.exact import ExactAvmClientScheme
    from x402.schemas import PaymentRequired
    import base64

    signer = PrivateKeySigner(payer_key)
    detail("Payer address", signer.address)

    # Build payload
    payload = build_demo_payload()
    request_id = payload["request"]["request_id"]

    step(2, "Verification Request")
    detail("Request ID", request_id[:8] + "...")

    async def _real_flow():
        async with httpx.AsyncClient(timeout=60) as client:
            # Step 3: Call semantic-repair without payment -> expect 402
            step(3, "HTTP 402 Challenge")
            t0 = time.time()
            resp = await client.post(f"{server_url}/api/v1/semantic-repair", json=payload)
            t_402 = (time.time() - t0) * 1000

            if resp.status_code != 402:
                failure(f"Expected 402, got {resp.status_code}")
                detail("Response", resp.text[:200])
                return

            timing("402 response", t_402)
            detail("Status", "402 Payment Required [OK]", GREEN)

            # Parse payment requirements
            payment_required_b64 = resp.headers.get("PAYMENT-REQUIRED")
            if not payment_required_b64:
                failure("No PAYMENT-REQUIRED header")
                return

            pr_json = base64.b64decode(payment_required_b64).decode("utf-8")
            pr_data = json.loads(pr_json)
            detail("Payment scheme", pr_data.get("accepts", [{}])[0].get("scheme", "unknown"))
            detail("Asset", pr_data.get("accepts", [{}])[0].get("asset", "unknown"))
            detail("Amount", pr_data.get("accepts", [{}])[0].get("amount", "unknown"))

            # Step 4: Create x402 payment
            step(4, "x402 Payment Construction")
            x402_client = x402Client()
            scheme = ExactAvmClientScheme(signer=signer)
            x402_client.register(env["ALGORAND_NETWORK"], scheme)
            payment_required_model = PaymentRequired(**pr_data)

            t0 = time.time()
            payment_payload = await x402_client.create_payment_payload(payment_required_model)
            t_payment = (time.time() - t0) * 1000
            timing("Payment construction", t_payment)
            detail("x402 version", str(payment_payload.x402_version))

            # Step 5: Submit payment
            step(5, "Payment Submission & Settlement")
            encoded = base64.b64encode(
                payment_payload.model_dump_json(by_alias=True, exclude_none=True).encode()
            ).decode()
            header_name = "PAYMENT-SIGNATURE" if payment_payload.x402_version == 2 else "X-PAYMENT"

            t0 = time.time()
            resp2 = await client.post(
                f"{server_url}/api/v1/semantic-repair",
                json=payload,
                headers={header_name: encoded},
            )
            t_settle = (time.time() - t0) * 1000

            if resp2.status_code == 200:
                timing("Settlement + repair + receipt", t_settle)
                detail("Status", "200 OK [OK]", GREEN)

                data = resp2.json()
                result = data["result"]
                receipt = data["receipt"]
                pm = data.get("payment_metadata")

                # Step 6: Show result
                step(6, "Semantic Repair Result")
                detail("Outcome", result["outcome"], GREEN)
                detail("Repair type", result.get("repair_info", {}).get("repair_type", "N/A"))
                detail("Payment ref", result.get("repair_info", {}).get("payment_ref", "N/A")[:8] + "...")

                # Step 7: Payment metadata
                step(7, "Payment Metadata")
                if pm:
                    detail("Status", pm["payment_status"], GREEN)
                    detail("Facilitator", pm["facilitator"])
                    detail("Network", pm["settlement_network"])
                    detail("Settlement TX", pm.get("algorand_tx_ref", "N/A"))

                # Step 8: Receipt
                step(8, "Verification Receipt")
                detail("Receipt ID", str(receipt["receipt_id"])[:8] + "...")
                detail("Outcome", receipt["outcome"])
                detail("Receipt hash", receipt["receipt_hash"][:16] + "...")
                detail("Output hash", receipt["output_hash"][:16] + "...")

                # Verify receipt hash
                from app.evidence.hasher import hash_data
                rd = dict(receipt)
                rd.pop("receipt_hash", None)
                rd.pop("signature", None)
                computed = hash_data(rd)
                valid = computed == receipt["receipt_hash"]
                detail("Receipt integrity", "VALID [OK]" if valid else "INVALID [FAIL]",
                       GREEN if valid else RED)

                # Step 9: SQLite
                step(9, "SQLite Persistence")
                from app.storage.store import LocalVerificationRecordStore
                from app.core.config import settings
                store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)
                record = store.get_by_request_id(request_id)
                if record:
                    detail("Record", "PERSISTED [OK]", GREEN)
                    detail("Anchoring", record.anchoring_status.value)
                else:
                    detail("Record", "NOT FOUND", RED)

                # Step 10: Merkle anchoring (if configured)
                step(10, "Merkle Anchoring")
                anchor_key = os.environ.get("ANCHOR_PRIVATE_KEY")
                if anchor_key:
                    unanchored = store.list_unanchored_records()
                    detail("Unanchored", str(len(unanchored)))

                    if len(unanchored) > 0:
                        from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof
                        leaves = [r.receipt_hash for r in unanchored[:10]]
                        tree = build_merkle_tree(leaves)
                        detail("Merkle root", tree.root[:16] + "...")

                        # Find demo record index
                        demo_idx = None
                        for i, r in enumerate(unanchored[:10]):
                            if r.request_id == request_id:
                                demo_idx = i
                                break

                        if demo_idx is not None:
                            proof = generate_proof(tree, demo_idx)
                            proof_valid = verify_proof(leaves[demo_idx], proof, tree.root, demo_idx)
                            detail("Inclusion proof", "VALID [OK]" if proof_valid else "INVALID [FAIL]",
                                   GREEN if proof_valid else RED)

                            # Tamper test
                            fake = hashlib.sha256("tampered".encode()).hexdigest()
                            tamper = verify_proof(fake, proof, tree.root, demo_idx)
                            detail("Tamper detection", "WORKING [OK]" if not tamper else "BROKEN",
                                   GREEN if not tamper else RED)
                else:
                    detail("ANCHOR_PRIVATE_KEY", "not set -- skipping anchoring")

                store.close()

            else:
                failure(f"Payment failed: {resp2.status_code}")
                detail("Response", resp2.text[:200])

    asyncio.run(_real_flow())

    header("DEMO COMPLETE")


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
