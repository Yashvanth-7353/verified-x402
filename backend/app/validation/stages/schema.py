from typing import List
from uuid import uuid4
import jsonschema

from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding
from app.models.enums import ValidationStage as StageEnum
from app.models.enums import Severity, Repairability
from app.validation.stages.base import ValidationStage

class SchemaValidationStage(ValidationStage):
    def validate(self, request: VerificationRequest, policy: SchemaPolicy) -> List[ValidationFinding]:
        findings = []
        
        validator_cls = jsonschema.validators.validator_for(policy.schema_definition)
        try:
            validator_cls.check_schema(policy.schema_definition)
        except jsonschema.exceptions.SchemaError as e:
            findings.append(ValidationFinding(
                finding_id=uuid4(),
                stage=StageEnum.schema,
                severity=Severity.blocking,
                description=f"Invalid schema: {e.message}",
                repairable=Repairability.not_repairable
            ))
            return findings

        validator = validator_cls(policy.schema_definition)
        for error in validator.iter_errors(request.output_payload):
            path = ".".join([str(p) for p in error.absolute_path]) if error.absolute_path else "$"
            stage_enum = StageEnum.type if error.validator == "type" else StageEnum.schema
            
            # Sanitize description to avoid leaking raw payload values.
            # For type errors, report the expected type and field without the actual value.
            if error.validator == "type":
                description = f"Value at '{path}' is not of type '{error.schema.get('type', 'unknown')}'"
            elif error.validator == "required":
                description = error.message  # Safe: only mentions the property name
            else:
                description = f"Schema violation at '{path}': {error.validator}"

            findings.append(
                ValidationFinding(
                    finding_id=uuid4(),
                    stage=stage_enum,
                    severity=Severity.blocking,
                    description=description,
                    field_path=path,
                    repairable=Repairability.not_repairable
                )
            )

        return findings
