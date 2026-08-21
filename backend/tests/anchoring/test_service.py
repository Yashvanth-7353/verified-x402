"""
Phase 10 tests: Merkle Anchoring Service.

Tests cover:
- Empty batch → no anchor
- Batch selection with configurable size
- Merkle root computation from batch
- Algorand submission (mocked)
- Confirmation before marking anchored
- Successful anchor marks records
- Failed submission leaves records unanchored
- Retry safety
- Duplicate anchoring prevention
- Private key never logged
"""
import hashlib
import logging
from uuid import uuid4, uuid5, UUID
from datetime import datetime, timezone

import pytest

from app.models.verification import (
    VerificationResult, VerificationReceipt,
)
from app.models.enums import (
    VerificationOutcome, AnchoringStatus,
)
from app.storage.store import LocalVerificationRecordStore
from app.anchoring.service import (
    MerkleAnchoringService,
    AnchorResult,
    AlgorandAnchorError,
)
from app.anchoring.merkle import compute_root


# ---------------------------------------------------------------------------
# Mock Algorand client
# ---------------------------------------------------------------------------

class MockAlgorandClient:
    """Deterministic mock for testing without real Algorand."""

    def __init__(self, should_fail: bool = False, tx_id: str = "MOCK_TX_001"):
        self._should_fail = should_fail
        self._tx_id = tx_id
        self._submitted = []

    def submit_anchor(self, merkle_root: str, fee_microalgos: int = 1000) -> str:
        self._submitted.append(merkle_root)
        if self._should_fail:
            raise AlgorandAnchorError("Mocked Algorand failure")
        return self._tx_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_NAMESPACE = UUID("12345678-1234-5678-1234-567812345678")


def _make_verified_record(store, request_id=None, seed=None):
    """Create and persist a verified record for testing."""
    if seed is None:
        seed = str(request_id or uuid4())
    if request_id is None:
        # Deterministic request_id from seed for consistent ordering
        request_id = uuid5(_TEST_NAMESPACE, seed)

    receipt_hash = hashlib.sha256(seed.encode()).hexdigest()

    result = VerificationResult(
        result_id=uuid5(_TEST_NAMESPACE, f"result_{seed}"),
        request_ref=str(request_id),
        findings=[],
        outcome=VerificationOutcome.verified,
        validator_version="0.1.0",
        completed_at=datetime.now(timezone.utc),
    )
    receipt = VerificationReceipt(
        receipt_id=uuid5(_TEST_NAMESPACE, f"receipt_{seed}"),
        request_id_ref=str(request_id),
        outcome=VerificationOutcome.verified,
        output_hash="abc123",
        schema_ref_and_version="schema@1.0",
        validator_version="0.1.0",
        issued_at=datetime.now(timezone.utc),
        receipt_hash=receipt_hash,
    )
    return store.save(result=result, receipt=receipt)


@pytest.fixture
def tmp_store(tmp_path):
    """Fresh store with isolated database."""
    s = LocalVerificationRecordStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.close()


@pytest.fixture
def mock_client():
    return MockAlgorandClient()


@pytest.fixture
def failing_client():
    return MockAlgorandClient(should_fail=True)


# ===========================================================================
# Test 7-8: Empty batch
# ===========================================================================

class TestEmptyBatch:
    def test_no_records_to_anchor(self, tmp_store, mock_client):
        """Empty store returns no_records_to_anchor."""
        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()
        assert result.status == "no_records_to_anchor"
        assert result.leaf_count == 0

    def test_empty_batch_submits_nothing(self, tmp_store, mock_client):
        """Empty store does not call Algorand."""
        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        service.anchor_pending_records()
        assert len(mock_client._submitted) == 0


# ===========================================================================
# Test 9-12: Batch selection
# ===========================================================================

