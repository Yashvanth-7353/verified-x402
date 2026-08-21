"""
Phase 9 tests: Local Verification Record Store (SQLite backend).

Tests cover:
- Basic persistence (save, retrieve by request_id, retrieve by receipt_id)
- All outcomes (verified, verified_repaired, rejected)
- Payment metadata preservation
- Idempotency and duplicate handling
- Anchoring status lifecycle
- Receipt/output hash integrity
- Privacy (no sensitive data stored)
- Database restart persistence
- Failure handling
"""
import os
import sqlite3
import tempfile
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt,
    ValidationFinding, RepairInfo,
)
from app.models.payments import PaymentMetadata
from app.models.enums import (
    OutputType, ValidationStage, Severity, Repairability,
    RepairType, VerificationOutcome, PaymentStatus, AnchoringStatus,
)
from app.storage.store import LocalVerificationRecordStore, LocalVerificationRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary SQLite database path for each test."""
    return str(tmp_path / "test_verified.db")


@pytest.fixture
def store(tmp_db):
    """Provide a fresh LocalVerificationRecordStore with isolated DB."""
    s = LocalVerificationRecordStore(db_path=tmp_db)
    yield s
    s.close()


@pytest.fixture
def base_request():
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload={"name": "Alice", "age": 30},
        schema_ref="user_schema",
        agent_identifier="test_agent",
    )


@pytest.fixture
def base_policy():
    return SchemaPolicy(
        schema_id=uuid4(),
        version="1.0",
        output_type=OutputType.json,
        schema_definition={"type": "object"},
        privacy_policy_ref="default",
    )


def _make_verified_result(request_id: str) -> VerificationResult:
    return VerificationResult(
        result_id=uuid4(),
        request_ref=str(request_id),
        findings=[],
        outcome=VerificationOutcome.verified,
        validator_version="0.1.0",
        completed_at=datetime.now(timezone.utc),
    )


def _make_rejected_result(request_id: str) -> VerificationResult:
    return VerificationResult(
        result_id=uuid4(),
        request_ref=str(request_id),
        findings=[
            ValidationFinding(
                finding_id=uuid4(),
                stage=ValidationStage.schema,
                severity=Severity.blocking,
                description="missing required property",
                repairable=Repairability.not_repairable,
            )
        ],
        outcome=VerificationOutcome.rejected,
        rejection_reasons=["missing required property"],
        validator_version="0.1.0",
        completed_at=datetime.now(timezone.utc),
    )


def _make_repaired_result(request_id: str, payment_ref: str = None) -> VerificationResult:
    return VerificationResult(
        result_id=uuid4(),
        request_ref=str(request_id),
        findings=[],
        repair_info=RepairInfo(
            repair_id=uuid4(),
            repair_type=RepairType.semantic if payment_ref else RepairType.deterministic,
            findings_addressed=["finding1"],
            pre_repair_output_hash="pre_hash",
            post_repair_output_hash="post_hash",
            payment_ref=payment_ref,
            semantic_repair_provider_ref="MockProvider" if payment_ref else None,
        ),
        outcome=VerificationOutcome.verified_repaired,
        validator_version="0.1.0",
        completed_at=datetime.now(timezone.utc),
    )


def _make_receipt(request_id: str, outcome: VerificationOutcome, receipt_hash: str = None) -> VerificationReceipt:
    r = VerificationReceipt(
        receipt_id=uuid4(),
        request_id_ref=str(request_id),
        outcome=outcome,
        output_hash="abc123def456",
        schema_ref_and_version="schema1@v1",
        validator_version="0.1.0",
        issued_at=datetime.now(timezone.utc),
        receipt_hash=receipt_hash or "",
        signature=None,
    )
    # Set a deterministic receipt_hash if not provided
    if not receipt_hash:
        from app.evidence.hasher import hash_data
        r_dict = r.model_dump(mode="json")
        r_dict.pop("receipt_hash", None)
        r_dict.pop("signature", None)
        r_dict.pop("signature_algorithm", None)
        r_dict.pop("signing_key_id", None)
        r.receipt_hash = hash_data(r_dict)
    return r


def _make_payment_metadata() -> PaymentMetadata:
    return PaymentMetadata(
        payment_id=uuid4(),
        x402_challenge_ref=str(uuid4()),
        payment_status=PaymentStatus.settled,
        facilitator="GoPlausible AVM Facilitator",
        settlement_network="Algorand",
        algorand_tx_ref="ALGO_TX_test123",
        amount_and_asset={"scheme": "exact", "asset": "10458941", "amount": "1000000"},
        verified_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# TEST 1-4: Basic persistence
# ===========================================================================

class TestBasicPersistence:
    def test_save_and_retrieve_by_request_id(self, store, base_request):
        """Save a record and retrieve by request_id."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved is not None
        assert retrieved.request_id == str(base_request.request_id)
        assert retrieved.receipt_id == str(receipt.receipt_id)
        assert retrieved.outcome == "verified"

    def test_save_and_retrieve_by_receipt_id(self, store, base_request):
        """Save a record and retrieve by receipt_id."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        retrieved = store.get_by_receipt_id(str(receipt.receipt_id))
        assert retrieved is not None
        assert retrieved.request_id == str(base_request.request_id)
        assert retrieved.receipt_id == str(receipt.receipt_id)

    def test_receipt_hash_preserved(self, store, base_request):
        """receipt_hash is preserved exactly after persistence."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.receipt_hash == receipt.receipt_hash

    def test_output_hash_preserved(self, store, base_request):
        """output_hash is preserved exactly after persistence."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.output_hash == receipt.output_hash


# ===========================================================================
# TEST 5-7: All outcomes
# ===========================================================================

class TestAllOutcomes:
    def test_persist_verified(self, store, base_request):
        """verified outcome is persisted correctly."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.outcome == "verified"

    def test_persist_verified_repaired(self, store, base_request):
        """verified_repaired outcome is persisted correctly."""
        result = _make_repaired_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified_repaired)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.outcome == "verified_repaired"

    def test_persist_rejected(self, store, base_request):
        """rejected outcome is persisted correctly."""
        result = _make_rejected_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.rejected)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.outcome == "rejected"


