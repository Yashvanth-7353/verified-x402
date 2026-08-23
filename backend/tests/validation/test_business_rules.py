"""
Tests for the business-rule validation stage.

Covers:
  - Financial consistency check (grand_total vs subtotal − discount + tax)
  - Deterministic repair does NOT automatically fix business-rule violations
  - Semantic repair is required for business-rule findings
  - Correct candidate passes re-validation
  - Incorrect candidate fails re-validation
"""

from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.models.verification import VerificationRequest, SchemaPolicy
from app.models.enums import (
    OutputType,
    VerificationOutcome,
    Severity,
    Repairability,
    ValidationStage,
)
from app.validation.engine import VerificationEngine
from app.repair.deterministic import DeterministicRepairEngine


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

FINANCIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "report_id": {"type": "string"},
        "customer": {"type": "string"},
        "currency": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price": {"type": "number"},
                    "total": {"type": "number"},
                },
                "required": ["description", "quantity", "unit_price", "total"],
            },
        },
        "subtotal": {"type": "number"},
        "discount": {"type": "number"},
        "tax": {"type": "number"},
        "grand_total": {"type": "number"},
    },
    "required": [
        "report_id",
        "customer",
        "currency",
        "line_items",
        "subtotal",
        "discount",
        "tax",
        "grand_total",
    ],
}

FINANCIAL_BUSINESS_RULES = [
    {
        "type": "financial_consistency",
        "description": "grand_total must equal (subtotal − discount) + tax",
        "computed_field": "grand_total",
        "formula": {
            "operands": ["subtotal", "discount", "tax"],
            "expression": "subtotal - discount + tax",
        },
    }
]

CORRECT_PAYLOAD = {
    "report_id": "FIN-Q3-2026-018",
    "customer": "Acme Robotics",
    "currency": "USD",
    "line_items": [
        {"description": "Hardware", "quantity": 10, "unit_price": 1200, "total": 12000},
        {"description": "Installation", "quantity": 2, "unit_price": 750, "total": 1500},
    ],
    "subtotal": 13500,
    "discount": 1000,
    "tax": 1250,
    "grand_total": 13750,  # correct
}

INCONSISTENT_PAYLOAD = {
    "report_id": "FIN-Q3-2026-018",
    "customer": "Acme Robotics",
    "currency": "USD",
    "line_items": [
        {"description": "Hardware", "quantity": 10, "unit_price": 1200, "total": 12000},
        {"description": "Installation", "quantity": 2, "unit_price": 750, "total": 1500},
    ],
    "subtotal": 13500,
    "discount": 1000,
    "tax": 1250,
    "grand_total": 14750,  # WRONG: should be 13750
}

INCORRECT_CANDIDATE = {
    "report_id": "FIN-Q3-2026-018",
    "customer": "Acme Robotics",
    "currency": "USD",
    "line_items": [
        {"description": "Hardware", "quantity": 10, "unit_price": 1200, "total": 12000},
        {"description": "Installation", "quantity": 2, "unit_price": 750, "total": 1500},
    ],
    "subtotal": 13500,
    "discount": 1000,
    "tax": 1250,
    "grand_total": 15000,  # WRONG: still incorrect
}


@pytest.fixture
def engine():
    return VerificationEngine()


@pytest.fixture
def repair_engine():
    return DeterministicRepairEngine()


@pytest.fixture
def policy_with_rules():
    return SchemaPolicy(
        schema_id=uuid4(),
        version="1.0",
        output_type=OutputType.json,
        schema_definition=FINANCIAL_SCHEMA,
        privacy_policy_ref="default",
        business_rules=FINANCIAL_BUSINESS_RULES,
    )


@pytest.fixture
def policy_without_rules():
    return SchemaPolicy(
        schema_id=uuid4(),
        version="1.0",
        output_type=OutputType.json,
        schema_definition=FINANCIAL_SCHEMA,
        privacy_policy_ref="default",
    )


def _make_request(payload: dict) -> VerificationRequest:
    return VerificationRequest(
        request_id=uuid4(),
        submitted_at=datetime.now(timezone.utc),
        output_type=OutputType.json,
        output_payload=payload,
        schema_ref="financial-report.v1",
        agent_identifier="test-agent",
    )


# ------------------------------------------------------------------
# Test 1: Correct financial report passes
# ------------------------------------------------------------------

