from uuid import uuid4
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.models.audit import LocalVerificationRecord, MerkleInclusion, AnchorTransaction
from app.models.enums import AnchoringStatus

def test_local_verification_record_valid():
    record = LocalVerificationRecord(
        record_id=uuid4(),
        result_ref="result_1",
        receipt_ref="receipt_1",
        anchoring_status=AnchoringStatus.unanchored
    )
    assert record.anchoring_status == AnchoringStatus.unanchored
    assert record.merkle_inclusion_ref is None

def test_local_verification_record_invalid():
    with pytest.raises(ValidationError):
        LocalVerificationRecord(
            record_id=uuid4(),
            result_ref="result_1",
            receipt_ref="receipt_1",
            anchoring_status="invalid_status"
        )

def test_anchor_transaction():
    tx = AnchorTransaction(
        anchor_tx_id="tx_123",
        merkle_root="root_hash",
        batch_size=10,
        submitted_at=datetime.now(timezone.utc)
    )
    assert tx.network == "Algorand"
    assert tx.confirmed_at is None
