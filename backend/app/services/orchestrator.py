from copy import deepcopy
from typing import Tuple

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt
)
from app.models.enums import VerificationOutcome, Severity
from app.validation.engine import VerificationEngine
from app.repair.deterministic import DeterministicRepairEngine
from app.evidence.receipt import ReceiptService

VALIDATOR_VERSION = "0.1.0"


class VerificationOrchestrator:
    """
    Orchestrates the full local verification flow:
    Validate -> Deterministic Repair (if applicable) -> Revalidate -> Receipt.

    All business logic stays here; the HTTP route is a thin adapter.
    """

    def __init__(self):
        self.verification_engine = VerificationEngine()
        self.deterministic_repair_engine = DeterministicRepairEngine()
        self.receipt_service = ReceiptService()

    def process(
        self, request: VerificationRequest, policy: SchemaPolicy
    ) -> Tuple[VerificationResult, VerificationReceipt]:
        # 1. Initial validation
        result = self.verification_engine.verify_request(
            request, policy, VALIDATOR_VERSION
        )

        final_payload = request.output_payload
        has_blocking = any(
            f.severity == Severity.blocking for f in result.findings
        )
        schema_is_invalid = any(
            f.severity == Severity.blocking and "Invalid schema" in f.description
            for f in result.findings
        )

        # 2. Deterministic repair
        if has_blocking and not schema_is_invalid:
            repaired_payload, repair_info = self.deterministic_repair_engine.attempt_repair(
                request, policy, result.findings
            )

            if repair_info is not None:
                # 3. Revalidate the deterministic repair
                repaired_request = request.model_copy()
                repaired_request.output_payload = repaired_payload

                revalidation_result = self.verification_engine.verify_request(
                    repaired_request, policy, VALIDATOR_VERSION
                )

                has_blocking = any(
                    f.severity == Severity.blocking
                    for f in revalidation_result.findings
                )

                if not has_blocking:
                    revalidation_result.repair_info = repair_info
                    revalidation_result.outcome = VerificationOutcome.verified_repaired
                    result = revalidation_result
                    final_payload = repaired_payload

        # 4. Generate receipt from the final result
        # NOTE: Semantic repair is NOT performed here.
        # It is gated behind the x402 payment flow on the separate
        # /semantic-repair endpoint. The orchestrator only handles
        # local validation + deterministic repair.
        # If blocking findings remain, outcome stays rejected —
        # the frontend shows an escalation button to trigger payment.
        receipt = self.receipt_service.generate_receipt(
            request, policy, result, final_payload
        )

        return result, receipt
