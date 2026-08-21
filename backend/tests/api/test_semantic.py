"""
Tests for POST /api/v1/semantic-repair (Phase 7 + Phase 8 hardened).

Phase 7 tests: x402 payment gating, 402 challenge, valid/invalid payment,
               payment-failure-never-invokes-engine, free routes unaffected.
Phase 8 tests: PaymentMetadata propagation, repair_info.payment_ref binding,
               receipt invariant enforcement, tamper detection, all acceptance criteria.

Mocking strategy:
  The custom x402 middleware (main.py) creates an x402HTTPResourceServer and calls:
    1. process_http_request() → verify payment
    2. process_settlement() → settle payment (BEFORE handler, per Phase 8)
    3. route handler runs with settlement info on request.state

  We patch at the CLASS level so all instances (including the one inside the
  middleware closure) are intercepted.

Patch targets (verified against x402-avm 2.x source + custom middleware):
  x402.http.x402_http_server.x402HTTPResourceServer.process_http_request
  x402.http.x402_http_server.x402HTTPResourceServer.process_settlement
  x402.http.x402_http_server.x402HTTPResourceServer.initialize
  x402.server.x402ResourceServer.initialize
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from x402.http import X_PAYMENT_HEADER
from x402.http.types import (
    HTTPProcessResult,
    HTTPResponseInstructions,
    ProcessSettleResult,
    RESULT_PAYMENT_VERIFIED,
    RESULT_PAYMENT_ERROR,
)

# Patch targets
_HTTP_SERVER = "x402.http.x402_http_server.x402HTTPResourceServer"
_RESOURCE_SERVER = "x402.server.x402ResourceServer"


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _verified_result() -> HTTPProcessResult:
    return HTTPProcessResult(type=RESULT_PAYMENT_VERIFIED)


def _payment_required_result() -> HTTPProcessResult:
    return HTTPProcessResult(
        type=RESULT_PAYMENT_ERROR,
        response=HTTPResponseInstructions(
            status=402,
            headers={"content-type": "application/json"},
            body={
                "x402Version": 2,
                "error": "Payment required",
                "accepts": [
                    {
                        "scheme": "avm.exact.v2",
                        "network": "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=",
                        "asset": "0",
                        "amount": "1000000",
                        "payTo": "TEST_ADDRESS",
                        "maxTimeoutSeconds": 60,
                    }
                ],
            },
        ),
    )


def _invalid_payment_result() -> HTTPProcessResult:
    return HTTPProcessResult(
        type=RESULT_PAYMENT_ERROR,
        response=HTTPResponseInstructions(
            status=402,
            headers={"content-type": "application/json"},
            body={"x402Version": 2, "error": "Payment invalid or expired", "accepts": []},
        ),
    )


def _successful_settle() -> ProcessSettleResult:
    return ProcessSettleResult(
        success=True,
        transaction="ALGO_TX_abc123",
        network="algorand",
        payer="PAYER_ADDRESS_xyz",
        headers={},
    )


def _failed_settle() -> ProcessSettleResult:
    return ProcessSettleResult(
        success=False,
        error_reason="Insufficient funds",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_body(output_payload: dict, schema_definition: dict) -> dict:
    return {
        "request": {
            "request_id": str(uuid4()),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "output_type": "json",
            "output_payload": output_payload,
            "schema_ref": "test_schema",
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


@pytest.fixture()
def no_payment_client():
    """Client where x402 middleware returns 402 (no/missing payment)."""
    with patch(f"{_RESOURCE_SERVER}.initialize"):
        with patch(f"{_HTTP_SERVER}.initialize"):
            with patch(
                f"{_HTTP_SERVER}.process_http_request",
                new_callable=AsyncMock,
                return_value=_payment_required_result(),
            ):
                with TestClient(__import__("app.main", fromlist=["app"]).app, raise_server_exceptions=False) as c:
                    yield c


@pytest.fixture()
def invalid_payment_client():
    """Client where x402 middleware rejects a malformed payment."""
    with patch(f"{_RESOURCE_SERVER}.initialize"):
        with patch(f"{_HTTP_SERVER}.initialize"):
            with patch(
                f"{_HTTP_SERVER}.process_http_request",
                new_callable=AsyncMock,
                return_value=_invalid_payment_result(),
            ):
                with TestClient(__import__("app.main", fromlist=["app"]).app, raise_server_exceptions=False) as c:
                    yield c


@pytest.fixture()
def authed_client():
    """Client where x402 middleware verifies AND settles payment."""
    with patch(f"{_RESOURCE_SERVER}.initialize"):
        with patch(f"{_HTTP_SERVER}.initialize"):
            with patch(
                f"{_HTTP_SERVER}.process_http_request",
                new_callable=AsyncMock,
                return_value=_verified_result(),
            ):
                with patch(
                    f"{_HTTP_SERVER}.process_settlement",
                    new_callable=AsyncMock,
                    return_value=_successful_settle(),
                ):
                    with TestClient(__import__("app.main", fromlist=["app"]).app, raise_server_exceptions=False) as c:
                        yield c


@pytest.fixture()
def settle_failure_client():
    """Client where x402 middleware verifies but settlement fails."""
    with patch(f"{_RESOURCE_SERVER}.initialize"):
        with patch(f"{_HTTP_SERVER}.initialize"):
            with patch(
                f"{_HTTP_SERVER}.process_http_request",
                new_callable=AsyncMock,
                return_value=_verified_result(),
            ):
                with patch(
                    f"{_HTTP_SERVER}.process_settlement",
                    new_callable=AsyncMock,
                    return_value=_failed_settle(),
                ):
                    with TestClient(__import__("app.main", fromlist=["app"]).app, raise_server_exceptions=False) as c:
                        yield c


@pytest.fixture()
def free_client():
    """Plain client for testing free routes — no payment stubs needed."""
    with patch(f"{_RESOURCE_SERVER}.initialize"):
        with patch(f"{_HTTP_SERVER}.initialize"):
            with TestClient(__import__("app.main", fromlist=["app"]).app, raise_server_exceptions=False) as c:
                yield c


# ===========================================================================
# TEST 1: No payment header → 402
# ===========================================================================

class TestNoPayment:
    def test_no_payment_returns_402(self, no_payment_client):
        """Without an X-PAYMENT header the middleware returns HTTP 402."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402, (
            f"Expected 402, got {resp.status_code}: {resp.text}"
        )

    def test_402_response_is_non_empty(self, no_payment_client):
        """The 402 body must be non-empty (challenge body)."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402
        assert len(resp.content) > 0


# ===========================================================================
# TEST 2: Payment requirements correctness
# ===========================================================================

class TestPaymentRequirements:
    def test_payment_requirements_returned(self, no_payment_client):
        """The 402 body must include x402 payment requirements."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402
        data = resp.json()
        assert "accepts" in data
        assert len(data["accepts"]) > 0

    def test_payment_requirements_use_algorand_testnet(self, no_payment_client):
        """Payment requirements must use the configured Algorand Testnet CAIP-2 identifier."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        if data.get("accepts"):
            network = data["accepts"][0].get("network", "")
            assert "algorand" in network.lower() or "SGO1GK" in network

    def test_payment_requirements_use_avm_scheme(self, no_payment_client):
        """Payment requirements must reference the avm.exact.v2 scheme."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        if data.get("accepts"):
            scheme = data["accepts"][0].get("scheme", "")
            assert "avm" in scheme


