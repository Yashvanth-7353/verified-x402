"""
Phase 12: Cryptographic Verification Receipt Signing.

Uses Ed25519 (via PyNaCl) to sign verification receipts.

Signing process:
    receipt_without_signature_and_receipt_hash
        ↓
    canonical bytes (deterministic JSON)
        ↓
    Ed25519 sign(private_key, canonical_bytes)
        ↓
    signature (64-byte Ed25519 signature, hex-encoded)

Verification process:
    signed receipt
        ↓
    extract canonical bytes from receipt (excluding signature + receipt_hash)
        ↓
    Ed25519 verify(public_key, signature, canonical_bytes)
        ↓
    VALID / INVALID

Design decisions (resolves DESIGN.md §12 TBD):
- Algorithm: Ed25519 (128-bit security, fast, compatible with Algorand ecosystem)
- Signed content: canonical JSON of all receipt fields EXCEPT receipt_hash and signature
- receipt_hash is NOT modified by signing (preserves Merkle anchoring compatibility)
- Signature is a separate, independently verifiable layer on top of receipt_hash
- Key pair is separate from payer wallet and anchor wallet

Privacy:
- Private signing key is NEVER stored in SQLite
- Private signing key is NEVER returned by API
- Private signing key is NEVER logged
- Only the public key / key_id is included in signed receipts
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from app.evidence.canonical import canonicalize

logger = logging.getLogger(__name__)

# Algorithm identifier
SIGNATURE_ALGORITHM = "Ed25519"


class ReceiptSigner:
    """
    Ed25519 signer for VerificationReceipts.

    The private key is loaded from configuration and used ONLY for signing.
    Verification uses only the public key and can be done independently.
    """

    def __init__(
        self,
        private_key_b64: Optional[str] = None,
    ):
        """
        Initialize the signer.

        Args:
            private_key_b64: Base64-encoded Ed25519 private key (32 bytes).
                If None, signing is disabled (receipts will have signature=None).
        """
        if private_key_b64:
            try:
                key_bytes = base64.b64decode(private_key_b64)
                if len(key_bytes) != 32:
                    raise ValueError(
                        f"Ed25519 private key must be 32 bytes, got {len(key_bytes)}"
                    )
                self._signing_key = SigningKey(key_bytes)
                self._verify_key = self._signing_key.verify_key
                self._key_id = hashlib.sha256(
                    self._verify_key.encode()
                ).hexdigest()[:16]
                self._enabled = True
                logger.info(
                    "Receipt signer initialized: algorithm=%s key_id=%s",
                    SIGNATURE_ALGORITHM,
                    self._key_id,
                )
            except Exception as e:
                logger.error("Failed to initialize receipt signer: %s", e)
                self._signing_key = None
                self._verify_key = None
                self._key_id = None
                self._enabled = False
        else:
            self._signing_key = None
            self._verify_key = None
            self._key_id = None
            self._enabled = False
            logger.info("Receipt signer disabled (no private key configured)")

    @property
    def enabled(self) -> bool:
        """Whether signing is enabled."""
        return self._enabled

    @property
    def key_id(self) -> Optional[str]:
        """The signing key identifier (truncated SHA-256 of public key)."""
        return self._key_id

    @property
    def public_key_b64(self) -> Optional[str]:
        """Base64-encoded Ed25519 public key (for verification)."""
        if self._verify_key is None:
            return None
        return base64.b64encode(self._verify_key.encode()).decode()

    @property
    def algorithm(self) -> str:
        """The signature algorithm identifier."""
        return SIGNATURE_ALGORITHM

    def _get_signable_bytes(self, receipt_dict: dict) -> bytes:
        """
        Get the canonical bytes that are signed.

        Excludes receipt_hash and signature fields.
        These are the "content" fields that the signature protects.
        """
        signable = dict(receipt_dict)
        signable.pop("receipt_hash", None)
        signable.pop("signature", None)
        signable.pop("signature_algorithm", None)
        signable.pop("signing_key_id", None)
        canonical_str = canonicalize(signable)
        return canonical_str.encode("utf-8")

    def sign_receipt(self, receipt_dict: dict) -> dict:
        """
        Sign a receipt and return the receipt dict with signature fields added.

        Args:
            receipt_dict: The receipt as a dict (with receipt_hash already computed,
                         signature fields not yet set).

        Returns:
            The receipt dict with signature, signature_algorithm, and signing_key_id added.
        """
        if not self._enabled or self._signing_key is None:
            return receipt_dict

        signable_bytes = self._get_signable_bytes(receipt_dict)
        signed = self._signing_key.sign(signable_bytes)
        signature_hex = signed.signature.hex()

        receipt_dict["signature"] = signature_hex
        receipt_dict["signature_algorithm"] = SIGNATURE_ALGORITHM
        receipt_dict["signing_key_id"] = self._key_id

        logger.debug(
            "Receipt signed: key_id=%s algorithm=%s signature=%s...",
            self._key_id,
            SIGNATURE_ALGORITHM,
            signature_hex[:16],
        )

        return receipt_dict

    @staticmethod
    def verify_signature(
        receipt_dict: dict,
        public_key_b64: str,
    ) -> bool:
        """
        Verify a receipt's signature using only the public key.

        This is a STATIC method — it does NOT require the private key.
        Any independent verifier can use this.

        Args:
            receipt_dict: The signed receipt as a dict.
            public_key_b64: Base64-encoded Ed25519 public key.

        Returns:
            True if the signature is valid, False otherwise.
        """
        signature_hex = receipt_dict.get("signature")
        if not signature_hex:
            return False

        try:
            key_bytes = base64.b64decode(public_key_b64)
            verify_key = VerifyKey(key_bytes)

            # Reconstruct signable bytes (same logic as signing)
            signable = dict(receipt_dict)
            signable.pop("receipt_hash", None)
            signable.pop("signature", None)
            signable.pop("signature_algorithm", None)
            signable.pop("signing_key_id", None)
            canonical_str = canonicalize(signable)
            signable_bytes = canonical_str.encode("utf-8")

            # Verify
            sig_bytes = bytes.fromhex(signature_hex)
            verify_key.verify(signable_bytes, sig_bytes)
            return True

        except BadSignatureError:
            return False
        except Exception as e:
            logger.debug("Signature verification failed: %s", e)
            return False

    @staticmethod
    def generate_keypair() -> tuple[str, str]:
        """
        Generate a new Ed25519 keypair.

        Returns:
            Tuple of (private_key_b64, public_key_b64).
        """
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key

        private_b64 = base64.b64encode(bytes(signing_key)).decode()
        public_b64 = base64.b64encode(verify_key.encode()).decode()

        return private_b64, public_b64
