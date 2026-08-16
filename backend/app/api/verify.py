import logging
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError as PydanticValidationError

from app.models.api import VerifyPayloadRequest, VerifyPayloadResponse
from app.services.orchestrator import VerificationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/verify",
    response_model=VerifyPayloadResponse,
    summary="Verify a structured agent output",
    description=(
        "Accepts a structured output payload and a schema policy, "
        "runs the local verification pipeline (schema validation, "
        "type checking, deterministic repair if applicable, revalidation), "
        "and returns a verification result with a tamper-evident receipt. "
        "Does not perform semantic repair, LLM calls, or external escalation."
    ),
    responses={
        400: {"description": "Malformed request or invalid schema definition"},
        422: {"description": "Request validation error"},
    },
)
def verify(payload: VerifyPayloadRequest) -> VerifyPayloadResponse:
    """Thin route: delegates all logic to the VerificationOrchestrator."""
    try:
        orchestrator = VerificationOrchestrator()
        result, receipt = orchestrator.process(payload.request, payload.policy)
        return VerifyPayloadResponse(result=result, receipt=receipt)
    except Exception as e:
        logger.exception("Unexpected error during verification")
        raise HTTPException(
            status_code=500,
            detail="Internal verification error"
        )
