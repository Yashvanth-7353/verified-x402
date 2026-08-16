from uuid import uuid4
from datetime import datetime, timezone
import pytest

from app.models.verification import VerificationRequest, SchemaPolicy
from app.models.enums import OutputType, ValidationStage, Severity
from app.validation.stages.stubs import SyntaxValidationStage, SqlSafetyValidationStage, PrivacyValidationStage

@pytest.fixture
def dummy_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={},
        schema_ref="ref",
        agent_identifier="agent1"
    )

@pytest.fixture
def dummy_policy():
    return SchemaPolicy(
        schema_id=uuid4(),
        version="1.0",
        output_type=OutputType.json,
        schema_definition={},
        privacy_policy_ref="default"
    )

def test_syntax_stage(dummy_request, dummy_policy):
    stage = SyntaxValidationStage()
    findings = stage.validate(dummy_request, dummy_policy)
    assert len(findings) == 1
    assert findings[0].stage == ValidationStage.syntax
    assert findings[0].severity == Severity.info

def test_sql_safety_stage(dummy_request, dummy_policy):
    stage = SqlSafetyValidationStage()
    findings = stage.validate(dummy_request, dummy_policy)
    assert len(findings) == 1
    assert findings[0].stage == ValidationStage.sql_safety
    assert findings[0].severity == Severity.info

def test_privacy_stage(dummy_request, dummy_policy):
    stage = PrivacyValidationStage()
    findings = stage.validate(dummy_request, dummy_policy)
    assert len(findings) == 1
    assert findings[0].stage == ValidationStage.privacy
    assert findings[0].severity == Severity.info
