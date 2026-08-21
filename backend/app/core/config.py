from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "Verified"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # x402 Payment Configuration
    AVM_ADDRESS: str = "SOME_ADDRESS_TO_RECEIVE_PAYMENT"
    FACILITATOR_URL: str = "https://facilitator.goplausible.xyz"
    ALGORAND_NETWORK: str = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
    SEMANTIC_REPAIR_PRICE: str = "1000000" # 1 ALGO in microAlgos for development

    # Phase 9: Local Verification Record Store
    DATABASE_PATH: str = ""  # Empty = use default backend/data/verified.db

    # Phase 10: Merkle Anchoring
    ANCHOR_PRIVATE_KEY: str = ""  # Base64-encoded Algorand private key for anchoring
    ANCHOR_ALGOD_ADDRESS: str = "https://testnet-api.algonode.cloud"  # Algorand TestNet node
    ANCHOR_ALGOD_TOKEN: str = ""  # Algod API token (empty for public nodes)
    MERKLE_BATCH_SIZE: int = 10  # Max records per anchor batch

    # Phase 12: Receipt Signing (Ed25519)
    RECEIPT_SIGNING_PRIVATE_KEY: str = ""  # Base64-encoded Ed25519 private key (32 bytes)
    RECEIPT_SIGNING_PUBLIC_KEY: str = ""   # Base64-encoded Ed25519 public key (for verification)

    # Phase 14: CORS & Frontend Readiness
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"  # Comma-separated allowed origins
    MAX_REQUEST_BYTES: int = 1_048_576  # 1 MB max request body

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    @property
    def resolved_database_path(self) -> str:
        """Resolve the database path, falling back to backend/data/verified.db."""
        if self.DATABASE_PATH:
            return self.DATABASE_PATH
        backend_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = backend_dir / "data"
        data_dir.mkdir(exist_ok=True)
        return str(data_dir / "verified.db")

settings = Settings()
