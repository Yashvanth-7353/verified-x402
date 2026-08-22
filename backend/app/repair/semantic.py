import json
import hashlib
from typing import Tuple, List, Optional, Protocol
from uuid import uuid4

from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding, RepairInfo
from app.models.enums import RepairType

class SemanticRepairProvider(Protocol):
    def request_repair(self, payload: dict, policy: SchemaPolicy, findings: List[ValidationFinding]) -> Optional[dict]:
        """Requests a semantic repair from the provider."""
        ...

class MockSemanticProvider:
    """A deterministic mock provider for testing and MVP without commercial dependencies."""
    def request_repair(self, payload: dict, policy: SchemaPolicy, findings: List[ValidationFinding]) -> Optional[dict]:
        # For testing, we look for a specific key "inject_mock_semantic_repair" in the payload
        # to trigger a deterministic repair. If missing, we return None (failure).
        if "inject_mock_semantic_repair" in payload:
            repaired = dict(payload)
            repaired.update(payload["inject_mock_semantic_repair"])
            del repaired["inject_mock_semantic_repair"]
            return repaired
        return None

def get_default_provider() -> SemanticRepairProvider:
    """Return the configured semantic repair provider.
    
    Uses GroqSemanticProvider when SEMANTIC_REPAIR_PROVIDER=groq and GROQ_API_KEY is set.
    Falls back to MockSemanticProvider for testing, offline demo, or when Groq is not configured.
    """
    from app.core.config import settings
    
    if settings.SEMANTIC_REPAIR_PROVIDER == "groq" and settings.GROQ_API_KEY:
        try:
            from app.repair.groq_provider import GroqSemanticProvider
            return GroqSemanticProvider()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to initialize GroqSemanticProvider (%s); falling back to MockSemanticProvider", e
            )
            return MockSemanticProvider()
    return MockSemanticProvider()


class SemanticRepairEngine:
    def __init__(self, provider: SemanticRepairProvider = None):
        self.provider = provider or get_default_provider()

    def attempt_repair(self, request: VerificationRequest, policy: SchemaPolicy, findings: List[ValidationFinding]) -> Tuple[dict, Optional[RepairInfo]]:
        """
        Attempts to semantically repair the payload using the configured provider.
        """
        if not findings:
            return request.output_payload, None

        pre_repair_str = json.dumps(request.output_payload, sort_keys=True)
        pre_repair_hash = hashlib.sha256(pre_repair_str.encode("utf-8")).hexdigest()

        # Isolate provider boundary (passing only necessary data)
        # In a real implementation with privacy filtering, the payload would be filtered here
        # before passing it to the provider. For now, we pass the payload directly.
        candidate_payload = self.provider.request_repair(request.output_payload, policy, findings)
        
        if candidate_payload is None:
            return request.output_payload, None

        post_repair_str = json.dumps(candidate_payload, sort_keys=True)
        post_repair_hash = hashlib.sha256(post_repair_str.encode("utf-8")).hexdigest()

        if pre_repair_hash == post_repair_hash:
            return request.output_payload, None

        addressed_finding_ids = [str(f.finding_id) for f in findings]

        repair_info = RepairInfo(
            repair_id=uuid4(),
            repair_type=RepairType.semantic,
            findings_addressed=addressed_finding_ids,
            pre_repair_output_hash=pre_repair_hash,
            post_repair_output_hash=post_repair_hash,
            semantic_repair_provider_ref=self.provider.__class__.__name__
        )

        return candidate_payload, repair_info
