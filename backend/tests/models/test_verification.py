import json
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding, RepairInfo, VerificationResult, VerificationReceipt
from app.models.enums import OutputType, ValidationStage, Severity, Repairability, RepairType, VerificationOutcome

def test_verification_request_valid():
    req = VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"foo": "bar"},
        schema_ref="schema_1",
        agent_identifier="agent_x"
    )
    assert req.output_type == OutputType.json
    assert req.privacy_class_hint is None
    assert isinstance(req.output_payload, dict)

def test_verification_request_invalid():
    with pytest.raises(ValidationError):
        VerificationRequest(
            request_id=uuid4(),
            submitted_at="not-a-date",
            output_type=OutputType.json,
            output_payload={"foo": "bar"},
            schema_ref="schema_1",
            agent_identifier="agent_x"
        )

def test_verification_receipt_serialization():
    receipt = VerificationReceipt(
        receipt_id=uuid4(),
        request_id_ref="req_1",
        outcome=VerificationOutcome.verified,
        output_hash="abcdef",
        schema_ref_and_version="schema_1@v1",
        validator_version="1.0.0",
        issued_at=datetime.now(timezone.utc),
        receipt_hash="123456"
    )
    dumped = receipt.model_dump_json()
    assert "abcdef" in dumped
    assert "verified" in dumped

    loaded = VerificationReceipt.model_validate_json(dumped)
    assert loaded.receipt_id == receipt.receipt_id
