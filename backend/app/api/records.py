"""
GET /api/v1/records
GET /api/v1/records/{record_id}

Exposes persisted verification records from the local SQLite store.

Returns safe metadata only — no private keys, X-PAYMENT data,
raw payloads, or sensitive internal fields.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.config import settings
from app.storage.store import LocalVerificationRecordStore

logger = logging.getLogger(__name__)

router = APIRouter()


class RecordSummary(BaseModel):
    """Safe metadata for a persisted verification record."""
    record_id: str
    request_id: str
    receipt_id: str
    outcome: str
    receipt_hash: str
    output_hash: Optional[str] = None
    payment_status: Optional[str] = None
    anchoring_status: str = "unanchored"
    merkle_root: Optional[str] = None
    anchor_tx_ref: Optional[str] = None
    created_at: str


class RecordDetail(RecordSummary):
    """Extended record detail for individual record view."""
    schema_ref_and_version: Optional[str] = None
    validator_version: Optional[str] = None
    signing_key_id: Optional[str] = None
    signature_algorithm: Optional[str] = None
    agent_identifier: Optional[str] = None
    repair_type: Optional[str] = None
    payment_facilitator: Optional[str] = None
    settlement_network: Optional[str] = None


class RecordsListResponse(BaseModel):
    """Response containing a list of records."""
    records: List[RecordSummary]
    total: int
    offset: int
    limit: int


def _record_to_summary(row: dict) -> RecordSummary:
    """Convert a database row to a safe RecordSummary."""
    return RecordSummary(
        record_id=row["record_id"],
        request_id=row["request_id"],
        receipt_id=row["receipt_id"],
        outcome=row.get("outcome", "unknown"),
        receipt_hash=row.get("receipt_hash", ""),
        output_hash=row.get("output_hash"),
        payment_status=row.get("payment_status"),
        anchoring_status=row.get("anchoring_status", "unanchored"),
        merkle_root=row.get("merkle_root"),
        anchor_tx_ref=row.get("anchor_tx_ref"),
        created_at=row.get("created_at", ""),
    )


def _record_to_detail(row: dict) -> RecordDetail:
    """Convert a database row to a safe RecordDetail."""
    base = _record_to_summary(row)
    return RecordDetail(
        **base.model_dump(),
        schema_ref_and_version=row.get("schema_ref_and_version"),
        validator_version=row.get("validator_version"),
        signing_key_id=row.get("signing_key_id"),
        signature_algorithm=row.get("signature_algorithm"),
        agent_identifier=row.get("agent_identifier"),
        repair_type=row.get("repair_type"),
        payment_facilitator=row.get("payment_facilitator"),
        settlement_network=row.get("settlement_network"),
    )


@router.get(
    "/records",
    response_model=RecordsListResponse,
    summary="List persisted verification records",
    description=(
        "Returns verification records from the local SQLite store. "
        "Supports pagination via offset and limit query parameters. "
        "Returns safe metadata only — no private keys or sensitive payloads."
    ),
)
def list_records(offset: int = 0, limit: int = 50) -> RecordsListResponse:
    """List persisted verification records with pagination."""
    try:
        store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)

        # Cap limit to prevent abuse
        limit = max(1, min(limit, 200))

        all_records = store.list_records(offset=0, limit=1000)  # Get total count
        total = len(all_records)

        # Get the page
        records = store.list_records(offset=offset, limit=limit)
        summaries = [_record_to_summary(r) for r in records]

        return RecordsListResponse(
            records=summaries,
            total=total,
            offset=offset,
            limit=limit,
        )
    except Exception as e:
        logger.exception("Failed to list records")
        raise HTTPException(status_code=500, detail="Failed to retrieve records")


@router.get(
    "/records/{record_id}",
    response_model=RecordDetail,
    summary="Get a specific verification record",
    description="Returns detailed metadata for a specific verification record.",
)
def get_record(record_id: str) -> RecordDetail:
    """Get a specific verification record by ID."""
    try:
        store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)
        row = store.get_by_record_id(record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return _record_to_detail(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get record %s", record_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve record")
