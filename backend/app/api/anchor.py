"""
POST /api/v1/anchor

Triggers Merkle anchoring of unanchored verification records to Algorand TestNet.

This is a manual trigger for the MVP. The architecture allows for future
automatic scheduling, but Phase 10 uses explicit invocation for testability.

The endpoint:
1. Selects unanchored records from the local store
2. Builds a deterministic Merkle tree over receipt_hash values
3. Submits the Merkle root to Algorand TestNet
4. Waits for confirmation
5. Marks records as anchored

Only runs if ANCHOR_PRIVATE_KEY is configured.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.storage.store import LocalVerificationRecordStore
from app.anchoring.service import (
    MerkleAnchoringService,
    TestNetAlgorandClient,
    AnchorResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class AnchorRequest(BaseModel):
    """Optional request body to override batch size."""
    batch_size: Optional[int] = None


class AnchorResponse(BaseModel):
    """Response from the anchoring operation."""
    status: str
    leaf_count: int = 0
    merkle_root: Optional[str] = None
    transaction_id: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/anchor",
    response_model=AnchorResponse,
    summary="Anchor unanchored verification records to Algorand TestNet",
    description=(
        "Triggers Merkle anchoring of unanchored local verification records. "
        "Builds a Merkle tree over receipt_hash values and submits the root "
        "to Algorand TestNet. Requires ANCHOR_PRIVATE_KEY to be configured."
    ),
    responses={
        503: {"description": "Anchoring not configured (missing ANCHOR_PRIVATE_KEY)"},
        500: {"description": "Anchoring failed"},
    },
)
def anchor_records(payload: AnchorRequest = None) -> AnchorResponse:
    """Trigger Merkle anchoring of unanchored records."""
    if not settings.ANCHOR_PRIVATE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Anchoring not configured: ANCHOR_PRIVATE_KEY is not set",
        )

    try:
        store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)

        client = TestNetAlgorandClient(
            private_key_b64=settings.ANCHOR_PRIVATE_KEY,
            algod_address=settings.ANCHOR_ALGOD_ADDRESS,
            algod_token=settings.ANCHOR_ALGOD_TOKEN,
        )

        batch_size = payload.batch_size if payload and payload.batch_size else settings.MERKLE_BATCH_SIZE

        service = MerkleAnchoringService(
            record_store=store,
            anchor_client=client,
            batch_size=batch_size,
        )

        result = service.anchor_pending_records()

        return AnchorResponse(
            status=result.status,
            leaf_count=result.leaf_count,
            merkle_root=result.merkle_root,
            transaction_id=result.transaction_id,
            error=result.error,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during anchoring")
        raise HTTPException(
            status_code=500,
            detail="Internal anchoring error",
        )