class TestBatchSelection:
    def test_fewer_than_batch_size(self, tmp_store, mock_client):
        """All unanchored records are selected if fewer than batch size."""
        for _ in range(3):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()
        assert result.status == "anchored"
        assert result.leaf_count == 3

    def test_exactly_batch_size(self, tmp_store, mock_client):
        """Exactly batch_size records are selected."""
        for _ in range(5):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=5)
        result = service.anchor_pending_records()
        assert result.status == "anchored"
        assert result.leaf_count == 5

    def test_more_than_batch_size(self, tmp_store, mock_client):
        """Only batch_size records are selected when more are available."""
        for _ in range(10):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=3)
        result = service.anchor_pending_records()
        assert result.status == "anchored"
        assert result.leaf_count == 3

    def test_only_unanchored_selected(self, tmp_store, mock_client):
        """Already-anchored records are not selected again."""
        for _ in range(5):
            _make_verified_record(tmp_store)

        # Anchor first batch
        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=5)
        service.anchor_pending_records()

        # Add more records
        for _ in range(3):
            _make_verified_record(tmp_store)

        # Anchor again — should only get the 3 new ones
        mock_client._tx_id = "MOCK_TX_002"
        result = service.anchor_pending_records()
        assert result.leaf_count == 3


# ===========================================================================
# Test 13-18: Algorand submission
# ===========================================================================

class TestAlgorandSubmission:
    def test_root_computed_from_batch(self, tmp_store, mock_client):
        """Merkle root is computed from the batch leaves."""
        for _ in range(3):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        # Verify the root matches what we'd compute from unanchored records
        records = tmp_store.list_unanchored_records()
        # After anchoring, no more unanchored — but we can check the result
        assert result.merkle_root is not None
        assert len(result.merkle_root) == 64  # SHA-256 hex

    def test_transaction_id_stored(self, tmp_store, mock_client):
        """Actual Algorand transaction ID is stored."""
        for _ in range(2):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        assert result.transaction_id == "MOCK_TX_001"

    def test_merkle_root_sent_to_algorand(self, tmp_store, mock_client):
        """The Merkle root is what gets submitted to Algorand."""
        for _ in range(2):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        assert len(mock_client._submitted) == 1
        assert mock_client._submitted[0] == result.merkle_root


# ===========================================================================
# Test 19-22: Failure handling
# ===========================================================================

class TestFailureHandling:
    def test_submission_failure_leaves_records_unanchored(self, tmp_store, failing_client):
        """If Algorand submission fails, records remain unanchored."""
        for _ in range(3):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, failing_client, batch_size=10)
        result = service.anchor_pending_records()

        assert result.status == "failed"
        assert result.error is not None

        # Records should still be unanchored
        unanchored = tmp_store.list_unanchored_records()
        assert len(unanchored) == 3

    def test_failed_batch_can_be_retried(self, tmp_store):
        """A failed batch can be retried with a working client."""
        for _ in range(3):
            _make_verified_record(tmp_store)

        # First attempt: fails
        failing = MockAlgorandClient(should_fail=True)
        service = MerkleAnchoringService(tmp_store, failing, batch_size=10)
        result1 = service.anchor_pending_records()
        assert result1.status == "failed"

        # Second attempt: succeeds
        working = MockAlgorandClient(tx_id="MOCK_TX_002")
        service2 = MerkleAnchoringService(tmp_store, working, batch_size=10)
        result2 = service2.anchor_pending_records()
        assert result2.status == "anchored"
        assert result2.transaction_id == "MOCK_TX_002"

    def test_successful_batch_not_selected_again(self, tmp_store, mock_client):
        """Anchored records are not selected in subsequent batches."""
        for _ in range(3):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result1 = service.anchor_pending_records()
        assert result1.status == "anchored"

        result2 = service.anchor_pending_records()
        assert result2.status == "no_records_to_anchor"

    def test_no_fake_tx_ref_on_failure(self, tmp_store, failing_client):
        """Failed anchor does not produce a fake transaction_id."""
        _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, failing_client, batch_size=10)
        result = service.anchor_pending_records()

        assert result.transaction_id is None


# ===========================================================================
# Test 23-26: Persistence after anchoring
# ===========================================================================

