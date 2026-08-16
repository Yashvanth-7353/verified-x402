from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from app.models.enums import PaymentStatus

class PaymentMetadata(BaseModel):
    payment_id: UUID
    x402_challenge_ref: str
    payment_status: PaymentStatus
    facilitator: str = "GoPlausible AVM Facilitator"
    settlement_network: str = "Algorand"
    algorand_tx_ref: Optional[str] = None
    amount_and_asset: Any
    verified_at: Optional[datetime] = None
