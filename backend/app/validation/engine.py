from uuid import uuid4
from datetime import datetime, timezone
from typing import List

from app.models.verification import VerificationRequest, SchemaPolicy, VerificationResult, ValidationFinding
from app.models.enums import VerificationOutcome, Severity
from app.validation.stages.base import ValidationStage
from app.validation.stages.schema import SchemaValidationStage
from app.validation.stages.stubs import SyntaxValidationStage, SqlSafetyValidationStage, PrivacyValidationStage
from app.validation.stages.business_rules import BusinessRuleValidationStage

class VerificationEngine:
    def __init__(self):
        self.stages: List[ValidationStage] = [
            SchemaValidationStage(),
            SyntaxValidationStage(),
            SqlSafetyValidationStage(),
            PrivacyValidationStage(),
            BusinessRuleValidationStage(),
        ]
        
    def verify_request(self, request: VerificationRequest, policy: SchemaPolicy, validator_version: str) -> VerificationResult:
        all_findings: List[ValidationFinding] = []
        
        for stage in self.stages:
            findings = stage.validate(request, policy)
            all_findings.extend(findings)
            
        has_blocking = any(f.severity == Severity.blocking for f in all_findings)
        
        outcome = VerificationOutcome.rejected if has_blocking else VerificationOutcome.verified
        
        rejection_reasons = None
        if has_blocking:
            rejection_reasons = [f.description for f in all_findings if f.severity == Severity.blocking]
            
        return VerificationResult(
            result_id=uuid4(),
            request_ref=str(request.request_id),
            findings=all_findings,
            outcome=outcome,
            rejection_reasons=rejection_reasons,
            validator_version=validator_version,
            completed_at=datetime.now(timezone.utc)
        )
