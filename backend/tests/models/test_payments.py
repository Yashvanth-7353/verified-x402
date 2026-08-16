from uuid import uuid4
from datetime import datetime, timezone
from app.models.payments import PaymentMetadata
from app.models.enums import PaymentStatus
from pydantic import ValidationError
import pytest

def test_payment_metadata_valid():
    pm = PaymentMetadata(
        payment_id=uuid4(),
        x402_challenge_ref="challenge_123",
        payment_status=PaymentStatus.settled,
        amount_and_asset={"amount": 100, "asset": "USDC"}
    )
    assert pm.payment_status == PaymentStatus.settled
    assert pm.facilitator == "GoPlausible AVM Facilitator"
    assert pm.settlement_network == "Algorand"
    assert pm.algorand_tx_ref is None
    assert pm.verified_at is None

def test_payment_metadata_invalid():
    with pytest.raises(ValidationError):
        PaymentMetadata(
            payment_id="not-a-uuid",
            x402_challenge_ref="challenge_123",
            payment_status=PaymentStatus.settled,
            amount_and_asset={"amount": 100}
        )
