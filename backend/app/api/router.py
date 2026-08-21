from fastapi import APIRouter
from app.api import health, verify, semantic, anchor, receipt, records, proof
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(
    verify.router,
    prefix=settings.API_V1_STR,
    tags=["verification"],
)
api_router.include_router(
    semantic.router,
    prefix=settings.API_V1_STR,
    tags=["semantic-repair"],
)
api_router.include_router(
    anchor.router,
    prefix=settings.API_V1_STR,
    tags=["anchoring"],
)
api_router.include_router(
    receipt.router,
    prefix=settings.API_V1_STR,
    tags=["receipt-verification"],
)
api_router.include_router(
    records.router,
    prefix=settings.API_V1_STR,
    tags=["records"],
)
api_router.include_router(
    proof.router,
    prefix=settings.API_V1_STR,
    tags=["merkle-proof"],
)
