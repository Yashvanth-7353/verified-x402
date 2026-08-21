"""
POST /api/v1/receipt/verify

Independent verification of a signed VerificationReceipt.

This endpoint allows any recipient to verify:
1. The receipt hash is valid (not tampered)
2. The cryptographic signature is valid (if present)
3. The receipt has not been modified since signing

Does NOT require the signing private key — uses only the public key
embedded in the receipt or from configuration.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.evidence.hasher import hash_data
from app.crypto.signing import ReceiptSigner
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ReceiptVerifyRequest(BaseModel):
    """A signed receipt to verify."""
    receipt: dict  # The full receipt as a JSON object


class ReceiptVerifyResponse(BaseModel):
    """Result of receipt verification."""
    receipt_valid: bool
    signature_valid: bool | None = None
    signing_key_id: str | None = None
    signature_algorithm: str | None = None
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

    # 1. Verify receipt_hash integrity
    receipt_for_hash = dict(receipt)
    receipt_for_hash.pop("receipt_hash", None)
    receipt_for_hash.pop("signature", None)
    receipt_for_hash.pop("signature_algorithm", None)
    receipt_for_hash.pop("signing_key_id", None)

    computed_hash = hash_data(receipt_for_hash)
    receipt_hash_valid = computed_hash == receipt.get("receipt_hash", "")

    if not receipt_hash_valid:
        return ReceiptVerifyResponse(
            receipt_valid=False,
            signature_valid=False,
            details="Receipt hash mismatch — receipt has been tampered with",
        )

    # 2. Verify signature if present
    signature_hex = receipt.get("signature")
    if not signature_hex:
        return ReceiptVerifyResponse(
            receipt_valid=True,
            signature_valid=None,
            details="Receipt hash valid but unsigned",
        )

    # Try to get public key from receipt's key_id or from configuration
    signing_key_id = receipt.get("signing_key_id")
    public_key_b64 = settings.RECEIPT_SIGNING_PUBLIC_KEY

    if not public_key_b64:
        return ReceiptVerifyResponse(
            receipt_valid=True,
            signature_valid=None,
            signing_key_id=signing_key_id,
            signature_algorithm=receipt.get("signature_algorithm"),
            details="Receipt hash valid; signature present but no public key configured for verification",
        )

    # Verify the signature
    sig_valid = ReceiptSigner.verify_signature(receipt, public_key_b64)

    return ReceiptVerifyResponse(
        receipt_valid=True,
        signature_valid=sig_valid,
        signing_key_id=signing_key_id,
        signature_algorithm=receipt.get("signature_algorithm"),
        details="Receipt verified: hash valid, signature valid" if sig_valid
        else "Receipt hash valid but signature INVALID",
    )
