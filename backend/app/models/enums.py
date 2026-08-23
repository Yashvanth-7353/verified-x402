from enum import Enum

class OutputType(str, Enum):
    json = "json"
    sql = "sql"
    function_call_args = "function_call_args"

class ValidationStage(str, Enum):
    schema = "schema"
    type = "type"
    syntax = "syntax"
    sql_safety = "sql_safety"
    privacy = "privacy"
    business_logic = "business_logic"

class Severity(str, Enum):
    info = "info"
    warning = "warning"
    blocking = "blocking"

class Repairability(str, Enum):
    deterministic = "deterministic"
    semantic = "semantic"
    not_repairable = "not_repairable"

class RepairType(str, Enum):
    deterministic = "deterministic"
    semantic = "semantic"
    none = "none"

class PaymentStatus(str, Enum):
    pending = "pending"
    verified = "verified"
    settled = "settled"
    failed = "failed"

class VerificationOutcome(str, Enum):
    verified = "verified"
    verified_repaired = "verified_repaired"
    rejected = "rejected"

class AnchoringStatus(str, Enum):
    unanchored = "unanchored"
    pending = "pending"
    anchored = "anchored"
