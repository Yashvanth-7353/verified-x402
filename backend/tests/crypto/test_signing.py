"""
Phase 12: Cryptographic Verification Receipt Signing Tests.

Tests cover:
1. Key generation
2. Sign valid receipt
3. Verify valid signature
4. Wrong public key
5. Modified receipt detection
6. Modified signature detection
7. Modified signed field detection
8. Deterministic canonicalization
9. Disabled signer behavior
10. ReceiptService integration
11. API verification endpoint
"""
import base64
import hashlib
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from nacl.signing import SigningKey

from app.crypto.signing import ReceiptSigner
from app.evidence.canonical import canonicalize
from app.evidence.hasher import hash_data
from app.evidence.receipt import ReceiptService
from app.models.enums import VerificationOutcome
from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult,
    VerificationReceipt, VerificationOutcome, OutputType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def keypair():
    """Generate a fresh Ed25519 keypair for testing."""
    return ReceiptSigner.generate_keypair()


@pytest.fixture
def signer(keypair):
    """A ReceiptSigner with a real private key."""
    private_b64, _ = keypair
    return ReceiptSigner(private_key_b64=private_b64)


@pytest.fixture
def disabled_signer():
    """A ReceiptSigner with no key (disabled)."""
    return ReceiptSigner(private_key_b64=None)


@pytest.fixture
def sample_receipt_dict():
    """A sample receipt dict for testing."""
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
def sample_receipt(sample_receipt_dict):
    """A VerificationReceipt with receipt_hash computed."""
    # Compute receipt_hash
    receipt_hash = hash_data(sample_receipt_dict)
    return {**sample_receipt_dict, "receipt_hash": receipt_hash}


# ---------------------------------------------------------------------------
# Test 1: Key generation
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    def test_generate_keypair(self):
        """Can generate a valid Ed25519 keypair."""
        private_b64, public_b64 = ReceiptSigner.generate_keypair()
        assert private_b64
        assert public_b64

        # Verify key sizes
        private_bytes = base64.b64decode(private_b64)
        public_bytes = base64.b64decode(public_b64)
        assert len(private_bytes) == 32
        assert len(public_bytes) == 32

    def test_keypair_uniqueness(self):
        """Two generated keypairs are different."""
        _, pub1 = ReceiptSigner.generate_keypair()
        _, pub2 = ReceiptSigner.generate_keypair()
        assert pub1 != pub2


# ---------------------------------------------------------------------------
# Test 2: Sign valid receipt
# ---------------------------------------------------------------------------

class TestSigning:
    def test_sign_adds_signature_fields(self, signer, sample_receipt):
        """Signing adds signature, algorithm, and key_id to receipt dict."""
        result = signer.sign_receipt(dict(sample_receipt))
        assert result["signature"] is not None
        assert result["signature_algorithm"] == "Ed25519"
        assert result["signing_key_id"] is not None
        assert len(result["signing_key_id"]) == 16  # Truncated SHA-256

    def test_disabled_signer_no_signature(self, disabled_signer, sample_receipt):
        """Disabled signer does not add signature fields."""
        result = disabled_signer.sign_receipt(dict(sample_receipt))
        assert result.get("signature") is None
        assert result.get("signature_algorithm") is None
        assert result.get("signing_key_id") is None

    def test_signature_is_hex_encoded(self, signer, sample_receipt):
        """Signature is a valid hex string."""
        result = signer.sign_receipt(dict(sample_receipt))
        sig = result["signature"]
        assert all(c in "0123456789abcdef" for c in sig)
        assert len(sig) == 128  # 64 bytes = 128 hex chars


# ---------------------------------------------------------------------------
# Test 3: Verify valid signature
# ---------------------------------------------------------------------------

class TestVerification:
    def test_verify_valid_receipt(self, signer, sample_receipt, keypair):
        """Valid receipt with correct public key verifies."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        assert ReceiptSigner.verify_signature(signed, public_b64) is True

    def test_wrong_public_key_fails(self, signer, sample_receipt):
        """Different public key fails verification."""
        _, wrong_pub = ReceiptSigner.generate_keypair()
        signed = signer.sign_receipt(dict(sample_receipt))
        assert ReceiptSigner.verify_signature(signed, wrong_pub) is False

    def test_no_signature_fails(self, sample_receipt, keypair):
        """Receipt without signature fails verification."""
        _, public_b64 = keypair
        assert ReceiptSigner.verify_signature(sample_receipt, public_b64) is False

    def test_invalid_signature_hex_fails(self, signer, sample_receipt, keypair):
        """Corrupted signature hex fails verification."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        # Corrupt one character
        sig_list = list(signed["signature"])
        sig_list[0] = "f" if sig_list[0] != "f" else "0"
        signed["signature"] = "".join(sig_list)
        assert ReceiptSigner.verify_signature(signed, public_b64) is False


# ---------------------------------------------------------------------------
# Test 4: Tamper detection
# ---------------------------------------------------------------------------

