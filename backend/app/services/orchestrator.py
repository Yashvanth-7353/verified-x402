from copy import deepcopy
from typing import Tuple

from app.models.verification import (
    VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt
)
from app.models.enums import VerificationOutcome, Severity
from app.validation.engine import VerificationEngine
from app.repair.deterministic import DeterministicRepairEngine
from app.repair.semantic import SemanticRepairEngine
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
        self.semantic_repair_engine = SemanticRepairEngine()
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

        # 4. Semantic repair if blocking findings remain and schema is valid
        if has_blocking and not schema_is_invalid:
            candidate_payload, sem_repair_info = self.semantic_repair_engine.attempt_repair(
                request, policy, result.findings
            )

            if sem_repair_info is not None:
                # 5. Revalidate semantic repair
                repaired_request = request.model_copy()
                repaired_request.output_payload = candidate_payload

                revalidation_result = self.verification_engine.verify_request(
                    repaired_request, policy, VALIDATOR_VERSION
                )

                revalidation_has_blocking = any(
                    f.severity == Severity.blocking
                    for f in revalidation_result.findings
                )

                if not revalidation_has_blocking:
                    revalidation_result.repair_info = sem_repair_info
                    revalidation_result.outcome = VerificationOutcome.verified_repaired
                    result = revalidation_result
                    final_payload = candidate_payload

        # 6. Generate receipt from the final result
        receipt = self.receipt_service.generate_receipt(
            request, policy, result, final_payload
        )

        return result, receipt
