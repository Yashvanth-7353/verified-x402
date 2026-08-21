"""
Phase 13: Independent Receipt Verification.

A standalone verifier that proves a signed VerificationReceipt is authentic
and unmodified, using ONLY:

- The signed receipt (JSON dict or string)
- The public verification key (base64-encoded Ed25519)

It does NOT require:
- The receipt-signing private key
- Access to the Verified backend
- SQLite database
- Algorand access
- GoPlausible facilitator

Architecture:
    Signed Receipt
          ↓
    Canonicalize signable fields
          ↓
    Decode Ed25519 signature
          ↓
    Verify with public key
          ↓
    VerificationResult

Signed fields (protected by signature):
- receipt_id
- request_id_ref
- outcome
- output_hash
- schema_ref_and_version
- repair_summary_hash
- validator_version
- issued_at

Excluded from signature (by design):
- receipt_hash (computed from content, Merkle-tree layer)
- signature (the signature itself)
- signature_algorithm (metadata)
- signing_key_id (metadata)

Relationship to Merkle anchoring:
- Receipt signature proves authenticity/integrity of the receipt itself
- Merkle root commits receipt_hash to a batch anchored on Algorand
- Merkle proof proves inclusion in the anchored batch
- These are complementary mechanisms, not replacements
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Optional

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from app.evidence.canonical import canonicalize
from app.evidence.hasher import hash_data

# Algorithm identifier
SIGNATURE_ALGORITHM = "Ed25519"

# Fields excluded from the signed canonical representation
_EXCLUDED_FROM_SIGNATURE = frozenset({
    "receipt_hash",
    "signature",
    "signature_algorithm",
    "signing_key_id",
})


@dataclass(frozen=True)
class VerificationResult:
    """Structured result of independent receipt verification."""
    valid: bool
    signature_valid: bool
    receipt_integrity_valid: bool
    algorithm: Optional[str] = None
    signing_key_id: Optional[str] = None
    details: str = ""


class ReceiptVerifier:
    """
    Independent verifier for signed VerificationReceipts.

    Requires ONLY a public key. Never needs the private signing key.

    Usage:
        verifier = ReceiptVerifier(public_key_b64="abc123...")
        result = verifier.verify(receipt_dict)
        assert result.valid
    """

    def __init__(self, public_key_b64: str):
        """
        Initialize the verifier with a public key.

        Args:
            public_key_b64: Base64-encoded Ed25519 public key (32 bytes).

        Raises:
            ValueError: If the key is invalid.
        """
        try:
            key_bytes = base64.b64decode(public_key_b64)
            if len(key_bytes) != 32:
                raise ValueError(
                    f"Ed25519 public key must be 32 bytes, got {len(key_bytes)}"
                )
            self._verify_key = VerifyKey(key_bytes)
            self._public_key_b64 = public_key_b64
        except Exception as e:
            raise ValueError(f"Invalid public key: {e}") from e

    @property
    def key_id(self) -> str:
        """Key ID: truncated SHA-256 of the public key bytes."""
        return hashlib.sha256(
            base64.b64decode(self._public_key_b64)
        ).hexdigest()[:16]

    @staticmethod
    def _get_signable_bytes(receipt_dict: dict) -> bytes:
        """
        Extract the canonical signable bytes from a receipt.

        Excludes receipt_hash, signature, signature_algorithm, signing_key_id.
        """
        signable = {
            k: v for k, v in receipt_dict.items()
            if k not in _EXCLUDED_FROM_SIGNATURE
        }
        canonical_str = canonicalize(signable)
        return canonical_str.encode("utf-8")

    @staticmethod
    def _verify_receipt_hash(receipt_dict: dict) -> bool:
        """
        Verify the receipt_hash field matches the computed hash of content fields.

        This is a separate check from the signature — it verifies the
        receipt_hash itself is correct (not tampered).
        """
        stored_hash = receipt_dict.get("receipt_hash")
        if not stored_hash:
            return False

        content_for_hash = {
            k: v for k, v in receipt_dict.items()
            if k not in _EXCLUDED_FROM_SIGNATURE
        }
        computed_hash = hash_data(content_for_hash)
        return computed_hash == stored_hash

    def verify(self, receipt_dict: dict) -> VerificationResult:
        """
        Independently verify a signed receipt.

        Checks:
        1. Receipt hash integrity (content hasn't been modified)
        2. Ed25519 signature validity (signed by the expected key)

        Args:
            receipt_dict: The signed receipt as a JSON-serializable dict.

        Returns:
            VerificationResult with detailed verification status.
        """
        # 1. Verify receipt hash integrity
        hash_valid = self._verify_receipt_hash(receipt_dict)

        if not hash_valid:
            return VerificationResult(
                valid=False,
                signature_valid=False,
                receipt_integrity_valid=False,
                algorithm=receipt_dict.get("signature_algorithm"),
                signing_key_id=receipt_dict.get("signing_key_id"),
                details="Receipt hash mismatch — content has been tampered with",
            )

        # 2. Verify signature
        signature_hex = receipt_dict.get("signature")
        if not signature_hex:
            return VerificationResult(
                valid=False,
                signature_valid=False,
                receipt_integrity_valid=True,
                details="Receipt has no signature — cannot verify authenticity",
            )

        try:
            sig_bytes = bytes.fromhex(signature_hex)
        except ValueError:
            return VerificationResult(
                valid=False,
                signature_valid=False,
                receipt_integrity_valid=True,
                algorithm=receipt_dict.get("signature_algorithm"),
                signing_key_id=receipt_dict.get("signing_key_id"),
                details="Malformed signature (not valid hex)",
            )

        signable_bytes = self._get_signable_bytes(receipt_dict)

        try:
            self._verify_key.verify(signable_bytes, sig_bytes)
        except BadSignatureError:
            return VerificationResult(
                valid=False,
                signature_valid=False,
                receipt_integrity_valid=True,
                algorithm=receipt_dict.get("signature_algorithm"),
                signing_key_id=receipt_dict.get("signing_key_id"),
                details="Ed25519 signature verification failed — signature is invalid",
            )
        except Exception as e:
            return VerificationResult(
                valid=False,
                signature_valid=False,
                receipt_integrity_valid=True,
                algorithm=receipt_dict.get("signature_algorithm"),
                signing_key_id=receipt_dict.get("signing_key_id"),
                details=f"Signature verification error: {e}",
            )

        # All checks passed
        return VerificationResult(
            valid=True,
            signature_valid=True,
            receipt_integrity_valid=True,
            algorithm=receipt_dict.get("signature_algorithm"),
            signing_key_id=receipt_dict.get("signing_key_id"),
            details="Receipt verified: hash valid, signature valid",
        )
