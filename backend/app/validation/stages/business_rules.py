"""
Business-rule validation stage.

Validates domain-specific invariants that go beyond JSON Schema
structure and type correctness.  These are explicit, bounded rules
derived from the schema policy — not LLM inference.

Currently supported rule types:
  - ``financial_consistency``: checks that computed totals in a financial
    report match the expected arithmetic (e.g. grand_total = subtotal −
    discount + tax).

Business-rule findings are classified as:
  - severity: blocking
  - repairable: not_repairable  (deterministic repair cannot reason
    about arithmetic or domain logic; semantic repair is required)

This stage is a no-op when ``policy.business_rules`` is ``None`` or
empty, so existing schemas continue to work unchanged.
"""

from typing import List
from uuid import uuid4

from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding
from app.models.enums import ValidationStage as StageEnum
from app.models.enums import Severity, Repairability
from app.validation.stages.base import ValidationStage


class BusinessRuleValidationStage(ValidationStage):
    """Validates explicit business rules defined in the schema policy."""

    def validate(
        self, request: VerificationRequest, policy: SchemaPolicy
    ) -> List[ValidationFinding]:
        findings: List[ValidationFinding] = []
        rules = policy.business_rules or []

        for rule in rules:
            rule_type = rule.get("type")
            if rule_type == "financial_consistency":
                findings.extend(
                    self._check_financial_consistency(request.output_payload, rule)
                )

        return findings

    # ------------------------------------------------------------------
    # Financial consistency
    # ------------------------------------------------------------------

    @staticmethod
    def _check_financial_consistency(
        payload: dict, rule: dict
    ) -> List[ValidationFinding]:
        """Check that a computed field matches its expected formula.

        ``rule`` schema::

            {
                "type": "financial_consistency",
                "description": "grand_total must equal ...",
                "computed_field": "grand_total",
                "formula": {
                    "operands": ["subtotal", "discount", "tax"],
                    "expression": "subtotal - discount + tax"
                }
            }

        The expression is evaluated in a restricted safe-eval sandbox
        (no imports, no attribute access, only arithmetic on the listed
        operand values).
        """
        findings: List[ValidationFinding] = []
        computed_field = rule.get("computed_field")
        formula = rule.get("formula", {})
        description = rule.get(
            "description",
            f"Business rule violated: {computed_field}",
        )

        if not computed_field or not formula:
            return findings

        operands = formula.get("operands", [])
        expression = formula.get("expression")

        if not expression:
            return findings

        # Extract operand values from payload
        operand_values = {}
        for op in operands:
            val = payload.get(op)
            if val is None:
                # Operand missing — schema validation will catch required
                # fields; skip this rule.
                return findings
            operand_values[op] = val

        # Safely evaluate the expression
        try:
            expected_value = _safe_arithmetic_eval(expression, operand_values)
        except (ValueError, TypeError, ZeroDivisionError):
            # If we can't evaluate the formula, skip — don't create a
            # false finding.
            return findings

        submitted_value = payload.get(computed_field)
        if submitted_value is None:
            # Field missing — caught by schema validation
            return findings

        # Compare (use float comparison with tolerance for rounding)
        try:
            if not _values_equal(submitted_value, expected_value):
                findings.append(
                    ValidationFinding(
                        finding_id=uuid4(),
                        stage=StageEnum.business_logic,
                        severity=Severity.blocking,
                        description=(
                            f"{description} "
                            f"(submitted={submitted_value}, expected={expected_value})"
                        ),
                        field_path=computed_field,
                        repairable=Repairability.not_repairable,
                    )
                )
        except (TypeError, ValueError):
            # Types incomparable — create a finding
            findings.append(
                ValidationFinding(
                    finding_id=uuid4(),
                    stage=StageEnum.business_logic,
                    severity=Severity.blocking,
                    description=(
                        f"{description} "
                        f"(submitted={submitted_value}, expected={expected_value})"
                    ),
                    field_path=computed_field,
                    repairable=Repairability.not_repairable,
                )
            )

        return findings


# ------------------------------------------------------------------
# Safe arithmetic evaluator
# ------------------------------------------------------------------

_ALLOWED_NAMES = {"__builtins__": {}}


def _safe_arithmetic_eval(expression: str, variables: dict) -> float:
    """Evaluate a simple arithmetic expression with provided variables.

    Only supports: numbers, variable names, +, -, *, /, (), and
    parentheses.  No imports, no function calls, no attribute access.
    """
    # Validate that the expression contains only safe tokens
    import re

    # Allow: digits, decimal points, variable names, operators, parens, spaces
    safe_pattern = re.compile(
        r"^[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+(\.[0-9]+)?|[+\-*/() ]+$"
    )
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+(?:\.[0-9]+)?|[+\-*/()]+", expression)
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", token):
            continue
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", token):
            if token not in variables:
                raise ValueError(f"Unknown variable in expression: {token}")
            continue
        if re.fullmatch(r"[+\-*/()]+", token):
            continue
        raise ValueError(f"Unsafe token in expression: {token}")

    # Replace variable names with their values for eval
    eval_expr = expression
    for var_name, var_value in sorted(variables.items(), key=lambda x: -len(x[0])):
        eval_expr = eval_expr.replace(var_name, repr(float(var_value)))

    result = eval(eval_expr, _ALLOWED_NAMES)  # noqa: S307 — sandboxed
    return float(result)


def _values_equal(submitted: float, expected: float, tolerance: float = 0.01) -> bool:
    """Compare two numeric values with a small tolerance for floating-point."""
    return abs(float(submitted) - expected) < tolerance
