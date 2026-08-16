import copy
import json
import hashlib
from typing import Tuple, List, Optional
from uuid import uuid4

from jsonschema import validators

from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding, RepairInfo
from app.models.enums import RepairType

def _get_default_validator(schema_definition):
    validator_class = validators.validator_for(schema_definition)
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(validator, properties, instance, schema):
            yield error

    return validators.extend(validator_class, {"properties": set_defaults})

class DeterministicRepairEngine:
    def attempt_repair(self, request: VerificationRequest, policy: SchemaPolicy, findings: List[ValidationFinding]) -> Tuple[dict, Optional[RepairInfo]]:
        """
        Attempts to deterministically repair the payload using only safe, supported rules.
        For MVP, the only supported rule is filling schema-defined default values.
        """
        if not findings:
            return request.output_payload, None

        # 1. Deep copy the payload to preserve immutability
        repaired_payload = copy.deepcopy(request.output_payload)
        
        # 2. Hash pre-repair payload
        pre_repair_str = json.dumps(request.output_payload, sort_keys=True)
        pre_repair_hash = hashlib.sha256(pre_repair_str.encode("utf-8")).hexdigest()

        # 3. Apply schema-defined defaults
        DefaultValidatingValidator = _get_default_validator(policy.schema_definition)
        validator = DefaultValidatingValidator(policy.schema_definition)
        # We only care about mutation, not the errors it yields (that's for VerificationEngine)
        list(validator.iter_errors(repaired_payload))

        # 4. Check if anything changed
        post_repair_str = json.dumps(repaired_payload, sort_keys=True)
        post_repair_hash = hashlib.sha256(post_repair_str.encode("utf-8")).hexdigest()

        if pre_repair_hash == post_repair_hash:
            return request.output_payload, None

        # 5. Populate RepairInfo
        # In a more advanced implementation, we would map exact finding IDs to exact property changes.
        # For MVP, we attribute the repair to all blocking schema findings since defaults fix missing fields.
        addressed_finding_ids = [str(f.finding_id) for f in findings if "required property" in f.description.lower()]

        repair_info = RepairInfo(
            repair_id=uuid4(),
            repair_type=RepairType.deterministic,
            findings_addressed=addressed_finding_ids,
            pre_repair_output_hash=pre_repair_hash,
            post_repair_output_hash=post_repair_hash,
            deterministic_rule_refs=["schema_defaults"]
        )

        return repaired_payload, repair_info