class TestTamperDetection:
    def test_modified_outcome_fails(self, signer, sample_receipt, keypair):
        """Changing outcome invalidates signature."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        signed["outcome"] = "rejected"
        assert ReceiptSigner.verify_signature(signed, public_b64) is False

    def test_modified_output_hash_fails(self, signer, sample_receipt, keypair):
        """Changing output_hash invalidates signature."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        signed["output_hash"] = "tampered"
        assert ReceiptSigner.verify_signature(signed, public_b64) is False

    def test_modified_request_id_fails(self, signer, sample_receipt, keypair):
        """Changing request_id_ref invalidates signature."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        signed["request_id_ref"] = str(uuid4())
        assert ReceiptSigner.verify_signature(signed, public_b64) is False

    def test_modified_schema_fails(self, signer, sample_receipt, keypair):
        """Changing schema_ref_and_version invalidates signature."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        signed["schema_ref_and_version"] = "tampered@2.0"
        assert ReceiptSigner.verify_signature(signed, public_b64) is False

    def test_receipt_hash_excluded_from_signed_content(self, signer, sample_receipt, keypair):
        """receipt_hash is excluded from signed content — modifying it does NOT invalidate signature.
        
        This is by design: receipt_hash is computed from the content fields,
        and the signature also covers those same content fields. The receipt_hash
        is a convenience hash for Merkle trees; the signature proves the content.
        """
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        signed["receipt_hash"] = "tampered"
        # Signature still valid because receipt_hash is excluded from signable content
        assert ReceiptSigner.verify_signature(signed, public_b64) is True

    def test_modified_validator_version_fails(self, signer, sample_receipt, keypair):
        """Changing validator_version invalidates signature."""
        _, public_b64 = keypair
        signed = signer.sign_receipt(dict(sample_receipt))
        signed["validator_version"] = "99.0.0"
        assert ReceiptSigner.verify_signature(signed, public_b64) is False


# ---------------------------------------------------------------------------
# Test 5: Deterministic canonicalization
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_signature(self, signer, sample_receipt):
        """Same receipt produces same signature."""
        r1 = signer.sign_receipt(dict(sample_receipt))
        r2 = signer.sign_receipt(dict(sample_receipt))
        assert r1["signature"] == r2["signature"]

    def test_different_input_different_signature(self, signer, keypair):
        """Different receipts produce different signatures."""
        _, public_b64 = keypair
        r1 = signer.sign_receipt({
            **{k: v for k, v in {
                "receipt_id": str(uuid4()),
                "request_id_ref": str(uuid4()),
                "outcome": "verified",
                "output_hash": "aaa",
                "schema_ref_and_version": "s@1",
                "repair_summary_hash": None,
                "validator_version": "0.1.0",
                "issued_at": "2026-01-01T00:00:00Z",
            }.items()},
            "receipt_hash": hash_data({"outcome": "verified"}),
        })
        r2 = signer.sign_receipt({
            **{k: v for k, v in {
                "receipt_id": str(uuid4()),
                "request_id_ref": str(uuid4()),
                "outcome": "rejected",
                "output_hash": "bbb",
                "schema_ref_and_version": "s@2",
                "repair_summary_hash": None,
                "validator_version": "0.2.0",
                "issued_at": "2026-01-02T00:00:00Z",
            }.items()},
            "receipt_hash": hash_data({"outcome": "rejected"}),
        })
        assert r1["signature"] != r2["signature"]

    def test_canonicalization_deterministic(self):
        """canonicalize() produces the same output for the same input."""
        data = {"b": 2, "a": 1, "c": {"z": 26, "a": 1}}
        c1 = canonicalize(data)
        c2 = canonicalize(data)
        assert c1 == c2
        # Keys are sorted
        assert c1.index('"a"') < c1.index('"b"') < c1.index('"c"')


# ---------------------------------------------------------------------------
# Test 6: ReceiptService integration
# ---------------------------------------------------------------------------