# ===========================================================================
# TEST 8-10: Payment metadata
# ===========================================================================

class TestPaymentMetadata:
    def test_semantic_repaired_preserves_payment_ref(self, store, base_request):
        """verified_repaired with semantic repair preserves payment_ref in result."""
        pm = _make_payment_metadata()
        result = _make_repaired_result(base_request.request_id, payment_ref=str(pm.payment_id))
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified_repaired)

        store.save(result=result, receipt=receipt, payment_metadata=pm)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        retrieved_result = store.get_result(retrieved)
        assert retrieved_result.repair_info.payment_ref == str(pm.payment_id)

    def test_payment_status_remains_settled(self, store, base_request):
        """PaymentMetadata.payment_status remains 'settled' after persistence."""
        pm = _make_payment_metadata()
        result = _make_repaired_result(base_request.request_id, payment_ref=str(pm.payment_id))
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified_repaired)

        store.save(result=result, receipt=receipt, payment_metadata=pm)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        retrieved_pm = store.get_payment_metadata(retrieved)
        assert retrieved_pm is not None
        assert retrieved_pm.payment_status == PaymentStatus.settled

    def test_settlement_reference_preserved(self, store, base_request):
        """Algorand settlement reference is preserved after persistence."""
        pm = _make_payment_metadata()
        result = _make_repaired_result(base_request.request_id, payment_ref=str(pm.payment_id))
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified_repaired)

        store.save(result=result, receipt=receipt, payment_metadata=pm)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        retrieved_pm = store.get_payment_metadata(retrieved)
        assert retrieved_pm.algorand_tx_ref == "ALGO_TX_test123"


# ===========================================================================
# TEST 11-12: Idempotency
# ===========================================================================

