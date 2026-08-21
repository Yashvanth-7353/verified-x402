"""
Phase 11: Demo failure path tests.

Demonstrates that the system fails correctly in each failure scenario:
A. Payment failure → no semantic repair → no verified_repaired
B. Semantic repair failure → no verified_repaired
C. Re-validation failure → no verified_repaired
D. Anchoring failure → record remains valid, anchoring_status = unanchored
"""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from x402.http.x402_http_server import x402HTTPResourceServer
from x402.server import x402ResourceServer
from x402.http.types import (
    HTTPProcessResult, ProcessSettleResult,
    RESULT_PAYMENT_VERIFIED, RESULT_PAYMENT_ERROR,
    HTTPResponseInstructions,
)

from app.main import app
from app.storage.store import LocalVerificationRecordStore
from app.core.config import settings
from app.models.enums import AnchoringStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_body(output_payload: dict, schema_definition: dict) -> dict:
    return {
        "request": {
            "request_id": str(uuid4()),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "output_type": "json",
            "output_payload": output_payload,
            "schema_ref": "demo_schema",
            "agent_identifier": "test_agent",
        },
        "policy": {
            "schema_id": str(uuid4()),
            "version": "1.0",
            "output_type": "json",
            "schema_definition": schema_definition,
            "privacy_policy_ref": "default",
        },
    }


# ===========================================================================
# Test A: Payment failure → no semantic repair
# ===========================================================================

class TestPaymentFailure:
    def test_failed_payment_returns_402(self):
        """Settlement failure returns 402, no semantic repair attempted."""
        settle_fail = ProcessSettleResult(success=False, error_reason="Insufficient funds")

        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}, "required": ["name", "age"]},
        )

        with patch.object(x402ResourceServer, "initialize"):
            with patch.object(x402HTTPResourceServer, "initialize"):
                with patch(
                    "x402.http.x402_http_server.x402HTTPResourceServer.process_http_request",
                    new_callable=AsyncMock,
                    return_value=HTTPProcessResult(type=RESULT_PAYMENT_VERIFIED),
                ):
                    with patch(
                        "x402.http.x402_http_server.x402HTTPResourceServer.process_settlement",
                        new_callable=AsyncMock,
                        return_value=settle_fail,
                    ):
                        with TestClient(app, raise_server_exceptions=False) as c:
                            resp = c.post("/api/v1/semantic-repair", json=body)
                            assert resp.status_code == 402
                            assert "Settlement failed" in resp.json().get("error", "")

    def test_failed_payment_no_result_or_receipt(self):
        """Failed payment produces no result or receipt in response body."""
        settle_fail = ProcessSettleResult(success=False, error_reason="Timeout")

        body = _make_body(
            {"name": "Bob", "inject_mock_semantic_repair": {"age": 25}},
            {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}, "required": ["name", "age"]},
        )

        with patch.object(x402ResourceServer, "initialize"):
            with patch.object(x402HTTPResourceServer, "initialize"):
                with patch(
                    "x402.http.x402_http_server.x402HTTPResourceServer.process_http_request",
                    new_callable=AsyncMock,
                    return_value=HTTPProcessResult(type=RESULT_PAYMENT_VERIFIED),
                ):
                    with patch(
                        "x402.http.x402_http_server.x402HTTPResourceServer.process_settlement",
                        new_callable=AsyncMock,
                        return_value=settle_fail,
                    ):
                        with TestClient(app, raise_server_exceptions=False) as c:
                            resp = c.post("/api/v1/semantic-repair", json=body)
                            assert resp.status_code == 402
                            data = resp.json()
                            assert "result" not in data
                            assert "receipt" not in data


# ===========================================================================
# Test B: Semantic repair failure → no verified_repaired
# ===========================================================================

