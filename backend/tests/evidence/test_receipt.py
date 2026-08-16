from uuid import uuid4
from datetime import datetime, timezone
import pytest

from app.models.verification import VerificationRequest, SchemaPolicy, VerificationResult, RepairInfo
from app.models.enums import OutputType, VerificationOutcome, RepairType
from app.evidence.receipt import ReceiptService

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
        schema_definition={"type": "object"},
        privacy_policy_ref="default"
    )

@pytest.fixture
def base_result(base_request):
    return VerificationResult(
        result_id=uuid4(),
        request_ref=str(base_request.request_id),
        findings=[],
        outcome=VerificationOutcome.verified,
        validator_version="1.0.0",
        completed_at=datetime.now(timezone.utc)
    )

def test_generate_and_verify_receipt_valid(base_request, base_policy, base_result):
    service = ReceiptService()
    receipt = service.generate_receipt(base_request, base_policy, base_result, base_request.output_payload)
    
    # Check no raw payload in receipt
    dump = receipt.model_dump_json()
    assert "Alice" not in dump
    
    # Verify receipt locally
    is_valid = service.verify_receipt(receipt, base_request, base_policy, base_result, base_request.output_payload)
    assert is_valid is True

def test_verify_receipt_tampered_payload(base_request, base_policy, base_result):
    service = ReceiptService()
    receipt = service.generate_receipt(base_request, base_policy, base_result, base_request.output_payload)
    
    tampered_payload = {"name": "Bob"}
    is_valid = service.verify_receipt(receipt, base_request, base_policy, base_result, tampered_payload)
    assert is_valid is False

def test_verify_receipt_tampered_hash(base_request, base_policy, base_result):
    service = ReceiptService()
    receipt = service.generate_receipt(base_request, base_policy, base_result, base_request.output_payload)
    
    receipt.receipt_hash = "invalid_hash"
    is_valid = service.verify_receipt(receipt, base_request, base_policy, base_result, base_request.output_payload)
    assert is_valid is False

def test_receipt_with_repair(base_request, base_policy, base_result):
    base_result.repair_info = RepairInfo(
        repair_id=uuid4(),
        repair_type=RepairType.deterministic,
        findings_addressed=["finding1"],
        pre_repair_output_hash="hash1",
        post_repair_output_hash="hash2"
    )
    
    service = ReceiptService()
    receipt = service.generate_receipt(base_request, base_policy, base_result, base_request.output_payload)
    
    assert receipt.repair_summary_hash is not None
    is_valid = service.verify_receipt(receipt, base_request, base_policy, base_result, base_request.output_payload)
    assert is_valid is True
