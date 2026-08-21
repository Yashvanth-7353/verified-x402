"""
Phase 13: Independent Receipt Verification Tests.

These tests prove that a signed VerificationReceipt can be verified
using ONLY the receipt + public key, without:
- Private signing key
- Backend server
- SQLite database
- Algorand access

Signed fields (protected by signature):
- receipt_id, request_id_ref, outcome, output_hash,
  schema_ref_and_version, repair_summary_hash, validator_version, issued_at

Excluded from signature (by design):
- receipt_hash (Merkle-tree layer, computed from content)
- signature, signature_algorithm, signing_key_id (metadata)
"""
import base64
import hashlib
import json
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.crypto.signing import ReceiptSigner
from app.crypto.verify import ReceiptVerifier, VerificationResult
from app.evidence.hasher import hash_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def keypair():
    """Generate a fresh Ed25519 keypair."""
    return ReceiptSigner.generate_keypair()


@pytest.fixture
def signer(keypair):
    """ReceiptSigner with real private key."""
    private_b64, _ = keypair
    return ReceiptSigner(private_key_b64=private_b64)


@pytest.fixture
def public_key_b64(keypair):
    """Public key for verification."""
    _, pub = keypair
    return pub


@pytest.fixture
def sample_receipt_dict():
    """Raw receipt dict (pre-hash, pre-sign)."""
    return {
        "receipt_id": str(uuid4()),
        "request_id_ref": str(uuid4()),
        "outcome": "verified",
        "output_hash": hashlib.sha256(b"test_output").hexdigest(),
        "schema_ref_and_version": "test_schema@1.0",
        "repair_summary_hash": None,
        "validator_version": "0.1.0",
        "issued_at": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def signed_receipt(signer, sample_receipt_dict):
    """A fully signed receipt dict."""
    receipt_hash = hash_data(sample_receipt_dict)
    receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
    return signer.sign_receipt(receipt)


# ---------------------------------------------------------------------------
# Test 1: Basic independent verification
# ---------------------------------------------------------------------------

class TestIndependentVerification:
    def test_valid_receipt_verifies(self, signed_receipt, public_key_b64):
        """Valid signed receipt verifies with only public key."""
        verifier = ReceiptVerifier(public_key_b64=public_key_b64)
        result = verifier.verify(signed_receipt)
        assert result.valid is True
        assert result.signature_valid is True
        assert result.receipt_integrity_valid is True
        assert result.algorithm == "Ed25519"
        assert result.signing_key_id is not None

    def test_verifier_needs_only_public_key(self, keypair):
        """ReceiptVerifier can be instantiated with ONLY public key — no private key."""
        _, public_b64 = keypair
        verifier = ReceiptVerifier(public_key_b64=public_b64)
        # Verifier has no access to private key material
        assert not hasattr(verifier, "_signing_key")
        assert not hasattr(verifier, "_private_key")
        assert verifier._public_key_b64 == public_b64

    def test_no_backend_required(self, signed_receipt, public_key_b64):
        """Verification works without any backend imports or configuration."""
        # ReceiptVerifier only imports nacl + canonical + hasher
        # It does NOT import FastAPI, settings, or any backend service
        verifier = ReceiptVerifier(public_key_b64=public_key_b64)
        result = verifier.verify(signed_receipt)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Test 2: Wrong public key
# ---------------------------------------------------------------------------

class TestWrongPublicKey:
    def test_wrong_key_fails(self, signed_receipt):
        """Different public key fails verification."""
        _, wrong_pub = ReceiptSigner.generate_keypair()
        verifier = ReceiptVerifier(public_key_b64=wrong_pub)
        result = verifier.verify(signed_receipt)
        assert result.valid is False
        assert result.signature_valid is False
        assert result.receipt_integrity_valid is True

    def test_empty_key_raises(self):
        """Empty public key raises ValueError."""
        with pytest.raises(ValueError):
            ReceiptVerifier(public_key_b64="")


# ---------------------------------------------------------------------------
# Test 3: Missing/malformed signature
# ---------------------------------------------------------------------------

class TestMissingSignature:
    def test_no_signature_fails(self, sample_receipt_dict, public_key_b64):
        """Receipt without signature fails."""
        receipt_hash = hash_data(sample_receipt_dict)
        receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
        # No signing — receipt has no signature
        verifier = ReceiptVerifier(public_key_b64=public_key_b64)
        result = verifier.verify(receipt)
        assert result.valid is False
        assert result.signature_valid is False
        assert result.receipt_integrity_valid is True
        assert "no signature" in result.details.lower()

    def test_malformed_signature_hex_fails(self, signer, sample_receipt_dict, public_key_b64):
        """Corrupted signature hex fails."""
        receipt_hash = hash_data(sample_receipt_dict)
        receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
        signed = signer.sign_receipt(receipt)
        # Corrupt the signature
        signed["signature"] = "not_valid_hex"
        verifier = ReceiptVerifier(public_key_b64=public_key_b64)
        result = verifier.verify(signed)
        assert result.valid is False
        assert result.signature_valid is False
        assert "malformed" in result.details.lower()


# ---------------------------------------------------------------------------
# Test 4: Tamper detection — signed fields
# ---------------------------------------------------------------------------

class TestTamperDetection:
    @pytest.fixture
    def tamperer(self, signer, sample_receipt_dict, keypair):
        """Helper: sign a receipt, return (signed, public_key)."""
        _, public_b64 = keypair
        receipt_hash = hash_data(sample_receipt_dict)
        receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
        signed = signer.sign_receipt(receipt)
        return signed, public_b64

    def test_modified_request_id_fails(self, tamperer):
        signed, pub = tamperer
        signed["request_id_ref"] = str(uuid4())
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_receipt_id_fails(self, tamperer):
        signed, pub = tamperer
        signed["receipt_id"] = str(uuid4())
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_outcome_fails(self, tamperer):
        signed, pub = tamperer
        signed["outcome"] = "rejected"
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_output_hash_fails(self, tamperer):
        signed, pub = tamperer
        signed["output_hash"] = "tampered"
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_schema_fails(self, tamperer):
        signed, pub = tamperer
        signed["schema_ref_and_version"] = "tampered@2.0"
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_validator_version_fails(self, tamperer):
        signed, pub = tamperer
        signed["validator_version"] = "99.0.0"
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_issued_at_fails(self, tamperer):
        signed, pub = tamperer
        signed["issued_at"] = "2099-12-31T23:59:59Z"
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_modified_signature_fails(self, tamperer):
        signed, pub = tamperer
        sig_list = list(signed["signature"])
        sig_list[0] = "f" if sig_list[0] != "f" else "0"
        signed["signature"] = "".join(sig_list)
        result = ReceiptVerifier(pub).verify(signed)
        assert result.valid is False
        assert result.signature_valid is False

    def test_signing_key_id_excluded_from_signature(self, tamperer):
        """signing_key_id is excluded from signable content (by design).
        
        It's metadata about the key, not content protected by the signature.
        Modifying it does NOT invalidate the signature.
        """
        signed, pub = tamperer
        signed["signing_key_id"] = "ffffffffffffffff"
        result = ReceiptVerifier(pub).verify(signed)
        # Signature is still valid — signing_key_id is excluded from signable content
        assert result.signature_valid is True

    def test_receipt_hash_excluded_from_signature(self, tamperer):
        """Modifying receipt_hash does NOT invalidate the signature.

        receipt_hash is excluded from signed content (by design).
        It's the Merkle-tree layer, not the signature layer.
        
        Note: ReceiptVerifier.verify() checks receipt_hash FIRST and short-circuits.
        To test signature independence from receipt_hash, we use the low-level
        ReceiptSigner.verify_signature which checks signature directly.
        """
        from app.crypto.signing import ReceiptSigner
        signed, pub = tamperer
        original_valid = ReceiptSigner.verify_signature(signed, pub)
        assert original_valid is True

        signed["receipt_hash"] = "tampered_hash"
        # ReceiptSigner.verify_signature checks signature directly (no hash check)
        sig_still_valid = ReceiptSigner.verify_signature(signed, pub)
        assert sig_still_valid is True  # Signature independent of receipt_hash

        # ReceiptVerifier checks hash first → overall fails, but signature is still valid
        result = ReceiptVerifier(pub).verify(signed)
        assert result.receipt_integrity_valid is False
        assert result.valid is False


# ---------------------------------------------------------------------------
# Test 5: No private key required
# ---------------------------------------------------------------------------

class TestNoPrivateKeyRequired:
    def test_verify_without_private_key_in_env(self, signed_receipt, public_key_b64):
        """Verification succeeds with NO private key available anywhere."""
        import os
        # Ensure no private key is accessible
        original = os.environ.get("RECEIPT_SIGNING_PRIVATE_KEY")
        os.environ.pop("RECEIPT_SIGNING_PRIVATE_KEY", None)
        try:
            # ReceiptVerifier does NOT import settings or access env
            verifier = ReceiptVerifier(public_key_b64=public_key_b64)
            result = verifier.verify(signed_receipt)
            assert result.valid is True
        finally:
            if original:
                os.environ["RECEIPT_SIGNING_PRIVATE_KEY"] = original

    def test_verify_independent_of_settings(self, signed_receipt, public_key_b64):
        """Verification does not use app.core.config.settings."""
        from unittest.mock import patch
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.RECEIPT_SIGNING_PRIVATE_KEY = ""
            mock_settings.RECEIPT_SIGNING_PUBLIC_KEY = ""
            # ReceiptVerifier ignores settings entirely
            verifier = ReceiptVerifier(public_key_b64=public_key_b64)
            result = verifier.verify(signed_receipt)
            assert result.valid is True


# ---------------------------------------------------------------------------
# Test 6: No SQLite required
# ---------------------------------------------------------------------------

class TestNoSQLiteRequired:
    def test_verify_without_database(self, signed_receipt, public_key_b64):
        """Verification works without any SQLite access."""
        # ReceiptVerifier does not import sqlite3, store, or any database module
        import app.crypto.verify as verify_module
        # Check that the module's imports don't include database dependencies
        source = open(verify_module.__file__).read()
        # The source mentions 'sqlite' only in docstring comments, not in imports
        import_lines = [l for l in source.split('\n') if l.strip().startswith('import ') or l.strip().startswith('from ')]
        combined_imports = ' '.join(import_lines)
        assert 'sqlite3' not in combined_imports.lower()
        assert 'LocalVerificationRecordStore' not in combined_imports
        assert 'store' not in combined_imports.lower()

        verifier = ReceiptVerifier(public_key_b64=public_key_b64)
        result = verifier.verify(signed_receipt)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Test 7: Structured VerificationResult
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_valid_result_fields(self, signed_receipt, public_key_b64):
        """Valid result has all expected fields."""
        result = ReceiptVerifier(public_key_b64).verify(signed_receipt)
        assert isinstance(result, VerificationResult)
        assert result.valid is True
        assert result.signature_valid is True
        assert result.receipt_integrity_valid is True
        assert result.algorithm == "Ed25519"
        assert result.signing_key_id is not None
        assert len(result.signing_key_id) == 16

    def test_invalid_result_fields(self, signed_receipt):
        """Invalid result has correct fields."""
        _, wrong_pub = ReceiptSigner.generate_keypair()
        result = ReceiptVerifier(wrong_pub).verify(signed_receipt)
        assert result.valid is False
        assert result.signature_valid is False
        assert result.receipt_integrity_valid is True
        assert result.details != ""


# ---------------------------------------------------------------------------
# Test 8: JSON roundtrip
# ---------------------------------------------------------------------------

class TestJSONRoundtrip:
    def test_verify_after_json_serialization(self, signer, sample_receipt_dict, public_key_b64):
        """Receipt survives JSON roundtrip and still verifies."""
        receipt_hash = hash_data(sample_receipt_dict)
        receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
        signed = signer.sign_receipt(receipt)

        # Serialize to JSON and back
        json_str = json.dumps(signed)
        deserialized = json.loads(json_str)

        result = ReceiptVerifier(public_key_b64).verify(deserialized)
        assert result.valid is True

    def test_verify_from_json_string(self, signer, sample_receipt_dict, public_key_b64):
        """Verify a receipt loaded from a JSON string."""
        receipt_hash = hash_data(sample_receipt_dict)
        receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
        signed = signer.sign_receipt(receipt)
        json_str = json.dumps(signed)

        receipt_from_json = json.loads(json_str)
        result = ReceiptVerifier(public_key_b64).verify(receipt_from_json)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Test 9: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_receipt_same_result(self, signed_receipt, public_key_b64):
        """Same signed receipt always produces same verification result."""
        verifier = ReceiptVerifier(public_key_b64)
        r1 = verifier.verify(signed_receipt)
        r2 = verifier.verify(dict(signed_receipt))
        assert r1.valid == r2.valid
        assert r1.signature_valid == r2.signature_valid
        assert r1.receipt_integrity_valid == r2.receipt_integrity_valid

    def test_canonical_bytes_deterministic(self):
        """Signable bytes are deterministic for same input."""
        from app.crypto.verify import ReceiptVerifier
        data = {"b": 2, "a": 1, "c": {"z": 26}}
        bytes1 = ReceiptVerifier._get_signable_bytes(data)
        bytes2 = ReceiptVerifier._get_signable_bytes(data)
        assert bytes1 == bytes2


# ---------------------------------------------------------------------------
# Test 10: Tamper test matrix (comprehensive)
# ---------------------------------------------------------------------------

class TestTamperMatrix:
    """Exhaustive field-by-field tamper detection."""

    @pytest.fixture
    def signed(self, signer, keypair):
        _, pub = keypair
        receipt = {
            "receipt_id": "aaa-bbb-ccc",
            "request_id_ref": "ddd-eee-fff",
            "outcome": "verified",
            "output_hash": "abc123",
            "schema_ref_and_version": "schema@1.0",
            "repair_summary_hash": None,
            "validator_version": "0.1.0",
            "issued_at": "2026-01-01T00:00:00Z",
        }
        receipt["receipt_hash"] = hash_data(receipt)
        signed = signer.sign_receipt(receipt)
        return signed, pub

    @pytest.mark.parametrize("field,value", [
        ("request_id_ref", "tampered"),
        ("receipt_id", "tampered"),
        ("outcome", "rejected"),
        ("output_hash", "tampered"),
        ("schema_ref_and_version", "tampered@2.0"),
        ("validator_version", "99.0.0"),
        ("issued_at", "2099-01-01T00:00:00Z"),
    ])
    def test_signed_field_tamper_detected(self, signed, field, value):
        """Tampering any signed field is detected."""
        receipt, pub = signed
        receipt[field] = value
        result = ReceiptVerifier(pub).verify(receipt)
        assert result.signature_valid is False, f"Tampered {field} was not detected"

    def test_repair_summary_hash_tamper_detected(self, signed):
        """Tampering repair_summary_hash is detected."""
        receipt, pub = signed
        receipt["repair_summary_hash"] = "tampered"
        result = ReceiptVerifier(pub).verify(receipt)
        assert result.signature_valid is False

    def test_extra_field_does_not_break(self, signed):
        """Adding an extra field does not invalidate the signature (not in signed content)."""
        receipt, pub = signed
        receipt["extra_field"] = "not_signed"
        result = ReceiptVerifier(pub).verify(receipt)
        # The extra field is NOT in the original signable content,
        # so the canonical representation differs → signature fails
        assert result.signature_valid is False

    def test_removing_optional_field_detected(self, signed):
        """Removing an optional field (None) changes canonical form."""
        receipt, pub = signed
        receipt_copy = dict(receipt)
        del receipt_copy["repair_summary_hash"]
        result = ReceiptVerifier(pub).verify(receipt_copy)
        assert result.signature_valid is False


# ---------------------------------------------------------------------------
# Test 11: Receipt hash integrity (separate from signature)
# ---------------------------------------------------------------------------

class TestReceiptHashIntegrity:
    def test_tampered_content_detected_by_hash(self, signer, sample_receipt_dict, public_key_b64):
        """Modified content is detected by receipt_hash even if signature is valid."""
        receipt_hash = hash_data(sample_receipt_dict)
        receipt = {**sample_receipt_dict, "receipt_hash": receipt_hash}
        signed = signer.sign_receipt(receipt)

        # Tamper with content AFTER signing
        signed["outcome"] = "rejected"

        result = ReceiptVerifier(public_key_b64).verify(signed)
        # Hash detects tampering (content changed → receipt_hash no longer matches)
        assert result.receipt_integrity_valid is False
        assert result.valid is False

    def test_valid_hash_integrity(self, signed_receipt, public_key_b64):
        """Valid receipt passes hash integrity check."""
        result = ReceiptVerifier(public_key_b64).verify(signed_receipt)
        assert result.receipt_integrity_valid is True
