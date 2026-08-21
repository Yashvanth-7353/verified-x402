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
