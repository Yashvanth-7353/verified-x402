from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.errors import VerificationError, verification_error_handler
from app.api.router import api_router

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Local-first verification layer for AI agents",
    version="0.1.0",
)

app.add_exception_handler(VerificationError, verification_error_handler)
app.include_router(api_router)