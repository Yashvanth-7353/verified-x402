from pydantic_settings import BaseSettings, SettingsConfigDict

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

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

settings = Settings()