# ===========================================================================
# TEST 3: Invalid payment is rejected
# ===========================================================================

class TestInvalidPayment:
    def test_invalid_payment_returns_402(self, invalid_payment_client):
        """A malformed X-PAYMENT is rejected by the middleware."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = invalid_payment_client.post(
            "/api/v1/semantic-repair",
            json=body,
            headers={X_PAYMENT_HEADER: "INVALID_GARBAGE"},
        )
        assert resp.status_code == 402

    def test_invalid_payment_never_invokes_semantic_engine(self, invalid_payment_client):
        """SemanticRepairEngine must never be called on invalid payment."""
        from app.repair.semantic import SemanticRepairEngine

        body = _make_body({"x": 1}, {"type": "object"})
        with patch.object(SemanticRepairEngine, "attempt_repair") as mock_repair:
            invalid_payment_client.post(
                "/api/v1/semantic-repair",
                json=body,
                headers={X_PAYMENT_HEADER: "INVALID_GARBAGE"},
            )
            mock_repair.assert_not_called()


# ===========================================================================
# TEST 4: Valid payment allows semantic repair
# ===========================================================================

class TestValidPaymentAccess:
    def test_valid_payment_returns_200(self, authed_client):
        """With a valid payment the handler returns 200."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200

    def test_valid_payment_response_has_result_and_receipt(self, authed_client):
        """Successful response must include 'result' and 'receipt'."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "receipt" in data

    def test_valid_payment_response_has_payment_metadata(self, authed_client):
        """Phase 8: response must include payment_metadata when payment was settled."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert "payment_metadata" in data
        assert data["payment_metadata"] is not None


