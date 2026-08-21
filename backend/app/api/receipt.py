"""
POST /api/v1/receipt/verify
GET  /api/v1/receipt/public-key

Independent verification of a signed VerificationReceipt.

POST /api/v1/receipt/verify:
  Accepts a signed receipt and verifies its integrity and signature.
  Does NOT require the signing private key — uses only the public key.

GET /api/v1/receipt/public-key:
  Returns the public verification key for the configured signing key.
  This allows third parties to obtain the public key for verification.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.crypto.verify import ReceiptVerifier, VerificationResult
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/v1/receipt/verify
# ---------------------------------------------------------------------------

class ReceiptVerifyRequest(BaseModel):
    """A signed receipt to verify."""
    receipt: dict  # The full receipt as a JSON object


class ReceiptVerifyResponse(BaseModel):
    """Result of receipt verification."""
    valid: bool
    signature_valid: bool
    receipt_integrity_valid: bool
    algorithm: str | None = None
    signing_key_id: str | None = None
    details: str = ""


@router.post(
    "/receipt/verify",
    response_model=ReceiptVerifyResponse,
    summary="Verify a signed verification receipt",
    description=(
        "Independently verifies a VerificationReceipt's integrity and "
        "cryptographic signature. Does not require the signing private key."
    ),
)
def verify_receipt(payload: ReceiptVerifyRequest) -> ReceiptVerifyResponse:
    """Verify receipt integrity and signature."""
    receipt = payload.receipt

    public_key_b64 = settings.RECEIPT_SIGNING_PUBLIC_KEY
    if not public_key_b64:
        raise HTTPException(
            status_code=503,
            detail="Receipt verification not configured: RECEIPT_SIGNING_PUBLIC_KEY not set",
        )

    try:
        verifier = ReceiptVerifier(public_key_b64=public_key_b64)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Invalid verification key: {e}")

    result = verifier.verify(receipt)

    return ReceiptVerifyResponse(
        valid=result.valid,
        signature_valid=result.signature_valid,
        receipt_integrity_valid=result.receipt_integrity_valid,
        algorithm=result.algorithm,
        signing_key_id=result.signing_key_id,
        details=result.details,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/receipt/public-key
# ---------------------------------------------------------------------------

class PublicKeyResponse(BaseModel):
    """Public verification key metadata."""
    algorithm: str
    key_id: str
    public_key: str


@router.get(
    "/receipt/public-key",
    response_model=PublicKeyResponse,
    summary="Get the public verification key",
    description=(
        "Returns the public Ed25519 key used to sign verification receipts. "
        "Third parties can use this key to independently verify receipts."
    ),
)
def get_public_key() -> PublicKeyResponse:
    """Return the public verification key."""
    public_key_b64 = settings.RECEIPT_SIGNING_PUBLIC_KEY
    if not public_key_b64:
        raise HTTPException(
            status_code=503,
            detail="Receipt signing not configured: RECEIPT_SIGNING_PUBLIC_KEY not set",
        )

    import hashlib
    import base64
    key_id = hashlib.sha256(
        base64.b64decode(public_key_b64)
    ).hexdigest()[:16]

    return PublicKeyResponse(
        algorithm="Ed25519",
        key_id=key_id,
        public_key=public_key_b64,
    )
