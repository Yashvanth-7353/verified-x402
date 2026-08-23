from uuid import uuid4
from datetime import datetime, timezone
import pytest

from app.models.verification import VerificationRequest, SchemaPolicy
from app.models.enums import OutputType, VerificationOutcome
from app.validation.engine import VerificationEngine
from app.repair.deterministic import DeterministicRepairEngine


@pytest.fixture
def verification_engine():
    return VerificationEngine()


@pytest.fixture
def repair_engine():
    return DeterministicRepairEngine()


@pytest.fixture
def base_policy():
    return SchemaPolicy(
        schema_id=uuid4(),
        version="1.0",
        output_type=OutputType.json,
        schema_definition={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string", "default": "user"},
                "age": {"type": "integer"}
            },
            "required": ["name", "role", "age"]
        },
        privacy_policy_ref="default"
    )


@pytest.fixture
def valid_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Alice", "role": "admin", "age": 30},
        schema_ref="user_schema",
        agent_identifier="agent1"
    )


@pytest.fixture
def missing_default_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Bob", "age": 25},  # missing role
        schema_ref="user_schema",
        agent_identifier="agent1"
    )


@pytest.fixture
def type_error_request():
    """age is a non-numeric string — cannot be deterministically repaired."""
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Charlie", "role": "user", "age": "thirty"},
        schema_ref="user_schema",
        agent_identifier="agent1"
    )


@pytest.fixture
def parseable_int_request():
    """age is a numeric string that can be safely coerced to integer."""
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Dave", "role": "user", "age": "25"},
        schema_ref="user_schema",
        agent_identifier="agent1"
    )


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------

def test_valid_input_no_repair(verification_engine, repair_engine, valid_request, base_policy):
    result = verification_engine.verify_request(valid_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.verified

    repaired_payload, repair_info = repair_engine.attempt_repair(
        valid_request, base_policy, result.findings
    )
    assert repair_info is None
    assert repaired_payload == valid_request.output_payload


def test_successful_default_injection(verification_engine, repair_engine, missing_default_request, base_policy):
    """Missing field with schema default → deterministic repair fills it."""
    result = verification_engine.verify_request(missing_default_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected

    repaired_payload, repair_info = repair_engine.attempt_repair(
        missing_default_request, base_policy, result.findings
    )

    assert repair_info is not None
    assert repair_info.pre_repair_output_hash != repair_info.post_repair_output_hash
    assert repaired_payload["role"] == "user"
    assert "role" not in missing_default_request.output_payload  # Original not mutated

    # Re-validate
    repaired_request = missing_default_request.model_copy()
    repaired_request.output_payload = repaired_payload
    new_result = verification_engine.verify_request(repaired_request, base_policy, "1.0.0")
    assert new_result.outcome == VerificationOutcome.verified


def test_non_numeric_string_not_repaired(verification_engine, repair_engine, type_error_request, base_policy):
    """'thirty' is not a valid integer — deterministic repair must NOT touch it."""
    result = verification_engine.verify_request(type_error_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected

    repaired_payload, repair_info = repair_engine.attempt_repair(
        type_error_request, base_policy, result.findings
    )

    assert repair_info is None
    assert repaired_payload == type_error_request.output_payload

    repaired_request = type_error_request.model_copy()
    repaired_request.output_payload = repaired_payload
    new_result = verification_engine.verify_request(repaired_request, base_policy, "1.0.0")
    assert new_result.outcome == VerificationOutcome.rejected


def test_string_integer_coercion(verification_engine, repair_engine, parseable_int_request, base_policy):
    """Case A: '25' → 25 when schema expects integer."""
    result = verification_engine.verify_request(parseable_int_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected  # age='25' fails integer check

    repaired_payload, repair_info = repair_engine.attempt_repair(
        parseable_int_request, base_policy, result.findings
    )

    assert repair_info is not None
    assert repaired_payload["age"] == 25
    assert isinstance(repaired_payload["age"], int)
    assert repair_info.pre_repair_output_hash != repair_info.post_repair_output_hash

    # Re-validate
    repaired_request = parseable_int_request.model_copy()
    repaired_request.output_payload = repaired_payload
    new_result = verification_engine.verify_request(repaired_request, base_policy, "1.0.0")
    assert new_result.outcome == VerificationOutcome.verified


def test_ambiguous_string_not_coerced(verification_engine, repair_engine, base_policy):
    """'480 USD' must NOT become 480 — requires interpretation, not deterministic."""
    request = VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Eve", "role": "admin", "age": "480 USD"},
        schema_ref="user_schema",
        agent_identifier="agent1"
    )
    result = verification_engine.verify_request(request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected

    repaired_payload, repair_info = repair_engine.attempt_repair(
        request, base_policy, result.findings
    )

    # Must NOT be coerced
    assert repair_info is None
    assert repaired_payload["age"] == "480 USD"


def test_boolean_coercion(verification_engine, repair_engine, base_policy):
    """'true' (string) → True (bool) when schema expects boolean."""
    policy = SchemaPolicy(
        schema_id=uuid4(),
        version="1.0",
        output_type=OutputType.json,
        schema_definition={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "active": {"type": "boolean"}
            },
            "required": ["name", "active"]
        },
        privacy_policy_ref="default"
    )
    request = VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Frank", "active": "true"},
        schema_ref="test_schema",
        agent_identifier="agent1"
    )

    result = verification_engine.verify_request(request, policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected

    repaired_payload, repair_info = repair_engine.attempt_repair(
        request, policy, result.findings
    )

    assert repair_info is not None
    assert repaired_payload["active"] is True
    assert isinstance(repaired_payload["active"], bool)

    repaired_request = request.model_copy()
    repaired_request.output_payload = repaired_payload
    new_result = verification_engine.verify_request(repaired_request, policy, "1.0.0")
    assert new_result.outcome == VerificationOutcome.verified


def test_repair_idempotency(verification_engine, repair_engine, missing_default_request, base_policy):
    """Running repair twice on an already-repaired payload is a no-op."""
    result = verification_engine.verify_request(missing_default_request, base_policy, "1.0.0")

    repaired_payload_1, _ = repair_engine.attempt_repair(
        missing_default_request, base_policy, result.findings
    )

    repaired_req_2 = missing_default_request.model_copy()
    repaired_req_2.output_payload = repaired_payload_1
    result_2 = verification_engine.verify_request(repaired_req_2, base_policy, "1.0.0")

    repaired_payload_2, repair_info_2 = repair_engine.attempt_repair(
        repaired_req_2, base_policy, result_2.findings
    )

    assert repair_info_2 is None
    assert repaired_payload_2 == repaired_payload_1
