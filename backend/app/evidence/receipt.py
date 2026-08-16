from uuid import uuid4
from datetime import datetime, timezone
from copy import deepcopy

from app.models.verification import VerificationRequest, SchemaPolicy, VerificationResult, VerificationReceipt
from app.evidence.hasher import hash_data

class ReceiptService:
    def generate_receipt(self, request: VerificationRequest, policy: SchemaPolicy, result: VerificationResult, final_payload: dict) -> VerificationReceipt:
        # Note: The original output hash is captured in the repair result if a repair occurred, 
        # or it is equal to final_payload hash. We adhere strictly to the Phase 1 model.
        output_hash = hash_data(final_payload)
        
        repair_summary_hash = None
        if result.repair_info:
            repair_summary_hash = hash_data(result.repair_info)
            
        receipt = VerificationReceipt(
            receipt_id=uuid4(),
            request_id_ref=str(request.request_id),
            outcome=result.outcome,
            output_hash=output_hash,
            schema_ref_and_version=f"{policy.schema_id}@{policy.version}",
            repair_summary_hash=repair_summary_hash,
            validator_version=result.validator_version,
            issued_at=datetime.now(timezone.utc),
            receipt_hash="", # Placeholder
            signature=None
        )
        
        # Compute the hash of the receipt itself, excluding the receipt_hash and signature fields
        receipt_dict = receipt.model_dump(mode="json")
        receipt_dict.pop("receipt_hash", None)
        receipt_dict.pop("signature", None)
        receipt.receipt_hash = hash_data(receipt_dict)
        
        return receipt

    def verify_receipt(self, receipt: VerificationReceipt, request: VerificationRequest, policy: SchemaPolicy, result: VerificationResult, final_payload: dict) -> bool:
        """
        Locally verifies the receipt against the supplied evidence.
        """
        # 1. Verify receipt hash itself
        receipt_dict = receipt.model_dump(mode="json")
        receipt_dict.pop("receipt_hash", None)
        receipt_dict.pop("signature", None)
        expected_receipt_hash = hash_data(receipt_dict)
        
        if receipt.receipt_hash != expected_receipt_hash:
            return False
            
        # 2. Verify output hash
        expected_output_hash = hash_data(final_payload)
        if receipt.output_hash != expected_output_hash:
            return False
            
        # 3. Verify repair summary hash
        if result.repair_info:
            expected_repair_hash = hash_data(result.repair_info)
            if receipt.repair_summary_hash != expected_repair_hash:
                return False
        elif receipt.repair_summary_hash is not None:
            return False
            
        # 4. Verify basic identifiers
        if receipt.request_id_ref != str(request.request_id):
            return False
            
        expected_schema_ref = f"{policy.schema_id}@{policy.version}"
        if receipt.schema_ref_and_version != expected_schema_ref:
            return False
            
        if receipt.outcome != result.outcome:
            return False
            
        return True
