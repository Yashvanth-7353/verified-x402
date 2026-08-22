import logging
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError as PydanticValidationError

from app.models.api import VerifyPayloadRequest, VerifyPayloadResponse
from app.services.orchestrator import VerificationOrchestrator
from app.storage.store import LocalVerificationRecordStore
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Phase 9: module-level record store (initialized lazily)
_record_store: LocalVerificationRecordStore | None = None


def _get_record_store() -> LocalVerificationRecordStore:
    global _record_store
    if _record_store is None:
        _record_store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)
    return _record_store


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

        # Phase 9: Persist the finalized record
        try:
            store = _get_record_store()
            store.upsert(result=result, receipt=receipt)
        except Exception:
            logger.exception(
                "Failed to persist verification record for request_id=%s "
                "(receipt still valid, persistence failure is separate concern)",
                payload.request.request_id,
            )

        return VerifyPayloadResponse(result=result, receipt=receipt)
    except Exception as e:
        logger.exception("Unexpected error during verification")
        raise HTTPException(
            status_code=500,
            detail="Internal verification error"
        )
