import copy
import json
import re
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
    """
    Deterministic repair engine.

    Performs ONLY safe, objective, schema-derived transformations:

      Case A — Integer coercion:  "480"  → 480   (schema type=integer)
      Case B — Number coercion:   "480.5"→ 480.5  (schema type=number)
      Case D — Boolean coercion:  "true" → true   (schema type=boolean)
      Case E — Schema defaults:   missing field → schema-defined default value

    Anything that requires interpretation, guessing, or reasoning
    (e.g. "480 USD" → 480, missing field without default) is NOT
    handled here.  Those cases require semantic repair (Groq) or
    must be rejected.
    """

    # ------------------------------------------------------------------
    # Type coercion: value lookup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_int(value) -> Optional[int]:
        """Safely coerce a value to int. Only accepts pure numeric strings
        and actual int/float values — rejects '480 USD', '1,000', etc."""
        if isinstance(value, bool):
            return None  # bool is a subclass of int; never coerce bool→int
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value == int(value):
                return int(value)
            return None  # 480.5 is not a valid integer
        if isinstance(value, str):
            stripped = value.strip()
            # Must be a pure decimal integer: optional sign, digits only
            if re.fullmatch(r"[+-]?\d+", stripped):
                return int(stripped)
        return None

    @staticmethod
    def _coerce_number(value) -> Optional[float]:
        """Safely coerce a value to float (schema type 'number').
        Accepts int, float, and pure numeric strings like '480' or '480.5'.
        Rejects '480 USD', '1,000', etc."""
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            # Pure numeric: optional sign, digits, optional decimal part
            if re.fullmatch(r"[+-]?\d+(\.\d+)?", stripped):
                return float(stripped)
        return None

    @staticmethod
    def _coerce_bool(value) -> Optional[bool]:
        """Safely coerce a value to bool.  Only the exact strings
        'true' and 'false' (case-insensitive) are accepted."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        return None

    @staticmethod
    def _coerce_string(value) -> Optional[str]:
        """Safely coerce a primitive value to string (lossless scalar only).
        Rejects dicts, lists, None."""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return None

    # ------------------------------------------------------------------
    # Coercion dispatch by schema type
    # ------------------------------------------------------------------

    _COERCION_MAP = {
        "integer": _coerce_int,
        "number": _coerce_number,
        "boolean": _coerce_bool,
        "string": _coerce_string,
    }

    @staticmethod
    def _coerce_for_type(value, target_type: str):
        """Attempt to coerce *value* to *target_type*.  Returns coerced value
        or None if the conversion is unsafe/ambiguous."""
        handler = DeterministicRepairEngine._COERCION_MAP.get(target_type)
        if handler is None:
            return None
        return handler(value)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def attempt_repair(
        self,
        request: VerificationRequest,
        policy: SchemaPolicy,
        findings: List[ValidationFinding],
    ) -> Tuple[dict, Optional[RepairInfo]]:
        """
        Attempts to deterministically repair the payload using only safe,
        objective, schema-derived transformations.

        Order of operations:
          1. Apply schema-defined default values for missing fields.
          2. Apply safe type coercion where the schema defines a target type
             and the value can be losslessly converted.
          3. If the payload changed, re-validation is the caller's job.

        Returns (repaired_payload, RepairInfo | None).
        """
        if not findings:
            return request.output_payload, None

        # 1. Deep copy
        repaired_payload = copy.deepcopy(request.output_payload)

        # 2. Pre-repair hash
        pre_repair_hash = hashlib.sha256(
            json.dumps(request.output_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 3. Apply schema-defined defaults (Case E)
        DefaultValidatingValidator = _get_default_validator(policy.schema_definition)
        validator = DefaultValidatingValidator(policy.schema_definition)
        list(validator.iter_errors(repaired_payload))

        # 4. Apply safe type coercion (Cases A, B, C, D)
        self._apply_type_coercion(repaired_payload, policy.schema_definition)

        # 5. Check if anything changed
        post_repair_hash = hashlib.sha256(
            json.dumps(repaired_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        if pre_repair_hash == post_repair_hash:
            return request.output_payload, None

        # 6. Build RepairInfo
        addressed_finding_ids = [
            str(f.finding_id)
            for f in findings
            if f.severity.value == "blocking"
        ]

        repair_info = RepairInfo(
            repair_id=uuid4(),
            repair_type=RepairType.deterministic,
            findings_addressed=addressed_finding_ids,
            pre_repair_output_hash=pre_repair_hash,
            post_repair_output_hash=post_repair_hash,
            deterministic_rule_refs=["schema_defaults", "type_coercion"],
        )

        return repaired_payload, repair_info

    # ------------------------------------------------------------------
    # Internal: walk schema properties and coerce types
    # ------------------------------------------------------------------

    def _apply_type_coercion(self, payload: dict, schema: dict) -> None:
        """Walk the schema's top-level properties.  For each property that
        has a ``type`` declaration, attempt safe type coercion on the
        corresponding value in *payload* (mutates in place)."""
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            expected_type = prop_schema.get("type")
            if expected_type is None or prop_name not in payload:
                continue
            current_value = payload[prop_name]
            coerced = self._coerce_for_type(current_value, expected_type)
            if coerced is not None and coerced != current_value:
                payload[prop_name] = coerced
