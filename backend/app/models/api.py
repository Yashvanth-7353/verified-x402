from pydantic import BaseModel

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt
)


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
