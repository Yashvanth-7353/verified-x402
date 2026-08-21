import json
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _make_payload(output_payload, schema_definition, required=None):
    """Helper to build a valid VerifyPayloadRequest body."""
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


class TestVerifyEndpointValid:
    def test_valid_request(self, client):
        body = _make_payload(
            output_payload={"name": "Alice", "age": 30},
            schema_definition={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified"
        assert "receipt" in data
        assert data["receipt"]["outcome"] == "verified"
        assert "output_hash" in data["receipt"]
        assert "receipt_hash" in data["receipt"]

    def test_response_does_not_echo_payload(self, client):
        """Confidential payload must NOT appear in the response."""
        body = _make_payload(
            output_payload={"secret_field": "SUPER_SECRET_VALUE_12345"},
            schema_definition={"type": "object"},
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        resp_text = resp.text
        assert "SUPER_SECRET_VALUE_12345" not in resp_text


class TestVerifyEndpointRepair:
    def test_repairable_request(self, client):
        body = _make_payload(
            output_payload={"name": "Bob"},
            schema_definition={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "default": "user"},
                },
                "required": ["name", "role"],
            },
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"] is not None
        assert data["result"]["repair_info"]["repair_type"] == "deterministic"
        assert data["receipt"]["repair_summary_hash"] is not None

    def test_semantic_repairable_request(self, client):
        body = _make_payload(
            output_payload={
                "name": "Bob",
                "inject_mock_semantic_repair": {"age": 25}
            },
            schema_definition={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "verified_repaired"
        assert data["result"]["repair_info"] is not None
        assert data["result"]["repair_info"]["repair_type"] == "semantic"
        assert data["receipt"]["repair_summary_hash"] is not None


class TestVerifyEndpointRejection:
    def test_unrepairable_request(self, client):
        body = _make_payload(
            output_payload={"name": "Charlie", "age": "not_a_number"},
            schema_definition={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"
        assert data["result"]["rejection_reasons"] is not None
        assert len(data["result"]["rejection_reasons"]) > 0


class TestVerifyEndpointErrors:
    def test_malformed_request(self, client):
        resp = client.post("/api/v1/verify", json={"garbage": True})
        assert resp.status_code == 422

    def test_invalid_schema_definition(self, client):
        body = _make_payload(
            output_payload={"name": "Alice"},
            schema_definition={"type": "invalid_type"},
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["outcome"] == "rejected"

    def test_error_does_not_leak_payload(self, client):
        """Even on errors, confidential data must not leak."""
        body = _make_payload(
            output_payload={"secret": "MY_API_KEY_999"},
            schema_definition={
                "type": "object",
                "properties": {"secret": {"type": "integer"}},
                "required": ["secret"],
            },
        )
        resp = client.post("/api/v1/verify", json=body)
        resp_text = resp.text
        assert "MY_API_KEY_999" not in resp_text


class TestVerifyEndpointReceipt:
    def test_receipt_generated_server_side(self, client):
        body = _make_payload(
            output_payload={"x": 1},
            schema_definition={"type": "object"},
        )
        resp = client.post("/api/v1/verify", json=body)
        assert resp.status_code == 200
        data = resp.json()
        receipt = data["receipt"]
        assert receipt["receipt_hash"] != ""
        # Phase 12: signature may be present (if signing key configured) or None
        if receipt["signature"] is not None:
            assert receipt["signature_algorithm"] == "Ed25519"
            assert receipt["signing_key_id"] is not None
