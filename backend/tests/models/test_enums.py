import pytest
from app.models.enums import OutputType, ValidationStage, Severity, Repairability, RepairType, PaymentStatus, VerificationOutcome, AnchoringStatus

def test_enums_exist():
    assert OutputType.json == "json"
    assert ValidationStage.schema == "schema"
    assert Severity.blocking == "blocking"
    assert Repairability.deterministic == "deterministic"
    assert RepairType.semantic == "semantic"
    assert PaymentStatus.settled == "settled"
    assert VerificationOutcome.verified == "verified"
    assert AnchoringStatus.anchored == "anchored"
