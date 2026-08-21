"""
Phase 10: Merkle Anchoring Service.

Batches unanchored local verification records into a deterministic Merkle tree
and anchors the root to Algorand TestNet via a payment transaction with the
Merkle root in the note field.

Critical ordering:
    select records
        ↓
    build Merkle tree → root
        ↓
    submit Algorand transaction
        ↓
    wait for confirmation
        ↓
    transaction confirmed → tx_id
        ↓
    mark records anchored (root + tx_id)

NEVER mark records anchored before confirmation.

Retry-safe:
    - If submission fails → records remain unanchored
    - If confirmation fails → records remain unanchored
    - Failed batches can be retried (records are still unanchored)
"""
from __future__ import annotations

import base64
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

from app.anchoring.merkle import compute_root, build_merkle_tree, MerkleTree
from app.storage.store import LocalVerificationRecordStore, LocalVerificationRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol for Algorand client (allows mocking in tests)
# ---------------------------------------------------------------------------

class AlgorandAnchorClient(Protocol):
    """
    Interface for submitting an anchor transaction to Algorand.

    This allows the anchoring service to be tested without real
    network access by providing a mock implementation.
    """

    def submit_anchor(self, merkle_root: str, fee_microalgos: int = 1000) -> str:
        """
        Submit a payment transaction to Algorand with the Merkle root as note.

        Args:
            merkle_root: The Merkle root hex string to anchor on-chain.
            fee_microalgos: Transaction fee in microAlgos.

        Returns:
            The confirmed Algorand transaction ID.

        Raises:
            AlgorandAnchorError: If submission or confirmation fails.
        """
        ...


class AlgorandAnchorError(Exception):
    """Raised when Algorand anchor submission or confirmation fails."""
    pass


# ---------------------------------------------------------------------------
# Anchor result
# ---------------------------------------------------------------------------

@dataclass
class AnchorResult:
    """Result of a single anchoring operation."""
    status: str  # "anchored" | "no_records_to_anchor" | "failed"
    record_ids: list[str] = field(default_factory=list)
    leaf_count: int = 0
    merkle_root: Optional[str] = None
    transaction_id: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Default Algorand client (real TestNet)
# ---------------------------------------------------------------------------

class TestNetAlgorandClient:
    """
    Algorand TestNet client for anchor transactions.

    Uses the algosdk library to submit a payment transaction with the
    Merkle root encoded in the note field.
    """

    def __init__(
        self,
        private_key_b64: str,
        algod_address: str = "https://testnet-api.algonode.cloud",
        algod_token: str = "",
    ):
        from algosdk import account, transaction
        from algosdk.v2client import algod

        self._private_key = private_key_b64
        self._address = account.address_from_private_key(private_key_b64)
        self._algod = algod.AlgodClient(algod_token, algod_address)
        self._transaction = transaction

    def submit_anchor(self, merkle_root: str, fee_microalgos: int = 1000) -> str:
        """
        Submit a payment transaction with Merkle root in the note field.

        The transaction sends 0 Algos to self with the Merkle root as a note,
        creating an immutable on-chain record of the anchor.
        """
        try:
            params = self._algod.suggested_params()
            params.fee = fee_microalgos
            params.min_fee = fee_microalgos

            # Encode Merkle root as note (UTF-8)
            note = b"verified-merkle-v1:" + merkle_root.encode("utf-8")

            txn = self._transaction.PaymentTxn(
                sender=self._address,
                sp=params,
                receiver=self._address,  # Send to self
                amt=0,
                note=note,
            )

            signed_txn = txn.sign(self._private_key)
            tx_id = self._algod.send_transaction(signed_txn)

            # Wait for confirmation
            result = self._transaction.wait_for_confirmation(self._algod, tx_id, 4)
            confirmed_tx_id = result.get("txn", {}).get("id", tx_id)

            logger.info("Algorand anchor confirmed: tx=%s round=%s", confirmed_tx_id, result.get("confirmed-round"))
            return confirmed_tx_id

        except Exception as e:
            raise AlgorandAnchorError(f"Algorand anchor failed: {e}") from e


# ---------------------------------------------------------------------------
# Anchoring Service
# ---------------------------------------------------------------------------

class MerkleAnchoringService:
    """
    Anchors unanchored verification records to Algorand TestNet.

    Thread-safe: uses a process-local lock to prevent duplicate anchoring
    of the same batch. Single-process design appropriate for the Jetson
    local-first architecture.
    """

    def __init__(
        self,
        record_store: LocalVerificationRecordStore,
        anchor_client: AlgorandAnchorClient,
        batch_size: int = 10,
    ):
        self._store = record_store
        self._client = anchor_client
        self._batch_size = batch_size
        self._lock = threading.Lock()

    def anchor_pending_records(self) -> AnchorResult:
        """
        Select unanchored records, build Merkle tree, anchor to Algorand.

        This is the main entry point for the anchoring trigger.
        Can be called manually or by a future scheduler.

        Returns:
            AnchorResult with the outcome of the anchoring operation.
        """
        with self._lock:
            return self._do_anchor()

    def _do_anchor(self) -> AnchorResult:
        """Internal anchoring implementation (must be called under lock)."""
        start_time = datetime.now(timezone.utc)

        # 1. Select unanchored records
        all_unanchored = self._store.list_unanchored_records()
        batch = all_unanchored[: self._batch_size]

        if not batch:
            logger.info("No unanchored records to anchor")
            return AnchorResult(status="no_records_to_anchor")

        logger.info(
            "Merkle anchor started: records=%d (of %d unanchored)",
            len(batch),
            len(all_unanchored),
        )

        # 2. Extract leaf hashes (receipt_hash values)
        leaves = [r.receipt_hash for r in batch]

        # 3. Build Merkle tree and compute root
        tree = build_merkle_tree(leaves)
        if tree.root is None:
            return AnchorResult(status="no_records_to_anchor")

        merkle_root = tree.root
        logger.info("Merkle root computed: root=%s... leaves=%d", merkle_root[:16], len(leaves))

        # 4. Submit to Algorand
        try:
            tx_id = self._client.submit_anchor(merkle_root)
        except AlgorandAnchorError as e:
            logger.error("Merkle anchor failed: %s", e)
            return AnchorResult(
                status="failed",
                leaf_count=len(batch),
                merkle_root=merkle_root,
                error=str(e),
            )

        logger.info("Algorand anchor confirmed: tx=%s", tx_id)

        # 5. Mark records anchored (only after confirmation)
        record_ids = [str(r.record_id) for r in batch]
        self._store.mark_anchored(
            record_ids=record_ids,
            merkle_root=merkle_root,
            anchor_tx_ref=tx_id,
        )

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            "Anchored %d verification records (merkle_root=%s..., tx=%s, elapsed=%.2fs)",
            len(batch),
            merkle_root[:16],
            tx_id,
            elapsed,
        )

        return AnchorResult(
            status="anchored",
            record_ids=record_ids,
            leaf_count=len(batch),
            merkle_root=merkle_root,
            transaction_id=tx_id,
        )
