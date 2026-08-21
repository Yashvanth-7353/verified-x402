"""
POST /api/v1/semantic-repair

Phase 8 hardened — payment metadata propagation.

The x402 middleware (main.py) now verifies AND settles payment BEFORE
calling this handler.  Settlement info is available on request.state:

  request.state.payment_payload       — the X-PAYMENT payload
  request.state.payment_requirements  — the payment requirements
  request.state.settlement_result     — ProcessSettleResult (success, tx, network, payer)

Architecture invariants enforced here:
- Payment settlement (done by middleware) is NEVER treated as verification success.
- SemanticRepairEngine runs only after middleware confirms settled payment.
- The repaired candidate MUST pass VerificationEngine revalidation before acceptance.
- No payment credentials, secrets, or X-PAYMENT contents are logged or returned.
- A verified_repaired outcome ALWAYS carries a non-null PaymentMetadata with
  payment_status=settled (Phase 8 invariant).
"""
import logging
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt,
)
from app.models.payments import PaymentMetadata
from app.models.enums import VerificationOutcome, Severity, PaymentStatus
from app.validation.engine import VerificationEngine
from app.repair.semantic import SemanticRepairEngine
from app.evidence.receipt import ReceiptService
from app.models.api import SemanticRepairRequest, SemanticRepairResponse
from app.storage.store import LocalVerificationRecordStore
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

VALIDATOR_VERSION = "0.1.0"

# Phase 9: module-level record store (initialized lazily)
_record_store: LocalVerificationRecordStore | None = None


def _get_record_store() -> LocalVerificationRecordStore:
    global _record_store
    if _record_store is None:
        _record_store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)
    return _record_store


def _build_payment_metadata(
    request: VerificationRequest,
    payment_payload,
    payment_requirements,
    settlement_result,
) -> PaymentMetadata:
    """
    Create a PaymentMetadata record from the x402 settlement context.

    Called ONLY after the middleware has confirmed settlement succeeded.
    This guarantees payment_status = settled and a real Algorand tx ref.
    """
    # Extract amount_and_asset from the payment requirements (x402 PaymentRequirements model)
    amount_and_asset = {
        "scheme": getattr(payment_requirements, "scheme", None),
        "asset": getattr(payment_requirements, "asset", None),
        "amount": getattr(payment_requirements, "amount", None),
        "pay_to": getattr(payment_requirements, "pay_to", None),
    }
    # Filter out None values for clean JSON serialization
    amount_and_asset = {k: v for k, v in amount_and_asset.items() if v is not None}

    return PaymentMetadata(
        payment_id=uuid4(),
        x402_challenge_ref=str(request.request_id),
        payment_status=PaymentStatus.settled,
        facilitator="GoPlausible AVM Facilitator",
        settlement_network="Algorand",
        algorand_tx_ref=getattr(settlement_result, "transaction", None),
        amount_and_asset=amount_and_asset,
        verified_at=datetime.now(timezone.utc),
    )


@router.post(
    "/semantic-repair",
    response_model=SemanticRepairResponse,
    summary="Semantically repair a structured agent output (x402 payment required)",
    description=(
        "Requires a valid x402 payment (X-PAYMENT header) verified AND settled "
        "by the GoPlausible AVM Facilitator on Algorand Testnet. "
        "Payment settlement grants access to one semantic-repair attempt. "
        "The repaired candidate is revalidated by VerificationEngine before "
        "acceptance. Payment success NEVER implies verification success."
    ),
    responses={
        402: {"description": "Payment required — returns x402 challenge, or settlement failed"},
        400: {"description": "Malformed request or invalid schema definition"},
        422: {"description": "Request validation error"},
    },
)
def semantic_repair(payload: SemanticRepairRequest, request: Request) -> SemanticRepairResponse:
    """
    Thin route: payment is already verified AND settled by middleware.
    Delegates all repair/revalidation logic to the engines.

    Phase 8: Creates PaymentMetadata from settlement info on request.state
    and attaches it to RepairInfo.payment_ref when repair succeeds.
    """
    try:
        verification_engine = VerificationEngine()
        semantic_engine = SemanticRepairEngine()
        receipt_service = ReceiptService()

        # ---- Extract settlement context from middleware ----
        settlement_result = getattr(request.state, "settlement_result", None)
        payment_payload = getattr(request.state, "payment_payload", None)
        payment_requirements = getattr(request.state, "payment_requirements", None)

        if settlement_result is None or not getattr(settlement_result, "success", False):
            # Defensive: middleware should never let us reach here without settled payment
            logger.error("semantic_repair called without settled payment on request.state")
            raise HTTPException(
                status_code=500,
                detail="Internal error: settlement context missing",
            )

        # ---- Build PaymentMetadata from actual settlement result ----
        payment_metadata = _build_payment_metadata(
            payload.request, payment_payload, payment_requirements, settlement_result
        )

        logger.info(
            "semantic_repair: request_id=%s payment_status=%s algorand_tx=%s",
            payload.request.request_id,
            payment_metadata.payment_status.value,
            payment_metadata.algorand_tx_ref or "N/A",
        )

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
                    # ---- Phase 8: Attach payment_ref to RepairInfo ----
                    repair_info.payment_ref = str(payment_metadata.payment_id)
                    revalidation_result.repair_info = repair_info
                    revalidation_result.outcome = VerificationOutcome.verified_repaired
                    final_result = revalidation_result
                    final_payload = candidate_payload

                    logger.info(
                        "semantic_repair SUCCESS: request_id=%s outcome=verified_repaired "
                        "repair_id=%s payment_ref=%s",
                        payload.request.request_id,
                        repair_info.repair_id,
                        repair_info.payment_ref,
                    )
                else:
                    logger.info(
                        "semantic_repair: revalidation still failed for request_id=%s, "
                        "outcome=rejected (payment consumed, repair failed)",
                        payload.request.request_id,
                    )
            else:
                logger.info(
                    "semantic_repair: provider returned no repair for request_id=%s",
                    payload.request.request_id,
                )
        else:
            logger.info(
                "semantic_repair: no semantic repair attempted for request_id=%s "
                "(has_blocking=%s, schema_is_invalid=%s)",
                payload.request.request_id,
                has_blocking,
                schema_is_invalid,
            )

        # 4. Generate receipt from the final verified/rejected result
        receipt = receipt_service.generate_receipt(
            payload.request, payload.policy, final_result, final_payload
        )

        logger.info(
            "semantic_repair: request_id=%s outcome=%s receipt_id=%s receipt_hash=%s",
            payload.request.request_id,
            final_result.outcome,
            receipt.receipt_id,
            receipt.receipt_hash[:16] + "...",
        )

        # Phase 8: Include payment_metadata only when semantic repair was attempted
        # with a settled payment (i.e., payment_metadata was created for this request)
        response = SemanticRepairResponse(
            result=final_result,
            receipt=receipt,
            payment_metadata=payment_metadata,
        )

        # Phase 9: Persist the finalized record
        try:
            store = _get_record_store()
            store.save(
                result=final_result,
                receipt=receipt,
                payment_metadata=payment_metadata,
            )
        except Exception:
            logger.exception(
                "Failed to persist semantic repair record for request_id=%s "
                "(receipt still valid, persistence failure is separate concern)",
                payload.request.request_id,
            )

        return response

    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during semantic repair")
        raise HTTPException(
            status_code=500,
            detail="Internal semantic repair error",
        )
