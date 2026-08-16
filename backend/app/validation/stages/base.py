from abc import ABC, abstractmethod
from typing import List
from app.models.verification import VerificationRequest, SchemaPolicy, ValidationFinding

class ValidationStage(ABC):
    """Abstract base class for validation stages."""
    
    @abstractmethod
    def validate(self, request: VerificationRequest, policy: SchemaPolicy) -> List[ValidationFinding]:
        """Perform validation and return a list of findings."""
        pass
