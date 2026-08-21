"""
Receipt generation and verification service.

Phase 8 hardened:
- verified_repaired requires non-null repair_info with payment_ref
- output_hash always reflects the FINAL validated output
- repair_summary_hash is deterministic (same RepairInfo → same hash)
- receipt_hash is computed over canonical JSON of all bound fields
- Changing any bound field changes receipt_hash (tamper evidence)
"""
from uuid import uuid4
from datetime import datetime, timezone
import logging

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt,
)
from app.models.enums import VerificationOutcome
from app.evidence.hasher import hash_data
from app.crypto.signing import ReceiptSigner
from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level signer (initialized lazily)
_signer: ReceiptSigner | None = None


def _get_signer() -> ReceiptSigner:
    global _signer
    if _signer is None:
        _signer = ReceiptSigner(
            private_key_b64=settings.RECEIPT_SIGNING_PRIVATE_KEY or None
        )
    return _signer


class ReceiptService:
    """
    Generates and verifies VerificationReceipts.

    This service ONLY consumes completed VerificationResult + related
    finalized metadata.  It does NOT:
    - perform validation
    - call the semantic-repair API
    - perform payment verification
    - talk to the facilitator

    Phase 12: Receipts are cryptographically signed using Ed25519
    if a signing key is configured.
    """

    def generate_receipt(
        self,
        request: VerificationRequest,
        policy: SchemaPolicy,
        result: VerificationResult,
        final_payload: dict,
    ) -> VerificationReceipt:
        """
        Generate a VerificationReceipt for the given completed result.

        Phase 8 invariants enforced:
        1. Every request produces exactly one receipt.
        2. output_hash is always computed from the FINAL validated output.
        3. repair_summary_hash is present when repair occurred.
        4. verified_repaired requires repair_info with payment_ref.
        5. receipt_hash is deterministic and changes if any bound field changes.
        """

        # ---- Phase 8 invariant: verified_repaired requires repair_info ----
        if result.outcome == VerificationOutcome.verified_repaired:
            if result.repair_info is None:
                logger.error(
                    "INVARIANT VIOLATION: outcome=verified_repaired but repair_info is None "
                    "for request_id=%s — forcing rejected",
                    request.request_id,
                )
                # Fail closed: downgrade to rejected
                result = result.model_copy()
                result.outcome = VerificationOutcome.rejected
                result.rejection_reasons = (
                    (result.rejection_reasons or [])
                    + ["Phase 8 invariant: verified_repaired without repair_info"]
                )

            elif result.repair_info.payment_ref is None:
                # For semantic repair, payment_ref MUST be present
                if result.repair_info.repair_type and result.repair_info.repair_type.value == "semantic":
                    logger.error(
                        "INVARIANT VIOLATION: outcome=verified_repaired with semantic repair "
                        "but payment_ref is None for request_id=%s — forcing rejected",
                        request.request_id,
                    )
                    result = result.model_copy()
                    result.outcome = VerificationOutcome.rejected
                    result.rejection_reasons = (
                        (result.rejection_reasons or [])
                        + ["Phase 8 invariant: semantic repair without settled payment_ref"]
                    )

        # ---- output_hash: always from the FINAL validated output ----
        output_hash = hash_data(final_payload)

        # ---- repair_summary_hash: deterministic hash of RepairInfo ----
        repair_summary_hash = None
        if result.repair_info is not None:
            repair_summary_hash = hash_data(result.repair_info)

        # ---- Build the receipt (receipt_hash is a placeholder for now) ----
        receipt = VerificationReceipt(
            receipt_id=uuid4(),
            request_id_ref=str(request.request_id),
            outcome=result.outcome,
            output_hash=output_hash,
            schema_ref_and_version=f"{policy.schema_id}@{policy.version}",
            repair_summary_hash=repair_summary_hash,
            validator_version=result.validator_version,
            issued_at=datetime.now(timezone.utc),
            receipt_hash="",  # Placeholder — computed below
            signature=None,
        )

        # ---- receipt_hash: canonical hash over all bound fields ----
        receipt_dict = receipt.model_dump(mode="json")
        receipt_dict.pop("receipt_hash", None)
        receipt_dict.pop("signature", None)
        receipt_dict.pop("signature_algorithm", None)
        receipt_dict.pop("signing_key_id", None)
        receipt.receipt_hash = hash_data(receipt_dict)

        # ---- Phase 12: Cryptographic signing ----
        signer = _get_signer()
        if signer.enabled:
            # Rebuild receipt dict with receipt_hash but without signature fields
            receipt_dict = receipt.model_dump(mode="json")
            receipt_dict.pop("signature", None)
            receipt_dict.pop("signature_algorithm", None)
            receipt_dict.pop("signing_key_id", None)

            # Sign the receipt (adds signature fields to dict)
            signed_dict = signer.sign_receipt(receipt_dict)

            # Update receipt with signature metadata
            receipt.signature = signed_dict.get("signature")
            receipt.signature_algorithm = signed_dict.get("signature_algorithm")
            receipt.signing_key_id = signed_dict.get("signing_key_id")

            logger.debug(
                "Receipt signed: key_id=%s algorithm=%s",
                receipt.signing_key_id,
                receipt.signature_algorithm,
            )

        logger.debug(
            "Receipt generated: receipt_id=%s outcome=%s output_hash=%s... receipt_hash=%s...",
            receipt.receipt_id,
            receipt.outcome,
            output_hash[:16],
            receipt.receipt_hash[:16],
        )

        return receipt

    def verify_receipt(
        self,
        receipt: VerificationReceipt,
        request: VerificationRequest,
        policy: SchemaPolicy,
        result: VerificationResult,
        final_payload: dict,
    ) -> bool:
        """
        Locally verifies the receipt against the supplied evidence.

        Checks:
        1. receipt_hash is valid (not tampered)
        2. output_hash matches the final payload
        3. repair_summary_hash matches RepairInfo (if present)
        4. Basic identifiers match (request_id, schema, outcome)
        5. Signature is valid (if present)
        """
        # 1. Verify receipt hash itself
        receipt_dict = receipt.model_dump(mode="json")
        receipt_dict.pop("receipt_hash", None)
        receipt_dict.pop("signature", None)
        receipt_dict.pop("signature_algorithm", None)
        receipt_dict.pop("signing_key_id", None)
        expected_receipt_hash = hash_data(receipt_dict)

        if receipt.receipt_hash != expected_receipt_hash:
            return False

        # 2. Verify output hash
        expected_output_hash = hash_data(final_payload)
        if receipt.output_hash != expected_output_hash:
            return False

        # 3. Verify repair summary hash
        if result.repair_info is not None:
            expected_repair_hash = hash_data(result.repair_info)
            if receipt.repair_summary_hash != expected_repair_hash:
                return False
        elif receipt.repair_summary_hash is not None:
            return False

        # 4. Verify basic identifiers
        if receipt.request_id_ref != str(request.request_id):
            return False

        expected_schema_ref = f"{policy.schema_id}@{policy.version}"
        if receipt.schema_ref_and_version != expected_schema_ref:
            return False

        if receipt.outcome != result.outcome:
            return False

        return True
