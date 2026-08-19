import os
import sys
import json
import base64
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

# x402 Client imports
from x402.client import x402Client
from x402.mechanisms.avm.exact import ExactAvmClientScheme
from x402.mechanisms.avm.signer import ClientAvmSigner
from x402.schemas import PaymentRequired

from algosdk import encoding

class PrivateKeySigner(ClientAvmSigner):
    """
    ClientAvmSigner implementation using a base64-encoded private key.
    Key format: 64 bytes = [32-byte seed][32-byte public key]
    """
    def __init__(self, private_key_b64: str):
        self._secret_key = base64.b64decode(private_key_b64)
        if len(self._secret_key) != 64:
            raise ValueError(f"Invalid key length: expected 64, got {len(self._secret_key)}")
        self._address = encoding.encode_address(self._secret_key[32:])
        self._signing_key = base64.b64encode(self._secret_key).decode()

    @property
    def address(self) -> str:
        return self._address

    def sign_transactions(self, unsigned_txns: list[bytes], indexes_to_sign: list[int]) -> list[bytes | None]:
        result: list[bytes | None] = []
        for i, txn_bytes in enumerate(unsigned_txns):
            if i not in indexes_to_sign:
                result.append(None)
                continue

            b64_txn = base64.b64encode(txn_bytes).decode("utf-8")
            txn_obj = encoding.msgpack_decode(b64_txn)
            signed_txn = txn_obj.sign(self._signing_key)
            
            signed_b64 = encoding.msgpack_encode(signed_txn)
            signed_bytes = base64.b64decode(signed_b64)
            result.append(signed_bytes)
        return result


async def run_e2e_test():
    load_dotenv(".env.client")
    
    private_key_b64 = os.environ.get("PAYER_PRIVATE_KEY")
    if not private_key_b64:
        print("ERROR: PAYER_PRIVATE_KEY is not set in .env.client")
        print("Please configure .env.client with your real Algorand TestNet private key (base64 encoded).")
        sys.exit(1)
        
    signer = PrivateKeySigner(private_key_b64)
    print(f"Payer Address: {signer.address}")
    
    api_url = "http://localhost:8000/api/v1/semantic-repair"
    
    payload = {
        "request": {
            "request_id": str(uuid4()),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "output_type": "json",
            "output_payload": {
                "name": "Alice",
                "inject_mock_semantic_repair": {"age": 30}
            },
            "schema_ref": "test_schema",
            "agent_identifier": "test_agent"
        },
        "policy": {
            "schema_id": str(uuid4()),
            "version": "1.0",
            "output_type": "json",
            "schema_definition": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["name", "age"]
            },
            "privacy_policy_ref": "default"
        }
    }

    print("\n--- STEP 1: Calling without payment ---")
    async with httpx.AsyncClient() as client:
        response = await client.post(api_url, json=payload)
        
        if response.status_code == 402:
            print(f"Received expected 402 Payment Required.")
            
            # The x402 specification requires the server to return the payment requirements
            # inside the Payment-Required header as a Base64 encoded JSON string.
            payment_required_b64 = response.headers.get("PAYMENT-REQUIRED")
            if not payment_required_b64:
                print("Failed! No PAYMENT-REQUIRED header found in 402 response.")
                print(response.headers)
                sys.exit(1)
                
            payment_required_json = base64.b64decode(payment_required_b64).decode("utf-8")
            payment_required_data = json.loads(payment_required_json)
            
            print("Payment requirements:")
            print(json.dumps(payment_required_data, indent=2))
        else:
            print(f"Failed! Expected 402, got {response.status_code}")
            print(response.text)
            sys.exit(1)

        print("\n--- STEP 2: Constructing payment via x402Client ---")
        x402_client = x402Client()
        
        # Register the AVM client scheme for Algorand Testnet
        scheme = ExactAvmClientScheme(signer=signer)
        x402_client.register("algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=", scheme)
        
        # Parse 402 response into PaymentRequired model
        payment_required_model = PaymentRequired(**payment_required_data)
        
        print("Creating payment payload (this will contact the GoPlausible facilitator and sign the tx)...")
        payment_payload = await x402_client.create_payment_payload(payment_required_model)
        
        # Encode the payload for the X-PAYMENT header
        x_payment_header = payment_payload.to_base64()
        print(f"Generated X-PAYMENT header (first 50 chars): {x_payment_header[:50]}...")
        
        print("\n--- STEP 3: Retrying with payment ---")
        response2 = await client.post(
            api_url, 
            json=payload, 
            headers={"X-PAYMENT": x_payment_header}
        )
        
        print(f"Status Code: {response2.status_code}")
        
        if response2.status_code == 200:
            print("Success! Response:")
            print(json.dumps(response2.json(), indent=2))
        else:
            print("Failed after payment!")
            print(response2.text)
            
if __name__ == "__main__":
    asyncio.run(run_e2e_test())