class TestCorrectFinancialReport:
    def test_correct_report_verified(self, engine, policy_with_rules):
        """A financially consistent report should be verified immediately."""
        request = _make_request(CORRECT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        assert result.outcome == VerificationOutcome.verified

    def test_no_business_findings_for_correct_report(self, engine, policy_with_rules):
        request = _make_request(CORRECT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        business_findings = [
            f for f in result.findings if f.stage == ValidationStage.business_logic
        ]
        assert len(business_findings) == 0


# ------------------------------------------------------------------
# Test 2: Inconsistent financial report produces a business-rule finding
# ------------------------------------------------------------------

class TestInconsistentFinancialReport:
    def test_inconsistent_report_rejected(self, engine, policy_with_rules):
        """An inconsistent grand_total should be rejected."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        assert result.outcome == VerificationOutcome.rejected

    def test_business_logic_finding_present(self, engine, policy_with_rules):
        """The finding must be classified as business_logic / blocking / not_repairable."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        business_findings = [
            f for f in result.findings if f.stage == ValidationStage.business_logic
        ]
        assert len(business_findings) == 1
        finding = business_findings[0]
        assert finding.severity == Severity.blocking
        assert finding.repairable == Repairability.not_repairable
        assert "grand_total" in finding.description
        assert "13750" in finding.description
        assert "14750" in finding.description

    def test_no_schema_findings_for_consistent_types(self, engine, policy_with_rules):
        """All primitive types are correct — only the business rule should fail."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        schema_findings = [
            f
            for f in result.findings
            if f.stage == ValidationStage.schema
            and f.severity == Severity.blocking
        ]
        assert len(schema_findings) == 0


# ------------------------------------------------------------------
# Test 3: Deterministic repair does NOT fix business-rule violations
# ------------------------------------------------------------------

class TestDeterministicRepairDoesNotFixBusinessRules:
    def test_deterministic_repair_returns_none(
        self, engine, repair_engine, policy_with_rules
    ):
        """Deterministic repair must not touch the business-rule-violating payload."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")

        repaired_payload, repair_info = repair_engine.attempt_repair(
            request, policy_with_rules, result.findings
        )

        # No repair should be attempted — types are already correct
        assert repair_info is None
        assert repaired_payload == INCONSISTENT_PAYLOAD

    def test_orchestrator_skips_deterministic_for_business_logic_only(
        self, policy_with_rules
    ):
        """When only business_logic findings are blocking, orchestrator
        should NOT attempt deterministic repair."""
        from app.services.orchestrator import VerificationOrchestrator

        orchestrator = VerificationOrchestrator()
        request = _make_request(INCONSISTENT_PAYLOAD)
        result, receipt, repaired_output = orchestrator.process(request, policy_with_rules)

        # Should be rejected, no repair
        assert result.outcome == VerificationOutcome.rejected
        assert result.repair_info is None
        assert repaired_output is None

    def test_no_business_rules_means_no_finding(self, engine, policy_without_rules):
        """Without business rules, the same payload should be verified."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_without_rules, "1.0.0")
        assert result.outcome == VerificationOutcome.verified


# ------------------------------------------------------------------
# Test 4: Correct candidate passes re-validation
# ------------------------------------------------------------------

class TestReValidationWithCorrectCandidate:
    def test_correct_candidate_revalidated(self, engine, policy_with_rules):
        """A candidate with grand_total=13750 should pass re-validation."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        assert result.outcome == VerificationOutcome.rejected

        # Simulate a correct candidate
        repaired_request = request.model_copy()
        repaired_request.output_payload = CORRECT_PAYLOAD
        revalidation = engine.verify_request(repaired_request, policy_with_rules, "1.0.0")
        assert revalidation.outcome == VerificationOutcome.verified
        business_findings = [
            f for f in revalidation.findings if f.stage == ValidationStage.business_logic
        ]
        assert len(business_findings) == 0


# ------------------------------------------------------------------
# Test 5: Incorrect candidate fails re-validation
# ------------------------------------------------------------------

class TestReValidationWithIncorrectCandidate:
    def test_incorrect_candidate_still_rejected(self, engine, policy_with_rules):
        """A candidate with grand_total=15000 should still fail."""
        request = _make_request(INCONSISTENT_PAYLOAD)
        result = engine.verify_request(request, policy_with_rules, "1.0.0")
        assert result.outcome == VerificationOutcome.rejected

        # Simulate an incorrect candidate
        repaired_request = request.model_copy()
        repaired_request.output_payload = INCORRECT_CANDIDATE
        revalidation = engine.verify_request(repaired_request, policy_with_rules, "1.0.0")
        assert revalidation.outcome == VerificationOutcome.rejected
        business_findings = [
            f for f in revalidation.findings if f.stage == ValidationStage.business_logic
        ]
        assert len(business_findings) == 1


# ------------------------------------------------------------------
# Test 6: Business rule with no rules is a no-op
# ------------------------------------------------------------------

class TestNoBusinessRules:
    def test_policy_without_business_rules(self, engine):
        """Policy without business_rules should work identically to before."""
        policy = SchemaPolicy(
            schema_id=uuid4(),
            version="1.0",
            output_type=OutputType.json,
            schema_definition={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            privacy_policy_ref="default",
        )
        request = _make_request({"name": "Alice"})
        result = engine.verify_request(request, policy, "1.0.0")
        assert result.outcome == VerificationOutcome.verified
        business_findings = [
            f for f in result.findings if f.stage == ValidationStage.business_logic
        ]
        assert len(business_findings) == 0
