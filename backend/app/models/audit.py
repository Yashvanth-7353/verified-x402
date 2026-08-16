from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.enums import AnchoringStatus

class LocalVerificationRecord(BaseModel):
    record_id: UUID
    result_ref: str
    receipt_ref: str
    anchoring_status: AnchoringStatus
    merkle_inclusion_ref: Optional[str] = None

class MerkleInclusion(BaseModel):
    inclusion_id: UUID
    receipt_hash_ref: str
    merkle_proof_path: list[str]
    merkle_root: str
    anchor_tx_ref: str

class AnchorTransaction(BaseModel):
    anchor_tx_id: str
    merkle_root: str
    batch_size: int
    submitted_at: datetime
    confirmed_at: Optional[datetime] = None
    network: str = "Algorand"
