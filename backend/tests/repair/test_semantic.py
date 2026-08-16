from uuid import uuid4
from datetime import datetime, timezone
import pytest

from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding
from app.models.enums import OutputType, VerificationOutcome, ValidationStage, Severity
from app.repair.semantic import SemanticRepairEngine, MockSemanticProvider

@pytest.fixture
def base_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Alice"},
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

@pytest.fixture
def dummy_finding():
    return ValidationFinding(
        finding_id=uuid4(),
        stage=ValidationStage.schema,
        severity=Severity.blocking,
        description="missing age",
        repairable="semantic"
    )

def test_semantic_repair_mock_success(base_request, base_policy, dummy_finding):
    engine = SemanticRepairEngine(MockSemanticProvider())
    
    # Inject trigger for the mock provider
    base_request.output_payload["inject_mock_semantic_repair"] = {"age": 30}
    
    repaired, info = engine.attempt_repair(base_request, base_policy, [dummy_finding])
    
    assert info is not None
    assert info.repair_type == "semantic"
    assert info.semantic_repair_provider_ref == "MockSemanticProvider"
    assert "age" in repaired
    assert repaired["age"] == 30
    assert "inject_mock_semantic_repair" not in repaired

def test_semantic_repair_mock_failure(base_request, base_policy, dummy_finding):
    engine = SemanticRepairEngine(MockSemanticProvider())
    
    # Do NOT inject trigger, so mock fails
    repaired, info = engine.attempt_repair(base_request, base_policy, [dummy_finding])
    
    assert info is None
    assert repaired == base_request.output_payload

def test_semantic_repair_preserves_original(base_request, base_policy, dummy_finding):
    engine = SemanticRepairEngine(MockSemanticProvider())
    base_request.output_payload["inject_mock_semantic_repair"] = {"age": 30}
    
    repaired, info = engine.attempt_repair(base_request, base_policy, [dummy_finding])
    
    assert "inject_mock_semantic_repair" in base_request.output_payload # Original not mutated
    assert repaired is not base_request.output_payload