class TestReceiptServiceSigning:
    def test_signed_receipt_has_signature(self):
        """ReceiptService generates a signed receipt when key is configured."""
        # This test verifies the integration works if a key is available
        # For unit tests, we test with a generated key
        from unittest.mock import patch

        private_b64, public_b64 = ReceiptSigner.generate_keypair()

        with patch("app.evidence.receipt.settings") as mock_settings:
            mock_settings.RECEIPT_SIGNING_PRIVATE_KEY = private_b64
            mock_settings.RECEIPT_SIGNING_PUBLIC_KEY = public_b64
            # Reset module-level signer
            import app.evidence.receipt as receipt_module
            receipt_module._signer = None

            service = ReceiptService()
            request = VerificationRequest(
                request_id=uuid4(),
                submitted_at=datetime.now(timezone.utc),
                output_type=OutputType.json,
                output_payload={"test": True},
                schema_ref="test",
                agent_identifier="test",
            )
            policy = SchemaPolicy(
                schema_id=uuid4(),
                version="1.0",
                output_type=OutputType.json,
                schema_definition={"type": "object"},
                privacy_policy_ref="default",
            )
            result = VerificationResult(
                result_id=uuid4(),
                request_ref=str(request.request_id),
                findings=[],
                outcome=VerificationOutcome.verified,
                validator_version="0.1.0",
                completed_at=datetime.now(timezone.utc),
            )
            receipt = service.generate_receipt(request, policy, result, {"test": True})

            assert receipt.signature is not None
            assert receipt.signature_algorithm == "Ed25519"
            assert receipt.signing_key_id is not None

            # Verify the signature
            assert ReceiptSigner.verify_signature(
                receipt.model_dump(mode="json"),
                public_b64,
            ) is True

    def test_unsigned_receipt_when_no_key(self):
        """ReceiptService generates unsigned receipt when no key is configured."""
        from unittest.mock import patch

        with patch("app.evidence.receipt.settings") as mock_settings:
            mock_settings.RECEIPT_SIGNING_PRIVATE_KEY = ""
            mock_settings.RECEIPT_SIGNING_PUBLIC_KEY = ""
            import app.evidence.receipt as receipt_module
            receipt_module._signer = None

            service = ReceiptService()
            request = VerificationRequest(
                request_id=uuid4(),
                submitted_at=datetime.now(timezone.utc),
                output_type=OutputType.json,
                output_payload={"test": True},
                schema_ref="test",
                agent_identifier="test",
            )
            policy = SchemaPolicy(
                schema_id=uuid4(),
                version="1.0",
                output_type=OutputType.json,
                schema_definition={"type": "object"},
                privacy_policy_ref="default",
            )
            result = VerificationResult(
                result_id=uuid4(),
                request_ref=str(request.request_id),
                findings=[],
                outcome=VerificationOutcome.verified,
                validator_version="0.1.0",
                completed_at=datetime.now(timezone.utc),
            )
            receipt = service.generate_receipt(request, policy, result, {"test": True})

            assert receipt.signature is None
            assert receipt.signature_algorithm is None
            assert receipt.signing_key_id is None


# ---------------------------------------------------------------------------
# Test 7: receipt_hash independence from signature
# ---------------------------------------------------------------------------

class TestReceiptHashIndependence:
    def test_receipt_hash_excludes_signature(self, signer):
        """receipt_hash is the same whether or not signature is present."""
        # Build a raw receipt dict (using strings for consistency)
        raw = {
            "receipt_id": str(uuid4()),
            "request_id_ref": str(uuid4()),
            "outcome": "verified",
            "output_hash": hashlib.sha256(b"test").hexdigest(),
            "schema_ref_and_version": "test_schema@1.0",
            "repair_summary_hash": None,
            "validator_version": "0.1.0",
            "issued_at": "2026-01-01T00:00:00Z",
        }

        # Compute receipt_hash from raw dict
        receipt_hash = hash_data(raw)
        raw["receipt_hash"] = receipt_hash

        # Sign the receipt
        signed = signer.sign_receipt(dict(raw))

        # Verify receipt_hash still matches
        signed_for_hash = dict(signed)
        signed_for_hash.pop("receipt_hash", None)
        signed_for_hash.pop("signature", None)
        signed_for_hash.pop("signature_algorithm", None)
        signed_for_hash.pop("signing_key_id", None)
        assert hash_data(signed_for_hash) == receipt_hash

    def test_signature_does_not_change_receipt_hash(self, signer):
        """Signing does not modify the receipt_hash."""
        r1 = signer.sign_receipt(dict({
            "receipt_id": str(uuid4()),
            "request_id_ref": str(uuid4()),
            "outcome": "verified",
            "output_hash": "abc",
            "schema_ref_and_version": "s@1",
            "repair_summary_hash": None,
            "validator_version": "0.1.0",
            "issued_at": "2026-01-01T00:00:00Z",
            "receipt_hash": "expected_hash",
            "signature": None,
            "signature_algorithm": None,
            "signing_key_id": None,
        }))
        assert r1["receipt_hash"] == "expected_hash"


# ---------------------------------------------------------------------------
# Test 8: Security properties
# ---------------------------------------------------------------------------

class TestSecurity:
    def test_private_key_not_in_receipt(self, signer, sample_receipt):
        """Signing never exposes the private key in the receipt."""
        signed = signer.sign_receipt(dict(sample_receipt))
        private_key = base64.b64encode(bytes(signer._signing_key)).decode()
        assert private_key not in str(signed)

    def test_key_id_is_deterministic(self, keypair):
        """Key ID is deterministic for the same key."""
        private_b64, _ = keypair
        s1 = ReceiptSigner(private_key_b64=private_b64)
        s2 = ReceiptSigner(private_key_b64=private_b64)
        assert s1.key_id == s2.key_id

    def test_different_keys_different_key_ids(self):
        """Different keys produce different key IDs."""
        _, s1 = ReceiptSigner.generate_keypair()
        _, s2 = ReceiptSigner.generate_keypair()
        signer1 = ReceiptSigner(private_key_b64=s1)
        signer2 = ReceiptSigner(private_key_b64=s2)
        assert signer1.key_id != signer2.key_id
