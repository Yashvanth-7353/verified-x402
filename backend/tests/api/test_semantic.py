"""
Tests for POST /api/v1/semantic-repair (Phase 7 — x402 gated).

Mocking strategy:
  The x402 middleware creates an x402HTTPResourceServer internally inside
  payment_middleware(). That server's process_http_request() coroutine is
  the authoritative gate. We patch it at its class level so all instances
  (including the one buried inside the middleware closure) are intercepted.

  We also patch x402ResourceServer.initialize() so that no real network call
  to the GoPlausible facilitator is made during tests.

Patch targets (verified against x402-avm 2.0.2 source):
  x402.http.x402_http_server.x402HTTPResourceServer.process_http_request
  x402.server.x402ResourceServer.initialize
"""
from unittest.mock import AsyncMock, MagicMock, patch
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

# Patch targets verified against installed package source
_HTTP_SERVER_PROCESS = (
    "x402.http.x402_http_server.x402HTTPResourceServer.process_http_request"
)
_RESOURCE_SERVER_INIT = "x402.server.x402ResourceServer.initialize"


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
    from x402.http.x402_http_server import x402HTTPResourceServer
    from x402.server import x402ResourceServer
    from app.main import app

    with patch.object(x402ResourceServer, "initialize"):
        with patch.object(
            x402HTTPResourceServer,
            "process_http_request",
            new_callable=AsyncMock,
            return_value=_payment_required_result(),
        ):
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c


@pytest.fixture()
def invalid_payment_client():
    """Client where x402 middleware rejects a malformed payment."""
    from x402.http.x402_http_server import x402HTTPResourceServer
    from x402.server import x402ResourceServer
    from app.main import app

    with patch.object(x402ResourceServer, "initialize"):
        with patch.object(
            x402HTTPResourceServer,
            "process_http_request",
            new_callable=AsyncMock,
            return_value=_invalid_payment_result(),
        ):
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c


@pytest.fixture()
def authed_client():
    """Client where x402 middleware allows the request through (payment verified)."""
    from x402.http.x402_http_server import x402HTTPResourceServer
    from x402.server import x402ResourceServer
    from app.main import app

    with patch.object(x402ResourceServer, "initialize"):
        with patch.object(
            x402HTTPResourceServer,
            "process_http_request",
            new_callable=AsyncMock,
            return_value=_verified_result(),
        ):
            with patch.object(
                x402HTTPResourceServer,
                "process_settlement",
                new_callable=AsyncMock,
                return_value=ProcessSettleResult(success=True, headers={}),
            ):
                with TestClient(app, raise_server_exceptions=False) as c:
                    yield c


@pytest.fixture()
def free_client():
    """Plain client for testing free routes — no payment stubs needed."""
    from x402.server import x402ResourceServer
    from app.main import app

    # Stub initialize so the facilitator is never contacted on free routes
    with patch.object(x402ResourceServer, "initialize"):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# Test 1: No payment header → 402
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 2: Correct payment requirements are returned
# ---------------------------------------------------------------------------

class TestPaymentRequirements:
    def test_payment_requirements_returned(self, no_payment_client):
        """
        The 402 body must include x402 payment requirements.
        """
        body = _make_body({"x": 1}, {"type": "object"})
        resp = no_payment_client.post("/api/v1/semantic-repair", json=body)
        assert resp.status_code == 402
        data = resp.json()
        assert "accepts" in data
        assert len(data["accepts"]) > 0

    def test_payment_requirements_use_algorand_testnet(self, no_payment_client):
        """
        Payment requirements must use the configured Algorand Testnet CAIP-2 identifier.
        """
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


# ---------------------------------------------------------------------------
# Test 3: Invalid payment is rejected
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 4: Mocked valid payment allows semantic repair invocation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 5: Valid payment + invalid semantic candidate → rejected
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 6: Valid payment + valid semantic repair → verified_repaired
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 7: Payment failure never invokes SemanticRepairEngine
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 8: Existing free /api/v1/verify remains free
# ---------------------------------------------------------------------------

class TestFreeRoutesUnaffected:
    def test_verify_endpoint_requires_no_payment(self, free_client):
        """
        /api/v1/verify must remain completely free — no X-PAYMENT required.
        """
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
        """
        Deterministic repair through /api/v1/verify must not require payment.
        """
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


# ---------------------------------------------------------------------------
# Test 9: Deterministic repair via /verify is free (explicit)
# ---------------------------------------------------------------------------

class TestDeterministicRepairFree:
    def test_deterministic_repair_is_free(self, free_client):
        """Deterministic repair (no semantic/payment) remains free."""
        body = _make_body(
            {"val": 1},
            {
                "type": "object",
                "properties": {
                    "val": {"type": "integer"},
                    "label": {"type": "string", "default": "ok"},
                },
                "required": ["val", "label"],
            },
        )
        resp = free_client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"


# ---------------------------------------------------------------------------
# Test 10: No payment secrets appear in responses
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 11: Existing Phase 0-6 tests — smoke run on verify endpoint
# ---------------------------------------------------------------------------

class TestExistingPipelineUnchanged:
    def test_valid_json_passes_verification(self, free_client):
        """Basic verification still works after Phase 7 changes."""
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
