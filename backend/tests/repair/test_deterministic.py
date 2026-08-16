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
        output_payload={"name": "Bob", "age": 25}, # missing role
        schema_ref="user_schema",
        agent_identifier="agent1"
    )

@pytest.fixture
def type_error_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Charlie", "role": "user", "age": "thirty"}, # age is string
        schema_ref="user_schema",
        agent_identifier="agent1"
    )

def test_valid_input_no_repair(verification_engine, repair_engine, valid_request, base_policy):
    # Validate
    result = verification_engine.verify_request(valid_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.verified
    
    # Attempt repair
    repaired_payload, repair_info = repair_engine.attempt_repair(valid_request, base_policy, result.findings)
    
    assert repair_info is None
    assert repaired_payload == valid_request.output_payload

def test_successful_default_injection(verification_engine, repair_engine, missing_default_request, base_policy):
    # Validate
    result = verification_engine.verify_request(missing_default_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected
    
    # Attempt repair
    repaired_payload, repair_info = repair_engine.attempt_repair(missing_default_request, base_policy, result.findings)
    
    assert repair_info is not None
    assert repair_info.pre_repair_output_hash != repair_info.post_repair_output_hash
    assert repaired_payload["role"] == "user"
    assert "role" not in missing_default_request.output_payload # Original not mutated
    
    # Revalidate
    repaired_request = missing_default_request.model_copy()
    repaired_request.output_payload = repaired_payload
    new_result = verification_engine.verify_request(repaired_request, base_policy, "1.0.0")
    assert new_result.outcome == VerificationOutcome.verified

def test_unsupported_repair_remains_unchanged(verification_engine, repair_engine, type_error_request, base_policy):
    # Validate
    result = verification_engine.verify_request(type_error_request, base_policy, "1.0.0")
    assert result.outcome == VerificationOutcome.rejected
    
    # Attempt repair (should not fix type errors)
    repaired_payload, repair_info = repair_engine.attempt_repair(type_error_request, base_policy, result.findings)
    
    assert repair_info is None
    assert repaired_payload == type_error_request.output_payload
    
    # Revalidate confirms it is still broken
    repaired_request = type_error_request.model_copy()
    repaired_request.output_payload = repaired_payload
    new_result = verification_engine.verify_request(repaired_request, base_policy, "1.0.0")
    assert new_result.outcome == VerificationOutcome.rejected

def test_repair_idempotency(verification_engine, repair_engine, missing_default_request, base_policy):
    result = verification_engine.verify_request(missing_default_request, base_policy, "1.0.0")
    
    repaired_payload_1, repair_info_1 = repair_engine.attempt_repair(missing_default_request, base_policy, result.findings)
    
    # Mocking a request with the already repaired payload
    repaired_req_2 = missing_default_request.model_copy()
    repaired_req_2.output_payload = repaired_payload_1
    result_2 = verification_engine.verify_request(repaired_req_2, base_policy, "1.0.0")
    
    repaired_payload_2, repair_info_2 = repair_engine.attempt_repair(repaired_req_2, base_policy, result_2.findings)
    
    assert repair_info_2 is None
    assert repaired_payload_2 == repaired_payload_1