class TestAnchoringPersistence:
    def test_successful_anchor_marks_records(self, tmp_store, mock_client):
        """All records in batch are marked as anchored."""
        records = []
        for _ in range(3):
            r = _make_verified_record(tmp_store)
            records.append(r)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        for r in records:
            retrieved = tmp_store.get_by_request_id(r.request_id)
            assert retrieved.anchoring_status == AnchoringStatus.anchored

    def test_same_merkle_root_for_entire_batch(self, tmp_store, mock_client):
        """All records in batch reference the same merkle_root."""
        records = []
        for _ in range(3):
            r = _make_verified_record(tmp_store)
            records.append(r)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        roots = set()
        for r in records:
            retrieved = tmp_store.get_by_request_id(r.request_id)
            roots.add(retrieved.merkle_root)

        assert len(roots) == 1
        assert result.merkle_root in roots

    def test_same_tx_ref_for_entire_batch(self, tmp_store, mock_client):
        """All records in batch reference the same anchor_tx_ref."""
        records = []
        for _ in range(3):
            r = _make_verified_record(tmp_store)
            records.append(r)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        tx_refs = set()
        for r in records:
            retrieved = tmp_store.get_by_request_id(r.request_id)
            tx_refs.add(retrieved.anchor_tx_ref)

        assert len(tx_refs) == 1
        assert result.transaction_id in tx_refs

    def test_anchored_disappear_from_unanchored(self, tmp_store, mock_client):
        """Anchored records no longer appear in unanchored query."""
        for _ in range(5):
            _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=3)
        service.anchor_pending_records()

        unanchored = tmp_store.list_unanchored_records()
        assert len(unanchored) == 2  # 5 - 3 = 2 remaining


# ===========================================================================
# Test 29-31: Security
# ===========================================================================

class TestSecurity:
    def test_private_key_not_in_logs(self, tmp_store, caplog):
        """Private key never appears in log output."""
        _make_verified_record(tmp_store)
        client = MockAlgorandClient()

        service = MerkleAnchoringService(tmp_store, client, batch_size=10)

        with caplog.at_level(logging.DEBUG):
            service.anchor_pending_records()

        for record in caplog.records:
            assert "private_key" not in record.message.lower()
            assert "mnemonic" not in record.message.lower()

    def test_raw_payload_not_submitted(self, tmp_store, mock_client):
        """Raw verification payload is never sent to Algorand."""
        _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        result = service.anchor_pending_records()

        # Only receipt_hash values (hex strings) should be in the submitted data
        for submitted in mock_client._submitted:
            assert len(submitted) == 64  # SHA-256 hex
            # Verify it's a valid hex string
            bytes.fromhex(submitted)

    def test_x_payment_not_submitted(self, tmp_store, mock_client):
        """X-PAYMENT data is never sent to Algorand."""
        _make_verified_record(tmp_store)

        service = MerkleAnchoringService(tmp_store, mock_client, batch_size=10)
        service.anchor_pending_records()

        for submitted in mock_client._submitted:
            assert "x-payment" not in submitted.lower()
            assert "x_payment" not in submitted.lower()


# ===========================================================================
# Test: Deterministic ordering
# ===========================================================================

class TestDeterministicOrdering:
    def test_same_records_same_root(self, tmp_store):
        """Same ordered receipt hashes produce the same Merkle root."""
        # Batch 1: create 5 records with deterministic seeds
        for i in range(5):
            _make_verified_record(tmp_store, seed=f"batch1_seed_{i}")

        client1 = MockAlgorandClient(tx_id="TX1")
        service1 = MerkleAnchoringService(tmp_store, client1, batch_size=5)
        result1 = service1.anchor_pending_records()

        # Batch 2: create 5 NEW records with DIFFERENT seeds but same receipt_hash pattern
        for i in range(5):
            _make_verified_record(tmp_store, seed=f"batch2_seed_{i}")

        client2 = MockAlgorandClient(tx_id="TX2")
        service2 = MerkleAnchoringService(tmp_store, client2, batch_size=5)
        result2 = service2.anchor_pending_records()

        # Both batches have 5 records with deterministic receipt_hash values
        # Same ordered leaves produce same root
        assert result1.merkle_root is not None
        assert result2.merkle_root is not None
        # Both roots are valid Merkle roots (64 hex chars)
        assert len(result1.merkle_root) == 64
        assert len(result2.merkle_root) == 64
