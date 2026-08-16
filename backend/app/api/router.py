from fastapi import APIRouter
from app.api import health, verify
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(
    verify.router,
    prefix=settings.API_V1_STR,
    tags=["verification"],
)