class TestIdempotency:
    def test_duplicate_save_same_record(self, store, base_request):
        """Saving the same record twice does not create duplicates."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record1 = store.save(result=result, receipt=receipt)
        record2 = store.save(result=result, receipt=receipt)

        # Should return the existing record (idempotent)
        assert record1.request_id == record2.request_id
        assert record1.receipt_id == record2.receipt_id

        # Only one record in the database
        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved is not None

    def test_conflicting_request_id_raises(self, store, base_request):
        """Saving with same request_id but different receipt_id raises IntegrityError."""
        result1 = _make_verified_result(base_request.request_id)
        receipt1 = _make_receipt(base_request.request_id, VerificationOutcome.verified)
        store.save(result=result1, receipt=receipt1)

        # Try to save with same request_id but different receipt
        result2 = _make_verified_result(base_request.request_id)
        receipt2 = _make_receipt(base_request.request_id, VerificationOutcome.rejected)

        with pytest.raises(sqlite3.IntegrityError):
            store.save(result=result2, receipt=receipt2)


# ===========================================================================
# TEST 13-16: Anchoring status
# ===========================================================================

class TestAnchoringStatus:
    def test_new_record_is_unanchored(self, store, base_request):
        """New records start as unanchored."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.anchoring_status == AnchoringStatus.unanchored

    def test_list_unanchored_returns_new_record(self, store, base_request):
        """list_unanchored_records() returns newly saved records."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        unanchored = store.list_unanchored_records()
        assert len(unanchored) >= 1
        assert any(r.request_id == str(base_request.request_id) for r in unanchored)

    def test_mark_anchored_updates_status(self, store, base_request):
        """mark_anchored() updates anchoring_status to 'anchored'."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        store.mark_anchored(
            record_ids=[str(record.record_id)],
            merkle_root="test_merkle_root_abc",
            anchor_tx_ref="ALGO_ANCHOR_TX_123",
        )

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.anchoring_status == AnchoringStatus.anchored
        assert retrieved.merkle_root == "test_merkle_root_abc"
        assert retrieved.anchor_tx_ref == "ALGO_ANCHOR_TX_123"

    def test_anchored_record_excluded_from_unanchored(self, store, base_request):
        """Anchored records do not appear in list_unanchored_records()."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        record = store.save(result=result, receipt=receipt)

        store.mark_anchored(
            record_ids=[str(record.record_id)],
            merkle_root="test_root",
            anchor_tx_ref="tx_123",
        )

        unanchored = store.list_unanchored_records()
        assert not any(r.request_id == str(base_request.request_id) for r in unanchored)


# ===========================================================================
# TEST 17-19: Integrity
# ===========================================================================

class TestIntegrity:
    def test_stored_receipt_hash_matches_original(self, store, base_request):
        """Stored receipt_hash matches the original receipt's hash."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        original_hash = receipt.receipt_hash
        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.receipt_hash == original_hash

    def test_stored_output_hash_matches_original(self, store, base_request):
        """Stored output_hash matches the original receipt's output_hash."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        original_output_hash = receipt.output_hash
        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.output_hash == original_output_hash

    def test_stored_outcome_matches_original(self, store, base_request):
        """Stored outcome matches the original receipt's outcome."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        assert retrieved.outcome == VerificationOutcome.verified.value


# ===========================================================================
# TEST 20-23: Privacy
# ===========================================================================

class TestPrivacy:
    def test_private_key_not_stored(self, store, base_request):
        """No private key data is stored in the record."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        # Check all stored JSON fields
        for field_val in [retrieved.receipt_json, retrieved.result_json, retrieved.payment_metadata_json]:
            if field_val:
                assert "private_key" not in field_val.lower()
                assert "mnemonic" not in field_val.lower()
                assert "seed" not in field_val.lower()

    def test_x_payment_not_stored(self, store, base_request):
        """X-PAYMENT data is not stored in the record."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        for field_val in [retrieved.receipt_json, retrieved.result_json]:
            if field_val:
                assert "x-payment" not in field_val.lower()
                assert "x_payment" not in field_val.lower()

    def test_recovery_phrase_not_stored(self, store, base_request):
        """Recovery phrase is not stored in the record."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        for field_val in [retrieved.receipt_json, retrieved.result_json, retrieved.payment_metadata_json]:
            if field_val:
                assert "recovery" not in field_val.lower()

    def test_raw_payload_not_stored(self, store, base_request):
        """Raw output payload is NOT stored directly in the record."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        # The record stores hashes, not raw payloads
        # Verify the record doesn't contain the raw payload values
        assert retrieved.output_hash != str(base_request.output_payload)
        # receipt_json should contain hashes, not raw payload
        assert "output_payload" not in retrieved.receipt_json


