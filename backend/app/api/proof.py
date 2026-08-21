"""
GET /api/v1/anchor/proof/{record_id}

Generates a Merkle inclusion proof for an anchored verification record.

The proof allows an independent verifier to confirm that a specific
receipt_hash was included in the Merkle tree that was anchored to Algorand.

Algorithm:
    1. Retrieve the record from SQLite
    2. Confirm it has been anchored
    3. Find all records with the same merkle_root (same batch)
    4. Rebuild the deterministic Merkle tree
    5. Generate inclusion proof for the specific leaf
    6. Verify the proof
    7. Return proof data + verification result
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.core.config import settings
from app.storage.store import LocalVerificationRecordStore
from app.anchoring.merkle import build_merkle_tree, generate_proof, verify_proof

logger = logging.getLogger(__name__)

router = APIRouter()


class ProofNode(BaseModel):
    """A single node in a Merkle inclusion proof."""
    hash: str
    position: str  # "left" or "right"


class MerkleProofResponse(BaseModel):
    """Response containing a Merkle inclusion proof."""
    record_id: str
    receipt_hash: str
    merkle_root: str
    leaf_index: int
    batch_size: int
    proof: List[ProofNode]
    anchor_tx_ref: Optional[str] = None
    verification: dict  # {"valid": true/false, "details": "..."}


@router.get(
    "/anchor/proof/{record_id}",
    response_model=MerkleProofResponse,
    summary="Get Merkle inclusion proof for an anchored record",
    description=(
        "Generates a Merkle inclusion proof for a specific anchored verification "
        "record. The proof demonstrates that the record's receipt_hash was included "
        "in the Merkle tree that was anchored to Algorand TestNet."
    ),
    responses={
        404: {"description": "Record not found"},
        400: {"description": "Record is not anchored"},
    },
)
def get_merkle_proof(record_id: str) -> MerkleProofResponse:
    """Generate a Merkle inclusion proof for an anchored record."""
    try:
        store = LocalVerificationRecordStore(db_path=settings.resolved_database_path)

        # 1. Retrieve the record
        row = store.get_by_record_id(record_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found")

        # 2. Confirm it has been anchored
        anchoring_status = row.get("anchoring_status", "unanchored")
        if anchoring_status != "anchored":
            raise HTTPException(
                status_code=400,
                detail=f"Record has not been anchored yet (status: {anchoring_status})",
            )

        merkle_root = row.get("merkle_root")
        receipt_hash = row.get("receipt_hash")
        anchor_tx_ref = row.get("anchor_tx_ref")

        if not merkle_root or not receipt_hash:
            raise HTTPException(
                status_code=400,
                detail="Record is missing merkle_root or receipt_hash",
            )

        # 3. Find all records with the same merkle_root (same batch)
        all_records = store.list_records(offset=0, limit=10000)
        batch_records = [
            r for r in all_records
            if r.get("merkle_root") == merkle_root
        ]

        if not batch_records:
            raise HTTPException(
                status_code=400,
                detail="No records found with matching merkle_root",
            )

        # Sort by created_at + record_id for deterministic ordering (same as Merkle construction)
        batch_records.sort(key=lambda r: (r.get("created_at", ""), r.get("record_id", "")))

        # 4. Extract leaves in order
        leaves = [r["receipt_hash"] for r in batch_records]

        # 5. Find the leaf index for our record
        leaf_index = None
        for i, r in enumerate(batch_records):
            if r.get("record_id") == record_id:
                leaf_index = i
                break

        if leaf_index is None:
            raise HTTPException(
                status_code=404,
                detail="Record not found in batch",
            )

        # 6. Build the Merkle tree (deterministic reconstruction)
        tree = build_merkle_tree(leaves)
        if tree is None or tree.root is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to build Merkle tree",
            )

        # 7. Generate the proof
        raw_proof = generate_proof(tree, leaf_index)

        # 8. Verify the proof
        proof_valid = verify_proof(receipt_hash, raw_proof, merkle_root, leaf_index)

        # 9. Build response
        proof_nodes = []
        idx = leaf_index
        for sibling_hex in raw_proof:
            position = "right" if idx % 2 == 0 else "left"
            proof_nodes.append(ProofNode(hash=sibling_hex, position=position))
            idx = idx // 2

        return MerkleProofResponse(
            record_id=record_id,
            receipt_hash=receipt_hash,
            merkle_root=merkle_root,
            leaf_index=leaf_index,
            batch_size=len(leaves),
            proof=proof_nodes,
            anchor_tx_ref=anchor_tx_ref,
            verification={
                "valid": proof_valid,
                "details": (
                    f"Proof verified: leaf {leaf_index} of {len(leaves)} "
                    f"in batch with root {merkle_root[:16]}..."
                    if proof_valid
                    else "Proof verification failed — possible tampering"
                ),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate Merkle proof for %s", record_id)
        raise HTTPException(status_code=500, detail="Failed to generate Merkle proof")