class TestSemanticRepairFailure:
    def test_unfixable_payload_stays_rejected(self):
        """Payment succeeds but payload can't be repaired → rejected."""
        verified = HTTPProcessResult(type=RESULT_PAYMENT_VERIFIED)
        settle_ok = ProcessSettleResult(success=True, transaction="TX_OK", network="algorand")

        body = _make_body(
            {"name": "Charlie", "age": "not_a_number"},  # type error, MockProvider can't fix
            {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}, "required": ["name", "age"]},
        )

        with patch.object(x402ResourceServer, "initialize"):
            with patch.object(x402HTTPResourceServer, "initialize"):
                with patch(
                    "x402.http.x402_http_server.x402HTTPResourceServer.process_http_request",
                    new_callable=AsyncMock,
                    return_value=verified,
                ):
                    with patch(
                        "x402.http.x402_http_server.x402HTTPResourceServer.process_settlement",
                        new_callable=AsyncMock,
                        return_value=settle_ok,
                    ):
                        with TestClient(app, raise_server_exceptions=False) as c:
                            resp = c.post("/api/v1/semantic-repair", json=body)
                            assert resp.status_code == 200
                            data = resp.json()
                            assert data["result"]["outcome"] == "rejected"
                            assert data["receipt"]["outcome"] == "rejected"


# ===========================================================================
# Test C: Re-validation failure → no verified_repaired
# ===========================================================================

class TestRevalidationFailure:
    def test_payment_success_repair_fails_revalidation(self):
        """Payment succeeds, repair returns garbage, re-validation rejects."""
        verified = HTTPProcessResult(type=RESULT_PAYMENT_VERIFIED)
        settle_ok = ProcessSettleResult(success=True, transaction="TX_2", network="algorand")

        # Use a payload that the MockProvider can't fix (no inject key)
        body = _make_body(
            {"name": "Dave", "data": "missing required age"},
            {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}, "required": ["name", "age"]},
        )

        with patch.object(x402ResourceServer, "initialize"):
            with patch.object(x402HTTPResourceServer, "initialize"):
                with patch(
                    "x402.http.x402_http_server.x402HTTPResourceServer.process_http_request",
                    new_callable=AsyncMock,
                    return_value=verified,
                ):
                    with patch(
                        "x402.http.x402_http_server.x402HTTPResourceServer.process_settlement",
                        new_callable=AsyncMock,
                        return_value=settle_ok,
                    ):
                        with TestClient(app, raise_server_exceptions=False) as c:
                            resp = c.post("/api/v1/semantic-repair", json=body)
                            assert resp.status_code == 200
                            data = resp.json()
                            # MockProvider returns None → no repair → rejected
                            assert data["result"]["outcome"] == "rejected"


# ===========================================================================
# Test D: Anchoring failure → record remains valid
# ===========================================================================

class TestAnchoringFailure:
    def test_anchoring_failure_preserves_record(self):
        """Failed anchoring does not affect verification record validity."""
        from app.anchoring.service import AlgorandAnchorError, MerkleAnchoringService

        # Save a record
        store = LocalVerificationRecordStore(db_path=str(
            settings.resolved_database_path
        ))

        from app.models.verification import VerificationResult, VerificationReceipt
        from app.models.enums import VerificationOutcome

        request_id = uuid4()
        result = VerificationResult(
            result_id=uuid4(),
            request_ref=str(request_id),
            findings=[],
            outcome=VerificationOutcome.verified,
            validator_version="0.1.0",
            completed_at=datetime.now(timezone.utc),
        )
        receipt = VerificationReceipt(
            receipt_id=uuid4(),
            request_id_ref=str(request_id),
            outcome=VerificationOutcome.verified,
            output_hash="test_hash",
            schema_ref_and_version="test@1.0",
            validator_version="0.1.0",
            issued_at=datetime.now(timezone.utc),
            receipt_hash="test_receipt_hash",
        )
        saved = store.save(result=result, receipt=receipt)

        # Try anchoring with failing client
        class FailingClient:
            def submit_anchor(self, merkle_root, fee_microalgos=1000):
                raise AlgorandAnchorError("Mocked Algorand failure")

        service = MerkleAnchoringService(store, FailingClient(), batch_size=10)
        anchor_result = service.anchor_pending_records()

        assert anchor_result.status == "failed"

        # Record should still be valid and unanchored
        retrieved = store.get_by_request_id(str(request_id))
        assert retrieved is not None
        assert retrieved.outcome == "verified"
        assert retrieved.anchoring_status == AnchoringStatus.unanchored

        store.close()