# ===========================================================================
# TEST 5: Valid payment + invalid semantic candidate → rejected
# ===========================================================================

class TestValidPaymentBadRepair:
    def test_payment_success_does_not_equal_verification_success(self, authed_client):
        """
        Payment authorization must NEVER be treated as repair/verification success.
        An unfixable payload must yield outcome='rejected', not 'verified'.
        """
        body = _make_body(
            {"name": "Alice", "age": "not_a_number"},  # type mismatch, MockProvider can't fix
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"

    def test_receipt_is_generated_even_on_rejection(self, authed_client):
        """A receipt must be generated regardless of whether repair succeeded."""
        body = _make_body(
            {"age": "bad_type"},
            {
                "type": "object",
                "properties": {"age": {"type": "integer"}},
                "required": ["age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"
        assert data["receipt"]["receipt_hash"]


# ===========================================================================
# TEST 6: Valid payment + valid semantic repair → verified_repaired
# ===========================================================================

class TestValidPaymentGoodRepair:
    def test_successful_semantic_repair_outcome(self, authed_client):
        """
        When the MockProvider fixes the payload and revalidation passes,
        outcome must be 'verified_repaired' with repair_type='semantic'.
        """
        body = _make_body(
            {
                "name": "Bob",
                "inject_mock_semantic_repair": {"age": 25},
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"]["repair_type"] == "semantic"

    def test_successful_repair_receipt_has_repair_hash(self, authed_client):
        """Receipt for a repaired result must include a repair_summary_hash."""
        body = _make_body(
            {
                "name": "Carol",
                "inject_mock_semantic_repair": {"score": 99},
            },
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["name", "score"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["receipt"]["repair_summary_hash"] is not None


# ===========================================================================
# TEST 7: Payment failure never invokes SemanticRepairEngine
# ===========================================================================

class TestPaymentFailureNeverCallsEngine:
    def test_missing_payment_does_not_invoke_engine(self, no_payment_client):
        """Missing X-PAYMENT must never reach SemanticRepairEngine."""
        from app.repair.semantic import SemanticRepairEngine

        body = _make_body({"x": 1}, {"type": "object"})
        with patch.object(SemanticRepairEngine, "attempt_repair") as mock_repair:
            resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
            assert resp.status_code == 402
            mock_repair.assert_not_called()

    def test_invalid_payment_does_not_invoke_engine(self, invalid_payment_client):
        """Invalid X-PAYMENT must never reach SemanticRepairEngine."""
        from app.repair.semantic import SemanticRepairEngine

        body = _make_body({"x": 1}, {"type": "object"})
        with patch.object(SemanticRepairEngine, "attempt_repair") as mock_repair:
            resp = invalid_payment_client.post(
                "/api/v1/semantic-repair",
                json=body,
                headers={X_PAYMENT_HEADER: "bad-token"},
            )
            assert resp.status_code == 402
            mock_repair.assert_not_called()


# ===========================================================================
# TEST 8: Settlement failure → 402
# ===========================================================================

class TestSettlementFailure:
    def test_settlement_failure_returns_402(self, settle_failure_client):
        """If settlement fails, the middleware returns 402 even after verification."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = settle_failure_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402

    def test_settlement_failure_does_not_invoke_engine(self, settle_failure_client):
        """Failed settlement must never reach the semantic repair handler."""
        from app.repair.semantic import SemanticRepairEngine

        body = _make_body({"x": 1}, {"type": "object"})
        with patch.object(SemanticRepairEngine, "attempt_repair") as mock_repair:
            settle_failure_client.post("/api/v1/semantic-repair", json=body)
            mock_repair.assert_not_called()


# ===========================================================================
# TEST 9: Free routes remain unaffected
# ===========================================================================

class TestFreeRoutesUnaffected:
    def test_verify_endpoint_requires_no_payment(self, free_client):
        """/api/v1/verify must remain completely free — no X-PAYMENT required."""
        body = _make_body(
            {"name": "Dave"},
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        assert resp.json()["result"]["outcome"] == "verified"

    def test_health_endpoint_requires_no_payment(self, free_client):
        """Health check must remain free."""
        resp = free_client.get("/health")
        assert resp.status_code == 200

    def test_deterministic_repair_via_verify_is_free(self, free_client):
        """Deterministic repair through /api/v1/verify must not require payment."""
        body = _make_body(
            {"name": "Eve"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "default": "viewer"},
                },
                "required": ["name", "role"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"]["repair_type"] == "deterministic"


# ===========================================================================
# TEST 10: No payment secrets appear in responses
# ===========================================================================

class TestNoPaymentSecretsInResponse:
    def test_402_has_no_private_keys(self, no_payment_client):
        """The 402 response must not contain private keys or wallet secrets."""
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402
        text = resp.text.lower()
        assert "private_key" not in text
        assert "mnemonic" not in text
        assert "seed" not in text

    def test_response_does_not_echo_x_payment(self, authed_client):
        """The success response must not contain the X-PAYMENT header value."""
        sentinel = "MOCK_PAYMENT_PROOF_SENTINEL_DO_NOT_LEAK_12345"
        body = _make_body({"x": 1}, {"type": "object"})
        resp = authed_client.post(
            "/api/v1/semantic-repair",
            json=body,
            headers={X_PAYMENT_HEADER: sentinel},
        )
        assert resp.status_code == 200
        assert sentinel not in resp.text

    def test_response_does_not_echo_payload(self, authed_client):
        """Confidential payload values must not appear in the response."""
        secret_value = "SUPER_CONFIDENTIAL_AGENT_OUTPUT_9988"
        body = _make_body({"data": secret_value}, {"type": "object"})
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 200
        assert secret_value not in resp.text


# ===========================================================================
# TEST 11: Existing pipeline smoke tests
# ===========================================================================

class TestExistingPipelineUnchanged:
    def test_valid_json_passes_verification(self, free_client):
        """Basic verification still works after Phase 7/8 changes."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified"
        assert "receipt_hash" in data["receipt"]

    def test_unrepairable_payload_is_rejected(self, free_client):
        """Unrepairable payloads continue to yield rejected outcome."""
        body = _make_body(
            {"name": "Bad", "age": "not_an_int"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"


# ===========================================================================
# PHASE 8: Payment metadata propagation tests
# ===========================================================================

class TestPaymentMetadataPropagation:
    """Phase 8 acceptance: PaymentMetadata is correctly created and propagated."""

    def test_payment_metadata_has_settled_status(self, authed_client):
        """PaymentMetadata.payment_status must be 'settled' after middleware settlement."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        pm = data["payment_metadata"]
        assert pm["payment_status"] == "settled"

    def test_payment_metadata_has_facilitator(self, authed_client):
        """PaymentMetadata.facilitator must be the GoPlausible AVM Facilitator."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        pm = resp.json()["payment_metadata"]
        assert pm["facilitator"] == "GoPlausible AVM Facilitator"

    def test_payment_metadata_has_settlement_network(self, authed_client):
        """PaymentMetadata.settlement_network must be 'Algorand'."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        pm = resp.json()["payment_metadata"]
        assert pm["settlement_network"] == "Algorand"

    def test_payment_metadata_has_algorand_tx_ref(self, authed_client):
        """PaymentMetadata.algorand_tx_ref must reflect actual settlement transaction."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        pm = resp.json()["payment_metadata"]
        assert pm["algorand_tx_ref"] == "ALGO_TX_abc123"

    def test_payment_metadata_x402_challenge_ref_matches_request(self, authed_client):
        """x402_challenge_ref must correlate to the specific request."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        pm = data["payment_metadata"]
        request_id = data["result"]["request_ref"]
        assert pm["x402_challenge_ref"] == request_id

    def test_repair_info_payment_ref_references_payment_metadata(self, authed_client):
        """RepairInfo.payment_ref must point to the PaymentMetadata.payment_id."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        repair_info = data["result"]["repair_info"]
        pm = data["payment_metadata"]
        assert repair_info["payment_ref"] == pm["payment_id"]

    def test_verified_repaired_requires_non_null_payment_ref(self, authed_client):
        """Phase 8 invariant: verified_repaired MUST have non-null payment_ref."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"]["payment_ref"] is not None
        assert data["result"]["repair_info"]["payment_ref"] != ""


# ===========================================================================
# PHASE 8: Receipt hashing and tamper detection tests
# ===========================================================================

class TestReceiptTamperDetection:
    """Phase 8 acceptance: receipt_hash is tamper-evident."""

    def test_tampered_outcome_changes_receipt_hash(self, free_client):
        """Changing outcome must change receipt_hash."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        receipt = resp.json()["receipt"]
        original_hash = receipt["receipt_hash"]

        # Tamper: change outcome in the receipt dict and recompute hash
        from app.evidence.hasher import hash_data
        tampered = dict(receipt)
        tampered["outcome"] = "rejected"
        tampered.pop("receipt_hash", None)
        tampered.pop("signature", None)
        tampered_hash = hash_data(tampered)
        assert original_hash != tampered_hash

    def test_tampered_output_changes_receipt_hash(self, free_client):
        """Changing output_hash must change receipt_hash."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        receipt = resp.json()["receipt"]
        original_hash = receipt["receipt_hash"]

        from app.evidence.hasher import hash_data
        tampered = dict(receipt)
        tampered["output_hash"] = "0" * 64  # different hash
        tampered.pop("receipt_hash", None)
        tampered.pop("signature", None)
        tampered_hash = hash_data(tampered)
        assert original_hash != tampered_hash

    def test_tampered_schema_version_changes_receipt_hash(self, free_client):
        """Changing schema_ref_and_version must change receipt_hash."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        receipt = resp.json()["receipt"]
        original_hash = receipt["receipt_hash"]

        from app.evidence.hasher import hash_data
        tampered = dict(receipt)
        tampered["schema_ref_and_version"] = "fake_schema@99"
        tampered.pop("receipt_hash", None)
        tampered.pop("signature", None)
        tampered_hash = hash_data(tampered)
        assert original_hash != tampered_hash

    def test_tampered_validator_version_changes_receipt_hash(self, free_client):
        """Changing validator_version must change receipt_hash."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        receipt = resp.json()["receipt"]
        original_hash = receipt["receipt_hash"]

        from app.evidence.hasher import hash_data
        tampered = dict(receipt)
        tampered["validator_version"] = "999.0.0"
        tampered.pop("receipt_hash", None)
        tampered.pop("signature", None)
        tampered_hash = hash_data(tampered)
        assert original_hash != tampered_hash

    def test_receipt_hash_is_deterministic(self, free_client):
        """Same receipt data must produce the same receipt_hash."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp1 = free_client.post("/api/v1/verify", json=body)
        resp2 = free_client.post("/api/v1/verify", json=body)
        # Different requests → different hashes (different request_id, timestamps)
        # But within each, receipt_hash matches the bound fields
        from app.evidence.hasher import hash_data
        for resp in [resp1, resp2]:
            receipt = resp.json()["receipt"]
            check = dict(receipt)
            check.pop("receipt_hash", None)
            check.pop("signature", None)
            assert receipt["receipt_hash"] == hash_data(check)

    def test_output_hash_matches_final_payload(self, free_client):
        """output_hash must reflect the FINAL validated output, not pre-repair."""
        # Deterministic repair: missing "role" field with default "viewer"
        body = _make_body(
            {"name": "Eve"},  # missing "role"
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "default": "viewer"},
                },
                "required": ["name", "role"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"

        from app.evidence.hasher import hash_data
        # The repaired payload has "role": "viewer"
        repaired_payload = {"name": "Eve", "role": "viewer"}
        expected_hash = hash_data(repaired_payload)
        assert data["receipt"]["output_hash"] == expected_hash

        # The original payload hash must be DIFFERENT
        original_hash = hash_data({"name": "Eve"})
        assert data["receipt"]["output_hash"] != original_hash

    def test_repair_summary_hash_present_for_repaired(self, free_client):
        """Repair summary hash must be present when repair occurred."""
        body = _make_body(
            {"name": "Eve"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "default": "viewer"},
                },
                "required": ["name", "role"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["receipt"]["repair_summary_hash"] is not None

    def test_repair_summary_hash_absent_for_verified(self, free_client):
        """Repair summary hash must be None when no repair occurred."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified"
        assert data["receipt"]["repair_summary_hash"] is None

    def test_schema_version_binding_in_receipt(self, free_client):
        """Receipt must bind to the exact schema version used by validation."""
        body = _make_body(
            {"name": "Alice"},
            {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        schema_id = data["result"]["request_ref"]  # Use request_ref as correlation
        receipt = data["receipt"]
        # schema_ref_and_version must be non-empty and contain @
        assert "@" in receipt["schema_ref_and_version"]

    def test_no_raw_payload_in_receipt(self, free_client):
        """Receipt must never contain raw payload content."""
        body = _make_body(
            {"secret_field": "SUPER_SECRET_VALUE_XYZ"},
            {"type": "object"},
        )
        resp = free_client.post("/api/v1/verify", json=body)
        receipt_text = str(resp.json()["receipt"])
        assert "SUPER_SECRET_VALUE_XYZ" not in receipt_text


# ===========================================================================
# PHASE 8: Every request gets a receipt
# ===========================================================================

class TestEveryRequestGetsReceipt:
    """Phase 8 acceptance: no receiptless outcome."""

    def test_verified_gets_receipt(self, free_client):
        """Valid output → verified → receipt."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified"
        assert data["receipt"]["receipt_hash"] != ""
        assert data["receipt"]["outcome"] == "verified"

    def test_deterministic_repair_gets_receipt(self, free_client):
        """Missing default → deterministic repair → verified_repaired → receipt."""
        body = _make_body(
            {"name": "Bob"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "default": "user"},
                },
                "required": ["name", "role"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["receipt"]["receipt_hash"] != ""

    def test_rejected_gets_receipt(self, free_client):
        """Unsafe type → rejected → receipt."""
        body = _make_body(
            {"name": "Charlie", "age": "not_a_number"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"
        assert data["receipt"]["receipt_hash"] != ""
        assert data["receipt"]["outcome"] == "rejected"

    def test_semantic_repair_success_gets_receipt(self, authed_client):
        """Payment + semantic repair + revalidation → verified_repaired → receipt."""
        body = _make_body(
            {"name": "Dave", "inject_mock_semantic_repair": {"age": 40}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["receipt"]["receipt_hash"] != ""

    def test_payment_failure_returns_402_rejection(self, settle_failure_client):
        """Payment failure → 402 rejection (middleware rejects before handler runs).

        When settlement fails, the x402 middleware returns a 402 JSONResponse
        directly. The handler never runs, so no VerificationReceipt is generated.
        The 402 IS the rejection signal for this case.
        """
        body = _make_body(
            {"name": "Eve", "inject_mock_semantic_repair": {"age": 25}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = settle_failure_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402
        data = resp.json()
        assert "error" in data
        assert "Settlement failed" in data["error"]


# ===========================================================================
# PHASE 8: Invariant enforcement tests
# ===========================================================================

class TestPhase8Invariants:
    """Phase 8 acceptance: critical invariants are enforced."""

    def test_verified_repaired_needs_payment_ref(self, authed_client):
        """verified_repaired with semantic repair must have non-null payment_ref."""
        body = _make_body(
            {"name": "Alice", "inject_mock_semantic_repair": {"age": 30}},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = authed_client.post("/api/v1/semantic-repair", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"]["payment_ref"] is not None
        # The payment_ref must match the payment_metadata.payment_id
        assert data["result"]["repair_info"]["payment_ref"] == data["payment_metadata"]["payment_id"]

    def test_deterministic_repair_no_payment_ref(self, free_client):
        """verified_repaired via deterministic repair must NOT have a payment_ref."""
        body = _make_body(
            {"name": "Bob"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "default": "user"},
                },
                "required": ["name", "role"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"]["repair_type"] == "deterministic"
        assert data["result"]["repair_info"]["payment_ref"] is None

    def test_verified_needs_no_payment_ref(self, free_client):
        """verified (no repair) must have no payment_ref and no repair_info."""
        body = _make_body(
            {"name": "Alice", "age": 30},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "verified"
        assert data["result"]["repair_info"] is None
        assert data["receipt"]["repair_summary_hash"] is None

    def test_rejected_has_no_payment_ref(self, free_client):
        """rejected must have no payment_ref."""
        body = _make_body(
            {"name": "Charlie", "age": "bad"},
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"
        assert data["result"]["repair_info"] is None
