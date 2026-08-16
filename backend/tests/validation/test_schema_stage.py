from uuid import uuid4
from datetime import datetime, timezone
import pytest

from app.models.verification import VerificationRequest, SchemaPolicy
from app.models.enums import OutputType, ValidationStage, Severity
from app.validation.stages.schema import SchemaValidationStage

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

def test_schema_validation_valid(base_request, base_policy):
    stage = SchemaValidationStage()
    findings = stage.validate(base_request, base_policy)
    assert len(findings) == 0

def test_schema_validation_missing_field(base_request, base_policy):
    base_request.output_payload = {"name": "Alice"}
    stage = SchemaValidationStage()
    findings = stage.validate(base_request, base_policy)
    assert len(findings) == 1
    assert findings[0].severity == Severity.blocking
    assert "required property" in findings[0].description.lower()

def test_schema_validation_type_error(base_request, base_policy):
    base_request.output_payload = {"name": "Alice", "age": "thirty"}
    stage = SchemaValidationStage()
    findings = stage.validate(base_request, base_policy)
    assert len(findings) == 1
    assert findings[0].stage == ValidationStage.type
    assert findings[0].severity == Severity.blocking
    assert findings[0].field_path == "age"

def test_schema_validation_invalid_schema(base_request, base_policy):
    base_policy.schema_definition = {"type": "invalid_type"}
    stage = SchemaValidationStage()
    findings = stage.validate(base_request, base_policy)
    assert len(findings) == 1
    assert findings[0].stage == ValidationStage.schema
    assert findings[0].severity == Severity.blocking
    assert "Invalid schema" in findings[0].description
