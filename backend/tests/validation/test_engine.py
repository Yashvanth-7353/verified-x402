from uuid import uuid4
from datetime import datetime, timezone
import pytest

from app.models.verification import VerificationRequest, SchemaPolicy
from app.models.enums import OutputType, VerificationOutcome
from app.validation.engine import VerificationEngine

@pytest.fixture
def engine():
    return VerificationEngine()

@pytest.fixture
def base_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Alice", "age": 30},
        schema_ref="user_schema",
        agent_identifier="agent1"
    )

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
                "age": {"type": "integer"}
            },
            "required": ["name", "age"]
        },
        privacy_policy_ref="default"
    )

def test_engine_valid_request(engine, base_request, base_policy):
    result = engine.verify_request(base_request, base_policy, "1.0.0")
    # Syntax, SqlSafety, and Privacy stubs each produce an info finding
    assert len(result.findings) == 3 
    assert result.outcome == VerificationOutcome.verified
    assert result.rejection_reasons is None

def test_engine_invalid_request(engine, base_request, base_policy):
    base_request.output_payload = {"name": "Alice"} # missing age
    result = engine.verify_request(base_request, base_policy, "1.0.0")
    
    assert result.outcome == VerificationOutcome.rejected
    # 1 blocking from schema, 3 info from stubs
    assert len(result.findings) == 4
    assert result.rejection_reasons is not None
    assert len(result.rejection_reasons) == 1
    assert "required property" in result.rejection_reasons[0].lower()
