import logging
from app.core.config import settings

# Configure root logger based on settings
def setup_logging():
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

# Initialize logging immediately so other modules can import the logger
setup_logging()
# Export a module‑level logger instance
logger = logging.getLogger("verified-x402")
