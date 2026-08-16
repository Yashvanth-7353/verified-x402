from typing import List
from uuid import uuid4

from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding
from app.models.enums import ValidationStage as StageEnum
from app.models.enums import Severity, Repairability
from app.validation.stages.base import ValidationStage

class SyntaxValidationStage(ValidationStage):
    def validate(self, request: VerificationRequest, policy: SchemaPolicy) -> List[ValidationFinding]:
        # As per corrections, output_payload is already a parsed dictionary.
        # Syntax validation is not observable.
        return [
            ValidationFinding(
                finding_id=uuid4(),
                stage=StageEnum.syntax,
                severity=Severity.info,
                description="Syntax validation not observable since payload is a parsed dictionary.",
                repairable=Repairability.not_repairable
            )
        ]

class SqlSafetyValidationStage(ValidationStage):
    def validate(self, request: VerificationRequest, policy: SchemaPolicy) -> List[ValidationFinding]:
        return [
            ValidationFinding(
                finding_id=uuid4(),
                stage=StageEnum.sql_safety,
                severity=Severity.info,
                description="SQL Safety validation not evaluated due to TBD ruleset.",
                repairable=Repairability.not_repairable
            )
        ]

class PrivacyValidationStage(ValidationStage):
    def validate(self, request: VerificationRequest, policy: SchemaPolicy) -> List[ValidationFinding]:
        return [
            ValidationFinding(
                finding_id=uuid4(),
                stage=StageEnum.privacy,
                severity=Severity.info,
                description="Privacy validation not evaluated due to TBD ruleset.",
                repairable=Repairability.not_repairable
            )
        ]
