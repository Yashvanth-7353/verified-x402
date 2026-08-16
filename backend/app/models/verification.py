from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from app.models.enums import (
    OutputType,
    ValidationStage,
    Severity,
    Repairability,
    RepairType,
    VerificationOutcome
)

class VerificationRequest(BaseModel):
    request_id: UUID
    submitted_at: datetime
    output_type: OutputType
    output_payload: dict[str, Any]
    schema_ref: str
    agent_identifier: str
    privacy_class_hint: Optional[str] = None

class SchemaPolicy(BaseModel):
    schema_id: UUID
    version: str
    output_type: OutputType
    schema_definition: dict[str, Any]
    deterministic_repair_rules_ref: Optional[str] = None
    sql_safety_ruleset_ref: Optional[str] = None
    privacy_policy_ref: str

class ValidationFinding(BaseModel):
    finding_id: UUID
    stage: ValidationStage
    severity: Severity
    description: str
    field_path: Optional[str] = None
    repairable: Repairability

class RepairInfo(BaseModel):
    repair_id: UUID
    repair_type: RepairType
    findings_addressed: list[str]
    pre_repair_output_hash: str
    post_repair_output_hash: str
    deterministic_rule_refs: Optional[list[str]] = None
    semantic_repair_provider_ref: Optional[str] = None
    payment_ref: Optional[str] = None

class VerificationResult(BaseModel):
    result_id: UUID
    request_ref: str
    findings: list[ValidationFinding]
    repair_info: Optional[RepairInfo] = None
    outcome: VerificationOutcome
    rejection_reasons: Optional[list[str]] = None
    validator_version: str
    completed_at: datetime

class VerificationReceipt(BaseModel):
    receipt_id: UUID
    request_id_ref: str
    outcome: VerificationOutcome
    output_hash: str
    schema_ref_and_version: str
    repair_summary_hash: Optional[str] = None
    validator_version: str
    issued_at: datetime
    receipt_hash: str
    signature: Optional[Any] = None
