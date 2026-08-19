"""
POST /api/v1/semantic-repair

This endpoint is protected by the x402 payment middleware registered in main.py.
The middleware handles the full 402 challenge / X-PAYMENT verification cycle via
the GoPlausible AVM Facilitator before this handler is ever invoked.

Architecture invariants enforced here:
- Payment authorization (done by middleware) is NEVER treated as verification success.
- SemanticRepairEngine runs only after middleware confirms valid payment.
- The repaired candidate MUST pass VerificationEngine revalidation before acceptance.
- No payment credentials, secrets, or X-PAYMENT contents are logged or returned.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt,
)
from app.models.enums import VerificationOutcome, Severity
from app.validation.engine import VerificationEngine
from app.repair.semantic import SemanticRepairEngine
from app.evidence.receipt import ReceiptService

logger = logging.getLogger(__name__)

router = APIRouter()

VALIDATOR_VERSION = "0.1.0"


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
    Returns only the verification result and receipt — never the raw payload
    or any payment credentials.
    """
    result: VerificationResult
    receipt: VerificationReceipt


@router.post(
    "/semantic-repair",
    response_model=SemanticRepairResponse,
    summary="Semantically repair a structured agent output (x402 payment required)",
    description=(
        "Requires a valid x402 payment (X-PAYMENT header) verified by the "
        "GoPlausible AVM Facilitator on Algorand Testnet. "
        "Payment authorization grants access to one semantic-repair attempt. "
        "The repaired candidate is revalidated by VerificationEngine before "
        "acceptance. Payment success NEVER implies verification success."
    ),
    responses={
        402: {"description": "Payment required — returns x402 challenge"},
        400: {"description": "Malformed request or invalid schema definition"},
        422: {"description": "Request validation error"},
    },
)
def semantic_repair(payload: SemanticRepairRequest) -> SemanticRepairResponse:
    """
    Thin route: payment is already verified by middleware.
    Delegates all repair/revalidation logic to the engines.
    """
    try:
        verification_engine = VerificationEngine()
        semantic_engine = SemanticRepairEngine()
        receipt_service = ReceiptService()

        # 1. Validate the original payload
        initial_result = verification_engine.verify_request(
            payload.request, payload.policy, VALIDATOR_VERSION
        )

        final_payload = payload.request.output_payload
        final_result = initial_result

        # 2. Attempt exactly ONE semantic repair pass
        schema_is_invalid = any(
            f.severity == Severity.blocking and "Invalid schema" in f.description
            for f in initial_result.findings
        )
        has_blocking = any(
            f.severity == Severity.blocking for f in initial_result.findings
        )

        if has_blocking and not schema_is_invalid:
            candidate_payload, repair_info = semantic_engine.attempt_repair(
                payload.request, payload.policy, initial_result.findings
            )

            if repair_info is not None:
                # 3. MANDATORY revalidation — payment does NOT equal success
                repaired_request = payload.request.model_copy()
                repaired_request.output_payload = candidate_payload

                revalidation_result = verification_engine.verify_request(
                    repaired_request, payload.policy, VALIDATOR_VERSION
                )

                revalidation_has_blocking = any(
                    f.severity == Severity.blocking
                    for f in revalidation_result.findings
                )

                if not revalidation_has_blocking:
                    revalidation_result.repair_info = repair_info
                    revalidation_result.outcome = VerificationOutcome.verified_repaired
                    final_result = revalidation_result
                    final_payload = candidate_payload
                # If revalidation still fails, final_result remains the original
                # (rejected) outcome — payment is consumed but repair failed.

        # 4. Generate receipt from the final verified/rejected result
        receipt = receipt_service.generate_receipt(
            payload.request, payload.policy, final_result, final_payload
        )

        return SemanticRepairResponse(result=final_result, receipt=receipt)

    except Exception:
        logger.exception("Unexpected error during semantic repair")
        raise HTTPException(
            status_code=500,
            detail="Internal semantic repair error",
        )