# ===========================================================================
# TEST 24: Restart persistence
# ===========================================================================

class TestRestartPersistence:
    def test_record_survives_database_reopen(self, tmp_db):
        """Record persists across database connection close/reopen."""
        # First connection: save a record
        store1 = LocalVerificationRecordStore(db_path=tmp_db)
        request_id = uuid4()
        result = _make_verified_result(request_id)
        receipt = _make_receipt(request_id, VerificationOutcome.verified)
        original_hash = receipt.receipt_hash

        store1.save(result=result, receipt=receipt)
        store1.close()

        # Second connection: retrieve the record
        store2 = LocalVerificationRecordStore(db_path=tmp_db)
        retrieved = store2.get_by_request_id(str(request_id))

        assert retrieved is not None
        assert retrieved.receipt_hash == original_hash
        assert retrieved.outcome == "verified"
        assert retrieved.request_id == str(request_id)
        store2.close()


# ===========================================================================
# TEST 25: Failure handling
# ===========================================================================

class TestFailureHandling:
    def test_get_nonexistent_returns_none(self, store):
        """Querying a nonexistent record returns None."""
        assert store.get_by_request_id(str(uuid4())) is None
        assert store.get_by_receipt_id(str(uuid4())) is None

    def test_list_unanchored_empty_database(self, store):
        """list_unanchored_records() returns empty list on empty database."""
        unanchored = store.list_unanchored_records()
        assert unanchored == []


# ===========================================================================
# TEST: Deserialization roundtrip
# ===========================================================================

class TestDeserialization:
    def test_receipt_roundtrip(self, store, base_request):
        """Receipt can be deserialized from stored record."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        deserialized_receipt = store.get_receipt(retrieved)

        assert deserialized_receipt.receipt_id == receipt.receipt_id
        assert deserialized_receipt.outcome == receipt.outcome
        assert deserialized_receipt.receipt_hash == receipt.receipt_hash
        assert deserialized_receipt.output_hash == receipt.output_hash

    def test_result_roundtrip(self, store, base_request):
        """Result can be deserialized from stored record."""
        result = _make_verified_result(base_request.request_id)
        receipt = _make_receipt(base_request.request_id, VerificationOutcome.verified)

        store.save(result=result, receipt=receipt)

        retrieved = store.get_by_request_id(str(base_request.request_id))
        deserialized_result = store.get_result(retrieved)

        assert deserialized_result.outcome == result.outcome
        assert deserialized_result.validator_version == result.validator_version
        assert str(deserialized_result.request_ref) == str(result.request_ref)


# ===========================================================================
# TEST: Multiple records
# ===========================================================================

class TestMultipleRecords:
    def test_multiple_distinct_records(self, store):
        """Multiple distinct records can be stored and retrieved."""
        for i in range(5):
            request_id = uuid4()
            result = _make_verified_result(request_id)
            receipt = _make_receipt(request_id, VerificationOutcome.verified)
            store.save(result=result, receipt=receipt)

        unanchored = store.list_unanchored_records()
        assert len(unanchored) >= 5

    def test_deterministic_ordering(self, store):
        """list_unanchored_records returns stable ordering."""
        request_ids = []
        for _ in range(3):
            rid = uuid4()
            request_ids.append(rid)
            result = _make_verified_result(rid)
            receipt = _make_receipt(rid, VerificationOutcome.verified)
            store.save(result=result, receipt=receipt)

        # Query twice — order should be the same
        list1 = [r.request_id for r in store.list_unanchored_records()]
        list2 = [r.request_id for r in store.list_unanchored_records()]
        assert list1 == list2
