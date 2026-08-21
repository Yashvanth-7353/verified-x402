from pydantic import BaseModel
from typing import Optional

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt
)
from app.models.payments import PaymentMetadata


class VerifyPayloadRequest(BaseModel):
    """
    API request model for the /verify endpoint.
    Accepts the verification request and the schema policy inline
    because no schema registry exists in the MVP.
    """
    request: VerificationRequest
    policy: SchemaPolicy


class VerifyPayloadResponse(BaseModel):
    """
    API response model for the /verify endpoint.
    Returns only the verification result and receipt.
    Does NOT echo the original or repaired payload.
    """
    result: VerificationResult
    receipt: VerificationReceipt


class SemanticRepairRequest(BaseModel):
    """
    API request model for the /semantic-repair endpoint.
    Accepts the request payload and schema policy inline (no registry in MVP).
    """
    request: VerificationRequest
    policy: SchemaPolicy


class SemanticRepairResponse(BaseModel):
    """
    API response model for the /semantic-repair endpoint.
    Returns the verification result, receipt, and (when semantic repair
    was attempted with a settled payment) the PaymentMetadata.
    Never returns raw payload or any payment credentials.
    """
    result: VerificationResult
    receipt: VerificationReceipt
    payment_metadata: Optional[PaymentMetadata] = None
